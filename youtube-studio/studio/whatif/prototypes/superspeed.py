"""Pilot test: 'What if you had super speed?' — mocap hero with an amber scarf, scrolling city, speed levels,
freeze-frame physics (chalk annotations over a desaturated frozen frame), sonic boom.

Facts on screen: Usain Bolt peak ~44.7 km/h (12.4 m/s, Berlin 2009); speed of sound in air at 20 C ~343 m/s
= 1,235 km/h; drag ~ v^2 -> (343/12.4)^2 ~ 765 (wave drag near Mach 1 adds more, hence 'at least')."""

import io
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import stick2 as s2        # noqa: E402
import stick_test as st    # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "superspeed"
(OUT / "anim").mkdir(parents=True, exist_ok=True)
W, H, FPS = 1920, 1080, 30
T_RUN, T_FREEZE, T_UNFREEZE, T_END = 3.0, 8.0, 12.0, 14.5
N = int(T_END * FPS)
HERO_H, GROUND = 250, 975
AMBER = "#FFB547"

# ---------------------------------------------------------------- background strip (city, mirrored tiles)
src = Image.open(HERE / "bg" / "2_city.png").convert("RGB")
src = src.resize((round(src.width * H / src.height), H), Image.Resampling.LANCZOS)
tiles = [src if k % 2 == 0 else src.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for k in range(8)]
STRIP = np.concatenate([np.asarray(t) for t in tiles], axis=1).astype(np.float32)


def background(offset, blur_px, freeze=0.0, shake=(0, 0)):
    x0 = int(offset) % (STRIP.shape[1] - W - 200) + 100 + int(shake[0])
    a = STRIP[:, x0 - 100:x0 + W + 100]
    k = int(blur_px)
    if k > 1:                                     # horizontal motion blur (box) via cumulative sum
        c = np.cumsum(np.pad(a, ((0, 0), (k, 0), (0, 0))), axis=1)
        a = (c[:, k:] - c[:, :-k]) / k
    a = a[:, 100:100 + W]
    if shake[1]:
        a = np.roll(a, int(shake[1]), axis=0)
    if freeze > 0:
        g = a.mean(-1, keepdims=True)
        a = a * (1 - 0.8 * freeze) + g * 0.8 * freeze
        a = a * (1 - 0.42 * freeze)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- hero simulation

WALK, RUN = s2.walk_seq(s2.WALK_A, 400), s2.walk_seq(s2.RUN, 2000)


def cadence(t):
    if t < 5.5:
        return 1.0
    if t < 7.2:
        return 1.0 + 1.2 * s2.st.ease((t - 5.5) / 1.0)
    return 2.2 + 1.6 * s2.st.ease((t - 7.2) / 0.8)


def kmh(t):
    if t < T_RUN:
        return 5
    if t < 5.5:
        return 5 + 39 * s2.st.ease((t - T_RUN) / 1.5)
    if t < 7.2:
        return 44 + 86 * s2.st.ease((t - 5.5) / 1.0)
    return 130 + 1105 * s2.st.ease((t - 7.2) / 0.8) ** 2


def rel(f):
    return s2.rel(f)


def lerp_pose(a, b, w):
    return {j: (a[j][0] * (1 - w) + b[j][0] * w, a[j][1] * (1 - w) + b[j][1] * w, a[j][2] * (1 - w) + b[j][2] * w)
            for j in a}


SIM = []          # per frame: pose (pelvis-relative), hero screen x, scroll offset, speed factor
x_screen, offset, k_run = 150.0, 0.0, 0.0
p_walk0 = WALK[0]["pelvis"][0]
for i in range(N):
    t = i / FPS
    if t < T_RUN:
        f = WALK[i]
        x_screen = 150 + (f["pelvis"][0] - p_walk0) * HERO_H
        pose = rel(f)
        spd = 0.0
    elif t < T_FREEZE:
        c = cadence(t)
        prev = RUN[int(k_run)]["pelvis"][0]
        k_run += c
        cur = RUN[int(k_run)]["pelvis"][0]
        offset += (cur - prev) * HERO_H
        pose = rel(RUN[int(k_run)])
        w = s2.st.ease((t - T_RUN) / 0.3)
        if w < 1:
            pose = lerp_pose(rel(WALK[i]), pose, w)
        spd = min(1.0, (c - 0.6) / 3.0)
    else:
        pose, spd = SIM[-1]["pose"], SIM[-1]["spd"]
        if t >= T_UNFREEZE:
            x_screen += 260 * (1 + (t - T_UNFREEZE) * 8)          # zip out of frame
    SIM.append(dict(pose=pose, x=x_screen, off=offset, spd=spd, k=k_run))

X_LOCK = SIM[int(T_RUN * FPS)]["x"]
for s in SIM[int(T_RUN * FPS):int(T_UNFREEZE * FPS)]:
    s["x"] = X_LOCK
