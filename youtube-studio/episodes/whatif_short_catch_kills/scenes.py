"""Short: why catching them kills them (vertical motion comic, art from whatif_super_speed).

Times: w(x) = x seconds into the spoken narration (projects/whatif_short_catch_kills/audio/narration_words.json)
+ the 0.2 s intro. Numbers on screen: script.md / parent calc_notes — 30 storeys ≈ 300 ft; ≈ 83 mph (134 km/h)
at the bottom; arm catch over ≈ 1.5 ft ≈ 150 g; braking over ≈ 60 ft keeps it under ≈ 4 g (big coasters 4–6 g).
Retention rules: the catch is the first frame; no numbers in the first 5 s; the end runs back into the opening.
Screen bands (1080x1920): text 150-560 when the characters stand on the ground (feet at 1110); text 900-1080
when they are high in the frame; captions 1150-1310 stay clear.
"""

from __future__ import annotations

from studio.whatif import fx, overlay
from studio.whatif.comic import label
from studio.whatif.shorts import GROUND, HERO, W, amber, cam_on, chalk, full_video, new, title, vboard

GR = GROUND["tower_plate"]
X = 1640                          # where you stand, under the fall line
FALL_X = 1700


def w(x: float) -> float:
    return x + 0.2


def car(x, y, s, p):
    """A chalk car (side view), drawn as p goes 0 -> 1."""
    body = [(0, 40), (10, 12), (60, 12), (80, 0), (140, 0), (165, 22), (200, 26), (205, 40), (0, 40)]
    pts = [[(x + a * s, y + b * s) for a, b in body]]
    wheels = "".join(f'<circle cx="{x + cx * s:.0f}" cy="{y + 42 * s:.0f}" r="{13 * s:.0f}" fill="none" '
                     f'stroke="{overlay.CHALK}" stroke-width="6" opacity="{min(1.0, max(0.0, p * 2 - 1)):.2f}"/>'
                     for cx in (45, 160))
    return overlay.sketch_paths(pts, p, 6, 31) + wheels


def coaster_board(u):
    track = [(0, 0), (60, 0), (110, 50), (190, 330), (260, 380), (380, 380), (450, 280), (520, 200), (700, 200),
             (760, 120), (840, 100)]
    pts = [[(130 + a * 1.0, 380 + b * 1.0) for a, b in track]]
    cart = ""
    if u > 1.4:                                               # a little cart riding the dip
        k = min(1.0, (u - 1.4) / 1.3)
        i = min(len(track) - 2, int(k * (len(track) - 1)))
        f = k * (len(track) - 1) - i
        cx = 130 + track[i][0] + (track[i + 1][0] - track[i][0]) * f
        cy = 380 + track[i][1] + (track[i + 1][1] - track[i][1]) * f
        cart = f'<rect x="{cx - 26:.0f}" y="{cy - 34:.0f}" width="52" height="28" rx="6" fill="{overlay.AMBER}"/>'
    return (overlay.sketch_paths(pts, u / 1.4, 7, 41) + cart
            + chalk(130, 860, "to them, it feels like", 52, u, 1.4)
            + chalk(130, 950, "a big roller coaster", 84, u, 1.7, 0.4, bold=True))


