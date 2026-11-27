"""Ink Mindset skits: short A|B scenes (~7.4 s) animated pose to pose (pose2d) and drawn by stage2d.

Each skit function returns {"top": Half, "bottom": Half, "pay": payoff time (local s)}; top = the weak choice, bottom
= the strong one; both start the same way. Poses are authored at 30 fps and up-sampled to 60.

Every skit has its own place (a painted plate in projects/ink_proto3d/bg + a matching ground from ink3d.ground) and
the weak side does something different each time - backs off, walks away, flees, freezes, waits, gets squeezed,
sleeps, stands idle - so no two skits look alike.

    python -m studio.ink3d.skits <skit> [top|bottom|both]      renders projects/ink_skits/<skit>_<half>.mp4
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from studio.ink3d import moves as M
from studio.ink3d import stage2d as S
from studio.ink3d.pose2d import FPS, Anim, full, world
from studio.ink3d.rift_anim import LOOK_DOWN, SIT, SLUMP, SQUAT, idx, pad, upsample

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "projects" / "ink_skits"
SKIT_DUR = 7.4
UP = S.FPS // FPS                                     # 30 fps poses -> 60 fps frames
HORIZON = 0.48                                        # the location plates have their horizon at 48 % of the height
SAFE_TOP = 300                                        # plate px: keep props below this - the label band + the punch-in
_ = SIT, SLUMP


def up(frames):
    return upsample(frames, UP)


def follow(frames, ahead=1.5, lo=-1e9, hi=1e9, smooth=18, y=S.CAM_Y, zoom=1.0):
    """Camera that tracks a figure's pelvis (60 fps frames), clamped to [lo, hi], softened."""
    xs = [min(hi, max(lo, (f["pelvis"][0] if f else 0.0) + ahead)) for f in frames]
    sm = _smooth(xs, smooth)
    return lambda i: (sm[min(i, len(sm) - 1)], y, zoom)


def _smooth(xs, n):
    out = []
    for i in range(len(xs)):
        a, b = max(0, i - n), min(len(xs), i + n + 1)
        out.append(sum(xs[a:b]) / (b - a))
    return out


def turn_back(a: Anim, pose: dict) -> Anim:
    """He turns round (yaw 0 -> 180 in 0.2 s); returns a new Anim facing -x that starts where he stands."""
    a.to({**pose, "yaw": 90}, 0.1, "in")
    a.to({**pose, "yaw": 180}, 0.1, "out")
    world(a)
    b = Anim(x0=a.roots[-1][0], facing=-1)
    b.hold(1 / FPS, pose)
    return b


def stone_shape(x, k, seed):
    """An irregular ink stepping stone, its top flush with y = 0, grown by k (0..1)."""
    rnd = random.Random(seed)
    w, h = 2.6 * k, 1.7 * k
    pts = [(x - w / 2, 0.0), (x + w / 2, 0.0)]
    for j in range(7):                                  # the rough underside
        a = math.pi * (j + 1) / 8
        rr = 0.75 + 0.35 * rnd.random()
        pts.append((x + math.cos(a) * w / 2 * rr, -math.sin(a) * h * rr))
    return pts


def cliff_face(P, e, side, gid, seed=4):
    """A rock wall falling away from a brink at x = e (side -1: the rock is left of e, +1: right of it): an ink wash
    that fades with depth, its chasm edge broken and jagged. The ground line itself stays on top."""
    rnd = random.Random(seed + (1 if side > 0 else 0))
    edge = [(e, -0.15)]
    y = -0.15
    while y > -11:
        y -= rnd.uniform(0.6, 1.4)
        edge.append((e + side * rnd.uniform(0.0, 0.9) - side * 0.15 * (-y) ** 0.5, y))
    far = e + side * 60
    pts = edge + [(far, edge[-1][1]), (far, -0.15)]
    (_, y0), (_, y1) = P(0, -0.15), P(0, -11)
    q = " ".join(f"{a:.1f},{b:.1f}" for a, b in (P(x, yy) for x, yy in pts))
    hatch = "".join(S.line(P, 1.0 * (P(1, 0)[0] - P(0, 0)[0]), [(e + side * 0.3 - side * k * 0.05, -0.5 - k * 1.1),
                                                              (e + side * (0.9 + 0.4 * rnd.random()), -0.9 - k * 1.1)],
                           width=0.07, opacity=0.5 * (1 - k / 8)) for k in range(7))
    return (f'<defs><linearGradient id="{gid}" x1="0" y1="{y0:.1f}" x2="0" y2="{y1:.1f}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{S.INK}" stop-opacity="0.92"/><stop offset="0.55" stop-color="{S.INK}" '
            f'stop-opacity="0.45"/><stop offset="1" stop-color="{S.INK}" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="{q}" fill="url(#{gid})"/>' + hatch)


# a true one-knee kneel: back knee and shin on the ground, the back foot lying flat behind, the front foot flat
# (found by searching the solved world pose: knee y 0.27, both ankles 0.32)
KNEEL_LEGS = {"thR": 95, "knR": 95, "ftR": -10, "thL": -12, "knL": 80, "ftL": -90}
STEP_BACK = {"lean": -4, "nod": 10, "thR": 14, "knR": 10, "thL": -26, "knL": 14, "ftL": -14, "arR": 10, "elR": 20,
             "arL": -10, "elL": 20}                    # weight on the front foot, the back foot reaching back
STEP_FWD = {"lean": 10, "nod": 0, "thR": 30, "knR": 12, "thL": -16, "knL": 18, "ftL": -10, "arR": 40, "elR": 50,
            "arL": 30, "elL": 40}                      # one step forward, right foot leading
LUNGE_UP = {"lean": 22, "nod": 0, "thR": 60, "knR": 60, "ftR": 0, "thL": -28, "knL": 30, "ftL": -40}

THINK = {"lean": 4, "nod": 14, "arR": 58, "elR": 138, "arL": 48, "elL": 96, "thR": 4, "knR": 6, "thL": -4,
         "knL": 6}                                     # hand to the chin, the other arm across the waist


