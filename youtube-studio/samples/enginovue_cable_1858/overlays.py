"""Exact chart overlays for Enginovue frames (SVG source + transparent 1920x1080 PNG).

Generated images never draw charts: their prompt reserves an empty area, and the editor
composites the overlay rendered here. Every curve is computed from its formula, so the
graphics stay mathematically correct.

Each overlay keeps 8-10% side margins and stays above the bottom 15% subtitle band (y < 918).

Usage: python build.py   (renders every overlay referenced by a GFX line in frames.txt)
Output: overlays/<frame-file>_gfx.svg and overlays/<frame-file>_gfx.png
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageColor, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "overlays"
W, H = 1920, 1080
SS = 2  # supersampling for the PNG raster
SUBTITLE_TOP = round(H * 0.85)
FONT_DIR = HERE.parents[1] / "assets" / "fonts" / "inter"  # bundled Inter, SIL OFL 1.1

NAVY, SEA, TURQ, SKY = "#071B35", "#0C5274", "#22E5EF", "#28BFF5"
ORANGE, GOLD, SILVER, GRAPHITE = "#FFA51F", "#FFC342", "#EDEAF1", "#242735"

STYLES = {
    # dark holographic panel (matches the tablet projection look)
    "dark": {"card": NAVY, "card_op": 0.93, "border": TURQ, "grid": SEA, "axis": SILVER,
             "text": SILVER, "muted": "#9FB3C8", "main": TURQ, "accent": ORANGE},
    # light explainer card
    "light": {"card": "#FFFFFF", "card_op": 0.95, "border": SEA, "grid": "#D5E3EC",
              "axis": NAVY, "text": NAVY, "muted": "#51657A", "main": SEA, "accent": ORANGE},
}


class Canvas:
    """Tiny two-backend canvas: identical primitives go to SVG and to a Pillow RGBA image."""

    def __init__(self) -> None:
        self.items: list[tuple] = []

    def rect(self, x, y, w, h, fill=None, op=1.0, stroke=None, sw=0, r=0):
        self.items.append(("rect", x, y, w, h, fill, op, stroke, sw, r))

    def line(self, pts, color, width, dash=None, op=1.0):
        self.items.append(("line", [(float(a), float(b)) for a, b in pts], color, width, dash, op))

    def circle(self, cx, cy, r, fill, stroke=None, sw=0):
        self.items.append(("circle", cx, cy, r, fill, stroke, sw))

    def poly(self, pts, fill):
        self.items.append(("poly", [(float(a), float(b)) for a, b in pts], fill))

    def text(self, x, y, s, size, color, anchor="ls", bold=False):
        """anchor: Pillow-style two letters, horizontal l/m/r + vertical t/m/s (baseline)."""
        self.items.append(("text", x, y, s, size, color, anchor, bold))

    # ---- SVG ----
    def svg(self) -> str:
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}">']
        for it in self.items:
            k = it[0]
            if k == "rect":
                _, x, y, w, h, fill, op, stroke, sw, r = it
                st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
                out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
                           f'fill="{fill or "none"}" fill-opacity="{op}"{st}/>')
            elif k == "line":
                _, pts, color, width, dash, op = it
                p = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
                d = f' stroke-dasharray="{dash[0]},{dash[1]}"' if dash else ""
                out.append(f'<polyline points="{p}" fill="none" stroke="{color}" '
                           f'stroke-opacity="{op}" stroke-width="{width}" stroke-linecap="round" '
                           f'stroke-linejoin="round"{d}/>')
            elif k == "circle":
                _, cx, cy, r, fill, stroke, sw = it
                st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
                out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{st}/>')
            elif k == "poly":
                _, pts, fill = it
                p = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
                out.append(f'<polygon points="{p}" fill="{fill}"/>')
            elif k == "text":
                _, x, y, s, size, color, anchor, bold = it
                ta = {"l": "start", "m": "middle", "r": "end"}[anchor[0]]
                db = {"t": "hanging", "m": "central", "s": "alphabetic"}[anchor[1]]
                out.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Inter, sans-serif" '
                           f'font-size="{size}" font-weight="{"bold" if bold else "normal"}" '
                           f'text-anchor="{ta}" dominant-baseline="{db}">{escape(s)}</text>')
        out.append("</svg>")
        return "\n".join(out) + "\n"

    # ---- PNG ----
    def png(self) -> Image.Image:
        img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        for it in self.items:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            k = it[0]
            if k == "rect":
                _, x, y, w, h, fill, op, stroke, sw, r = it
                box = [x * SS, y * SS, (x + w) * SS, (y + h) * SS]
                d.rounded_rectangle(box, radius=r * SS, fill=_c(fill, op) if fill else None,
                                    outline=_c(stroke) if stroke else None, width=round(sw * SS))
            elif k == "line":
                _, pts, color, width, dash, op = it
                segs = _dashed(pts, dash) if dash else [pts]
                for seg in segs:
                    sp = [(a * SS, b * SS) for a, b in seg]
                    d.line(sp, fill=_c(color, op), width=round(width * SS), joint="curve")
                    rr = width * SS / 2
                    for a, b in (sp[0], sp[-1]):  # round caps
                        d.ellipse([a - rr, b - rr, a + rr, b + rr], fill=_c(color, op))
            elif k == "circle":
                _, cx, cy, r, fill, stroke, sw = it
                box = [(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS]
                d.ellipse(box, fill=_c(fill), outline=_c(stroke) if stroke else None,
                          width=round(sw * SS))
            elif k == "poly":
                _, pts, fill = it
                d.polygon([(a * SS, b * SS) for a, b in pts], fill=_c(fill))
            elif k == "text":
                _, x, y, s, size, color, anchor, bold = it
                font = _font(size * SS, bold)
                d.text((x * SS, y * SS), s, font=font, fill=_c(color), anchor=anchor)
            img = Image.alpha_composite(img, layer)
        return img.resize((W, H), Image.Resampling.LANCZOS)


def _c(color: str, op: float = 1.0) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(color)[:3]
    return (r, g, b, round(255 * op))


def _font(size: float, bold: bool) -> ImageFont.FreeTypeFont:
    name = "Inter-Bold.ttf" if bold else "Inter-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), round(size))


def _dashed(pts, dash):
    on, off = dash
    segs, cur, pos, draw = [], [pts[0]], 0.0, True
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        seg = math.hypot(x2 - x1, y2 - y1)
        t = 0.0
        while seg > 0 and t < seg:
            step = min((on if draw else off) - pos, seg - t)
            t += step
            pos += step
            p = (x1 + (x2 - x1) * t / seg, y1 + (y2 - y1) * t / seg)
            if draw:
                cur.append(p)
            if pos >= (on if draw else off) - 1e-9:
                if draw:
                    segs.append(cur)
                draw, pos, cur = not draw, 0.0, [p]
    if draw and len(cur) > 1:
        segs.append(cur)
    return [s for s in segs if len(s) > 1]


def propto(c: Canvas, x: float, y: float, size: float, color: str) -> float:
    """Draw the proportionality sign (Inter has no U+221D glyph). Returns its width."""
    # Lemniscate of Bernoulli: t in (pi/2, 3pi/2) is the closed left loop; extending t a little
    # past both ends adds the two open arms on the right, which is exactly the shape of the sign.
    a, d = size * 0.36, 1.0
    raw = []
    for i in range(161):
        t = math.pi / 2 - d + (math.pi + 2 * d) * i / 160
        den = 1 + math.sin(t) ** 2
        raw.append((a * math.cos(t) / den, -a * math.sin(t) * math.cos(t) / den))
    x_min = min(p[0] for p in raw)
    pts = [(x + px - x_min, y + py) for px, py in raw]
    c.line(pts, color, max(3, size * 0.075))
    return max(p[0] for p in pts) - x


def formula(c: Canvas, x: float, y: float, size: int, color: str, left: str, right: str) -> None:
    """Draw `left ∝ right` with the baseline at y."""
    f = _font(size, True)
    c.text(x, y, left, size, color, "ls", bold=True)
    x += f.getlength(left) + size * 0.22
    x += propto(c, x, y - size * 0.33, size, color) + size * 0.22
    c.text(x, y, right, size, color, "ls", bold=True)


def card(c: Canvas, s: dict, x, y, w, h) -> None:
    assert x >= W * 0.08 - 1 and x + w <= W * 0.92 + 1, "card breaks side safe margins"
    assert y >= H * 0.08 - 1 and y + h <= SUBTITLE_TOP, "card enters top margin or subtitle band"
    c.rect(x, y, w, h, fill=s["card"], op=s["card_op"], stroke=s["border"], sw=4, r=28)


# ---------------------------------------------------------------- overlays

def erfc(x: float) -> float:
    return math.erfc(x)


def rc_step(s: float) -> float:
    """Far-end response of Thomson's distributed RC cable to a voltage step, s = t / (r c x^2)."""
    return 0.0 if s <= 0 else erfc(1 / (2 * math.sqrt(s)))


