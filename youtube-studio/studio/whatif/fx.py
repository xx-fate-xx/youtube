"""World-space destruction and impact effects for motion-comic scenes (drawn on the plate, under the camera).

Each factory returns a draw function fn(world_img, u, t) for Comic.draw(at, until, fn): u = seconds since `at`.
Everything is deterministic (seeded) so parallel render chunks agree frame for frame.

    debris   chunks of asphalt/concrete thrown up with gravity, spinning, then lying on the ground
    dust     expanding, fading dust clouds
    sparks   short bright streaks spraying from a point (optionally for a duration, e.g. shoes on asphalt)
    cracks   a crack pattern spreading from a point and staying (a decal)
    gouge    two skid/gouge lines left behind a moving point (a decal), sparks at the head
    bullet   a brass bullet with a pressure cone and a wake of rings, flying between two points
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

GRAV = 2600.0                      # plate px / s^2 for debris (cartoon gravity)


def _rng(seed: int) -> random.Random:
    return random.Random(seed * 7919 + 17)


def debris(x: float, y: float, n: int = 26, power: float = 1.0, color=(70, 70, 76), seed: int = 1,
           ground: float | None = None, spread: tuple[float, float] = (200.0, 340.0)):
    """Chunks flying up and out from (x, y) (angles in degrees, 0 = right, 270 = up), landing on `ground`."""
    r = _rng(seed)
    g = y if ground is None else ground
    parts = []
    for _ in range(n):
        a = math.radians(r.uniform(*spread))
        v = r.uniform(500, 1500) * power
        size = r.uniform(8, 26) * (0.7 + 0.6 * power)
        spin = r.uniform(-9, 9)
        sides = r.randint(4, 6)
        shade = r.uniform(0.75, 1.25)
        parts.append((math.cos(a) * v, math.sin(a) * v, size, spin, sides, shade, r.uniform(0, 6.28)))

    def f(img: Image.Image, u: float, _t: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        for vx, vy, size, spin, sides, shade, ph in parts:
            px, py = x + vx * u, y + vy * u + 0.5 * GRAV * u * u
            if py > g:                                   # landed: slide a little and stop
                t_land = _land_time(vy, y, g)
                px, py = x + vx * t_land + vx * 0.08, g
                ang = ph + spin * t_land
            else:
                ang = ph + spin * u
            col = tuple(int(min(255, c * shade)) for c in color) + (255,)
            pts = [(px + size * math.cos(ang + k * 2 * math.pi / sides) * (0.75 + 0.25 * ((k * 37) % 3) / 2),
                    py + size * math.sin(ang + k * 2 * math.pi / sides)) for k in range(sides)]
            d.polygon(pts, fill=col, outline=(20, 20, 22, 255))
    return f


def _land_time(vy: float, y0: float, g: float) -> float:
    # y0 + vy t + G t^2 / 2 = g  (vy < 0 going up)
    a, b, c = 0.5 * GRAV, vy, y0 - g
    disc = max(0.0, b * b - 4 * a * c)
    return (-b + math.sqrt(disc)) / (2 * a)


def dust(x: float, y: float, n: int = 16, size: float = 120.0, life: float = 1.6, seed: int = 2,
         color=(196, 182, 160)):
    r = _rng(seed)
    puffs = [(r.uniform(-1, 1) * size * 0.8, r.uniform(-0.6, 0.1) * size * 0.5, r.uniform(0.6, 1.2), r.uniform(-1, 1))
             for _ in range(n)]

    def f(img: Image.Image, u: float, _t: float) -> None:
        if u > life:
            return
        k = u / life
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for ox, oy, s, drift in puffs:
            rad = size * s * (0.35 + 1.1 * (1 - (1 - k) ** 2))
            cx, cy = x + ox * (0.4 + k) + drift * 80 * k, y + oy - 40 * k
            a = int(95 * (1 - k) ** 1.5)
            d.ellipse([cx - rad, cy - rad * 0.7, cx + rad, cy + rad * 0.7], fill=(*color, a))
        img.alpha_composite(layer)
    return f


def sparks(x: float, y: float, n: int = 22, life: float = 0.5, duration: float = 0.0, seed: int = 3,
           direction: float = 200.0, cone: float = 50.0, follow=None):
    """Bright streaks from (x, y); with duration > 0 new sparks keep coming (follow(u) -> (x, y) moves the source)."""
    r = _rng(seed)
    waves = max(1, int(duration * 20)) if duration > 0 else 1
    sp = [[(math.radians(direction + r.uniform(-cone, cone)), r.uniform(600, 1500), r.uniform(0.15, life))
           for _ in range(n)] for _ in range(waves)]

    def f(img: Image.Image, u: float, _t: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        for w, wave in enumerate(sp):
            t0 = w / 20.0
            uu = u - t0
            if uu < 0:
                continue
            sx, sy = follow(t0) if follow else (x, y)
            for ang, v, lf in wave:
                if uu > lf:
                    continue
                k = uu / lf
                px, py = sx + math.cos(ang) * v * uu, sy + math.sin(ang) * v * uu + 900 * uu * uu
                tail = 0.035
                qx, qy = px - math.cos(ang) * v * tail, py - math.sin(ang) * v * tail
                a = int(255 * (1 - k))
                d.line([(qx, qy), (px, py)], fill=(255, 220, 120, a), width=4)
                d.line([(qx, qy), (px, py)], fill=(255, 255, 230, a), width=2)
    return f


def cracks(x: float, y: float, size: float = 260.0, grow: float = 0.25, seed: int = 4, flat: float = 0.35,
           color=(28, 28, 32)):
    """Branching cracks spreading from (x, y); flat < 1 squashes them onto a ground plane."""
    r = _rng(seed)
    segs = []

    def branch(px, py, ang, length, depth):
        if depth > 3 or length < 18:
            return
        steps = r.randint(3, 5)
        for _ in range(steps):
            ang += r.uniform(-0.5, 0.5)
            nx, ny = px + math.cos(ang) * length / steps, py + math.sin(ang) * length / steps * flat
            segs.append((px, py, nx, ny, depth))
            px, py = nx, ny
            if r.random() < 0.35:
                branch(px, py, ang + r.choice((-1, 1)) * r.uniform(0.5, 1.1), length * 0.5, depth + 1)
    for k in range(7):
        branch(x, y, k * 2 * math.pi / 7 + r.uniform(-0.3, 0.3), size * r.uniform(0.6, 1.0), 0)

    def f(img: Image.Image, u: float, _t: float) -> None:
        k = min(1.0, u / grow)
        d = ImageDraw.Draw(img, "RGBA")
        for x0, y0, x1, y1, depth in segs:
            dist = math.hypot(x0 - x, (y0 - y) / flat) / size
            if dist > k:
                continue
            w = max(2, 7 - 2 * depth)
            d.line([(x0, y0), (x1, y1)], fill=(*color, 235), width=w)
            d.line([(x0, y0 + 2), (x1, y1 + 2)], fill=(255, 255, 255, 40), width=max(1, w - 3))
    return f


def gouge(path, until: float, y_gap: float = 26.0, color=(30, 30, 34), seed: int = 5):
    """Two dark lines left behind a moving point path(u) -> (x, y) up to `until` seconds, with sparks at the head."""
    sp = sparks(0, 0, n=10, life=0.35, duration=until, seed=seed, direction=210, cone=35,
                follow=lambda tt: path(min(tt, until)))

    def f(img: Image.Image, u: float, t: float) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        uu = min(u, until)
        pts = [path(uu * j / 24) for j in range(25)]
        for off in (-y_gap / 2, y_gap / 2):
            d.line([(px, py + off) for px, py in pts], fill=(*color, 200), width=9)
        if u < until + 0.3:
            sp(img, u, t)
    return f


def bullet(p0, p1, dur: float, start: float = 0.0, scale: float = 1.0, rings: bool = True):
    """A brass bullet travelling p0 -> p1 over `dur` s (beginning `start` s after the draw starts); a pale pressure
    cone at the nose and fading wake rings behind it (the air it pushes)."""
    def f(img: Image.Image, u: float, _t: float) -> None:
        uu = u - start
        if uu < 0:
            return
        k = min(1.0, uu / dur)
        x, y = p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k
        dirx = 1 if p1[0] >= p0[0] else -1
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        L, R = 46 * scale, 13 * scale
        if rings:
            for j in range(1, 7):
                bx = x - dirx * j * 34 * scale
                rr = R * (1.2 + 0.45 * j)
                d.ellipse([bx - rr * 0.35, y - rr, bx + rr * 0.35, y + rr], outline=(255, 255, 255, int(150 / j)),
                          width=max(1, int(3 * scale)))
            d.polygon([(x + dirx * (L * 0.5 + 18 * scale), y), (x - dirx * 4 * scale, y - R * 2.2),
                       (x - dirx * 4 * scale, y + R * 2.2)], fill=(255, 255, 255, 40))
        tail = x - dirx * L * 0.5
        d.rectangle([min(tail, x), y - R, max(tail, x), y + R], fill=(176, 120, 52, 255))
        d.pieslice([x - R * 1.6, y - R, x + R * 1.6, y + R], -90 if dirx > 0 else 90, 90 if dirx > 0 else 270,
                   fill=(214, 156, 74, 255))
        d.line([(tail, y - R * 0.45), (x, y - R * 0.45)], fill=(255, 226, 160, 255), width=max(1, int(3 * scale)))
        d.rectangle([min(tail, x), y - R, max(tail, x), y + R], outline=(40, 26, 10, 255), width=max(1, int(2 * scale)))
        img.alpha_composite(layer)
    return f