# ================================================================ PLAN IT | STEP IN  (cliffs, rock ledge)
def steps():
    """Both walk up to a chasm in the mountains. Top stops at the brink, looks down, backs off and stands there
    thinking it over. Bottom walks straight out over the void - an ink stone blooms under every step - and lands on
    the far side on the drop."""
    PAY = 5.06
    T = SKIT_DUR
    b = Anim(x0=-6.0)
    b.cycle(M.WALK, T + 0.3, phase=0.1, blend=0.0)
    bw = world(b)
    i_edge = idx(1.35)
    edge = max(bw[i_edge]["toeR"][0], bw[i_edge]["toeL"][0]) + 0.3
    far = bw[idx(PAY)]["pelvis"][0] - 0.4                 # he steps onto the far side on the drop
    stones = []
    for side in "LR":
        on = False
        for i, J in enumerate(bw):
            low = min(J["ankle" + side][1] - 0.28, J["toe" + side][1] - 0.22)
            x = J["ankle" + side][0]
            if low < 0.03 and not on and edge < x < far:
                stones.append((i, x + 0.25))
            on = low < 0.03
    # top: the same walk, a dead stop at the brink, a look down - then two steps back, and he stays there, thinking
    t = Anim(x0=-6.0)
    t.cycle(M.WALK, 1.15, phase=0.1, blend=0.0, end="pass")
    t.to(M.STAND, 0.3, "out")
    t.to(LOOK_DOWN, 0.35, "io")
    t.hold(0.35, breathe=0.5)
    t.to({**M.STAND, "lean": -4, "nod": 6}, 0.2, "out")         # a start: too deep
    t.to(STEP_BACK, 0.35, "io")                                  # one step back from the edge
    t.to({**M.STAND, "lean": -2}, 0.35, "io")                    # and the front foot joins it
    t.to(THINK, 0.4, "io")
    t.hold(max(0.0, 4.6 - t.n / FPS), breathe=0.6)
    t.to({**THINK, "nod": 19, "lean": 7}, 0.35, "io")            # still weighing it up
    t.hold(0.6, breathe=0.5)
    t.to(THINK, 0.4, "io")
    pad(t, T, breathe=0.6)
    tw = world(t)
    t_edge = max(tw[idx(1.6)]["toeR"][0], tw[idx(1.6)]["toeL"][0]) + 0.35

    def cliffs(P, e, f):
        return cliff_face(P, e, -1, "cl") + cliff_face(P, f, 1, "cr")

    def props_b(i, tt, P, s):
        out = [cliffs(P, edge, far)]
        for fi, x in stones:
            k = (i - fi * UP + 8) / 8                      # blooms over ~8 frames (60 fps) before the foot lands
            if k <= 0:
                continue
            k = S.ease(min(1.0, k))
            out.append(S.poly(P, stone_shape(x, k, fi), S.INK, opacity=0.3 + 0.7 * k))
        return "".join(out), ""

    def props_t(i, tt, P, s):
        return cliffs(P, t_edge, t_edge + (far - edge)), ""

    bu, tu = up(bw), up(tw)
    gap = far - edge
    bottom = S.Half(T, {"hero": bu}, cam=follow(bu, ahead=1.2), props=props_b, plate="plate_cliff",
                    ground=[(-1e9, edge), (far, 1e9)], tone=lambda tt: "rock")
    top = S.Half(T, {"hero": tu}, cam=follow(tu, ahead=1.2, hi=t_edge + gap / 2 - 1.0), props=props_t,
                 plate="plate_cliff", ground=[(-1e9, t_edge), (t_edge + gap, 1e9)], tone=lambda tt: "rock",
                 bright=S.keys([(0, 1.0), (PAY, 1.0), (T, 0.85)]))
    return {"top": top, "bottom": bottom, "pay": PAY}


# ================================================================ QUIT | REST  (desert, sand)
HANDS_KNEES = {"lean": 50, "nod": -12, "thR": 22, "knR": 30, "ftR": 0, "thL": -8, "knL": 26, "ftL": 0,
               "arR": 8, "elR": 64, "arL": 12, "elL": 20}            # palms on the knees


def rest():
    """Both run through the desert until they are spent and stop, hands on knees, gasping. Top straightens up, turns
    round and trudges back the way he came. Bottom gets his breath back, looks ahead - and runs on, on the beat."""
    PAY = 5.16
    T = SKIT_DUR

    def base():
        a = Anim(x0=-8.0)
        ph = a.cycle(M.JOG, 1.4, phase=0.2, blend=0.0, mods={"lean": 6, "nod": 10})
        a.cycle(M.TRUDGE, 0.8, phase=ph % 1, blend=0.35, end="pass")
        a.to(M.STAND, 0.2, "out")
        a.to(HANDS_KNEES, 0.35, "io")
        return a
    t = base()
    t.hold(1.3, breathe=1.8)
    t.to({**M.STAND, "nod": 22, "lean": 6}, 0.45, "io")             # straightens up, head down
    t.hold(0.35, breathe=0.6)
    t2 = turn_back(t, {**M.STAND, "nod": 22, "lean": 6})
    t2.cycle(M.TRUDGE, T - t.n / FPS + 0.3, phase=0.25, blend=0.2, rate=0.9)
    tw = world(t) + world(t2)[1:]
    b = base()
    b.hold(PAY - 0.75 - b.n / FPS, breathe=1.8)
    b.to({**HANDS_KNEES, "nod": -30, "lean": 44}, 0.25, "out")     # head up: eyes on the road ahead
    b.to({**M.STAND, "lean": 14}, 0.3, "io")
    b.hold(0.1)
    b.cycle(M.SPRINT, T - b.n / FPS + 0.2, phase=0.62, ramp=(1.5, 1.15), blend=0.1)
    bw = world(b)
    tu, bu = up(tw), up(bw)
    stop_x = tw[idx(2.9)]["pelvis"][0]
    top = S.Half(T, {"hero": tu}, cam=follow(tu, ahead=-0.6, lo=stop_x - 9.0, hi=stop_x + 0.6, smooth=24),
                 plate="plate_desert", tone=lambda tt: "sand",
                 bright=S.keys([(0, 1.0), (PAY, 1.0), (T, 0.8)]))
    bottom = S.Half(T, {"hero": bu}, cam=follow(bu, ahead=1.4, lo=stop_x - 9.0), plate="plate_desert",
                    tone=lambda tt: "sand")
    return {"top": top, "bottom": bottom, "pay": PAY}


# ================================================================ AVOID IT | FACE IT  (bamboo grove)
SCARED = {"lean": -8, "nod": -10, "thR": 14, "knR": 14, "thL": -14, "knL": 16, "arR": 40, "elR": 90,
          "arL": 30, "elL": 80}


def scale_frames(frames, ks, ax):
    """Per-frame scale about the ground point under ax (a giant that grows or shrinks)."""
    out = []
    for f, k in zip(frames, ks, strict=False):
        if f is None or k <= 0:
            out.append(None)
            continue
        out.append({**{j: (ax + (v[0] - ax) * k, v[1] * k, v[2] * k) for j, v in f.items() if not j.startswith("_")},
                    "_hr": k})
    return out


