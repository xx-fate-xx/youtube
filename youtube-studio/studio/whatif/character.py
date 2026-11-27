"""Expressive characters: big round head with a 3/4 face (eyes, lids, mouth), blinking, optional clothes.

The face carries the emotion: the eye openness and the tilt of the upper lids (no eyebrows on a black head), plus a
white mouth stroke. Bodies are the same mocap stickmen as rig.stickman.
"""

from __future__ import annotations

import math

from .motion import Pose
from .rig import FAR, LIMBS, NEAR, _line, _mix, to_screen

# expression -> (eye openness 0..1, lid tilt deg (+ = down toward the nose: angry/focused), pupil drop, mouth)
FACES = {
    "neutral": (0.80, 0.0, 0.00, "line"),
    "unimpressed": (0.42, -4.0, 0.06, "flat"),
    "surprised": (1.00, -8.0, 0.00, "o"),
    "worried": (0.85, -18.0, 0.04, "wobble"),
    "determined": (0.60, 16.0, 0.00, "flat"),
    "smile": (0.70, -6.0, 0.00, "smile"),
    "wince": (0.00, 10.0, 0.00, "grit"),
}
WHITE = "#F6F3EC"
INK = "#0B0B0E"


def face(hx: float, hy: float, r: float, s: int, expr: str = "neutral", tilt: float = 0.0, blink: float = 0.0,
         look: float = 0.0, profile: bool = True) -> str:
    """Face on a black head facing s (+1 = right). profile: one big eye at the front of the head (side view, as on
    the model sheet); else a 3/4 face with two eyes. blink 0..1 closes the eyes; look moves the pupils."""
    op, lid, pdy, mouth = FACES.get(expr, FACES["neutral"])
    op *= 1 - blink
    out = []
    eyes = [(0.60, 0.27, 0.31)] if profile else [(0.08, 0.17, 0.24), (0.50, 0.20, 0.27)]
    for k, (ex, erx, ery) in enumerate(eyes):
        cx, cy = hx + s * ex * r, hy - 0.06 * r
        rx, ry = r * erx, r * ery
        if op <= 0.05:                                      # closed: a lash curve
            out.append(f'<path d="M{cx - rx:.1f},{cy:.1f} Q{cx:.1f},{cy + ry * 0.45:.1f} {cx + rx:.1f},{cy:.1f}" '
                       f'stroke="{WHITE}" stroke-width="{r * 0.07:.1f}" fill="none" stroke-linecap="round"/>')
            continue
        out.append(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{WHITE}"/>')
        px, py = cx + s * (0.35 + 0.3 * look) * rx, cy + (0.15 + pdy * 4) * ry
        out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rx * 0.48:.1f}" fill="{INK}"/>')
        edge = cy - ry + 2 * ry * (1 - op)                  # lower edge of the upper lid
        dy = math.tan(math.radians(lid) * (1 if k == len(eyes) - 1 else 0.8)) * rx * s
        out.append(f'<path d="M{cx - rx * 1.4:.1f},{cy - ry * 1.6:.1f} L{cx + rx * 1.4:.1f},{cy - ry * 1.6:.1f} '
                   f'L{cx + rx * 1.4:.1f},{edge + dy:.1f} L{cx - rx * 1.4:.1f},{edge - dy:.1f} Z" fill="{INK}"/>')
    mx, my, w = (hx + s * 0.50 * r, hy + 0.40 * r, r * 0.30) if profile else (hx + s * 0.34 * r, hy + 0.46 * r, r * 0.30)
    sw = r * 0.07
    paths = {
        "line": f"M{mx - w / 2:.1f},{my:.1f} L{mx + w / 2:.1f},{my:.1f}",
        "flat": f"M{mx - w * 0.35:.1f},{my:.1f} L{mx + w * 0.35:.1f},{my:.1f}",
        "smile": f"M{mx - w / 2:.1f},{my - w * 0.1:.1f} Q{mx:.1f},{my + w * 0.45:.1f} {mx + w / 2:.1f},{my - w * 0.1:.1f}",
        "wobble": (f"M{mx - w / 2:.1f},{my + w * 0.1:.1f} Q{mx - w / 4:.1f},{my - w * 0.15:.1f} {mx:.1f},"
                   f"{my + w * 0.05:.1f} T{mx + w / 2:.1f},{my - w * 0.05:.1f}"),
    }
    if mouth == "o":
        out.append(f'<ellipse cx="{mx:.1f}" cy="{my + r * 0.04:.1f}" rx="{w * 0.28:.1f}" ry="{w * 0.38:.1f}" '
                   f'fill="{WHITE}"/>')
    elif mouth == "grit":
        out.append(f'<rect x="{mx - w * 0.55:.1f}" y="{my - w * 0.2:.1f}" width="{w * 1.1:.1f}" height="{w * 0.42:.1f}" '
                   f'rx="{w * 0.1:.1f}" fill="{WHITE}"/><path d="M{mx - w * 0.55:.1f},{my:.1f} L{mx + w * 0.55:.1f},'
                   f'{my:.1f}" stroke="{INK}" stroke-width="{sw * 0.6:.1f}"/>')
    else:
        out.append(f'<path d="{paths[mouth]}" stroke="{WHITE}" stroke-width="{sw:.1f}" fill="none" '
                   f'stroke-linecap="round"/>')
    body = "".join(out)
    return f'<g transform="rotate({tilt:.1f} {hx:.1f} {hy:.1f})">{body}</g>' if abs(tilt) > 0.5 else body


