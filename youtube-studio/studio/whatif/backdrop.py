"""Painted backgrounds: fit to the frame height, mirrored strip for long camera travel, motion blur,
freeze-frame desaturation, day/night cross-fade (night = a separate painted variant `<id>_night.png` when present,
else a code grade). A missing background becomes a dark placeholder card naming the id."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PAD = 80                        # extra columns each side (room for the motion blur kernel)


def _grade_night(a: np.ndarray) -> np.ndarray:
    lum = a.mean(-1, keepdims=True)
    land = (a * 0.17 + lum * 0.06) * np.array([0.55, 0.72, 1.2], dtype=np.float32)
    y = np.linspace(0, 1, a.shape[0], dtype=np.float32)[:, None, None]
    v = np.clip((0.33 - y) / 0.2, 0, 1) ** 1.5
    return (land * (1 - v) + np.array([2.5, 3.5, 8.0], dtype=np.float32) * v).astype(np.float32)


def _placeholder(name: str, size: tuple[int, int]) -> Image.Image:
    from ..pipeline.episode import FONTS
    w, h = size
    img = Image.new("RGB", (w, h), (24, 30, 44))
    d = ImageDraw.Draw(img)
    d.rectangle([0, int(h * 0.86), w, h], fill=(40, 46, 60))
    f = ImageFont.truetype(str(FONTS / "Inter-Bold.ttf"), max(28, w // 40))
    d.text((w / 2, h * 0.45), f"BACKGROUND: {name}", font=f, fill=(150, 160, 180), anchor="mm")
    return img


class Backdrop:
    def __init__(self, folder: Path, name: str, size: tuple[int, int], tiles: int = 6,
                 parallax: float | None = None):
        """parallax=y_split (fraction of the height): the far layer above it stays still while the ground band
        below scrolls with the camera (long, fast travel); None = the whole picture moves together."""
        self.size = size
        self.parallax = parallax
        w, h = size
        p = folder / f"{name}.png"
        img = Image.open(p).convert("RGB") if p.is_file() else _placeholder(name, (int(h * 16 / 9), h))
        img = img.resize((max(w, round(img.width * h / img.height)), h), Image.Resampling.LANCZOS)
        night_p = folder / f"{name}_night.png"
        nimg = (Image.open(night_p).convert("RGB").resize(img.size, Image.Resampling.LANCZOS)
                if night_p.is_file() else None)
        self.day = self._strip(img, tiles)                       # uint8: ~4x less memory per worker
        self.night = (self._strip(nimg, tiles) if nimg is not None
                      else np.clip(_grade_night(self.day.astype(np.float32)), 0, 255).astype(np.uint8))
        self.tile_w = img.width
        self.width = self.day.shape[1]
        # the strip repeats every 2 tiles (picture + mirror); wrap only by whole periods so it never jumps
        period = 2 * self.tile_w
        self.span = period * max(1, (self.width - w - 2 * PAD - 1) // period)

    @staticmethod
    def _strip(img: Image.Image, tiles: int) -> np.ndarray:
        parts = [img if k % 2 == 0 else img.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for k in range(tiles)]
        return np.concatenate([np.asarray(p) for p in parts], axis=1)

    def _window(self, x0f: float, night: float) -> np.ndarray:
        """Columns [x0f - PAD, x0f + w + PAD) of the strip, sub-pixel (linear between neighbouring columns), so
        slow pans glide instead of stepping a whole pixel at a time."""
        w = self.size[0]
        xi = math.floor(x0f)
        fr = x0f - xi

        def cols(arr: np.ndarray) -> np.ndarray:
            a = arr[:, xi - PAD:xi + w + PAD + 1].astype(np.float32)
            return a[:, :-1] * (1 - fr) + a[:, 1:] * fr if fr > 1e-3 else a[:, :-1]
        a = cols(self.day)
        if night > 0:
            b = cols(self.night)
            a = b if night >= 1 else a * (1 - night) + b * night
        return a

    @staticmethod
    def _blur(a: np.ndarray, k: int, w: int) -> np.ndarray:
        """Horizontal box blur of width k centred on each pixel (a centred kernel does not shift the picture
        when the blur grows or shrinks with speed); returns the w visible columns."""
        if k <= 1:
            return a[:, PAD:PAD + w]
        c = np.concatenate([np.zeros_like(a[:, :1]), np.cumsum(a, axis=1)], axis=1)
        lo = PAD - k // 2
        return (c[:, lo + k:lo + k + w] - c[:, lo:lo + w]) / k

    def frame(self, cam_x: float, night: float = 0.0, blur_px: float = 0.0, desat: float = 0.0) -> np.ndarray:
        """Window of the strip starting at cam_x (screen x 0 = cam_x), as float32 HxWx3."""
        w, h = self.size
        home = (self.tile_w - w) / 2 + PAD
        k = min(2 * PAD - 2, round(blur_px))
        a = self._blur(self._window((cam_x + home - PAD) % self.span + PAD, night), k, w)
        if self.parallax is not None and cam_x != 0:
            # two layers: far rows (above y_split) stay put, the ground band below scrolls with the camera
            y_split = int(h * self.parallax)
            far = self._window(home, night)[:, PAD:PAD + w]
            m = np.clip((np.arange(h, dtype=np.float32) - y_split) / 28.0 + 0.5, 0, 1)[:, None, None]
            a = far * (1 - m) + a * m
        if desat > 0:
            g = a.mean(-1, keepdims=True)
            a = (a * (1 - 0.8 * desat) + g * 0.8 * desat) * (1 - 0.42 * desat)
        return a


class TallBackdrop:
    """A tall painting for vertical camera travel (falls, wall runs): fitted to the frame width, bottom edge =
    street level at camera offset 0; the camera looks `off_y` background pixels higher. Vertical motion blur is a
    centred box like the horizontal one."""

    def __init__(self, folder: Path, name: str, size: tuple[int, int]):
        w, h = size
        p = folder / f"{name}.png"
        if p.is_file():
            img = Image.open(p).convert("RGB")
        else:
            img = _placeholder(name, (w, h * 3))
            g = np.linspace(0, 1, h * 3, dtype=np.float32)[:, None, None]
            img = Image.fromarray((np.asarray(img, dtype=np.float32) * (0.55 + 0.45 * g)).astype(np.uint8))
        img = img.resize((w, max(h, round(img.height * w / img.width))), Image.Resampling.LANCZOS)
        self.size = size
        self.day = np.asarray(img)
        self.height = self.day.shape[0]

    def frame(self, off_y: float, night: float = 0.0, blur_px: float = 0.0, desat: float = 0.0) -> np.ndarray:
        w, h = self.size
        y0f = min(max(self.height - h - off_y, 0.0), self.height - h)
        k = min(2 * PAD - 2, round(blur_px))
        lo = max(0, math.floor(y0f) - PAD)
        hi = min(self.height, math.floor(y0f) + h + PAD + 1)
        a = self.day[lo:hi].astype(np.float32)
        yi = math.floor(y0f)
        a = np.pad(a, ((PAD - (yi - lo), yi + h + PAD + 1 - hi), (0, 0), (0, 0)), mode="edge")
        fr = y0f - math.floor(y0f)
        a = a[:-1] * (1 - fr) + a[1:] * fr if fr > 1e-3 else a[:-1]
        if k > 1:
            c = np.concatenate([np.zeros_like(a[:1]), np.cumsum(a, axis=0)], axis=0)
            q = PAD - k // 2
            a = (c[q + k:q + k + h] - c[q:q + h]) / k
        else:
            a = a[PAD:PAD + h]
        if night > 0:
            a = a * (1 - night) + _grade_night(a) * night
        if desat > 0:
            g = a.mean(-1, keepdims=True)
            a = (a * (1 - 0.8 * desat) + g * 0.8 * desat) * (1 - 0.42 * desat)
        return a


@lru_cache(maxsize=4)
def load_tall(folder: str, name: str, size: tuple[int, int]) -> TallBackdrop:
    return TallBackdrop(Path(folder), name, size)


@lru_cache(maxsize=16)
def load(folder: str, name: str, size: tuple[int, int],
         parallax: float | None = None) -> Backdrop:
    return Backdrop(Path(folder), name, size, parallax=parallax)
