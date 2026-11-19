"""Vector canvas with two backends: editable SVG (source asset) and PNG raster (Pillow).

All coordinates are in a logical space (default 1920x1080). Elements carry a build `step`
(and optional `until`) so a diagram can be revealed progressively for restrained motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, ImageColor, ImageDraw, ImageFont

from studio.channels import VisualIdentity

INTER_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "inter"
# Bundled Inter (SIL OFL 1.1, provenance in assets/fonts/inter/SOURCE.json) comes first.
# System fonts are only a fallback; their licence for video use is NOT cleared.
FONT_CANDIDATES: list[tuple[str, str, int, int]] = [
    (str(INTER_DIR / "Inter-Regular.ttf"), str(INTER_DIR / "Inter-Bold.ttf"), 0, 0),
    ("/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/HelveticaNeue.ttc", 0, 1),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial.ttf", 0, 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0, 0),
]
FONT_OVERRIDE: str | None = None


def font_paths() -> tuple[str, str] | None:
    """(regular, bold) files actually used for rendering, or None for Pillow's default."""
    if FONT_OVERRIDE and Path(FONT_OVERRIDE).exists():
        return FONT_OVERRIDE, FONT_OVERRIDE
    for regular, bold, _, _ in FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    return None


def font_is_bundled_inter() -> bool:
    paths = font_paths()
    return bool(paths) and Path(paths[0]).parent == INTER_DIR


@lru_cache(maxsize=512)
def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(1, int(size))
    if FONT_OVERRIDE and Path(FONT_OVERRIDE).exists():
        return ImageFont.truetype(FONT_OVERRIDE, size)
    for regular, bold_path, r_idx, b_idx in FONT_CANDIDATES:
        path = bold_path if bold else regular
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=b_idx if bold else r_idx)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def rgba(color: str) -> tuple[int, int, int, int]:
    c = ImageColor.getrgb(color)
    return (c[0], c[1], c[2], c[3] if len(c) == 4 else 255)


def svg_color(color: str | None) -> tuple[str, float]:
    if not color:
        return "none", 1.0
    r, g, b, a = rgba(color)
    return f"#{r:02x}{g:02x}{b:02x}", round(a / 255, 3)


def wrap_text(text: str, size: int, max_width: float, bold: bool = False) -> list[str]:
    font = get_font(size, bold)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}".strip()
            if font.getlength(trial) <= max_width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


@dataclass(frozen=True)
class Theme:
    bg: str
    fg: str
    accent: str
    accent2: str
    muted: str
    caption_bg: str
    font_family: str
    danger: str = "#E5484D"

    @classmethod
    def from_identity(cls, v: VisualIdentity) -> Theme:
        return cls(v.background, v.foreground, v.accent, v.accent_2, v.muted, v.caption_bg,
                   v.font_family)


