"""Shared Blender kit for ink_mindset scenes (import inside Blender with ROOT on sys.path):

render setup (Eevee, transparent film over a painted plate, Freestyle brush outlines), two-tone toon materials
with a wandering wash edge, the hero (skinned joint graph + big round head) driven by CMU mocap tracks, and small
helpers (keyframes, idle breathing, clip cross-fades, walk loops).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[2]
MOCAP = ROOT / "projects" / "ink_proto3d" / "mocap"
FPS = 30
HEIGHT = 1.8
INK, PAPER, VERMILION = (0.086, 0.078, 0.059), (0.957, 0.929, 0.878), (0.851, 0.255, 0.169)


def srgb(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


# ---------------------------------------------------------------- scene

class Scene:
    def __init__(self, out: Path, nframes: int, size=(1200, 1066)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.sc = sc = bpy.context.scene
        sc.render.engine = "BLENDER_EEVEE_NEXT"
        sc.render.resolution_x, sc.render.resolution_y = size
        sc.render.fps = FPS
        sc.frame_start, sc.frame_end = 1, nframes
        sc.view_settings.view_transform = "Standard"
        sc.render.film_transparent = True
        sc.render.image_settings.file_format = "PNG"
        sc.render.use_motion_blur = False                # motion blur ghosts fast limbs (grey smears)
        sc.render.filepath = str(out) + "/"
        self.out, self.n = out, nframes
        w = bpy.data.worlds.new("paper")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = srgb(PAPER)
        sc.world = w
        sc.view_layers[0].use_pass_z = True              # depth: inner lines where one limb is in front of another
        for a in ("fig", "head"):                        # AOV masks for the compositor outline (before any RL node)
            ao = sc.view_layers[0].aovs.add()
            ao.name, ao.type = a, "VALUE"
        self.noline = bpy.data.collections.new("noline")
        sc.collection.children.link(self.noline)
        self._lines()
        sc.render.use_freestyle = False                  # outlines are inverted hulls now (stable, no broken strokes)
        sun = bpy.data.lights.new("sun", "SUN")
        sun.energy, sun.angle = 4.0, math.radians(6)
        self.sun = bpy.data.objects.new("sun", sun)
        self.sun.rotation_euler = Euler((math.radians(50), math.radians(-25), math.radians(-35)))
        sc.collection.objects.link(self.sun)

    def _lines(self, tmin=1.0, tmax=3.8):
        sc = self.sc
        sc.render.use_freestyle = True
        sc.render.line_thickness_mode = "ABSOLUTE"
        fs = sc.view_layers[0].freestyle_settings
        ls = fs.linesets[0] if fs.linesets else fs.linesets.new("ink")
        ls.select_by_visibility, ls.select_by_edge_types = True, True
        ls.select_silhouette, ls.select_border, ls.select_crease, ls.select_contour = True, True, False, True
        ls.select_by_collection, ls.collection, ls.collection_negation = True, self.noline, "EXCLUSIVE"
        st = ls.linestyle or bpy.data.linestyles.new("ink")
        ls.linestyle = st
        st.color, st.chaining, st.caps = INK, "PLAIN", "ROUND"
        cal = st.thickness_modifiers.new("calligraphy", "CALLIGRAPHY")
        cal.orientation, cal.thickness_min, cal.thickness_max = 55.0, tmin, tmax
        # no noise modifiers: Freestyle re-parameterises strokes every frame, so any noise "boils" (jittering
        # outlines read as AI artefacts). The calligraphic thick/thin alone stays stable from frame to frame.

    def no_outline(self, ob):
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        self.noline.objects.link(ob)

    def plates(self, *images, mix_keys=None, bright_keys=None):
        """Compositor: painted plate(s) behind the transparent render. Two plates cross-fade with mix_keys
        [(frame, factor 0..1)]; bright_keys [(frame, brightness)] darken/lighten the plate."""
        sc = self.sc
        sc.use_nodes = True
        ct = sc.node_tree
        ct.nodes.clear()
        rl, ov, comp = ct.nodes.new("CompositorNodeRLayers"), ct.nodes.new("CompositorNodeAlphaOver"), \
            ct.nodes.new("CompositorNodeComposite")
        outs = []
        self.plate_tr = []
        for p in images:
            img, scn = ct.nodes.new("CompositorNodeImage"), ct.nodes.new("CompositorNodeScale")
            img.image = bpy.data.images.load(str(p))
            scn.space = "RENDER_SIZE"
            src = img.outputs[0]
            if img.image.size[0] > 1.5 * sc.render.resolution_x:     # a wide (mirror-tiled) plate: it scrolls
                tr = ct.nodes.new("CompositorNodeTranslate")
                tr.wrap_axis = "XAXIS"
                # [original | mirror]: the crop shows the middle, i.e. the mirror seam - start on the original
                tr["base"] = img.image.size[0] / 4
                tr.inputs["X"].default_value = tr["base"]
                ct.links.new(src, tr.inputs[0])
                src = tr.outputs[0]
                self.plate_tr.append(tr)
                scn.frame_method = "CROP"
            ct.links.new(src, scn.inputs[0])
            outs.append(scn.outputs[0])
        bg = outs[0]
        if len(outs) > 1:
            mx = ct.nodes.new("CompositorNodeMixRGB")
            ct.links.new(outs[0], mx.inputs[1])
            ct.links.new(outs[1], mx.inputs[2])
            for f, v in mix_keys or [(1, 0.0)]:
                mx.inputs[0].default_value = v
                mx.inputs[0].keyframe_insert("default_value", frame=f)
            bg = mx.outputs[0]
        if bright_keys:
            bc = ct.nodes.new("CompositorNodeBrightContrast")
            ct.links.new(bg, bc.inputs[0])
            for f, v in bright_keys:
                bc.inputs["Bright"].default_value = v
                bc.inputs["Bright"].keyframe_insert("default_value", frame=f)
            bg = bc.outputs[0]
        ct.links.new(bg, ov.inputs[1])
        ct.links.new(rl.outputs["Image"], ov.inputs[2])
        ct.links.new(ov.outputs[0], comp.inputs[0])
        fo = ct.nodes.new("CompositorNodeOutputFile")         # figure / head masks for studio/ink3d/outline.py
        fo.base_path = str(self.out) + "/masks/"
        fo.format.file_format, fo.format.color_mode = "PNG", "BW"
        fo.file_slots.clear()
        for name in ("fig", "head"):
            fo.file_slots.new(name + "_")
            ct.links.new(rl.outputs[name], fo.inputs[name + "_"])

    def scroll(self, keys):
        """Parallax: shift the wide plates by keys [(frame, px)] (plate pixels, + moves the picture right)."""
        for tr in getattr(self, "plate_tr", []):
            for f, v in keys:
                tr.inputs["X"].default_value = tr.get("base", 0.0) + v
                tr.inputs["X"].keyframe_insert("default_value", frame=f)

    def ground(self, image: Path, x0: float = -150.0, x1: float = 250.0, y: float = -0.6, px_per_m: float = 200.0,
               tile_m: float = 6.0, top_m: float = 0.3, depth_m: float = 2.6):
        """The road: a vertical strip facing the camera from top_m above the ground line down to -depth_m, textured
        with a seamless ink tile (alpha) repeated along x - it scrolls past 1:1 as the camera tracks."""
        import bmesh
        me = bpy.data.meshes.new("ground")
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in ((x0, y, -depth_m), (x1, y, -depth_m), (x1, y, top_m), (x0, y, top_m))]
        face = bm.faces.new(vs)
        uv = bm.loops.layers.uv.new()
        reps = (x1 - x0) / tile_m
        for loop, (u, v) in zip(face.loops, ((0, 0), (reps, 0), (reps, 1), (0, 1)), strict=False):
            loop[uv].uv = (u, v)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("ground", me)
        self.sc.collection.objects.link(ob)
        mat = bpy.data.materials.new("ground_ink")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(image))
        tex.interpolation = "Cubic"
        em, tr, mix, out = (nt.nodes.new(t) for t in ("ShaderNodeEmission", "ShaderNodeBsdfTransparent",
                                                      "ShaderNodeMixShader", "ShaderNodeOutputMaterial"))
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        else:
            mat.blend_method = "BLEND"
        ob.data.materials.append(mat)
        ob.visible_shadow = False
        self.no_outline(ob)
        return ob

    def _outline(self, ct, rl, image, width=5):
        """Ink outline from the figure's silhouette (object-index masks): one ring around the whole figure and one
        around the head. Screen-space, so it can never poke through the body (no wedges at the neck or hips)."""
        cache = {}

        def mask(name):                                  # binary masks: morphology on soft edges left grey rings
            if name not in cache:
                g = ct.nodes.new("CompositorNodeMath")
                g.operation = "GREATER_THAN"
                g.inputs[1].default_value = 0.5
                ct.links.new(rl.outputs[name], g.inputs[0])
                cache[name] = g.outputs[0]
            return cache[name]
        def ring(m):
            dl = ct.nodes.new("CompositorNodeDilateErode")
            dl.mode, dl.distance = "DISTANCE", width
            ct.links.new(m, dl.inputs[0])
            sub = ct.nodes.new("CompositorNodeMath")
            sub.operation, sub.use_clamp = "SUBTRACT", True
            ct.links.new(dl.outputs[0], sub.inputs[0])
            ct.links.new(m, sub.inputs[1])
            return sub.outputs[0]
        # close small gaps in the silhouette (between a tucked head and the back, between arm and body): dilate
        # then erode the figure mask, paint the closed-in sliver white, and outline the closed shape
        dil = ct.nodes.new("CompositorNodeDilateErode")
        dil.mode, dil.distance = "DISTANCE", 10
        ct.links.new(mask("fig"), dil.inputs[0])
        ero = ct.nodes.new("CompositorNodeDilateErode")
        ero.mode, ero.distance = "DISTANCE", -10
        ct.links.new(dil.outputs[0], ero.inputs[0])
        gap = ct.nodes.new("CompositorNodeMath")
        gap.operation, gap.use_clamp = "SUBTRACT", True
        ct.links.new(ero.outputs[0], gap.inputs[0])
        ct.links.new(mask("fig"), gap.inputs[1])
        gbin = ct.nodes.new("CompositorNodeMath")               # all-or-nothing: half-filled edge pixels were
        gbin.operation = "GREATER_THAN"                          # the grey ghost lines and rings in the gap
        gbin.inputs[1].default_value = 0.01
        ct.links.new(gap.outputs[0], gbin.inputs[0])
        fill = ct.nodes.new("CompositorNodeMixRGB")
        fill.inputs[2].default_value = srgb((0.985, 0.97, 0.935))
        ct.links.new(gbin.outputs[0], fill.inputs[0])
        ct.links.new(image, fill.inputs[1])
        image = fill.outputs[0]
        rings = ct.nodes.new("CompositorNodeMath")
        rings.operation = "MAXIMUM"
        ct.links.new(ring(ero.outputs[0]), rings.inputs[0])  # outer silhouette of the whole (closed) figure
        ct.links.new(ring(mask("head")), rings.inputs[1])    # the head's own line (over the shoulders too)
        # no inner lines: depth-edge strokes came out broken and read as artefacts (clean silhouette instead)
        soft = ct.nodes.new("CompositorNodeBlur")               # anti-alias the binary outline
        soft.size_x = soft.size_y = 1
        soft.filter_type = "GAUSS"
        ct.links.new(rings.outputs[0], soft.inputs[0])
        mix = ct.nodes.new("CompositorNodeMixRGB")
        mix.inputs[2].default_value = srgb(INK)
        ct.links.new(soft.outputs[0], mix.inputs[0])
        ct.links.new(image, mix.inputs[1])
        return mix.outputs[0]

    def camera(self, lens=50):
        cam = bpy.data.cameras.new("cam")
        cam.lens = lens
        self.cam = bpy.data.objects.new("cam", cam)
        self.sc.collection.objects.link(self.cam)
        self.sc.camera = self.cam
        self.target = bpy.data.objects.new("target", None)
        self.sc.collection.objects.link(self.target)
        tc = self.cam.constraints.new("TRACK_TO")
        tc.target, tc.track_axis, tc.up_axis = self.target, "TRACK_NEGATIVE_Z", "UP_Y"
        return self.cam, self.target

    def render(self, stills=None):
        self.out.mkdir(parents=True, exist_ok=True)
        if stills:
            for f in stills:
                self.sc.frame_set(f)
                self.sc.render.filepath = str(self.out / f"still_{f:04d}.png")
                bpy.ops.render.render(write_still=True)
        else:
            bpy.ops.render.render(animation=True)


# ---------------------------------------------------------------- materials

def flat(name, color, aovs=()):
    """Clean flat fill (no shading, no shadow patches) — the white cartoon figure. `aovs` names value passes this
    material writes 1.0 into (Eevee has no object-index pass; AOV masks drive the compositor outline)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e, o = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    e.inputs[0].default_value = srgb(color)
    nt.links.new(e.outputs[0], o.inputs[0])
    for a in aovs:
        ao = nt.nodes.new("ShaderNodeOutputAOV")
        ao.aov_name = a
        ao.inputs["Value"].default_value = 1.0
    return m


