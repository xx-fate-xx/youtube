"""2D stage renderer for Ink Mindset skits (no Blender): painted plate with parallax, the scrolling ink road,
props, the stick figures, contact shadows and foreground props, straight to 60 fps frames + MP4.

The Rift rendered its world in Blender through a level orthographic camera - i.e. a flat side view. This draws the
same picture directly: world units are head radii R (pose2d), x forward, y up, the ground at y = 0.

    half = Half(dur, figures={"hero": frames}, cam=..., props=...)
    render_half(half, out_dir)          -> out_dir/NNNN.png + out_dir.mp4

Frames are composed in the main process as plain data (plate offset, ground offset, one SVG overlay string per
frame) and drawn by worker processes (PIL for the raster plate/ground, resvg for the vectors).
"""

from __future__ import annotations

import io
import math
import os
import subprocess
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageEnhance

from studio.ink3d import stick2d
from studio.ink3d.pose2d import to_px

ROOT = Path(__file__).resolve().parents[2]
BG = ROOT / "projects" / "ink_proto3d" / "bg"
W, H = 1200, 1066
FPS = 60
PPM = 64.0                 # pixels per head radius (the Rift's ortho framing: head radius ~64 px)
CAM_Y = 4.6                # world height (R) at the frame centre: the ground sits at ~78 % of the height
PARALLAX = 0.07            # the painted plate drifts this fraction of the camera travel
R_M = 0.3                  # one head radius in metres (ground texture scale, shadow fade)
INK, STONE, VERM, PAPER = "#16140F", "#575248", "#D9412B", "#F4EDE0"


@dataclass
class Half:
    """One half of a skit. figures: name -> world frames (R) at FPS (None = hidden). cam(i) -> (x, y, zoom).
    props(i, t, P, s) -> (back_svg, front_svg) with P(x, y) -> (px, py) and s = px per R.
    plate / plate2: names in projects/ink_proto3d/bg (the *_wide.png versions are used);
    bright(t) -> 0..1.2 plate brightness; mix(t) -> 0..1 cross-fade to plate2; ground: x ranges with a road;
    tone(t) -> "ink" | "light" road marks; cover: name -> weights per frame (arms crossed over the face)."""
    dur: float
    figures: dict
    cam: Callable[[int], tuple] = lambda i: (0.0, CAM_Y, 1.0)
    props: Callable | None = None
    plate: str = "plate_calm"
    plate2: str | None = None
    bright: Callable[[float], float] = lambda t: 1.0
    mix: Callable[[float], float] = lambda t: 0.0
    ground: list = field(default_factory=lambda: [(-1e9, 1e9)])
    tone: Callable[[float], str] = lambda t: "ink"
    styles: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(round(self.dur * FPS)) + 1


# ---------------------------------------------------------------- per-frame data (main process)

