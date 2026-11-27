"""Rebuild sprites from upscaled pose sheets.

The 4K upscaler returns an opaque RGB image (the transparent background turns black), so the alpha comes from the
original sheet, resized to the upscaled size; colours and line detail come from the upscale. Each sprite is then
cleaned: pieces of neighbouring figures that were cut into its box (they touch the box's left/right edge and are
small next to the figure) are removed.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

from .sprites import _columns


def compose(orig: Path, up: Path) -> Image.Image:
    o = Image.open(orig).convert("RGBA")
    u = Image.open(up).convert("RGB")
    a = o.getchannel("A").resize(u.size, Image.Resampling.LANCZOS)
    out = u.copy()
    out.putalpha(a)
    return out


def boxes_auto(alpha: np.ndarray, count: int) -> list[tuple[int, int]]:
    cols = _columns(alpha, min_gap=10, min_w=40)
    while len(cols) < count:
        k = max(range(len(cols)), key=lambda i: cols[i][1] - cols[i][0])
        x0, x1 = cols[k]
        occ = (alpha[:, x0:x1] > 40).sum(0).astype(float)
        a, b = int((x1 - x0) * 0.3), int((x1 - x0) * 0.7)
        cut = x0 + a + int(np.argmin(occ[a:b]))
        cols[k:k + 1] = [(x0, cut), (cut, x1)]
    return cols[:count]


def _components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    lab = np.zeros(mask.shape, dtype=np.int32)
    h, w = mask.shape
    n = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not lab[y, x]:
                n += 1
                q = deque([(y, x)])
                lab[y, x] = n
                while q:
                    cy, cx = q.popleft()
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = n
                            q.append((ny, nx))
    return lab, n


def clean(sprite: Image.Image, step: int = 3) -> Image.Image:
    """Drop pieces that touch the left/right edge and are small compared with the largest piece."""
    a = np.asarray(sprite)[..., 3]
    small = a[::step, ::step] > 60
    lab, n = _components(small)
    if n <= 1:
        return sprite
    areas = np.bincount(lab.ravel())
    areas[0] = 0
    big = areas.max()
    drop = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        touches = xs.min() <= 1 or xs.max() >= lab.shape[1] - 2
        if touches and areas[k] < 0.25 * big:
            drop.append(k)
    if not drop:
        return sprite
    m = np.isin(lab, drop)
    full = np.kron(m, np.ones((step, step), dtype=bool))[:a.shape[0], :a.shape[1]]
    pad = np.zeros_like(a, dtype=bool)
    pad[:full.shape[0], :full.shape[1]] = full
    # grow the drop mask a little so anti-aliased fringes go too
    g = pad.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (0, 2), (-2, 0), (0, -2)):
        g |= np.roll(np.roll(pad, dy, 0), dx, 1)
    arr = np.asarray(sprite).copy()
    arr[g, 3] = 0
    return Image.fromarray(arr)


def rebuild(art: Path, orig: str, up: str, prefix: str, count: int,
            ranges: list[tuple[int, int]] | None = None) -> list[dict]:
    """Slice the composed sheet into <prefix>_<k>.png (upscaled), clean them, update sprites.json."""
    o_alpha = np.asarray(Image.open(art / orig).convert("RGBA"))[..., 3]
    boxes = ranges or boxes_auto(o_alpha, count)
    sheet = compose(art / orig, art / up)
    fx = sheet.width / o_alpha.shape[1]
    A = np.asarray(sheet)[..., 3]
    out = []
    for k, (x0, x1) in enumerate(boxes):
        X0, X1 = int(x0 * fx), int(x1 * fx)
        ys = np.nonzero((A[:, X0:X1] > 40).any(1))[0]
        fr = sheet.crop((X0, int(ys.min()) - 4, X1, int(ys.max()) + 6))
        fr = clean(fr)
        al = np.asarray(fr)[..., 3]
        cols = np.nonzero((al > 40).any(0))[0]
        rows = np.nonzero((al > 40).any(1))[0]
        fr = fr.crop((max(0, cols.min() - 4), max(0, rows.min() - 4), min(fr.width, cols.max() + 5),
                      min(fr.height, rows.max() + 5)))
        fn = f"{prefix}_{k}.png"
        fr.save(art / fn)
        rows = np.nonzero((np.asarray(fr)[..., 3] > 128).any(1))[0]
        out.append({"file": fn, "w": fr.width, "h": fr.height, "ground": int(rows.max()), "scale": fx})
    meta_f = art / "sprites.json"
    meta = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.is_file() else {}
    meta[prefix] = out
    meta_f.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out
