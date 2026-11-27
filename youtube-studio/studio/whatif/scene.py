"""Scene engine for the What If channel: a Seq covers consecutive narration shots and renders as one clip.

    s = Seq(shots=(3, 6), bg="city")
    hero = s.actor(x=150, h=250, hero=True)
    hero.walk(0)
    hero.run(s.at(4), cadence=lambda t: 1 + t)     # cadence may depend on motion time (s from seq start)
    s.follow(hero, s.at(4))                         # camera travels with the hero from shot 4
    s.hud("LEVEL 1", "44 km/h", "Usain Bolt's top speed", s.at(4, 1.0), s.at(5))
    s.freeze(s.at(6), s.at(6, 4.0), [arrow(...), note(...)])
    s.boom(s.at(6, 4.0), hero)

Times are seconds from the sequence start, or s.at(shot, offset) / s.end(offset) resolved at render time from the
shot durations (aligned narration, or the storyboard slots for a silent preview). A freeze stops all motion
(actors, camera, scarf) while the clip time keeps running, so narration can explain the frozen frame.
"""

from __future__ import annotations

import io
import math
import random
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image

from . import backdrop, character, cutout, overlay, rig, sprites
from .motion import Track, ease


@dataclass(frozen=True)
class At:
    shot: int | None            # None = end of the sequence
    off: float = 0.0


Time = float | At


@dataclass
class Actor:
    seq: Seq
    x: float
    h: float = 240.0
    ground: float | None = None
    flip: bool = False
    hat: str | None = None
    hero: bool = False
    mark: str = "none"               # optional accessory (rig.mark); the hero's identity is the face (2026-11-22)
    head_scale: float = 1.9          # big expressive head (character.py; model sheet proportions)
    exprs: list = field(default_factory=list)    # (at, expression) timeline; default "neutral"
    todo: list = field(default_factory=list)
    exit_at: Time | None = None
    path: Callable[[float], tuple[float, float, float]] | None = None   # motion t -> (x, y of feet, angle deg)
    pivot: str = "feet"              # rotation centre for `path` angles: "feet" or "center"
    arms: list = field(default_factory=list)      # (at, until, style, blend): rig.arms overrides
    name: str | None = None          # extra ctx anchor for chalk notes (chest point)

    def _add(self, at: Time, kind: str, **kw) -> Actor:
        self.todo.append((at, kind, kw))
        return self

    def walk(self, at: Time = 0.0, **kw) -> Actor:
        return self._add(at, "walk", **kw)

    def walk_b(self, at: Time = 0.0, **kw) -> Actor:
        return self._add(at, "walk_b", **kw)

    def run(self, at: Time = 0.0, **kw) -> Actor:
        return self._add(at, "run", **kw)

    def play(self, clip: str, at: Time = 0.0, **kw) -> Actor:
        return self._add(at, clip, **kw)

    def hold(self, at: Time) -> Actor:
        return self._add(at, "hold")

    def along(self, fn: Callable[[float], tuple[float, float, float]], pivot: str = "feet") -> Actor:
        """Position from a function of motion time -> (x, y, angle): falls, wall runs, carried people. y is the
        world y of the feet (the "ground" under them); angle rotates the figure about the pivot (-90 = body
        horizontal pointing left, feet on a wall to the right)."""
        self.path, self.pivot = fn, pivot
        return self

    def face(self, expr: str, at: Time = 0.0) -> Actor:
        """Change expression from `at` (character.FACES: neutral, unimpressed, surprised, worried, determined,
        smile, wince)."""
        self.exprs.append((at, expr))
        return self

    def pose_arms(self, style: str, at: Time, until: Time | None = None, blend: float = 0.2) -> Actor:
        """Arms override (rig.ARMS: catch, carry, reach) over the captured motion."""
        self.arms.append((at, until, style, blend))
        return self

    def exit(self, at: Time) -> Actor:
        """Zip out of frame (super speed) from `at`."""
        self.exit_at = at
        return self


FreezeItem = Callable[[dict, float], str]       # (context, seconds since the freeze began) -> svg


