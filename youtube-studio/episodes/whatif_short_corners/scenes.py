"""Short: super speed needs super grip (vertical motion comic, art from whatif_super_speed).

Times are seconds of the aligned narration (projects/whatif_short_corners/audio/narration_words.json).
Numbers on screen: script.md calc — max push = mu*m*g, mu ~ 0.8 on dry concrete ("a bit less than your body
weight"); drag = push at ~46 m/s = 166 km/h ~ 103 mph ("around 105 mph", ~170 km/h); tightest turn at highway speed
(130 km/h ~ 80 mph): r = v^2/(mu g) = 166 m, diameter ~ 332 m ~ 1,100 ft; street corner r ~ 10 m (~ 30 ft) at
343 m/s: a = v^2/r ~ 1,200 g -> grip ~ 1,200 x body weight. The maps are diagrams, not to scale.
"""

from __future__ import annotations

import math

from studio.whatif import fx, overlay
from studio.whatif.shorts import (
    GROUND,
    HERO,
    W,
    amber,
    cam_on,
    chalk,
    full_video,
    hud,
    new,
    title,
    vboard,
)

AMB = overlay.AMBER


def arrow(x0, y0, x1, y1, p, color=overlay.CHALK, width=9):
    """A straight solid arrow (grows with p) for force diagrams."""
    if p <= 0:
        return ""
    p = min(1.0, p)
    x, y = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
    a = math.atan2(y1 - y0, x1 - x0)
    h1 = (x - 34 * math.cos(a - 0.5), y - 34 * math.sin(a - 0.5))
    h2 = (x - 34 * math.cos(a + 0.5), y - 34 * math.sin(a + 0.5))
    return (f'<path d="M{x0:.0f},{y0:.0f} L{x:.0f},{y:.0f} M{h1[0]:.0f},{h1[1]:.0f} L{x:.0f},{y:.0f} '
            f'L{h2[0]:.0f},{h2[1]:.0f}" stroke="{color}" stroke-width="{width}" fill="none" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def poly(pts, p, color=AMB, width=12, dash=""):
    """A polyline drawn progressively (p 0 -> 1) in a solid colour."""
    if p <= 0:
        return ""
    total = sum(math.dist(a, b) for a, b in zip(pts, pts[1:], strict=False)) or 1.0
    left, out = min(1.0, p) * total, [pts[0]]
    for a, b in zip(pts, pts[1:], strict=False):
        d = math.dist(a, b)
        if left <= 0:
            break
        k = min(1.0, left / d)
        out.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
        left -= d
    path = "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in out)
    return (f'<path d="{path}" stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round" '
            f'stroke-linejoin="round" {dash}/>')


def streets(u, ox=0):
    """A street corner seen from above: a road coming from the left, turning up."""
    return overlay.sketch_paths([[(60 + ox, 940), (640 + ox, 940), (640 + ox, 250)],
                                 [(60 + ox, 860), (560 + ox, 860), (560 + ox, 250)]], u / 0.9, 6, seed=101)


def turn_board(u):
    ox = -200
    out = amber(70, 220, "CORNERS", 64, u, 0.0)
    out += streets(u, ox)
    out += poly([(70, 900), (600 + ox, 900), (1060, 900)], (u - 0.9) / 0.9)            # overshoots the corner
    if u > 1.8:
        out += overlay.chalk_text(1010, 860, "✗", 80, (u - 1.8) / 0.2, 800, "Inter Display", "end")
    cx = 600 + ox
    circ = [(cx + 300 * math.sin(a), 600 + 300 * math.cos(a)) for a in [k * math.pi / 40 for k in range(81)]]
    out += overlay.chalk_line(circ, (u - 1.9) / 2.2, 7, seed=102, rough=False)
    out += overlay.chalk_line([(cx - 300, 600), (cx + 300, 600)], (u - 4.5) / 0.4, 5, seed=103, rough=False)
    out += chalk(cx + 330, 590, "≈ 1,100 ft", 64, u, 4.9, 0.4, bold=True)
    out += amber(cx + 330, 650, "≈ 330 m", 44, u, 5.2)
    out += chalk(70, 1030, "tightest turn at highway speed", 44, u, 1.6)
    out += amber(70, 1090, "80 mph · 130 km/h, normal grip", 40, u, 3.3, weight=700)
    return out


def corner_board(u):
    ox = -250
    out = amber(70, 220, "A STREET CORNER", 56, u, 0.0)
    out += streets(u, ox)
    arc = ([(70, 900)] + [(560 + ox + 40 * math.sin(a), 860 + 40 * math.cos(a))
                          for a in [k * math.pi / 2 / 12 for k in range(13)]] + [(600 + ox, 260)])
    out += poly(arc, (u - 0.8) / 1.2)
    out += chalk(460, 320, "radius ≈ 30 ft (10 m)", 40, u, 1.4)
    out += chalk(460, 400, "at the speed of sound:", 40, u, 2.2)
    out += chalk(460, 560, "≈ 1,200 ×", 120, u, 4.9, 0.4, bold=True)
    out += amber(460, 640, "your body weight", 52, u, 5.5)
    out += chalk(460, 710, "of grip", 52, u, 6.0)
    return out


def build_seq():
    c = new((1, 6), "night_plate", fade_out=0.5)
    GR = GROUND["night_plate"]
    c.cast("hero", height=HERO)
    # 0-4.1: a problem nobody talks about: grip
    c.cam(0.0, *cam_on(1300, GR))
    c.key("hero", 0.0, "a5", 1300, GR)
    c.text(0.2, 3.3, title("SUPER SPEED HAS", "a problem nobody mentions", 170, 58))
    c.key("hero", 3.3, "a7", 1300, GR)
    c.text(3.4, 4.1, lambda u, _t: chalk(W / 2, 300, "GRIP.", 160, u, 0.0, 0.25, bold=True, anchor="middle"))
    c.sfx(3.4, "sfx_hit", 0.45)
    # 4.1-12.6: feet push back, friction pushes you forward; ~ body weight at most
    c.key("hero", 4.1, "a0", 700, GR)
    c.key("hero", 5.0, "a0", 1300, GR, tween="out")
    c.cam(4.1, *cam_on(1000, GR), "hold")
    c.cam(5.0, *cam_on(1300, GR), "out")
    c.speed_lines(4.1, 5.0)
    c.sfx(4.1, "sfx_dash", 0.4)
    c.freeze(5.0, 12.6, [
        lambda ctx, u: arrow(330, 1112, 70, 1112, (u - 0.1) / 0.4),
        lambda ctx, u: chalk(60, 1066, "feet push", 40, u, 0.2),
        lambda ctx, u: arrow(600, 1000, 900, 1000, (u - 1.9) / 0.4, AMB),
        lambda ctx, u: amber(990, 950, "friction → you", 40, u, 2.0, "end", 700),
        lambda ctx, u: chalk(70, 360, "good rubber · dry concrete:", 44, u, 3.9),
        lambda ctx, u: chalk(70, 450, "≈ 0.8 × body weight", 76, u, 5.5, 0.5, bold=True),
    ])
    c.sfx(5.0, "sfx_freeze", 0.4)
    # 12.6-16.9: ~105 mph: the air pushes back just as hard
    c.key("hero", 12.6, "a0", 1300, GR)
    c.key("hero", 14.5, "a0", 2250, GR, tween="lin")
    c.cam(12.6, *cam_on(1300, GR), "hold")
    c.cam(14.5, *cam_on(2250, GR), "lin")
    c.speed_lines(12.6, 21.6)
    c.sfx(12.7, "sfx_dash", 0.45)
    c.text(12.7, 21.6, hud([(12.7, 105, "≈ 170 km/h"), (16.9, 105, "… and no faster")]))
    c.freeze(14.5, 16.9, [
        lambda ctx, u: arrow(120, 470, 520, 470, (u - 0.1) / 0.4, AMB, 14),
        lambda ctx, u: amber(120, 540, "your push", 42, u, 0.2, weight=700),
        lambda ctx, u: arrow(960, 470, 560, 470, (u - 0.6) / 0.4, overlay.CHALK, 14),
        lambda ctx, u: chalk(960, 540, "AIR", 50, u, 0.7, bold=True, anchor="end"),
        lambda ctx, u: chalk(W / 2, 380, "= equal", 84, u, 1.5, 0.4, bold=True, anchor="middle"),
    ])
    c.sfx(14.5, "sfx_tick", 0.35)
    # 16.9-21.6: past that, shoes can't push harder: you'd just spin your feet
    c.key("hero", 16.9, "b2", 2250, GR)
    c.key("hero", 21.6, "b2", 2290, GR, tween="lin")
    c.sfx(17.0, "sfx_skid", 0.45)
    c.draw(16.9, 21.6, fx.sparks(2230, GR - 5, n=8, life=0.35, duration=4.6, seed=111, direction=200, cone=30))
    for k in range(5):
        c.draw(16.9 + k * 0.9, 21.6, fx.dust(2200 + 10 * k, GR, n=8, size=110, life=1.4, seed=112 + k))
    c.text(17.0, 21.6, lambda u, _t: chalk(70, 380, "normal shoes:", 44, u, 0.0)
           + chalk(70, 460, "no faster", 80, u, 1.0, 0.4, bold=True)
           + amber(1010, 460, "just spinning ↺", 44, u, 2.9, "end", 700))
    # 21.6-35.3: corners, on the chalkboard
    c.text(21.6, 27.77, vboard(turn_board))
    c.sfx(21.7, "sfx_chalk", 0.3)
    c.text(27.77, 35.27, vboard(corner_board))
    c.sfx(32.6, "sfx_hit", 0.35)
    # 35.3-end: super speed needs super grip
    c.cam(35.27, *cam_on(1300, GR), "hold")
    c.key("hero", 35.27, "a7", 1300, GR)
    c.text(35.4, 37.5, title("SUPER SPEED", "needs super grip", 150, 76))
    c.sfx(35.4, "sfx_alert", 0.35)
    c.text(37.6, c.end(), full_video(170))
    c.music(0.0, "music_main", 0.12)
    return c


def build(size):
    return [build_seq()]
