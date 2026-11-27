"""Sumi-e ink overlays for the ink_mindset channel (screen-space SVG for Comic.text): brush-written labels, ink-bleed
transitions, a brush-stroke seam between stacked halves, a vermilion bloom and the channel's seal stamp.

Each helper returns fn(u, t) -> svg, where u = seconds since the overlay started (Comic.text convention).
"""

from __future__ import annotations

import math
import random

from .overlay import esc

INK, PAPER, VERMILION = "#16140F", "#F4EDE0", "#D9412B"
FONT = "Caveat Brush"


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _rough(fid: str, freq: float, scale: float, seed: int) -> str:
    """Rough, organic edge. resvg needs an opaque noise map (alpha forced to 1) and its displacement is much
    stronger than the nominal scale: keep scale <= ~25, larger values wipe the shape out completely."""
    return (f'<filter id="{fid}" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" '
            f'baseFrequency="{freq}" numOctaves="3" seed="{seed}" result="n"/><feColorMatrix in="n" type="matrix" '
            f'values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0 1" result="m"/><feDisplacementMap '
            f'in="SourceGraphic" in2="m" scale="{scale}" xChannelSelector="R" yChannelSelector="G"/></filter>')


def label(x: float, y: float, s: str, size: float = 92, dur: float = 0.55, fill: str = INK, anchor: str = "middle",
          delay: float = 0.0, fade_out: tuple[float, float] | None = None, halo: bool = True):
    """Brush-written word: revealed left to right like a stroke of the brush (clip grows), with soft rough edges."""
    w_est = 0.48 * size * len(s) + size
    x0 = x - w_est / 2 if anchor == "middle" else (x - w_est if anchor == "end" else x)
    key = abs(hash((s, round(x), round(y)))) % 10**8

    def f(u, _t):
        k = _ease((u - delay) / dur)
        if k <= 0:
            return ""
        op = 1.0
        if fade_out:
            op = 1.0 - _ease((u - fade_out[0]) / fade_out[1])
            if op <= 0:
                return ""
        cid, fid, hid = f"lc{key}", f"lr{key}", f"lh{key}"
        txt = (f'<text x="{x:.0f}" y="{y:.0f}" font-family="{FONT}" font-size="{size}" text-anchor="{anchor}" '
               f'letter-spacing="2"')
        glow = ""
        if halo:                                   # soft paper glow so the ink word reads on dark washes too
            glow = (f'<g filter="url(#{hid})" opacity="0.9">{txt} fill="{PAPER}" stroke="{PAPER}" '
                    f'stroke-width="{size * 0.32:.0f}" stroke-linejoin="round">{esc(s)}</text></g>')
        return (f'<defs><clipPath id="{cid}"><rect x="{x0 - 30:.0f}" y="{y - size * 1.3:.0f}" '
                f'width="{(w_est + 60) * k:.0f}" height="{size * 1.9:.0f}"/></clipPath>{_rough(fid, 0.08, 2.5, 3)}'
                f'<filter id="{hid}" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur '
                f'stdDeviation="{size * 0.09:.1f}"/></filter></defs>'
                f'<g clip-path="url(#{cid})" opacity="{op:.2f}">{glow}'
                f'<g filter="url(#{fid})">{txt} fill="{fill}">{esc(s)}</text></g></g>')
    return f


def slam(x: float, y: float, s: str, size: float = 92, delay: float = 0.0, fill: str = INK, halo: bool = True):
    """Label that hits on a beat: scales from 1.7x to 1x in 0.12 s with a quick ink burst behind it."""
    burst = splash(x, y - size * 0.3, size * 0.9, seed=len(s) * 7 + int(x), delay=delay, color=PAPER if halo else INK)
    base = label(x, y, s, size, dur=0.001, fill=fill, halo=halo)
    cy = y - size * 0.35

    def f(u, t):
        k = (u - delay) / 0.12
        if k <= 0:
            return ""
        sc = 1.0 + 0.7 * (1 - _ease(min(1.0, k))) ** 2
        body = base(u - delay + 0.01, t)
        return (burst(u, t) + f'<g transform="translate({x:.0f},{cy:.0f}) scale({sc:.3f}) translate({-x:.0f},{-cy:.0f})" '
                f'opacity="{min(1.0, k * 1.5):.2f}">{body}</g>')
    return f