OFF_FREEZE = SIM[int(T_FREEZE * FPS) - 1]["off"]

# bystanders (world x). Group B stands where the hero freezes.
SW_BOOM = int((T_UNFREEZE + 0.05) * FPS)
BY = [dict(wx=1250, h=235, g=962, flip=True, seq=s2.walk_seq(s2.WALK_B, N, 4)),
      dict(wx=1650, h=225, g=950, flip=False, seq=s2.hold([s2.WALK_B[-1]], N))]
stand = [s2.WALK_B[-1]] * N
for dx, h, g, flip, react, cut in ((X_LOCK - 430, 230, 958, False, s2.SURPRISE, 3.45), (X_LOCK + 420, 240, 968, True, s2.SCARED, 0.5),
                                   (X_LOCK + 700, 215, 948, True, s2.SURPRISE, 3.45), (X_LOCK + 960, 228, 960, True, s2.SCARED, 0.5)):
    BY.append(dict(wx=OFF_FREEZE + dx, h=h, g=g, flip=flip,
                   seq=s2.hold(s2.blend_into(stand, s2.segment(react, cut), SW_BOOM + random.Random(dx).randint(0, 5), 6), N)))


# ---------------------------------------------------------------- drawing helpers

def pose_actor(pose, x, h, g, flip=False, hat=None):
    return dict(x0=x, h=h, flip=flip, layer="front", hat=hat, seq=[pose], ground=g)


def draw_actor(a, night=0.0):
    st.ground_y = (lambda gg: (lambda _x: gg))(a["ground"])
    return s2.stick(a, 0, night)


def neck_xy(pose, x, h, g):
    hip = ((pose["hipL"][0] + pose["hipR"][0]) / 2, (pose["hipL"][1] + pose["hipR"][1]) / 2 + 0.02)
    nx, ny, _ = pose["neck"]
    nx, ny = hip[0] + (nx - hip[0]) * 1.12, hip[1] + (ny - hip[1]) * 1.12
    return x + (nx - pose["pelvis"][0]) * h, g + 2 - ny * h


def scarf(pose, x, h, g, spd, t):
    nx, ny = neck_xy(pose, x, h, g)
    L = h * (0.32 + 0.35 * spd)
    ang0 = math.radians(-70 + 66 * spd)          # -70 deg: hangs down-back; ~0: streams straight back
    pts = [(nx, ny + h * 0.01)]
    for k in range(1, 7):
        u = k / 6
        wave = math.sin(t * (6 + 22 * spd) - k * 1.1) * (0.10 + 0.12 * spd) * u
        a = ang0 + wave
        px = nx - math.cos(a) * L * u
        py = ny + h * 0.01 - math.sin(a) * L * u
        pts.append((px, py))
    d = "M" + " L".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
    wid = h * 0.045
    return (f'<path d="M{nx - h * 0.03:.1f},{ny:.1f} L{nx + h * 0.03:.1f},{ny:.1f}" stroke="{AMBER}" stroke-width="{wid * 1.2:.1f}" stroke-linecap="round"/>'
            f'<path d="{d}" stroke="{AMBER}" stroke-width="{wid:.1f}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>')


def ghost(pose, x, h, g, op):
    old = (s2.NEAR, s2.FAR)
    s2.NEAR, s2.FAR = AMBER, "#C98A2E"
    out = f'<g opacity="{op:.2f}">' + draw_actor(pose_actor(pose, x, h, g)) + "</g>"
    s2.NEAR, s2.FAR = old
    return out.replace('fill="#000"', 'fill="none"')


def shadowed(svg_text):
    return f'<g filter="url(#sh)" opacity="1">{svg_text.replace("#F2EEE4", "#000").replace(AMBER, "#000")}</g>{svg_text}'


def chalk_line(pts, p, width=6):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    L = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    return (f'<path d="{d}" stroke="#F4F1E8" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" fill="none" '
            f'stroke-dasharray="{L:.0f}" stroke-dashoffset="{L * (1 - p):.0f}" filter="url(#chalk)"/>')


def wobble(pts, seed, amp=3):
    r = random.Random(seed)
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for k in range(8):
            u = k / 8
            out.append((x0 + (x1 - x0) * u + r.uniform(-amp, amp), y0 + (y1 - y0) * u + r.uniform(-amp, amp)))
    out.append(pts[-1])
    return out


def chalk_text(x, y, s, size, p, weight=600, fam="Inter", col="#F4F1E8"):
    n = max(0, min(len(s), int(len(s) * p + 0.999)))
    if n == 0:
        return ""
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-weight="{weight}" font-size="{size}" fill="{col}" '
            f'filter="url(#chalk)">{s[:n]}</text>')


