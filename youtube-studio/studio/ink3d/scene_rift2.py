"""ink_mindset pilot "The Rift", v2: the world (plates, props, camera, light) in Blender; the figures' motion comes
from the pose-to-pose animation (studio/ink3d/rift_anim.py -> projects/ink_rift/anim/<meta>_<half>.json).

    blender -b -P studio/ink3d/scene_rift2.py -- <wall|gap|fist|race> <top|bottom> <out_dir> [--still]
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

from studio.ink3d import kit  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if not a.startswith("--")]
META, HALF = argv[0], argv[1]
OUT = ROOT / argv[2]
DUR = {"wall": 7.50, "gap": 4.93, "fist": 5.56, "race": 12.01}[META]
data = json.loads((ROOT / "projects" / "ink_rift" / "anim" / f"{META}_{HALF}.json").read_text(encoding="utf-8"))
FPS = kit.FPS = data.get("fps", 30)
N = int(round(DUR * FPS)) + 2
F = lambda t: int(round(t * FPS)) + 1          # noqa: E731   Blender frame shown at local time t
SM = FPS / 30                                  # smoothing windows were tuned in 30 fps frames
BG = ROOT / "projects" / "ink_proto3d" / "bg"

RU = data["r_unit"]
MK = data["marks"]


def mx(r: float) -> float:
    """A mark in R units -> Blender x (metres)."""
    return r * RU * kit.HEIGHT


S = kit.Scene(OUT, N)


def figure(name: str, scale: float = 1.0):
    fr = data["figures"][name]
    hero = kit.Hero(S, scale=scale)
    seen = [f for f in fr if f is not None]
    full = []
    last = seen[0]
    for f in fr[: N + 2]:
        last = f if f is not None else last
        full.append(last)
    full += [last] * max(0, N + 2 - len(full))
    hero.drive(full, 1)
    if any(f is None for f in fr):
        hero.hide_from = next(i for i, f in enumerate(fr) if f is None) + 1
    return hero, full


hero, track = figure("hero")
FRONT = []                        # (object, fill): props between the camera and the figures, drawn over them in 2D
CAM = {}                          # the tracking camera's x path (for the plate parallax)
GROUND = [(-1e9, 1e9)]            # x ranges with ground under the figures (soft contact shadows only there)
PARALLAX = 0.07                   # the painted plate moves this fraction of the camera's travel
others = {}
if "shadow" in data["figures"]:
    others["shadow"], gtrack = figure("shadow", scale=MK.get("G", 1.9))
PX = [kit.mc(f["pelvis"]).x for f in track]


def ortho(cam, lens, dist):
    """Flat side view: an orthographic camera with the framing the perspective lens had at `dist`, kept level, so
    box props show no top or side faces (no slanted corners) - the world reads like a 2D drawing."""
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 36.0 / lens * dist
    return cam


def smooth(xs, w=9):
    w = int(round(w * SM))
    out = []
    for i in range(len(xs)):
        lo, hi = max(0, i - w), min(len(xs), i + w + 1)
        out.append(sum(xs[lo:hi]) / (hi - lo))
    return out


def track_camera(xs, lens=42, dist=6.6, height=1.5, aim=1.3, step=2):
    cam, target = S.camera(lens=lens)
    ortho(cam, lens, dist)
    mid = (height + aim) / 2                               # level: the old aim height splits the difference
    for fr in range(1, N + 2, step):
        x = xs[min(fr - 1, len(xs) - 1)]
        kit.key(target, fr, loc=(x, 0, mid))
        kit.key(cam, fr, loc=(x, -dist, mid))              # parallel tracking: the camera never rotates
    CAM["xs"], CAM["scale"] = xs, cam.data.ortho_scale
    return cam


def holdout_below_horizon(cam, D=28.0, top=None):
    """A holdout card in front of everything below the painted horizon (top: its edge in camera-local metres)."""
    hold = bpy.data.objects.new("hold", bpy.data.meshes.new("hold"))
    t = -0.012 * D if top is None else top
    hold.data.from_pydata([(-80, -80, -D), (80, -80, -D), (80, t, -D), (-80, t, -D)], [],
                          [(0, 1, 2, 3)])
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


# ================================================================ WAIT FOR A DOOR / MAKE ONE
if META == "wall":
    D = MK["D"]
    if HALF == "top":
        S.plates(BG / "plate_night_wide.png", bright_keys=[(1, 0.0), (F(D), 0.0), (N, -10.0)])
    else:
        S.plates(BG / "plate_night_wide.png", BG / "plate_calm_wide.png", mix_keys=[(F(D) - 1, 0.0), (F(D + 0.5), 1.0)])
    stone = kit.flat("stone", (0.36, 0.34, 0.30))
    wall_x = mx(MK["wall_x"])
    g_night = S.ground(BG / "ground_light.png")             # light marks on the night plate
    if HALF == "bottom":                                    # morning after the wall breaks: ink marks
        g_day = S.ground(BG / "ground_ink.png", y=-0.61)
        for ob, on in ((g_night, True), (g_day, False)):
            ob.hide_render = not on
            ob.keyframe_insert("hide_render", frame=1)
            ob.hide_render = on
            ob.keyframe_insert("hide_render", frame=F(D + 0.25))
    if HALF == "top":
        sx0, sx1, stop = mx(MK["seat"]["x0"]), mx(MK["seat"]["x1"]), mx(MK["seat"]["top"])
        seat = kit.block(S, "seat", (sx1 - sx0, 0.8, stop), ((sx0 + sx1) / 2, 0.45, stop / 2))   # just behind him
        seat.data.materials.clear()
        seat.data.materials.append(stone)
    rnd = random.Random(3)
    bw, bh, rows = 0.45, 0.55, 8                         # shallow in depth: no side face swings into view
    for r in range(rows):
        for k in range(2):
            y = 0.25
            pos = Vector((wall_x + bw / 2 + k * bw, y, bh / 2 + r * bh))
            b = kit.block(S, f"w{r}_{k}", (bw * 0.98, 0.5, bh * 0.98), pos)
            b.data.materials.clear()
            b.data.materials.append(stone)
            kit.key(b, 1, loc=pos, rot=(0, 0, 0))
            if HALF == "bottom":
                kit.key(b, F(2.0), loc=pos + Vector((0.03, 0, 0)), rot=(0, 0, 0))     # the push: a tremor only
                kit.key(b, F(2.07), loc=pos - Vector((0.015, 0, 0)), rot=(0, 0, 0))
                kit.key(b, F(2.14), loc=pos, rot=(0, 0, 0))
                kit.key(b, F(D) - 1, loc=pos, rot=(0, 0, 0))
                v = Vector((rnd.uniform(5, 10), rnd.uniform(-2, 2) + y, rnd.uniform(2, 7)))
                for j in range(1, N - F(D) + 2, 2):        # bursts apart, tumbling, under gravity
                    t = j / FPS
                    kit.key(b, F(D) + j, loc=pos + v * t + Vector((0, 0, -4.9 * t * t)),
                            rot=(rnd.uniform(-1, 1) * 6 * t, rnd.uniform(-1, 1) * 6 * t, 0))
    if HALF == "top":
        xs = [min(x + 0.7, wall_x - 0.6) for x in PX]
        xs = [max(x, (wall_x + PX[i]) / 2) for i, x in enumerate(xs)]      # keeps him and the wall in frame
    else:
        xs = [min(x + 0.7, wall_x - 0.6) if i < F(D) - 1 else x + 0.7 for i, x in enumerate(PX)]
    track_camera(smooth(xs, 8))

# ================================================================ DOUBT / JUMP
elif META == "gap":
    TO = MK["TO"]
    S.plates(BG / "plate_calm_wide.png")
    edge = mx(MK["edge_top"] if HALF == "top" else MK["edge_bottom"])
    gap = mx(MK["gap"])
    kit.block(S, "cliff_near", (60, 1.6, 8), (edge - 30, 0.2, -4))     # shallow: no side faces grow on screen
    kit.block(S, "cliff_far", (60, 1.6, 8), (edge + gap + 30, 0.2, -4))
    S.ground(BG / "ground_ink.png", x0=edge - 120, x1=edge, y=-0.7)             # the road ends at the brink
    S.ground(BG / "ground_ink.png", x0=edge + gap, x1=edge + gap + 120, y=-0.7)
    GROUND[:] = [(-1e9, edge), (edge + gap, 1e9)]
    if HALF == "top":
        stop = PX[min(len(PX) - 1, F(TO) + 6)]
        far = edge + gap                                      # after the stop: him and the far side both in frame
        xs = [x + 0.9 if i < F(TO) else
              (stop + 0.9) + ((x + far) / 2 - (stop + 0.9)) * min(1.0, (i - F(TO)) / FPS) for i, x in enumerate(PX)]
        track_camera(smooth(xs, 6), lens=50, dist=8.0, height=1.2, aim=1.0)
    else:
        track_camera(smooth([x + 0.9 for x in PX], 4), lens=50, dist=8.0, height=1.95, aim=1.75)

# ================================================================ STAY DOWN / HIT BACK
elif META == "fist":
    HIT, PUNCH = MK["HIT"], MK["PUNCH"]
    if HALF == "top":
        S.plates(BG / "plate_dark_wide.png", bright_keys=[(1, 0.0), (F(HIT), 0.0), (N, -30.0)])
    else:
        S.plates(BG / "plate_dark_wide.png", BG / "plate_calm_wide.png", mix_keys=[(F(PUNCH) - 1, 0.0), (F(PUNCH + 0.4), 1.0)])
    S.ground(BG / "ground_ink.png")
    gx = kit.mc(gtrack[0]["pelvis"]).x
    cx = (PX[0] + gx) / 2 - 0.2
    cam, target = S.camera(lens=36)
    ortho(cam, 36, 7.8)
    kit.key(target, 1, loc=(cx, 0, 1.8))
    kit.key(cam, 1, loc=(cx, -7.8, 1.8))
    cam.data.keyframe_insert("ortho_scale", frame=1)
    cam.data.ortho_scale = 36.0 / 36 * 7.1                 # slow push-in
    cam.data.keyframe_insert("ortho_scale", frame=N)

# ================================================================ TURN BACK / ONE MORE
elif META == "race":
    QUIT, RIBBON, HIT = MK["QUIT"], MK["RIBBON"], MK["HIT"]
    S.plates(BG / "plate_calm_wide.png", bright_keys=[(1, 0.0), (F(QUIT), 0.0), (N, -18.0)] if HALF == "top" else None)
    S.ground(BG / "ground_ink.png")
    if HALF == "top":
        stop = F(QUIT + 1.4)                                   # the camera stops with him; he walks back out
        xs = [x + 0.6 if i < stop else PX[stop] + 0.6 for i, x in enumerate(PX)]
        track_camera(smooth(xs, 10))
    else:
        rx = mx(MK["ribbon_x"])
        CX = [kit.mc(f["chest"]).x + 0.1 for f in track]              # front of his chest (stroke radius)
        snap = F(RIBBON)
        verm = bpy.data.materials.get("verm_solid") or kit.flat("verm_solid", kit.VERMILION)
        for side in (-1, 1):                                          # -1: the near post (towards the camera)
            post = kit.block(S, f"pole{side}", (0.12, 0.12, 2.0), (rx, side * 1.2, 1.0))
            half = bpy.data.objects.new(f"rib{side}", None)
            S.sc.collection.objects.link(half)
            half.location = (rx, side * 1.2, 1.1)
            r = kit.block(S, f"ribbon{side}", (0.03, 1.0, 0.12), (0, -side * 0.5, 0), color=kit.VERMILION)
            r.data.materials.clear()
            r.data.materials.append(verm)
            r.parent = half
            if side == -1:
                FRONT += [(post, "#16140F"), (r, "#D9412B")]
            th_snap = 0.0
            for fr in range(1, N + 2):
                if fr < snap:                                         # straight across, then pulled by his chest
                    d = max(0.0, CX[min(fr - 1, len(CX) - 1)] - rx)
                    th, ln = side * math.atan2(d, 1.2), math.hypot(d, 1.2)
                    th_snap = th
                else:                                                 # snapped: both halves whip forward and settle
                    u = min(1.0, (fr - snap) / 7)
                    k = 1 - (1 - u) ** 3
                    th = th_snap + (side * math.radians(115) - th_snap) * k
                    if fr - snap > 7:
                        th = side * math.radians(115 - 25 * min(1.0, (fr - snap - 7) / 20))
                    ln = 1.2 * (1 - 0.35 * min(1.0, (fr - snap) / 5))  # the torn ends recoil a little
                half.rotation_euler = Euler((0, 0, th))
                half.scale = (1, ln, 1)
                half.keyframe_insert("rotation_euler", frame=fr)
                half.keyframe_insert("scale", frame=fr)
        cam = track_camera(smooth([x + 0.8 for x in PX], 6))
        # orthographic camera: the sun is a plain disc behind him (size/position don't shrink with distance),
        # rising from under the painted horizon on the hit
        sun = kit.disc(S, "sun", kit.glow("vermilion", kit.VERMILION, 1.0, soft=0.03), 0.75)
        sun.rotation_euler = Euler((math.radians(90), 0, 0))
        ex = PX[min(len(PX) - 1, F(HIT))] + 1.5
        kit.key(sun, 1, loc=(ex, 40, -1.0))
        kit.key(sun, F(HIT) - 2, loc=(ex, 40, -1.0))
        kit.key(sun, F(HIT + 0.35), loc=(ex, 40, 2.3))                               # bursts up on the hit
        kit.key(sun, N, loc=(ex, 40, 2.5))
        holdout_below_horizon(cam, top=-0.12)

if os.environ.get("DEBUG_PROJ"):
    from bpy_extras.object_utils import world_to_camera_view
    fr = int(os.environ["DEBUG_PROJ"])
    S.sc.frame_set(fr)
    W_ = S.sc.render.resolution_x
    for name, co in (("wall", Vector((mx(MK.get("wall_x", 0)), 0, 0.5))),
                     ("wristR", hero.joints["wristR"].matrix_world.translation.copy())):
        v = world_to_camera_view(S.sc, S.sc.camera, co)
        print("PROJ", name, tuple(round(c, 3) for c in co), round(v.x * W_, 1))
    for o in S.sc.objects:
        if o.name.startswith("w0_0"):
            print("PROJ block", o.name, tuple(round(c, 3) for c in o.matrix_world.translation), tuple(round(c, 3) for c in o.dimensions))
if CAM:                           # parallax: the far painting drifts a little against the camera's travel
    ppm = S.sc.render.resolution_x / CAM["scale"]
    x0 = CAM["xs"][0]
    S.scroll([(fr, -(CAM["xs"][min(fr - 1, len(CAM["xs"]) - 1)] - x0) * ppm * PARALLAX) for fr in range(1, N + 2, 2)])
kit.export_2d(S, hero, OUT / "joints2d.json", others)
if True:                          # soft contact shadows under the figures (fade as they leave the ground)
    from bpy_extras.object_utils import world_to_camera_view
    W_, H_ = S.sc.render.resolution_x, S.sc.render.resolution_y
    shadows = {}
    for name, h in {"hero": hero, **others}.items():
        rows = []
        for fr in range(S.sc.frame_start, S.sc.frame_end + 1):
            if h.hide_from is not None and fr >= h.hide_from:
                rows.append(None)
                continue
            S.sc.frame_set(fr)
            pel = h.joints["pelvis"].matrix_world.translation
            if not any(a <= pel.x <= b for a, b in GROUND):
                rows.append(None)
                continue
            low = min(h.joints[j].matrix_world.translation.z for j in ("ankleL", "ankleR", "toeL", "toeR"))
            g = world_to_camera_view(S.sc, S.sc.camera, Vector((pel.x, 0.0, 0.0)))
            rows.append([round(g.x * W_, 1), round((1 - g.y) * H_, 1), round(max(0.0, low - 0.08 * h.scale), 3)])
        shadows[name] = rows
    jp = OUT / "joints2d.json"
    jd = json.loads(jp.read_text(encoding="utf-8"))
    jd["shadow"] = shadows
    if data.get("cover"):
        jd["cover"] = data["cover"]
    jp.write_text(json.dumps(jd), encoding="utf-8")
if FRONT:                         # project the foreground props per frame; Blender doesn't render them
    from bpy_extras.object_utils import world_to_camera_view
    W_, H_ = S.sc.render.resolution_x, S.sc.render.resolution_y
    fronts = []
    for fr in range(S.sc.frame_start, S.sc.frame_end + 1):
        S.sc.frame_set(fr)
        polys = []
        for ob, fill in FRONT:
            pts = []
            for c in ob.bound_box:
                v = world_to_camera_view(S.sc, S.sc.camera, ob.matrix_world @ Vector(c))
                pts.append((v.x * W_, (1 - v.y) * H_))
            pts = sorted(set((round(x, 1), round(y, 1)) for x, y in pts))
            hull = []
            for seq in (pts, pts[::-1]):                         # monotone chain convex hull
                part = []
                for q in seq:
                    while len(part) >= 2 and ((part[-1][0] - part[-2][0]) * (q[1] - part[-2][1])
                                              - (part[-1][1] - part[-2][1]) * (q[0] - part[-2][0])) <= 0:
                        part.pop()
                    part.append(q)
                hull += part[:-1]
            polys.append({"pts": hull, "fill": fill})
        fronts.append(polys)
    jp = OUT / "joints2d.json"
    jd = json.loads(jp.read_text(encoding="utf-8"))
    jd["front"] = fronts
    jp.write_text(json.dumps(jd), encoding="utf-8")
    for ob, _ in FRONT:
        ob.hide_render = True
STILLS = os.environ.get("STILLS", "15 45 75 110 150 190 240 300")
S.render(stills=[int(x) for x in STILLS.split() if int(x) <= N] if "--still" in sys.argv else None)
