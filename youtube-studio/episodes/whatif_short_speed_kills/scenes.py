"""Short: How fast before super speed kills you? (vertical motion comic, art from whatif_super_speed).

Times are seconds of the aligned narration (projects/whatif_short_speed_kills/audio/narration_words.json).
Numbers on screen: script.md (60 mph = 97 km/h; 185 mph = 298 km/h; Category 5 >= 157 mph; > 6,000 lb ~ 3 t;
> 900 F ~ 500 C) plus Mach 1 = 343 m/s = 767 mph, Mach 3 ~ 2,300 mph.
"""

from __future__ import annotations

from studio.whatif import fx, overlay
from studio.whatif.comic import chalk_arrow, notes
from studio.whatif.shorts import (
    GROUND,
    HERO,
    W,
    amber,
    cam_on,
    chalk,
    full_video,
    heat,
    hud,
    new,
    scr,
    title,
    tx,
    wind,
)


def run_seq():
    c = new((1, 6), "highway_plate")
    GR = GROUND["highway_plate"]
    c.cast("hero", height=HERO)
    # 0-6.7: super speed, normal body
    c.cam(0.0, *cam_on(900, GR))
    c.key("hero", 0.0, "a7", 900, GR)
    c.text(0.2, 4.0, title("SUPER SPEED", "normal human body", 170, 66))
    c.sfx(0.2, "sfx_hit", 0.4)
    c.text(1.8, 4.0, tx(chalk_arrow(860, 620, 680, 760, 0.0, 0.4)))
    c.text(1.8, 4.0, lambda u, _t: chalk(1010, 590, "100 % human", 54, u, 0.3, bold=True, anchor="end"))
    c.key("hero", 4.0, "a5", 900, GR)
    c.text(4.0, 6.7, title("SO", "how fast can you go?", 330, 66))
    # the speed readout for the whole run
    c.text(4.3, 37.0, hud([(4.3, 0, "standing still"), (6.7, 60, "97 km/h"), (13.3, 60, "feet never slip"),
                           (15.1, 185, "298 km/h"), (20.2, 767, "MACH 1 · 1,235 km/h"),
                           (28.4, 2300, "MACH 3 · 3,700 km/h")]))
    # 6.7-13.2: 60 mph, one stumble
    c.key("hero", 6.7, "a0", 500, GR)
    c.key("hero", 8.2, "a0", 2200, GR, tween="lin")
    c.cam(6.7, *cam_on(500, GR), "hold")
    c.cam(8.2, *cam_on(2200, GR), "lin")
    c.speed_lines(6.7, 8.3)
    c.sfx(6.7, "sfx_dash", 0.45)
    c.key("hero", 8.3, "a1", 2240, GR - 40, ang=-10)
    c.key("hero", 9.4, "a1", 2420, GR + 30, ang=110, tween="in")
    c.cam(9.4, *cam_on(2380, GR), "ease")
    c.sfx(8.3, "sfx_slip", 0.5)
    c.sfx(9.4, "sfx_crash", 0.4)
    c.shake(9.4, 0.5, 26)
    c.draw(9.4, 13.3, fx.dust(2420, GR, n=22, size=260, life=3.0, seed=31))
    c.draw(9.4, 13.3, fx.debris(2420, GR, n=14, power=0.5, color=(84, 84, 88), seed=32, spread=(200, 330)))
    c.freeze(10.0, 13.2, [lambda ctx, u: notes([("one stumble at 60 mph", 56, True),
                                                 ("= the road at highway speed", 44, False),
                                                 ("no helmet · no leathers", 44, False)], 70, 380, 1.0, sc=False)(u)])
    c.sfx(10.0, "sfx_freeze", 0.4)
    # 13.2-20.1: feet never slip; 185 mph and a hurricane in the face
    c.rewind(13.2, 13.8)
    c.sfx(13.2, "sfx_rewind", 0.4)
    c.cam(13.2, *cam_on(900, GR), "hold")
    c.key("hero", 13.2, "hero7", 900, GR)
    c.text(13.5, 15.0, title("RULE", "your feet never slip", 315, 58))
    c.key("hero", 15.1, "a0", 500, GR)
    c.key("hero", 16.3, "a0", 1500, GR, tween="lin")
    c.cam(15.1, *cam_on(500, GR), "hold")
    c.cam(16.3, *cam_on(1500, GR), "lin")
    c.speed_lines(15.1, 20.1)
    c.sfx(15.1, "sfx_dash", 0.45)
    c.key("hero", 16.3, "b2", 1500, GR)
    c.key("hero", 20.1, "b2", 1800, GR, tween="lin")
    c.cam(20.1, *cam_on(1800, GR), "lin")
    c.draw(15.6, 28.3, wind(GR - 620, GR - 40, n=30, seed=41))
    c.text(16.6, 20.1, lambda u, _t: chalk(70, 345, "the wind in your face:", 44, u, 0.0)
           + chalk(70, 420, "> Category 5 hurricane", 60, u, 1.9, bold=True)
           + amber(1010, 470, "(157 mph +)", 38, u, 2.6, anchor="end"))
    # 20.2-27.7: the sound barrier: > 6,000 lb of air
    c.flash(20.2, 0.1)
    c.shake(20.2, 0.6, 24)
    c.sfx(20.2, "sfx_sonic", 0.5)
    c.key("hero", 20.2, "b3", 1800, GR)
    c.key("hero", 21.6, "b3", 1900, GR, tween="out")
    cam3 = cam_on(1900, GR)
    c.cam(21.6, *cam3, "ease")
    hx, hy = scr(cam3, 1900 + 150, GR - 300)
    c.freeze(21.7, 27.7, [
        lambda ctx, u: "".join(overlay.chalk_arrow(W - 40, hy - 120 + 120 * j, hx + 40, hy - 120 + 120 * j,
                                                   (u - 0.1 * j) / 0.4, seed=50 + j) for j in range(3)),
        lambda ctx, u: chalk(W - 60, hy - 200, "AIR", 64, u, 0.3, bold=True, anchor="end"),
        lambda ctx, u: chalk(110, 380, "> 6,000 lb", 104, u, 1.0, 0.4, bold=True),
        lambda ctx, u: amber(110, 460, "≈ 3 t · the weight of 2 cars", 44, u, 3.1),
    ])
    c.sfx(21.7, "sfx_freeze", 0.4)
    # 27.8-33.9: Mach 3: the air piles up and heats past 900 F
    c.key("hero", 27.8, "c0", 1900, GR)
    c.flash(28.4, 0.08)
    c.sfx(28.4, "sfx_dash", 0.4)
    c.draw(28.4, 33.9, heat(1860, GR - 250, 520))
    c.text(31.6, 33.9, lambda u, _t: chalk(70, 340, "air piling up in front:", 44, u, 0.0)
           + chalk(70, 440, "> 900 °F", 96, u, 0.3, 0.4, bold=True)
           + amber(1010, 440, "≈ 500 °C", 46, u, 0.8, anchor="end"))
    # 33.9-37.0: the speed never hurts you, the air does
    c.speed_lines(28.4, 33.9)
    c.cam(33.9, *cam_on(1300, GR), "hold")
    c.key("hero", 33.9, "a6", 1300, GR)
    c.text(34.0, 37.03, lambda u, _t: chalk(W / 2, 400, "speed: harmless", 64, u, 0.1, bold=True, anchor="middle")
           + chalk(W / 2, 500, "air: deadly", 84, u, 2.0, 0.4, bold=True, anchor="middle"))
    c.sfx(36.0, "sfx_hit", 0.4)
    c.music(0.0, "music_main", 0.13, until=c.end(9.0))
    return c