@dataclass
class Seq:
    shots: tuple[int, int]
    bg: str
    ground: float = 975.0
    parallax: float = 1.0
    push: tuple[float, float] = (1.0, 1.04)
    depth: float | None = None       # ground-band split for long fast travel (backdrop.Backdrop)
    actors: list[Actor] = field(default_factory=list)
    cam: list = field(default_factory=list)              # (at, "follow"|"hold", actor)
    huds: list = field(default_factory=list)
    titles: list = field(default_factory=list)
    freezes: list = field(default_factory=list)          # (at, until, items)
    booms: list = field(default_factory=list)
    nights: list = field(default_factory=list)           # (at, duration)
    streak: list = field(default_factory=list)           # (from, until)
    extra: list = field(default_factory=list)            # callables (ctx) -> svg drawn over everything
    cuts: list = field(default_factory=list)             # (at, zoom, focus, x_out, y_out), newest first
    tall: bool = False               # vertical world: tall background, camera travels in y (Seq.camera)
    parallax_y: float = 0.3          # background travel per world px of vertical camera travel
    camfn: Callable[[float], tuple[float, float]] | None = None   # motion t -> (cam_x, cam_y)
    props: list = field(default_factory=list)            # (fn(ctx) -> svg in world coords, front)
    rewinds: list = field(default_factory=list)          # (at, until, speed): motion time runs backwards
    cards: list = field(default_factory=list)            # (at, until, label, title)
    t0: float = 0.0                  # motion clock at the first frame (start mid-action, e.g. before a rewind)
    boards: list = field(default_factory=list)           # (at, until, opacity): dark "chalkboard" under chalk
    _t: dict = field(default_factory=dict)

    # ---- authoring
    def at(self, shot: int, off: float = 0.0) -> At:
        return At(shot, off)

    def end(self, off: float = 0.0) -> At:
        return At(None, off)

    def actor(self, x: float, h: float = 240.0, **kw) -> Actor:
        a = Actor(self, x, h, **kw)
        self.actors.append(a)
        return a

    def follow(self, actor: Actor, at: Time) -> None:
        self.cam.append((at, "follow", actor))

    def camera(self, fn: Callable[[float], tuple[float, float]]) -> None:
        """Explicit camera: motion time -> (cam_x, cam_y); cam_y > 0 looks up (world moves down on screen)."""
        self.camfn = fn

    def prop(self, fn: Callable[[dict], str], front: bool = False) -> None:
        """World-space drawing (buildings, vehicles, platforms): fn(ctx) -> svg in world coordinates; ctx has t,
        mt (motion time), i. Drawn behind the actors unless front=True."""
        self.props.append((fn, front))

    def rewind(self, at: Time, until: Time, speed: float = 3.0) -> None:
        """Play motion backwards between `at` and `until` (VHS-style rewind look)."""
        self.rewinds.append((at, until, speed))

    def stop_camera(self, at: Time) -> None:
        self.cam.append((at, "hold", None))

    def hud(self, label: str, value: str | Callable[[float], str], note: str, at: Time, until: Time,
            note_at: Time | None = None) -> None:
        self.huds.append((at, until, label, value, note, note_at))

    def card(self, label: str, title: str, at: Time, until: Time) -> None:
        """Mission card top left ("RESCUE 1" / "The fall")."""
        self.cards.append((at, until, label, title))

    def board(self, at: Time, until: Time, opacity: float = 0.6) -> None:
        """Darken the frame (under titles and chalk) so a chalk drawing reads like a blackboard."""
        self.boards.append((at, until, opacity))

    def title(self, lines: list[str], at: Time, until: Time) -> None:
        self.titles.append((at, until, lines))

    def freeze(self, at: Time, until: Time, items: list[FreezeItem]) -> None:
        self.freezes.append((at, until, items))

    def boom(self, at: Time, actor: Actor) -> None:
        self.booms.append((at, actor))

    def night(self, at: Time, duration: float = 0.25) -> None:
        self.nights.append((at, duration))

    def cut(self, at: Time, zoom: float = 1.0, focus: str | tuple[float, float] | None = "hero",
            x: float = 0.5, y: float = 0.55) -> None:
        """Reframe from `at` (an edit between camera angles): zoom on the hero (or a screen point, or the centre);
        the focus lands at (x, y) of the output frame. zoom=1 returns to the wide shot."""
        self.cuts.append((at, zoom, focus, x, y))

    def speed_lines(self, start: Time, until: Time) -> None:
        self.streak.append((start, until))

    def ramp(self, points: list[tuple[Time, float]]) -> Callable[[float], float]:
        """Eased value through (time, value) points; times may be s.at(...) (resolved at render time)."""
        return lambda t: ramp([(self.T(a), v) for a, v in points])(t)

    # ---- timing
    def layout(self, durations: dict[int, float]) -> float:
        t, self._t = 0.0, {}
        for n in range(self.shots[0], self.shots[1] + 1):
            self._t[n] = t
            t += durations[n]
        self._t[None] = t
        self.cuts.sort(key=lambda c: -self.T(c[0]))
        return t

    def T(self, x: Time | None) -> float | None:
        if x is None:
            return None
        if isinstance(x, At):
            return self._t[x.shot] + x.off
        return float(x)