def outline(ob, width=0.024, color=INK):
    """Cartoon ink outline as an inverted hull: a slightly bigger, inside-out black shell behind the surface.
    Constant thickness, never flickers, and a limb in front of the body gets its own line."""
    m = bpy.data.materials.get("ink_hull") or flat("ink_hull", color)
    m.use_backface_culling = True
    ob.data.materials.append(m)
    so = ob.modifiers.new("hull", "SOLIDIFY")
    so.thickness, so.offset = width, 1.0
    so.use_flip_normals, so.use_rim = True, False
    so.material_offset = len(ob.data.materials) - 1
    return ob


def toon(name, lit, shade, dark=None, wander=0.18):
    """Ink-wash toon: Diffuse -> Shader to RGB -> (+ noise so the wash edge wanders like a brush) -> constant ramp."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    dif, s2r, bw = nt.nodes.new("ShaderNodeBsdfDiffuse"), nt.nodes.new("ShaderNodeShaderToRGB"), \
        nt.nodes.new("ShaderNodeRGBToBW")
    tc, nz = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 4.0, 6.0
    sub, mul, add = (nt.nodes.new("ShaderNodeMath") for _ in range(3))
    sub.operation, sub.inputs[1].default_value = "SUBTRACT", 0.5
    mul.operation, mul.inputs[1].default_value = "MULTIPLY", wander
    add.operation = "ADD"
    ramp, emi, out = nt.nodes.new("ShaderNodeValToRGB"), nt.nodes.new("ShaderNodeEmission"), \
        nt.nodes.new("ShaderNodeOutputMaterial")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, srgb(dark or shade)
    el[1].position, el[1].color = 0.55, srgb(lit)
    if dark:
        el.new(0.18).color = srgb(shade)
    L = nt.links.new
    for a, b in ((dif.outputs[0], s2r.inputs[0]), (s2r.outputs[0], bw.inputs[0]), (tc.outputs["Object"], nz.inputs["Vector"]),
                 (nz.outputs["Fac"], sub.inputs[0]), (sub.outputs[0], mul.inputs[0]), (bw.outputs[0], add.inputs[0]),
                 (mul.outputs[0], add.inputs[1]), (add.outputs[0], ramp.inputs[0]), (ramp.outputs[0], emi.inputs[0]),
                 (emi.outputs[0], out.inputs[0])):
        L(a, b)
    return m


def glow(name, color, strength=1.0, soft=0.35):
    """Flat emissive disc with a soft round edge (alpha falls off towards the rim): light pools, suns."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = "BLENDED"
    nt = m.node_tree
    nt.nodes.clear()
    tc, ln, mr = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeVectorMath"), nt.nodes.new("ShaderNodeMapRange")
    ln.operation = "LENGTH"
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 1.0 - soft, 1.0
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0
    emi, tr, mix, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeBsdfTransparent"), \
        nt.nodes.new("ShaderNodeMixShader"), nt.nodes.new("ShaderNodeOutputMaterial")
    emi.inputs[0].default_value, emi.inputs[1].default_value = srgb(color), strength
    L = nt.links.new
    for a, b in ((tc.outputs["Object"], ln.inputs[0]), (ln.outputs["Value"], mr.inputs["Value"]), (mr.outputs[0], mix.inputs[0]),
                 (tr.outputs[0], mix.inputs[1]), (emi.outputs[0], mix.inputs[2]), (mix.outputs[0], out.inputs[0])):
        L(a, b)
    return m