DEFS = ('<defs><filter id="sh" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="7"/></filter><radialGradient id="scrim"><stop offset="0" stop-color="#000" stop-opacity="0.62"/><stop offset="0.6" stop-color="#000" stop-opacity="0.32"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
        '<filter id="chalk" x="-5%" y="-20%" width="110%" height="140%"><feTurbulence type="fractalNoise" baseFrequency="0.9" '
        'numOctaves="2" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="3.5"/></filter></defs>')

LEVELS = [(3.4, 5.5, "LEVEL 1", "44 km/h", "Usain Bolt's top speed"),
          (5.9, 7.2, "LEVEL 2", "130 km/h", "highway speed"),
          (7.6, 99, "LEVEL 3", "1,235 km/h", "the speed of sound")]


REACHED = {"LEVEL 1": 4.5, "LEVEL 2": 6.5, "LEVEL 3": 8.0}


def hud(t):
    out = []
    if t < 2.9:
        op = s2.st.ease((t - 0.3) / 0.4) * (1 - s2.st.ease((t - 2.5) / 0.4))
        if op > 0:
            out.append(shadowed(st.text(110, 170, "What if you had", 84, "#F2EEE4", op=op)
                                + st.text(110, 262, "super speed?", 84, "#F2EEE4", op=op)))
    for a, b, lev, val, note in LEVELS:
        if a <= t < min(b, T_UNFREEZE):
            op = s2.st.ease((t - a) / 0.25)
            live = f"{round(kmh(t)):,} km/h" if t < T_FREEZE else val
            out.append(shadowed(st.text(110, 120, lev, 30, AMBER, "start", 600, "IBM Plex Mono", 6, op)
                                + st.text(110, 210, live, 92, "#F2EEE4", op=op)
                                + st.text(112, 258, note, 34, "#F2EEE4", "start", 600, "Inter", 0,
                                          op * s2.st.ease((t - REACHED[lev]) / 0.25))))
    return "".join(out)


def freeze_notes(t, hx):
    p = lambda a, d=0.6: s2.st.ease((t - a) / d)    # noqa: E731
    gy = GROUND - HERO_H * 0.62
    out = []
    # AIR arrow pushing back on the hero
    arrow = wobble([(hx + 560, gy), (hx + 120, gy)], 1)
    out.append(chalk_line(arrow, p(8.35, 0.5)))
    if p(8.85, 0.2) > 0:
        out.append(chalk_line(wobble([(hx + 160, gy - 34), (hx + 118, gy), (hx + 160, gy + 34)], 2), p(8.85, 0.2)))
    out.append(chalk_text(hx + 360, gy - 30, "AIR", 46, p(8.6, 0.4), 800, "Inter Display"))
    # speed of sound note
    x0, y0 = 1130, 190
    out.append(chalk_text(x0, y0, "≈ 28× Bolt's top speed", 44, p(9.2, 0.8)))
    out.append(chalk_text(x0, y0 + 70, "Air drag grows with speed²", 40, p(10.0, 0.8), 500))
    out.append(chalk_text(x0, y0 + 160, "at least ~770×", 76, p(10.8, 0.5), 800, "Inter Display"))
    out.append(chalk_text(x0, y0 + 215, "the air resistance Bolt feels", 40, p(11.1, 0.6), 500))
    out.append(chalk_line(wobble([(x0, y0 + 175), (x0 + 560, y0 + 175)], 5, 2), p(11.5, 0.3), 4))
    return "".join(out)