# ---------------------------------------------------------------- freeze items (chalk)

def arrow(dx0: float, dy0: float, dx1: float, dy1: float, t: float, d: float = 0.5, anchor: str = "hero",
          seed: int = 1) -> FreezeItem:
    """Chalk arrow; coordinates relative to the anchor (hero chest) or absolute when anchor='screen'."""
    def f(ctx: dict, u: float) -> str:
        ox, oy = ctx[anchor] if anchor != "screen" else (0, 0)
        return overlay.chalk_arrow(ox + dx0, oy + dy0, ox + dx1, oy + dy1, (u - t) / d, seed)
    return f


def note(x: float, y: float, s: str, size: int = 44, t: float = 0.0, d: float = 0.8, weight: int = 600,
         family: str = "Inter", anchor: str = "screen") -> FreezeItem:
    def f(ctx: dict, u: float) -> str:
        ox, oy = ctx[anchor] if anchor != "screen" else (0, 0)
        return overlay.chalk_text(ox + x, oy + y, s, size, (u - t) / d, weight, family)
    return f


def arc(dx0: float, dy0: float, dx1: float, dy1: float, bend: float, t: float, d: float = 0.7,
        anchor: str = "hero", seed: int = 3) -> FreezeItem:
    """Chalk curve (quadratic) from p0 to p1; `bend` pushes the middle sideways (px, + = down)."""
    def f(ctx: dict, u: float) -> str:
        ox, oy = ctx[anchor] if anchor != "screen" else (0, 0)
        x0, y0, x1, y1 = ox + dx0, oy + dy0, ox + dx1, oy + dy1
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2 + bend
        pts = [((1 - q) ** 2 * x0 + 2 * (1 - q) * q * mx + q * q * x1,
                (1 - q) ** 2 * y0 + 2 * (1 - q) * q * my + q * q * y1) for q in (k / 24 for k in range(25))]
        return overlay.chalk_line(pts, (u - t) / d, seed=seed, rough=False)
    return f


def sketch(paths: list[list[tuple[float, float]]], t: float, d: float = 1.2, anchor: str = "screen",
           width: float = 5.0) -> FreezeItem:
    """A chalk drawing (several polylines, drawn in order) relative to the anchor."""
    def f(ctx: dict, u: float) -> str:
        ox, oy = ctx[anchor] if anchor != "screen" else (0, 0)
        return overlay.sketch_paths([[(ox + x, oy + y) for x, y in q] for q in paths], (u - t) / d, width)
    return f


def underline(x0: float, y: float, x1: float, t: float, d: float = 0.3) -> FreezeItem:
    return lambda ctx, u: overlay.chalk_line([(x0, y), (x1, y)], (u - t) / d, 4, seed=5)


# ---------------------------------------------------------------- render

