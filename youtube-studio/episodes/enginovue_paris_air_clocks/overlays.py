"""Exact chart overlays of "The Air-Powered Clocks of Paris" (rendered by `studio pipe build`).

Numbers come from research/*.md: valve cycle (La Nature 1880, Berly 1881), pulse speed (speed of sound
~340 m/s, NASA Glenn), network length and clock counts (Histoire de la SUDAC; Berly 1881).
"""

from __future__ import annotations

from collections.abc import Callable

from studio.pipeline.overlay_kit import (  # noqa: F401
    NAVY, ORANGE, SEA, STYLES, TURQ, Canvas, card,
)

SOUND = 340.0                    # m/s, speed of the pressure front (≈ speed of sound in air)
MAINS_KM = [(1888, 48), (1900, 164), (1920, 435), (1930, 525), (1949, 678), (1970, 941)]
CLOCKS = [("1880", 1475, "1,475"), ("1881", 4000, "~4,000"), ("1884", 7800, "7,800"), ("1926", 5018, "5,018")]


def _axes(c: Canvas, s: dict, x0: float, y0: float, w: float, h: float) -> None:
    c.line([(x0, y0), (x0, y0 + h), (x0 + w, y0 + h)], s["axis"], 4)


def pulse_cycle(c: Canvas) -> None:
    """Valve state over two minutes: 20 s connected to the air tank, 40 s vented."""
    s = STYLES["light"]
    x0, y0, w, h = 560, 120, 1180, 640
    card(c, s, x0, y0, w, h)
    c.text(x0 + 60, y0 + 80, "The master clock's valve, minute by minute", 36, s["text"], "ls", bold=True)
    ax, ay, aw, ah = x0 + 120, y0 + 170, w - 200, 300
    _axes(c, s, ax, ay, aw, ah)
    sec = aw / 120.0
    hi, lo = ay + 40, ay + ah - 10
    pts = []
    for m in range(2):
        t0 = ax + m * 60 * sec
        pts += [(t0, lo), (t0, hi), (t0 + 20 * sec, hi), (t0 + 20 * sec, lo), (t0 + 60 * sec, lo)]
    c.line(pts, SEA, 10)
    for m in range(2):
        t0 = ax + m * 60 * sec
        c.rect(t0, hi, 20 * sec, lo - hi, fill=TURQ, op=0.25)
        c.text(t0 + 10 * sec, hi - 16, "air on", 26, s["text"], "ms", bold=True)
        c.text(t0 + 40 * sec, lo - 24, "vented", 26, s["muted"], "ms", bold=True)
    for t in (0, 20, 60, 80, 120):
        x = ax + t * sec
        c.line([(x, ay + ah), (x, ay + ah + 14)], s["axis"], 3)
        c.text(x, ay + ah + 50, f"{t} s", 26, s["text"], "ms")
    c.text(ax - 20, hi, "open", 24, s["muted"], "rm")
    c.text(ax - 20, lo, "vented", 24, s["muted"], "rm")
    c.text(x0 + 60, y0 + h - 40, "20 s of air, 40 s vented: every minute (La Nature, 1880)", 24, s["muted"], "ls")