@dataclass
class Canvas:
    width: int = 1920
    height: int = 1080
    background: str = "#000000"
    font_family: str = "Helvetica, Arial, sans-serif"
    elements: list[dict[str, Any]] = field(default_factory=list)

    # ---------------------------------------------------------------- primitives
    def _add(self, kind: str, step: int, until: int | None, **params: Any) -> None:
        self.elements.append({"kind": kind, "step": step, "until": until, **params})

    def rect(self, x: float, y: float, w: float, h: float, *, fill: str | None = None,
             stroke: str | None = None, sw: float = 2, r: float = 0, step: int = 0,
             until: int | None = None, **fx: Any) -> None:
        self._add("rect", step, until, x=x, y=y, w=w, h=h, fill=fill, stroke=stroke, sw=sw, r=r,
                  **fx)

    def line(self, points: list[tuple[float, float]], *, color: str, width: float = 3,
             dash: tuple[float, float] | None = None, step: int = 0,
             until: int | None = None, **fx: Any) -> None:
        self._add("line", step, until, points=points, color=color, width=width, dash=dash, **fx)

    def circle(self, cx: float, cy: float, r: float, *, fill: str | None = None,
               stroke: str | None = None, sw: float = 2, step: int = 0,
               until: int | None = None, **fx: Any) -> None:
        self._add("circle", step, until, cx=cx, cy=cy, r=r, fill=fill, stroke=stroke, sw=sw, **fx)

    def polygon(self, points: list[tuple[float, float]], *, fill: str | None = None,
                stroke: str | None = None, sw: float = 2, step: int = 0,
                until: int | None = None, **fx: Any) -> None:
        self._add("polygon", step, until, points=points, fill=fill, stroke=stroke, sw=sw, **fx)

    def text(self, x: float, y: float, s: str, *, size: int = 36, color: str = "#FFFFFF",
             anchor: str = "lt", bold: bool = False, step: int = 0,
             until: int | None = None, **fx: Any) -> None:
        """anchor: horizontal l|m|r + vertical t|m|b."""
        self._add("text", step, until, x=x, y=y, s=s, size=size, color=color, anchor=anchor,
                  bold=bold, **fx)

    def paragraph(self, x: float, y: float, s: str, *, size: int, color: str, max_width: float,
                  bold: bool = False, line_height: float = 1.25, anchor_h: str = "l",
                  step: int = 0, until: int | None = None, **fx: Any) -> float:
        """Wrapped text block; returns the y below the block."""
        group = f"p{len(self.elements)}"
        for line in wrap_text(s, size, max_width, bold):
            self.text(x, y, line, size=size, color=color, anchor=f"{anchor_h}t", bold=bold,
                      step=step, until=until, group=group, **fx)
            y += size * line_height
        return y

    def arrow(self, x1: float, y1: float, x2: float, y2: float, *, color: str, width: float = 4,
              head: float = 18, dash: tuple[float, float] | None = None, step: int = 0,
              until: int | None = None, **fx: Any) -> None:
        ang = math.atan2(y2 - y1, x2 - x1)
        bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
        self.line([(x1, y1), (bx, by)], color=color, width=width, dash=dash, step=step,
                  until=until, **fx)
        left = (bx + head * 0.55 * math.sin(ang), by - head * 0.55 * math.cos(ang))
        right = (bx - head * 0.55 * math.sin(ang), by + head * 0.55 * math.cos(ang))
        fx_head = {k: v for k, v in fx.items() if k not in {"flow", "anim", "delay", "dur"}}
        head_delay = float(fx.get("delay", 0.0)) + 0.6 * float(fx.get("dur", 1.0))
        self.polygon([(x2, y2), left, right], fill=color, step=step, until=until,
                     anim="fade", delay=head_delay, **fx_head)

    # ---------------------------------------------------------------- rendering
    @property
    def max_step(self) -> int:
        return max((e["step"] for e in self.elements), default=0)

    def visible(self, upto: int | None) -> list[dict[str, Any]]:
        if upto is None:
            upto = self.max_step
        return [e for e in self.elements
                if e["step"] <= upto and (e["until"] is None or upto <= e["until"])]

    def to_svg(self, upto: int | None = None) -> str:
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
               f'height="{self.height}" viewBox="0 0 {self.width} {self.height}">']
        bg, _ = svg_color(self.background)
        out.append(f'<rect width="100%" height="100%" fill="{bg}"/>')
        for e in self.visible(upto):
            k = e["kind"]
            if k in {"rect", "circle", "polygon"}:
                fill, fo = svg_color(e["fill"])
                stroke, so = svg_color(e["stroke"])
                style = (f'fill="{fill}" fill-opacity="{fo}" stroke="{stroke}" '
                         f'stroke-opacity="{so}" stroke-width="{e["sw"]}"')
                if k == "rect":
                    out.append(f'<rect x="{e["x"]:.1f}" y="{e["y"]:.1f}" width="{e["w"]:.1f}" '
                               f'height="{e["h"]:.1f}" rx="{e["r"]}" {style}/>')
                elif k == "circle":
                    out.append(f'<circle cx="{e["cx"]:.1f}" cy="{e["cy"]:.1f}" r="{e["r"]:.1f}" '
                               f'{style}/>')
                else:
                    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in e["points"])
                    out.append(f'<polygon points="{pts}" {style}/>')
            elif k == "line":
                color, op = svg_color(e["color"])
                pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in e["points"])
                dash = f' stroke-dasharray="{e["dash"][0]},{e["dash"][1]}"' if e["dash"] else ""
                out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                           f'stroke-opacity="{op}" stroke-width="{e["width"]}" '
                           f'stroke-linecap="round" stroke-linejoin="round"{dash}/>')
            elif k == "text":
                color, op = svg_color(e["color"])
                ta = {"l": "start", "m": "middle", "r": "end"}[e["anchor"][0]]
                db = {"t": "hanging", "m": "central", "b": "alphabetic"}[e["anchor"][1]]
                weight = "bold" if e["bold"] else "normal"
                out.append(f'<text x="{e["x"]:.1f}" y="{e["y"]:.1f}" fill="{color}" '
                           f'fill-opacity="{op}" font-family="{escape(self.font_family)}" '
                           f'font-size="{e["size"]}" font-weight="{weight}" text-anchor="{ta}" '
                           f'dominant-baseline="{db}">{escape(e["s"])}</text>')
        out.append("</svg>")
        return "\n".join(out)

    def to_image(self, upto: int | None = None, size: tuple[int, int] | None = None,
                 supersample: int = 2) -> Image.Image:
        out_w, out_h = size or (self.width, self.height)
        scale = out_w / self.width * supersample
        img = Image.new("RGB", (round(self.width * scale), round(self.height * scale)),
                        rgba(self.background)[:3])
        draw = ImageDraw.Draw(img, "RGBA")
        for e in self.visible(upto):
            draw_element(draw, e, scale)
        if supersample != 1:
            img = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
        return img

    def save(self, svg_path: Path | None, png_path: Path | None, upto: int | None = None,
             size: tuple[int, int] | None = None) -> None:
        if svg_path:
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(self.to_svg(upto), encoding="utf-8")
        if png_path:
            png_path.parent.mkdir(parents=True, exist_ok=True)
            self.to_image(upto, size).save(png_path, optimize=False, compress_level=3)