def disc(sc: Scene, name, mat, radius=1.0, loc=(0, 0, 0.003)):
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=1.0, fill_type="NGON", location=loc)
    d = bpy.context.object
    d.name = name
    d.scale = (radius, radius, 1)
    d.data.materials.append(mat)
    d.visible_shadow = False
    sc.no_outline(d)
    return d


def key(ob, fr, loc=None, rot=None, scale=None):
    if loc is not None:
        ob.location = loc
        ob.keyframe_insert("location", frame=fr)
    if rot is not None:
        ob.rotation_euler = Euler(rot)
        ob.keyframe_insert("rotation_euler", frame=fr)
    if scale is not None:
        ob.scale = scale
        ob.keyframe_insert("scale", frame=fr)


# ---------------------------------------------------------------- hero

BONES = [("pelvis", "chest"), ("chest", "neck"), ("pelvis", "hipL"), ("hipL", "kneeL"), ("kneeL", "ankleL"),
         ("ankleL", "toeL"), ("pelvis", "hipR"), ("hipR", "kneeR"), ("kneeR", "ankleR"), ("ankleR", "toeR"),
         ("neck", "shL"), ("shL", "elbL"), ("elbL", "wristL"), ("neck", "shR"), ("shR", "elbR"), ("elbR", "wristR")]