def splash(x: float, y: float, size: float = 120, seed: int = 3, delay: float = 0.0, color: str = INK,
           life: float = 0.9):
    """Ink burst on a hit: a blot swells in 0.1 s and drops fly outward, then everything fades."""
    rnd = random.Random(seed)
    drops = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.6, 1.6), rnd.uniform(0.04, 0.12)) for _ in range(16)]
    fid = f"sp{seed}"

    def f(u, _t):
        v = u - delay
        if v <= 0 or v > life:
            return ""
        k = _ease(min(1.0, v / 0.22))
        op = 1.0 if v < life * 0.55 else max(0.0, 1 - (v - life * 0.55) / (life * 0.45))
        g = f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{size * 0.32 * _ease(min(1.0, v / 0.1)):.0f}"/>'
        g += "".join(f'<circle cx="{x + math.cos(a) * size * d * k:.0f}" cy="{y + math.sin(a) * size * d * k:.0f}" '
                     f'r="{size * r * (1.2 - 0.4 * k):.1f}"/>' for a, d, r in drops)
        return (f'<defs>{_rough(fid, 0.06, 8, seed)}</defs><g fill="{color}" opacity="{op:.2f}" '
                f'filter="url(#{fid})">{g}</g>')
    return f


def seam(W: int, y: float, thickness: float = 16, seed: int = 7):
    """Horizontal brush stroke between stacked halves (tapered ends, dry-brush edge) on a paper band."""
    rnd = random.Random(seed)
    n = 24
    top, bot = [], []
    for i in range(n + 1):
        x = -20 + (W + 40) * i / n
        taper = math.sin(math.pi * min(1.0, max(0.0, (i + 0.6) / (n + 1.2))))
        h = thickness * (0.35 + 0.65 * taper) * (0.85 + 0.3 * rnd.random())
        wob = 3 * math.sin(i * 0.7 + seed)
        top.append((x, y - h / 2 + wob))
        bot.append((x, y + h / 2 + wob))
    pts = top + bot[::-1]
    d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts) + " Z"
    band = f'<rect x="0" y="{y - 14:.0f}" width="{W}" height="28" fill="{PAPER}"/>'

    def f(_u, _t):
        return (f'<defs>{_rough("seamr", 0.05, 6, seed)}</defs>{band}'
                f'<path d="{d}" fill="{INK}" opacity="0.92" filter="url(#seamr)"/>')
    return f


def stroke(x0: float, y: float, x1: float, thickness: float = 14, color: str = VERMILION, delay: float = 0.0,
           dur: float = 0.35, seed: int = 9):
    """A single tapered brush stroke drawn on from left to right (e.g. a vermilion underline under a label)."""
    rnd = random.Random(seed)
    n = 16
    top, bot = [], []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        taper = math.sin(math.pi * (0.15 + 0.85 * i / n)) ** 0.6
        h = thickness * (0.3 + 0.7 * taper) * (0.85 + 0.3 * rnd.random())
        wob = 4 * math.sin(i * 0.5 + seed) - 6 * i / n
        top.append((x, y - h / 2 + wob))
        bot.append((x, y + h / 2 + wob))
    d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in top + bot[::-1]) + " Z"
    key = f"st{seed}{round(x0)}{round(y)}"

    def f(u, _t):
        k = _ease((u - delay) / dur)
        if k <= 0:
            return ""
        return (f'<defs><clipPath id="{key}c"><rect x="{x0 - 5:.0f}" y="{y - 60:.0f}" width="{(x1 - x0 + 10) * k:.0f}" '
                f'height="120"/></clipPath>{_rough(key + "r", 0.07, 5, seed)}</defs>'
                f'<g clip-path="url(#{key}c)"><path d="{d}" fill="{color}" opacity="0.9" filter="url(#{key}r)"/></g>')
    return f


