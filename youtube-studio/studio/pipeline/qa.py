"""Automatic composition QA for generated frames (local, free, no API calls).

Checks every image against the storyboard rules:
  * 16:9 format and enough pixels for 1920x1080;
  * 8-10% safe margins on the left, right and top, with exceptions for objects that
    deliberately continue past the frame (pipes, cables, roads, sea, ground);
  * cut-off objects at the frame edge;
  * the bottom 15% subtitle band: no heads/faces or key detail, background calm enough for text;
  * readability after downscaling (subject size and contrast at thumbnail size);
  * frames with a GFX overlay: the reserved overlay area must be empty.

Two analysis methods:
  * "plain"   - light scenes on a plain background (Light Explainer). The background is modelled
                as a smooth colour field, everything else is foreground, so margins are measured on
                real objects, not on single dark pixels.
  * "complex" - dark or full-bleed scenes. Subject bounds cannot be separated reliably, so margins
                are judged by detail touching the frame edges; anything doubtful goes to manual
                review (WARNING), never to an automatic failure.

Statuses: PASS, WARNING (worth a manual look), NEEDS_FIX (significant problem).

Optional auto-fix (plain scenes only): small scale-down (>= 90%) and/or shift, filling the exposed
strip with the modelled plain background. A fix is used only if a re-check proves it better and it
neither cuts content nor extends a continuing object. Dark/complex scenes are never padded.
Source PNGs are never modified; fixes go to <out>/<stem>_fixed.png.

Usage:
  studio pipe qa <image-or-dir> [...] [--out DIR] [--no-fix]   (or python -m studio.pipeline.qa)
  (`studio pipe record` calls qa.run() after every saved frame.)
Output: <out>/qa_report.md, <out>/qa_report.json, <out>/<stem>_preview.png, <out>/<stem>_fixed.png
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .episode import FONTS, ep

FONT = FONTS / "Inter-Bold.ttf"

AW, AH = 480, 270           # analysis resolution (16:9)
MARGIN, MARGIN_GOOD = 0.08, 0.10
SUB = 0.15                  # subtitle band height
EDGE_T = 40.0               # strong edge (Sobel/4 units; a bold cartoon outline is ~100+)
RANK = {"PASS": 0, "WARNING": 1, "NEEDS_FIX": 2}
STEM_RE = re.compile(r"(\d{2}_\d{2}_\d{2}_\d{3})")


# ------------------------------------------------------------------ data

@dataclass
class Issue:
    check: str
    status: str
    message: str
    fix: str = ""


@dataclass
class Result:
    file: str
    frame: int | None
    mode: str
    method: str
    size: str
    status: str = "PASS"
    issues: list[Issue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    fixed_file: str = ""
    fixed_status: str = ""
    preview: str = ""

    def add(self, check: str, status: str, message: str, fix: str = "") -> None:
        self.issues.append(Issue(check, status, message, fix))
        if RANK[status] > RANK[self.status]:
            self.status = status


# ------------------------------------------------------------------ helpers

def frame_meta() -> dict[str, dict]:
    """file stem -> storyboard frame (mode, shot, characters, gfx) from frames.txt."""
    try:
        from . import frames  # parsing only, nothing is written
        return {f["file"][:-4]: f for f in frames.parse()}
    except Exception:  # noqa: BLE001 - QA must still run on loose images
        return {}


def to_169(img: Image.Image) -> tuple[Image.Image, int, int]:
    """Centre-crop to exact 16:9. Returns image and cropped pixels (x, y)."""
    w, h = img.size
    tw = round(h * 16 / 9)
    if tw <= w:
        dx = w - tw
        return img.crop((dx // 2, 0, dx // 2 + tw, h)), dx, 0
    th = round(w * 9 / 16)
    dy = h - th
    return img.crop((0, dy // 2, w, dy // 2 + th)), 0, dy


def _vertical() -> bool:
    try:
        return ep().vertical
    except RuntimeError:            # loose images without an episode: the long format
        return False


def to_916(img: Image.Image) -> tuple[Image.Image, int, int]:
    """Centre-crop to exact 9:16 (Shorts). Returns image and cropped pixels (x, y)."""
    w, h = img.size
    tw = round(h * 9 / 16)
    if tw <= w:
        dx = w - tw
        return img.crop((dx // 2, 0, dx // 2 + tw, h)), dx, 0
    th = round(w * 16 / 9)
    dy = h - th
    return img.crop((0, dy // 2, w, dy // 2 + th)), 0, dy


def to_frame(img: Image.Image) -> tuple[Image.Image, int, int]:
    """Centre-crop to the selected episode's frame aspect (16:9, or 9:16 for a Short)."""
    return to_916(img) if _vertical() else to_169(img)


def check_vertical(path: Path, meta: dict | None, img: Image.Image | None = None) -> Result:
    """Shorts frames: format and resolution only. The composition analysis below is built for 16:9 frames;
    vertical frames are reviewed by eye on contact sheets (`studio pipe sheet`)."""
    src = img or Image.open(path)
    w, h = src.size
    mode = ("B" if meta and meta["mode"] == "B" else "A") if meta else "?"
    r = Result(str(path), meta["n"] if meta else None, mode, "vertical", f"{w}x{h}")
    dev = (w / h) / (9 / 16) - 1
    if abs(dev) <= 0.01:
        r.add("format", "PASS", f"aspect {w / h:.3f} ≈ 9:16")
    else:
        r.add("format", "NEEDS_FIX" if abs(dev) > 0.03 else "WARNING",
              f"aspect {w / h:.3f} is {dev:+.1%} off 9:16", "regenerate with aspect_ratio 9:16")
    if w >= 1080 - 8 and h >= 1920 - 8:
        r.add("resolution", "PASS", f"{w}x{h} downscales to 1080x1920 (zoom reserve ×{w / 1080:.2f})")
    else:
        r.add("resolution", "WARNING", f"{w}x{h} needs ×{1080 / w:.2f} upscale for 1080x1920",
              "generate at 2k for final frames")
    r.add("composition", "PASS", "vertical frame: review by eye (pipe sheet)")
    return r


