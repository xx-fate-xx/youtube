"""Soundtrack: sound design from frames.txt + sounds.yaml, then the local mix (free).

Sound library (episodes/<slug>/sounds.yaml): spot effects, looping ambiences and music cues with their
ElevenLabs prompts; Claude generates the missing ones with the ElevenLabs MCP (see `status()`) and saves
them as projects/<slug>/audio/{sfx,music}/<id>.mp3 (read-only).

Placement comes from frames.txt: AMB (ambience bed, persists until changed), SFX (spot effects with offset,
gain, max length, tail), MUSIC (cue start), CHAPTER (whoosh in the dip before each chapter).

Mix -> projects/<slug>/audio/mix_full.wav + stems (stem_music, stem_ambience, stem_sfx):
* every asset is loudness-normalised (EBU R128, measured with FFmpeg) relative to the narration,
  then the cue gain is applied;
* ambience loops are tiled over runs of consecutive frames with 0.8 s fades;
* music cues are cut at their boundaries with a 2 s crossfade inside the dip to black;
* music, ambiences and effects are ducked under the narration (envelope follower), and a rider keeps the
  whole bed >= SPEECH_MARGIN dB under the voice while it speaks (voice always on top);
* a spot never outlives its own frame (cut at the frame end + tail_s, default 0.5 s);
* the master is peak-limited; the render applies the final loudness normalisation.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from . import frames as frames_mod
from .episode import ep

SR = 48000
# ElevenLabs credits actually charged (Creator plan, 2026-11-21): spot effect with automatic length ~17,
# 20 s loop ~67, music ~15 per second (the up-front estimate shows ~27.5/s). Preflight only.
PRICE = {"spot": 17.0, "ambience_per_s": 3.35, "music_per_s": 15.0}
REL = {"spot": -6.0, "ambience": -16.0, "music": -9.0}      # LU relative to the narration (before ducking)


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def lufs(path: Path) -> float:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else -23.0


def db(x: float) -> float:
    return 10 ** (x / 20)


def fade(a: np.ndarray, fin: float, fout: float) -> np.ndarray:
    n = len(a)
    i, o = min(n, int(fin * SR)), min(n, int(fout * SR))
    if i:
        a[:i] *= np.linspace(0, 1, i, dtype=np.float32)[:, None]
    if o:
        a[n - o:] *= np.linspace(1, 0, o, dtype=np.float32)[:, None]
    return a


def place(bus: np.ndarray, clip: np.ndarray, t: float) -> None:
    s = int(round(t * SR))
    if s < 0:
        clip, s = clip[-s:], 0
    e = min(len(bus), s + len(clip))
    if e > s:
        bus[s:e] += clip[: e - s]


def envelope(x: np.ndarray, attack: float = 0.08, release: float = 0.6) -> np.ndarray:
    """0..1 speech presence from the narration (block RMS, gated, attack/release smoothing)."""
    mono = np.abs(x).mean(axis=1)
    hop = SR // 100
    blocks = len(mono) // hop + 1
    rms = np.sqrt(np.add.reduceat(mono ** 2, np.arange(0, len(mono), hop)) / hop)[:blocks]
    gate = (20 * np.log10(rms + 1e-9) > -45).astype(np.float32)
    a, r = np.exp(-1 / (attack * 100)), np.exp(-1 / (release * 100))
    out, g = np.zeros_like(gate), 0.0
    for k, v in enumerate(gate):
        g = a * g + (1 - a) * v if v > g else r * g + (1 - r) * v
        out[k] = g
    return np.repeat(out, hop)[: len(x)]


SPEECH_MARGIN, GAP_MARGIN = 12.0, 3.0        # dB
WIN, HOP = 0.4, 0.05                          # s, short-term level window / hop


def short_rms(x: np.ndarray) -> np.ndarray:
    """Short-term RMS (dBFS-linear) every HOP seconds over a WIN window, mono."""
    mono = x.mean(axis=1) ** 2
    c = np.concatenate([[0.0], np.cumsum(mono, dtype=np.float64)])
    w, h = int(WIN * SR), int(HOP * SR)
    idx = np.arange(0, len(mono), h)
    lo, hi = np.clip(idx - w // 2, 0, len(mono)), np.clip(idx + w // 2, 0, len(mono))
    return np.sqrt((c[hi] - c[lo]) / np.maximum(hi - lo, 1)) + 1e-9


def ref_rms(narr: np.ndarray) -> float:
    r = short_rms(narr)
    return float(np.median(r[r > np.percentile(r, 40)]))       # typical level while speaking


def rider_gain(narr: np.ndarray, bed: np.ndarray, env: np.ndarray, ref: float) -> np.ndarray:
    rn, rb = short_rms(narr), short_rms(bed)
    h = int(HOP * SR)
    speaking = env[::h][: len(rn)] > 0.3
    allowed = np.where(speaking, np.maximum(rn, ref * 0.5) * db(-SPEECH_MARGIN), ref * db(-GAP_MARGIN))
    need = np.minimum(1.0, allowed / rb)
    # look-ahead: take the min over the next 150 ms, then smooth (fast attack, 400 ms release)
    k = int(0.15 / HOP)
    need = np.array([need[i:i + k + 1].min() for i in range(len(need))])
    out, g, rel = np.empty_like(need), 1.0, np.exp(-HOP / 0.4)
    for i, v in enumerate(need):
        g = v if v < g else rel * g + (1 - rel) * v
        out[i] = g
    return np.interp(np.arange(len(narr)), np.arange(len(out)) * h, out).astype(np.float32)


def report_masking(narr: np.ndarray, bed: np.ndarray, env: np.ndarray, start: dict[int, float],
                   label: str = "") -> dict[int, float]:
    """Per frame: 5th-percentile voice-to-bed margin (dB) over windows where the voice is actually sounding."""
    rn, rb = short_rms(narr), short_rms(bed)
    ref = ref_rms(narr)
    voiced = rn > ref * db(-10)
    margin = 20 * np.log10(rn / rb)
    t = np.arange(len(rn)) * HOP
    frames = sorted(start.items(), key=lambda kv: kv[1])
    edges = [s for _, s in frames] + [1e9]
    worst: dict[int, float] = {}
    for k, (n, s0) in enumerate(frames):
        sel = voiced & (t >= s0) & (t < edges[k + 1])
        if sel.sum() >= 3:
            worst[n] = float(np.percentile(margin[sel], 5))
    bad = {n: m for n, m in worst.items() if m < SPEECH_MARGIN - 4.0}   # audibly competing with the voice
    print(f"{label}voice-over-bed margin (5th pct per frame): min {min(worst.values()):.1f} dB, "
          f"median {np.median(list(worst.values())):.1f} dB; frames under {SPEECH_MARGIN - 4:.0f} dB: "
          f"{', '.join(f'#{n} ({m:.1f})' for n, m in sorted(bad.items())) or 'none'}")
    return worst


def sound_design(write: bool = True) -> dict:
    """Cue sheet derived from frames.txt (AMB/SFX/MUSIC/CHAPTER) and sounds.yaml."""
    lib = ep().sounds()
    frames = frames_mod.parse()
    amb_ids = list((lib.get("ambience") or {}).keys())
    runs: dict[str, list[list[int]]] = {}
    for f in frames:
        a = f.get("amb")
        if not a:
            continue
        if a not in amb_ids:
            raise SystemExit(f"frame #{f['n']}: ambience '{a}' is not in sounds.yaml")
        r = runs.setdefault(a, [])
        if r and r[-1][1] == f["n"] - 1:
            r[-1][1] = f["n"]
        else:
            r.append([f["n"], f["n"]])
    spot_ids = set((lib.get("spots") or {}).keys())
    spots = []
    for f in frames:
        for sp in f.get("sfx", []):
            if sp["sfx"] not in spot_ids:
                raise SystemExit(f"frame #{f['n']}: effect '{sp['sfx']}' is not in sounds.yaml")
            spots.append(sp)
    music_ids = set((lib.get("music") or {}).keys())
    starts = [(f["n"], f["music"]) for f in frames if f.get("music")]
    music = []
    for k, (n, m) in enumerate(starts):
        if m["file"] not in music_ids:
            raise SystemExit(f"frame #{n}: music '{m['file']}' is not in sounds.yaml")
        music.append({"file": m["file"], "from_frame": n, "to_frame": starts[k + 1][0] if k + 1 < len(starts) else None,
                      "gain_db": m["gain_db"]})
    wh = lib.get("chapter_whoosh") or {}
    chapter_frames = [n for n, _ in frames_mod.chapters(frames)][1:]
    cue = {"ambience": {a: runs[a] for a in amb_ids if a in runs},
           "ambience_gain_db": {a: v["gain_db"] for a, v in (lib.get("ambience") or {}).items() if v.get("gain_db")},
           "spots": spots,
           "chapter_whoosh": {"sfx": wh.get("sfx"), "frames": chapter_frames if wh.get("sfx") else [],
                              "at": wh.get("at", -0.9), "gain_db": wh.get("gain_db", -12)},
           "music": music,
           "duck_db": lib.get("duck_db") or {"music": 6, "ambience": 4, "sfx": 6}}
    if write:
        ep().audio.mkdir(parents=True, exist_ok=True)
        (ep().audio / "sound_design.json").write_text(json.dumps(cue, ensure_ascii=False, indent=1), encoding="utf-8")
    return cue


def asset_path(kind: str, sid: str) -> Path:
    """Where a newly generated asset of this episode is saved (lookups use ep().sound_file)."""
    return ep().audio / ("music" if kind == "music" else "sfx") / f"{sid}.mp3"


def status() -> dict:
    """Sound library state: which assets exist, which must still be generated, and their credit estimate."""
    lib = ep().sounds()
    out = {"missing": [], "present": [], "credits_missing": 0.0}
    for kind, key in (("spot", "spots"), ("ambience", "ambience"), ("music", "music")):
        for sid, spec in (lib.get(key) or {}).items():
            p = ep().sound_file(kind, sid)
            if kind == "spot":
                cost = PRICE["spot"]
            elif kind == "ambience":
                cost = PRICE["ambience_per_s"] * spec.get("duration", 20)
            else:
                cost = PRICE["music_per_s"] * spec["duration"]
            item = {"id": sid, "kind": kind, "file": str(p), "prompt": spec.get("prompt", ""),
                    "duration": spec.get("duration"), "loop": spec.get("loop", kind == "ambience"), "credits": cost}
            if p.is_file():
                out["present"].append(item)
            else:
                out["missing"].append(item)
                out["credits_missing"] += cost
    return out


def mix(cue: dict | None = None) -> Path:
    AUDIO = ep().audio
    cue = cue or sound_design()
    tm = json.loads((AUDIO / "narration_timing.json").read_text(encoding="utf-8"))
    start = {f["n"]: f["start"] for f in tm["frames"]}
    end = {f["n"]: f["start"] + f["duration"] for f in tm["frames"]}
    total = tm["total_s"]
    n = int(round(total * SR))
    narr_path = AUDIO / "narration_full.wav"
    narr = decode(narr_path)[:n]
    narr = np.pad(narr, ((0, n - len(narr)), (0, 0)))
    tmp = AUDIO / "_narr_stereo.wav"         # measure the narration as it sits in the stereo mix
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(narr_path), "-ac", "2", str(tmp)], check=True)
    ref = lufs(tmp)
    tmp.unlink()
    cache: dict[str, tuple[np.ndarray, float]] = {}

    def asset(name: str, kind: str) -> np.ndarray:
        if name not in cache:
            p = ep().sound_file(kind, name)          # own file, else the sound library's
            cache[name] = (decode(p), lufs(p))
        a, lu = cache[name]
        return a * db(ref + REL[kind] - lu)

    music, amb, sfx = (np.zeros((n, 2), np.float32) for _ in range(3))
    # ambiences
    for name, ranges in cue["ambience"].items():
        g = db(cue.get("ambience_gain_db", {}).get(name, 0))
        loop = asset(name, "ambience") * g
        for a, b in ranges:
            t0, t1 = start[a], end[b]
            k = int((t1 - t0) * SR)
            reps = k // len(loop) + 1
            place(amb, fade(np.tile(loop, (reps, 1))[:k].copy(), 0.8, 0.8), t0)
    # spots
    spots = list(cue["spots"]) + [{"sfx": cue["chapter_whoosh"]["sfx"], "frame": f, "at": cue["chapter_whoosh"]["at"],
                                    "gain_db": cue["chapter_whoosh"]["gain_db"]} for f in cue["chapter_whoosh"]["frames"]]
    for s in spots:
        clip = asset(s["sfx"], "spot") * db(s["gain_db"])
        t0 = start[s["frame"]] + s["at"]
        # a spot never outlives its own frame: cut at the frame end (+ tail_s, default 0.5 s) with a fade
        limit = min(s.get("max_s", 1e9), end[s["frame"]] - t0 + s.get("tail_s", 0.5))
        if len(clip) > limit * SR:
            clip = fade(clip[: int(limit * SR)].copy(), 0.0, min(0.6, limit / 3))
        place(sfx, clip, t0)
    # music
    for m in cue["music"]:
        t0 = 0.0 if m["from_frame"] == 1 else start[m["from_frame"]] - 1.0
        t1 = total if m["to_frame"] is None else start[m["to_frame"]] + 1.0
        clip = asset(m["file"], "music")[: int((t1 - t0) * SR)].copy() * db(m["gain_db"])
        place(music, fade(clip, 0.0 if m["from_frame"] == 1 else 2.0, 3.0 if m["to_frame"] is None else 2.0), t0)
    # ducking under the narration
    env = envelope(narr)[:, None]
    music *= 1 - env * (1 - db(-cue["duck_db"]["music"]))
    amb *= 1 - env * (1 - db(-cue["duck_db"]["ambience"]))
    sfx *= 1 - env * (1 - db(-cue["duck_db"].get("sfx", 6)))
    # rider: the whole bed (music + ambience + effects) stays >= SPEECH_MARGIN dB under the voice while it
    # speaks, and never louder than the voice's average level - GAP_MARGIN dB in the pauses
    bed = music + amb + sfx
    g = rider_gain(narr, bed, env[:, 0], ref_rms(narr))
    music *= g[:, None]
    amb *= g[:, None]
    sfx *= g[:, None]
    report_masking(narr, music + amb + sfx, env[:, 0], start)
    mix = narr + music + amb + sfx
    peak = float(np.abs(mix).max())
    if peak > 0.89:                                  # simple safety gain; render applies loudnorm + limiter
        mix *= 0.89 / peak
    for name, data in (("mix_full", mix), ("stem_music", music), ("stem_ambience", amb), ("stem_sfx", sfx)):
        out = AUDIO / f"{name}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-i", "-",
                        "-c:a", "pcm_s24le", str(out)], input=np.clip(data, -1, 1).astype(np.float32).tobytes(),
                       check=True)
    print(f"narration {ref:.1f} LUFS, peak before safety gain {20 * np.log10(peak):.1f} dBFS, "
          f"{len(spots)} spots, {sum(len(r) for r in cue['ambience'].values())} ambience runs, "
          f"{len(cue['music'])} music cues -> {AUDIO / 'mix_full.wav'}")
    return AUDIO / "mix_full.wav"