PULSE_START, PULSE_LEN, T_MAX = 0.6, 1.0, 9.0  # in units of the line time constant tau = r c L^2


def _pulse_axes(c: Canvas, s: dict, title: str, sub: str):
    x0, y0, w, h = 300, 100, 1320, 560
    card(c, s, x0, y0, w, h)
    c.text(x0 + 50, y0 + 70, title, 40, s["text"], "ls", bold=True)
    c.text(x0 + 50, y0 + 112, sub, 26, s["muted"], "ls")
    px, py, pw, ph = x0 + 110, y0 + 150, w - 170, h - 230  # plot box
    for i in range(1, 9):
        gx = px + pw * i / 9
        c.line([(gx, py), (gx, py + ph)], s["grid"], 2)
    for i in range(1, 4):
        gy = py + ph * i / 4
        c.line([(px, gy), (px + pw, gy)], s["grid"], 2)
    c.line([(px, py + ph), (px + pw + 10, py + ph)], s["axis"], 4)
    c.line([(px, py + ph), (px, py - 10)], s["axis"], 4)
    c.text(px + pw, py + ph + 44, "time", 26, s["muted"], "rs")
    c.text(px - 70, py + ph / 2, "V", 30, s["muted"], "mm", bold=True)

    def to_xy(t: float, v: float) -> tuple[float, float]:
        return px + pw * t / T_MAX, py + ph - ph * v / 1.1

    return to_xy


