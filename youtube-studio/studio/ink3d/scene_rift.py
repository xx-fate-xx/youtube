"""ink_mindset pilot "The Rift" — four metaphors, two halves each. Run inside Blender:

    blender -b -P studio/ink3d/scene_rift.py -- <wall|gap|fist|race> <top|bottom> <out_dir> [--still]

Timing is on the Head Bang cut (Mixkit, from 7.9 s): drop 5.03 s, beat 0.617 s, section two 17.99 s.
Local time 0 = the metaphor's start in the Short (wall 0, gap 7.50, fist 12.43, race 17.99).

wall  WAIT / PUSH        a black wall at night. Top waits in front of it and sinks down. Bottom pushes; on the
                         drop the wall bursts into pieces and morning light floods in.
gap   DOUBT / JUMP       both sprint to a cliff edge. Top stops dead at the edge, the far side drifts away.
                         Bottom leaps on the beat and lands running.
fist  STAY DOWN / HIT BACK  a giant shadow of himself punches. Top goes down and stays. Bottom takes the hit,
                         charges and hits back; the shadow bursts into ink.
race  QUIT / ONE MORE    a sprint. Top runs out of breath and stops. Bottom keeps going and breaks the vermilion
                         finish ribbon on the strong beat; the sun comes up.
"""

from __future__ import annotations

import math
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
BEAT = 0.617
DUR = {"wall": 7.50, "gap": 4.93, "fist": 5.56, "race": 12.01}[META]
N = int(round(DUR * kit.FPS)) + 2
F = lambda t: int(round(t * kit.FPS)) + 1          # noqa: E731
BG = ROOT / "projects" / "ink_proto3d" / "bg"
FPS = kit.FPS

S = kit.Scene(OUT, N)
hero = kit.Hero(S)
rig = kit.Rig()
others = {}


def at(track, ref, key="pelvis"):
    """Continue a clip from where the previous pose ended (ground position of `key`)."""
    return kit.shift(track, ref[key][0] - track[0][key][0], ref[key][2] - track[0][key][2])


def feet_at(track, ref):
    fx = lambda f, i: (f["ankleL"][i] + f["ankleR"][i]) / 2                          # noqa: E731
    return kit.shift(track, fx(ref, 0) - fx(track[0], 0), fx(ref, 2) - fx(track[0], 2))


def cut(track, t):
    return track[: int(round(t * FPS))]


def follow_camera(track, ahead=0.6, dist=6.2, height=1.7, aim=1.3, step=3):
    cam, target = S.camera(lens=42)
    xs = [kit.mc(f["pelvis"]).x for f in track]
    for fr in range(1, N + 2, step):
        x = xs[min(fr - 1, len(xs) - 1)]
        kit.key(target, fr, loc=(x + ahead, 0, aim))
        kit.key(cam, fr, loc=(x + ahead - 0.4, -dist, height))
    return cam


def fixed_camera(cx, dist=6.2, height=1.7, aim=1.3):
    cam, target = S.camera(lens=42)
    kit.key(target, 1, loc=(cx, 0, aim))
    kit.key(cam, 1, loc=(cx - 0.4, -dist, height))
    return cam


