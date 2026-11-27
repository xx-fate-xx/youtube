"""Stickman drawing (SVG fragments): body from a mocap pose, accessories, the hero's scarf, speed ghosts."""

from __future__ import annotations

import math

from .motion import Pose

NEAR, FAR = "#0B0B0E", "#2E3038"
AMBER = "#FFB547"
RIM = "#7088AA"
UPPER = ("chest", "neck", "headbase", "headtop", "elbL", "elbR", "wristL", "wristR")
LIMBS = [("L", ["hipC", "kneeL", "ankleL"]), ("L", ["heelL", "tipL"]), ("R", ["hipC", "kneeR", "ankleR"]),
         ("R", ["heelR", "tipR"]), ("L", ["shC", "elbL", "wristL"]), ("R", ["shC", "elbR", "wristR"])]
FOOT_FLAT = math.radians(20)   # ankle->ball angle of a flat foot in the CMU data (the ball, not the heel, is low)
SOLE = 0.026                   # half the limb stroke (body heights): a flat foot's drawn sole touches the floor


def _mix(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(p + (q - p) * t):02x}" for p, q in zip(a, b, strict=False))


def _smooth(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _foot(p: Pose, side: str) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Heel and toe-tip of a drawn foot. The capture gives ankle -> ball of the foot, which slopes down like a
    tiptoe; a planted foot is drawn flat on the floor (heel just behind the ankle, sole on the ground), a lifted
    foot keeps the captured tilt beyond the flat angle (toe-off, heel strike)."""
    ax, ay, az = p["ankle" + side]
    bx, by, _ = p["toe" + side]
    c = 1 - _smooth((ay - 0.045) / 0.035)                   # 1 = planted
    r = (math.atan2(ay - by, abs(bx - ax) + 1e-9) - FOOT_FLAT) * (1 - c)
    cr, sr = math.cos(r), math.sin(r)
    out = []
    for ox in (-0.03, 0.068):                                 # ankle sits ~1/4 of the foot from the heel
        sx, sy = ox * cr - 0.010 * sr, -ox * sr - 0.010 * cr  # rotated: toe down for r > 0
        fy = SOLE - ay
        x, y = sx * (1 - c) + ox * c, sy * (1 - c) + fy * c
        out.append((ax + x, max(ay + y, SOLE * 0.8), az))
    return out[0], out[1]


def styled(pose: Pose) -> Pose:
    """Stickman proportions: a slightly bigger upper body (feet untouched, so they stay planted), flat feet."""
    hip = ((pose["hipL"][0] + pose["hipR"][0]) / 2, (pose["hipL"][1] + pose["hipR"][1]) / 2 + 0.02, 0.0)
    p = dict(pose)
    p["hipC"] = hip
    for j in UPPER:
        x, y, z = p[j]
        p[j] = (hip[0] + (x - hip[0]) * 1.12, hip[1] + (y - hip[1]) * 1.12, z)
    sh, ch = p["neck"], p["chest"]
    p["shC"] = (sh[0] * 0.85 + ch[0] * 0.15, sh[1] * 0.85 + ch[1] * 0.15, 0.0)
    for side in "LR":
        p["heel" + side], p["tip" + side] = _foot(pose, side)
    return p


def to_screen(pose: Pose, x: float, ground: float, h: float, flip: bool):
    s = -1 if flip else 1
    p = styled(pose)
    return {j: (x + s * (v[0] - pose["pelvis"][0]) * h, ground - v[1] * h) for j, v in p.items()}


def _line(P, js, col, w) -> str:
    d = "M" + " L".join(f"{P[j][0]:.1f},{P[j][1]:.1f}" for j in js)
    return (f'<path d="{d}" stroke="{col}" stroke-width="{w:.1f}" stroke-linecap="round" stroke-linejoin="round" '
            f'fill="none"/>')


def head(P, h: float) -> tuple[float, float, float]:
    hb, ht = P["headbase"], P["headtop"]
    return hb[0] * 0.35 + ht[0] * 0.65, hb[1] * 0.35 + ht[1] * 0.65, h * 0.082


def stickman(pose: Pose, x: float, ground: float, h: float, flip: bool = False, hat: str | None = None,
             night: float = 0.0, near: str = NEAR, far: str = FAR, shadow: float = 0.22, opacity: float = 1.0) -> str:
    P = to_screen(pose, x, ground, h, flip)
    s = -1 if flip else 1
    sw = h * 0.05
    far_c = _mix(far, "#1C2230", night)
    out = []
    if shadow > 0:
        out.append(f'<ellipse cx="{x:.1f}" cy="{ground + 2:.1f}" rx="{h * 0.2:.1f}" ry="{h * 0.03:.1f}" fill="#000" '
                   f'opacity="{shadow * (1 - night):.2f}"/>')
    hx, hy, r = head(P, h)
    if night > 0:
        out.append(f'<g opacity="{0.5 * night:.2f}">' + "".join(_line(P, js, RIM, sw + 5) for _, js in LIMBS)
                   + _line(P, ["hipC", "chest", "neck"], RIM, sw * 1.15 + 5)
                   + f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r + 2.5:.1f}" fill="{RIM}"/></g>')
    out += [_line(P, js, far_c, sw * 0.95) for side, js in LIMBS if side == "L"]
    out.append(_line(P, ["hipC", "chest", "neck"], near, sw * 1.15))
    out += [_line(P, js, near, sw) for side, js in LIMBS if side == "R"]
    out.append(f'<path d="M{P["neck"][0]:.1f},{P["neck"][1]:.1f} L{hx:.1f},{hy:.1f}" stroke="{near}" '
               f'stroke-width="{sw:.1f}" stroke-linecap="round"/>')
    out.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r:.1f}" fill="{near}"/>')
    if hat == "hardhat":
        out.append(f'<path d="M{hx - r * 1.08:.1f},{hy - r * 0.15:.1f} A{r * 1.08:.1f},{r:.1f} 0 0,1 {hx + r * 1.08:.1f},'
                   f'{hy - r * 0.15:.1f} L{hx + s * r * 1.45:.1f},{hy - r * 0.02:.1f} L{hx - s * r * 1.1:.1f},{hy - r * 0.02:.1f} Z" '
                   f'fill="#F2B233"/>')
    elif hat == "cap":
        out.append(f'<path d="M{hx - r:.1f},{hy - r * 0.1:.1f} A{r:.1f},{r:.1f} 0 0,1 {hx + r:.1f},{hy - r * 0.1:.1f} '
                   f'L{hx + s * r * 1.7:.1f},{hy:.1f} L{hx - s * r:.1f},{hy:.1f} Z" fill="#2E7DD1"/>')
    elif hat in ("backpack", "satchel"):
        # strapped to the back: follows the torso angle; drawn under the near arm
        (x0, y0), (x1, y1) = P["hipC"], P["neck"]
        ang = math.degrees(math.atan2(x1 - x0, y0 - y1))
        col = "#3F6E8C" if hat == "backpack" else "#8A5A36"
        bw, bh = (h * 0.11, h * 0.19) if hat == "backpack" else (h * 0.09, h * 0.08)
        bx, by = x0 * 0.45 + x1 * 0.55 - s * (sw * 0.5 + bw * 0.42), y0 * 0.45 + y1 * 0.55
        strap = (f'<path d="M{bx + s * bw * 0.2:.1f},{by - bh * 0.42:.1f} Q{x1 + s * sw * 0.9:.1f},{y1 + h * 0.01:.1f} '
                 f'{x1 * 0.55 + x0 * 0.45 + s * sw * 0.45:.1f},{y1 * 0.55 + y0 * 0.45 - h * 0.02:.1f}" stroke="{col}" '
                 f'stroke-width="{sw * 0.32:.1f}" fill="none" stroke-linecap="round"/>')
        bag = (f'<g transform="rotate({ang:.1f} {bx:.1f} {by:.1f})"><rect x="{bx - bw / 2:.1f}" y="{by - bh / 2:.1f}" '
               f'width="{bw:.1f}" height="{bh:.1f}" rx="{bw * 0.32:.1f}" fill="{col}"/>'
               f'<path d="M{bx - bw / 2:.1f},{by - bh * 0.12:.1f} L{bx + bw / 2:.1f},{by - bh * 0.12:.1f}" '
               f'stroke="#000" stroke-opacity="0.22" stroke-width="{sw * 0.22:.1f}"/>'
               f'<rect x="{bx - bw * 0.32:.1f}" y="{by + bh * 0.08:.1f}" width="{bw * 0.64:.1f}" height="{bh * 0.28:.1f}" '
               f'rx="{bw * 0.12:.1f}" fill="#000" opacity="0.15"/></g>') + strap
        if hat == "satchel":
            bx, by = P["hipC"][0] - s * h * 0.05, P["hipC"][1] - h * 0.01
            bag = (f'<path d="M{P["neck"][0]:.1f},{P["neck"][1]:.1f} L{bx:.1f},{by:.1f}" stroke="{col}" '
                   f'stroke-width="{sw * 0.35:.1f}"/><rect x="{bx - bw / 2:.1f}" y="{by - bh * 0.3:.1f}" width="{bw:.1f}" '
                   f'height="{bh:.1f}" rx="{bw * 0.15:.1f}" fill="{col}"/>')
        near_arm = [_line(P, js, near, sw) for side, js in LIMBS if side == "R"][-1]
        out.append(bag + near_arm)
    body = "".join(out)
    return body if opacity >= 1 else f'<g opacity="{opacity:.2f}">{body}</g>'


def scarf(pose: Pose, x: float, ground: float, h: float, speed: float, t: float, flip: bool = False) -> str:
    """The hero's amber scarf: hangs at rest, streams straight back at speed (speed 0..1)."""
    P = to_screen(pose, x, ground, h, flip)
    s = -1 if flip else 1
    nx, ny = P["neck"]
    ny += h * 0.01
    length = h * (0.30 + 0.37 * speed)
    a0 = math.radians(-72 + 68 * speed)
    pts = [(nx, ny)]
    for k in range(1, 7):
        u = k / 6
        a = a0 + math.sin(t * (5 + 22 * speed) - k * 1.1) * (0.08 + 0.13 * speed) * u
        pts.append((nx - s * math.cos(a) * length * u, ny - math.sin(a) * length * u))
    d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    w = h * 0.045
    return (f'<path d="M{nx - h * 0.03:.1f},{ny:.1f} L{nx + h * 0.03:.1f},{ny:.1f}" stroke="{AMBER}" '
            f'stroke-width="{w * 1.2:.1f}" stroke-linecap="round"/>'
            f'<path d="{d}" stroke="{AMBER}" stroke-width="{w:.1f}" stroke-linecap="round" stroke-linejoin="round" '
            f'fill="none"/>')


def ghost(pose: Pose, x: float, ground: float, h: float, opacity: float, flip: bool = False) -> str:
    """Amber after-image left behind at speed."""
    return stickman(pose, x, ground, h, flip, near=AMBER, far="#C98A2E", shadow=0, opacity=opacity)


# ---------------------------------------------------------------- hero marks (identity options)

def mark(style: str, pose: Pose, x: float, ground: float, h: float, speed: float, t: float, flip: bool = False,
         color: str = AMBER) -> tuple[str, str]:
    """Hero identity accessory -> (svg drawn behind the body, svg drawn over it)."""
    if style == "scarf":
        return scarf(pose, x, ground, h, speed, t, flip), ""
    P = to_screen(pose, x, ground, h, flip)
    s = -1 if flip else 1
    hx, hy, r = head(P, h)
    nx, ny = P["neck"]
    cx, cy = P["chest"]
    if style == "cape":
        length = h * (0.42 + 0.12 * speed)
        a = math.radians(-80 + 55 * speed)
        wave = math.sin(t * (4 + 16 * speed)) * 0.08
        tip = (nx - s * math.cos(a + wave) * length, ny - math.sin(a + wave) * length)
        tip2 = (nx - s * math.cos(a - 0.25 + wave) * length * 0.9, ny - math.sin(a - 0.25 + wave) * length * 0.9)
        d = (f"M{nx - s * h * 0.02:.1f},{ny - h * 0.01:.1f} L{nx + s * h * 0.03:.1f},{ny + h * 0.02:.1f} "
             f"Q{(nx + tip[0]) / 2:.1f},{(ny + tip[1]) / 2 + h * 0.06:.1f} {tip[0]:.1f},{tip[1]:.1f} "
             f"L{tip2[0]:.1f},{tip2[1]:.1f} Z")
        return f'<path d="{d}" fill="{color}"/>', ""
    if style == "goggles":
        band = (f'<path d="M{hx - s * r:.1f},{hy - r * 0.05:.1f} L{hx + s * r * 0.98:.1f},{hy - r * 0.05:.1f}" '
                f'stroke="{color}" stroke-width="{r * 0.32:.1f}" stroke-linecap="round"/>')
        lens = (f'<ellipse cx="{hx + s * r * 0.62:.1f}" cy="{hy - r * 0.05:.1f}" rx="{r * 0.42:.1f}" ry="{r * 0.30:.1f}" '
                f'fill="{color}" stroke="#2A1A05" stroke-width="{r * 0.08:.1f}"/>'
                f'<ellipse cx="{hx + s * r * 0.72:.1f}" cy="{hy - r * 0.12:.1f}" rx="{r * 0.12:.1f}" ry="{r * 0.07:.1f}" '
                f'fill="#FFF3D6"/>')
        return "", band + lens
    if style == "core":
        px, py = cx * 0.55 + nx * 0.45, cy * 0.55 + ny * 0.45
        pulse = 1 + 0.12 * math.sin(t * 6)
        rr = h * 0.026 * pulse
        glow = (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rr * 3.2:.1f}" fill="{color}" opacity="0.18"/>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rr * 1.9:.1f}" fill="{color}" opacity="0.35"/>')
        return "", glow + f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rr:.1f}" fill="#FFF1CC"/>'
    if style == "headband":
        by = hy - r * 0.25
        band = (f'<path d="M{hx - r * 0.98:.1f},{by:.1f} L{hx + r * 0.98:.1f},{by:.1f}" stroke="{color}" '
                f'stroke-width="{r * 0.34:.1f}" stroke-linecap="round"/>')
        kx = hx - s * r * 0.9
        tails = []
        for k, off in enumerate((0.0, 0.35)):
            a0 = math.radians(-60 + 58 * speed) - off * (1 - speed)
            pts = [(kx, by)]
            for j in range(1, 6):
                u = j / 5
                a = a0 + math.sin(t * (6 + 20 * speed) - j * 1.2 - k) * (0.1 + 0.12 * speed) * u
                pts.append((kx - s * math.cos(a) * h * 0.22 * u, by - math.sin(a) * h * 0.22 * u))
            d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            tails.append(f'<path d="{d}" stroke="{color}" stroke-width="{r * 0.26:.1f}" stroke-linecap="round" '
                         f'stroke-linejoin="round" fill="none"/>')
        return "".join(tails), band
    if style == "amber_head":
        return "", f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r:.1f}" fill="{color}"/>'
    if style == "question":
        # a "?"-shaped amber curl springing from the top of the head: the channel's question
        bx, by = hx - s * r * 0.15, hy - r * 0.92
        q = r * 0.62
        d = (f"M{bx:.1f},{by:.1f} C{bx:.1f},{by - q * 0.9:.1f} {bx + s * q * 0.15:.1f},{by - q * 1.2:.1f} "
             f"{bx + s * q * 0.7:.1f},{by - q * 1.6:.1f} C{bx + s * q * 1.5:.1f},{by - q * 2.1:.1f} "
             f"{bx + s * q * 2.2:.1f},{by - q * 2.9:.1f} {bx + s * q * 1.2:.1f},{by - q * 3.3:.1f} "
             f"C{bx + s * q * 0.4:.1f},{by - q * 3.6:.1f} {bx - s * q * 0.4:.1f},{by - q * 3.1:.1f} "
             f"{bx - s * q * 0.3:.1f},{by - q * 2.5:.1f}")
        sway = math.sin(t * 3) * 2
        return "", (f'<g transform="rotate({sway:.1f} {bx:.1f} {by:.1f})"><path d="{d}" stroke="{color}" '
                    f'stroke-width="{r * 0.30:.1f}" stroke-linecap="round" fill="none"/></g>')
    if style == "chalk_outline":
        body = stickman(pose, x, ground, h, flip, near="#F4F1E8", far="#F4F1E8", shadow=0)
        return f'<g filter="url(#outline)">{body}</g>', ""
    if style == "aura":
        body = stickman(pose, x, ground, h, flip, near=color, far=color, shadow=0)
        return f'<g filter="url(#aura)" opacity="{0.75 + 0.15 * math.sin(t * 5):.2f}">{body}</g>', ""
    return "", ""


