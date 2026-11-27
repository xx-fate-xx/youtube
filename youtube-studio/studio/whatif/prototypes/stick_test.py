"""Stick-figure concept: rigged black stickmen (forward kinematics) in a painted code landscape.
Scene: noon, people walk; T+ 00:08:20 the Sun's light stops arriving -> instant dark sky, everyone stops and looks up."""

import io
import math
import random
import sys
from pathlib import Path

import resvg_py
from PIL import Image

HERE = Path(__file__).parent
OUT = HERE / "stick"
(OUT / "anim").mkdir(parents=True, exist_ok=True)
FONT_FILES = [str(p) for p in Path(sys.argv[1]).glob("*.ttf")] + [str(p) for p in (HERE / "data").glob("*.ttf")]
W, H = 1920, 1080
FPS, DUR, SWITCH = 30, 9.0, 5.0


def lerp(a, b, t):
    return a + (b - a) * t


def lc(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(lerp(x, y, t)):02x}" for x, y in zip(a, b))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- landscape

DAY = dict(sky0="#3E9AD6", sky1="#CFEAF3", far="#93B4C8", mid="#8CC063", mid2="#62A148", front="#55963F", grass="#3B7430", midb="#5E8F45", mid2b="#3F7A33", frontb="#2F5E28", fg="#1F3D1C", haze="#E6F2F2",
           tree="#2F6B36", trunk="#5A4632", cloud="#FFFFFF")
NIGHT = dict(sky0="#03050C", sky1="#0B1222", far="#141C2B", mid="#121C1A", mid2="#0F1816", front="#0C1412", grass="#0A110F", midb="#0B1311", mid2b="#090F0D", frontb="#070C0A", fg="#040706", haze="#0B1222",
             tree="#0A1310", trunk="#120F0C", cloud="#0E1320")


def ridge(y0, amp, seed, step=24, freqs=(1, 2.3, 5.1)):
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.28) for _ in freqs]
    pts = []
    for x in range(-40, W + 60, step):
        y = y0 + sum(amp / (k + 1) * math.sin(x / W * 2 * math.pi * f + p) for k, (f, p) in enumerate(zip(freqs, ph)))
        pts.append((x, y))
    return pts


def ground_y(x):          # front hill surface (people walk on it)
    return 900 + 18 * math.sin(x / 420 + 0.6) + 8 * math.sin(x / 150)


def mid_y(x):
    return 760 + 30 * math.sin(x / 520 + 2.0)


RND = random.Random(11)
STARS = [(RND.uniform(0, W), RND.uniform(0, 640), RND.choice([1.1, 1.5, 2.0, 2.6]), RND.uniform(0.4, 1)) for _ in range(220)]
FAR = ridge(620, 90, 3)
TREES = [(x, RND.uniform(0.8, 1.25)) for x in (180, 260, 1240, 1310, 1385, 1690)]
BLADES = [(x, RND.uniform(10, 26), RND.uniform(-0.4, 0.4)) for x in range(0, W, 9)]


def poly(pts, bottom=H):
    return "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in pts) + f" L{W + 60},{bottom} L-40,{bottom} Z"


