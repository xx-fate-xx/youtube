"""Blender prototype composite: top = EXCUSES (wall around him), bottom = STEPS (stairs he climbs). Both halves are
video plates rendered by studio/ink3d/scene_bricks.py (1200x1066, 30 fps); this adds the brush seam, slam labels
on the music's hits, shakes on the brick landings and the ink-bleed out. Not for upload."""

from __future__ import annotations

from studio.whatif import ink
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 1200, 1066
SPAN = 10.0
LY, LS = 122, 84


def kv(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    return fx_ * PW, fy * PH, PW / z


def build(size):
    a, b = Comic(shots=(1, 1), plate="@proto4_top"), Comic(shots=(1, 1), plate="@proto5_bottom")
    a.clip(0.0, "proto4_top")
    b.clip(0.0, "proto5_bottom")
    for c in (a, b):
        c.cam(0.0, *kv(0.5, 0.5, 1.0))
        c.cam(SPAN, *kv(0.5, 0.5, 1.06), "lin")
        c.shake(2.05, 0.25, 14)                       # the hit: building starts
    for t in (3.5, 5.5, 8.0):
        a.shake(t, 0.2, 10)
    b.shake(3.9, 0.2, 12)                             # he steps onto the stairs
    b.shake(8.0, 0.25, 14)
    c = Comic(shots=(1, 1), plate=a.plate)
    c.split, c.stack = (a, b), True
    c.text(0.0, SPAN, ink.seam(W, HH))
    c.text(0.0, SPAN, ink.slam(W / 2, LY, "EXCUSES", LS, delay=0.75))
    c.text(0.0, SPAN, ink.slam(W / 2, HH + LY, "STEPS", LS, delay=1.5))
    c.text(0.0, SPAN, ink.stroke(W / 2 - 150, HH + LY + 24, W / 2 + 150, 14, delay=8.0, dur=0.25, seed=6))
    c.text(SPAN - 0.5, SPAN, ink.bleed(W, H, 0.5, cover=True, seed=37))
    c.music(0.0, "music_epic", 0.9, until=SPAN)
    c.sfx(SPAN - 0.55, "sfx_bleed", 0.6)
    return [c]
