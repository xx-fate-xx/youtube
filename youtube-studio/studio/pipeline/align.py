"""Narration: chapter chunks for ElevenLabs, then free local word alignment -> per-frame slot timing.

  chunks()  -> projects/<slug>/audio/narration_chunks.json (one take per CHAPTER; text = the frames' VO,
               never rewritten) — Claude generates each take with the ElevenLabs MCP and saves it as
               audio/narration/chNN.mp3 (read-only)
  align()   -> narration_words.json (cached per take by SHA-256), narration_timing.json (frame start and
               duration, snapped to 30 fps), narration_full.wav (takes joined with pauses)

A frame starts `lead_s` before its first spoken word; chapters are separated by `gap_s` of silence (the
picture dips to black there). Recognised words are only time anchors matched to the script with difflib.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from . import frames as frames_mod
from .episode import ROOT, ep

SR = 48000
ALIGN_VENV = ROOT / "projects" / ".tools" / "align-venv"


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def chunks(write: bool = True) -> list[dict]:
    frames = frames_mod.parse()
    starts = [n for n, _ in frames_mod.chapters(frames)] + [len(frames) + 1]
    out = []
    for a, b in zip(starts, starts[1:], strict=False):
        text = " ".join(f["vo"].strip() for f in frames if a <= f["n"] < b)
        out.append({"chunk": len(out) + 1, "frames": [a, b - 1], "chars": len(text), "text": text})
    if write:
        ep().audio.mkdir(parents=True, exist_ok=True)
        (ep().audio / "narration_chunks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")
    return out


def take_path(k: int) -> Path:
    return ep().audio / "narration" / f"ch{k:02d}.mp3"


def ensure_align_env() -> Path:
    py = ALIGN_VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not py.is_file():
        print("creating the alignment environment (faster-whisper, free, one-time)...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(ALIGN_VENV)], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "faster-whisper"], check=True)
    return py


def words(chs: list[dict]) -> tuple[dict[int, list], str]:
    """Recognised words per chunk; takes whose SHA-256 is unchanged come from the cache."""
    cache_f = ep().audio / "narration_words.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.is_file() else {}
    meta = cache.get("_sha256", {})
    out, todo = {}, []
    for c in chs:
        p = take_path(c["chunk"])
        if not p.is_file():
            raise SystemExit(f"missing narration take {p}")
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        key = str(c["chunk"])
        if key in cache and meta.get(key) in (sha, None):
            out[c["chunk"]] = cache[key]
            meta[key] = sha
        else:
            todo.append((c["chunk"], p, sha))
    device = cache.get("_device", "cache")
    if todo:
        py = ensure_align_env()
        tmp = ep().audio / "_whisper_words.json"
        subprocess.run([str(py), str(Path(__file__).with_name("whisper_words.py")), str(tmp),
                        *[str(p) for _, p, _ in todo]], check=True)
        res = json.loads(tmp.read_text(encoding="utf-8"))
        tmp.unlink()
        device = res["_device"]
        for k, p, sha in todo:
            out[k] = res[str(p)]
            meta[str(k)] = sha
    cache = {str(k): v for k, v in sorted(out.items())} | {"_sha256": meta, "_device": device}
    cache_f.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    return out, device


def align() -> dict:
    nar = ep().cfg["narration"]
    INTRO, GAP, OUTRO, LEAD = nar["intro_s"], nar["gap_s"], nar["outro_s"], nar["lead_s"]
    chs = chunks()
    vo = {f["n"]: f["vo"] for f in frames_mod.parse()}
    rec_all, device = words(chs)
    frames_out, t0, concat = [], INTRO, []
    for c in chs:
        mp3 = take_path(c["chunk"])
        dur = duration(mp3)
        rec = rec_all[c["chunk"]]
        script = [(n, norm(w)) for n in range(c["frames"][0], c["frames"][1] + 1) for w in vo[n].split() if norm(w)]
        sm = difflib.SequenceMatcher(a=[w for _, w in script], b=[norm(w[0]) for w in rec], autojunk=False)
        t_of = {}
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                t_of[a + k] = rec[b + k][1]
        matched = len(t_of) / max(1, len(script))
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
            start = t0 - GAP / 2 if i == 0 else t0 + max(0.0, starts[n] - LEAD)
            frames_out.append({"n": n, "chunk": c["chunk"], "start": round(start, 3)})
        concat.append((mp3, t0, dur))
        flag = "" if matched >= 0.9 else "  <-- check this take (low match: missing or extra words?)"
        print(f"chapter {c['chunk']:>2}: {dur:6.2f}s  words matched {matched:.0%}  frames {ns[0]}-{ns[-1]}{flag}",
              flush=True)
        t0 += dur + GAP
    total = t0 - GAP + OUTRO
    frames_out[0]["start"] = 0.0
    for i, f in enumerate(frames_out):
        end = frames_out[i + 1]["start"] if i + 1 < len(frames_out) else total
        f["duration"] = round(end - f["start"], 3)
    acc = 0
    for f in frames_out:                      # snap to whole video frames (30 fps)
        fr = max(15, round((f["start"] + f["duration"]) * 30) - acc)
        f["start"], f["duration"] = acc / 30, fr / 30
        acc += fr
    inputs, filt = [], []
    for k, (mp3, start, _) in enumerate(concat):
        inputs += ["-i", str(mp3)]
        ms = round(start * 1000)
        filt.append(f"[{k}]aresample={SR},aformat=channel_layouts=mono,adelay={ms}|{ms}[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(concat)))
    filt.append(f"{mix}amix=inputs={len(concat)}:normalize=0,apad=whole_dur={acc / 30:.3f}[out]")
    wav = ep().audio / "narration_full.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-ac", "1", "-ar", str(SR), "-t", f"{acc / 30:.3f}", str(wav)], check=True)
    timing = {"voice": f"{nar.get('voice_name')} ({nar.get('voice_id')})", "model": nar.get("model"),
              "aligner": f"faster-whisper small.en ({device})", "intro_s": INTRO, "gap_s": GAP, "outro_s": OUTRO,
              "total_s": acc / 30, "frames": frames_out}
    (ep().audio / "narration_timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    print(f"total {acc / 30:.2f}s ({int(acc / 30 // 60)}:{acc / 30 % 60:05.2f}) -> {wav}")
    return timing
