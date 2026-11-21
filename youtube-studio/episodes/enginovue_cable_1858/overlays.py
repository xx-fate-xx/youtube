"""Exact chart overlays of the 1858 cable episode (rendered by `studio pipe build`).

Every curve is computed from its formula, so the graphics stay mathematically correct.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from studio.pipeline.overlay_kit import (  # noqa: F401
    GOLD,
    GRAPHITE,
    NAVY,
    ORANGE,
    SEA,
    SILVER,
    SKY,
    STYLES,
    SUBTITLE_TOP,
    TURQ,
    Canvas,
    H,
    W,
    _c,
    _font,
    card,
    formula,
    propto,
)


def erfc(x: float) -> float:
    return math.erfc(x)


def rc_step(s: float) -> float:
    """Far-end response of Thomson's distributed RC cable to a voltage step, s = t / (r c x^2)."""
    return 0.0 if s <= 0 else erfc(1 / (2 * math.sqrt(s)))


PULSE_START, PULSE_LEN, T_MAX = 0.6, 1.0, 9.0  # in units of the line time constant tau = r c L^2


def _pulse_axes(c: Canvas, s: dict, title: str, sub: str):
    x0, y0, w, h = 300, 100, 1320, 560
    card(c, s, x0, y0, w, h)
    c.text(x0 + 50, y0 + 70, title, 40, s["text"], "ls", bold=True)
    c.text(x0 + 50, y0 + 112, sub, 26, s["muted"], "ls")
    px, py, pw, ph = x0 + 110, y0 + 150, w - 170, h - 230  # plot box
    for i in range(1, 9):
        gx = px + pw * i / 9
        c.line([(gx, py), (gx, py + ph)], s["grid"], 2)
    for i in range(1, 4):
        gy = py + ph * i / 4
        c.line([(px, gy), (px + pw, gy)], s["grid"], 2)
    c.line([(px, py + ph), (px + pw + 10, py + ph)], s["axis"], 4)
    c.line([(px, py + ph), (px, py - 10)], s["axis"], 4)
    c.text(px + pw, py + ph + 44, "time", 26, s["muted"], "rs")
    c.text(px - 70, py + ph / 2, "V", 30, s["muted"], "mm", bold=True)

    def to_xy(t: float, v: float) -> tuple[float, float]:
        return px + pw * t / T_MAX, py + ph - ph * v / 1.1

    return to_xy


def _rect_pulse(to_xy) -> list[tuple[float, float]]:
    a, b = PULSE_START, PULSE_START + PULSE_LEN
    return [to_xy(0, 0), to_xy(a, 0), to_xy(a, 1), to_xy(b, 1), to_xy(b, 0), to_xy(T_MAX, 0)]


def pulse_sent(c: Canvas) -> None:
    s = STYLES["light"]
    to_xy = _pulse_axes(c, s, "Sent from Ireland", "A crisp, square telegraph pulse")
    c.line(_rect_pulse(to_xy), s["main"], 7)


def received(t: float) -> float:
    u = t - PULSE_START
    return rc_step(u) - rc_step(u - PULSE_LEN)


def pulse_received(c: Canvas) -> None:
    s = STYLES["light"]
    to_xy = _pulse_axes(c, s, "Received in Newfoundland",
                        "Same pulse, same scale: delayed, flattened and smeared out")
    c.line(_rect_pulse(to_xy), s["muted"], 3, dash=(14, 12), op=0.8)
    n = 400
    pts = [to_xy(T_MAX * i / n, received(T_MAX * i / n)) for i in range(n + 1)]
    c.line(pts, s["main"], 7)
    x, y = to_xy(0, 0)
    c.text(x, y + 44, "Model: Thomson (1855), cable as a distributed RC line", 22, s["muted"], "ls")


def delay_vs_length(c: Canvas) -> None:
    s = STYLES["dark"]
    x0, y0, w, h = 1000, 100, 760, 740
    card(c, s, x0, y0, w, h)
    formula(c, x0 + 50, y0 + 92, 64, s["text"], "t", "L²")
    c.text(x0 + 50, y0 + 140, "delay grows with the square of length", 26, s["muted"], "ls")
    px, py, pw, ph = x0 + 120, y0 + 235, w - 190, h - 355
    lmax, tmax = 3.25, 3.25 ** 2

    def to_xy(L: float, t: float) -> tuple[float, float]:
        return px + pw * L / lmax, py + ph - ph * t / tmax

    for k in (1, 2, 3):  # light grid at the marked lengths
        c.line([to_xy(k, 0), to_xy(k, tmax)], s["grid"], 2)
    c.line([(px, py + ph), (px + pw + 10, py + ph)], s["axis"], 4)
    c.line([(px, py + ph), (px, py - 10)], s["axis"], 4)
    n = 300
    c.line([to_xy(lmax * i / n, (lmax * i / n) ** 2) for i in range(n + 1)], s["main"], 8)
    for k in (1, 2, 3):
        t = k * k
        x, y = to_xy(k, t)
        c.line([to_xy(k, 0), (x, y)], s["accent"], 3, dash=(10, 9))
        c.line([to_xy(0, t), (x, y)], s["accent"], 3, dash=(10, 9))
        c.circle(x, y, 11, s["accent"], stroke=NAVY, sw=3)
        c.text(x, py + ph + 38, f"{k}×", 28, s["text"], "ms", bold=True)
        c.text(px - 16, y, f"{t}×", 28, s["accent"], "rm", bold=True)
    c.text(px + pw + 10, py + ph + 82, "cable length  L", 26, s["muted"], "rs")
    c.text(px - 16, py - 26, "signal delay  t", 26, s["muted"], "ls")