def _alpha(color: str, alpha: float) -> tuple[int, int, int, int]:
    r, g, b, a = rgba(color)
    return (r, g, b, max(0, min(255, round(a * alpha))))


def polyline_length(pts: list[tuple[float, float]]) -> float:
    return sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:],
                                                                           strict=False))


def point_at(pts: list[tuple[float, float]], frac: float) -> tuple[float, float]:
    """Point at fraction `frac` of the polyline's length."""
    target = polyline_length(pts) * max(0.0, min(1.0, frac))
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg >= target and seg > 0:
            u = target / seg
            return x1 + (x2 - x1) * u, y1 + (y2 - y1) * u
        target -= seg
    return pts[-1]


def truncate_polyline(pts: list[tuple[float, float]], frac: float) -> list[tuple[float, float]]:
    if frac >= 1:
        return pts
    target = polyline_length(pts) * max(0.0, frac)
    out = [pts[0]]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg >= target:
            u = target / seg if seg else 0
            out.append((x1 + (x2 - x1) * u, y1 + (y2 - y1) * u))
            return out
        out.append((x2, y2))
        target -= seg
    return out


def default_anim(e: dict[str, Any]) -> str:
    if "anim" in e:
        return e["anim"]
    return {"line": "draw", "circle": "grow"}.get(e["kind"], "fade")


