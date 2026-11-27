"""Cutout ("перекладка") character: drawn parts in the style of the approved model sheet, rigged on mocap bones.

The parts come from two AI-drawn sheets with transparent backgrounds (projects/_assets/character_ref, git-ignored,
recorded in the episode credits log): parts_sheet.png (coat body, sleeves, hands, legs, shoe, coat tails) and
heads_sheet.png (8 side-profile heads with expressions). `extract()` cuts them into single PNGs and measures the
anchor points (joint ends of every limb piece); `draw()` places them on a pose as SVG <image> elements, each piece
stretched along its bone (thickness fixed by the character's scale), so the look is the sheet's and the motion is
the capture's.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "projects" / "_assets" / "character_ref"
PARTS = REF / "parts"

# boxes on the 2688x1520 sheets (x0, y0, x1, y1), found by eye on the previews; refined to the alpha bbox
SHEET_BOXES = {
    "coat": (90, 90, 590, 1160),
    "upper": (650, 210, 920, 840),
    "fore": (970, 330, 1210, 820),
    "fist": (1290, 280, 1530, 500),
    "hand": (1290, 560, 1530, 790),
    "thigh": (1660, 190, 1810, 830),
    "shin": (1930, 310, 2070, 760),
    "shoe": (2170, 470, 2560, 660),
    "tail1": (570, 950, 1600, 1440),
    "tail2": (1700, 940, 2540, 1420),
}
HEADS = ["neutral", "determined", "unimpressed", "surprised", "worried", "smile", "wince", "shout"]


def _bbox(a: np.ndarray, thr: int = 20) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(a > thr)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _stick_ends(alpha: np.ndarray) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Joint points of a rounded stick piece: centres of its top and bottom caps (inset by half the width)."""
    m = alpha > 128
    ys = np.nonzero(m.any(1))[0]
    widths = m.sum(1)[ys]
    w = float(np.median(widths))
    y0, y1 = ys.min(), ys.max()

    def cx(y):
        row = np.nonzero(m[int(y)])[0]
        return float(row.mean())
    top = (cx(y0 + w * 0.5), y0 + w * 0.5)
    bot = (cx(y1 - w * 0.5), y1 - w * 0.5)
    return top, bot, w


def _darken(img: Image.Image, white=(200, 198, 192), black=(46, 48, 56)) -> Image.Image:
    """Far-side copy: whites to light grey, blacks to the far-limb grey (keeps alpha)."""
    a = np.asarray(img.convert("RGBA")).astype(np.float32)
    lum = a[..., :3].mean(-1, keepdims=True) / 255.0
    rgb = np.array(black, np.float32) * (1 - lum) + np.array(white, np.float32) * lum
    keep_orange = (a[..., 0] - a[..., 2] > 60)[..., None]
    rgb = np.where(keep_orange, a[..., :3] * 0.8, rgb)
    return Image.fromarray(np.concatenate([rgb, a[..., 3:]], -1).clip(0, 255).astype(np.uint8))