def _frame_data(h: Half, i: int, sides: dict, x0: float) -> dict:
    t = i / FPS
    cx, cy, z = h.cam(i)
    s = PPM * z
    ox, oy = W / 2 - cx * s, H / 2 + cy * s                      # screen position of the world origin

    def P(x, y):
        return ox + x * s, oy - y * s
    back, front = h.props(i, t, P, s) if h.props else ("", "")
    parts = ['<defs><filter id="soft" x="-50%" y="-200%" width="200%" height="500%">'
             '<feGaussianBlur stdDeviation="6"/></filter>'
             '<filter id="glow" x="-100%" y="-100%" width="300%" height="300%">'
             '<feGaussianBlur stdDeviation="14"/></filter></defs>', back]
    figs = {}
    for name, fr in h.figures.items():
        J = fr[i] if i < len(fr) else None
        if J is None:
            continue
        d = to_px(J, ox, oy, s)
        figs[name] = (J, d)
        pel = J["pelvis"][0]
        if any(a <= pel <= b for a, b in h.ground):              # soft contact shadow on the road
            low = min(J[k][1] for k in ("ankleL", "ankleR", "toeL", "toeR"))
            parts.append(stick2d.shadow_svg(d, [d["pelvis"][0], oy, max(0.0, (low - 0.3) * R_M)]))
    for name in sorted(figs, key=lambda n: n == "hero"):         # shadows (giants) behind, the hero on top
        J, d = figs[name]
        fill, line = stick2d.STYLES.get(h.styles.get(name, name.split("_")[0]), stick2d.STYLES["hero"])
        parts.append(stick2d.svg(d, W, H, sides[name][i], fill, line, wrap=False, cover=J.get("_cover", 0.0)))
    parts.append(front)
    road = [(max(-1e5, P(a, 0)[0]), min(1e5, P(b, 0)[0])) for a, b in h.ground]
    return {"plate": h.plate, "plate2": h.plate2, "mix": float(h.mix(t)), "bright": float(h.bright(t)),
            "left": (cx - x0) * PPM * PARALLAX, "road_off": ox, "road_y": oy, "road": road, "tone": h.tone(t),
            "zoom": z, "svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{"".join(parts)}</svg>'}


# ---------------------------------------------------------------- drawing (workers)

@lru_cache(maxsize=8)
def _plate(name: str) -> Image.Image:
    p = BG / f"{name}_wide.png"
    if not p.is_file():
        p = BG / f"{name}.png"
    im = Image.open(p).convert("RGB")
    if im.height != H:
        im = im.resize((round(im.width * H / im.height), H), Image.LANCZOS)
    return im


@lru_cache(maxsize=4)
def _road_tile(tone: str, zoom: float) -> Image.Image:
    from studio.ink3d import ground
    p = BG / f"ground_{tone}.png"
    im = Image.open(p).convert("RGBA")
    k = PPM * zoom / (R_M * ground.PX_PER_M)                     # texture px -> screen px
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def _plate_view(name: str, left: float) -> Image.Image:
    im = _plate(name)
    wide = im.width >= 2 * W
    start = (im.width - W) / 2 - (im.width / 4 if wide else 0) + left    # wide = [original | mirror]
    x = int(round(start)) % im.width
    if x + W <= im.width:
        return im.crop((x, 0, x + W, H))
    out = Image.new("RGB", (W, H))
    out.paste(im.crop((x, 0, im.width, H)), (0, 0))
    out.paste(im.crop((0, 0, W - (im.width - x), H)), (im.width - x, 0))
    return out


def _draw(args) -> None:
    import resvg_py
    path, fd = args
    from studio.ink3d import ground
    base = _plate_view(fd["plate"], fd["left"])
    if fd["plate2"] and fd["mix"] > 0:
        base = Image.blend(base, _plate_view(fd["plate2"], fd["left"]), min(1.0, fd["mix"]))
    if abs(fd["bright"] - 1.0) > 1e-3:
        base = ImageEnhance.Brightness(base).enhance(fd["bright"])
    base = base.convert("RGBA")
    tile = _road_tile(fd["tone"], round(fd["zoom"], 3))
    top = int(round(fd["road_y"] - tile.height * ground.TOP_M / (ground.TOP_M + ground.DEPTH_M)))   # line on y = 0
    road = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x = int(math.floor(fd["road_off"])) % tile.width - tile.width
    while x < W:
        road.alpha_composite(tile, (max(0, x), max(0, top)), (max(0, -x), max(0, -top)))
        x += tile.width
    mask = Image.new("L", (W, H), 0)                              # the road only where there is ground
    for a, b in fd["road"]:
        a, b = int(max(0, a)), int(min(W, b))
        if b > a:
            mask.paste(255, (a, 0, b, H))
    base.paste(road, (0, 0), Image.composite(road, Image.new("RGBA", (W, H), (0, 0, 0, 0)), mask))
    fg = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=fd["svg"])))).convert("RGBA")
    base.alpha_composite(fg)
    base.convert("RGB").save(path)


