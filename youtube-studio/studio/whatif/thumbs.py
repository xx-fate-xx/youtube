"""Thumbnails for What If videos, composed from the episode's own art (plates + HD single-pose sprites) — no video
overlays, no new generation. Used by studio.pipeline.release when a thumbnail entry has `plate` instead of `frame`.

episode.yaml release.thumbnails entry:
    {name: thumbnail_a, plate: tower_plate, crop: [x0, y0, x1],            # plate crop (16:9 from width)
     sprites: [[hero4, 820, 690, 560], [cleaner3, 840, 240, 300, flip?, ang?]],   # name, x, ground y, height (px)
     fx: [[bullet, x0, y, x1, scale]],                                      # optional effects (thumbnail px)
     lines: [["YOU'RE UNBREAKABLE.", 92], ["THEY'RE NOT.", 120]], side: left}
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..pipeline.episode import FONTS
from . import comic, fx

TW, TH = 1280, 720
AMBER = (255, 181, 71)


def _sprite(art: Path, name: str, height: float, flip: bool = False, ang: float = 0.0) -> Image.Image:
    im, _gr, _h = comic._sprite(str(art), name)
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a > 20)
    im = im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    k = height / im.height
    im = im.resize((max(1, int(im.width * k)), max(1, int(height))), Image.Resampling.LANCZOS)
    if flip:
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if ang:
        im = im.rotate(-ang, resample=Image.Resampling.BICUBIC, expand=True)
    return im


def compose(art: Path, th: dict, out: Path) -> Path:
    plate = Image.open(art / f"{th['plate']}.png").convert("RGB")
    x0, y0, x1 = th.get("crop", [0, 0, plate.width])
    h = (x1 - x0) * TH / TW
    img = plate.crop((x0, y0, x1, y0 + h)).resize((TW, TH), Image.Resampling.LANCZOS).convert("RGBA")
    side = th.get("side", "left")
    # directional darkening behind the text (no boxes, no bars)
    g = Image.new("L", (TW, TH), 0)
    gd = ImageDraw.Draw(g)
    for x in range(TW):
        f = (1 - x / TW) if side == "left" else (x / TW)
        gd.line([(x, 0), (x, TH)], fill=int(200 * max(0.0, f - 0.3) / 0.7))
    img = Image.alpha_composite(img, Image.merge("RGBA", (*[Image.new("L", (TW, TH), 6)] * 3, g)))
    for e in th.get("fx", []):
        if e[0] == "bullet":
            _, bx0, by, bx1, sc = e
            fx.bullet((bx0, by), (bx1, by), 1.0, scale=sc)(img, 1.0, 0.0)
    for s in th.get("sprites", []):
        name, x, ground, height = s[:4]
        flip = bool(s[4]) if len(s) > 4 else False
        ang = float(s[5]) if len(s) > 5 else 0.0
        sp = _sprite(art, name, height, flip, ang)
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))                        # soft contact shadow
        ImageDraw.Draw(sh).ellipse([x - sp.width * 0.35, ground - 14, x + sp.width * 0.35, ground + 14],
                                   fill=(0, 0, 0, 90))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.alpha_composite(sp, (int(x - sp.width / 2), int(ground - sp.height)))
        img = Image.alpha_composite(img, layer)
    lines = [tuple(x) for x in th["lines"]]
    tx = 60 if side == "left" else TW - 60
    y = TH / 2 - sum(s for _, s in lines) * 0.56 + th.get("dy", 0)
    for k, (text, size) in enumerate(lines):
        f = ImageFont.truetype(str(FONTS / "InterDisplay-ExtraBold.ttf"), size)
        anchor = "la" if side == "left" else "ra"
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((tx, y + 6), text, font=f, fill=(0, 0, 0, 230), anchor=anchor)
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(9)))
        col = AMBER if (k == len(lines) - 1 and th.get("last_amber", True)) else (255, 255, 255)
        ImageDraw.Draw(img).text((tx, y), text, font=f, fill=col, anchor=anchor, stroke_width=3,
                                 stroke_fill=(10, 10, 14))
        y += size * 1.1
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=92)
    return out
