"""Day One — the ink_mindset pilot. Shot 1 (0-16 s): two stacked halves, Blender video plates with a hard cut at
8.06 s from metaphor 1 (STAY / STEP OUT) to metaphor 2 (STAY DOWN / GET UP). Shot 2 (16-26 s): the full-screen
finale; on the track's biggest hit (21.23 s) time stops at the top of his leap: flash, shake, DAY ONE., seal.
Everything sits on the beat grid of the Five Armies cut (0.12 + k * 0.794 s)."""

from __future__ import annotations

import json
from pathlib import Path

from studio.whatif import ink
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 1200, 1066                                  # half plates
FW, FH = 1200, 2132                                  # finale plate
LY, LS = 122, 84
M2 = 8.06                                            # metaphor 2 starts
BEAT = 0.794
ROOT = Path(__file__).resolve().parents[2]


def kv(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    return fx_ * PW, fy * PH, PW / z


def labels(c: Comic, t0: float, t1: float, top: str, bottom: str, under: float | None) -> None:
    c.text(t0, t1, ink.slam(W / 2, LY, top, LS, delay=0.12))
    c.text(t0, t1, ink.slam(W / 2, HH + LY, bottom, LS, delay=0.12 + BEAT))
    if under is not None:
        hw = 0.24 * LS * len(bottom) + 24
        c.text(t0, t1, ink.stroke(W / 2 - hw, HH + LY + 24, W / 2 + hw, 14, delay=under - t0, dur=0.25,
                                  seed=len(bottom)))
    c.sfx(t0 + 0.12, "sfx_brush", 0.55)
    c.sfx(t0 + 0.12 + BEAT, "sfx_brush", 0.45)


def halves():
    a, b = Comic(shots=(1, 1), plate="@p_m1_top"), Comic(shots=(1, 1), plate="@p_m1_bottom")
    a.clip(0.0, "p_m1_top")
    b.clip(0.0, "p_m1_bottom")
    a.clip(M2, "p_m2_top")
    b.clip(M2, "p_m2_bottom")
    for c in (a, b):
        c.cam(0.0, *kv(0.5, 0.52, 1.0))
        c.cam(M2 - 0.01, *kv(0.5, 0.52, 1.06), "lin")
        c.cam(M2, *kv(0.5, 0.52, 1.0), "hold")
        c.cam(16.0, *kv(0.5, 0.52, 1.08), "lin")
        c.shake(1.71, 0.22, 14)                         # the split
        c.shake(M2 + 1.59, 0.3, 22)                     # both fall
    a.shake(6.47, 0.25, 12)                             # his light goes out
    b.shake(4.88, 0.2, 10)                              # dawn
    b.shake(M2 + 4.76, 0.25, 16)                        # up and sprinting
    c = Comic(shots=(1, 1), plate=a.plate)
    c.split, c.stack = (a, b), True
    c.text(0.0, 16.0, ink.seam(W, HH))
    labels(c, 0.0, M2, "STAY", "STEP OUT", 4.88)
    labels(c, M2, 16.0, "STAY DOWN", "GET UP", M2 + 6.35)
    c.text(M2 - 0.45, M2, ink.bleed(W, H, 0.45, cover=True, seed=31))
    c.text(M2, M2 + 0.45, ink.bleed(W, H, 0.45, cover=False, seed=33))
    c.text(16.0 - 0.45, 16.0, ink.bleed(W, H, 0.45, cover=True, seed=37))
    c.sfx(M2 - 0.45, "sfx_bleed", 0.5)
    c.sfx(M2 + 1.59, "sfx_stamp", 0.7)                  # the fall
    c.sfx(16.0 - 0.45, "sfx_bleed", 0.55)
    c.music(0.0, "music_pilot", 0.8, until=26.0)
    return c


def finale():
    J = json.loads((ROOT / "projects/ink_proto3d/render/pilot/fin/joints2d.json").read_text(encoding="utf-8"))
    apex = 5.23
    hx, hy, _ = J[int(round(apex * 30))]["chest"]
    c = Comic(shots=(2, 2), plate="@p_fin")
    c.clip(0.0, "p_fin")
    c.cam(0.0, FW * 0.48, FH * 0.47, FW * 0.78)
    c.cam(apex, FW * 0.5, FH * 0.45, FW * 0.74, "lin")
    c.cam(9.4, hx, hy - 60, FW * 0.52, "ease")           # the slow push-in on the frozen leap
    c.text(0.0, 0.45, ink.bleed(W, H, 0.45, cover=False, seed=39))
    c.flash(apex, 0.08)
    c.shake(apex, 0.35, 26)
    c.text(apex, 10.0, ink.slam(W / 2, 400, "DAY ONE.", 190, delay=0.0))
    c.text(apex, 10.0, ink.stroke(W / 2 - 300, 450, W / 2 + 300, 24, delay=0.5, dur=0.3, seed=12))
    c.text(apex, 10.0, ink.seal(W / 2 + 380, 280, 120, delay=1.2))
    c.text(9.4, 10.0, ink.bleed(W, H, 0.6, cover=True, seed=41))
    c.sfx(apex, "sfx_stamp", 0.8)
    c.sfx(apex + 1.2, "sfx_stamp", 0.5)
    c.sfx(9.4, "sfx_bleed", 0.5)
    return c


def build(size):
    return [halves(), finale()]
