"""Stickmen v3: mocap stickmen composited over painted backgrounds; night = code grade of the same painting."""

import io
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import stick2 as s2        # noqa: E402  (mocap helpers + stick drawing)
import stick_test as st    # noqa: E402

HERE = Path(__file__).parent
BG = HERE / "bg"
OUT = HERE / "stick3"
(OUT / "anim").mkdir(parents=True, exist_ok=True)
W, H, FPS = 1920, 1080, 30
SWITCH = 6.5                      # T+ 00:08:20
SHOTS = [("city", 0.0, 3.5), ("meadow", 3.5, 9.8), ("orbit", 9.8, 13.5)]


def fit(img):
    img = img.convert("RGB")
    w, h = img.size
    sc = max(W * 1.06 / w, H * 1.06 / h)          # 6% headroom for a slow camera push
    return img.resize((round(w * sc), round(h * sc)), Image.Resampling.LANCZOS)


def _stars(shape, seed, n_div=5000):
    rnd = np.random.default_rng(seed)
    hh, ww = shape
    n = int(hh * ww / n_div)
    return rnd.integers(0, hh, n), rnd.integers(0, ww, n), rnd.uniform(0.35, 1.0, n) ** 2


def night_grade(img: Image.Image, seed=5, star_top=0.27):
    a = np.asarray(img).astype(np.float32) / 255
    hh = a.shape[0]
    lum = a.mean(-1, keepdims=True)
    land = (a * 0.17 + lum * 0.06) * np.array([0.55, 0.72, 1.2])          # starlight: dim and cold
    y = np.linspace(0, 1, hh)[:, None, None]
    v = np.clip((star_top + 0.06 - y) / 0.2, 0, 1) ** 1.5                   # upper sky -> deep black
    base = np.array([0.010, 0.014, 0.032])
    out = land * (1 - v) + base * v
    for yy, xx, br in zip(*_stars(a.shape[:2], seed)):
        if yy < star_top * hh:
            f = br * (1 - min(1, yy / (star_top * hh)) * 0.6)
            out[yy, xx] = np.maximum(out[yy, xx], f)
            if br > 0.6 and 0 < yy < hh - 1 and 0 < xx < a.shape[1] - 1:
                out[yy - 1:yy + 2, xx] = np.maximum(out[yy - 1:yy + 2, xx], f * 0.45)
                out[yy, xx - 1:xx + 2] = np.maximum(out[yy, xx - 1:xx + 2], f * 0.45)
    return np.clip(out, 0, 1)


def orbit_night(img: Image.Image):
    from PIL import ImageFilter
    a = np.asarray(img).astype(np.float32) / 255
    lum = a.mean(-1)
    blur = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(6))).astype(np.float32) / 255
    yy = np.linspace(0, 1, a.shape[0])[:, None]
    earth = (blur > 0.10) & (yy > 0.36)
    out = np.where(earth[..., None], a * 0.07 * np.array([0.6, 0.75, 1.25]), 0.008)
    star = ((lum - blur) > 0.25) & ~earth
    yx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    sun = ((yx[1] - a.shape[1] * 0.095) ** 2 + (yx[0] - a.shape[0] * 0.14) ** 2) < (a.shape[0] * 0.2) ** 2
    out = np.where((star & ~sun)[..., None], a, out)
    return np.clip(out, 0, 1)


BGS = {}
for name, fn in (("city", "2_city.png"), ("meadow", "1_meadow.png"), ("orbit", "4_orbit.png")):
    im = fit(Image.open(BG / fn))
    day = np.asarray(im).astype(np.float32) / 255
    nig = orbit_night(im) if name == "orbit" else night_grade(im)
    BGS[name] = (day, nig)


def bg_frame(name, t_local, dur, night):
    day, nig = BGS[name]
    a = day * (1 - night) + nig * night if 0 < night < 1 else (nig if night >= 1 else day)
    hh, ww = a.shape[:2]
    z = 1.0 + 0.05 * (t_local / dur)                 # slow push-in
    cw, ch = W * 1.06 / z * (ww / (W * 1.06)), H * 1.06 / z * (hh / (H * 1.06))
    cw, ch = min(ww, ww / z), min(hh, hh / z)
    x0, y0 = (ww - cw) / 2, (hh - ch) * 0.6
    img = Image.fromarray((a * 255).astype(np.uint8)).crop((x0, y0, x0 + cw, y0 + ch))
    return img.resize((W, H), Image.Resampling.BILINEAR)


# ---------------------------------------------------------------- actors per shot (mocap)

def seq_walk(clip, n, start=0):
    return s2.walk_seq(clip, n, start)


