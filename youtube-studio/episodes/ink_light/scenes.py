"""STAY vs STEP OUT — two Blender halves (1200x1066 video plates) + labels on the beat, a hit shake on the split,
the light-out splash, the dawn underline and an ink-bleed out. Music: Five Armies cut (90 bpm, beat 0.67 s)."""

from __future__ import annotations

from studio.whatif import ink
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 1200, 1066
SPAN = 11.0
LY, LS = 122, 84
SPLIT, DAWN, OUT = 1.84, 8.54, 9.21


def kv(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    return fx_ * PW, fy * PH, PW / z


def build(size):
    a, b = Comic(shots=(1, 1), plate="@s2_topb"), Comic(shots=(1, 1), plate="@s3_bottomb")
    a.clip(0.0, "s2_topb")
    b.clip(0.0, "s3_bottomb")
    for c in (a, b):
        c.cam(0.0, *kv(0.5, 0.52, 1.0))
        c.cam(SPAN, *kv(0.5, 0.52, 1.05), "lin")
        c.shake(SPLIT, 0.22, 14)
    a.shake(OUT, 0.25, 12)
    b.shake(DAWN, 0.25, 12)
    c = Comic(shots=(1, 1), plate=a.plate)
    c.split, c.stack = (a, b), True
    c.text(0.0, SPAN, ink.seam(W, HH))
    c.text(0.0, SPAN, ink.slam(W / 2, LY, "STAY", LS, delay=0.50))
    c.text(0.0, SPAN, ink.slam(W / 2, HH + LY, "STEP OUT", LS, delay=1.17))
    c.text(0.0, SPAN, ink.stroke(W / 2 - 185, HH + LY + 24, W / 2 + 185, 14, delay=DAWN, dur=0.25, seed=6))
    c.text(SPAN - 0.55, SPAN, ink.bleed(W, H, 0.55, cover=True, seed=37))
    c.music(0.0, "music_five_armies", 0.75, until=SPAN)
    return [c]
