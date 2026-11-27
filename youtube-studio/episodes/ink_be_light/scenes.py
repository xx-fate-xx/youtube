"""Be the Light — ink_mindset Short #3: four A|B skits (studio/ink3d/skits.py, drawn by stage2d at 60 fps) on the
Waka Floka Type cut (drop 5.06 s; 808 hits 12.56 / 21.04 / 28.45 s)."""

from __future__ import annotations

from studio.whatif import ink
from studio.whatif.ink_short import HH, Skit, W
from studio.whatif.ink_short import build as build_short

T3 = 14.8


def _clock():
    """A small brush clock in the 5 AM skit: the hour creeps on while he runs; the sunrise time in vermilion."""
    marks = [(0.1, "5:00"), (1.6, "5:20"), (3.0, "5:41"), (4.6, "5:58"), (6.24, "6:12")]
    out = []
    for k, (t, s) in enumerate(marks):
        t1 = marks[k + 1][0] if k + 1 < len(marks) else 7.4
        fill = ink.VERMILION if k == len(marks) - 1 else ink.INK
        out.append((T3 + t, T3 + t1, ink.label(W * 0.17, HH + 250, s, 64, dur=0.15, fill=fill)))
    return out


SKITS = [Skit(0.0, "WAIT FOR LIGHT", "BE THE LIGHT", 5.06, "lantern"),
         Skit(7.4, "STAY SAFE", "STEP OUT", 12.56, "bubble"),
         Skit(T3, "SLEEP IN", "5 AM", 21.04, "dawn"),
         Skit(22.2, "WAIT FOR WIND", "MAKE WIND", 28.45, "kite")]


def build(size):
    return build_short(SKITS, prefix="s3b", music="music_waka", end=29.6)