JN = sorted({j for b in BONES for j in b})
RAD = {"pelvis": 0.16, "chest": 0.16, "neck": 0.055, "hipL": 0.13, "hipR": 0.13, "kneeL": 0.10, "kneeR": 0.10,
       "ankleL": 0.085, "ankleR": 0.085, "toeL": 0.075, "toeR": 0.075, "shL": 0.115, "shR": 0.115, "elbL": 0.10,
       "elbR": 0.10, "wristL": 0.10, "wristR": 0.10}
HEAD_R = 0.30


def mc(p, off=(0.0, 0.0, 0.0)):
    """mocap (x fwd, y up, z lateral; height 1) -> Blender metres (+ offset)."""
    return Vector((p[0] * HEIGHT + off[0], -p[2] * HEIGHT + off[1], p[1] * HEIGHT + off[2]))


class Hero:
    """The white cartoon figure: a tapered capsule per bone plus a sphere at every joint (all flat white, all in
    the "fig" mask), and a big round head ("fig" + "head"). The compositor outlines only their union, so the parts
    read as one smooth body. Separate primitives instead of a Skin modifier: Skin grows flickering spikes where
    three limbs meet (neck/shoulders)."""

    def __init__(self, sc: Scene, color=(0.985, 0.97, 0.935), scale: float = 1.0):
        self.scale, self.hide_from = scale, None          # 2D export: head size; frames >= hide_from are not drawn
        self.mat = flat("hero_body", color, aovs=("fig",))
        head_mat = flat("hero_head", color, aovs=("fig", "head"))
        self.joints, self.bones = {}, {}
        for j in JN:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=RAD[j], segments=32, ring_count=16)
            o = bpy.context.object
            o.name = f"j_{j}"
            o.data.materials.append(self.mat)
            bpy.ops.object.shade_smooth()
            o.visible_shadow = False
            self.joints[j] = o
        for a_, b_ in BONES:
            bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=RAD[a_], radius2=RAD[b_], depth=1.0, location=(0, 0, 0))
            o = bpy.context.object
            o.name = f"b_{a_}_{b_}"
            o.data.materials.append(self.mat)
            bpy.ops.object.shade_smooth()
            for v in o.data.vertices:                    # pivot at the base: z in [0, 1] from joint a to joint b
                v.co.z += 0.5
            o.rotation_mode = "QUATERNION"
            o.visible_shadow = False
            self.bones[(a_, b_)] = o
        bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.17, radius2=0.24, depth=1.0)   # chest -> head:
        self.neck = bpy.context.object                   # no slit between a bowed head and the back
        self.neck.data.materials.append(self.mat)
        for v in self.neck.data.vertices:
            v.co.z += 0.5
        self.neck.rotation_mode = "QUATERNION"
        self.neck.visible_shadow = False
        bpy.ops.mesh.primitive_uv_sphere_add(radius=HEAD_R, segments=64, ring_count=32)
        self.head = bpy.context.object
        self.head.data.materials.append(head_mat)
        bpy.ops.object.shade_smooth()
        self.head.visible_shadow = False
        self.body = self.joints["pelvis"]

    def drive(self, frames, start, off=(0.0, 0.0, 0.0)):
        z = Vector((0, 0, 1))
        for i, f in enumerate(frames):
            fr = start + i
            P = {j: mc(f[j], off) for j in JN}
            for j, o in self.joints.items():
                o.location = P[j]
                o.keyframe_insert("location", frame=fr)
            for (a_, b_), o in self.bones.items():
                d = P[b_] - P[a_]
                o.location = P[a_]
                o.rotation_quaternion = z.rotation_difference(d.normalized()) if d.length > 1e-6 else o.rotation_quaternion
                o.scale = (1, 1, max(d.length, 1e-4))
                o.keyframe_insert("location", frame=fr)
                o.keyframe_insert("rotation_quaternion", frame=fr)
                o.keyframe_insert("scale", frame=fr)
            hb, ht = mc(f["headbase"], off), mc(f["headtop"], off)
            self.head.location = hb + (ht - hb).normalized() * HEAD_R * 0.72 * self.scale   # tucked in
            self.head.keyframe_insert("location", frame=fr)
            d = self.head.location - P["chest"]
            self.neck.location = P["chest"]
            self.neck.rotation_quaternion = z.rotation_difference(d.normalized())
            self.neck.scale = (1, 1, d.length)
            for path in ("location", "rotation_quaternion", "scale"):
                self.neck.keyframe_insert(path, frame=fr)
        return start + len(frames)


