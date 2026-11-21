"""Editor titles ("editorial" style): big line + optional small letter-spaced line, placed per frame.

Style (house rule: no accent bars / borders): white InterDisplay Bold with a soft shadow, optional small
second line in light turquoise caps, and a soft local dark glow behind the block (no box, no full-width
band). Placement is chosen per frame and stored in title_layout.json:

  {"<n>": {"main": "...", "sub": "..."|null, "pos": "bottom_center"|..., "dx": 0, "dy": 0, "source": "auto|manual"}}

`py titles.py propose`  -> scores the calmest candidate area of every titled frame (edge density),
                           keeps manual entries, writes title_layout.json
`py titles.py sheet OUT [a-b]` -> contact sheets of frames with their titles for visual review
`py titles.py set N POS [dx dy]` -> manual placement (source=manual)
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
LAYOUT = HERE / "title_layout.json"
FONTS = HERE.parents[1] / "assets" / "fonts" / "inter"
W, H = 1920, 1080
MAIN_PX, SUB_PX, SUB_GAP = 62, 32, 18
SUB_COLOR = (190, 240, 245)
# anchor -> centre of the text block (fractions of the frame); kept inside the 8 % safe area and above
# the bottom 15 % subtitle band
POS = {
    "bottom_center": (0.50, 0.805), "bottom_left": (0.24, 0.805), "bottom_right": (0.76, 0.805),
    "top_center": (0.50, 0.165), "top_left": (0.24, 0.165), "top_right": (0.76, 0.165),
    "mid_left": (0.22, 0.50), "mid_right": (0.78, 0.50),
}
# title text split: frames whose "A · B" becomes big A + small B (others keep one line)
TWO_TIER = {30, 32, 64, 110, 126, 140, 141}
NO_TITLE_WITH_CHART = True          # charts already carry the number (#42, #43, #146)


FALLBACKS = [Path("C:/Windows/Fonts/seguisym.ttf"), Path("C:/Windows/Fonts/cambria.ttc"),
             Path("/System/Library/Fonts/Apple Symbols.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
_CMAP: dict[str, set[int]] = {}


def font(name: str | Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(name if isinstance(name, Path) else FONTS / name), size)


def _cmap(path: Path) -> set[int]:
    if str(path) not in _CMAP:
        from fontTools.ttLib import TTCollection, TTFont
        fonts = TTCollection(str(path)).fonts if path.suffix == ".ttc" else [TTFont(str(path), lazy=True)]
        _CMAP[str(path)] = set(fonts[0].getBestCmap())
    return _CMAP[str(path)]


def runs(text: str, name: str, size: int) -> list[tuple[str, ImageFont.FreeTypeFont]]:
    """Split text into runs drawn with the Inter face or, for glyphs it lacks (e.g. ∝), a symbol fallback."""
    primary = FONTS / name
    out: list[tuple[str, ImageFont.FreeTypeFont]] = []
    for ch in text:
        path = primary
        if ord(ch) not in _cmap(primary):
            path = next((f for f in FALLBACKS if f.is_file() and ord(ch) in _cmap(f)), primary)
        f = font(path, size)
        if out and out[-1][1].path == f.path:
            out[-1] = (out[-1][0] + ch, out[-1][1])
        else:
            out.append((ch, f))
    return out


def text_width(text: str, name: str, size: int) -> float:
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    return sum(d.textlength(t, font=f) for t, f in runs(text, name, size))


def draw_text(d: ImageDraw.ImageDraw, cx: float, cy: float, text: str, name: str, size: int, fill) -> None:
    """Centre text at (cx, cy) like anchor="mm", mixing fonts on one baseline."""
    asc, desc = font(name, size).getmetrics()
    x, base = cx - text_width(text, name, size) / 2, cy + (asc - desc) / 2
    for t, f in runs(text, name, size):
        d.text((x, base), t, font=f, fill=fill, anchor="ls")
        x += d.textlength(t, font=f)


def split(n: int, text: str) -> tuple[str, str | None]:
    if n in TWO_TIER and "·" in text:
        a, b = text.split("·", 1)
        return a.strip(), b.strip().upper()
    return text, None


def block_size(main: str, sub: str | None) -> tuple[int, int]:
    w = text_width(main, "InterDisplay-Bold.ttf", MAIN_PX)
    h = MAIN_PX
    if sub:
        w = max(w, text_width(" ".join(sub), "Inter-SemiBold.ttf", SUB_PX))
        h += SUB_GAP + SUB_PX
    return int(w), int(h)


def centre(spec: dict) -> tuple[float, float]:
    """Block centre, clamped so the whole block stays inside the 8 % safe area."""
    fx, fy = POS[spec["pos"]]
    bw, bh = block_size(spec["main"], spec.get("sub"))
    cx, cy = fx * W + spec.get("dx", 0), fy * H + spec.get("dy", 0)
    cx = min(max(cx, 0.08 * W + bw / 2), 0.92 * W - bw / 2)
    cy = min(max(cy, 0.08 * H + bh / 2), 0.85 * H - bh / 2)
    return cx, cy


def draw(spec: dict) -> Image.Image:
    """Transparent 1920x1080 layer with the title block at its placement."""
    main, sub = spec["main"], spec.get("sub")
    bw, bh = block_size(main, sub)
    cx, cy = centre(spec)
    top = cy - bh / 2
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # soft local glow behind the block (no box): a blurred dark ellipse
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pad_x, pad_y = 70 + bw * 0.12, 46
    gd.ellipse([cx - bw / 2 - pad_x, top - pad_y, cx + bw / 2 + pad_x, top + bh + pad_y], fill=(4, 12, 24, 150))
    layer = Image.alpha_composite(layer, glow.filter(ImageFilter.GaussianBlur(38)))
    # text shadows
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    ym = top + MAIN_PX / 2
    ys = ym + MAIN_PX / 2 + SUB_GAP + SUB_PX / 2
    draw_text(sd, cx, ym + 3, main, "InterDisplay-Bold.ttf", MAIN_PX, (0, 0, 0, 190))
    if sub:
        draw_text(sd, cx, ys + 2, " ".join(sub), "Inter-SemiBold.ttf", SUB_PX, (0, 0, 0, 190))
    layer = Image.alpha_composite(layer, sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(layer)
    draw_text(d, cx, ym, main, "InterDisplay-Bold.ttf", MAIN_PX, (255, 255, 255, 255))
    if sub:
        draw_text(d, cx, ys, " ".join(sub), "Inter-SemiBold.ttf", SUB_PX, (*SUB_COLOR, 255))
    return layer


def load() -> dict[int, dict]:
    if LAYOUT.is_file():
        return {int(k): v for k, v in json.loads(LAYOUT.read_text(encoding="utf-8")).items()}
    return {}


def save(layout: dict[int, dict]) -> None:
    LAYOUT.write_text(json.dumps({str(k): layout[k] for k in sorted(layout)}, ensure_ascii=False, indent=1),
                      encoding="utf-8")


def titled_rows() -> list[dict]:
    rows = [r for r in csv.DictReader(open(HERE / "edit_timeline.csv", encoding="utf-8")) if r["overlay"]]
    return [r for r in rows if not (NO_TITLE_WITH_CHART and r["gfx_overlay"])]


def frame_image(n: int) -> Image.Image:
    import production
    import qa
    d = production.decisions(production.load_state())[n]
    return qa.to_169(Image.open(production.PROJECT / d["file"]).convert("RGB"))[0].resize((W, H))


def busyness(img: Image.Image, spec: dict) -> float:
    """Mean edge strength under the block (+margin); lower = calmer place for text."""
    bw, bh = block_size(spec["main"], spec.get("sub"))
    cx, cy = centre(spec)
    box = [int(cx - bw / 2 - 40), int(cy - bh / 2 - 30), int(cx + bw / 2 + 40), int(cy + bh / 2 + 30)]
    box = [max(0, box[0]), max(0, box[1]), min(W, box[2]), min(H, box[3])]
    edges = img.convert("L").filter(ImageFilter.FIND_EDGES).crop(box)
    hist = edges.histogram()
    return sum(i * c for i, c in enumerate(hist)) / max(1, sum(hist))


def propose() -> None:
    layout = load()
    for r in titled_rows():
        n = int(r["n"])
        if layout.get(n, {}).get("source") == "manual":
            continue
        main, sub = split(n, r["overlay"])
        img = frame_image(n)
        best = None
        for pos in POS:
            spec = {"main": main, "sub": sub, "pos": pos}
            score = busyness(img, spec) + (0 if pos == "bottom_center" else 1.5)   # mild prior for bottom centre
            if best is None or score < best[0]:
                best = (score, pos)
        layout[n] = {"main": main, "sub": sub, "pos": best[1], "dx": 0, "dy": 0, "source": "auto"}
        print(f"#{n:<4} {best[1]:<14} {best[0]:5.1f}  {main}{' / ' + sub if sub else ''}", flush=True)
    keep = {int(r["n"]) for r in titled_rows()}
    save({k: v for k, v in layout.items() if k in keep})


def sheet(out: Path, rng: str | None) -> None:
    layout = load()
    ns = sorted(layout)
    if rng:
        lo, hi = (int(x) for x in rng.split("-"))
        ns = [n for n in ns if lo <= n <= hi]
    cols, tw, th = 3, 640, 360
    for page in range(0, len(ns), 12):
        chunk = ns[page:page + 12]
        rows_n = (len(chunk) + cols - 1) // cols
        sh = Image.new("RGB", (cols * tw + (cols - 1) * 8, rows_n * (th + 30)), (24, 24, 24))
        d = ImageDraw.Draw(sh)
        for k, n in enumerate(chunk):
            img = Image.alpha_composite(frame_image(n).convert("RGBA"), draw(layout[n])).convert("RGB")
            x, y = (k % cols) * (tw + 8), (k // cols) * (th + 30)
            sh.paste(img.resize((tw, th), Image.Resampling.LANCZOS), (x, y + 30))
            d.text((x + 6, y + 6), f"#{n}  {layout[n]['pos']}  ({layout[n]['source']})", fill=(230, 230, 230),
                   font=font("Inter-SemiBold.ttf", 18))
        p = out / f"titles_{chunk[0]:03d}-{chunk[-1]:03d}.png"
        sh.save(p)
        print(p)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "propose"
    if cmd == "propose":
        propose()
    elif cmd == "sheet":
        sheet(Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "set":
        layout = load()
        n = int(sys.argv[2])
        layout[n].update(pos=sys.argv[3], dx=int(sys.argv[4]) if len(sys.argv) > 4 else 0,
                         dy=int(sys.argv[5]) if len(sys.argv) > 5 else 0, source="manual")
        save(layout)
        print(n, layout[n])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