def pulse_speed(c: Canvas) -> None:
    """Distance reached by the pressure front at ~340 m/s."""
    s = STYLES["light"]
    x0, y0, w, h = 300, 100, 1320, 620
    card(c, s, x0, y0, w, h)
    c.text(x0 + 60, y0 + 78, "How far the air pulse travels", 38, s["text"], "ls", bold=True)
    c.text(x0 + 60, y0 + 120, "front of the pressure wave at about 340 m/s (speed of sound in air)", 26, s["muted"], "ls")
    ax, ay, aw, ah = x0 + 150, y0 + 170, w - 260, 330
    _axes(c, s, ax, ay, aw, ah)
    t_max, d_max = 20.0, 7.0
    X = lambda t: ax + aw * t / t_max  # noqa: E731
    Y = lambda d: ay + ah - ah * d / d_max  # noqa: E731
    c.line([(X(0), Y(0)), (X(t_max), Y(SOUND * t_max / 1000))], SEA, 8)
    for d in (1, 5):
        t = d * 1000 / SOUND
        c.line([(X(0), Y(d)), (X(t), Y(d)), (X(t), Y(0))], ORANGE, 3, dash=(10, 9))
        c.circle(X(t), Y(d), 11, ORANGE, stroke=NAVY, sw=3)
        if d == 1:   # below the line, to the right
            c.text(X(t) + 22, Y(d) + 40, f"{d} km in ~{t:.0f} s", 28, s["text"], "ls", bold=True)
        else:        # above the line, to the left
            c.text(X(t) - 22, Y(d) - 22, f"{d} km in ~{t:.0f} s", 28, s["text"], "rs", bold=True)
    for t in (0, 5, 10, 15, 20):
        c.text(X(t), ay + ah + 42, f"{t} s", 24, s["text"], "ms")
    for d in (0, 2, 4, 6):
        c.text(ax - 18, Y(d), f"{d} km", 24, s["text"], "rm")


def network_km(c: Canvas) -> None:
    """Length of the compressed-air power mains (company figures)."""
    s = STYLES["light"]
    x0, y0, w, h = 380, 110, 1240, 680
    card(c, s, x0, y0, w, h)
    c.text(x0 + 60, y0 + 80, "Compressed-air power mains in Paris", 38, s["text"], "ls", bold=True)
    base, top = y0 + h - 110, y0 + 150
    bw, gap = 120, (w - 160 - 120 * len(MAINS_KM)) / (len(MAINS_KM) - 1)
    for i, (year, km) in enumerate(MAINS_KM):
        bx = x0 + 80 + i * (bw + gap)
        bh = (base - top) * km / 1000
        c.rect(bx, base - bh, bw, bh, fill=SEA if year < 1970 else TURQ, r=8)
        c.text(bx + bw / 2, base - bh - 14, f"{km} km", 28, s["text"], "ms", bold=True)
        c.text(bx + bw / 2, base + 44, str(year), 28, s["text"], "ms")
    c.text(x0 + 60, y0 + h - 30, "Company figures (Histoire de la SUDAC, 1996)", 22, s["muted"], "ls")


def clock_count(c: Canvas) -> None:
    """Private pneumatic clocks connected in Paris."""
    s = STYLES["light"]
    x0, y0, w, h = 520, 110, 1100, 680
    card(c, s, x0, y0, w, h)
    c.text(x0 + 60, y0 + 80, "Pneumatic clocks in Paris homes and offices", 36, s["text"], "ls", bold=True)
    base, top = y0 + h - 110, y0 + 160
    bw, gap = 150, (w - 160 - 150 * len(CLOCKS)) / (len(CLOCKS) - 1)
    for i, (year, n, label) in enumerate(CLOCKS):
        bx = x0 + 80 + i * (bw + gap)
        bh = (base - top) * n / 8000
        c.rect(bx, base - bh, bw, bh, fill=ORANGE if year == "1884" else SEA, r=8)
        c.text(bx + bw / 2, base - bh - 14, label, 30, s["text"], "ms", bold=True)
        c.text(bx + bw / 2, base + 44, year, 28, s["text"], "ms")
    c.text(x0 + 60, y0 + h - 30, "Annuaire statistique via Histoire de la SUDAC; 1881: Berly (1881)", 22, s["muted"], "ls")


OVERLAYS: dict[str, Callable[[Canvas], None]] = {
    "pulse_cycle": pulse_cycle,
    "pulse_speed": pulse_speed,
    "network_km": network_km,
    "clock_count": clock_count,
}


def self_check() -> None:
    assert abs(1000 / SOUND - 2.94) < 0.01 and abs(5000 / SOUND - 14.7) < 0.1
    assert [k for _, k in MAINS_KM] == sorted(k for _, k in MAINS_KM)
