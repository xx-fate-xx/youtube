"""World-space props drawn from Higgsfield art (sprites in the art library), for Comic.draw.

Operator rule (2026-11-23): every object on screen is Higgsfield art; code draws only chalk arrows / chalk text.
These helpers place, move, open/close and spin that art inside a scene (all coordinates in plate px):

    prop(name, x, ground, h)        a sprite standing on `ground` (optional slide to a second point)
    portal(x, y, w)                 the teleport portal (portal0) snapping open and closed, or kept alive
    globe(idx, x, y, size, spin)    the painted Earth (globe0 from above the pole, globe1 from the side)
    spray(x0, x1, dur, y)           droplets / ice chips kicked up behind a sliding body
    halo(x, y)                      soft light behind a dark figure on a black sky
    submerge(x, sea, plate)         the plate's own water redrawn over a body that is in the sea
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw


def _art():
    from . import render
    return render.library("art")


@lru_cache(maxsize=256)
def img(name: str, h: int, flip: bool = False, ang: int = 0) -> Image.Image:
    from .thumbs import _sprite
    return _sprite(_art(), name, h, flip, ang)


def paste(world: Image.Image, s: Image.Image, x: float, ground: float) -> None:
    from .comic import _composite
    _composite(world, s, int(x - s.width / 2), int(ground - s.height))


def prop(name, x, ground, h, flip=False, ang=0, fade=0.2, slide=None, dur=1.0, tween=lambda q: q):
    def f(world, u, _t):
        a = min(1.0, u / fade) if fade else 1.0
        xx, gg = x, ground
        if slide:
            p = tween(min(1.0, u / dur))
            xx, gg = x + (slide[0] - x) * p, ground + (slide[1] - ground) * p
        s = img(name, int(h), flip, int(ang))
        if a < 1:
            s = s.copy()
            s.putalpha(s.getchannel("A").point(lambda v: int(v * a)))
        paste(world, s, xx, gg)
    return f


def portal(x, y, w=300, life=0.9, keep=False):
    """The portal sprite centred at (x, y); put it at the feet (y = ground - 10) as a teleport pad."""
    def f(world, u, _t):
        if not keep and u > life:
            return
        if keep:
            s = min(1.0, u / 0.18)
        else:
            q = u / life
            s = min(1.0, q / 0.2) if q < 0.7 else max(0.0, 1 - (q - 0.7) / 0.3)
        if s <= 0.02:
            return
        base = img("portal0", int(w * 0.55))
        im = base.resize((max(2, int(base.width * s)), max(2, int(base.height * (0.6 + 0.4 * s)))),
                         Image.Resampling.BILINEAR)
        if keep:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * (0.85 + 0.15 * math.sin(u * 7)))))
        paste(world, im, x, y + im.height / 2)
    return f


@lru_cache(maxsize=96)
def _globe_rot(idx: int, size: int, ang10: int) -> Image.Image:
    g = img(f"globe{idx}", size)
    return g.rotate(ang10 / 10, resample=Image.Resampling.BICUBIC) if ang10 else g


def globe(idx, x, y, size, spin=0.0, a0=0.0):
    def f(world, u, _t):
        ang = (a0 + spin * u) % 360
        g = _globe_rot(idx, int(size), int(round(ang * 10)) // 5 * 5)
        paste(world, g, x, y + g.height / 2)
    return f


def spray(x0, x1, dur, y, seed=5, every=0.06, col=(240, 248, 255)):
    def f(world, u, _t):
        d = ImageDraw.Draw(world, "RGBA")
        sgn = 1 if x1 >= x0 else -1
        for k in range(int(min(u, dur) / every) + 1):
            te = k * every
            age = u - te
            if age < 0 or age > 0.9:
                continue
            ex = x0 + (x1 - x0) * min(1.0, te / dur)
            r = random.Random(seed * 1000 + k)
            fade = 1 - age / 0.9
            for _j in range(6):
                vx, vy = -sgn * r.uniform(80, 320), -r.uniform(240, 560)
                px, py = ex + vx * age, y + vy * age + 1100 * age * age
                if py > y + 6:
                    continue
                rr = r.uniform(5, 12)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(*col, int(220 * fade)))
    return f


def halo(x, y, r=260, col=(150, 190, 255), a=70):
    def f(world, u, _t):
        layer = Image.new("RGBA", world.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        k = min(1.0, u / 0.4)
        for j in range(8):
            rr = r * (1 - j / 9)
            d.ellipse([x - rr, y - rr * 1.15, x + rr, y + rr * 1.15], fill=(*col, int(a * k * (j + 1) / 8 / 2.2)))
        world.alpha_composite(layer)
    return f


def submerge(x, sea, plate, half=260):
    def f(world, _u, _t):
        from .comic import _plate
        pl = _plate(str(_art()), plate)
        box = (int(x - half), int(sea) - 4, int(x + half), pl.height)
        world.alpha_composite(pl.crop(box), (box[0], box[1]))
    return f
