"""Short: you can run on water — here's the catch (vertical motion comic, art from whatif_super_speed).

Times: w(x) = x seconds into the spoken narration + the 0.2 s intro. Numbers on screen (script.md, parent
factcheck row 27, Minetti et al. 2012 citing Glasheen & McMahon 1996): a human would need to slap the water at
> 30 m/s (67 mph) with ≈ 15× the available muscle power. Retention rules: the run on water is the first frame; no
numbers in the first 5 s; the end bursts back into the opening run. No tsunami images here.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from studio.whatif import overlay
from studio.whatif.comic import _plate, label
from studio.whatif.shorts import HERO, W, amber, cam_on, chalk, full_video, new, title, vboard

SEA = 1300                        # the water surface under the runner (plate px)
CH = overlay.CHALK


def w(x: float) -> float:
    return x + 0.2


def spray(x0: float, x1: float, dur: float, y: float = SEA, seed: int = 5, every: float = 0.06):
    """Droplets kicked up behind a runner going x0 -> x1 over `dur` s (world px), plus foam slaps on the surface."""
    def f(img: Image.Image, u: float, _t: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        sgn = 1 if x1 >= x0 else -1
        n = int(min(u, dur) / every) + 1
        for k in range(n):
            te = k * every
            age = u - te
            if age < 0 or age > 0.9:
                continue
            ex = x0 + (x1 - x0) * min(1.0, te / dur)
            r = random.Random(seed * 1000 + k)
            fade = 1 - age / 0.9
            d.ellipse([ex - 70 - 60 * age, y - 10, ex + 70 + 60 * age, y + 16], outline=(240, 250, 255, int(160 * fade)),
                      width=5)
            for _j in range(6):
                vx, vy = -sgn * r.uniform(80, 320), -r.uniform(380, 720)
                px, py = ex + vx * age, y + vy * age + 1100 * age * age
                if py > y + 6:
                    continue
                rr = r.uniform(5, 13)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(236, 248, 255, int(220 * fade)))
    return f


def submerge(x: float, half: float = 260):
    """Water in front of a sinking figure: the plate's own water re-drawn over everything below the surface."""
    def f(img: Image.Image, _u: float, _t: float) -> None:
        from studio.whatif import render
        pl = _plate(str(render.library("art")), "ocean_plate_v")
        box = (int(x - half), SEA - 4, int(x + half), pl.height)
        img.alpha_composite(pl.crop(box), (box[0], box[1]))
    return f


