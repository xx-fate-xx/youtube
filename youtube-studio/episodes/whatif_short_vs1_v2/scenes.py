"""Short (wordless format test, v2): superpowers, the wrong way vs the right way — stacked split screen, music-led.

v2 replaces the sprite cut-outs with whole Higgsfield keyframes (Nano Banana 2, characters drawn into the scene with
light, shadows and reflections): each half is a sequence of keyframes with hard cuts, camera moves, shakes and small
code effects (dust, sparks, the bullet). Top half = the wrong way (✗), bottom half = the right way (✓); both halves
start on the same picture. Three 11-second pairs, then a 3-second end card that cuts back to the opening (loop).
Keyframes: projects/whatif_short_vs1_v2/art/kf_*.png (2400x1792); halves are 1080x960.
"""

from __future__ import annotations

from studio.whatif import fx, overlay
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 2400, 1792                               # keyframe size
FULL = PH * W / HH                                # camera width that shows the keyframe's full height
RED, GREEN = "#FF5A4E", "#7CE38B"
SPAN = 11.0


def _music() -> str:
    from studio.whatif import render
    return "music_vs_fit" if (render.library("sfx") / "music_vs_fit.mp3").is_file() else "music_tense"


def kc(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    """Camera on a keyframe: centre at fractions of the picture, zoom z (1 = full height)."""
    return fx_ * PW, fy * PH, FULL / z


def half(shots, plate: str) -> Comic:
    c = Comic(shots=shots, plate=plate)
    c.shade = (0.35, 230)                         # darker top band of each half: the label stays legible
    return c


def cut(c: Comic, t: float, plate: str, cam) -> None:
    c.cut(t, plate)
    c.cam(t, *cam, "hold")


def labels(top: str, bottom: str, fade: float = 0.0):
    def f(u, _t):
        op = 1.0 if not fade else min(1.0, u / fade)
        return (overlay.text(W / 2, 92, top, 56, overlay.TXT, "middle", 800, "Inter Display", ls=3, op=op)
                + overlay.text(W / 2, HH + 92, bottom, 56, overlay.TXT, "middle", 800, "Inter Display", ls=3,
                               op=op))
    return f


def mark(side: int, ok: bool, x: float = 1000, y: float = 104):
    """A ✗ / ✓ popping in at the right end of a half's label band (0 = top, 1 = bottom)."""
    def f(u, _t):
        k = min(1.0, u / 0.15)
        size = 120 * (1.25 - 0.25 * k)
        return overlay.text(x, y + side * HH, "✓" if ok else "✗", size, GREEN if ok else RED, "middle", 900,
                            "Inter Display", op=k)
    return f


def parent(shots, top: Comic, bottom: Comic) -> Comic:
    c = Comic(shots=shots, plate=top.plate)
    c.split = (top, bottom)
    c.stack = True
    return c


# ---------------------------------------------------------------- pair 1: a falling window cleaner

def pair_catch():
    a, b = half((1, 1), "kf_p1_start"), half((1, 1), "kf_p1_start")
    for c in (a, b):
        c.cam(0.0, *kc(0.5, 0.45, 1.0))
    # top — CATCH: they land in your arms at full speed = a crash
    a.cam(1.15, *kc(0.42, 0.42, 1.12), "ease")
    a.speed_lines(0.0, 1.2)
    cut(a, 1.2, "kf_p1_impact", kc(0.5, 0.5, 1.0))
    a.shake(1.2, 0.5, 28)
    cut(a, 1.75, "kf_p1_down", kc(0.5, 0.75, 1.1))
    a.shake(1.75, 0.3, 12)
    a.draw(1.75, 3.6, fx.dust(1200, 1580, size=260, seed=12))
    a.cam(4.45, *kc(0.5, 0.75, 1.2))
    cut(a, 4.5, "kf_p1_down", kc(0.42, 0.76, 2.0))         # close: the catcher, dizzy
    a.cam(6.75, *kc(0.42, 0.76, 2.15))
    cut(a, 6.8, "kf_p1_down", kc(0.64, 0.82, 2.0))         # close: the cleaner, face down
    a.cam(8.95, *kc(0.62, 0.82, 2.15))
    cut(a, 9.0, "kf_p1_down", kc(0.5, 0.75, 1.05))
    a.cam(11.0, *kc(0.5, 0.75, 1.2))
    # bottom — BRAKE: run up, catch them by the wrist, brake down the glass
    cut(b, 0.6, "kf_p1_wallrun", kc(0.52, 0.5, 1.05))
    b.cam(1.55, *kc(0.52, 0.32, 1.15), "ease")
    b.speed_lines(0.6, 1.55)
    cut(b, 1.6, "kf_p1_dive", kc(0.5, 0.3, 1.1))
    b.cam(3.15, *kc(0.52, 0.38, 1.2), "lin")
    b.speed_lines(1.6, 3.15)
    cut(b, 3.2, "kf_p1_slide", kc(0.6, 0.28, 1.15))
    b.cam(5.55, *kc(0.6, 0.42, 1.2), "lin")
    b.shake(3.2, 0.3, 10)
    b.draw(3.2, 5.6, fx.sparks(1755, 480, n=12, life=0.35, duration=2.3, seed=17, direction=150))
    b.draw(3.2, 5.6, fx.sparks(1635, 786, n=12, life=0.35, duration=2.3, seed=18, direction=150))
    cut(b, 5.6, "kf_p1_land", kc(0.45, 0.6, 1.1))
    b.draw(5.6, 6.5, fx.sparks(1560, 1490, n=16, life=0.4, duration=0.6, seed=19, direction=200))
    b.draw(5.9, 7.3, fx.dust(1560, 1520, size=140, seed=16))
    cut(b, 7.3, "kf_p1_safe", kc(0.6, 0.66, 1.0))
    b.cam(9.25, *kc(0.6, 0.66, 1.15))
    cut(b, 9.3, "kf_p1_safe", kc(0.6, 0.6, 1.6))           # close: both of them, fine
    b.cam(11.0, *kc(0.6, 0.6, 1.75))

    c = parent((1, 1), a, b)
    c.text(0.0, SPAN, labels("CATCH", "BRAKE"))
    c.text(2.0, SPAN, mark(0, False))
    c.text(7.6, SPAN, mark(1, True))
    c.sfx(0.0, "sfx_fall", 0.4)
    c.sfx(1.2, "sfx_crash", 0.55)
    c.sfx(3.2, "sfx_scrape", 0.35)
    c.sfx(7.4, "sfx_catch", 0.35)
    c.music(0.0, _music(), 0.7, until=3 * SPAN + 3.0)
    return c


# ---------------------------------------------------------------- pair 2: teleport from the equator

def pair_teleport():
    a, b = half((2, 2), "kf_p2_beach"), half((2, 2), "kf_p2_beach")
    for c in (a, b):
        c.cam(0.0, *kc(0.42, 0.5, 1.05))
        c.cam(0.75, *kc(0.42, 0.5, 1.15), "ease")
    # top — NORTH POLE: you arrive with the equator's speed; the ice has none
    cut(a, 0.8, "kf_p2_skid", kc(0.35, 0.55, 1.15))
    a.cam(4.5, *kc(0.62, 0.55, 1.25), "lin")
    a.speed_lines(0.8, 4.5)
    a.shake(0.8, 0.4, 20)
    cut(a, 4.6, "kf_p2_snow", kc(0.62, 0.55, 1.1))
    a.shake(4.6, 0.5, 26)
    a.cam(6.75, *kc(0.62, 0.55, 1.2))
    cut(a, 6.8, "kf_p2_snow", kc(0.62, 0.43, 1.9))         # close: the legs in the drift
    a.cam(8.95, *kc(0.62, 0.43, 2.05))
    cut(a, 9.0, "kf_p2_snow", kc(0.6, 0.5, 1.0))
    a.cam(11.0, *kc(0.6, 0.5, 1.15))
    # bottom — TWIN SPOT: the one place that moves exactly like the beach: you just stand there (in the sea)
    cut(b, 0.8, "kf_p2_sea", kc(0.5, 0.58, 1.1))
    b.cam(2.55, *kc(0.5, 0.55, 1.2))
    cut(b, 2.6, "kf_p2_sea", kc(0.5, 0.47, 1.8))            # close: blinking, perfectly still
    b.cam(4.45, *kc(0.5, 0.47, 1.95))
    cut(b, 4.5, "kf_p2_sea_ok", kc(0.47, 0.56, 1.15))
    b.cam(6.75, *kc(0.47, 0.54, 1.25))
    cut(b, 6.8, "kf_p2_sea_ok", kc(0.52, 0.42, 1.9))        # close: the thumbs-up
    b.cam(8.95, *kc(0.52, 0.42, 2.05))
    cut(b, 9.0, "kf_p2_sea_ok", kc(0.5, 0.5, 1.0))
    b.cam(11.0, *kc(0.5, 0.5, 1.1))

    c = parent((2, 2), a, b)
    c.flash(0.0, 0.06)
    c.text(0.0, SPAN, labels("NORTH POLE", "TWIN SPOT"))
    c.text(5.0, SPAN, mark(0, False))
    c.text(3.4, SPAN, mark(1, True))
    c.sfx(0.05, "sfx_teleport", 0.5)
    c.sfx(0.85, "sfx_ice", 0.5)
    c.sfx(0.9, "sfx_water", 0.3)
    c.sfx(4.6, "sfx_crash", 0.45)
    return c


# ---------------------------------------------------------------- pair 3: a bullet heading for a bystander

def pair_bullet():
    a, b = half((3, 3), "kf_p3_street"), half((3, 3), "kf_p3_street")
    for c in (a, b):
        c.cam(0.0, *kc(0.5, 0.6, 1.0))
        c.cam(0.55, *kc(0.5, 0.6, 1.06), "ease")
    # top — SHOVE: you push them out of the way — at your speed the push is the crash
    cut(a, 0.6, "kf_p3_shove", kc(0.5, 0.5, 1.0))
    a.shake(0.6, 0.45, 26)
    a.draw(0.9, 1.6, fx.bullet((-100, 1040), (2500, 1040), 0.45, scale=2.2))
    cut(a, 2.2, "kf_p3_down", kc(0.5, 0.6, 1.0))
    a.shake(2.2, 0.3, 14)
    a.cam(4.55, *kc(0.5, 0.6, 1.1))
    cut(a, 4.6, "kf_p3_down", kc(0.72, 0.62, 1.9))         # close: the bystander, knocked out
    a.cam(6.75, *kc(0.72, 0.62, 2.05))
    cut(a, 6.8, "kf_p3_down", kc(0.32, 0.4, 1.9))          # close: your face
    a.cam(8.95, *kc(0.32, 0.4, 2.05))
    cut(a, 9.0, "kf_p3_down", kc(0.5, 0.55, 1.0))
    a.cam(11.0, *kc(0.5, 0.55, 1.1))
    # bottom — MATCH: run beside the bullet at its speed and close your hand: nobody gets hit
    cut(b, 0.6, "kf_p3_run", kc(0.45, 0.55, 1.1))
    b.cam(4.0, *kc(0.55, 0.52, 1.35), "lin")
    b.speed_lines(0.6, 4.0)
    b.draw(0.6, 4.0, fx.bullet((1250, 932), (1330, 932), 3.4, scale=2.2))
    cut(b, 4.0, "kf_p3_catch", kc(0.58, 0.5, 1.0))
    b.cam(6.15, *kc(0.58, 0.5, 1.1))
    cut(b, 6.2, "kf_p3_catch", kc(0.45, 0.3, 2.0))         # close: the bullet in your fingers
    b.cam(8.35, *kc(0.45, 0.3, 2.15))
    cut(b, 8.4, "kf_p3_catch", kc(0.8, 0.35, 1.9))         # close: the bystander, unhurt
    b.cam(9.75, *kc(0.8, 0.35, 2.0))
    cut(b, 9.8, "kf_p3_catch", kc(0.58, 0.5, 1.0))
    b.cam(11.0, *kc(0.58, 0.5, 1.06))

    c = parent((3, 3), a, b)
    c.flash(0.0, 0.06)
    c.text(0.0, SPAN, labels("SHOVE", "MATCH"))
    c.text(2.2, SPAN, mark(0, False))
    c.text(4.6, SPAN, mark(1, True))
    c.sfx(0.5, "sfx_dash", 0.4)
    c.sfx(0.6, "sfx_hit", 0.5)
    c.sfx(4.05, "sfx_catch", 0.4)
    return c


# ---------------------------------------------------------------- end card, then the opening again (loop)

def end_card():
    a, b = half((4, 4), "kf_p1_start"), half((4, 4), "kf_p1_start")
    for c in (a, b):
        c.cam(0.0, *kc(0.5, 0.45, 1.0))
    c = parent((4, 4), a, b)
    c.flash(0.0, 0.06)

    def card(u, _t):
        k = 1.0 if u < 2.3 else max(0.0, 1 - (u - 2.3) / 0.5)
        if k <= 0:
            return ""
        return (f'<rect width="100%" height="100%" fill="#050507" opacity="{0.9 * k:.2f}"/>'
                + overlay.text(W / 2, 860, "PHYSICS", 150, overlay.TXT, "middle", 900, "Inter Display",
                               op=min(1.0, u / 0.2) * (k > 0.9))
                + overlay.text(W / 2, 1040, "SAYS NO", 150, overlay.AMBER, "middle", 900, "Inter Display",
                               op=min(1.0, max(0.0, (u - 0.5) / 0.2)) * (k > 0.9)))
    c.text(0.0, c.end(), card)
    c.text(2.3, c.end(), labels("CATCH", "BRAKE", fade=0.4))
    c.sfx(0.0, "sfx_hit", 0.5)
    return c


def build(size):
    return [pair_catch(), pair_teleport(), pair_bullet(), end_card()]
