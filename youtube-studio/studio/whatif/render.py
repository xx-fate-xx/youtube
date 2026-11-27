"""Render a What If episode: scenes.py sequences -> clips -> one MP4 with the narration/mix (same outputs and
names as studio.pipeline.render, so check/release work unchanged).

episodes/<slug>/scenes.py must define `build(size) -> list[Seq]`. Shots not covered by any sequence get a
placeholder card (marked in the report). Durations: aligned narration (narration_timing.json) or, with
--silent / before narration exists, the storyboard slots from frames.txt. Backgrounds: projects/<slug>/bg/<id>.png
(and optional <id>_night.png).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ..pipeline import episode as episode_mod
from ..pipeline import frames as frames_mod
from ..pipeline import render as prender
from ..pipeline.episode import ep
from . import comic, scene


def library(kind: str) -> Path:
    """projects/<slug>/<kind>, or the sound/art library of the parent episode (Shorts reuse the long video's art)."""
    own = ep().work / kind
    if own.is_dir():
        return own
    lib = ep().cfg.get("sound_library") or ep().cfg.get("parent")
    return ep().work.parent / lib / kind if lib else own


def load_scenes(size: tuple[int, int]) -> list[scene.Seq]:
    f = ep().src / "scenes.py"
    if not f.is_file():
        return []
    spec = importlib.util.spec_from_file_location(f"scenes_{ep().slug}", f)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.build(size)


def durations(silent: bool) -> tuple[dict[int, float], dict | None]:
    parsed = frames_mod.parse()
    tf = ep().audio / "narration_timing.json"
    pad = float(ep().cfg.get("end_screen", 0) or 0)          # seconds of end screen after the last line
    if tf.is_file() and not silent:
        timing = json.loads(tf.read_text(encoding="utf-8"))
        d = {f["n"]: f["duration"] for f in timing["frames"]}
    else:
        d, timing = {f["n"]: float(f["duration"]) for f in parsed}, None
    if pad and d:
        d[max(d)] += pad
    return d, timing


def plan(size: tuple[int, int]) -> list[scene.Seq]:
    """Sequences in shot order; uncovered shots become single-shot placeholder sequences."""
    seqs = load_scenes(size)
    covered = {n for s in seqs for n in range(s.shots[0], s.shots[1] + 1)}
    parsed = frames_mod.parse()
    for f in parsed:
        if f["n"] not in covered:
            ph = scene.Seq(shots=(f["n"], f["n"]), bg=f"NO SCENE #{f['n']}", push=(1.0, 1.0))
            ph.placeholder = True  # type: ignore[attr-defined]
            seqs.append(ph)
    return sorted(seqs, key=lambda s: s.shots[0])


CHUNK = 150          # frames per parallel job (5 s)


def _job(args: tuple) -> str:
    """Worker: rebuild the sequences of the episode, bake one, encode frames [i0, i1)."""
    src, idx, i0, i1, out, silent, crf = args
    episode_mod.use(src)
    size = ep().size
    seq = plan(size)[idx]
    durs, _ = durations(silent)
    if isinstance(seq, comic.Comic):
        seq.art = library("art")
        n = max(1, round(seq.layout(durs) * comic.FPS))
        comic.encode(seq, i0, min(i1, n), Path(out), size, crf, threads=2)
        return out
    bk = scene.Baked(seq, seq.layout(durs), 30)
    scene.encode(seq, bk, i0, min(i1, bk.n), Path(out), ep().work / "bg", size, crf, threads=2)
    return out


COOLDOWN = {"sfx_hit": 14.0, "sfx_freeze": 12.0, "sfx_chalk": 10.0, "sfx_dash": 5.0, "sfx_catch": 8.0}
# Spot effects are accents: anything longer is cut with a short fade (sfx_alert is a 15 s warning siren that
# once played in full under a Short). Ambiences and long one-offs get their own limit.
SFX_MAX_S = 2.5
SFX_MAX = {"sfx_wind": 12.0, "sfx_deep": 8.0, "sfx_rocket": 8.0, "sfx_sonic": 4.0, "sfx_slowmo": 3.0, "sfx_ice": 4.0,
           "sfx_alert": 1.2, "sfx_alarm": 1.5}


def add_cues(video: Path, cues: list, total: float) -> None:
    """Mix scene sound cues (SFX; music beds looped to their length) from projects/<slug>/sfx under the existing
    audio track, in place."""
    sfx_dir = library("sfx")
    ins, filt, labels = [], [], ["[0:a]"]
    last: dict[str, float] = {}
    kept = []
    for cue in sorted(cues, key=lambda c: c[0]):           # the same effect never repeats within COOLDOWN s
        t, name, _vol, kind, _dur = cue
        gap = COOLDOWN.get(name, 4.0)
        if kind == "sfx" and t - last.get(name, -1e9) < gap:
            continue
        last[name] = t
        kept.append(cue)
    for t, name, vol, kind, dur in kept:
        f = sfx_dir / f"{name}.mp3"
        if not f.is_file():
            print(f"missing sound cue: {f}")
            continue
        k = len(labels)
        ms = max(0, int(t * 1000))
        if kind == "music" and dur:
            ins += ["-stream_loop", "-1", "-i", str(f)]
            shape = f",atrim=0:{dur:.2f},afade=t=in:d=1.0,afade=t=out:st={max(0.0, dur - 1.5):.2f}:d=1.5"
        else:
            ins += ["-i", str(f)]
            mx = SFX_MAX.get(name, SFX_MAX_S)
            shape = f",atrim=0:{mx:.2f},afade=t=out:st={max(0.0, mx - 0.4):.2f}:d=0.4"
        filt.append(f"[{k}:a]aresample=48000{shape},adelay={ms}|{ms},volume={vol}[c{k}]")
        labels.append(f"[c{k}]")
    if len(labels) == 1:
        return
    filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,alimiter=limit=0.95[mix]")
    tmp = video.with_name(video.stem + "_cues.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), *ins, "-filter_complex", ";".join(filt),
                    "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)


def _low_priority() -> None:
    """Run render workers (and the ffmpeg they start) below normal priority so the PC stays usable."""
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
        else:
            os.nice(10)
    except Exception:
        pass


def render_parallel(seqs: list[tuple[int, scene.Seq]], durs: dict[int, float], work: Path, silent: bool,
                    crf: int, workers: int | None = None) -> list[Path]:
    """All sequences split into 5 s chunks, rendered on all cores, chunks joined per sequence (stream copy)."""
    jobs, parts = [], {}
    for idx, s in seqs:
        n = max(1, round(s.layout(durs) * (comic.FPS if isinstance(s, comic.Comic) else 30)))
        a, b = s.shots
        parts[idx] = []
        for k, i0 in enumerate(range(0, n, CHUNK)):
            out = work / f"seq_{a:03d}_{b:03d}_part{k:03d}.mp4"
            parts[idx].append(out)
            jobs.append((str(ep().src), idx, i0, i0 + CHUNK, str(out), silent, crf))
    # 12 workers (x2 ffmpeg threads, each holding the art caches) shut the operator's PC down (2026-11-23):
    # default 4, override with WHATIF_WORKERS; workers run at below-normal priority.
    workers = workers or max(1, int(os.environ.get("WHATIF_WORKERS", "4")))
    print(f"{len(jobs)} chunks on {workers} processes", flush=True)
    with ProcessPoolExecutor(max_workers=workers, initializer=_low_priority) as pool:
        for k, _ in enumerate(pool.map(_job, jobs), 1):
            if k % max(1, len(jobs) // 10) == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)} chunks done", flush=True)
    clips = []
    for idx, s in seqs:
        a, b = s.shots
        clip = work / f"seq_{a:03d}_{b:03d}.mp4"
        lst = work / f"seq_{a:03d}_{b:03d}.txt"
        lst.write_text("".join(f"file '{q.as_posix()}'\n" for q in parts[idx]), encoding="utf-8")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                        str(clip)], check=True)
        for q in parts[idx]:
            q.unlink(missing_ok=True)
        clips.append(clip)
    return clips


def run(only: str | None = None, crf: int = 18, silent: bool = False) -> Path:
    fps = int(ep().cfg.get("fps", 30))                     # e.g. 60 for Shorts with fast action
    os.environ["COMIC_FPS"] = str(fps)                     # render workers re-import comic and read it
    comic.FPS = fps
    size = ep().size
    w, h = size
    out = ep().render_dir
    work = out / "work_whatif"
    work.mkdir(parents=True, exist_ok=True)
    durs, timing = durations(silent)
    indexed = list(enumerate(plan(size)))
    if only:
        lo, hi = (int(x) for x in only.split("-"))
        indexed = [(k, s) for k, s in indexed if s.shots[1] >= lo and s.shots[0] <= hi]
    seqs = [s for _, s in indexed]
    bg_dir = ep().work / "bg"
    clips, report, t = [], [], 0.0
    vo = {f["n"]: f["vo"] for f in frames_mod.parse()}
    srt = []
    del bg_dir
    clips = render_parallel(indexed, durs, work, silent, crf)
    cues = []
    for s in seqs:
        a, b = s.shots
        if isinstance(s, comic.Comic):
            s.layout(durs)
            cues += [(t + s.T(at), name, vol, kind, (s.T(u) - s.T(at)) if u is not None else None)
                     for at, name, vol, kind, u in s.cues]
        for n in range(a, b + 1):
            srt.append(f"{len(srt) + 1}\n{prender.ts(t)} --> {prender.ts(t + durs[n])}\n{vo[n]}\n")
            t += durs[n]
        ph = getattr(s, "placeholder", False)
        report.append(f"| #{a}–#{b} | {s.bg} | {sum(durs[n] for n in range(a, b + 1)):.2f}s | "
                      f"{'PLACEHOLDER' if ph else len(s.actors)} | {len(s.freezes)} | {len(s.booms)} |")
    nm = prender.names()
    mixf = ep().audio / "mix_full.wav"
    voiced = timing is not None
    base = (nm["mixed"] if mixf.is_file() else nm["voiced"]) if voiced else nm["silent"]
    stem = base if not only else f"{base}_preview_{only}"
    lst = work / f"concat_{stem}.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    video = out / f"{stem}.mp4"
    first = seqs[0].shots[0]
    if voiced:
        t_start = {f["n"]: f["start"] for f in timing["frames"]}[first]
        track = mixf if mixf.is_file() else ep().audio / "narration_full.wav"
        audio_in = ["-ss", f"{t_start:.3f}", "-t", f"{t:.3f}", "-i", str(track)]
        audio_f = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.89:level=disabled,aresample=48000,apad",
                   "-ac", "2", "-b:a", "192k"]
    else:
        t_start = 0.0
        audio_in, audio_f = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"], []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), *audio_in,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", *audio_f, "-shortest",
                    "-movflags", "+faststart", str(video)], check=True)
    if cues:
        add_cues(video, cues, t)
    (out / f"{stem}.srt").write_text("\n".join(srt), encoding="utf-8")
    if ep().vertical and voiced:
        prender.burn_captions(video, t_start, t, work)
    ph = sum(1 for r in report if "PLACEHOLDER" in r)
    (out / f"render_report_{stem}.md").write_text(
        f"# Render report — {stem}\n\nWhat If engine, {w}x{h}, {comic.FPS} fps. Sequences: {len(report)}, placeholders: "
        f"{ph}, duration {t:.1f} s, {'voiced' if voiced else 'silent (storyboard slots)'}.\n\n"
        "| Shots | Background | Length | Actors | Freezes | Booms |\n|---|---|---|---|---|---|\n"
        + "\n".join(report) + "\n", encoding="utf-8")
    print(f"video: {video}\n{len(report)} sequences, {t:.1f} s, placeholders {ph}")
    return video
