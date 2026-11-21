"""Exact chart overlay kit (SVG source + transparent 1920x1080 PNG) shared by all episodes.

Generated images never draw charts: their prompt reserves an empty area, and the editor
composites the overlay rendered here. Every curve is computed from its formula, so the
graphics stay mathematically correct.

Each overlay keeps 8-10% side margins and stays above the bottom 15% subtitle band (y < 918).

Each episode defines its charts in episodes/<slug>/overlays.py (OVERLAYS dict, optional self_check) using
these primitives; `studio pipe build` renders the ones referenced by GFX lines in frames.txt into
episodes/<slug>/overlays/<frame-file>_gfx.svg|png.
"""

from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageColor, ImageDraw, ImageFont

from .episode import FONTS, ep

W, H = 1920, 1080
SS = 2  # supersampling for the PNG raster
SUBTITLE_TOP = round(H * 0.85)
FONT_DIR = FONTS  # bundled Inter, SIL OFL 1.1

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


# ---------------------------------------------------------------- rendering

def episode_module():
    """Load episodes/<slug>/overlays.py (charts of the current episode), or None if it has none."""
    import importlib.util
    path = ep().src / "overlays.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"overlays_{ep().slug}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render(mod, overlay_id: str, stem: str) -> tuple[Path, Path]:
    c = Canvas()
    mod.OVERLAYS[overlay_id](c)
    out = ep().overlays_dir
    out.mkdir(exist_ok=True)
    svg, png = out / f"{stem}_gfx.svg", out / f"{stem}_gfx.png"
    svg.write_text(c.svg(), encoding="utf-8")
    c.png().save(png)
    return svg, png


def render_all(jobs: list[tuple[str, str]]) -> list[Path]:
    if not jobs:
        return []
    mod = episode_module()
    if mod is None:
        raise SystemExit("frames.txt uses GFX overlays but the episode has no overlays.py")
    unknown = {i for i, _ in jobs} - set(mod.OVERLAYS)
    if unknown:
        raise SystemExit(f"unknown GFX overlays {unknown}")
    if hasattr(mod, "self_check"):
        mod.self_check()
    files: list[Path] = []
    for overlay_id, stem in jobs:
        files.extend(render(mod, overlay_id, stem))
    return files
