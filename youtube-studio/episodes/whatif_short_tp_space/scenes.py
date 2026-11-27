"""Short: never teleport to the space station (vertical, art from whatif_teleport; Higgsfield art only — code draws
only chalk arrows/text). Times = seconds of the aligned narration (+0.2 s intro). Rules: action in frame 1, no
numbers on screen in the first 5 s, a change every ~3 s, loop ending; the meteor is flipped so its fire trails behind.
"""

from __future__ import annotations

import math

from studio.whatif import overlay, props
from studio.whatif.comic import Comic
from studio.whatif.shorts import W, amber, chalk, full_video, title

SHEET = {"hero": 499, "cleaner": 481, "a": 424, "b": 394, "c": 455, "t": 2005}
K = 1.1                                   # hero size on the station plate (relative to the 400 px base)
HX, HY = 1150, 1000                       # where you float (plate px, the 'ground' point under the figure)


def build_seq():
    c = Comic(shots=(1, 8), plate="iss_plate_v")
    c.sheet_ref = dict(SHEET)
    c.shade = (0.5, 760)
    c.cast("hero", height=400)
    near = (HX + 60, 900, 820)                                   # only you in frame: the station is already gone
    wide = (1650, 1060, 1150)                                    # you + the station
    # 0-3.6: COLD OPEN — you pop out of a portal in orbit; the station is gone
    c.cam(0.0, *near)
    c.draw(0.0, c.end(), props.halo(HX + 10, HY - 230, 300), front=False)
    c.draw(0.0, 1.0, props.portal(HX, HY - 200, 420), front=False)
    c.sfx(0.0, "sfx_teleport", 0.5)
    c.key("hero", 0.0, "t5", HX, HY, scale=K, fixed=True)
    c.speed_lines(0.0, 3.6)
    c.text(0.3, 2.2, title("THE SPACE STATION", "you made it", 300, 66))
    c.text(2.2, 3.6, lambda u, _t: chalk(W / 2, 330, "it's already gone", 76, u, 0.0, 0.35, bold=True, anchor="middle")
           + overlay.chalk_arrow(640, 440, 980, 440, (u - 0.3) / 0.3, seed=11))
    # 3.6-11.1: it isn't hovering — it falls toward Earth and keeps missing (wide: the station appears)
    c.cam(3.6, *wide, "ease")
    c.text(3.8, 11.1, lambda u, _t: chalk(70, 210, "it isn't hovering", 58, u, 0.2, 0.4, bold=True)
           + amber(70, 300, "it falls the whole time…", 52, u, 2.0) + chalk(70, 385, "…and keeps missing", 52, u, 5.4))

    def orbit(u, _t):
        pts = [(80 + 230 * j, 1080 - 150 * math.sin(j / 4.0 * math.pi)) for j in range(5)]
        return overlay.chalk_line(pts, (u - 4.0) / 0.9, 6, seed=21, rough=False)
    c.text(3.8, 11.1, orbit)
    # 11.1-17.1: about five miles every second — falling, always missing: an orbit
    c.text(11.1, 17.1, lambda u, _t: amber(70, 280, "≈ 5 miles every second", 62, u, 0.3)
           + overlay.chalk_arrow(600, 760, 1000, 760, (u - 0.4) / 0.4, seed=31)
           + chalk(70, 400, "falling, always missing", 52, u, 2.6) + chalk(70, 480, "= an orbit", 60, u, 4.6, bold=True))
    c.speed_lines(11.4, 13.4)
    # 17.1-22.8: and you? only the speed of the ground you left: a crawl

    def bars(u, _t):
        q = min(1.0, max(0.0, (u - 1.4) / 0.8))
        return (chalk(70, 260, "the station", 46, u, 0.2) + f'<rect x="70" y="280" width="{880 * q:.0f}" height="44" '
                f'fill="{overlay.CHALK}"/>' + chalk(70, 390, "you", 46, u, 0.9)
                + f'<rect x="70" y="410" width="{60 * q:.0f}" height="44" fill="{overlay.AMBER}"/>'
                + amber(70, 540, "a crawl", 70, u, 4.4))
    c.text(17.1, 22.8, bars)
    # 22.8-25.7: the station zips away — and down you go
    c.cam(22.8, *near, "ease")
    c.whip(22.8, 23.3)
    c.sfx(22.8, "sfx_dash", 0.4)
    c.key("hero", 23.6, "t5", HX, HY, scale=K, fixed=True)
    c.key("hero", 25.7, "t5", HX + 60, HY + 380, scale=K, fixed=True, tween="in")
    c.cam(25.7, HX + 120, 1250, 820, "in")
    c.text(23.4, 25.7, title("DOWN", "you go", 220, 110))
    # 25.7-32.8: into the air at thousands of mph — you glow like a meteor (fire trails behind)
    c.key("hero", 25.7, "t6", HX + 60, HY + 380, scale=K * 1.15, fixed=True, flip=True)
    c.key("hero", 32.8, "t6", HX + 760, HY + 980, scale=K * 1.15, fixed=True, flip=True, tween="in")
    c.cam(32.8, HX + 800, 1500, 900, "in")
    c.sfx(26.0, "sfx_rocket", 0.35)
    c.text(27.4, 32.8, lambda u, _t: chalk(70, 260, "thousands of mph", 62, u, 0.6, 0.4, bold=True)
           + amber(70, 370, "glowing like a meteor", 60, u, 3.6))
    # 32.8-38.9: the real trick: height is easy, sideways speed is what costs you
    c.key("hero", 32.8, None)
    c.cut(32.8, "space_plate_v")
    c.cam(32.8, 1344, 1060, 1150, "hold")
    c.draw(32.8, 38.9, props.globe(1, 1344, 1400, 700))

    def side(u, _t):
        x0, y0 = 540, 900
        return (overlay.chalk_arrow(x0, y0, x0, y0 - 170, (u - 1.6) / 0.35, seed=41)
                + chalk(x0 + 24, y0 - 190, "up: easy", 46, u, 2.0)
                + overlay.chalk_arrow(x0, y0, x0 + 440, y0, (u - 3.6) / 0.5, seed=42)
                + amber(70, 400, "sideways speed:", 56, u, 4.2) + amber(70, 480, "what costs you", 56, u, 4.6)
                + chalk(70, 270, "the real trick", 64, u, 0.2, 0.4, bold=True))
    c.text(32.8, 38.9, side)
    # 38.9-end: full video; the station isn't even the worst — then the opening again (loop)
    c.cut(38.9, "iss_plate_v")
    c.cam(38.9, *near, "hold")
    c.text(39.0, 41.8, full_video(330))
    c.text(41.8, 43.8, lambda u, _t: chalk(70, 300, "and the station", 56, u, 0.0)
           + amber(70, 400, "isn't even the worst", 60, u, 0.5))
    c.draw(43.8, c.end(), props.portal(HX, HY - 200, 420), front=False)
    c.sfx(43.85, "sfx_teleport", 0.45)
    c.key("hero", 43.9, "t5", HX, HY, scale=K, fixed=True)
    c.speed_lines(43.9, c.end())
    c.music(0.0, "music_tense", 0.12)
    return c


def build(size):
    return [build_seq()]
