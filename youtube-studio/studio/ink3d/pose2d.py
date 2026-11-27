"""Pose-to-pose 2D animation for the ink stickman (replaces mocap: a side-view projection of 3D motion collapses
arms and tangles legs; a cartoon reads from clean key poses, constant limb lengths and planted feet).

Units: one head radius R. Angles in degrees: limbs measure from straight down, + swings forward (towards +x when
he faces +x). A pose is a dict of PARAMS (missing ones fall back to STAND):

    rot   whole figure tipped forward about the pelvis (falls, dives)
    lean  torso forward from vertical (relative to rot); nod = head forward relative to the torso
    th*   thigh (absolute, + forward)        kn*  knee bend (>= 0, shin swings back)
    ft*   ankle: 0 = foot at 90 deg to the shin, - = toe pointed down
    ar*   upper arm relative to the torso    el*  elbow bend (>= 0, forearm swings forward/up)
    yaw   0 = facing +x, 90 = facing the camera, 180 = facing -x (turns pass through a front view)
    lift  extra pelvis height over the ground solve (flight, jumps)

Root motion is solved, not authored, wherever possible: "plant" frames stand on the ground (lowest foot point on
it) and the planted point keeps its x, so feet never slide; airborne frames carry the last velocity. Export goes to
the mocap joint format of kit.py (x fwd, y up, z lateral, height ~1) so Blender drives the hero and projects it.

    python -m studio.ink3d.pose2d <module:function> <out_dir>      preview (paper background, 30 fps, sheet)
"""

from __future__ import annotations

import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

R_UNIT = 0.30 / 1.8                 # kit.HEAD_R / kit.HEIGHT: one head radius in mocap units
FPS = 30
L = {"thigh": 1.45, "shin": 1.5, "foot": 0.55, "torso": 1.6, "neck": 0.45, "head": 1.0, "upper": 1.35, "fore": 1.2}
SOLE, TOE = 0.28, 0.22              # stroke radius under the ankle / toe: contact with the ground
HIP_W, SH_W = 0.35, 0.45            # lateral offsets (front view, depth order)
NOD_MAX = (16.0, 30.0)              # head bend back / forward relative to the torso (degrees)
SWING_D = 0.45                      # R: a locked foot whose posed spot moved this far is swinging (low gaits)
SH_DROP = 0.38                      # shoulders this far below the neck point (on the head circle's edge)
PARAMS = ("rot", "lean", "nod", "thR", "knR", "ftR", "arR", "elR", "thL", "knL", "ftL", "arL", "elL", "yaw", "lift")
STAND = {"rot": 0, "lean": 2, "nod": 0, "thR": 2, "knR": 3, "ftR": 0, "arR": -8, "elR": 12, "thL": -2, "knL": 3,
         "ftL": 0, "arL": 6, "elL": 15, "yaw": 0, "lift": 0}


def full(p: dict) -> dict:
    return {k: float(p.get(k, STAND[k])) for k in PARAMS}


def mirror(p: dict) -> dict:
    """Swap left and right limbs."""
    q = dict(p)
    for a in ("th", "kn", "ft", "ar", "el"):
        q[a + "R"], q[a + "L"] = p.get(a + "L", STAND[a + "L"]), p.get(a + "R", STAND[a + "R"])
    return q


def _dd(a: float) -> tuple[float, float]:
    r = math.radians(a)
    return math.sin(r), -math.cos(r)