def render_half(h: Half, out: Path, workers: int = 2) -> Path:
    """All frames of a half -> out/NNNN.png and out.mp4 (FPS)."""
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.png"):
        p.unlink()
    sides = {}
    for name, fr in h.figures.items():
        seen = [to_px(J, 0, 0, PPM) for J in fr if J is not None]
        ss = stick2d.near_sides(seen) if seen else []
        it = iter(ss)
        sides[name] = [next(it) if J is not None else "R" for J in fr]
    x0 = h.cam(0)[0]
    jobs = [(out / f"{i + 1:04d}.png", _frame_data(h, i, sides, x0)) for i in range(h.n)]
    with ProcessPoolExecutor(workers, initializer=_low_priority) as ex:
        list(ex.map(_draw, jobs, chunksize=8))
    mp4 = out.with_suffix(".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(out / "%04d.png"), "-c:v",
                    "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    return mp4


def _low_priority() -> None:
    try:
        import psutil
        psutil.Process(os.getpid()).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:  # noqa: BLE001 - best effort
        pass


# ---------------------------------------------------------------- SVG prop helpers (screen space via P)

def rect(P, x0, y0, x1, y1, fill=INK, rot=0.0, opacity=1.0) -> str:
    (a, b), (c, d) = P(x0, y1), P(x1, y0)
    cx, cy = (a + c) / 2, (b + d) / 2
    tr = f' transform="rotate({rot:.1f} {cx:.1f} {cy:.1f})"' if rot else ""
    return (f'<rect x="{a:.1f}" y="{b:.1f}" width="{c - a:.1f}" height="{d - b:.1f}" fill="{fill}" '
            f'opacity="{opacity:.3f}"{tr}/>')


def disc(P, s, x, y, r, fill=VERM, opacity=1.0, glow=False) -> str:
    px, py = P(x, y)
    f = ' filter="url(#glow)"' if glow else ""
    return f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r * s:.1f}" fill="{fill}" opacity="{opacity:.3f}"{f}/>'


def ring(P, s, x, y, r, width=0.18, stroke=INK, opacity=1.0) -> str:
    px, py = P(x, y)
    return (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r * s:.1f}" fill="none" stroke="{stroke}" '
            f'stroke-width="{width * s:.1f}" opacity="{opacity:.3f}"/>')


def poly(P, pts, fill=INK, opacity=1.0) -> str:
    q = " ".join(f"{a:.1f},{b:.1f}" for a, b in (P(x, y) for x, y in pts))
    return f'<polygon points="{q}" fill="{fill}" opacity="{opacity:.3f}"/>'


def line(P, s, pts, width=0.08, stroke=INK, opacity=1.0, cap="round") -> str:
    q = " L".join(f"{a:.1f},{b:.1f}" for a, b in (P(x, y) for x, y in pts))
    return (f'<path d="M{q}" fill="none" stroke="{stroke}" stroke-width="{width * s:.1f}" '
            f'stroke-linecap="{cap}" stroke-linejoin="round" opacity="{opacity:.3f}"/>')


def ease(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def keys(pairs: list[tuple[float, float]]) -> Callable[[float], float]:
    """Piecewise smooth keyframes [(t, v)] -> f(t)."""
    def f(t):
        if t <= pairs[0][0]:
            return pairs[0][1]
        for (a, va), (b, vb) in zip(pairs, pairs[1:], strict=False):
            if a <= t <= b:
                return va + (vb - va) * ease((t - a) / max(1e-6, b - a))
        return pairs[-1][1]
    return f


def sun(P, s, x, y, r, horizon=0.47, fill=VERM, opacity=0.95, cid="sunclip") -> str:
    """A sun disc hidden below the painted horizon (the plate's hills sit at ~47 % of the frame height, fixed on
    screen): it rises from behind the far hills, never from under the road or behind the figures."""
    hy = horizon * H
    clip = f'<defs><clipPath id="{cid}"><rect x="-99999" y="-99999" width="199999" height="{hy + 99999:.1f}"/></clipPath></defs>'
    px, py = P(x, y)
    return (clip + f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r * s:.1f}" fill="{fill}" opacity="{opacity:.3f}" '
            f'clip-path="url(#{cid})"/>')
