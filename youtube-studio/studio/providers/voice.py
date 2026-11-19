"""Voice providers. All write mono 16-bit PCM WAV at 22.05 kHz, one file per sentence."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from studio.models import LicenseClearance

SAMPLE_RATE = 22050


@dataclass(frozen=True)
class VoiceLicense:
    license: str
    clearance: LicenseClearance
    proof: str
    author: str
    notes: str = ""


class VoiceProvider(Protocol):
    name: str
    paid: bool
    is_placeholder: bool
    timing_method: str
    voice: str

    def estimate_usd(self, text: str) -> float: ...

    def license(self) -> VoiceLicense: ...

    def synthesize_sentence(self, text: str, out: Path) -> float:
        """Write `out` (WAV) and return its duration in seconds."""
        ...


def write_silence(path: Path, seconds: float) -> float:
    frames = max(0, round(seconds * SAMPLE_RATE))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * frames)
    return frames / SAMPLE_RATE


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


class MockVoiceProvider:
    """Silent placeholder narration with durations estimated from the channel's pace."""

    name = "mock_voice"
    paid = False
    is_placeholder = True
    timing_method = "estimated"

    def __init__(self, words_per_minute: int = 150):
        self.wpm = words_per_minute
        self.voice = f"silent-placeholder@{words_per_minute}wpm"

    def estimate_usd(self, text: str) -> float:
        return 0.0

    def license(self) -> VoiceLicense:
        return VoiceLicense("n/a - silent placeholder", LicenseClearance.RESTRICTED,
                            "generated silence", "studio",
                            "Placeholder: replace with real narration before approval.")

    def synthesize_sentence(self, text: str, out: Path) -> float:
        words = max(1, len(text.split()))
        return write_silence(out, max(0.6, words / self.wpm * 60.0))


class MacOSSayVoiceProvider:
    """Local, free macOS `say` synthesis for listenable previews.

    Licensing: the macOS licence allows system voices for personal, non-commercial use only,
    so output is marked RESTRICTED and blocks approval for publishing.
    """

    name = "macos_say"
    paid = False
    is_placeholder = False
    timing_method = "sentence_exact_word_interpolated"

    def __init__(self, voice: str = "Samantha", words_per_minute: int = 150):
        if not shutil.which("say"):
            raise RuntimeError("macOS `say` is not available on this system")
        self.voice = voice
        self.wpm = words_per_minute

    def estimate_usd(self, text: str) -> float:
        return 0.0

    def license(self) -> VoiceLicense:
        return VoiceLicense(
            "macOS system voice (Apple SLA)",
            LicenseClearance.RESTRICTED,
            "macOS Software License Agreement: system voices for personal, non-commercial use",
            "Apple Inc. (system voice)",
            "Preview only. Replace with your own recording or a licensed TTS before publishing.",
        )

    def synthesize_sentence(self, text: str, out: Path) -> float:
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["say", "-v", self.voice, "-r", str(self.wpm), "-o", str(out),
             f"--data-format=LEI16@{SAMPLE_RATE}", text],
            check=True, capture_output=True, timeout=120,
        )
        return wav_duration(out)


# --------------------------------------------------------------------------- ElevenLabs
# API facts checked against elevenlabs.io/docs on 2026-11-18 (see docs/PHASE-2-REPORT.md):
#   POST {base}/v1/text-to-speech/{voice_id}/with-timestamps?output_format=pcm_22050
#   header xi-api-key; body {text, model_id, voice_settings, previous_text, next_text}
#   200 -> {audio_base64, alignment{characters, character_start_times_seconds,
#           character_end_times_seconds} | null, normalized_alignment{...} | null}
# Pricing (API pay-as-you-go, multilingual v2 / v4): $0.08 per 1,000 characters.
# Commercial use: free plan has NO commercial licence; paid plans include one.

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"
ELEVENLABS_DEFAULT_USD_PER_1K = 0.08
# Plans (elevenlabs.io/pricing and /pricing/api, checked 2026-11-18). "API usage is billed in
# US dollars, not credits": the subscription price is the included API allowance, e.g.
# Starter $6/month = 75,000 characters on v2/v3/v4 at $0.08/1K (150,000 on Flash/Turbo).
# The 30,000 "credits" of Starter are the web-app (UI) allowance. No overage billing on new
# self-serve plans; extra usage only via prepaid Pay-As-You-Go top-ups.
ELEVENLABS_PLAN_USD = {"free": 0.0, "starter": 6.0, "creator": 22.0, "pro": 99.0}
ELEVENLABS_PLAN_UI_CREDITS = {"free": 10_000, "starter": 30_000, "creator": 121_000,
                              "pro": 600_000}
