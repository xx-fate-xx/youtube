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


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def chapters(ws: Workspace) -> list[tuple[float, str]]:
    """YouTube chapters from section starts: first at 0:00, >= 3 chapters, each >= 10 s.

    Returns [] when the rules cannot be met (YouTube would ignore them anyway)."""
    from studio.models import NarrationTrack
    from studio.storyboard import load_storyboard

    if not (ws.storyboard_file.exists() and ws.narration_file.exists()):
        return []
    board = load_storyboard(ws)
    track = read_model(ws.narration_file, NarrationTrack)
    timing = {s.scene_id: s for s in track.scenes}
    out: list[tuple[float, str]] = []
    for sc in board.scenes:
        if sc.starts_section and sc.id in timing:
            start = 0.0 if not out else timing[sc.id].start
            if out and start - out[-1][0] < 10:
                continue  # too close to the previous chapter: merge into it
            out.append((start, sc.section_heading))
    if len(out) < 3 or track.duration_s - out[-1][0] < 10:
        return out if len(out) >= 3 and track.duration_s - out[-1][0] >= 10 else []
    return out


DISCLOSURE_LINE = ("Narration uses a synthetic AI voice. Script researched and fact-checked "
                   "by a human editor. Diagrams are schematic, not to scale.")


def build_description(episode: Episode, ws: Workspace, channel: ChannelProfile, *,
                      synthetic_voice: bool) -> str:
    pack = load_pack(ws)
    manifest = load_manifest(ws, episode.id)
    lines = [episode.title, ""]
    chaps = chapters(ws)
    if chaps:
        lines += ["Chapters:"] + [f"{fmt_ts(t)} {title}" for t, title in chaps] + [""]
    used: list[str] = []  # claims actually spoken in the video or a Short
    if ws.script_file.exists():
        from studio.editorial import load_script
        from studio.shorts import load_shorts

        sc = load_script(ws)
        used = [c for sec in sc.sections for para in sec.paragraphs for c in para.claim_ids]
        used += [c for sh in load_shorts(ws) for c in sh.claim_ids]
    cited: list[str] = []
    for cid in used:
        try:
            for sid in pack.claim(cid).source_ids:
                if sid not in cited:
                    cited.append(sid)
        except KeyError:
            continue
    sources = [pack.source(sid) for sid in cited] if cited else pack.sources
    lines += ["Sources:"]
    for s in sources:
        pub = f" ({s.publisher})" if s.publisher else ""
        lines.append(f"- {s.title}{pub}: {s.url}")
    credits = attributions(manifest)
    if credits:
        lines += ["", "Credits:"] + [f"- {c}" for c in credits]
    if channel.key == "business_uncovered":
        lines += ["", "This video is for education only and is not investment advice."]
    if synthetic_voice:
        lines += ["", DISCLOSURE_LINE]
    lines += ["", "Corrections: tell us in the comments and we will check the source."]
    return "\n".join(lines)[:5000]


def build_metadata(episode: Episode, ws: Workspace, channel: ChannelProfile,
                   decision: ReviewDecision | None) -> dict:
    from studio.models import NarrationTrack

    synthetic = False
    if ws.narration_file.exists():
        synthetic = read_model(ws.narration_file, NarrationTrack).provider not in {
            "user_recording", "mock_voice"}
    srt = ws.render / f"{episode.id}.en.srt"
    thumb = ws.render / "thumbnail_draft.png"
    return {
        "title": episode.title[:100],
        "description": build_description(episode, ws, channel, synthetic_voice=synthetic),
        "tags": channel.default_tags,
        "privacyStatus": "private",
        "defaultLanguage": channel.language,
        "containsSyntheticMedia": bool(decision and decision.ai_disclosure_altered_content),
        "channel": channel.key,
        "youtube_channel_id": channel.youtube_channel_id or None,
        "captions_file": str(srt) if srt.exists() else None,
        "thumbnail_file": str(thumb) if thumb.exists() else None,
        "chapters": [[fmt_ts(t), title] for t, title in chapters(ws)],
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
        captions = publisher.upload_captions(result["id"], srt)
        shorts_uploaded = _upload_shorts_private(publisher, ws, episode, result["id"])
        episode.remote_video_id = result["id"]
        episode.youtube_privacy = "private"
        transition(session, episode, EpisodeState.PRIVATE_UPLOADED,
                   note=f"uploaded private as {result['id']}")
        receipt = ws.release / "upload_receipt.json"
        atomic_write_text(receipt, redact({"video": result, "captions": captions,
                                           "shorts": shorts_uploaded}) + "\n")
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
        "6. Chapters are already in the description (first line 0:00).\n"
        "7. Upload each Short from shorts/ the same way (Private), adding the episode link.\n"
        "8. Then record the video id: `studio record-upload <ep> <video-id>`.\n"
    ))
    return PublishResult("release_folder", rel)


def _upload_shorts_private(publisher: YouTubePublisher, ws: Workspace, episode: Episode,
                           long_video_id: str) -> list[dict]:
    """Each rendered Short as its own PRIVATE video, linking to the long episode."""
    import json as _json

    done = []
    for short_dir in sorted(p for p in ws.shorts.glob("*") if p.is_dir() and p.name != "frames"):
        mp4 = next(iter(sorted(short_dir.glob("*_master.mp4"))), None)
        meta_file = short_dir / "metadata.json"
        if not mp4 or not meta_file.exists():
            continue
        meta = _json.loads(meta_file.read_text(encoding="utf-8"))
        desc = (meta.get("description", "") +
                f"\n\nFull episode: https://youtu.be/{long_video_id}")
        res = publisher.upload(mp4, title=meta.get("title", short_dir.name),
                               description=desc, tags=["Shorts"])
        srt = next(iter(sorted(short_dir.glob("*.srt"))), None)
        if srt:
            publisher.upload_captions(res["id"], srt)
        meta["remote_video_id"] = res["id"]
        atomic_write_json(meta_file, meta)
        done.append({"short": short_dir.name, "id": res["id"]})
    return done


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