def ring(x: float, y: float = SEA):
    def f(img: Image.Image, u: float, _t: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        for j in range(3):
            k = u * 1.2 - j * 0.25
            if 0 < k < 1:
                rx = 60 + 260 * k
                d.ellipse([x - rx, y - rx * 0.12, x + rx, y + rx * 0.12], outline=(240, 250, 255, int(220 * (1 - k))),
                          width=6)
    return f


def stick(x, y, s, p, drop=0.0):
    """A plain chalk stick figure (not the hero) standing at (x, y) screen px; `drop` px pulls it down."""
    y += drop
    paths = [[(x, y - 150 * s), (x, y - 60 * s)], [(x, y - 60 * s), (x - 40 * s, y)], [(x, y - 60 * s), (x + 40 * s, y)],
             [(x - 55 * s, y - 120 * s), (x, y - 130 * s), (x + 55 * s, y - 120 * s)]]
    head = (f'<circle cx="{x}" cy="{y - 180 * s:.0f}" r="{30 * s:.0f}" fill="none" stroke="{CH}" stroke-width="6" '
            f'opacity="{min(1.0, max(0.0, p * 2 - 1)):.2f}"/>')
    return overlay.sketch_paths(paths, p, 6, 91) + head


def slap_board(u):
    """The basilisk's trick, timed to the narration from 6.9 s: slap down, the water pushes back up, the foot
    leaves before the air pocket closes."""
    sx, sy = 540, 760                                            # the water surface (screen px)
    out = overlay.chalk_line([(90, sy), (990, sy)], u / 0.4, 7, seed=11, rough=True)
    # foot: down (0.3-0.8), stays (to 3.6), lifts out (3.6-4.4)
    down = min(1.0, max(0.0, (u - 0.3) / 0.5))
    up = min(1.0, max(0.0, (u - 3.6) / 0.8))
    fy = sy - 170 + 230 * down - 330 * up
    out += f'<ellipse cx="{sx}" cy="{fy:.0f}" rx="95" ry="34" fill="none" stroke="{CH}" stroke-width="7"/>'
    out += overlay.chalk_line([(sx - 20, fy - 34), (sx - 50, fy - 200)], 1.0, 7, seed=12, rough=False)
    # air pocket under the foot: opens with the slap, stays open, closes after the foot is out (5.0-5.7)
    if u > 0.7:
        o = min(1.0, (u - 0.7) / 0.4) * (1 - min(1.0, max(0.0, (u - 5.0) / 0.7)))
        if o > 0:
            depth = 230 * o
            out += (f'<path d="M{sx - 110},{sy} Q{sx - 100},{sy + depth} {sx},{sy + depth} Q{sx + 100},{sy + depth} '
                    f'{sx + 110},{sy}" fill="#0E1714" stroke="{CH}" stroke-width="6"/>')
    out += chalk(90, 320, "SLAP ↓", 92, u, 0.3, 0.3, bold=True)
    if u > 1.8:
        out += overlay.chalk_arrow(sx + 170, sy + 160, sx + 170, sy - 40, (u - 1.8) / 0.4, seed=13)
        out += amber(sx + 195, sy + 60, "water pushes", 42, u, 2.0) + amber(sx + 195, sy + 112, "back up", 42, u, 2.1)
    if u > 3.4:
        out += chalk(90, 1060, "foot out…", 64, u, 3.6, 0.4, bold=True)
        out += chalk(90, 1130, "before the hole closes", 48, u, 4.6, 0.5)
    return out


def build_seq():
    c = new((1, 10), "ocean_plate")
    c.cast("hero", height=HERO)
    c.cast("lizard", height=HERO, ref="c6")

    # 0-3: COLD OPEN — you, sprinting across open water
    c.key("hero", 0.0, "c5", 500, SEA)
    c.key("hero", w(3.0), "c5", 1500, SEA, tween="lin", smear=True)
    c.cam(0.0, *cam_on(560, SEA))
    c.cam(w(3.0), *cam_on(1540, SEA), "lin")
    c.speed_lines(0.0, w(3.0))
    c.draw(0.0, w(3.6), spray(500, 1500, w(3.0), seed=5))
    c.sfx(0.0, "sfx_water", 0.5)
    c.text(w(0.1), w(1.7), title("YOU CAN", "run on water", 230, 96))
    c.text(w(1.7), w(3.0), title("HERE'S", "the catch", 230, 96))

    # 3-6.8: the basilisk already does it
    c.hide("hero", w(3.0))
    c.key("lizard", w(3.0), "c6", 300, SEA, scale=0.9, fixed=True)
    c.key("lizard", w(6.8), "c6", 1300, SEA, scale=0.9, fixed=True, tween="lin")
    c.cam(w(3.0), *cam_on(420, SEA), "hold")
    c.cam(w(6.8), *cam_on(1260, SEA), "lin")
    c.draw(w(3.0), w(7.4), spray(300, 1300, w(6.8) - w(3.0), seed=6, every=0.05))
    c.sfx(w(3.1), "sfx_water", 0.35)
    c.text(w(4.9), w(6.8), label(70, 200, "BASILISK LIZARD", "it really does this", 70))

    # 6.9-13.2: chalkboard — how it works
    c.text(w(6.7), w(13.2), vboard(slap_board))
    c.sfx(w(7.0), "sfx_hit", 0.4)
    c.sfx(w(12.4), "sfx_chalk", 0.3)

    # 13.2-16.6: could you? — freeze on the lizard, a chalk human beside it
    c.key("lizard", w(13.2), "c6", 1300, SEA, scale=0.9, fixed=True)
    c.key("lizard", w(13.8), "c6", 1460, SEA, scale=0.9, fixed=True, tween="lin")
    c.cam(w(13.2), *cam_on(1500, SEA), "hold")
    c.freeze(w(13.8), w(16.6), [
        lambda ctx, u: stick(840, 980, 1.3, u / 0.8),
        lambda ctx, u: chalk(810, 700, "?", 140, u, 0.4, 0.2, bold=True),
        lambda ctx, u: chalk(70, 300, "could you?", 80, u, 0.0, 0.35, bold=True),
        lambda ctx, u: chalk(70, 400, "scientists did the math", 50, u, 1.2, 0.5),
        lambda ctx, u: overlay.sketch_paths([[(70 + 40 * k, 470 + (18 if k % 2 else 0)) for k in range(11)]],
                                            (u - 1.9) / 0.6, 5, 21),
    ])
    c.sfx(w(13.8), "sfx_freeze", 0.4)

    # 16.6-20.4: your feet must hit the water faster than a highway car
    c.hide("lizard", w(16.6))
    c.key("hero", w(16.6), "c5", 400, SEA)
    c.key("hero", w(20.4), "c5", 1400, SEA, tween="lin", smear=True)
    c.cam(w(16.6), *cam_on(460, SEA), "hold")
    c.cam(w(20.4), *cam_on(1440, SEA), "lin")
    c.speed_lines(w(16.6), w(20.4))
    c.draw(w(16.6), w(21.0), spray(400, 1400, w(20.4) - w(16.6), seed=7))
    c.sfx(w(16.7), "sfx_water", 0.45)

    def feet(u, _t):
        body = [(0, 40), (10, 12), (60, 12), (80, 0), (140, 0), (165, 22), (200, 26), (205, 40), (0, 40)]
        s, x, y = 1.5, 70, 360
        car = overlay.sketch_paths([[(x + a * s, y + b * s) for a, b in body]], (u - 1.2) / 0.6, 6, 31)
        return (chalk(70, 260, "each foot slap:", 56, u, 0.0, 0.3, bold=True) + car
                + chalk(420, 420, "← faster than this", 50, u, 1.6))
    c.text(w(16.6), w(20.4), feet)

    # 20.4-24.6: freeze — and fifteen times the muscle power
    c.freeze(w(20.4), w(24.6), [
        lambda ctx, u: chalk(130, 260, "power needed", 56, u, 0.0, 0.3, bold=True),
        lambda ctx, u: chalk(130, 350, "your muscles", 40, u, 0.6),
        lambda ctx, u: f'<rect x="130" y="370" width="{min(60.0, 60 * max(0.0, (u - 0.8) / 0.3)):.0f}" '
                       f'height="44" fill="{CH}"/>',
        lambda ctx, u: chalk(130, 460, "needed", 40, u, 1.4),
        lambda ctx, u: f'<rect x="130" y="480" width="{min(820.0, 820 * max(0.0, (u - 1.6) / 1.2)):.0f}" '
                       f'height="44" fill="{overlay.AMBER}"/>',
        lambda ctx, u: chalk(800, 455, "× 15", 64, u, 2.8, 0.3, bold=True),
    ])
    c.sfx(w(20.4), "sfx_freeze", 0.4)

    # 24.6-26.9: a normal person? splash.
    c.hide("hero", w(24.6))
    c.cam(w(24.6), *cam_on(1100, SEA), "hold")

    def normal(u, _t):
        drop = 0.0 if u < 1.4 else min(1.0, (u - 1.4) / 0.25) * 260
        clip = ('<clipPath id="above"><rect x="0" y="0" width="1080" height="1110"/></clipPath>'
                f'<g clip-path="url(#above)">{stick(540, 1110, 1.6, u / 0.6, drop)}</g>')
        out = clip + chalk(70, 260, "a normal person?", 66, u, 0.0, 0.3, bold=True)
        if u > 1.4:
            k = min(1.0, (u - 1.4) / 0.5)
            for j in range(9):
                a = math.radians(200 + j * 17.5)
                r0, r1 = 40 + 60 * k, 90 + 170 * k
                out += (f'<line x1="{540 + r0 * math.cos(a):.0f}" y1="{1100 + r0 * math.sin(a):.0f}" '
                        f'x2="{540 + r1 * math.cos(a):.0f}" y2="{1100 + r1 * math.sin(a):.0f}" stroke="{CH}" '
                        f'stroke-width="7" stroke-linecap="round" opacity="{1 - 0.6 * k:.2f}"/>')
            out += amber(W / 2, 420, "SPLASH", 120, u, 1.5, anchor="middle")
        return out
    c.text(w(24.6), w(26.9), normal)
    c.draw(w(26.0), w(27.5), ring(1100))
    c.sfx(w(26.0), "sfx_water", 0.55)

    # 26.9-31.7: with super speed it's easy — slap, slap, slap, across the bay
    c.key("hero", w(26.9), "c5", 300, SEA)
    c.key("hero", w(30.2), "c5", 1500, SEA, tween="lin", smear=True)
    c.key("hero", w(31.7), "c5", 2500, SEA, tween="lin", smear=True)
    c.cam(w(26.9), *cam_on(360, SEA), "hold")
    c.cam(w(30.2), *cam_on(1540, SEA), "lin")
    c.cam(w(31.7), *cam_on(2380, SEA, vw=1000), "lin")
    c.speed_lines(w(26.9), w(31.7))
    c.draw(w(26.9), w(32.3), spray(300, 2500, w(31.7) - w(26.9), seed=8))
    c.text(w(27.0), w(28.6), title("WITH SUPER SPEED", "easy", 230, 110))
    for k, (tt, x) in enumerate([(28.68, 260), (29.5, 640), (29.68, 420)]):
        c.text(w(tt), w(tt) + 0.9, lambda u, _t, x=x, k=k: amber(x, 300 + 90 * k, "SLAP!", 96, u, 0.0, anchor="middle"))
        c.sfx(w(tt), "sfx_water" if k == 0 else "sfx_hit", 0.35)
    c.text(w(30.1), w(31.7), lambda u, _t: chalk(W / 2, 300, "all the way across the bay", 56, u, 0.0, 0.5,
                                                 bold=True, anchor="middle"))

    # 31.7-34.8: one rule: never stop — you stop, and you sink
    c.key("hero", w(31.8), "hero7", 1500, SEA)
    c.cam(w(31.8), *cam_on(1500, SEA), "hold")
    c.text(w(31.9), w(33.4), title("THERE'S JUST", "one rule", 230, 100))
    c.text(w(33.4), w(34.8), title("RULE #1", "never stop", 230, 110))
    c.key("hero", w(33.9), "hero6", 1500, SEA)
    c.key("hero", w(34.25), "hero6", 1500, SEA + HERO * 1.1, tween="in")
    c.key("hero", w(34.8), "hero6", 1500, SEA + HERO * 0.82, tween="out")
    c.draw(w(33.9), w(38.2), submerge(1500))
    c.draw(w(34.1), w(35.6), ring(1500))
    c.sfx(w(34.1), "sfx_water", 0.55)

    # 34.8-38.2: the full video (you try to outrun a tsunami) — you bob there, head out of the water
    c.text(w(34.9), w(38.1), full_video(250))
    c.text(w(36.2), w(38.1), lambda u, _t: amber(W / 2, 470, "→ outrun a tsunami?", 50, u, 0.0, anchor="middle"))

    # 38.2-end: keep your feet moving — you burst out and run again (back into the opening)
    c.key("hero", w(38.2), "c5", 1500, SEA)
    c.key("hero", c.end(), "c5", 2350, SEA, tween="lin", smear=True)
    c.cam(w(38.2), *cam_on(1540, SEA), "hold")
    c.cam(c.end(), *cam_on(2390, SEA), "lin")
    c.speed_lines(w(38.2), c.end())
    c.draw(w(38.2), w(38.9), ring(1500))
    c.draw(w(38.2), c.end(), spray(1500, 2350, 2.3, seed=9))
    c.sfx(w(38.25), "sfx_water", 0.5)
    c.text(w(38.3), c.end(), lambda u, _t: chalk(W / 2, 300, "keep your feet moving", 64, u, 0.0, 0.4, bold=True,
                                                 anchor="middle"))
    c.music(0.0, "music_main", 0.12)
    return c


def build(size):
    return [build_seq()]
