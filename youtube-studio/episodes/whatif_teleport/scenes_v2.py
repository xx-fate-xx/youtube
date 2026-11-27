"""Motion-comic scenes for "What If You Could Teleport? (Your Speed Comes Too)" (16:9).

Shot numbers: frames.txt (56 shots, made by script_source.py from the approved script.md). Art: projects/whatif_teleport/
art = the pilot's library + new plates (beach, pole, jungle, sky, trench, room, moon, launch) + sprites t0 snap,
t1 slide, t2 launched up, t3 shiver, t4 tumble, snow0 (legs in a snowbank), car0. Numbers on screen: script.md
calc_notes / factcheck_report.md. Rule of the power (on screen): your speed comes with you (as seen from space).

Pilot sprites: hero0-7 (0 relaxed, 1 crouch, 2 sprint, 3 skid, 4 arms up, 5 impact, 6 horrified, 7 explaining),
a: 0 sprint, 1 dive, 2 carry, 3 carry bracing, 5 thinking, 6 shrug, 7 pointing up; c: 0 blink, 1 fast brain;
cleaner0-4 (0 standing, 1 slipping, 2 falling back, 3 head-first fall, 4 curled).
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from studio.whatif import fx, overlay
from studio.whatif.comic import Comic, board, counter, label, punch

W, H = 1920, 1080
SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455, "t": 2005}
CH, AMB = overlay.CHALK, overlay.AMBER
HERO = 400
GR = {"tower_plate": 1362, "highway_plate": 1400, "room_plate": 1430, "beach_plate": 1420, "pole_plate": 1360,
      "jungle_plate": 1430, "ocean_plate": 1250, "map_plate": 1400, "sky_plate": 1000, "trench_plate": 1470,
      "moon_plate": 1420, "launch_plate": 1440}
WIDE = (1344, 760, 2688)


def new(shots, plate, **kw) -> Comic:
    c = Comic(shots=shots, plate=plate, **kw)
    c.sheet_ref = dict(SHEET)
    return c


def scr(cam, x, y):
    cx, cy, vw = cam
    k = W / vw
    vh = vw * H / W
    x0 = min(max(cx - vw / 2, 0), 2688 - vw)
    y0 = min(max(cy - vh / 2, 0), 1520 - vh)
    return (x - x0) * k, (y - y0) * k


def ch(x, y, s, size, u, at=0.0, d=0.5, bold=False, anchor="start"):
    t = overlay.chalk_text(x, y, s, size, (u - at) / d, 800 if bold else 600, "Inter Display" if bold else "Inter",
                           anchor)
    return overlay.shadowed(t) if t else t


def am(x, y, s, size, u, at=0.0, anchor="start", weight=800):
    k = max(0.0, min(1.0, (u - at) / 0.2))
    return overlay.shadowed(overlay.text(x, y, s, size, AMB, anchor, weight, "Inter Display", op=k)) if k else ""


def big(x, y, s, size, u, at=0.0, anchor="start"):
    k = max(0.0, min(1.0, (u - at) / 0.2))
    return overlay.shadowed(overlay.text(x, y, s, size, anchor=anchor, op=k)) if k else ""


def vb(fn, dim=0.97):
    return board(fn, dim)


def ring(x, y, w=230, life=0.7, color=(255, 181, 71)):
    """A teleport ring (world px): an amber ellipse that snaps open, glows and closes."""
    def f(img: Image.Image, u: float, _t: float) -> None:
        if u > life:
            return
        k = u / life
        s = math.sin(math.pi * min(1.0, k * 1.2)) if k < 0.83 else max(0.0, 1 - (k - 0.83) / 0.17) * 0.5
        rx, ry = w * (0.3 + 0.7 * s), w * 0.22 * (0.3 + 0.7 * s)
        d = ImageDraw.Draw(img, "RGBA")
        for j, a in enumerate((60, 110, 255)):
            e = 18 - 7 * j
            d.ellipse([x - rx - e, y - ry - e, x + rx + e, y + ry + e], outline=(*color, int(a * s)), width=8 - 2 * j)
        r = random.Random(int(x + y))
        for _ in range(10):
            a = r.uniform(0, 2 * math.pi)
            rr = rx * r.uniform(0.9, 1.4)
            px, py = x + rr * math.cos(a), y + rr * 0.22 * math.sin(a) - 120 * k * r.uniform(0.3, 1)
            d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(255, 230, 170, int(220 * s)))
    return f


def tp(c: Comic, at, x, y, w=230, sound=True):
    """A teleport pop at world point (x, y) (the ring sits at the figure's middle)."""
    c.draw(at, c.end(), ring(x, y, w))
    if sound:
        c.sfx(at, "sfx_teleport", 0.5)


def spray(x0, x1, dur, y, seed=5, every=0.06, col=(240, 248, 255)):
    """Ice/water spray kicked up behind a body sliding x0 -> x1 over dur s (world px)."""
    def f(img, u, _t):
        d = ImageDraw.Draw(img, "RGBA")
        sgn = 1 if x1 >= x0 else -1
        for k in range(int(min(u, dur) / every) + 1):
            te = k * every
            age = u - te
            if age < 0 or age > 0.9:
                continue
            ex = x0 + (x1 - x0) * min(1.0, te / dur)
            r = random.Random(seed * 1000 + k)
            fade = 1 - age / 0.9
            for _j in range(6):
                vx, vy = -sgn * r.uniform(80, 320), -r.uniform(240, 560)
                px, py = ex + vx * age, y + vy * age + 1100 * age * age
                if py > y + 6:
                    continue
                rr = r.uniform(5, 12)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(*col, int(220 * fade)))
    return f


def submerge(x, sea, half=260, plate="ocean_plate"):
    def f(img, _u, _t):
        from studio.whatif import render
        from studio.whatif.comic import _plate
        pl = _plate(str(render.library("art")), plate)
        box = (int(x - half), int(sea) - 4, int(x + half), pl.height)
        img.alpha_composite(pl.crop(box), (box[0], box[1]))
    return f


def wall(x, ground, w=160, h=420):
    def f(img, _u, _t):
        d = ImageDraw.Draw(img, "RGBA")
        top = ground - h
        d.rectangle([x, top, x + w, ground], fill=(150, 146, 140, 255), outline=(22, 22, 24, 255), width=8)
        for j in range(1, 6):
            yy = top + h * j / 6
            d.line([(x + 6, yy), (x + w - 6, yy)], fill=(110, 106, 100, 255), width=4)
            off = 0 if j % 2 else w / 2
            d.line([(x + off, yy - h / 6), (x + off, yy)], fill=(110, 106, 100, 255), width=4)
    return f


# ---------------------------------------------------------------- chalk drawings (screen px)

def car_doodle(x, y, s, p, seed=31):
    body = [(0, 40), (10, 12), (60, 12), (80, 0), (140, 0), (165, 22), (200, 26), (205, 40), (0, 40)]
    wheels = "".join(f'<circle cx="{x + cx * s:.0f}" cy="{y + 42 * s:.0f}" r="{13 * s:.0f}" fill="none" '
                     f'stroke="{CH}" stroke-width="5" opacity="{min(1.0, max(0.0, p * 2 - 1)):.2f}"/>' for cx in (45, 160))
    return overlay.sketch_paths([[(x + a * s, y + b * s) for a, b in body]], p, 5, seed) + wheels