# ---------------------------------------------------------------- mocap tracks

def load(cid, t0=0.0, t1=None, reverse=False):
    fr = json.loads((MOCAP / f"{cid}.json").read_text())
    hs = sorted(f["headtop"][1] for f in fr)
    if hs[-1] > 1.15:                              # clip normalised on a lying/crouched start: rescale to standing
        tall = [h for h in hs if h > 0.6 * hs[-1]]
        top = tall[len(tall) // 2]
        fr = [{j: [v / top for v in p] for j, p in f.items()} for f in fr]
    fr = fr[int(t0 * FPS): int(t1 * FPS) if t1 else None]
    return fr[::-1] if reverse else fr


def shift(frames, dx=0.0, dz=0.0):
    """Move a track in the ground plane (mocap units: x forward, z lateral)."""
    return [{j: [v[0] + dx, v[1], v[2] + dz] for j, v in f.items()} for f in frames]


def to_origin(frames, at=-1):
    p = frames[at]["pelvis"]
    return shift(frames, -p[0], -p[2])


def idle(pose, n, seed=0.0):
    out = []
    for i in range(n):
        b = 0.006 * math.sin(i / FPS * 2 * math.pi * 0.3 + seed)
        sw = 0.004 * math.sin(i / FPS * 2 * math.pi * 0.17 + seed)
        out.append({j: [x + sw * y, y + (0 if j.startswith(("ankle", "toe", "knee", "hip", "pelvis")) else b), z]
                    for j, (x, y, z) in pose.items()})
    return out


UPPER = ("chest", "neck", "headbase", "headtop", "shL", "shR", "elbL", "elbR", "wristL", "wristR")


def exaggerate(frames, k=1.5, window=0.8, joints=UPPER):
    """Cartoon exaggeration: upper-body joints move k times further from their slow (moving-average) path,
    measured relative to the pelvis, so small real gestures read on a simple character. Feet stay planted."""
    n, h = len(frames), max(1, int(window * FPS / 2))
    rel = [{j: [f[j][i] - f["pelvis"][i] for i in range(3)] for j in joints} for f in frames]
    out = []
    for t, f in enumerate(frames):
        lo, hi = max(0, t - h), min(n, t + h + 1)
        g = dict(f)
        for j in joints:
            base = [sum(rel[u][j][i] for u in range(lo, hi)) / (hi - lo) for i in range(3)]
            g[j] = [f["pelvis"][i] + base[i] + k * (rel[t][j][i] - base[i]) for i in range(3)]
        out.append(g)
    return out


def blend(prev, frames, n=8):
    out = []
    for i, f in enumerate(frames):
        w = min(1.0, i / n)
        out.append({j: [a * (1 - w) + b * w for a, b in zip(prev[j], f[j], strict=False)] for j in f} if w < 1 else f)
    return out


def walk_loop(cid, seconds, speed=1.0):
    """A long straight walk from a short clip: cut one gait cycle between two left-foot plants, repeat it shifted
    by the cycle's travel, cross-fade the seams, remove sideways drift."""
    fr = json.loads((MOCAP / f"{cid}.json").read_text())
    ank = [f["ankleL"][1] for f in fr]
    plants = [i for i in range(2, len(fr) - 2) if ank[i] <= min(ank[i - 2:i + 3]) and ank[i] < min(ank) + 0.02]
    a, b = plants[0], next(p for p in plants if p - plants[0] > 15)
    cyc = fr[a:b]
    d = [fr[b]["pelvis"][k] - fr[a]["pelvis"][k] for k in (0, 1, 2)]
    out, k = [], 0
    need = int(seconds * FPS * speed) + 2
    while len(out) < need:
        c = shift(cyc, d[0] * k, d[2] * k)
        out.extend(blend(out[-1], c, 4) if out else c)
        k += 1
    out = to_origin(out, 0)
    drift = out[-1]["pelvis"][2]
    out = [{j: [v[0], v[1], v[2] - drift * i / len(out)] for j, v in f.items()} for i, f in enumerate(out)]
    if speed != 1.0:
        res = []
        t = 0.0
        while int(t) + 1 < len(out):
            i0, u = int(t), t - int(t)
            res.append({j: [x * (1 - u) + y * u for x, y in zip(out[i0][j], out[i0 + 1][j], strict=False)] for j in out[i0]})
            t += speed
        out = res
    return out


def plants(frames, foot):
    """Frames where a foot is planted (lowest and slow) -> [(frame index, ankle position in mocap units)]."""
    a = [f[f"ankle{foot}"] for f in frames]
    out, last = [], -99
    for i in range(1, len(a) - 1):
        v = math.dist(a[i], a[i - 1]) * FPS
        if v < 0.15 and a[i][1] < min(p[1] for p in a) + 0.03 and i - last > 10:
            out.append((i, a[i]))
            last = i
    return out


# ---------------------------------------------------------------- game-style animation library (Quaternius, CC0)

UAL = ROOT / "projects" / "_assets" / "anim_dl" / "UAL_Standard" / "Universal Animation Library[Standard]" / \
    "Unreal-Godot" / "UAL1_Standard_RM.glb"
UAL_JOINTS = {"pelvis": ("pelvis", "head"), "hipL": ("thigh_l", "head"), "kneeL": ("calf_l", "head"),
              "ankleL": ("foot_l", "head"), "toeL": ("ball_l", "head"), "hipR": ("thigh_r", "head"),
              "kneeR": ("calf_r", "head"), "ankleR": ("foot_r", "head"), "toeR": ("ball_r", "head"),
              "chest": ("spine_03", "head"), "neck": ("neck_01", "head"), "headbase": ("Head", "head"),
              "headtop": ("Head", "tail"), "shL": ("upperarm_l", "head"), "elbL": ("lowerarm_l", "head"),
              "wristL": ("hand_l", "head"), "shR": ("upperarm_r", "head"), "elbR": ("lowerarm_r", "head"),
              "wristR": ("hand_r", "head")}


class Rig:
    """Quaternius Universal Animation Library (CC0, root motion baked): imported once, hidden; `track()` samples
    an action into joint tracks in the same format as the mocap loaders (x fwd, y up, z lateral; height 1), so the
    hero, blends, idles and plants work unchanged. Cartoon game animation reads far better than raw lab mocap."""

    def __init__(self):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(UAL))
        new = [o for o in bpy.data.objects if o not in before]
        self.arm = next(o for o in new if o.type == "ARMATURE")
        for o in new:
            o.hide_render = True
            o.hide_viewport = True
        self.arm.hide_viewport = False                  # pose evaluation needs it in the view layer
        self.arm.animation_data_create()
        self.actions = {a.name: a for a in bpy.data.actions}
        ref = self._sample("Idle_Loop")[0]               # one scale and one floor for every clip (standing hero)
        self.floor = min(ref["ankleL"].z, ref["ankleR"].z, ref["toeL"].z, ref["toeR"].z)
        self.h = ref["headtop"].z - self.floor

    def _sample(self, name):
        act = self.actions[name]
        self.arm.animation_data.action = act
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        sc = bpy.context.scene
        out = []
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            bpy.context.view_layer.update()
            mw = self.arm.matrix_world
            d = {}
            for j, (b, end) in UAL_JOINTS.items():
                pb = self.arm.pose.bones[b]
                p = mw @ (pb.head if end == "head" else pb.tail)
                d[j] = p.copy()
            # the big cartoon head sits up on the shoulders: half neck direction, half straight up (otherwise in a
            # forward lean it juts out past his hands)
            dn = (d["headbase"] - d["neck"]).normalized()
            d["headtop"] = d["headbase"] + (dn + Vector((0, 0, 1))).normalized() * 0.24
            out.append(d)
        return out

    def track(self, name, seconds=None, loops=1, speed=1.0, src_fps=30):
        """Joint frames for an action; loops repeat it, carrying the root motion forward each time."""
        cyc = self._sample(name)
        n_need = int(seconds * FPS) + 2 if seconds else None
        frames, shift_v, k = [], Vector(), 0
        travel = cyc[-1]["pelvis"] - cyc[0]["pelvis"]
        travel.z = 0
        while (n_need is None and k < loops) or (n_need is not None and len(frames) * FPS / src_fps / speed < n_need + 2):
            frames.extend({j: v + shift_v for j, v in f.items()} for f in (cyc if k == 0 else cyc[1:]))
            shift_v = shift_v + travel
            k += 1
        # resample src_fps*speed -> FPS
        step = src_fps * speed / FPS
        res, t = [], 0.0
        while int(t) + 1 < len(frames):
            i0, u = int(t), t - int(t)
            res.append({j: frames[i0][j].lerp(frames[i0 + 1][j], u) for j in frames[i0]})
            t += step
        if n_need:
            res = res[:n_need]
        # world metres (Blender: x, y, z up) -> mocap units (x fwd, y up, z lateral; height 1). Facing: travel dir
        # (or the rig's -Y for in-place clips) becomes +x.
        h = self.h
        fwd = Vector((travel.x, travel.y, 0))
        fwd = fwd.normalized() if fwd.length > 0.2 else Vector((0, -1, 0))
        side = Vector((fwd.y, -fwd.x, 0))
        o = res[0]["pelvis"]
        floor = self.floor
        return [{j: [(v - o).dot(fwd) / h, (v.z - floor) / h + 0.035, -(v - o).dot(side) / h] for j, v in f.items()}
                for f in res]


