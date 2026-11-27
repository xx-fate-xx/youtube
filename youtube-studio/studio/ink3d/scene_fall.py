"""ink_mindset metaphor 2: STAY DOWN / GET UP — run inside Blender:

    blender -b -P studio/ink3d/scene_fall.py -- <top|bottom> <out_dir>

A storm. Both run in from the left; on the beat (1.59 s) both trip and fall flat. Top (STAY DOWN): he stays on the
ground and the world sinks into darkness. Bottom (GET UP): he pushes himself up, breaks into a sprint on the strong
beat (4.76 s) and on the next one (6.35 s) the storm breaks open into the painted morning.
Local time 0 = 8.06 s of the Short (Five Armies cut from 6.20 s; beat 0.794 s).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from studio.ink3d import kit  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if not a.startswith("--")]
HALF = argv[0] if argv else "bottom"
OUT = ROOT / (argv[1] if len(argv) > 1 else f"projects/ink_proto3d/render/fall_{HALF}")
T_FALL, T_RISE, T_SPRINT, T_CLEAR = 1.59, 3.45, 4.76, 6.35
N = int(round(7.94 * kit.FPS)) + 2
F = lambda t: int(round(t * kit.FPS)) + 1          # noqa: E731
BG = ROOT / "projects" / "ink_proto3d" / "bg"

S = kit.Scene(OUT, N)
if HALF == "top":
    S.plates(BG / "plate_dark.png", bright_keys=[(1, 0.0), (F(T_FALL), 0.0), (N, -45.0)])
else:
    S.plates(BG / "plate_dark.png", BG / "plate_calm.png", mix_keys=[(F(T_CLEAR) - 1, 0.0), (F(T_CLEAR + 0.9), 1.0)])
hero = kit.Hero(S)
rig = kit.Rig()


def at(track, ref):                                   # continue a clip from where the previous one ended
    return kit.shift(track, ref["pelvis"][0] - track[0]["pelvis"][0], ref["pelvis"][2] - track[0]["pelvis"][2])


run = rig.track("Jog_Fwd_Loop", seconds=T_FALL + 0.3, speed=0.85)
run = kit.shift(run, -run[0]["pelvis"][0] - 2.2, -run[0]["pelvis"][2])
nr = int(round(T_FALL * kit.FPS))
fall = at(rig.track("Death01"), run[nr - 1])
track = run[:nr] + kit.blend(run[nr - 1], fall, 4)
if HALF == "top":
    track += kit.idle(track[-1], N + 2 - len(track))
else:
    lie = kit.idle(track[-1], max(0, int(round(T_RISE * kit.FPS)) - len(track)))
    track += lie
    up = rig.track("Death01")[::-1]                                              # the fall, backwards: he gets up
    up = kit.shift(up, track[-1]["pelvis"][0] - up[0]["pelvis"][0], track[-1]["pelvis"][2] - up[0]["pelvis"][2])
    n_up = int(round((T_SPRINT - T_RISE) * kit.FPS))
    track += [up[min(len(up) - 1, int(i * len(up) / n_up))] for i in range(n_up)]
    sprint = at(rig.track("Sprint_Loop", seconds=(N - len(track)) / kit.FPS + 1, speed=0.8), track[-1])
    track += kit.blend(track[-1], sprint, 6)
track += kit.idle(track[-1], max(0, N + 2 - len(track)))
hero.drive(track[: N + 2], 1)

cam, target = S.camera(lens=42)
xs = [kit.mc(f["pelvis"]).x for f in track[: N + 2]]
for fr in range(1, N + 2, 4):
    x = xs[min(fr - 1, len(xs) - 1)]
    kit.key(target, fr, loc=(x + 0.5, 0, 1.25))
    kit.key(cam, fr, loc=(x + 0.2, -5.6, 1.6))

kit.export_2d(S, hero, OUT / "joints2d.json")
S.render(stills=[20, 50, 70, 100, 130, 160, 200, 235] if "--still" in sys.argv else None)
