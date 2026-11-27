"""SVG overlays: titles, level HUD, chalk notes for freeze-frame physics, effects (boom, dust, flash, streaks)."""

from __future__ import annotations

import math
import random
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TXT, AMBER, CHALK = "#F2EEE4", "#FFB547", "#F4F1E8"
DEFS = ('<defs><filter id="sh" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="7"/>'
        '</filter><filter id="chalk" x="-5%" y="-20%" width="110%" height="140%"><feTurbulence type="fractalNoise" '
        'baseFrequency="0.9" numOctaves="2" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" '
        'scale="3.5"/></filter><radialGradient id="scrim"><stop offset="0" stop-color="#000" stop-opacity="0.62"/>'
        '<stop offset="0.6" stop-color="#000" stop-opacity="0.32"/><stop offset="1" stop-color="#000" '
        'stop-opacity="0"/></radialGradient><filter id="aura" x="-50%" y="-50%" width="200%" height="200%">'
        '<feMorphology operator="dilate" radius="5"/><feGaussianBlur stdDeviation="7"/></filter>'
        '<filter id="outline" x="-20%" y="-20%" width="140%" height="140%"><feMorphology operator="dilate" '
        'radius="4"/></filter><filter id="amberize"><feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 0.71  '
        '0 0 0 0 0.28  0 0 0 1 0"/></filter></defs>')


@lru_cache(maxsize=1)
def font_files() -> list[str]:
    fonts = ROOT / "assets" / "fonts"
    return [str(p) for p in fonts.rglob("*.ttf")]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size, fill=TXT, anchor="start", weight=800, family="Inter Display", ls=0.0, op=1.0) -> str:
    if op <= 0:
        return ""
    return (f'<text x="{x:.0f}" y="{y:.0f}" font-family="{family}" font-weight="{weight}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}" opacity="{op:.2f}">{esc(s)}</text>')


def shadowed(svg: str) -> str:
    dark = svg
    for c in (TXT, AMBER, CHALK):
        dark = dark.replace(f'fill="{c}"', 'fill="#000"')
    return f'<g filter="url(#sh)">{dark}</g>{svg}'


def scrim(cx, cy, rx, ry, op=1.0) -> str:
    return f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{ry:.0f}" fill="url(#scrim)" opacity="{op:.2f}"/>' \
        if op > 0 else ""


def title(lines: list[str], op: float, x=110, y=170, size=84) -> str:
    if op <= 0:
        return ""
    body = "".join(text(x, y + k * size * 1.1, ln, size, op=op) for k, ln in enumerate(lines))
    return scrim(x + 220, y + 20, 760, 330, op) + shadowed(body)


def hud(label: str, value: str, note: str, op: float, note_op: float, x=110, y=120) -> str:
    if op <= 0:
        return ""
    body = (text(x, y, label, 30, AMBER, weight=600, family="IBM Plex Mono", ls=6, op=op)
            + text(x, y + 90, value, 92, op=op)
            + text(x + 2, y + 138, note, 34, weight=600, family="Inter", op=op * note_op))
    return scrim(x + 220, y + 50, 760, 330, op) + shadowed(body)


# ---------------------------------------------------------------- chalk

def wobble(pts, seed, amp=3.0):
    r = random.Random(seed)
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        for k in range(8):
            u = k / 8
            out.append((x0 + (x1 - x0) * u + r.uniform(-amp, amp), y0 + (y1 - y0) * u + r.uniform(-amp, amp)))
    out.append(pts[-1])
    return out


def chalk_line(pts, p: float, width=6.0, seed=1, rough=True) -> str:
    if p <= 0:
        return ""
    pts = wobble(pts, seed) if rough else pts
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    L = sum(math.dist(a, b) for a, b in zip(pts, pts[1:], strict=False))
    return (f'<path d="{d}" stroke="{CHALK}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" '
            f'fill="none" stroke-dasharray="{L:.0f}" stroke-dashoffset="{L * (1 - min(1, p)):.0f}"'
            + (' filter="url(#chalk)"/>' if rough else "/>"))   # a straight line has a zero-size box: no filter


def chalk_arrow(x0, y0, x1, y1, p: float, seed=1) -> str:
    out = chalk_line([(x0, y0), (x1, y1)], p, seed=seed)
    if p >= 0.85:
        a = math.atan2(y1 - y0, x1 - x0)
        q = min(1, (p - 0.85) / 0.15)
        for s in (1, -1):
            hx, hy = x1 - 42 * math.cos(a + s * 0.5), y1 - 42 * math.sin(a + s * 0.5)
            out += chalk_line([(hx, hy), (x1, y1)], q, seed=seed + 7 + s)
    return out


def chalk_text(x, y, s, size, p: float, weight=600, family="Inter", anchor="start") -> str:
    n = max(0, min(len(s), int(len(s) * p + 0.999)))
    if n == 0:
        return ""
    return (f'<text x="{x:.0f}" y="{y:.0f}" font-family="{family}" font-weight="{weight}" font-size="{size}" '
            f'fill="{CHALK}" text-anchor="{anchor}" filter="url(#chalk)">{esc(s[:n])}</text>')


# ---------------------------------------------------------------- effects

def boom(cx, cy, u: float, w: int, h: int) -> str:
    out = []
    for k, delay in enumerate((0.0, 0.08, 0.18)):
        v = u - delay
        if 0 < v < 0.9:
            rx = 60 + v * 2200
            out.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{rx * 0.42:.0f}" fill="none" '
                       f'stroke="#FFFFFF" stroke-width="{max(1, 14 - k * 4 - v * 12):.1f}" opacity="{max(0, 0.7 - v * 0.8):.2f}"/>')
    if u < 0.18:
        out.append(f'<rect width="{w}" height="{h}" fill="#FFFFFF" opacity="{0.55 * (1 - u / 0.18):.2f}"/>')
    return "".join(out)


