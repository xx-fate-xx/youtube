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
BEAT = 0.67
T_SPLIT, T_DAWN, T_OUT = 1.84, 8.54, 9.21
N = int(round(4 * 4 * BEAT * kit.FPS))            # 4 bars
F = lambda t: int(round(t * kit.FPS)) + 1          # noqa: E731  seconds -> frame
BG = ROOT / "projects" / "ink_proto3d" / "bg"

S = kit.Scene(OUT, N)
if HALF == "top":
    S.plates(BG / "plate_night.png")
else:
    S.plates(BG / "plate_night.png", BG / "plate_calm.png",
             mix_keys=[(F(T_DAWN) - 1, 0.0), (F(T_DAWN + 1.2), 1.0)])
S.sun.data.energy = 3.0

hero = kit.Hero(S, kit.toon("hero", (0.99, 0.975, 0.94), (0.78, 0.75, 0.70)))
pool_mat = kit.glow("pool", kit.PAPER, 1.0, soft=0.45)

# ---------------------------------------------------------------- motion
start = kit.to_origin(kit.load("80_41", 0.0, T_SPLIT + 0.05), 0)          # both: standing, a little cold
n0 = len(start)
if HALF == "top":
    rest = kit.blend(start[-1], kit.exaggerate(kit.to_origin(kit.load("80_41", T_SPLIT, None), 0), 1.7), 8)
    track = start + rest
    track += kit.idle(track[-1], max(0, N + 2 - len(track)))
else:
    walk = kit.walk_loop("02_01", (N - n0) / kit.FPS + 1, speed=1.2)
    walk = kit.shift(walk, start[-1]["pelvis"][0], start[-1]["pelvis"][2])
    track = start + kit.blend(start[-1], walk, 10)
hero.drive(track[: N + 2], 1)

# ---------------------------------------------------------------- light pools
first = kit.disc(S, "pool0", pool_mat, 1.5)
kit.key(first, 1, scale=(1.5, 1.5, 1))
if HALF == "top":
    for t, r in ((T_SPLIT, 1.5), (T_SPLIT + 2.0, 1.15), (T_DAWN, 0.45), (T_OUT - 0.05, 0.38)):
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
        x = sum(xs[max(0, fr - 12): fr]) / max(1, len(xs[max(0, fr - 12): fr])) if fr > 1 else xs[0]
        kit.key(target, fr, loc=(x + 0.6, 0, 1.45))
        kit.key(cam, fr, loc=(x + 0.2, -5.8, 1.8))

S.render(stills=[30, 90, 180, 260, 315] if "--still" in sys.argv else None)