# Credits charged per character of `text`, by model (pricing page, checked 2026-11-18).
ELEVENLABS_CREDITS_PER_CHAR = {
    "eleven_multilingual_v2": 1.0,
    "eleven_v3": 1.0,
    "eleven_v4": 1.0,
    "eleven_flash_v2_5": 0.5,
    "eleven_flash_v2": 0.5,
    "eleven_turbo_v2_5": 0.5,
    "eleven_turbo_v2": 0.5,
}
ELEVENLABS_COMMERCIAL_PLANS = {"starter", "creator", "pro", "scale", "business", "enterprise"}
ELEVENLABS_TERMS_URL = ("https://elevenlabs.io/docs/help-center/legal/"
                        "can-i-publish-the-content-i-generate-on-the-platform")
RETRYABLE = {429, 500, 502, 503, 504}

Transport = Callable[[str, dict[str, str], bytes], tuple[int, dict[str, str], bytes]]


class ElevenLabsError(RuntimeError):
    pass


class NotArmed(RuntimeError):
    """Raised when a paid request is attempted without a passed budget preflight."""


def _urllib_transport(url: str, headers: dict[str, str], body: bytes):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read()


def words_from_alignment(alignment: dict | None) -> list[tuple[str, float, float]]:
    """Group character timings into words: (word, start, end) in seconds."""
    if not alignment:
        return []
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    words: list[tuple[str, float, float]] = []
    cur, w_start, w_end = "", 0.0, 0.0
    for ch, st, en in zip(chars, starts, ends, strict=False):
        if ch.isspace():
            if cur:
                words.append((cur, w_start, w_end))
            cur = ""
            continue
        if not cur:
            w_start = float(st)
        cur += ch
        w_end = float(en)
    if cur:
        words.append((cur, w_start, w_end))
    return words


def _pcm_to_wav(pcm: bytes, out: Path) -> float:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.wav")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    tmp.replace(out)
    return wav_duration(out)