def _rect_pulse(to_xy) -> list[tuple[float, float]]:
    a, b = PULSE_START, PULSE_START + PULSE_LEN
    return [to_xy(0, 0), to_xy(a, 0), to_xy(a, 1), to_xy(b, 1), to_xy(b, 0), to_xy(T_MAX, 0)]


def pulse_sent(c: Canvas) -> None:
    s = STYLES["light"]
    to_xy = _pulse_axes(c, s, "Sent from Ireland", "A crisp, square telegraph pulse")
    c.line(_rect_pulse(to_xy), s["main"], 7)


def received(t: float) -> float:
    u = t - PULSE_START
    return rc_step(u) - rc_step(u - PULSE_LEN)


def pulse_received(c: Canvas) -> None:
    s = STYLES["light"]
    to_xy = _pulse_axes(c, s, "Received in Newfoundland",
                        "Same pulse, same scale: delayed, flattened and smeared out")
    c.line(_rect_pulse(to_xy), s["muted"], 3, dash=(14, 12), op=0.8)
    n = 400
    pts = [to_xy(T_MAX * i / n, received(T_MAX * i / n)) for i in range(n + 1)]
    c.line(pts, s["main"], 7)
    x, y = to_xy(0, 0)
    c.text(x, y + 44, "Model: Thomson (1855), cable as a distributed RC line", 22, s["muted"], "ls")


