"""Episode creation, lookup and per-episode workspace layout."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, col, select

from studio.channels import ChannelProfile
from studio.config import Settings
from studio.models import Episode, EpisodeState, StateTransition


def slugify(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) > max_len:
        cut = slug[: max_len + 1]
        slug = cut[: cut.rfind("-")] if "-" in cut else slug[:max_len]
    return slug.strip("-") or "episode"


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def research(self) -> Path:
        return self.root / "research"

    @property
    def script(self) -> Path:
        return self.root / "script"

    @property
    def storyboard(self) -> Path:
        return self.root / "storyboard"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def audio(self) -> Path:
        return self.root / "audio"

    @property
    def render(self) -> Path:
        return self.root / "render"

    @property
    def shorts(self) -> Path:
        return self.root / "shorts"

    @property
    def review(self) -> Path:
        return self.root / "review"

    @property
    def release(self) -> Path:
        return self.root / "release"

    # well-known artifact files
    @property
    def research_file(self) -> Path:
        return self.research / "research_pack.json"

    @property
    def script_file(self) -> Path:
        return self.script / "script.json"

    @property
    def storyboard_file(self) -> Path:
        return self.storyboard / "storyboard.json"

    @property
    def manifest_file(self) -> Path:
        return self.assets / "asset_manifest.json"

    @property
    def narration_file(self) -> Path:
        return self.audio / "narration.json"

    @property
    def shorts_file(self) -> Path:
        return self.shorts / "shorts.json"

    @property
    def decision_file(self) -> Path:
        return self.review / "decision.json"

    def ensure(self) -> Workspace:
        for d in (self.research, self.script, self.storyboard, self.assets, self.audio,
                  self.render, self.shorts, self.review, self.release):
            d.mkdir(parents=True, exist_ok=True)
        return self


def workspace(settings: Settings, episode: Episode) -> Workspace:
    return Workspace(settings.projects_dir / episode.channel / episode.id)


def create_episode(
    session: Session,
    settings: Settings,
    channel: ChannelProfile,
    topic: str,
    *,
    title: str | None = None,
    target_minutes: float = 10.0,
    sample: str | None = None,
) -> Episode:
    lo, hi = channel.runtime_minutes
    if not lo <= target_minutes <= hi:
        raise ValueError(f"target_minutes must be within {lo}-{hi} for {channel.name}")
    existing = session.exec(select(Episode).where(Episode.channel == channel.key)).all()
    for ep in existing:
        if slugify(ep.topic) == slugify(topic):
            raise ValueError(
                f"Episode {ep.id} already covers this topic on {channel.name}. "
                "Avoid materially repetitive videos; edit the existing episode instead."
            )
    number = len(existing) + 1
    episode_id = f"{channel.id_prefix}-{number:04d}-{slugify(topic, 32)}"
    episode = Episode(
        id=episode_id,
        channel=channel.key,
        topic=topic,
        title=title or topic,
        state=EpisodeState.IDEA.value,
        target_minutes=target_minutes,
        sample=sample,
    )
    session.add(episode)
    session.add(StateTransition(episode_id=episode_id, from_state="", to_state="idea",
                                note="created"))
    session.flush()
    workspace(settings, episode).ensure()
    return episode


def get_episode(session: Session, ref: str) -> Episode:
    """Look up by full id or by unique prefix (e.g. 'ee-0001')."""
    exact = session.get(Episode, ref)
    if exact:
        return exact
    matches = session.exec(select(Episode).where(col(Episode.id).startswith(ref))).all()
    if not matches:
        raise KeyError(f"No episode matches '{ref}'")
    if len(matches) > 1:
        raise KeyError(f"'{ref}' is ambiguous: {', '.join(m.id for m in matches)}")
    return matches[0]