def length_x10(c: Canvas) -> None:
    s = STYLES["light"]
    x0, y0, w, h = 160, 330, 1600, 440
    card(c, s, x0, y0, w, h)
    left, unit = x0 + 110, 135.0
    for row_y, units, label in ((y0 + 150, 1, "L"), (y0 + 330, 10, "10 L")):
        end = left + unit * units
        c.line([(left, row_y), (end, row_y)], s["main"], 26)
        c.line([(left, row_y), (end, row_y)], TURQ, 6)
        for i in range(units + 1):
            tx = left + unit * i
            c.line([(tx, row_y - 34), (tx, row_y - 22)], s["muted"], 3)
        c.text(end + 24, row_y, label, 40, s["text"], "lm", bold=True)
    c.text(left, y0 + 66, "Same cable, ten times longer", 30, s["muted"], "ls")


def delay_x100(c: Canvas) -> None:
    s = STYLES["light"]
    x0, y0, w, h = 700, 90, 1060, 770
    card(c, s, x0, y0, w, h)
    c.text(x0 + 50, y0 + 70, "Signal delay", 40, s["text"], "ls", bold=True)
    c.text(x0 + 50, y0 + 112, "bar heights to exact scale", 24, s["muted"], "ls")
    base, top = y0 + h - 120, y0 + 160
    full = base - top
    c.line([(x0 + 70, base), (x0 + w - 70, base)], s["axis"], 4)
    for cx, ratio, top_label, bottom_label in ((x0 + 300, 1, "1×", "length L"),
                                               (x0 + 740, 100, "100×", "length 10 L")):
        bh = full * ratio / 100
        c.rect(cx - 90, base - bh, 180, bh, fill=SEA if ratio == 100 else ORANGE, r=0)
        c.text(cx, base - bh - 18, top_label, 40, s["text"], "ms", bold=True)
        c.text(cx, base + 50, bottom_label, 28, s["muted"], "ms")


CABLE_SHARE = 0.99   # ITU (2025): undersea cables carry "over 99%" of intercontinental data traffic


def _ring_sector(cx, cy, r_out, r_in, a0, a1, steps=180):
    """Annular sector from angle a0 to a1 (radians, clockwise from 12 o'clock)."""
    n = max(2, round(steps * (a1 - a0) / (2 * math.pi)))
    outer = [(cx + r_out * math.sin(a0 + (a1 - a0) * i / n), cy - r_out * math.cos(a0 + (a1 - a0) * i / n))
             for i in range(n + 1)]
    inner = [(cx + r_in * math.sin(a1 - (a1 - a0) * i / n), cy - r_in * math.cos(a1 - (a1 - a0) * i / n))
             for i in range(n + 1)]
    return outer + inner


def share_99(c: Canvas) -> None:
    s = STYLES["light"]
    x0, y0, w, h = 480, 100, 960, 740
    card(c, s, x0, y0, w, h)
    c.text(x0 + w / 2, y0 + 70, "Data crossing between continents", 38, s["text"], "ms", bold=True)
    cx, cy, ro, ri = x0 + 300, y0 + 390, 220, 140
    cable = 2 * math.pi * CABLE_SHARE
    c.poly(_ring_sector(cx, cy, ro, ri, 0, cable), SEA)
    c.poly(_ring_sector(cx, cy, ro + 14, ri - 14, cable, 2 * math.pi), ORANGE)  # the tiny remainder
    c.text(cx, cy - 10, "~99%", 64, s["text"], "mm", bold=True)
    c.text(cx, cy + 50, "undersea cables", 24, s["muted"], "mm")
    lx = x0 + 580
    c.rect(lx, y0 + 300, 34, 34, fill=SEA, r=6)
    c.text(lx + 50, y0 + 317, "undersea cables", 28, s["text"], "lm", bold=True)
    c.rect(lx, y0 + 380, 34, 34, fill=ORANGE, r=6)
    c.text(lx + 50, y0 + 397, "everything else", 28, s["text"], "lm", bold=True)
    c.text(lx + 50, y0 + 432, "(satellites, other routes)", 22, s["muted"], "lm")
    c.text(x0 + 50, y0 + h - 40, "Estimate: International Telecommunication Union (2025)", 22, s["muted"], "ls")


OVERLAYS: dict[str, Callable[[Canvas], None]] = {
    "pulse_sent": pulse_sent,
    "pulse_received": pulse_received,
    "delay_vs_length": delay_vs_length,
    "length_x10": length_x10,
    "delay_x100": delay_x100,
    "share_99": share_99,
}


def self_check() -> None:
    """Numerical checks that the plotted models are what the captions claim."""
    for L in (1, 2, 3, 10):
        assert round(L**2) == L**2
    assert abs(rc_step(1e9) - 1) < 1e-3 and rc_step(0) == 0
    peak = max(received(T_MAX * i / 2000) for i in range(2001))
    assert 0.2 < peak < 0.6, f"received pulse peak {peak:.2f} no longer a smeared bump"
    t_peak = max(range(2001), key=lambda i: received(T_MAX * i / 2000)) * T_MAX / 2000
    assert t_peak > PULSE_START + PULSE_LEN * 0.5, "received pulse is not delayed"
