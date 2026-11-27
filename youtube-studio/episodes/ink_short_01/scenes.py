"""ink_mindset pilot Short: three choices side by side in sumi-e ink — wordless, music-led, stacked split screen.

Top half = the comfortable way, bottom half = the way that grows. Each metaphor is 11 s: whole Higgsfield keyframes
(Nano Banana 2, 2400x1792) with slow camera drift, cuts to close-ups every ~2.5-3 s, brush-written labels and an
ink-bleed transition into the next metaphor. The end card blooms vermilion, stamps the seal and soaks back into the
opening picture (loop). Overlays: studio/whatif/ink.py. Keyframes: projects/ink_short_01/art/kf_*.png.
"""

from __future__ import annotations

from studio.whatif import ink
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 2400, 1792
FULL = PH * W / HH                                # camera width that shows the keyframe's full height
SPAN = 11.0
LY = 122                                          # label baseline inside each half (top ~16 % band)
LS = 84                                           # label size


def kc(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    """Camera on a keyframe: centre at fractions of the picture, zoom z (1 = full height)."""
    return fx_ * PW, fy * PH, FULL / z


def cut(c: Comic, t: float, plate: str, cam) -> None:
    c.cut(t, plate)
    c.cam(t, *cam, "hold")


def parent(shots, top: Comic, bottom: Comic) -> Comic:
    c = Comic(shots=shots, plate=top.plate)
    c.split = (top, bottom)
    c.stack = True
    return c


def dressing(c: Comic, top: str, bottom: str, open_bleed: bool = True, labels_at: float = 0.0) -> None:
    """Shared screen layer of a metaphor: seam brush stroke, two brush labels, vermilion underline on the bottom
    (growing) label, ink bleed in at the start and out at the end."""
    c.text(0.0, SPAN, ink.seam(W, HH))
    c.text(0.0, SPAN, ink.label(W / 2, LY, top, LS, delay=labels_at))
    c.text(0.0, SPAN, ink.label(W / 2, HH + LY, bottom, LS, delay=labels_at + 0.25))
    half_w = 0.24 * LS * len(bottom) + 24
    c.text(0.0, SPAN, ink.stroke(W / 2 - half_w, HH + LY + 24, W / 2 + half_w, 14, delay=6.0, dur=0.45,
                                 seed=len(bottom)))
    if open_bleed:
        c.text(0.0, 0.6, ink.bleed(W, H, 0.55, cover=False, seed=31))
    c.text(SPAN - 0.55, SPAN, ink.bleed(W, H, 0.55, cover=True, seed=37))


# ---------------------------------------------------------------- 1: the armchair vs the lantern

def comfort_growth(open_bleed: bool = False) -> Comic:
    a, b = Comic(shots=(1, 1), plate="kf_m1_chair"), Comic(shots=(1, 1), plate="kf_m1_lantern")
    # top — COMFORT: the phone glow, then the same chair much later (cobwebs, cups)
    a.cam(0.0, *kc(0.47, 0.58, 1.05))
    a.cam(2.75, *kc(0.47, 0.58, 1.3), "ease")
    cut(a, 2.8, "kf_m1_chair", kc(0.5, 0.64, 2.3))          # close: the face lit by the phone
    a.cam(5.45, *kc(0.5, 0.64, 2.45))
    cut(a, 5.5, "kf_m1_chair_late", kc(0.47, 0.6, 1.1))      # later: dust, cobwebs, a tower of cups
    a.cam(8.15, *kc(0.47, 0.6, 1.25))
    cut(a, 8.2, "kf_m1_chair_late", kc(0.45, 0.65, 1.9))     # close: the cups and the cobwebs
    a.cam(SPAN, *kc(0.45, 0.65, 2.05))
    # bottom — GROWTH: walking into the dark with a lantern, then dawn on the summit
    b.cam(0.0, *kc(0.45, 0.62, 1.05))
    b.cam(2.75, *kc(0.5, 0.65, 1.25), "lin")
    cut(b, 2.8, "kf_m1_lantern", kc(0.55, 0.73, 2.2))         # close: hero and lantern
    b.cam(5.45, *kc(0.58, 0.73, 2.35), "lin")
    cut(b, 5.5, "kf_m1_summit_v2", kc(0.5, 0.55, 1.05))      # the summit at dawn
    b.cam(8.15, *kc(0.52, 0.53, 1.2))
    cut(b, 8.2, "kf_m1_summit_v2", kc(0.6, 0.54, 1.8))       # close: hero and the rising sun
    b.cam(SPAN, *kc(0.6, 0.55, 1.95))

    c = parent((1, 1), a, b)
    dressing(c, "COMFORT", "GROWTH", open_bleed=open_bleed)
    c.sfx(0.0, "sfx_brush", 0.5)
    c.sfx(0.25, "sfx_brush", 0.4)
    c.sfx(6.0, "sfx_brush", 0.45)
    c.sfx(SPAN - 0.6, "sfx_bleed", 0.5)
    c.music(0.0, "music_ink", 0.75, until=3 * SPAN + 3.0)
    return c


# ---------------------------------------------------------------- 2: waiting vs planting

def waiting_planting() -> Comic:
    a, b = Comic(shots=(2, 2), plate="kf_m2_wait"), Comic(shots=(2, 2), plate="kf_m2_plant")
    # top — WAITING under a bare tree, then the snow
    a.cam(0.0, *kc(0.46, 0.55, 1.05))
    a.cam(2.75, *kc(0.46, 0.5, 1.2))
    cut(a, 2.8, "kf_m2_wait", kc(0.48, 0.7, 2.2))           # close: hugging his knees, looking up
    a.cam(5.45, *kc(0.48, 0.7, 2.35))
    cut(a, 5.5, "kf_m2_wait_late", kc(0.52, 0.62, 1.1))      # months later: snow
    a.cam(8.15, *kc(0.52, 0.64, 1.25))
    cut(a, 8.2, "kf_m2_wait_late", kc(0.56, 0.7, 2.3))      # close: half buried, still waiting
    a.cam(SPAN, *kc(0.56, 0.7, 2.45))
    # bottom — PLANTING a seed a day, then the shade of his own tree
    b.cam(0.0, *kc(0.45, 0.6, 1.05))
    b.cam(2.75, *kc(0.47, 0.62, 1.2))
    cut(b, 2.8, "kf_m2_plant", kc(0.5, 0.72, 2.3))           # close: the vermilion seed going in
    b.cam(5.45, *kc(0.58, 0.72, 2.45), "lin")                # drift along the row of sprouts
    cut(b, 5.5, "kf_m2_tree", kc(0.55, 0.52, 1.05))          # later: the grown tree with vermilion fruit
    b.cam(8.15, *kc(0.57, 0.55, 1.2))
    cut(b, 8.2, "kf_m2_tree", kc(0.64, 0.76, 2.1))             # close: resting in his own shade
    b.cam(SPAN, *kc(0.64, 0.77, 2.25))

    c = parent((2, 2), a, b)
    dressing(c, "WAITING", "PLANTING")
    c.sfx(0.05, "sfx_brush", 0.5)
    c.sfx(0.3, "sfx_brush", 0.4)
    c.sfx(6.0, "sfx_brush", 0.45)
    c.sfx(SPAN - 0.6, "sfx_bleed", 0.5)
    return c


# ---------------------------------------------------------------- 3: one perfect circle vs one hundred

def perfect_hundred() -> Comic:
    a, b = Comic(shots=(3, 3), plate="kf_m3_blank"), Comic(shots=(3, 3), plate="kf_m3_many")
    # top — ONE PERFECT: the brush hangs over a blank sheet; hours later the candle is a stub
    a.cam(0.0, *kc(0.5, 0.55, 1.05))
    a.cam(2.75, *kc(0.5, 0.55, 1.2))
    cut(a, 2.8, "kf_m3_blank", kc(0.5, 0.47, 2.2))          # close: the dry brush and the empty page
    a.cam(5.45, *kc(0.5, 0.47, 2.35))
    cut(a, 5.5, "kf_m3_blank_late", kc(0.52, 0.58, 1.1))     # hours later
    a.cam(8.15, *kc(0.55, 0.62, 1.25))
    cut(a, 8.2, "kf_m3_blank_late", kc(0.6, 0.68, 1.7))     # close: the candle stub, the page still blank
    a.cam(SPAN, *kc(0.6, 0.68, 1.85))
    # bottom — ONE HUNDRED: rough circles everywhere, then the one beautiful circle
    b.cam(0.0, *kc(0.5, 0.58, 1.05))
    b.cam(2.75, *kc(0.5, 0.6, 1.2))
    cut(b, 2.8, "kf_m3_many", kc(0.53, 0.53, 1.6))           # close: another circle, brush moving
    b.cam(5.45, *kc(0.53, 0.54, 1.75))
    cut(b, 5.5, "kf_m3_enso", kc(0.52, 0.55, 1.05))          # the one beautiful circle
    b.cam(8.15, *kc(0.54, 0.52, 1.2))
    cut(b, 8.2, "kf_m3_enso", kc(0.56, 0.39, 2.0))           # close: the circle with its vermilion dot
    b.cam(SPAN, *kc(0.56, 0.39, 2.15))

    c = parent((3, 3), a, b)
    dressing(c, "ONE PERFECT", "ONE HUNDRED")
    c.sfx(0.05, "sfx_brush", 0.5)
    c.sfx(0.3, "sfx_brush", 0.4)
    c.sfx(6.0, "sfx_brush", 0.45)
    c.sfx(SPAN - 0.6, "sfx_bleed", 0.5)
    return c


# ---------------------------------------------------------------- end: vermilion bloom, seal, back to the start

def end_card() -> Comic:
    a, b = Comic(shots=(4, 4), plate="kf_m1_chair"), Comic(shots=(4, 4), plate="kf_m1_lantern")
    a.cam(0.0, *kc(0.47, 0.58, 1.05))                        # = the opening framing (loop)
    b.cam(0.0, *kc(0.45, 0.62, 1.05))
    c = parent((4, 4), a, b)
    c.text(0.0, c.end(), ink.seam(W, HH))

    def card(u, _t):                                          # paper card from 0 to 2.3 s, then it soaks away
        if u >= 2.3:
            return ""
        return f'<rect width="{W}" height="{H}" fill="{ink.PAPER}"/>'
    c.text(0.0, c.end(), card)
    c.text(0.0, 2.3, ink.bleed(W, H, 0.5, cover=False, seed=41))             # the ink of the last cut soaks away
    c.text(0.35, 2.3, ink.label(W / 2, 900, "BEGIN.", 190, dur=0.6))
    c.text(0.35, 2.3, ink.stroke(W / 2 - 230, 960, W / 2 + 230, 22, delay=0.7, dur=0.4, seed=5))
    c.text(0.35, 2.3, ink.seal(W / 2, 1180, 150, delay=1.1))
    c.text(2.3, c.end(), ink.bleed(W, H, 0.5, cover=False, color=ink.PAPER, seed=43))
    c.text(2.3, c.end(), ink.label(W / 2, LY, "COMFORT", LS, delay=0.3))
    c.text(2.3, c.end(), ink.label(W / 2, HH + LY, "GROWTH", LS, delay=0.55))
    c.sfx(0.4, "sfx_brush", 0.5)
    c.sfx(1.45, "sfx_stamp", 0.6)
    return c


def build(size):
    return [comfort_growth(), waiting_planting(), perfect_hundred(), end_card()]
