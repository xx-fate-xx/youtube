"""Motion-comic scenes for shots 6-76 of the super-speed pilot (format approved 2026-11-22).

Art in projects/whatif_super_speed/art: plates (tower, fire, stairs, highway, night, ocean, map) and pose sheets sliced
into sprites: hero0-7 / cleaner0-5 (cold-open sheets), a0-7, b0-7, c0-7 (see the pose list below). Sounds in
projects/whatif_super_speed/sfx. Every number on screen is from script.md calc_notes / factcheck_report.md.

a: 0 sprint, 1 dive, 2 carry (calm), 3 carry (bracing), 4 two under the arms, 5 thinking, 6 shrug, 7 pointing up
b: 0 coughing worker, 1 squished worker, 2 hero shoved back (sparks), 3 hero bracing, 4 truck, 5 driver panics,
   6 driver relieved, 7 hero dusting hands
c: 0 hero too slow (blink), 1 hero fast brain (glow), 2 hero catching the bullet, 3 hero shows the bullet,
   4 startled woman, 5 hero running on water, 6 basilisk lizard, 7 hero shouting
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from studio.whatif import fx, overlay
from studio.whatif.comic import (
    Comic,
    board,
    chalk_arrow,
    chalk_line,
    chalk_note,
    counter,
    label,
    punch,
    scrim,
)

SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455}     # standing body height on each sheet (px)
W, H = 1920, 1080


def new(shots, plate, **kw) -> Comic:
    c = Comic(shots=shots, plate=plate, **kw)
    c.sheet_ref = dict(SHEET)
    return c


def scr(cam, x, y):
    """Plate point -> screen point for a camera (cx, cy, width) on a 2688x1520 plate."""
    cx, cy, vw = cam
    k = W / vw
    vh = vw * H / W
    x0 = min(max(cx - vw / 2, 0), 2688 - vw)
    y0 = min(max(cy - vh / 2, 0), 1520 - vh)
    return (x - x0) * k, (y - y0) * k


def notes(lines, x=120, y=250, gap=1.0, sc=True):
    """Chalk lines written one after another (text, size, bold) over a soft scrim; for c.text or freezes."""
    def f(u, _t=None):
        out = [overlay.scrim(x + 420, y + 40 * len(lines), 720, 120 + 70 * len(lines), min(1.0, u / 0.3))] if sc else []
        yy, prev = y, lines[0][1]
        for k, (s, size, bold) in enumerate(lines):
            if k:
                yy += size * 1.15 + prev * 0.22            # room for this line and the descenders of the last
            prev = size
            out.append(overlay.chalk_text(x, yy, s, size, (u - 0.15 - k * gap) / 0.5, 800 if bold else 600,
                                          "Inter Display" if bold else "Inter"))
        return "".join(out)
    return f


def frz(fn):
    """A text fn as a freeze item."""
    return lambda ctx, u: fn(u)


def lesson(c: Comic, at, n: int, text: str, until=None):
    c.text(at, until if until is not None else c.end(), label(110, 170, f"LESSON {n}", text, 76))
    c.sfx(at, "sfx_hit", 0.4)


def rescue(c: Comic, at, n: int, title: str, until):
    c.text(at, until, label(110, 170, f"RESCUE {n}", title, 84))
    c.sfx(at, "sfx_hit", 0.45)


def streak(c: Comic, x0, x1, y, at, dur, color=(255, 190, 80)):
    """A bullet: a small glowing slug with a short trail, travelling x0 -> x1 (plate px) in `dur` seconds."""
    def f(img: Image.Image, u, _t):
        if u > dur:
            return
        k = u / dur
        x = x0 + (x1 - x0) * k
        d = ImageDraw.Draw(img, "RGBA")
        tail = 260 * (1 if x1 > x0 else -1)
        for j in range(6):
            a = 40 + 30 * j
            d.line([(x - tail * (1 - j / 6), y), (x, y)], fill=(*color, a), width=10 - j)
        d.ellipse([x - 10, y - 6, x + 10, y + 6], fill=(255, 215, 120, 255))
    c.draw(at, c.end(), f)


# ---------------------------------------------------------------- 6-7: title + the freeze device

def title_seq():
    c = new((6, 7), "tower_plate")
    GR = 1362
    c.cast("hero", height=405)
    at = c.at
    c.cam(0.0, 1100, 1000, 1700)
    c.cam(at(7, 0.0), 1100, 1000, 1500)
    c.key("hero", 0.0, "a7", 760, GR)
    c.text(at(6, 0.3), at(7, 0.0), punch(1250, 330, "WHAT IF", "you had super speed?", 84))
    c.sfx(at(6, 0.3), "sfx_hit", 0.45)
    c.key("hero", at(7, 0.0), "a0", 520, GR)
    c.key("hero", at(7, 0.45), "a0", 1240, GR, tween="snap", smear=True)
    c.speed_lines(at(7, 0.0), at(7, 0.5))
    c.sfx(at(7, 0.0), "sfx_dash", 0.45)
    c.freeze(at(7, 0.5), c.end(), [
        scrim(1300, 420, 700, 380),
        chalk_note(1020, 330, "FREEZE", 96, 0.1, 0.4, 800, "Inter Display"),
        chalk_note(1024, 410, "= stop the clock,", 46, 0.6, 0.5),
        chalk_note(1024, 470, "look at the physics", 46, 1.1, 0.5),
        chalk_arrow(1000, 520, 870, 640, 1.6, 0.4),
    ])
    c.sfx(at(7, 0.5), "sfx_freeze", 0.5)
    c.music(0.0, "music_main", 0.13)
    return c


# ---------------------------------------------------------------- 8-17: rescue 1, the fall

def fall_seq():
    c = new((8, 17), "tower_plate")
    GR = 1362
    c.cast("hero", height=405)
    c.cast("cleaner", height=397, ref="cleaner0", persp=(316, GR, 0.24))
    c.cast("pair", height=405)
    at = c.at
    # 8: rewind; the problem is the stop
    c.cam(0.0, 1600, 900, 1700)
    c.rewind(0.0, 0.8)
    c.sfx(0.0, "sfx_rewind", 0.4)
    c.key("hero", 0.0, "hero4", 1640, GR)
    c.key("cleaner", 0.0, "cleaner3", 1700, 1000, scale=0.92, fixed=True)
    c.key("cleaner", 0.8, "cleaner3", 1700, 420, scale=0.92, fixed=True, tween="ease")
    rescue(c, at(8, 0.9), 1, "The fall", at(8, 4.2))
    c.freeze(at(8, 2.0), at(9, 0.0), [frz(notes([("falling fast:  fine", 52, True),
                                               ("stopping fast:  the problem", 52, True)], 120, 560, 1.4))])
    c.sfx(at(8, 2.0), "sfx_freeze", 0.4)
    # 9: catch in the arms -> 140 g
    c.key("cleaner", at(9, 0.1), "cleaner3", 1700, 420, scale=0.92, fixed=True)
    c.key("cleaner", at(9, 0.7), "cleaner3", 1700, 880, scale=0.92, fixed=True, tween="in")
    c.key("cleaner", at(9, 0.7), "cleaner4", 1675, GR - 330, ang=-8, scale=0.8, fixed=True)
    c.key("hero", at(9, 0.7), "hero5", 1640, GR)
    c.cam(at(9, 0.7), 1600, 980, 1300, "hold")
    c.flash(at(9, 0.7), 0.1)
    c.shake(at(9, 0.7), 0.5, 30)
    c.sfx(at(9, 0.65), "sfx_catch", 0.5)
    c.draw(at(9, 0.7), at(10, 0.0), fx.cracks(1640, GR + 4, 300, seed=11), front=False)
    c.draw(at(9, 0.7), at(10, 0.0), fx.dust(1640, GR, size=150, seed=12))
    c.draw(at(9, 0.7), at(10, 0.0), fx.debris(1640, GR, n=18, power=0.8, seed=13))
    c.freeze(at(9, 1.2), at(10, 0.0), [
        scrim(500, 420, 700, 400),
        chalk_note(140, 330, "stops in ≈ 1.5 ft", 52, 0.2, 0.5),
        chalk_note(140, 440, "≈ 140 g", 120, 0.9, 0.4, 800, "Inter Display"),
        chalk_arrow(620, 470, 880, 560, 1.4, 0.4),
    ])
    # 10-11: Stapp's rocket sled (chalkboard)
    rail = [[(150, 700), (1250, 700)]]
    sled = [[(600, 700), (600, 620), (880, 620), (930, 670), (930, 700)], [(700, 620), (700, 530), (760, 530)],
            [(580, 645), (500, 635)], [(580, 665), (470, 670)], [(580, 685), (510, 700)]]
    rider = [[(735, 530), (735, 460)], [(735, 460), (785, 485)], [(735, 515), (795, 560)]]

    def stapp(u):
        return (overlay.sketch_paths(rail + sled + rider, (u - 0.3) / 2.0)
                + overlay.chalk_text(150, 250, "John Paul Stapp · Air Force doctor · 1954", 44, (u - 1.2) / 0.8)
                + overlay.chalk_text(150, 350, "> 600 mph → 0", 84, (u - 3.0) / 0.5, 800, "Inter Display")
                + overlay.chalk_text(150, 430, "over 40 g · strapped in", 48, (u - 6.0) / 0.6)
                + overlay.chalk_text(150, 850, "bruised · vision gone for minutes", 48, (u - 11.5) / 0.8))
    c.text(at(10, 0.0), at(12, 0.0), board(stapp))
    c.sfx(at(10, 0.3), "sfx_chalk", 0.35)
    coaster = [[(180, 300), (330, 300), (420, 360), (520, 640), (600, 700), (760, 700), (880, 600), (980, 560),
                (1200, 560), (1320, 430), (1440, 380)]]

    def coast(u):
        return (overlay.sketch_paths(coaster, (u - 0.2) / 1.6)
                + overlay.chalk_text(180, 850, "biggest roller coasters:", 48, (u - 1.5) / 0.6)
                + overlay.chalk_text(180, 950, "4 – 6 g, for a moment", 76, (u - 2.4) / 0.5, 800, "Inter Display"))
    c.text(at(12, 0.0), at(13, 0.0), board(coast))
    c.sfx(at(12, 0.2), "sfx_chalk", 0.35)
    # 13: 60 ft to slow down -> can't wait at the bottom (wide: the hero small against the tower)
    cam13 = (1500, 900, 2688)
    c.cam(at(13, 0.0), *cam13, "hold")
    c.hide("cleaner", at(13, 0.0))
    c.key("hero", at(13, 0.0), "a5", 1650, GR, scale=0.4, fixed=True)
    gx, gy = scr(cam13, 1830, GR)
    top = scr(cam13, 1830, GR - 250)[1]

    def tape(u, _t=None):
        out = overlay.chalk_line([(gx, gy), (gx, top)], (u - 0.3) / 1.0, 6, seed=21, rough=False)
        out += overlay.chalk_line([(gx - 25, top), (gx + 25, top)], (u - 1.3) / 0.2, 5, seed=22, rough=False)
        out += overlay.chalk_text(gx + 40, top + 20, "60 ft · 18 m", 56, (u - 1.4) / 0.4, 800, "Inter Display")
        out += overlay.chalk_text(gx + 40, top + 80, "→ under 4 g", 44, (u - 2.0) / 0.4)
        out += notes([("can't wait at the bottom", 54, True)], 120, 250)(u - 4.6) if u > 4.6 else ""
        return out
    c.text(at(13, 0.0), at(14, 0.0), tape)
    # 14: super grip
    c.cam(at(14, 0.0), 1600, 1000, 1300, "hold")
    c.key("hero", at(14, 0.0), "a7", 1640, GR)
    c.text(at(14, 0.4), at(15, 0.0), label(110, 170, "NEW POWER", "+ super grip", 90))
    # 15: up the wall, meet them, match their speed
    c.cam(at(15, 0.0), 1700, 1000, 1500, "hold")
    c.key("hero", at(15, 0.0), "a0", 1650, GR)
    c.key("hero", at(15, 0.3), "a0", 1835, GR - 120, ang=-90, scale=0.75, fixed=True)
    c.key("hero", at(15, 1.3), "a0", 1855, 420, ang=-90, scale=0.75, fixed=True, tween="snap", smear=True)
    c.cam(at(15, 0.3), 1700, 1000, 1500)
    c.cam(at(15, 1.3), 1800, 520, 1300, "snap")
    c.speed_lines(at(15, 0.3), at(15, 1.4))
    c.sfx(at(15, 0.3), "sfx_dash", 0.45)
    c.draw(at(15, 0.3), at(16, 0.0), fx.dust(1800, GR, size=130, seed=14))
    c.draw(at(15, 0.3), at(16, 0.0), fx.debris(1810, GR, n=12, power=0.6, seed=15, spread=(220, 300)))
    c.key("cleaner", at(15, 1.6), "cleaner3", 1680, 260, scale=0.7, fixed=True)
    c.key("cleaner", at(15, 3.0), "cleaner3", 1680, 520, scale=0.7, fixed=True, tween="lin")
    c.key("hero", at(15, 2.0), "a1", 1790, 330, scale=0.75, fixed=True)
    c.key("hero", at(15, 3.0), "a1", 1790, 560, scale=0.75, fixed=True, tween="lin")
    c.cam(at(15, 1.6), 1750, 450, 1250)
    c.cam(at(15, 3.0), 1750, 560, 1250, "lin")
    c.freeze(at(15, 3.0), at(16, 0.0), [frz(notes([("them:  ↓ 75 mph", 54, True), ("you:  ↓ 75 mph", 54, True),
                                                    ("same speed = nothing hits", 46, False)], 120, 250, 0.9))])
    c.sfx(at(15, 3.0), "sfx_freeze", 0.4)
    # 16: brake gently over the last 60 ft
    c.hide("cleaner", at(16, 0.0))
    c.hide("hero", at(16, 0.0))
    c.key("pair", at(16, 0.0), "a3", 1720, 700, scale=0.75, fixed=True)
    c.key("pair", at(16, 3.6), "a3", 1720, GR, scale=1.0, fixed=True, tween="out")
    c.draw(at(16, 3.6), at(17, 0.0), fx.dust(1720, GR, size=120, seed=16))
    c.cam(at(16, 0.0), 1700, 760, 1500, "hold")
    c.cam(at(16, 3.6), 1650, 1000, 1500, "out")
    c.text(at(16, 0.2), at(17, 0.0), counter(110, 120, "ON THEM", lambda u: f"{min(3.9, 1 + u * 1.6):.1f} g",
                                            "keep it under 4 g"))
    # 17: lesson one
    c.key("pair", at(17, 0.0), "a2", 1640, GR)
    c.cam(at(17, 0.0), 1500, 1000, 1500, "hold")
    lesson(c, at(17, 1.0), 1, "Stop slowly.")
    c.music(0.0, "music_main", 0.13)
    return c


# ---------------------------------------------------------------- 18-30: rescue 2, the burning tower

def fire_seq():
    c = new((18, 19), "fire_plate")
    c.cast("hero", height=330)
    c.cast("pair", height=330)
    c.cast("worker", height=330)
    at = c.at
    # 18: the fire; smoke kills
    c.cam(0.0, 1344, 760, 2688)
    c.cam(at(18, 4.5), 1900, 420, 1700, "ease")
    rescue(c, at(18, 0.4), 2, "The burning tower", at(18, 4.2))
    c.sfx(at(18, 0.2), "sfx_alarm", 0.35)
    c.text(at(18, 5.2), at(19, 0.0), notes([("most fire deaths:", 50, False), ("the SMOKE,", 76, True),
                                             ("not the flames", 50, False)], 120, 560, 0.7))
    # 19: less than two minutes
    c.cam(at(19, 0.0), 1700, 560, 1900, "hold")

    def clock(u):
        s = max(0.0, 120 - u * 1.0)
        return f"{int(s // 60)}:{int(s % 60):02d}"
    c.text(at(19, 0.3), c.end(), counter(110, 120, "TIME TO GET OUT", clock, "from the smoke alarm"))
    c.sfx(at(19, 0.3), "sfx_tick", 0.35)
    c.music(0.0, "music_tense", 0.12)
    return c


def stairs_seq():
    c = new((20, 24), "stairs_plate")
    FL, LAND = 1460, 1000
    c.cast("hero", height=290)
    c.cast("pair", height=290)
    c.cast("worker", height=290)
    at = c.at
    cam = (1344, 760, 2688)
    c.cam(0.0, *cam)
    # 20: run in, grab, head for the stairs... and hit a wall
    c.key("worker", 0.0, "b0", 2150, LAND)
    c.key("hero", at(20, 0.3), "a0", 300, FL)
    c.key("hero", at(20, 0.8), "a0", 1950, LAND, tween="snap", smear=True)
    c.sfx(at(20, 0.3), "sfx_dash", 0.4)
    c.speed_lines(at(20, 0.3), at(20, 0.85))
    c.hide("hero", at(20, 2.2))
    c.hide("worker", at(20, 2.2))
    c.key("pair", at(20, 2.2), "a2", 2050, LAND)
    c.text(at(20, 2.4), at(20, 4.8), label(110, 170, "NEXT", "head for the stairs", 76))
    c.shake(at(20, 5.2), 0.35, 14)
    c.text(at(20, 5.2), at(21, 0.0), punch(960, 330, "...", "and you hit a wall", 80))
    # 21: the landing is ~4 ft wide
    lx0, ly = scr(cam, 1760, LAND)
    lx1 = scr(cam, 2500, LAND)[0]
    c.freeze(at(21, 0.0), at(22, 0.0), [
        scrim(1500, 560, 700, 380),
        chalk_line([(lx0, ly + 30), (lx1, ly + 30)], 0.2, 0.5, 6, 31),
        chalk_note(lx0 + 60, ly + 100, "landing ≈ 4 ft", 56, 0.7, 0.5, 800, "Inter Display"),
        chalk_arrow(lx1 - 80, ly - 230, lx0 + 40, ly - 120, 1.4, 0.5),
        chalk_note(lx0 - 40, ly - 260, "turn back every floor", 44, 1.8, 0.6),
    ])
    c.sfx(at(21, 0.0), "sfx_freeze", 0.4)
    # 22: highway speed around that turn = crushed
    c.hide("pair", at(22, 0.0))
    c.key("worker", at(22, 0.0), "b1", 2100, LAND, scale=1.5, fixed=True)
    c.cam(at(22, 0.0), 2100, 840, 1200, "hold")
    c.flash(at(22, 0.3), 0.08)
    c.shake(at(22, 0.3), 0.45, 24)
    c.sfx(at(22, 0.25), "sfx_catch", 0.4)
    c.text(at(22, 0.8), at(23, 0.0), notes([("highway speed", 54, True), ("on a 4 ft turn = crushing g", 46, False)],
                                           120, 250, 0.8))
    # 23: two g -> ten mph per turn
    c.cam(at(23, 0.0), *cam, "hold")
    c.hide("worker", at(23, 0.0))
    c.key("pair", at(23, 0.0), "a2", 1900, LAND)
    c.freeze(at(23, 0.3), at(24, 0.0), [frz(notes([("keep it under 2 g", 54, True),
                                                    ("→ ≈ 10 mph on every turn", 54, True)], 120, 250, 1.2))])
    # 24: super speed is now a jog
    c.hide("pair", at(24, 0.0))
    c.key("hero", at(24, 0.0), "a6", 1344, FL, scale=1.5, fixed=True)
    c.cam(at(24, 0.0), 1344, 1150, 1400, "hold")
    c.text(at(24, 0.3), c.end(), punch(960, 250, "WITH A PASSENGER", "super speed = a jog", 80))
    c.music(0.0, "music_tense", 0.12)
    return c


def window_seq():
    c = new((25, 30), "fire_plate")
    GR = 1380
    c.cast("hero", height=330)
    c.cast("pair", height=330)
    at = c.at
    # 25: the window
    c.cam(0.0, 1800, 700, 1700)
    c.key("hero", 0.0, "a7", 1600, GR)
    c.text(at(25, 0.3), at(26, 0.0), label(110, 170, "THE FASTEST WAY DOWN", "the window", 84))
    # 26: down the wall: free drop 200 ft, brake 2 g for the last 100
    c.hide("hero", at(26, 0.0))
    c.key("pair", at(26, 0.4), "a3", 2010, 470, scale=0.9, fixed=True)
    c.key("pair", at(26, 3.6), "a3", 1975, 1050, scale=0.95, fixed=True, tween="in")
    c.key("pair", at(26, 5.6), "a3", 1960, GR, scale=1.0, fixed=True, tween="out")
    c.draw(at(26, 5.6), at(27, 0.0), fx.dust(1960, GR, size=140, seed=21))
    c.draw(at(26, 5.6), at(27, 0.0), fx.cracks(1960, GR + 4, 220, seed=22), front=False)
    c.cam(at(26, 0.0), 1900, 600, 1500, "hold")
    c.cam(at(26, 3.6), 1900, 1000, 1500, "in")
    c.cam(at(26, 5.6), 1800, 1050, 1600, "out")
    c.text(at(26, 0.5), at(27, 0.0), counter(110, 120, "THE DROP", lambda u: "free fall" if u < 3.2 else "brake 2 g",
                                            "200 ft drop · 100 ft braking"))
    c.sfx(at(26, 0.5), "sfx_fall", 0.3)
    # 27: about five seconds; back up the wall alone
    c.text(at(27, 0.0), at(27, 3.4), punch(960, 300, "≈ 5 s", "like a roller-coaster drop", 72))
    c.hide("pair", at(27, 3.3))
    c.key("hero", at(27, 3.3), "a0", 1960, GR - 40, ang=-90, scale=0.9, fixed=True)
    c.key("hero", at(27, 3.8), "a0", 2010, 470, ang=-90, scale=0.9, fixed=True, tween="snap", smear=True)
    c.key("hero", at(27, 5.3), "a0", 1960, GR - 40, ang=-90, scale=0.9, fixed=True, tween="hold")
    c.key("hero", at(27, 5.8), "a0", 2010, 470, ang=-90, scale=0.9, fixed=True, tween="snap", smear=True)
    c.cam(at(27, 3.2), 1800, 760, 2000, "hold")
    c.speed_lines(at(27, 3.3), at(27, 3.9))
    c.speed_lines(at(27, 5.3), at(27, 5.9))
    c.sfx(at(27, 3.3), "sfx_dash", 0.4)
    c.sfx(at(27, 5.3), "sfx_dash", 0.35)
    # 28: ten people a minute; two at a time -> twenty
    c.hide("hero", at(28, 0.0))
    c.key("pair", at(28, 0.0), "a4", 1500, GR, scale=1.25, fixed=True)
    c.cam(at(28, 0.0), 1500, 1050, 1500, "hold")
    c.text(at(28, 0.3), at(29, 0.0), counter(110, 120, "PEOPLE OUT", lambda u: "10 / min" if u < 4.6 else "20 / min",
                                            "one trip ≈ 6 s"))
    # 29: fifty people on that floor?
    c.text(at(29, 0.1), at(30, 0.0), punch(1250, 330, "50", "people on that floor?", 76))
    # 30: two and a half minutes; lesson two
    c.cam(at(30, 0.0), 1700, 700, 2400, "hold")
    c.text(at(30, 0.1), at(30, 3.0), counter(110, 120, "ALL OUT IN", lambda u: "≈ 2:30", "two at a time"))
    c.hide("pair", at(30, 3.0))
    c.key("hero", at(30, 3.0), "a5", 1500, GR, scale=1.2, fixed=True)
    c.cam(at(30, 3.0), 1500, 1050, 1500, "hold")
    lesson(c, at(30, 3.1), 2, "Their bodies set the limit.")
    c.music(0.0, "music_tense", 0.12)
    return c


# ---------------------------------------------------------------- 31-42: rescue 3, the runaway truck

def truck_seq():
    c = new((31, 42), "highway_plate")
    GR = 1400
    c.cast("hero", height=360)
    c.cast("truck", height=360 * 1.9)
    c.cast("driver", height=900)
    at = c.at
    wide = (1344, 900, 2688)
    c.cam(0.0, *wide)
    # 31: 80,000 lb at 65 mph, no brakes
    rescue(c, at(31, 0.3), 3, "The runaway truck", at(31, 3.6))
    c.key("truck", 0.0, "b4", 3600, GR)
    c.key("truck", at(31, 3.0), "b4", 1700, GR, tween="lin")
    c.speed_lines(at(31, 1.0), at(31, 3.0))
    c.sfx(at(31, 0.8), "sfx_truck", 0.45)
    c.text(at(31, 3.8), at(32, 0.0), notes([("80,000 lb", 76, True), ("65 mph · no brakes", 50, False)],
                                           120, 250, 0.6))
    # 32: > 500 ft to stop even with brakes
    c.freeze(at(32, 0.0), at(33, 0.0), [frz(notes([("with working brakes:", 46, False),
                                                    ("> 500 ft to stop", 70, True)], 120, 250, 0.8))])
    c.sfx(at(32, 0.0), "sfx_freeze", 0.35)
    # 33: step in front; unbreakable is not heavy
    c.key("hero", at(33, 0.0), "b3", 900, GR)
    c.cam(at(33, 0.0), 1250, 1000, 1900, "hold")
    c.text(at(33, 3.4), at(34, 0.0), punch(960, 250, "UNBREAKABLE", "≠ heavy", 96))
    # 34-35: 200 lb vs 400x heavier
    c.text(at(34, 0.0), at(35, 0.0), notes([("you:  ≈ 200 lb", 60, True), ("truck:  80,000 lb", 60, True)],
                                           120, 250, 0.7))
    c.freeze(at(35, 0.6), at(36, 0.0), [frz(notes([("ordinary shoes push ≈ your weight", 46, False),
                                                    ("truck = 400 × heavier", 66, True)], 120, 250, 1.4))])
    # 36: shoved along for more than ten miles
    c.hide("hero", at(36, 0.0))
    c.key("hero", at(36, 0.0), "b2", 2000, GR)
    c.key("truck", at(36, 0.0), "b4", 2780, GR)
    c.key("hero", at(36, 4.4), "b2", 330, GR, tween="lin")
    c.key("truck", at(36, 4.4), "b4", 1110, GR, tween="lin")
    c.cam(at(36, 0.0), 1838, 1000, 1700, "hold")
    c.cam(at(36, 4.4), 850, 1000, 1700, "lin")
    c.sfx(at(36, 0.0), "sfx_scrape", 0.45)
    c.draw(at(36, 0.0), at(37, 0.0), fx.gouge(lambda u: (2000 - (2000 - 330) * min(1.0, u / 4.4), GR - 6), 4.4,
                                              seed=31), front=False)
    c.text(at(36, 0.6), at(37, 0.0), punch(1300, 300, "> 10 miles", "before it stops", 70))
    # 37: super grip; think about the driver (cutaway)
    c.key("truck", at(37, 0.0), "b4", 1700, GR)
    c.key("hero", at(37, 0.0), "b3", 900, GR)
    c.cam(at(37, 0.0), 1250, 1000, 1900, "hold")
    c.text(at(37, 0.2), at(37, 2.4), label(110, 170, "+ SUPER GRIP", "push as hard as you like", 70))
    c.key("driver", at(37, 2.5), "b5", 1344, 1250)
    c.hide("truck", at(37, 2.5))
    c.hide("hero", at(37, 2.5))
    c.cam(at(37, 2.5), 1344, 820, 1300, "hold")
    # 38: dead stop in 3 ft -> ~48 g
    c.hide("driver", at(38, 0.0))
    c.key("hero", at(38, 0.0), "b3", 900, GR)
    c.key("truck", at(38, 0.0), "b4", 2600, GR)
    c.key("truck", at(38, 0.5), "b4", 1700, GR, tween="in")
    c.cam(at(38, 0.0), 1250, 1000, 1900, "hold")
    c.flash(at(38, 0.5), 0.12)
    c.shake(at(38, 0.5), 0.6, 36)
    c.sfx(at(38, 0.45), "sfx_crash", 0.5)
    c.draw(at(38, 0.5), at(39, 0.0), fx.cracks(930, GR + 6, 420, seed=32), front=False)
    c.draw(at(38, 0.5), at(39, 0.0), fx.debris(960, GR, n=34, power=1.3, seed=33, spread=(190, 330)))
    c.draw(at(38, 0.5), at(39, 0.0), fx.sparks(1050, GR - 120, n=40, life=0.6, seed=34, direction=300, cone=70))
    c.draw(at(38, 0.5), at(39, 0.0), fx.dust(1000, GR, size=260, life=2.2, seed=35))
    c.freeze(at(38, 1.0), at(39, 0.0), [
        scrim(500, 420, 700, 400),
        chalk_note(140, 330, "stop in 3 ft", 56, 0.2, 0.5),
        chalk_note(140, 450, "≈ 48 g", 130, 0.8, 0.4, 800, "Inter Display"),
    ])
    # 39: worse than car crash tests (wall at up to 35 mph)
    c.text(at(39, 0.0), at(40, 0.0), board(lambda u: (
        overlay.sketch_paths([[(300, 760), (1100, 760)], [(1100, 520), (1100, 800)], [(1100, 520), (1160, 520)],
                              [(1160, 520), (1160, 800)]], (u - 0.2) / 1.0)
        + overlay.chalk_text(300, 300, "crash tests: a concrete wall", 50, (u - 0.8) / 0.6)
        + overlay.chalk_text(300, 400, "at up to 35 mph", 80, (u - 1.6) / 0.5, 800, "Inter Display")
        + overlay.chalk_text(300, 920, "your stop would be worse", 50, (u - 3.0) / 0.6))))
    # 40: the boring heroic move: brake over ~300 ft
    c.key("truck", at(40, 0.0), "b4", 2400, GR)
    c.key("hero", at(40, 0.0), "b3", 1600, GR)
    c.key("truck", at(40, 8.0), "b4", 1500, GR, tween="out")
    c.key("hero", at(40, 8.0), "b3", 700, GR, tween="out")
    c.draw(at(40, 0.0), at(41, 0.0), fx.gouge(lambda u: (1600 - 900 * (1 - (1 - min(1.0, u / 8.0)) ** 2), GR - 6), 8.0,
                                              seed=36), front=False)
    c.cam(at(40, 0.0), 1738, 1000, 1900, "hold")
    c.cam(at(40, 8.0), 1100, 1000, 1900, "out")
    c.text(at(40, 0.3), at(41, 0.0), counter(110, 120, "BRAKING OVER ≈ 300 FT",
                                            lambda u: f"{max(0, 65 * (1 - min(1, u / 8.0)) ** 2):.0f} mph",
                                            "≈ a car's emergency stop"))
    # 41: feels like slamming on the brakes
    c.key("driver", at(41, 0.0), "b6", 1344, 1250)
    c.hide("truck", at(41, 0.0))
    c.hide("hero", at(41, 0.0))
    c.cam(at(41, 0.0), 1344, 820, 1300, "hold")
    c.text(at(41, 0.3), at(42, 0.0), label(110, 170, "IN THE CAB", "hard braking. nothing worse.", 66))
    # 42: lesson three
    c.hide("driver", at(42, 0.0))
    c.key("hero", at(42, 0.0), "b7", 900, GR)
    c.key("truck", at(42, 0.0), "b4", 1700, GR)
    c.cam(at(42, 0.0), 1100, 1000, 1700, "hold")
    lesson(c, at(42, 0.8), 3, "Stopping hard is a crash too.")
    c.music(0.0, "music_tense", 0.12)
    return c


# ---------------------------------------------------------------- 43-56: rescue 4, the bullet

def bullet_seq():
    c = new((43, 56), "night_plate")
    GR = 1420
    c.cast("hero", height=340)
    c.cast("woman", height=330)
    at = c.at
    wide = (1344, 900, 2688)
    c.cam(0.0, *wide)
    rescue(c, at(43, 0.2), 4, "The bullet", at(43, 3.2))
    c.key("woman", 0.0, "c4", 1900, GR)
    c.sfx(at(43, 0.4), "sfx_bang", 0.45)
    c.flash(at(43, 0.4), 0.05)
    c.draw(at(43, 0.42), at(44, 0.0), fx.bullet((150, GR - 230), (1750, GR - 230), 0.35, scale=2.2))
    c.text(at(43, 3.4), at(44, 0.0), counter(110, 120, "PISTOL BULLET", lambda u: "1,200 ft/s", "≈ 360 m/s · a bit faster than sound"))
    # 44: 30 ft in 1/40 s (freeze with the bullet mid-air)
    c.draw(at(44, 0.0), at(45, 0.0), fx.bullet((760, GR - 230), (1750, GR - 230), 2.5, scale=2.6))
    c.freeze(at(44, 0.2), at(45, 0.0), [frz(notes([("30 ft", 70, True), ("in ≈ 1/40 of a second", 50, False)],
                                                   120, 250, 0.8))])
    c.sfx(at(44, 0.2), "sfx_freeze", 0.35)
    # 45: your legs are fast, your brain isn't
    c.key("hero", at(45, 0.0), "c0", 1344, GR, scale=1.6, fixed=True)
    c.hide("woman", at(45, 0.0))
    c.cam(at(45, 0.0), 1344, 1150, 1300, "hold")
    c.text(at(45, 1.4), at(46, 0.0), notes([("legs:  fast", 60, True), ("brain:  not", 60, True)], 120, 250, 1.4))
    # 46: reaction 1/5 s vs bullet 1/40 s (board with bars)

    def bars(u):
        k = min(1.0, max(0.0, (u - 0.6) / 1.2))
        return (overlay.chalk_text(200, 330, "you react:  ≈ 1/5 s", 54, (u - 0.2) / 0.5, 800, "Inter Display")
                + overlay.chalk_line([(200, 400), (200 + 1400 * k, 400)], 1.0, 34, seed=41, rough=False)
                + overlay.chalk_text(200, 610, "bullet:  1/40 s", 54, (u - 2.2) / 0.5, 800, "Inter Display")
                + overlay.chalk_line([(200, 680), (200 + 175 * min(1, max(0, (u - 2.6) / 0.3)), 680)], 1.0, 34,
                                     seed=42, rough=False))
    c.text(at(46, 0.0), at(47, 0.0), board(bars))
    # 47: eight times too slow
    c.text(at(47, 0.0), at(48, 0.0), punch(1480, 200, "8× TOO SLOW", "it's already over.", 76))
    # 48: a brain that runs fast too
    c.key("hero", at(48, 0.0), "c1", 1344, GR, scale=1.6, fixed=True)
    c.text(at(48, 2.5), at(49, 0.0), label(110, 170, "SECOND POWER", "+ a fast brain", 90))
    # 49: the world slows to a crawl
    c.hide("hero", at(49, 0.0))
    c.cam(at(49, 0.0), *wide, "hold")
    c.key("woman", at(49, 0.0), "c4", 1900, GR)
    c.key("hero", at(49, 0.0), "c1", 1000, GR)
    c.draw(at(49, 0.0), at(54, 0.0), fx.bullet((1150, GR - 230), (1600, GR - 230), 60.0, scale=2.4))
    c.sfx(at(49, 0.0), "sfx_slowmo", 0.45)
    c.text(at(49, 1.5), at(50, 0.0), punch(960, 250, "SLOW MOTION", "what do you do?", 72))
    # 50 / 52: the options
    c.text(at(50, 0.0), at(51, 0.0), punch(960, 300, "OPTION 1", "shove them?", 90))
    c.freeze(at(51, 0.0), at(52, 0.0), [frz(notes([("move them 2 ft in 1/40 s", 50, False), ("≈ 200 g", 110, True),
                                                    ("≈ 4× Stapp's ride", 46, False)], 120, 250, 1.4))])
    c.text(at(52, 0.0), at(53, 0.0), punch(960, 300, "OPTION 2", "block it?", 90))
    c.freeze(at(53, 0.0), at(54, 0.0), [frz(notes([("you're a steel plate", 52, True),
                                                    ("ricochets & fragments", 52, True),
                                                    ("hit the people nearby", 46, False)], 120, 250, 1.6))])
    # 54: run alongside, match its speed, close your hand
    c.hide("hero", at(54, 0.0))
    c.key("hero", at(54, 0.0), "c2", 700, GR)
    c.key("hero", at(54, 6.0), "c2", 1150, GR, tween="lin")
    c.speed_lines(at(54, 0.0), at(54, 6.0))
    c.cam(at(54, 0.0), 1000, 1080, 1500, "hold")
    c.cam(at(54, 6.0), 1150, 1080, 1300, "lin")
    c.text(at(54, 0.5), at(55, 0.0), label(110, 170, "OPTION 3", "match its speed, then close your hand", 64))
    # 55: a bang... nobody hurt
    c.flash(at(55, 0.2), 0.08)
    c.sfx(at(55, 0.2), "sfx_bang", 0.5)
    c.text(at(55, 0.2), at(55, 1.6), lambda u, _t: overlay.boom(1000, 560, u, W, H))
    c.key("hero", at(55, 0.4), "c3", 1300, GR, scale=1.3, fixed=True)
    c.cam(at(55, 0.4), 1500, 1050, 1700, "hold")
    c.text(at(55, 1.2), at(56, 0.0), punch(1350, 300, "BANG", "…and nobody gets hurt", 70))
    lesson(c, at(56, 0.3), 4, "Speed needs a fast brain.")
    c.music(0.0, "music_tense", 0.12)
    return c


# ---------------------------------------------------------------- 57-72: rescue 5, the wave (real event; calm)

MAP_CAM = (1344, 760, 2688)
EPI = (1780, 990)                    # off the west coast of northern Sumatra
SRI = (520, 800)
THAI = (2010, 720)


def _water_mask():
    from studio.pipeline.episode import ep
    from studio.whatif.comic import _plate
    a = np.asarray(_plate(str(ep().work / "art"), "map_plate").convert("RGB")).astype(np.int16)
    return (a[..., 2] > a[..., 0] + 40) & (a[..., 2] > a[..., 1] + 5)


def rings(c: Comic, at, until, speed=260.0):
    """Tsunami fronts spreading from the epicentre, drawn only over water."""
    cache = {}

    def f(img, u, _t):
        if "m" not in cache:
            cache["m"] = _water_mask()
        m = cache["m"]
        hgt, wid = m.shape
        yy, xx = np.ogrid[:hgt, :wid]
        d = np.sqrt((xx - EPI[0]) ** 2 + (yy - EPI[1]) ** 2)
        a = np.asarray(img).astype(np.float32)
        for k in range(3):
            r = speed * u - k * 160
            if r <= 0:
                continue
            band = (np.abs(d - r) < 10) & m
            fade = max(0.0, 1 - r / 2200)
            a[band, :3] = a[band, :3] * (1 - 0.75 * fade) + 255 * 0.75 * fade
        img.paste(Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA"))
    c.draw(at, until, f)


def pin(x, y, s, sub="", t=0.0):
    """A map marker (screen space, map camera) with a label."""
    sx, sy = scr(MAP_CAM, x, y)

    def f(u, _t=None):
        u = u - t
        if u <= 0:
            return ""
        k = min(1.0, u / 0.3)
        return (f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{10 + 4 * math.sin(u * 4):.1f}" fill="{overlay.AMBER}" '
                f'opacity="{k:.2f}"/>'
                + overlay.shadowed(overlay.text(sx + 22, sy - 10, s, 40, op=k))
                + (overlay.shadowed(overlay.text(sx + 22, sy + 34, sub, 30, overlay.AMBER, weight=600, family="Inter",
                                                 op=k)) if sub else ""))
    return f


def wave_seq():
    c = new((57, 57), "ocean_plate")
    c.cast("hero", height=300)
    c.cast("lizard", height=300)
    at = c.at
    c.cam(0.0, 1344, 900, 2688)
    c.text(at(57, 0.3), at(57, 4.6), label(110, 170, "RESCUE 5 · THIS ONE REALLY HAPPENED", "The wave", 84))
    c.music(0.0, "music_calm", 0.12)
    return c


def map_seq_1():
    c = new((58, 61), "map_plate")
    at = c.at
    c.cam(0.0, *MAP_CAM)
    c.text(at(58, 0.5), c.end(), pin(*EPI, "26 Dec 2004", "magnitude 9.1"))
    rings(c, at(59, 0.0), c.end())
    c.text(at(59, 0.3), at(60, 0.0), notes([("deep water:", 46, False), ("> 500 mph", 76, True), ("as fast as a jet", 46, False)],
                                           120, 250, 0.7))
    c.text(at(60, 0.5), c.end(), pin(*THAI, "Thailand", "≈ 1.5 – 2 h"))
    c.text(at(60, 2.5), c.end(), pin(*SRI, "Sri Lanka", "≈ 2 – 3 h"))

    def toll(u, _t):
        k = min(1.0, u / 0.6)
        return (f'<rect width="{W}" height="{H}" fill="#04070C" opacity="{0.55 * k:.2f}"/>'
                + overlay.text(760, 880, "the only warning system of its kind: the Pacific", 44, anchor="middle",
                               weight=600, family="Inter", op=k)
                + overlay.text(760, 990, "≈ 228,000 killed or missing", 84, anchor="middle", op=min(1, (u - 2.5) / 0.8)))
    c.text(at(61, 0.0), c.end(), toll)
    c.music(0.0, "music_calm", 0.12)
    return c


def sea_seq():
    c = new((62, 65), "ocean_plate")
    SEA = 1250
    c.cast("hero", height=300)
    c.cast("lizard", height=300)
    at = c.at
    c.cam(0.0, 1344, 900, 2688)
    c.key("hero", 0.0, "a5", 2350, 1030, scale=0.35, fixed=True)
    c.text(at(62, 0.2), at(63, 0.0), label(110, 170, "OUTRUN IT?", "not on land", 84))
    c.hide("hero", at(63, 0.0))
    c.key("lizard", at(63, 0.0), "c6", 400, SEA, scale=1.8, fixed=True)
    c.key("lizard", at(63, 7.5), "c6", 2300, SEA, scale=1.8, fixed=True, tween="lin")
    c.cam(at(63, 0.0), 1344, 1050, 1900, "hold")
    c.text(at(63, 0.5), at(64, 0.0), label(110, 170, "BASILISK LIZARD", "runs on water", 80))
    c.sfx(at(63, 0.3), "sfx_water", 0.35)

    def slap(u):
        return (overlay.chalk_text(160, 330, "a human would need to", 50, (u - 0.2) / 0.5)
                + overlay.chalk_text(160, 460, "slap the water > 65 mph", 80, (u - 1.0) / 0.6, 800, "Inter Display")
                + overlay.chalk_text(160, 600, "with ≈ 15× our muscle power", 60, (u - 3.0) / 0.6, 800,
                                     "Inter Display"))
    c.text(at(64, 0.0), at(65, 0.0), board(slap))
    c.hide("lizard", at(65, 0.0))
    c.key("hero", at(65, 0.0), "c5", 300, SEA)
    c.key("hero", at(65, 2.1), "c5", 2400, SEA, tween="lin", smear=True)
    c.speed_lines(at(65, 0.0), at(65, 2.1))
    c.sfx(at(65, 0.0), "sfx_water", 0.45)
    c.text(at(65, 0.2), c.end(), punch(1300, 300, "FOR YOU", "easy", 90))
    c.music(0.0, "music_calm", 0.12)
    return c


def map_seq_2():
    c = new((66, 67), "map_plate")
    at = c.at
    c.cam(0.0, *MAP_CAM)
    sx0, sy0 = scr(MAP_CAM, *EPI)
    sx1, sy1 = scr(MAP_CAM, *SRI)

    def path(u, _t):
        k = min(1.0, max(0.0, (u - 0.3) / 3.0))
        x, y = sx0 + (sx1 - sx0) * k, sy0 + (sy1 - sy0) * k
        return (overlay.chalk_line([(sx0, sy0), (x, y)], 1.0, 6, seed=51, rough=False)
                + f'<circle cx="{x:.0f}" cy="{y:.0f}" r="14" fill="{overlay.AMBER}"/>'
                + overlay.shadowed(overlay.text(960, 160, "1,000 mph → Sri Lanka in ≈ 1 hour", 62,
                                                anchor="middle", op=min(1, (u - 2.0) / 0.4))))
    c.text(at(66, 0.0), at(67, 0.0), path)
    coasts = [(560, 760, 680, 690), (300, 760, 460, 520), (1960, 620, 2060, 900), (1860, 880, 2000, 1050),
              (1500, 420, 1600, 900)]

    def glow(u, _t):
        out = [overlay.shadowed(overlay.text(960, 160, "coasts: thousands of miles · you: one person", 54,
                                             anchor="middle", op=min(1, u / 0.4)))]
        for k, (x0, y0, x1, y1) in enumerate(coasts):
            a, b = scr(MAP_CAM, x0, y0), scr(MAP_CAM, x1, y1)
            out.append(overlay.chalk_line([a, b], (u - 0.5 - 0.4 * k) / 0.6, 8, seed=60 + k, rough=True))
        return "".join(out)
    c.text(at(67, 0.0), c.end(), glow)
    c.music(0.0, "music_calm", 0.12)
    return c


def shout_seq():
    c = new((68, 69), "ocean_plate")
    c.cast("hero", height=300)
    at = c.at
    c.cam(0.0, 1344, 1050, 1700)
    c.key("hero", 0.0, "c7", 1720, 1250, scale=1.4, fixed=True)
    c.text(at(68, 0.6), at(69, 0.0), notes([("faster than sound:", 50, False), ("you arrive before your voice", 56, True)],
                                           120, 250, 0.8))
    c.flash(at(69, 0.5), 0.08)
    c.shake(at(69, 0.5), 0.6, 18)
    c.sfx(at(69, 0.45), "sfx_sonic", 0.5)
    c.text(at(69, 0.5), at(69, 3.0), lambda u, _t: overlay.boom(1300, 600, u, W, H))
    c.text(at(69, 2.0), c.end(), punch(620, 330, "ALL THEY HEAR", "“thunder”", 90))
    c.music(0.0, "music_calm", 0.12)
    return c


def warn_seq():
    c = new((70, 72), "map_plate")
    at = c.at
    c.cam(0.0, *MAP_CAM)
    sites = [(560, 700), (520, 880), (330, 740), (250, 600), (420, 420), (700, 300), (1000, 120), (1300, 140),
             (1550, 300), (1560, 600), (1600, 860), (1950, 650), (2030, 780), (1880, 880), (1950, 1000), (2080, 1150)]

    def icons(u, _t):
        out = [overlay.shadowed(overlay.text(110, 170, "2006: a first warning system", 54, op=min(1, (u - 0.6) / 0.4)))
               + overlay.shadowed(overlay.text(110, 240, "2011: run by the region's own centres", 54,
                                               op=min(1, (u - 4.2) / 0.4)))]
        for k, (x, y) in enumerate(sites):
            sx, sy = scr(MAP_CAM, x, y)
            on = u - 1.0 - 0.25 * k
            if on > 0:
                p = 1 + 0.25 * math.sin(u * 5 + k)
                out.append(f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{12 * p:.1f}" fill="{overlay.AMBER}" '
                           f'opacity="{min(1.0, on / 0.3):.2f}"/>')
        return "".join(out)
    c.text(at(70, 0.0), at(71, 0.0), icons)

    def all_at_once(u, _t):
        out = []
        for x, y in sites:
            sx, sy = scr(MAP_CAM, x, y)
            r = 12 + (u * 60) % 90
            out.append(f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{r:.1f}" fill="none" stroke="{overlay.AMBER}" '
                       f'stroke-width="4" opacity="{max(0.0, 1 - ((u * 60) % 90) / 90):.2f}"/>'
                       f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="12" fill="{overlay.AMBER}"/>')
        out.append(overlay.shadowed(overlay.text(960, 980, "sensors · alert networks · a whole coastline at once",
                                                 50, anchor="middle", op=min(1, u / 0.5))))
        return "".join(out)
    c.text(at(71, 0.0), at(72, 0.0), all_at_once)
    c.sfx(at(71, 0.3), "sfx_alert", 0.35)
    c.text(at(72, 0.0), c.end(), lambda u, _t: (f'<rect width="{W}" height="{H}" fill="#04070C" '
                                                 f'opacity="{0.5 * min(1, u / 0.4):.2f}"/>'
                                                 + overlay.text(W / 2, 560, "No runner could ever do that.", 80,
                                                                anchor="middle", op=min(1, u / 0.4))))
    c.music(0.0, "music_calm", 0.12)
    return c


# ---------------------------------------------------------------- 73-76: ending + end screen

def ending_seq():
    c = new((73, 76), "tower_plate", fade_out=0.8)
    GR = 1362
    c.cast("hero", height=405)
    c.cast("cleaner", height=397)
    at = c.at
    c.cam(0.0, 1344, 1000, 1700)
    c.key("hero", 0.0, "hero7", 1000, GR)
    c.text(at(73, 0.3), at(74, 0.0), label(110, 170, "THE HARD PART", "isn't getting there", 84))
    items = ["stop them gently", "turn them softly", "think fast enough", "reach everyone at once"]
    c.text(at(74, 0.0), at(75, 0.0), notes([(s, 60, True) for s in items], 1060, 250, 1.4))
    c.sfx(at(74, 0.1), "sfx_chalk", 0.3)
    c.key("cleaner", at(75, 0.0), "cleaner0", 1700, GR)
    c.text(at(75, 0.2), at(76, 0.0), punch(560, 150, "YOU", "unbreakable"))
    c.text(at(75, 1.6), at(76, 0.0), punch(1390, 150, "THEM", "not.", 96))
    c.text(at(76, 0.0), at(76, 5.0), label(110, 170, "YOUR TURN", "which rescue would you try first?", 66))

    def end_screen(u, _t):
        k = min(1.0, u / 0.5)
        box = ('<rect x="{x}" y="300" width="760" height="428" rx="18" fill="#000" opacity="{o:.2f}" '
               'stroke="#F2EEE4" stroke-width="4"/>')
        return (f'<rect width="{W}" height="{H}" fill="#06080C" opacity="{0.78 * k:.2f}"/>'
                + box.format(x=140, o=0.55 * k) + box.format(x=1020, o=0.55 * k)
                + overlay.text(W / 2, 200, "watch next", 64, anchor="middle", op=k)
                + overlay.text(W / 2, 880, "subscribe for the next “what if”", 44, overlay.AMBER, "middle",
                               600, "Inter", op=k))
    c.text(at(76, 5.0), c.end(), end_screen)
    c.hide("hero", at(76, 5.0))
    c.hide("cleaner", at(76, 5.0))
    c.sfx(at(76, 5.0), "sfx_hit", 0.35)
    c.music(0.0, "music_main", 0.13)
    return c


def build_all():
    return [title_seq(), fall_seq(), fire_seq(), stairs_seq(), window_seq(), truck_seq(), bullet_seq(), wave_seq(),
            map_seq_1(), sea_seq(), map_seq_2(), shout_seq(), warn_seq(), ending_seq()]
