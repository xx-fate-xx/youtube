"""Motion-comic scenes for "What If You Could Teleport? (Your Speed Comes Too)" — v3 (16:9, ~8:03).

Operator feedback on v2 (2026-11-23): too short, the opening stays at one location, the code-drawn Earth / doodles /
rings looked cheap, the hero was tiny in the room. v3: all props and globes are Higgsfield art (art/globe0 top view,
globe1 side view, portal0, wall0, bike0, car0; plates incl. iss, mars, space); only chalk arrows and chalk/kinetic
text are drawn in code. Montages use Comic.cut (plate cuts inside a comic). Hero height per plate (HS) and cameras
that always keep the feet in frame (camg). The v2 scenes are kept in scenes_v2.py.

Shot numbers: frames.txt (75 shots from script.md v3). Numbers on screen: script.md calc_notes / factcheck_report.md.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from studio.whatif import fx, overlay
from studio.whatif.comic import Comic, counter, label, punch

W, H = 1920, 1080
SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455, "t": 2005}
CH, AMB = overlay.CHALK, overlay.AMBER
HS = {"tower_plate": 400, "highway_plate": 400, "room_plate": 640, "beach_plate": 430, "pole_plate": 430,
      "jungle_plate": 450, "ocean_plate": 400, "sky_plate": 420, "trench_plate": 470, "moon_plate": 430,
      "mars_plate": 430, "iss_plate": 420, "launch_plate": 430, "night_plate": 380, "space_plate": 400}
GR = {"tower_plate": 1362, "highway_plate": 1400, "room_plate": 1440, "beach_plate": 1420, "pole_plate": 1380,
      "jungle_plate": 1440, "ocean_plate": 1250, "sky_plate": 1000, "trench_plate": 1470, "moon_plate": 1430,
      "mars_plate": 1440, "launch_plate": 1450, "night_plate": 1420}
WIDE = (1344, 760, 2688)


def new(shots, plate, **kw) -> Comic:
    c = Comic(shots=shots, plate=plate, **kw)
    c.sheet_ref = dict(SHEET)
    c.cast("hero", height=400)                       # base height; per-plate size via k(plate) on each key
    return c


def k(plate: str) -> float:
    return HS[plate] / 400


def camg(x, ground, vw=1900, feet=0.84):
    """Camera (cx, cy, width) with the ground line at `feet` of the screen height (feet always in frame)."""
    vh = vw * H / W
    return x, ground - (feet - 0.5) * vh, vw


def scr(cam, x, y):
    cx, cy, vw = cam
    kk = W / vw
    vh = vw * H / W
    x0 = min(max(cx - vw / 2, 0), 2688 - vw)
    y0 = min(max(cy - vh / 2, 0), 1520 - vh)
    return (x - x0) * kk, (y - y0) * kk


def hero(c: Comic, t, spr, x, y, plate, **kw):
    sc = kw.pop("scale", 1.0)
    c.key("hero", t, spr, x, y, scale=k(plate) * sc, fixed=True, **kw)


# ---------------------------------------------------------------- text

def ch(x, y, s, size, u, at=0.0, d=0.5, bold=False, anchor="start"):
    t = overlay.chalk_text(x, y, s, size, (u - at) / d, 800 if bold else 600, "Inter Display" if bold else "Inter",
                           anchor)
    return overlay.shadowed(t) if t else t


def am(x, y, s, size, u, at=0.0, anchor="start", weight=800):
    kk = max(0.0, min(1.0, (u - at) / 0.2))
    return overlay.shadowed(overlay.text(x, y, s, size, AMB, anchor, weight, "Inter Display", op=kk)) if kk else ""


def big(x, y, s, size, u, at=0.0, anchor="start"):
    kk = max(0.0, min(1.0, (u - at) / 0.2))
    return overlay.shadowed(overlay.text(x, y, s, size, anchor=anchor, op=kk)) if kk else ""


def arrow(x0, y0, x1, y1, u, at=0.0, d=0.35, seed=1):
    return overlay.chalk_arrow(x0, y0, x1, y1, (u - at) / d, seed)


# ---------------------------------------------------------------- Higgsfield props drawn into the world

def _art():
    from studio.whatif import render
    return render.library("art")


@lru_cache(maxsize=256)
def _img(name: str, h: int, flip: bool = False, ang: int = 0) -> Image.Image:
    from studio.whatif.thumbs import _sprite
    return _sprite(_art(), name, h, flip, ang)


def _paste(img, s, x, ground):
    from studio.whatif.comic import _composite
    _composite(img, s, int(x - s.width / 2), int(ground - s.height))


def prop(name, x, ground, h, flip=False, ang=0, fade=0.2, slide=None, dur=1.0, tween=lambda q: q):
    """World draw: a Higgsfield prop standing on `ground` at x (slide=(x1, ground1) moves it over `dur` s)."""
    def f(img: Image.Image, u, _t):
        a = min(1.0, u / fade) if fade else 1.0
        xx, gg = x, ground
        if slide:
            p = tween(min(1.0, u / dur))
            xx, gg = x + (slide[0] - x) * p, ground + (slide[1] - ground) * p
        s = _img(name, int(h), flip, int(ang))
        if a < 1:
            s = s.copy()
            s.putalpha(s.getchannel("A").point(lambda v: int(v * a)))
        _paste(img, s, xx, gg)
    return f


def portal(x, y, w=300, life=0.9, keep=False):
    """World draw: the Higgsfield portal sprite snapping open at (x, y) (centre) and closing (unless keep)."""
    def f(img, u, _t):
        if not keep and u > life:
            return
        if keep:
            s = min(1.0, u / 0.18)
        else:
            q = u / life
            s = min(1.0, q / 0.2) if q < 0.7 else max(0.0, 1 - (q - 0.7) / 0.3)
        if s <= 0.02:
            return
        base = _img("portal0", int(w * 0.55))
        ww = max(2, int(base.width * s))
        hh = max(2, int(base.height * (0.6 + 0.4 * s)))
        im = base.resize((ww, hh), Image.Resampling.BILINEAR)
        if keep:                                                     # a living portal shimmers
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * (0.85 + 0.15 * math.sin(u * 7)))))
        _paste(img, im, x, y + hh / 2)
    return f


def tp(c: Comic, at, x, y, w=300, sound=True):
    c.draw(at, c.end(), portal(x, y, w), front=False)
    if sound:
        c.sfx(at, "sfx_teleport", 0.5)


@lru_cache(maxsize=96)
def _globe_rot(idx: int, size: int, ang10: int) -> Image.Image:
    g = _img(f"globe{idx}", size)
    return g.rotate(ang10 / 10, resample=Image.Resampling.BICUBIC) if ang10 else g


def globe(idx, x, y, size, spin=0.0, a0=0.0):
    """World draw: the painted Earth (idx 0 from above the North Pole, 1 from the side) centred at (x, y);
    spin = degrees per second."""
    def f(img, u, _t):
        ang = (a0 + spin * u) % 360
        g = _globe_rot(idx, int(size), int(round(ang * 10)) // 5 * 5)
        _paste(img, g, x, y + g.height / 2)
    return f


def spray(x0, x1, dur, y, seed=5, every=0.06, col=(240, 248, 255)):
    def f(img, u, _t):
        d = ImageDraw.Draw(img, "RGBA")
        sgn = 1 if x1 >= x0 else -1
        for kk in range(int(min(u, dur) / every) + 1):
            te = kk * every
            age = u - te
            if age < 0 or age > 0.9:
                continue
            ex = x0 + (x1 - x0) * min(1.0, te / dur)
            r = random.Random(seed * 1000 + kk)
            fade = 1 - age / 0.9
            for _j in range(6):
                vx, vy = -sgn * r.uniform(80, 320), -r.uniform(240, 560)
                px, py = ex + vx * age, y + vy * age + 1100 * age * age
                if py > y + 6:
                    continue
                rr = r.uniform(5, 12)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(*col, int(220 * fade)))
    return f


def submerge(x, sea, half=260, plate="ocean_plate"):
    def f(img, _u, _t):
        from studio.whatif.comic import _plate
        pl = _plate(str(_art()), plate)
        box = (int(x - half), int(sea) - 4, int(x + half), pl.height)
        img.alpha_composite(pl.crop(box), (box[0], box[1]))
    return f


def halo(x, y, r=260, col=(150, 190, 255), a=70):
    """World draw: a soft light behind a dark figure on a black sky (so the black head stays readable)."""
    def f(img, u, _t):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        k_ = min(1.0, u / 0.4)
        for j in range(8):
            rr = r * (1 - j / 9)
            d.ellipse([x - rr, y - rr * 1.15, x + rr, y + rr * 1.15], fill=(*col, int(a * k_ * (j + 1) / 8 / 2.2)))
        img.alpha_composite(layer)
    return f


def flash_card(text, sub=""):
    def f(u, _t):
        kk = min(1.0, u / 0.12)
        z = 1 + 0.05 * u
        return (f'<rect width="{W}" height="{H}" fill="#050507"/>'
                f'<g transform="translate({W / 2},{H / 2}) scale({z:.4f}) translate({-W / 2},{-H / 2})">'
                + overlay.text(W / 2, 560, text, 150, anchor="middle", op=kk)
                + (overlay.text(W / 2, 660, sub, 48, AMB, "middle", 600, "Inter", op=kk) if sub else "") + "</g>")
    return f


def dim(op=0.35):
    return lambda u, _t: f'<rect width="{W}" height="{H}" fill="#06101C" opacity="{op}"/>'


# ---------------------------------------------------------------- the globe stage (space plate)
GX, GY, GS = 900, 760, 1080                 # world centre and size of the painted globe on the space plate
GCAM = (1250, 760, 2500)                    # camera on the space plate (globe left, text right)


def gscr(fx_, fy_):
    """Screen point of a spot on the globe sprite (fractions of its box)."""
    return scr(GCAM, GX - GS / 2 + fx_ * GS, GY - GS / 2 + fy_ * GS)


def rim_arrows(u, at=0.0, r_frac=0.47, n=8, spin_deg=0.0):
    cx, cy = gscr(0.5, 0.5)
    r = r_frac * GS * W / GCAM[2]
    out = ""
    for j in range(n):
        a = j * 2 * math.pi / n - math.radians(spin_deg)
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        tx, ty = math.sin(a), -math.cos(a)                 # counter-clockwise on screen (y down)
        out += arrow(px, py, px + 95 * tx, py + 95 * ty, u, at + 0.06 * j, seed=200 + j)
    return out


# ================================================================ 1-10: hook montage, the window cleaner, timing

def hook_seq():
    c = new((1, 10), "tower_plate")
    G = GR["tower_plate"]
    c.cast("cleaner", height=397, ref="cleaner0")
    at = c.at
    FX = 2050
    # 1: you can teleport — anywhere (street, beach, pole, launch pad), instantly
    c.cam(0.0, *camg(1000, G, 1800))
    hero(c, 0.0, "t0", 900, G, "tower_plate")
    c.text(at(1, 0.15), at(1, 3.2), punch(1350, 260, "WHAT IF", "you could teleport?", 84))
    c.sfx(at(1, 0.15), "sfx_hit", 0.4)
    for t, plate, x, spr in [(0.95, "beach_plate", 1100, "a7"), (1.75, "pole_plate", 1300, "t3"),
                             (2.6, "launch_plate", 900, "t0")]:
        c.cut(at(1, t), plate)
        c.cam(at(1, t), *camg(x + 200, GR[plate], 1800), "hold")
        hero(c, at(1, t), spr, x, GR[plate], plate)
        tp(c, at(1, t), x, GR[plate] - 10, 360, sound=(t != 1.75))
    c.cut(at(1, 3.3), "tower_plate")
    c.cam(at(1, 3.3), *WIDE, "hold")
    hero(c, at(1, 3.3), "t0", 1500, G, "tower_plate")
    # 2: a window cleaner slips; you blink them down. Safe.
    c.key("cleaner", at(1, 3.3), "cleaner0", FX + 90, 360, scale=0.5, fixed=True)
    c.key("cleaner", at(2, 0.4), "cleaner1", FX + 90, 360, scale=0.5, fixed=True)
    c.sfx(at(2, 0.4), "sfx_slip", 0.45)
    c.key("cleaner", at(2, 1.0), "cleaner3", FX, 420, scale=0.55, fixed=True)
    c.key("cleaner", at(2, 3.1), "cleaner3", FX, 820, scale=0.6, fixed=True, tween="in")
    c.sfx(at(2, 1.0), "sfx_fall", 0.4)
    tp(c, at(2, 3.1), FX, 700, 260)
    c.draw(at(2, 3.15), c.end(), portal(FX - 250, G - 200, 260), front=False)
    c.key("cleaner", at(2, 3.15), "cleaner3", FX - 250, G - 40, scale=0.62, fixed=True)
    c.cam(at(2, 3.15), *camg(1650, G, 1500), "snap")
    c.freeze(at(2, 5.4), at(3, 0.3), [lambda ctx, u: big(110, 260, "SAFE?", 110, u, 0.0)])
    c.sfx(at(2, 5.4), "sfx_freeze", 0.35)
    # 3: they arrive still falling
    c.key("cleaner", at(3, 0.5), "cleaner3", FX - 250, G + 10, scale=0.62, fixed=True, tween="in")
    c.key("cleaner", at(3, 0.55), "cleaner4", FX - 250, G, scale=0.55, fixed=True)
    c.shake(at(3, 0.55), 0.5, 26)
    c.sfx(at(3, 0.5), "sfx_crash", 0.5)
    c.draw(at(3, 0.55), at(4, 0.0), fx.dust(FX - 250, G, size=170, seed=12))
    c.draw(at(3, 0.55), at(4, 0.0), fx.cracks(FX - 250, G + 4, 260, seed=11), front=False)
    hero(c, at(3, 0.55), "hero6", 1350, G, "tower_plate")
    c.text(at(3, 1.2), at(4, 0.0), lambda u, _t: ch(110, 230, "still falling at", 48, u, 0.0)
           + am(110, 310, "highway speed", 64, u, 0.8))
    c.draw(at(3, 1.6), at(4, 0.0), prop("car0", 1050, G, 320, fade=0.25))
    # 4: the rule
    c.hide("cleaner", at(4, 0.0))
    c.cam(at(4, 0.0), *camg(1150, G, 1500), "ease")
    hero(c, at(4, 0.0), "a7", 1550, G, "tower_plate")
    c.text(at(4, 0.3), at(5, 0.0), label(110, 170, "THE ONE RULE", "your speed comes with you", 76))
    c.sfx(at(4, 0.3), "sfx_hit", 0.4)
    c.text(at(4, 2.0), at(5, 0.0), lambda u, _t: ch(110, 420, "change WHERE  ✓", 58, u, 0.0, 0.4, bold=True)
           + am(110, 520, "change HOW FAST  ✗", 58, u, 1.6))
    # 5: montage — North Pole -> car crash, Africa -> cannon launch, space -> falling star
    c.cut(at(5, 1.4), "pole_plate")
    P = GR["pole_plate"]
    c.cam(at(5, 1.4), *camg(1300, P, 1900), "hold")
    tp(c, at(5, 1.4), 500, P - 10, 360)
    hero(c, at(5, 1.45), "t1", 500, P + 10, "pole_plate")
    hero(c, at(5, 3.4), "t1", 2200, P + 10, "pole_plate", tween="lin", smear=True)
    c.draw(at(5, 1.45), at(5, 3.6), spray(500, 2200, 1.95, P + 10, seed=7))
    c.sfx(at(5, 1.5), "sfx_ice", 0.5)
    c.text(at(5, 1.5), at(5, 3.6), lambda u, _t: big(110, 230, "North Pole", 70, u, 0.0)
           + am(110, 320, "→ a car crash", 56, u, 1.2))
    c.cut(at(5, 3.9), "jungle_plate")
    J = GR["jungle_plate"]
    c.cam(at(5, 3.9), *camg(1300, J, 1900), "hold")
    tp(c, at(5, 3.9), 1300, J - 10, 380)
    hero(c, at(5, 3.95), "t2", 1300, J, "jungle_plate")
    hero(c, at(5, 5.6), "t2", 1250, J - 1500, "jungle_plate", tween="in", smear=True)
    c.draw(at(5, 3.95), at(5, 6.3), fx.debris(1300, J, n=18, power=0.9, color=(70, 110, 50), seed=31))
    c.shake(at(5, 3.95), 0.4, 18)
    c.sfx(at(5, 4.0), "sfx_sonic", 0.45)
    c.text(at(5, 4.0), at(5, 6.3), lambda u, _t: big(110, 230, "Africa", 70, u, 0.0)
           + am(110, 320, "→ a cannon launch", 56, u, 1.0))
    c.cut(at(5, 6.3), "iss_plate")
    c.cam(at(5, 6.3), *WIDE, "hold")
    hero(c, at(5, 6.3), "t6", 600, 300, "iss_plate", scale=1.4, flip=True)          # moving down-right: tail up-left
    hero(c, at(5, 8.9), "t6", 1500, 1200, "iss_plate", scale=1.4, flip=True, tween="lin")
    c.text(at(5, 6.4), at(6, 0.0), lambda u, _t: big(1200, 230, "space", 70, u, 0.0)
           + am(1200, 320, "→ a falling star", 56, u, 1.0))
    # 6: one secret route — stay for it
    c.cut(at(6, 0.0), "tower_plate")
    c.cam(at(6, 0.0), *camg(1150, G, 1500), "hold")
    hero(c, at(6, 0.0), "t0", 1000, G, "tower_plate")
    c.text(at(6, 0.3), at(7, 0.0), punch(1300, 300, "ONE SECRET ROUTE", "stay for that one", 80))
    c.sfx(at(6, 0.3), "sfx_hit", 0.3)
    # 7: rewind; teleport in the first half-second -> a stumble
    c.rewind(at(7, 0.0), at(7, 0.8))
    c.sfx(at(7, 0.0), "sfx_rewind", 0.4)
    c.cam(at(7, 0.0), *WIDE, "hold")
    hero(c, at(7, 0.0), "t0", 1500, G, "tower_plate")
    c.key("cleaner", at(7, 0.0), "cleaner1", FX + 90, 360, scale=0.5, fixed=True)
    c.text(at(7, 1.0), at(7, 3.6), label(110, 170, "THE TRICK", "timing", 84))
    c.key("cleaner", at(7, 3.6), "cleaner3", FX, 420, scale=0.55, fixed=True)
    c.key("cleaner", at(7, 4.1), "cleaner3", FX, 440, scale=0.55, fixed=True, tween="in")
    tp(c, at(7, 4.1), FX, 470, 240)
    c.draw(at(7, 4.15), c.end(), portal(FX - 250, G - 200, 260), front=False)
    c.cam(at(7, 4.15), *camg(1700, G, 1500), "snap")
    c.key("cleaner", at(7, 4.15), "cleaner1", FX - 250, G - 20, scale=0.98, fixed=True)
    c.key("cleaner", at(7, 4.5), "cleaner0", FX - 250, G, scale=0.98, fixed=True, tween="in")
    c.draw(at(7, 4.5), at(8, 0.0), fx.dust(FX - 250, G, size=90, seed=13))
    c.text(at(7, 4.6), at(8, 0.0), lambda u, _t: ch(110, 250, "after ½ second:", 52, u, 0.0)
           + am(110, 330, "a stumble ✓", 66, u, 0.6))
    # 8: one second — as fast as a bike rolling downhill
    c.hide("cleaner", at(8, 0.0))
    c.cam(at(8, 0.0), *WIDE, "hold")
    c.key("cleaner", at(8, 0.0), "cleaner3", FX, 420, scale=0.55, fixed=True)
    c.key("cleaner", at(8, 1.0), "cleaner3", FX, 470, scale=0.55, fixed=True, tween="in")
    c.draw(at(8, 0.6), at(9, 0.0), prop("bike0", 700, G, 230, fade=0.3))
    c.freeze(at(8, 1.0), at(9, 0.0), [lambda ctx, u: ch(110, 300, "after 1 second:", 50, u, 0.0)
                                     + am(110, 380, "a bike rolling downhill", 60, u, 0.5)])
    c.sfx(at(8, 1.0), "sfx_freeze", 0.35)
    # 9: until the end: over 80 mph; teleporting only picks where they crash
    c.key("cleaner", at(9, 0.0), "cleaner3", FX, 470, scale=0.55, fixed=True)
    c.key("cleaner", at(9, 1.4), "cleaner3", FX, G - 60, scale=0.62, fixed=True, tween="in")
    c.key("hero", at(9, 0.0), None)
    c.cam(at(9, 1.4), *camg(1700, G, 1500), "ease")
    c.freeze(at(9, 1.5), at(10, 0.0), [
        lambda ctx, u: ch(110, 300, "over 80 mph", 72, u, 0.0, 0.4, bold=True),
        lambda ctx, u: ch(110, 420, "teleporting only picks", 48, u, 2.4),
        lambda ctx, u: am(110, 500, "WHERE they crash", 60, u, 3.4),
    ])
    c.sfx(at(9, 1.5), "sfx_freeze", 0.35)
    # 10: back to the roof? they arrive diving into the floor up there
    c.hide("cleaner", at(10, 0.0))
    c.cam(at(10, 0.0), 2100, 450, 1300, "ease")
    c.text(at(10, 0.2), at(10, 2.6), punch(820, 230, "BACK UP", "to the top?", 80))
    tp(c, at(10, 2.8), 2160, 170, 220)
    c.key("cleaner", at(10, 2.85), "cleaner3", 2160, 200, scale=0.5, fixed=True)
    c.key("cleaner", at(10, 3.3), "cleaner3", 2160, 340, scale=0.5, fixed=True, tween="in")
    c.key("cleaner", at(10, 3.35), "cleaner4", 2160, 350, scale=0.45, fixed=True)
    c.shake(at(10, 3.35), 0.5, 24)
    c.sfx(at(10, 3.3), "sfx_crash", 0.45)
    c.draw(at(10, 3.35), c.end(), fx.dust(2160, 350, size=110, seed=14))
    c.text(at(10, 4.8), c.end(), lambda u, _t: big(110, 300, "same crash,", 80, u, 0.0)
           + am(110, 400, "nicer view ✓", 80, u, 1.0))
    c.music(0.0, "music_main", 0.12)
    return c


# ================================================================ 11-13: the car gag (highway)

def car_seq():
    c = new((11, 13), "highway_plate")
    G = GR["highway_plate"]
    c.cast("car", height=330, ref="car0")
    at = c.at
    c.draw(0.0, c.end(), prop("wall0", 2400, G + 10, 300, fade=0), front=False)
    c.cam(0.0, *camg(1500, G, 2000))
    c.key("car", 0.0, "car0", 700, G)
    c.key("car", at(11, 3.6), "car0", 1950, G, ang=-6, tween="lin", smear=True)
    c.speed_lines(0.0, at(11, 3.6))
    c.sfx(at(11, 0.2), "sfx_skid", 0.45)
    c.text(at(11, 0.2), at(11, 2.6), lambda u, _t: ch(110, 230, "your car skids", 60, u, 0.0, 0.4, bold=True)
           + ch(110, 310, "toward a wall…", 48, u, 0.6))
    tp(c, at(11, 3.2), 1800, G - 120, 240)
    c.draw(at(11, 3.25), c.end(), portal(1500, G - 10, 340), front=False)
    hero(c, at(11, 3.25), "t4", 1500, G - 30, "highway_plate", scale=0.6)
    hero(c, at(12, 1.6), "t4", 1780, G - 10, "highway_plate", scale=0.6, ang=540, tween="out")
    c.key("car", at(11, 4.4), "car0", 2230, G, ang=-8, tween="lin")
    c.shake(at(11, 4.4), 0.5, 22)
    c.sfx(at(11, 4.35), "sfx_crash", 0.45)
    c.draw(at(11, 4.4), at(12, 3.0), fx.debris(2330, G - 120, n=16, power=0.7, seed=21))
    c.draw(at(11, 3.3), at(12, 2.0), fx.dust(1800, G, size=140, seed=22))
    c.speed_lines(at(11, 3.3), at(12, 1.6))
    hero(c, at(12, 1.65), "hero5", 1780, G, "highway_plate")
    c.text(at(12, 0.3), at(12, 3.4), lambda u, _t: ch(110, 230, "same speed as the car", 56, u, 0.0, 0.4, bold=True))
    c.text(at(12, 3.4), at(12, 5.0), punch(980, 280, "CONGRATULATIONS", "…?", 80))
    c.text(at(12, 5.0), at(13, 0.0), lambda u, _t: ch(110, 230, "you crashed without", 52, u, 0.0)
           + ch(110, 310, "the car ✗  the seatbelt ✗  the airbag ✗", 46, u, 0.8))
    hero(c, at(13, 0.0), "a6", 1780, G, "highway_plate")
    c.text(at(13, 0.2), c.end(), label(110, 170, "LESSON ONE", "a door, not a brake", 84))
    c.sfx(at(13, 0.2), "sfx_hit", 0.45)
    c.music(0.0, "music_main", 0.12)
    return c


# ================================================================ 14-17: the portal loop (room)

def loop_seq():
    c = new((14, 17), "room_plate")
    G = GR["room_plate"]
    at = c.at
    X, TOP = 820, 300
    c.cam(0.0, 1250, 820, 2400)
    hero(c, 0.0, "a7", X + 420, G, "room_plate")
    c.text(at(14, 0.2), at(14, 2.8), punch(1450, 260, "ALTHOUGH…", "a very good accelerator", 70))
    c.draw(at(14, 2.4), c.end(), portal(X, G - 30, 520, keep=True), front=False)
    c.draw(at(14, 2.6), c.end(), portal(X, TOP - 140, 520, keep=True), front=True)
    c.sfx(at(14, 2.4), "sfx_teleport", 0.4)
    t = 5.4
    laps = [1.1, 0.8, 0.6, 0.45, 0.38, 0.34, 0.32, 0.31] + [0.3] * 20
    for kk, d in enumerate(laps):
        hero(c, at(14, t) if t < 6.5 else at(15, t - 6.5), "a1", X, TOP + 120, "room_plate", ang=37)
        t += d
        hero(c, at(14, t) if t < 6.5 else at(15, t - 6.5), "a1", X, G - 60, "room_plate", ang=37,
             tween="in" if kk < 4 else "lin", smear=kk > 2)
        if t > 6.5 + 7.8:
            break
    c.speed_lines(at(15, 0.5), at(16, 0.0))
    c.text(at(15, 0.0), at(16, 0.0), counter(1300, 120, "FALL SPEED", lambda u: f"{min(120.0, 25 + 15 * u):.0f} mph",
                                             "faster every lap…"))
    c.text(at(15, 6.0), at(16, 0.0), lambda u, _t: am(1300, 330, "…until the wind holds you", 44, u, 0.0))
    hero(c, at(16, 0.0), "hero7", X + 420, G, "room_plate")
    c.text(at(16, 0.3), at(16, 3.2), punch(1400, 260, "FREE SPEED", "forever?", 84))
    c.text(at(16, 3.2), at(16, 5.6), lambda u, _t: (f'<rect width="100%" height="100%" fill="#050507" '
                                                     f'opacity="{0.9 * min(1, u / 0.2):.2f}"/>'
                                                     + f'<g transform="translate({W / 2},{H / 2}) scale({1 + 0.05 * u:.4f}) '
                                                       f'translate({-W / 2},{-H / 2})">'
                                                     + overlay.text(W / 2, 520, "PERPETUAL MOTION?", 90, anchor="middle",
                                                                    op=min(1, u / 0.2))
                                                     + overlay.text(W / 2, 650, "PHYSICS SAYS NO.", 120, AMB, "middle",
                                                                    op=min(1, (u - 0.9) / 0.2)) + "</g>"))
    c.sfx(at(16, 4.1), "sfx_hit", 0.5)
    c.key("hero", at(16, 3.25), None)
    hero(c, at(16, 5.6), "hero7", X + 420, G, "room_plate")
    c.text(at(16, 5.6), at(17, 0.0), lambda u, _t: ch(1250, 280, "a real teleporter", 52, u, 0.0)
           + ch(1250, 360, "charges you for every", 52, u, 0.6) + am(1250, 440, "bit of height", 62, u, 1.4))
    hero(c, at(17, 0.0), "a6", X + 420, G, "room_plate")
    c.text(at(17, 0.1), c.end(), lambda u, _t: big(1250, 330, "no free energy.", 80, u, 0.0))
    c.music(0.0, "music_main", 0.12)
    return c


# ================================================================ 18-22: the equator beach, the spinning planet

def spin_seq():
    c = new((18, 22), "beach_plate")
    G = GR["beach_plate"]
    at = c.at
    c.cam(0.0, *camg(1000, G, 2000))
    hero(c, 0.0, "hero0", 700, G, "beach_plate")
    c.text(at(18, 0.3), at(18, 5.0), label(1150, 170, "ECUADOR", "right on the equator", 74))
    c.text(at(18, 5.0), at(19, 0.0), lambda u, _t: ch(1150, 260, "you want to see", 52, u, 0.0)
           + ch(1150, 340, "the North Pole", 72, u, 0.6, 0.4, bold=True)
           + am(1150, 460, "nothing's moving. right?", 50, u, 2.6))
    hero(c, at(18, 6.0), "a5", 700, G, "beach_plate")
    # 19: wrong — the painted Earth from above, turning
    c.cut(at(19, 0.0), "space_plate")
    c.cam(at(19, 0.0), *GCAM, "hold")
    c.key("hero", at(19, 0.0), None)
    c.draw(at(19, 0.0), at(20, 0.0), globe(0, GX, GY, GS, spin=-6.0))
    c.text(at(19, 0.0), at(19, 1.2), lambda u, _t: am(1450, 200, "WRONG.", 110, u, 0.0, "middle"))
    c.sfx(at(19, 0.1), "sfx_hit", 0.45)
    c.text(at(19, 1.2), at(20, 0.0), lambda u, _t: rim_arrows(u, 0.3, spin_deg=6 * u)
           + ch(1350, 360, "the equator goes", 48, u, 0.4) + ch(1350, 430, "all the way around", 48, u, 0.8)
           + ch(1350, 500, "every day", 48, u, 1.2) + big(1350, 650, "faster than sound", 66, u, 4.4))
    # 20: you never feel it — sea, air and you all move together
    c.cut(at(20, 0.0), "beach_plate")
    c.cam(at(20, 0.0), *camg(1000, G, 2000), "hold")
    hero(c, at(20, 0.0), "hero7", 700, G, "beach_plate")

    def together(u, _t):
        out = ""
        for kk, (x, y, s) in enumerate([(380, 380, "air"), (1150, 680, "sea"), (860, 860, "you")]):
            out += arrow(x, y, x + 240, y, u, 0.2 + 0.3 * kk, seed=60 + kk)
            out += ch(x + 260, y + 16, s, 46, u, 0.4 + 0.3 * kk)
        return out + am(1150, 260, "all moving together", 56, u, 1.6)
    c.text(at(20, 0.0), at(21, 0.0), together)
    # 21: like pouring a drink on a plane
    c.cut(at(21, 0.0), "sky_plate")
    c.cam(at(21, 0.0), 1900, 700, 1500, "hold")
    c.cam(at(22, 0.0), 1950, 700, 1350, "lin")
    c.key("hero", at(21, 0.0), None)
    c.text(at(21, 0.2), at(22, 0.0), lambda u, _t: ch(110, 260, "a drink on a plane", 56, u, 0.0, 0.4, bold=True)
           + am(110, 350, "pours just fine", 56, u, 1.2) + ch(110, 440, "everything moves with you", 44, u, 2.4))
    # 22: now teleport — the pole only turns on the spot
    c.cut(at(22, 0.0), "beach_plate")
    c.cam(at(22, 0.0), *camg(1000, G, 2000), "hold")
    hero(c, at(22, 0.0), "t0", 700, G, "beach_plate")
    tp(c, at(22, 0.9), 700, G - 10, 380)
    c.key("hero", at(22, 0.95), None)
    c.cut(at(22, 1.4), "space_plate")
    c.cam(at(22, 1.4), *GCAM, "hold")
    c.draw(at(22, 1.4), c.end(), globe(0, GX, GY, GS, spin=-6.0, a0=-30))
    px, py = gscr(0.5, 0.5)
    c.text(at(22, 1.6), c.end(), lambda u, _t: (f'<circle cx="{px:.0f}" cy="{py:.0f}" r="{46 + 8 * math.sin(u * 4):.0f}" '
                                                f'fill="none" stroke="{AMB}" stroke-width="7"/>')
           + ch(1350, 360, "the pole doesn't travel", 48, u, 0.3)
           + ch(1350, 440, "it just turns on the spot", 48, u, 1.4)
           + am(1350, 540, "like the middle of a record", 44, u, 3.2))
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 23-28: the North Pole skid, a dozen cars, the note

def pole_seq():
    c = new((23, 28), "pole_plate")
    G = GR["pole_plate"]
    c.cast("snow", height=380, ref="snow0")
    at = c.at
    c.cam(0.0, *camg(900, G, 1800))
    tp(c, at(23, 0.1), 300, G - 10, 380)
    hero(c, at(23, 0.15), "t1", 300, G + 10, "pole_plate")
    hero(c, at(24, 0.6), "t1", 2300, G + 10, "pole_plate", tween="lin", smear=True)
    c.cam(at(24, 0.6), *camg(2000, G, 1800), "lin")
    c.draw(at(23, 0.15), at(25, 0.0), spray(300, 2300, 3.5 + 0.6, G + 10, seed=7))
    c.speed_lines(at(23, 0.15), at(24, 0.6))
    c.sfx(at(23, 0.2), "sfx_ice", 0.55)
    c.text(at(23, 0.6), at(24, 0.0), lambda u, _t: ch(110, 230, "you:  full speed", 56, u, 0.0, 0.4, bold=True)
           + am(110, 310, "the ice:  0", 56, u, 1.0))
    c.freeze(at(24, 0.6), at(25, 0.0), [
        lambda ctx, u: ch(110, 230, "you don't fall.", 56, u, 0.0, 0.4),
        lambda ctx, u: ch(110, 310, "you SKID", 80, u, 0.6, 0.3, bold=True),
        lambda ctx, u: am(110, 420, "faster than a pistol bullet", 52, u, 1.8),
    ])
    c.sfx(at(24, 0.6), "sfx_freeze", 0.4)
    # 25: a dozen cars hitting a wall (cut to the highway)
    c.cut(at(25, 0.0), "highway_plate")
    HG = GR["highway_plate"]
    c.cam(at(25, 0.0), *camg(1400, HG, 2400), "hold")
    c.key("hero", at(25, 0.0), None)
    c.draw(at(25, 0.0), at(26, 0.0), prop("wall0", 2450, HG + 10, 300, fade=0), front=False)
    for kk in range(12):
        row, col = kk // 6, kk % 6
        x0 = 200 + col * 330 - row * 160
        c.draw(at(25, 0.2 + 0.05 * kk), at(26, 0.0), prop("car0", x0, HG - 70 * row, 120 - 10 * row, fade=0.1,
                                                         slide=(2280 - (5 - col) * 70, HG - 70 * row), dur=1.6,
                                                         tween=lambda q: q * q))
    c.shake(at(25, 1.9), 0.6, 24)
    c.sfx(at(25, 1.85), "sfx_crash", 0.5)
    c.text(at(25, 0.3), at(26, 0.0), lambda u, _t: ch(110, 230, "the crash energy of", 50, u, 0.0)
           + am(110, 310, "a dozen cars at highway speed", 56, u, 1.0) + big(110, 400, "all of it, in you", 56, u, 3.4))
    # 26-27: the note for physics fans + "a very short video"
    c.cut(at(26, 0.0), "space_plate")
    c.cam(at(26, 0.0), *GCAM, "hold")
    c.draw(at(26, 0.0), at(27, 3.0), globe(0, GX, GY, GS, spin=-6.0, a0=-60))
    c.text(at(26, 0.0), at(27, 3.0), lambda u, _t: rim_arrows(u, 0.3, spin_deg=6 * u)
           + ch(1300, 330, "speed measured", 50, u, 0.3) + big(1300, 410, "as seen from space", 54, u, 0.9)
           + ch(1300, 560, "measured against the ground?", 36, u, 4.4) + am(1300, 630, "nothing would happen", 46, u, 5.4))
    c.text(at(27, 3.0), at(28, 0.0), flash_card("THE END", "…a very short video"))
    # 28: subscribe — it gets worse (you, head-first in a snowbank)
    c.cut(at(28, 0.0), "pole_plate")
    c.key("snow", at(28, 0.0), "snow0", 1650, G + 20)
    c.cam(at(28, 0.0), *camg(1500, G, 1600), "hold")
    c.text(at(28, 0.3), c.end(), lambda u, _t: am(110, 250, "SUBSCRIBE", 90, u, 0.0)
           + big(110, 340, "it gets worse", 64, u, 1.6))
    c.sfx(at(28, 0.3), "sfx_hit", 0.3)
    c.music(0.0, "music_tense", 0.12)
    return c


# ================================================================ 29-37: the quarter turn, the launch, west, the far side

def quarter_seq():
    c = new((29, 37), "beach_plate")
    G = GR["beach_plate"]
    at = c.at
    c.cam(0.0, *camg(1100, G, 1900))
    hero(c, 0.0, "a5", 900, G, "beach_plate")
    c.text(at(29, 0.2), at(30, 0.0), punch(1350, 300, "IT GETS WORSE", "the farther you go", 76))
    hero(c, at(30, 0.0), "t0", 900, G, "beach_plate")
    c.text(at(30, 0.3), at(31, 0.0), lambda u, _t: ch(1150, 260, "a quarter of the way", 52, u, 0.0)
           + ch(1150, 340, "around the world", 52, u, 0.6) + am(1150, 440, "→ EAST, to Africa", 64, u, 3.0))
    tp(c, at(30, 6.4), 900, G - 10, 380)
    c.key("hero", at(30, 6.45), None)
    # 31: Earth from above: your arrow keeps its direction; a quarter turn later it points up
    c.cut(at(31, 0.0), "space_plate")
    c.cam(at(31, 0.0), *GCAM, "hold")
    c.draw(at(31, 0.0), at(32, 0.0), globe(0, GX, GY, GS, spin=0.0, a0=0))

    def turn(u, _t):
        cx, cy = gscr(0.5, 0.5)
        r = 0.47 * GS * W / GCAM[2]
        q = min(1.0, max(0.0, (u - 3.6) / 2.2))
        a = math.pi / 2 - (math.pi / 2) * q                    # from the bottom of the globe to its right side
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        return (f'<circle cx="{px:.0f}" cy="{py:.0f}" r="16" fill="{AMB}"/>'
                + arrow(px, py, px + 230, py, u, 0.0, seed=401)
                + ch(1350, 300, "Earth from above", 50, u, 0.2)
                + ch(1350, 400, "speed: along the ground", 42, u, 1.4)
                + am(1350, 560, "a quarter turn later:", 44, u, 5.0) + am(1350, 630, "the same arrow points UP", 44, u, 6.0))
    c.text(at(31, 0.0), at(32, 0.0), turn)
    # 32: the jungle launch
    c.cut(at(32, 0.0), "jungle_plate")
    J = GR["jungle_plate"]
    c.cam(at(32, 0.0), *camg(1300, J, 1900), "hold")
    tp(c, at(32, 0.2), 1300, J - 10, 380)
    hero(c, at(32, 0.25), "t2", 1300, J, "jungle_plate")
    hero(c, at(32, 1.6), "t2", 1180, J - 1700, "jungle_plate", tween="in", smear=True)
    c.cam(at(32, 1.6), 1100, 760, 2300, "snap")
    c.whip(at(32, 0.3), at(32, 1.0))
    c.shake(at(32, 0.25), 0.6, 22)
    c.sfx(at(32, 0.25), "sfx_sonic", 0.5)
    c.draw(at(32, 0.25), at(33, 0.0), fx.debris(1300, J, n=24, power=1.0, color=(70, 110, 50), seed=31))
    c.draw(at(32, 0.25), at(33, 0.0), fx.dust(1300, J, size=200, seed=32))
    c.text(at(32, 1.6), at(33, 0.0), lambda u, _t: big(110, 260, "like a cannonball", 80, u, 0.0)
           + am(110, 360, "…while the jungle slides away", 48, u, 1.6))
    # 33-34: how high? airliner height with no air; with air, a wall of wind
    c.cut(at(33, 0.0), "sky_plate")
    c.cam(at(33, 0.0), 1700, 760, 1900, "hold")
    hero(c, at(33, 0.0), "t2", 1500, 1500, "sky_plate")
    hero(c, at(33, 2.4), "t2", 1500, 560, "sky_plate", tween="out")
    c.text(at(33, 0.4), at(34, 0.0), lambda u, _t: ch(1150, 260, "with no air:", 52, u, 0.0)
           + am(1150, 350, "up to where airliners fly", 50, u, 0.8))
    hero(c, at(34, 0.0), "t4", 1500, 560, "sky_plate", scale=0.6)
    hero(c, at(34, 2.6), "t4", 1450, 1500, "sky_plate", scale=0.6, ang=720, tween="in")
    c.text(at(34, 0.0), at(35, 0.0), lambda u, _t: ch(1150, 260, "with air:", 52, u, 0.0)
           + big(1150, 350, "a wall of wind", 70, u, 0.6))
    c.sfx(at(34, 0.2), "sfx_wind", 0.4)
    # 35: west -> straight down into the Pacific
    c.cut(at(35, 0.0), "ocean_plate")
    S = GR["ocean_plate"]
    c.cam(at(35, 0.0), *camg(1300, S, 1900, 0.78), "hold")
    c.text(at(35, 0.2), at(35, 3.8), lambda u, _t: ch(110, 230, "a quarter turn WEST", 56, u, 0.0, 0.4, bold=True)
           + am(110, 310, "the same arrow points DOWN", 50, u, 1.4))
    tp(c, at(35, 4.0), 1300, 520, 300)
    hero(c, at(35, 4.05), "a1", 1300, 620, "ocean_plate", ang=37)
    hero(c, at(35, 4.4), "a1", 1300, S + 260, "ocean_plate", ang=37, tween="in", smear=True)
    c.draw(at(35, 4.0), at(36, 0.0), submerge(1300, S, 300))
    c.draw(at(35, 4.35), at(36, 0.0), spray(1300, 1300, 0.6, S, seed=11, every=0.03))
    c.shake(at(35, 4.4), 0.5, 20)
    c.sfx(at(35, 4.35), "sfx_water", 0.55)
    c.text(at(35, 5.0), at(36, 0.0), lambda u, _t: big(110, 230, "into the Pacific", 72, u, 0.0))
    # 36-37: the far side: the ground spins the other way -> twice the speed, four times the crash
    c.cut(at(36, 0.0), "space_plate")
    c.cam(at(36, 0.0), *GCAM, "hold")
    c.key("hero", at(36, 0.0), None)
    c.draw(at(36, 0.0), c.end(), globe(0, GX, GY, GS, spin=0.0, a0=40))

    def far(u, _t):
        top = gscr(0.5, 0.04)
        bot = gscr(0.5, 0.96)
        return (f'<circle cx="{bot[0]:.0f}" cy="{bot[1]:.0f}" r="16" fill="{CH}"/>'
                + arrow(bot[0], bot[1], bot[0] + 230, bot[1], u, 0.0, seed=411)
                + f'<circle cx="{top[0]:.0f}" cy="{top[1]:.0f}" r="16" fill="{AMB}"/>'
                + arrow(top[0], top[1], top[0] - 230, top[1], u, 1.6, seed=412)
                + ch(1350, 300, "the far side:", 48, u, 0.8) + ch(1300, 380, "the ground spins the other way", 36, u, 1.8)
                + am(1350, 520, "× 2 the speed", 70, u, 4.4))
    c.text(at(36, 0.0), at(37, 0.0), far)
    c.text(at(37, 0.0), c.end(), lambda u, _t: am(1350, 520, "× 2 the speed", 70, u, -1.0)
           + big(1350, 640, "= × 4 the crash", 80, u, 0.3))
    c.sfx(at(37, 0.3), "sfx_crash", 0.4)
    c.music(0.0, "music_tense", 0.12)
    return c


# ================================================================ 38-48: real trips from New York; the safe teleporter

def trips_seq():
    c = new((38, 48), "tower_plate")
    G = GR["tower_plate"]
    c.cast("car", height=330, ref="car0")
    at = c.at
    c.cam(0.0, *camg(1150, G, 1700))
    hero(c, 0.0, "a5", 950, G, "tower_plate")
    c.text(at(38, 0.2), at(38, 3.6), punch(1350, 300, "USELESS?", "not at all", 90))
    c.text(at(38, 3.6), at(39, 0.0), lambda u, _t: big(110, 230, "it's all about distance", 66, u, 0.0)
           + am(110, 320, "the farther you jump, the bigger the mismatch", 42, u, 1.6))
    # 39: real trips from New York; across town: nothing
    c.text(at(39, 0.0), at(39, 1.8), label(110, 170, "REAL TRIPS", "from New York", 80))
    tp(c, at(39, 1.9), 950, G - 10, 340)
    c.draw(at(39, 1.95), c.end(), portal(1450, G - 10, 340), front=False)
    hero(c, at(39, 1.95), "a6", 1450, G, "tower_plate")
    c.text(at(39, 2.0), at(39, 4.0), lambda u, _t: big(110, 260, "across town", 72, u, 0.0)
           + am(110, 350, "you won't even notice", 52, u, 0.8))
    # 39-40: Philadelphia: a fall off a bike
    c.text(at(39, 4.0), at(40, 2.4), lambda u, _t: big(110, 260, "Philadelphia", 80, u, 0.0)
           + am(110, 350, "like falling off a bike", 52, u, 1.6))
    hero(c, at(39, 4.0), "t4", 900, G - 15, "tower_plate", scale=0.6)
    hero(c, at(40, 1.6), "t4", 1500, G - 5, "tower_plate", scale=0.6, ang=420, tween="out")
    c.draw(at(39, 4.0), at(40, 2.4), prop("bike0", 1100, G, 230, slide=(1700, G), dur=1.2,
                                          tween=lambda q: 1 - (1 - q) ** 2))
    c.sfx(at(40, 0.3), "sfx_crash", 0.35)
    # 40: Boston: a car crash
    c.cut(at(40, 2.4), "highway_plate")
    HG = GR["highway_plate"]
    c.cam(at(40, 2.4), *camg(1500, HG, 2000), "hold")
    c.key("hero", at(40, 2.4), None)
    c.draw(at(40, 2.4), at(41, 0.0), prop("wall0", 2400, HG + 10, 300, fade=0), front=False)
    c.key("car", at(40, 2.4), "car0", 900, HG)
    c.key("car", at(40, 3.9), "car0", 2230, HG, ang=-8, tween="in", smear=True)
    c.hide("car", at(41, 0.0))
    c.shake(at(40, 3.9), 0.5, 22)
    c.sfx(at(40, 3.85), "sfx_crash", 0.5)
    c.text(at(40, 2.5), at(41, 0.0), lambda u, _t: big(110, 260, "Boston", 80, u, 0.0)
           + am(110, 350, "a car crash", 56, u, 1.4))
    # 41: London: faster than sound; Tokyo: twice that (night street, sonic booms)
    c.cut(at(41, 0.0), "night_plate")
    NG = GR["night_plate"]
    c.cam(at(41, 0.0), *camg(1300, NG, 2000), "hold")
    tp(c, at(41, 0.2), 500, NG - 10, 340)
    hero(c, at(41, 0.25), "t1", 500, NG + 10, "night_plate")
    hero(c, at(41, 1.4), "t1", 2300, NG + 10, "night_plate", tween="lin", smear=True)
    c.flash(at(41, 0.3), 0.06)
    c.shake(at(41, 0.3), 0.5, 24)
    c.sfx(at(41, 0.3), "sfx_sonic", 0.5)
    c.text(at(41, 0.3), at(41, 1.6), lambda u, _t: overlay.boom(700, 600, u, W, H))
    c.text(at(41, 0.0), at(41, 2.6), lambda u, _t: big(110, 260, "London", 80, u, 0.0)
           + am(110, 350, "faster than sound", 56, u, 0.6))
    tp(c, at(41, 2.7), 1800, NG - 10, 340)
    hero(c, at(41, 2.75), "t2", 1800, NG, "night_plate")
    hero(c, at(41, 4.0), "t2", 1750, NG - 1500, "night_plate", tween="in", smear=True)
    c.flash(at(41, 2.8), 0.08)
    c.shake(at(41, 2.8), 0.7, 34)
    c.sfx(at(41, 2.8), "sfx_bang", 0.55)
    c.text(at(41, 2.8), at(41, 4.2), lambda u, _t: overlay.boom(1400, 600, u, W, H))
    c.text(at(41, 2.7), at(42, 0.0), lambda u, _t: big(110, 260, "Tokyo", 80, u, 0.0)
           + am(110, 350, "twice the speed of sound", 56, u, 0.8))
    # 42: commute vs vacation
    c.text(at(42, 0.0), at(43, 0.0), dim(0.45))
    c.text(at(42, 0.0), at(43, 0.0), lambda u, _t: big(560, 560, "commute ✓", 110, u, 0.0, "middle")
           + am(1400, 560, "vacation ✗", 110, u, 1.3, "middle"))
    c.sfx(at(42, 1.3), "sfx_hit", 0.4)
    # 43-46: a safe teleporter: a door with a really good brake (beach, a living portal)
    c.cut(at(43, 0.0), "beach_plate")
    BG = GR["beach_plate"]
    c.cam(at(43, 0.0), *camg(1200, BG, 2000), "hold")
    c.draw(at(43, 0.0), at(47, 0.0), portal(1500, BG - 260, 560, keep=True), front=False)
    hero(c, at(43, 0.0), "a7", 800, BG, "beach_plate")
    c.text(at(43, 0.2), at(44, 0.0), label(110, 170, "A SAFE TELEPORTER", "needs a second job", 76))
    c.text(at(44, 0.0), at(45, 0.0), lambda u, _t: ch(110, 230, "take away the old speed", 52, u, 0.0, 0.4, bold=True)
           + am(110, 320, "hand you the ground's speed", 52, u, 1.8))
    c.text(at(45, 0.0), at(46, 0.0), lambda u, _t: ch(110, 230, "every long trip:", 52, u, 0.0)
           + am(110, 320, "a dozen car crashes' worth of energy", 50, u, 0.6))
    c.text(at(46, 0.0), at(47, 0.0), lambda u, _t: big(110, 240, "a door", 80, u, 0.0)
           + am(110, 340, "+ a really, really good brake", 60, u, 0.9))
    c.sfx(at(46, 0.9), "sfx_hit", 0.4)
    # 47-48: no more vacations? a secret route... but first
    hero(c, at(47, 0.0), "a6", 800, BG, "beach_plate")
    c.text(at(47, 0.0), at(48, 0.0), label(110, 170, "NOT SO FAST", "there's a secret route", 80))
    c.text(at(48, 0.0), c.end(), punch(1300, 340, "BUT FIRST", "what else is waiting", 84))
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 49-52: other ways a jump goes wrong

def wrong_seq():
    c = new((49, 52), "sky_plate")
    at = c.at
    c.cam(0.0, 1300, 760, 2000)
    tp(c, at(49, 0.2), 1000, 640)
    hero(c, at(49, 0.25), "t3", 1000, 900, "sky_plate")
    hero(c, at(50, 0.0), "t3", 1000, 1000, "sky_plate", tween="lin")
    c.sfx(at(49, 0.3), "sfx_wind", 0.45)
    c.text(at(49, 0.6), at(50, 0.0), lambda u, _t: ch(1350, 300, "where airliners fly", 52, u, 0.0)
           + big(1350, 400, "air: thin", 72, u, 1.2) + am(1350, 500, "≈ half a minute", 50, u, 3.2))
    # 50: the deepest trench
    c.cut(at(50, 0.0), "trench_plate")
    T = GR["trench_plate"]
    c.cam(at(50, 0.0), *camg(1344, T, 1900), "hold")
    tp(c, at(50, 0.2), 1344, T - 10, 400)
    hero(c, at(50, 0.25), "hero6", 1344, T, "trench_plate")
    c.sfx(at(50, 0.3), "sfx_deep", 0.5)
    c.draw(at(50, 3.2), at(51, 0.0), prop("car0", 600, T - 20, 330, fade=0.3))
    c.text(at(50, 0.3), at(51, 0.0), lambda u, _t: ch(110, 230, "the deepest trench", 56, u, 0.0, 0.4, bold=True)
           + ch(110, 330, "every fingernail-sized patch", 44, u, 1.6)
           + am(110, 420, "carries the weight of a small car", 48, u, 3.4))
    # 51-52: into a room: the air must get out of the way — a bang, two actually
    c.cut(at(51, 0.0), "room_plate")
    R = GR["room_plate"]
    rc = (1300, 820, 2400)
    c.cam(at(51, 0.0), *rc, "hold")
    tp(c, at(51, 0.5), 1550, R - 330, 520)
    hero(c, at(51, 0.55), "hero6", 1550, R, "room_plate")

    def burst(x, y):
        def f(u, _t):
            out = ""
            for j in range(12):
                a = j * math.pi / 6
                r0, r1 = 50 + 180 * min(1.0, u / 0.5), 120 + 280 * min(1.0, u / 0.5)
                out += overlay.chalk_line([(x + r0 * math.cos(a), y + r0 * math.sin(a)),
                                           (x + r1 * math.cos(a), y + r1 * math.sin(a))], 1.0, 6, seed=500 + j,
                                          rough=False)
            return out
        return f
    hx, hy = scr(rc, 1550, R - 330)
    c.text(at(51, 0.55), at(51, 1.4), burst(hx, hy))
    c.text(at(51, 1.4), at(52, 0.0), lambda u, _t: ch(110, 230, "the air in your spot", 52, u, 0.0)
           + big(110, 320, "has to get out of the way", 60, u, 0.8) + am(110, 410, "all at once", 56, u, 2.6))
    c.flash(at(52, 0.2), 0.06)
    c.shake(at(52, 0.2), 0.4, 22)
    c.sfx(at(52, 0.15), "sfx_bang", 0.5)
    c.text(at(52, 0.2), at(52, 1.4), burst(hx, hy))
    c.text(at(52, 0.3), c.end(), lambda u, _t: am(110, 230, "BANG", 110, u, 0.0)
           + ch(110, 330, "like a gunshot", 52, u, 0.4) + ch(110, 410, "two, actually:", 52, u, 1.6))
    tp(c, at(52, 2.6), 1550, R - 330, 520)
    c.key("hero", at(52, 2.65), None)
    c.draw(at(52, 2.7), c.end(), portal(700, R - 330, 520), front=False)
    hero(c, at(52, 2.7), "hero6", 700, R, "room_plate")
    c.sfx(at(52, 3.0), "sfx_crash", 0.4)
    c.text(at(52, 3.0), at(52, 4.0), burst(hx, hy))
    c.text(at(52, 3.6), c.end(), lambda u, _t: ch(1100, 500, "one where you arrive,", 44, u, 0.0)
           + ch(1100, 560, "one where you left", 44, u, 1.0))
    c.music(0.0, "music_tense", 0.1)
    return c


# ================================================================ 53-62: space — the station, the meteor, the Moon, Mars

def space_seq():
    c = new((53, 62), "iss_plate")
    at = c.at
    icam = (1100, 700, 2200)
    c.cam(0.0, *WIDE)
    c.cam(at(53, 4.0), *icam, "ease")
    c.text(at(53, 0.2), at(53, 3.6), punch(1300, 300, "LEAVE THE PLANET?", "", 80))
    tp(c, at(53, 4.0), 1150, 560, 280)
    hero(c, at(53, 4.05), "t5", 1150, 700, "iss_plate")
    c.draw(at(53, 4.05), at(58, 0.0), halo(1165, 520), front=False)
    hero(c, at(56, 5.5), "t5", 1180, 760, "iss_plate", tween="lin")
    c.text(at(53, 4.4), at(54, 0.0), label(110, 170, "SPACE STATION", "about 250 miles up", 62))
    # 54-55: it isn't parked: it falls around the planet at five miles every second
    sx, sy = scr(icam, 2050, 300)
    c.text(at(54, 0.4), at(55, 0.0), lambda u, _t: ch(110, 230, "it isn't parked up there", 52, u, 0.0)
           + arrow(sx - 120, sy + 210, sx + 200, sy + 210, u, 6.2, seed=601)
           + am(110, 320, "five miles every second", 50, u, 6.4))
    c.speed_lines(at(54, 6.4), at(55, 1.4))

    def orbit(u, _t):
        pts = [(200 + 300 * j, 900 - 168 * math.sin(j / 5.0 * math.pi)) for j in range(6)]
        return (overlay.chalk_line(pts, u / 0.8, 6, seed=611, rough=False)
                + big(110, 230, "that's an orbit:", 60, u, 0.0) + am(110, 320, "falling, but always missing", 48, u, 0.5))
    c.text(at(55, 0.0), at(56, 0.0), orbit)

    def bars(u, _t):
        q = min(1.0, max(0.0, (u - 1.6) / 0.8))
        return (ch(110, 230, "the station", 46, u, 0.2)
                + f'<rect x="110" y="250" width="{900 * q:.0f}" height="40" fill="{CH}"/>'
                + ch(110, 340, "you", 46, u, 1.2)
                + f'<rect x="110" y="360" width="{60 * q:.0f}" height="40" fill="{AMB}"/>'
                + am(110, 470, "a tiny fraction", 56, u, 2.6))
    c.text(at(56, 0.0), at(57, 0.0), bars)
    # 57: it shoots past; you start to fall
    c.whip(at(57, 0.0), at(57, 0.5))
    c.sfx(at(57, 0.0), "sfx_dash", 0.4)
    hero(c, at(57, 0.6), "t5", 1180, 760, "iss_plate")
    hero(c, at(58, 0.0), "t5", 1250, 1050, "iss_plate", tween="in")
    c.text(at(57, 0.3), at(58, 0.0), lambda u, _t: big(110, 260, "…and you fall", 70, u, 0.0))
    # 58: a homemade meteor at ~5,000 mph
    hero(c, at(58, 0.0), "t6", 1250, 1050, "iss_plate", scale=1.2, flip=True)       # continues the fall, tail behind
    hero(c, at(58, 5.0), "t6", 1950, 1420, "iss_plate", scale=1.2, flip=True, tween="in")
    c.cam(at(58, 0.0), *WIDE, "ease")
    c.sfx(at(58, 0.3), "sfx_rocket", 0.35)
    c.text(at(58, 1.8), at(59, 0.0), lambda u, _t: big(110, 260, "≈ 5,000 mph", 84, u, 0.0)
           + am(110, 360, "a homemade meteor", 60, u, 2.8))
    # 59: the hard part is sideways
    c.key("hero", at(59, 0.0), None)
    c.text(at(59, 0.0), at(60, 0.0), dim(0.35))

    def side(u, _t):
        x0, y0 = 700, 760
        return (arrow(x0, y0, x0, y0 - 160, u, 1.4, seed=621) + ch(x0 + 30, y0 - 170, "up: the easy part", 44, u, 1.8)
                + arrow(x0, y0, x0 + 900, y0, u, 3.6, 0.6, seed=622)
                + am(x0 + 40, y0 + 70, "sideways, incredibly fast: the hard part", 46, u, 4.4)
                + big(110, 230, "the secret of rockets", 64, u, 0.0))
    c.text(at(59, 0.0), at(60, 0.0), side)
    # 60: the Moon: out of step, slamming into the dust
    c.cut(at(60, 0.0), "moon_plate")
    M = GR["moon_plate"]
    c.cam(at(60, 0.0), *camg(1100, M, 2000), "hold")
    c.text(at(60, 0.0), at(60, 3.0), lambda u, _t: big(110, 230, "the Moon?", 80, u, 0.0)
           + am(110, 320, "racing around the Earth", 48, u, 0.4) + ch(110, 390, "you're not", 48, u, 1.9))
    tp(c, at(60, 3.0), 500, M - 10, 380)
    hero(c, at(60, 3.05), "t1", 500, M - 120, "moon_plate")
    hero(c, at(60, 4.4), "t1", 2300, M, "moon_plate", tween="out", smear=True)
    c.cam(at(60, 4.4), *camg(1900, M, 2000), "ease")
    c.draw(at(60, 3.2), at(61, 0.0), spray(500, 2300, 1.2, M, seed=13, col=(205, 205, 200)))
    c.draw(at(60, 3.2), at(61, 0.0), fx.dust(1600, M, n=24, size=200, life=3.0, seed=14, color=(190, 188, 182)))
    c.shake(at(60, 3.2), 0.6, 24)
    c.sfx(at(60, 3.2), "sfx_crash", 0.45)
    c.text(at(60, 4.6), at(61, 0.0), lambda u, _t: am(110, 230, "faster than a pistol bullet", 52, u, 0.0))
    # 61-62: Mars: thousands of mph on the best day; a new crater
    c.cut(at(61, 0.0), "mars_plate")
    MG = GR["mars_plate"]
    mcam = camg(1300, MG, 2200)
    c.cam(at(61, 0.0), *mcam, "hold")
    c.key("hero", at(61, 0.0), None)
    c.text(at(61, 0.0), at(61, 4.0), lambda u, _t: big(110, 230, "Mars is worse", 80, u, 0.0)
           + ch(110, 330, "Earth and Mars race at different speeds", 42, u, 1.2))
    hero(c, at(61, 4.0), "t6", 2500, 200, "mars_plate", scale=1.1)
    hero(c, at(62, 1.6), "t6", 1300, MG - 40, "mars_plate", scale=1.1, tween="in")
    c.text(at(61, 4.0), at(62, 0.2), lambda u, _t: am(110, 230, "best day: thousands of mph", 52, u, 1.8))
    c.key("hero", at(62, 1.65), None)
    c.flash(at(62, 1.65), 0.1)
    c.shake(at(62, 1.65), 0.8, 36)
    c.sfx(at(62, 1.6), "sfx_crash", 0.55)
    c.draw(at(62, 1.65), c.end(), fx.debris(1300, MG - 20, n=30, power=1.2, color=(150, 70, 40), seed=41))
    c.draw(at(62, 1.65), c.end(), fx.dust(1300, MG, n=26, size=300, life=4.0, seed=42, color=(190, 110, 70)))
    cx_, cy_ = scr(mcam, 1300, MG)
    c.text(at(62, 0.2), at(62, 1.6), lambda u, _t: am(110, 230, "bad day: × 10", 60, u, 0.0))
    c.text(at(62, 3.0), c.end(), lambda u, _t: (f'<ellipse cx="{cx_:.0f}" cy="{cy_:.0f}" rx="{230 * min(1, u / 0.5):.0f}" '
                                                f'ry="60" fill="none" stroke="{CH}" stroke-width="7"/>')
           + big(110, 230, "not a landing:", 64, u, 0.0) + am(110, 330, "a brand new crater", 64, u, 0.6))
    c.music(0.0, "music_tense", 0.1)
    return c


# ================================================================ 63-67: the secret route (painted Earth from the side)

NY = (0.585, 0.27)
TWIN = (0.535, 0.76)


def twin_seq():
    c = new((63, 67), "space_plate")
    at = c.at
    c.cam(0.0, *GCAM)
    c.draw(0.0, at(66, 0.0), globe(1, GX, GY, GS))
    c.text(at(63, 0.0), at(64, 0.0), label(1300, 200, "THE SECRET ROUTE", "your twin spot", 70))
    c.sfx(at(63, 0.2), "sfx_hit", 0.35)

    def twins(u, _t):
        ny, tw = gscr(*NY), gscr(*TWIN)
        el, er = gscr(0.06, 0.5), gscr(0.94, 0.5)
        mid = gscr(0.575, 0.52)
        out = overlay.chalk_line([el, er], u / 0.6, 5, seed=701, rough=False)
        out += ch(er[0] - 30, er[1] - 18, "equator", 34, u, 0.4, anchor="end")
        out += f'<circle cx="{ny[0]:.0f}" cy="{ny[1]:.0f}" r="15" fill="{AMB}"/>'
        out += ch(1350, 330, "New York", 46, u, 0.6, bold=True)
        if u > 2.0:
            out += overlay.chalk_line([ny, mid, tw], (u - 2.0) / 0.9, 5, seed=702, rough=False)
            out += f'<circle cx="{tw[0]:.0f}" cy="{tw[1]:.0f}" r="15" fill="{AMB}"/>'
            out += am(1350, 420, "its twin: same distance south", 38, u, 2.6)
        return out
    c.text(at(64, 0.0), at(66, 0.0), twins)

    def same(u, _t):
        ny, tw = gscr(*NY), gscr(*TWIN)
        return (arrow(ny[0], ny[1], ny[0] + 220, ny[1], u, 0.4, seed=711)
                + arrow(tw[0], tw[1], tw[0] + 220, tw[1], u, 1.0, seed=712)
                + big(1350, 560, "same direction,", 54, u, 1.6) + big(1350, 630, "same speed", 54, u, 2.2)
                + ch(1350, 720, "like a wheel on an axle", 42, u, 3.2))
    c.text(at(65, 0.0), at(66, 0.0), same)
    # 66-67: off southern Chile: perfectly still... and a little bit wet; London: bring a boat
    c.cut(at(66, 0.0), "ocean_plate")
    S = GR["ocean_plate"]
    c.cam(at(66, 0.0), *camg(1500, S, 1900, 0.78), "hold")
    c.text(at(66, 0.0), at(66, 5.4), lambda u, _t: ch(110, 230, "New York → off southern Chile", 52, u, 0.0, 0.4,
                                                       bold=True) + am(110, 310, "more than 5,000 miles", 48, u, 2.8))
    tp(c, at(66, 5.5), 1500, S - 130)
    hero(c, at(66, 5.55), "a6", 1500, S + HS["ocean_plate"] * 0.55, "ocean_plate")
    c.draw(at(66, 5.5), c.end(), submerge(1500, S, 280))
    c.draw(at(66, 5.55), at(67, 1.5), fx.dust(1500, S, size=60, life=1.0, seed=17, color=(240, 248, 255)))
    c.sfx(at(66, 5.6), "sfx_water", 0.35)
    c.text(at(66, 6.2), at(67, 2.6), lambda u, _t: big(110, 230, "0 mph  ✓", 80, u, 0.0)
           + am(110, 330, "perfectly still…", 56, u, 0.8) + am(110, 410, "…and a little bit wet", 56, u, 2.4))
    c.text(at(67, 2.6), c.end(), lambda u, _t: big(110, 230, "London's twin:", 64, u, 0.0)
           + am(110, 320, "the open South Atlantic", 52, u, 0.6) + big(110, 420, "bring a boat", 64, u, 4.6))
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 68-71: rockets and the spin

def launch_seq():
    c = new((68, 71), "launch_plate")
    G = GR["launch_plate"]
    at = c.at
    cam = camg(1400, G, 2200)
    c.cam(0.0, *cam)
    hero(c, 0.0, "a7", 900, G, "launch_plate")
    c.sfx(at(68, 0.2), "sfx_rocket", 0.4)
    c.text(at(68, 0.2), at(68, 3.0), label(110, 170, "ROCKET ENGINEERS", "love the spin too", 76))
    c.text(at(68, 3.0), at(69, 0.0), lambda u, _t: ch(110, 230, "launch close to the equator", 50, u, 0.0)
           + am(110, 310, "aimed EAST →", 64, u, 1.6))
    c.text(at(69, 0.0), at(69, 4.4), lambda u, _t: ch(110, 230, "a free push of", 50, u, 0.0)
           + big(110, 320, "≈ 1,000 mph", 84, u, 0.6) + ch(110, 400, "before the engines light", 40, u, 1.6))
    hero(c, at(69, 4.4), "t0", 900, G, "launch_plate")
    c.draw(at(69, 4.4), c.end(), portal(900, G - 10, 380), front=False)
    c.sfx(at(69, 4.4), "sfx_teleport", 0.4)
    c.text(at(69, 4.5), at(70, 0.0), lambda u, _t: ch(110, 230, "your teleporter:", 56, u, 0.0)
           + am(110, 320, "+ 0 mph", 84, u, 0.8))

    def swivel(u, _t):
        hx, hy = scr(cam, 900, G - 240)
        a = math.radians(-90 * min(1.0, u / 1.6))
        return (overlay.chalk_arrow(hx, hy, hx + 240 * math.cos(a), hy + 240 * math.sin(a), 1.0, seed=801)
                + ch(110, 230, "it only chooses", 52, u, 0.0) + am(110, 310, "where your speed points", 56, u, 0.6))
    c.text(at(70, 0.0), at(71, 0.0), swivel)
    hero(c, at(71, 0.0), "a7", 900, G, "launch_plate")
    c.text(at(71, 0.2), c.end(), label(110, 170, "THE TRICK", "land where the ground moves like you", 64))
    c.sfx(at(71, 0.2), "sfx_hit", 0.4)
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 72-75: ending (recap montage) + end screen

def ending_seq():
    c = new((72, 75), "beach_plate", fade_out=0.8)
    G = GR["beach_plate"]
    at = c.at
    c.cam(0.0, *camg(1100, G, 2000))
    hero(c, 0.0, "hero0", 800, G, "beach_plate")
    c.text(at(72, 0.3), at(72, 8.2), lambda u, _t: big(1150, 260, "no skipping physics", 60, u, 0.0)
           + am(1150, 350, "your speed comes with you", 48, u, 2.8))
    # 72-73: "the planet is moving, you're moving, everything is" — quick cuts
    for t, plate, spr, x, y, kw in [(8.2, "pole_plate", "t1", 900, None, {}),
                                    (9.0, "jungle_plate", "t2", 1300, None, {}),
                                    (9.8, "iss_plate", "t6", 1200, 700, {"scale": 1.2})]:
        tt = at(72, t) if t < 8.6 else at(73, t - 8.6)
        c.cut(tt, plate)
        gy = GR.get(plate, 1200) if y is None else y
        c.cam(tt, *(camg(x + 200, gy, 1900) if y is None else WIDE), "hold")
        hero(c, tt, spr, x, gy, plate, **kw)
    c.cut(at(73, 1.6), "beach_plate")
    c.cam(at(73, 1.6), *camg(1100, G, 2000), "hold")
    hero(c, at(73, 1.6), "hero7", 800, G, "beach_plate")
    c.text(at(73, 2.6), at(73, 8.6), lambda u, _t: big(1150, 300, "speed is the one thing", 60, u, 0.0)
           + am(1150, 390, "you can't leave behind", 60, u, 0.8))
    hero(c, at(74, 0.0), "t0", 800, G, "beach_plate")
    c.text(at(73, 8.6), at(74, 1.5), punch(1350, 300, "JUMP SMALL.", "jump smart.", 90))
    c.text(at(74, 1.5), at(74, 3.0), lambda u, _t: big(1150, 300, "never, ever", 70, u, 0.0))
    c.cut(at(74, 3.0), "pole_plate")
    P = GR["pole_plate"]
    c.cam(at(74, 3.0), *camg(1300, P, 1900), "hold")
    tp(c, at(74, 3.0), 500, P - 10, 360)
    hero(c, at(74, 3.05), "t1", 500, P + 10, "pole_plate")
    hero(c, at(74, 4.6), "t1", 2300, P + 10, "pole_plate", tween="lin", smear=True)
    c.draw(at(74, 3.05), at(75, 0.4), spray(500, 2300, 1.55, P + 10, seed=9))
    c.sfx(at(74, 3.1), "sfx_ice", 0.45)
    c.text(at(74, 3.0), at(75, 0.0), lambda u, _t: am(110, 260, "teleport to the North Pole", 64, u, 0.0))
    c.cut(at(75, 0.0), "beach_plate")
    c.cam(at(75, 0.0), *camg(1100, G, 2000), "hold")
    hero(c, at(75, 0.0), "a7", 800, G, "beach_plate")
    c.text(at(75, 0.2), at(75, 7.6), label(110, 170, "YOUR TURN", "where would you go first?", 70))

    def end_screen(u, _t):
        kk = min(1.0, u / 0.5)
        bob = 10 * math.sin(u * 2.2)
        box = ('<rect x="{x}" y="300" width="760" height="428" rx="18" fill="#000" opacity="{o:.2f}" '
               'stroke="#F2EEE4" stroke-width="4"/>')
        z = 1 + 0.03 * u
        return (f'<rect width="{W}" height="{H}" fill="#06080C" opacity="{0.78 * kk:.2f}"/>'
                + f'<g transform="translate({W / 2},{H / 2}) scale({z:.4f}) translate({-W / 2},{-H / 2})">'
                + box.format(x=140, o=0.55 * kk) + box.format(x=1020, o=0.55 * kk)
                + overlay.text(W / 2, 200 + bob, "watch next", 64, anchor="middle", op=kk)
                + overlay.text(W / 2, 880, "subscribe for the next “what if”", 44, AMB, "middle", 600, "Inter", op=kk)
                + "</g>")
    c.text(at(75, 7.6), c.end(), end_screen)
    c.hide("hero", at(75, 7.6))
    c.music(0.0, "music_main", 0.12)
    return c


def build(size):
    return [hook_seq(), car_seq(), loop_seq(), spin_seq(), pole_seq(), quarter_seq(), trips_seq(), wrong_seq(),
            space_seq(), twin_seq(), launch_seq(), ending_seq()]