class Baked:
    """Per-frame state of a sequence (positions, camera, motion clock)."""

    def __init__(self, seq: Seq, total: float, fps: int):
        self.seq, self.fps = seq, fps
        self.n = max(1, round(total * fps))
        T = seq.T
        total = self.n / fps
        # a freeze that would release less than 0.6 s before the cut holds to the end instead: a split second of
        # motion between a freeze and the next sequence reads as a glitch
        self.freezes = sorted(((T(a), total + 1.0 if total - T(b) < 0.6 else T(b), items)
                               for a, b, items in seq.freezes), key=lambda f: f[0])
        frz = [(a, b) for a, b, _ in self.freezes]

        rw = [(T(a), T(b), k) for a, b, k in seq.rewinds]

        def motion_t(t: float) -> float:
            m = t
            for a, b in frz:
                m -= max(0.0, min(t, b) - a) if t > a else 0.0
            for a, b, k in rw:
                m -= (1 + k) * max(0.0, min(t, b) - a) if t > a else 0.0
            return max(0.0, seq.t0 + m)
        self.frz, self.rw = frz, rw
        self.mt = [motion_t(i / fps) for i in range(self.n)]
        mn = int(max(self.mt) * fps) + 2
        self.tracks, self.trk = [], []
        for a in seq.actors:
            tr = Track(fps)
            for at, kind, kw in a.todo:
                tr.add(motion_t(T(at)), kind, **kw)
            baked = tr.bake(mn)
            wx, xs = 0.0, []
            if uses_sprites(a):
                # drawn frames: travel at the stride speed of the drawing so the planted foot stays put
                for m in range(mn):
                    act = active_action(tr, m / fps)
                    v = 0.0
                    if act is not None and act.kind in ("walk", "walk_b", "run"):
                        cad = act.cadence(m / fps) if callable(act.cadence) else act.cadence
                        v = sprites.stride_speed(act.kind) * cad
                    wx += v * a.h / fps * (-1 if a.flip else 1)
                    xs.append(wx)
            else:
                for _pose, dx in baked:
                    wx += dx * a.h * (-1 if a.flip else 1)
                    xs.append(wx)
            self.tracks.append((baked, xs))
            self.trk.append(tr)
        # camera: follows the actor's travel smoothed over ~half a stride (a camera locked to the pelvis surges
        # and checks with every step, which makes the whole background judder); worked out in motion time so a
        # freeze holds the camera still
        cams = sorted(((motion_t(T(at)), mode, act) for at, mode, act in seq.cam), key=lambda c: c[0])
        smooth = [_gauss(xs, 5.0 * fps / 30) for _b, xs in self.tracks]
        cam_m: list[float] = []
        cam, lock, mode, actor_i = 0.0, 0.0, "hold", None
        for m in range(mn):
            for ct, cm, act in cams:
                if abs(ct * fps - m) < 0.5 or (m == 0 and ct <= 0):
                    mode = cm
                    if cm == "follow":
                        actor_i = seq.actors.index(act)
                        lock = act.x + smooth[actor_i][m] - cam
            if mode == "follow" and actor_i is not None:
                cam = seq.actors[actor_i].x + smooth[actor_i][m] - lock
            cam_m.append(cam)
        self.cam_x = [cam_m[min(self.mi(i), mn - 1)] for i in range(self.n)]
        self.cam_y = [0.0] * self.n
        if seq.camfn is not None:
            cxy = [seq.camfn(self.mt[i]) for i in range(self.n)]
            self.cam_x = [c[0] for c in cxy]
            self.cam_y = [c[1] for c in cxy]
        self.boom_xy = []
        for at, act in seq.booms:
            ib = min(self.n - 1, round(T(at) * fps))
            k = seq.actors.index(act)
            xs = self.tracks[k][1]
            g = act.ground if act.ground is not None else seq.ground
            self.boom_xy.append((act.x + xs[min(self.mi(ib), len(xs) - 1)] - self.cam_x[ib], g, act.h))

    def mi(self, i: int) -> int:
        return int(round(self.mt[i] * self.fps))

    def rewinding(self, t: float) -> float:
        for a, b, _k in self.rw:
            if a <= t < b:
                return min(1.0, (t - a) / 0.12, (b - t) / 0.12)
        return 0.0

    def frozen(self, t: float) -> tuple[float, float]:
        """Freeze strength (0..1) and seconds since the freeze began (or -1)."""
        best = (0.0, -1.0)
        for a, b in self.frz:                       # back-to-back freezes: the strongest wins (no flicker)
            if a <= t < b + 0.2:
                k = min(1.0, (t - a) / 0.15) if t < b else 1 - (t - b) / 0.2
                if max(0.0, k) > best[0]:
                    best = (max(0.0, k), t - a)
        return best


def uses_sprites(a: Actor) -> bool:
    """The hero is drawn from the model-sheet frames when they exist (sprites.py)."""
    return a.hero and a.hat is None and sprites.available()