class ElevenLabsVoiceProvider:
    """Paid ElevenLabs TTS with exact word timings (from character alignment).

    Safety layers, all required before any HTTP request:
    1. STUDIO_ENABLE_PAID_PROVIDERS=1 and ELEVENLABS_API_KEY (checked by the CLI/BudgetGuard);
    2. BudgetGuard.preflight(..., consent=True) - the operator's explicit --i-consent-to-spend;
    3. `arm(max_chars)` called with the preflighted character budget; requests beyond it raise
       NotArmed, so a bug cannot spend more than was approved.
    The API key is never logged or written to artifacts.
    """

    name = "elevenlabs"
    paid = True
    is_placeholder = False
    timing_method = "provider_alignment"

    def __init__(self, usd_per_1k_chars: float | None = None, voice: str = "", *,
                 api_key: str = "", model_id: str = ELEVENLABS_DEFAULT_MODEL, plan: str = "",
                 base_url: str = ELEVENLABS_BASE_URL, transport: Transport | None = None,
                 voice_settings: dict | None = None, stitching: str = "request_ids",
                 max_retries: int = 4, sleep: Callable[[float], None] = time.sleep):
        self.usd_per_1k_chars = (usd_per_1k_chars if usd_per_1k_chars is not None
                                 else ELEVENLABS_DEFAULT_USD_PER_1K)
        self.voice = voice
        self.model_id = model_id
        self.plan = plan.strip().lower()
        self.voice_settings = dict(voice_settings or {})
        # "request_ids": continuity via previous_request_ids (no extra text sent - billing of
        # previous_text/next_text is unconfirmed); "text": send neighbouring sentences; "none".
        if stitching not in {"request_ids", "text", "none"}:
            raise ValueError(f"stitching must be request_ids|text|none, not {stitching!r}")
        self.stitching = stitching
        self._recent_ids: list[str] = []
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport or _urllib_transport
        self.max_retries = max_retries
        self._sleep = sleep
        self._armed_chars = 0
        self.chars_sent = 0
        self.requests = 0

    def __repr__(self) -> str:  # never expose the key
        return f"ElevenLabsVoiceProvider(voice={self.voice!r}, model={self.model_id!r})"

    def estimate_usd(self, text: str) -> float:
        return round(len(text) / 1000.0 * self.usd_per_1k_chars, 4)

    def estimate_credits(self, chars: int) -> float:
        return chars * ELEVENLABS_CREDITS_PER_CHAR.get(self.model_id, 1.0)

    @property
    def cache_tag(self) -> str:
        """Part of the sentence-cache key: new settings must not reuse old audio."""
        return json.dumps(self.voice_settings, sort_keys=True)

    def license(self) -> VoiceLicense:
        if self.plan in ELEVENLABS_COMMERCIAL_PLANS:
            return VoiceLicense(
                f"ElevenLabs paid plan ({self.plan}) - commercial licence",
                LicenseClearance.CLEARED,
                f"{ELEVENLABS_TERMS_URL} ('All paid plans include a commercial license'); "
                f"plan declared by operator via ELEVENLABS_PLAN={self.plan}",
                "ElevenLabs (synthetic voice)",
                "Keep the invoice/plan screenshot for the generation month. Do not use voice "
                "clones of real people without documented permission.")
        if self.plan == "free":
            return VoiceLicense("ElevenLabs free plan", LicenseClearance.RESTRICTED,
                                ELEVENLABS_TERMS_URL,
                                "ElevenLabs (synthetic voice)",
                                "Free plan has no commercial licence; do not monetise.")
        return VoiceLicense("ElevenLabs plan not declared", LicenseClearance.UNKNOWN,
                            ELEVENLABS_TERMS_URL, "ElevenLabs (synthetic voice)",
                            "Set ELEVENLABS_PLAN to your paid plan to clear commercial use.")

    # ------------------------------------------------------------------ guarded requests
    def arm(self, max_chars: int) -> None:
        """Allow up to `max_chars` characters of requests (call only after a passed preflight)."""
        if not self._api_key:
            raise ElevenLabsError("ELEVENLABS_API_KEY is not set")
        if not self.voice:
            raise ElevenLabsError("Set ELEVENLABS_VOICE_ID (a stock/licensed voice id)")
        self._armed_chars = max(0, int(max_chars))

    def get_voice(self, voice_id: str, getter=None) -> dict:
        """Read-only voice metadata (GET /v1/voices/{id}); generates nothing, costs nothing.

        Returns name, category, labels (accent/age/gender/use case), preview_url and the
        sharing notice fields (e.g. disable_at_unix) when present."""
        if not self._api_key:
            raise ElevenLabsError("ELEVENLABS_API_KEY is not set")
        url = f"{self.base_url}/v1/voices/{urllib.parse.quote(voice_id)}"
        if getter is None:
            def getter(u, h):
                req = urllib.request.Request(u, headers=h, method="GET")
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        return resp.status, resp.read()
                except urllib.error.HTTPError as exc:
                    return exc.code, exc.read()
        status, raw = getter(url, {"xi-api-key": self._api_key, "Accept": "application/json"})
        if status != 200:
            raise ElevenLabsError(f"ElevenLabs HTTP {status}: {_error_detail(raw)}")
        data = json.loads(raw)
        sharing = data.get("sharing") or {}
        return {"voice_id": data.get("voice_id", voice_id), "name": data.get("name", ""),
                "category": data.get("category", ""), "labels": data.get("labels") or {},
                "preview_url": data.get("preview_url", ""),
                "disable_at_unix": sharing.get("disable_at_unix") or data.get("disable_at_unix"),
                "sharing_status": sharing.get("status", "")}

    def synthesize_sentence(self, text: str, out: Path) -> float:
        return self.synthesize_sentence_timed(text, out)[0]

    def synthesize_sentence_timed(self, text: str, out: Path, *, previous_text: str = "",
                                  next_text: str = "") -> tuple[float, list[tuple[str, float,
                                                                                   float]]]:
        if self.chars_sent + len(text) > self._armed_chars:
            raise NotArmed("ElevenLabs request blocked: no passed budget preflight covers it "
                           f"({self.chars_sent + len(text)} > {self._armed_chars} chars)")
        url = (f"{self.base_url}/v1/text-to-speech/{urllib.parse.quote(self.voice)}"
               f"/with-timestamps?output_format=pcm_{SAMPLE_RATE}")
        body: dict = {"text": text, "model_id": self.model_id}
        if self.voice_settings:
            body["voice_settings"] = self.voice_settings
        if self.stitching == "text":
            if previous_text:
                body["previous_text"] = previous_text
            if next_text:
                body["next_text"] = next_text
        elif self.stitching == "request_ids" and self._recent_ids:
            body["previous_request_ids"] = self._recent_ids[-3:]  # closest last, max 3
        headers = {"xi-api-key": self._api_key, "Content-Type": "application/json",
                   "Accept": "application/json"}
        payload = json.dumps(body).encode()
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            status, resp_headers, raw = self._transport(url, headers, payload)
            self.requests += 1
            if status == 200:
                rid = {k.lower(): v for k, v in resp_headers.items()}.get("request-id")
                if rid:
                    self._recent_ids = [*self._recent_ids, rid][-3:]
                break
            detail = _error_detail(raw)
            if status in RETRYABLE and attempt < self.max_retries:
                self._sleep(delay)
                delay *= 2
                continue
            hint = {401: "check ELEVENLABS_API_KEY", 402: "insufficient credits",
                    403: "plan does not allow this (format/feature)",
                    422: "request validation failed"}.get(status, "")
            raise ElevenLabsError(f"ElevenLabs HTTP {status} {hint}: {detail}".strip())
        self.chars_sent += len(text)
        data = json.loads(raw)
        pcm = base64.b64decode(data["audio_base64"])
        duration = _pcm_to_wav(pcm, out)
        words = words_from_alignment(data.get("alignment")) or words_from_alignment(
            data.get("normalized_alignment"))
        out.with_suffix(".align.json").write_text(json.dumps(
            {"text": text, "model_id": self.model_id, "voice": self.voice, "words": words}),
            encoding="utf-8")
        return duration, words


def _error_detail(raw: bytes) -> str:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return raw[:200].decode(errors="replace")
    detail = data.get("detail", data) if isinstance(data, dict) else data
    if isinstance(detail, dict):
        return f"{detail.get('code') or detail.get('status', '')} {detail.get('message', '')}"
    return str(detail)[:300]
