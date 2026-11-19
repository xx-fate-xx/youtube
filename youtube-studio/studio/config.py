"""Runtime settings. Secrets are read from the environment / .env and never echoed."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

TRUE_VALUES = {"1", "true", "yes", "on"}


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: sets variables that are not already in the environment."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in TRUE_VALUES


def _float(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()
    return float(value) if value else default


@dataclass(frozen=True)
class Settings:
    root: Path
    projects_dir: Path
    channels_dir: Path
    samples_dir: Path
    db_path: Path
    monthly_budget_usd: float
    enable_paid: bool
    enable_youtube: bool
    youtube_client_secrets: Path | None
    youtube_token_file: Path
    elevenlabs_key_present: bool
    elevenlabs_usd_per_1k_chars: float | None
    elevenlabs_voice_id: str
    elevenlabs_model_id_env: str
    elevenlabs_plan: str
    llm_model: str
    llm_effort: str
    anthropic_credentials_hint: bool
    ffmpeg_override: str | None
    font_path: str | None
    default_voice_provider: str

    def ffmpeg_binary(self) -> str:
        """Locate FFmpeg: STUDIO_FFMPEG -> PATH -> imageio-ffmpeg bundled binary."""
        if self.ffmpeg_override:
            return self.ffmpeg_override
        found = shutil.which("ffmpeg")
        if found:
            return found
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "FFmpeg not found. Install with `brew install ffmpeg` or `uv sync` "
                "(imageio-ffmpeg), or set STUDIO_FFMPEG."
            ) from exc


def load_settings(root: Path | None = None) -> Settings:
    root = (root or Path(os.environ.get("STUDIO_ROOT", Path.cwd()))).resolve()
    _load_dotenv(root / ".env")
    projects = Path(os.environ.get("STUDIO_PROJECTS_DIR", root / "projects")).resolve()
    secrets = os.environ.get("YOUTUBE_CLIENT_SECRETS_FILE", "").strip()
    rate = os.environ.get("ELEVENLABS_USD_PER_1K_CHARS", "").strip()
    return Settings(
        root=root,
        projects_dir=projects,
        channels_dir=root / "channels",
        samples_dir=root / "samples",
        db_path=projects / "studio.db",
        monthly_budget_usd=_float("STUDIO_MONTHLY_BUDGET_USD", 250.0),
        enable_paid=_flag("STUDIO_ENABLE_PAID_PROVIDERS"),
        enable_youtube=_flag("STUDIO_ENABLE_YOUTUBE"),
        youtube_client_secrets=Path(secrets).expanduser() if secrets else None,
        youtube_token_file=projects / ".secrets" / "youtube_token.json",
        elevenlabs_key_present=bool(os.environ.get("ELEVENLABS_API_KEY", "").strip()),
        elevenlabs_usd_per_1k_chars=float(rate) if rate else None,
        elevenlabs_voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "").strip(),
        elevenlabs_model_id_env=os.environ.get("ELEVENLABS_MODEL_ID", "").strip(),
        elevenlabs_plan=os.environ.get("ELEVENLABS_PLAN", "").strip(),
        llm_model=os.environ.get("STUDIO_LLM_MODEL", "").strip() or "claude-opus-5-5",
        llm_effort=os.environ.get("STUDIO_LLM_EFFORT", "").strip() or "high",
        anthropic_credentials_hint=bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()
                                        or os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()),
        ffmpeg_override=os.environ.get("STUDIO_FFMPEG", "").strip() or None,
        font_path=os.environ.get("STUDIO_FONT", "").strip() or None,
        default_voice_provider=os.environ.get("STUDIO_VOICE_PROVIDER", "mock").strip() or "mock",
    )
