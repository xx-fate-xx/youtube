"""Short: can you catch a bullet? (vertical motion comic, art from whatif_super_speed).

Times: w(x) = x seconds into the spoken narration + the 0.2 s intro. Numbers on screen (script.md, parent
factcheck rows 19-21, 29, calc_notes): 9 mm ≈ 1,180 ft/s; 30 ft in ≈ 1/40 s; reaction ≈ 1/5 s (8×); a 2 ft shove in
1/40 s ≈ 200 g. No shooter and no one hit: only a muzzle flash at the frame edge. Retention rules: the bullet at your
palm is the first frame; no numbers in the first 5 s; the end freezes back into the opening picture.
"""

from __future__ import annotations

import math

from studio.whatif import fx, overlay
from studio.whatif.comic import label
from studio.whatif.shorts import GROUND, HERO, W, amber, cam_on, chalk, full_video, new, scr, title, vboard

GR = GROUND["night_plate"]
CHEST = GR - 270                  # bullet height (plate px)
CH = overlay.CHALK


def w(x: float) -> float:
    return x + 0.2


def race_board(u):
    """Bullet vs your brain on one scale (the brain bar is 8× longer)."""
    kb = min(1.0, max(0.0, (u - 0.5) / 0.25))
    kr = min(1.0, max(0.0, (u - 0.9) / 1.8))
    return (chalk(110, 330, "the bullet arrives", 52, u, 0.1, 0.3)
            + f'<rect x="110" y="360" width="{100 * kb:.0f}" height="60" fill="{overlay.AMBER}"/>'
            + chalk(110, 560, "your brain reacts", 52, u, 0.6, 0.3)
            + f'<rect x="110" y="590" width="{800 * kr:.0f}" height="60" fill="{CH}"/>'
            + chalk(110, 800, "8× slower", 110, u, 1.1, 0.35, bold=True)
            )


def crash_doodle(cx, cy, p):
    out = ""
    for j in range(10):
        a = j * math.pi / 5
        r0, r1 = 30, 80 if j % 2 else 120
        out += overlay.chalk_line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                                   (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], (p - j * 0.05) / 0.3, 6,
                                  seed=40 + j, rough=False)
    return out


def zigzag(x0, y0, x1, y1, p, seed):
    pts = []
    for k in range(7):
        t = k / 6
        off = (24 if k % 2 else -24) if 0 < k < 6 else 0
        pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + off))
    return overlay.chalk_line(pts, p, 6, seed=seed, rough=False)


