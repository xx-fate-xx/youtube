"""Short: teleport from New York to Boston? a car crash (vertical, art from whatif_teleport; Higgsfield art only —
code draws only chalk arrows/text). Times = seconds of the aligned narration (+0.2 s intro). Rules: action in frame 1,
no numbers on screen, a change every ~3 s, loop ending. Directions per the fact-check: London flings you UP, Tokyo
slams you sideways. Proportions: car ≈ 0.8 of the hero's height, tumble pose at 0.6.
"""

from __future__ import annotations

from studio.whatif import overlay, props
from studio.whatif.comic import Comic
from studio.whatif.shorts import W, amber, cam_on, chalk, full_video, title

SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455, "t": 2005}
HS = {"highway_plate": 440, "tower_plate": 440, "night_plate": 420, "ocean_plate": 420}
GR = {"highway_plate": 1400, "tower_plate": 1362, "night_plate": 1420, "ocean_plate": 1250}


def hero(c, t, spr, x, plate, y=None, **kw):
    sc = kw.pop("scale", 1.0)
    c.key("hero", t, spr, x, GR[plate] if y is None else y, scale=HS[plate] / 400 * sc, fixed=True, **kw)


def cut(c, t, plate, cam):
    c.cut(t, f"{plate}_v")
    c.cam(t, *cam, "hold")


def boston(c, t0, t1):
    """You pop out of a portal and tumble into the barrier at Boston (the opening, and the loop)."""
    G = GR["highway_plate"]
    cut(c, t0, "highway_plate", cam_on(1720, G, 900))
    c.draw(t0, t1, props.prop("wall0", 2050, G + 10, HS["highway_plate"] * 0.75, fade=0), front=False)
    c.draw(t0, t0 + 0.8, props.portal(1420, G - 10, 380), front=False)
    c.sfx(t0 + 0.02, "sfx_teleport", 0.45)
    hero(c, t0, "t4", 1420, "highway_plate", y=G - 20, scale=0.6)