def fk(p: dict) -> dict:
    """Joint positions relative to the pelvis: {joint: (x, y, z)} in R (x forward, y up, z lateral right)."""
    p = full(p)
    p["nod"] = max(-NOD_MAX[0], min(NOD_MAX[1], p["nod"]))   # a short neck: the head stays on the torso's axis
    rot, lean = p["rot"], p["lean"] + p["rot"]
    J = {"pelvis": (0.0, 0.0)}

    def add(a, ang, ln):
        dx, dy = _dd(ang)
        return a[0] + dx * ln, a[1] + dy * ln
    def up(a, ang, ln):                                       # ang from straight up, + leans forward
        return a[0] + math.sin(math.radians(ang)) * ln, a[1] + math.cos(math.radians(ang)) * ln
    J["chest"] = up(J["pelvis"], lean, L["torso"])
    J["neck"] = up(J["chest"], lean + 0.35 * p["nod"], L["neck"])
    J["head"] = up(J["neck"], lean + p["nod"], L["head"])
    # shoulders sit a little below the head circle, so every arm visibly starts from the body
    J["sh"] = up(J["neck"], lean + 180, SH_DROP)
    for s in "LR":
        th = p["th" + s] - rot                                 # tipping forward swings a hanging leg back
        shin = th - p["kn" + s]
        J["knee" + s] = add(J["pelvis"], th, L["thigh"])
        J["ankle" + s] = add(J["knee" + s], shin, L["shin"])
        J["toe" + s] = add(J["ankle" + s], shin + 90 + p["ft" + s], L["foot"])
        ar = p["ar" + s] - lean                                # arms hang along the torso
        J["elb" + s] = add(J["sh"], ar, L["upper"])
        J["wrist" + s] = add(J["elb" + s], ar + p["el" + s], L["fore"])
    out = {}
    for j, (x, y) in J.items():
        side = j[-1] if j[-1] in "LR" and j not in ("head",) else ""
        w = (HIP_W if j[:-1] in ("knee", "ankle", "toe") else SH_W) if side else 0.0
        out[j] = (x, y, w if side == "R" else -w if side == "L" else 0.0)
    sh = out.pop("sh")
    for s in "LR":
        out["hip" + s] = (0.0, 0.0, HIP_W if s == "R" else -HIP_W)
        out["sh" + s] = (sh[0], sh[1], SH_W if s == "R" else -SH_W)
    yaw = math.radians(p["yaw"])
    c, s_ = math.cos(yaw), math.sin(yaw)
    return {j: (x * c - z * s_, y, x * s_ + z * c) for j, (x, y, z) in out.items()}


def contacts(J: dict) -> dict:
    """Foot contact points (heel = under the ankle, toe): name -> (x, bottom y)."""
    return {f"{k}{s}": (J[k + s][0], J[k + s][1] - (SOLE if k == "ankle" else TOE))
            for s in "LR" for k in ("ankle", "toe")}


BODY_R = {"head": 1.0, "pelvis": 0.34, "chest": 0.34, "kneeL": 0.22, "kneeR": 0.22, "elbL": 0.22, "elbR": 0.22,
          "wristL": 0.24, "wristR": 0.24}


def all_contacts(J: dict) -> dict:
    """Feet plus body parts (a figure lying, kneeling or on its hands rests on them)."""
    c = contacts(J)
    c.update({j: (J[j][0], J[j][1] - r) for j, r in BODY_R.items()})
    return c


def clear_head(p: dict, margin: float = 0.6) -> dict:
    """Arms never cross the big round head (a hand behind or over the head reads as a glitch): while the elbow,
    the forearm's middle or the wrist is inside the head circle (+ margin), swing that arm forward/down and open
    the elbow a little."""
    q = full(p)
    for s in "LR":
        for _ in range(40):
            J = fk(q)
            hx, hy = J["head"][0], J["head"][1]
            e, w = J["elb" + s], J["wrist" + s]
            pts = [e, ((e[0] + w[0]) / 2, (e[1] + w[1]) / 2), w]
            if all((x - hx) ** 2 + (y - hy) ** 2 > (1.0 + margin) ** 2 for x, y, *_ in pts):
                break
            q["ar" + s] -= 4 if q["ar" + s] > 60 else -4
            q["el" + s] = max(0.0, q["el" + s] - 3)
    return q


# ---------------------------------------------------------------- curves and easing

def ease(u: float, kind: str = "io") -> float:
    u = min(1.0, max(0.0, u))
    if kind == "lin":
        return u
    if kind == "in":                    # slow start, fast end (falls, wind-up releases)
        return u ** 2.4
    if kind == "out":                   # fast start, slow end (snaps settling into a pose)
        return 1 - (1 - u) ** 2.4
    if kind == "snap":                  # very fast out: a punch, a slam
        return 1 - (1 - u) ** 4
    if kind == "back":                  # overshoot then settle
        k = 1.9
        v = u - 1
        return 1 + (k + 1) * v ** 3 + k * v ** 2
    if kind == "step":
        return 1.0 if u >= 1 else 0.0
    return u * u * (3 - 2 * u)          # io


def catmull(vals: list[float], u: float, periodic: bool = False) -> float:
    """Value along a uniform Catmull-Rom spline through vals at u in [0, n-1] (or [0, n) periodic)."""
    n = len(vals)
    i = int(math.floor(u))
    t = u - i

    def v(k):
        return vals[k % n] if periodic else vals[min(n - 1, max(0, k))]
    p0, p1, p2, p3 = v(i - 1), v(i), v(i + 1), v(i + 2)
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


