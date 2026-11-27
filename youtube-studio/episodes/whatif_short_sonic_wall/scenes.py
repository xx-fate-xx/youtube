"""Short: unbreakable bones vs the sound barrier (vertical motion comic, art from whatif_super_speed).

Times are seconds of the aligned narration (projects/whatif_short_sonic_wall/audio/narration_words.json).
Numbers on screen: script.md — 767 mph (343 m/s) -> 0 in ~1.5 ft (0.5 m): a = v^2 / 2d = 117,650 m/s^2 ~ 12,000 g;
Stapp, Sonic Wind No. 1, 10 Dec 1954, 632 mph, 46.2 g (Smithsonian NASM); highest known survived crash ~ 214 g
(Kenny Bräck, 2003), said as "about 200 g". Stapp is a plain chalk stick figure (no likeness).
"""

from __future__ import annotations

import math

from PIL import Image

from studio.whatif import fx, overlay
from studio.whatif.comic import ease
from studio.whatif.shorts import (
    GROUND,
    HERO,
    amber,
    cam_on,
    chalk,
    full_video,
    hud,
    new,
    title,
    vboard,
    wall,
)

AMB = overlay.AMBER


def math_board(u):
    return (chalk(90, 380, "767 mph → 0", 96, u, 0.4, 0.5, bold=True)
            + chalk(90, 470, "speed of sound · 343 m/s", 40, u, 1.0)
            + chalk(90, 600, "in ≈ 1.5 ft  (0.5 m)", 66, u, 2.6, 0.5, bold=True)
            + chalk(90, 730, "a = v² ÷ 2d", 60, u, 3.6, 0.5)
            + chalk(90, 900, "≈ 12,000 g", 150, u, 4.4, 0.4, bold=True))


BONE, BRAIN, BRAIN_D, HEART, HEART_D, LIVER, LIVER_D = ("#F4F1E8", "#F2A7B8", "#B9586F", "#D9404F", "#8E1F2C",
                                                        "#A2473A", "#5E2219")
WALL_X = 800                     # the wall the body hit (screen px)


def _op(u, at, d=0.3):
    return max(0.0, min(1.0, (u - at) / d))


def _squish(shape: str, front: float, cy: float, dx: float, sq: float, wob: float) -> str:
    """Move an organ forward by dx; squash it against the bone in front (anchored at `front`) by sq (0-1);
    wob = soft jelly wobble."""
    sx = (1 - 0.18 * sq) * (1 + wob)
    sy = (1 + 0.12 * sq) * (1 - wob)
    return (f'<g transform="translate({dx:.1f},0) translate({front:.1f},{cy:.1f}) scale({sx:.3f},{sy:.3f}) '
            f'translate({-front:.1f},{-cy:.1f})">{shape}</g>')


