"""Vertical (1080x1920) motion-comic helpers for What If Shorts.

Shorts reuse the long video's art library (render.library: episode.yaml `sound_library` / `parent`): plates get a
`_v` variant with extra foreground ground (comic.tall_plate) so the characters' feet sit above the burned captions
(centre at 64 % of the height) and the Shorts UI at the bottom. Screen layout, top to bottom:

    120-300   HUD / kicker titles          300-560  chalk notes, punch titles
    560-1120  the characters (feet at FEET) 1150-1310 burned captions (keep clear)   > 1450 platform UI
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter

from . import overlay
from .comic import V_EXTRA, Comic, board, punch

W, H = 1080, 1920
SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455}     # standing body height on each sheet (px)
GROUND = {"tower_plate": 1362, "highway_plate": 1400, "night_plate": 1420}
PW, PH = 2688, 1520 + V_EXTRA
FEET = 1110                       # screen y of the characters' feet
VW = 800                          # default camera width (plate px) -> 1.35x
HERO = 420                        # hero height on the plate (≈ 570 px on screen; raised hands stay below y ≈ 470)


def new(shots, plate: str, **kw) -> Comic:
    c = Comic(shots=shots, plate=f"{plate}_v", **kw)
    c.sheet_ref = dict(SHEET)
    c.shade = (0.5, 760)
    return c


def cam_on(x: float, ground: float, vw: float = VW, feet: float = FEET) -> tuple[float, float, float]:
    """Camera (cx, cy, width) centred on plate x with the ground line `ground` at screen y `feet`."""
    k = W / vw
    vh = vw * H / W
    return x, ground - feet / k + vh / 2, vw


def scr(cam, x: float, y: float) -> tuple[float, float]:
    """Plate point -> screen point for a camera (cx, cy, width) (ignores the ambient drift)."""
    cx, cy, vw = cam
    k = W / vw
    vh = vw * H / W
    x0 = min(max(cx - vw / 2, 0), PW - vw)
    y0 = min(max(cy - vh / 2, 0), PH - vh)
    return (x - x0) * k, (y - y0) * k


def tx(item):
    """A freeze item (ctx, u) -> svg as a Comic.text fn (u, t) -> svg."""
    return lambda u, _t: item({}, u)


def vboard(fn, dim: float = 1.0):
    return board(fn, dim, cx=W / 2, cy=H / 2)


def chalk(x, y, s, size, u, at=0.0, d=0.5, bold=False, anchor="start"):
    """Chalk text written from `at` (seconds into the fn's own clock u) over `d` seconds."""
    return overlay.chalk_text(x, y, s, size, (u - at) / d, 800 if bold else 600,
                              "Inter Display" if bold else "Inter", anchor)


def amber(x, y, s, size, u, at=0.0, anchor="start", weight=800):
    k = max(0.0, min(1.0, (u - at) / 0.2))
    return overlay.text(x, y, s, size, overlay.AMBER, anchor, weight, "Inter Display", op=k) if k else ""


def title(small: str, big: str, y: float = 330, size: int = 72):
    """Centred kinetic title (amber kicker over a white line)."""
    return punch(W / 2, y, small, big, size)


def hud(stages, x: float = 70, y: float = 130, kicker: str = "SPEED"):
    """Live speed readout. stages: [(t, value, note)] in scene seconds; the shown value counts up to each new
    stage over 0.45 s. value is a number (mph) or a string."""
    def f(u: float, t: float) -> str:
        cur = [s for s in stages if s[0] <= t]
        if not cur:
            return ""
        t1, v1, note = cur[-1]
        prev = cur[-2][1] if len(cur) > 1 else 0
        if isinstance(v1, (int, float)) and isinstance(prev, (int, float)):
            k = min(1.0, (t - t1) / 0.45)
            v = prev + (v1 - prev) * (1 - (1 - k) ** 3)
            val = f"{v:,.0f} mph"
        else:
            val = str(v1)
        return overlay.hud(kicker, val, note, min(1.0, u / 0.25), 1.0, x=x, y=y)
    return f


def full_video(y: float = 330):
    """Closing title: the full video is linked below (Shorts 'related video')."""
    def f(u: float, _t: float) -> str:
        s = 1 + 0.25 * math.exp(-u * 10)
        bob = 10 * math.sin(u * 5)
        return (f'<g transform="translate({W / 2},{y}) scale({s:.3f})">'
                + overlay.shadowed(overlay.text(0, 0, "FULL VIDEO", 92, overlay.AMBER, "middle", 800, "Inter Display"))
                + overlay.shadowed(overlay.text(0, 86 + bob, "linked below ↓", 60, anchor="middle")) + "</g>")
    return f


def wind(y0: float, y1: float, n: int = 26, speed: float = 2600, seed: int = 7, x0: float = 0, x1: float = PW):
    """World-space gusts: pale streaks racing right -> left between plate rows y0..y1."""
    import random
    r = random.Random(seed)
    ls = [(r.uniform(x0, x1), r.uniform(y0, y1), r.uniform(120, 380), r.uniform(0.7, 1.3)) for _ in range(n)]

    def f(img: Image.Image, u: float, _t: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        span = x1 - x0 + 800
        for x, y, ln, v in ls:
            px = x1 + 400 - ((x1 - x + u * speed * v) % span)
            d.line([(px, y), (px + ln, y)], fill=(255, 255, 255, 120), width=5)
    return f


def heat(x: float, y: float, h: float, facing: int = 1):
    """Hot compressed air in front of a runner: a glowing amber bow (shock layer) curving around plate point
    (x, y) — the nose of the bow — `h` px tall, flickering; facing=1 when running right."""
    def f(img: Image.Image, u: float, _t: float) -> None:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        k = min(1.0, u / 0.5)
        for j in range(7):
            off = 18 * j + 6 * math.sin(u * 11 + j * 1.7)
            w = h * (0.32 + 0.05 * j)
            box = [x - w - off if facing > 0 else x - w + off, y - h / 2 - off * 0.6,
                   x + w - off if facing > 0 else x + w + off, y + h / 2 + off * 0.6]
            a = int(k * (230 - 28 * j))
            col = (255, 250, 210) if j == 0 else (255, 196 - 12 * j, 70 - 6 * j)
            d.arc(box, -70 if facing > 0 else 110, 70 if facing > 0 else 250, fill=(*col, a), width=max(4, 16 - j))
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3)))
        img.alpha_composite(layer)
    return f


