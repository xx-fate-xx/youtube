"""Ink outline as a post-process on Blender frames (deterministic, no compositor quirks).

    python -m studio.ink3d.outline <frames_dir> [width_px]

Reads <dir>/NNNN.png and the masks Blender wrote (<dir>/masks/fig_NNNN.png, head_NNNN.png). Per frame:
binary figure mask -> morphological close (bridges the slit between a tucked head and the back, an arm and the
body) -> fill every enclosed hole -> paint the closed-in pixels figure-white -> ring around the closed figure plus
a ring around the head -> slightly anti-aliased ink line. Overwrites NNNN.png in place (keeps a .raw copy once).
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

INK = (22, 20, 15)
WHITE = (251, 247, 238)


def _bin(im: Image.Image) -> Image.Image:
    return im.convert("L").point(lambda v: 255 if v > 127 else 0)


def _shift_max(a: np.ndarray, r: int, op) -> np.ndarray:
    """Disk-ish dilation/erosion by r px: r rounds of a 3x3 cross (numpy, fast)."""
    for _ in range(r):
        p = np.pad(a, 1, mode="edge")
        a = op.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    return a


def _grow(m: Image.Image, r: int) -> Image.Image:
    return Image.fromarray(_shift_max(np.asarray(m), r, np.maximum))


def _shrink(m: Image.Image, r: int) -> Image.Image:
    return Image.fromarray(_shift_max(np.asarray(m), r, np.minimum))


def _fill_holes(m: np.ndarray) -> np.ndarray:
    """Fill enclosed holes: flood the outside on a 4x smaller mask (PIL floodfill is pure Python), scale back."""
    h, w = m.shape
    small = Image.fromarray(m).resize((w // 4, h // 4), Image.Resampling.BOX).point(lambda v: 255 if v > 0 else 0)
    pad = Image.new("L", (small.width + 2, small.height + 2), 0)
    pad.paste(small, (1, 1))
    ImageDraw.floodfill(pad, (0, 0), 128)
    outside = np.asarray(pad.crop((1, 1, small.width + 1, small.height + 1)).resize((w, h), Image.Resampling.NEAREST)) == 128
    outside = _shift_max(outside.astype(np.uint8), 3, np.maximum) > 0       # stay off the real edge
    return np.where(outside, m, 255).astype(np.uint8)


def frame(img: Image.Image, fig: Image.Image, head: Image.Image, width: int = 5, close: int = 10) -> Image.Image:
    """Repaint the whole (closed, hole-free) figure flat white, then ink rings: no seams, nothing can poke out."""
    f = np.asarray(_bin(fig))
    hd = np.asarray(_bin(head))
    if not f.any():
        return img.convert("RGB")
    closed = _shift_max(_shift_max(f, close, np.maximum), close, np.minimum)
    closed = _fill_holes(np.maximum(closed, f))
    out = np.asarray(img.convert("RGB")).astype(np.float32)
    fill = Image.fromarray(closed).filter(ImageFilter.GaussianBlur(0.6))
    k = np.asarray(fill).astype(np.float32)[..., None] / 255
    out = out * (1 - k) + np.array(WHITE, np.float32) * k
    head_ring = (_shift_max(hd, width, np.maximum).astype(np.int16) - hd) * (closed > 0)
    ys = np.nonzero(hd)[0]
    if len(ys):                                   # inner head line only on the upper half (back of the head over
        head_ring[int(ys.mean()):] = 0            # the shoulders); under the chin it made a dark wedge
    ring = np.maximum(_shift_max(closed, width, np.maximum).astype(np.int16) - closed, head_ring)
    ring = Image.fromarray(ring.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    k = np.asarray(ring).astype(np.float32)[..., None] / 255
    out = out * (1 - k) + np.array(INK, np.float32) * k
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _one(args):
    f, d = args
    k, raw = f.stem, d / "raw" / f.name
    if not raw.exists():
        f.replace(raw)
    fig, head = d / "masks" / f"fig_{k}.png", d / "masks" / f"head_{k}.png"
    img = Image.open(raw)
    if fig.exists():
        img = frame(img, Image.open(fig), Image.open(head))
    img.convert("RGB").save(f)


def main(d: Path, width: int = 5) -> None:
    from concurrent.futures import ProcessPoolExecutor
    (d / "raw").mkdir(exist_ok=True)
    names = {p.name for p in d.glob("[0-9][0-9][0-9][0-9].png")} | {p.name for p in (d / "raw").glob("*.png")}
    jobs = [(d / n, d) for n in sorted(names)]
    with ProcessPoolExecutor(4) as ex:
        list(ex.map(_one, jobs, chunksize=8))
    print(len(jobs), "frames outlined")


if __name__ == "__main__":
    main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 5)
