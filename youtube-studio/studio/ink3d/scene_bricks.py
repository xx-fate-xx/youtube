"""Blender prototype (ink_mindset): EXCUSES vs STEPS — run inside Blender:

    blender -b -P studio/ink3d/scene_bricks.py -- <half: top|bottom> <out_dir> [frames]

Look: sumi-e ink — cream paper world, two-tone toon shading (white / grey wash), Freestyle ink outlines with a
slight hand wobble, one vermilion accent (the sun, bottom half only). The hero is one smooth skinned mesh driven
frame by frame by CMU motion-capture joints (exported by studio/ink3d/export_mocap.py), with a big round head.
Bricks are procedural: they rain into a pile (shared opening), then fly into a wall around him (top, EXCUSES) or
into a staircase he climbs (bottom, STEPS).
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
MOCAP = ROOT / "projects" / "ink_proto3d" / "mocap"
FPS = 30
HEIGHT = 1.8                                       # hero height (m); mocap joints are normalised to height 1
INK, PAPER, VERMILION = (0.086, 0.078, 0.059), (0.957, 0.929, 0.878), (0.851, 0.255, 0.169)

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if not a.startswith("--")]
HALF = argv[0] if argv else "bottom"
OUT = (ROOT / argv[1]) if len(argv) > 1 else ROOT / "projects" / "ink_proto3d" / "render" / HALF
NFRAMES = int(argv[2]) if len(argv) > 2 else 270
PLATE = (ROOT / argv[3]) if len(argv) > 3 else None   # painted ink background (1200x1066) behind the 3D action


def srgb(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


# ---------------------------------------------------------------- scene, world, render settings

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x, sc.render.resolution_y = 1200, 1066      # 10 % margin for the 2D engine's camera
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, NFRAMES
sc.view_settings.view_transform = "Standard"
sc.render.film_transparent = PLATE is not None
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = str(OUT) + "/"
world = bpy.data.worlds.new("paper")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = srgb(PAPER)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.world = world

# ink outlines
sc.render.use_freestyle = True
sc.render.line_thickness_mode = "ABSOLUTE"
ls = sc.view_layers[0].freestyle_settings.linesets[0] if sc.view_layers[0].freestyle_settings.linesets else \
    sc.view_layers[0].freestyle_settings.linesets.new("ink")
ls.select_by_visibility, ls.select_by_edge_types = True, True
ls.select_silhouette, ls.select_border, ls.select_crease = True, True, False
ls.select_contour = True
lst = ls.linestyle or bpy.data.linestyles.new("ink")
ls.linestyle = lst
lst.color = INK
lst.thickness = 4.2
lst.chaining = "PLAIN"
lst.caps = "ROUND"
cal = lst.thickness_modifiers.new("calligraphy", "CALLIGRAPHY")   # thick/thin like a brush held at an angle
cal.orientation, cal.thickness_min, cal.thickness_max = 55.0, 1.2, 4.6
th = lst.thickness_modifiers.new("brush", "NOISE")
th.amplitude, th.period, th.blend = 1.2, 30.0, "ADD"
gm = lst.geometry_modifiers.new("wobble", "PERLIN_NOISE_1D")
gm.frequency, gm.amplitude, gm.octaves = 6.0, 1.6, 2


def toon(name, lit, shade, dark=None):
    """Two/three-step ink-wash toon material: Diffuse -> Shader to RGB -> constant colour ramp."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    emi = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, srgb(dark or shade)
    el[1].position, el[1].color = 0.55, srgb(lit)
    if dark:
        e = el.new(0.18)
        e.color = srgb(shade)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 4.0
    nz.inputs["Detail"].default_value = 6.0
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation, sub.inputs[1].default_value = "SUBTRACT", 0.5
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation, mul.inputs[1].default_value = "MULTIPLY", 0.18
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs[0], bw.inputs[0])
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], sub.inputs[0])
    nt.links.new(sub.outputs[0], mul.inputs[0])
    nt.links.new(bw.outputs[0], add.inputs[0])
    nt.links.new(mul.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], ramp.inputs[0])            # the wash edge wanders like a brush, not a CG terminator
    nt.links.new(ramp.outputs[0], emi.inputs[0])
    nt.links.new(emi.outputs[0], out.inputs[0])
    return m