def shot_actors(name, n, sw):
    A = []
    if name == "city":
        A.append(dict(x0=200, h=230, flip=False, ground=972, hat="hardhat", seq=seq_walk(s2.WALK_A, n)))
        A.append(dict(x0=1500, h=215, flip=True, ground=955, hat="scarf", seq=seq_walk(s2.WALK_B, n, 4)))
        A.append(dict(x0=900, h=200, flip=False, ground=945, hat=None, seq=seq_walk(s2.WALK_A, n, 12)))
        A.append(dict(x0=-150, h=210, flip=False, ground=960, hat="cap", seq=seq_walk(s2.RUN, n)))
    elif name == "meadow":
        A.append(dict(x0=-60, h=300, flip=False, ground=985, hat="hardhat",
                      seq=s2.hold(s2.blend_into(seq_walk(s2.WALK_A, n), s2.segment(s2.SURPRISE, 3.45), sw + 5, 9), n)))
        A.append(dict(x0=1990, h=290, flip=True, ground=975, hat="scarf",
                      seq=s2.hold(s2.blend_into(seq_walk(s2.WALK_B, n), s2.segment(s2.SCARED, 0.5), sw + 9, 12), n)))
        A.append(dict(x0=1080, h=190, flip=False, ground=905, hat=None,
                      seq=s2.hold(s2.blend_into([s2.WALK_B[-1]] * n, s2.segment(s2.SCARED, 0.5), sw + 6, 12), n)))
        A.append(dict(x0=-250, h=200, flip=False, ground=915, hat="cap", seq=seq_walk(s2.RUN, n)))
        A.append(dict(x0=1700, h=180, flip=True, ground=900, hat=None,
                      seq=s2.hold(s2.blend_into(seq_walk(s2.WALK_A, n, 3), s2.segment(s2.SURPRISE, 3.45), sw + 14, 10), n)))
    return A


ACTORS = {}
for name, a, b in SHOTS:
    n = int((b - a) * FPS) + 1
    ACTORS[name] = shot_actors(name, n, int((SWITCH - a) * FPS))


def clock(t):
    s = 500 + (t - SWITCH)
    s = math.floor(s)
    return f"T+ 00:{s // 60:02d}:{s % 60:02d}"


def frame(i):
    t = i / FPS
    name, a, b = next(x for x in SHOTS if x[1] <= t < x[2]) if t < SHOTS[-1][2] else SHOTS[-1]
    tl = t - a
    night = st.ease((t - SWITCH) / 0.25)
    bg = bg_frame(name, tl, b - a, night)
    svg = []
    k = int(tl * FPS)
    for act in sorted(ACTORS.get(name, []), key=lambda x: x["h"]):
        st.ground_y = (lambda g: (lambda x: g))(act["ground"])
        act = {**act, "layer": "front"}
        piece = s2.stick(act, k, night)
        if night <= 0:   # painted scenes are softly lit: lighter contact shadow already in stick()
            pass
        svg.append(piece)
    svg.append('<defs><filter id="sh" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="5"/></filter></defs>')
    svg.append('<g filter="url(#sh)" opacity="0.75">' + st.text(1812, 104, clock(t), 40, "#000", "end", 600, "IBM Plex Mono") + "</g>")
    svg.append(st.text(1810, 100, clock(t), 40, "#FFB547", "end", 600, "IBM Plex Mono"))
    if name == "meadow":
        cap = st.ease((t - SWITCH - 1.6) / 0.5)
        if cap > 0:
            svg.append(st.text(110, 170, "The last sunlight", 84, "#F2EEE4", op=cap))
            svg.append(st.text(110, 262, "just arrived.", 84, "#F2EEE4", op=cap))
    if name == "orbit":
        cap = st.ease((tl - 0.6) / 0.5)
        svg.append(st.text(110, 170, "Earth, eight minutes", 84, "#F2EEE4", op=cap))
        svg.append(st.text(110, 262, "after the Sun vanished.", 84, "#F2EEE4", op=cap))
    doc = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{"".join(svg)}</svg>'
    png = st.resvg_py.svg_to_bytes(svg_string=doc, font_files=st.FONT_FILES, skip_system_fonts=True)
    ov = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    out = bg.convert("RGBA")
    out.alpha_composite(ov)
    # fade through black between shots (short)
    for _, a2, _b in SHOTS[1:]:
        d = abs(t - a2)
        if d < 0.12:
            out = Image.blend(out, Image.new("RGBA", out.size, (0, 0, 0, 255)), 1 - d / 0.12)
    return out.convert("RGB")


if __name__ == "__main__":
    mode = sys.argv[2] if len(sys.argv) > 2 else "all"
    if mode == "test":
        for t in (1.5, 5.0, 8.5, 12.0):
            frame(int(t * FPS)).save(OUT / f"t{t}.png")
    else:
        for i in range(int(SHOTS[-1][2] * FPS)):
            frame(i).save(OUT / "anim" / f"{i:04d}.png")
    print("ok")