def dust(cx, ground, u: float, seed=42, n=70) -> str:
    r = random.Random(seed)
    out = []
    for _ in range(n):
        ang = r.uniform(math.pi * 1.05, math.pi * 1.95)
        sp = r.uniform(200, 900)
        x = cx + math.cos(ang) * sp * u
        y = ground - 5 + math.sin(ang) * sp * u + 900 * u * u
        rad = r.uniform(3, 9)
        if y < ground + 10 and u < 1.6:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad:.1f}" fill="#CDBBA0" opacity="{max(0, 0.8 - u * 0.5):.2f}"/>')
    return "".join(out)


def streaks(seed: int, strength: float, w: int, h: int) -> str:
    if strength <= 0:
        return ""
    r = random.Random(seed)
    out = []
    for _ in range(int(10 + 25 * strength)):
        y = r.uniform(h * 0.11, h * 0.93)
        x = r.uniform(-200, w)
        ln = r.uniform(150, 600) * (0.5 + strength)
        out.append(f'<path d="M{x:.0f},{y:.0f} l{ln:.0f},0" stroke="#FFFFFF" stroke-width="{r.uniform(1.5, 4):.1f}" '
                   f'opacity="{r.uniform(0.15, 0.45) * strength:.2f}" stroke-linecap="round"/>')
    return "".join(out)


def card(label: str, title_s: str, op: float, x=110, y=110) -> str:
    """Mission card (top left): small amber label over a white title."""
    if op <= 0:
        return ""
    body = (text(x, y, label, 30, AMBER, weight=600, family="IBM Plex Mono", ls=6, op=op)
            + text(x, y + 66, title_s, 60, op=op))
    return scrim(x + 220, y + 30, 700, 260, op * 0.9) + shadowed(body)


def rewind_look(i: int, k: float, w: int, h: int) -> str:
    """VHS-style rewind: drifting scan bands and a chalk rewind sign."""
    r = random.Random(i // 2)
    out = []
    for _ in range(5):
        y = r.uniform(0, h)
        out.append(f'<rect x="0" y="{y:.0f}" width="{w}" height="{r.uniform(3, 14):.0f}" fill="#FFFFFF" '
                   f'opacity="{0.10 * k:.2f}"/>')
    out.append(text(w - 110, 150, "◀◀", 84, CHALK, anchor="end", op=0.9 * k))
    return "".join(out)


def sketch_paths(paths: list[list[tuple[float, float]]], p: float, width=5.0, seed=11) -> str:
    """Several chalk polylines drawn one after another as p goes 0 -> 1 (a quick chalk drawing)."""
    total = sum(sum(math.dist(a, b) for a, b in zip(q, q[1:], strict=False)) for q in paths) or 1.0
    done, out = p * total, []
    for k, q in enumerate(paths):
        ln = sum(math.dist(a, b) for a, b in zip(q, q[1:], strict=False)) or 1.0
        if done <= 0:
            break
        out.append(chalk_line(q, min(1.0, done / ln), width, seed=seed + k))
        done -= ln
    return "".join(out)