M_HERO = toon("hero", (0.99, 0.975, 0.94), (0.80, 0.77, 0.72))
M_BRICK = toon("brick", (0.90, 0.87, 0.81), (0.66, 0.63, 0.58), (0.45, 0.43, 0.40))
def shadow_ground():
    """Invisible ground that keeps only the shadows, as a soft grey ink wash that fades out with distance."""
    m = bpy.data.materials.new("ground")
    m.use_nodes = True
    m.surface_render_method = "BLENDED"
    nt = m.node_tree
    nt.nodes.clear()
    dif, s2r, bw = nt.nodes.new("ShaderNodeBsdfDiffuse"), nt.nodes.new("ShaderNodeShaderToRGB"), nt.nodes.new("ShaderNodeRGBToBW")
    ramp = nt.nodes.new("ShaderNodeValToRGB")                  # lit -> 0, shadow -> 1
    ramp.color_ramp.interpolation = "EASE"
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.25, (1, 1, 1, 1)
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.5, (0, 0, 0, 1)
    tc, ln = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    fade = nt.nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value, fade.inputs["From Max"].default_value = 3.0, 9.0
    fade.inputs["To Min"].default_value, fade.inputs["To Max"].default_value = 1.0, 0.0
    a1, a2 = nt.nodes.new("ShaderNodeMath"), nt.nodes.new("ShaderNodeMath")
    a1.operation, a2.operation = "MULTIPLY", "MULTIPLY"
    a2.inputs[1].default_value = 0.42
    tr, emi, mix = nt.nodes.new("ShaderNodeBsdfTransparent"), nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeMixShader")
    emi.inputs[0].default_value = srgb((0.42, 0.40, 0.37))
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    L = nt.links.new
    for a, b in ((dif.outputs[0], s2r.inputs[0]), (s2r.outputs[0], bw.inputs[0]), (bw.outputs[0], ramp.inputs[0]),
                 (tc.outputs["Object"], ln.inputs[0]), (ln.outputs["Value"], fade.inputs["Value"]),
                 (ramp.outputs[0], a1.inputs[0]), (fade.outputs[0], a1.inputs[1]), (a1.outputs[0], a2.inputs[0]),
                 (a2.outputs[0], mix.inputs[0]), (tr.outputs[0], mix.inputs[1]), (emi.outputs[0], mix.inputs[2]),
                 (mix.outputs[0], out.inputs[0])):
        L(a, b)
    return m


M_GROUND = shadow_ground() if PLATE else toon("ground", PAPER, (0.84, 0.81, 0.75))

sun = bpy.data.lights.new("sun", "SUN")
sun.energy = 4.0
sun.angle = math.radians(6)
sun_ob = bpy.data.objects.new("sun", sun)
sun_ob.rotation_euler = Euler((math.radians(50), math.radians(-25), math.radians(-35)))
sc.collection.objects.link(sun_ob)

bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
ground = bpy.context.object
ground.data.materials.append(M_GROUND)
noline = bpy.data.collections.new("noline")            # no ink outline for the ground (no horizon stroke)
sc.collection.children.link(noline)
sc.collection.objects.unlink(ground)
noline.objects.link(ground)
ls.select_by_collection, ls.collection, ls.collection_negation = True, noline, "EXCLUSIVE"

# ---------------------------------------------------------------- the hero (skinned joint graph + round head)

BONES = [("pelvis", "chest"), ("chest", "neck"), ("pelvis", "hipL"), ("hipL", "kneeL"), ("kneeL", "ankleL"),
         ("ankleL", "toeL"), ("pelvis", "hipR"), ("hipR", "kneeR"), ("kneeR", "ankleR"), ("ankleR", "toeR"),
         ("neck", "shL"), ("shL", "elbL"), ("elbL", "wristL"), ("neck", "shR"), ("shR", "elbR"), ("elbR", "wristR")]