class Cycle:
    """A periodic gait: per-parameter keys over one cycle (phase 0..1) for the RIGHT limbs and the body; the left
    limbs replay the right curves half a cycle later. Keys: {param: [v0, v1, ...]} sampled evenly over the cycle
    (periodic Catmull-Rom), e.g. 8 values = every 1/8 cycle."""

    def __init__(self, keys: dict, period: float):
        self.keys, self.period = keys, period

    def _v(self, name: str, ph: float) -> float:
        vals = self.keys[name]
        return catmull(vals, (ph % 1.0) * len(vals), periodic=True)

    def pose(self, ph: float) -> dict:
        p = {}
        for k in self.keys:
            if k[-1] == "R" and k[:-1] in ("th", "kn", "ft", "ar", "el"):
                p[k] = self._v(k, ph)
                p[k[:-1] + "L"] = self._v(k, ph + 0.5)
            else:
                p[k] = self._v(k, ph)
        return p


def lerp_pose(a: dict, b: dict, u: float) -> dict:
    a, b = full(a), full(b)
    return {k: a[k] + (b[k] - a[k]) * u for k in PARAMS}


def add_pose(a: dict, d: dict) -> dict:
    q = full(a)
    for k, v in d.items():
        q[k] += v
    return q


# ---------------------------------------------------------------- the timeline