def fear():
    """A giant ink shadow blocks the path through the bamboo. Top turns and runs - and it comes after him, step for
    step. Bottom walks at it; the closer he gets, the smaller it is - on the beat it is a pebble, and he steps over
    it."""
    from studio.ink3d.rift_anim import G_TALL
    PAY = 6.24
    T = SKIT_DUR
    G0 = 2.6
    Z = 0.6

    def approach(a):
        a.cycle(M.WALK, 1.2, phase=0.1, blend=0.0, end="pass")
        a.to(SCARED, 0.25, "out")
        a.hold(0.5, breathe=1.2)
    b = Anim(x0=-5.0)
    approach(b)
    b.to({**M.STAND, "nod": 14, "lean": 6}, 0.3, "io")
    b.cycle(M.WALK, T - b.n / FPS + 0.2, phase=0.75, blend=0.2, rate=0.66, mods={"lean": 4})   # steady, not hurried
    bw = world(b)
    gx = bw[idx(PAY)]["pelvis"][0] + 1.6                 # the pebble lies just ahead of him on the beat
    t = Anim(x0=-5.0)
    approach(t)
    t_turn = t.n / FPS
    t2 = turn_back(t, {**M.STAND, "nod": -6})
    t2.cycle(M.SPRINT, T - t.n / FPS + 0.2, phase=0.25, blend=0.15)
    tw = world(t) + world(t2)[1:]
    tu, bu = up(tw), up(bw)
    n = len(bu)

    def giant(rate):
        g = Anim(x0=0.0, facing=-1)
        g.hold(t_turn + 0.25, G_TALL, breathe=1.2)
        g.cycle(M.WALK, T - g.n / FPS + 0.3, phase=0.1, blend=0.3, rate=rate, mods={"lean": 6, "nod": 10})
        gw = up(world(g))
        return [{j: (v[0] + gx, v[1], v[2]) if isinstance(v, tuple) else v for j, v in f.items()} for f in gw]
    # the giant keeps pace with him: its walk rate set from his running speed
    g1 = giant(1.0)
    i0, i1 = int((t_turn + 1.2) * S.FPS), min(len(tu), len(g1)) - 1
    v_h = (tu[i0]["pelvis"][0] - tu[i1]["pelvis"][0]) / max(1, i1 - i0)
    v_g = (g1[i0]["pelvis"][0] - g1[i1]["pelvis"][0]) / max(1, i1 - i0) * G0
    gt = giant(min(1.6, max(0.6, 0.92 * v_h / max(1e-6, v_g))))
    g_top = scale_frames(gt, [G0] * len(gt), gx)
    g_still = giant(1.0)[: int((t_turn + 0.25) * S.FPS)]
    g_still += [g_still[-1]] * (n - len(g_still))
    k_bot = [G0 + (0.16 - G0) * S.ease((i / S.FPS - 2.4) / (PAY - 2.4)) if i / S.FPS < PAY else 0.0
             for i in range(n)]
    g_bot = scale_frames(g_still, k_bot, gx)

    def props_b(i, tt, P, s):
        if tt < PAY - 0.05:
            return "", ""
        return S.poly(P, [(gx - 0.7, 0.0), (gx - 0.4, 0.45), (gx + 0.3, 0.55), (gx + 0.75, 0.0)], S.INK), ""
    stand_x = bw[idx(1.6)]["pelvis"][0]
    cy = 1066 / (S.PPM * Z) * 0.36                       # ground at ~86 % of the frame height
    hw = S.W / 2 / (S.PPM * Z)
    c_start = (stand_x + gx) / 2 + 1.0
    xs = []
    for i in range(n):                                   # frame the pair; never let him run out of the left side
        hx = tu[min(i, len(tu) - 1)]["pelvis"][0]
        gxi = g_top[min(i, len(g_top) - 1)]["pelvis"][0]
        xs.append(min(c_start, (hx + gxi) / 2 + 1.0, hx + hw - 4.5))
    cam_t = _smooth(xs, 20)
    top = S.Half(T, {"hero": tu, "shadow": g_top}, cam=lambda i: (cam_t[min(i, n - 1)], cy, Z),
                 plate="plate_bamboo", bright=S.keys([(0, 1.0), (2.0, 1.0), (T, 0.62)]))

    def cam_b(i):
        hx = bu[min(i, n - 1)]["pelvis"][0]
        return (max(c_start, (hx + gx) / 2 + 1.0), cy, Z)
    bottom = S.Half(T, {"hero": bu, "shadow": g_bot}, cam=cam_b, props=props_b, plate="plate_bamboo",
                    bright=S.keys([(0, 1.0), (2.4, 0.85), (PAY, 1.05)]))
    return {"top": top, "bottom": bottom, "pay": PAY}


# ================================================================ WAIT FOR CALM | RISE 8  (snowy pass)
KNOCKED = {"lean": -26, "rot": -6, "nod": -24, "thR": 30, "knR": 20, "thL": -6, "knL": 30, "arR": -60, "elR": 40,
           "arL": 96, "elL": 30}
KNEEL = {"lean": 22, "nod": 16, "thR": 70, "knR": 96, "ftR": 10, "thL": -4, "knL": 116, "ftL": -40, "arR": 50,
         "elR": 20, "arL": 20, "elL": 30}
BRACE = {"lean": 30, "nod": -8, "thR": 42, "knR": 52, "ftR": 8, "thL": -40, "knL": 10, "ftL": -40, "arR": 60,
         "elR": 96, "arL": 44, "elL": 96}
TALL = {"lean": -6, "nod": -14, "thR": 10, "knR": 6, "thL": -10, "knL": 6, "arR": -4, "elR": 18, "arL": 4,
        "elL": 20}
HUDDLE = {"lean": 38, "nod": 40, "thR": 96, "knR": 140, "ftR": 20, "thL": 92, "knL": 136, "ftL": 20,
          "arR": 70, "elR": 60, "arL": 60, "elL": 70}
HUNCH = {"lean": 14, "nod": 32, "thR": 8, "knR": 18, "thL": -6, "knL": 16, "arR": 14, "elR": 100, "arL": 8,
         "elL": 106}                                   # back to the wind, arms wrapped round himself
FALLS = [0.55, 1.35, 2.05, 2.7, 3.25, 3.75, 4.2]       # seven gusts knock him down; the eighth (5.2) doesn't
HIT = {**BRACE, "lean": 4, "nod": -22, "ftL": -80, "arR": 116, "elR": 112, "arL": 104, "elL": 120}   # whipped back
KNEEL_W = {"lean": 18, "nod": 22, **KNEEL_LEGS, "arR": 110, "elR": 112, "arL": 98, "elL": 118}


def knock(a: Anim, room: float):
    """One gust: the torso is whipped back, arms up over the face, and he is driven down onto one knee - in place,
    the front foot never leaves the ground - then pushes back up into the brace. Fits in `room` seconds."""
    k = min(1.0, max(0.55, room / 0.6))
    a.to(HIT, 0.09 * k, "out", anchor="ankleR")
    a.to(KNEEL_W, 0.17 * k, "in", anchor="ankleR")
    a.hold(0.07 * k)
    a.to({**BRACE, "ftL": -80}, 0.25 * k, "io", anchor="ankleR")  # up; the back foot rolls back onto its toes
    a.to(BRACE, 0.08 * k, "io", anchor="ankleR")


def gust(t):
    """Wind strength 0..1 (gusts on the falls, the big one before the beat, calm after it)."""
    PAY = 6.25
    if t >= PAY:
        return max(0.0, 1 - (t - PAY) / 0.25) * 0.8
    w = 0.35
    for g in FALLS + [5.2]:
        w = max(w, math.exp(-((t - g + 0.05) / 0.16) ** 2))
    if 5.0 <= t < PAY:
        w = max(w, 0.95)
    return w


def wind_svg(P, s, tt, seed=5, cutoff=None, calm=None, part="both"):
    """Ink wind streaks and snow blowing right to left; density and opacity follow gust(t) (or `calm` steady).
    part: "streaks" (drawn behind the figures - never a line across a face), "flakes" (in front), "both"."""
    rnd = random.Random(seed)
    w = (gust(tt) if calm is None else calm) if cutoff is None else min(gust(tt), cutoff)
    out = []
    for _k in range(40):
        y = rnd.uniform(0.3, 11.0)
        ln = rnd.uniform(1.5, 4.5)
        sp = rnd.uniform(26, 40)
        ph = rnd.uniform(0, 40)
        x = 30 - ((tt * sp + ph) % 60)
        if rnd.random() > 0.25 + 0.75 * w:
            continue
        if part != "flakes":
            out.append(S.line(P, s, [(x, y), (x + ln * 0.5, y + 0.04), (x + ln, y + 0.12)], width=0.12,
                              stroke=S.STONE, opacity=0.3 + 0.5 * w))
    for _k in range(70):                                 # flakes
        y0 = rnd.uniform(-1.0, 12.0)
        sp = rnd.uniform(18, 30)
        ph = rnd.uniform(0, 50)
        x = 30 - ((tt * sp + ph) % 60)
        y = y0 - ((tt * 2.0 + ph) % 13.0) + 0.4 * math.sin(tt * 3 + ph)
        if y < 0.05 or rnd.random() > 0.3 + 0.7 * w or part == "streaks":
            continue
        out.append(S.disc(P, s, x, y, rnd.uniform(0.06, 0.13), "#FFFFFF", opacity=0.9))
        out.append(S.ring(P, s, x, y, rnd.uniform(0.07, 0.13), width=0.03, stroke=S.STONE, opacity=0.5))
    return "".join(out)


def drift(P, s, x, h, w=2.4):
    """A snowdrift piled against his legs (h = height in R)."""
    if h <= 0.02:
        return ""
    pts = [(x - w, 0.0)] + [(x - w + 2 * w * j / 12, h * math.sin(math.pi * j / 12) ** 0.8) for j in range(13)] + \
          [(x + w, 0.0)]
    q = " ".join(f"{a:.1f},{b:.1f}" for a, b in (P(px, py) for px, py in pts))
    return (f'<polygon points="{q}" fill="#FBF8F2" stroke="{S.STONE}" stroke-width="{0.06 * s:.1f}" '
            f'stroke-linejoin="round"/>')


