"""Narration assembly: per-sentence synthesis (cached), pauses, timings, licence record."""

from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from pathlib import Path

from studio.channels import ChannelProfile
from studio.episodes import Workspace
from studio.fsutil import atomic_write_json, sha256_file, sha256_text
from studio.models import AssetRecord, NarrationTrack, SceneTiming, WordTiming
from studio.providers.voice import SAMPLE_RATE, VoiceProvider, wav_duration
from studio.storyboard import split_sentences


@dataclass(frozen=True)
class NarrationItem:
    """A narration unit: one scene's text (long video) or one Short's text."""

    id: str
    text: str


def _interpolate_words(sentence: str, start: float, duration: float) -> list[WordTiming]:
    words = sentence.split()
    total = sum(len(w) + 1 for w in words) or 1
    out, t = [], start
    for w in words:
        d = duration * (len(w) + 1) / total
        out.append(WordTiming(word=w, start=round(t, 3), end=round(t + d, 3)))
        t += d
    return out


def _append_wav(dst: wave.Wave_write, src: Path) -> None:
    with wave.open(str(src), "rb") as r:
        if (r.getnchannels(), r.getsampwidth(), r.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError(f"{src}: expected mono 16-bit {SAMPLE_RATE} Hz WAV")
        dst.writeframes(r.readframes(r.getnframes()))


def synthesize(
    items: list[NarrationItem],
    provider: VoiceProvider,
    channel: ChannelProfile,
    out_wav: Path,
    cache_dir: Path,
    *,
    lead_in_s: float = 0.4,
) -> tuple[list[SceneTiming], float]:
    """Synthesize items into one WAV; return per-item timings and total duration."""
    n = channel.narration
    timings: list[SceneTiming] = []
    pieces: list[tuple[str, Path | float]] = [("silence", lead_in_s)]
    t = lead_in_s
    for item in items:
        start = t
        words: list[WordTiming] = []
        sentences = split_sentences(item.text)
        for k, sentence in enumerate(sentences):
            model = getattr(provider, "model_id", "")
            tag = getattr(provider, "cache_tag", "")
            key = sha256_text(provider.name, provider.voice, model, *([tag] if tag else []),
                              sentence)[:20]
            path = cache_dir / f"{key}.wav"
            align = path.with_suffix(".align.json")
            timed = hasattr(provider, "synthesize_sentence_timed")
            if path.exists() and (not timed or align.exists()):
                d = wav_duration(path)
                exact = json.loads(align.read_text())["words"] if align.exists() else []
            elif timed:
                ctx = getattr(provider, "stitching", "") == "text"
                d, exact = provider.synthesize_sentence_timed(
                    sentence, path,
                    previous_text=" ".join(sentences[max(0, k - 2):k]) if ctx else "",
                    next_text=" ".join(sentences[k + 1:k + 3]) if ctx else "")
            else:
                d, exact = provider.synthesize_sentence(sentence, path), []
            if exact:
                words += [WordTiming(word=w, start=round(t + a0, 3), end=round(t + a1, 3))
                          for w, a0, a1 in exact]
            else:
                words += _interpolate_words(sentence, t, d)
            pieces.append(("file", path))
            pieces.append(("silence", n.sentence_pause_s))
            t += d + n.sentence_pause_s
        pieces.append(("silence", n.scene_pause_s))
        t += n.scene_pause_s
        timings.append(SceneTiming(scene_id=item.id, start=round(start, 3), end=round(t, 3),
                                   words=words))
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_wav.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        for kind, value in pieces:
            if kind == "file":
                _append_wav(w, value)  # type: ignore[arg-type]
            else:
                w.writeframes(b"\x00\x00" * round(float(value) * SAMPLE_RATE))  # type: ignore[arg-type]
    tmp.replace(out_wav)
    return timings, wav_duration(out_wav)


def build_narration(ws: Workspace, episode_id: str, items: list[NarrationItem],
                    provider: VoiceProvider, channel: ChannelProfile) -> tuple[NarrationTrack,
                                                                               AssetRecord]:
    out = ws.audio / "narration.wav"
    timings, duration = synthesize(items, provider, channel, out, ws.audio / "sentences")
    lic = provider.license()
    record = AssetRecord(
        id="narration",
        path=str(out.relative_to(ws.root)),
        kind="narration",
        origin="generated_local" if not provider.paid else "ai_generated",
        author=lic.author,
        license=lic.license,
        license_proof=lic.proof,
        clearance=lic.clearance,
        ai_generated=provider.name not in {"mock_voice", "user_recording"},
        realistic=False,
        sha256=sha256_file(out),
        notes=lic.notes,
    )
    track = NarrationTrack(
        episode_id=episode_id, provider=provider.name, voice=provider.voice,
        audio_path=str(out.relative_to(ws.root)), duration_s=round(duration, 3),
        is_placeholder=provider.is_placeholder, timing_method=provider.timing_method,
        license_asset_id=record.id, scenes=timings,
    )
    atomic_write_json(ws.narration_file, track)
    return track, record


def detect_silences(binary: str, wav: Path, *, noise_db: float = -35.0,
                    min_silence_s: float = 0.15) -> list[tuple[float, float]]:
    """Silent intervals in a recording (FFmpeg silencedetect)."""
    import re
    import subprocess

    proc = subprocess.run(
        [binary, "-hide_banner", "-nostdin", "-i", str(wav), "-af",
         f"silencedetect=noise={noise_db}dB:d={min_silence_s}", "-f", "null", "-"],
        capture_output=True, text=True, timeout=600)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    out = []
    for i, st in enumerate(starts):
        en = ends[i] if i < len(ends) else wav_duration(wav)
        out.append((max(0.0, st), en))
    return out


def align_sentences(sentences: list[str], duration: float,
                    silences: list[tuple[float, float]]) -> list[tuple[float, float]] | None:
    """Map N sentences onto the recording using pauses as boundaries.

    Picks N-1 pauses (in order) whose midpoints best match the boundaries expected from
    sentence lengths (dynamic programming, longer pauses preferred). Returns (start, end)
    per sentence, or None when the recording has too few pauses."""
    n = len(sentences)
    if n == 0:
        return []
    speech_start = silences[0][1] if silences and silences[0][0] <= 0.05 else 0.0
    speech_end = silences[-1][0] if silences and silences[-1][1] >= duration - 0.05 \
        else duration
    inner = [(a, b) for a, b in silences if a > speech_start + 0.05 and b < speech_end - 0.05]
    if n == 1:
        return [(speech_start, speech_end)]
    if len(inner) < n - 1:
        return None
    weights = [max(1, len(x)) for x in sentences]
    total = sum(weights)
    span = speech_end - speech_start
    expected = []
    acc = 0
    for w in weights[:-1]:
        acc += w
        expected.append(speech_start + span * acc / total)
    m = len(inner)
    mids = [(a + b) / 2 for a, b in inner]
    lens = [b - a for a, b in inner]

    def cost(k: int, j: int) -> float:  # boundary k uses pause j
        return (mids[j] - expected[k]) ** 2 / (span / n) ** 2 - 0.5 * min(lens[j], 1.0)

    inf = float("inf")
    best = [[inf] * m for _ in range(n - 1)]
    back = [[-1] * m for _ in range(n - 1)]
    for j in range(m):
        best[0][j] = cost(0, j)
    for k in range(1, n - 1):
        run_min, run_arg = inf, -1
        for j in range(m):
            if j - 1 >= 0 and best[k - 1][j - 1] < run_min:
                run_min, run_arg = best[k - 1][j - 1], j - 1
            if run_arg >= 0:
                best[k][j] = run_min + cost(k, j)
                back[k][j] = run_arg
    j = min(range(m), key=lambda x: best[n - 2][x])
    if best[n - 2][j] == inf:
        return None
    picks = [j]
    for k in range(n - 2, 0, -1):
        j = back[k][j]
        picks.append(j)
    picks.reverse()
    bounds = [inner[j] for j in picks]
    out = []
    start = speech_start
    for a, b in bounds:
        out.append((start, a))
        start = b
    out.append((start, speech_end))
    return out


def narration_from_user_file(ws: Workspace, episode_id: str, items: list[NarrationItem],
                             wav_22k_mono: Path, *, speaker: str,
                             binary: str | None = None) -> tuple[NarrationTrack, AssetRecord]:
    """Use the operator's own recording.

    With FFmpeg available, sentence boundaries are aligned to the pauses in the recording
    (sentence-exact captions); otherwise timings are distributed by word count."""
    out = ws.audio / "narration.wav"
    if wav_22k_mono.resolve() != out.resolve():
        out.write_bytes(wav_22k_mono.read_bytes())
    duration = wav_duration(out)
    per_item = [split_sentences(i.text) for i in items]
    sentences = [x for group in per_item for x in group]
    spans = None
    if binary:
        spans = align_sentences(sentences, duration, detect_silences(binary, out))
    timings = []
    if spans:
        method = "sentence_pause_aligned"
        k = 0
        for item, group in zip(items, per_item, strict=True):
            words: list[WordTiming] = []
            for sent in group:
                a, b = spans[k]
                words += _interpolate_words(sent, a, b - a)
                k += 1
            first, last = spans[k - len(group)], spans[k - 1]
            timings.append(SceneTiming(scene_id=item.id, start=round(first[0], 3),
                                       end=round(last[1], 3), words=words))
        # scenes are contiguous on the timeline: each starts where the previous ended
        for prev, cur in zip(timings, timings[1:], strict=False):
            cur.start = prev.end
        timings[0].start = 0.0
    else:
        method = "estimated_proportional"
        total_words = sum(len(i.text.split()) for i in items) or 1
        t = 0.0
        for item in items:
            d = duration * len(item.text.split()) / total_words
            timings.append(SceneTiming(scene_id=item.id, start=round(t, 3),
                                       end=round(t + d, 3),
                                       words=_interpolate_words(item.text, t, d)))
            t += d
    record = AssetRecord(
        id="narration", path=str(out.relative_to(ws.root)), kind="narration",
        origin="user_supplied", author=speaker, license="Operator's own recording",
        license_proof=f"Operator statement: recorded by {speaker}",
        clearance="cleared", sha256=sha256_file(out),
        notes=("Sentence boundaries aligned to pauses in the recording." if spans else
               "Timings estimated proportionally (too few pauses found to align)."),
    )
    track = NarrationTrack(
        episode_id=episode_id, provider="user_recording", voice=speaker,
        audio_path=str(out.relative_to(ws.root)), duration_s=round(duration, 3),
        is_placeholder=False, timing_method=method,
        license_asset_id="narration", scenes=timings,
    )
    atomic_write_json(ws.narration_file, track)
    return track, record