def build_seq():
    c = new((1, 10), "tower_plate")
    c.cast("hero", height=HERO)
    c.cast("cleaner", height=HERO * 0.98, ref="cleaner0")
    c.cast("pair", height=HERO)
    near = cam_on(X + 40, GR)

    # 0-3: COLD OPEN — they drop into your arms, then the twist
    c.cam(0.0, *near)
    c.key("hero", 0.0, "hero4", X, GR)
    c.key("cleaner", 0.0, "cleaner3", FALL_X, GR - 640, scale=0.8, fixed=True)
    c.key("cleaner", w(0.35), "cleaner3", FALL_X, GR - 430, scale=0.8, fixed=True, tween="in")
    c.hide("cleaner", w(0.35))
    c.hide("hero", w(0.35))
    c.key("pair", w(0.35), "a3", X, GR)
    c.speed_lines(0.0, w(0.35))
    c.flash(w(0.35), 0.06)
    c.shake(w(0.35), 0.5, 30)
    c.sfx(w(0.3), "sfx_catch", 0.55)
    c.draw(w(0.35), w(2.85), fx.cracks(X, GR + 4, 280, seed=11), front=False)
    c.draw(w(0.35), w(2.85), fx.dust(X, GR, size=150, seed=12))
    c.freeze(w(1.0), w(2.85), [
        lambda ctx, u: chalk(W / 2, 300, "SAVED?", 120, u, 0.0, 0.35, bold=True, anchor="middle") if u < 0.8 else "",
        lambda ctx, u: chalk(W / 2, 300, "NOPE.", 120, u, 0.8, 0.3, bold=True, anchor="middle"),
        lambda ctx, u: amber(W / 2, 400, "…that's what kills them", 56, u, 0.9, anchor="middle"),
    ])
    c.sfx(w(1.0), "sfx_freeze", 0.4)

    # 3-5.8: rewind; super speed, nothing hurts you
    c.rewind(w(2.85), w(3.5))
    c.sfx(w(2.85), "sfx_rewind", 0.4)
    c.hide("pair", w(2.85))
    c.key("hero", w(2.85), "a7", X - 250, GR)
    c.cam(w(2.85), *cam_on(X - 250, GR), "hold")
    c.text(w(3.1), w(5.8), title("SUPER SPEED", "nothing can hurt you", 230, 64))
    c.key("hero", w(4.3), "hero2", X - 650, GR)
    c.key("hero", w(4.75), "hero2", X + 150, GR, tween="snap", smear=True)
    c.cam(w(4.75), *cam_on(X + 100, GR), "snap")
    c.speed_lines(w(4.3), w(4.8))
    c.sfx(w(4.3), "sfx_dash", 0.45)
    c.key("hero", w(4.8), "hero7", X + 150, GR)

    # 5.9-8.5: up on the cradle, a window cleaner slips (you are off-screen, down on the street)
    c.hide("hero", w(5.85))
    c.cam(w(5.85), 2120, 700, 800, "ease")
    c.key("cleaner", w(5.85), "cleaner0", 2150, 352, scale=0.42, fixed=True)
    c.key("cleaner", w(6.5), "cleaner1", 2150, 352, scale=0.42, fixed=True)
    c.key("cleaner", w(7.1), "cleaner2", 2100, 420, ang=-20, scale=0.45, fixed=True)
    c.key("cleaner", w(8.45), "cleaner3", 2060, 900, scale=0.55, fixed=True, tween="in")
    c.sfx(w(6.5), "sfx_slip", 0.5)
    c.sfx(w(7.1), "sfx_fall", 0.45)
    c.text(w(7.2), w(8.3), lambda u, _t: amber(70, 1000, "FLOOR 30", 110, u, 0.0)
           + chalk(70, 1075, "a window cleaner slips", 48, u, 0.2))

    # 8.5-11.6: you get there in time; arms out; easy?
    c.cam(w(8.5), *cam_on(X - 100, GR), "hold")
    c.hide("cleaner", w(8.5))
    c.key("hero", w(8.5), "hero2", X - 700, GR)
    c.key("hero", w(8.9), "hero2", X, GR, tween="snap", smear=True)
    c.cam(w(8.9), *near, "snap")
    c.speed_lines(w(8.5), w(8.95))
    c.sfx(w(8.5), "sfx_dash", 0.45)
    c.key("hero", w(8.95), "hero7", X, GR)
    c.key("hero", w(9.65), "hero4", X, GR)
    c.key("cleaner", w(9.3), "cleaner3", FALL_X, GR - 1150, scale=0.8, fixed=True)
    c.key("cleaner", w(11.7), "cleaner3", FALL_X, GR - 700, scale=0.8, fixed=True, tween="in")
    c.text(w(10.6), w(11.65), lambda u, _t: chalk(300, 420, "easy?", 110, u, 0.0, 0.3, bold=True,
                                                  anchor="middle"))

    # 11.7-16.3: freeze — they're falling faster than a highway car (you and them on the right)
    cam4 = (X - 120, GR - 560, 760)
    c.cam(w(11.7), *cam4, "ease")
    c.key("cleaner", w(12.2), "cleaner3", FALL_X, GR - 660, scale=0.8, fixed=True, tween="lin")
    c.freeze(w(12.2), w(16.3), [
        lambda ctx, u: chalk(60, 300, "not really.", 66, u, 0.0, 0.3, bold=True),
        lambda ctx, u: chalk(60, 420, "a car on the highway:", 40, u, 1.6),
        lambda ctx, u: car(60, 450, 1.6, (u - 1.9) / 0.7),
        lambda ctx, u: chalk(60, 640, "they're faster", 60, u, 2.6, 0.4, bold=True),
    ])
    c.sfx(w(12.2), "sfx_freeze", 0.4)

    # 16.3-19.1: your arms stop them in about a foot and a half
    c.cam(w(16.3), *near, "ease")
    c.key("cleaner", w(16.3), "cleaner3", FALL_X, GR - 660, scale=0.8, fixed=True)
    c.key("cleaner", w(16.75), "cleaner3", FALL_X, GR - 430, scale=0.8, fixed=True, tween="in")
    c.hide("cleaner", w(16.75))
    c.hide("hero", w(16.75))
    c.key("pair", w(16.75), "a3", X, GR)
    c.flash(w(16.75), 0.06)
    c.shake(w(16.75), 0.5, 30)
    c.sfx(w(16.7), "sfx_crash", 0.5)
    c.draw(w(16.75), w(19.1), fx.dust(X, GR, size=150, seed=13))
    c.freeze(w(17.3), w(19.0), [
        lambda ctx, u: chalk(70, 260, "from highway speed", 52, u, 0.0, 0.3),
        lambda ctx, u: chalk(70, 380, "to zero in 1.5 ft", 84, u, 0.5, 0.35, bold=True),
    ])
    c.sfx(w(17.3), "sfx_freeze", 0.35)

    # 19.1-23.4: not a catch — a crash; your arms are the wall
    c.cam(w(19.0), *cam_on(X + 40, GR, vw=700), "snap")
    c.text(w(19.1), w(20.4), title("THAT'S NOT", "a catch", 150, 92))
    c.text(w(20.4), w(21.5), title("THAT'S", "A CRASH", 150, 130))
    c.shake(w(20.5), 0.4, 22)
    c.sfx(w(20.5), "sfx_hit", 0.5)

    def wall_note(u, _t):
        out = ""
        k = min(1.0, max(0.0, u / 0.7))
        for r in range(3):                                    # a chalk brick wall
            for j in range(5):
                x0 = 70 + j * 190 + (95 if r % 2 else 0)
                if (r * 5 + j) / 15 > k or x0 + 180 > W - 40:
                    continue
                out += (f'<rect x="{x0}" y="{110 + r * 64}" width="180" height="62" fill="none" '
                        f'stroke="{overlay.CHALK}" stroke-width="5" opacity="0.8"/>')
        return (out + chalk(70, 390, "your arms = the wall", 66, u, 0.5, 0.4, bold=True))
    c.text(w(21.5), w(23.4), wall_note)
    c.sfx(w(21.6), "sfx_chalk", 0.3)

    # 23.4-25.6: you're unbreakable; they're not
    c.cam(w(23.4), *cam_on(X, GR, vw=760), "ease")
    c.key("pair", w(23.4), "a2", X, GR)
    c.text(w(23.5), w(25.6), lambda u, _t: chalk(70, 260, "you:  unbreakable ✓", 64, u, 0.0, 0.35, bold=True)
           + amber(70, 370, "them:  not ✗", 76, u, 1.1))

    # 25.6-28.9: new power: super grip; sprint up the building
    c.hide("pair", w(25.6))
    c.key("hero", w(25.6), "a7", X, GR)
    c.cam(w(25.6), *near, "ease")
    c.text(w(25.7), w(27.1), label(70, 170, "NEW POWER", "+ super grip", 86))
    c.key("hero", w(27.1), "a0", X, GR)
    c.key("hero", w(27.3), "a0", 1835, GR - 120, ang=-90, scale=0.9, fixed=True, tween="snap")
    c.key("hero", w(28.5), "a0", 1855, 460, ang=-90, scale=0.9, fixed=True, tween="lin", smear=True)
    c.cam(w(27.3), *cam_on(1800, GR), "ease")
    c.cam(w(28.5), 1820, 700, 820, "lin")
    c.speed_lines(w(27.2), w(28.6))
    c.sfx(w(27.2), "sfx_dash", 0.45)
    c.draw(w(27.3), w(29.0), fx.dust(1810, GR, size=130, seed=14))

    # 28.9-31.9: catch up with them mid-air and fall side by side
    c.key("cleaner", w(28.6), "cleaner3", FALL_X, 300, scale=0.8, fixed=True)
    c.key("cleaner", w(31.9), "cleaner3", FALL_X, 640, scale=0.8, fixed=True, tween="lin")
    c.key("hero", w(28.9), "a1", 1840, 330, scale=0.9, fixed=True)
    c.key("hero", w(31.9), "a1", 1840, 670, scale=0.9, fixed=True, tween="lin")
    c.cam(w(28.9), 1780, 520, 820, "ease")
    c.cam(w(31.9), 1780, 720, 820, "lin")
    c.text(w(30.3), w(31.95), lambda u, _t: chalk(W / 2, 960, "same speed", 80, u, 0.0, 0.35, bold=True,
                                                  anchor="middle")
           + amber(W / 2, 1050, "nothing hits anything", 52, u, 0.5, anchor="middle"))
    c.sfx(w(30.3), "sfx_slowmo", 0.3)

    # 32-35: brake slowly over ~60 ft (the pair slides down the facade)
    c.hide("cleaner", w(32.0))
    c.hide("hero", w(32.0))
    c.key("pair", w(32.0), "a3", 1740, 760)
    c.key("pair", w(35.2), "a3", 1740, 1180, tween="out")
    c.cam(w(32.0), 1740, 720, 820, "hold")
    c.cam(w(35.2), 1740, 1000, 820, "out")
    c.sfx(w(32.1), "sfx_scrape", 0.35)
    c.draw(w(32.0), w(35.2), fx.sparks(1800, 780, n=14, life=0.4, duration=3.0, seed=17))

    def brake(u, _t):
        k = min(1.0, max(0.0, (u - 1.4) / 1.2))
        return (chalk(70, 250, "brake slowly", 66, u, 0.0, 0.35, bold=True)
                + chalk(70, 340, "over ≈ 60 ft", 66, u, 1.4, 0.35, bold=True)
                + overlay.chalk_line([(1000, 150), (1000, 150 + 700 * k)], 1.0, 8, seed=61, rough=False))
    c.text(w(32.0), w(35.1), brake)

    # 35-37.9: chalkboard — it feels like a big roller coaster
    c.text(w(35.1), w(37.9), vboard(coaster_board))
    c.sfx(w(35.2), "sfx_chalk", 0.3)

    # 37.9-40: feet on the ground. Alive.
    c.key("pair", w(37.9), "a2", 1740, GR)
    c.cam(w(37.9), *cam_on(1740, GR), "hold")
    c.draw(w(37.95), w(39.0), fx.dust(1740, GR, size=110, seed=16))
    c.hide("pair", w(38.9))
    c.key("hero", w(38.9), "hero7", 1620, GR)
    c.key("cleaner", w(38.9), "cleaner0", 1830, GR, scale=0.98, fixed=True)
    c.cam(w(38.9), *cam_on(1725, GR), "ease")
    c.text(w(38.9), w(40.0), lambda u, _t: amber(W / 2, 400, "ALIVE ✓", 130, u, 0.0, anchor="middle"))
    c.sfx(w(38.95), "sfx_hit", 0.3)

    # 40-end: full video; then back to the opening — you, arms out, as they fall ...
    c.text(w(40.0), w(42.0), full_video(250))
    c.hide("cleaner", w(42.0))
    c.key("hero", w(42.0), "hero4", X, GR)
    c.cam(w(42.0), *near, "hold")
    c.key("cleaner", w(42.0), "cleaner3", FALL_X, GR - 1100, scale=0.8, fixed=True)
    c.key("cleaner", c.end(), "cleaner3", FALL_X, GR - 660, scale=0.8, fixed=True, tween="in")
    c.speed_lines(w(43.6), c.end())
    c.sfx(w(42.1), "sfx_fall", 0.35)
    c.music(0.0, "music_tense", 0.12)
    return c


def build(size):
    return [build_seq()]