def wind():
    """A blizzard on a mountain pass. Top turns his back on it, wraps his arms round himself and waits for calm - the
    snow piles up round his legs. Bottom walks into it: knocked down seven times, up seven times - the eighth gust
    doesn't move him; on the beat the wind drops and the sun comes up."""
    PAY = 6.25
    T = SKIT_DUR
    b = Anim(x0=0.0)
    b.to(BRACE, 0.2, "out")
    for k, g in enumerate(FALLS):
        b.hold(max(0.0, g - 0.05 - b.n / FPS), breathe=0.3)
        nxt = FALLS[k + 1] if k + 1 < len(FALLS) else 5.0
        knock(b, nxt - g - 0.06)
    b.hold(max(0.0, 5.0 - b.n / FPS), breathe=0.3)
    b.to({**BRACE, "lean": 38, "knR": 64}, 0.2, "out")           # the eighth gust: he takes it
    for k in range(int((PAY - 0.15 - b.n / FPS) * FPS)):
        b.frames.append({"pose": {**full({**BRACE, "lean": 38, "knR": 64}),
                                  "lean": 38 + 1.5 * math.sin(k * 1.7)}, "mode": "plant"})
    b.to(TALL, 0.35, "out")                                      # the wind drops: he stands up straight
    pad(b, T, breathe=0.8)
    bw = world(b)
    t = Anim(x0=0.0)
    t.to(BRACE, 0.2, "out")
    t.hold(max(0.0, FALLS[0] - 0.05 - t.n / FPS), breathe=0.3)
    t.to(HIT, 0.09, "out", anchor="ankleR")                       # the first gust - and he has had enough
    t.to(KNEEL_W, 0.17, "in", anchor="ankleR")
    t.hold(0.25)
    t.to(LUNGE_UP, 0.3, "io", anchor="ankleR")
    t.to(M.STAND, 0.3, "io", anchor="ankleR")
    t2 = turn_back(t, {**M.STAND, "nod": 10})
    t2.to(HUNCH, 0.45, "io")
    t2.hold(T - t.n / FPS - t2.n / FPS + 0.2, breathe=0.7)
    tw = world(t) + world(t2)[1:]
    tu, bu = up(tw), up(bw)
    hx = tu[-1]["pelvis"][0]

    def props_t(i, tt, P, s):
        h = 2.0 * S.ease((tt - 1.6) / 5.6)
        return wind_svg(P, s, tt, seed=7, calm=0.85, part="streaks"), (drift(P, s, hx + 0.2, h) +
                                                                       wind_svg(P, s, tt, seed=7, calm=0.85,
                                                                                part="flakes"))

    cam_b = follow(up(bw), ahead=1.6, smooth=40)
    sun_x = cam_b(int(PAY * S.FPS))[0] + 4.6                    # where the camera is when the wind drops

    def props_b(i, tt, P, s):
        sun = ""
        if tt > PAY - 0.35:
            k = S.ease((tt - PAY + 0.35) / 0.55)                        # up within half a second of the beat
            sun = S.sun(P, s, sun_x, -1.0 + 7.4 * k, 1.5, horizon=HORIZON)
        return wind_svg(P, s, tt, seed=11, part="streaks") + sun, wind_svg(P, s, tt, seed=11, part="flakes")
    top = S.Half(T, {"hero": tu}, cam=lambda i: (hx - 0.6, S.CAM_Y, 1.0), props=props_t,
                 plate="plate_snow", tone=lambda tt: "snow", bright=S.keys([(0, 0.85), (T, 0.6)]))
    bottom = S.Half(T, {"hero": bu}, cam=cam_b, props=props_b, plate="plate_snow",
                    tone=lambda tt: "snow", bright=S.keys([(0, 0.85), (PAY - 0.1, 0.8), (PAY + 0.6, 0.97)]))
    return {"top": top, "bottom": bottom, "pay": PAY}


# ================================================================ shared helpers for Short #3
def plants(frames, t_from=0.0, fps=S.FPS):
    """Foot plants in 60 fps world frames after t_from: [(frame, x)] when a foot touches down."""
    out = []
    for side in "LR":
        on = False
        for i, J in enumerate(frames):
            if J is None:
                continue
            low = min(J["ankle" + side][1] - 0.28, J["toe" + side][1] - 0.22)
            if low < 0.03 and not on and i / fps >= t_from:
                out.append((i, J["ankle" + side][0] + 0.2))
            on = low < 0.03
    return sorted(out)


def overlay(a: Anim, t0: float, t1: float, arms: dict, ramp: float = 0.2):
    """Lay an arm action over a span of frames (blends in/out over `ramp` s)."""
    i0, i1 = idx(t0), min(a.n, idx(t1))
    r = max(1, int(ramp * FPS))
    for i in range(i0, i1):
        w = min(1.0, (i - i0 + 1) / r, (i1 - i) / r) if t1 < 90 else min(1.0, (i - i0 + 1) / r)
        a.frames[i]["arms"], a.frames[i]["arms_w"] = arms, max(0.0, w)


# ================================================================ WAIT FOR LIGHT | BE THE LIGHT  (old town at night)
KNEEL_LOW = {"lean": 30, "nod": 26, **KNEEL_LEGS, "arR": 62, "elR": 40, "arL": 50, "elL": 50}   # striking a light
LANTERN_UP = {"arR": 112, "elR": 20}                          # the flame held up high
ARMS_X = {"arR": 14, "elR": 100, "arL": 8, "elL": 106}       # arms folded


def street_lamp(P, s, px):
    """A wooden lamp post with a dead paper lantern hanging from its arm (world x of the post)."""
    lx = px - 2.9
    return (S.line(P, s, [(px, 0.0), (px, 8.6)], width=0.22, cap="butt") +
            S.line(P, s, [(px + 0.1, 8.4), (lx - 0.4, 8.4)], width=0.16) +
            S.line(P, s, [(lx, 8.4), (lx, 8.1)], width=0.05) +
            S.rect(P, lx - 0.38, 6.9, lx + 0.38, 8.1, "#3A3630") +
            S.rect(P, lx - 0.46, 8.0, lx + 0.46, 8.16, S.INK) + S.rect(P, lx - 0.46, 6.84, lx + 0.46, 6.98, S.INK))