JN = sorted({j for b in BONES for j in b})
RAD = {"pelvis": 0.20, "chest": 0.22, "neck": 0.10, "hipL": 0.14, "hipR": 0.14, "kneeL": 0.10, "kneeR": 0.10,
       "ankleL": 0.08, "ankleR": 0.08, "toeL": 0.07, "toeR": 0.07, "shL": 0.11, "shR": 0.11, "elbL": 0.08,
       "elbR": 0.08, "wristL": 0.075, "wristR": 0.075}
HEAD_R = 0.30                                      # big round head, like the 2D ink hero


def mc(p, off=(0.0, 0.0, 0.0), yaw=0.0):
    """mocap (x fwd, y up, z lateral; height 1) -> Blender metres; rotated by yaw about Z, then offset."""
    x, y, z = p[0] * HEIGHT, -p[2] * HEIGHT, p[1] * HEIGHT
    c, s = math.cos(yaw), math.sin(yaw)
    return Vector((x * c - y * s + off[0], x * s + y * c + off[1], z + off[2]))


def make_hero():
    me = bpy.data.meshes.new("hero")
    me.from_pydata([(0, 0, i * 0.1) for i in range(len(JN))], [(JN.index(a), JN.index(b)) for a, b in BONES], [])
    ob = bpy.data.objects.new("hero", me)
    sc.collection.objects.link(ob)
    empties = {}
    for i, j in enumerate(JN):
        e = bpy.data.objects.new(f"j_{j}", None)
        sc.collection.objects.link(e)
        empties[j] = e
        h = ob.modifiers.new(f"h_{j}", "HOOK")
        h.object = e
        h.vertex_indices_set([i])
        h.matrix_inverse = Matrix.Translation((0, 0, i * 0.1)).inverted()   # vertex i follows its empty exactly
    skin = ob.modifiers.new("skin", "SKIN")
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 2
    for i, j in enumerate(JN):
        me.skin_vertices[0].data[i].radius = (RAD[j], RAD[j])
        me.skin_vertices[0].data[i].use_root = j == "pelvis"
    skin.use_smooth_shade = True
    ob.data.materials.append(M_HERO)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=HEAD_R, segments=48, ring_count=24)
    head = bpy.context.object
    head.data.materials.append(M_HERO)
    bpy.ops.object.shade_smooth()
    return empties, head


