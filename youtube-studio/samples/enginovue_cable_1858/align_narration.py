"""Align the ElevenLabs narration to the storyboard and derive per-frame slot durations.

Input : projects/enginovue_cable_1858/audio/narration_chunks.json (chapter texts, frame ranges)
        projects/enginovue_cable_1858/audio/narration/chNN.mp3   (one take per chapter)
Output: projects/enginovue_cable_1858/audio/narration_timing.json  (per-frame start/duration)
        projects/enginovue_cable_1858/audio/narration_full.wav     (chapters joined with pauses)
        projects/enginovue_cable_1858/audio/narration_words.json   (recognised words with times)

Word times come from a local faster-whisper run (free, offline). The script text is never changed:
recognised words are only used as time anchors, matched to the script words with difflib.
A frame starts LEAD seconds before its first spoken word; chapters are separated by GAP seconds
of silence (where the picture dips to black).

Run with the alignment venv:  projects/.tools/align-venv/Scripts/python.exe align_narration.py
"""

from __future__ import annotations

import csv
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parents[1] / "projects" / "enginovue_cable_1858" / "audio"
SR = 48000
INTRO, GAP, OUTRO, LEAD = 0.6, 1.0, 2.0, 0.12   # seconds


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def pcm16k(path: Path):
    """Decode to 16 kHz mono float32 with ffmpeg (avoids the PyAV version faster-whisper pins)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def load_model():
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel("small.en", device="cuda", compute_type="float16")
        list(m.transcribe(pcm16k(AUDIO / "narration" / "ch01.mp3")[:16000 * 5], word_timestamps=False)[0])
        return m, "cuda"
    except Exception as e:  # missing CUDA libraries -> CPU
        print(f"CUDA unavailable ({type(e).__name__}); using CPU", flush=True)
        return WhisperModel("small.en", device="cpu", compute_type="int8"), "cpu"


def main() -> None:
    chunks = json.loads((AUDIO / "narration_chunks.json").read_text(encoding="utf-8"))
    rows = {int(r["n"]): r for r in csv.DictReader(open(HERE / "edit_timeline.csv", encoding="utf-8"))}
    model, device = load_model()
    frames_out, words_out, t0 = [], {}, INTRO
    concat = []
    for c in chunks:
        mp3 = AUDIO / "narration" / f"ch{c['chunk']:02d}.mp3"
        if not mp3.is_file():
            sys.exit(f"missing {mp3}")
        dur = duration(mp3)
        segs, _ = model.transcribe(pcm16k(mp3), language="en", word_timestamps=True, beam_size=5,
                                   condition_on_previous_text=False)
        rec = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]
        words_out[c["chunk"]] = rec
        # script words with their frame number
        script = []
        for n in range(c["frames"][0], c["frames"][1] + 1):
            for w in rows[n]["voiceover"].split():
                if norm(w):
                    script.append((n, norm(w)))
        sm = difflib.SequenceMatcher(a=[w for _, w in script], b=[norm(w) for w, _, _ in rec], autojunk=False)
        t_of = {}
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                t_of[a + k] = rec[b + k][1]
        matched = len(t_of) / max(1, len(script))
        # first-word time per frame (interpolate between anchors when the first word is unmatched)
        starts = {}
        for idx, (n, _) in enumerate(script):
            if n in starts:
                continue
            if idx in t_of:
                starts[n] = t_of[idx]
            else:
                prev = max((i for i in t_of if i < idx), default=None)
                nxt = min((i for i in t_of if i > idx), default=None)
                if prev is not None and nxt is not None:
                    starts[n] = t_of[prev] + (t_of[nxt] - t_of[prev]) * (idx - prev) / (nxt - prev)
                else:
                    starts[n] = t_of[nxt] if nxt is not None else 0.0
        ns = list(range(c["frames"][0], c["frames"][1] + 1))
        for i, n in enumerate(ns):
            # a chapter's first frame starts in the middle of the pause before it (the dip to black)
            start = t0 - GAP / 2 if i == 0 else t0 + max(0.0, starts[n] - LEAD)
            frames_out.append({"n": n, "chunk": c["chunk"], "start": round(start, 3)})
        concat.append((mp3, t0, dur))
        print(f"chapter {c['chunk']:>2}: {dur:6.2f}s  words matched {matched:.0%}  frames {ns[0]}-{ns[-1]}", flush=True)
        t0 += dur + GAP
    total = t0 - GAP + OUTRO
    frames_out[0]["start"] = 0.0
    for i, f in enumerate(frames_out):
        end = frames_out[i + 1]["start"] if i + 1 < len(frames_out) else total
        f["duration"] = round(end - f["start"], 3)
    # snap to whole video frames (30 fps) so the picture and the audio stay in sync
    acc = 0
    for f in frames_out:
        fr = max(15, round((f["start"] + f["duration"]) * 30) - acc)
        f["start"], f["duration"] = acc / 30, fr / 30
        acc += fr
    # joined narration wav
    inputs, filt = [], []
    for k, (mp3, start, _) in enumerate(concat):
        inputs += ["-i", str(mp3)]
        ms = round(start * 1000)
        filt.append(f"[{k}]aresample={SR},aformat=channel_layouts=mono,adelay={ms}|{ms}[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(concat)))
    filt.append(f"{mix}amix=inputs={len(concat)}:normalize=0,apad=whole_dur={acc / 30:.3f}[out]")
    wav = AUDIO / "narration_full.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-ac", "1", "-ar", str(SR), "-t", f"{acc / 30:.3f}", str(wav)], check=True)
    (AUDIO / "narration_words.json").write_text(json.dumps(words_out, indent=1), encoding="utf-8")
    (AUDIO / "narration_timing.json").write_text(json.dumps(
        {"voice": "Ryan - American Documentary Narrator (GQQpeRnV5mCWTgxKhGo5)", "model": "eleven_v4",
         "aligner": f"faster-whisper small.en ({device})", "intro_s": INTRO, "gap_s": GAP, "outro_s": OUTRO,
         "total_s": acc / 30, "frames": frames_out}, indent=1), encoding="utf-8")
    print(f"total {acc / 30:.2f}s ({int(acc / 30 // 60)}:{acc / 30 % 60:05.2f}) -> {wav}")


if __name__ == "__main__":
    main()