def flame_svg(px: float, py: float, r: float, tt: float, op: float = 1.0, drag: float = 0.0) -> str:
    """A living flame (screen px, base radius r px): the body leans and its tip sways and stretches with
    out-of-step sines, a side tongue licks up and dies, the warm core trembles on its own beat, and small
    embers rise, drift and fade. drag (-1..1) bends the whole flame back against the hand's motion."""
    def wob(f1, f2, ph):
        return 0.6 * math.sin(tt * f1 + ph) + 0.4 * math.sin(tt * f2 + 1.7 * ph)

    def tongue(cx, rr, h, sway, col, o, wid=1.0):
        sway = sway + drag * 0.6
        tip_x, tip_y = cx + sway * rr, py - h * rr
        rr_w = rr * wid
        mid = 0.55 * sway * rr
        return (f'<path d="M{cx:.1f},{py + rr:.1f} C{cx - 1.25 * rr_w:.1f},{py + rr:.1f} {cx - 0.95 * rr_w + mid:.1f},'
                f'{py - 0.5 * rr:.1f} {tip_x:.1f},{tip_y:.1f} C{cx + 0.95 * rr_w + mid:.1f},{py - 0.5 * rr:.1f} '
                f'{cx + 1.25 * rr_w:.1f},{py + rr:.1f} {cx:.1f},{py + rr:.1f} Z" fill="{col}" opacity="{o:.3f}"/>')
    out = []
    for side, f0, ph in ((1, 6.1, 0.0), (-1, 4.7, 2.0)):      # side tongues that lick up and die, out of step
        lick = max(0.0, math.sin(tt * f0 + ph)) ** 1.5
        out.append(tongue(px + side * 0.5 * r, r * 0.48, 1.6 + 2.2 * lick, side * (0.7 + 0.6 * wob(13, 23, ph)),
                          S.VERM, op * (0.25 + 0.75 * lick)))
    out.append(tongue(px, r, 2.3 + 0.9 * wob(11, 19, 0.0), 1.0 * wob(7, 15, 1.0), S.VERM, op,
                      wid=1 + 0.12 * wob(21, 33, 6.0)))
    h_out = 2.3 + 0.9 * wob(11, 19, 0.0)                     # the core follows the body: never pokes out of it
    out.append(tongue(px + 0.08 * r * wob(17, 29, 3.0), r * 0.55, 0.62 * h_out + 0.25 * wob(14, 27, 4.0),
                      1.0 * wob(7, 15, 1.0) / 0.55 * 0.5 + 0.15 * wob(9, 21, 5.0), "#FFD9A0", op))
    for j in range(5):                                         # embers: born at the tip, rise and fade in ~0.7 s
        life = (tt * 1.4 + j / 5) % 1.0
        ex = px + r * (0.6 * math.sin(j * 2.3 + tt * 3) + 0.9 * life * math.sin(j * 1.7))
        ey = py - r * (2.2 + 4.0 * life)
        out.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="{max(0.8, 0.12 * r * (1 - life)):.1f}" '
                   f'fill="#F2A060" opacity="{op * (1 - life) * 0.9:.3f}"/>')
    return "".join(out)


def lantern():
    """Night in the old town; the street lantern is dead. Both stop under it and look up. Top folds his arms and
    waits for someone to light it. Bottom kneels, strikes a light - on the drop a vermilion lantern flares in his
    raised hand and he walks on, leaving glowing steps behind him."""
    PAY = 5.06
    T = SKIT_DUR

    def start():
        a = Anim(x0=-4.0)
        a.cycle(M.TRUDGE, 1.4, phase=0.1, blend=0.0, end="pass")
        a.to(M.STAND, 0.25, "out")
        a.to({**M.STAND, "nod": -22, "lean": -4}, 0.4, "io")     # looks up at the dead lantern
        a.hold(0.3, breathe=0.6)
        return a
    t = start()
    t.to({**M.STAND, **ARMS_X, "nod": -6}, 0.45, "io")            # folds his arms: someone will come
    t.hold(1.2, breathe=0.6)
    t.to({**M.STAND, **ARMS_X, "nod": -24, "lean": -3}, 0.4, "io")
    t.hold(0.9, breathe=0.5)
    t.to({**M.STAND, **ARMS_X, "nod": 18, "lean": 6}, 0.6, "io")  # nothing. head drops
    pad(t, T, breathe=0.5)
    tw = world(t)
    post = tw[idx(2.0)]["pelvis"][0] + 7.0                      # clear of him even when he kneels
    b = start()
    b.to(STEP_FWD, 0.24, "io")
    b.to({**LUNGE_UP, "arR": 40, "elR": 40}, 0.2, "io", anchor="ankleR")     # step, lunge, down onto the knee
    b.to(KNEEL_LOW, 0.3, "io", anchor="ankleR")
    b.hold(PAY - 0.55 - b.n / FPS, breathe=0.4)
    b.to(LUNGE_UP, 0.28, "io", anchor="ankleR")                  # up off the knee over the front foot
    b.to({**M.STAND, "lean": 4}, 0.24, "io", anchor="ankleR")
    b.cycle(M.WALK, T - b.n / FPS + 0.2, phase=0.75, blend=0.2, rate=0.9)
    T_STRIKE = (idx(3.15) / FPS, PAY - 0.95)                       # kneeling: strikes sparks
    T_FLAME = PAY - 1.0                                            # the flame catches in his hands
    # from the moment the flame catches he cups it in front of his chest (both palms), carries it up as he
    # rises, and on the beat lifts it high - one continuous arm line, never hanging at the thigh
    CUP_R, CUP_L = {"arR": 52, "elR": 68}, {"arL": 40, "elL": 70}    # both hands out in front, the flame on the palm
    i0, i_up = idx(T_FLAME - 0.25), idx(PAY - 0.08)
    n_up = idx(0.2)
    for i in range(i0, b.n):
        if i < i_up:
            w = min(1.0, (i - i0 + 1) / idx(0.25))
            b.frames[i]["arms"], b.frames[i]["arms_w"] = {**CUP_R, **CUP_L}, w
        else:
            u = S.ease(min(1.0, (i - i_up + 1) / n_up))
            arms = {k: CUP_R[k] + (LANTERN_UP[k] - CUP_R[k]) * u for k in CUP_R}
            base = full(b.frames[i]["pose"])                           # the free hand drops back into the walk
            arms.update({k: CUP_L[k] + (base[k] - CUP_L[k]) * u for k in CUP_L})
            b.frames[i]["arms"], b.frames[i]["arms_w"] = arms, 1.0
    bw = world(b)
    bu, tu = up(bw), up(tw)
    steps_lit = [(i, x) for i, x in plants(bu, PAY)]

    def props_t(i, tt, P, s):
        return street_lamp(P, s, post), ""

    def props_b(i, tt, P, s):
        back = [street_lamp(P, s, post)]
        for fi, x in steps_lit:                          # glowing footprints that fade slowly
            if i < fi:
                continue
            age = (i - fi) / S.FPS
            op = max(0.0, 0.9 - 0.25 * age)
            back.append(S.disc(P, s, x, 0.05, 0.45, S.VERM, opacity=op * 0.5, glow=True))
            back.append(f'<ellipse cx="{P(x, 0.05)[0]:.1f}" cy="{P(x, 0.05)[1]:.1f}" rx="{0.55 * s:.1f}" '
                        f'ry="{0.14 * s:.1f}" fill="{S.VERM}" opacity="{op:.2f}"/>')
        front = []
        J = bu[min(i, len(bu) - 1)]
        ex, ey = J["elbR"][0], J["elbR"][1]
        wx, wy = J["wristR"][0], J["wristR"][1]
        fl_ = math.hypot(wx - ex, wy - ey) or 1.0
        wx, wy = wx + (wx - ex) / fl_ * 0.32, wy + (wy - ey) / fl_ * 0.32   # on the fingertips, not on the wrist
        if T_STRIKE[0] <= tt < T_STRIKE[1]:                      # flint sparks at his hands while he kneels
            rnd = random.Random(int(tt * 9))
            if (tt * 9) % 1 < 0.45:
                for _ in range(7):
                    a_ = rnd.uniform(0.2, 2.9)
                    ln = rnd.uniform(0.3, 0.9)
                    front.append(S.line(P, s, [(wx + 0.1, wy + 0.1), (wx + 0.1 + math.cos(a_) * ln,
                                                                       wy + 0.1 + math.sin(a_) * ln)],
                                        width=0.06, stroke="#F2B060", opacity=0.9))
        if tt >= T_FLAME:                                          # a small flame caught in his palm, then raised
            k = S.ease((tt - T_FLAME) / 0.3)
            big = S.ease((tt - PAY + 0.05) / 0.25)                 # it flares up as the arm goes up on the beat
            flare = 1.0 + 1.2 * math.exp(-((tt - PAY - 0.1) / 0.2) ** 2)
            r = (0.28 + 0.42 * big) * k
            fy = wy + 0.05 + r
            px_, py_ = P(wx, fy)
            back.append(f'<defs><radialGradient id="lp"><stop offset="0" stop-color="#FFE2B0" stop-opacity="0.55"/>'
                        f'<stop offset="0.35" stop-color="#F2A060" stop-opacity="0.22"/>'
                        f'<stop offset="1" stop-color="#F2A060" stop-opacity="0"/></radialGradient></defs>'
                        f'<circle cx="{px_:.1f}" cy="{py_:.1f}" r="{(2.0 + 6.5 * big) * k * s:.1f}" fill="url(#lp)" '
                        f'opacity="{min(1.0, k * flare / 1.2):.3f}"/>')
            Jp = bu[max(0, min(i, len(bu) - 1) - 6)]                  # the flame trails the hand's motion
            drag = max(-1.0, min(1.0, -(J["wristR"][0] - Jp["wristR"][0]) * 0.9))
            front.append(flame_svg(px_, py_, r * s, tt, k, drag))
        return "".join(back), "".join(front)
    sp = tw[idx(3.0)]["pelvis"][0]
    top = S.Half(T, {"hero": tu}, cam=follow(tu, ahead=1.0, hi=sp + 1.0), props=props_t, plate="plate_town",
                 bright=S.keys([(0, 0.5), (T, 0.36)]), tone=lambda tt: "light")
    bottom = S.Half(T, {"hero": bu}, cam=follow(bu, ahead=1.6, lo=sp + 1.0), props=props_b, plate="plate_town",
                    bright=S.keys([(0, 0.5), (PAY - 0.1, 0.48), (PAY + 0.4, 0.62)]), tone=lambda tt: "light")
    return {"top": top, "bottom": bottom, "pay": PAY}


