"""Rise Eight — ink_mindset Short #2: four A|B skits (studio/ink3d/skits.py, drawn by stage2d at 60 fps) on the
Waka Floka Type cut (drop 5.06 s; 808 hits 12.56 / 21.04 / 28.45 s)."""

from __future__ import annotations

from studio.whatif import ink
from studio.whatif.ink_short import HH, Skit, W
from studio.whatif.ink_short import build as build_short

FALLS = [0.55, 1.35, 2.05, 2.7, 3.25, 3.75, 4.2]     # studio/ink3d/skits.py wind(): the seven knock-downs
T4 = 22.2


def _counter():
    """Big brush numerals by the hero in the wind skit: 1..7 on each fall, a vermilion 8 on the beat."""
    out = []
    for k, g in enumerate(FALLS):
        t = T4 + g + 0.12
        t1 = T4 + (FALLS[k + 1] if k + 1 < len(FALLS) else 5.0) + 0.1
        out.append((t, t1, ink.slam(W * 0.12, HH + 290, str(k + 1), 120, delay=0.0)))
    out.append((28.45, 29.6, ink.slam(W * 0.12, HH + 290, "8", 150, delay=0.0, fill=ink.VERMILION)))
    return out


SKITS = [Skit(0.0, "PLAN IT", "STEP IN", 5.06, "steps"),
         Skit(7.4, "QUIT", "REST", 12.56, "rest"),
         Skit(14.8, "AVOID IT", "FACE IT", 21.04, "fear"),
         Skit(T4, "WAIT FOR CALM", "RISE 8", 28.45, "wind", extra=_counter())]


def build(size):
    return build_short(SKITS, prefix="s2b", music="music_waka", end=29.6)
