"""Thumbnail variants (1280x720) for A/B choice, with a small-size readability check.

All artwork is the episode's own code-generated diagrams (no stock, no faces), so every
variant inherits the diagram licence (original work). YouTube accepts JPG/PNG up to 2 MB.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from studio.channels import ChannelProfile
from studio.diagrams import get_diagram
from studio.visuals import Theme, get_font, rgba, wrap_text

W, H = 1280, 720
MOBILE_W = 320  # YouTube search/home thumbnails on phones are roughly this wide
MIN_MOBILE_TEXT_PX = 14


@dataclass(frozen=True)
class Variant:
    key: str
    path: Path
    text: str
    min_text_px_at_mobile: float
    size_bytes: int


def _artwork(ref: str, theme: Theme) -> Image.Image:
    canvas = get_diagram(ref).build(theme)
    canvas.elements = [
        e for e in canvas.elements
        if e["kind"] != "text" and not e.get("hud") and e.get("anim") != "none"
        and not (e["kind"] == "line" and e["width"] <= 2)        # leader lines
        and not (e["kind"] == "circle" and e["r"] <= 8)]          # leader dots
    return canvas.to_image(None, (1920, 1080))


def _crop_center(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Crop the busiest region (largest non-background area) to the requested aspect."""
    bg = img.getpixel((5, 5))
    diff = Image.eval(img.convert("L"), lambda v: v)
    mask = Image.new("L", img.size, 0)
    mask.paste(diff.point(lambda v, b=sum(bg[:3]) // 3: 255 if abs(v - b) > 18 else 0))
    bbox = mask.getbbox() or (0, 0, *img.size)
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    aspect = box_w / box_h
    w = min(img.width, max(bbox[2] - bbox[0], (bbox[3] - bbox[1]) * aspect) * 1.08)
    h = w / aspect
    if h > img.height:
        h = img.height
        w = h * aspect
    x0 = min(max(0, cx - w / 2), img.width - w)
    y0 = min(max(0, cy - h / 2), img.height - h)
    return img.crop((round(x0), round(y0), round(x0 + w), round(y0 + h))).resize(
        (box_w, box_h), Image.Resampling.LANCZOS)


def _text_block(d: ImageDraw.ImageDraw, text: str, x: int, y: int, max_w: int, size: int,
                color, *, upper: bool = True, max_lines: int = 4,
                shadow: bool = False) -> tuple[int, int]:
    """Draw wrapped bold text; shrinks to fit max_lines. Returns (used font size, bottom y)."""
    s = text.upper() if upper else text
    while size > 28:
        lines = wrap_text(s, size, max_w, bold=True)
        if len(lines) <= max_lines:
            break
        size -= 4
    lines = wrap_text(s, size, max_w, bold=True)[:max_lines]
    font = get_font(size, bold=True)
    for line in lines:
        if shadow:
            d.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0, 170))
        d.text((x, y), line, font=font, fill=color)
        y += int(size * 1.08)
    return size, y


def render_variants(out_dir: Path, *, title: str, hook: str, channel: ChannelProfile,
                    diagram: str) -> list[Variant]:
    theme = Theme.from_identity(channel.visual)
    bg = rgba(theme.bg)[:3]
    fg = rgba(theme.fg)
    accent = rgba(theme.accent)
    accent2 = rgba(theme.accent2)
    art = _artwork(diagram, theme)
    out_dir.mkdir(parents=True, exist_ok=True)
    made: list[Variant] = []

    def save(key: str, img: Image.Image, text: str, size: int) -> None:
        jpg = out_dir / f"thumbnail_{key}.jpg"
        img.convert("RGB").save(jpg, quality=90, optimize=True)
        img.convert("RGB").save(out_dir / f"thumbnail_{key}.png")
        made.append(Variant(key, jpg, text, size * MOBILE_W / W, jpg.stat().st_size))

    # A: classic - title column + artwork
    a = Image.new("RGB", (W, H), bg)
    a.paste(_crop_center(art, 600, 600), (W - 600 - 24, 60))
    d = ImageDraw.Draw(a, "RGBA")
    d.rectangle([60, 120, 72, 560], fill=accent)
    size, _ = _text_block(d, title, 100, 130, 520, 66, fg)
    d.text((100, 640), channel.name.upper(), font=get_font(30, bold=True), fill=accent)
    save("a_classic", a, title, size)

    # B: big hook over a dimmed full-bleed diagram
    b = _crop_center(art, W, H)
    b = ImageEnhance.Brightness(b.filter(ImageFilter.GaussianBlur(2))).enhance(0.45)
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 0, W, H], fill=(*bg, 90))
    size, bottom = _text_block(d, hook, 80, 150, W - 160, 128, fg, max_lines=3, shadow=True)
    d.rectangle([80, bottom + 18, 380, bottom + 34], fill=accent2)
    save("b_hook", b, hook, size)

    # C: contrast split - hook on the dark half, artwork on an accent panel
    c = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(c, "RGBA")
    d.rectangle([W // 2, 0, W, H], fill=accent)
    tile = _crop_center(art, W // 2 - 60, H - 120)
    c.paste(tile, (W // 2 + 30, 60))
    size, _ = _text_block(d, hook, 60, 170, W // 2 - 110, 104, accent2, max_lines=4)
    save("c_split", c, hook, size)
    return made


def readability_issues(variants: list[Variant]) -> list[str]:
    issues = []
    for v in variants:
        if v.min_text_px_at_mobile < MIN_MOBILE_TEXT_PX:
            issues.append(f"{v.key}: text only {v.min_text_px_at_mobile:.0f}px tall at "
                          f"{MOBILE_W}px wide (< {MIN_MOBILE_TEXT_PX}px) - shorten the text")
        if v.size_bytes > 2_000_000:
            issues.append(f"{v.key}: {v.size_bytes / 1e6:.1f} MB exceeds YouTube's 2 MB limit")
    return issues
