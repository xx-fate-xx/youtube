"""Short: never teleport to the North Pole (vertical, art from whatif_teleport; Higgsfield art only — code draws only
chalk arrows/text). Times = seconds of the aligned narration (+0.2 s intro). Rules: action in frame 1, no numbers on
screen in the first 5 s, a change every ~3 s, loop ending (the last seconds rebuild the opening skid).
"""

from __future__ import annotations

from studio.whatif import overlay, props
from studio.whatif.comic import Comic
from studio.whatif.shorts import W, amber, cam_on, chalk, full_video, title

SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455, "t": 2005}
HS = {"pole_plate": 470, "beach_plate": 470}
GR = {"pole_plate": 1380, "beach_plate": 1420}
GX, GY, GSZ = 1344, 1060, 1000                    # the painted globe on the space plate (screen centre 540, 960)


def new(shots, plate) -> Comic:
    c = Comic(shots=shots, plate=f"{plate}_v")
    c.sheet_ref = dict(SHEET)
    c.shade = (0.5, 760)
    c.cast("hero", height=400)
    return c


def hero(c, t, spr, x, plate, y=None, **kw):
    sc = kw.pop("scale", 1.0)
    c.key("hero", t, spr, x, GR[plate] if y is None else y, scale=HS[plate] / 400 * sc, fixed=True, **kw)


def cut(c, t, plate, cam):
    c.cut(t, f"{plate}_v")
    c.cam(t, *cam, "hold")


def rim(u, at, cx=540, cy=960, r=470, spin=0.0):
    import math
    out = ""
    for j in range(8):
        a = j * math.pi / 4 - math.radians(spin)
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        tx, ty = math.sin(a), -math.cos(a)
        out += overlay.chalk_arrow(px, py, px + 90 * tx, py + 90 * ty, (u - at - 0.06 * j) / 0.3, seed=300 + j)
    return out