# ================================================================ STAY SAFE | STEP OUT  (river bank)
BUB_RY = 0.85                                         # the bubble is a dome: ry = 0.85 r, centre 0.55 ry up, cut flat
BUB_Y = 0.55 * BUB_RY


def bubble():
    """Each stands inside an ink bubble by the river. Top stays: the bubble slowly closes in until he has to crouch.
    Bottom walks up to its wall, leans on it, pushes - on the beat it bursts and he steps out into the open."""
    PAY = 5.16
    T = SKIT_DUR
    R0 = 6.3
    t = Anim(x0=0.0)
    t.hold(1.2, M.STAND, breathe=0.6)
    t.to({**M.STAND, "nod": -18}, 0.4, "io")                     # looks up: the wall is closer
    t.hold(0.8, breathe=0.5)
    t.to({**SQUAT, "nod": -10}, 0.6, "io")                       # forced down
    t.hold(0.6, breathe=0.5)
    t.to(HUDDLE, 1.0, "io")
    pad(t, T, breathe=0.6)
    tw = world(t)
    c0 = tw[0]["pelvis"][0] + 0.3
    b = Anim(x0=0.0)
    b.hold(0.5, M.STAND, breathe=0.6)
    b.to({**M.STAND, "nod": -10}, 0.3, "io")
    from studio.ink3d.rift_anim import PUSH
    b.to(STEP_FWD, 0.28, "io")                                     # one step and he leans into the wall
    b.to(PUSH, 0.3, "out")
    T_PUSH = b.n / FPS - 0.12                                       # palms meet the wall
    b.hold(PAY - 0.1 - b.n / FPS, breathe=0.2)
    b.to({**PUSH, "lean": 46}, 0.1, "snap")
    b.cycle(M.WALK, T - b.n / FPS + 0.2, phase=0.25, blend=0.2)
    bw = world(b)
    tu, bu = up(tw), up(bw)
    ip = int((PAY - 0.6) * S.FPS)
    J = bu[ip]
    hand_push, hand_y = max(J["wristR"][0], J["wristL"][0]), max(J["wristR"][1], J["wristL"][1])
    # the wall passes through his palms: centre x so that the circle meets (hand_push, hand_y)
    dy = (hand_y - BUB_Y * R0) / (BUB_RY * R0)
    cb = hand_push + 0.1 - R0 * math.sqrt(max(0.0, 1 - dy * dy))

    r_top = S.keys([(0, R0), (1.2, R0), (2.6, 6.05), (3.6, 5.3), (4.6, 4.6), (6.6, 4.05)])   # always just over his head

    def ring_svg(P, s, cx, r, rx=None, ry=None, op=1.0, width=0.22):
        rx, ry = rx or r, ry or BUB_RY * r
        px, py = P(cx, BUB_Y * r)
        gy = P(0, 0)[1]
        return (f'<defs><clipPath id="above"><rect x="-99999" y="-99999" width="199999" height="{gy + 99999:.1f}"/>'
                f'</clipPath></defs><g clip-path="url(#above)"><ellipse cx="{px:.1f}" cy="{py:.1f}" rx="{rx * s:.1f}" '
                f'ry="{ry * s:.1f}" fill="#FFFFFF" fill-opacity="{0.10 * op:.3f}" stroke="{S.INK}" '
                f'stroke-width="{width * s:.1f}" stroke-dasharray="{0.9 * s:.1f} {0.12 * s:.1f}" '
                f'opacity="{op:.3f}"/></g>')

    def props_t(i, tt, P, s):
        return "", ring_svg(P, s, c0, r_top(tt))

    def props_b(i, tt, P, s):
        if tt < PAY:
            # the wall as a dashed path: where his palms reach it, it is pressed out exactly to his palms (a dent
            # that follows the hands), so he always visibly pushes on it
            Jb = bu[min(i, len(bu) - 1)]
            hands = [Jb["wristR"], Jb["wristL"]]
            hy = max(h[1] for h in hands)
            hx = max(h[0] for h in hands) + 0.12                   # the palm, just past the wrist
            ry = BUB_RY * R0
            u = (hy - BUB_Y * R0) / ry
            wall = cb + R0 * math.sqrt(max(0.0, 1 - u * u))         # the wall's x at hand height
            gap = hx - wall
            on = S.ease((tt - T_PUSH) / 0.15) if tt >= T_PUSH else (1.0 if abs(gap) < 0.05 else 0.0)
            quiver = 0.05 * math.sin(tt * 40) * on
            pts = []
            for j in range(97):
                a = -math.pi / 2 + 2 * math.pi * j / 96
                x, y = cb + R0 * math.cos(a), BUB_Y * R0 + ry * math.sin(a)
                if math.cos(a) > 0:
                    w = math.exp(-((y - hy) / 1.3) ** 2) * on
                    x += (gap + quiver) * w
                pts.append(P(x, y))
            gy = P(0, 0)[1]
            d = "M" + " L".join(f"{a_:.1f},{b_:.1f}" for a_, b_ in pts) + " Z"
            return "", (f'<defs><clipPath id="above"><rect x="-99999" y="-99999" width="199999" '
                        f'height="{gy + 99999:.1f}"/></clipPath></defs><g clip-path="url(#above)"><path d="{d}" '
                        f'fill="#FFFFFF" fill-opacity="0.1" stroke="{S.INK}" stroke-width="{0.22 * s:.1f}" '
                        f'stroke-linejoin="round" stroke-dasharray="{0.9 * s:.1f} {0.12 * s:.1f}"/></g>')
        k = (tt - PAY) / 0.55                                   # burst: the wall flies apart behind him and fades
        if k > 1:
            return "", ""
        out = []
        for j in range(16):
            a = 2 * math.pi * (j + 0.5) / 16
            r1 = R0 * (1.05 + 1.1 * k)
            x0, y0 = cb + math.cos(a) * r1, BUB_Y * R0 + BUB_RY * math.sin(a) * r1
            x1, y1 = cb + math.cos(a + 0.22) * r1, BUB_Y * R0 + BUB_RY * math.sin(a + 0.22) * r1
            if min(y0, y1) < 0.1:
                continue
            out.append(S.line(P, s, [(x0, y0), (x1, y1)], width=0.22 * (1 - k), opacity=1 - k))
        return "".join(out), ""
    xs = [cb + 1.0 if i / S.FPS < PAY else max(cb + 1.0, (f["pelvis"][0] if f else 0) + 1.0) for i, f in enumerate(bu)]
    cam_x = _smooth(xs, 40)
    top = S.Half(T, {"hero": tu}, cam=lambda i: (c0 + 1.0, S.CAM_Y + 0.6, 1.0), props=props_t,
                 plate="plate_river", tone=lambda tt: "bank", bright=S.keys([(0, 0.95), (T, 0.7)]))
    bottom = S.Half(T, {"hero": bu}, cam=lambda i: (cam_x[min(i, len(cam_x) - 1)], S.CAM_Y + 0.6, 1.0),
                    props=props_b, plate="plate_river", tone=lambda tt: "bank",
                    bright=S.keys([(0, 0.85), (PAY - 0.05, 0.85), (PAY + 0.6, 1.0)]))
    print(f"bubble: start pelvis {bu[0]['pelvis'][0]:.2f}, bubble {cb - R0:.2f}..{cb + R0:.2f}", file=sys.stderr)
    return {"top": top, "bottom": bottom, "pay": PAY}


