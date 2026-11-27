"""The Rift — ink_mindset pilot. One stacked split comic (0-30 s): each half plays the Blender video plates of four
metaphors back to back (hard cuts with a quick ink bleed). Every payoff sits on the Head Bang cut: drop 5.03 s,
beat 0.617 s, section two 17.99 s, strong hits 19.84 / 24.15 / 26.62 s."""

from __future__ import annotations

from studio.whatif import ink
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 1200, 1066
LY, LS = 122, 84
BEAT = 0.617
# metaphor: start, top label, bottom label, payoff (underline), plate prefix
M = [(0.0, "WAIT FOR A DOOR", "MAKE ONE", 5.03, "wall"),
     (7.50, "DOUBT", "JUMP", 9.97, "gap"),
     (12.43, "STAY DOWN", "HIT BACK", 16.13, "fist"),
     (17.99, "TURN BACK", "ONE MORE", 24.15, "race")]
# hits per half: (time, strength) — camera punch-in (no speed ramps or inverted frames: on a 30 fps plate
# they read as lag)
HITS = {"top": [(14.28, 1.0)], "bottom": [(5.03, 1.0), (9.97, 0.6), (14.28, 0.7), (16.13, 1.0), (24.15, 1.0)]}
END = 30.0
P = "r6"                                       # plate set: projects/ink_proto3d/render/rift6 (pose-to-pose animation)


def kv(fx_: float, fy: float, z: float = 1.0) -> tuple[float, float, float]:
    return fx_ * PW, fy * PH, PW / z


def build(size):
    a, b = Comic(shots=(1, 1), plate=f"@{P}_wall_top"), Comic(shots=(1, 1), plate=f"@{P}_wall_bottom")
    for t0, *_rest, name in M:
        a.clip(t0, f"{P}_{name}_top")
        b.clip(t0, f"{P}_{name}_bottom")
    for c, half in ((a, "top"), (b, "bottom")):
        for k, (t0, *_r, _name) in enumerate(M):
            t1 = M[k + 1][0] if k + 1 < len(M) else END
            base = lambda t, t0=t0, t1=t1: 1.01 + 0.06 * (t - t0) / (t1 - t0)            # noqa: E731
            keys = [(t0, base(t0), "hold")]
            for h, k_ in HITS[half]:
                if t0 + 0.7 < h < t1 - 0.4:
                    keys += [(h - 0.02, base(h - 0.02), "lin"), (h, base(h) + 0.16 * k_, "hold"),
                             (h + 0.4, base(h + 0.4), "ease")]
            keys.append((t1 - 0.01, base(t1 - 0.01), "lin"))
            for t, z, tw in keys:
                c.cam(t, *kv(0.5, 0.52, z), tw)
    # impacts
    b.shake(5.03, 0.3, 26)                    # the wall bursts on the drop
    b.shake(10.69, 0.2, 14)                   # he lands across the gap
    a.shake(14.28, 0.3, 24)                   # the shadow's punch lands
    b.shake(14.28, 0.3, 24)
    b.shake(16.13, 0.35, 30)                  # he hits back
    b.shake(24.15, 0.3, 24)                   # the ribbon
    b.shake(26.62, 0.25, 18)

    c = Comic(shots=(1, 1), plate=a.plate)
    c.split, c.stack = (a, b), True
    c.text(0.0, END, ink.seam(W, HH))
    for k, (t0, top, bottom, pay, _name) in enumerate(M):
        t1 = M[k + 1][0] if k + 1 < len(M) else END
        c.text(t0, t1, ink.slam(W / 2, LY, top, LS, delay=0.05))
        c.text(t0, t1, ink.slam(W / 2, HH + LY, bottom, LS, delay=0.05 + BEAT))
        hw = 0.24 * LS * len(bottom) + 24
        c.text(t0, t1, ink.stroke(W / 2 - hw, HH + LY + 24, W / 2 + hw, 14, delay=pay - t0, dur=0.22,
                                  seed=len(bottom)))
        c.sfx(t0 + 0.05, "sfx_brush", 0.5)
        c.sfx(t0 + 0.05 + BEAT, "sfx_brush", 0.45)
        if k:                                  # quick ink wipe between metaphors
            c.text(t0 - 0.3, t0, ink.bleed(W, H, 0.3, cover=True, seed=30 + k))
            c.text(t0, t0 + 0.3, ink.bleed(W, H, 0.3, cover=False, seed=40 + k))
            c.sfx(t0 - 0.3, "sfx_bleed", 0.35)
    c.text(16.13, 17.5, ink.splash(W * 0.78, HH + 300, 130, seed=7, color=ink.INK))       # the shadow bursts
    c.text(24.15, 25.4, ink.splash(W * 0.55, HH + 600, 160, seed=11, color=ink.VERMILION))  # the ribbon
    c.flash(26.62, 0.06)
    c.text(END - 0.6, END, ink.bleed(W, H, 0.6, cover=True, seed=59))                     # back to the start
    for t in (5.03, 14.28, 16.13, 24.15):
        c.sfx(t, "sfx_stamp", 0.6)
    c.music(0.0, "music_rift", 1.0, until=END)
    return [c]