# ---------------------------------------------------------------- 2D stick hero (drawn over the Blender render)

def export_2d(sc: Scene, hero, path: Path, others: dict | None = None) -> None:
    """Project the animated figures' joints through the camera for every frame -> JSON for studio/ink3d/stick2d.py,
    then hide the 3D figures (Blender renders only the world; figures are drawn as clean 2D).
    hero = the main figure; others = {name: Hero} (e.g. a giant shadow). Output: {"figures": {name: [frame...]}};
    a frame is null when the figure is hidden (Hero.hide_from)."""
    from bpy_extras.object_utils import world_to_camera_view
    s = sc.sc
    W, H = s.render.resolution_x, s.render.resolution_y
    cam = s.camera
    figs = {"hero": hero, **(others or {})}
    out = {k: [] for k in figs}
    for fr in range(s.frame_start, s.frame_end + 1):
        s.frame_set(fr)
        right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))

        def px(co):
            v = world_to_camera_view(s, cam, co)
            return [round(v.x * W, 2), round((1 - v.y) * H, 2), round(v.z, 4)]
        for name, h in figs.items():
            if h.hide_from is not None and fr >= h.hide_from:
                out[name].append(None)
                continue
            d = {j: px(o.matrix_world.translation) for j, o in h.joints.items()}
            hc = h.head.matrix_world.translation
            d["head"] = px(hc)
            d["head_r"] = round(abs(px(hc + right * HEAD_R * h.scale)[0] - d["head"][0]), 2)
            out[name].append(d)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"figures": out}), encoding="utf-8")
    for h in figs.values():
        for o in [*h.joints.values(), *h.bones.values(), h.head, h.neck]:
            o.hide_render = True


