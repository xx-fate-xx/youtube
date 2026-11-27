"""Layout check for What If motion comics: finds on-screen text that collides with other text, with drawings,
with the characters, with the burned-caption band (Shorts) or with the frame edge.

    python -m studio.whatif.layout_check episodes/<slug> [--step 0.25]

Every screen-space item active at a sample time (Comic.text fns, freeze items) is rendered; each <text> element is
rendered on its own (at half resolution) to get its pixel mask, the rest of the item (arrows, drawings) forms the
item's drawing mask. Only bright pixels count (white/amber/chalk), so scrims and board backgrounds are ignored.
Characters are their sprite boxes on screen. Consecutive hits of the same pair are merged into time ranges.
"""

from __future__ import annotations

import argparse
import re
from functools import lru_cache

import numpy as np

from ..pipeline import episode as em
from . import comic, render
from .scene import _svg

S = 0.5                                   # render scale
TEXT_RE = re.compile(r"<text\b[^>]*>.*?</text>", re.S)
CAPTION_BAND = (0.60, 0.68)               # Shorts: burned captions (fraction of the height)
COVER_RE = re.compile(r'<rect width="100%" height="100%" fill="#(?:14201C|050507)"(?: opacity="([0-9.]+)")?')


def _covered(svgs: list[str]) -> bool:
    """A full-screen chalkboard or black card hides the picture (and its characters)."""
    for svg in svgs:
        for m in COVER_RE.finditer(svg):
            if m.group(1) is None or float(m.group(1)) > 0.8:
                return True
    return False


@lru_cache(maxsize=4096)
def _mask(svg: str, w: int, h: int) -> np.ndarray:
    if not svg.strip():
        return np.zeros((int(h * S), int(w * S)), bool)
    im = _svg(f'<g transform="scale({S})">{svg}</g>', int(w * S), int(h * S))
    a = np.asarray(im).astype(np.float32)
    lum = a[..., :3].mean(-1)
    return (a[..., 3] > 128) & (lum > 120)


def _label(el: str) -> str:
    t = re.sub(r"<[^>]+>", "", el)
    return (t[:28] + "…") if len(t) > 28 else t


def items_at(c: comic.Comic, i: int, size: tuple[int, int]) -> list[tuple[str, str]]:
    """(source, svg) of every screen item active in frame i (freeze items pinned like in the render)."""
    t = i / comic.FPS
    out = []
    for fa, fb, items in c.freezes:
        a0, b0 = c.T(fa), c.T(fb)
        if a0 <= t < b0:
            out += [(f"freeze@{a0:.1f}", comic.pinned(c, i, size, a0, it({}, t - a0))) for it in items]
    for ta, tb, fn in c.texts:
        a0, b0 = c.T(ta), c.T(tb)
        if a0 <= t < b0:
            out.append((f"text@{a0:.1f}", fn(t - a0, t)))
    return out