def load(cid, t0=0.0, t1=None, reverse=False):
    f = MOCAP / f"{cid}.json"
    if not f.is_file():                            # clip not downloaded yet: hold the first frame of any clip we have
        print("MISSING MOCAP", cid)
        any_clip = json.loads(next(MOCAP.glob("*.json")).read_text())
        return [any_clip[0]] * 200
    fr = json.loads(f.read_text())
    hs = sorted(fr_["headtop"][1] for fr_ in fr)  # clips that start lying down were normalised to a tiny height:
    top = hs[len(hs) // 2] if hs[-1] < 1.15 else sorted(h for h in hs if h > 0.6 * hs[-1])[len([h for h in hs if h > 0.6 * hs[-1]]) // 2]
    if top > 1.15:                                 # rescale so the median standing head height is 1
        fr = [{j: [v / top for v in p] for j, p in fr_.items()} for fr_ in fr]
    fr = fr[int(t0 * FPS): int(t1 * FPS) if t1 else None]
    return fr[::-1] if reverse else fr


def idle(pose, n, seed=0):
    """Hold a pose for n frames without freezing: slow breathing (chest/head rise) and a slight sway."""
    out = []
    for i in range(n):
        b = 0.006 * math.sin(i / FPS * 2 * math.pi * 0.3 + seed)
        sw = 0.004 * math.sin(i / FPS * 2 * math.pi * 0.17 + seed)
        f = {}
        for j, (x, y, z) in pose.items():
            up = 0 if j.startswith(("ankle", "toe", "knee", "hip", "pelvis")) else b
            f[j] = [x + sw * y, y + up, z]
        out.append(f)
    return out


def blend(prev, frames, n=8):
    """Cross-fade the first n frames of a clip from the last pose of the previous one (no pops between clips)."""
    out = []
    for i, f in enumerate(frames):
        w = min(1.0, i / n)
        out.append({j: [a * (1 - w) + b * w for a, b in zip(prev[j], f[j], strict=False)] for j in f} if w < 1 else f)
    return out


def drive(empties, head, frames, start, off=(0.0, 0.0, 0.0), yaw=0.0, lift=None):
    """Keyframe the hero from mocap frames starting at scene frame `start`; lift(i) adds height (stairs)."""
    for i, f in enumerate(frames):
        fr = start + i
        dz = lift(i) if lift else 0.0
        for j, e in empties.items():
            e.location = mc(f[j], off, yaw) + Vector((0, 0, dz))
            e.keyframe_insert("location", frame=fr)
        hb, ht = mc(f["headbase"], off, yaw), mc(f["headtop"], off, yaw)
        head.location = hb + (ht - hb).normalized() * HEAD_R * 0.9 + Vector((0, 0, dz))
        head.keyframe_insert("location", frame=fr)
    return start + len(frames)


# ---------------------------------------------------------------- bricks

STAIRS = json.loads((MOCAP / "stairs_track.json").read_text())   # studio/ink3d/stairs.py
BW, BD, BH = STAIRS["depth"] * HEIGHT, 0.5, STAIRS["rise"] * HEIGHT  # one brick = one step deep, one step high


def brick(name):
    bpy.ops.mesh.primitive_cube_add(size=1)
    b = bpy.context.object
    b.name = name
    b.scale = (BW, BD, BH)
    bpy.ops.object.transform_apply(scale=True)
    bev = b.modifiers.new("bev", "BEVEL")
    bev.width, bev.segments = 0.012, 2
    b.data.materials.append(M_BRICK)
    return b


def key(ob, fr, loc, rot=(0, 0, 0)):
    ob.location, ob.rotation_euler = loc, Euler(rot)
    ob.keyframe_insert("location", frame=fr)
    ob.keyframe_insert("rotation_euler", frame=fr)


def arc(ob, f0, f1, a, b, rot0, rot1, height=1.2, settle=True):
    """Fly a brick from a to b on a parabola (eased), spinning from rot0 to rot1, with a tiny landing settle."""
    n = max(2, f1 - f0)
    for k in range(n + 1):
        u = k / n
        e = 1 - (1 - u) ** 2.2                        # fast start, soft landing
        p = Vector(a).lerp(Vector(b), e)
        p.z += height * 4 * e * (1 - e)
        r = tuple(r0 + (r1 - r0) * e for r0, r1 in zip(rot0, rot1, strict=False))
        key(ob, f0 + k, p, r)
    if settle:
        key(ob, f1 + 2, Vector(b) + Vector((0, 0, -0.012)), rot1)
        key(ob, f1 + 4, Vector(b), rot1)


# ---------------------------------------------------------------- choreography

rnd = random.Random(7)
empties, head = make_hero()
S = STAIRS["steps"]
N = 2 * S * (S + 1) // 2                           # bricks: enough for the staircase (2 across per layer)

# shared opening (0-2 s): bricks rain into a pile behind him while he stands
look_up = load("77_01", 0.0, 1.3)                 # he looks around as the bricks rain down
stand = look_up + idle(look_up[-1], 300)
_lp = stand[-1]["pelvis"]                           # he ends the opening exactly at the origin (clips chain there)
stand = [{j: [v[0] - _lp[0], v[1], v[2] - _lp[2]] for j, v in f.items()} for f in stand]
pile_c = Vector((0.9, 1.7, 0.0))
bricks, pile = [], []
for i in range(N):
    b = brick(f"b{i}")
    layer, k = divmod(i, 9)
    px = pile_c.x + (k % 3 - 1) * (BW + 0.05) + rnd.uniform(-0.06, 0.06)
    py = pile_c.y + (k // 3 - 1) * (BD + 0.04) + rnd.uniform(-0.04, 0.04)
    p = Vector((px, py, BH / 2 + layer * BH))
    r = (0, 0, rnd.uniform(-0.3, 0.3))
    f0 = 1 + int(i * 50 / N)
    key(b, 1, Vector((px, py, 9.0)), (rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0))
    arc(b, f0, f0 + 9, (px, py, 7.0), p, (rnd.uniform(-2, 2), rnd.uniform(-2, 2), 0), r, height=0.0)
    bricks.append(b)
    pile.append((p, r))

T_BUILD = 62                                       # ~2.05 s: the hit — building starts
if HALF == "top":
    # EXCUSES: a ring wall around him, course by course; he sinks to the floor (111_06 reversed); light fades
    drive(empties, head, stand[:T_BUILD], 1)
    down = load("111_06", 1.3, 3.3, reverse=True)   # he gives up: lies down
    # keep him inside the ring: drift the clip so its pelvis travels from the standing spot to the ring centre
    p0, p1, q = down[0]["pelvis"], down[-1]["pelvis"], stand[T_BUILD - 1]["pelvis"]
    n = len(down)
    down = [{j: [v[0] - (p0[0] + (p1[0] - p0[0]) * i / (n - 1)) + q[0] * (1 - i / (n - 1)) - 0.12 * i / (n - 1), v[1],
                 v[2] - (p0[2] + (p1[2] - p0[2]) * i / (n - 1)) + q[2] * (1 - i / (n - 1))] for j, v in f.items()}
            for i, f in enumerate(down)]
    down = blend(stand[T_BUILD - 1], down, 10)
    nf = drive(empties, head, down, T_BUILD)
    drive(empties, head, idle(down[-1], max(2, NFRAMES - nf + 2), seed=1), nf)
    per, R = 15, 1.45
    last = down[-1]                                 # the wall closes around where he ends up lying
    cen = sum((mc(v) for v in last.values()), Vector()) / len(last)
    for i, b in enumerate(bricks):
        course, k = divmod(i, per)
        ang = 2 * math.pi * (k + 0.5 * (course % 2)) / per
        dst = Vector((cen.x + R * math.cos(ang), cen.y + R * math.sin(ang), BH / 2 + course * BH))
        f0 = T_BUILD + int(i * 150 / N)
        p, r = pile[i]
        arc(b, f0, f0 + 10, p, dst, r, (0, 0, ang + math.pi / 2), height=1.0)
    sun.keyframe_insert("energy", frame=T_BUILD)
    sun.energy = 1.2
    sun.keyframe_insert("energy", frame=NFRAMES)
    bg = world.node_tree.nodes["Background"].inputs[1]
    bg.keyframe_insert("default_value", frame=T_BUILD)
    bg.default_value = 0.45
    bg.keyframe_insert("default_value", frame=NFRAMES)
else:
    # STEPS: the same bricks stack into a staircase (2 across, layer by layer) under the measured foot plants;
    # he walks up it (111_27 step cycle, studio/ink3d/stairs.py); a vermilion sun rises at the top
    s0 = STAIRS["step0_x"] * HEIGHT
    slots = [(s, layer, col) for layer in range(S) for s in range(layer, S) for col in (0, 1)]
    for i, (b, (s, layer, col)) in enumerate(zip(bricks, slots, strict=False)):
        dst = Vector((s0 + (s + 0.5) * BW, (col - 0.5) * BD, BH / 2 + layer * BH))
        f0 = T_BUILD + int(i * 45 / N)
        p, r = pile[i]
        arc(b, f0, f0 + 8, p, dst, r, (0, 0, 0), height=0.8)
    T_CLIMB = T_BUILD + 55
    drive(empties, head, stand[:T_CLIMB], 1)
    climb = blend(stand[T_CLIMB - 1], [dict(zip(STAIRS["joints"], f, strict=False)) for f in STAIRS["frames"]], 10)
    nf = drive(empties, head, climb, T_CLIMB)
    if nf <= NFRAMES:
        drive(empties, head, idle(climb[-1], NFRAMES - nf + 2, seed=2), nf)
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=1.8, fill_type="NGON")
    disc = bpy.context.object
    m = bpy.data.materials.new("vermilion")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = srgb(VERMILION)
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = srgb(VERMILION)
    disc.data.materials.append(m)
    sc.collection.objects.unlink(disc)
    noline.objects.link(disc)                      # solid vermilion, no ink outline (it rises from behind the ground)
    rot = (math.radians(90), 0, math.radians(14))
    key(disc, 1, (6.5, 14, -3.0), rot)
    key(disc, T_CLIMB + 60, (6.5, 14, -3.0), rot)
    key(disc, NFRAMES, (6.5, 14, 2.8), rot)
    # the ground is invisible now (shadow-only over the painted plate), so a holdout wall below the horizon hides
    # the sun until it rises: where it covers the sun, the painted plate shows through instead
    bpy.ops.mesh.primitive_plane_add(size=1)
    hold = bpy.context.object
    hold.scale = (60, 10, 1)                       # plane XY -> after the X rotation, Y is the height
    hold.rotation_euler = Euler((math.radians(90), 0, math.radians(14)))
    hold.location = (6.0, 12.0, -5.0)
    hm = bpy.data.materials.new("holdout")
    hm.use_nodes = True
    hm.node_tree.nodes.clear()
    hm.node_tree.links.new(hm.node_tree.nodes.new("ShaderNodeHoldout").outputs[0],
                           hm.node_tree.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    hold.data.materials.append(hm)
    hold.visible_shadow = False
    sc.collection.objects.unlink(hold)
    noline.objects.link(hold)

# ---------------------------------------------------------------- camera: 3/4 side view, slow push

cam = bpy.data.cameras.new("cam")
cam.lens = 40
cam_ob = bpy.data.objects.new("cam", cam)
sc.collection.objects.link(cam_ob)
sc.camera = cam_ob
target = bpy.data.objects.new("target", None)
sc.collection.objects.link(target)
tc = cam_ob.constraints.new("TRACK_TO")
tc.target, tc.track_axis, tc.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
look = Vector((1.6, 0.4, 0.9)) if HALF == "bottom" else Vector((cen.x, cen.y, 0.4))
key(target, 1, look)
key(cam_ob, 1, look + Vector((1.0, -5.2, 1.7 if HALF == "bottom" else 2.6)))
key(cam_ob, NFRAMES, look + Vector((0.8, -4.2, 1.4 if HALF == "bottom" else 2.3)))
if HALF == "bottom":                               # follow him up the stairs
    key(target, T_BUILD + 55, look)
    key(target, NFRAMES, look + Vector((3.2, 0, 1.0)))

if PLATE:
    sc.use_nodes = True
    ct = sc.node_tree
    ct.nodes.clear()
    rl, img, ov, comp = (ct.nodes.new("CompositorNodeRLayers"), ct.nodes.new("CompositorNodeImage"),
                         ct.nodes.new("CompositorNodeAlphaOver"), ct.nodes.new("CompositorNodeComposite"))
    img.image = bpy.data.images.load(str(PLATE))
    sc_n = ct.nodes.new("CompositorNodeScale")
    sc_n.space = "RENDER_SIZE"
    ct.links.new(img.outputs[0], sc_n.inputs[0])
    if HALF == "top":                                  # the world darkens as the wall closes
        bc = ct.nodes.new("CompositorNodeBrightContrast")
        bc.inputs["Bright"].default_value = 0.0
        bc.inputs["Bright"].keyframe_insert("default_value", frame=T_BUILD)
        bc.inputs["Bright"].default_value = -28.0
        bc.inputs["Bright"].keyframe_insert("default_value", frame=NFRAMES)
        ct.links.new(sc_n.outputs[0], bc.inputs[0])
        ct.links.new(bc.outputs[0], ov.inputs[1])
    else:
        ct.links.new(sc_n.outputs[0], ov.inputs[1])
    ct.links.new(rl.outputs["Image"], ov.inputs[2])
    ct.links.new(ov.outputs[0], comp.inputs[0])
    sc.render.film_transparent = True

OUT.mkdir(parents=True, exist_ok=True)
if "--still" in sys.argv:
    for f in (40, 85, 150, 260):
        sc.frame_set(f)
        sc.render.filepath = str(OUT / f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