def scale_track(frames, k, anchor=None):
    """Scale a joint track about a ground point (mocap units): a giant version of the same motion."""
    ax, az = anchor if anchor else (frames[0]["pelvis"][0], frames[0]["pelvis"][2])
    return [{j: [ax + (v[0] - ax) * k, v[1] * k, az + (v[2] - az) * k] for j, v in f.items()} for f in frames]


def aim_arm(frames, side, target, peak, rise=6, fall=10):
    """Bend an arm's motion so its wrist reaches `target` (mocap xyz) at frame `peak`, blending in over `rise` frames
    and out over `fall` (a punch aimed down at a smaller opponent). The elbow follows halfway."""
    w0 = frames[peak][f"wrist{side}"]
    off = [t - w for t, w in zip(target, w0, strict=False)]
    out = []
    for i, f in enumerate(frames):
        u = 1 - (peak - i) / rise if peak - rise <= i <= peak else (1 - (i - peak) / fall if peak < i <= peak + fall else 0)
        u = max(0.0, min(1.0, u))
        g = dict(f)
        g[f"wrist{side}"] = [a + o * u for a, o in zip(f[f"wrist{side}"], off, strict=False)]
        g[f"elb{side}"] = [a + o * u * 0.5 for a, o in zip(f[f"elb{side}"], off, strict=False)]
        out.append(g)
    return out


