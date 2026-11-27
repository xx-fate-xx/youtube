"""Short (wordless format test): superpowers, the wrong way vs the right way — split screen, music-led.

Three 11-second pairs, then a 3-second end card that cuts back to the opening picture (loop). Each pair starts the
same on both halves and splits apart: left = the wrong way (✗), right = the right way (✓). 2-word labels on top,
no narration, no numbers. Art: the whatif_teleport library (Higgsfield sprites and plates); code draws only the
labels, the marks and small effects (dust, sparks, the bullet, as in the super-speed Shorts).
Half frames are 540x1920: the camera sees a ~560 px wide, nearly full-height slice of a `_v` plate.
"""

from __future__ import annotations

from studio.whatif import fx, overlay, props
from studio.whatif.comic import Comic

W, H, HW = 1080, 1920, 540
SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455, "t": 2005}
HS = {"tower_plate": 440, "beach_plate": 440, "pole_plate": 440, "ocean_plate": 420, "night_plate": 420}
GR = {"tower_plate": 1362, "beach_plate": 1420, "pole_plate": 1380, "ocean_plate": 1250, "night_plate": 1420}
RED, GREEN = "#FF5A4E", "#7CE38B"
SPAN = 11.0                                       # seconds per pair (frames.txt slots)


def _music() -> str:
    from studio.whatif import render
    return "music_vs_fit" if (render.library("sfx") / "music_vs_fit.mp3").is_file() else "music_tense"


def hcam(x: float, ground: float, vw: float = 560, feet: float = 1250) -> tuple[float, float, float]:
    """Half-frame camera (cx, cy, width) on plate x with the ground at screen y `feet`."""
    k = HW / vw
    return x, ground - feet / k + vw * H / HW / 2, vw


def half(shots, plate: str) -> Comic:
    c = Comic(shots=shots, plate=f"{plate}_v")
    c.sheet_ref = dict(SHEET)
    c.shade = (0.35, 420)
    c.cast("hero", height=400)
    c.cast("other", height=400 * 0.98, ref="cleaner0")
    return c


def hero(c, t, spr, x, plate, y=None, who="hero", **kw):
    sc = kw.pop("scale", 1.0)
    c.key(who, t, spr, x, GR[plate] if y is None else y, scale=HS[plate] / 400 * sc, fixed=True, **kw)


def cut(c, t, plate, cam, tween="hold"):
    c.cut(t, f"{plate}_v")
    c.cam(t, *cam, tween)


def labels(left: str, right: str, fade: float = 0.0):
    def f(u, _t):
        op = 1.0 if not fade else min(1.0, u / fade)
        return (overlay.text(HW / 2, 128, left, 54, overlay.TXT, "middle", 800, "Inter Display", ls=3, op=op)
                + overlay.text(HW + HW / 2, 128, right, 54, overlay.TXT, "middle", 800, "Inter Display", ls=3,
                               op=op))
    return f


def mark(side: int, ok: bool, y: float = 360):
    """A big ✗ / ✓ popping in over one half (0 = left, 1 = right)."""
    def f(u, _t):
        k = min(1.0, u / 0.15)
        size = 190 * (1.25 - 0.25 * k)
        return overlay.text(HW / 2 + side * HW, y, "✓" if ok else "✗", size, GREEN if ok else RED, "middle", 900,
                            "Inter Display", op=k)
    return f


def parent(shots, left: Comic, right: Comic) -> Comic:
    c = Comic(shots=shots, plate=left.plate)
    c.sheet_ref = dict(SHEET)
    c.split = (left, right)
    return c


# ---------------------------------------------------------------- pair 1: a falling window cleaner

T1 = "tower_plate"
CX, FALL_X = 1700, 1760                           # the catcher on the street / the fall line (left)
WALL_X = 1880                                     # the climbing line on the facade (right)


def catch_opening(c: Comic, t0, until=None) -> None:
    """Left at its first frame: arms up under a falling cleaner."""
    G = GR[T1]
    c.cam(t0, *hcam(CX + 30, G))
    hero(c, t0, "hero4", CX, T1)
    c.key("other", t0, "cleaner3", FALL_X, 680, scale=0.8, fixed=True)


def brake_opening(c: Comic, t0) -> None:
    """Right at its first frame: halfway up the facade, the cleaner falling beside you."""
    G = GR[T1]
    c.cam(t0, *hcam(WALL_X - 100, G))
    hero(c, t0, "a0", WALL_X, T1, y=980, ang=-90, scale=0.9)
    c.key("other", t0, "cleaner3", FALL_X - 120, 680, scale=0.8, fixed=True)