def extract() -> dict:
    """Cut the sheets into parts/*.png and write parts/parts.json with anchors (pixels in each part image)."""
    PARTS.mkdir(parents=True, exist_ok=True)
    sheet = Image.open(REF / "parts_sheet.png").convert("RGBA")
    A = np.asarray(sheet)[..., 3]
    meta: dict = {}
    for name, (x0, y0, x1, y1) in SHEET_BOXES.items():
        bx0, by0, bx1, by1 = _bbox(A[y0:y1, x0:x1])
        pad = 4
        box = (x0 + bx0 - pad, y0 + by0 - pad, x0 + bx1 + pad, y0 + by1 + pad)
        part = sheet.crop(box)
        part.save(PARTS / f"{name}.png")
        _darken(part).save(PARTS / f"{name}_far.png")
        al = np.asarray(part)[..., 3]
        w, h = part.size
        m = {"w": w, "h": h}
        if name in ("upper", "fore", "thigh", "shin"):
            top, bot, width = _stick_ends(al)
            m.update(a=top, b=bot, width=width)
        elif name in ("fist", "hand"):
            m.update(c=(w / 2, h / 2), r=min(w, h) / 2)
        elif name == "shoe":
            rows = np.nonzero((al > 128).any(1))[0]
            m.update(heel=(w * 0.16, rows.max() - h * 0.18), tip=(w * 0.9, rows.max() - h * 0.18),
                     ankle=(w * 0.17, rows.min() + h * 0.25))
        elif name == "coat":
            mm = al > 128
            rows = np.nonzero(mm.any(1))[0]
            top_row = rows.min()
            band = mm[top_row:top_row + int(h * 0.04)].any(0)
            xs = np.nonzero(band)[0]
            m.update(top=(float(xs.mean()), float(top_row)), hem=float(rows.max()),
                     left=float(np.nonzero(mm.any(0))[0].min()), right=float(np.nonzero(mm.any(0))[0].max()))
        elif name.startswith("tail"):
            mm = al > 128
            cols = np.nonzero(mm.any(0))[0]
            xr = cols.max()                                   # root = right end (attached to the coat)
            ys = np.nonzero(mm[:, max(0, xr - int(w * 0.06)):xr + 1].any(1))[0]
            m.update(root=(float(xr - w * 0.04), float(ys.mean())))
        meta[name] = m
    heads = Image.open(REF / "heads_sheet.png").convert("RGBA")
    HA = np.asarray(heads)[..., 3]
    W, H = heads.size
    for k, name in enumerate(HEADS):
        cx0, cy0 = (k % 4) * W // 4, (k // 4) * H // 2
        bx0, by0, bx1, by1 = _bbox(HA[cy0:cy0 + H // 2, cx0:cx0 + W // 4])
        box = (cx0 + bx0 - 3, cy0 + by0 - 3, cx0 + bx1 + 3, cy0 + by1 + 3)
        hd = heads.crop(box)
        hd.save(PARTS / f"head_{name}.png")
        w, h = hd.size
        meta[f"head_{name}"] = {"w": w, "h": h, "c": (w / 2, h / 2), "r": min(w, h) / 2 - 3}
    (PARTS / "parts.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


@lru_cache(maxsize=1)
def parts() -> dict:
    f = PARTS / "parts.json"
    if not f.is_file():
        return extract()
    return json.loads(f.read_text(encoding="utf-8"))


def available() -> bool:
    return (REF / "parts_sheet.png").is_file() and (REF / "heads_sheet.png").is_file()


# ---------------------------------------------------------------- placing parts

def _rot(t: float) -> tuple[float, float, float, float]:
    c, s_ = math.cos(t), math.sin(t)
    return c, -s_, s_, c                     # [[a, b], [c, d]] row-major


def _mul(m, n):
    a, b, c, d = m
    e, f, g, h = n
    return a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h


def _img(name: str, M, anchor, at, op: float = 1.0) -> str:
    """<image> of a part with 2x2 matrix M (row-major) taking image point `anchor` to world point `at`."""
    m = parts()[name.replace("_far", "")]
    a, b, c, d = M
    e = at[0] - (a * anchor[0] + b * anchor[1])
    f = at[1] - (c * anchor[0] + d * anchor[1])
    o = f' opacity="{op:.2f}"' if op < 1 else ""
    # SVG matrix(a b c d e f) maps x' = a x + c y + e, y' = b x + d y + f
    return (f'<image href="{name}.png" width="{m["w"]}" height="{m["h"]}" '
            f'transform="matrix({a:.5f},{c:.5f},{b:.5f},{d:.5f},{e:.2f},{f:.2f})"{o}/>')


def _phi(vx: float, vy: float) -> float:
    """Angle of a vector measured from +y (down the screen) toward +x."""
    return math.atan2(vx, vy)


def _stick(name: str, A, B, k: float) -> str:
    """Limb piece from joint A to joint B: the piece's own joint points land on A and B, its thickness is k x image."""
    m = parts()[name.replace("_far", "")]
    (ax, ay), (bx, by) = m["a"], m["b"]
    L_img = math.hypot(bx - ax, by - ay) or 1.0
    L = math.hypot(B[0] - A[0], B[1] - A[1]) or 1e-3
    to_y = _rot(_phi(bx - ax, by - ay))                          # image axis -> +y
    to_w = _rot(-_phi(B[0] - A[0], B[1] - A[1]))                 # +y -> world bone
    M = _mul(to_w, _mul((k, 0.0, 0.0, L / L_img), to_y))
    return _img(name, M, (ax, ay), A)


def _rigid(name: str, anchor, at, tilt: float, k: float, flip: bool) -> str:
    """Rigid piece (coat, head, hand, tail): scale k, mirrored when facing left, tilted by `tilt` (rad, + = clockwise)."""
    M = _mul(_rot(tilt), (-k if flip else k, 0.0, 0.0, k))
    return _img(name, M, anchor, at)


COAT_LEN = 0.62          # coat height (collar top to hem) x body height h
HEAD_R = 0.150           # head radius x h


def draw(P: dict, h: float, flip: bool, expr: str = "neutral", speed: float = 0.0, t: float = 0.0) -> str:
    """The cutout character on screen joints P (rig.to_screen of a styled pose)."""
    pm = parts()
    s = -1 if flip else 1
    coat = pm["coat"]
    k = COAT_LEN * h / (coat["hem"] - coat["top"][1])          # px per sheet px (the sheet has one scale)
    (nx, ny), (hx, hy) = P["neck"], P["hipC"]
    ux, uy = hx - nx, hy - ny
    Ls = math.hypot(ux, uy) or 1.0
    ux, uy = ux / Ls, uy / Ls                                   # spine direction (down)
    tilt = -_phi(ux, uy)                                        # rotation of the upright pieces
    top = (nx - ux * h * 0.02, ny - uy * h * 0.02)              # collar top

    def shoulder(side: str):
        x, y = top[0] + ux * h * 0.07, top[1] + uy * h * 0.07
        ex, ey = P["elb" + side]
        L = math.hypot(ex - x, ey - y) or 1.0
        g = 0.055 if side == "R" else 0.04
        return x + (ex - x) / L * h * g, y + (ey - y) / L * h * g * 0.5

    def limb(side: str, far: bool) -> str:
        suf = "_far" if far else ""
        sh, el, wr = shoulder(side), P["elb" + side], P["wrist" + side]
        hand = "fist" if speed > 0.3 else "hand"
        return (_stick("upper" + suf, sh, el, k) + _stick("fore" + suf, el, wr, k)
                + _rigid(hand + suf, tuple(pm[hand]["c"]), wr, tilt, k, flip))

    def leg(side: str, far: bool) -> str:
        suf = "_far" if far else ""
        hip, kn, an = P["hipC"], P["knee" + side], P["ankle" + side]
        heel, tip = P["heel" + side], P["tip" + side]
        sm = pm["shoe"]
        (hx_, hy_), (tx_, ty_) = sm["heel"], sm["tip"]
        ivx = (tx_ - hx_) * (-1 if flip else 1)
        th = math.atan2(tip[1] - heel[1], tip[0] - heel[0]) - math.atan2(ty_ - hy_, ivx)
        M = _mul(_rot(th), (-k if flip else k, 0.0, 0.0, k))
        shoe = _img("shoe" + suf, M, (hx_, hy_), heel)
        return _stick("thigh" + suf, hip, kn, k) + _stick("shin" + suf, kn, an, k) + shoe

    out = [limb("L", True), leg("L", True)]
    if speed > 0.2:                                              # the coat tail streaming behind, fluttering
        tail = "tail1" if math.sin(t * 9) > 0 else "tail2"
        tm = pm[tail]
        back = (coat["top"][0] - coat["left"]) * k * 0.8
        root = (top[0] + ux * h * 0.30 - s * back, top[1] + uy * h * 0.30)
        wob = math.sin(t * 13) * 0.07
        kk = k * (0.35 + 0.3 * min(1.0, speed))
        M = _mul(_rot(tilt * 0.5 + wob * s), ((-kk if flip else kk), 0.0, 0.0, k * (0.9 + 0.1 * math.sin(t * 11))))
        out.append(_img(tail, M, tuple(tm["root"]), root))
    out.append(leg("R", False))
    out.append(_rigid("coat", tuple(coat["top"]), top, tilt, k, flip))
    out.append(limb("R", False))
    name = f"head_{expr}" if f"head_{expr}" in pm else "head_neutral"
    hm = pm[name]
    kh = HEAD_R * h / hm["r"]
    hc = (top[0] - ux * HEAD_R * h * 0.82, top[1] - uy * HEAD_R * h * 0.82)
    out.append(_rigid(name, tuple(hm["c"]), hc, tilt * 0.6, kh, flip))
    return "".join(out)