def reach_arms(frames, front_x, i0, i1, ramp=6):
    """Cartoon stretch: between frames i0..i1 both arms reach so the wrists are at x = front_x (mocap units)."""
    out = []
    for i, f in enumerate(frames):
        u = 0.0 if i < i0 - ramp or i > i1 + ramp else min(1.0, (i - (i0 - ramp)) / ramp, ((i1 + ramp) - i) / ramp)
        g = dict(f)
        for s in "LR":
            dx = (front_x - f[f"wrist{s}"][0]) * u
            g[f"wrist{s}"] = [f[f"wrist{s}"][0] + dx, f[f"wrist{s}"][1], f[f"wrist{s}"][2]]
            g[f"elb{s}"] = [f[f"elb{s}"][0] + dx * 0.5, f[f"elb{s}"][1], f[f"elb{s}"][2]]
        out.append(g)
    return out


def rotate_track(frames, angles, cx=None, cz=None):
    """Turn a track about the vertical through (cx, cz) (default: each frame's pelvis) by angles[i] radians."""
    out = []
    for f, a in zip(frames, angles, strict=False):
        ox = f["pelvis"][0] if cx is None else cx
        oz = f["pelvis"][2] if cz is None else cz
        c, s_ = math.cos(a), math.sin(a)
        out.append({j: [ox + (v[0] - ox) * c - (v[2] - oz) * s_, v[1], oz + (v[0] - ox) * s_ + (v[2] - oz) * c]
                    for j, v in f.items()})
    return out


def lerp_pose(a, b, u):
    """Blend two poses relative to their pelvis (the caller places the pelvis)."""
    pa, pb = a["pelvis"], b["pelvis"]
    return {j: [(a[j][k] - pa[k]) * (1 - u) + (b[j][k] - pb[k]) * u for k in range(3)] for j in a}


def mirror_x(frames, about=0.0):
    """Turn a track to face -x (rotate 180 deg about the vertical through x=about)."""
    return [{j: [2 * about - v[0], v[1], -v[2]] for j, v in f.items()} for f in frames]


def block(sc: Scene, name, size, loc, color=INK):
    """Solid ink prop (no outline needed: flat black on paper)."""
    import bpy as _bpy
    _bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = _bpy.context.object
    o.name = name
    o.scale = size
    o.data.materials.append(_bpy.data.materials.get("ink_solid") or flat("ink_solid", color))
    o.visible_shadow = False
    sc.no_outline(o)
    return o