def pair_catch():
    G = GR[T1]
    a, b = half((1, 1), T1), half((1, 1), T1)
    # left — CATCH: they land in your arms at full speed = a crash
    catch_opening(a, 0.0)
    a.key("other", 1.3, "cleaner3", FALL_X, G - 430, scale=0.8, fixed=True, tween="in")
    a.speed_lines(0.0, 1.3)
    a.hide("other", 1.3)
    hero(a, 1.3, "a3", CX, T1, tween="hold")
    a.shake(1.3, 0.5, 26)
    a.draw(1.3, 4.0, fx.dust(CX, G, size=150, seed=12))
    a.cam(1.3, *hcam(CX + 30, G), "hold")
    a.cam(8.0, *hcam(CX, G, vw=440, feet=1150), "ease")
    hero(a, 6.0, "a3", CX, T1)
    # right — BRAKE: climb, fall alongside, brake slowly down the facade
    brake_opening(b, 0.0)
    hero(b, 0.7, "a0", WALL_X, T1, y=640, ang=-90, scale=0.9, tween="lin", smear=True)
    b.key("other", 0.7, "cleaner3", FALL_X - 120, 740, scale=0.8, fixed=True, tween="lin")
    b.speed_lines(0.0, 0.7)
    hero(b, 0.75, "a1", WALL_X - 10, T1, y=760, ang=37, scale=0.9, tween="hold")
    hero(b, 3.0, "a1", WALL_X - 10, T1, y=980, ang=37, scale=0.9, tween="lin")
    b.key("other", 3.0, "cleaner3", FALL_X - 120, 940, scale=0.8, fixed=True, tween="lin")
    b.hide("other", 3.05)
    hero(b, 3.05, "a2", WALL_X - 60, T1, y=980, tween="hold")
    hero(b, 6.6, "a2", WALL_X - 60, T1, tween="out")
    b.draw(3.05, 6.6, fx.sparks(WALL_X + 30, 1000, n=14, life=0.4, duration=3.4, seed=17))
    b.draw(6.6, 8.5, fx.dust(WALL_X - 60, G, size=120, seed=16))
    hero(b, 7.4, "hero7", WALL_X - 170, T1, tween="hold")
    b.key("other", 7.4, "cleaner0", WALL_X + 50, G, scale=0.98, fixed=True)
    hero(b, 9.6, "a7", WALL_X - 170, T1)
    b.cam(7.4, *hcam(WALL_X - 60, G), "hold")
    b.cam(11.0, *hcam(WALL_X - 60, G, vw=480, feet=1200), "ease")

    c = parent((1, 1), a, b)
    c.text(0.0, SPAN, labels("CATCH", "BRAKE"))
    c.text(1.6, SPAN, mark(0, False))
    c.text(7.6, SPAN, mark(1, True))
    c.sfx(0.0, "sfx_fall", 0.4)
    c.sfx(1.25, "sfx_crash", 0.55)
    c.sfx(3.1, "sfx_scrape", 0.35)
    c.sfx(7.6, "sfx_catch", 0.35)
    c.music(0.0, _music(), 0.7, until=3 * SPAN + 3.0)
    return c


# ---------------------------------------------------------------- pair 2: teleport from the equator

def beach_start(c: Comic, x: float = 1300) -> None:
    B = "beach_plate"
    c.cam(0.0, *hcam(x, GR[B]))
    c.draw(0.0, 0.7, props.portal(x, GR[B] - 10, 380), front=False)
    hero(c, 0.0, "t0", x, B)