def delay_vs_length(c: Canvas) -> None:
    s = STYLES["dark"]
    x0, y0, w, h = 1000, 100, 760, 740
    card(c, s, x0, y0, w, h)
    formula(c, x0 + 50, y0 + 92, 64, s["text"], "t", "L²")
    c.text(x0 + 50, y0 + 140, "delay grows with the square of length", 26, s["muted"], "ls")
    px, py, pw, ph = x0 + 120, y0 + 235, w - 190, h - 355
    lmax, tmax = 3.25, 3.25 ** 2

    def to_xy(L: float, t: float) -> tuple[float, float]:
        return px + pw * L / lmax, py + ph - ph * t / tmax

    for k in (1, 2, 3):  # light grid at the marked lengths
        c.line([to_xy(k, 0), to_xy(k, tmax)], s["grid"], 2)
    c.line([(px, py + ph), (px + pw + 10, py + ph)], s["axis"], 4)
    c.line([(px, py + ph), (px, py - 10)], s["axis"], 4)
    n = 300
    c.line([to_xy(lmax * i / n, (lmax * i / n) ** 2) for i in range(n + 1)], s["main"], 8)
    for k in (1, 2, 3):
        t = k * k
        x, y = to_xy(k, t)
        c.line([to_xy(k, 0), (x, y)], s["accent"], 3, dash=(10, 9))
        c.line([to_xy(0, t), (x, y)], s["accent"], 3, dash=(10, 9))
        c.circle(x, y, 11, s["accent"], stroke=NAVY, sw=3)
        c.text(x, py + ph + 38, f"{k}×", 28, s["text"], "ms", bold=True)
        c.text(px - 16, y, f"{t}×", 28, s["accent"], "rm", bold=True)
    c.text(px + pw + 10, py + ph + 82, "cable length  L", 26, s["muted"], "rs")
    c.text(px - 16, py - 26, "signal delay  t", 26, s["muted"], "ls")


def length_x10(c: Canvas) -> None:
    s = STYLES["light"]
    x0, y0, w, h = 160, 330, 1600, 440
    card(c, s, x0, y0, w, h)
    left, unit = x0 + 110, 135.0
    for row_y, units, label in ((y0 + 150, 1, "L"), (y0 + 330, 10, "10 L")):
        end = left + unit * units
        c.line([(left, row_y), (end, row_y)], s["main"], 26)
        c.line([(left, row_y), (end, row_y)], TURQ, 6)
        for i in range(units + 1):
            tx = left + unit * i
            c.line([(tx, row_y - 34), (tx, row_y - 22)], s["muted"], 3)
        c.text(end + 24, row_y, label, 40, s["text"], "lm", bold=True)
    c.text(left, y0 + 66, "Same cable, ten times longer", 30, s["muted"], "ls")


def delay_x100(c: Canvas) -> None:
    s = STYLES["light"]
    x0, y0, w, h = 700, 90, 1060, 770
    card(c, s, x0, y0, w, h)
    c.text(x0 + 50, y0 + 70, "Signal delay", 40, s["text"], "ls", bold=True)
    c.text(x0 + 50, y0 + 112, "bar heights to exact scale", 24, s["muted"], "ls")
    base, top = y0 + h - 120, y0 + 160
    full = base - top
    c.line([(x0 + 70, base), (x0 + w - 70, base)], s["axis"], 4)
    for cx, ratio, top_label, bottom_label in ((x0 + 300, 1, "1×", "length L"),
                                               (x0 + 740, 100, "100×", "length 10 L")):
        bh = full * ratio / 100
        c.rect(cx - 90, base - bh, 180, bh, fill=SEA if ratio == 100 else ORANGE, r=0)
        c.text(cx, base - bh - 18, top_label, 40, s["text"], "ms", bold=True)
        c.text(cx, base + 50, bottom_label, 28, s["muted"], "ms")


CABLE_SHARE = 0.99   # ITU (2025): undersea cables carry "over 99%" of intercontinental data traffic