def build_seq():
    c = Comic(shots=(1, 8), plate="highway_plate_v")
    c.sheet_ref = dict(SHEET)
    c.shade = (0.5, 760)
    c.cast("hero", height=400)
    G = GR["highway_plate"]
    # 0-4.2: COLD OPEN — New York to Boston: you arrive tumbling into the barrier = a car crash
    boston(c, 0.0, 4.2)
    hero(c, 3.2, "t4", 1900, "highway_plate", y=G - 10, scale=0.6, ang=540, tween="in")
    c.speed_lines(0.0, 3.2)
    c.key("hero", 3.25, "hero5", 1880, G, scale=HS["highway_plate"] / 400, fixed=True)
    c.shake(3.25, 0.5, 26)
    c.flash(3.25, 0.05)
    c.sfx(3.2, "sfx_crash", 0.55)
    c.draw(3.25, 4.2, props.prop("car0", 1520, G, HS["highway_plate"] * 0.8, fade=0.2))
    c.text(0.3, 2.6, title("NEW YORK → BOSTON", "by teleport", 300, 70))
    c.text(2.6, 4.2, lambda u, _t: amber(W / 2, 380, "= a car crash", 80, u, 0.3, anchor="middle"))
    # 4.2-10.1: a teleporter keeps your speed; the ground is almost never still (painted Earth, side)
    cut(c, 4.2, "space_plate", (1344, 1060, 1150))
    c.key("hero", 4.2, None)
    c.draw(4.2, 15.4, props.globe(1, 1344, 1060, 1000))
    c.text(4.4, 10.1, lambda u, _t: chalk(70, 250, "a teleporter keeps", 52, u, 0.6)
           + amber(70, 340, "your speed", 64, u, 1.6) + chalk(70, 430, "the ground never stops", 48, u, 3.6))
    # 10.1-15.4: every city rides along at its own speed, in its own direction
    gx0, gy0 = 540 - 470, 960 - 470                                # the globe's box on screen

    def cities(u, _t):
        out = chalk(70, 250, "every city:", 52, u, 0.2) + amber(70, 340, "its own speed & direction", 50, u, 1.4)
        for k, (fx, fy, dx, dy) in enumerate([(0.585, 0.27, 190, 0), (0.62, 0.22, 150, -30), (0.30, 0.25, 130, 50),
                                              (0.60, 0.40, 230, 15)]):
            px, py = gx0 + fx * 1000 * 1080 / 1150, gy0 + fy * 1000 * 1080 / 1150
            out += (f'<circle cx="{px:.0f}" cy="{py:.0f}" r="11" fill="{overlay.AMBER}" '
                    f'opacity="{min(1.0, max(0.0, (u - 1.8 - 0.4 * k) / 0.2)):.2f}"/>')
            out += overlay.chalk_arrow(px, py, px + dx, py + dy, (u - 2.0 - 0.4 * k) / 0.3, seed=50 + k)
        return out
    c.text(10.1, 15.4, cities)
    # 15.4-17.9: across town — nothing happens
    T = GR["tower_plate"]
    cut(c, 15.4, "tower_plate", cam_on(1300, T, 900))
    c.draw(15.5, 16.3, props.portal(1300, T - 10, 380), front=False)
    c.sfx(15.5, "sfx_teleport", 0.4)
    hero(c, 15.55, "a6", 1300, "tower_plate")
    c.text(15.6, 17.9, lambda u, _t: chalk(70, 280, "across town", 64, u, 0.0, 0.4, bold=True)
           + amber(70, 380, "nothing happens", 60, u, 1.4))
    # 17.9-20.8: Philadelphia — like flying off your bike
    hero(c, 17.9, "t4", 1000, "tower_plate", y=T - 15, scale=0.6)
    hero(c, 19.6, "t4", 1600, "tower_plate", y=T - 5, scale=0.6, ang=420, tween="out")
    c.cam(17.9, *cam_on(1100, T, 900), "hold")
    c.cam(19.6, *cam_on(1500, T, 900), "out")
    c.draw(17.9, 20.8, props.prop("bike0", 1150, T, HS["tower_plate"] * 0.55, slide=(1750, T), dur=1.2,
                                  tween=lambda q: 1 - (1 - q) ** 2))
    c.sfx(18.4, "sfx_crash", 0.35)
    c.text(18.0, 20.8, lambda u, _t: chalk(70, 280, "Philadelphia", 66, u, 0.0, 0.4, bold=True)
           + amber(70, 380, "off your bike", 60, u, 1.0))
    # 20.8-25.8: London — faster than sound, and the ground flings you into the sky
    N = GR["night_plate"]
    cut(c, 20.8, "night_plate", cam_on(1300, N, 900))
    c.key("hero", 20.8, None)
    c.draw(21.4, 22.2, props.portal(1450, N - 10, 380), front=False)
    c.sfx(21.4, "sfx_teleport", 0.4)
    hero(c, 21.45, "t2", 1450, "night_plate")
    hero(c, 23.6, "t2", 1420, "night_plate", y=N - 1400, tween="in", smear=True)
    c.flash(21.5, 0.06)
    c.shake(21.5, 0.6, 26)
    c.sfx(21.5, "sfx_sonic", 0.5)
    c.text(21.5, 22.9, lambda u, _t: overlay.boom(760, 1000, u, W, 1920))
    c.text(21.7, 25.8, lambda u, _t: chalk(70, 280, "London", 70, u, 0.0, 0.4, bold=True)
           + amber(70, 380, "flung into the sky", 60, u, 1.8))
    # 25.8-28.3: Tokyo — double the speed of sound, sideways (a slam and a skid)
    cut(c, 25.8, "tower_plate", cam_on(700, T, 900))
    c.cam(27.6, *cam_on(1750, T, 900), "lin")
    c.draw(25.8, 26.6, props.portal(500, T - 10, 380), front=False)
    hero(c, 25.85, "t1", 500, "tower_plate", y=T + 10)
    hero(c, 27.6, "t1", 1800, "tower_plate", y=T + 10, tween="lin", smear=True)
    c.draw(25.85, 28.3, props.spray(500, 1800, 1.75, T + 10, seed=13, col=(200, 196, 190)))
    c.speed_lines(25.85, 27.6)
    c.sfx(25.9, "sfx_skid", 0.5)
    c.text(25.9, 28.3, lambda u, _t: chalk(70, 280, "Tokyo", 70, u, 0.0, 0.4, bold=True)
           + amber(70, 380, "× 2 sound, sideways", 58, u, 0.9))
    # 28.3-32.6: your commute is fine; your summer trip is not
    c.key("hero", 28.3, None)
    c.text(28.3, 32.6, lambda u, _t: f'<rect width="100%" height="100%" fill="#06101C" opacity="0.5"/>'
           + chalk(W / 2, 700, "commute ✓", 110, u, 0.6, 0.4, bold=True, anchor="middle")
           + amber(W / 2, 880, "summer trip ✗", 96, u, 2.6, anchor="middle"))
    c.sfx(30.8, "sfx_hit", 0.4)
    # 32.6-37.2: one long trip lands without a bump — in the full video (you, perfectly still, in the sea)
    O = GR["ocean_plate"]
    cut(c, 32.6, "ocean_plate", cam_on(1500, O, 900, feet=1000))
    c.draw(32.7, 37.2, props.submerge(1500, O, "ocean_plate_v", 260))
    hero(c, 32.7, "a6", 1500, "ocean_plate", y=O + HS["ocean_plate"] * 0.55)
    c.text(32.8, 35.8, lambda u, _t: chalk(70, 280, "one long trip:", 60, u, 0.0)
           + amber(70, 380, "no bump at all", 64, u, 1.4))
    c.text(35.8, 37.2, full_video(330))
    # 37.2-end: until then, don't — the tumble into the barrier again (loops into the opening)
    boston(c, 37.2, c.end())
    hero(c, c.end(), "t4", 1600, "highway_plate", y=G - 15, scale=0.6, ang=300, tween="in")
    c.speed_lines(37.2, c.end())
    c.text(37.4, c.end(), title("DON'T TELEPORT", "New York → Boston", 300, 66))
    c.music(0.0, "music_tense", 0.12)
    return c


def build(size):
    return [build_seq()]