def save_seq():
    c = new((7, 7), "tower_plate", fade_out=0.5)
    GR = GROUND["tower_plate"]
    c.cast("hero", height=HERO)
    c.cast("cleaner", height=HERO * 0.98, ref="cleaner0")
    at = c.at
    t0 = 37.03                                           # shot 7 start in narration time

    def a(t):
        return at(7, t - t0)
    c.cam(a(37.03), *cam_on(1500, GR))
    c.key("hero", a(37.03), "c1", 1500, GR)
    c.text(a(37.1), a(39.2), title("BUT WHAT IF", "you were invulnerable?", 330, 62))
    c.sfx(a(37.1), "sfx_hit", 0.45)
    # 39.3: then you could save anyone... right?
    c.cam(a(39.2), *cam_on(1500, GR, vw=1000), "hold")
    c.cam(a(40.5), *cam_on(1500, GR), "out")
    c.key("cleaner", a(39.2), "cleaner3", 1510, GR - 880, fixed=True, scale=0.8)
    c.key("cleaner", a(40.5), "cleaner3", 1510, GR - 420, fixed=True, scale=0.8, tween="in")
    c.hide("cleaner", a(40.5))
    c.key("hero", a(39.2), "hero4", 1500, GR)
    c.key("hero", a(40.5), "a2", 1500, GR)
    c.sfx(a(39.3), "sfx_fall", 0.4)
    c.sfx(a(40.5), "sfx_catch", 0.45)
    c.shake(a(40.5), 0.35, 16)
    c.draw(a(40.5), c.end(), fx.dust(1500, GR, size=140, seed=61))
    c.freeze(a(40.7), a(41.7), [lambda ctx, u: chalk(W / 2, 440, "… right?", 92, u, 0.0, 0.4, bold=True,
                                                     anchor="middle")])
    c.text(a(41.7), c.end(), full_video(330))
    c.sfx(a(41.7), "sfx_chalk", 0.3)
    return c


def build(size):
    return [run_seq(), save_seq()]
