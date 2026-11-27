"""Energy test: metaphor 1 (COMFORT vs GROWTH) cut to the epic track — cuts and hits on the music's onsets,
a Kling clip as the bottom half's video plate (sped up), slam labels, ink splashes, shakes. Not for upload.

Music onsets (music_epic.mp3, energy flux): 0.75 1.50 3.50 4.00 4.75 5.50 6.75 8.00 8.75 9.50 s.
"""

from __future__ import annotations

from studio.whatif import ink
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 2400, 1792                               # keyframes
CW = 960                                          # Kling clips are 960x960
FULL = PH * W / HH
SPAN = 12.0
LY, LS = 122, 84


def kc(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    return fx_ * PW, fy * PH, FULL / z


def kv(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    """Camera on a 960x960 clip: z=1 shows the full width (the half is 1080x960, so 11 % of the height is cut)."""
    return fx_ * CW, fy * CW, CW / z


def cut(c: Comic, t: float, plate: str, cam) -> None:
    c.cut(t, plate)
    c.cam(t, *cam, "hold")


def clip(c: Comic, t: float, name: str, cam, speed: float = 1.0, offset: float = 0.0) -> None:
    c.clip(t, name, speed, offset)
    c.cam(t, *cam, "hold")


def hit(c: Comic, t: float, amp: float = 16) -> None:
    c.shake(t, 0.22, amp)


def build(size):
    a, b = Comic(shots=(1, 1), plate="kf_m1_chair"), Comic(shots=(1, 1), plate="@kling_lantern")
    # top — COMFORT (keyframes): every cut lands on a hit
    a.cam(0.0, *kc(0.5, 0.6, 1.1))
    a.cam(1.45, *kc(0.5, 0.62, 1.35), "lin")
    cut(a, 1.5, "kf_m1_chair", kc(0.5, 0.64, 2.3))            # phone glow on the face
    a.cam(3.45, *kc(0.5, 0.64, 2.6), "lin")
    cut(a, 3.5, "kf_m1_chair_late", kc(0.47, 0.6, 1.1))       # later: dust, cups
    a.cam(5.45, *kc(0.47, 0.62, 1.3), "lin")
    cut(a, 5.5, "kf_m1_chair_late", kc(0.45, 0.65, 1.9))      # the cups
    a.cam(7.95, *kc(0.42, 0.66, 2.2), "lin")
    cut(a, 8.0, "kf_m1_chair_late", kc(0.52, 0.62, 2.8))      # tight on the sagging head
    a.cam(SPAN, *kc(0.52, 0.62, 3.2), "lin")
    for t in (1.5, 3.5, 5.5, 8.0):
        hit(a, t, 12)
    # bottom — GROWTH: the Kling walk (sped up), the summit, the walk again
    clip(b, 0.0, "kling_lantern", kv(0.5, 0.55, 1.0), speed=1.35)
    b.cam(3.45, *kv(0.58, 0.6, 1.35), "lin")
    cut(b, 3.5, "kf_m1_summit_v2", kc(0.52, 0.55, 1.05))
    b.cam(5.45, *kc(0.55, 0.53, 1.3), "lin")
    cut(b, 5.5, "kf_m1_summit_v2", kc(0.6, 0.54, 1.8))
    b.cam(7.95, *kc(0.6, 0.52, 2.2), "lin")
    clip(b, 8.0, "kling_lantern", kv(0.68, 0.62, 1.45), speed=1.0, offset=2.0)
    b.cam(SPAN, *kv(0.72, 0.62, 1.7), "lin")
    for t in (3.5, 5.5, 8.0):
        hit(b, t, 16)

    c = Comic(shots=(1, 1), plate=a.plate)
    c.split, c.stack = (a, b), True
    c.text(0.0, SPAN, ink.seam(W, HH))
    c.text(0.0, SPAN, ink.slam(W / 2, LY, "COMFORT", LS, delay=0.0))
    c.text(0.0, SPAN, ink.slam(W / 2, HH + LY, "GROWTH", LS, delay=0.75))
    c.text(0.0, SPAN, ink.stroke(W / 2 - 190, HH + LY + 24, W / 2 + 190, 14, delay=4.0, dur=0.25, seed=6))
    c.text(0.0, SPAN, ink.splash(880, 640, 150, seed=4, delay=4.75))
    c.text(0.0, SPAN, ink.splash(200, HH + 700, 170, seed=8, delay=6.75))
    c.text(0.0, SPAN, ink.splash(860, 520, 130, seed=12, delay=9.5))
    c.text(SPAN - 0.5, SPAN, ink.bleed(W, H, 0.5, cover=True, seed=37))
    c.flash(0.0, 0.05)
    c.music(0.0, "music_epic", 0.9, until=SPAN)
    c.sfx(SPAN - 0.55, "sfx_bleed", 0.6)
    return [c]