def landscape(night: float, t: float):
    c = {k: lc(DAY[k], NIGHT[k], night) for k in DAY}
    b = [f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["sky0"]}"/>'
         f'<stop offset="1" stop-color="{c["sky1"]}"/></linearGradient>'
         + ''.join(f'<linearGradient id="g{k}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c[k]}"/><stop offset="1" stop-color="{c[k + "b"]}"/></linearGradient>' for k in ("mid", "mid2", "front"))
         + f'<linearGradient id="haze" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["haze"]}" stop-opacity="0"/><stop offset="1" stop-color="{c["haze"]}" stop-opacity="0.55"/></linearGradient>'
         + '<radialGradient id="sun"><stop offset="0.35" stop-color="#FFF6D0"/><stop offset="0.5" stop-color="#FFE38A" stop-opacity="0.8"/>'
         '<stop offset="1" stop-color="#FFE38A" stop-opacity="0"/></radialGradient></defs>',
         f'<rect width="{W}" height="{H}" fill="url(#sky)"/>']
    if night > 0:
        b.append(f'<g opacity="{night:.2f}">' + "".join(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#FFFFFF" opacity="{o:.2f}"/>' for x, y, r, o in STARS) + "</g>")
    if night < 1:
        b.append(f'<circle cx="1500" cy="170" r="210" fill="url(#sun)" opacity="{1 - night:.2f}"/>')
    for cx, cy, s, v in ((380, 190, 1.0, 9), (980, 120, 0.7, 6), (1720, 330, 0.55, 11)):
        x = (cx + t * v) % (W + 400) - 200
        b.append(f'<g transform="translate({x:.0f},{cy}) scale({s})" fill="{c["cloud"]}" opacity="0.92">'
                 '<ellipse cx="0" cy="0" rx="140" ry="40"/><circle cx="-55" cy="-22" r="52"/><circle cx="35" cy="-38" r="66"/>'
                 '<circle cx="100" cy="-8" r="40"/></g>')
    b.append(f'<path d="{poly(FAR)}" fill="{c["far"]}"/>')
    b.append(f'<rect x="0" y="520" width="{W}" height="260" fill="url(#haze)"/>')
    b.append(f'<path d="{poly([(x, mid_y(x)) for x in range(-40, W + 60, 20)])}" fill="url(#gmid)"/>')
    for x, s in TREES:
        y = mid_y(x)
        b.append(f'<rect x="{x - 6 * s:.0f}" y="{y - 70 * s:.0f}" width="{12 * s:.0f}" height="{74 * s:.0f}" fill="{c["trunk"]}"/>'
                 f'<ellipse cx="{x}" cy="{y - 100 * s:.0f}" rx="{46 * s:.0f}" ry="{58 * s:.0f}" fill="{c["tree"]}"/>')
    b.append(f'<path d="{poly([(x, 820 + 20 * math.sin(x / 300)) for x in range(-40, W + 60, 20)])}" fill="url(#gmid2)"/>')
    b.append(f'<path d="{poly([(x, ground_y(x)) for x in range(-40, W + 60, 12)])}" fill="url(#gfront)"/>')
    sway = math.sin(t * 1.7)
    b.append('<g stroke="' + c["grass"] + '" stroke-width="4" stroke-linecap="round">' + "".join(
        f'<path d="M{x},{ground_y(x) + 3:.0f} l{(lean + 0.15 * sway) * h:.1f},{-h:.1f}"/>' for x, h, lean in BLADES) + "</g>")
    return "".join(b)


FG = [(x, RND.uniform(40, 110), RND.uniform(-0.5, 0.5)) for x in range(-20, W + 20, 14)]


def foreground(night, t):
    col = lc(DAY["fg"], NIGHT["fg"], night)
    sway = math.sin(t * 1.3 + 1)
    base = [(x, 1050 + 22 * math.sin(x / 260) + 14 * math.sin(x / 90)) for x in range(-40, W + 60, 16)]
    out = [f'<path d="{poly(base)}" fill="{col}"/>', f'<g stroke="{col}" stroke-width="9" stroke-linecap="round">']
    for x, h, lean in FG:
        y = 1050 + 22 * math.sin(x / 260) + 14 * math.sin(x / 90)
        if x % 3 == 0 or (300 < x < 1600 and x % 2):   # keep the middle low so people stay clear
            h *= 0.45
        out.append(f'<path d="M{x},{y + 10:.0f} q{(lean + 0.1 * sway) * h * 0.5:.1f},{-h * 0.6:.1f} {(lean + 0.12 * sway) * h:.1f},{-h:.1f}"/>')
    return "".join(out) + "</g>"


# ---------------------------------------------------------------- stickman rig (forward kinematics)

THIGH, SHIN, TORSO, UPPER, FORE, HEAD = 50, 50, 74, 40, 40, 21


def seg(p, ang, length):
    """angle 0 = straight down, positive = towards facing (+x)."""
    a = math.radians(ang)
    return (p[0] + math.sin(a) * length, p[1] + math.cos(a) * length)


def rig(pose):
    hip = (0.0, 0.0)
    neck = seg(hip, 180 + pose["torso"], TORSO)
    head = seg(hip, 180 + pose["torso"], TORSO + HEAD + 4)
    sh = seg(hip, 180 + pose["torso"], TORSO - 6)
    pts = {"hip": hip, "neck": neck, "head": head}
    for s in ("L", "R"):
        k = seg(hip, pose["thigh" + s], THIGH)
        pts["knee" + s], pts["foot" + s] = k, seg(k, pose["thigh" + s] + pose["knee" + s] * -1, SHIN)
        e = seg(sh, pose["arm" + s], UPPER)
        pts["elb" + s], pts["hand" + s] = e, seg(e, pose["arm" + s] + pose["elb" + s], FORE)
    pts["sh"] = sh
    low = max(pts["footL"][1], pts["footR"][1])
    return {k: (x, y - low) for k, (x, y) in pts.items()}


def walk(ph, amp=1.0):
    s, c = math.sin(ph), math.cos(ph)
    return dict(torso=-4 * amp, thighL=28 * s * amp, kneeL=50 * max(0, -c) * amp + 6, thighR=-28 * s * amp,
                kneeR=50 * max(0, c) * amp + 6, armL=-26 * s * amp, elbL=20, armR=26 * s * amp, elbR=20)


STAND = dict(torso=0, thighL=6, kneeL=4, thighR=-6, kneeR=4, armL=-8, elbL=6, armR=8, elbR=6)
LOOKUP = dict(torso=12, thighL=10, kneeL=4, thighR=-6, kneeR=4, armL=-20, elbL=20, armR=30, elbR=40)
POINT = dict(torso=14, thighL=10, kneeL=4, thighR=-8, kneeR=4, armL=-10, elbL=10, armR=150, elbR=6)
SHOCK = dict(torso=8, thighL=12, kneeL=8, thighR=-12, kneeR=8, armL=-130, elbL=-50, armR=130, elbR=50)


def blend(a, b, t):
    return {k: lerp(a[k], b[k], t) for k in a}


def stickman(x, y, s, face, pose, rim=0.0, hat=None):
    p = rig(pose)
    tr = f'translate({x:.1f},{y:.1f}) scale({s * face:.3f},{s:.3f})'

    def P(k):
        return f"{p[k][0]:.1f},{p[k][1]:.1f}"
    d = (f"M{P('footL')} L{P('kneeL')} L{P('hip')} L{P('kneeR')} L{P('footR')} M{P('hip')} L{P('neck')} "
         f"M{P('handL')} L{P('elbL')} L{P('sh')} L{P('elbR')} L{P('handR')}")
    hx, hy = p["head"]
    out = [f'<g transform="{tr}">']
    if rim > 0:   # cool rim so black figures read against the night
        out.append(f'<g opacity="{rim:.2f}"><path d="{d}" stroke="#6F86A8" stroke-width="17" stroke-linecap="round" '
                   f'stroke-linejoin="round" fill="none"/><circle cx="{hx:.1f}" cy="{hy:.1f}" r="{HEAD + 3.5}" fill="#6F86A8"/></g>')
    out.append(f'<path d="{d}" stroke="#0B0B0D" stroke-width="11" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
               f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{HEAD}" fill="#0B0B0D"/>')
    if hat == "hardhat":
        out.append(f'<path d="M{hx - 24:.1f},{hy - 4:.1f} A24,22 0 0,1 {hx + 24:.1f},{hy - 4:.1f} L{hx + 30:.1f},{hy - 1:.1f} '
                   f'L{hx - 26:.1f},{hy - 1:.1f} Z" fill="#F2B233"/>')
    elif hat == "scarf":
        nx, ny = p["neck"]
        out.append(f'<path d="M{nx - 12:.1f},{ny + 4:.1f} L{nx + 12:.1f},{ny + 4:.1f} L{nx - 14:.1f},{ny + 38:.1f} L{nx - 24:.1f},{ny + 34:.1f} Z" fill="#D9452B"/>')
    elif hat == "cap":
        out.append(f'<path d="M{hx - 21:.1f},{hy - 3:.1f} A21,20 0 0,1 {hx + 21:.1f},{hy - 3:.1f} L{hx + 36:.1f},{hy - 1:.1f} '
                   f'L{hx - 21:.1f},{hy - 1:.1f} Z" fill="#2E7DD1"/>')
    out.append("</g>")
    return "".join(out)


# actors: start x, speed px/s, facing, scale, layer, final pose, hat, reaction delay
ACTORS = [
    (-36, 80, 1, 1.0, "front", POINT, "hardhat", 0.15),
    (421, 60, 1, 0.98, "front", LOOKUP, None, 0.35),
    (1946, -75, -1, 1.02, "front", SHOCK, "scarf", 0.25),
    (1469, -55, -1, 0.96, "front", LOOKUP, "cap", 0.5),
    (700, 45, 1, 0.55, "mid", LOOKUP, None, 0.6),
    (1000, -40, -1, 0.55, "mid", POINT, None, 0.7),
    (1400, 35, 1, 0.52, "mid", LOOKUP, None, 0.8),
]


def people(t, night):
    out = []
    for x0, v, face, s, layer, final, hat, delay in sorted(ACTORS, key=lambda a: a[3]):
        stop = ease((t - SWITCH - delay) / 0.6)       # decelerate after the light goes
        # distance travelled: full speed until stop starts, then smooth slowdown
        t_run = min(t, SWITCH + delay)
        extra = 0.0
        if t > SWITCH + delay:
            dt = min(t - SWITCH - delay, 0.6)
            extra = v * (dt - dt * dt / 1.2)
        x = x0 + v * t_run + extra
        ph = (x - x0) / (s * 34) * (1 if v > 0 else -1)
        pose = blend(walk(ph), final, ease((t - SWITCH - delay - 0.3) / 0.5)) if t > SWITCH + delay else walk(ph)
        y = ground_y(x) + 4 if layer == "front" else mid_y(x) + 34
        out.append(stickman(x, y, s, face, pose, rim=night * 0.55, hat=hat))
    return "".join(out)


def text(x, y, s, size, fill, anchor="start", weight=800, family="Inter Display", ls=0, op=1.0):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-weight="{weight}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" opacity="{op:.2f}">{s}</text>')


def frame(t):
    night = ease((t - SWITCH) / 0.25)        # no air glow without the Sun: the sky goes dark at once
    sec = 15 + int(t * (5 / SWITCH)) if t < SWITCH else 20 + int(t - SWITCH)
    body = landscape(night, t) + people(t, night) + foreground(night, t)
    body += text(1810, 100, f"T+ 00:08:{min(sec, 59):02d}", 40, "#FFB547", "end", 600, "IBM Plex Mono")
    cap = ease((t - SWITCH - 1.2) / 0.5)
    if cap > 0:
        body += text(110, 170, "The last sunlight", 84, "#F2EEE4", op=cap)
        body += text(110, 262, "just arrived.", 84, "#F2EEE4", op=cap)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{body}</svg>'
    png = resvg_py.svg_to_bytes(svg_string=svg, font_files=FONT_FILES, skip_system_fonts=True)
    return Image.open(io.BytesIO(bytes(png))).convert("RGB")


if __name__ == "__main__":
    for i in range(int(DUR * FPS)):
        frame(i / FPS).save(OUT / "anim" / f"{i:04d}.png")
    print("ok")