def _blots(W: int, H: int, seed: int, n: int = 5):
    rnd = random.Random(seed)
    pts = [(rnd.uniform(0.1, 0.9) * W, rnd.uniform(0.1, 0.9) * H, rnd.uniform(0.7, 1.3)) for _ in range(n)]
    drops = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(6, 26), rnd.uniform(0.0, 0.6)) for _ in range(40)]
    return pts, drops


def bleed(W: int, H: int, dur: float = 0.5, cover: bool = True, color: str = INK, seed: int = 11, delay: float = 0.0):
    """Ink-bleed transition. cover=True: blots spread until the frame is solid ink (end of a scene).
    cover=False: starts solid and the ink soaks back into a few points (start of the next scene)."""
    pts, drops = _blots(W, H, seed)
    R = math.hypot(W, H)
    fid = f"bl{seed}"

    def f(u, _t):
        k = _ease((u - delay) / dur)
        k = k if cover else 1.0 - k
        if k <= 0.001:
            return ""
        if k >= 0.999:
            return f'<rect width="{W}" height="{H}" fill="{color}"/>'
        g = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{R * 0.5 * s * k ** 1.8:.0f}"/>' for x, y, s in pts)
        dr = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r * min(1.0, k / max(0.05, 1 - d)):.0f}"/>'
                     for x, y, r, d in drops if k > d * 0.5)
        return (f'<defs>{_rough(fid, 0.018, 24, seed)}</defs>'
                f'<g fill="{color}" opacity="0.35" filter="url(#{fid})" transform="translate(-8,-8) scale(1.015)">'
                f'{g}</g><g fill="{color}" filter="url(#{fid})">{g}{dr}</g>')
    return f


def seal(x: float, y: float, size: float = 120, delay: float = 0.0):
    """The channel's vermilion seal stamp (our own mark: a brush circle with a dot), stamped with a small pop."""
    def f(u, _t):
        k = (u - delay) / 0.14
        if k <= 0:
            return ""
        s = 1.35 - 0.35 * _ease(k)
        op = min(1.0, k) * 0.93
        r = size / 2
        return (f'<defs>{_rough("sealr", 0.09, 5, 21)}</defs>'
                f'<g transform="translate({x:.0f},{y:.0f}) scale({s:.3f})" opacity="{op:.2f}" filter="url(#sealr)">'
                f'<rect x="{-r:.0f}" y="{-r:.0f}" width="{size:.0f}" height="{size:.0f}" rx="{size * 0.12:.0f}" '
                f'fill="{VERMILION}"/>'
                f'<circle cx="0" cy="0" r="{r * 0.58:.0f}" fill="none" stroke="{PAPER}" stroke-width="{size * 0.09:.1f}" '
                f'stroke-dasharray="{r * 3.2:.0f} {r * 0.5:.0f}" transform="rotate(-60)"/>'
                f'<circle cx="0" cy="0" r="{size * 0.07:.1f}" fill="{PAPER}"/></g>')
    return f


def grain(W: int, H: int, op: float = 0.06, seed: int = 5):
    """Static rice-paper fibre texture over everything (very faint)."""
    def f(_u, _t):
        return (f'<defs><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" '
                f'seed="{seed}"/><feColorMatrix type="matrix" values="0 0 0 0 0.3  0 0 0 0 0.25  0 0 0 0 0.15  '
                f'0 0 0 1.4 -0.55"/></filter></defs><rect width="{W}" height="{H}" filter="url(#grain)" '
                f'opacity="{op}"/>')
    return f
