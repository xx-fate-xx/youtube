"""Sprite animation for the hero: the drawn frames of the approved model sheets played back like hand-drawn animation.

The walk (8 frames) and run (6 frames) come straight from the reference sheets in projects/_assets/character_ref
(grey background keyed out); poses (stand, look up, catch, reach, carry, brace, land, point) from a pose sheet
drawn with the same references. Every frame is measured once: ground line (lowest opaque row), body centre (centre
of the white coat) and height, so frames line up on the ground and the character can be scaled to any size.
Cached in parts/sprites.json.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from PIL import Image

from .cutout import PARTS, REF

ANIM_FPS = 12                    # drawn frames per second at cadence 1 (animation "on twos" at 24)
SHEETS = {
    # name: (file, row box (x0, y0, x1, y1) on the full-size sheet or None, keyed grey background?)
    "walk": ("walk_sheet.png", None, True),
    "run": ("run_turnaround.png", (0, 0, 2688, 600), True),
    "pose": ("pose_sheet.png", None, False),
}
POSES = ["stand", "look_up", "catch", "reach", "carry", "brace", "land", "point"]


def _key_grey(img: Image.Image) -> Image.Image:
    """Grey background -> transparent, soft edge (the coat is white and the lines black, both far from the grey)."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    corners = np.concatenate([a[:20, :20].reshape(-1, 3), a[-20:, -20:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    d = np.sqrt(((a - bg) ** 2).sum(-1))
    alpha = np.clip((d - 14) / 26, 0, 1)
    return Image.fromarray(np.dstack([a, alpha * 255]).astype(np.uint8), "RGBA")


def _columns(alpha: np.ndarray, min_gap: int = 12, min_w: int = 60) -> list[tuple[int, int]]:
    """x-ranges of figures separated by empty columns."""
    occ = (alpha > 40).sum(0) > 2
    out, x, n = [], 0, len(occ)
    while x < n:
        if occ[x]:
            x0 = x
            gap = 0
            while x < n and gap < min_gap:
                gap = 0 if occ[x] else gap + 1
                x += 1
            if x - gap - x0 >= min_w:
                out.append((x0, x - gap))
        else:
            x += 1
    return out


def slice_all() -> dict:
    meta: dict = {}
    for name, (fname, box, key) in SHEETS.items():
        p = REF / fname
        if not p.is_file():
            continue
        img = Image.open(p).convert("RGBA")
        if box:
            img = img.crop(box)
        if key:
            img = _key_grey(img)
        A = np.asarray(img)[..., 3]
        frames = []
        for k, (x0, x1) in enumerate(_columns(A)):
            ys = np.nonzero((A[:, x0:x1] > 40).any(1))[0]
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            fr = img.crop((x0 - 4, y0 - 4, x1 + 4, y1 + 4))
            fn = f"spr_{name}_{k}.png"
            fr.save(PARTS / fn)
            a = np.asarray(fr).astype(np.float32)
            white = (a[..., :3].min(-1) > 200) & (a[..., 3] > 200)
            ys_w, xs_w = np.nonzero(white)
            al = a[..., 3] > 128
            rows = np.nonzero(al.any(1))[0]
            dark = (a[..., :3].max(-1) < 70) & al
            top = int(rows.min())
            head_rows = dark[top:top + int((rows.max() - top) * 0.3)]
            head_d = float(np.percentile(head_rows.sum(1), 90)) if len(head_rows) else 1.0
            frames.append({"file": fn, "w": fr.width, "h": fr.height, "ground": float(rows.max()),
                           "top": float(top), "cx": float(xs_w.mean()) if len(xs_w) else fr.width / 2,
                           "y0": float(y0 - 4), "head_d": head_d})
        base = max(f["y0"] + f["ground"] for f in frames)          # the sheet's ground line (keeps flight phases)
        hd = float(np.median([f["head_d"] for f in frames]))
        for f in frames:
            f["lift"] = base - (f["y0"] + f["ground"])
            f["sheet_head_d"] = hd
        meta[name] = frames
    PARTS.mkdir(parents=True, exist_ok=True)
    (PARTS / "sprites.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


@lru_cache(maxsize=1)
def sprites() -> dict:
    f = PARTS / "sprites.json"
    if not f.is_file():
        return slice_all()
    return json.loads(f.read_text(encoding="utf-8"))


def available() -> bool:
    s = sprites()
    return bool(s.get("walk")) and bool(s.get("run"))


def frame_for(kind: str, t_in: float, cadence: float = 1.0) -> dict:
    """The drawn frame for an action `kind` that started t_in seconds ago."""
    s = sprites()
    if kind in ("walk", "walk_b", "run"):
        cyc = s["run" if kind == "run" else "walk"]
        return cyc[int(t_in * ANIM_FPS * cadence) % len(cyc)]
    poses = s.get("pose") or []
    if kind in POSES and len(poses) == len(POSES):
        return poses[POSES.index(kind)]
    return poses[0] if poses else s["walk"][0]


HEAD_D = 0.30                    # drawn head diameter x actor height h (matches the cutout parts)


def draw(fr: dict, x: float, ground: float, h: float, flip: bool, amber: bool = False, op: float = 1.0) -> str:
    """One frame on the ground at x; scaled by the sheet's head size so every sheet draws the hero the same size;
    frames from a jump/flight phase keep their height above the sheet's ground line."""
    k = h * HEAD_D / fr["sheet_head_d"]
    fx = -k if flip else k
    e = x - fx * fr["cx"]
    f = ground - k * (fr["ground"] + fr["lift"])
    flt = ' filter="url(#amberize)"' if amber else ""
    o = f' opacity="{op:.2f}"' if op < 1 else ""
    return (f'<image href="{fr["file"]}" width="{fr["w"]}" height="{fr["h"]}" '
            f'transform="matrix({fx:.5f},0,0,{k:.5f},{e:.2f},{f:.2f})"{flt}{o}/>')


def stride_speed(kind: str) -> float:
    """Travel speed (body heights per second at cadence 1) that keeps the planted foot still: one cycle covers two
    steps; a step is the distance between the feet in the widest frame of the cycle."""
    s = sprites()
    cyc = s["run" if kind == "run" else "walk"]
    hpx = cyc[0]["sheet_head_d"] / HEAD_D                    # sheet px per body height
    widest = max(f["w"] for f in cyc)
    step = widest * 0.62                                     # feet span ~ most of the widest frame
    return 2 * step / hpx * ANIM_FPS / len(cyc)
