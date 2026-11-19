"""Motion engine: eased camera moves, element reveal animations, flowing pulses and
crossfades. Frames are rendered with Pillow and piped to FFmpeg as raw RGB, one cached
segment per scene (the existing segment cache / concat architecture is unchanged).

Concepts
- A *layer* is the canvas rasterised at `layer_scale` pixels per logical unit (static
  elements only); it is cached per step state.
- The *camera* is a logical view rectangle (centre + view width; height follows the output
  aspect). Every frame is `layer.resize(out_size, box=view*layer_scale)`; the float box gives
  sub-pixel smooth moves.
- *Beats* are the times at which the scene's build steps change. Entering elements animate
  (draw-on / grow / fade, staggered), leaving elements fade out.
- *HUD* elements (diagram title strip) ignore the camera.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from studio.visuals import Canvas, draw_element, element_bbox, point_at, polyline_length, rgba

ENGINE_VERSION = "motion-1"
CANVAS_W, CANVAS_H = 1920, 1080


def ease(x: float) -> float:
    """Cubic ease-in-out on [0, 1]."""
    x = max(0.0, min(1.0, x))
    return 4 * x**3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


@dataclass(frozen=True)
class Shot:
    cx: float
    cy: float
    vw: float  # logical view width; view height = vw / aspect

    def lerp(self, other: Shot, u: float) -> Shot:
        return Shot(self.cx + (other.cx - self.cx) * u, self.cy + (other.cy - self.cy) * u,
                    self.vw + (other.vw - self.vw) * u)


@dataclass
class ScenePlan:
    beats: list[tuple[float, int]]  # (t_rel, step) - step shown from t_rel
    duration: float
    aspect: float
    start_prev_step: int  # step visible before the scene (-1 = nothing: new visual)
    keys: list[tuple[float, Shot, bool]] = field(default_factory=list)  # (t, shot, eased)
    reveal_s: float = 0.9

    @property
    def end_shot(self) -> Shot:
        return self.shot_at(self.duration)

    def shot_at(self, t: float) -> Shot:
        keys = self.keys
        if t <= keys[0][0]:
            return keys[0][1]
        for (t0, s0, _), (t1, s1, eased) in zip(keys, keys[1:], strict=False):
            if t <= t1:
                u = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                return s0.lerp(s1, ease(u) if eased else u)
        return keys[-1][1]

    def moving(self, t: float) -> bool:
        """True while the camera is in an eased move (labels may be partly off-frame)."""
        return any(t0 < t < t1 and eased for (t0, _, _), (t1, _, eased)
                   in zip(self.keys, self.keys[1:], strict=False))

    def state_at(self, t: float) -> tuple[int, int, float]:
        """(current step, previous step, seconds since the current beat)."""
        idx = 0
        for i, (bt, _) in enumerate(self.beats):
            if bt <= t + 1e-9:
                idx = i
        step = self.beats[idx][1]
        prev = self.beats[idx - 1][1] if idx > 0 else self.start_prev_step
        return step, prev, t - self.beats[idx][0]

    @property
    def last_step(self) -> int:
        return self.beats[-1][1]


# --------------------------------------------------------------------------- camera planning


def base_width(aspect: float) -> float:
    """Widest view of the canvas for an output aspect ratio."""
    return min(CANVAS_W, CANVAS_H * aspect)


def clamp_shot(s: Shot, aspect: float) -> Shot:
    vw = max(240.0, min(s.vw, base_width(aspect)))
    vh = vw / aspect
    cx = min(max(s.cx, vw / 2), CANVAS_W - vw / 2)
    cy = min(max(s.cy, vh / 2), CANVAS_H - vh / 2)
    return Shot(cx, cy, vw)


def wide_shot(aspect: float) -> Shot:
    return clamp_shot(Shot(CANVAS_W / 2, CANVAS_H / 2, base_width(aspect)), aspect)


def focus_shot(box: tuple[float, float, float, float], aspect: float, *, pad: float = 110,
               max_zoom: float = 1.32, hud_frac: float = 0.0) -> Shot:
    """Frame `box`; the top `hud_frac` of the picture is reserved for the title strip."""
    x0, y0, x1, y1 = box
    w, h = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    vw = max(w, h * aspect / (1 - hud_frac), base_width(aspect) / max_zoom)
    vh = vw / aspect
    cy = (y0 - pad) - hud_frac * vh + vh / 2  # box top sits just below the HUD strip
    cy = max(cy, (y0 + y1) / 2)
    return clamp_shot(Shot((x0 + x1) / 2, cy, vw), aspect)


def parse_camera(spec: str) -> tuple[str, list[tuple[float, float, float, float]]]:
    """'' | 'auto' | 'static' | 'wide' | 'focus:x,y,w,h|x,y,w,h' (logical coords)."""
    spec = (spec or "auto").strip()
    if spec.startswith("focus:"):
        boxes = []
        for part in spec[len("focus:"):].split("|"):
            x, y, w, h = (float(v) for v in part.split(","))
            boxes.append((x, y, x + w, y + h))
        return "focus", boxes
    if spec not in {"auto", "static", "wide"}:
        raise ValueError(f"Unknown camera spec {spec!r}")
    return spec, []


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def new_elements(canvas: Canvas, prev: int, step: int) -> list[dict[str, Any]]:
    """Elements that animate in when `step` replaces `prev`.

    For a brand-new visual (prev < 0) the scaffold (steps below the first shown step, and
    step 0) appears with the scene transition; only the first shown step > 0 animates.
    """
    if prev < 0:
        return [e for e in canvas.visible(step) if (e.get("intro") or (step > 0 and
                e["step"] == step)) and not e.get("hud") and e.get("anim") != "none"]
    before = {id(e) for e in canvas.visible(prev)}
    return [e for e in canvas.visible(step) if id(e) not in before and not e.get("hud")
            and e.get("anim") != "none"]


def _focusable(e: dict[str, Any]) -> bool:
    if e.get("hud") or e.get("nofocus") or e.get("anim") == "none":
        return False
    x0, y0, x1, y1 = element_bbox(e)
    return (x1 - x0) * (y1 - y0) < 0.45 * CANVAS_W * CANVAS_H


def beat_times(n: int, duration: float, anchors: list[float] | None = None, *,
               first_weight: float = 0.6, min_gap: float = 2.0) -> list[float]:
    """When each build step starts. The first step is shorter (the picture is already there
    from the transition); later steps snap to the nearest sentence start in `anchors` so a
    new element appears as the narrator begins talking about it."""
    if n <= 1:
        return [0.0]
    weights = [first_weight] + [1.0] * (n - 1)
    total = sum(weights)
    targets = [duration * sum(weights[:i]) / total for i in range(1, n)]
    times = [0.0]
    for i, target in enumerate(targets):
        lo = times[-1] + min_gap
        hi = duration - min_gap * (n - 1 - i)
        cands = [a for a in (anchors or []) if lo <= a <= hi and abs(a - target) <= 0.35 *
                 duration / n + 1.0]
        t = min(cands, key=lambda a: abs(a - target)) if cands else min(max(target, lo), hi)
        times.append(t)
    return times


def plan_scene(canvas: Canvas, steps: list[int], duration: float, *, aspect: float = 16 / 9,
               camera: str = "auto", start_shot: Shot | None = None,
               start_prev_step: int = -1, max_zoom: float = 1.32,
               drift: float = 0.035, anchors: list[float] | None = None,
               hud_frac: float = 0.16) -> ScenePlan:
    beats = list(zip(beat_times(len(steps), duration, anchors), steps, strict=True))
    plan = ScenePlan(beats=beats, duration=duration, aspect=aspect,
                     start_prev_step=start_prev_step)
    mode, boxes = parse_camera(camera)
    wide = wide_shot(aspect)
    cur = clamp_shot(start_shot, aspect) if start_shot else wide
    keys: list[tuple[float, Shot, bool]] = [(0.0, cur, False)]

    if mode == "static":
        plan.keys = [(0.0, cur, False), (duration, cur, False)]
        return plan

    # Targets: one per beat (auto/wide) or one per focus box (focus).
    if mode == "focus":
        # one box per build step -> the camera moves with the steps; otherwise evenly
        times = ([bt for bt, _ in beats] if len(boxes) == len(beats)
                 else [i * duration / len(boxes) for i in range(len(boxes))])
        slots = [(tt, focus_shot(b, aspect, pad=0, max_zoom=4.0, hud_frac=hud_frac))
                 for tt, b in zip(times, boxes, strict=True)]
        if start_shot is None:  # open directly on the first framing
            cur = slots[0][1]
            keys = [(0.0, cur, False)]
    elif mode == "wide":
        slots = [(0.0, wide)]
    else:
        slots = []
        prev = start_prev_step
        for t0, step in beats:
            fresh = [e for e in new_elements(canvas, prev, step) if _focusable(e)]
            if fresh:
                bbox = _union([element_bbox(e) for e in fresh])
                target = focus_shot(bbox, aspect, max_zoom=max_zoom, hud_frac=hud_frac)
            else:
                target = slots[-1][1] if slots else cur
            slots.append((t0, target))
            prev = step
    move_s = 1.6
    for i, (t0, target) in enumerate(slots):
        t_end = slots[i + 1][0] if i + 1 < len(slots) else duration
        move_start = t0 + (0.15 if t0 > 0 else 0.0)
        move_end = min(t_end, move_start + move_s)
        if math.dist((cur.cx, cur.cy), (target.cx, target.cy)) > 2 or abs(cur.vw - target.vw) > 2:
            if move_start > keys[-1][0]:
                keys.append((move_start, cur, False))
            keys.append((move_end, target, True))
            cur = target
        # slow drift (gentle push-in) until the next slot
        drifted = clamp_shot(Shot(cur.cx, cur.cy, cur.vw * (1 - drift)), aspect)
        if t_end > keys[-1][0] + 0.05:
            keys.append((t_end, drifted, False))
            cur = drifted
    plan.keys = keys
    return plan


# --------------------------------------------------------------------------- frame rendering


@dataclass
class Overlay:
    """Things drawn in output pixel space after the camera (captions, badges)."""

    draw: Callable[[Image.Image, float], None] | None = None


class SceneRenderer:
    def __init__(self, canvas: Canvas, plan: ScenePlan, out_size: tuple[int, int], *,
                 layer_scale: float = 2.0, view_offset: tuple[int, int] = (0, 0),
                 view_size: tuple[int, int] | None = None, hud: bool = True):
        self.canvas = canvas
        self.plan = plan
        self.out_size = out_size
        self.view_size = view_size or out_size  # where the camera picture is placed
        self.view_offset = view_offset
        self.layer_scale = layer_scale
        self.hud = hud
        self._layers: dict[tuple, Image.Image] = {}
        self._hud_img: Image.Image | None = None
        self.idx = {id(e): i for i, e in enumerate(canvas.elements)}
        self.bg = rgba(canvas.background)[:3]

    # layers -------------------------------------------------------------------------
    def _world(self, step: int) -> list[dict[str, Any]]:
        if step < 0:
            return []
        return [e for e in self.canvas.visible(step) if not e.get("hud")]

    def _layer(self, key: tuple, elements: list[dict[str, Any]]) -> Image.Image:
        img = self._layers.get(key)
        if img is None:
            s = self.layer_scale
            img = Image.new("RGB", (round(CANVAS_W * s), round(CANVAS_H * s)), self.bg)
            d = ImageDraw.Draw(img, "RGBA")
            for e in elements:
                draw_element(d, e, s)
            if len(self._layers) > 6:
                self._layers.pop(next(iter(self._layers)))
            self._layers[key] = img
        return img

    def _hud_layer(self) -> Image.Image | None:
        if self._hud_img is None:
            hud = [e for e in self.canvas.elements if e.get("hud")]
            if not hud or not self.hud:
                return None
            w, h = self.view_size
            ss = 2
            img = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
            d = ImageDraw.Draw(img, "RGBA")
            scale = w / base_width(self.plan.aspect) * ss
            for e in hud:
                draw_element(d, e, scale)
            self._hud_img = img.resize((w, h), Image.Resampling.LANCZOS)
        return self._hud_img

    # animation ------------------------------------------------------------------------
    def _delay(self, rank: int, e: dict[str, Any]) -> float:
        return min(0.9, rank * 0.06) + float(e.get("delay", 0.0)) * self.plan.reveal_s

    def _dur(self, e: dict[str, Any]) -> float:
        return self.plan.reveal_s * float(e.get("dur", 1.0))

    def world_image(self, t: float) -> Image.Image:
        step, prev, since = self.plan.state_at(t)
        cur = self._world(step)
        before = self._world(prev)
        cur_ids = {id(e) for e in cur}
        entering = new_elements(self.canvas, prev, step)
        entering_ids = {id(e) for e in entering}
        leaving = [e for e in before if id(e) not in cur_ids]
        rev = self.plan.reveal_s
        anim_end = max((self._delay(i, e) + self._dur(e) for i, e in enumerate(entering)),
                       default=rev)
        animating = since < anim_end and (entering or leaving)
        dynamic = [e for e in cur if e.get("flow") or e.get("pulse")]
        if not animating:
            base = self._layer(("s", step), cur)
            if not dynamic:
                return base
            img = base.copy()
            d = ImageDraw.Draw(img, "RGBA")
        else:
            static = [e for e in cur if id(e) not in entering_ids]
            img = self._layer(("b", prev, step), static).copy()
            d = ImageDraw.Draw(img, "RGBA")
            s = self.layer_scale
            for e in leaving:
                draw_element(d, e, s, alpha=1 - ease(since / rev))
            for rank, e in enumerate(entering):
                u = (since - self._delay(rank, e)) / self._dur(e)
                if u > 0:
                    draw_element(d, e, s, progress=ease(u) if u < 1 else 1.0)
        self._draw_dynamic(d, dynamic, t, entering if animating else [], since)
        return img

    def _draw_dynamic(self, d: ImageDraw.ImageDraw, elements, t: float, entering, since):
        s = self.layer_scale
        entering_ids = {id(e): r for r, e in enumerate(entering)}
        for e in elements:
            if id(e) in entering_ids:  # wait until it is drawn in
                u = (since - self._delay(entering_ids[id(e)], e)) / self._dur(e)
                if u < 1:
                    continue
            phase0 = (self.idx.get(id(e), 0) * 0.137) % 1
            if e["kind"] == "line" and e.get("flow"):
                pts = e["points"]
                length = polyline_length(pts)
                gap = float(e.get("flow_gap", 200))
                speed = float(e.get("flow_speed", 240))
                n = max(1, int(length // gap))
                r = max(5.0, e["width"] * 1.5)
                color = e["flow"]
                for k in range(n):
                    frac = ((t * speed / length) + k / n + phase0) % 1
                    x, y = point_at(pts, frac)
                    for rr, a in ((r * 2.4, 0.22), (r * 1.5, 0.45), (r, 1.0)):
                        R = rr * s
                        d.ellipse([x * s - R, y * s - R, x * s + R, y * s + R],
                                  fill=_with_alpha(color, a))
            if e["kind"] == "circle" and e.get("pulse"):
                period = float(e.get("pulse_period", 1.8))
                ph = ((t / period) + phase0) % 1
                R = e["r"] * (1 + 1.6 * ph) * s
                color = e.get("pulse") if isinstance(e.get("pulse"), str) else (
                    e["fill"] or e["stroke"])
                cx, cy = e["cx"] * s, e["cy"] * s
                d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=_with_alpha(color, 0.8 *
                          (1 - ph)), width=max(1, round(3 * s)))

    def frame(self, t: float) -> Image.Image:
        world = self.world_image(t)
        shot = self.plan.shot_at(t)
        vw = shot.vw
        vh = vw / self.plan.aspect
        s = self.layer_scale
        W, H = world.size
        x0 = min(max(0.0, (shot.cx - vw / 2) * s), max(0.0, W - vw * s))
        y0 = min(max(0.0, (shot.cy - vh / 2) * s), max(0.0, H - vh * s))
        box = (x0, y0, min(W, x0 + vw * s), min(H, y0 + vh * s))
        view = world.resize(self.view_size, Image.Resampling.BILINEAR, box=box,
                            reducing_gap=None)
        hud = self._hud_layer()
        if hud is not None:
            view.paste(hud, (0, 0), hud)
        if self.view_size == self.out_size and self.view_offset == (0, 0):
            return view
        out = Image.new("RGB", self.out_size, self.bg)
        out.paste(view, self.view_offset)
        return out


def _with_alpha(color: str, a: float) -> tuple[int, int, int, int]:
    r, g, b, aa = rgba(color)
    return (r, g, b, max(0, min(255, round(aa * a))))


def blend(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    return Image.blend(a, b, max(0.0, min(1.0, u)))


# --------------------------------------------------------------------------- encoding


def frames_to_mp4(binary: str, frames, n_frames: int, size: tuple[int, int], fps: int,
                  out: Path, *, preset: str, crf: int) -> None:
    """Pipe `n_frames` PIL images (iterator) into an H.264 segment."""
    w, h = size
    tmp = out.with_suffix(".part.mp4")
    cmd = [binary, "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-r", str(fps), "-an", str(tmp)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    written = 0
    try:
        for img in frames:
            if written >= n_frames:
                break
            proc.stdin.write(img.tobytes())
            written += 1
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg segment encode failed: {err[-1500:]}")
    if written != n_frames:
        raise RuntimeError(f"expected {n_frames} frames, wrote {written}")
    tmp.replace(out)


def canvas_digest(canvas: Canvas) -> str:
    payload = json.dumps([canvas.background, canvas.elements], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def plan_digest(plan: ScenePlan) -> str:
    payload = json.dumps([plan.beats, round(plan.duration, 4), plan.aspect,
                          plan.start_prev_step,
                          [(round(t, 3), round(s.cx, 2), round(s.cy, 2), round(s.vw, 2), e)
                           for t, s, e in plan.keys]])
    return hashlib.sha256(payload.encode()).hexdigest()[:20]
