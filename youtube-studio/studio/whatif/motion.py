"""Actor motion: mocap loops with planted feet, one-shot clips, cross-fades -> per-frame poses.

A pose is a dict joint -> (x, y, z) in body heights, pelvis-relative in x (pelvis x = 0), y above the floor.
Each baked frame also carries `dx`: how far the actor travelled along +x since the previous frame (body
heights), taken from the mocap root motion, so feet stay planted when the actor is drawn at x += dx * height.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import mocap

Pose = dict[str, tuple[float, float, float]]
LOOPS = {"walk", "walk_b", "run"}
SRC_FPS = 120                   # capture rate of the CMU data; poses are interpolated from it


def rel(f: Pose) -> Pose:
    px = f["pelvis"][0]
    return {j: (x - px, y, z) for j, (x, y, z) in f.items()}


def _dist(a: Pose, b: Pose) -> float:
    ra, rb = rel(a), rel(b)
    return sum((ra[j][0] - rb[j][0]) ** 2 + (ra[j][1] - rb[j][1]) ** 2 for j in ra)


def loop_cycle(frames: list[Pose], start: int = 0, min_len: int = 20) -> tuple[list[Pose], float]:
    """One gait cycle [start, end) whose end pose matches the start pose, and its forward advance."""
    end = min(range(start + min_len, len(frames)), key=lambda b: _dist(frames[start], frames[b]))
    return frames[start:end], frames[end]["pelvis"][0] - frames[start]["pelvis"][0]


def lerp(a: Pose, b: Pose, w: float) -> Pose:
    return {j: tuple(p * (1 - w) + q * w for p, q in zip(a[j], b[j], strict=False)) for j in a}  # type: ignore[misc]


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


@dataclass
class Action:
    t: float                     # start (motion seconds)
    kind: str                    # loop name (walk/run/...), clip name, or "hold"
    cadence: float = 1.0         # loops: playback speed (1 = as captured); may be a callable of t
    phase: int = 0               # loops: start frame inside the cycle
    blend: float = 0.3           # cross-fade from the previous pose (s)


@dataclass
class Track:
    fps: int = 30
    actions: list[Action] = field(default_factory=list)

    def add(self, t: float, kind: str, **kw) -> Track:
        self.actions.append(Action(t, kind, **kw))
        self.actions.sort(key=lambda a: a.t)
        return self

    def bake(self, n: int) -> list[tuple[Pose, float]]:
        """Per motion-frame (pose, dx). Before the first action the actor holds a standing pose.

        Poses are sampled from the 120 fps capture at fractional positions and interpolated, so any cadence
        (0.7x, 1.45x, 3x ...) plays smoothly instead of skipping capture frames unevenly."""
        stand = rel(mocap.clip("stand")[-1])
        step = SRC_FPS / self.fps                    # capture frames per output frame at cadence 1
        out: list[tuple[Pose, float]] = []
        cur, k, prev_pose = None, 0.0, stand
        fade_from, fade_t0 = None, 0.0
        cycles: dict[str, tuple[list[Pose], float]] = {}
        for i in range(n):
            t = i / self.fps
            act = None
            for a in self.actions:
                if a.t <= t + 1e-9:
                    act = a
            if act is not cur:                       # switch: start a cross-fade from the last pose
                fade_from, fade_t0 = prev_pose, t
                cur, k = act, float(act.phase * step if act else 0)
            dx = 0.0
            if cur is None or cur.kind == "hold":
                pose = prev_pose if cur else stand
            elif cur.kind in LOOPS:
                if cur.kind not in cycles:
                    cycles[cur.kind] = loop_cycle(mocap.clip(cur.kind, SRC_FPS), min_len=int(0.66 * SRC_FPS))
                cyc, adv = cycles[cur.kind]
                c = cur.cadence(t) if callable(cur.cadence) else cur.cadence
                k0, k = k, k + c * step

                def at(q: float, cyc=cyc, adv=adv) -> float:
                    m, r = divmod(q, len(cyc))
                    a0 = cyc[int(r)]["pelvis"][0]
                    a1 = cyc[(int(r) + 1) % len(cyc)]["pelvis"][0] + (adv if int(r) + 1 >= len(cyc) else 0.0)
                    return m * adv + a0 + (a1 - a0) * (r - int(r)) - cyc[0]["pelvis"][0]
                dx = at(k) - at(k0)
                r = k % len(cyc)
                pose = lerp(rel(cyc[int(r)]), rel(cyc[(int(r) + 1) % len(cyc)]), r - int(r))
            else:                                   # one-shot clip, then hold its last pose
                fr = mocap.clip(cur.kind, SRC_FPS)
                # previous frame's sample point, clamped the same way: once the clip has ended both clamp to
                # its last pose, so dx = 0 (the actor holds still instead of drifting by the last delta)
                q1 = min((t - cur.t) * SRC_FPS, len(fr) - 1.001)
                q0 = min(max(0.0, (t - cur.t) * SRC_FPS - step), len(fr) - 1.001)

                def sample(q: float, fr=fr) -> Pose:
                    j = int(q)
                    return lerp(fr[j], fr[min(j + 1, len(fr) - 1)], q - j)
                a1, a0 = sample(q1), sample(q0)
                dx = a1["pelvis"][0] - a0["pelvis"][0] if t > cur.t else 0.0
                pose = rel(a1)
            if fade_from is not None and cur is not None and cur.blend > 0 and t - fade_t0 < cur.blend:
                pose = lerp(fade_from, pose, ease((t - fade_t0) / cur.blend))
            prev_pose = pose
            out.append((pose, dx))
        return out
