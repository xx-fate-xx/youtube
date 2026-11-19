"""Publishing: private-only upload behind a feature flag, or a local release folder."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from studio.assets import attributions, load_manifest
from studio.channels import ChannelProfile
from studio.config import Settings
from studio.episodes import Workspace
from studio.fsutil import atomic_write_json, atomic_write_text, read_model, sha256_file
from studio.models import Episode, EpisodeState, ReviewDecision, ReviewDecisionKind
from studio.providers.youtube import (
    GoogleYouTubeClient,
    YouTubeClient,
    YouTubePublisher,
    redact,
)
from studio.research import load_pack
from studio.state import transition


class PublishBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishResult:
    mode: str  # youtube_private | release_folder
    path: Path
    remote_video_id: str | None = None


def require_approved_artifact(episode: Episode, ws: Workspace) -> ReviewDecision:
    if EpisodeState(episode.state) != EpisodeState.APPROVED:
        raise PublishBlocked(f"Episode is '{episode.state}'; upload requires 'approved'.")
    if not ws.decision_file.exists():
        raise PublishBlocked("No review decision artifact found.")
    decision = read_model(ws.decision_file, ReviewDecision)
    if decision.decision != ReviewDecisionKind.APPROVE:
        raise PublishBlocked(f"Latest review decision is '{decision.decision.value}'.")
    video = Path(decision.video_path)
    if not video.exists():
        raise PublishBlocked(f"Approved video missing: {video}")
    if sha256_file(video) != decision.video_sha256:
        raise PublishBlocked("Video changed after approval (sha256 mismatch). Re-review it.")
    return decision


def build_metadata(episode: Episode, ws: Workspace, channel: ChannelProfile,
                   decision: ReviewDecision) -> dict:
    pack = load_pack(ws)
    manifest = load_manifest(ws, episode.id)
    lines = [f"{episode.title}", ""]
    lines += ["Sources:"]
    for s in pack.sources:
        lines.append(f"- {s.title} ({s.publisher}): {s.url}")
    credits = attributions(manifest)
    if credits:
        lines += ["", "Credits:"] + [f"- {c}" for c in credits]
    if channel.key == "business_uncovered":
        lines += ["", "This video is for education only and is not investment advice."]
    lines += ["", "Corrections: tell us in the comments and we will check the source."]
    return {
        "title": episode.title[:100],
        "description": "\n".join(lines)[:5000],
        "tags": channel.default_tags,
        "privacyStatus": "private",
        "defaultLanguage": channel.language,
        "containsSyntheticMedia": bool(decision.ai_disclosure_altered_content),
        "channel": channel.key,
        "youtube_channel_id": channel.youtube_channel_id or None,
    }


def publish_private(settings: Settings, session: Session, episode: Episode, ws: Workspace,
                    channel: ChannelProfile, *, client: YouTubeClient | None = None
                    ) -> PublishResult:
    decision = require_approved_artifact(episode, ws)
    video = Path(decision.video_path)
    meta = build_metadata(episode, ws, channel, decision)
    srt = ws.render / f"{episode.id}.en.srt"
    thumb = ws.render / "thumbnail_draft.png"

    use_youtube = client is not None or (settings.enable_youtube
                                         and settings.youtube_client_secrets is not None
                                         and settings.youtube_client_secrets.exists())
    if use_youtube:
        if client is None:  # pragma: no cover - needs real OAuth
            client = GoogleYouTubeClient(settings.youtube_client_secrets,  # type: ignore[arg-type]
                                         settings.youtube_token_file)
        publisher = YouTubePublisher(client)
        result = publisher.upload(video, title=meta["title"], description=meta["description"],
                                  tags=meta["tags"], default_language="en",
                                  contains_synthetic_media=meta["containsSyntheticMedia"],
                                  thumbnail=thumb if thumb.exists() else None)
        episode.remote_video_id = result["id"]
        episode.youtube_privacy = "private"
        transition(session, episode, EpisodeState.PRIVATE_UPLOADED,
                   note=f"uploaded private as {result['id']}")
        receipt = ws.release / "upload_receipt.json"
        atomic_write_text(receipt, redact(result) + "\n")
        return PublishResult("youtube_private", receipt, result["id"])

    # No OAuth: export a publish-ready local package. State stays 'approved'.
    rel = ws.release / datetime.now().strftime("%Y%m%d-%H%M%S")
    rel.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, rel / video.name)
    for extra in (srt, thumb, ws.research / "sources.md", ws.manifest_file, ws.decision_file):
        if extra.exists():
            shutil.copy2(extra, rel / extra.name)
    for short_dir in sorted(p for p in ws.shorts.iterdir() if p.is_dir() and p.name != "frames"):
        for f in list(short_dir.glob("*_master.mp4")) + list(short_dir.glob("*.srt")) + \
                list(short_dir.glob("metadata.json")):
            dest = rel / "shorts" / short_dir.name
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest / f.name)
    atomic_write_json(rel / "metadata.json", meta)
    atomic_write_text(rel / "UPLOAD_INSTRUCTIONS.md", (
        "# Manual upload\n\n"
        "1. In YouTube Studio choose Create -> Upload video, select the MP4.\n"
        "2. Paste title/description/tags from metadata.json.\n"
        "3. Visibility: **Private**. Do not schedule or publish until you decide to.\n"
        "4. Upload the .srt under Subtitles, and the thumbnail.\n"
        f"5. Altered or synthetic content disclosure: "
        f"{'YES' if meta['containsSyntheticMedia'] else 'NO'} (operator decision at review).\n"
        "6. Then record the video id: `studio publish record-remote <ep> <video-id>`.\n"
    ))
    return PublishResult("release_folder", rel)


def record_manual_upload(session: Session, episode: Episode, ws: Workspace,
                         video_id: str) -> None:
    require_approved_artifact(episode, ws)
    episode.remote_video_id = video_id
    episode.youtube_privacy = "private"
    transition(session, episode, EpisodeState.PRIVATE_UPLOADED,
               note=f"manually uploaded private as {video_id}")


def change_visibility(settings: Settings, session: Session, episode: Episode, *,
                      visibility: str, confirm_episode_id: str,
                      publish_at: datetime | None = None,
                      client: YouTubeClient | None = None) -> dict:
    """Separate, explicit operator action. Never called by the pipeline."""
    if EpisodeState(episode.state) not in {EpisodeState.PRIVATE_UPLOADED, EpisodeState.PUBLISHED}:
        raise PublishBlocked("Visibility can only change after a private upload.")
    if not episode.remote_video_id:
        raise PublishBlocked("No remote video id recorded.")
    if client is None:
        if not (settings.enable_youtube and settings.youtube_client_secrets):
            raise PublishBlocked("YouTube integration is disabled; change visibility in "
                                 "YouTube Studio manually.")
        client = GoogleYouTubeClient(settings.youtube_client_secrets,  # pragma: no cover
                                     settings.youtube_token_file)
    result = YouTubePublisher(client).set_visibility(
        episode.remote_video_id, episode_id=episode.id, confirm_episode_id=confirm_episode_id,
        visibility=visibility, publish_at=publish_at)
    episode.youtube_privacy = visibility
    if visibility in {"public", "scheduled"} and episode.state != EpisodeState.PUBLISHED.value:
        transition(session, episode, EpisodeState.PUBLISHED, note=f"visibility={visibility}")
    else:
        session.add(episode)
    return result