def build_seq():
    c = new((1, 9), "pole_plate")
    P, B = GR["pole_plate"], GR["beach_plate"]
    gcam = (GX, GY, 1150)
    # 0-3.7: COLD OPEN — you are already skidding across the ice; you can't stop
    c.cam(0.0, *cam_on(500, P, 900))
    c.cam(3.7, *cam_on(1900, P, 900), "lin")
    hero(c, 0.0, "t1", 420, "pole_plate", y=P + 10)
    hero(c, 3.7, "t1", 1850, "pole_plate", y=P + 10, tween="lin", smear=True)
    c.draw(0.0, 3.8, props.spray(420, 1850, 3.7, P + 10, seed=7))
    c.speed_lines(0.0, 3.7)
    c.sfx(0.0, "sfx_ice", 0.55)
    c.text(0.3, 2.4, title("THE NORTH POLE", "you just teleported", 330, 64))
    c.text(2.4, 3.7, title("AND YOU", "can't stop", 330, 96))
    # 3.7-8.1: you came from a beach on the equator
    cut(c, 3.7, "beach_plate", cam_on(800, B, 900))
    hero(c, 3.7, "hero0", 1020, "beach_plate")
    c.text(4.0, 8.1, lambda u, _t: chalk(70, 300, "you came from", 54, u, 0.4)
           + amber(70, 400, "a beach on the equator", 60, u, 2.6))
    # 8.1-15.4: the equator spins — faster than sound (painted Earth from above)
    cut(c, 8.1, "space_plate", gcam)
    c.key("hero", 8.1, None)
    c.draw(8.1, 15.4, props.globe(0, GX, GY, GSZ, spin=-8.0))
    c.text(8.3, 15.4, lambda u, _t: rim(u, 0.4, spin=8 * u)
           + chalk(W / 2, 250, "the equator spins", 64, u, 0.3, 0.4, bold=True, anchor="middle")
           + amber(W / 2, 370, "faster than sound", 72, u, 5.5, anchor="middle"))
    c.sfx(8.2, "sfx_hit", 0.35)
    # 15.4-20.0: you can't feel it — the sand, the waves and the air ride along
    cut(c, 15.4, "beach_plate", cam_on(800, B, 900))
    hero(c, 15.4, "hero7", 1020, "beach_plate")

    def together(u, _t):
        out = ""
        for k, (y, s) in enumerate([(360, "air"), (470, "waves"), (580, "sand")]):
            out += overlay.chalk_arrow(140, y, 420, y, (u - 0.6 - 0.4 * k) / 0.3, seed=60 + k)
            out += chalk(450, y + 18, s, 50, u, 0.8 + 0.4 * k)
        return out + amber(70, 260, "all moving with you", 56, u, 2.4)
    c.text(15.4, 20.0, together)
    # 20.0-25.6: but the North Pole only spins in place
    cut(c, 20.0, "space_plate", gcam)
    c.key("hero", 20.0, None)
    c.draw(20.0, 25.6, props.globe(0, GX, GY, GSZ, spin=-8.0, a0=-40))
    c.text(20.2, 25.6, lambda u, _t: (f'<circle cx="540" cy="960" r="{50 + 8 * __import__("math").sin(u * 4):.0f}" '
                                      f'fill="none" stroke="{overlay.AMBER}" stroke-width="8"/>')
           + chalk(W / 2, 250, "the North Pole", 64, u, 0.3, 0.4, bold=True, anchor="middle")
           + amber(W / 2, 370, "only spins in place", 64, u, 2.6, anchor="middle"))
    # 25.6-29.3: you arrive with all that speed; the ice has none
    cut(c, 25.6, "pole_plate", cam_on(700, P, 900))
    c.draw(25.7, 29.4, props.portal(500, P - 10, 380), front=False)
    c.sfx(25.7, "sfx_teleport", 0.5)
    hero(c, 25.8, "t1", 500, "pole_plate", y=P + 10)
    c.text(26.0, 29.3, lambda u, _t: chalk(70, 300, "you: all that speed", 56, u, 0.0, 0.4, bold=True)
           + amber(70, 400, "the ice: none", 64, u, 2.0))
    # 29.3-32.8: the skid — faster than a pistol bullet
    hero(c, 29.3, "t1", 500, "pole_plate", y=P + 10)
    hero(c, 31.0, "t1", 2000, "pole_plate", y=P + 10, tween="lin", smear=True)
    c.cam(29.3, *cam_on(700, P, 900), "hold")
    c.cam(31.0, *cam_on(1950, P, 900), "lin")
    c.draw(29.3, 32.8, props.spray(500, 2000, 1.7, P + 10, seed=8))
    c.speed_lines(29.3, 31.0)
    c.sfx(29.35, "sfx_ice", 0.5)
    c.freeze(31.0, 32.8, [lambda ctx, u: chalk(70, 320, "faster than", 56, u, 0.0, 0.3)
                          + amber(70, 420, "a pistol bullet", 76, u, 0.4)])
    c.sfx(31.0, "sfx_freeze", 0.4)
    # 32.8-36.8: teleporting changes where you are, not how fast you move
    hero(c, 32.8, "a7", 2180, "pole_plate")
    c.text(32.9, 36.8, lambda u, _t: chalk(70, 300, "change WHERE ✓", 64, u, 0.2, 0.4, bold=True)
           + amber(70, 410, "change HOW FAST ✗", 64, u, 2.3))
    # 36.8-end: the full video... until then — the skid again (loops into the opening)
    c.text(36.9, 40.5, full_video(230))
    cut(c, 40.5, "pole_plate", cam_on(500, P, 900))
    c.cam(c.end(), *cam_on(1000, P, 900), "lin")
    c.draw(40.5, c.end(), props.portal(420, P - 10, 380), front=False)
    c.sfx(40.55, "sfx_teleport", 0.45)
    hero(c, 40.6, "t1", 420, "pole_plate", y=P + 10)
    hero(c, c.end(), "t1", 900, "pole_plate", y=P + 10, tween="lin", smear=True)
    c.draw(40.6, c.end(), props.spray(420, 900, 3.7, P + 10, seed=9))
    c.text(41.0, c.end(), title("NEVER TELEPORT", "to the North Pole", 250, 70))
    c.music(0.0, "music_tense", 0.12)
    return c


def build(size):
    return [build_seq()]