def lum(a: np.ndarray) -> np.ndarray:
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def ring_mask(h: int, w: int, frac: float = 0.03) -> np.ndarray:
    m = np.zeros((h, w), bool)
    ry, rx = max(1, int(h * frac)), max(1, int(w * frac))
    m[:ry], m[-ry:], m[:, :rx], m[:, -rx:] = True, True, True, True
    return m


def poly_terms(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], axis=-1)


def label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected component labelling (small images only)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    flat = mask.ravel()
    lab_flat = lab.ravel()
    for start in np.flatnonzero(flat):
        if lab_flat[start]:
            continue
        n += 1
        stack = [start]
        lab_flat[start] = n
        while stack:
            p = stack.pop()
            y, x = divmod(p, w)
            for q, ok in ((p - 1, x > 0), (p + 1, x < w - 1), (p - w, y > 0), (p + w, y < h - 1)):
                if ok and flat[q] and not lab_flat[q]:
                    lab_flat[q] = n
                    stack.append(q)
    return lab, n


def morph(mask: np.ndarray, size: int, op: str) -> np.ndarray:
    im = Image.fromarray(mask.astype(np.uint8) * 255)
    f = ImageFilter.MaxFilter(size) if op == "dilate" else ImageFilter.MinFilter(size)
    return np.array(im.filter(f)) > 127


def fill_holes(mask: np.ndarray) -> np.ndarray:
    lab, _ = label(~mask)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    outside = np.isin(lab, list(border))
    return mask | (~outside & ~mask)