def frame(i):
    t = i / FPS
    s = SIM[i]
    freeze = 0.0
    if T_FREEZE <= t < T_UNFREEZE:
        freeze = min(1.0, (t - T_FREEZE) / 0.15)
    elif T_UNFREEZE <= t < T_UNFREEZE + 0.2:
        freeze = 1 - (t - T_UNFREEZE) / 0.2
    shake = (0, 0)
    if t >= T_UNFREEZE:
        d = max(0.0, 1 - (t - T_UNFREEZE) / 0.8)
        r = random.Random(i)
        shake = (r.uniform(-1, 1) * 22 * d, r.uniform(-1, 1) * 14 * d)
    blur = 0 if t >= T_FREEZE or t < T_RUN else min(70, (cadence(t) - 0.7) * 18)
    bg = background(s["off"], blur, freeze, shake)
    svg = [DEFS, f'<g transform="translate({shake[0]:.1f},{shake[1]:.1f})">']
    # speed streaks
    if T_RUN + 2.5 < t < T_FREEZE:
        r = random.Random(i)
        for _ in range(int(10 + 25 * s["spd"])):
            y = r.uniform(120, 1000)
            x = r.uniform(-200, W)
            ln = r.uniform(150, 600) * (0.5 + s["spd"])
            svg.append(f'<path d="M{x:.0f},{y:.0f} l{ln:.0f},0" stroke="#FFFFFF" stroke-width="{r.uniform(1.5, 4):.1f}" '
                       f'opacity="{r.uniform(0.15, 0.45) * s["spd"]:.2f}" stroke-linecap="round"/>')
    # bystanders
    for b in BY:
        x = b["wx"] - s["off"] + (b["seq"][min(i, len(b["seq"]) - 1)]["pelvis"][0] - b["seq"][0]["pelvis"][0]) * b["h"] * (-1 if b["flip"] else 1)
        if -300 < x < W + 300:
            f = b["seq"][min(i, len(b["seq"]) - 1)]
            svg.append(draw_actor(pose_actor(rel(f), x, b["h"], b["g"], b["flip"])))
    # hero: ghosts, scarf, body
    if t < T_UNFREEZE + 0.5:
        if T_RUN + 2.0 < t < T_UNFREEZE:
            for j in (3, 2, 1):
                gi = max(0, i - j)
                gs = SIM[gi]
                gap = j * (30 + 90 * s["spd"])
                svg.append(ghost(gs["pose"], s["x"] - gap, HERO_H, GROUND, 0.12 + 0.1 * (3 - j)))
        svg.append(scarf(s["pose"], s["x"], HERO_H, GROUND, s["spd"] if t < T_FREEZE else SIM[int(T_FREEZE * FPS) - 1]["spd"],
                         t if t < T_FREEZE else T_FREEZE))
        svg.append(draw_actor(pose_actor(s["pose"], s["x"], HERO_H, GROUND)))
    # boom
    if t >= T_UNFREEZE:
        u = t - T_UNFREEZE
        cx, cy = X_LOCK + 40, GROUND - HERO_H * 0.55
        for k, delay in enumerate((0.0, 0.08, 0.18)):
            v = u - delay
            if 0 < v < 0.9:
                rx = 60 + v * 2200
                svg.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{rx * 0.42:.0f}" fill="none" stroke="#FFFFFF" '
                           f'stroke-width="{max(1, 14 - k * 4 - v * 12):.1f}" opacity="{max(0, 0.7 - v * 0.8):.2f}"/>')
        r = random.Random(42)
        for _ in range(70):
            ang = r.uniform(math.pi * 1.05, math.pi * 1.95)
            sp = r.uniform(200, 900)
            vx, vy = math.cos(ang) * sp, math.sin(ang) * sp
            x, y = cx + vx * u, GROUND - 5 + vy * u + 900 * u * u
            if y < GROUND + 10:
                svg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r.uniform(3, 9):.1f}" fill="#CDBBA0" opacity="{max(0, 0.8 - u * 0.5):.2f}"/>')
        if u < 0.18:
            svg.append(f'<rect width="{W}" height="{H}" fill="#FFFFFF" opacity="{0.55 * (1 - u / 0.18):.2f}"/>')
    svg.append("</g>")
    if 0.25 < t < T_UNFREEZE + 0.1 or t > T_UNFREEZE + 0.8:
        svg.append(f'<ellipse cx="330" cy="170" rx="760" ry="330" fill="url(#scrim)"/>')
    if T_FREEZE + 0.9 < t < T_UNFREEZE + 0.15:
        op = min(1, (t - T_FREEZE - 0.9) / 0.4) * (1 if t < T_UNFREEZE else 1 - (t - T_UNFREEZE) / 0.15)
        svg.append(f'<ellipse cx="1440" cy="300" rx="760" ry="330" fill="url(#scrim)" opacity="{op:.2f}"/>')
    if T_FREEZE <= t < T_UNFREEZE + 0.15:
        fade = 1 - s2.st.ease((t - T_UNFREEZE) / 0.15) if t >= T_UNFREEZE else 1
        svg.append(f'<g opacity="{fade:.2f}">' + freeze_notes(t, X_LOCK) + "</g>")
    svg.append(hud(t))
    if t > T_UNFREEZE + 0.9:
        op = s2.st.ease((t - T_UNFREEZE - 0.9) / 0.4)
        svg.append(shadowed(st.text(110, 210, "And that's only level 3.", 84, "#F2EEE4", op=op)))
    doc = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{"".join(svg)}</svg>'
    png = st.resvg_py.svg_to_bytes(svg_string=doc, font_files=st.FONT_FILES, skip_system_fonts=True)
    ov = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    out = bg.convert("RGBA")
    out.alpha_composite(ov)
    return out.convert("RGB")


if __name__ == "__main__":
    mode = sys.argv[2] if len(sys.argv) > 2 else "all"
    if mode == "test":
        for t in (1.5, 4.5, 6.8, 7.9, 11.5, 12.15, 13.6):
            frame(int(t * FPS)).save(OUT / f"t{t}.png")
    else:
        for i in range(N):
            frame(i).save(OUT / "anim" / f"{i:04d}.png")
    print("ok")
