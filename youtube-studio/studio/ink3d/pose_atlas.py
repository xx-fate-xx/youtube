"""QA sheet: every named key pose (rift_anim, moves) and every gait key, drawn large with its name.

    python -m studio.ink3d.pose_atlas <out.jpg>
"""

import io
import sys

import resvg_py
from PIL import Image, ImageDraw

from studio.ink3d import moves, rift_anim, stick2d
from studio.ink3d.pose2d import Cycle, fk, full, to_px


def poses() -> list[tuple[str, dict]]:
    out = []
    for mod in (moves, rift_anim):
        for k, v in vars(mod).items():
            if k.isupper() and isinstance(v, dict) and "lean" in v:
                out.append((k, v))
            if isinstance(v, Cycle):
                for i in range(8):
                    out.append((f"{k} {i}/8", v.pose(i / 8)))
    return out


def draw(name: str, p: dict, w: int = 300, h: int = 340) -> Image.Image:
    J = fk(full(p))
    low = min(min(J["ankleL"][1], J["ankleR"][1]) - 0.28, min(J["toeL"][1], J["toeR"][1]) - 0.22)
    s = 30.0
    d = to_px({k: (v[0], v[1] - low, v[2]) for k, v in J.items()}, w / 2, h - 30, s)
    side = stick2d.near_sides([d])[0]
    svg = stick2d.svg(d, w, h, side)
    im = Image.new("RGB", (w, h), (244, 237, 224))
    fg = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert("RGBA")
    im.paste(fg, (0, 0), fg)
    dr = ImageDraw.Draw(im)
    dr.line([(0, h - 30), (w, h - 30)], fill=(120, 110, 95), width=2)
    dr.text((6, 6), name, fill=(0, 0, 0))
    return im


if __name__ == "__main__":
    items = poses()
    cols = 10
    tiles = [draw(n, p) for n, p in items]
    rows = (len(tiles) + cols - 1) // cols
    W = Image.new("RGB", (cols * 300, rows * 340), "white")
    for k, t in enumerate(tiles):
        W.paste(t, ((k % cols) * 300, (k // cols) * 340))
    W.save(sys.argv[1], quality=88)
    print(len(items), "poses")
