"""Original, code-generated explanatory diagrams.

Each diagram is a function (Theme) -> Canvas. Layout keeps y > 880 free for captions.
All diagrams are schematic: no real map geometry or measured dimensions are implied, and
they contain no numbers (numbers live in narration, tied to verified claims).

Motion hints understood by studio.motion (ignored by the static SVG export):
  anim="draw|grow|fade|slide|none", dur=<x reveal time>, delay=<x reveal time>,
  flow=<colour> (pulses travel along a line), pulse=True|<colour> (ring around a circle),
  hud=True (fixed on screen), nofocus=True (ignored by the auto camera).
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from studio.visuals import Canvas, Theme, base_frame, blob, quad_curve

WAVE_COLORS = ["#FF6B6B", "#FFD93D", "#6BCB77", "#4D96FF", "#C77DFF"]
LIGHT = "#E6FFFB"
POWER = "#E8A33D"


@dataclass
class Diagram:
    id: str
    title: str
    build: Callable[[Theme], Canvas]
    default_camera: str = "auto"


def _x_mark(c: Canvas, x: float, y: float, color: str, step: int, size: float = 30,
            until: int | None = None) -> None:
    c.line([(x - size, y - size), (x + size, y + size)], color=color, width=9, step=step,
           until=until, anim="fade")
    c.line([(x + size, y - size), (x - size, y + size)], color=color, width=9, step=step,
           until=until, anim="fade", delay=0.2)


def _ship(c: Canvas, x: float, y: float, t: Theme, step: int, until: int | None = None,
          **fx) -> None:
    fx.setdefault("anim", "slide")
    fx.setdefault("slide_from", (260.0, 0.0))
    c.polygon([(x - 170, y), (x + 170, y), (x + 130, y + 60), (x - 150, y + 60)],
              fill=t.fg, step=step, until=until, **fx)
    c.rect(x - 60, y - 70, 120, 70, fill=t.fg, step=step, until=until, **fx)
    c.rect(x - 40, y - 55, 80, 20, fill=t.bg, step=step, until=until, **fx)


# ------------------------------------------------------------------------------ hook


def atlantic_telegraph(t: Theme) -> Canvas:
    """Cold open: a cable is laid across an ocean, carries messages, then fails."""
    c = base_frame(t, "A cable across the Atlantic")
    land = t.muted + "66"
    west = [(0, 180), (260, 200), (330, 330), (300, 520), (360, 700), (300, 880), (0, 880)]
    east = [(1920, 170), (1650, 210), (1600, 360), (1660, 520), (1590, 690), (1650, 880),
            (1920, 880)]
    c.polygon(west, fill=land, stroke=t.muted, sw=2)
    c.polygon(east, fill=land, stroke=t.muted, sw=2)
    c.text(150, 260, "North America", size=30, color=t.fg, anchor="mm")
    c.text(1780, 250, "Europe", size=30, color=t.fg, anchor="mm")
    for k in range(5):  # gentle swell lines
        y = 300 + k * 110
        c.line(quad_curve((420, y), (960, y - 30), (1500, y)), color=t.accent + "26", width=2,
               anim="none")
    route = quad_curve((330, 470), (960, 640), (1600, 450), n=80)
    # step 1: the cable is laid
    c.line(route, color=t.accent, width=6, step=1, until=2, dur=3.0, flow=LIGHT,
           flow_gap=260, flow_speed=320)
    c.text(960, 690, "A telegraph cable on the sea floor", size=34, color=t.accent,
           anchor="mt", bold=True, step=1, until=1, delay=1.5)
    for x, y in ((330, 470), (1600, 450)):
        c.circle(x, y, 14, fill=t.accent2, stroke=t.bg, sw=4, step=1, pulse=True)
    # step 2: messages in minutes instead of weeks
    c.text(960, 690, "Messages crossed the ocean without a ship", size=34, color=t.accent2,
           anchor="mt", bold=True, step=2, until=2)
    # step 3: it fails
    c.line(route, color=t.muted, width=6, step=3, anim="fade")
    _x_mark(c, 960, 555, t.danger, step=3, size=34)
    c.text(960, 690, "Then, after a few weeks, it failed", size=38, color=t.danger,
           anchor="mt", bold=True, step=3)
    return c


# ------------------------------------------------------------------------------ the map


ROUTE_STATIONS = {"A": (560, 330), "B": (575, 520), "C": (540, 680),
                  "D": (1345, 300), "E": (1330, 460), "F": (1300, 800)}


def route_schematic(t: Theme) -> Canvas:
    c = base_frame(t, "Cable routes (schematic)")
    land = t.muted + "66"
    west = blob(330, 500, 250, 300, seed=1)
    east = blob(1620, 330, 290, 190, seed=4)
    south = blob(1600, 830, 320, 120, seed=7)
    for poly in (west, east, south):
        c.polygon(poly, fill=land, stroke=t.muted, sw=2)
    s = ROUTE_STATIONS
    curves = {
        "AD": quad_curve(s["A"], (950, 200), s["D"]),
        "BE": quad_curve(s["B"], (960, 420), s["E"]),
        "BD": quad_curve(s["B"], (950, 330), s["D"]),
        "CF": quad_curve(s["C"], (900, 800), s["F"]),
        "CS": quad_curve(s["C"], (1100, 640), (1920, 640), n=60),  # through the strait
    }
    # step 1: one cable system between two landing stations
    c.line(curves["AD"], color=t.accent, width=5, step=1, until=3, dur=1.6, flow=LIGHT)
    for name in "AD":
        c.circle(*s[name], 13, fill=t.accent2, stroke=t.bg, sw=4, step=1, pulse=True)
    c.text(545, 300, "Landing station", size=30, color=t.fg, anchor="rb", step=1, until=2)
    c.text(950, 230, "Cable system", size=30, color=t.accent, anchor="mb", step=1, until=3)
    # step 2: many systems
    for key in ("BE", "BD", "CF", "CS"):
        c.line(curves[key], color=t.accent, width=5, step=2, until=None if key != "BE" else 3,
               dur=1.4, flow=LIGHT)
    for name in "BCEF":
        c.circle(*s[name], 13, fill=t.accent2, stroke=t.bg, sw=4, step=2)
    # step 3: a chokepoint - a narrow corridor between two coasts that many cables share
    for dy in (-34, -12, 12, 34):
        c.line(quad_curve((1150, 640 + dy), (1500, 640 + dy * 0.35), (1920, 640 + dy * 0.8)),
               color=t.accent2, width=3, step=3, dur=1.4, flow=t.accent2, flow_gap=150)
    c.rect(1440, 560, 260, 160, stroke=t.accent2, sw=4, r=20, step=3, anim="grow")
    c.text(1570, 740, "Chokepoint", size=32, color=t.accent2, anchor="mt", bold=True, step=3,
           delay=0.6)
    c.text(1570, 788, "many cables, one corridor", size=26, color=t.fg, anchor="mt", step=3,
           delay=0.8)
    # step 4: route diversity - one route cut, traffic carried by the others
    c.line(curves["AD"], color=t.accent2, width=9, step=4, anim="fade", flow=LIGHT,
           flow_speed=360, flow_gap=140)
    broken = curves["BE"]
    c.line(broken[:18], color=t.muted, width=5, step=4, anim="fade")
    c.line(broken[23:], color=t.muted, width=5, step=4, anim="fade")
    mx, my = broken[20]
    _x_mark(c, mx, my, t.danger, step=4)
    c.text(960, 180, "One route cut - traffic moves to the others", size=34, color=t.fg,
           anchor="mt", bold=True, step=4, delay=0.5)
    return c


def landing_station(t: Theme) -> Canvas:
    c = base_frame(t, "Where cables come ashore")
    land_y = 420
    # sea (left) with a sloping floor; land (right)
    c.rect(80, land_y + 20, 820, 420, fill=t.accent + "18", until=1)
    c.line([(80, land_y + 20), (900, land_y + 20)], color=t.accent, width=3, until=1)
    c.polygon([(80, 800), (420, 780), (700, 680), (900, land_y + 20), (980, land_y),
               (1840, land_y), (1840, 860), (80, 860)], fill=t.muted + "77", until=1)
    c.text(400, 480, "Sea", size=30, color=t.muted, anchor="mt", until=1)
    c.text(1500, 640, "Land", size=30, color=t.muted, anchor="mt", until=1)
    # step 1: cable comes ashore into a landing station, then onto land networks
    cable = [(80, 785), (420, 765), (700, 665), (900, land_y + 30), (1000, land_y - 10)]
    c.line(cable, color=t.accent, width=6, step=1, until=1, dur=1.8, flow=LIGHT)
    c.rect(990, land_y - 130, 170, 130, fill=t.fg, r=10, step=1, until=1, anim="grow")
    c.text(1075, land_y - 150, "Landing station", size=32, color=t.fg, anchor="mb", bold=True,
           step=1, until=1, delay=0.6)
    for k, y in enumerate((land_y - 110, land_y - 65, land_y - 20)):
        c.line([(1160, y), (1500, y), (1560, y - 60 + k * 60)], color=t.accent2, width=4,
               step=1, until=1, delay=0.9 + 0.2 * k, flow=t.accent2, flow_gap=120)
    for k, (x, h) in enumerate(((1590, 120), (1650, 170), (1720, 90), (1780, 140))):
        c.rect(x, land_y - h, 50, h, fill=t.accent2 + "AA", step=1, until=1,
               delay=1.2 + 0.1 * k)
    c.text(1690, land_y - 190, "Networks on land", size=30, color=t.accent2, anchor="mb",
           step=1, until=1, delay=1.4)
    # step 2: narrow corridors shared by many cables (full composition)
    top = [(80, 180), (1840, 180), (1840, 420), (1500, 470), (1150, 500), (800, 490),
           (450, 450), (80, 420)]
    bottom = [(80, 860), (1840, 860), (1840, 690), (1500, 640), (1150, 610), (800, 625),
              (450, 660), (80, 700)]
    c.polygon(top, fill=t.muted + "88", step=2, anim="fade")
    c.polygon(bottom, fill=t.muted + "88", step=2, anim="fade")
    c.text(960, 190, "Narrow corridors", size=40, color=t.accent2, anchor="mt", bold=True,
           step=2, delay=0.4)
    for k in range(7):
        y0 = 450 + k * 35
        y1 = 520 + k * 14
        c.line(quad_curve((80, y0), (960, y1 + 10), (1840, y0 - 10)), color=t.accent,
               width=4, step=2, delay=0.3 + 0.1 * k, flow=LIGHT, flow_gap=220)
    c.text(960, 800, "e.g. the Red Sea and the Strait of Malacca", size=32, color=t.fg,
           anchor="mm", bold=True, step=2, delay=1.0)
    return c


def route_diversity(t: Theme) -> Canvas:
    c = base_frame(t, "Why the arrangement matters")
    land = t.muted + "66"
    panels = [(120, "Several cables, different landings"), (1000, "Only one cable")]
    for x0, title in panels:
        c.rect(x0, 190, 800, 650, fill=t.muted + "12", stroke=t.muted, sw=2, r=24)
        c.text(x0 + 400, 225, title, size=32, color=t.fg, anchor="mt", bold=True)
    a = blob(330, 520, 150, 210, seed=3)
    b = blob(1210, 520, 150, 210, seed=5)
    c.polygon(a, fill=land, stroke=t.muted, sw=2)
    c.polygon(b, fill=land, stroke=t.muted, sw=2, until=0)
    c.polygon(b, fill=t.danger + "33", stroke=t.danger, sw=3, step=1, anim="fade", delay=0.6)
    a_cables = [((450, 380), (900, 330)), ((470, 480), (900, 450)), ((470, 590), (900, 600)),
                ((440, 690), (900, 740))]
    for k, (p0, p1) in enumerate(a_cables):
        pts = quad_curve(p0, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - 30), p1)
        c.line(pts, color=t.accent, width=5, flow=LIGHT, until=0 if k == 1 else None)
        c.circle(*p0, 11, fill=t.accent2, stroke=t.bg, sw=3)
        if k == 1:
            c.line(pts[:18], color=t.muted, width=5, step=1, anim="fade")
            _x_mark(c, *pts[22], t.danger, step=1, size=24)
    b_pts = quad_curve((1340, 520), (1560, 490), (1780, 520))
    c.line(b_pts, color=t.accent, width=5, flow=LIGHT, until=0)
    c.circle(1340, 520, 11, fill=t.accent2, stroke=t.bg, sw=3)
    c.line(b_pts[:18], color=t.muted, width=5, step=1, anim="fade")
    _x_mark(c, *b_pts[22], t.danger, step=1, size=24)
    c.text(520, 800, "Loses one - still connected", size=30, color=t.accent, anchor="mb",
           bold=True, step=1, delay=0.8)
    c.text(1400, 800, "Loses one - cut off", size=30, color=t.danger, anchor="mb", bold=True,
           step=1, delay=0.8)
    return c


# ------------------------------------------------------------------------------ light in glass


def fiber_tir(t: Theme) -> Canvas:
    c = base_frame(t, "Light in an optical fibre")
    c.rect(160, 300, 1600, 340, fill=t.muted + "55", stroke=t.muted, sw=2, r=20)
    c.rect(160, 410, 1600, 120, fill=t.accent + "40", stroke=t.accent, sw=2)
    c.text(190, 330, "Cladding - lower refractive index", size=30, color=t.fg)
    c.text(190, 470, "Core", size=30, color=t.fg, anchor="lm", bold=True)
    c.text(190, 600, "Cladding", size=30, color=t.fg)
    xs = list(range(320, 1700, 160))
    pts = [(x, 418 if i % 2 == 0 else 522) for i, x in enumerate(xs)]
    c.line(pts[:-1], color=t.accent2, width=6, step=1, dur=2.2, flow=LIGHT, flow_gap=240)
    c.arrow(*pts[-2], *pts[-1], color=t.accent2, width=6, head=26, step=1, delay=1.6)
    c.text(960, 690, "Light reflects at the core boundary and stays inside", size=34,
           color=t.accent2, anchor="mt", bold=True, step=1, until=1, delay=1.4)
    # step 2: a steep ray escapes; shallow rays are reflected
    c.line([(640, 522), (760, 418), (820, 240)], color=t.muted, width=4, dash=(16, 12), step=2,
           dur=1.4)
    c.text(830, 230, "Too steep: escapes", size=28, color=t.muted, anchor="lb", step=2,
           delay=1.0)
    c.circle(xs[3], 522, 30, stroke=t.fg, sw=3, step=2, pulse=t.fg)
    c.text(xs[3], 770, "Total internal reflection", size=34, color=t.fg, anchor="mt", step=2)
    c.line([(xs[3], 556), (xs[3], 760)], color=t.fg, width=2, dash=(8, 8), step=2)
    return c


def wdm_colors(t: Theme) -> Canvas:
    c = base_frame(t, "Many colours, one fibre")
    c.rect(520, 330, 170, 280, fill=t.bg, stroke=t.fg, sw=3, r=16)
    c.text(605, 470, "MUX", size=38, color=t.fg, anchor="mm", bold=True)
    c.rect(1230, 330, 170, 280, fill=t.bg, stroke=t.fg, sw=3, r=16)
    c.text(1315, 470, "DEMUX", size=34, color=t.fg, anchor="mm", bold=True)
    c.line([(690, 470), (1230, 470)], color=t.fg, width=14)
    c.text(960, 430, "Single fibre", size=28, color=t.muted, anchor="mb")
    for i, color in enumerate(WAVE_COLORS):
        y = 360 + i * 55
        c.line([(220, y), (520, y)], color=color, width=7, step=1, delay=0.15 * i,
               flow=color, flow_gap=110, flow_speed=180)
        c.line([(700, 462 + i * 4), (1220, 462 + i * 4)], color=color, width=3, step=1,
               delay=0.6 + 0.1 * i, flow=color, flow_gap=170, flow_speed=260)
        c.line([(1400, y), (1700, y)], color=color, width=7, step=1, delay=1.2 + 0.1 * i,
               flow=color, flow_gap=110, flow_speed=180)
    c.text(220, 330, "Separate channels", size=28, color=t.fg, anchor="lb", step=1)
    c.text(1700, 330, "Separated again", size=28, color=t.fg, anchor="rb", step=1, delay=1.4)
    c.rect(470, 650, 980, 130, fill=t.accent2 + "22", stroke=t.accent2, sw=2, r=16, step=2)
    c.text(960, 715, "Upgrade the equipment at each end - the glass stays on the sea floor",
           size=32, color=t.accent2, anchor="mm", step=2)
    return c


# ------------------------------------------------------------------------------ repeaters


def repeater_chain(t: Theme) -> Canvas:
    c = base_frame(t, "Keeping the signal alive")
    seabed_y = 640
    c.line([(80, seabed_y + 40), (1840, seabed_y + 40)], color=t.muted, width=3)
    for x, label in ((110, "Landing station"), (1650, "Landing station")):
        c.rect(x, seabed_y - 120, 160, 120, fill=t.muted + "88", stroke=t.fg, sw=2, r=8)
        c.text(x + 80, seabed_y - 140, label, size=26, color=t.fg, anchor="mb")
    c.line([(270, seabed_y - 30), (1650, seabed_y - 30)], color=t.accent, width=6)
    reps = [470, 690, 910, 1130, 1350, 1570]
    # step 1: signal fades without help
    top, bottom = 200, 420
    decay = [(x, bottom - (bottom - top) * math.exp(-(x - 280) / 380))
             for x in range(280, 1640, 20)]
    c.line(decay, color=t.danger, width=5, step=1, until=1, dur=2.5)
    c.text(300, 180, "Signal strength without repeaters: it fades away", size=30,
           color=t.danger, anchor="lb", step=1, until=1)
    # step 2: repeaters restore the signal (sawtooth)
    for k, x in enumerate(reps):
        c.rect(x - 34, seabed_y - 52, 68, 44, fill=t.accent2, stroke=t.bg, sw=3, r=10, step=2,
               delay=0.15 * k)
        c.circle(x, seabed_y - 30, 20, stroke=t.accent2, sw=2, step=2, pulse=t.accent2,
                 anim="fade", nofocus=True)
    saw: list[tuple[float, float]] = []
    prev = 280
    for x in reps + [1640]:
        for xx in range(prev, x, 20):
            saw.append((xx, top + (bottom - top) * 0.7 * (1 - math.exp(-(xx - prev) / 300))))
        saw.append((x, top))
        prev = x
    c.line(saw, color=t.accent2, width=5, step=2, dur=2.5)
    c.text(300, 180, "With repeaters: amplified again and again", size=30, color=t.accent2,
           anchor="lb", step=2)
    c.text(reps[2] + 110, seabed_y + 70, "Repeaters", size=28, color=t.accent2, anchor="mt",
           step=2)
    c.line([(270, seabed_y - 30), (1650, seabed_y - 30)], color=t.accent, width=6, step=2,
           anim="none", flow=LIGHT, flow_gap=180, nofocus=True)
    # step 3: inside a repeater (optical amplifier)
    c.rect(560, 440, 800, 150, fill=t.bg, stroke=t.accent2, sw=3, r=16, step=3, until=3)
    c.text(960, 458, "Inside: erbium-doped fibre amplifier", size=28, color=t.accent2,
           anchor="mt", bold=True, step=3, until=3)
    c.arrow(600, 540, 760, 540, color=t.danger, width=4, step=3, until=3)
    c.text(680, 556, "weak", size=24, color=t.fg, anchor="mt", step=3, until=3)
    c.rect(770, 515, 380, 50, fill=t.accent + "55", stroke=t.accent, sw=2, r=24, step=3,
           until=3)
    c.text(960, 540, "doped fibre + pump laser", size=24, color=t.fg, anchor="mm", step=3,
           until=3)
    c.arrow(1160, 540, 1320, 540, color=t.accent2, width=8, step=3, until=3)
    c.text(1240, 556, "strong", size=24, color=t.fg, anchor="mt", step=3, until=3)
    # step 4: DC power feed from the landing stations
    c.line([(270, seabed_y - 14), (1650, seabed_y - 14)], color=POWER, width=3,
           dash=(14, 10), step=4, dur=2.0)
    c.line([(270, seabed_y - 14), (1650, seabed_y - 14)], color=POWER, width=1, step=4,
           anim="none", flow=POWER, flow_gap=120, flow_speed=200, nofocus=True)
    c.arrow(300, 770, 520, 770, color=POWER, width=4, step=4)
    c.arrow(1620, 770, 1400, 770, color=POWER, width=4, step=4)
    c.text(960, 830, "DC power fed from shore through a conductor in the cable", size=30,
           color=POWER, anchor="mm", bold=True, step=4)
    return c


def edfa_inside(t: Theme) -> Canvas:
    c = base_frame(t, "Inside an optical amplifier")
    c.rect(330, 250, 1260, 520, fill=t.muted + "18", stroke=t.muted, sw=2, r=30)
    c.text(960, 280, "Repeater housing (schematic)", size=26, color=t.muted, anchor="mt")
    y = 470
    # input / coupler / doped coil / output
    c.line([(120, y), (560, y)], color=t.accent, width=5)
    c.text(140, y - 40, "Weak signal in", size=30, color=t.fg, anchor="lb")
    c.polygon([(560, y - 34), (640, y - 8), (640, y + 8), (560, y + 34)], fill=t.fg)
    c.text(600, y - 50, "Coupler", size=24, color=t.fg, anchor="mb")
    coil = []
    for i in range(0, 361):
        a = i / 360 * 2 * math.pi * 5
        coil.append((680 + i * 1.5 + 40 * math.sin(a) * 0.4, y + 70 * math.sin(a)))
    c.line(coil, color=t.accent + "AA", width=4)
    c.text(950, y + 120, "Fibre doped with erbium", size=28, color=t.fg, anchor="mt")
    c.line([(1240, y), (1800, y)], color=t.accent, width=5)
    # flows: weak input
    c.line([(120, y), (560, y)], color=t.accent, width=2, anim="none", flow="#7FA9B5",
           flow_gap=150, flow_speed=160, nofocus=True)
    # step 1: the pump laser energises the erbium
    c.rect(520, 620, 180, 90, fill=t.danger + "CC", r=12, step=1, anim="grow")
    c.text(610, 665, "Pump laser", size=26, color=t.fg, anchor="mm", bold=True, step=1)
    c.line([(610, 620), (610, y + 10)], color=t.danger, width=5, step=1, delay=0.4,
           flow=t.danger, flow_gap=40, flow_speed=120)
    c.line(coil, color=t.danger, width=6, step=1, delay=0.8, dur=2.0)
    c.text(950, 360, "Excited erbium adds energy to the passing light", size=28,
           color=t.danger, anchor="mb", step=1, delay=1.2)
    # step 2: strong signal out - still light
    c.line([(1240, y), (1800, y)], color=t.accent2, width=10, step=2, flow=LIGHT,
           flow_gap=110, flow_speed=360)
    c.text(1780, y - 40, "Stronger signal out", size=30, color=t.accent2, anchor="rb",
           bold=True, step=2)
    c.text(960, 830, "Amplified as light - no conversion to an electrical signal", size=32,
           color=t.fg, anchor="mm", bold=True, step=2, delay=0.6)
    return c


def cable_cross_section(t: Theme) -> Canvas:
    c = base_frame(t, "Inside a submarine cable")
    cx, cy = 620, 500
    # step 4: shore-end armour (outermost)
    for i in range(36):
        a = 2 * math.pi * i / 36
        c.circle(cx + 300 * math.cos(a), cy + 300 * math.sin(a), 24, fill="#5E6B73",
                 stroke=t.bg, sw=2, step=4, delay=i * 0.02)
    c.circle(cx, cy, 270, fill="#1F2A30", stroke=t.fg, sw=3, step=3)  # polyethylene sheath
    c.circle(cx, cy, 200, fill="#B08D57", stroke=t.bg, sw=2, step=2)  # power conductor
    c.circle(cx, cy, 176, fill=t.bg, step=1)
    for i in range(18):  # steel strength wires
        a = 2 * math.pi * i / 18
        c.circle(cx + 140 * math.cos(a), cy + 140 * math.sin(a), 30, fill="#A9B4BB",
                 stroke=t.bg, sw=2, step=1, delay=i * 0.03)
    c.circle(cx, cy, 100, fill="#E9EEF1", stroke=t.fg, sw=2)  # tube
    for i, color in enumerate(WAVE_COLORS + ["#FFFFFF", "#FF9F1C", "#2EC4B6"]):
        a = 2 * math.pi * i / 8
        c.circle(cx + 50 * math.cos(a), cy + 50 * math.sin(a), 14, fill=color, stroke="#333333",
                 sw=1)
    labels = [
        (0, "Optical fibres inside a protective tube", cy - 10, cx + 50),
        (1, "Steel strength wires", cy - 140, cx + 140),
        (2, "Conductor - carries power", cy + 120, cx + 190),
        (3, "Polyethylene insulation", cy + 230, cx + 240),
        (4, "Extra steel armour near the shore", cy - 300, cx + 280),
    ]
    for step, label, ly, lx in labels:
        c.line([(lx, ly), (1060, ly)], color=t.fg, width=2, step=step, delay=0.5)
        c.circle(lx, ly, 6, fill=t.fg, step=step)
        c.text(1080, ly, label, size=32, color=t.fg, anchor="lm", step=step, delay=0.9)
    c.paragraph(1080, 800, "Deep-sea cable has fewer protective layers than shore-end cable",
                size=28, color=t.muted, max_width=780, step=4)
    return c


# ------------------------------------------------------------------------------ laying and repair


def cable_laying(t: Theme) -> Canvas:
    c = base_frame(t, "Laying a cable")
    sea_y = 300
    c.rect(0, sea_y, 1920, 580, fill=t.accent + "18")
    c.line([(0, sea_y), (1920, sea_y)], color=t.accent, width=3)
    floor = [(x, 560 + 230 * (x / 1920) ** 1.6 + 18 * math.sin(x / 70)) for x in range(0, 1921, 20)]
    c.polygon(floor + [(1920, 880), (0, 880)], fill=t.muted + "88")
    # step 0: survey the route first (hazards marked)
    _ship(c, 1300, sea_y - 60, t, 0, until=0)
    for k in range(-4, 5):
        c.line([(1300, sea_y), (1300 + k * 70, 720)], color=t.accent2 + "88", width=2, step=0,
               until=0)
    c.circle(1300, sea_y + 10, 30, stroke=t.accent2, sw=2, step=0, until=0, pulse=t.accent2,
             nofocus=True)
    for hx in (640, 980):
        c.circle(hx, 640 + 230 * (hx / 1920) ** 1.6 - 10, 24, stroke=t.danger, sw=4, step=0,
                 until=0)
    c.text(810, 520, "Hazards to avoid", size=28, color=t.danger, anchor="mb", step=0,
           until=0)
    c.text(640, 210, "Survey the route first", size=34, color=t.accent2, anchor="mb",
           bold=True, step=0, until=0)
    # step 1: cable ship pays out cable over the stern
    _ship(c, 1250, sea_y - 60, t, 1)
    c.rect(1150, sea_y - 52, 70, 40, fill=t.accent2, step=1, delay=0.8)
    c.text(1060, sea_y - 30, "Cable tank", size=24, color=t.fg, anchor="rm", step=1, delay=0.9)
    lay = quad_curve((1080, sea_y + 10), (950, 560), (560, 640))
    c.line(lay + [(100, 600)], color=t.accent2, width=6, step=1, delay=1.0, dur=2.6)
    c.text(600, 210, "Laid along the route as the ship moves", size=34, color=t.accent2,
           anchor="mb", bold=True, step=1)
    # step 2: plough burial in shallow water, deep water laid on the bottom
    c.rect(330, 585, 120, 50, fill=t.fg, r=8, step=2, anim="slide", slide_from=(-200.0, 0.0))
    c.line([(450, 600), (900, 360), (1080, sea_y + 10)], color=t.fg, width=3, dash=(12, 8),
           step=2)
    c.text(390, 680, "Shallow water: buried by a sea plough", size=28, color=t.fg, anchor="mt",
           step=2)
    c.text(1500, 840, "Deep water: laid on the sea bed", size=28, color=t.fg, anchor="mb",
           step=2, delay=0.8)
    return c


def cable_repair(t: Theme) -> Canvas:
    c = base_frame(t, "Repairing a cable at sea")
    sea_y = 300
    c.rect(0, sea_y, 1920, 580, fill=t.accent + "18")
    c.line([(0, sea_y), (1920, sea_y)], color=t.accent, width=3)
    c.rect(0, 760, 1920, 120, fill=t.muted + "88")
    c.rect(60, 180, 180, 120, fill=t.muted + "88", stroke=t.fg, sw=2, r=8)
    c.text(255, 205, "Shore station", size=26, color=t.fg, anchor="lm")
    # step 0: fault location by test signals
    c.line([(240, 290), (300, 760), (1100, 755)], color=t.accent, width=6, step=0, until=1)
    c.line([(1180, 755), (1860, 760)], color=t.accent, width=6, step=0, until=1)
    c.line([(1120, 730), (1160, 780)], color=t.danger, width=7, step=0, until=1)
    c.line([(1160, 730), (1120, 780)], color=t.danger, width=7, step=0, until=1)
    c.line([(240, 290), (300, 760), (1100, 755)], color=t.accent2, width=2, step=0, until=0,
           anim="none", flow=t.accent2, flow_gap=160, flow_speed=300)
    c.text(700, 690, "Test signals locate the fault", size=30, color=t.accent2, anchor="mb",
           step=0, until=0)
    # step 1: grapnel
    _ship(c, 1140, sea_y - 60, t, 1, until=1)
    c.line([(1140, sea_y), (1110, 740)], color=t.fg, width=3, step=1, until=1, delay=0.8,
           dur=1.6)
    c.polygon([(1095, 740), (1125, 740), (1110, 770)], fill=t.fg, step=1, until=1, delay=2.2)
    c.text(1180, 520, "A grapnel catches the cable", size=30, color=t.accent2, anchor="lm",
           step=1, until=1, delay=1.6)
    # step 2: ends recovered, one buoyed; splice on board
    _ship(c, 1140, sea_y - 60, t, 2, anim="none")
    c.line([(240, 290), (300, 760), (900, 755), (1060, sea_y)], color=t.accent, width=6,
           step=2)
    c.line([(1860, 760), (1400, 755), (1300, sea_y + 10)], color=t.accent, width=6, step=2,
           delay=0.5)
    c.text(1330, sea_y - 95, "Splice on board", size=28, color=t.accent2, anchor="lm",
           bold=True, step=2, until=2, delay=1.0)
    # step 3: lowered back, slightly longer
    c.line([(900, 755), (980, 830), (1320, 830), (1400, 755)], color=t.accent2, width=6,
           step=3, dur=1.8)
    c.text(1150, 842, "New section - the cable is now a little longer", size=28,
           color=t.accent2, anchor="mt", step=3)
    return c


# ------------------------------------------------------------------------------ failures


def failure_modes(t: Theme) -> Canvas:
    c = base_frame(t, "What damages cables")
    c.rect(140, 200, 780, 600, fill=t.accent2 + "14", stroke=t.accent2, sw=3, r=24)
    c.text(530, 240, "Most common: human activity", size=38, color=t.accent2, anchor="mt",
           bold=True)
    # anchor icon
    ax, ay = 330, 520
    fx = {"anim": "slide", "slide_from": (0.0, -120.0)}
    c.circle(ax, ay - 140, 22, stroke=t.fg, sw=6, **fx)
    c.line([(ax, ay - 118), (ax, ay + 60)], color=t.fg, width=10, **fx)
    c.line([(ax - 60, ay - 80), (ax + 60, ay - 80)], color=t.fg, width=10, **fx)
    c.line(quad_curve((ax - 110, ay - 10), (ax - 80, ay + 90), (ax, ay + 70)), color=t.fg,
           width=10, **fx)
    c.line(quad_curve((ax + 110, ay - 10), (ax + 80, ay + 90), (ax, ay + 70)), color=t.fg,
           width=10, **fx)
    c.text(ax, 700, "Ship anchors", size=32, color=t.fg, anchor="mt")
    # trawl net icon
    nx, ny = 700, 470
    c.polygon([(nx - 120, ny - 80), (nx + 100, ny - 30), (nx + 100, ny + 30), (nx - 120, ny + 80)],
              stroke=t.fg, sw=5)
    for k in range(1, 5):
        x = nx - 120 + k * 44
        c.line([(x, ny - 80 + k * 10), (x, ny + 80 - k * 10)], color=t.fg, width=2)
    c.text(nx, 700, "Fishing gear", size=32, color=t.fg, anchor="mt")
    # step 1: natural hazards
    c.rect(1000, 200, 780, 600, fill=t.muted + "22", stroke=t.muted, sw=3, r=24, step=1)
    c.text(1390, 240, "Rarer, but wide-reaching: nature", size=38, color=t.fg, anchor="mt",
           bold=True, step=1)
    slope = [(1060, 380), (1300, 420), (1560, 640), (1740, 700), (1740, 760), (1060, 760)]
    c.polygon(slope, fill=t.muted + "88", step=1)
    for k, dx in enumerate((0, 50, 100)):
        c.arrow(1330 + dx, 470 + k * 25, 1470 + dx, 600 + k * 25, color=t.danger, width=5,
                step=1, delay=0.6 + 0.2 * k)
    for k in range(3):
        y = 650 + k * 25
        c.line([(1080, y), (1740, y + 30)], color=t.accent, width=4, step=1)
    c.text(1390, 790, "Undersea landslides can cut several cables at once", size=28,
           color=t.fg, anchor="mb", step=1)
    return c


def quake_landslide(t: Theme) -> Canvas:
    c = base_frame(t, "When the sea floor moves")
    slope = [(80, 300), (520, 330), (900, 470), (1250, 690), (1840, 760), (1840, 860),
             (80, 860)]
    c.polygon(slope, fill=t.muted + "88", stroke=t.muted, sw=2)
    c.text(300, 270, "Continental slope", size=28, color=t.fg, anchor="mb")
    def slope_y(x: float) -> float:
        for (x0, y0), (x1, y1) in zip(slope, slope[1:4], strict=False):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return 760.0

    cables = [(x, slope_y(x) - 13) for x in (700, 960, 1160, 1500)]
    for x, y in cables:
        c.circle(x, y, 13, fill=t.accent, stroke=t.bg, sw=3, pulse=LIGHT, until=1)
    c.text(1180, 420, "Cables on the slope (seen end-on)", size=28, color=t.accent,
           anchor="mb")
    # step 1: the earthquake shakes the slope
    for r in (40, 80, 120):
        c.circle(520, 330, r, stroke=t.danger, sw=4, step=1, pulse=t.danger, anim="grow")
    c.text(520, 200, "Earthquake", size=32, color=t.danger, anchor="mb", bold=True, step=1)
    # step 2: a landslide / sediment flow runs downslope and cuts several cables
    slide = [(560, 335), (900, 470), (1250, 690), (1700, 740), (1700, 790), (1200, 760),
             (850, 540), (560, 380)]
    c.polygon(slide, fill="#8C5A3C" + "CC", step=2, anim="slide", slide_from=(-300.0, -150.0),
              dur=2.2)
    for x, y in cables:
        c.circle(x, y, 13, fill=t.muted, stroke=t.bg, sw=3, step=2, anim="fade", delay=1.0)
        _x_mark(c, x, y - 40, t.danger, step=2, size=20)
    c.text(960, 830, "One event can damage several cables at once", size=34, color=t.fg,
           anchor="mm", bold=True, step=2, delay=1.6)
    return c


# ------------------------------------------------------------------------------ satellites


def fiber_vs_satellite(t: Theme) -> Canvas:
    c = base_frame(t, "Cables vs satellites")
    earth_y = 820
    c.line(quad_curve((80, earth_y), (960, earth_y - 120), (1840, earth_y)), color=t.accent,
           width=5)
    c.text(960, earth_y - 40, "Earth surface", size=26, color=t.muted, anchor="mt", until=1)
    a, b = (360, earth_y - 50), (1560, earth_y - 50)
    for x, y in (a, b):
        c.circle(x, y, 14, fill=t.accent2)
    # step 0: GEO - very high; a request goes up and down, the reply up and down again
    c.rect(930, 170, 60, 40, fill=t.fg, r=6, step=0, until=1)
    c.line([(870, 190), (1050, 190)], color=t.fg, width=4, step=0, until=1)
    c.line([a, (960, 210), b], color=t.danger, width=4, dash=(16, 10), step=0, until=1)
    c.line([a, (960, 210), b], color=t.danger, width=1, step=0, until=1, anim="none",
           flow=t.danger, flow_gap=900, flow_speed=330, nofocus=True)
    c.text(140, 250, "Geostationary: very high, long round trip", size=30, color=t.danger,
           anchor="lt", step=0, until=1)
    # fibre along the surface for comparison
    c.line(quad_curve(a, (960, earth_y - 150), b), color=t.accent, width=1, step=0, until=1,
           anim="none", flow=LIGHT, flow_gap=300, flow_speed=900, nofocus=True)
    # step 1: LEO - much lower
    c.rect(930, 520, 50, 30, fill=t.fg, r=6, step=1, until=1, anim="slide",
           slide_from=(-400.0, 0.0))
    c.line([a, (955, 545), b], color=t.accent2, width=4, dash=(16, 10), step=1, until=1)
    c.text(1000, 500, "Low Earth orbit: much lower, shorter delay", size=30, color=t.accent2,
           anchor="lb", step=1, until=1)
    # step 2: capacity comparison (qualitative)
    c.text(160, 220, "Capacity between continents (qualitative)", size=36, color=t.fg,
           bold=True, step=2)
    c.rect(160, 300, 1500, 90, fill=t.accent, r=12, step=2, anim="slide",
           slide_from=(-600.0, 0.0), dur=1.6)
    c.text(190, 345, "Submarine cables", size=32,
           color=t.bg, anchor="lm", bold=True, step=2, delay=1.2)
    c.rect(160, 430, 260, 90, fill=t.muted, r=12, step=2, anim="slide",
           slide_from=(-200.0, 0.0), delay=0.6)
    c.text(450, 475, "Satellite", size=32, color=t.fg, anchor="lm", step=2, delay=1.2)
    c.text(160, 560, "Bar lengths illustrate the relationship only; not measured values.",
           size=24, color=t.muted, step=2)
    return c


def satellite_roles(t: Theme) -> Canvas:
    c = base_frame(t, "Where satellites shine")
    earth_y = 800
    c.line(quad_curve((80, earth_y), (960, earth_y - 100), (1840, earth_y)), color=t.accent,
           width=4)
    sx, sy = 960, 240
    c.rect(sx - 30, sy - 20, 60, 40, fill=t.fg, r=6)
    c.line([(sx - 110, sy), (sx + 110, sy)], color=t.fg, width=5)
    # step 0: places not yet wired with fibre
    hut = (420, 690)
    c.polygon([(hut[0] - 60, hut[1]), (hut[0], hut[1] - 50), (hut[0] + 60, hut[1])],
              fill=t.fg)
    c.rect(hut[0] - 42, hut[1], 84, 50, fill=t.fg)
    c.line([(sx, sy + 20), (hut[0], hut[1] - 60)], color=t.accent2, width=3, dash=(12, 10),
           step=0)
    c.line([(sx, sy + 20), (hut[0], hut[1] - 60)], color=t.accent2, width=1, anim="none",
           flow=t.accent2, flow_gap=160, flow_speed=220, nofocus=True)
    c.text(hut[0], hut[1] + 70, "Places not yet wired", size=32, color=t.fg, anchor="mt",
           bold=True)
    c.text(hut[0], hut[1] + 118, "with fibre", size=32, color=t.fg, anchor="mt", bold=True)
    # step 1: one source to many locations
    dishes = [(1180, 680), (1400, 650), (1620, 690)]
    for k, (x, y) in enumerate(dishes):
        c.polygon([(x - 34, y - 20), (x + 34, y - 20), (x, y + 14)], fill=t.fg, step=1,
                  delay=0.2 * k)
        c.rect(x - 4, y + 10, 8, 34, fill=t.fg, step=1, delay=0.2 * k)
        c.line([(sx, sy + 20), (x, y - 30)], color=t.accent2, width=3, dash=(12, 10), step=1,
               delay=0.3 + 0.2 * k)
        c.line([(sx, sy + 20), (x, y - 30)], color=t.accent2, width=1, step=1, anim="none",
               flow=t.accent2, flow_gap=160, flow_speed=220, nofocus=True)
    c.text(1400, 760, "One source, many locations", size=32, color=t.fg, anchor="mt",
           bold=True, step=1, delay=0.8)
    return c


# ------------------------------------------------------------------------------ recap


def recap(t: Theme) -> Canvas:
    c = base_frame(t, "Recap", schematic=False)
    items = [
        ("Light in glass", "Most data that crosses oceans travels through fibre on the sea bed."),
        ("Powered repeaters", "Amplifiers along the route keep the light strong enough."),
        ("Many routes", "Cables are tough but not invulnerable; diversity and repair ships "
                        "keep the network up."),
    ]
    for i, (head, body) in enumerate(items):
        y = 220 + i * 210
        c.circle(230, y + 50, 50, fill=t.accent, step=i, pulse=t.accent)
        c.text(230, y + 50, str(i + 1), size=52, color=t.bg, anchor="mm", bold=True, step=i,
               delay=0.4)
        c.text(320, y + 10, head, size=46, color=t.accent2, bold=True, step=i, anim="slide",
               slide_from=(60.0, 0.0))
        c.paragraph(320, y + 70, body, size=34, color=t.fg, max_width=1400, step=i, delay=0.5)
    return c


DIAGRAMS: dict[str, Diagram] = {
    d.id: d
    for d in [
        Diagram("atlantic_telegraph", "The first transatlantic cable", atlantic_telegraph),
        Diagram("route_schematic", "Cable routes (schematic)", route_schematic),
        Diagram("landing_station", "Landing stations and corridors", landing_station),
        Diagram("route_diversity", "Route diversity", route_diversity),
        Diagram("fiber_tir", "Light in an optical fibre", fiber_tir),
        Diagram("wdm_colors", "Wavelength-division multiplexing", wdm_colors),
        Diagram("repeater_chain", "Repeaters and power feed", repeater_chain),
        Diagram("edfa_inside", "Erbium-doped fibre amplifier", edfa_inside),
        Diagram("cable_cross_section", "Cable cross-section", cable_cross_section),
        Diagram("cable_laying", "Cable laying", cable_laying),
        Diagram("cable_repair", "Cable repair", cable_repair),
        Diagram("failure_modes", "Failure modes", failure_modes),
        Diagram("quake_landslide", "Earthquake and landslide", quake_landslide),
        Diagram("fiber_vs_satellite", "Fibre vs satellite", fiber_vs_satellite),
        Diagram("satellite_roles", "Satellite roles", satellite_roles),
        Diagram("recap", "Recap", recap),
    ]
}


# ------------------------------------------------------------------------------ YAML templates
# Specs live in <repo>/diagram_specs/<id>.yaml (override with STUDIO_DIAGRAM_SPECS).

SPECS_DIR = Path(__file__).resolve().parents[2] / "diagram_specs"
_SPEC_CACHE: dict[str, tuple[float, Diagram]] = {}


def specs_dir() -> Path:
    env = os.environ.get("STUDIO_DIAGRAM_SPECS", "").strip()
    return Path(env) if env else SPECS_DIR


def load_spec(path: Path):
    from pydantic import TypeAdapter

    from studio.diagrams.templates import DiagramSpec

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("id", path.stem)
    try:
        return TypeAdapter(DiagramSpec).validate_python(data)
    except Exception as exc:  # pydantic ValidationError -> readable message
        raise ValueError(f"{path.name}: {exc}") from exc


def spec_ids() -> list[str]:
    d = specs_dir()
    return sorted(p.stem for p in d.glob("*.yaml")) if d.exists() else []


def has_diagram(ref: str) -> bool:
    return ref in DIAGRAMS or (specs_dir() / f"{ref}.yaml").exists()


def get_diagram(ref: str) -> Diagram:
    """Hand-coded diagram, or a YAML template spec of the same id."""
    if ref in DIAGRAMS:
        return DIAGRAMS[ref]
    path = specs_dir() / f"{ref}.yaml"
    if not path.exists():
        raise KeyError(f"Unknown diagram '{ref}' (no code diagram, no {path})")
    mtime = path.stat().st_mtime
    cached = _SPEC_CACHE.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    spec = load_spec(path)
    d = Diagram(ref, spec.title, spec.build, spec.default_camera())
    d.spec = spec  # type: ignore[attr-defined]
    _SPEC_CACHE[str(path)] = (mtime, d)
    return d


def diagram_claims(ref: str) -> list[str]:
    d = get_diagram(ref)
    spec = getattr(d, "spec", None)
    return list(spec.claims) if spec else []


def layout_issues(canvas: Canvas, *, top: float = 140, bottom: float = 880,
                  gap: float = 6) -> list[str]:
    """Static layout QA per build step: overlapping labels, text off-canvas, text under the
    title strip or inside the caption band."""
    from studio.visuals import element_bbox

    issues: set[str] = set()
    for step in range(canvas.max_step + 1):
        texts = [e for e in canvas.visible(step) if e["kind"] == "text" and not e.get("hud")]
        boxes = [(e["s"], element_bbox(e), e.get("group")) for e in texts]
        for s, (x0, y0, x1, y1), _g in boxes:
            if x0 < 20 or x1 > 1900:
                issues.add(f"'{s[:30]}' runs off the canvas horizontally")
            if y0 < top:
                issues.add(f"'{s[:30]}' sits under the title strip (y={y0:.0f})")
            if y1 > bottom:
                issues.add(f"'{s[:30]}' enters the caption band (y={y1:.0f})")
        for i, (sa, a, ga) in enumerate(boxes):
            for sb, b, gb in boxes[i + 1:]:
                if ga and ga == gb:
                    continue  # lines of one paragraph
                if (min(a[2], b[2]) - max(a[0], b[0]) > -gap / 2
                        and min(a[3], b[3]) - max(a[1], b[1]) > -gap / 2):
                    issues.add(f"labels overlap at step {step}: '{sa[:24]}' / '{sb[:24]}'")
    return sorted(issues)