# ---------------------------------------------------------------- arm overrides

# elbow / wrist offsets from the neck (body heights, +x forward, +y up) for poses the capture library lacks
ARMS = {
    "catch": ((0.10, 0.04), (0.20, 0.11)),      # both arms out and up, ready to catch someone from above
    "carry": ((0.09, -0.10), (0.19, -0.09)),    # forearms level in front of the hips: holding someone
    "reach": ((0.12, 0.09), (0.23, 0.20)),      # stretched forward-up, grabbing
    "brace": ((0.11, -0.03), (0.22, -0.02)),    # straight ahead at chest height: pushing
}


def arms(pose: Pose, style: str, w: float = 1.0) -> Pose:
    """Blend both arms toward a held pose (w 0..1); the far arm sits a touch behind the near one."""
    (ex, ey), (wx, wy) = ARMS[style]
    nx, ny, _ = pose["neck"]
    p = dict(pose)
    for side, off in (("R", 0.0), ("L", -0.018)):
        for joint, (dx, dy) in (("elb", (ex, ey)), ("wrist", (wx, wy))):
            x0, y0, z0 = pose[joint + side]
            p[joint + side] = (x0 + (nx + dx + off - x0) * w, y0 + (ny - 0.035 + dy - y0) * w, z0)
    return p