def big_head(P: dict, h: float, scale: float) -> tuple[float, float, float, float]:
    """Centre, radius and tilt (deg) of an enlarged head sitting on the neck, along the neck -> head direction."""
    hb, ht = P["headbase"], P["headtop"]
    dx, dy = ht[0] - hb[0], ht[1] - hb[1]
    n = math.hypot(dx, dy) or 1.0
    r = h * 0.082 * scale
    return hb[0] + dx / n * r * 0.92, hb[1] + dy / n * r * 0.92, r, math.degrees(math.atan2(dx, -dy))


def outfit(style: str, P: dict, s: int, sw: float) -> str:
    """Clothes over the torso, under the near arm: labcoat, vest, tee."""
    (nx, ny), (hx, hy) = P["neck"], P["hipC"]
    ux, uy = hx - nx, hy - ny
    L = math.hypot(ux, uy) or 1.0
    qx, qy = -uy / L, ux / L                               # perpendicular to the spine

    def pt(t: float, side: float) -> tuple[float, float]:
        return nx + ux * t + qx * side, ny + uy * t + qy * side

    def quad(t0: float, w0: float, t1: float, w1: float, fill: str, stroke: str = INK, sk: float = 0.15) -> str:
        a, b, c, d = pt(t0, -w0), pt(t0, w0), pt(t1, w1), pt(t1, -w1)
        return (f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} L{c[0]:.1f},{c[1]:.1f} L{d[0]:.1f},{d[1]:.1f} Z" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw * sk:.1f}" stroke-linejoin="round"/>')
    if style == "vest":
        out = quad(0.0, sw * 1.15, 0.92, sw * 1.25, "#2F8F83")
        for q in (0.3, 0.55, 0.8):
            a, b = pt(q, -sw * 1.15), pt(q, sw * 1.15)
            out += f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f}" stroke="#1F6B62" stroke-width="{sw * 0.16:.1f}"/>'
        return out
    if style == "backpack":
        (x0, y0), (x1, y1) = P["hipC"], P["neck"]
        ang = math.degrees(math.atan2(x1 - x0, y0 - y1))
        bw, bh = sw * 2.2, sw * 3.8
        bx, by = x0 * 0.45 + x1 * 0.55 - s * (sw * 0.5 + bw * 0.42), y0 * 0.45 + y1 * 0.55
        return (f'<g transform="rotate({ang:.1f} {bx:.1f} {by:.1f})"><rect x="{bx - bw / 2:.1f}" y="{by - bh / 2:.1f}" '
                f'width="{bw:.1f}" height="{bh:.1f}" rx="{bw * 0.32:.1f}" fill="#3F6E8C"/>'
                f'<rect x="{bx - bw * 0.32:.1f}" y="{by + bh * 0.08:.1f}" width="{bw * 0.64:.1f}" height="{bh * 0.28:.1f}" '
                f'rx="{bw * 0.12:.1f}" fill="#000" opacity="0.15"/></g>')
    if style == "tee":
        return quad(0.0, sw * 1.05, 0.78, sw * 1.05, "#FFB547", stroke="#FFB547", sk=0.0)
    return ""