def wall(x: float, ground: float, w: float = 300, h: float = 760):
    """A cartoon concrete wall (thick dark outline, panel seams, tie holes) standing on the ground at x..x+w."""
    def f(img: Image.Image, _u: float, _t: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        top = ground - h
        d.rectangle([x + 18, top + 18, x + w + 18, ground], fill=(0, 0, 0, 70))          # soft shadow
        d.rectangle([x, top, x + w, ground], fill=(156, 154, 150, 255), outline=(22, 22, 24, 255), width=9)
        for j in range(1, 4):
            yy = top + h * j / 4
            d.line([(x + 6, yy), (x + w - 6, yy)], fill=(110, 108, 104, 255), width=4)
            for k in (0.25, 0.75):
                cx = x + w * k
                d.ellipse([cx - 7, yy - h / 8 - 7, cx + 7, yy - h / 8 + 7], fill=(96, 94, 90, 255))
        d.rectangle([x, top, x + 14, ground], fill=(186, 184, 180, 255))              # lit edge facing us
        import random
        r = random.Random(int(x))
        for _ in range(int(w * h / 900)):                                           # concrete pores
            px, py = r.uniform(x + 16, x + w - 8), r.uniform(top + 8, ground - 8)
            g = r.randint(118, 140)
            d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(g, g - 2, g - 5, 255))
    return f