def sobel(L: np.ndarray) -> np.ndarray:
    p = np.pad(L, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.hypot(gx, gy) / 4


# ------------------------------------------------------------------ analysis

@dataclass
class Analysis:
    method: str
    fg: np.ndarray | None          # foreground mask (plain method)
    edges: np.ndarray              # strong edges
    coef: np.ndarray | None        # background polynomial (plain method)
    sides: dict                    # per side: kind, margin, extreme, blobs
    comps: list                    # significant foreground components
    metrics: dict
    luma: np.ndarray               # analysis-resolution luminance



def analyse(img: Image.Image, dark_hint: bool | None) -> Analysis:
    a = np.asarray(img.convert("RGB").resize((AW, AH), Image.Resampling.LANCZOS), np.float32)
    L = lum(a)
    mag = sobel(L)
    edges = mag > EDGE_T
    ring = ring_mask(AH, AW)
    ring_med = np.median(a[ring], axis=0)
    ring_L = float(lum(ring_med[None])[0])
    metrics = {"ring_luma": round(ring_L, 1), "mean_luma": round(float(L.mean()), 1)}

    light = ring_L > 165 and not dark_hint
    if light:
        ys, xs = np.mgrid[0:AH, 0:AW]
        X, Y = xs / AW, ys / AH
        T = poly_terms(X, Y)
        cand = np.linalg.norm(a - ring_med, axis=-1) < 40
        coef = None
        for _ in range(2):
            idx = np.flatnonzero(cand.ravel())[::7]
            if len(idx) < 200:
                break
            coef, *_ = np.linalg.lstsq(T.reshape(-1, 6)[idx], a.reshape(-1, 3)[idx], rcond=None)
            bg = T @ coef
            dist = np.linalg.norm(a - bg, axis=-1)
            sigma = float(np.std(dist[cand]))
            cand = dist < max(20.0, 3 * sigma)
        if coef is not None:
            bg = T @ coef
            dist = np.linalg.norm(a - bg, axis=-1)
            thr = max(30.0, 4 * sigma)
            chroma = a.max(-1) - a.min(-1)
            shadow = (chroma < 22) & ((lum(bg) - L) > 0) & ((lum(bg) - L) < 70) & (dist < 80)
            fg = (dist > thr) & ~shadow
            fg = morph(morph(fg, 5, "dilate"), 5, "erode")      # close outlines + fills
            fg = morph(morph(fg, 3, "erode"), 3, "dilate")      # drop speckle
            fg = fill_holes(fg)
            fg = drop_soft(fg, edges)
            plain = 1 - float(fg[ring].mean())
            metrics.update(bg_sigma=round(sigma, 1), ring_plain=round(plain, 3),
                           fg_area=round(float(fg.mean()), 3))
            # A light frame counts as "plain" only if the background model explains most of the
            # frame border; full-bleed light interiors fall back to the complex method.
            if plain > 0.6 and sigma < 14 and 0.02 < fg.mean() < 0.75:
                sides, comps = side_analysis(fg)
                return Analysis("plain", fg, edges, coef, sides, comps, metrics, L)
    # complex: estimate the main subjects by local contrast + saturation (lit figures, key props)
    est = saliency_mask(a, L, edges)
    metrics["est_area"] = round(float(est.mean()), 3)
    sides, comps = side_analysis(est)
    for k in sides:
        sides[k].update(complex_side(edges, k))
    reliable = 0.03 < est.mean() < 0.45 and sum(c["area"] >= 0.005 for c in comps) <= 8
    metrics["estimate_reliable"] = bool(reliable)
    return Analysis("complex", est if reliable else None, edges, None, sides,
                    comps if reliable else [], metrics, L)


HW, HH = 960, 540           # head-room analysis resolution


# Skin-tone profiles: daylight cartoon skin, and skin under warm lamp light in dark scenes.
SKIN_PROFILES = (
    {"rg": (15, 95), "sat": (0.12, 0.62), "L": (100, 245)},
    {"rg": (40, 120), "sat": (0.45, 0.75), "L": (90, 220)},
)


def find_heads(norm: Image.Image) -> tuple[list[dict], np.ndarray]:
    """Locate cartoon human faces (skin-tone blobs with dark facial features) and measure how far
    the head above each face (hair, hat) reaches toward the top edge.

    Above each face the columns are walked upward while pixels look like head material (skin,
    hair, a dark hat) AND differ from the background sampled at the same height beside the head.
    The 25th percentile of the stop rows is the head top: one stray pixel does not decide the
    result, a tall top hat does.
    """
    a = np.asarray(norm.convert("RGB").resize((HW, HH), Image.Resampling.LANCZOS), np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    L = lum(a)
    warm = (r > 120) & (r > g) & (g > b) & (r - b > 35)
    heads: list[dict] = []
    all_skin = np.zeros((HH, HW), bool)
    for prof in SKIN_PROFILES:
        skin = (warm & (r - g > prof["rg"][0]) & (r - g < prof["rg"][1]) & (sat > prof["sat"][0])
                & (sat < prof["sat"][1]) & (prof["L"][0] < L) & (prof["L"][1] > L))
        headlike = skin | (L < 85) | ((r >= g) & (g >= b) & (L < 170)) | ((sat < 0.12) & (L > 200))
        skin = morph(morph(morph(skin, 3, "erode"), 9, "dilate"), 5, "erode")  # merge lit fragments
        skin = fill_holes(skin)                                                   # eyes, brows, mouth
        all_skin |= skin
        for h in _heads_from_skin(a, L, skin, headlike):
            if not any(abs(h["face_top"] - o["face_top"]) < 0.03 and h["x0"] < o["x1"] and o["x0"] < h["x1"]
                       for o in heads):
                heads.append(h)
    return heads, all_skin


def _heads_from_skin(a: np.ndarray, L: np.ndarray, skin: np.ndarray, headlike: np.ndarray) -> list[dict]:
    lab, n = label(skin)
    heads = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        area = len(ys) / (HW * HH)
        if not 0.002 <= area <= 0.06:
            continue
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        w, h = x1 - x0, y1 - y0
        if not 0.55 <= h / w <= 1.9 or len(ys) / (w * h) < 0.6 or y1 > HH * 0.75:
            continue
        inner = L[y0 + h // 5:y1 - h // 5, x0 + w // 5:x1 - w // 5]
        dark = float((inner < 75).mean()) if inner.size else 0.0
        if not 0.01 <= dark <= 0.25:          # eyes / brows / mouth make a face, not a wall
            continue
        cols = range(x0 + int(w * 0.2), x1 - int(w * 0.2))
        limit = max(0, y0 - int(2.5 * h))
        lx = slice(max(0, x0 - int(1.2 * w)), max(0, x0 - int(0.7 * w)))
        rx = slice(min(HW, x1 + int(0.7 * w)), min(HW, x1 + int(1.2 * w)))
        stops, open_ = [], 0
        for x in cols:
            y, gap = y0 - 1, 0
            while y > limit:
                # background beside the head, each side on its own (a window on one side and a wall
                # on the other must not average into a colour that matches neither)
                sides = [a[y, sl] for sl in (lx, rx) if sl.stop > sl.start]
                if not sides:
                    break
                d_bg = min(np.linalg.norm(a[y, x] - np.median(sd, axis=0)) for sd in sides)
                if headlike[y, x] and d_bg > 35:
                    gap = 0
                else:
                    gap += 1
                    if gap > 2:
                        y += gap
                        break
                y -= 1
            if y <= limit and limit > 0:
                open_ += 1                     # never met background: ambiguous column
            stops.append(max(0, y))
        if not stops:
            continue
        top = float(np.percentile(stops, 25))
        heads.append({"x0": x0 / HW, "x1": x1 / HW, "face_top": y0 / HH, "face_h": h / HH,
                      "head_top": top / HH, "touches": top <= 2,
                      "ambiguous": open_ > len(stops) * 0.5, "hat_or_hair": (y0 - top) / max(h, 1)})
    return heads


def drop_soft(mask: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Remove components with almost no strong edges inside: soft shadows, glows, vignettes."""
    lab, n = label(mask)
    near_edge = morph(edges, 3, "dilate")
    keep = np.zeros_like(mask)
    for i in range(1, n + 1):
        m = lab == i
        if (near_edge & m).sum() / m.sum() >= 0.03:
            keep |= m
    return keep


def saliency_mask(a: np.ndarray, L: np.ndarray, edges: np.ndarray) -> np.ndarray:
    blur = np.asarray(Image.fromarray(L.astype(np.uint8)).filter(ImageFilter.GaussianBlur(AW * 0.06)),
                      np.float32)
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    sal = np.abs(L - blur) + 60 * sat * (mx / 255)
    m = sal > max(35.0, float(np.percentile(sal, 80)))
    m = morph(morph(m, 5, "dilate"), 5, "erode")
    m = morph(morph(m, 3, "erode"), 3, "dilate")
    return drop_soft(fill_holes(m), edges)


def band_slice(side: str, frac: float) -> tuple[slice, slice]:
    bh, bw = max(1, round(AH * frac)), max(1, round(AW * frac))
    return {
        "left": (slice(None), slice(0, bw)), "right": (slice(None), slice(AW - bw, AW)),
        "top": (slice(0, bh), slice(None)), "bottom": (slice(AH - bh, AH), slice(None)),
    }[side]


def complex_side(edges: np.ndarray, side: str) -> dict:
    outer = float(edges[band_slice(side, 0.02)].mean())
    band = float(edges[band_slice(side, MARGIN)].mean())
    return {"edge_outer": round(outer, 3), "edge_band": round(band, 3)}


def side_analysis(fg: np.ndarray) -> tuple[dict, list]:
    lab, n = label(fg)
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < AW * AH * 0.0008:
            continue
        comps.append({"id": i, "area": len(ys) / (AW * AH), "x0": xs.min() / AW,
                      "x1": (xs.max() + 1) / AW, "y0": ys.min() / AH, "y1": (ys.max() + 1) / AH})
    main_ids = {c["id"] for c in comps if c["area"] >= max(0.08, max((d["area"] for d in comps), default=0) * 0.5)}
    sides = {}
    for side in ("left", "right", "top", "bottom"):
        horiz = side in ("left", "right")
        depth = round((AW if horiz else AH) * MARGIN)
        sub = fg[band_slice(side, MARGIN)]
        sublab = lab[band_slice(side, MARGIN)]
        if side in ("right", "bottom"):  # orient so index 0 is the frame edge
            sub, sublab = (sub[:, ::-1], sublab[:, ::-1]) if horiz else (sub[::-1], sublab[::-1])
        if not horiz:
            sub, sublab = sub.T, sublab.T   # rows along the edge, columns = distance from edge
        blab, bn = label(sub)
        blobs, extreme, robust, kind = [], None, None, "clear"
        length = sub.shape[0]
        for i in range(1, bn + 1):
            m = blab == i
            area = m.sum() / (AW * AH)
            if area < 0.0003:
                continue
            cols = np.nonzero(m.any(axis=0))[0]
            dist = cols.min() / (AW if horiz else AH)
            touches = cols.min() == 0
            span_edge = m[:, 0].sum() / length
            span_inner = m[:, depth - 1].sum() / length
            continuing = (touches and m[:, depth - 1].any() and span_edge < 0.4
                          and 0.4 < (span_inner / max(span_edge, 1e-6)) < 2.5)
            # a pipe/cable receding in perspective tapers to a point just short of the edge
            near = m[:, :max(2, depth // 4)].any(axis=1).sum() / length
            tapering = (not touches and dist < 0.025 and m[:, depth - 1].any()
                        and span_inner < 0.12 and near <= span_inner)
            ground = side == "bottom" and touches and span_edge >= 0.4
            ids = sublab[m]
            main = bool(np.isin(ids, list(main_ids)).mean() > 0.5) if len(ids) else False
            b = {"area": round(float(area), 4), "dist": round(float(dist), 4),
                 "touches": bool(touches), "span_edge": round(float(span_edge), 3),
                 "continuing": bool(continuing or ground or tapering), "main": main}
            blobs.append(b)
            if continuing or ground or tapering:
                kind = "continuing" if kind == "clear" else kind
                continue
            if touches:
                kind = "cut"
            extreme = dist if extreme is None else min(extreme, dist)
            if area >= 0.0008:
                robust = dist if robust is None else min(robust, dist)
        if kind != "cut" and extreme is not None:
            kind = "intrusion"   # a real intrusion outranks a continuing object on the same side
        sides[side] = {"kind": kind, "extreme": extreme, "robust": robust, "blobs": blobs,
                       "cut_main": any(b["touches"] and not b["continuing"] and b["main"]
                                       and b["area"] >= 0.002 for b in blobs)}
    return sides, comps


# ------------------------------------------------------------------ checks

def check(path: Path, meta: dict | None, img: Image.Image | None = None) -> tuple[Result, Analysis, Image.Image]:
    src = img or Image.open(path)
    w, h = src.size
    norm, cx, cy = to_169(src.convert("RGB"))
    mode = ("B" if meta and meta["mode"] == "B" else "A") if meta else "?"
    r = Result(str(path), meta["n"] if meta else None, mode, "", f"{w}x{h}")
    an = analyse(norm, dark_hint=(mode == "B") if meta else None)
    r.method, r.metrics = an.method, an.metrics

    # format and resolution
    dev = (w / h) / (16 / 9) - 1
    if abs(dev) <= 0.01:
        note = f"; centre-crop {cx or cy}px {'width' if cx else 'height'} to fit 16:9" if (cx or cy) else ""
        r.add("format", "PASS", f"aspect {w / h:.3f} ≈ 16:9{note}")
    else:
        r.add("format", "NEEDS_FIX" if abs(dev) > 0.03 else "WARNING",
              f"aspect {w / h:.3f} is {dev:+.1%} off 16:9", "regenerate with aspect_ratio 16:9")
    if w >= 1920 and h >= 1080 - 8:
        r.add("resolution", "PASS", f"{w}x{h} downscales to 1920x1080 (zoom reserve ×{w / 1920:.2f})")
    else:
        r.add("resolution", "WARNING", f"{w}x{h} needs ×{1920 / w:.2f} upscale for 1080p",
              "generate at 2k for final frames")

    if an.method == "plain":
        plain_checks(r, an, meta)
    else:
        complex_checks(r, an, meta)
    gfx_check(r, an, meta, norm)
    if meta is None or meta["era"] in ("h", "m") or any(c not in MASCOTS for c in meta["chars"]):
        named = bool(meta) and any(c not in MASCOTS for c in meta["chars"])
        headroom_check(r, norm, named)
    return r, an, norm


def plain_checks(r: Result, an: Analysis, meta: dict | None) -> None:
    has_chars = bool(meta and meta["chars"])
    for side in ("left", "right", "top"):
        s = an.sides[side]
        if s["kind"] == "cut":
            if s["cut_main"]:
                r.add(f"margin_{side}", "NEEDS_FIX", f"main subject cut by the {side} edge",
                      "regenerate; a cut object cannot be restored by shifting")
            else:
                r.add(f"margin_{side}", "WARNING", f"a secondary object touches the {side} edge "
                      "(scenery is fine; a cut tool or prop is not)", "check the preview")
        elif s["kind"] in ("intrusion",):
            d = s["robust"] if s["robust"] is not None else s["extreme"]
            ext = s["extreme"]
            msg = f"{side} margin {d:.1%} (outermost point {ext:.1%}), target ≥ {MARGIN:.0%}"
            if d >= MARGIN:
                r.add(f"margin_{side}", "PASS", msg)
            elif d >= 0.05:
                r.add(f"margin_{side}", "WARNING", msg, "auto-fix: small shift / scale")
            else:
                r.add(f"margin_{side}", "NEEDS_FIX", msg, "auto-fix if background is plain, else regenerate")
        elif s["kind"] == "continuing":
            r.add(f"margin_{side}", "PASS", f"{side}: only a continuing object (pipe/cable/ground) reaches the edge")
        else:
            r.add(f"margin_{side}", "PASS", f"{side}: clear")
    subtitle_checks(r, an, has_chars)
    readability(r, an)


def subtitle_checks(r: Result, an: Analysis, has_chars: bool) -> None:
    band = slice(round(AH * (1 - SUB)), AH)
    detail = float(an.edges[band].mean())
    r.metrics["sub_edge_density"] = round(detail, 3)
    r.metrics["sub_luma_std"] = round(float(an.luma[band].std()), 1)
    if an.method == "plain":
        fg_band = float(an.fg[band].mean())
        r.metrics["sub_fg"] = round(fg_band, 3)
        heads = [c for c in an.comps if c["area"] > 0.015 and has_chars
                 and c["y0"] + 0.3 * (c["y1"] - c["y0"]) > 1 - SUB]
        if heads:
            r.add("subtitles", "NEEDS_FIX", "a large object's top part (likely a head/face) sits in the "
                  "bottom 15% subtitle band", "regenerate with the character higher in frame")
        elif fg_band > 0.25 and detail > 0.06:
            r.add("subtitles", "WARNING", f"subtitle band {fg_band:.0%} covered with detailed content",
                  "check that no key detail sits under the subtitles; use a subtitle box")
        elif fg_band > 0.02:
            lowest = max((c["y1"] for c in an.comps), default=0)
            r.add("subtitles", "PASS", f"band mostly calm (objects reach {lowest:.1%} of height, "
                  f"{fg_band:.0%} of band; no heads)")
        else:
            r.add("subtitles", "PASS", "subtitle band empty")
    else:
        busy = detail > 0.08 or r.metrics["sub_luma_std"] > 50
        heads = [c for c in an.comps if c["area"] > 0.015 and has_chars
                 and c["y0"] + 0.3 * (c["y1"] - c["y0"]) > 1 - SUB]
        if heads:
            r.add("subtitles", "WARNING", "an estimated figure's upper part sits in the subtitle band",
                  "manual review: no face may sit under the subtitles")
        else:
            r.add("subtitles", "WARNING" if busy else "PASS",
                  f"subtitle band detail {detail:.2f} ({'busy' if busy else 'calm'})",
                  "use a semi-opaque subtitle box" if busy else "")


def complex_checks(r: Result, an: Analysis, meta: dict | None) -> None:
    """Dark / full-bleed scenes: estimates only, so problems become WARNING (manual review)."""
    reliable = r.metrics.get("estimate_reliable", False)
    if not reliable:
        r.add("margins", "WARNING", "subject bounds cannot be separated reliably in this scene "
              f"(estimated subject area {r.metrics.get('est_area', 0):.0%})",
              "manual review with the preview guides")
    else:
        for side in ("left", "right", "top"):
            sd = an.sides[side]
            if sd["kind"] == "cut":
                r.add(f"margin_{side}", "WARNING", f"a lit/detailed object seems to touch the {side} edge "
                      "(estimate)", "manual review: scenery may run off, a face/tool may not")
            elif sd["kind"] == "intrusion":
                d = sd["robust"] if sd["robust"] is not None else sd["extreme"]
                st = "PASS" if d >= MARGIN else "WARNING"
                r.add(f"margin_{side}", st, f"{side} margin ≈ {d:.1%} (estimate), target ≥ {MARGIN:.0%}",
                      "" if st == "PASS" else "manual review; never pad a dark scene, regenerate if needed")
            else:
                r.add(f"margin_{side}", "PASS", f"{side}: no estimated subject near the edge"
                      + (" (continuing object only)" if sd["kind"] == "continuing" else ""))
    subtitle_checks(r, an, bool(meta and meta["chars"]))
    r.metrics["edge_density"] = round(float(an.edges.mean()), 3)


def readability(r: Result, an: Analysis) -> None:
    area = float(an.fg.mean())
    if area < 0.03:
        r.add("readability", "WARNING", f"subjects cover only {area:.1%} of the frame", "frame closer")
    else:
        r.add("readability", "PASS", f"subjects cover {area:.0%} of the frame; clear figure/ground at thumbnail size")


MASCOTS = {"octo", "lynx", "bit"}


def headroom_check(r: Result, norm: Image.Image, named_people: bool = False) -> None:
    """Top-edge check for human figures: hair, hats (top hats!) and the top of the head.

    Works in light and dark scenes because it compares the head with the background at the same
    height rather than with a global background model. Never triggers regeneration by itself.
    """
    heads, _ = find_heads(norm)
    r.metrics["heads"] = [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in h.items()}
                          for h in heads]
    if not heads:
        if named_people:
            r.add("headroom", "WARNING", "a named historical person is in this frame but no face was "
                  "located, so headroom could not be measured", "manual review of the head/hat area")
        else:
            r.add("headroom", "PASS", "no prominent human face located (headroom not measured)")
        return
    worst = min(heads, key=lambda h: h["head_top"])
    tall = " (hat or tall hair)" if worst["hat_or_hair"] > 0.6 else ""
    msg = (f"top of the head{tall} at {worst['head_top']:.1%} of frame height, "
           f"face top at {worst['face_top']:.1%}; target ≥ {MARGIN:.0%}")
    if worst["touches"] or worst["head_top"] < 0.03:
        r.add("headroom", "NEEDS_FIX", "head/hat touches or nearly touches the top edge: " + msg,
              "regenerate with more headroom (prompt: whole hat visible, empty space above it); "
              "padding a full-bleed scene is not allowed")
    elif worst["head_top"] < MARGIN:
        r.add("headroom", "WARNING", "tight headroom: " + msg,
              "manual review; avoid camera push-ins toward the top in editing")
    elif worst["ambiguous"]:
        r.add("headroom", "WARNING", "head outline merges with the background; " + msg,
              "manual review with the preview")
    else:
        r.add("headroom", "PASS", msg)


def gfx_check(r: Result, an: Analysis, meta: dict | None, norm: Image.Image) -> None:
    if not meta or not meta.get("gfx"):
        return
    ov = ep().overlays_dir / meta["gfx_file"]
    if not ov.is_file():
        r.add("gfx_area", "WARNING", f"overlay {ov.name} missing; run `studio pipe build`")
        return
    box = Image.open(ov).getchannel("A").getbbox()
    if not box:
        return
    x0, y0, x1, y1 = (round(box[0] / 1920 * AW), round(box[1] / 1080 * AH),
                      round(box[2] / 1920 * AW), round(box[3] / 1080 * AH))
    if an.method == "plain":
        occ = float(an.fg[y0:y1, x0:x1].mean())
    else:
        occ = float(an.edges[y0:y1, x0:x1].mean()) * 3
    r.metrics["gfx_area_occupied"] = round(occ, 3)
    if occ > 0.06:
        r.add("gfx_area", "NEEDS_FIX", f"reserved overlay area is {occ:.0%} occupied by drawn content",
              "regenerate: the prompt must leave this area empty for the exact chart")
    else:
        r.add("gfx_area", "PASS", "reserved overlay area is empty")


# ------------------------------------------------------------------ auto-fix

def plan_fix(an: Analysis) -> tuple[float, float, float] | None:
    """Smallest scale/shift that brings left/right/top margins to target. None if unsafe."""
    s_ = an.sides
    if any(s_[k]["kind"] == "cut" for k in ("left", "right", "top")):
        return None
    ext = {k: (s_[k]["robust"] if s_[k]["robust"] is not None else s_[k]["extreme"]) for k in s_}
    lx = ext["left"] if s_["left"]["kind"] == "intrusion" else (min((c["x0"] for c in an.comps), default=0.5))
    rx = 1 - ext["right"] if s_["right"]["kind"] == "intrusion" else max((c["x1"] for c in an.comps), default=0.5)
    ty = ext["top"] if s_["top"]["kind"] == "intrusion" else min((c["y0"] for c in an.comps), default=0.5)
    by = max((c["y1"] for c in an.comps), default=0.5)
    plain = {k: s_[k]["kind"] in ("clear", "intrusion") for k in s_}
    cont = {k: s_[k]["kind"] == "continuing" for k in s_}
    best = None
    for s in (1.0, 0.98, 0.96, 0.94, 0.92, 0.90):
        for tx in np.arange(-0.10, 0.1001, 0.0025):
            for ty_ in np.arange(-0.06, 0.0601, 0.0025):
                f = lambda v, t: 0.5 + s * (v - 0.5) + t  # noqa: E731, B023 - used within this iteration
                gap = {"left": f(0, tx) > 1e-6, "right": f(1, tx) < 1 - 1e-6,
                       "top": f(0, ty_) > 1e-6, "bottom": f(1, ty_) < 1 - 1e-6}
                if any(gap[k] and not plain[k] for k in gap):
                    continue                      # never extend a continuing object or scenery
                if not cont["left"] and f(lx, tx) < MARGIN:
                    continue
                if not cont["right"] and f(rx, tx) > 1 - MARGIN:
                    continue
                if not cont["top"] and f(ty, ty_) < MARGIN:
                    continue
                if f(by, ty_) > max(by, 1 - SUB) + 1e-6:
                    continue                      # do not push content further into the subtitles
                cost = 3 * (1 - s) + abs(tx) + abs(ty_)
                if best is None or cost < best[0]:
                    best = (cost, s, float(tx), float(ty_))
    return None if best is None or best[0] == 0 else best[1:]


def apply_fix(norm: Image.Image, an: Analysis, s: float, tx: float, ty: float) -> Image.Image:
    W, H = norm.size
    # background field: polynomial model evaluated over the whole canvas (incl. exposed strips)
    ys, xs = np.mgrid[0:H:4, 0:W:4]
    u = ((xs + 2) / W - 0.5 - tx) / s + 0.5
    v = ((ys + 2) / H - 0.5 - ty) / s + 0.5
    bg = poly_terms(u, v) @ an.coef
    canvas = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).resize((W, H), Image.Resampling.BICUBIC)
    sw, sh = round(W * s), round(H * s)
    content = norm.resize((sw, sh), Image.Resampling.LANCZOS)
    ox, oy = round(W * (0.5 - s / 2 + tx)), round(H * (0.5 - s / 2 + ty))
    feather = max(4, round(W * 0.006))
    alpha = Image.new("L", (sw, sh), 255)
    d = ImageDraw.Draw(alpha)
    for i in range(feather):  # soft seam only on edges that expose new background
        val = round(255 * (i + 1) / (feather + 1))
        if ox > 0:
            d.line([(i, 0), (i, sh)], fill=val)
        if ox + sw < W:
            d.line([(sw - 1 - i, 0), (sw - 1 - i, sh)], fill=val)
        if oy > 0:
            d.line([(0, i), (sw, i)], fill=val)
        if oy + sh < H:
            d.line([(0, sh - 1 - i), (sw, sh - 1 - i)], fill=val)
    canvas.paste(content, (ox, oy), alpha)
    return canvas


# ------------------------------------------------------------------ preview

def preview(norm: Image.Image, r: Result, an: Analysis, out: Path) -> None:
    W, H = 1280, 720
    im = norm.resize((W, H), Image.Resampling.LANCZOS).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rectangle([0, round(H * (1 - SUB)), W, H], fill=(40, 120, 255, 60))
    for frac, col in ((MARGIN, (255, 200, 0, 255)), (MARGIN_GOOD, (0, 200, 120, 200))):
        d.rectangle([W * frac, H * frac, W * (1 - frac), H * (1 - frac)], outline=col, width=2)
    if an.fg is not None:
        edge = an.fg & ~morph(an.fg, 3, "erode")
        m = Image.fromarray((edge * 255).astype(np.uint8)).resize((W, H), Image.Resampling.NEAREST)
        d.bitmap((0, 0), m, fill=(255, 0, 200, 230))
    for hd in r.metrics.get("heads", []):
        x0, x1, ht, ft = hd["x0"] * W, hd["x1"] * W, hd["head_top"] * H, hd["face_top"] * H
        d.rectangle([x0, ht, x1, ft + hd["face_h"] * H], outline=(0, 230, 255, 255), width=2)
        d.line([x0 - 20, ht, x1 + 20, ht], fill=(0, 230, 255, 255), width=3)
    colours = {"PASS": (0, 160, 90), "WARNING": (230, 150, 0), "NEEDS_FIX": (210, 30, 30)}
    font = ImageFont.truetype(str(FONT), 22) if FONT.is_file() else ImageFont.load_default()
    small = ImageFont.truetype(str(FONT), 16) if FONT.is_file() else ImageFont.load_default()
    d.rectangle([0, 0, W, 34], fill=(*colours[r.status], 230))
    d.text((10, 6), f"{r.status}  #{r.frame or '?'}  {Path(r.file).name}  [{r.method}]", font=font, fill="white")
    y = 40
    for i in r.issues:
        if i.status != "PASS":
            d.text((10, y), f"{i.status}: {i.message}", font=small, fill=(*colours[i.status], 255),
                   stroke_width=2, stroke_fill="white")
            y += 22
    d.text((10, H - 24), "yellow = 8% safe, green = 10%, blue = subtitle band, magenta = objects, "
           "cyan = head top",
           font=small, fill="white", stroke_width=2, stroke_fill="black")
    Image.alpha_composite(im, ov).convert("RGB").save(out)


# ------------------------------------------------------------------ driver

def unique_stem(path: Path, base: Path | None) -> str:
    try:
        rel = path.relative_to(base) if base else Path(path.name)
    except ValueError:
        rel = Path(path.name)
    return "__".join(rel.with_suffix("").parts)


def run(paths: list[Path], out: Path, fix: bool = True, base: Path | None = None,
        replace: bool = False) -> list[Result]:
    """Check images. replace=True rewrites the report with exactly these files (folder scans);
    the default merges into an existing report (one frame at a time after generation)."""
    out.mkdir(parents=True, exist_ok=True)
    meta_all = frame_meta()
    results = []
    for p in paths:
        m = STEM_RE.search(p.stem)
        meta = meta_all.get(m.group(1)) if m else None
        if _vertical():
            results.append(check_vertical(p, meta))
            continue
        r, an, norm = check(p, meta)
        stem = unique_stem(p, base)
        if fix and an.method == "plain" and any(
                i.fix.startswith("auto-fix") and i.status != "PASS" for i in r.issues):
            plan = plan_fix(an)
            if plan:
                fixed = apply_fix(norm, an, *plan)
                r2, an2, _ = check(p, meta, img=fixed)
                worse = any(i.status == "NEEDS_FIX" for i in r2.issues if i.check != "resolution")
                if RANK[r2.status] < RANK[r.status] or (not worse and r2.status == r.status and
                                                         _deficit(an2) < _deficit(an)):
                    fpath = save_new(fixed, out, f"{stem}_fixed")
                    r.fixed_file, r.fixed_status = str(fpath), r2.status
                    r.metrics["fix"] = {"scale": plan[0], "shift_x": round(plan[1], 4),
                                        "shift_y": round(plan[2], 4)}
                    preview(fixed, r2, an2, out / f"{stem}_fixed_preview.png")
                else:
                    r.metrics["fix"] = "rejected: re-check not better"
            else:
                r.metrics["fix"] = "not possible without cutting or extending content"
        if r.status != "PASS":
            r.preview = str(out / f"{stem}_preview.png")
            preview(norm, r, an, Path(r.preview))
        results.append(r)
    write_report(results, out, base, replace)
    return results


def save_new(img: Image.Image, out: Path, stem: str) -> Path:
    """Never overwrite an earlier fixed copy (it may already be accepted and locked read-only):
    reuse it if the pixels are identical, otherwise save as <stem>_2.png, <stem>_3.png, ..."""
    k = 1
    while True:
        path = out / (f"{stem}.png" if k == 1 else f"{stem}_{k}.png")
        if not path.exists():
            img.save(path)
            return path
        with Image.open(path) as old:
            if old.size == img.size and np.array_equal(np.asarray(old.convert("RGB")), np.asarray(img)):
                return path
        k += 1


def _deficit(an: Analysis) -> float:
    tot = 0.0
    for k in ("left", "right", "top"):
        s = an.sides[k]
        if s.get("kind") == "intrusion":
            d = s["robust"] if s["robust"] is not None else s["extreme"]
            tot += max(0.0, MARGIN - d)
    return tot


def write_report(results: list[Result], out: Path, base: Path | None, replace: bool = False) -> None:
    jpath = out / "qa_report.json"
    old = {}
    if jpath.is_file() and not replace:
        old = {e["file"]: e for e in json.loads(jpath.read_text(encoding="utf-8"))}
    for r in results:
        old[r.file] = asdict(r)
    entries = sorted(old.values(), key=lambda e: e["file"])
    jpath.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")

    def rel(p: str) -> str:
        if not p:
            return ""
        try:
            return Path(p).relative_to(out).as_posix()
        except ValueError:
            return Path(p).as_posix()

    lines = ["# Enginovue frame QA report\n",
             "Statuses: PASS (meets rules), WARNING (look manually), NEEDS_FIX (significant problem). "
             "Generated by qa.py; sources are never modified.\n",
             "| File | Frame | Method | Status | Main issue | Auto-fix |", "|---|---|---|---|---|---|"]
    for e in entries:
        bad = sorted((i for i in e["issues"] if i["status"] != "PASS"), key=lambda i: (-RANK[i["status"]], i["check"] in ("format", "resolution")))
        main = bad[0]["message"] if bad else "—"
        fx = f"{e['fixed_status']} → `{rel(e['fixed_file'])}`" if e["fixed_file"] else (
            e["metrics"].get("fix", "—") if isinstance(e["metrics"].get("fix"), str) else "—")
        name = display_name(Path(e["file"]), base)
        lines.append(f"| `{name}` | {e['frame'] or '?'} | {e['method']} | **{e['status']}** | {main} | {fx} |")
    lines.append("")
    for e in entries:
        lines.append(f"## {Path(e['file']).name} — {e['status']}\n")
        lines.append(f"- File: `{e['file']}` ({e['size']}), frame #{e['frame'] or '?'}, mode {e['mode']}, "
                     f"method {e['method']}")
        for i in e["issues"]:
            tail = f" → {i['fix']}" if i["fix"] and i["status"] != "PASS" else ""
            lines.append(f"- {i['status']} · {i['check']}: {i['message']}{tail}")
        if e["preview"]:
            lines.append(f"- Preview: `{rel(e['preview'])}`")
        if e["fixed_file"]:
            fx = e["metrics"]["fix"]
            lines.append(f"- Auto-fix ({e['fixed_status']}): scale {fx['scale']:.2f}, shift x {fx['shift_x']:+.1%}, "
                         f"y {fx['shift_y']:+.1%} → `{rel(e['fixed_file'])}`")
        elif isinstance(e["metrics"].get("fix"), str):
            lines.append(f"- Auto-fix: {e['metrics']['fix']}")
        lines.append("")
    (out / "qa_report.md").write_text("\n".join(lines), encoding="utf-8")


def display_name(path: Path, base: Path | None) -> str:
    if base is not None and path.is_relative_to(base):
        return path.relative_to(base).as_posix()
    return path.as_posix()


def selftest() -> None:
    """Synthetic frames with known answers; also proves sources are never modified."""
    import hashlib
    import tempfile

    def frame(bg, shapes) -> Image.Image:
        im = Image.new("RGB", (1920, 1080), bg)
        d = ImageDraw.Draw(im)
        for kind, box, fill in shapes:
            if kind == "blob":  # outlined "character" with an inner detail
                d.ellipse(box, fill=fill, outline=(10, 20, 40), width=10)
                d.ellipse([box[0] + 60, box[1] + 60, box[0] + 140, box[1] + 140], fill=(255, 190, 40),
                          outline=(10, 20, 40), width=6)
            else:
                d.rectangle(box, fill=fill, outline=(10, 20, 40), width=8)
        return im

    light, teal = (238, 242, 247), (20, 130, 150)
    dark_blobs = [("blob", (x, 200 + x % 300, x + 260, 460 + x % 300), (40, 90, 140))
                  for x in range(-100, 1900, 330)]
    cases = {  # name: (image, expected status, expected status of the auto-fixed copy)
        "ok_centered": (frame(light, [("blob", (700, 300, 1200, 800), teal)]), "PASS", None),
        "near_left": (frame(light, [("blob", (50, 300, 550, 800), teal)]), "NEEDS_FIX", "PASS"),
        "pipe_right": (frame(light, [("blob", (500, 300, 1000, 800), teal),
                                     ("rect", (900, 520, 1920, 600), (90, 95, 110))]), "PASS", None),
        "cut_left": (frame(light, [("blob", (-300, 200, 600, 900), teal)]), "NEEDS_FIX", None),
        "dark_scene": (frame((8, 27, 53), dark_blobs), "WARNING", None),
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        paths, hashes = [], {}
        for name, (im, _, _) in cases.items():
            path = tmp / f"{name}.png"
            im.save(path)
            paths.append(path)
            hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        results = {Path(r.file).stem: r for r in run(paths, tmp / "qa", base=tmp)}
        ok = True
        for name, (_, want, want_fix) in cases.items():
            r = results[name]
            good = r.status == want and (want_fix is None or r.fixed_status == want_fix)
            ok &= good
            print(f"{'ok ' if good else 'BAD'} {name:12} -> {r.status}"
                  f"{' / fixed copy ' + r.fixed_status if r.fixed_file else ''}  (expected {want}"
                  f"{' / fixed ' + want_fix if want_fix else ''})")
        control = None
        with contextlib.suppress(RuntimeError):     # no episode selected: skip the pilot control frame
            control = ep().work / "pilot_low_2k" / "00_02_20_000.png"
        if control is not None and control.is_file():   # pilot frame #44: top hat touching the top edge must be caught
            rc, _, _ = check(control, frame_meta().get("00_02_20_000"))
            hr = next((i for i in rc.issues if i.check == "headroom"), None)
            good = bool(hr) and hr.status == "NEEDS_FIX"
            ok &= good
            print(f"{'ok ' if good else 'BAD'} control #44 top hat -> {hr.status if hr else 'no check'} "
                  "(expected NEEDS_FIX)")
        same = all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in hashes.items())
        print(("ok " if same else "BAD") + " source PNGs unchanged")
        if not (ok and same):
            raise SystemExit(1)


DERIVED_DIRS = {"qa", "composite"}   # QA output and editorial composites are not source frames


def collect(args: list[str]) -> list[Path]:
    files: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            files += sorted(q for q in p.rglob("*.png")
                            if not (set(q.relative_to(p).parts[:-1]) & DERIVED_DIRS)
                            and not q.stem.endswith(("_fixed", "_preview")))
        elif p.suffix.lower() == ".png":
            files.append(p)
    return files


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--out", help="report folder (default: <first dir>/qa)")
    ap.add_argument("--no-fix", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="run synthetic checks and exit")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    files = collect(a.paths)
    if not files:
        raise SystemExit("no PNG files found")
    first = Path(a.paths[0])
    base = first if first.is_dir() else first.parent
    out = Path(a.out) if a.out else base / "qa"
    results = run(files, out, fix=not a.no_fix, base=base, replace=first.is_dir())
    for r in results:
        bad = sorted((i for i in r.issues if i.status != "PASS"), key=lambda i: (-RANK[i.status], i.check in ("format", "resolution")))
        fx = f"  fixed→{r.fixed_status}" if r.fixed_file else ""
        print(f"{r.status:9} #{r.frame or '?':<4} {display_name(Path(r.file), base)}"
              f"  [{r.method}] {bad[0].message if bad else ''}{fx}")
    print(f"report: {out / 'qa_report.md'}")


if __name__ == "__main__":
    main()
