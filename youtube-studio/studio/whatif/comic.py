"""Motion-comic scenes for the What If channel (format approved 2026-11-22).

Characters are expressive drawn poses (AI-drawn sheets in the style of the approved model sheet, sliced into
sprites by `slice_sheet`) snapped pose-to-pose over a painted plate, with cartoon techniques done in code:
squash/stretch "pop" on every pose change, smear trails, speed lines, whip-pan blur, impact flash, camera shake,
freeze frames with chalk, rewinds, a directed camera and kinetic text. Sound cues (SFX, music) are part of the scene.

    c = Comic(shots=(1, 5), plate="tower_plate")
    c.cast("hero", height=520)                              # px tall on the plate at street level
    c.cast("cleaner", height=505, persp=(316, 1362, 0.24))  # smaller higher up (seen from the street)
    c.key("cleaner", 0.0, "cleaner0", 2085, 316)            # snap to a pose at a place (feet / ground point)
    c.key("cleaner", 2.0, "cleaner2", 1915, 616, ang=-15, tween="ease")   # move there over the interval
    c.cam(0.0, 2120, 330, 1050)                             # camera centre and view width (plate px)
    c.freeze(c.at(1, 3.0), c.at(2), [svg items])            # world desaturates, chalk explains
    c.flash(c.at(2, 4.0)); c.shake(...); c.sfx(c.at(1, 1.3), "sfx_slip")

Times are seconds from the scene start or c.at(shot, offset) / c.end(offset) like scene.Seq. Art: projects/<slug>/art
(<plate>.png, optional <plate>_front.png drawn over the characters, sprites from sprites.json); sound:
projects/<slug>/sfx/<name>.mp3.
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import overlay
from .scene import At, Time, _svg

FPS = int(os.environ.get("COMIC_FPS", "30"))      # episode.yaml `fps` (render.run sets it)


# ---------------------------------------------------------------- art


def slice_sheet(sheet: Path, prefix: str, count: int, out_dir: Path) -> list[dict]:
    """Cut a transparent pose sheet (one row of figures) into <prefix>_<k>.png; returns their metadata."""
    from .sprites import _columns
    im = Image.open(sheet).convert("RGBA")
    A = np.asarray(im)[..., 3]
    cols = _columns(A, min_gap=10, min_w=40)
    while len(cols) < count:                       # merged neighbours: split at the emptiest column
        k = max(range(len(cols)), key=lambda i: cols[i][1] - cols[i][0])
        x0, x1 = cols[k]
        occ = (A[:, x0:x1] > 40).sum(0).astype(float)
        a, b = int((x1 - x0) * 0.3), int((x1 - x0) * 0.7)
        cut = x0 + a + int(np.argmin(occ[a:b]))
        cols[k:k + 1] = [(x0, cut), (cut, x1)]
    out = []
    for k, (x0, x1) in enumerate(cols[:count]):
        ys = np.nonzero((A[:, x0:x1] > 40).any(1))[0]
        fr = im.crop((x0 - 2, int(ys.min()) - 3, x1 + 2, int(ys.max()) + 4))
        fn = f"{prefix}_{k}.png"
        fr.save(out_dir / fn)
        rows = np.nonzero((np.asarray(fr)[..., 3] > 128).any(1))[0]
        out.append({"file": fn, "w": fr.width, "h": fr.height, "ground": int(rows.max())})
    meta_f = out_dir / "sprites.json"
    meta = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.is_file() else {}
    meta[prefix] = out
    meta_f.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


@lru_cache(maxsize=4)
def _meta(art: str) -> dict:
    f = Path(art) / "sprites.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


@lru_cache(maxsize=256)
def _sprite(art: str, name: str) -> tuple[Image.Image, int, int]:
    """name like 'hero3' -> (image, ground row, body height reference)."""
    prefix = name.rstrip("0123456789")
    k = int(name[len(prefix):])
    m = _meta(art)[prefix][k]
    return Image.open(Path(art) / m["file"]).convert("RGBA"), m["ground"], m["h"]


def _pxscale(art: str, name: str) -> float:
    """Sheet upscale factor of a sprite (sprites rebuilt from 4K sheets are drawn at their original size)."""
    prefix = name.rstrip("0123456789")
    k = int(name[len(prefix):])
    return float(_meta(art)[prefix][k].get("scale", 1.0))


V_EXTRA = 600                      # px of ground added under a plate for vertical (9:16) framing


def tall_plate(src: Path, extra: int = V_EXTRA, strip: int = 150) -> Image.Image:
    """A landscape plate with `extra` px of foreground ground below it (its bottom strip stretched and slightly
    darkened), so a 9:16 camera can put the characters' feet above the Shorts caption and UI band."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    out = Image.new("RGB", (w, h + extra))
    out.paste(im, (0, 0))
    s = np.asarray(im.crop((0, h - strip, w, h)).resize((w, strip + extra), Image.Resampling.BICUBIC))
    g = np.linspace(1.0, 0.72, s.shape[0])[:, None, None]
    out.paste(Image.fromarray((s.astype(np.float32) * g).astype(np.uint8)), (0, h - strip))
    return out