COAT, COAT_SHADE, COAT_LINE = "#F1EFE9", "#C9C5BB", "#0B0B0E"


def _pl(pts, fill: str, sw: float, k: float = 0.2) -> str:
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    return f'<path d="{d}" fill="{fill}" stroke="{COAT_LINE}" stroke-width="{sw * k:.1f}" stroke-linejoin="round"/>'


OL = 0.2                                                     # outline width (x limb stroke)
# proportions taken from the model sheets in projects/_assets/character_ref (side view, x body height h)
TORSO_HALF = 0.10             # half width of the coat body
HAND_R = 0.036                # round black "mitten" hands
SLEEVE_W = 1.4                # sleeve thickness (x limb stroke)


def _axis(P: dict):
    (nx, ny), (hx, hy) = P["neck"], P["hipC"]
    L = math.hypot(hx - nx, hy - ny) or 1.0
    return (nx, ny), (hx, hy), ((hx - nx) / L, (hy - ny) / L), L


def coat_top(P: dict, h: float) -> tuple[float, float]:
    """Centre of the rounded top of the coat (the head sits right on it, no visible neck)."""
    (nx, ny), _h, (ax, ay), _L = _axis(P)
    wh = h * TORSO_HALF
    return nx + ax * wh * 0.55, ny + ay * wh * 0.55


def shoulder(P: dict, s: int, sw: float, side: str = "", h: float = 0.0) -> tuple[float, float]:
    """Where a sleeve starts: a top corner of the coat. It rolls with the arm (forward on the forward swing, back
    on the back swing), so a sleeve never comes out of the middle of the body."""
    x, y = coat_top(P, h)
    _n, _hh, (ax, ay), _L = _axis(P)
    wh = h * TORSO_HALF
    x, y = x + ax * wh * 0.35, y + ay * wh * 0.35
    if side:
        ex, ey = P["elb" + side]
        L = math.hypot(ex - x, ey - y) or 1.0
        k = 0.75 if side == "R" else 0.55
        x += (ex - x) / L * wh * k
        y += (ey - y) / L * wh * 0.3
    return x, y


