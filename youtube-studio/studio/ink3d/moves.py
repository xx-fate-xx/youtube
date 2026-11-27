"""Gaits and key poses for the ink stickman (studio/ink3d/pose2d.py). Poses face +x; angles in degrees.

Cycles: phase 0 = right foot contact; 8 evenly spaced keys per cycle (contact, down, passing, up / push-off ...),
the left limbs follow half a cycle later. Classic run/walk key poses, exaggerated for a cartoon: deep lean, high
knee drive, tight 90-degree arm pumps.
"""

from __future__ import annotations

from studio.ink3d.pose2d import Cycle

SPRINT = Cycle({
    "thR": [32, 12, -14, -40, -30, -6, 42, 58],
    "knR": [12, 40, 24, 16, 88, 128, 112, 50],
    "ftR": [-6, 24, 18, -40, -40, -28, -12, -4],
    "arR": [-60, -42, 0, 48, 70, 52, 4, -44],
    "elR": [60, 72, 88, 98, 104, 96, 78, 64],
    "lean": [18, 19, 18, 17, 18, 19, 18, 17],
    "nod": [-12] * 8,
    "lift": [0, 0, 0, 0.35, 0.1, 0, 0, 0.35, 0.1, 0, 0, 0, 0, 0, 0, 0][:8],
}, period=0.62)

JOG = Cycle({
    "thR": [26, 10, -8, -28, -24, -4, 30, 38],
    "knR": [10, 30, 18, 12, 60, 95, 80, 35],
    "ftR": [-6, 18, 12, -30, -30, -20, -8, -4],
    "arR": [-40, -28, 0, 32, 46, 34, 2, -30],
    "elR": [70, 78, 85, 90, 92, 88, 80, 72],
    "lean": [9, 10, 9, 8, 9, 10, 9, 8],
    "nod": [-5] * 8,
    "lift": [0, 0, 0, 0.18, 0, 0, 0, 0.18],
}, period=0.70)

WALK = Cycle({
    "thR": [26, 16, 0, -16, -24, -8, 20, 30],
    "knR": [4, 20, 12, 6, 34, 74, 52, 10],
    "ftR": [-16, 6, 14, 10, -20, 6, 14, -4],
    "arR": [-34, -22, 0, 22, 34, 22, 0, -22],
    "elR": [14, 16, 22, 30, 36, 30, 22, 16],
    "lean": [5, 6, 5, 5, 5, 6, 5, 5],
    "nod": [0] * 8,
}, period=1.0)

# a tired, heavy walk (slumped, small arm swing): giving up
TRUDGE = Cycle({
    "thR": [20, 13, 0, -13, -20, -4, 18, 23],
    "knR": [8, 22, 14, 10, 40, 78, 52, 14],
    "ftR": [-12, 4, 12, 4, -22, 4, 14, -2],
    "arR": [-12, -8, 0, 8, 12, 8, 0, -8],
    "elR": [10, 10, 12, 14, 14, 14, 12, 10],
    "lean": [8, 9, 8, 8, 8, 9, 8, 8],
    "nod": [24] * 8,
}, period=1.15)

# stepping backwards (play with reverse=True): upright, leaning back a little, eyes front, arms loose and forward
BACKSTEP = Cycle({
    "thR": [24, 14, 0, -16, -22, -8, 16, 26],
    "knR": [6, 16, 8, 6, 34, 62, 44, 10],
    "ftR": [-6, 0, 8, 5, 0, 8, 12, 0],
    "arR": [26, 22, 18, 22, 26, 22, 18, 22],
    "elR": [55, 50, 45, 50, 55, 50, 45, 50],
    "lean": [-7, -6, -7, -8, -7, -6, -7, -8],
    "nod": [4] * 8,
}, period=0.62)

# charging with the head down behind crossed arms: long low strides, torso nearly upright
CHARGE_RUN = Cycle({
    "thR": [40, 22, -6, -36, -44, -18, 22, 42],
    "knR": [18, 34, 22, 10, 34, 64, 56, 30],
    "ftR": [-8, 18, 14, -30, -32, -10, 0, -4],
    "arR": [-40, -28, 0, 30, 40, 28, 0, -28],
    "elR": [60, 64, 70, 76, 80, 76, 70, 64],
    "lean": [11, 12, 11, 10, 11, 12, 11, 10],
    "nod": [0] * 8,
    "lift": [0, 0, 0, 0.12, 0, 0, 0, 0.12],
}, period=0.6)

STAND = {"lean": 2, "nod": 0, "thR": 3, "knR": 3, "thL": -3, "knL": 3, "arR": -6, "elR": 12, "arL": 6, "elL": 14}


def demo():
    from studio.ink3d.pose2d import Anim, world
    a = Anim()
    a.hold(0.4, STAND)
    a.cycle(WALK, 2.0)
    a.cycle(SPRINT, 2.5, blend=0.25)
    a.cycle(JOG, 1.2, blend=0.3)
    return {"hero": world(a)}