def active_action(tr: Track, mt: float):
    act = None
    for x in tr.actions:
        if x.t <= mt + 1e-9:
            act = x
    return act


SPRITE_POSE = {"catch": "catch", "carry": "carry", "reach": "reach", "brace": "brace"}


def sprite_frame(a: Actor, tr: Track, mt: float, t: float, T) -> dict:
    """Drawn frame for the hero now: an arm override (catch/carry/...) picks a pose, else the current action."""
    for at, until, style, _blend in a.arms:
        if T(at) <= t < (T(until) if until is not None else 1e9) and style in SPRITE_POSE:
            return sprites.frame_for(SPRITE_POSE[style], 0.0)
    act = active_action(tr, mt)
    if act is None or act.kind in ("hold", "stand", "surprised", "look_around", "freezing"):
        return sprites.frame_for("stand", 0.0)
    if act.kind == "scared":
        return sprites.frame_for("look_up", 0.0)
    cad = act.cadence(mt) if callable(act.cadence) else act.cadence
    return sprites.frame_for(act.kind, mt - act.t, min(cad, 2.2))   # drawn frames never faster than ~26 fps


def _gauss(xs: list[float], sigma: float) -> list[float]:
    """Zero-phase Gaussian smoothing of a position track (edges held)."""
    if sigma <= 0 or len(xs) < 3:
        return list(xs)
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a = np.pad(np.asarray(xs, dtype=np.float64), r, mode="edge")
    return np.convolve(a, k, mode="valid").tolist()


def _svg(body: str, w: int, h: int) -> Image.Image:
    doc = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{overlay.DEFS}{body}</svg>'
    png = resvg_py.svg_to_bytes(svg_string=doc, font_files=overlay.font_files(), skip_system_fonts=True,
                                resources_dir=str(cutout.PARTS))
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA")