def draw_element(draw: ImageDraw.ImageDraw, e: dict[str, Any], scale: float, *,
                 ox: float = 0.0, oy: float = 0.0, progress: float = 1.0,
                 alpha: float = 1.0) -> None:
    """Draw one canvas element. Logical (x, y) maps to ((x - ox) * scale, (y - oy) * scale).

    `progress` (0..1) animates the reveal: lines are drawn on, circles grow, everything else
    fades (text also slides up slightly). `alpha` multiplies opacity (used for exits).
    """
    k = e["kind"]
    anim = default_anim(e)
    a = alpha
    dx = dy = 0.0
    if progress < 1:
        if anim == "fade":
            a *= progress
            if k == "text":
                dy = 14 * (1 - progress)
        elif anim == "grow":
            a *= min(1.0, progress * 2)
        elif anim == "slide":
            sx, sy = e.get("slide_from", (0.0, -40.0))
            dx, dy = sx * (1 - progress), sy * (1 - progress)
            a *= min(1.0, progress * 3)
        elif anim == "draw" and k != "line":
            a *= progress
    if a <= 0.004:
        return

    def p(x: float, y: float) -> tuple[float, float]:
        return (x + dx - ox) * scale, (y + dy - oy) * scale

    def col(c: str | None):
        return _alpha(c, a) if c else None

    if k == "rect":
        box = [*p(e["x"], e["y"]), *p(e["x"] + e["w"], e["y"] + e["h"])]
        draw.rounded_rectangle(box, radius=e["r"] * scale, fill=col(e["fill"]),
                               outline=col(e["stroke"]),
                               width=max(1, round(e["sw"] * scale)) if e["stroke"] else 0)
    elif k == "circle":
        cx, cy = p(e["cx"], e["cy"])
        grow = progress if (anim == "grow" and progress < 1) else 1.0
        grow = 1 - (1 - grow) ** 3
        r = e["r"] * scale * grow
        if r <= 0.3:
            return
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col(e["fill"]),
                     outline=col(e["stroke"]),
                     width=max(1, round(e["sw"] * scale)) if e["stroke"] else 0)
    elif k == "polygon":
        pts = [p(x, y) for x, y in e["points"]]
        if e["fill"]:
            draw.polygon(pts, fill=col(e["fill"]))
        if e["stroke"]:
            draw.line(pts + [pts[0]], fill=col(e["stroke"]),
                      width=max(1, round(e["sw"] * scale)), joint="curve")
    elif k == "line":
        src = e["points"]
        if anim == "draw" and progress < 1:
            src = truncate_polyline(src, 1 - (1 - progress) ** 2)
            if len(src) < 2:
                return
        pts = [p(x, y) for x, y in src]
        width = max(1, round(e["width"] * scale))
        color = col(e["color"])
        if e["dash"]:
            for seg in _dash_segments(pts, e["dash"][0] * scale, e["dash"][1] * scale):
                draw.line(seg, fill=color, width=width)
        else:
            draw.line(pts, fill=color, width=width, joint="curve")
            r = width / 2
            for x, y in (pts[0], pts[-1]):
                draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    elif k == "text":
        font = get_font(round(e["size"] * scale), e["bold"])
        pil_anchor = e["anchor"][0] + {"t": "t", "m": "m", "b": "s"}[e["anchor"][1]]
        draw.text(p(e["x"], e["y"]), e["s"], font=font, fill=col(e["color"]), anchor=pil_anchor)


def element_bbox(e: dict[str, Any]) -> tuple[float, float, float, float]:
    """Approximate logical bounding box (x0, y0, x1, y1)."""
    k = e["kind"]
    if k == "rect":
        return e["x"], e["y"], e["x"] + e["w"], e["y"] + e["h"]
    if k == "circle":
        return e["cx"] - e["r"], e["cy"] - e["r"], e["cx"] + e["r"], e["cy"] + e["r"]
    if k in {"polygon", "line"}:
        xs = [x for x, _ in e["points"]]
        ys = [y for _, y in e["points"]]
        return min(xs), min(ys), max(xs), max(ys)
    font = get_font(e["size"], e["bold"])
    w = font.getlength(e["s"])
    h = e["size"] * 1.2
    x0 = {"l": e["x"], "m": e["x"] - w / 2, "r": e["x"] - w}[e["anchor"][0]]
    y0 = {"t": e["y"], "m": e["y"] - h / 2, "b": e["y"] - h}[e["anchor"][1]]
    return x0, y0, x0 + w, y0 + h