# ================================================================ SLEEP IN | 5 AM  (sea shore before dawn)
SLEEP = {"rot": -90, "lean": 0, "nod": 0, "thR": 30, "knR": 60, "thL": 36, "knL": 70, "ftR": 0, "ftL": 0,
         "arR": 10, "elR": 60, "arL": 4, "elL": 70}


def dawn():
    """Before dawn by the sea. Top sleeps on. Bottom is already out running along the shore in the dark; on the
    beat the sun clears the sea in front of him and lays a red path on the water."""
    PAY = 6.24
    T = SKIT_DUR
    t = Anim(x0=0.0)
    t.hold(T + 0.1, {**SLEEP, "nod": 50, "ftR": -60, "ftL": -60, "arR": -4, "elR": 4,
                             "arL": 2, "elL": 6}, breathe=0.6)   # flat on his back, head on a pillow
    tw = world(t)
    MAT = 0.22
    lift = MAT + 0.32 - (tw[0]["head"][1] - 1.0)          # the head rests on the pillow, the back on the mat
    tw = [{k: (v[0], v[1] + lift, v[2]) if isinstance(v, tuple) else v for k, v in f.items()} for f in tw]
    b = Anim(x0=0.0)
    b.cycle(M.JOG, T + 0.2, phase=0.1, blend=0.0)
    bw = world(b)
    tu, bu = up(tw), up(bw)
    S_cam = follow(bu, ahead=2.0)

    def props_b(i, tt, P, s):
        k = S.ease((tt - PAY + 0.5) / 1.0)
        if k <= 0:
            return "", ""
        cx = S_cam(i)[0] + 4.2
        sy = -1.2 + 7.2 * k                               # it clears the sea but stays under the label
        sun = S.sun(P, s, cx, sy, 2.3, horizon=HORIZON)
        glow = S.disc(P, s, cx, sy, 4.5, S.VERM, opacity=0.12 * k, glow=True)
        px = P(cx, 0)[0]                                # the sun's path on the sea (screen space, under the horizon)
        rnd = random.Random(3)
        path = []
        for j in range(9):
            y = S.H * (HORIZON + 0.012 + 0.016 * j)
            w = (0.9 + 0.35 * j) * s * (0.6 + 0.4 * rnd.random())
            path.append(f'<rect x="{px - w / 2 + rnd.uniform(-8, 8):.1f}" y="{y:.1f}" width="{w:.1f}" '
                        f'height="{3 + j * 0.6:.1f}" fill="{S.VERM}" opacity="{0.55 * k * (1 - j / 11):.3f}"/>')
        return glow + sun + "".join(path), ""

    def props_t(i, tt, P, s):
        x = tw[0]["pelvis"][0]
        J = tu[min(i, len(tu) - 1)]
        hx = J["head"][0]
        mat = S.rect(P, x - 4.4, 0.0, x + 3.6, MAT, S.STONE)
        pillow = (f'<ellipse cx="{P(hx, MAT + 0.16)[0]:.1f}" cy="{P(hx, MAT + 0.16)[1]:.1f}" rx="{1.15 * s:.1f}" '
                  f'ry="{0.2 * s:.1f}" fill="#CFC6B4" stroke="{S.INK}" stroke-width="{0.06 * s:.1f}"/>')
        ch, kn, an = J["chest"], max(J["kneeL"][1], J["kneeR"][1]), max(J["ankleL"][0], J["ankleR"][0])
        kx = (J["kneeL"][0] + J["kneeR"][0]) / 2
        b0 = (ch[0] - 0.1, ch[1] + 0.45)                    # a soft blanket from the shoulders over the knees
        pts = [P(*q) for q in [(ch[0] - 0.4, MAT), b0, (kx - 0.6, kn + 0.25), (kx + 0.2, kn + 0.42),
                               (an + 0.2, J["ankleL"][1] + 0.4), (an + 0.7, MAT)]]
        d = (f"M{pts[0][0]:.1f},{pts[0][1]:.1f} Q{pts[0][0]:.1f},{pts[1][1]:.1f} {pts[1][0]:.1f},{pts[1][1]:.1f} "
             f"C{pts[2][0]:.1f},{pts[1][1]:.1f} {pts[2][0]:.1f},{pts[2][1]:.1f} {pts[3][0]:.1f},{pts[3][1]:.1f} "
             f"Q{pts[4][0]:.1f},{pts[3][1]:.1f} {pts[4][0]:.1f},{pts[4][1]:.1f} "
             f"Q{pts[5][0]:.1f},{pts[4][1]:.1f} {pts[5][0]:.1f},{pts[5][1]:.1f} Z")
        blanket = (f'<path d="{d}" fill="#C9C0AE" stroke="{S.INK}" stroke-width="{0.08 * s:.1f}" '
                   f'stroke-linejoin="round"/>')
        mat = mat + pillow
        zz = "".join(f'<text x="{P(x + 1.6 + 0.7 * j, 3.2 + 0.8 * j + 0.3 * math.sin(tt * 2 + j))[0]:.1f}" '
                     f'y="{P(0, 3.2 + 0.8 * j + 0.3 * math.sin(tt * 2 + j))[1]:.1f}" font-size="{(0.9 + 0.3 * j) * s:.0f}" '
                     f'font-family="Georgia" font-style="italic" fill="#EDE6D6" opacity="{0.35 + 0.25 * math.sin(tt * 1.5 + j) ** 2:.2f}">z</text>'
                     for j in range(3))
        return mat, blanket + zz
    top = S.Half(T, {"hero": tu}, cam=lambda i: (tw[0]["pelvis"][0] + 0.5, S.CAM_Y, 1.0), props=props_t,
                 plate="plate_sea", bright=S.keys([(0, 0.45), (T, 0.4)]), tone=lambda tt: "light")
    bottom = S.Half(T, {"hero": bu}, cam=S_cam, props=props_b, plate="plate_sea",
                    bright=S.keys([(0, 0.45), (2.0, 0.5), (PAY - 0.2, 0.62), (PAY + 0.5, 1.0)]),
                    tone=lambda tt: "light" if tt < PAY else "sand")
    return {"top": top, "bottom": bottom, "pay": PAY}