def frame(seq: Seq, bk: Baked, i: int, bg_dir: Path, size: tuple[int, int]) -> Image.Image:
    w, h = size
    fps, T = bk.fps, seq.T
    t, mi = i / fps, bk.mi(i)
    total = bk.n / fps
    frz, frz_u = bk.frozen(t)
    night = 0.0
    for at, dur in seq.nights:
        night = max(night, ease((t - T(at)) / max(dur, 1e-3)))
    cam, cam_y = bk.cam_x[i], bk.cam_y[i]
    vcam = abs(cam - bk.cam_x[i - 1]) if i > 0 else 0.0
    vcy = abs(cam_y - bk.cam_y[i - 1]) if i > 0 else 0.0
    rew = bk.rewinding(t)
    dim = max(frz, 0.55 * rew)
    if seq.tall:
        bd = backdrop.load_tall(str(bg_dir), seq.bg, size)
        vb = vcy * seq.parallax_y
        bg = bd.frame(cam_y * seq.parallax_y, night, min(70.0, vb * 0.9) if vb > 3 else 0.0, dim)
    else:
        bd = backdrop.load(str(bg_dir), seq.bg, size, seq.depth)
        bg = bd.frame(cam * seq.parallax, night, min(70.0, vcam * 0.9) if vcam > 3 else 0.0, dim)

    # shake after booms
    shake = (0.0, 0.0)
    for at, _a in seq.booms:
        u = t - T(at)
        if 0 <= u < 0.8:
            r = random.Random(i)
            d = 1 - u / 0.8
            shake = (r.uniform(-1, 1) * 22 * d, r.uniform(-1, 1) * 14 * d)

    world, ctx = [], {}
    pctx = {"t": t, "mt": bk.mt[i], "i": i, "night": night}
    for fn, front in seq.props:
        if not front:
            world.append(f'<g transform="translate({-cam:.2f},{cam_y:.2f})">{fn(pctx)}</g>')
    order = sorted(range(len(seq.actors)), key=lambda k: seq.actors[k].h)
    for k in order:
        a = seq.actors[k]
        baked, xs = bk.tracks[k]
        pose, _dx = baked[min(mi, len(baked) - 1)]
        for at, until, style, blend in a.arms:
            a0, a1 = T(at), T(until) if until is not None else 1e9
            wgt = ease((t - a0) / max(blend, 1e-3)) * (1 - ease((t - a1) / max(blend, 1e-3)))
            if wgt > 0:
                pose = rig.arms(pose, style, wgt)
        if a.path is not None:
            px, py, ang, *rest = a.path(bk.mt[i])
            flip = rest[0] if rest else a.flip
            sx, g = px - cam, py + cam_y
            q = a.path(max(0.0, bk.mt[i] - 1 / fps))
            v = math.hypot(px - q[0], py - q[1]) * fps / a.h
        else:
            sx = a.x + xs[min(mi, len(xs) - 1)] - cam
            if a.exit_at is not None and t > T(a.exit_at):
                u = t - T(a.exit_at)
                sx += (-1 if a.flip else 1) * 260 * fps * u * (1 + 4 * u)
            g = (a.ground if a.ground is not None else seq.ground) + cam_y
            ang, flip = 0.0, a.flip
            j = max(1, min(mi, len(xs) - 1))
            v = abs(xs[j] - xs[j - 1]) * fps / a.h
        piv = (sx, g) if a.pivot == "feet" else (sx, g - a.h * 0.5)

        def rot(x: float, y: float, piv=piv, ang=ang) -> tuple[float, float]:
            c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            return piv[0] + (x - piv[0]) * c - (y - piv[1]) * s_, piv[1] + (x - piv[0]) * s_ + (y - piv[1]) * c
        chest = rot(sx, g - a.h * 0.62)
        if a.hero:
            ctx["hero"] = chest
            ctx["hero_ground"] = rot(sx, g)
        if a.name:
            ctx[a.name] = chest
            ctx[a.name + "_ground"] = rot(sx, g)
        if not (-400 - a.h < chest[0] < w + 400 + a.h and -400 - a.h < chest[1] < h + 400 + a.h):
            continue
        parts = []
        if uses_sprites(a):
            spd = min(1.0, max(0.0, (v - 1.5) / 25.0))
            tr = bk.trk[k]
            if spd > 0.3:                                      # amber after-images from the same drawn frames
                for gk in (3, 2, 1):
                    mt_g = max(0.0, bk.mt[i] - gk * 0.035 * (0.5 + spd))
                    frg = sprite_frame(a, tr, mt_g, t, T)
                    if a.path is not None:
                        gx, gy, *_r = a.path(mt_g)
                        ox, oy = gx - cam - sx, gy + cam_y - g
                        if abs(ang) > 1e-3:
                            c, s_ = math.cos(math.radians(-ang)), math.sin(math.radians(-ang))
                            ox, oy = ox * c - oy * s_, ox * s_ + oy * c
                    else:
                        ox, oy = -(-1 if flip else 1) * gk * (30 + 90 * spd), 0.0
                    parts.append(sprites.draw(frg, sx + ox, g + oy, a.h, flip, amber=True, op=0.12 + 0.1 * (3 - gk)))
            if abs(ang) < 1:
                parts.append(f'<ellipse cx="{sx:.1f}" cy="{g + 2:.1f}" rx="{a.h * 0.2:.1f}" ry="{a.h * 0.03:.1f}" '
                             f'fill="#000" opacity="{0.22 * (1 - night):.2f}"/>')
            parts.append(sprites.draw(sprite_frame(a, tr, bk.mt[i], t, T), sx, g, a.h, flip))
            body = "".join(parts)
            if abs(ang) > 1e-3:
                body = f'<g transform="rotate({ang:.2f} {piv[0]:.1f} {piv[1]:.1f})">{body}</g>'
            world.append(body)
            continue
        if a.hero:
            # speed 0..1 from travel (body heights per second), frozen during a freeze
            spd = min(1.0, max(0.0, (v - 1.5) / 25.0))
            if spd > 0.3 and (a.exit_at is None or t < T(a.exit_at)):
                for gk in (3, 2, 1):
                    gi = max(0, mi - gk)
                    gp = baked[min(gi, len(baked) - 1)][0]
                    if a.path is not None:
                        gx, gy, *_r = a.path(max(0.0, bk.mt[i] - gk * 0.035 * (0.5 + spd)))
                        ox, oy = gx - cam - sx, gy + cam_y - g
                        if abs(ang) > 1e-3:      # offset is in world space; the group below rotates it back
                            c, s_ = math.cos(math.radians(-ang)), math.sin(math.radians(-ang))
                            ox, oy = ox * c - oy * s_, ox * s_ + oy * c
                        parts.append(f'<g transform="translate({ox:.1f},{oy:.1f})">'
                                     + character.ghost(gp, sx, g, a.h, 0.12 + 0.1 * (3 - gk), flip, a.head_scale)
                                     + "</g>")
                    else:
                        parts.append(character.ghost(gp, sx - (-1 if flip else 1) * gk * (30 + 90 * spd), g, a.h,
                                                     0.12 + 0.1 * (3 - gk), flip, a.head_scale))
            behind, front = rig.mark(a.mark, pose, sx, g, a.h, spd, bk.mt[i], flip)
            parts.append(behind)
        expr = "neutral"
        for at_e, e in sorted(a.exprs, key=lambda q: T(q[0])):
            if T(at_e) <= t:
                expr = e
        wear = a.hat if a.hat is not None else ("labcoat" if a.hero else None)
        spd_c = min(1.0, max(0.0, (v - 1.0) / 8.0))
        if wear == "labcoat" and cutout.available():
            # the hero: cutout parts in the style of the approved model sheet, on the captured skeleton
            if abs(ang) < 1:
                parts.append(f'<ellipse cx="{sx:.1f}" cy="{g + 2:.1f}" rx="{a.h * 0.2:.1f}" ry="{a.h * 0.03:.1f}" '
                             f'fill="#000" opacity="{0.22 * (1 - night):.2f}"/>')
            parts.append(cutout.draw(rig.to_screen(pose, sx, g, a.h, flip), a.h, flip, expr, spd_c, bk.mt[i]))
        else:
            parts.append(character.character(pose, sx, g, a.h, flip, expr, a.head_scale, wear, bk.mt[i], night=night,
                                             shadow=0.22 if abs(ang) < 1 else 0, seed=k, speed=spd_c))
        if a.hero:
            parts.append(front)
        body = "".join(parts)
        if abs(ang) > 1e-3:
            body = f'<g transform="rotate({ang:.2f} {piv[0]:.1f} {piv[1]:.1f})">{body}</g>'
        world.append(body)
    for fn, front in seq.props:
        if front:
            world.append(f'<g transform="translate({-cam:.2f},{cam_y:.2f})">{fn(pctx)}</g>')
    for s0, s1 in seq.streak:
        if T(s0) <= t < T(s1) and frz == 0:
            world.append(overlay.streaks(i, min(1.0, vcam / 60), w, h))
    for (at, _a), (bx, bg_y, bh) in zip(seq.booms, bk.boom_xy, strict=False):
        u = t - T(at)
        if u >= 0:
            world.append(overlay.boom(bx + 40, bg_y - bh * 0.55, u, w, h) + overlay.dust(bx, bg_y, u))
    # framing: slow push over the sequence x the current cut (reframe), with shake; the background is cropped
    # and scaled, the vector layer is re-drawn at the new scale so lines stay sharp
    z = seq.push[0] + (seq.push[1] - seq.push[0]) * (t / total)
    focus, fx_out, fy_out = None, 0.5, 0.5
    for at, cz, cf, ox, oy in seq.cuts:
        if T(at) <= t:
            z *= cz
            focus, fx_out, fy_out = cf, ox, oy
            break
    if focus == "hero" and "hero" in ctx:
        fx, fy = ctx["hero"]
    elif isinstance(focus, tuple):
        fx, fy = focus
    else:
        fx, fy, fx_out, fy_out = w / 2, h / 2, 0.5, 0.5
    cw, ch = w / z, h / z
    x0 = min(max(fx - cw * fx_out, 0.0), w - cw) + shake[0]
    y0 = min(max(fy - ch * fy_out, 0.0), h - ch) + shake[1]
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).convert("RGBA")
    if z > 1.0005 or shake != (0.0, 0.0):
        img = img.resize((w, h), Image.Resampling.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    if world:
        img.alpha_composite(_svg(f'<g transform="scale({z:.5f}) translate({-x0:.2f},{-y0:.2f})">'
                                 + "".join(world) + "</g>", w, h))
    ctx = {k: ((v[0] - x0) * z, (v[1] - y0) * z) for k, v in ctx.items()}

    ui = []
    for at, until, op in seq.boards:
        a, b = T(at), T(until)
        if a <= t < b + 0.3:
            k = ease((t - a) / 0.3) * (1 - ease((t - b) / 0.3))
            ui.append(f'<rect width="{w}" height="{h}" fill="#0A0E14" opacity="{op * k:.2f}"/>')
    for at, until, lines in seq.titles:
        a, b = T(at), T(until)
        op = ease((t - a) / 0.4) * (1 - ease((t - b + 0.4) / 0.4))
        ui.append(overlay.title(lines, op))
    for at, until, label, title_s in seq.cards:
        a, b = T(at), T(until)
        if a <= t < b:
            ui.append(overlay.card(label, title_s, ease((t - a) / 0.3) * (1 - ease((t - b + 0.3) / 0.3))))
    for at, until, label, value, note_s, note_at in seq.huds:
        a, b = T(at), T(until)
        if a <= t < b:
            op = ease((t - a) / 0.25) * (1 - ease((t - b + 0.25) / 0.25))
            val = value(bk.mt[i]) if callable(value) else value
            nop = ease((t - T(note_at)) / 0.25) if note_at is not None else 1.0
            ui.append(overlay.hud(label, val, note_s, op, nop))
    if frz > 0:
        for a, b, items in bk.freezes:
            if a <= t < b + 0.2:
                u = t - a
                fade = 1.0 if t < b else max(0.0, 1 - (t - b) / 0.15)
                ui.append(overlay.scrim(w * 0.75, h * 0.28, w * 0.4, h * 0.31, min(1, u / 0.4) * fade))
                ui.append(f'<g opacity="{fade:.2f}">' + "".join(it(ctx, u) for it in items) + "</g>")
    if rew > 0:
        ui.append(overlay.rewind_look(i, rew, w, h))
    for fn in seq.extra:
        ui.append(fn({**ctx, "t": t, "i": i}))
    if any(ui):
        img.alpha_composite(_svg("".join(ui), w, h))
    return img.convert("RGB")


def encode(seq: Seq, bk: Baked, i0: int, i1: int, out: Path, bg_dir: Path, size: tuple[int, int],
           crf: int = 18, threads: int = 0) -> Path:
    """Frames [i0, i1) of a baked sequence -> H.264 clip (same settings as every other clip, so they concat)."""
    w, h = size
    out.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                          "-r", str(bk.fps), "-i", "-", "-frames:v", str(i1 - i0), "-r", str(bk.fps), "-c:v", "libx264",
                          "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                          *(["-threads", str(threads)] if threads else []), str(out)], stdin=subprocess.PIPE)
    assert p.stdin is not None
    for i in range(i0, i1):
        p.stdin.write(frame(seq, bk, i, bg_dir, size).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {out}")
    return out


def render(seq: Seq, durations: dict[int, float], out: Path, bg_dir: Path, size: tuple[int, int],
           fps: int = 30, crf: int = 18) -> Path:
    """Whole sequence in this process (the episode renderer splits sequences across processes instead)."""
    bk = Baked(seq, seq.layout(durations), fps)
    return encode(seq, bk, 0, bk.n, out, bg_dir, size, crf)


def stills(seq: Seq, durations: dict[int, float], times: list[float], bg_dir: Path, size: tuple[int, int],
           fps: int = 30) -> list[Image.Image]:
    total = seq.layout(durations)
    bk = Baked(seq, total, fps)
    return [frame(seq, bk, min(bk.n - 1, int(t * fps)), bg_dir, size) for t in times]


def speed_value(kmh: Callable[[float], float]) -> Callable[[float], str]:
    return lambda mt: f"{round(kmh(mt)):,} km/h"


def ramp(points: list[tuple[float, float]]) -> Callable[[float], float]:
    """Piecewise eased interpolation through (time, value) points."""
    def f(t: float) -> float:
        if t <= points[0][0]:
            return points[0][1]
        for (a, va), (b, vb) in zip(points, points[1:], strict=False):
            if t <= b:
                return va + (vb - va) * ease((t - a) / max(b - a, 1e-6))
        return points[-1][1]
    return f


__all__ = ["Seq", "Actor", "At", "arrow", "note", "underline", "render", "stills", "ramp", "speed_value", "math"]