def _dash_segments(pts: list[tuple[float, float]], on: float, off: float):
    segs: list[list[tuple[float, float]]] = []
    drawing, remaining = True, on
    current: list[tuple[float, float]] = [pts[0]]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        seg_len = math.hypot(x2 - x1, y2 - y1)
        pos = 0.0
        while seg_len - pos > 1e-6:
            step = min(remaining, seg_len - pos)
            pos += step
            t = pos / seg_len
            pt = (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
            if drawing:
                current.append(pt)
            remaining -= step
            if remaining <= 1e-6:
                if drawing and len(current) > 1:
                    segs.append(current)
                drawing = not drawing
                remaining = on if drawing else off
                current = [pt]
    if drawing and len(current) > 1:
        segs.append(current)
    return segs


# ------------------------------------------------------------------ geometry helpers


def quad_curve(p0, p1, p2, n: int = 40) -> list[tuple[float, float]]:
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        pts.append((x, y))
    return pts


def blob(cx: float, cy: float, rx: float, ry: float, seed: int, n: int = 72):
    """Deterministic irregular landmass outline (schematic, not geographic)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        wobble = (1 + 0.10 * math.sin(3 * a + seed) + 0.06 * math.sin(7 * a + seed * 2.1)
                  + 0.03 * math.sin(13 * a + seed * 0.7))
        pts.append((cx + rx * wobble * math.cos(a), cy + ry * wobble * math.sin(a)))
    return pts


# ------------------------------------------------------------------ shared frames


def base_frame(t: Theme, title: str, *, schematic: bool = True, grid: bool = True) -> Canvas:
    c = Canvas(background=t.bg, font_family=t.font_family)
    if grid:
        faint = t.muted + "22" if len(t.muted) == 7 else t.muted
        for x in range(0, 1921, 80):
            c.line([(x, 0), (x, 1080)], color=faint, width=1, anim="none")
        for y in range(0, 1081, 80):
            c.line([(0, y), (1920, y)], color=faint, width=1, anim="none")
    # HUD band: keeps the title readable when the camera moves into the diagram.
    c.rect(0, 0, 1920, 128, fill=t.bg + "FF", hud=True)
    for k, alpha in enumerate(("CC", "88", "44", "18")):
        c.rect(0, 128 + k * 9, 1920, 9, fill=t.bg + alpha, hud=True)
    c.rect(90, 70, 8, 44, fill=t.accent, hud=True)
    c.text(116, 92, title.upper(), size=34, color=t.fg, anchor="lm", bold=True, hud=True)
    if schematic:
        c.text(1830, 92, "SCHEMATIC - NOT TO SCALE", size=22, color=t.muted, anchor="rm",
               hud=True)
    return c


def title_card(t: Theme, title: str, channel_name: str) -> Canvas:
    c = Canvas(background=t.bg, font_family=t.font_family)
    for i in range(9):
        y = 640 + i * 26
        c.line(quad_curve((0, y), (960, y - 120 + i * 18), (1920, y + 40)),
               color=t.accent + "55", width=2, intro=True, delay=0.1 * i, dur=2.0,
               flow=t.accent + "AA" if i % 3 == 1 else None, flow_gap=420, flow_speed=200,
               nofocus=True)
    c.rect(150, 300, 10, 230, fill=t.accent, intro=True, anim="grow", delay=0.6)
    c.text(190, 300, channel_name.upper(), size=34, color=t.accent, bold=True, intro=True,
           delay=0.8)
    c.paragraph(190, 360, title, size=88, color=t.fg, max_width=1500, bold=True,
                line_height=1.1, intro=True, anim="slide", slide_from=(-60.0, 0.0), delay=1.1)
    return c


def text_card(t: Theme, text: str, heading: str = "") -> Canvas:
    items = [s.strip() for s in text.split("|") if s.strip()]
    c = base_frame(t, heading or "In this video", schematic=False)
    if len(items) == 1:
        c.paragraph(960, 420, items[0], size=72, color=t.fg, max_width=1500, bold=True,
                    anchor_h="m", intro=True, delay=0.4)
        return c
    y = 230
    for i, item in enumerate(items, start=1):
        fx = {"intro": True} if i == 1 else {}
        c.circle(260, y + 40, 38, fill=t.accent, step=i - 1, **fx)
        c.text(260, y + 40, str(i), size=40, color=t.bg, anchor="mm", bold=True, step=i - 1,
               delay=0.3, **fx)
        c.text(330, y + 40, item, size=54, color=t.fg, anchor="lm", step=i - 1, anim="slide",
               slide_from=(80.0, 0.0), delay=0.2, **fx)
        y += 120
    return c