def coat(P: dict, s: int, sw: float, h: float, speed: float = 0.0, t: float = 0.0) -> str:
    """Lab coat as on the model sheet (projects/_assets/character_ref): a wide body with rounded shoulders right
    under the head, nearly straight sides, a level hem above the knees, a folded lapel at the front of the neck and a
    breast pocket with the orange pen. Walking: the hem opens just enough for the forward knee. Running: the back
    of the coat streams out behind like a flag (wavy, fluttering)."""
    (nx, ny), (hx, hy), (ax, ay), L = _axis(P)
    wh = h * TORSO_HALF
    c0 = coat_top(P, h)
    kL, kR = P["kneeL"], P["kneeR"]
    kf, kb = (kL, kR) if s * kL[0] >= s * kR[0] else (kR, kL)
    hem_y = hy + ((kL[1] + kR[1]) / 2 - hy) * 0.85
    fx = max(s * (hx + wh * 1.05 * s), s * (kf[0] + sw * 0.9 * s)) * s          # front edge: hip width or knee
    bx = min(s * (hx - wh * 1.05 * s), s * (kb[0] - sw * 0.9 * s)) * s          # back edge
    if s * (fx - hx) > wh * 1.7:
        fx = hx + s * wh * 1.7
    if s * (hx - bx) > wh * 1.5:
        bx = hx - s * wh * 1.5
    hf, hb = (fx, hem_y), (bx, hem_y)
    wf, wb = (hx + s * wh, hy - wh * 0.4), (hx - s * wh, hy - wh * 0.4)
    tf, tb = (c0[0] + s * wh, c0[1] + wh * 0.35), (c0[0] - s * wh, c0[1] + wh * 0.35)
    top = c0[1] - wh * 0.55
    body = (f"M{tb[0]:.1f},{tb[1]:.1f} Q{tb[0]:.1f},{top:.1f} {c0[0]:.1f},{top:.1f} Q{tf[0]:.1f},{top:.1f} "
            f"{tf[0]:.1f},{tf[1]:.1f} L{wf[0]:.1f},{wf[1]:.1f} L{hf[0]:.1f},{hf[1]:.1f} ")
    if speed > 0.05:
        # the tail: a ribbon that leaves the back between the waist and the hem and streams straight back, tapering,
        # with a travelling wave (as on the model sheet's run cycle)
        k = min(1.0, speed)
        ln = h * 0.27 * k
        ph = t * 15
        r_top = (hx - s * wh, hy - wh * 0.35)
        r_bot = hb
        rcx, rcy = (r_top[0] + r_bot[0]) / 2, (r_top[1] + r_bot[1]) / 2
        th0 = r_bot[1] - r_top[1]
        tops, bots = [], []
        for j in range(1, 9):
            u = j / 8
            cx = rcx - s * ln * u
            cy = rcy - h * 0.05 * k * u + math.sin(ph - u * 4.2) * h * 0.035 * k * u
            th = th0 * (1 - 0.6 * u)
            tops.append((cx, cy - th / 2))
            bots.append((cx, cy + th / 2))
        pts = [r_bot] + bots + [(bots[-1][0] - s * th0 * 0.12, (bots[-1][1] + tops[-1][1]) / 2)] + tops[::-1] + [r_top]
        body += "L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    else:
        body += f"L{hb[0]:.1f},{hb[1]:.1f} L{wb[0]:.1f},{wb[1]:.1f} Z"
    ol = sw * OL
    out = f'<path d="{body}" fill="{COAT}" stroke="{COAT_LINE}" stroke-width="{2 * ol:.1f}" stroke-linejoin="round"/>'
    line = (f'stroke="{COAT_LINE}" stroke-width="{ol * 0.8:.1f}" fill="none" stroke-linecap="round" '
            f'stroke-linejoin="round"')
    # folded lapel at the front of the neck, then the front edge of the coat down to the hem
    l0 = (c0[0] + s * wh * 0.25, top + wh * 0.15)
    l1 = (c0[0] + s * wh * 0.95, c0[1] + wh * 0.55)
    l2 = (c0[0] + s * wh * 0.55, c0[1] + wh * 1.35)
    out += _pl([l0, l1, l2], COAT, sw, OL * 0.8)
    out += f'<path d="M{l2[0]:.1f},{l2[1]:.1f} L{hf[0] - s * wh * 0.3:.1f},{hf[1] - sw * 0.2:.1f}" {line}/>'
    # breast pocket with the orange pen
    kx, ky = c0[0] + s * wh * 0.45, c0[1] + wh * 1.25
    pw, ph_ = wh * 0.55, wh * 0.62
    out += (f'<path d="M{kx - pw / 2:.1f},{ky:.1f} L{kx - pw / 2:.1f},{ky + ph_ * 0.8:.1f} Q{kx - pw / 2:.1f},'
            f'{ky + ph_:.1f} {kx:.1f},{ky + ph_:.1f} Q{kx + pw / 2:.1f},{ky + ph_:.1f} {kx + pw / 2:.1f},'
            f'{ky + ph_ * 0.8:.1f} L{kx + pw / 2:.1f},{ky:.1f}" {line}/>'
            f'<path d="M{kx:.1f},{ky - ph_ * 0.6:.1f} L{kx:.1f},{ky + ph_ * 0.35:.1f}" stroke="#E8892B" '
            f'stroke-width="{sw * 0.32:.1f}" stroke-linecap="round"/>')
    return out


def sleeve(P: dict, side: str, sw: float, fill: str, s: int = 1, h: float = 0.0) -> str:
    """Thick white sleeve from the top corner of the coat down to the wrist (outlined), and a round black hand."""
    sh, el, wr = shoulder(P, s, sw, side, h), P["elb" + side], P["wrist" + side]
    d = f"M{sh[0]:.1f},{sh[1]:.1f} L{el[0]:.1f},{el[1]:.1f} L{wr[0]:.1f},{wr[1]:.1f}"
    w = sw * SLEEVE_W
    return (f'<path d="{d}" stroke="{COAT_LINE}" stroke-width="{w + 2 * sw * OL:.1f}" stroke-linecap="round" '
            f'stroke-linejoin="round" fill="none"/>'
            f'<path d="{d}" stroke="{fill}" stroke-width="{w:.1f}" stroke-linecap="round" stroke-linejoin="round" '
            f'fill="none"/>'
            f'<circle cx="{wr[0]:.1f}" cy="{wr[1]:.1f}" r="{h * HAND_R:.1f}" fill="{NEAR}"/>')