def extract_clip(src: Path, art: Path, name: str) -> Path:
    """Video plate: unpack an AI clip once into art/clip_<name>/NNNN.jpg (+ fps.txt) so render workers can read
    single frames. Use it in a scene with Comic.clip(at, name)."""
    d = Path(art) / f"clip_{name}"
    if not (d / "fps.txt").is_file():
        d.mkdir(parents=True, exist_ok=True)
        rate = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=r_frame_rate", "-of", "csv=p=0", str(src)], capture_output=True,
                              text=True, check=True).stdout.strip()
        a, _, b = rate.partition("/")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-q:v", "2", str(d / "%04d.jpg")], check=True)
        (d / "fps.txt").write_text(str(float(a) / float(b or 1)), encoding="utf-8")
    return d


@lru_cache(maxsize=64)
def _clip_frame(art: str, name: str, idx: int) -> Image.Image:
    d = Path(art) / f"clip_{name}"
    n = len(list(d.glob("*.jpg")))
    return Image.open(d / f"{min(max(idx, 0), n - 1) + 1:04d}.jpg").convert("RGBA")


def _clip_fps(art: str, name: str) -> float:
    return float((Path(art) / f"clip_{name}" / "fps.txt").read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def _plate(art: str, name: str) -> Image.Image:
    if name.startswith("@"):                                          # video plate: its first frame (sizes, checks)
        return _clip_frame(art, name[1:], 0)
    p = Path(art) / f"{name}.png"
    if not p.is_file() and name.endswith("_v") and (Path(art) / f"{name[:-2]}.png").is_file():
        tall_plate(Path(art) / f"{name[:-2]}.png").save(p)           # <plate>_v: built once, then reused
    if p.is_file():
        return Image.open(p).convert("RGBA")
    from .backdrop import _placeholder
    return _placeholder(name, (2688, 1520)).convert("RGBA")


@lru_cache(maxsize=8)
def _front(art: str, name: str) -> Image.Image | None:
    p = Path(art) / f"{name}_front.png"
    return Image.open(p).convert("RGBA") if p.is_file() else None


# ---------------------------------------------------------------- scene description

def ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


TWEENS: dict[str, Callable[[float], float]] = {
    "hold": lambda u: 0.0,
    "lin": lambda u: u,
    "ease": ease,
    "in": lambda u: u * u,                 # accelerate (falling)
    "out": lambda u: 1 - (1 - u) ** 2,     # decelerate (landing, skid)
    "snap": lambda u: 1 - (1 - u) ** 4,    # very fast start (dash)
}


@dataclass
class Key:
    t: Time
    sprite: str | None                     # None = hidden
    x: float
    y: float                               # ground point under the figure (plate px)
    ang: float = 0.0
    scale: float = 1.0                     # extra scale on top of the cast height (and perspective)
    tween: str = "hold"                    # how to get here from the previous key
    pop: bool = True                       # squash/stretch when the sprite changes
    smear: bool = False                    # smear trail while travelling into this key
    flip: bool = False
    fixed: bool = False                    # ignore the cast's perspective scale (scale is absolute)


@dataclass
class Cast:
    name: str
    height: float                          # body height at street level (plate px)
    ref: str | None = None                 # sprite whose drawn height == `height` (default: <name>0)
    persp: tuple[float, float, float] | None = None   # (y_far, y_near, scale_far): smaller higher up
    keys: list[Key] = field(default_factory=list)

    def k(self, y: float) -> float:
        if not self.persp:
            return 1.0
        y0, y1, f = self.persp
        u = max(0.0, min(1.0, (y - y0) / (y1 - y0)))
        return f + (1 - f) * u ** 0.8


@dataclass
class Comic:
    shots: tuple[int, int]
    plate: str
    art: Path | None = None
    casts: dict[str, Cast] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    cams: list = field(default_factory=list)          # (t, cx, cy, width)
    freezes: list = field(default_factory=list)       # (at, until, items) — items: (ctx, u) -> svg
    flashes: list = field(default_factory=list)       # (at, length)
    shakes: list = field(default_factory=list)        # (at, length, amp)
    whips: list = field(default_factory=list)         # (at, until)
    streak: list = field(default_factory=list)        # (at, until)
    rewinds: list = field(default_factory=list)       # (at, until)
    fronts: list = field(default_factory=list)        # (at, until) when <plate>_front.png covers the characters
    texts: list = field(default_factory=list)         # (at, until, fn(u, t) -> svg) screen space
    cues: list = field(default_factory=list)          # (at, file, volume, kind, duration or None)
    draws: list = field(default_factory=list)         # (at, until, fn(world_img, u, t), front)
    sheet_ref: dict = field(default_factory=dict)     # sprite prefix -> body height of a standing figure (sheet px)
    fade_out: float = 0.0
    shade: tuple[float, float] = (0.0, 0.0)          # (opacity, height px): darken the top band for legible chalk
    _t: dict = field(default_factory=dict)
    placeholder: bool = False
    plates: list = field(default_factory=list)        # (at, plate): hard cuts to another plate inside the comic
    clips: list = field(default_factory=list)         # (at, name, speed, offset): video plates (plate "@name")
    inverts: list = field(default_factory=list)       # (at, length): anime-style impact frames (colours inverted)
    split: tuple | None = None                        # (left Comic, right Comic): side-by-side halves; this comic
                                                      # adds the shared screen texts, flashes and all sound cues
    stack: bool = False                               # split halves stacked top/bottom (W x H/2 each) instead

    # compatibility with the render report (scene.Seq fields)
    @property
    def bg(self) -> str:
        return self.plate

    @property
    def actors(self) -> list:
        return list(self.casts)

    booms: list = field(default_factory=list)

    # ---- authoring
    def at(self, shot: int, off: float = 0.0) -> At:
        return At(shot, off)

    def end(self, off: float = 0.0) -> At:
        return At(None, off)

    def cast(self, name: str, height: float, ref: str | None = None,
             persp: tuple[float, float, float] | None = None) -> Cast:
        c = Cast(name, height, ref, persp)
        self.casts[name] = c
        self.order.append(name)
        return c

    def key(self, who: str, t: Time, sprite: str | None, x: float = 0.0, y: float = 0.0, **kw) -> None:
        self.casts[who].keys.append(Key(t, sprite, x, y, **kw))

    def hide(self, who: str, t: Time) -> None:
        self.casts[who].keys.append(Key(t, None, 0.0, 0.0))

    def cam(self, t: Time, cx: float, cy: float, width: float, tween: str = "ease") -> None:
        self.cams.append((t, cx, cy, width, tween))

    def freeze(self, at: Time, until: Time, items: list) -> None:
        self.freezes.append((at, until, items))

    def cut(self, at: Time, plate: str) -> None:
        """Hard cut to another plate (same size) from `at` on — montages inside one comic."""
        self.plates.append((at, plate))

    def clip(self, at: Time, name: str, speed: float = 1.0, offset: float = 0.0) -> None:
        """Hard cut to a video plate (an AI clip unpacked with extract_clip) from `at` on; it plays at `speed` from
        `offset` seconds into the clip and holds its last frame if the scene runs longer (avoid that)."""
        self.plates.append((at, f"@{name}"))
        self.clips.append((at, name, speed, offset))

    def clip_frame(self, art: str, name: str, t: float) -> Image.Image:
        start = [(a, sp, off) for a, nm, sp, off in self.clips if nm == name and self.T(a) <= t]
        a, sp, off = max(start, key=lambda x: self.T(x[0])) if start else (0.0, 1.0, 0.0)
        # + epsilon: t = i / fps minus a start time lands a hair under whole frames (2.9999999 -> 2), which shows one
        # plate frame twice and skips the next - a stutter on every other frame at 60 fps
        v = (t - self.T(a)) * sp * _clip_fps(art, name) + off * _clip_fps(art, name)
        return _clip_frame(art, name, int(math.floor(v + 1e-4)))

    def plate_at(self, t: float) -> str:
        name = self.plate
        for a, p in sorted(self.plates, key=lambda x: self.T(x[0])):
            if self.T(a) <= t:
                name = p
        return name

    def flash(self, at: Time, length: float = 0.12) -> None:
        self.flashes.append((at, length))

    def shake(self, at: Time, length: float = 0.4, amp: float = 20) -> None:
        self.shakes.append((at, length, amp))

    def whip(self, at: Time, until: Time) -> None:
        self.whips.append((at, until))

    def speed_lines(self, at: Time, until: Time) -> None:
        self.streak.append((at, until))

    def rewind(self, at: Time, until: Time) -> None:
        self.rewinds.append((at, until))

    def front(self, at: Time, until: Time) -> None:
        self.fronts.append((at, until))

    def text(self, at: Time, until: Time, fn: Callable[[float, float], str]) -> None:
        self.texts.append((at, until, fn))

    def sfx(self, at: Time, name: str, vol: float = 0.55) -> None:
        self.cues.append((at, name, vol, "sfx", None))

    def music(self, at: Time, name: str, vol: float = 0.16, until: Time | None = None) -> None:
        """Music bed from `at`, looped until `until` (default: end of the scene), faded in/out."""
        self.cues.append((at, name, vol, "music", until if until is not None else self.end()))

    def draw(self, at: Time, until: Time, fn: Callable, front: bool = True) -> None:
        """World-space drawing: fn(world RGBA image in plate px, seconds since `at`, scene time) — props, effects,
        map overlays. Drawn over the characters unless front=False."""
        self.draws.append((at, until, fn, front))

    # ---- timing
    def layout(self, durations: dict[int, float]) -> float:
        t, self._t = 0.0, {}
        for n in range(self.shots[0], self.shots[1] + 1):
            self._t[n] = t
            t += durations[n]
        self._t[None] = t
        if self.split:
            for half in self.split:
                half.layout(durations)
        for c in self.casts.values():
            c.keys.sort(key=lambda k: self.T(k.t))
        self.cams.sort(key=lambda c: self.T(c[0]))
        return t

    def T(self, x: Time | None) -> float | None:
        if x is None:
            return None
        if isinstance(x, At):
            return self._t[x.shot] + x.off
        return float(x)


# ---------------------------------------------------------------- evaluation

def _within(c: Comic, spans, t: float, pad: float = 0.0):
    for sp in spans:
        a, b = c.T(sp[0]), c.T(sp[1])
        if a - pad <= t < b + pad:
            return sp, a, b
    return None


def frozen(c: Comic, t: float) -> tuple[float, float]:
    """(strength, freeze start) — the world holds the frame at the start of the freeze."""
    hit = _within(c, [(a, b) for a, b, _ in c.freezes], t)
    if not hit:
        return 0.0, t
    _sp, a, b = hit
    return min(1.0, (t - a) / 0.12) * (1 - max(0.0, (t - (b - 0.12)) / 0.12)), a


def cast_state(c: Comic, who: Cast, t: float):
    """(sprite, x, y, ang, scale, flip, since_change, smear, travel, fixed) at time t, or None when hidden."""
    ks = who.keys
    if not ks or t < c.T(ks[0].t):
        return None
    i = max(j for j, k in enumerate(ks) if c.T(k.t) <= t)
    cur = ks[i]
    nxt = ks[i + 1] if i + 1 < len(ks) else None
    x, y, ang, sc = cur.x, cur.y, cur.ang, cur.scale
    travel = 0.0
    if nxt is not None and nxt.tween != "hold" and nxt.sprite is not None:
        t0, t1 = c.T(cur.t), c.T(nxt.t)
        u = TWEENS[nxt.tween]((t - t0) / max(t1 - t0, 1e-6))
        x, y = cur.x + (nxt.x - cur.x) * u, cur.y + (nxt.y - cur.y) * u
        ang, sc = cur.ang + (nxt.ang - cur.ang) * u, cur.scale + (nxt.scale - cur.scale) * u
        travel = math.hypot(nxt.x - cur.x, nxt.y - cur.y) / max(t1 - t0, 1e-6)
    if cur.sprite is None:
        return None
    since = t - c.T(cur.t) if (i == 0 or ks[i - 1].sprite != cur.sprite) else 9.0
    smear = nxt.smear if (nxt is not None and travel > 0) else False
    return cur.sprite, x, y, ang, sc, cur.flip, since, smear, travel, cur.fixed


def pop(since: float, amt: float = 0.18) -> tuple[float, float]:
    if since > 0.45:
        return 1.0, 1.0
    e = math.sin(since * 22) * math.exp(-since * 9) * amt
    return 1 + e, 1 - e


def _put(canvas: Image.Image, art: str, name: str, x: float, ground: float, k: float, sx=1.0, sy=1.0,
         ang=0.0, alpha=1.0, flip=False) -> None:
    im, gr, _h = _sprite(art, name)
    w, h = max(1, int(im.width * k * sx)), max(1, int(im.height * k * sy))
    s = im.resize((w, h), Image.Resampling.BICUBIC)
    if flip:
        s = s.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if alpha < 1:
        a = np.asarray(s).copy()
        a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
        s = Image.fromarray(a)
    gy = gr * k * sy
    if abs(ang) > 0.01:
        s = s.rotate(-ang, resample=Image.Resampling.BICUBIC, expand=True)
        _composite(canvas, s, int(x - s.width / 2), int(ground - gy / 2 - s.height / 2))
    else:
        _composite(canvas, s, int(x - w / 2), int(ground - gy))


def _composite(canvas: Image.Image, s: Image.Image, dx: int, dy: int) -> None:
    """alpha_composite that tolerates sprites hanging over the plate's edges (they are clipped)."""
    x0, y0 = max(0, -dx), max(0, -dy)
    x1, y1 = min(s.width, canvas.width - dx), min(s.height, canvas.height - dy)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(s.crop((x0, y0, x1, y1)), (dx + x0, dy + y0))


def _cam(c: Comic, t: float, pw: int, ph: int) -> tuple[float, float, float]:
    if not c.cams:
        return pw / 2, ph / 2, pw
    pts = [(c.T(a), x, y, w, tw) for a, x, y, w, tw in c.cams]
    if t <= pts[0][0]:
        return pts[0][1:4]
    for (t0, *v0, _tw0), (t1, *v1, tw1) in zip(pts, pts[1:], strict=False):
        if t < t1:                                     # at a key's own time its value applies (clean cuts)
            u = TWEENS[tw1]((t - t0) / max(t1 - t0, 1e-6))
            return tuple(p + (q - p) * u for p, q in zip(v0, v1, strict=False))
    return pts[-1][1:4]


def view(c: Comic, i: int, size: tuple[int, int], pw: int, ph: int) -> tuple[float, float, float, float]:
    """The camera window (x0, y0, vw, vh) on the plate for frame i, including handheld drift, push and shake."""
    W, H = size
    t = i / FPS
    frz, t_hold = frozen(c, t)
    tw = t_hold if frz > 0 else t
    cx, cy, vw = _cam(c, tw, pw, ph)
    # the picture is never still: a slow handheld float plus a creeping push; during a freeze the push continues
    # (the world is frozen, the camera is not)
    calm = 1 - 0.6 * frz                               # during a freeze the float calms down (chalk is pinned to it)
    cx += (34 * math.sin(t * 0.55) + 10 * math.sin(t * 1.7)) * calm
    cy += 20 * math.sin(t * 0.63 + 1.0) * calm
    vw *= (1 - 0.05 * (0.5 + 0.5 * math.sin(t * 0.37))) if frz == 0 else (1 - 0.04 * min(1.0, (t - t_hold) / 5.0))
    vh = vw * H / W
    shx = shy = 0.0
    for a, ln, amp in c.shakes:
        a = c.T(a)
        if a <= t < a + ln:
            d = 1 - (t - a) / ln
            r = random.Random(i)
            shx, shy = r.uniform(-1, 1) * amp * d, r.uniform(-1, 1) * amp * d
    if shx or shy:                                     # leave room to shake inside the plate
        vw, vh = vw * 0.96, vh * 0.96
    x0 = min(max(cx - vw / 2 + shx, 0), pw - vw)
    y0 = min(max(cy - vh / 2 + shy, 0), ph - vh)
    return x0, y0, vw, vh


def pinned(c: Comic, i: int, size: tuple[int, int], a0: float, svg: str) -> str:
    """Freeze annotations stick to the frozen picture: the camera keeps floating and pushing in during a freeze,
    so the chalk (drawn in screen px of the freeze's first frame) gets the same move."""
    if not svg:
        return svg
    pl = _plate(str(c.art), c.plate)
    xa, ya, vwa, _ = view(c, int(round(a0 * FPS)) + 1, size, pl.width, pl.height)
    x0, y0, vw, _ = view(c, i, size, pl.width, pl.height)
    k = size[0] / vw
    return (f'<g transform="matrix({vwa / vw:.5f},0,0,{vwa / vw:.5f},{(xa - x0) * k:.2f},{(ya - y0) * k:.2f})">'
            + svg + "</g>")


def sprite_boxes(c: Comic, i: int, size: tuple[int, int]) -> list[tuple[str, tuple, tuple]]:
    """Visible characters in frame i: (name, screen box of the opaque pixels, (sprite, flip, left, top, screen
    scale)) — for layout checks (rotation ignored)."""
    art = str(c.art)
    plate = _plate(art, c.plate)
    x0, y0, vw, _vh = view(c, i, size, plate.width, plate.height)
    sk = size[0] / vw
    t = i / FPS
    frz, t_hold = frozen(c, t)
    tw = t_hold if frz > 0 else t
    out = []
    for name in c.order:
        who = c.casts[name]
        st = cast_state(c, who, tw)
        if st is None:
            continue
        spr, x, y, _ang, sc, flip, *_ = st
        prefix = spr.rstrip("0123456789")
        ref = who.ref or f"{name}0"
        ref_h = c.sheet_ref.get(prefix) or _sprite(art, ref)[2] / _pxscale(art, ref)
        k = who.height / ref_h * (1.0 if st[-1] else who.k(y)) * sc / _pxscale(art, spr)
        im, gr, _h = _sprite(art, spr)
        bx = im.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox()
        if not bx:
            continue
        lf, tp, r, b = bx
        if flip:
            lf, r = im.width - r, im.width - lf
        left, top = x - im.width * k / 2, y - gr * k
        out.append((name, ((left + lf * k - x0) * sk, (top + tp * k - y0) * sk,
                           (left + r * k - x0) * sk, (top + b * k - y0) * sk),
                    (spr, flip, (left - x0) * sk, (top - y0) * sk, k * sk)))
    return out


def frame(c: Comic, i: int, size: tuple[int, int]) -> Image.Image:
    W, H = size
    if c.split:
        return _split_frame(c, i, size)
    art = str(c.art)
    t = i / FPS
    frz, t_hold = frozen(c, t)
    tw = t_hold if frz > 0 else t                      # world time (holds during a freeze)
    pname = c.plate_at(tw)
    plate = c.clip_frame(art, pname[1:], tw) if pname.startswith("@") else _plate(art, pname)
    world = plate.copy()
    for da, db, fn, front in c.draws:
        if not front and c.T(da) <= tw < c.T(db):
            fn(world, tw - c.T(da), tw)
    for name in c.order:
        who = c.casts[name]
        st = cast_state(c, who, tw)
        if st is None:
            continue
        spr, x, y, ang, sc, flip, since, smear, travel, fixed = st
        prefix = spr.rstrip("0123456789")
        ref = who.ref or f"{name}0"
        ref_h = c.sheet_ref.get(prefix) or _sprite(art, ref)[2] / _pxscale(art, ref)
        k = who.height / ref_h * (1.0 if fixed else who.k(y)) * sc / _pxscale(art, spr)
        sx, sy = pop(since)
        b = 0.02 * math.sin(t * 3.1 + sum(map(ord, name)) % 7)  # breathing: the drawing is never perfectly still
        sx, sy = sx * (1 - b * 0.5), sy * (1 + b)
        if smear and travel > 0:
            for j, back in enumerate((0.36, 0.24, 0.12)):
                bx = x - math.copysign(travel * back * 0.12, 1 if not flip else -1)
                _put(world, art, spr, bx, y, k, 1.22, 0.95, ang, 0.16 + 0.12 * j, flip)
            sx, sy = 1.16, 0.95
        _put(world, art, spr, x, y, k, sx, sy, ang, flip=flip)
    for da, db, fn, front in c.draws:
        if front and c.T(da) <= tw < c.T(db):
            fn(world, tw - c.T(da), tw)
    if _within(c, c.fronts, tw):
        f = _front(art, c.plate_at(tw))
        if f is not None:
            world.alpha_composite(f)
    x0, y0, vw, vh = view(c, i, size, plate.width, plate.height)
    img = world.resize((W, H), Image.Resampling.BICUBIC, box=(x0, y0, x0 + vw, y0 + vh)).convert("RGB")
    if _within(c, c.whips, t):
        img = img.filter(ImageFilter.BoxBlur(6))
    a = np.asarray(img).astype(np.float32)
    if frz > 0:
        g = a.mean(-1, keepdims=True)
        a = (a * (1 - 0.75 * frz) + g * 0.75 * frz) * (1 - 0.35 * frz)
    rw = _within(c, c.rewinds, t)
    if rw:
        g = a.mean(-1, keepdims=True)
        a = a * 0.5 + g * 0.5
    for fa, ln in c.flashes:
        fa = c.T(fa)
        if fa <= t < fa + ln:
            a = a * 0.15 + 255 * 0.85
    if c.shade[0] > 0:
        sh = int(c.shade[1])
        a[:sh] *= (1 - c.shade[0] * (1 - np.linspace(0, 1, sh)) ** 1.5)[:, None, None]
    total = c._t[None]
    if c.fade_out and t > total - c.fade_out:
        a *= max(0.0, (total - t) / c.fade_out)
    out = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    ui = []
    if rw:
        ui.append(overlay.rewind_look(i, 1.0, W, H))
    if _within(c, c.streak, t):
        ui.append(overlay.streaks(i, 1.0, W, H))
    for fa, fb, items in c.freezes:
        a0, b0 = c.T(fa), c.T(fb)
        if a0 <= t < b0:
            ui.append(pinned(c, i, size, a0, "".join(it({}, t - a0) for it in items)))
    for ta, tb, fn in c.texts:
        a0, b0 = c.T(ta), c.T(tb)
        if a0 <= t < b0:
            ui.append(fn(t - a0, t))
    if ui:
        out.alpha_composite(_svg("".join(ui), W, H))
    return out.convert("RGB")


def _split_frame(c: Comic, i: int, size: tuple[int, int]) -> Image.Image:
    """Two half comics side by side (or stacked top/bottom with `stack`), a dark seam between them, then this
    comic's screen texts and flashes."""
    W, H = size
    out = Image.new("RGB", (W, H), (8, 8, 10))
    half = (W, H // 2) if c.stack else (W // 2, H)
    for k, sub in enumerate(c.split):
        if sub.art is None:
            sub.art = c.art
        out.paste(frame(sub, i, half), (0, k * (H // 2)) if c.stack else (k * (W // 2), 0))
    seam = [0, H // 2 - 3, W, H // 2 + 2] if c.stack else [W // 2 - 3, 0, W // 2 + 2, H]
    ImageDraw.Draw(out).rectangle(seam, fill=(8, 8, 10))
    t = i / FPS
    a = np.asarray(out).astype(np.float32)
    for fa, ln in c.flashes:
        fa = c.T(fa)
        if fa <= t < fa + ln:
            a = a * 0.15 + 255 * 0.85
    for ia, ln in c.inverts:
        if c.T(ia) <= t < c.T(ia) + ln:
            a = 255.0 - a
    total = c._t[None]
    if c.fade_out and t > total - c.fade_out:
        a *= max(0.0, (total - t) / c.fade_out)
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    ui = [fn(t - c.T(ta), t) for ta, tb, fn in c.texts if c.T(ta) <= t < c.T(tb)]
    if ui:
        img.alpha_composite(_svg("".join(ui), W, H))
    return img.convert("RGB")


def encode(c: Comic, i0: int, i1: int, out: Path, size: tuple[int, int], crf: int = 18, threads: int = 0) -> Path:
    W, H = size
    out.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-frames:v", str(i1 - i0), "-r", str(FPS), "-c:v", "libx264",
                          "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                          *(["-threads", str(threads)] if threads else []), str(out)], stdin=subprocess.PIPE)
    assert p.stdin is not None
    for i in range(i0, i1):
        p.stdin.write(frame(c, i, size).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {out}")
    return out


# ---------------------------------------------------------------- chalk / text helpers for scenes

def chalk_note(x: float, y: float, s: str, size: int = 44, t: float = 0.0, d: float = 0.6, weight: int = 600,
               family: str = "Inter"):
    return lambda ctx, u: overlay.chalk_text(x, y, s, size, (u - t) / d, weight, family)


def chalk_line(pts, t: float = 0.0, d: float = 0.5, width: float = 6.0, seed: int = 3):
    return lambda ctx, u: overlay.chalk_line(pts, (u - t) / d, width, seed=seed, rough=False)


def chalk_arrow(x0, y0, x1, y1, t: float = 0.0, d: float = 0.5, seed: int = 6):
    return lambda ctx, u: overlay.chalk_arrow(x0, y0, x1, y1, (u - t) / d, seed)


def scrim(cx, cy, rx, ry):
    return lambda ctx, u: overlay.scrim(cx, cy, rx, ry, min(1.0, u / 0.3))


def label(x: float, y: float, small: str, big: str, size: int = 84):
    """Kicker label (amber mono) over a big white line, fading in."""
    def f(u: float, _t: float) -> str:
        return (overlay.shadowed(overlay.text(x, y, small, 40, overlay.AMBER, weight=700, family="IBM Plex Mono", ls=6,
                                              op=min(1, u / 0.2)))
                + overlay.shadowed(overlay.text(x, y + size + 6, big, size, op=min(1, (u - 0.1) / 0.2))))
    return f


def punch(x: float, y: float, small: str, big: str, size: int = 76, anchor: str = "middle"):
    """Kinetic pop-in title: overshoots and settles."""
    def f(u: float, _t: float) -> str:
        s = 1 + 0.25 * math.exp(-u * 10)
        return (f'<g transform="translate({x},{y}) scale({s:.3f})">'
                + overlay.shadowed(overlay.text(0, 0, small, 70, overlay.AMBER, anchor, 800, "Inter Display"))
                + overlay.shadowed(overlay.text(0, size + 14, big, size, anchor=anchor)) + "</g>")
    return f


def card(big: str, small: str, size: int = 190, cx: float = 960, cy: float = 580):
    """Full-screen black card with a big number, popping in (and creeping in, so it never sits still)."""
    def f(u: float, _t: float) -> str:
        k = min(1.0, u / 0.12)
        s = 1 + 0.15 * (1 - k) + 0.02 * u
        return (f'<rect width="100%" height="100%" fill="#050507"/>'
                f'<g transform="translate({cx},{cy}) scale({s:.3f})">' + overlay.text(0, 0, big, size, anchor="middle")
                + "</g>" + overlay.text(cx, cy + 90, small, 44, overlay.AMBER, "middle", 600, "Inter", op=k))
    return f


def notes(lines, x=120, y=250, gap=1.0, sc=True):
    """Chalk lines written one after another (text, size, bold) over a soft scrim; for Comic.text or freezes."""
    def f(u, _t=None):
        out = [overlay.scrim(x + 420, y + 40 * len(lines), 720, 120 + 70 * len(lines), min(1.0, u / 0.3))] if sc else []
        yy, prev = y, lines[0][1]
        for k, (s, size, bold) in enumerate(lines):
            if k:
                yy += size * 1.15 + prev * 0.22
            prev = size
            out.append(overlay.chalk_text(x, yy, s, size, (u - 0.15 - k * gap) / 0.5, 800 if bold else 600,
                                          "Inter Display" if bold else "Inter"))
        return "".join(out)
    return f


def board(fn: Callable[[float], str], dim: float = 0.97, cx: float = 960, cy: float = 540):
    """Full-screen chalkboard: dark slate + whatever chalk fn(u) draws (screen px; centre cx, cy)."""
    def f(u: float, _t: float) -> str:
        k = min(1.0, u / 1.4)                                  # the moving scene fades out under it
        dx, dy = 22 * math.sin(u * 0.6), 14 * math.sin(u * 0.75 + 1.0)
        z = 1 + 0.03 * (0.5 + 0.5 * math.sin(u * 0.45))      # the board floats like the camera does elsewhere
        return (f'<rect width="100%" height="100%" fill="#14201C" opacity="{dim * k:.2f}"/>'
                f'<g transform="translate({cx + dx:.1f},{cy + dy:.1f}) scale({z:.4f}) translate({-cx},{-cy})">'
                + fn(u) + "</g>")
    return f


def counter(x: float, y: float, kicker: str, fmt: Callable[[float], str], note: str = ""):
    """HUD-style live value (amber kicker, big white value) driven by seconds since it appeared."""
    def f(u: float, _t: float) -> str:
        return overlay.hud(kicker, fmt(u), note, min(1.0, u / 0.25), 1.0, x=x, y=y)
    return f