def _ring_sector(cx, cy, r_out, r_in, a0, a1, steps=180):
    """Annular sector from angle a0 to a1 (radians, clockwise from 12 o'clock)."""
    n = max(2, round(steps * (a1 - a0) / (2 * math.pi)))
    outer = [(cx + r_out * math.sin(a0 + (a1 - a0) * i / n), cy - r_out * math.cos(a0 + (a1 - a0) * i / n))
             for i in range(n + 1)]
    inner = [(cx + r_in * math.sin(a1 - (a1 - a0) * i / n), cy - r_in * math.cos(a1 - (a1 - a0) * i / n))
             for i in range(n + 1)]
    return outer + inner


def share_99(c: Canvas) -> None:
    s = STYLES["light"]
    x0, y0, w, h = 480, 100, 960, 740
    card(c, s, x0, y0, w, h)
    c.text(x0 + w / 2, y0 + 70, "Data crossing between continents", 38, s["text"], "ms", bold=True)
    cx, cy, ro, ri = x0 + 300, y0 + 390, 220, 140
    cable = 2 * math.pi * CABLE_SHARE
    c.poly(_ring_sector(cx, cy, ro, ri, 0, cable), SEA)
    c.poly(_ring_sector(cx, cy, ro + 14, ri - 14, cable, 2 * math.pi), ORANGE)  # the tiny remainder
    c.text(cx, cy - 10, "~99%", 64, s["text"], "mm", bold=True)
    c.text(cx, cy + 50, "undersea cables", 24, s["muted"], "mm")
    lx = x0 + 580
    c.rect(lx, y0 + 300, 34, 34, fill=SEA, r=6)
    c.text(lx + 50, y0 + 317, "undersea cables", 28, s["text"], "lm", bold=True)
    c.rect(lx, y0 + 380, 34, 34, fill=ORANGE, r=6)
    c.text(lx + 50, y0 + 397, "everything else", 28, s["text"], "lm", bold=True)
    c.text(lx + 50, y0 + 432, "(satellites, other routes)", 22, s["muted"], "lm")
    c.text(x0 + 50, y0 + h - 40, "Estimate: International Telecommunication Union (2025)", 22, s["muted"], "ls")


OVERLAYS: dict[str, Callable[[Canvas], None]] = {
    "pulse_sent": pulse_sent,
    "pulse_received": pulse_received,
    "delay_vs_length": delay_vs_length,
    "length_x10": length_x10,
    "delay_x100": delay_x100,
    "share_99": share_99,
}


def render(overlay_id: str, stem: str) -> tuple[Path, Path]:
    c = Canvas()
    OVERLAYS[overlay_id](c)
    OUT.mkdir(exist_ok=True)
    svg, png = OUT / f"{stem}_gfx.svg", OUT / f"{stem}_gfx.png"
    svg.write_text(c.svg(), encoding="utf-8")
    c.png().save(png)
    return svg, png


def self_check() -> None:
    """Numerical checks that the plotted models are what the captions claim."""
    for L in (1, 2, 3, 10):
        assert L**2 == round(L**2)
    assert abs(rc_step(1e9) - 1) < 1e-3 and rc_step(0) == 0
    peak = max(received(T_MAX * i / 2000) for i in range(2001))
    assert 0.2 < peak < 0.6, f"received pulse peak {peak:.2f} no longer a smeared bump"
    t_peak = max(range(2001), key=lambda i: received(T_MAX * i / 2000)) * T_MAX / 2000
    assert t_peak > PULSE_START + PULSE_LEN * 0.5, "received pulse is not delayed"


def render_all(jobs: list[tuple[str, str]]) -> list[Path]:
    self_check()
    files: list[Path] = []
    for overlay_id, stem in jobs:
        files.extend(render(overlay_id, stem))
    return files


if __name__ == "__main__":
    self_check()
    print("model checks passed; run build.py to render the overlays used by frames.txt")