def pair_teleport():
    a, b = half((2, 2), "beach_plate"), half((2, 2), "beach_plate")
    beach_start(a)
    beach_start(b)
    # left — NORTH POLE: you arrive with the equator's speed; the ice has none
    P = "pole_plate"
    G = GR[P]
    cut(a, 0.7, P, hcam(520, G))
    hero(a, 0.7, "t1", 520, P, y=G + 10, scale=0.72, tween="hold")
    hero(a, 4.6, "t1", 2150, P, y=G + 10, scale=0.72, tween="lin", smear=True)
    a.cam(4.6, *hcam(2150, G), "lin")
    a.draw(0.7, 4.7, props.spray(520, 2150, 3.9, G + 10, seed=7))
    a.speed_lines(0.7, 4.6)
    a.key("hero", 4.65, None)
    for j in range(12):                           # legs kicking in the drift
        a.draw(4.65 + 0.5 * j, 5.15 + 0.5 * j, props.prop("snow0", 2330, G + 30, HS[P] * 0.95,
                                                          ang=4 if j % 2 else -4, fade=0))
    a.shake(4.65, 0.5, 24)
    a.cam(4.65, *hcam(2300, G), "hold")
    a.cam(11.0, *hcam(2310, G, vw=460, feet=1180), "ease")
    # right — TWIN SPOT: the one place that moves exactly like the beach: you just stand there (in the sea)
    OC = "ocean_plate"
    G2 = GR[OC]
    cut(b, 0.7, OC, hcam(1500, G2, feet=1150))
    b.draw(0.7, 1.5, props.portal(1500, G2 - 10, 380), front=False)
    b.draw(0.7, SPAN, props.submerge(1500, G2, "ocean_plate_v", 260))
    base = G2 + HS[OC] * 0.55
    hero(b, 0.7, "a6", 1500, OC, y=base, tween="hold")
    for j, t in enumerate((2.0, 3.4, 4.8, 6.2, 7.6, 9.0, 10.4)):
        spr = "a6" if t < 4.0 else "hero7"
        hero(b, t, spr, 1500, OC, y=base + (10 if j % 2 else -8), tween="ease")
    b.cam(11.0, *hcam(1500, G2, vw=480, feet=1100), "ease")

    c = parent((2, 2), a, b)
    c.flash(0.0, 0.06)
    c.text(0.0, SPAN, labels("NORTH POLE", "TWIN SPOT"))
    c.text(5.0, SPAN, mark(0, False))
    c.text(3.4, SPAN, mark(1, True))
    c.sfx(0.05, "sfx_teleport", 0.5)
    c.sfx(0.75, "sfx_ice", 0.5)
    c.sfx(0.8, "sfx_water", 0.3)
    c.sfx(4.65, "sfx_crash", 0.45)
    return c


# ---------------------------------------------------------------- pair 3: a bullet heading for a bystander

def pair_bullet():
    N = "night_plate"
    G = GR[N]
    CHEST = G - 250
    a, b = half((3, 3), N), half((3, 3), N)
    # left — SHOVE: you push them out of the way — at your speed the push is the crash
    a.cam(0.0, *hcam(1640, G))
    hero(a, 0.0, "hero2", 1380, N)
    hero(a, 0.5, "hero2", 1560, N, tween="snap", smear=True)
    hero(a, 0.55, "b3", 1580, N)
    a.speed_lines(0.0, 0.5)
    a.key("other", 0.0, "c4", 1760, G, scale=0.95, fixed=True)
    a.key("other", 0.6, "c4", 1760, G, scale=0.95, fixed=True)
    a.key("other", 1.1, "c4", 1950, G - 220, ang=70, scale=0.95, fixed=True, tween="out")
    a.key("other", 1.5, "c4", 1990, G - 20, ang=90, scale=0.95, fixed=True, tween="in")
    a.shake(0.6, 0.4, 22)
    a.shake(1.5, 0.4, 18)
    a.draw(1.5, 3.5, fx.dust(1990, G, size=130, seed=21))
    a.draw(0.9, 1.4, fx.bullet((1300, CHEST), (2300, CHEST), 0.5, scale=1.6))
    a.cam(0.6, *hcam(1640, G), "hold")
    a.cam(1.6, *hcam(1810, G, vw=590), "ease")
    hero(a, 2.6, "hero3", 1650, N, tween="hold")
    a.cam(11.0, *hcam(1810, G, vw=540, feet=1220), "ease")
    # right — MATCH: run beside the bullet at its speed and close your hand: nobody gets hit
    b.cam(0.0, *hcam(1000, G))
    b.cam(4.0, *hcam(1520, G), "lin")
    hero(b, 0.0, "hero2", 900, N)
    hero(b, 4.0, "hero2", 1420, N, tween="lin", smear=True)
    b.draw(0.0, 4.05, fx.bullet((1000, CHEST), (1520, CHEST), 4.0, scale=1.6))
    b.speed_lines(0.0, 4.0)
    hero(b, 4.05, "c3", 1430, N)
    b.key("other", 0.0, "c4", 1720, G, scale=0.95, fixed=True)
    b.cam(5.0, *hcam(1580, G), "ease")
    hero(b, 8.0, "hero7", 1430, N)
    b.cam(11.0, *hcam(1580, G, vw=500, feet=1220), "ease")

    c = parent((3, 3), a, b)
    c.flash(0.0, 0.06)
    c.text(0.0, SPAN, labels("SHOVE", "MATCH"))
    c.text(2.0, SPAN, mark(0, False))
    c.text(4.6, SPAN, mark(1, True))
    c.sfx(0.0, "sfx_dash", 0.4)
    c.sfx(0.6, "sfx_hit", 0.5)
    c.sfx(4.05, "sfx_catch", 0.4)
    return c


# ---------------------------------------------------------------- end card, then the opening again (loop)

def end_card():
    a, b = half((4, 4), T1), half((4, 4), T1)
    catch_opening(a, 0.0)
    brake_opening(b, 0.0)
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
