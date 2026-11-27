"""ink_mindset metaphor: STAY / STEP OUT — run inside Blender:

    blender -b -P studio/ink3d/scene_light.py -- <top|bottom> <out_dir> [--still]

Night. Both halves open the same: the hero stands in one small pool of light. On the hit (1.84 s) they split:
top (STAY) — he keeps standing, freezing, and the pool shrinks until the light goes out (9.21 s);
bottom (STEP OUT) — he walks into the dark and every footstep blooms a new pool of light, a path forms, and at
8.54 s dawn breaks: the night plate fades to the painted morning and a vermilion sun rises.
Timing is on the Five Armies cut (90 bpm, bar = 2.68 s): 4 bars = 10.72 s.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bpy  # noqa: E402
from mathutils import Euler  # noqa: E402

from studio.ink3d import kit  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if not a.startswith("--")]
HALF = argv[0] if argv else "bottom"
OUT = ROOT / (argv[1] if len(argv) > 1 else f"projects/ink_proto3d/render/light_{HALF}")
BEAT = 0.794                                        # Five Armies cut from 6.20 s: beats at 0.12 + k * 0.794
T_SPLIT, T_DAWN, T_OUT = 1.71, 4.88, 6.47
N = int(round(8.06 * kit.FPS)) + 2                  # metaphor 1 = 0 .. 8.06 s of the Short
F = lambda t: int(round(t * kit.FPS)) + 1          # noqa: E731  seconds -> frame
BG = ROOT / "projects" / "ink_proto3d" / "bg"

S = kit.Scene(OUT, N)
if HALF == "top":
    S.plates(BG / "plate_night.png")
else:
    S.plates(BG / "plate_night.png", BG / "plate_calm.png",
             mix_keys=[(F(T_DAWN) - 1, 0.0), (F(T_DAWN + 1.0), 1.0)])
S.sun.data.energy = 3.0

hero = kit.Hero(S)
pool_mat = kit.glow("pool", kit.PAPER, 1.0, soft=0.45)

# ---------------------------------------------------------------- motion (Quaternius CC0 game animations)
rig = kit.Rig()
n0 = int(round(T_SPLIT * kit.FPS))
start = rig.track("Idle_Loop", seconds=T_SPLIT + 0.1)[:n0]                  # both: standing in the light
if HALF == "top":
    hold = rig.track("Idle_Loop", seconds=1.6)                                    # he stays... and stays
    hold = kit.shift(hold, start[-1]["pelvis"][0] - hold[0]["pelvis"][0], start[-1]["pelvis"][2] - hold[0]["pelvis"][2])
    kneel = rig.track("Fixing_Kneeling", seconds=N / kit.FPS)                     # then sinks to one knee
    feet = lambda f, i: (f["ankleL"][i] + f["ankleR"][i]) / 2                       # noqa: E731
    kneel = kit.shift(kneel, feet(hold[-1], 0) - feet(kneel[0], 0), feet(hold[-1], 2) - feet(kneel[0], 2))
    low = min(range(min(len(kneel), 90)), key=lambda i: kneel[i]["pelvis"][1])     # the clip stands up again
    kneel = kneel[: low + 1]                                                       # later: keep only the way down
    track = start + kit.blend(start[-1], hold, 10)
    track += kit.blend(track[-1], kneel, 16)
else:
    walk = rig.track("Walk_Loop", seconds=T_DAWN - T_SPLIT + 0.4, speed=1.1)
    walk = kit.shift(walk, start[-1]["pelvis"][0], start[-1]["pelvis"][2])
    run = rig.track("Jog_Fwd_Loop", seconds=N / kit.FPS - T_DAWN + 1)       # at dawn he breaks into a run
    run = kit.shift(run, walk[-1]["pelvis"][0] - run[0]["pelvis"][0], walk[-1]["pelvis"][2] - run[0]["pelvis"][2])
    nw = int(round((T_DAWN - T_SPLIT) * kit.FPS))
    track = start + kit.blend(start[-1], walk[:nw], 10)
    track += kit.blend(track[-1], run, 8)
track += kit.idle(track[-1], max(0, N + 2 - len(track)))
hero.drive(track[: N + 2], 1)

# ---------------------------------------------------------------- light pools
first = kit.disc(S, "pool0", pool_mat, 1.5)
kit.key(first, 1, scale=(1.5, 1.5, 1))
if HALF == "top":
    for t, r in ((T_SPLIT, 1.5), (T_SPLIT + 1.4, 1.15), (T_OUT - 1.0, 0.45), (T_OUT - 0.05, 0.38)):
        kit.key(first, F(t), scale=(r, r, 1))
    kit.key(first, F(T_OUT), scale=(0.0, 0.0, 1))                         # the light goes out on the hit
    for fc in first.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "SINE"
else:
    steps = sorted(kit.plants(track[: N], "L") + kit.plants(track[: N], "R"))
    k = 0
    for i, ank in steps:
        if i < n0 + 6:
            continue
        p = kit.mc(ank)
        d = kit.disc(S, f"pool{k + 1}", pool_mat, 0.42, loc=(p.x + 0.1, p.y * 0.3, 0.003))
        kit.key(d, 1, scale=(0, 0, 1))
        kit.key(d, i, scale=(0, 0, 1))
        kit.key(d, i + 3, scale=(0.62, 0.62, 1))           # each footstep blooms its own pool of light
        kit.key(d, i + 7, scale=(0.42, 0.42, 1))
        k += 1
    sun_mat = kit.glow("vermilion", kit.VERMILION, 1.0, soft=0.04)
    end_x = kit.mc(track[N - 1]["pelvis"]).x
    sun = kit.disc(S, "sun", sun_mat, 1.4, loc=(end_x + 6, 18, -3))
    sun.rotation_euler = Euler((math.radians(90), 0, 0))
    kit.key(sun, 1, loc=(end_x + 6, 18, -3))
    kit.key(sun, F(T_DAWN), loc=(end_x + 6, 18, -3))
    kit.key(sun, N, loc=(end_x + 6, 18, 2.2))
    hold = bpy.data.objects.new("hold", bpy.data.meshes.new("hold"))            # hides the sun below the horizon
    hold.data.from_pydata([(-80, 16, -30), (80, 16, -30), (80, 16, 0), (-80, 16, 0)], [], [(0, 1, 2, 3)])
    hm = bpy.data.materials.new("holdout")
    hm.use_nodes = True
    hm.node_tree.nodes.clear()
    hm.node_tree.links.new(hm.node_tree.nodes.new("ShaderNodeHoldout").outputs[0],
                           hm.node_tree.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    hold.data.materials.append(hm)
    S.sc.collection.objects.link(hold)
    S.no_outline(hold)

# ---------------------------------------------------------------- camera: side view, he is big in frame
cam, target = S.camera(lens=45)
if HALF == "top":
    kit.key(target, 1, loc=(0.1, 0, 1.35))          # aim high: he stands low, the label band stays clear
    kit.key(cam, 1, loc=(3.6, -3.6, 1.6))                 # 3/4 front: his arms and hands read in front of the body
    kit.key(cam, N, loc=(3.1, -3.1, 1.5))                 # slow push in on him as the dark closes
else:
    xs = [kit.mc(f["pelvis"]).x for f in track[: N + 2]]
    for fr in range(1, N + 2, 6):                          # follow with a little lag, the path stays behind him
        x = xs[min(fr - 1, len(xs) - 1)] + 0.5                      # keep him centred, room ahead
        kit.key(target, fr, loc=(x + 0.6, 0, 1.45))
        kit.key(cam, fr, loc=(x + 0.2, -5.8, 1.8))

kit.export_2d(S, hero, OUT / "joints2d.json")
S.render(stills=[30, 91, 136, 180, 196, 241, 260, 315] if "--still" in sys.argv else None)