def kite_body(P, s, kx, ky):
    """A vermilion diamond kite with an ink outline and spars (reads against the sun as well)."""
    pts = [(kx, ky + 0.9), (kx + 0.7, ky), (kx, ky - 1.0), (kx - 0.7, ky)]
    q = " ".join(f"{a:.1f},{b:.1f}" for a, b in (P(x, y) for x, y in pts))
    return (f'<polygon points="{q}" fill="{S.VERM}" stroke="{S.INK}" stroke-width="{0.09 * s:.1f}" '
            f'stroke-linejoin="round"/>' + S.line(P, s, [pts[0], pts[2]], width=0.05) +
            S.line(P, s, [pts[1], pts[3]], width=0.05))


# ================================================================ WAIT FOR WIND | MAKE WIND  (temple hill)
def kite():
    """Below a hill temple. Top stands holding the string of a kite that lies flat on the stones; he looks up for a
    wind and tugs the string - the kite flops over and lies down again. Bottom grabs his and runs - the kite lifts off behind him and climbs; on the
    beat it flies across the rising sun."""
    PAY = 6.25
    T = SKIT_DUR
    HOLD = {"arR": 70, "elR": 20}                                   # bottom: the string hand forward
    LOW = {"arR": 28, "elR": 52}                                    # top: the string hand low in front
    TUG = {"arR": -12, "elR": 78}                                   # a sharp pull back on the string
    TUGS = [1.3, 2.3, 4.5]
    t = Anim(x0=0.0)
    t.hold(1.0, {**M.STAND, **LOW}, breathe=0.5)
    t.to({**M.STAND, **LOW, "nod": -16}, 0.4, "io")                 # looks up at the sky
    t.hold(1.6, breathe=0.5)
    t.to({**M.STAND, **LOW, "nod": 6, "lean": 4}, 0.5, "io")
    t.hold(0.9, breathe=0.5)
    t.to({**M.STAND, **LOW, "nod": -14}, 0.4, "io")
    t.hold(1.0, breathe=0.5)
    t.to({**M.STAND, **LOW, "nod": 22, "lean": 8}, 0.6, "io")       # nothing: shoulders drop
    pad(t, T, breathe=0.5)
    for g in TUGS:
        overlay(t, g, g + 0.42, TUG, ramp=0.14)
    tw = world(t)
    sp = tw[0]["pelvis"]

    def kite_ground(tt):
        """The kite lies in front of him; each tug drags it a little closer and it flops straight back down."""
        x, y = sp[0] + 5.0, 0.0
        for g in TUGS:
            u = (tt - g - 0.08) / 0.5
            if u > 0:
                x -= 0.45 * S.ease(min(1.0, u))
                if u < 1:
                    y = max(y, 0.7 * math.sin(math.pi * u))
        return x, y
    b = Anim(x0=0.0)
    b.hold(0.25, {**M.STAND, **HOLD})
    b.cycle(M.SPRINT, T, phase=0.62, ramp=(1.3, 1.0), blend=0.15)
    overlay(b, 0.0, 99, {"arR": -40, "elR": 18}, ramp=0.05)        # the string hand held back behind him
    bw = world(b)
    tu, bu = up(tw), up(bw)
    n = len(bu)
    L = 9.0
    ang = [math.radians(4 + 62 * S.ease((i / S.FPS - 0.4) / (PAY - 0.4))) for i in range(n)]

    def kite_pos(i):
        J = bu[min(i, n - 1)]
        hx, hy = J["wristR"][0], J["wristR"][1]
        a = ang[min(i, n - 1)]
        top = cam_y(i) + (S.H / 2 - SAFE_TOP) / (S.PPM * 0.85) - 1.0    # the kite stays below the label band
        return hx - L * math.cos(a), min(top, max(0.4, hy + L * math.sin(a) - 1.5 * (1 - math.sin(a))))

    def cam_y(i):
        return S.CAM_Y + 3.6 * S.ease((i / S.FPS - 1.5) / 4.0)

    def kite_svg(P, s, kx, ky, tilt, tt):
        tail = [(kx - 0.3 * j * math.cos(tilt) - 0.25 * math.sin(tt * 9 + j),
                 ky - 0.9 - 0.55 * j + 0.15 * math.sin(tt * 7 + j * 0.8)) for j in range(6)]
        return S.line(P, s, [(kx, ky - 0.7)] + tail, width=0.09, stroke=S.VERM) + kite_body(P, s, kx, ky)

    def props_b(i, tt, P, s):
        kx, ky = kite_pos(i)
        J = bu[min(i, n - 1)]
        sun = ""
        if tt > PAY - 0.6:
            k = S.ease((tt - PAY + 0.6) / 0.9)
            y_max = (P(0, 0)[1] - SAFE_TOP - 2.4 * s) / s  # keep the whole disc below the label band
            sun = S.sun(P, s, kx + 0.6, min(y_max, -1.5 + (ky + 1.2) * k), 2.4, horizon=HORIZON)
        string = S.line(P, s, [(J["wristR"][0], J["wristR"][1]), (kx, ky)], width=0.04, opacity=0.9)
        return sun + string, kite_svg(P, s, kx, ky, 0.3, tt)          # the string runs behind him, never over his face

    def props_t(i, tt, P, s):
        J = tu[min(i, len(tu) - 1)]
        kx, ky = kite_ground(tt)
        tilt = 0.0 if ky < 0.05 else 0.6 * ky
        pts = [(kx + 0.9, 0.12 + ky), (kx, 0.3 + ky + tilt), (kx - 0.9, 0.12 + ky), (kx, 0.02 + ky - tilt * 0.3)]
        return "", (S.line(P, s, [(J["wristR"][0], J["wristR"][1]), (kx - 0.8, 0.15 + ky)], width=0.04,
                           opacity=0.9) + S.poly(P, pts, S.VERM))

    def cam_b(i):
        J = bu[min(i, n - 1)]
        kx, _ = kite_pos(i)
        return ((J["pelvis"][0] + kx) / 2 + 1.0, cam_y(i), 0.85)
    top = S.Half(T, {"hero": tu}, cam=lambda i: (sp[0] - 1.5, S.CAM_Y, 1.0), props=props_t,
                 plate="plate_temple", tone=lambda tt: "stone", bright=S.keys([(0, 1.0), (T, 0.78)]))
    bottom = S.Half(T, {"hero": bu}, cam=cam_b, props=props_b, plate="plate_temple", tone=lambda tt: "stone")
    return {"top": top, "bottom": bottom, "pay": PAY}


SKITS = {"steps": steps, "rest": rest, "fear": fear, "wind": wind,
         "lantern": lantern, "bubble": bubble, "dawn": dawn, "kite": kite}


def check(name: str, out: Path, times=(0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.2)) -> Path:
    """A quick full-size still check (no video): both halves at a few times -> out/<name>_<half>_<t>.png."""
    from studio.ink3d import stick2d
    from studio.ink3d.pose2d import to_px
    from studio.ink3d.stage2d import _draw, _frame_data
    res = SKITS[name]()
    out.mkdir(parents=True, exist_ok=True)
    for half in ("top", "bottom"):
        h = res[half]
        sides = {}
        for nm, fr in h.figures.items():
            seen = [to_px(J, 0, 0, S.PPM) for J in fr if J is not None]
            ss = stick2d.near_sides(seen) if seen else []
            it = iter(ss)
            sides[nm] = [next(it) if J is not None else "R" for J in fr]
        x0 = h.cam(0)[0]
        for tt in times:
            i = min(h.n - 1, int(tt * S.FPS))
            _draw((out / f"{name}_{half}_{tt:.1f}.png", _frame_data(h, i, sides, x0)))
    return out


if __name__ == "__main__":
    name = sys.argv[1]
    which = sys.argv[2] if len(sys.argv) > 2 else "both"
    if which == "check":
        print(check(name, OUT / "check"))
        sys.exit()
    res = SKITS[name]()
    for half in ("top", "bottom"):
        if which in (half, "both"):
            print(S.render_half(res[half], OUT / f"{name}_{half}"))
    _ = math, full