def bike_doodle(x, y, s, p):
    wheels = "".join(f'<circle cx="{x + cx * s:.0f}" cy="{y:.0f}" r="{34 * s:.0f}" fill="none" stroke="{CH}" '
                     f'stroke-width="5" opacity="{min(1.0, max(0.0, p * 2 - 0.5)):.2f}"/>' for cx in (0, 120))
    frame = [[(x, y), (x + 50 * s, y - 50 * s), (x + 120 * s, y)], [(x + 50 * s, y - 50 * s), (x + 95 * s, y - 50 * s),
             (x + 120 * s, y)], [(x + 95 * s, y - 50 * s), (x + 100 * s, y - 75 * s)]]
    return overlay.sketch_paths(frame, p, 5, 41) + wheels


def globe_top(u, cx=960, cy=560, r=300, spin=0.0, arrows=True, label_pole=True, extra=""):
    """Earth seen from above the North Pole (chalk): spinning blobs, the pole in the middle, speed arrows on the rim."""
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#1D4E7E" opacity="0.9"/>',
           f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CH}" stroke-width="7"/>']
    blobs = [(0.2, 0.55, 0.32), (1.5, 0.7, 0.26), (2.6, 0.45, 0.22), (3.7, 0.62, 0.3), (5.0, 0.5, 0.24)]
    for a, rr, s in blobs:
        bx, by = cx + r * rr * math.cos(a + spin), cy + r * rr * math.sin(a + spin)
        out.append(f'<ellipse cx="{bx:.0f}" cy="{by:.0f}" rx="{r * s * 0.6:.0f}" ry="{r * s * 0.38:.0f}" '
                   f'transform="rotate({math.degrees(a + spin):.0f} {bx:.0f} {by:.0f})" fill="#5E8C4A" opacity="0.85"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="{CH}"/>')
    if label_pole:
        out.append(ch(cx + 18, cy - 14, "North Pole", 34, u, 0.3))
    if arrows:
        for k in range(8):
            a = k * math.pi / 4 + spin
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            tx, ty = -math.sin(a), math.cos(a)                           # counter-clockwise from above
            out.append(overlay.chalk_arrow(px, py, px + 110 * tx, py + 110 * ty, (u - 0.4 - 0.05 * k) / 0.3,
                                           seed=200 + k))
    return "".join(out) + extra


def globe_side(u, cx=960, cy=560, r=300, phase=0.0, axis=True):
    """Earth from the side: equator line, spin axis, meridians sliding round."""
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#1D4E7E" opacity="0.9"/>',
           f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CH}" stroke-width="7"/>',
           overlay.chalk_line([(cx - r, cy), (cx + r, cy)], u / 0.4, 5, seed=301, rough=False)]
    for k in range(6):
        a = (phase + k * math.pi / 6) % math.pi
        rx = abs(r * math.cos(a))
        out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.0f}" ry="{r}" fill="none" stroke="{CH}" stroke-width="3" '
                   f'opacity="0.45"/>')
    if axis:
        out.append(f'<line x1="{cx}" y1="{cy - r - 70}" x2="{cx}" y2="{cy + r + 70}" stroke="{CH}" stroke-width="5" '
                   f'stroke-dasharray="14 10"/>')
    return "".join(out)


def flash_card(text, sub=""):
    def f(u, _t):
        k = min(1.0, u / 0.12)
        z = 1 + 0.05 * u                                     # creeping push: never a still picture
        return (f'<rect width="{W}" height="{H}" fill="#050507"/>'
                f'<g transform="translate({W / 2},{H / 2}) scale({z:.4f}) translate({-W / 2},{-H / 2})">'
                + overlay.text(W / 2, 560, text, 150, anchor="middle", op=k)
                + (overlay.text(W / 2, 660, sub, 48, AMB, "middle", 600, "Inter", op=k) if sub else "") + "</g>")
    return f


# ================================================================ 1-10: tower — cold open and timing

