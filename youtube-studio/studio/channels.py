"""Channel editorial style profiles loaded from channels/*.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class ElevenLabsVoiceConfig(BaseModel):
    """Chosen ElevenLabs voice for the channel (env ELEVENLABS_VOICE_ID overrides voice_id)."""

    voice_id: str = ""
    name: str = ""
    model_id: str = "eleven_multilingual_v2"
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    speed: float = 1.0

    def voice_settings(self) -> dict:
        return {"stability": self.stability, "similarity_boost": self.similarity_boost,
                "style": self.style, "use_speaker_boost": self.use_speaker_boost,
                "speed": self.speed}


class NarrationSettings(BaseModel):
    words_per_minute: int = 150
    tone: str
    local_voice: str = ""  # macOS `say` voice for local previews
    elevenlabs: ElevenLabsVoiceConfig = ElevenLabsVoiceConfig()
    sentence_pause_s: float = 0.25
    scene_pause_s: float = 0.6


class VisualIdentity(BaseModel):
    background: str
    foreground: str
    accent: str
    accent_2: str
    muted: str
    caption_bg: str = "#000000B4"
    font_family: str = "Helvetica, Arial, sans-serif"
    motif: str = ""


class ChannelProfile(BaseModel):
    key: str
    name: str
    id_prefix: str
    language: str = "en-US"
    runtime_minutes: tuple[float, float] = (8, 15)
    audience: str
    positioning: str
    tone: list[str]
    storytelling_structure: list[str]
    do: list[str]
    dont: list[str]
    narration: NarrationSettings
    visual: VisualIdentity
    shorts_style: str
    idea_backlog: list[str] = []
    default_tags: list[str] = []
    youtube_channel_id: str = ""  # filled in by the operator after OAuth mapping


def load_channels(channels_dir: Path) -> dict[str, ChannelProfile]:
    profiles: dict[str, ChannelProfile] = {}
    for path in sorted(channels_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = ChannelProfile.model_validate(data)
        if profile.key != path.stem:
            raise ValueError(f"{path.name}: key '{profile.key}' must match file name")
        profiles[profile.key] = profile
    prefixes = [p.id_prefix for p in profiles.values()]
    if len(prefixes) != len(set(prefixes)):
        raise ValueError("Channel id_prefix values must be unique")
    return profiles


def get_channel(channels_dir: Path, key: str) -> ChannelProfile:
    channels = load_channels(channels_dir)
    if key not in channels:
        raise KeyError(f"Unknown channel '{key}'. Known: {', '.join(channels)}")
    return channels[key]