def blink_amount(t: float, seed: int = 0) -> float:
    """0..1 eye closing: a quick blink about every 3.2 s (offset per character)."""
    ph = (t + seed * 1.37) % 3.2
    return max(0.0, 1 - abs(ph - 0.06) / 0.06) if ph < 0.12 else 0.0


def character(pose: Pose, x: float, ground: float, h: float, flip: bool = False, expr: str = "neutral",
              head_scale: float = 1.7, wear: str | None = None, t: float = 0.0, look: float = 0.0,
              night: float = 0.0, shadow: float = 0.22, seed: int = 0, near: str = NEAR, far: str = FAR,
              show_face: bool = True, opacity: float = 1.0, speed: float = 0.0) -> str:
    P = to_screen(pose, x, ground, h, flip)
    s = -1 if flip else 1
    sw = h * 0.05
    out = []
    if shadow > 0:
        out.append(f'<ellipse cx="{x:.1f}" cy="{ground + 2:.1f}" rx="{h * 0.2:.1f}" ry="{h * 0.03:.1f}" fill="#000" '
                   f'opacity="{shadow * (1 - night):.2f}"/>')
    far_c = _mix(far, "#1C2230", night)
    coat = wear == "labcoat"
    legs = [(side, js) for side, js in LIMBS if js[0] != "shC"]
    arms_ = [(side, js) for side, js in LIMBS if js[0] == "shC"]
    if coat and show_face:
        shoe = sw * 1.25
        out += [_line(P, js, far_c, shoe if js[0] == "heelL" else sw * 0.95) for side, js in legs if side == "L"]
        out.append(sleeve(P, "L", sw, "#DEDAD1", s, h))
        out += [_line(P, js, near, shoe if js[0] == "heelR" else sw) for side, js in legs if side == "R"]
        out.append(globals()["coat"](P, s, sw, h, speed, t))
        out.append(sleeve(P, "R", sw, COAT, s, h))
        hx, hy, r, tilt = big_head(P, h, head_scale)
        cx, cy = coat_top(P, h)
        _n, _hh, (ax, ay), _L = _axis(P)
        hx, hy = cx - ax * r * 0.92, cy - ay * r * 0.92          # head sits on the coat: no neck
        out.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r:.1f}" fill="{near}"/>')
    else:
        out += [_line(P, js, far_c, sw * 0.95) for side, js in legs + arms_ if side == "L"]
        out.append(_line(P, ["hipC", "chest", "neck"], near, sw * 1.15))
        out += [_line(P, js, near, sw) for side, js in legs if side == "R"]
        if wear and wear != "labcoat":
            out.append(outfit(wear, P, s, sw))
        out += [_line(P, js, near, sw) for side, js in arms_ if side == "R"]
        hx, hy, r, tilt = big_head(P, h, head_scale)
        out.append(f'<path d="M{P["neck"][0]:.1f},{P["neck"][1]:.1f} L{hx:.1f},{hy:.1f}" stroke="{near}" '
                   f'stroke-width="{sw:.1f}" stroke-linecap="round"/>')
        out.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r:.1f}" fill="{near}"/>')
    if show_face:
        out.append(face(hx, hy, r, s, expr, tilt * 0.6, blink_amount(t, seed), look))
    body = "".join(out)
    return body if opacity >= 1 else f'<g opacity="{opacity:.2f}">{body}</g>'


def ghost(pose: Pose, x: float, ground: float, h: float, opacity: float, flip: bool = False,
          head_scale: float = 1.7) -> str:
    """Amber after-image left behind at speed (no face)."""
    return character(pose, x, ground, h, flip, head_scale=head_scale, near="#FFB547", far="#C98A2E", shadow=0,
                     show_face=False, opacity=opacity)