def tower_seq():
    c = new((1, 10), "tower_plate")
    G = GR["tower_plate"]
    c.cast("hero", height=HERO)
    c.cast("cleaner", height=397, ref="cleaner0")
    at = c.at
    FX = 2050                                                     # the cleaner's fall line under the cradle
    # 1: you can teleport (three pops), then a glance up at the tower
    c.cam(0.0, 1100, 1000, 1700)
    c.key("hero", 0.0, "t0", 700, G)
    c.text(at(1, 0.2), at(1, 3.4), punch(1240, 300, "WHAT IF", "you could teleport?", 84))
    c.sfx(at(1, 0.2), "sfx_hit", 0.4)
    for k, (t, x0, x1) in enumerate([(1.2, 700, 1300), (2.2, 1300, 900), (3.1, 900, 1500)]):
        tp(c, at(1, t), x0, G - 200, sound=(k != 1))
        c.draw(at(1, t + 0.05), c.end(), ring(x1, G - 200))
        c.key("hero", at(1, t), "t0" if k != 1 else "hero7", x1, G)
    c.cam(at(1, 4.0), *WIDE, "ease")
    c.text(at(1, 4.4), at(2, 0.0), lambda u, _t: am(110, 220, "the first person you try to save…", 56, u, 0.0))
    # 2: a window cleaner slips; you blink them down. Safe.
    c.key("cleaner", at(1, 4.0), "cleaner0", FX + 90, 360, scale=0.5, fixed=True)
    c.key("cleaner", at(2, 0.4), "cleaner1", FX + 90, 360, scale=0.5, fixed=True)
    c.sfx(at(2, 0.4), "sfx_slip", 0.45)
    c.key("cleaner", at(2, 1.0), "cleaner3", FX, 420, scale=0.55, fixed=True)
    c.key("cleaner", at(2, 3.1), "cleaner3", FX, 820, scale=0.6, fixed=True, tween="in")
    c.sfx(at(2, 1.0), "sfx_fall", 0.4)
    c.key("hero", at(2, 0.0), "t0", 1500, G)
    tp(c, at(2, 3.1), FX, 700, 200)
    c.draw(at(2, 3.15), c.end(), ring(FX - 250, G - 160, 200))
    c.key("cleaner", at(2, 3.15), "cleaner3", FX - 250, G - 40, scale=0.62, fixed=True)
    c.cam(at(2, 3.15), 1500, 1000, 1500, "snap")
    c.freeze(at(2, 5.6), at(3, 0.3), [lambda ctx, u: big(110, 260, "SAFE?", 110, u, 0.0)])
    c.sfx(at(2, 5.6), "sfx_freeze", 0.35)
    # 3: except they arrive still falling — at highway speed
    c.key("cleaner", at(3, 0.5), "cleaner3", FX - 250, G + 10, scale=0.62, fixed=True, tween="in")
    c.key("cleaner", at(3, 0.55), "cleaner4", FX - 250, G, scale=0.55, fixed=True)
    c.shake(at(3, 0.55), 0.5, 26)
    c.sfx(at(3, 0.5), "sfx_crash", 0.5)
    c.draw(at(3, 0.55), at(4, 0.0), fx.dust(FX - 250, G, size=170, seed=12))
    c.draw(at(3, 0.55), at(4, 0.0), fx.cracks(FX - 250, G + 4, 260, seed=11), front=False)
    c.key("hero", at(3, 0.55), "hero6", 1350, G)
    c.text(at(3, 1.4), at(4, 0.0), lambda u, _t: ch(110, 230, "still falling at", 48, u, 0.0)
           + car_doodle(110, 270, 1.4, (u - 0.4) / 0.6) + am(110, 400, "highway speed", 46, u, 1.6))
    # 4: the rule
    c.hide("cleaner", at(4, 0.0))
    c.cam(at(4, 0.0), 1150, 1000, 1500, "ease")
    c.key("hero", at(4, 0.0), "a7", 1000, G)
    c.text(at(4, 0.3), c.at(5, 0.0), label(110, 170, "THE ONE RULE", "your speed comes with you", 76))
    c.sfx(at(4, 0.3), "sfx_hit", 0.4)
    c.text(at(4, 2.0), at(5, 0.0), lambda u, _t: ch(1180, 420, "change WHERE  ✓", 58, u, 0.0, 0.4, bold=True)
           + am(1180, 520, "change HOW FAST  ✗", 58, u, 1.6))
    # 5: chalkboard teaser — what that one rule does

    def teaser(u):
        out = ch(160, 240, "one rule turns…", 54, u, 0.1)
        # a trip to the North Pole -> a car crash
        out += ch(160, 380, "a trip to the North Pole", 46, u, 0.7) + am(160, 440, "→ a car crash", 46, u, 1.6)
        out += car_doodle(1160, 360, 1.5, (u - 1.0) / 0.6, 51)
        # a vacation -> a cannon launch
        out += ch(160, 560, "a vacation", 46, u, 2.6) + am(160, 620, "→ a cannon launch", 46, u, 3.4)
        out += overlay.chalk_arrow(1270, 690, 1270, 500, (u - 3.2) / 0.4, seed=52)
        # the whole spinning planet -> a trap
        out += ch(160, 740, "the whole spinning planet", 46, u, 4.5) + am(160, 800, "→ a trap", 46, u, 5.6)
        if u > 4.7:
            out += globe_top(u - 4.7, 1290, 860, 120, spin=0.8 * (u - 4.7), arrows=False, label_pole=False)
        return out
    c.text(at(5, 0.0), at(6, 0.0), vb(teaser))
    c.sfx(at(5, 0.1), "sfx_chalk", 0.3)
    # 6: one secret route — stay for it
    c.key("hero", at(6, 0.0), "t0", 1000, G)
    c.text(at(6, 0.3), at(7, 0.0), punch(1280, 300, "ONE SECRET ROUTE", "stay for that one", 80))
    c.sfx(at(6, 0.3), "sfx_hit", 0.3)
    # 7: rewind; the trick is timing: teleport in the first half-second -> a stumble
    c.rewind(at(7, 0.0), at(7, 0.8))
    c.sfx(at(7, 0.0), "sfx_rewind", 0.4)
    c.cam(at(7, 0.0), *WIDE, "hold")
    c.key("hero", at(7, 0.0), "t0", 1500, G)
    c.key("cleaner", at(7, 0.0), "cleaner1", FX + 90, 360, scale=0.5, fixed=True)
    c.text(at(7, 1.0), at(7, 3.6), label(110, 170, "THE TRICK", "timing", 84))
    c.key("cleaner", at(7, 3.6), "cleaner3", FX, 420, scale=0.55, fixed=True)
    c.key("cleaner", at(7, 4.1), "cleaner3", FX, 440, scale=0.55, fixed=True, tween="in")
    tp(c, at(7, 4.1), FX, 470, 200)
    c.draw(at(7, 4.15), c.end(), ring(FX - 250, G - 160, 200))
    c.cam(at(7, 4.15), 1650, 1000, 1500, "snap")
    c.key("cleaner", at(7, 4.15), "cleaner1", FX - 250, G - 20, scale=0.98, fixed=True)
    c.key("cleaner", at(7, 4.5), "cleaner0", FX - 250, G, scale=0.98, fixed=True, tween="in")
    c.draw(at(7, 4.5), at(8, 0.0), fx.dust(FX - 250, G, size=90, seed=13))
    c.text(at(7, 4.6), at(8, 0.0), lambda u, _t: ch(110, 250, "after ½ second:", 52, u, 0.0)
           + am(110, 330, "a stumble ✓", 66, u, 0.6))
    # 8: one second: a bike rolling downhill (fall-speed counter)
    c.hide("cleaner", at(8, 0.0))
    c.cam(at(8, 0.0), *WIDE, "hold")
    c.key("cleaner", at(8, 0.0), "cleaner3", FX, 420, scale=0.55, fixed=True)
    c.key("cleaner", at(8, 1.0), "cleaner3", FX, 470, scale=0.55, fixed=True, tween="in")
    c.text(at(8, 0.0), at(10, 0.0), counter(110, 120, "FALL SPEED", lambda u: (
        f"{min(82.0, 22.0 * u):.0f} mph" if u < 1.0 else ("22 mph" if u < 4.8 else f"{min(82, 22 + (u - 4.8) * 40):.0f} mph")),
        "after 1 second"))
    c.freeze(at(8, 1.0), at(9, 0.0), [lambda ctx, u: bike_doodle(150, 500, 1.4, u / 0.8)
                                     + ch(130, 600, "a bike rolling downhill", 50, u, 0.6)])
    c.sfx(at(8, 1.0), "sfx_freeze", 0.35)
    # 9: wait until the end: over 80 mph; teleporting only picks where they crash
    c.key("cleaner", at(9, 0.0), "cleaner3", FX, 470, scale=0.55, fixed=True)
    c.key("hero", at(9, 0.0), None)
    c.key("cleaner", at(9, 1.4), "cleaner3", FX, G - 60, scale=0.62, fixed=True, tween="in")
    c.cam(at(9, 1.4), 1700, 1050, 1500, "ease")
    c.freeze(at(9, 1.5), at(10, 0.0), [
        lambda ctx, u: ch(110, 420, "over 80 mph", 72, u, 0.0, 0.4, bold=True),
        lambda ctx, u: ch(110, 600, "teleporting only picks", 48, u, 2.4),
        lambda ctx, u: ch(110, 670, "WHERE they crash", 60, u, 3.4, 0.4, bold=True),
    ])
    c.sfx(at(9, 1.5), "sfx_freeze", 0.35)
    # 10: back up to the roof? they arrive diving into the floor up there
    c.hide("cleaner", at(10, 0.0))
    c.cam(at(10, 0.0), 2100, 450, 1300, "ease")
    c.text(at(10, 0.2), at(10, 2.6), punch(820, 230, "BACK UP", "to the top?", 80))
    tp(c, at(10, 2.8), 2160, 160, 180)
    c.key("cleaner", at(10, 2.85), "cleaner3", 2160, 200, scale=0.5, fixed=True)
    c.key("cleaner", at(10, 3.3), "cleaner3", 2160, 340, scale=0.5, fixed=True, tween="in")
    c.key("cleaner", at(10, 3.35), "cleaner4", 2160, 350, scale=0.45, fixed=True)
    c.shake(at(10, 3.35), 0.5, 24)
    c.sfx(at(10, 3.3), "sfx_crash", 0.45)
    c.draw(at(10, 3.35), c.end(), fx.dust(2160, 350, size=110, seed=14))
    c.text(at(10, 4.8), c.end(), lambda u, _t: big(110, 300, "same crash,", 80, u, 0.0)
           + am(110, 400, "nicer view ✓", 80, u, 1.0))
    c.music(0.0, "music_main", 0.12)
    return c


