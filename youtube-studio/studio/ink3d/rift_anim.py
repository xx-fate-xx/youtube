"""The Rift pilot, animated pose to pose (studio/ink3d/pose2d.py). One function per metaphor returns both halves:

    {"top": {"hero": frames, ...}, "bottom": {...}, "marks": {...}}      (world frames in R units)

Local time 0 = the metaphor's start in the Short; beats from the Head Bang cut (beat 0.617 s).

    python -m studio.ink3d.rift_anim <wall|gap|fist|race> [out_dir]      2D previews of both halves + JSON
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from studio.ink3d import moves as M
from studio.ink3d.pose2d import FPS, R_UNIT, Anim, fk, full, preview, scaled, sheet, to_mocap, world

ROOT = Path(__file__).resolve().parents[2]
DUR = {"wall": 7.50, "gap": 4.93, "fist": 5.56, "race": 12.01}


def idx(t: float) -> int:
    """Frame index shown at local time t (frame i is on screen at i / FPS)."""
    return int(round(t * FPS))


def pad(a: Anim, sec: float, breathe: float = 1.0):
    """Hold the last pose until the metaphor ends."""
    left = int(round(sec * FPS)) + 2 - a.n
    if left > 0:
        a.hold(left / FPS, breathe=breathe)


def front_x(J: dict, names=("wristL", "wristR", "head", "elbL", "elbR", "chest", "kneeL", "kneeR", "toeL", "toeR")):
    """Front-most drawn point (R): joints plus their stroke radius (head: its radius)."""
    return max(J[n][0] + (1.0 if n == "head" else 0.3) for n in names)


# ================================================================ WAIT FOR A DOOR / MAKE ONE
STEP_IN = {"lean": 14, "nod": -10, "thR": 25, "knR": 20, "thL": -22, "knL": 55, "ftL": -10,
           "arR": 70, "elR": 30, "arL": 60, "elL": 30}
# pushing for real: torso low and long, head tucked between the arms, elbows bent, palms on the wall at shoulder
# height, the back leg driving straight from the toe
PUSH = {"lean": 50, "nod": -16, "thR": 36, "knR": 66, "ftR": 8, "thL": -44, "knL": 4, "ftL": -40,
        "arR": 126, "elR": 16, "arL": 120, "elL": 22}
RECOIL = {"lean": -4, "nod": 6, "thR": 8, "knR": 12, "thL": -10, "knL": 10, "arR": 20, "elR": 50,
          "arL": 10, "elL": 40}
COIL = {"lean": 52, "nod": -42, "thR": 62, "knR": 108, "ftR": 20, "thL": -30, "knL": 98, "ftL": -40,
        "arR": -55, "elR": 70, "arL": 95, "elL": 80}
COIL_LOW = {**COIL, "lean": 58, "thR": 70, "knR": 122, "knL": 112}
# running through: forearms crossed up in front of the face (laid over the sprint's arms)
COVER = {"arR": 150, "elR": 180, "arL": 193, "elL": 222, "nod": 8}   # an X over the face: near arm "/", far forearm "\\"
# (kept for reference) the full-force push on the run
CHARGE = {"lean": 40, "nod": 0, "thR": 42, "knR": 44, "ftR": 8, "thL": -46, "knL": 6, "ftL": -42,
          "arR": 126, "elR": 6, "arL": 120, "elL": 10}
LOOK_UP = {"lean": -10, "nod": -34, "arR": -4, "elR": 8, "arL": 4, "elL": 10, "thR": 6, "thL": -6}
KNOCK_UP = {"lean": 2, "nod": -6, "arR": 62, "elR": 72, "arL": -6, "elL": 16, "thR": 8, "thL": -8}
KNOCK_HIT = {**KNOCK_UP, "lean": 6, "arR": 84, "elR": 22}
SIGH = {"lean": 8, "nod": 26, "arR": -2, "elR": 6, "arL": 2, "elL": 8, "knR": 6, "knL": 6}
SQUAT = {"lean": 38, "nod": 0, "thR": 62, "knR": 92, "thL": 58, "knL": 88, "arR": 70, "elR": 20,
         "arL": 64, "elL": 24}
SIT = {"lean": 16, "nod": 12, "thR": 86, "knR": 92, "ftR": 4, "thL": 82, "knL": 86, "ftL": 4,
       "arR": 52, "elR": 34, "arL": 46, "elL": 40}
SLUMP = {**SIT, "lean": 36, "nod": 40, "arR": 30, "elR": 18, "arL": 24, "elL": 22}
SLUMP2 = {**SLUMP, "lean": 40, "nod": 52}


def _walk_in(a: Anim):
    a.cycle(M.WALK, 1.27, phase=0.1, blend=0.0, end="pass")
    a.to(M.STAND, 0.25, "out")


def wall():
    D = 5.03
    T = DUR["wall"]
    # bottom first: the wall stands where his hands meet it
    b = Anim(x0=0.0)
    _walk_in(b)
    b.keys([(0.14, STEP_IN), (0.16, PUSH)])
    i_push = b.n
    b.hold(0.15, breathe=0.0)
    for k in range(int(0.45 * FPS)):                       # straining: a fast tremor
        sgn = 1 if k % 2 else -1
        b.frames.append({"pose": {**full(PUSH), "lean": PUSH["lean"] + 1.2 * sgn, "nod": PUSH["nod"] - 2 * sgn},
                         "mode": "plant"})
    b.to(RECOIL, 0.16, "out")
    i_back = b.n
    w0 = world(b)
    wall_x = max(max(w0[i]["wristR"][0], w0[i]["wristL"][0]) for i in range(i_push, i_back)) + 0.28

    RUN, SET = 0.70, 0.28                                  # run-up and the coiled "set" before it

    def build(rate):
        a = Anim(x0=0.0)
        a.frames = [dict(f) for f in b.frames]
        back = D - RUN - SET - 0.16 - a.n / FPS
        a.cycle(M.BACKSTEP, back, rate=rate, reverse=True, blend=0.14, phase=0.5)
        a.to(COIL, 0.16, "out")
        a.to(COIL_LOW, (idx(D) - idx(RUN) - a.n) / FPS, "io")
        ph = a.cycle(M.SPRINT, (idx(D) - 14 - a.n) / FPS, phase=0.62, ramp=(1.6, 1.3), blend=0.14)
        # the last strides: a long low charging run, arms crossed over the face; straight through and on
        a.cycle(M.CHARGE_RUN, 1.0, phase=ph % 1, blend=0.12)
        for i in range(idx(D) - 14, min(a.n, idx(D) + 16)):
            u = max(0.0, min(1.0, (i - (idx(D) - 14)) / 6, (idx(D) + 16 - i) / 8))
            fr = a.frames[i]
            fr["arms"], fr["arms_w"], fr["cover"], fr["cover_w"] = COVER, u, True, u
        return a
    lo, hi = 0.2, 2.5
    for _ in range(30):                                   # backpedal distance so the shoulder meets the wall at D
        mid = (lo + hi) / 2
        a = build(mid)
        w = world(a)
        # the crossed forearms in front of his face meet the wall on the drop
        err = front_x(w[idx(D)], ("elbR", "elbL", "wristR", "wristL", "head")) - (wall_x + 0.1)
        if err > 0:
            lo = mid
        else:
            hi = mid
    a = build((lo + hi) / 2)
    a.cycle(M.SPRINT, T - a.n / FPS + 0.2, phase=0.1, blend=0.1)
    bottom = world(a)

    # top: same walk, a few steps more, he knocks on the wall like on a door - nothing; he sighs and sits down on a
    # stone to wait
    def top_walk(extra):
        t = Anim(x0=0.0)
        t.cycle(M.WALK, 1.27 + extra, phase=0.1, blend=0.0)
        t.to(M.STAND, 0.25, "out")
        t.to(KNOCK_UP, 0.18, "out")
        return t
    lo, hi = 0.0, 1.5
    for _ in range(25):                                   # walk on until the knuckles just reach the wall
        mid = (lo + hi) / 2
        w = world(top_walk(mid).to(KNOCK_HIT, 0.07, "snap"))
        if w[-1]["wristR"][0] + 0.3 < wall_x:
            lo = mid
        else:
            hi = mid
    t = top_walk(hi)
    hit = KNOCK_HIT
    for el in range(0, 121, 2):                           # bend the elbow until the knuckles just touch
        hit = {**KNOCK_HIT, "elR": el, "arR": KNOCK_HIT["arR"] - el * 0.3}
        tt = top_walk(hi).to(hit, 0.07, "snap")
        if world(tt)[-1]["wristR"][0] + 0.3 <= wall_x:
            break
    for _ in range(3):                                    # knock, knock, knock
        t.to(hit, 0.07, "snap", sm=1)
        t.to(KNOCK_UP, 0.13, "out", sm=1)
    t.to(M.STAND, 0.25, "io")
    t.hold(0.25, breathe=0.5)
    t.to(LOOK_UP, 0.35, "out")                            # nothing. He leans back and looks up at it
    t.hold(0.3, breathe=0.6)
    t.to(SIGH, 0.4, "io")
    t.keys([(0.3, SQUAT), (0.25, SIT)])
    i_sit = t.n
    t.to(SLUMP, 1.0, "io")
    t.hold(max(0.0, D - 0.25 - t.n / FPS), breathe=0.5)
    t.to(SLUMP2, 0.35, "out")                             # the head drops on the drop
    pad(t, T, breathe=0.4)
    top = world(t)
    sp = top[i_sit + 4]["pelvis"]
    seat = {"x0": sp[0] - 1.25, "x1": sp[0] + 0.75, "top": sp[1] - 0.36}
    return {"top": {"hero": top}, "bottom": {"hero": bottom},
            "marks": {"wall_x": wall_x, "seat": seat, "D": D}}


# ================================================================ DOUBT / JUMP
TAKEOFF = {"lean": 30, "nod": -30, "thR": -42, "knR": 6, "ftR": -50, "thL": 70, "knL": 100, "ftL": 0,
           "arR": 128, "elR": 20, "arL": -60, "elL": 40}
FLY = {"lean": 10, "nod": -14, "thR": -48, "knR": 70, "ftR": -30, "thL": 72, "knL": 28, "ftL": 8,
       "arR": 132, "elR": 15, "arL": 96, "elL": 25, "lift": 0}
REACH = {"lean": 34, "nod": -20, "thR": 76, "knR": 18, "ftR": 6, "thL": 64, "knL": 34, "ftL": 0,
         "arR": 100, "elR": 30, "arL": 80, "elL": 40}
LAND = {"lean": 34, "nod": -22, "thR": 78, "knR": 112, "ftR": 18, "thL": 46, "knL": 118, "ftL": 10,
        "arR": 70, "elR": 50, "arL": 40, "elL": 60}
SKID = {"lean": -24, "nod": 14, "thR": 50, "knR": 4, "ftR": 14, "thL": -4, "knL": 76, "ftL": -10,
        "arR": -75, "elR": 50, "arL": 75, "elL": 25}
TEETER_F = {"lean": 24, "nod": 34, "thR": 4, "knR": 4, "thL": -4, "knL": 4, "arR": 88, "elR": 8,
            "arL": -70, "elL": 20}
TEETER_B = {"lean": -10, "nod": 18, "thR": 4, "knR": 8, "thL": -4, "knL": 8, "arR": -70, "elR": 20,
            "arL": 96, "elL": 8}
LOOK_DOWN = {"lean": 18, "nod": 40, "thR": 4, "knR": 10, "thL": -6, "knL": 10, "arR": 6, "elR": 20,
             "arL": -4, "elL": 20}
DOUBT = {"lean": 10, "nod": 34, "thR": -4, "knR": 8, "thL": 6, "knL": 8, "arR": 10, "elR": 70,
         "arL": 4, "elL": 60}


def gap():
    TO, AIR = 2.47, 0.72
    T = DUR["gap"]
    # bottom: sprints to the edge, leaps on the beat, lands running
    b = Anim(x0=0.0)
    b.cycle(M.SPRINT, (idx(TO) - 4) / FPS, phase=0.3, blend=0.0)
    b.to(TAKEOFF, 4 / FPS, "out", sm=3)
    w = world(b)
    J = w[-1]
    edge = max(J["toeR"][0], J["toeL"][0]) + 0.25
    v = (w[-1]["pelvis"][0] - w[-6]["pelvis"][0]) / 5 * FPS
    dist = v * AIR * 1.05
    b.to(FLY, 0.45 * AIR, "out", mode="air", dx=dist * 0.45, arc=0.0, dy=2.3)
    b.to(REACH, 0.55 * AIR, "in", mode="air", dx=dist * 0.55, arc=0.0, dy=-2.3)
    i_land = b.n
    b.to(LAND, 3 / FPS, "snap", sm=1)
    b.hold(2 / FPS, breathe=0.0)
    b.cycle(M.SPRINT, T - b.n / FPS + 0.2, phase=0.0, blend=0.16)
    bottom = world(b)
    # the far edge: well before where he lands
    land_x = min(bottom[i_land]["toeR"][0], bottom[i_land]["toeL"][0])
    gap_w = (land_x - 0.7) - edge
    # top: the same sprint; he brakes hard, teeters at the brink, looks down, backs away
    t = Anim(x0=0.0)
    t.cycle(M.SPRINT, 1.83, phase=0.3, blend=0.0)
    vt = 11.8
    t.to(SKID, 0.5, "out", mode="slide", dx=vt * 0.5 * 0.45, xkind="out")
    t.hold(0.06, breathe=0.0, mode="slide")
    i_stop = t.n
    t.keys([(0.16, TEETER_F), (0.2, TEETER_B), (0.18, TEETER_F), (0.22, LOOK_DOWN)])
    t.hold(0.5, breathe=0.6)
    t.cycle(M.BACKSTEP, 0.6, reverse=True, phase=0.75, blend=0.3, end="pass")
    t.to(DOUBT, 0.4, "io")
    pad(t, T, breathe=0.6)
    top = world(t)
    Js = top[i_stop]
    edge_top = max(Js["toeR"][0], Js["toeL"][0]) + 0.2
    return {"top": {"hero": top}, "bottom": {"hero": bottom},
            "marks": {"edge_bottom": edge, "gap": gap_w, "edge_top": edge_top, "TO": TO}}


def props_gap(m, half):
    e = m["edge_top"] if half == "top" else m["edge_bottom"]

    def draw(dr, i, P):
        a0, b0 = P(e - 40, 0)
        a1, b1 = P(e, -6)
        dr.rectangle([a0, b0, a1, b1], fill=(40, 36, 30, 255))
        c0, d0 = P(e + m["gap"], 0)
        c1, d1 = P(e + m["gap"] + 40, -6)
        dr.rectangle([c0, d0, c1, d1], fill=(40, 36, 30, 255))
    return draw


# ================================================================ STAY DOWN / HIT BACK
G = 1.9                                                     # the shadow giant: the same figure x1.9
G_GUARD = {"lean": 10, "nod": -12, "thR": 22, "knR": 26, "thL": -18, "knL": 22, "arR": 64, "elR": 112,
           "arL": 52, "elL": 104}
G_WIND = {"lean": -10, "nod": -4, "thR": 24, "knR": 34, "thL": -26, "knL": 26, "arR": -40, "elR": 118,
          "arL": 82, "elL": 92}
G_CROSS = {"lean": 34, "nod": -26, "thR": 44, "knR": 56, "ftR": 14, "thL": -36, "knL": 6, "ftL": -36,
           "arR": 90, "elR": 0, "arL": 30, "elL": 110}
G_TALL = {"lean": -6, "nod": -18, "thR": 14, "knR": 8, "thL": -14, "knL": 8, "arR": -4, "elR": 14,
          "arL": 6, "elL": 18}                         # after its punch: chest out, arms down, looking down on him
H_GUARD = {"lean": 6, "nod": -8, "thR": 14, "knR": 16, "thL": -14, "knL": 14, "arR": 62, "elR": 118,
           "arL": 50, "elL": 112}
H_NERV = {"lean": -2, "nod": 4, "thR": 6, "knR": 8, "thL": -6, "knL": 8, "arR": 30, "elR": 70,
          "arL": 22, "elL": 64}
H_SNAP = {"rot": -18, "lean": -26, "nod": -30, "thR": 26, "knR": 10, "thL": 6, "knL": 30, "arR": 110,
          "elR": 30, "arL": 70, "elL": 40}
H_FLY = {"rot": -62, "lean": -12, "nod": -20, "thR": 36, "knR": 20, "thL": 20, "knL": 50, "arR": 120,
         "elR": 20, "arL": 90, "elL": 30}
H_LIE = {"rot": -90, "lean": 0, "nod": 0, "thR": 2, "knR": 6, "ftR": 0, "thL": 48, "knL": 92, "ftL": 0,
         "arR": 6, "elR": 8, "arL": 2, "elL": 14}
H_TRY = {**H_LIE, "lean": 30, "nod": 20, "arR": -14, "elR": 70, "arL": -22, "elL": 80}
H_STAGGER = {"lean": -18, "nod": -24, "thR": 30, "knR": 14, "thL": -16, "knL": 30, "arR": 70, "elR": 50,
             "arL": -40, "elL": 40}
H_SET = {"lean": 34, "nod": -34, "thR": 52, "knR": 84, "ftR": 16, "thL": -32, "knL": 70, "ftL": -36,
         "arR": -40, "elR": 80, "arL": 70, "elL": 110}
H_PUNCH = {"lean": 24, "nod": -24, "thR": 78, "knR": 112, "thL": -30, "knL": 84, "arR": 100, "elR": 0,
           "arL": -40, "elL": 100}
H_LAND = {"lean": 30, "nod": -20, "thR": 70, "knR": 104, "ftR": 16, "thL": -10, "knL": 96, "ftL": -24,
          "arR": 40, "elR": 70, "arL": -30, "elL": 70}
H_STAND = {"lean": -4, "nod": -10, "thR": 10, "knR": 6, "thL": -10, "knL": 6, "arR": 10, "elR": 30,
           "arL": -6, "elL": 30}


def aim(pose: dict, side: str, target: tuple) -> dict:
    """Swing an arm (relative angle search) so the neck->wrist line points at target (pose-relative R coords,
    facing +x)."""
    q = full(pose)
    best = None
    for a in range(-40, 181):
        q["ar" + side] = a
        J = fk(q)
        w, n = J["wrist" + side], J["neck"]
        d = abs(math.atan2(w[1] - n[1], w[0] - n[0]) - math.atan2(target[1] - n[1], target[0] - n[0]))
        if best is None or d < best[0]:
            best = (d, a)
    q["ar" + side] = best[1]
    return q


def shift(frames, dx):
    return [None if f is None else {j: ((v[0] + dx, v[1], v[2]) if isinstance(v, tuple) else v) for j, v in f.items()}
            for f in frames]


def fist():
    HIT, PUNCH = 1.85, 3.70
    T = DUR["fist"]
    # the hero stands at x = 0, nervous, then raises his fists; his face at HIT is the giant's target
    h0 = Anim(x0=0.0)
    h0.hold(0.6, H_NERV, breathe=0.8)
    h0.to(H_GUARD, 0.35, "out")
    h0.hold((idx(HIT) - h0.n) / FPS, breathe=0.6)
    face = world(h0)[-1]["head"]
    # the giant, built in its own units (scaled x G afterwards, facing -x): its cross lands on the face at HIT
    cross = full(G_CROSS)
    for _ in range(4):                                   # aim the straight arm down at the face height
        J = fk(cross)
        gp_y = world(Anim().hold(1 / FPS, cross))[-1]["pelvis"][1]
        cross = aim(cross, "R", (J["wristR"][0], face[1] / G - gp_y))
    gA = Anim(x0=0.0, facing=-1)
    gA.hold(1.15, G_GUARD, breathe=1.0)
    gA.to(G_WIND, 0.42, "out")
    gA.hold((idx(HIT) - 3 - gA.n) / FPS, breathe=0.0)
    gA.to(cross, 3 / FPS, "snap", sm=1)
    gA.hold(4 / FPS, breathe=0.0)
    gA.to(G_TALL, 0.5, "io")
    pad(gA, T, breathe=1.0)
    gw = world(gA)
    wr = gw[idx(HIT)]["wristR"]
    gx = face[0] + 0.7 - wr[0] * G                       # knuckles just into the face (head radius 1)
    giant = shift(scaled(gw, G, anchor_x=0.0), gx)

    # top: knocked down, tries to get up once, falls back on the bottom's punch and stays down
    t = Anim(x0=0.0)
    t.frames = [dict(f) for f in h0.frames]
    t.to(H_SNAP, 3 / FPS, "snap", mode="air", dx=-1.4, dy=0.6, sm=1)
    t.to(H_FLY, 0.22, "out", mode="air", dx=-1.8, dy=-0.4)
    t.to(H_LIE, 0.14, "in", mode="air", dx=-0.6, dy=-3.0)
    t.to({**H_LIE, "lean": 8, "thL": 56, "knL": 100}, 0.1, "out")
    t.to(H_LIE, 0.16, "in")
    t.hold(0.55, breathe=0.6)
    t.to(H_TRY, 0.5, "io")
    t.hold(max(0.0, PUNCH - 0.05 - t.n / FPS), breathe=1.2)
    t.to(H_LIE, 0.16, "in")
    pad(t, T, breathe=0.5)
    top = world(t)

    # bottom: snapped back, staggers, plants his feet, charges and leaps into a punch on the beat
    def build(dx_air, punch=H_PUNCH, dy_air=1.6):
        b = Anim(x0=0.0)
        b.frames = [dict(f) for f in h0.frames]
        b.to(H_STAGGER, 3 / FPS, "snap", mode="slide", dx=-0.8, sm=1)
        b.to({**H_STAGGER, "lean": -8}, 0.12, "out", mode="slide", dx=-0.5)
        b.cycle(M.BACKSTEP, 0.32, reverse=True, phase=0.75, blend=0.1, end="pass")
        b.to(H_GUARD, 0.3, "out")
        b.hold(0.2, breathe=0.6)
        b.to(H_SET, 0.18, "out")
        b.hold(0.1, breathe=0.0)
        b.cycle(M.SPRINT, (idx(PUNCH) - 6 - b.n) / FPS, phase=0.62, ramp=(1.5, 1.2), blend=0.1)
        b.to(punch, 7 / FPS, "out", mode="air", dx=dx_air, dy=dy_air, sm=1)
        return b
    chest = giant[idx(PUNCH)]["chest"]
    punch = H_PUNCH
    dx_air, dy_air = 3.0, 1.6
    for _ in range(4):                                   # the fist lands on the giant's chest at PUNCH
        J = world(build(dx_air, punch, dy_air))[idx(PUNCH)]
        dx_air += chest[0] - 0.42 * G - 0.3 - J["wristR"][0]     # knuckles on the chest's outline
        dy_air += (chest[1] - 0.6) - J["neck"][1] - 0.3  # a leaping uppercut: shoulders just under the target
        punch = aim(punch, "R", (chest[0] - J["pelvis"][0], chest[1] - J["pelvis"][1]))
    b = build(dx_air, punch, dy_air)
    b.hold(2 / FPS, punch, breathe=0.0, mode="free")    # short hit-stop: the shadow bursts
    b.to(H_LAND, 0.2, "in", mode="air", dx=0.7, dy=-dy_air)
    b.to(H_LAND, 2 / FPS, "out", sm=1)
    b.to(H_STAND, 0.45, "out")
    pad(b, T, breathe=0.8)
    bottom = world(b)
    giant_b = giant[: idx(PUNCH) + 1] + [None] * (len(bottom) - idx(PUNCH) - 1)
    return {"top": {"hero": top, "shadow": giant}, "bottom": {"hero": bottom, "shadow": giant_b},
            "marks": {"HIT": HIT, "PUNCH": PUNCH, "G": G}}


# ================================================================ TURN BACK / ONE MORE
TIRED = {"lean": 58, "nod": -20, "thR": 26, "knR": 34, "thL": -6, "knL": 30, "arR": 34, "elR": 6,
         "arL": 26, "elL": 8}
DIP = {"lean": 40, "nod": -26, "thR": 46, "knR": 30, "ftR": 10, "thL": -40, "knL": 40, "ftL": -40,
       "arR": -80, "elR": 20, "arL": -70, "elL": 30}
CROUCH = {"lean": 30, "nod": -10, "thR": 54, "knR": 92, "thL": 40, "knL": 84, "arR": -30, "elR": 60,
          "arL": -20, "elL": 70}
VICTORY = {"lean": -12, "nod": -24, "thR": 8, "knR": 20, "thL": -12, "knL": 40, "arR": 108, "elR": 22,
           "arL": 96, "elL": 30}


def race():
    QUIT, RIBBON, HIT = 1.85, 6.16, 8.63
    T = DUR["race"]
    t = Anim(x0=0.0)
    t.cycle(M.SPRINT, QUIT, phase=0.3, blend=0.0)
    ph = t.cycle(M.JOG, 0.6, phase=0.3, blend=0.3)
    t.cycle(M.TRUDGE, 0.9, phase=ph % 1, blend=0.3, end="pass")
    t.to(TIRED, 0.3, "out")
    for k in range(int(1.1 * FPS)):                       # panting
        b_ = math.sin(2 * math.pi * k / 9)
        t.frames.append({"pose": {**full(TIRED), "lean": TIRED["lean"] + 3 * b_, "nod": TIRED["nod"] + 4 * b_},
                         "mode": "plant"})
    t.to(M.STAND, 0.35, "io")
    t.hold(0.15, breathe=0.5)
    t.to({**M.STAND, "nod": 14, "yaw": 90}, 0.12, "in")    # turns around: a quick pass through a front view
    t.to({**M.STAND, "nod": 20, "yaw": 180}, 0.12, "out")
    w1 = world(t)
    # the walk back: a separate pass that faces -x (gait and foot locks stay in their own frame)
    t2 = Anim(x0=t.roots[-1][0], facing=-1)
    t2.hold(1 / FPS, {**M.STAND, "nod": 20})
    t2.cycle(M.TRUDGE, T - (t.n + 1) / FPS + 0.2, phase=0.25, blend=0.2)   # first step from the passing pose
    top = w1 + world(t2)[1:]

    b = Anim(x0=0.0)
    b.cycle(M.SPRINT, 3.0, phase=0.3, blend=0.0)
    ph = b.cycle(M.SPRINT, 1.9, phase=(0.3 + 3.0 / 0.62) % 1, rate=0.82, blend=0.4,
                 mods={"lean": 8, "nod": 20})                # grinding, head down
    ph = b.cycle(M.SPRINT, (idx(RIBBON) - 3 - b.n) / FPS, phase=ph % 1, ramp=(0.9, 1.3), blend=0.25,
                 mods={"nod": -6})                            # ONE MORE: head up, faster
    b.to(DIP, 3 / FPS, "out", sm=1)
    i_rib = b.n - 1
    ph = b.cycle(M.SPRINT, 0.6, phase=(ph + 3 * 1.3 / (M.SPRINT.period * FPS)) % 1, blend=0.2)
    ph = b.cycle(M.JOG, 0.6, phase=ph % 1, blend=0.3)
    b.cycle(M.WALK, max(0.3, HIT - 0.45 - 0.35 - b.n / FPS), phase=ph % 1, blend=0.3, end="pass")
    b.to(M.STAND, 0.3, "out")
    b.to(CROUCH, (idx(HIT) - 2 - b.n) / FPS, "io")
    b.to(VICTORY, 0.18, "out", mode="air", dy=1.2, dx=0.3, sm=1)
    b.to(VICTORY, 0.18, "in", mode="air", dy=-1.2, dx=0.2)
    b.to({**VICTORY, "knR": 40, "knL": 50, "thR": 20}, 2 / FPS, "out")
    b.to(VICTORY, 0.25, "out")
    pad(b, T, breathe=1.0)
    bottom = world(b)
    rib_x = bottom[i_rib - 3]["chest"][0] + 0.34          # the tape touches his chest 3 frames before the beat
    return {"top": {"hero": top}, "bottom": {"hero": bottom},
            "marks": {"ribbon_x": rib_x, "RIBBON": RIBBON, "HIT": HIT, "QUIT": QUIT}}


def props_none(m, half):
    def draw(dr, i, P):
        if "ribbon_x" in m and half == "bottom":
            x0, y0 = P(m["ribbon_x"], 0)
            dr.line([(x0, y0), (x0, y0 - 300)], fill=(30, 30, 30, 255), width=6)
    return draw


SCENES = {"wall": wall, "gap": gap, "fist": fist, "race": race}


def props_wall(m, half):
    def draw(dr, i, P):
        x0, y0 = P(m["wall_x"], 0)
        x1, y1 = P(m["wall_x"] + 3.0, 14)
        if half == "top" or i < idx(m["D"]):
            dr.rectangle([x0, y1, x1, y0], fill=(70, 66, 60, 255))
        if half == "top":
            s = m["seat"]
            a0, b0 = P(s["x0"], 0)
            a1, b1 = P(s["x1"], s["top"])
            dr.rectangle([a0, b1, a1, b0], fill=(110, 104, 94, 255))
    return draw


PROPS = {"wall": props_wall, "gap": props_gap, "fist": props_none, "race": props_none}


BONES = [("pelvis", "chest"), ("chest", "neck"), ("neck", "head"), ("chest", "shL"), ("chest", "shR"),
         ("shL", "elbL"), ("elbL", "wristL"), ("shR", "elbR"), ("elbR", "wristR"), ("pelvis", "hipL"),
         ("pelvis", "hipR"), ("pelvis", "kneeL"), ("kneeL", "ankleL"), ("ankleL", "toeL"), ("pelvis", "kneeR"),
         ("kneeR", "ankleR"), ("ankleR", "toeR")]


def upsample(frames: list, k: int = 2) -> list:
    """30 -> 30*k fps: in-betweens between poses, with every bone kept at its length (a straight blend of joint
    positions would shrink limbs that swing fast). Hidden (None) frames stay hidden."""
    out = []
    for i, a in enumerate(frames):
        out.append(a)
        b = frames[i + 1] if i + 1 < len(frames) else None
        for m in range(1, k):
            if a is None or b is None:
                out.append(a if b is None else None)
                continue
            u = m / k
            a0 = frames[i - 1] if i > 0 and frames[i - 1] is not None else a
            b1 = frames[i + 2] if i + 2 < len(frames) and frames[i + 2] is not None else b

            def cub(j, c, a0=a0, b1=b1, a=a, b=b, u=u):
                p0, p1, p2, p3 = a0[j][c], a[j][c], b[j][c], b1[j][c]
                if abs(p2 - p1) < 1e-6:                  # holds stay perfectly still
                    return p1
                v = 0.5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                           + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
                lo, hi = min(p1, p2), max(p1, p2)           # no overshoot past either neighbouring pose
                return max(lo, min(hi, v))
            mid = {j: tuple(cub(j, c) for c in range(3)) for j in a if not j.startswith("_")}
            for pa, ch in BONES:                      # restore lengths, parent first
                ln = math.dist(a[pa], a[ch])
                d = [mid[ch][c] - mid[pa][c] for c in range(3)]
                n = math.sqrt(sum(v * v for v in d)) or 1.0
                mid[ch] = tuple(mid[pa][c] + d[c] / n * ln for c in range(3))
            for key in set(a) | set(b):
                if key.startswith("_"):                     # per-frame numbers (head size, cover weight) blend too
                    mid[key] = a.get(key, 0.0) + (b.get(key, 0.0) - a.get(key, 0.0)) * u
            out.append(mid)
    return out


OUT_FPS = 60


def export(name: str, out: Path) -> dict:
    """Both halves -> <out>/<name>_<half>.json (mocap units at OUT_FPS, for the Blender scene) + 30 fps previews."""
    res = SCENES[name]()
    out.mkdir(parents=True, exist_ok=True)
    for half in ("top", "bottom"):
        figs = res[half]
        ups = {k: upsample(v, OUT_FPS // FPS) for k, v in figs.items()}
        data = {"figures": {k: to_mocap(v) for k, v in ups.items()},
                "cover": {k: [round(f.get("_cover", 0.0), 3) if f else 0.0 for f in v] for k, v in ups.items()},
                "marks": res["marks"], "r_unit": R_UNIT, "fps": OUT_FPS}
        (out / f"{name}_{half}.json").write_text(json.dumps(data), encoding="utf-8")
        mp4 = preview(figs, out / f"{name}_{half}", props=PROPS[name](res["marks"], half), s=28.0 if name == "fist" else 52.0)
        sheet(mp4, 0, DUR[name], out / f"{name}_{half}_sheet.jpg", cols=15, width=128, fps=30)
    return res


if __name__ == "__main__":
    export(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "projects" / "ink_rift" / "anim")
