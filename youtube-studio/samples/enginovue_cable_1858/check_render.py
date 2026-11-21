"""Automatic QA of a rendered episode: frozen picture, unexpected black, audio gaps, A/V length.

Usage: py check_render.py [video.mp4]   (default: newest enginovue_1858_v*_*.mp4 in projects/.../render)

* frozen picture: FFmpeg freezedetect on edge maps (>= FREEZE_S without visible change), mapped to frames;
* black: blackdetect; black is expected only around chapter dips (± DIP_TOL s of a chapter boundary)
  and at the very start/end;
* audio gaps: silencedetect below -50 dBFS for >= 1.2 s;
* lengths: video vs audio stream duration.
Exit code 1 if anything unexpected is found.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "projects" / "enginovue_cable_1858"
FREEZE_S, DIP_TOL = 1.0, 0.6
CHAPTERS = (14, 25, 31, 48, 71, 87, 107, 115, 132, 142)


def run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True).stderr


def main() -> None:
    video = Path(sys.argv[1]) if len(sys.argv) > 1 else max(
        (PROJECT / "render").glob("enginovue_1858_v*_*.mp4"), key=lambda p: p.stat().st_mtime)
    tm = json.loads((PROJECT / "audio" / "narration_timing.json").read_text(encoding="utf-8"))["frames"]
    frame_at = lambda t: next((f["n"] for f in reversed(tm) if f["start"] <= t + 1e-6), 1)  # noqa: E731
    bounds = [f["start"] for f in tm if f["n"] in CHAPTERS]
    problems: list[str] = []

    # freeze test on edge maps: brightness flicker or fades over a frozen picture do not hide the freeze
    log = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-filter_complex",
               "[0:v]split[a][b];[a]scale=640:-1,edgedetect=low=0.08:high=0.25,"
               f"freezedetect=n=-45dB:d={FREEZE_S}[fa];[b]blackdetect=d=0.15:pix_th=0.08[fb]",
               "-map", "[fa]", "-f", "null", "-", "-map", "[fb]", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        problems.append(f"frozen picture {s:.2f}-{e if e is None else round(e, 2)} s "
                        f"(frame #{frame_at(s)}{'' if e is None else f'..#{frame_at(e)}'})")
    for s, e in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log):
        s, e = float(s), float(e)
        expected = s < 0.5 or any(b - DIP_TOL <= s and e <= b + DIP_TOL for b in bounds) or e > tm[-1]["start"] + tm[-1]["duration"] - 0.6
        if not expected:
            problems.append(f"unexpected black {s:.2f}-{e:.2f} s (frame #{frame_at(s)})")

    alog = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af",
                "silencedetect=n=-50dB:d=1.2", "-f", "null", "-"])
    for s in re.findall(r"silence_start: ([\d.]+)", alog):
        if float(s) > 0.5:
            problems.append(f"audio gap from {float(s):.2f} s (frame #{frame_at(float(s))})")

    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0",
                            str(video)], capture_output=True, text=True).stdout.split()
    durs = {p.split(",")[0]: float(p.split(",")[1]) for p in probe}
    if abs(durs.get("video", 0) - durs.get("audio", 0)) > 0.1:
        problems.append(f"video {durs.get('video')} s vs audio {durs.get('audio')} s")

    print(f"{video.name}: video {durs.get('video', 0):.2f} s, audio {durs.get('audio', 0):.2f} s")
    print("\n".join(problems) if problems else "OK: no frozen picture, no unexpected black, no audio gaps")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