def _brain(op):
    cx, cy, rx, ry = 520, 450, 150, 112
    g = [f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{BRAIN}" stroke="{BRAIN_D}" stroke-width="6"/>']
    for j, dy in enumerate((-70, -32, 6, 44, 80)):                      # folds (gyri), kept inside the outline
        half = rx * (1 - (dy / ry) ** 2) ** 0.5 * 0.82
        pts = []
        for k in range(15):
            x = cx - half + 2 * half * k / 14
            pts.append(f"{x:.0f},{cy + dy + 9 * (-1) ** (k + j):.0f}")
        g.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{BRAIN_D}" stroke-width="5" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
    g.append(f'<path d="M{cx - 40},{cy + ry - 8} Q{cx - 10},{cy + ry + 40} {cx + 30},{cy + ry + 60}" '
             f'fill="none" stroke="{BRAIN_D}" stroke-width="22" stroke-linecap="round"/>')        # brain stem
    return f'<g opacity="{op:.2f}">' + "".join(g) + "</g>"


def _heart(op):
    # a cartoon heart with the aortic arch, tilted like a real heart (apex down-left)
    body = "M0,-38 C26,-74 84,-52 74,-4 C66,34 26,58 -2,84 C-26,58 -66,34 -74,-4 C-84,-52 -26,-74 0,-38 Z"
    return (f'<g opacity="{op:.2f}" transform="translate(620,850) rotate(-18)">'
            f'<path d="M-8,-44 C-10,-92 46,-104 52,-58" fill="none" stroke="{HEART_D}" stroke-width="20" '
            f'stroke-linecap="round"/>'
            f'<path d="{body}" fill="{HEART}" stroke="{HEART_D}" stroke-width="6"/>'
            f'<path d="M-40,-30 Q-50,0 -30,26" fill="none" stroke="#F08A95" stroke-width="9" stroke-linecap="round"/>'
            "</g>")


def _liver(op):
    return (f'<g opacity="{op:.2f}"><path d="M470,1000 Q560,950 700,965 Q745,972 735,1010 Q700,1060 600,1070 '
            f'Q500,1072 470,1040 Z" fill="{LIVER}" stroke="{LIVER_D}" stroke-width="6"/>'
            f'<path d="M560,975 Q590,1010 575,1062" fill="none" stroke="{LIVER_D}" stroke-width="4"/></g>')


def _skull(p):
    """Side view of a skull facing right (towards the wall), fading in as p goes 0 -> 1."""
    if p <= 0:
        return ""
    o = min(1.0, p / 0.6)
    st = f'fill="none" stroke="{BONE}" stroke-linejoin="round" stroke-linecap="round"'
    teeth = "".join(f'<rect x="{714 + 14 * k}" y="600" width="11" height="18" rx="3" fill="{BONE}"/>' for k in range(5))
    return (f'<g opacity="{o:.2f}">'
            f'<path d="M412,612 C342,560 318,470 330,400 C352,300 452,248 566,252 C684,258 770,330 772,436 '
            f'L772,470 L786,500 L776,518 L792,572 L770,584 L776,598 L712,600" {st} stroke-width="15"/>'
            f'<path d="M778,624 L772,664 Q750,696 682,694 L624,686 Q592,650 600,606" {st} stroke-width="15"/>'
            f'<circle cx="716" cy="514" r="30" {st} stroke-width="9"/>'
            f'<path d="M760,540 L748,566" {st} stroke-width="7"/>' + teeth + "</g>")


def _ribcage(p):
    if p <= 0:
        return ""
    o = min(1.0, p / 0.6)
    g = [f'<g opacity="{o:.2f}">']
    for k in range(9):                                                           # vertebrae
        g.append(f'<rect x="372" y="{760 + 40 * k}" width="46" height="32" rx="9" fill="{BONE}"/>')
    g.append(f'<rect x="752" y="770" width="26" height="200" rx="12" fill="{BONE}"/>')    # sternum
    for k in range(6):                                                           # ribs: spine -> sternum
        y0 = 770 + 34 * k
        g.append(f'<path d="M418,{y0} C520,{y0 - 30} 690,{y0 - 10} 754,{y0 + 30}" fill="none" stroke="{BONE}" '
                 f'stroke-width="11" stroke-linecap="round" opacity="0.92"/>')
    g.append("</g>")
    return "".join(g)


def _lead(y, x1, label, u, at):
    """A label at the left with a chalk leader line to the organ."""
    if u < at:
        return ""
    return (amber(70, y + 15, label, 46, u, at, weight=800)
            + overlay.chalk_line([(250, y), (x1, y)], (u - at - 0.1) / 0.3, 4, seed=int(y), rough=False))


def _burst(x, y, u, at):
    if u < at or u > at + 0.9:
        return ""
    k = (u - at) / 0.9
    out = []
    for j in range(7):
        a = -1.2 + j * 0.4
        r0, r1 = 20 + 40 * k, 50 + 70 * k
        out.append(f'<line x1="{x + r0 * math.cos(a):.0f}" y1="{y + r0 * math.sin(a):.0f}" '
                   f'x2="{x + r1 * math.cos(a):.0f}" y2="{y + r1 * math.sin(a):.0f}" stroke="{AMB}" '
                   f'stroke-width="8" stroke-linecap="round" opacity="{1 - k:.2f}"/>')
    return "".join(out)


def xray_board(u):
    """Cross-sections facing the wall: skull + brain, ribcage + heart + liver. The bones stop; the soft organs
    wobble, keep going and squash against the skull and ribs (timed to the narration from 15.43 s)."""
    out = '<g transform="translate(40,80) scale(0.93)">'
    out += f'<rect x="{WALL_X}" y="300" width="60" height="810" fill="#6C6A66"/>'
    out += overlay.chalk_line([(WALL_X, 300), (WALL_X, 1110)], u / 0.4, 8, seed=71, rough=False)
    for k in range(9):                                                           # wall hatching
        out += overlay.chalk_line([(WALL_X + 4, 330 + 90 * k), (WALL_X + 56, 300 + 90 * k)], (u - 0.2) / 0.4, 4,
                                  seed=72 + k, rough=False)
    go = ease((u - 4.4) / 0.9)                                                   # organs keep going ...
    sq = ease((u - 5.3) / 0.25)                                                  # ... and hit the bone
    wob = (0.04 * math.sin(u * 14) * (1.0 if 3.6 < u < 4.5 else 0.0)
           + (0.03 * math.sin(u * 20) * max(0.0, 1 - (u - 5.3) / 0.8) if u > 5.3 else 0.0))
    # organs first, bones over them (the bones are in front, as in an x-ray)
    if u >= 3.1:
        out += _squish(_brain(_op(u, 3.1)), 670, 450, 68 * go, sq, wob)
    if u >= 1.8:
        out += _squish(_heart(_op(u, 1.8)), 694, 850, 52 * go, sq, wob)
    if u >= 2.4:
        out += _squish(_liver(_op(u, 2.4)), 740, 1010, 34 * go, sq, wob)
    out += _skull(u / 0.8) + _ribcage((u - 0.4) / 0.8)
    out += _lead(440, 368 + 68 * go, "BRAIN", u, 3.1)
    out += _lead(850, 545 + 52 * go, "HEART", u, 1.8)
    out += _lead(1030, 465 + 34 * go, "LIVER", u, 2.4)
    out += _burst(772, 440, u, 5.3) + _burst(770, 860, u, 5.3) + "</g>"
    out += chalk(70, 200, "the skeleton stops", 52, u, 0.3, 0.5, bold=True)
    out += (amber(70, 262, "the soft organs keep going →", 44, u, 4.4) if u < 5.6
            else amber(70, 262, "… into ribs and skull", 44, u, 5.6))
    return out


def clipped(fn, box):
    """Run a world draw fn but keep only what lands inside box (x0, y0, x1, y1) — e.g. cracks on the wall."""
    def f(img: Image.Image, u, t):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        fn(layer, u, t)
        img.alpha_composite(layer.crop(box), (box[0], box[1]))
    return f


SLED = [[(150, 300), (330, 300), (330, 230), (520, 230), (570, 280), (570, 300)], [(250, 230), (250, 150)]]
RIDER = [[(290, 230), (290, 150)], [(290, 150), (330, 170)], [(290, 210), (345, 250)]]


def stapp_board(u):
    dx = -520 * (1 - ease((u - 3.4) / 2.6))                     # the sled slides in and stops

    def m(x, y):
        return 160 + (x - 150) * 1.7 + dx, 1060 + (y - 300) * 1.7
    rail = overlay.chalk_line([(40, 1060), (1040, 1060)], u / 0.6, 6, seed=81)
    sled = overlay.sketch_paths([[m(x, y) for x, y in q] for q in SLED + RIDER], (u - 0.3) / 1.4, 7, 82)
    hx, hy = m(290, 128)
    head = f'<circle cx="{hx:.0f}" cy="{hy:.0f}" r="36" fill="none" stroke="{overlay.CHALK}" ' \
           f'stroke-width="7" opacity="{min(1.0, max(0.0, (u - 1.2) / 0.4)):.2f}"/>'
    return (rail + sled + head
            + chalk(90, 300, "1954 · Air Force rocket sled", 46, u, 0.2)
            + chalk(90, 370, "John Paul Stapp, doctor", 40, u, 2.3)
            + chalk(90, 480, "632 mph → 0", 96, u, 4.2, 0.5, bold=True)
            + chalk(90, 620, "≈ 46 g", 130, u, 7.1, 0.4, bold=True)
            + amber(90, 690, "recovered · no lasting injury", 44, u, 8.8, weight=700))


def bars_board(u):
    """46 g, ~200 g, 12,000 g on one linear scale (2 px per g): the last bar leaves the board."""
    out = chalk(90, 300, "same scale:", 46, u, 0.1)
    rows = [("Stapp's sled · 1954", 46, 430, 0.4, False), ("worst crash survived", 200, 650, 0.9, False),
            ("your organs at the wall", 12000, 870, 4.6, True)]
    for name, g, y, at, big in rows:
        if u < at:
            continue
        grow = ease((u - at) / (1.6 if big else 0.6))
        ln = min(2 * g * grow, 1200)
        out += chalk(90, y, name, 44, u, at, 0.4)
        col = AMB if big else overlay.CHALK
        out += f'<rect x="90" y="{y + 25}" width="{ln:.0f}" height="70" fill="{col}" opacity="0.9"/>'
        lab = "≈ 12,000 g" if big else f"{'≈ ' if g == 200 else ''}{g} g"
        if not big:
            out += amber(110 + ln, y + 80, lab, 54, u, at + 0.4)
        elif u > at + 1.6:
            out += overlay.chalk_text(90, y + 190, lab, 120, (u - at - 1.6) / 0.4, 800, "Inter Display")
            out += overlay.chalk_text(90, y + 270, "a different universe", 54, (u - at - 2.2) / 0.5)
    return out


def build_seq():
    c = new((1, 7), "tower_plate", fade_out=0.5)
    GR = GROUND["tower_plate"]
    c.cast("hero", height=HERO)
    c.draw(0.0, c.end(), wall(1700, GR), front=False)
    # 0-3.5: bones a hundred times stronger
    c.cam(0.0, *cam_on(1150, GR))
    c.key("hero", 0.0, "a7", 1150, GR)
    c.text(0.2, 3.5, title("YOUR BONES", "× 100 stronger", 150, 76))
    c.sfx(0.2, "sfx_hit", 0.4)
    # 3.5-5.7: a concrete wall at the speed of sound
    c.cam(3.5, *cam_on(1400, GR, vw=1150), "hold")
    c.key("hero", 3.5, "hero1", 1110, GR)
    c.text(3.7, 5.4, lambda u, _t: chalk(1040, 370, "concrete wall", 50, u, 0.0, bold=True, anchor="end"))
    c.text(4.9, 6.6, hud([(4.9, "767 mph", "speed of sound · MACH 1")]))
    c.sfx(3.6, "sfx_dash", 0.4)
    c.key("hero", 5.3, "a0", 1110, GR)
    c.key("hero", 5.65, "a0", 1520, GR, tween="snap", smear=True)
    c.speed_lines(5.3, 5.7)
    c.sfx(5.3, "sfx_sonic", 0.45)
    c.key("hero", 5.7, "hero5", 1545, GR)
    c.cam(5.7, *cam_on(1650, GR), "hold")
    c.flash(5.7, 0.1)
    c.shake(5.7, 0.6, 34)
    c.sfx(5.7, "sfx_crash", 0.5)
    c.draw(5.7, c.end(), clipped(fx.cracks(1712, GR - 360, 300, grow=0.2, seed=91, flat=1.0),
                                 (1705, GR - 755, 1995, GR - 5)), front=False)
    c.draw(5.7, 9.3, fx.debris(1700, GR - 360, n=22, power=0.9, color=(150, 148, 144), seed=92, ground=GR,
                               spread=(160, 260)))
    c.draw(5.7, 9.3, fx.dust(1690, GR - 200, n=18, size=200, life=2.5, seed=93))
    # 6.6-9.3: bones survive, organs don't
    c.freeze(6.6, 9.3, [lambda ctx, u: chalk(70, 360, "bones:  ✓", 84, u, 0.0, 0.4, bold=True),
                        lambda ctx, u: amber(70, 470, "organs:  ✗", 84, u, 1.3)])
    c.sfx(6.6, "sfx_freeze", 0.4)
    # 9.3-23.7: the numbers, then the x-ray
    c.text(9.3, 15.43, vboard(math_board))
    c.sfx(9.4, "sfx_chalk", 0.3)
    c.text(15.43, 23.67, vboard(xray_board))
    c.sfx(19.8, "sfx_slowmo", 0.35)
    c.sfx(20.7, "sfx_hit", 0.35)
    # 23.7-42.4: Stapp's sled, then the scale
    c.text(23.67, 34.6, vboard(stapp_board))
    c.sfx(23.8, "sfx_chalk", 0.3)
    c.text(34.6, 42.3, vboard(bars_board))
    c.sfx(34.7, "sfx_chalk", 0.3)
    # 42.3-end: strong bones aren't enough; what if every part was unbreakable?
    c.cam(42.3, *cam_on(1150, GR), "hold")
    c.key("hero", 42.3, "a6", 1150, GR)
    c.text(42.4, 43.8, title("STRONG BONES", "aren't enough", 170, 76))
    c.key("hero", 43.8, "c1", 1150, GR)
    c.text(43.9, 46.7, title("WHAT IF EVERY PART", "of you was unbreakable?", 170, 60))
    c.sfx(43.9, "sfx_alert", 0.35)
    c.text(46.8, c.end(), full_video(170))
    c.music(0.0, "music_tense", 0.12)
    return c


def build(size):
    return [build_seq()]
