"""Stickmen v2: real human motion (CMU mocap) projected to 2D, looped walks with planted feet, blended reactions."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import stick_test as st          # landscape, foreground, text, ease, lc  # noqa: E402
from mocap import Clip           # noqa: E402

HERE = Path(__file__).parent
M = HERE / "mocap"
OUT = HERE / "stick2"
(OUT / "anim").mkdir(parents=True, exist_ok=True)
FPS = 30
DUR, SWITCH = 10.0, 5.5
st.SWITCH = SWITCH
st.ground_y = lambda x: 930 + 6 * math.sin(x / 400 + 0.6)       # gentle front meadow


def load(cid, fps=FPS):
    s = cid.split("_")[0]
    fr = Clip(M / f"{s}.asf", M / f"{cid}.amc").joints2d(fps)
    # face +x: toes ahead of ankles on average
    fwd = sum((f["toeL"][0] - f["ankleL"][0]) + (f["toeR"][0] - f["ankleR"][0]) for f in fr)
    if fwd < 0:
        fr = [{j: (-x, y, z) for j, (x, y, z) in f.items()} for f in fr]
    return fr


def rel(f):
    px = f["pelvis"][0]
    return {j: (x - px, y, z) for j, (x, y, z) in f.items()}


def dist(a, b):
    ra, rb = rel(a), rel(b)
    return sum((ra[j][0] - rb[j][0]) ** 2 + (ra[j][1] - rb[j][1]) ** 2 for j in ra)


def walk_loop(fr, start=0, min_len=24):
    best = min(range(start + min_len, len(fr)), key=lambda b: dist(fr[start], fr[b]))
    return fr[start:best], fr[best]["pelvis"][0] - fr[start]["pelvis"][0]


def walk_seq(fr, n, start=0):
    cyc, dx = walk_loop(fr, start)
    out = []
    for i in range(n):
        k, f = divmod(i, len(cyc))
        out.append({j: (x + k * dx, y, z) for j, (x, y, z) in cyc[f].items()})
    return out


def blend_into(seq, react, at, length=10):
    """seq continues until frame `at`, then cross-fades (pelvis-relative) into `react` (aligned in x)."""
    out = seq[:at]
    base_x = seq[at]["pelvis"][0]
    rx0 = react[0]["pelvis"][0]
    for i, rf in enumerate(react):
        r = {j: (x - rx0 + base_x, y, z) for j, (x, y, z) in rf.items()}
        if i < length and at + i < len(seq):
            w = st.ease(i / length)
            s = seq[at + i]
            sx = s["pelvis"][0]
            # blend relative poses, keep pelvis x easing from walking to reacting
            px = sx + (r["pelvis"][0] - sx) * w
            f = {}
            for j in r:
                a, b = s[j], r[j]
                f[j] = (px + (a[0] - sx) * (1 - w) + (b[0] - r["pelvis"][0]) * w, a[1] * (1 - w) + b[1] * w,
                        a[2] * (1 - w) + b[2] * w)
            out.append(f)
        else:
            out.append(r)
    return out


def segment(fr, t0, t1=None):
    a = int(t0 * FPS)
    return fr[a:int(t1 * FPS) if t1 else None]


# ---------------------------------------------------------------- actors

N = int(DUR * FPS)
SW = int(SWITCH * FPS)
WALK_A, WALK_B = load("02_01"), load("16_33")
SURPRISE, SCARED, LOOK = load("120_15"), load("79_73"), load("77_01")
RUN = load("09_01")


def hold(seq, n):
    return seq + [seq[-1]] * max(0, n - len(seq))


ACTORS = []
# x0 (screen px), height px, mirrored, frames, extra
ACTORS.append(dict(x0=-120, h=300, flip=False, layer="front", hat="hardhat",
                   seq=hold(blend_into(walk_seq(WALK_A, N), segment(SURPRISE, 3.45), SW + 5, 9), N)))
ACTORS.append(dict(x0=2040, h=290, flip=True, layer="front", hat="scarf",
                   seq=hold(blend_into(walk_seq(WALK_B, N, 0), segment(SCARED, 0.5), SW + 9, 12), N)))
ACTORS.append(dict(x0=1050, h=150, flip=False, layer="mid", hat=None,
                   seq=hold(blend_into([WALK_B[-1]] * N, segment(SCARED, 0.5), SW + 6, 12), N)))
ACTORS.append(dict(x0=-200, h=160, flip=False, layer="mid", hat="cap", seq=walk_seq(RUN, N)))
ACTORS.append(dict(x0=1600, h=140, flip=True, layer="mid", hat=None,
                   seq=hold(blend_into(walk_seq(WALK_A, N, 3), segment(SURPRISE, 3.45), SW + 14, 10), N)))

NEAR, FAR = "#0B0B0E", "#2E3038"
LIMBS = [("L", ["hipC", "kneeL", "ankleL", "toeL"]), ("R", ["hipC", "kneeR", "ankleR", "toeR"]),
         ("L", ["shC", "elbL", "wristL"]), ("R", ["shC", "elbR", "wristR"])]


def stick(a, i, night):
    f = a["seq"][min(i, len(a["seq"]) - 1)]
    h, sgn = a["h"], (-1 if a["flip"] else 1)
    p0 = a["seq"][0]["pelvis"][0]
    cx = a["x0"] + sgn * (f["pelvis"][0] - p0) * h
    gy = st.ground_y(cx) + 2 if a["layer"] == "front" else st.mid_y(cx) + 30

    hip = ((f["hipL"][0] + f["hipR"][0]) / 2, (f["hipL"][1] + f["hipR"][1]) / 2 + 0.02, 0)
    pts = dict(f)
    pts["hipC"] = hip
    for j in ("chest", "neck", "headbase", "headtop", "elbL", "elbR", "wristL", "wristR"):   # stylise: bigger upper body
        x, y, z = pts[j]
        pts[j] = (hip[0] + (x - hip[0]) * 1.12, hip[1] + (y - hip[1]) * 1.12, z)
    sh, ch = pts["neck"], pts["chest"]
    pts["shC"] = (sh[0] * 0.85 + ch[0] * 0.15, sh[1] * 0.85 + ch[1] * 0.15, 0)

    def P(j):
        x, y, _ = pts[j]
        return a["x0"] + sgn * (x - p0) * h, gy - y * h

    sw = h * 0.05
    near_side = "R"    # camera side (consistent draw order for every actor)
    col_far = st.lc(FAR, "#1C2230", night)
    body = []
    # contact shadow
    body.append(f'<ellipse cx="{cx:.1f}" cy="{gy + 2:.1f}" rx="{h * 0.2:.1f}" ry="{h * 0.03:.1f}" fill="#000" '
                f'opacity="{0.22 * (1 - night):.2f}"/>')

    def line(js, col, w):
        d = "M" + " L".join(f"{P(j)[0]:.1f},{P(j)[1]:.1f}" for j in js)
        return f'<path d="{d}" stroke="{col}" stroke-width="{w:.1f}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'

    rim = []
    for side, js in LIMBS:
        if side != near_side:
            body.append(line(js, col_far, sw * 0.95))
            rim.append(js)
    spine = ["hipC", "chest", "neck"]
    body.append(line(spine, NEAR, sw * 1.15))
    for side, js in LIMBS:
        if side == near_side:
            body.append(line(js, NEAR, sw))
            rim.append(js)
    rim.append(spine)
    hb, ht = P("headbase"), P("headtop")
    hx, hy = (hb[0] * 0.35 + ht[0] * 0.65), (hb[1] * 0.35 + ht[1] * 0.65)
    r = h * 0.082
    nb = P("neck")
    body.append(line(["neck"], NEAR, sw))
    body.append(f'<path d="M{nb[0]:.1f},{nb[1]:.1f} L{hx:.1f},{hy:.1f}" stroke="{NEAR}" stroke-width="{sw:.1f}" stroke-linecap="round"/>')
    body.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r:.1f}" fill="{NEAR}"/>')
    if a["hat"] == "hardhat":
        body.append(f'<path d="M{hx - r * 1.08:.1f},{hy - r * 0.15:.1f} A{r * 1.08:.1f},{r:.1f} 0 0,1 {hx + r * 1.08:.1f},{hy - r * 0.15:.1f} '
                    f'L{hx + sgn * r * 1.45:.1f},{hy - r * 0.02:.1f} L{hx - sgn * r * 1.1:.1f},{hy - r * 0.02:.1f} Z" fill="#F2B233"/>')
    elif a["hat"] == "cap":
        body.append(f'<path d="M{hx - r:.1f},{hy - r * 0.1:.1f} A{r:.1f},{r:.1f} 0 0,1 {hx + r:.1f},{hy - r * 0.1:.1f} '
                    f'L{hx + sgn * r * 1.7:.1f},{hy:.1f} L{hx - sgn * r:.1f},{hy:.1f} Z" fill="#2E7DD1"/>')
    elif a["hat"] == "scarf":
        n = P("neck")
        body.append(f'<path d="M{n[0] - r * 0.6:.1f},{n[1] + r * 0.1:.1f} L{n[0] + r * 0.6:.1f},{n[1] + r * 0.1:.1f} '
                    f'L{n[0] - sgn * r * 0.9:.1f},{n[1] + r * 1.7:.1f} L{n[0] - sgn * r * 1.4:.1f},{n[1] + r * 1.5:.1f} Z" fill="#D9452B"/>')
    out = ""
    if night > 0:      # cool rim light so black figures read against the dark
        out += f'<g opacity="{0.5 * night:.2f}">' + "".join(line(js, "#7088AA", sw + 5) for js in rim) + \
               f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r + 2.5:.1f}" fill="#7088AA"/></g>'
    return out + "".join(body)


def frame(i):
    t = i / FPS
    night = st.ease((t - SWITCH) / 0.25)
    sec = 15 + int(t * (5 / SWITCH)) if t < SWITCH else 20 + int(t - SWITCH)
    body = st.landscape(night, t)
    for a in sorted(ACTORS, key=lambda a: a["h"]):
        body += stick(a, i, night)
    body += st.foreground(night, t)
    body += st.text(1810, 100, f"T+ 00:08:{min(sec, 59):02d}", 40, "#FFB547", "end", 600, "IBM Plex Mono")
    cap = st.ease((t - SWITCH - 1.6) / 0.5)
    if cap > 0:
        body += st.text(110, 170, "The last sunlight", 84, "#F2EEE4", op=cap)
        body += st.text(110, 262, "just arrived.", 84, "#F2EEE4", op=cap)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{st.W}" height="{st.H}">{body}</svg>'
    import io
    png = st.resvg_py.svg_to_bytes(svg_string=svg, font_files=st.FONT_FILES, skip_system_fonts=True)
    return st.Image.open(io.BytesIO(bytes(png))).convert("RGB")


if __name__ == "__main__":
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    if which == "test":
        for t in (2.0, 7.5):
            frame(int(t * FPS)).save(OUT / f"t{t}.png")
    else:
        for i in range(N):
            frame(i).save(OUT / "anim" / f"{i:04d}.png")
    print("ok")