# ================================================================ 11-13: the car gag (highway)

def car_seq():
    c = new((11, 13), "highway_plate")
    G = GR["highway_plate"]
    c.cast("hero", height=HERO)
    c.cast("car", height=230, ref="car0")
    at = c.at
    c.draw(0.0, c.end(), wall(2300, G), front=False)
    c.cam(0.0, 1500, 1000, 2000)
    c.key("car", 0.0, "car0", 700, G)
    c.key("car", at(11, 3.6), "car0", 1900, G, ang=-6, tween="lin", smear=True)
    c.speed_lines(0.0, at(11, 3.6))
    c.sfx(at(11, 0.2), "sfx_skid", 0.45)
    c.text(at(11, 0.2), at(11, 2.6), lambda u, _t: ch(110, 230, "your car skids", 60, u, 0.0, 0.4, bold=True)
           + ch(110, 310, "toward a wall…", 48, u, 0.6))
    tp(c, at(11, 3.2), 1750, G - 120, 170)
    c.draw(at(11, 3.25), c.end(), ring(1500, G - 200, 200))
    c.key("hero", at(11, 3.25), "t4", 1500, G - 40)
    c.key("hero", at(12, 1.6), "t4", 2200, G - 20, ang=540, tween="out")
    c.key("car", at(11, 4.4), "car0", 2150, G, ang=-8, tween="lin")
    c.shake(at(11, 4.4), 0.5, 22)
    c.sfx(at(11, 4.35), "sfx_crash", 0.45)
    c.draw(at(11, 4.4), at(12, 3.0), fx.debris(2290, G - 120, n=16, power=0.7, seed=21))
    c.draw(at(11, 3.3), at(12, 2.0), fx.dust(1800, G, size=140, seed=22))
    c.speed_lines(at(11, 3.3), at(12, 1.6))
    c.key("hero", at(12, 1.65), "hero5", 2200, G)
    c.text(at(12, 0.3), at(12, 3.4), lambda u, _t: ch(110, 230, "same speed as the car", 56, u, 0.0, 0.4, bold=True))
    c.text(at(12, 3.4), at(12, 5.0), punch(980, 280, "CONGRATULATIONS", "…?", 80))
    c.text(at(12, 5.0), at(13, 0.0), lambda u, _t: ch(110, 230, "you crashed without", 52, u, 0.0)
           + ch(110, 310, "the car ✗  the seatbelt ✗  the airbag ✗", 46, u, 0.8))
    c.key("hero", at(13, 0.0), "a6", 2100, G)
    c.text(at(13, 0.2), c.end(), label(110, 170, "LESSON ONE", "a door, not a brake", 84))
    c.sfx(at(13, 0.2), "sfx_hit", 0.45)
    c.music(0.0, "music_main", 0.12)
    return c


# ================================================================ 14-17: the portal loop (room)