def holdout_below_horizon(cam, D=28.0):
    hold = bpy.data.objects.new("hold", bpy.data.meshes.new("hold"))
    hold.data.from_pydata([(-80, -80, -D), (80, -80, -D), (80, -0.012 * D, -D), (-80, -0.012 * D, -D)], [],
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


# ================================================================ WAIT / PUSH
if META == "wall":
    D = 5.03
    if HALF == "top":
        S.plates(BG / "plate_night.png", bright_keys=[(1, 0.0), (F(D), 0.0), (N, -10.0)])
    else:
        S.plates(BG / "plate_night.png", BG / "plate_calm.png", mix_keys=[(F(D) - 1, 0.0), (F(D + 0.5), 1.0)])
    stone = kit.flat("stone", (0.36, 0.34, 0.30))
    walk = rig.track("Walk_Loop", seconds=1.6, speed=1.1)
    walk = kit.shift(walk, -walk[0]["pelvis"][0] - 1.2, -walk[0]["pelvis"][2])
    n_walk = int(round(1.25 * FPS))
    track = walk[:n_walk]
    HR = kit.HEAD_R / kit.HEIGHT
    if HALF == "top":
        # WAIT FOR A DOOR: he stops, sits down on a stone in front of the wall and waits while the light goes
        stand = feet_at(rig.track("Idle_Loop", seconds=1.0), track[-1])
        track += kit.blend(track[-1], stand[:18], 8)
        sit_in = feet_at(rig.track("Sitting_Enter"), track[-1])
        track += kit.blend(track[-1], sit_in, 6)
        sit = at(rig.track("Sitting_Idle_Loop", seconds=DUR), track[-1])
        track += kit.blend(track[-1], sit, 6)
        track += kit.idle(track[-1], max(0, N + 2 - len(track)))
        hero.drive(track[: N + 2], 1)
        sp = track[-1]["pelvis"]
        seat_top = sp[1] * kit.HEIGHT - 0.17
        seat = kit.block(S, "seat", (0.62, 0.8, seat_top), (kit.mc(sp).x - 0.12, 0.3, seat_top / 2))  # he passes in front
        seat.data.materials.clear()
        seat.data.materials.append(stone)
        wall_x = kit.mc([max(stand[0]["toeR"][0], stand[0]["toeL"][0]) + 0.75, 0, 0]).x
    else:
        # MAKE ONE: he pushes, it does not move; he steps back, runs at it and smashes through on the drop
        push = feet_at(rig.track("Push_Loop", seconds=2), track[-1])[: int(round(1.45 * FPS))]
        push = [kit.reach_arms([f], f["headbase"][0] + 1.72 * HR + 0.07, 0, 0, ramp=1)[0] for f in push]
        track += kit.blend(track[-1], push, 6)
        wall_x = kit.mc([max(f["wristR"][0] for f in push[8:]) + 0.01, 0, 0]).x
        back = at(rig.track("Walk_Loop", seconds=1.2)[::-1], track[-1])        # walk played backwards: steps back
        track += kit.blend(track[-1], back[: int(round(0.8 * FPS))], 6)
        hit_pose = push[len(push) // 2]
        goal = wall_x / kit.HEIGHT - (hit_pose["wristR"][0] - hit_pose["pelvis"][0])   # pelvis x at contact
        run = at(rig.track("Sprint_Loop", seconds=2, speed=0.85), track[-1])
        n_run = next((i for i, f in enumerate(run) if f["pelvis"][0] >= goal), len(run) - 1)
        n_hold = max(0, F(D) - 1 - len(track) - n_run - 3)
        if n_hold:                                                               # coils before the run
            crouch = feet_at(rig.track("Crouch_Idle_Loop", seconds=1.0), track[-1])
            track += kit.blend(track[-1], crouch[:n_hold], 5)
        track += kit.blend(track[-1], at(run, track[-1])[:n_run], 3)
        smash = kit.shift([hit_pose], track[-1]["pelvis"][0] - hit_pose["pelvis"][0] + 0.02,
                          track[-1]["pelvis"][2] - hit_pose["pelvis"][2])[0]
        track += [smash] * 3                                                     # into the wall on the drop
        go = at(rig.track("Sprint_Loop", seconds=DUR - D + 0.5, speed=0.7), track[-1])
        track += kit.blend(track[-1], go, 6)
        track += kit.idle(track[-1], max(0, N + 2 - len(track)))
        hero.drive(track[: N + 2], 1)
    rnd = random.Random(3)
    bw, bh, rows = 0.9, 0.55, 7
    for r in range(rows):
        for k in range(3):                                 # depth (y) columns
            y = (k - 1) * 1.1
            pos = Vector((wall_x + bw / 2, y, bh / 2 + r * bh))
            b = kit.block(S, f"w{r}_{k}", (bw, 1.08, bh * 0.98), pos)
            b.data.materials.clear()
            b.data.materials.append(stone)
            kit.key(b, 1, loc=pos, rot=(0, 0, 0))
            if HALF == "bottom":
                kit.key(b, int(round(2.0 * FPS)), loc=pos + Vector((0.025, 0, 0)), rot=(0, 0, 0))   # just a tremor
                kit.key(b, int(round(2.1 * FPS)), loc=pos, rot=(0, 0, 0))
                kit.key(b, F(D) - 1, loc=pos, rot=(0, 0, 0))
                v = Vector((rnd.uniform(5, 10), rnd.uniform(-2, 2) + y, rnd.uniform(2, 7)))
                for j in range(1, N - F(D) + 2, 2):        # bursts apart, tumbling, under gravity
                    t = j / FPS
                    kit.key(b, F(D) + j, loc=pos + v * t + Vector((0, 0, -4.9 * t * t)),
                            rot=(rnd.uniform(-1, 1) * 6 * t, rnd.uniform(-1, 1) * 6 * t, 0))
    cam, target = S.camera(lens=42)
    xs = [kit.mc(f["pelvis"]).x for f in track[: N + 2]]
    for fr in range(1, N + 2, 3):                          # parallel tracking: the camera never rotates
        x = xs[min(fr - 1, len(xs) - 1)] + 0.7
        if HALF == "top" or fr < F(D):
            x = min(x, wall_x - 0.5)
        kit.key(target, fr, loc=(x, 0, 1.3))
        kit.key(cam, fr, loc=(x, -6.6, 1.5))

# ================================================================ DOUBT / JUMP
elif META == "gap":
    TO = 2.47                                              # on the beat: the edge
    S.plates(BG / "plate_calm.png")
    run = rig.track("Sprint_Loop", seconds=DUR + 1, speed=0.8)
    n_to = int(round(TO * FPS))
    run = kit.shift(run, -run[n_to]["pelvis"][0], -run[0]["pelvis"][2])          # edge at x = 0 (pelvis)
    vx = run[n_to]["pelvis"][0] - run[n_to - 1]["pelvis"][0]
    n_air = int(round(0.72 * FPS))
    edge = kit.mc(run[n_to]["toeR"]).x + 0.1
    gap = 0.55 * vx * n_air * kit.HEIGHT                   # well inside the flight distance
    track = run[:n_to]
    if HALF == "top":
        stop = feet_at(rig.track("Idle_Loop", seconds=DUR), track[-1])
        track += kit.blend(track[-1], stop, 6)                                     # dead stop at the brink
        edge = kit.mc([max(stop[0]["toeR"][0], stop[0]["toeL"][0]) + 0.02, 0, 0]).x
    else:
        # a real leap: takeoff stride -> legs tucked in the air -> reaching the landing stride, on a high arc
        stride = max(range(n_to - 16, n_to), key=lambda i: abs(run[i]["ankleL"][0] - run[i]["ankleR"][0]))
        take, land = run[stride], run[n_to + n_air]
        p0 = run[n_to - 1]["pelvis"]
        for i in range(n_air):
            u = (i + 1) / n_air
            pose = kit.lerp_pose(take, land, min(1.0, max(0.0, (u - 0.25) / 0.5)))   # a stride through the air
            px, py = p0[0] + vx * (i + 1), p0[1] + 0.45 * 4 * u * (1 - u)
            track.append({j: [px + v[0], py + v[1], p0[2] + v[2]] for j, v in pose.items()})
        track[n_to:] = kit.blend(track[n_to - 1], track[n_to:], 3)
        track += kit.blend(track[-1], at(run[n_to + n_air:], track[-1]), 3)
    track += kit.idle(track[-1], max(0, N + 2 - len(track)))
    hero.drive(track[: N + 2], 1)
    # cliffs shallow in depth (front face just in front of him): no side faces, nothing grows on screen
    kit.block(S, "cliff_near", (60, 1.6, 8), (edge - 30, 0.2, -4))
    kit.block(S, "cliff_far", (60, 1.6, 8), (edge + gap + 30, 0.2, -4))
    cam, target = S.camera(lens=50)
    xs = [kit.mc(f["pelvis"]).x for f in track[: N + 2]]
    for fr in range(1, N + 2, 3):                          # parallel tracking: the camera never rotates
        x = xs[min(fr - 1, len(xs) - 1)] + 0.9
        if HALF == "top" and fr >= F(TO):                  # glides on to show the gap he won't jump
            x = xs[F(TO) - 1] + 0.9 + 1.2 * min(1.0, (fr - F(TO)) / 30)
        kit.key(target, fr, loc=(x, 0, 1.0 if HALF == "top" else 1.75))   # room above the leap for the label
        kit.key(cam, fr, loc=(x, -8.0, 1.2 if HALF == "top" else 1.95))

# ================================================================ STAY DOWN / HIT BACK
elif META == "fist":
    HIT, PUNCH = 1.85, 3.70
    S.plates(BG / "plate_dark.png", bright_keys=[(1, 0.0), (F(HIT), 0.0), (N, -30.0 if HALF == "top" else 0.0)]) \
        if HALF == "top" else S.plates(BG / "plate_dark.png", BG / "plate_calm.png",
                                       mix_keys=[(F(PUNCH) - 1, 0.0), (F(PUNCH + 0.4), 1.0)])
    stand = rig.track("Idle_Loop", seconds=DUR)
    stand = kit.shift(stand, -stand[0]["pelvis"][0], -stand[0]["pelvis"][2])
    nh = int(round(HIT * FPS))
    track = stand[:nh]
    # the giant shadow: the same body x1.9, facing him; its cross snaps onto his face exactly at HIT
    G = 1.9
    giant = kit.Hero(S, scale=G)
    gp = rig.track("Punch_Cross", speed=1.8)                                          # a snap, not a shove
    reach = lambda f: max(f["wristR"][0], f["wristL"][0]) - f["pelvis"][0]           # noqa: E731
    g_imp = max(range(len(gp)), key=lambda i: reach(gp[i]))
    g_hand = "wristR" if gp[g_imp]["wristR"][0] >= gp[g_imp]["wristL"][0] else "wristL"
    gi = rig.track("Idle_Loop", seconds=DUR)
    gt = gi[: max(0, nh - g_imp)] + kit.blend(gi[max(0, nh - g_imp) - 1], feet_at(gp, gi[max(0, nh - g_imp) - 1]), 2)
    gt += kit.idle(gt[-1], max(0, N + 2 - len(gt)))
    gt = kit.scale_track(gt, G, anchor=(gt[0]["pelvis"][0], gt[0]["pelvis"][2]))
    gt = kit.mirror_x(gt, about=gt[0]["pelvis"][0])
    hb, ht = track[nh - 1]["headbase"], track[nh - 1]["headtop"]
    L = sum((y - x) ** 2 for x, y in zip(hb, ht, strict=False)) ** 0.5
    head_x = hb[0] + (ht[0] - hb[0]) / L * (kit.HEAD_R * 0.72 / kit.HEIGHT)            # centre of the drawn head
    dx = head_x + 0.06 - gt[nh][g_hand][0]                                             # the fist lands on his face
    gt = kit.shift(gt, dx, -gt[0]["pelvis"][2] + 0.4)
    face = [head_x + 0.04, hb[1] + (ht[1] - hb[1]) / L * (kit.HEAD_R * 0.72 / kit.HEIGHT), gt[nh][g_hand][2]]
    gt = kit.aim_arm(gt, g_hand[-1], face, nh, rise=7, fall=10)                     # aimed down, onto his face
    if HALF == "top":                                                                 # down on the same frame
        fall = at(kit.mirror_x(rig.track("Death01", speed=1.5), about=0.0), track[-1])  # knocked backwards
        fall = [kit.shift([f], -0.6 * (1 - (1 - min(1.0, i / 8)) ** 2), 0)[0] for i, f in enumerate(fall)]
        track += kit.blend(track[-1], fall, 2)
    else:
        hit = feet_at(rig.track("Hit_Head", speed=1.3), track[-1])                  # head snaps back, he staggers
        hit = [kit.shift([f], -0.55 * (1 - (1 - min(1.0, i / 7)) ** 2), 0)[0] for i, f in enumerate(hit)]
        track += kit.blend(track[-1], hit, 1)
        rec = feet_at(rig.track("Idle_Loop", seconds=0.6), track[-1])
        track += kit.blend(track[-1], rec[:12], 4)
        pc = rig.track("Punch_Cross")
        impact = max(range(len(pc)), key=lambda i: max(pc[i]["wristR"][0], pc[i]["wristL"][0]) - pc[i]["pelvis"][0])
        # he must end up in front of the giant: his fist at the giant's belly when the punch lands
        hand = lambda f: max(f["wristR"][0], f["wristL"][0])                         # noqa: E731
        goal = min(gt[nh]["pelvis"][0], gt[nh]["ankleL"][0], gt[nh]["ankleR"][0]) - 0.05
        need = goal - (hand(pc[impact]) - pc[0]["pelvis"][0]) - track[-1]["pelvis"][0]
        charge = at(rig.track("Jog_Fwd_Loop", seconds=3, speed=0.9), track[-1])
        n_run = next((i for i, f in enumerate(charge) if f["pelvis"][0] - charge[0]["pelvis"][0] >= need), len(charge))
        n_wait = int(round(PUNCH * FPS)) - impact - len(track) - n_run
        if n_wait > 0:                                                                # squares up, then charges
            track += kit.idle(track[-1], n_wait)
        track += kit.blend(track[-1], charge[:n_run], 4)
        track += kit.blend(track[-1], feet_at(pc, track[-1]), 3)
    track += kit.idle(track[-1], max(0, N + 2 - len(track)))
    hero.drive(track[: N + 2], 1)
    giant.drive(gt[: N + 2], 1)
    if HALF == "bottom":
        giant.hide_from = F(PUNCH) + 1
    others["shadow"] = giant
    gx = kit.mc(gt[0]["pelvis"]).x
    cx = (kit.mc(track[0]["pelvis"]).x + gx) / 2
    cam, target = S.camera(lens=36)
    kit.key(target, 1, loc=(cx, 0, 1.9))
    kit.key(cam, 1, loc=(cx - 0.3, -7.6, 1.7))
    kit.key(cam, N, loc=(cx - 0.3, -6.9, 1.6))

# ================================================================ QUIT / ONE MORE
elif META == "race":
    QUIT, RIBBON, HIT = 1.85, 6.16, 8.63
    S.plates(BG / "plate_calm.png", bright_keys=[(1, 0.0), (F(QUIT), 0.0), (N, -18.0)] if HALF == "top" else None)
    run = rig.track("Sprint_Loop", seconds=DUR + 1, speed=0.8)
    run = kit.shift(run, -run[0]["pelvis"][0], -run[0]["pelvis"][2])
    nq = int(round(QUIT * FPS))
    if HALF == "top":
        # TURN BACK: he slows, stops, turns around and walks back the way he came
        track = run[:nq]
        slow = at(rig.track("Walk_Loop", seconds=1.6, speed=0.9), track[-1])
        track += kit.blend(track[-1], slow[:30], 10)
        stand = feet_at(rig.track("Idle_Loop", seconds=3), track[-1])
        track += kit.blend(track[-1], stand[:20], 8)
        n_turn = 16
        turn = kit.rotate_track(stand[20:20 + n_turn],
                                [math.pi * (1 - math.cos(math.pi * (i + 1) / n_turn)) / 2 for i in range(n_turn)])
        track += kit.blend(track[-1], turn, 3)
        back = kit.mirror_x(rig.track("Walk_Loop", seconds=DUR, speed=0.9), about=0.0)
        track += kit.blend(track[-1], at(back, track[-1]), 6)
        track += kit.idle(track[-1], max(0, N + 2 - len(track)))
        hero.drive(track[: N + 2], 1)
        cam, target = S.camera(lens=42)
        xs = [kit.mc(f["pelvis"]).x for f in track]
        hold_fr = nq + 50                                                       # the camera stops; he leaves
        for fr in range(1, N + 2, 3):
            x = xs[min(fr - 1, hold_fr)]
            kit.key(target, fr, loc=(x + 0.6, 0, 1.3))
            kit.key(cam, fr, loc=(x + 0.6, -6.2, 1.5))
    else:
        nr = int(round((RIBBON + 1.6) * FPS))
        track = run[:nr]
        slow = at(rig.track("Jog_Fwd_Loop", seconds=1.2, speed=0.8), track[-1])
        track += kit.blend(track[-1], slow[:24], 8)
        stand = feet_at(rig.track("Idle_Loop", seconds=DUR), track[-1])
        track += kit.blend(track[-1], stand, 14)
        track += kit.idle(track[-1], max(0, N + 2 - len(track)))
        hero.drive(track[: N + 2], 1)
        rx = kit.mc(run[int(round(RIBBON * FPS))]["pelvis"]).x + 0.25
        for side in (-1, 1):
            kit.block(S, f"pole{side}", (0.12, 0.12, 2.0), (rx, side * 1.2, 1.0))
            half = bpy.data.objects.new(f"rib{side}", None)
            S.sc.collection.objects.link(half)
            half.location = (rx, side * 1.2, 1.1)
            r = kit.block(S, f"ribbon{side}", (0.05, 1.2, 0.14), (0, -side * 0.6, 0), color=kit.VERMILION)
            r.data.materials.clear()
            r.data.materials.append(bpy.data.materials.get("verm_solid") or kit.flat("verm_solid", kit.VERMILION))
            r.parent = half
            kit.key(half, 1, rot=(0, 0, 0))
            kit.key(half, F(RIBBON), rot=(0, 0, 0))
            kit.key(half, F(RIBBON) + 6, rot=(0, 0, side * math.radians(-80)))      # torn, swinging away
            kit.key(half, F(RIBBON) + 14, rot=(0, 0, side * math.radians(-60)))
        cam = follow_camera(track, ahead=0.8)
        sun = kit.disc(S, "sun", kit.glow("vermilion", kit.VERMILION, 1.0, soft=0.03), 30.0)
        sun.rotation_euler = Euler((math.radians(90), 0, 0))
        ex = kit.mc(track[min(len(track) - 1, F(HIT))]["pelvis"]).x
        kit.key(sun, 1, loc=(ex + 40, 250, -60))
        kit.key(sun, F(HIT) - 4, loc=(ex + 40, 250, -60))
        kit.key(sun, F(HIT) + 10, loc=(ex + 40, 250, 24))                            # bursts up on the hit
        kit.key(sun, N, loc=(ex + 40, 250, 30))
        holdout_below_horizon(cam)

kit.export_2d(S, hero, OUT / "joints2d.json", others)
import os  # noqa: E402

STILLS = os.environ.get("STILLS", "15 45 75 110 150 190 240 300")
S.render(stills=[int(x) for x in STILLS.split() if int(x) <= N] if "--still" in sys.argv else None)
