"""Readiness of every paid or external service - prints facts, never secret values."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field

from studio.channels import load_channels
from studio.config import Settings


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Service:
    name: str
    paid: bool
    checks: list[Check] = field(default_factory=list)
    next_step: str = ""

    @property
    def ready(self) -> bool:
        return all(c.ok for c in self.checks)


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def status(s: Settings) -> list[Service]:
    channels = load_channels(s.channels_dir)
    ee = channels.get("engineering_explained")
    voice_id = s.elevenlabs_voice_id or (ee.narration.elevenlabs.voice_id if ee else "")
    out = []

    el = Service("ElevenLabs narration", paid=True)
    el.checks = [
        Check("paid flag", s.enable_paid, "STUDIO_ENABLE_PAID_PROVIDERS=1"),
        Check("API key", s.elevenlabs_key_present, "ELEVENLABS_API_KEY in .env"),
        Check("paid plan declared", s.elevenlabs_plan.lower() in
              {"starter", "creator", "pro", "scale", "business", "enterprise"},
              f"ELEVENLABS_PLAN={s.elevenlabs_plan or '(unset)'}"),
        Check("voice chosen", bool(voice_id), voice_id or "studio voices use <key>"),
    ]
    el.next_step = ("studio voices check -> studio voices use <key> -> "
                    "studio voice <ep> --provider elevenlabs --dry-run")
    out.append(el)

    an = Service("Claude drafts (Anthropic API)", paid=True)
    an.checks = [
        Check("paid flag", s.enable_paid, "STUDIO_ENABLE_PAID_PROVIDERS=1"),
        Check("SDK installed", _has_module("anthropic"), "uv sync --extra llm"),
        Check("credentials", s.anthropic_credentials_hint,
              "ANTHROPIC_API_KEY set (an `ant auth login` profile also works; not checked "
              "here)"),
    ]
    an.next_step = f"studio draft script <ep> --dry-run (model {s.llm_model}, effort " \
                   f"{s.llm_effort})"
    out.append(an)

    yt = Service("YouTube upload + Analytics (OAuth)", paid=False)
    secrets = s.youtube_client_secrets
    mapped = [k for k, c in channels.items() if c.youtube_channel_id]
    yt.checks = [
        Check("feature flag", s.enable_youtube, "STUDIO_ENABLE_YOUTUBE=1"),
        Check("Google libraries", _has_module("googleapiclient")
              and _has_module("google_auth_oauthlib"), "uv sync --extra youtube"),
        Check("OAuth client file", bool(secrets and secrets.exists()),
              "YOUTUBE_CLIENT_SECRETS_FILE (Desktop app OAuth client JSON)"),
        Check("authorised once", s.youtube_token_file.exists(),
              "first upload or `studio analytics --api` opens the consent page"),
        Check("channel mapping", bool(mapped),
              f"youtube_channel_id set for: {', '.join(mapped) or 'none'}"),
    ]
    yt.next_step = "studio publish <ep>  (always private; needs an approved review)"
    out.append(yt)
    return out


def status_markdown(services: list[Service], month_spent: float, cap: float) -> str:
    lines = ["# External services", "",
             f"Budget: ${month_spent:.2f} spent this month of ${cap:.2f}.", ""]
    for sv in services:
        tag = "READY" if sv.ready else "not connected"
        lines += [f"## {sv.name} - {tag}{' (paid)' if sv.paid else ''}", ""]
        lines += [f"- [{'x' if c.ok else ' '}] {c.name}: {c.detail}" for c in sv.checks]
        lines += [f"- next: `{sv.next_step}`", ""]
    return "\n".join(lines)