def check_frame(c: comic.Comic, i: int, size: tuple[int, int], vertical: bool) -> list[tuple[str, str]]:
    W, H = size
    texts, draws = [], []
    active = items_at(c, i, size)
    hidden = _covered([svg for _src, svg in active])
    for src, svg in active:
        els = TEXT_RE.findall(svg)
        for el in els:
            m = _mask(_only_text(svg, el), W, H)
            if m.any():
                texts.append((f"{src}:{_label(el)}", m, src))
        rest = TEXT_RE.sub("", svg)
        dm = _mask(rest, W, H)
        if dm.any():
            draws.append((src, dm))
    issues = []
    grow = _dilate
    chars = [] if hidden else [(who, _char_mask(c, spec, W, H)) for who, _box, spec in comic.sprite_boxes(c, i, size)]
    if c.split and not hidden:                       # split screen: the halves' characters, shifted into place
        half, dx, dy = ((W, H // 2), 0, H // 2) if c.stack else ((W // 2, H), W // 2, 0)
        for k, sub in enumerate(c.split):
            sub.art = sub.art or c.art
            for who, _box, (spr, flip, left, top, sk) in comic.sprite_boxes(sub, i, half):
                spec = (spr, flip, left + k * dx, top + k * dy, sk)
                chars.append((f"{who}[{('TB' if c.stack else 'LR')[k]}]", _char_mask(sub, spec, W, H)))
    for a in range(len(texts)):
        na, ma, sa = texts[a]
        ga = grow(ma)
        for b in range(a + 1, len(texts)):
            nb, mb, _sb = texts[b]
            if na.split(":", 1)[1] == nb.split(":", 1)[1]:
                continue                                        # the same text twice (shadow copy)
            if (ga & mb).sum() > 20:
                issues.append(("text/text", f"{na}  ×  {nb}"))
        for sd, dm in draws:
            if (ma & dm).sum() > 40:
                issues.append(("text/drawing", f"{na}  ×  drawing of {sd}"))
        ys, xs = np.nonzero(ma)
        if xs.min() < 6 * S or xs.max() > (W - 6) * S or ys.min() < 4 * S:
            issues.append(("edge", na))
        if vertical:
            y0, y1 = CAPTION_BAND[0] * H * S, CAPTION_BAND[1] * H * S
            if ((ys > y0) & (ys < y1)).sum() > 30:
                issues.append(("captions", na))
        for who, cm in chars:
            if (ga & cm).sum() > 60:
                issues.append(("text/character", f"{na}  ×  {who}"))
    return issues


def _char_mask(c: comic.Comic, spec, W: int, H: int) -> np.ndarray:
    """Screen mask (half resolution) of one character's opaque pixels."""
    from PIL import Image
    spr, flip, left, top, k = spec
    im = comic._sprite(str(c.art), spr)[0].getchannel("A")
    w, h = max(1, int(im.width * k * S)), max(1, int(im.height * k * S))
    a = im.resize((w, h))
    if flip:
        a = a.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    canvas = Image.new("L", (int(W * S), int(H * S)), 0)
    canvas.paste(a, (int(left * S), int(top * S)))
    return np.asarray(canvas) > 100


def _only_text(svg: str, keep: str) -> str:
    """The item's svg with only the <text> element `keep`: other texts and drawing primitives are dropped, the
    wrapping groups (transforms) stay."""
    body = TEXT_RE.sub(lambda m: m.group(0) if m.group(0) == keep else "", svg)
    # drop drawing primitives but keep their groups (transforms)
    return re.sub(r"<(path|line|rect|ellipse|circle|polyline|polygon)\b[^>]*/>", "", body)


def _dilate(m: np.ndarray, r: int = 3) -> np.ndarray:
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def run(src: str, step: float = 0.25) -> list[tuple[float, float, str, str]]:
    em.use(src)
    size = em.ep().size
    vertical = em.ep().vertical
    durs, _ = render.durations(False)
    found: dict[tuple[str, str], list[float]] = {}
    t0 = 0.0
    for s in render.plan(size):
        if not isinstance(s, comic.Comic):
            continue
        s.art = render.library("art")
        n = s.layout(durs)
        tt = 0.0
        while tt < n:
            for kind, what in check_frame(s, int(tt * comic.FPS), size, vertical):
                found.setdefault((kind, what), []).append(t0 + tt)
            tt += step
        t0 += n
    out = []
    for (kind, what), ts in found.items():
        a = prev = ts[0]
        for x in ts[1:] + [1e9]:
            if x - prev > step * 1.5:
                out.append((a, prev, kind, what))
                a = x
            prev = x
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--step", type=float, default=0.25)
    a = ap.parse_args()
    res = run(a.episode, a.step)
    for t0, t1, kind, what in res:
        print(f"{t0:6.2f}-{t1:6.2f}  {kind:15s} {what}")
    print(f"{len(res)} issue(s)")


if __name__ == "__main__":
    main()
