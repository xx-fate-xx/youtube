"""Ink ground texture: a seamless horizontal tile (RGBA, transparent) laid on a strip under the figures' feet, so
the road scrolls past 1:1 with the world and the walkers read as stepping on something.

    python -m studio.ink3d.ground <out.png> [ink|light|sand|snow|stone|bank|rock] [seed]

Layout (top to bottom): a margin for grass tufts, the ground line (a dry-brush stroke with breaks), then pebbles
and horizontal brush streaks thinning out with depth. Scale: PX_PER_M pixels per metre, TILE_M metres wide.
Location grounds (one per painted plate): sand (ripples and stipple, no grass), snow (a pale soft line, drift
shadows), stone (paved street / temple courtyard: slab joints), bank (river bank: pebbles and reeds), rock (a cliff
ledge: a heavy line and cracks).
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PX_PER_M = 200
TILE_M = 6.0
TOP_M = 0.3          # margin above the ground line (grass tufts)
DEPTH_M = 2.6        # strip depth below the line


def tile(out: Path, tone: str = "ink", seed: int = 1) -> Path:
    if tone in LOCATIONS:
        return LOCATIONS[tone](out, seed)
    W = int(TILE_M * PX_PER_M)
    top = int(TOP_M * PX_PER_M)
    H = top + int(DEPTH_M * PX_PER_M)
    col = (22, 20, 15) if tone == "ink" else (205, 198, 182)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rnd = random.Random(seed)

    def wrap(fn, x, *a):                               # draw at x and x +- W: the tile wraps seamlessly
        for dx in (-W, 0, W):
            fn(x + dx, *a)

    # the ground line: overlapping dry-brush dabs with a gentle wave, a few breaks
    x = 0.0
    while x < W:
        seg = rnd.uniform(60, 220)
        if rnd.random() < 0.12:                        # a break in the stroke
            x += rnd.uniform(8, 26)
            continue
        th = rnd.uniform(5, 9)
        y0 = top + 3 * math.sin(x / 97.0) + rnd.uniform(-1.5, 1.5)
        y1 = top + 3 * math.sin((x + seg) / 97.0) + rnd.uniform(-1.5, 1.5)
        a = rnd.randint(170, 235)

        def line(xx, ya=y0, yb=y1, s=seg, t=th, al=a):
            dr.line([(xx, ya), (xx + s, yb)], fill=(*col, al), width=int(t))
        wrap(line, x)
        x += seg * rnd.uniform(0.75, 0.95)
    # grass tufts standing on the line
    x = rnd.uniform(0, 80)
    while x < W:
        n = rnd.randint(3, 6)
        h = rnd.uniform(0.08, 0.2) * PX_PER_M
        for _ in range(n):
            ang = math.radians(rnd.uniform(-35, 35))
            hh = h * rnd.uniform(0.5, 1.0)

            def blade(xx, an=ang, hb=hh, al=rnd.randint(150, 220)):
                dr.line([(xx, top + 2), (xx + math.sin(an) * hb, top + 2 - math.cos(an) * hb)], fill=(*col, al),
                        width=3)
            wrap(blade, x + rnd.uniform(-6, 6))
        x += rnd.uniform(0.5, 1.6) * PX_PER_M
    # pebbles just under the line, streaks deeper down (thinning out)
    for _ in range(int(TILE_M * 10)):
        px, py = rnd.uniform(0, W), top + rnd.uniform(8, 0.35 * PX_PER_M)
        r = rnd.uniform(2, 6)

        def peb(xx, yy=py, rr=r, al=rnd.randint(90, 170)):
            dr.ellipse([xx - rr * 1.4, yy - rr, xx + rr * 1.4, yy + rr], fill=(*col, al))
        wrap(peb, px)
    for _ in range(int(TILE_M * 26)):
        d = rnd.random() ** 2                          # denser near the top
        py = top + 12 + d * (H - top - 20)
        ln = rnd.uniform(0.15, 0.9) * PX_PER_M * (1 - 0.5 * d)
        px = rnd.uniform(0, W)

        def streak(xx, yy=py, ll=ln, al=int(rnd.randint(40, 110) * (1 - 0.7 * d)), t=rnd.choice((2, 2, 3, 4))):
            dr.line([(xx, yy), (xx + ll, yy + rnd.uniform(-2, 2))], fill=(*col, al), width=t)
        wrap(streak, px)
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def _canvas():
    W = int(TILE_M * PX_PER_M)
    top = int(TOP_M * PX_PER_M)
    H = top + int(DEPTH_M * PX_PER_M)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im), W, H, top


def _wrap(W, fn, x):
    for dx in (-W, 0, W):
        fn(x + dx)


def _line(dr, W, top, rnd, col, th=(5, 9), alpha=(170, 235), wave=3.0, breaks=0.12):
    """The ground line: overlapping dry-brush dabs with a gentle wave."""
    x = 0.0
    while x < W:
        seg = rnd.uniform(60, 220)
        if rnd.random() < breaks:
            x += rnd.uniform(8, 26)
            continue
        t = rnd.uniform(*th)
        y0 = top + wave * math.sin(x / 97.0) + rnd.uniform(-1.5, 1.5)
        y1 = top + wave * math.sin((x + seg) / 97.0) + rnd.uniform(-1.5, 1.5)
        a = rnd.randint(*alpha)

        def dab(xx, ya=y0, yb=y1, sg=seg, tt=t, al=a):
            dr.line([(xx, ya), (xx + sg, yb)], fill=(*col, al), width=max(1, int(tt)))
        _wrap(W, dab, x)
        x += seg * rnd.uniform(0.75, 0.95)


def _streaks(dr, W, H, top, rnd, col, n, amax=110, wmax=4):
    for _ in range(n):
        d = rnd.random() ** 2
        py = top + 12 + d * (H - top - 20)
        ln = rnd.uniform(0.15, 0.9) * PX_PER_M * (1 - 0.5 * d)

        def st(xx, yy=py, ll=ln, al=int(rnd.randint(30, amax) * (1 - 0.7 * d)), t=rnd.randint(2, wmax),
               dy=rnd.uniform(-2, 2)):
            dr.line([(xx, yy), (xx + ll, yy + dy)], fill=(*col, al), width=t)
        _wrap(W, st, rnd.uniform(0, W))


def _save(im, out):
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def _sand(out, seed):
    im, dr, W, H, top = _canvas()
    rnd = random.Random(seed)
    col = (70, 62, 48)
    _line(dr, W, top, rnd, col, th=(4, 7), alpha=(170, 225), wave=5.0, breaks=0.12)
    for _ in range(int(TILE_M * 9)):                    # wind ripples: shallow arcs
        d = rnd.random() ** 1.5
        py = top + 16 + d * (H - top - 30)
        w = rnd.uniform(0.3, 0.9) * PX_PER_M * (1 - 0.4 * d)

        def rip(xx, yy=py, ww=w, al=int(rnd.randint(50, 120) * (1 - 0.6 * d))):
            dr.arc([xx, yy - 10, xx + ww, yy + 10], 200, 340, fill=(*col, al), width=2)
        _wrap(W, rip, rnd.uniform(0, W))
    for _ in range(int(TILE_M * 160)):                  # stipple grains
        d = rnd.random() ** 2

        def grain(xx, yy=top + 6 + d * (H - top - 10), al=int(rnd.randint(40, 120) * (1 - 0.6 * d))):
            dr.ellipse([xx - 1.2, yy - 1.2, xx + 1.2, yy + 1.2], fill=(*col, al))
        _wrap(W, grain, rnd.uniform(0, W))
    return _save(im, out)


def _snow(out, seed):
    im, dr, W, H, top = _canvas()
    rnd = random.Random(seed)
    col = (70, 78, 88)
    _line(dr, W, top, rnd, col, th=(3, 6), alpha=(150, 210), wave=6.0, breaks=0.18)
    for _ in range(int(TILE_M * 3)):                    # drift shadows: long soft blue-grey washes
        py = top + rnd.uniform(10, 0.5 * (H - top))
        w = rnd.uniform(0.8, 2.2) * PX_PER_M

        def drift(xx, yy=py, ww=w, al=rnd.randint(10, 24)):
            dr.ellipse([xx, yy - 6, xx + ww, yy + 10], fill=(*col, al))
        _wrap(W, drift, rnd.uniform(0, W))
    _streaks(dr, W, H, top, rnd, col, int(TILE_M * 8), amax=60, wmax=2)
    return _save(im, out)


def _stone(out, seed):
    im, dr, W, H, top = _canvas()
    rnd = random.Random(seed)
    col = (22, 20, 15)
    _line(dr, W, top, rnd, col, th=(6, 9), alpha=(190, 235), wave=1.0, breaks=0.04)
    y, row = float(top + 10), 0
    while y < H - 10 and row < 4:                        # a few slab courses, broken brush lines, fading out
        h = 26 + 30 * row
        al = int(140 * (1 - 0.28 * row))
        x = rnd.uniform(0, 60)
        while x < W:                                     # the course line in broken dabs
            seg = rnd.uniform(40, 150)
            if rnd.random() < 0.65:
                def dash(xx, yy=y + h + rnd.uniform(-2, 2), sg=seg, a=int(al * rnd.uniform(0.4, 0.8))):
                    dr.line([(xx, yy), (xx + sg, yy + rnd.uniform(-2, 2))], fill=(*col, a), width=2)
                _wrap(W, dash, x)
            x += seg + rnd.uniform(10, 40)
        x = rnd.uniform(0, 120) + row * 53
        while x < W:                                     # joints: slightly tilted, not every one complete
            def joint(xx, y0=y, y1=y + h * rnd.uniform(0.6, 1.0), a=int(al * rnd.uniform(0.6, 1.0)),
                      tilt=rnd.uniform(-5, 5)):
                dr.line([(xx, y0 + 3), (xx + tilt, y1 - 2)], fill=(*col, a), width=3)
            _wrap(W, joint, x)
            x += rnd.uniform(0.55, 1.1) * PX_PER_M
        y += h
        row += 1
    _streaks(dr, W, H, top, rnd, col, int(TILE_M * 6), amax=60)
    return _save(im, out)


def _bank(out, seed):
    im, dr, W, H, top = _canvas()
    rnd = random.Random(seed)
    col = (22, 20, 15)
    _line(dr, W, top, rnd, col)
    x = rnd.uniform(0, 120)
    while x < W:                                         # reeds in clumps
        for _ in range(rnd.randint(4, 8)):
            ang = math.radians(rnd.uniform(-18, 18))
            hb = rnd.uniform(0.12, 0.28) * PX_PER_M

            def reed(xx, an=ang, hh=hb, al=rnd.randint(150, 220)):
                dr.line([(xx, top + 2), (xx + math.sin(an) * hh, top + 2 - math.cos(an) * hh)], fill=(*col, al),
                        width=3)
            _wrap(W, reed, x + rnd.uniform(-10, 10))
        x += rnd.uniform(1.0, 2.4) * PX_PER_M
    for _ in range(int(TILE_M * 14)):                   # river pebbles: rounded outlines, bigger near the line
        d = rnd.random() ** 1.6
        py = top + 10 + d * (H - top - 20)
        r = rnd.uniform(4, 12) * (1 - 0.5 * d)

        def peb(xx, yy=py, rr=r, al=int(rnd.randint(110, 190) * (1 - 0.6 * d))):
            dr.ellipse([xx - rr * 1.5, yy - rr, xx + rr * 1.5, yy + rr], fill=(*col, al // 2))
        _wrap(W, peb, rnd.uniform(0, W))
    _streaks(dr, W, H, top, rnd, col, int(TILE_M * 10), amax=80)
    return _save(im, out)


def _rock(out, seed):
    im, dr, W, H, top = _canvas()
    rnd = random.Random(seed)
    col = (22, 20, 15)
    _line(dr, W, top, rnd, col, th=(9, 13), alpha=(200, 245), wave=4.0, breaks=0.03)
    for _ in range(int(TILE_M * 4)):                    # short cracks from the edge down: two strokes each
        y0 = float(top + 6)
        a1 = (rnd.uniform(-10, 10), y0 + rnd.uniform(16, 30))
        a2 = (a1[0] + rnd.uniform(-12, 12), a1[1] + rnd.uniform(10, 24))

        def crack(xx, p1=a1, p2=a2, al=rnd.randint(120, 190), yy=y0):
            dr.line([(xx, yy), (xx + p1[0], p1[1]), (xx + p2[0], p2[1])], fill=(*col, al), width=4)
        _wrap(W, crack, rnd.uniform(0, W))
    for _ in range(int(TILE_M * 10)):                   # dry-brush hatching under the edge
        py = top + rnd.uniform(10, 60)
        ln = rnd.uniform(20, 70)

        def hatch(xx, yy=py, ll=ln, al=rnd.randint(50, 110)):
            dr.line([(xx, yy), (xx + ll, yy + ll * 0.35)], fill=(*col, al), width=2)
        _wrap(W, hatch, rnd.uniform(0, W))
    _streaks(dr, W, H, top, rnd, col, int(TILE_M * 22), amax=120, wmax=5)
    return _save(im, out)


LOCATIONS = {"sand": _sand, "snow": _snow, "stone": _stone, "bank": _bank, "rock": _rock}


if __name__ == "__main__":
    tile(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "ink", int(sys.argv[3]) if len(sys.argv) > 3 else 1)