class Anim:
    """A figure's performance: a list of frames {pose, mode, ...}; solve() turns them into world joints.
    modes: "plant" (ground solve + no sliding), "air" (y from lift over the takeoff ground, x carried with the
    velocity or an explicit dx), "free" (explicit root offsets per frame relative to the segment start)."""

    def __init__(self, x0: float = 0.0, facing: int = 1, ground: float = 0.0):
        self.frames: list[dict] = []
        self.x0, self.facing, self.ground = x0, facing, ground
        self.marks: dict = {}
        self.roots: list = []

    # -- building
    @property
    def n(self) -> int:
        return len(self.frames)

    @property
    def last(self) -> dict:
        return self.frames[-1]["pose"] if self.frames else full(STAND)

    def mark(self, name: str) -> int:
        self.marks[name] = self.n
        return self.n

    def hold(self, sec: float, pose: dict | None = None, breathe: float = 0.0, mode: str = "plant"):
        p = full(pose or self.last)
        seg = ("hold", self.n)
        for i in range(int(round(sec * FPS))):
            b = math.sin(2 * math.pi * i / (FPS * 1.3))
            q = add_pose(p, {"lean": 1.5 * b * breathe, "nod": 2 * b * breathe, "arR": -1 * b * breathe,
                             "arL": 1 * b * breathe})
            f = {"pose": q, "mode": mode}
            if mode != "plant":
                f["d"], f["seg"] = (0.0, 0.0), seg
            self.frames.append(f)
        return self

    def to(self, pose: dict, sec: float, kind: str = "io", mode: str = "plant", dx: float | None = None,
           arc: float = 0.0, dy: float = 0.0, xkind: str | None = None, sm: int | None = None,
           anchor: str | None = None):
        """Ease from the current pose into `pose` over sec. Modes "air" / "slide" / "free" move the root dx in
        total (air: linear in time along an arc of height `arc`, ending dy higher; slide: eased by xkind, on the
        ground). sm = root smoothing window for these frames (1 = sharp, for impacts). anchor = a contact point
        ("ankleR", "toeR", ...) that keeps its world x through the move (getting up off a knee: the front foot
        stays put instead of the root following whatever touches the ground)."""
        a = self.last
        b = full(pose)
        n = max(1, int(round(sec * FPS)))
        xk = xkind or ("lin" if mode == "air" else kind)
        seg = self.n
        for i in range(1, n + 1):
            u = ease(i / n, kind)
            f = {"pose": lerp_pose(a, b, u), "mode": mode}
            if sm is not None:
                f["sm"] = sm
            if anchor:
                f["anchor"] = (anchor, seg)
            if mode in ("air", "free", "slide"):
                lu = i / n
                f["d"] = ((dx or 0.0) * ease(lu, xk), arc * 4 * lu * (1 - lu) + dy * lu)
                f["seg"] = seg
            self.frames.append(f)
        return self

    def keys(self, poses: list[tuple[float, dict]], mode: str = "plant"):
        """Smooth pass through several key poses (Catmull-Rom per parameter, uniform in key index; the time of
        each key is given as seconds after the previous one)."""
        ks = [full(self.last)] + [full(p) for _, p in poses]
        ts = [0.0]
        for d, _ in poses:
            ts.append(ts[-1] + d)
        n = int(round(ts[-1] * FPS))
        for i in range(1, n + 1):
            t = i / FPS
            k = max(0, min(len(ts) - 2, next((j for j in range(len(ts) - 1) if ts[j] <= t <= ts[j + 1]), len(ts) - 2)))
            u = k + (t - ts[k]) / max(1e-6, ts[k + 1] - ts[k])
            self.frames.append({"pose": {p: catmull([q[p] for q in ks], u) for p in PARAMS}, "mode": mode})
        return self

    def cycle(self, cyc: Cycle, sec: float, phase: float = 0.0, rate: float = 1.0, blend: float = 0.12,
              reverse: bool = False, mods: dict | None = None, ramp: tuple | None = None, end: str = ""):
        """Play a gait for sec seconds from `phase` (rate scales its tempo; reverse plays it backwards: a backward
        walk). Returns the phase where it stopped. ramp=(rate0, rate1) accelerates linearly."""
        start = self.last
        n = int(round(sec * FPS))
        if end == "pass" and ramp is None:                 # stop where the legs pass each other (one foot free)
            step = rate / (cyc.period * FPS)
            best = min(range(max(1, n - 12), n + 13),
                       key=lambda k: abs(((phase + (-1 if reverse else 1) * step * k - 0.25) % 0.5) - 0.0)
                       if ((phase + (-1 if reverse else 1) * step * k - 0.25) % 0.5) < 0.25
                       else 0.5 - ((phase + (-1 if reverse else 1) * step * k - 0.25) % 0.5))
            n = best
        nb = max(1, int(round(blend * FPS)))
        ph = phase
        for i in range(n):
            r = rate if ramp is None else ramp[0] + (ramp[1] - ramp[0]) * i / max(1, n - 1)
            p = full(cyc.pose(ph))
            if mods:
                p = add_pose(p, mods)
            if i < nb and self.frames:
                p = lerp_pose(start, p, ease((i + 1) / nb))
            self.frames.append({"pose": p, "mode": "plant"})
            ph += (-1 if reverse else 1) * r / (cyc.period * FPS)
        return ph

    # -- solving
    def solve(self) -> list[dict]:
        """World joints per frame (R units; x, y, z). Three passes: (1) root path from the planted contact point,
        (2) that path smoothed (per-frame window "sm", default 7 frames; 1 = keep sharp), (3) foot locks: a foot
        that touches the ground stays where it landed (2-bone IK on the leg) until the pose lifts it."""
        raw = self._roots()
        n = len(raw)
        plant = [f["mode"] == "plant" for f in self.frames]
        # x: a pin switch can make a one-frame jump -> median-filter the per-frame steps inside planted runs,
        # integrate, then smooth the path (window "sm")
        steps = [0.0] + [raw[i][0] - raw[i - 1][0] for i in range(1, n)]
        fixed = list(steps)
        for i in range(1, n):
            if plant[i] and int(self.frames[i].get("sm", 7)) > 1:
                win = [steps[j] for j in range(max(1, i - 2), min(n, i + 3)) if plant[j]]
                fixed[i] = sorted(win)[len(win) // 2]
        px = [raw[0][0]]
        for i in range(1, n):
            px.append(px[-1] + fixed[i])
        xs, ys = [], []
        for i in range(n):
            w = int(self.frames[i].get("sm", 7)) // 2 if plant[i] else 0
            lo, hi = max(0, i - w), min(n - 1, i + w)
            k = min(i - lo, hi - i)
            xs.append(sum(px[i - k: i + k + 1]) / (2 * k + 1))
            # y: the lowest-contact solve kinks at every step change -> a light smoothing inside planted runs
            k2 = 2 if plant[i] and int(self.frames[i].get("sm", 7)) > 1 else 0
            while k2 and not all(plant[j] for j in range(max(0, i - k2), min(n, i + k2 + 1))):
                k2 -= 1
            k2 = min(k2, i, n - 1 - i)
            ys.append(sum(r[1] for r in raw[i - k2: i + k2 + 1]) / (2 * k2 + 1))
        self.roots = [(xs[i], ys[i]) for i in range(n)]
        out = []
        lock = {"L": None, "R": None}
        fade = {"L": None, "R": None}
        p_prev = full(STAND)
        anchor: dict = {}
        for i, f in enumerate(self.frames):
            p = full(f["pose"])
            x, y = self.roots[i]
            yaw = math.radians(p["yaw"])
            fe = self.facing * (1 if math.cos(yaw) >= 0 else -1)
            # where the pose itself puts each ankle in the world this frame (before any lock): a foot whose raw
            # position travels over the ground is swinging, even if a low, shuffling gait barely lifts it
            Jr = fk({**p, "yaw": 0.0})
            xr = raw[i][0]                                    # the pinned (unsmoothed) root: a stance foot is still
            raw_ank = {s_: xr + fe * Jr["ankle" + s_][0] for s_ in "LR"}
            # a locked foot whose posed position has walked away from where it was locked is mid-swing
            swinging = {s_: lock[s_] is not None and s_ in anchor and abs(raw_ank[s_] - anchor[s_]) > SWING_D
                        for s_ in "LR"}
            if f["mode"] == "plant" and abs(math.sin(yaw)) < 0.1 and not f.get("nolock"):
                for s_ in "LR":
                    if swinging[s_] and lock[s_] is not None:
                        fade[s_] = ({k: p_prev[k + s_] for k in ("th", "kn", "ft")}, 4)
                        lock[s_] = None
                drop = max(self._lock(p, s_, x, y, fe, lock[s_])[2] for s_ in "LR" if not swinging[s_]) \
                    if not all(swinging.values()) else 0.0
                if drop > 0:                                  # a planted leg can't reach: the hips dip
                    y -= min(drop, 0.45)
                    self.roots[i] = (x, y)
                for s_ in "LR":
                    if swinging[s_]:
                        continue
                    had = lock[s_]
                    q, lock[s_], _ = self._lock(p, s_, x, y, fe, lock[s_])
                    if had is None and lock[s_] is not None:
                        anchor[s_] = raw_ank[s_]
                    if had is not None and lock[s_] is None:     # released: ease the leg back to its pose
                        fade[s_] = ({k: p_prev[k + s_] for k in ("th", "kn", "ft")}, 4)
                    p = q
            else:
                lock = {"L": None, "R": None}
            for s_ in "LR":
                if lock[s_] is None and fade[s_] and fade[s_][1] > 0:
                    saved, left = fade[s_]
                    u = ease(1 - (left - 1) / 4, "io")
                    p = dict(p)
                    for k in ("th", "kn", "ft"):
                        p[k + s_] = saved[k] + (p[k + s_] - saved[k]) * u
                    fade[s_] = (saved, left - 1)
                    lifting = 0.1 * (4 - left + 1)                 # a released foot peels off the ground
                else:
                    lifting = 0.0
                if lock[s_] is None and f["mode"] == "plant":     # a swinging foot never scrapes the ground
                    for _ in range(25):
                        Jc = fk(p)
                        lo = min(Jc["ankle" + s_][1] - SOLE, Jc["toe" + s_][1] - TOE) + y
                        if lo >= self.ground - 0.005 + lifting:
                            break
                        p = dict(p)
                        p["kn" + s_] += 4
                        p["th" + s_] += 2
            for s_ in "LR":                                   # last word: no part of a foot below the ground
                for _ in range(30):
                    Jc = fk(p)
                    toe_lo = Jc["toe" + s_][1] - TOE + y
                    heel_lo = Jc["ankle" + s_][1] - SOLE + y
                    if toe_lo >= self.ground - 0.01 and heel_lo >= self.ground - 0.01:
                        break
                    p = dict(p)
                    if toe_lo < self.ground - 0.01 and heel_lo >= self.ground - 0.01:
                        p["ft" + s_] += 3                       # tip the toe up onto the ground
                    else:
                        p["kn" + s_] += 3                       # the heel is under: bend the knee
                        p["th" + s_] += 1.5
            if f.get("arms"):                                 # an arm action laid over the body motion
                wgt = f.get("arms_w", 1.0)
                p = dict(p)
                for k, v in f["arms"].items():
                    p[k] = p[k] + (v - p[k]) * wgt
            if not f.get("cover"):                            # covering the face is the one time arms cross it
                p = clear_head(p)
            p_prev = p
            J = fk(p)
            if self.facing < 0:
                J = {j: (-a, b, -c) for j, (a, b, c) in J.items()}
            f["solved"] = p
            out.append({j: (x + a, y + b, c) for j, (a, b, c) in J.items()})
            if f.get("cover_w"):
                out[-1]["_cover"] = float(f["cover_w"])
        return out

    def _lock(self, p, s, x, y, fe, lk):
        """Keep side s's foot planted. Returns (pose, lock, hip drop needed); lock = (contact name, world x).
        Works in the figure's own frame (yaw 0); fe carries the facing (and a 180-degree yaw)."""
        p = dict(p)
        yaw0 = p.get("yaw", 0.0)
        p["yaw"] = 0.0
        J = fk(p)
        gy = self.ground + 0.03
        heel = (x + fe * J["ankle" + s][0], y + J["ankle" + s][1] - SOLE)
        toe = (x + fe * J["toe" + s][0], y + J["toe" + s][1] - TOE)
        low = "ankle" if heel[1] <= toe[1] else "toe"
        if min(heel[1], toe[1]) > (gy if lk is None else self.ground + 0.09):
            return {**p, "yaw": yaw0}, None, 0.0             # the pose lifts this foot clearly: release
        if lk is None:
            return {**p, "yaw": yaw0}, (low, heel[0] if low == "ankle" else toe[0]), 0.0
        name, lx = lk
        shin0 = p["th" + s] - p["rot"] - p["kn" + s]
        foot_abs = shin0 + 90 + p["ft" + s]
        if name == "ankle":
            ax, ay = (lx - x) * fe, self.ground + SOLE - y         # the heel sits exactly on the ground
        else:
            fa = max(55.0, min(82.0, foot_abs))                  # on the toe the heel only ever rises
            dx, dy = _dd(fa)
            ax, ay = (lx - x) * fe - dx * L["foot"], self.ground + TOE - y - dy * L["foot"]   # the toe on it
        d = math.hypot(ax, ay)
        lt, ls = L["thigh"], L["shin"]
        reach = (lt + ls) * 0.995
        if d > reach and name == "ankle":                     # the heel comes up: roll onto the planted toe
            return self._lock({**p, "yaw": yaw0}, s, x, y, fe, ("toe", lx + fe * L["foot"]))
        if d > reach:
            if abs(ax) >= reach:
                return {**p, "yaw": yaw0}, None, 0.0         # hopeless: let the foot go
            drop = -ay - math.sqrt(reach * reach - ax * ax)
            ay += drop
            d = math.hypot(ax, ay)
            if drop > 0.45:
                return {**p, "yaw": yaw0}, None, 0.0
        else:
            drop = 0.0
        if d < abs(lt - ls) + 0.05:
            return {**p, "yaw": yaw0}, None, 0.0
        base = math.degrees(math.atan2(ax, -ay))
        a1 = math.degrees(math.acos(max(-1.0, min(1.0, (lt * lt + d * d - ls * ls) / (2 * lt * d)))))
        th = base + a1
        kx, ky = _dd(th)
        kx, ky = kx * lt, ky * lt
        shin = math.degrees(math.atan2(ax - kx, -(ay - ky)))
        q = dict(p)
        q["th" + s] = th + p["rot"]
        q["kn" + s] = th - shin
        if name == "ankle":
            # heel planted: the foot lies flat on the ground (a toe-up heel strike settles within the lock; a toe
            # pointing down into the ground is never shown)
            q["ft" + s] = 90 + max(0.0, min(12.0, foot_abs - 90)) * 0.5 - shin - 90
        else:
            # rolled onto the toe (push-off): the heel may rise, but not steeper than ~35 degrees
            q["ft" + s] = max(55.0, min(82.0, foot_abs)) - shin - 90
        if name == "ankle" and low == "toe" and foot_abs < 70:  # the pose clearly peels the heel: lock the toe
            Jq = fk(q)
            return {**q, "yaw": yaw0}, ("toe", x + fe * Jq["toe" + s][0]), drop
        return {**q, "yaw": yaw0}, lk, drop

    def _roots(self) -> list[tuple[float, float]]:
        roots = []
        x, y = self.x0, self.ground
        vx, pin, hist, measured = 0.0, None, [], []
        anchor_seg, anchor_x = None, 0.0
        seg0, base = None, (x, y)
        for i, f in enumerate(self.frames):
            p = full(f["pose"])
            J = fk(p)
            if self.facing < 0:
                J = {j: (-a, b, -c) for j, (a, b, c) in J.items()}
            C = all_contacts(J)
            low_name = min(C, key=lambda k: C[k][1])
            low = C[low_name][1]
            mode = f["mode"]
            lift = max(0.0, p["lift"])
            if mode == "plant" and f.get("anchor"):
                name = f["anchor"][0]
                if anchor_seg != f["anchor"]:
                    anchor_seg, anchor_x = f["anchor"], x + C[name][0]
                ny = self.ground - low + lift
                nx = anchor_x - C[name][0]
                pin = (low_name, nx + C[low_name][0])
            elif mode == "plant":
                ny = self.ground - low + lift
                if lift < 0.02 and pin is not None and C[pin[0]][1] - low < 0.15:
                    nx = pin[1] - C[pin[0]][0]               # the planted point keeps its world x
                else:
                    nx = x + vx
                pin = (low_name, nx + C[low_name][0]) if lift < 0.02 else None
            else:
                if f.get("seg") != seg0:
                    seg0 = f.get("seg")
                    base = (x, y)
                dxx, dyy = f.get("d", (0.0, 0.0))
                nx = base[0] + dxx * self.facing if f.get("d") is not None else x + vx
                if mode == "free":
                    ny = base[1] + dyy
                elif mode == "slide":                          # explicit x, standing on the ground
                    ny = self.ground - low + lift
                else:                                         # air: the arc, never below the ground
                    ny = max(self.ground - low, base[1] + dyy)
                pin = None
            if i:
                hist.append(nx - x)
                vx = sorted(hist[-3:])[len(hist[-3:]) // 2]    # carried velocity: median of the last 3 steps
                if mode == "plant" and lift < 0.02 and not measured:
                    measured.append(i)
            x, y = nx, ny
            roots.append((x, y))
        # a clip that starts mid-stride (in the air) has no measured speed yet: give the opening frames the speed of
        # the first planted steps instead of starting from rest (feet would slide)
        first = measured[0] if measured else None
        if first and first + 3 < len(roots) and all(self.frames[j]["mode"] == "plant" for j in range(first + 1)):
            v0 = sorted(roots[j + 1][0] - roots[j][0] for j in range(first, first + 3))[1]
            if abs(v0) > 0.02:
                shift = [(first - j) * v0 for j in range(first)]
                base = roots[first][0]
                roots = [(base - shift[j], roots[j][1]) if j < first else r for j, r in enumerate(roots)]
        return roots


def stretch_roots(roots, i0, i1, k):
    out = list(roots)
    x0 = roots[i0][0]
    shift = (roots[i1][0] - x0) * (k - 1)
    for i in range(len(roots)):
        if i0 <= i <= i1:
            out[i] = (x0 + (roots[i][0] - x0) * k, roots[i][1])
        elif i > i1:
            out[i] = (roots[i][0] + shift, roots[i][1])
    return out


def world(anim: Anim, k_fit: tuple | None = None) -> list[dict]:
    """Solve, apply an optional root stretch (i0, i1, k), return world joints (R units)."""
    w = anim.solve()
    if not k_fit:
        return w
    roots = stretch_roots(anim.roots, *k_fit)
    return [{j: (a - anim.roots[i][0] + roots[i][0], b, c) for j, (a, b, c) in f.items()} for i, f in enumerate(w)]


# ---------------------------------------------------------------- export / preview

def to_mocap(frames: list[dict]) -> list:
    """World joints (R) -> kit mocap units: x fwd, y up, z lateral (right side = +z = towards the camera).
    None frames (hidden) stay None; a giant's head offsets follow its "_hr"."""
    u = R_UNIT
    out = []
    for J in frames:
        if J is None:
            out.append(None)
            continue
        hr = J.get("_hr", 1.0)
        d = {j: [J[j][0] * u, J[j][1] * u, J[j][2] * u] for j in ("pelvis", "chest", "neck", "hipL", "hipR", "shL",
                                                                   "shR")}
        for s in "LR":
            d["knee" + s], d["ankle" + s], d["toe" + s] = ([J[k + s][0] * u, J[k + s][1] * u, J[k + s][2] * u]
                                                           for k in ("knee", "ankle", "toe"))
            d["elb" + s], d["wrist" + s] = ([J[k + s][0] * u, J[k + s][1] * u, J[k + s][2] * u] for k in ("elb", "wrist"))
        hc, nk = J["head"], J["neck"]
        dx, dy, dz = hc[0] - nk[0], hc[1] - nk[1], hc[2] - nk[2]
        ln = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        dx, dy, dz = dx / ln, dy / ln, dz / ln
        k = 0.72 * hr                                                 # kit: head = hb + dir * 0.72 R * scale
        hb = (hc[0] - k * dx, hc[1] - k * dy, hc[2] - k * dz)
        d["headbase"] = [hb[0] * u, hb[1] * u, hb[2] * u]
        d["headtop"] = [(hb[0] + 0.8 * dx) * u, (hb[1] + 0.8 * dy) * u, (hb[2] + 0.8 * dz) * u]
        out.append(d)
    return out


def to_px(J: dict, cx: float, cy: float, s: float) -> dict:
    """World joints (R) -> stick2d frame dict (px; depth = -z so +z is nearer). J["_hr"] = head radius in R."""
    d = {j: [cx + v[0] * s, cy - v[1] * s, 10 - v[2] * 0.01] for j, v in J.items() if not j.startswith("_")}
    d["head_r"] = s * J.get("_hr", 1.0)
    return d


def scaled(frames: list[dict], k: float, anchor_x: float | None = None) -> list[dict]:
    """A giant: world frames scaled by k about the ground under anchor_x (default: first pelvis)."""
    ax = frames[0]["pelvis"][0] if anchor_x is None else anchor_x
    return [None if f is None else {**{j: (ax + (v[0] - ax) * k, v[1] * k, v[2] * k) for j, v in f.items()
                                       if not j.startswith("_")}, "_hr": k} for f in frames]


def preview(anims: dict, out: Path, w: int = 640, h: int = 520, s: float = 52.0, follow: str = "hero",
            ground_y: float | None = None, props=None) -> Path:
    """Draw the figures over plain paper with a ground line, camera following `follow`'s pelvis (x only).
    anims = {name: world frames (R)}; writes out/frames + out.mp4 + out_sheet.jpg (every frame, 30 fps)."""
    import io

    import resvg_py
    from PIL import Image, ImageDraw

    from studio.ink3d import stick2d
    out.mkdir(parents=True, exist_ok=True)
    n = max(len(v) for v in anims.values())
    gy = h * 0.86 if ground_y is None else ground_y
    lead = anims[follow]
    for i in range(n):
        cxw = lead[min(i, len(lead) - 1)]["pelvis"][0]
        figs = {}
        for name, fr in anims.items():
            if i < len(fr) and fr[i] is not None:
                figs[name] = [to_px(fr[i], w / 2 - cxw * s, gy, s)]
        sides = {k: [stick2d.near_sides([v[0]])[0]] for k, v in figs.items()}
        cov = {name: [fr[i].get("_cover", 0.0)] for name, fr in anims.items() if i < len(fr) and fr[i] is not None}
        svg = stick2d.frame_svg(figs, 0, w, h, sides, cover=cov)
        im = Image.new("RGBA", (w, h), (244, 237, 224, 255))
        dr = ImageDraw.Draw(im)
        dr.line([(0, gy), (w, gy)], fill=(120, 110, 95, 255), width=2)
        for k in range(-20, 40):                       # ground ticks show the camera motion / foot sliding
            x = w / 2 + (k * 2.0 - cxw) * s
            dr.line([(x, gy), (x, gy + 10)], fill=(120, 110, 95, 255), width=2)
        if props:
            props(dr, i, lambda x, y, c=cxw: (w / 2 + (x - c) * s, gy - y * s))
        fg = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert("RGBA")
        im.alpha_composite(fg)
        dr = ImageDraw.Draw(im)
        dr.text((10, 10), f"{i} {i / FPS:.2f}s", fill=(0, 0, 0, 255))
        im.convert("RGB").save(out / f"{i + 1:04d}.png")
    mp4 = out.with_suffix(".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(out / "%04d.png"), "-c:v",
                    "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    return mp4


def sheet(mp4: Path, t0: float, t1: float, out: Path, cols: int = 10, width: int = 216, fps: int = 30) -> None:
    n = int(round((t1 - t0) * fps))
    rows = max(1, math.ceil(n / cols))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(mp4), "-vf",
                    f"fps={fps},scale={width}:-1,tile={cols}x{rows}", "-frames:v", "1", str(out)], check=True)


def dump(path: Path, figures: dict, marks: dict) -> None:
    """figures = {name: world frames (R)} -> JSON for the Blender scene (mocap units); marks in R are converted
    by the caller."""
    data = {"figures": {k: to_mocap(fr) for k, fr in figures.items()}, "marks": marks,
            "r_unit": R_UNIT}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


if __name__ == "__main__":
    mod, fn = sys.argv[1].split(":")
    res = getattr(importlib.import_module(mod), fn)()
    preview(res, Path(sys.argv[2]))


def sliding(frames: list[dict], tol: float = 0.05) -> list[tuple[int, str, float]]:
    """QA: frames where a contact point on the ground in two consecutive frames moved (feet sliding), in R."""
    out = []
    for i in range(1, len(frames)):
        a, b = contacts(frames[i - 1]), contacts(frames[i])
        for k in a:
            if a[k][1] < tol and b[k][1] < tol and abs(b[k][0] - a[k][0]) > 0.04:
                out.append((i, k, round(b[k][0] - a[k][0], 3)))
    return out