def build_seq():
    c = new((1, 10), "night_plate")
    c.cast("hero", height=HERO)
    c.cast("woman", height=HERO * 0.95, ref="c4")
    HX = 1200
    open_cam = cam_on(HX + 120, GR, vw=700)

    # 0-3.4: COLD OPEN — frozen street, a bullet a hand's length from your palm
    c.cam(0.0, *open_cam)
    c.key("hero", 0.0, "hero2", HX, GR)
    c.draw(0.0, w(3.4), fx.bullet((HX + 300, CHEST - 20), (HX + 300, CHEST - 20), 1.0, scale=2.4))
    bx, by = scr(open_cam, HX + 300, CHEST - 20)
    c.freeze(0.0, w(3.4), [
        lambda ctx, u: f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="{120 * min(1.0, u / 0.3):.0f}" fill="none" '
                       f'stroke="{overlay.AMBER}" stroke-width="7"/>',
        lambda ctx, u: chalk(W / 2, 260, "catch a bullet?", 92, u, 0.0, 0.35, bold=True, anchor="middle"),
        lambda ctx, u: amber(W / 2, 370, "YES.", 100, u, 1.6, anchor="middle"),
        lambda ctx, u: chalk(W / 2, 450, "but not the way you think", 48, u, 2.2, 0.4, anchor="middle"),
    ])
    c.sfx(0.0, "sfx_freeze", 0.4)

    # 3.4-6.6: someone fires a pistol across the street (only a flash at the frame edge)
    wide = cam_on(1350, GR, vw=1150)
    c.cam(w(3.4), *wide, "ease")
    c.key("hero", w(3.4), "hero7", 1000, GR)
    c.key("woman", w(3.4), "c4", 1750, GR)
    c.flash(w(4.6), 0.05)
    c.sfx(w(4.55), "sfx_bang", 0.5)
    c.draw(w(4.62), w(6.6), fx.bullet((700, CHEST), (2000, CHEST), 0.35, scale=2.0))

    # 6.6-10.4: chalkboard — the bullet is 8× faster than your reaction
    c.text(w(6.5), w(10.4), vboard(race_board))
    c.sfx(w(6.6), "sfx_chalk", 0.3)

    # 10.4-13: legs fast enough; brain isn't
    c.hide("woman", w(10.4))
    c.cam(w(10.4), *cam_on(1000, GR, vw=760), "hold")
    c.key("hero", w(10.4), "c0", 1000, GR)
    c.text(w(10.5), w(13.0), lambda u, _t: chalk(70, 260, "legs:  fast enough ✓", 62, u, 0.0, 0.3, bold=True)
           + amber(70, 360, "brain:  too slow ✗", 66, u, 1.4))

    # 13-18.3: a fast brain too — now the world crawls and you see it coming
    c.key("hero", w(13.0), "c1", 1000, GR)
    c.key("hero", w(15.2), "c1", 830, GR)
    c.text(w(13.1), w(15.2), label(70, 170, "NEW POWER", "+ a fast brain", 86))
    c.sfx(w(13.1), "sfx_hit", 0.35)
    c.cam(w(15.2), *wide, "ease")
    c.key("woman", w(15.2), "c4", 1750, GR)
    c.draw(w(15.2), w(18.3), fx.bullet((1000, CHEST), (1180, CHEST), 3.1, scale=2.4))
    c.sfx(w(15.3), "sfx_slowmo", 0.45)
    c.text(w(15.4), w(18.3), lambda u, _t: chalk(W / 2, 260, "the world crawls", 70, u, 0.0, 0.4, bold=True,
                                                 anchor="middle")
           + amber(W / 2, 350, "you see it coming", 52, u, 1.3, anchor="middle"))

    # 18.3-22.6: shove them out of the way? that push is a crash
    near = cam_on(1580, GR, vw=760)
    c.cam(w(18.3), *near, "ease")
    c.key("hero", w(18.3), "b3", 1450, GR)
    c.key("woman", w(19.6), "c4", 1750, GR)
    c.key("woman", w(19.9), "c4", 1960, GR - 60, ang=18, tween="snap")
    c.shake(w(19.9), 0.4, 20)
    c.sfx(w(19.85), "sfx_hit", 0.45)
    c.text(w(18.4), w(19.9), title("SHOVE THEM", "out of the way?", 200, 80))
    c.freeze(w(20.0), w(22.6), [
        lambda ctx, u: crash_doodle(860, 300, u),
        lambda ctx, u: chalk(70, 260, "a push that fast", 56, u, 0.0, 0.3),
        lambda ctx, u: chalk(70, 360, "= a crash", 84, u, 0.6, 0.3, bold=True),
    ])
    c.sfx(w(20.0), "sfx_freeze", 0.4)

    # 22.6-28.6: take it in the chest? it bounces or shatters — the pieces fly sideways
    chest_cam = cam_on(1450, GR, vw=900)
    c.cam(w(22.6), *chest_cam, "ease")
    c.key("hero", w(22.6), "hero7", 1500, GR)
    c.key("woman", w(22.6), "c4", 1170, GR, flip=True)
    c.text(w(22.7), w(24.0), title("TAKE IT", "in the chest?", 200, 84))
    c.draw(w(23.4), w(23.75), fx.bullet((2300, CHEST), (1560, CHEST), 0.35, scale=2.0))
    c.draw(w(23.75), w(26.0), fx.sparks(1560, CHEST, n=26, life=0.45, seed=61))
    c.draw(w(23.75), w(27.0), fx.debris(1560, CHEST, n=10, power=0.7, color=(200, 150, 70), seed=62,
                                        ground=GR, spread=(150, 230)))
    c.shake(w(23.75), 0.3, 16)
    c.sfx(w(23.7), "sfx_hit", 0.5)
    cx_, cy_ = scr(chest_cam, 1560, CHEST)
    wx_, wy_ = scr(chest_cam, 1220, CHEST)
    c.freeze(w(25.0), w(28.6), [
        lambda ctx, u: chalk(70, 260, "you: unbreakable ✓", 56, u, 0.0, 0.3, bold=True),
        lambda ctx, u: zigzag(cx_ - 40, cy_, wx_ + 60, cy_ - 60, (u - 0.6) / 0.5, 71),
        lambda ctx, u: zigzag(cx_ - 40, cy_ + 20, cx_ - 300, cy_ + 200, (u - 0.9) / 0.5, 72),
        lambda ctx, u: amber(70, 360, "the pieces fly ✗", 64, u, 1.7),
    ])
    c.sfx(w(25.0), "sfx_freeze", 0.4)

    # 28.6-34.6: the move — run beside the bullet, match its speed, close your hand
    c.hide("woman", w(28.6))
    c.text(w(28.7), w(29.9), title("HERE'S", "the move", 200, 110))
    c.key("hero", w(28.6), "hero2", 500, GR)
    c.key("hero", w(33.1), "hero2", 1380, GR, tween="lin", smear=True)
    c.cam(w(28.6), *cam_on(620, GR, vw=800), "hold")
    c.cam(w(33.1), *cam_on(1500, GR, vw=800), "lin")
    c.draw(w(28.6), w(33.15), fx.bullet((700, CHEST), (1580, CHEST), w(33.1) - w(28.6), scale=1.8))
    c.speed_lines(w(29.3), w(33.1))
    c.sfx(w(29.4), "sfx_dash", 0.4)
    c.text(w(31.4), w(33.0), lambda u, _t: chalk(W / 2, 260, "match its speed", 72, u, 0.0, 0.35, bold=True,
                                                 anchor="middle"))
    c.key("hero", w(33.15), "c3", 1450, GR)
    c.text(w(33.2), w(34.6), lambda u, _t: amber(W / 2, 300, "…and close your hand", 60, u, 0.0, anchor="middle"))
    c.sfx(w(33.2), "sfx_catch", 0.35)

    # 34.6-40.2: the gunshot, then a second crack — that's you, faster than sound
    c.cam(w(34.6), *cam_on(1500, GR, vw=900), "ease")
    c.key("woman", w(34.6), "c4", 1900, GR)
    c.flash(w(35.5), 0.05)
    c.sfx(w(35.5), "sfx_bang", 0.5)
    c.text(w(35.5), w(37.1), lambda u, _t: chalk(70, 260, "the gunshot…", 64, u, 0.0, 0.3, bold=True))
    c.text(w(37.1), w(38.3), lambda u, _t: overlay.boom(540, 900, u, W, 1920))
    c.shake(w(37.1), 0.5, 26)
    c.sfx(w(37.1), "sfx_sonic", 0.5)
    c.text(w(37.2), w(40.2), lambda u, _t: chalk(70, 260, "…then a 2nd crack", 64, u, 0.0, 0.3, bold=True)
           + amber(70, 350, "that's you", 70, u, 0.6)
           + chalk(70, 430, "faster than sound", 50, u, 1.6, 0.4))

    # 40.2-end: full video; then freeze back into the opening (the bullet at your palm)
    c.text(w(40.2), w(42.3), full_video(250))
    c.hide("woman", w(42.3))
    c.cam(w(42.3), *open_cam, "snap")
    c.key("hero", w(42.3), "hero2", HX, GR)
    c.draw(w(42.3), c.end(), fx.bullet((HX + 300, CHEST - 20), (HX + 300, CHEST - 20), 1.0, scale=2.4))
    c.freeze(w(42.4), c.end(), [
        lambda ctx, u: f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="{120 * min(1.0, u / 0.3):.0f}" fill="none" '
                       f'stroke="{overlay.AMBER}" stroke-width="7"/>',
    ])
    c.sfx(w(42.4), "sfx_freeze", 0.35)
    c.music(0.0, "music_tense", 0.12)
    return c


def build(size):
    return [build_seq()]
