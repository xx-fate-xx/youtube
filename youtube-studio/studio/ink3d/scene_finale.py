"""ink_mindset finale (full screen, portrait) — run inside Blender:

    blender -b -P studio/ink3d/scene_finale.py -- <out_dir>

Morning. He sprints left to right toward a huge vermilion sun; the camera tracks low beside him. He launches into
a jump so that the apex lands on the track's biggest hit (5.23 s local = 21.23 s of the Short), and time stops
there: he hangs in the air against the sun while the camera keeps pushing in (the comic engine adds the flash and
"DAY ONE."). Local time 0 = 16.00 s of the Short.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mathutils import Euler  # noqa: E402

from studio.ink3d import kit  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if not a.startswith("--")]
OUT = ROOT / (argv[0] if argv else "projects/ink_proto3d/render/finale")
T_TAKEOFF, T_APEX = 4.60, 5.23
N = int(round(10.0 * kit.FPS)) + 2
F = lambda t: int(round(t * kit.FPS)) + 1          # noqa: E731
BG = ROOT / "projects" / "ink_proto3d" / "bg"

S = kit.Scene(OUT, N, size=(1200, 2133))
S.plates(BG / "plate_calm_tall.png")
hero = kit.Hero(S)
rig = kit.Rig()

n_to = int(round(T_TAKEOFF * kit.FPS))
sprint = rig.track("Sprint_Loop", seconds=T_TAKEOFF + 0.5, speed=0.8)
sprint = kit.shift(sprint, -sprint[n_to]["pelvis"][0], -sprint[0]["pelvis"][2])   # takeoff at x = 0
track = sprint[:n_to]
vx = sprint[n_to]["pelvis"][0] - sprint[n_to - 1]["pelvis"][0]                    # sprint speed per frame
# leap pose: the sprint frame with the widest stride, frozen and lifted (reads as a heroic flying leap)
stride = max(range(len(sprint)), key=lambda i: abs(sprint[i]["ankleL"][0] - sprint[i]["ankleR"][0]))
leap = sprint[stride]
n_up = int(round((T_APEX - T_TAKEOFF) * kit.FPS))
peak = 0.55                                                                        # apex height (x body height)
for i in range(n_up + 1):
    u = i / n_up
    lift = peak * (1 - (1 - u) ** 2)                                                 # decelerating rise
    track.append({j: [p[0] - leap["pelvis"][0] + sprint[n_to - 1]["pelvis"][0] + vx * (i + 1), p[1] + lift,
                      p[2] - leap["pelvis"][2]] for j, p in leap.items()})
track[n_to:] = kit.blend(track[n_to - 1], track[n_to:], 5)
apex = track[-1]
track += kit.idle(apex, N + 2 - len(track))                                          # time stops at the apex
hero.drive(track[: N + 2], 1)

cam, target = S.camera(lens=38)
xs = [kit.mc(f["pelvis"]).x for f in track[: N + 2]]
zs = [kit.mc(f["pelvis"]).z for f in track[: N + 2]]
for fr in range(1, N + 2, 3):
    i = min(fr - 1, len(xs) - 1)
    push = 0.0                                       # camera holds after the apex (the edit adds the push-in)
    kit.key(target, fr, loc=(xs[i] + 0.3, 0, 1.5 + 0.9 * push))                    # fixed height: the leap rises in frame
    kit.key(cam, fr, loc=(xs[i] + 0.1, -6.0 + 1.8 * push, 0.5))                      # low angle: he flies above us


# a holdout below the painted horizon (fixed on screen: the plate does not move), parented to the camera, so the
# sun rises from behind the hills instead of floating over the ground
import bpy  # noqa: E402

hold = bpy.data.objects.new("hold", bpy.data.meshes.new("hold"))
D = 28.0
hold.data.from_pydata([(-60, -80, -D), (60, -80, -D), (60, -0.012 * D, -D), (-60, -0.012 * D, -D)], [], [(0, 1, 2, 3)])
hm = bpy.data.materials.new("holdout")
hm.use_nodes = True
hm.node_tree.nodes.clear()
hm.node_tree.links.new(hm.node_tree.nodes.new("ShaderNodeHoldout").outputs[0],
                       hm.node_tree.nodes.new("ShaderNodeOutputMaterial").inputs[0])
hold.data.materials.append(hm)
hold.parent = cam
S.sc.collection.objects.link(hold)
S.no_outline(hold)
hold.visible_shadow = False

# the sun sits exactly behind his chest at the apex (on the camera ray), rising into place before it
from mathutils import Vector  # noqa: E402

sun = kit.disc(S, "sun", kit.glow("vermilion", kit.VERMILION, 1.0, soft=0.03), 46.0)   # far away: no parallax
sun.rotation_euler = Euler((math.radians(90), 0, 0))
S.sc.frame_set(F(T_APEX))                          # fixed world spot: behind his chest at the apex
c = cam.matrix_world.translation.copy()
ray = kit.mc(apex["chest"]) - c
spot = c + ray * ((300 - c.y) / ray.y)
kit.key(sun, 1, loc=spot - Vector((0, 0, 32.0)))                  # a half sun on the hills when he starts running
kit.key(sun, F(T_APEX), loc=spot)                                # risen fully behind him at the top of the leap
kit.key(sun, N, loc=spot + Vector((0, 0, 3.0)))

kit.export_2d(S, hero, OUT / "joints2d.json")
S.render(stills=[30, 100, 138, 150, 157, 200, 290] if "--still" in sys.argv else None)