def loop_seq():
    c = new((14, 17), "room_plate")
    G = GR["room_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    X, TOP = 760, 260
    cam = (1150, 820, 2000)
    c.cam(0.0, *cam)
    c.key("hero", 0.0, "a7", X + 330, G)
    c.text(at(14, 0.2), at(14, 2.8), punch(1400, 260, "ALTHOUGH…", "a very good accelerator", 70))

    def portals(img, u, _t):
        d = ImageDraw.Draw(img, "RGBA")
        for y in (G - 20, TOP):
            g = 0.75 + 0.25 * math.sin(u * 6)
            for j, a in enumerate((60, 120, 255)):
                e = 16 - 6 * j
                d.ellipse([X - 150 - e, y - 30 - e, X + 150 + e, y + 30 + e], outline=(255, 181, 71, int(a * g)),
                          width=8 - 2 * j)
    c.draw(at(14, 2.4), c.end(), portals)
    c.sfx(at(14, 2.4), "sfx_teleport", 0.4)
    # laps: each faster, until the drag limit (~120 mph); 15 s of falling compressed into the shot
    t0 = 5.4
    laps = [1.1, 0.8, 0.6, 0.45, 0.38, 0.34, 0.32, 0.31, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]
    t = t0
    for k, d in enumerate(laps):
        c.key("hero", at(14, t) if t < 6.5 else at(15, t - 6.5), "a1", X, TOP + 40, ang=90)
        t += d
        c.key("hero", at(14, t) if t < 6.5 else at(15, t - 6.5), "a1", X, G - 60, ang=90, tween="in" if k < 4 else "lin",
              smear=k > 2)
        if t > 6.5 + 7.8:
            break
    c.speed_lines(at(15, 0.5), at(16, 0.0))
    c.text(at(15, 0.0), at(16, 0.0), counter(1250, 120, "FALL SPEED", lambda u: f"{min(120.0, 25 + 15 * u):.0f} mph",
                                             "faster every lap…"))
    c.text(at(15, 6.0), at(16, 0.0), lambda u, _t: am(1250, 330, "…until the wind holds you", 44, u, 0.0))
    # 16: free speed forever? physics says no.
    c.key("hero", at(16, 0.0), "hero7", X + 330, G)
    c.text(at(16, 0.3), at(16, 3.2), punch(1350, 260, "FREE SPEED", "forever?", 84))
    c.text(at(16, 3.2), at(16, 5.6), lambda u, _t: (f'<rect width="{W}" height="{H}" fill="#050507" '
                                                     f'opacity="{0.72 * min(1, u / 0.2):.2f}"/>'
                                                     + overlay.text(W / 2, 520, "PERPETUAL MOTION?", 90, anchor="middle",
                                                                    op=min(1, u / 0.2))
                                                     + overlay.text(W / 2, 650, "PHYSICS SAYS NO.", 120, AMB, "middle",
                                                                    op=min(1, (u - 0.9) / 0.2))))
    c.sfx(at(16, 4.1), "sfx_hit", 0.5)
    c.text(at(16, 5.6), at(17, 0.0), lambda u, _t: ch(1150, 300, "a real teleporter", 52, u, 0.0)
           + ch(1150, 380, "charges you for every", 52, u, 0.6) + am(1150, 460, "bit of height", 62, u, 1.4))
    c.key("hero", at(17, 0.0), "a6", X + 330, G)
    c.text(at(17, 0.1), c.end(), lambda u, _t: big(1150, 330, "no free energy.", 80, u, 0.0))
    c.music(0.0, "music_main", 0.12)
    return c


# ================================================================ 18-21: the beach on the equator

def beach_seq():
    c = new((18, 21), "beach_plate")
    G = GR["beach_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    c.cam(0.0, 1000, 900, 2100)
    c.key("hero", 0.0, "hero0", 700, G)
    c.text(at(18, 0.3), at(18, 5.0), label(1150, 170, "ECUADOR", "right on the equator", 74))
    c.text(at(18, 5.0), at(19, 0.0), lambda u, _t: ch(1150, 260, "you want to see", 52, u, 0.0)
           + ch(1150, 340, "the North Pole", 72, u, 0.6, 0.4, bold=True)
           + am(1150, 460, "nothing's moving. right?", 50, u, 2.6))
    c.key("hero", at(18, 6.0), "a5", 700, G)
    # 19: wrong — the spinning planet (board)

    def spin(u):
        return (globe_top(u, 860, 560, 330, spin=0.35 * u)
                + ch(1300, 300, "the equator goes", 48, u, 1.6) + ch(1300, 370, "all the way around", 48, u, 2.0)
                + ch(1300, 440, "every day", 48, u, 2.4)
                + ch(1300, 600, "faster than sound", 66, u, 5.4, 0.4, bold=True))
    c.text(at(19, 0.0), at(20, 0.0), vb(spin))
    c.text(at(19, 0.0), at(19, 1.0), punch(1500, 120, "WRONG.", "", 120))
    c.sfx(at(19, 0.1), "sfx_hit", 0.45)
    # 20: you never feel it — sea, air and you all move together
    c.key("hero", at(20, 0.0), "hero7", 700, G)

    def together(u, _t):
        out = ""
        for k, (x, y, s) in enumerate([(380, 380, "air"), (1150, 680, "sea"), (520, 860, "you")]):
            out += overlay.chalk_arrow(x, y, x + 240, y, (u - 0.2 - 0.3 * k) / 0.3, seed=60 + k)
            out += ch(x + 260, y + 16, s, 46, u, 0.4 + 0.3 * k)
        return out + am(1150, 260, "all moving together", 56, u, 1.6)
    c.text(at(20, 0.0), at(21, 0.0), together)
    # 21: now teleport — the pole only turns on the spot
    c.key("hero", at(21, 0.0), "t0", 700, G)
    tp(c, at(21, 0.9), 700, G - 200)
    c.key("hero", at(21, 0.95), None)

    def pole(u):
        return (globe_top(u, 860, 560, 330, spin=0.35 * (u + 9))
                + f'<circle cx="860" cy="560" r="{40 + 8 * math.sin(u * 4):.0f}" fill="none" stroke="{AMB}" '
                  f'stroke-width="6"/>'
                + ch(1250, 360, "the pole doesn't travel", 46, u, 0.3)
                + ch(1250, 440, "it just turns on the spot", 46, u, 1.4)
                + am(1250, 540, "like the middle of a record", 42, u, 3.2))
    c.text(at(21, 1.2), c.end(), vb(pole))
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 22-27: the North Pole skid

def pole_seq():
    c = new((22, 27), "pole_plate")
    G = GR["pole_plate"]
    c.cast("hero", height=HERO)
    c.cast("snow", height=360, ref="snow0")
    at = c.at
    c.cam(0.0, 900, 1000, 1800)
    tp(c, at(22, 0.1), 300, G - 160)
    c.key("hero", at(22, 0.15), "t1", 300, G + 10)
    c.key("hero", at(23, 0.6), "t1", 2300, G + 10, tween="lin", smear=True)
    c.cam(at(23, 0.6), 2000, 1000, 1800, "lin")
    c.draw(at(22, 0.15), at(24, 0.0), spray(300, 2300, 3.6 + 0.6, G + 10, seed=7))
    c.speed_lines(at(22, 0.15), at(23, 0.6))
    c.sfx(at(22, 0.2), "sfx_ice", 0.55)
    c.text(at(22, 0.6), at(23, 0.0), lambda u, _t: ch(110, 230, "you:  full speed", 56, u, 0.0, 0.4, bold=True)
           + am(110, 310, "the ice:  0", 56, u, 1.0))
    # 23: you don't fall, you skid — faster than a pistol bullet (freeze)
    c.freeze(at(23, 0.6), at(24, 0.0), [
        lambda ctx, u: ch(110, 230, "you don't fall.", 56, u, 0.0, 0.4),
        lambda ctx, u: ch(110, 310, "you SKID", 80, u, 0.6, 0.3, bold=True),
        lambda ctx, u: ch(110, 420, "faster than a typical", 46, u, 1.6),
        lambda ctx, u: am(110, 480, "pistol bullet", 56, u, 2.2),
    ])
    c.sfx(at(23, 0.6), "sfx_freeze", 0.4)
    # 24: a dozen cars hitting a wall
    c.key("hero", at(24, 0.0), "t1", 2300, G + 10)
    c.key("hero", at(24, 2.0), "t1", 2600, G + 10, tween="out")

    def cars(u, _t):
        out = ch(110, 230, "crash energy of", 50, u, 0.0)
        for k in range(12):
            out += car_doodle(110 + (k % 6) * 150, 280 + (k // 6) * 90, 0.62, (u - 0.4 - 0.12 * k) / 0.3, 70 + k)
        out += overlay.chalk_line([(1040, 270), (1040, 470)], (u - 2.0) / 0.3, 10, seed=90, rough=False)
        return out + am(110, 560, "≈ a dozen cars hitting a wall", 50, u, 2.4) + am(110, 620, "all of it, in you", 44,
                                                                                    u, 4.6)
    c.text(at(24, 0.0), at(25, 0.0), cars)
    # 25-26: the note for physics fans (board) + "a very short video"

    def frame_note(u):
        return (globe_top(u, 560, 560, 260, spin=0.3 * u, label_pole=False)
                + ch(960, 330, "speed measured", 52, u, 0.3) + ch(960, 410, "as seen from space", 66, u, 0.9, bold=True)
                + ch(960, 560, "measured against the ground?", 44, u, 4.6)
                + am(960, 630, "nothing would happen at all", 48, u, 5.8))
    c.text(at(25, 0.0), at(26, 3.0), vb(frame_note))
    c.text(at(26, 3.0), at(27, 0.0), flash_card("THE END", "…a very short video"))
    # 27: subscribe — it gets worse (you, head-first in a snowbank)
    c.hide("hero", at(27, 0.0))
    c.key("snow", at(27, 0.0), "snow0", 1650, G + 20)
    c.cam(at(27, 0.0), 1500, 1050, 1600, "hold")
    c.text(at(27, 0.3), c.end(), lambda u, _t: am(110, 250, "SUBSCRIBE", 90, u, 0.0)
           + big(110, 340, "it gets worse", 64, u, 1.6))
    c.sfx(at(27, 0.3), "sfx_hit", 0.3)
    c.music(0.0, "music_tense", 0.12)
    return c


# ================================================================ 28-30: back to Ecuador; the quarter turn

def quarter_seq():
    c = new((28, 30), "beach_plate")
    G = GR["beach_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    c.cam(0.0, 1100, 950, 1900)
    c.key("hero", 0.0, "a5", 900, G)
    c.text(at(28, 0.2), at(29, 0.0), punch(1350, 300, "IT GETS WORSE", "the farther you go", 76))
    c.key("hero", at(29, 0.0), "t0", 900, G)
    c.text(at(29, 0.3), at(30, 0.0), lambda u, _t: ch(1150, 260, "a quarter of the way", 52, u, 0.0)
           + ch(1150, 340, "around the world", 52, u, 0.6) + am(1150, 440, "→ EAST, to Africa", 64, u, 3.0))
    tp(c, at(29, 6.6), 900, G - 200)
    c.key("hero", at(29, 6.65), None)

    def turn(u):
        # the point moves a quarter turn; your velocity arrow keeps its direction
        k = min(1.0, max(0.0, (u - 3.6) / 2.2))
        a = math.pi / 2 - (math.pi / 2) * k          # start at the bottom of the globe, end at its right side
        cx, cy, r = 700, 560, 300
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        out = globe_top(u, cx, cy, r, spin=0.0, arrows=False, label_pole=False)
        out += f'<circle cx="{px:.0f}" cy="{py:.0f}" r="14" fill="{AMB}"/>'
        out += overlay.chalk_arrow(px, py, px + 220, py, min(1.0, u / 0.4), seed=401)
        out += ch(1340, 300, "Earth from above", 50, u, 0.2)
        out += ch(1340, 400, "speed: along the ground", 40, u, 1.4)
        out += am(1340, 560, "a quarter turn later:", 44, u, 5.0) + am(1340, 630, "the same arrow points UP", 44, u, 6.0)
        return out
    c.text(at(30, 0.0), c.end(), vb(turn))
    c.music(0.0, "music_tense", 0.12)
    return c


# ================================================================ 31: the jungle launch

def jungle_seq():
    c = new((31, 31), "jungle_plate")
    G = GR["jungle_plate"]
    c.cast("hero", height=HERO)
    c.cam(0.0, 1300, 950, 1900)
    tp(c, 0.2, 1300, G - 200)
    c.key("hero", 0.25, "t2", 1300, G)
    c.key("hero", 1.6, "t2", 1180, G - 1700, tween="in", smear=True)
    c.cam(0.25, 1300, 950, 1900, "hold")
    c.cam(1.6, 1100, 760, 2300, "snap")
    c.whip(0.3, 1.0)
    c.shake(0.25, 0.6, 22)
    c.sfx(0.25, "sfx_sonic", 0.5)
    c.draw(0.25, c.end(), fx.debris(1300, G, n=24, power=1.0, color=(70, 110, 50), seed=31))
    c.draw(0.25, c.end(), fx.dust(1300, G, size=200, seed=32))
    c.text(1.6, c.end(), lambda u, _t: big(110, 260, "like a cannonball", 80, u, 0.0)
           + am(110, 360, "…while the jungle slides away", 48, u, 1.6))
    c.music(0.0, "music_tense", 0.12)
    return c


# ================================================================ 32-33: west -> into the Pacific; the far side

def ocean_down_seq():
    c = new((32, 33), "ocean_plate")
    S = GR["ocean_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    c.cam(0.0, 1300, 900, 1900)
    c.text(at(32, 0.2), at(32, 3.8), lambda u, _t: ch(110, 230, "a quarter turn WEST", 56, u, 0.0, 0.4, bold=True)
           + am(110, 310, "the same arrow points DOWN", 50, u, 1.4))
    tp(c, at(32, 4.0), 1300, 500)
    c.key("hero", at(32, 4.05), "a1", 1300, 600, ang=90)
    c.key("hero", at(32, 4.4), "a1", 1300, S + 250, ang=90, tween="in", smear=True)
    c.draw(at(32, 4.0), c.end(), submerge(1300, S, 300))
    c.draw(at(32, 4.35), c.end(), spray(1300, 1300, 0.6, S, seed=11, every=0.03))
    c.shake(at(32, 4.4), 0.5, 20)
    c.sfx(at(32, 4.35), "sfx_water", 0.55)
    c.text(at(32, 5.0), at(33, 0.0), lambda u, _t: big(110, 230, "into the Pacific", 72, u, 0.0))

    def far(u):
        out = globe_top(u, 760, 560, 300, spin=0.0, arrows=False, label_pole=False)
        out += overlay.chalk_arrow(760, 860, 1000, 860, min(1.0, u / 0.4), seed=411)
        out += f'<circle cx="760" cy="860" r="14" fill="{CH}"/><circle cx="760" cy="260" r="14" fill="{AMB}"/>'
        out += overlay.chalk_arrow(760, 260, 520, 260, (u - 1.6) / 0.4, seed=412)
        out += ch(1180, 300, "far side of the planet:", 48, u, 0.8)
        out += ch(1180, 380, "the ground spins the other way", 44, u, 1.8)
        out += am(1180, 520, "you hit it at", 50, u, 4.0) + am(1180, 600, "× 2 the speed", 80, u, 4.8)
        return out
    c.text(at(33, 0.0), c.end(), vb(far))
    c.music(0.0, "music_tense", 0.12)
    return c


# ================================================================ 34-39: the safe zone (map)

def safe_seq():
    c = new((34, 39), "map_plate")
    at = c.at
    MC = (1344, 760, 2300)
    c.cam(0.0, *MC)
    cx, cy = 980, 560
    c.text(0.0, c.end(), lambda u, _t: f'<rect width="{W}" height="{H}" fill="#06101C" opacity="0.38"/>')
    c.text(at(34, 0.2), at(34, 4.0), punch(960, 300, "USELESS?", "not at all", 90))
    c.text(at(34, 4.0), at(35, 0.0), lambda u, _t: big(110, 230, "it's all about distance", 70, u, 0.0)
           + am(110, 320, "the farther you jump, the bigger the mismatch can get", 44, u, 1.6))

    def rings3(u, _t):
        out = f'<circle cx="{cx}" cy="{cy}" r="10" fill="{AMB}"/>'
        rows = [(30, "1 mile", "✓ you won't notice", 0.0), (170, "100 miles", "a fall off a fast bike", 3.4),
                (420, "1,000 miles", "✗ you could be done", 6.6)]
        for k, (r, a, b, t) in enumerate(rows):
            if u < t:
                continue
            p = min(1.0, (u - t) / 0.6)
            out += (f'<circle cx="{cx}" cy="{cy}" r="{r * p:.0f}" fill="none" stroke="{CH}" stroke-width="6" '
                    f'stroke-dasharray="18 10"/>')
            out += ch(1430, 300 + 150 * k, a, 56, u, t + 0.2, 0.4, bold=True)
            out += (am if k != 1 else (lambda *x, **y: ch(*x, **y)))(1430, 360 + 150 * k, b, 40, u, t + 0.8)
        return out
    c.text(at(35, 0.0), at(37, 0.0), rings3)
    c.text(at(37, 0.0), at(38, 0.0), lambda u, _t: big(560, 520, "commute ✓", 110, u, 0.0, "middle")
           + am(1400, 520, "vacation ✗", 110, u, 1.3, "middle"))
    c.sfx(at(37, 1.3), "sfx_hit", 0.4)
    c.text(at(38, 0.0), at(39, 0.0), label(110, 170, "NOT SO FAST", "there's a secret route", 80))
    c.text(at(39, 0.0), c.end(), punch(960, 340, "BUT FIRST", "what else is waiting", 84))
    c.sfx(at(39, 0.1), "sfx_hit", 0.3)
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 40-44: other ways a jump goes wrong

def sky_seq():
    c = new((40, 40), "sky_plate")
    c.cast("hero", height=HERO)
    c.cam(0.0, 1300, 760, 2000)
    c.cam(c.end(), 1300, 820, 1800, "lin")
    tp(c, 0.2, 1000, 600)
    c.key("hero", 0.25, "t3", 1000, 780)
    c.key("hero", c.end(), "t3", 1000, 900, tween="lin")
    c.sfx(0.3, "sfx_wind", 0.45)
    c.text(0.6, c.end(), lambda u, _t: ch(1350, 300, "where airliners fly", 52, u, 0.0)
           + big(1350, 400, "air: thin", 72, u, 1.2)
           + am(1350, 500, "≈ half a minute of clear thinking", 44, u, 3.2))
    c.music(0.0, "music_tense", 0.1)
    return c


def trench_seq():
    c = new((41, 41), "trench_plate")
    G = GR["trench_plate"]
    c.cast("hero", height=HERO)
    c.cam(0.0, 1344, 1000, 1900)
    tp(c, 0.2, 1344, G - 200)
    c.key("hero", 0.25, "hero6", 1344, G)
    c.sfx(0.3, "sfx_deep", 0.5)

    def nail(u, _t):
        return (ch(110, 230, "the deepest trench", 56, u, 0.0, 0.4, bold=True)
                + ch(110, 330, "every fingernail-sized patch", 44, u, 1.6)
                + car_doodle(1350, 220, 1.6, (u - 3.4) / 0.6, 81)
                + overlay.chalk_line([(1420, 300), (1480, 380), (1540, 300)], (u - 4.0) / 0.3, 6, seed=82,
                                     rough=False)
                + am(110, 420, "carries the weight of a small car", 48, u, 4.2))
    c.text(0.3, c.end(), nail)
    c.music(0.0, "music_tense", 0.1)
    return c


def room_bang_seq():
    c = new((42, 43), "room_plate")
    G = GR["room_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    c.cam(0.0, 1300, 900, 2000)
    tp(c, at(42, 0.5), 1500, G - 200)
    c.key("hero", at(42, 0.55), "hero6", 1500, G)

    def burst(x, y):
        def f(u, _t):
            out = ""
            for j in range(12):
                a = j * math.pi / 6
                r0, r1 = 40 + 160 * min(1.0, u / 0.5), 100 + 260 * min(1.0, u / 0.5)
                out += overlay.chalk_line([(x + r0 * math.cos(a), y + r0 * math.sin(a)),
                                           (x + r1 * math.cos(a), y + r1 * math.sin(a))], 1.0, 6, seed=500 + j,
                                          rough=False)
            return out
        return f
    hx, hy = scr((1300, 900, 2000), 1500, G - 200)
    c.text(at(42, 0.55), at(42, 1.4), burst(hx, hy))
    c.text(at(42, 1.4), at(43, 0.0), lambda u, _t: ch(110, 230, "the air in your spot", 52, u, 0.0)
           + big(110, 320, "has to get out of the way", 60, u, 0.8) + am(110, 410, "all at once", 56, u, 2.6))
    c.flash(at(43, 0.2), 0.06)
    c.shake(at(43, 0.2), 0.4, 22)
    c.sfx(at(43, 0.15), "sfx_bang", 0.5)
    c.text(at(43, 0.2), at(43, 1.4), burst(hx, hy))
    c.text(at(43, 0.3), c.end(), lambda u, _t: am(110, 230, "BANG", 110, u, 0.0)
           + ch(110, 330, "like a gunshot", 52, u, 0.4) + ch(110, 410, "two, actually:", 52, u, 1.6))
    tp(c, at(43, 2.6), 1500, G - 200)
    c.key("hero", at(43, 2.65), None)
    c.draw(at(43, 2.7), c.end(), ring(700, G - 200))
    c.key("hero", at(43, 2.7), "hero6", 700, G)
    c.sfx(at(43, 3.0), "sfx_crash", 0.4)
    c.text(at(43, 3.0), at(43, 4.0), burst(*scr((1300, 900, 2000), 1500, G - 200)))
    c.text(at(43, 3.6), c.end(), lambda u, _t: ch(110, 500, "one where you arrive,", 44, u, 0.0)
           + ch(110, 560, "one where you left", 44, u, 1.0))
    c.music(0.0, "music_tense", 0.1)
    return c


def moon_seq():
    c = new((44, 44), "moon_plate")
    G = GR["moon_plate"]
    c.cast("hero", height=HERO)
    c.cam(0.0, 1100, 900, 2000)
    c.text(0.2, 3.6, lambda u, _t: big(110, 230, "the Moon?", 80, u, 0.0)
           + am(110, 320, "it's racing around the Earth", 48, u, 1.0) + ch(110, 390, "you're not", 48, u, 2.4))
    tp(c, 4.4, 500, G - 300)
    c.key("hero", 4.45, "t1", 500, G - 120)
    c.key("hero", 5.6, "t1", 2300, G, tween="out", smear=True)
    c.cam(5.6, 1900, 950, 2000, "ease")
    c.draw(4.6, c.end(), spray(500, 2300, 1.2, G, seed=13, col=(205, 205, 200)))
    c.draw(4.6, c.end(), fx.dust(1600, G, n=24, size=200, life=3.0, seed=14, color=(190, 188, 182)))
    c.shake(4.6, 0.6, 24)
    c.sfx(4.6, "sfx_crash", 0.45)
    c.text(5.8, c.end(), lambda u, _t: big(110, 230, "out of step", 72, u, 0.0)
           + am(110, 320, "much faster than a pistol bullet", 48, u, 1.0))
    c.music(0.0, "music_tense", 0.1)
    return c


# ================================================================ 45-49: the secret route

def twin_seq():
    c = new((45, 49), "ocean_plate")
    S = GR["ocean_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    c.cam(0.0, 1500, 900, 1900)
    c.text(at(45, 0.0), at(45, 2.8), punch(960, 380, "SO WHERE DOES IT WORK?", "", 84))

    def twins(u):
        cx, cy, r = 700, 560, 320
        lat = math.radians(41)
        out = globe_side(u, cx, cy, r, phase=0.5 * u)
        ny = (cx + 0.15 * r, cy - r * math.sin(lat))
        sx = (cx + 0.15 * r, cy + r * math.sin(lat))
        if u > 1.0:
            out += f'<circle cx="{ny[0]:.0f}" cy="{ny[1]:.0f}" r="14" fill="{AMB}"/>'
            out += ch(cx - r - 24, ny[1] + 12, "New York", 38, u, 1.0, anchor="end")
        if u > 3.0:
            out += overlay.chalk_line([ny, sx], (u - 3.0) / 0.8, 5, seed=601, rough=False)
            out += f'<circle cx="{sx[0]:.0f}" cy="{sx[1]:.0f}" r="14" fill="{AMB}"/>'
            out += ch(cx - r - 24, sx[1] + 12, "its twin", 38, u, 3.8, anchor="end")
        out += label(1150, 240, "THE SECRET ROUTE", "your twin spot", 64)(u, 0)
        out += ch(1150, 470, "same distance south,", 46, u, 5.0) + ch(1150, 540, "same line down the map", 46, u, 6.0)
        if u > 9.0:                                                 # 47: identical arrows, wheel on an axle
            out += overlay.chalk_arrow(ny[0], ny[1], ny[0] + 200, ny[1], (u - 9.0) / 0.4, seed=602)
            out += overlay.chalk_arrow(sx[0], sx[1], sx[0] + 200, sx[1], (u - 9.6) / 0.4, seed=603)
            out += am(1150, 680, "same direction, same speed", 50, u, 11.5)
            out += ch(1150, 760, "like a wheel on an axle", 44, u, 10.0)
        return out
    c.text(at(45, 2.8), at(48, 0.0), vb(twins))
    # 48-49: from New York to just off southern Chile: perfectly still... and a little bit wet
    c.text(at(48, 0.0), at(48, 4.8), lambda u, _t: ch(110, 230, "New York → off southern Chile", 52, u, 0.0, 0.4,
                                                       bold=True) + am(110, 310, "more than 5,000 miles", 48, u, 1.6))
    tp(c, at(48, 5.2), 1500, S - 120)
    c.key("hero", at(48, 5.25), "a6", 1500, S + HERO * 0.55)
    c.draw(at(48, 5.2), c.end(), submerge(1500, S, 260))
    c.draw(at(48, 5.25), at(49, 1.5), fx.dust(1500, S, size=60, life=1.0, seed=17, color=(240, 248, 255)))
    c.sfx(at(48, 5.3), "sfx_water", 0.35)
    c.text(at(48, 6.0), c.end(), lambda u, _t: big(110, 230, "0 mph  ✓", 80, u, 0.0)
           + am(110, 330, "perfectly still…", 56, u, 1.2))
    c.text(at(49, 0.6), c.end(), lambda u, _t: am(110, 420, "…and a little bit wet", 56, u, 0.0))
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 50-53: rockets and the spin

def launch_seq():
    c = new((50, 53), "launch_plate")
    G = GR["launch_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    c.cam(0.0, 1400, 900, 2200)
    c.key("hero", 0.0, "a7", 900, G)
    c.sfx(at(50, 0.2), "sfx_rocket", 0.4)
    c.text(at(50, 0.2), at(50, 3.0), label(110, 170, "ROCKET ENGINEERS", "love the spin too", 76))
    c.text(at(50, 3.0), at(51, 0.0), lambda u, _t: ch(110, 230, "launch close to the equator", 50, u, 0.0)
           + am(110, 310, "aimed EAST →", 64, u, 1.6))
    c.text(at(51, 0.0), at(51, 4.6), lambda u, _t: ch(110, 230, "a free push of", 50, u, 0.0)
           + big(110, 320, "≈ 1,000 mph", 84, u, 0.6) + ch(110, 400, "before the engines light", 40, u, 1.6))
    c.key("hero", at(51, 4.6), "t0", 900, G)
    c.draw(at(51, 4.6), c.end(), ring(900, G - 200))
    c.text(at(51, 4.7), at(52, 0.0), lambda u, _t: ch(110, 230, "your teleporter:", 56, u, 0.0)
           + am(110, 320, "+ 0 mph", 84, u, 0.8))

    def swivel(u, _t):
        hx, hy = scr((1400, 900, 2200), 900, G - 220)
        a = math.radians(-90 * min(1.0, u / 1.6))
        return (overlay.chalk_arrow(hx, hy, hx + 220 * math.cos(a), hy + 220 * math.sin(a), 1.0, seed=701)
                + ch(110, 230, "it only chooses", 52, u, 0.0) + am(110, 310, "where your speed points", 56, u, 0.6))
    c.text(at(52, 0.0), at(53, 0.0), swivel)
    c.key("hero", at(53, 0.0), "a7", 900, G)
    c.text(at(53, 0.2), c.end(), label(110, 170, "THE TRICK", "land where the ground moves like you", 64))
    c.sfx(at(53, 0.2), "sfx_hit", 0.4)
    c.music(0.0, "music_calm", 0.12)
    return c


# ================================================================ 54-56: ending + end screen

def ending_seq():
    c = new((54, 56), "beach_plate", fade_out=0.8)
    G = GR["beach_plate"]
    c.cast("hero", height=HERO)
    at = c.at
    c.cam(0.0, 1100, 950, 2000)
    c.key("hero", 0.0, "hero0", 800, G)
    items = ["a door, not a brake", "the ground is already moving", "jump small", "find your twin"]
    c.text(at(54, 0.3), at(55, 0.0), lambda u, _t: "".join(ch(1150, 260 + 90 * k, s, 50, u, 0.3 + 1.4 * k, 0.5, True)
                                                            for k, s in enumerate(items)))
    c.sfx(at(54, 0.3), "sfx_chalk", 0.3)
    c.key("hero", at(55, 0.0), "t0", 800, G)
    c.text(at(55, 0.0), at(55, 2.8), punch(1350, 300, "JUMP SMALL.", "jump smart.", 90))
    c.key("hero", at(55, 2.8), "hero6", 800, G)
    c.text(at(55, 2.8), at(56, 0.0), lambda u, _t: big(1150, 300, "never, ever", 70, u, 0.0)
           + am(1150, 400, "teleport to the North Pole", 60, u, 0.6))
    c.key("hero", at(56, 0.0), "a7", 800, G)
    c.text(at(56, 0.2), at(56, 4.6), label(110, 170, "YOUR TURN", "where would you go first?", 70))

    def end_screen(u, _t):
        k = min(1.0, u / 0.5)
        box = ('<rect x="{x}" y="300" width="760" height="428" rx="18" fill="#000" opacity="{o:.2f}" '
               'stroke="#F2EEE4" stroke-width="4"/>')
        bob = 10 * math.sin(u * 2.2)
        return (f'<rect width="{W}" height="{H}" fill="#06080C" opacity="{0.78 * k:.2f}"/>'
                + box.format(x=140, o=0.55 * k) + box.format(x=1020, o=0.55 * k)
                + overlay.text(W / 2, 200 + bob, "watch next", 64, anchor="middle", op=k)
                + overlay.text(W / 2, 880, "subscribe for the next “what if”", 44, AMB, "middle", 600, "Inter", op=k))
    c.text(at(56, 4.6), c.end(), end_screen)
    c.hide("hero", at(56, 4.6))
    c.music(0.0, "music_main", 0.12)
    return c


def build(size):
    return [tower_seq(), car_seq(), loop_seq(), beach_seq(), pole_seq(), quarter_seq(), jungle_seq(),
            ocean_down_seq(), safe_seq(), sky_seq(), trench_seq(), room_bang_seq(), moon_seq(), twin_seq(),
            launch_seq(), ending_seq()]
