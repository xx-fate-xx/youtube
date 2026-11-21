"""Episode context for the video pipeline.

An episode has two directories:
  src  = episodes/<slug>/   committed sources: episode.yaml, frames.txt, characters.yaml, sounds.yaml,
                            overlays.py (optional exact charts), title_layout.json, fact-check notes
  work = projects/<slug>/   git-ignored media and state: generated frames, audio, renders, release kit

Every pipeline module reads paths and settings through `ep()`, the episode selected with `use()`
(the CLI calls it from --episode). Nothing here calls a paid service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]          # youtube-studio/
EPISODES = ROOT / "episodes"
PROJECTS = ROOT / "projects"
FONTS = ROOT / "assets" / "fonts" / "inter"
STYLES = Path(__file__).resolve().parent / "styles"

DEFAULTS: dict = {
    "language": "en-US",
    "style": "enginovue_cartoon",
    "storyboard_end": None,                          # "m:ss" end of the last storyboard slot
    "image": {"model": "gpt_image_2_6", "params": {"aspect_ratio": "16:9", "quality": "low", "resolution": "2k"},
              "price_credits": 1.25},
    "animation": {"model": "grok_video_v15_lite", "resolution": "720p", "duration": 4, "price_credits": 4.0,
                  "max_clips": 2},
    "budget": {"higgsfield_credits": 200.0, "elevenlabs_credits": 25000.0, "retry_reserve": 0.10},
    "narration": {"voice_id": "", "voice_name": "", "model": "eleven_v4", "intro_s": 0.6, "gap_s": 1.0,
                  "outro_s": 2.0, "lead_s": 0.12},
    "pilot_manifest": None,
    "release": {},
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


@dataclass
class Episode:
    src: Path
    cfg: dict = field(default_factory=dict)

    @classmethod
    def load(cls, src: str | Path) -> Episode:
        p = Path(src)
        if not p.is_absolute() and not p.exists():
            p = EPISODES / p                          # allow a bare slug
        p = p.resolve()
        cfg_file = p / "episode.yaml"
        if not cfg_file.is_file():
            raise FileNotFoundError(f"{cfg_file} not found (create it with `studio pipe new`)")
        cfg = _merge(DEFAULTS, yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {})
        cfg.setdefault("slug", p.name)
        return cls(src=p, cfg=cfg)

    # ---- paths
    @property
    def slug(self) -> str:
        return self.cfg["slug"]

    @property
    def work(self) -> Path:
        w = self.cfg.get("work_dir")
        return (ROOT / w).resolve() if w else PROJECTS / self.slug

    @property
    def prod(self) -> Path:
        return self.work / "production"

    @property
    def frames_dir(self) -> Path:
        return self.prod / "frames"

    @property
    def audio(self) -> Path:
        return self.work / "audio"

    @property
    def render_dir(self) -> Path:
        return self.work / "render"

    @property
    def release_dir(self) -> Path:
        return self.work / "release"

    @property
    def frames_txt(self) -> Path:
        return self.src / "frames.txt"

    @property
    def overlays_dir(self) -> Path:
        return self.src / "overlays"

    # ---- settings
    def style(self) -> dict:
        s = yaml.safe_load((STYLES / f"{self.cfg['style']}.yaml").read_text(encoding="utf-8"))
        if self.cfg.get("eras"):
            s["eras"] = {**s.get("eras", {}), **self.cfg["eras"]}
        return s

    def characters(self) -> dict:
        f = self.src / "characters.yaml"
        return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.is_file() else {}

    def sounds(self) -> dict:
        f = self.src / "sounds.yaml"
        return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.is_file() else {}


_CURRENT: Episode | None = None


def use(src: str | Path | Episode) -> Episode:
    global _CURRENT
    _CURRENT = src if isinstance(src, Episode) else Episode.load(src)
    return _CURRENT


def ep() -> Episode:
    if _CURRENT is None:
        raise RuntimeError("no episode selected (pass --episode)")
    return _CURRENT
