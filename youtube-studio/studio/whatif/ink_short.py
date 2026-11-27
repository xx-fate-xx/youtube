"""Ink Mindset skit Shorts: 3-5 A|B skits back to back in one stacked split comic (top = the weak choice, bottom =
the strong one). Each skit's two halves are video plates rendered by studio/ink3d/stage2d (60 fps); labels slam in
on the first frame, the payoff lands on a strong beat with a camera punch-in, a shake and a stamp; skits are joined
by a quick ink bleed. Used by episodes/<slug>/scenes.py:

    from studio.whatif.ink_short import Skit, build
    def build_scenes(size): return build(SKITS, prefix="s2", music="music_waka", end=29.6)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from studio.whatif import ink
from studio.whatif.comic import Comic

W, H, HH = 1080, 1920, 960
PW, PH = 1200, 1066
LY, LS = 122, 84


@dataclass
class Skit:
    t0: float                 # start in the Short (s)
    top: str                  # top label (the weak choice)
    bottom: str               # bottom label (the strong choice)
    pay: float                # payoff time in the Short (s), on a strong beat
    name: str                 # plate name: <prefix>_<name>_<top|bottom>
    top_hit: float | None = None              # a hit in the top half too (time in the Short)
    extra: list = field(default_factory=list)  # [(t0, t1, svg)] more text (counters...)


def _kv(z: float) -> tuple[float, float, float]:
    return 0.5 * PW, 0.52 * PH, PW / z


def build(skits: list[Skit], prefix: str, music: str, end: float, music_vol: float = 1.0):
    a = Comic(shots=(1, 1), plate=f"@{prefix}_{skits[0].name}_top")
    b = Comic(shots=(1, 1), plate=f"@{prefix}_{skits[0].name}_bottom")
    for s in skits:
        a.clip(s.t0, f"{prefix}_{s.name}_top")
        b.clip(s.t0, f"{prefix}_{s.name}_bottom")
    for c, half in ((a, "top"), (b, "bottom")):
        for k, s in enumerate(skits):
            t1 = skits[k + 1].t0 if k + 1 < len(skits) else end

            def base(t, t0=s.t0, t1=t1):
                return 1.01 + 0.05 * (t - t0) / (t1 - t0)          # a slow push-in through the skit
            keys = [(s.t0, base(s.t0), "hold")]
            hit = s.pay if half == "bottom" else s.top_hit
            if hit is not None and s.t0 + 0.5 < hit < t1 - 0.3:
                keys += [(hit - 0.02, base(hit - 0.02), "lin"), (hit, base(hit) + 0.14, "hold"),
                         (hit + 0.45, base(hit + 0.45), "ease")]
                c.shake(hit, 0.3, 22)
            keys.append((t1 - 0.01, base(t1 - 0.01), "lin"))
            for t, z, tw in keys:
                c.cam(t, *_kv(z), tw)
    c = Comic(shots=(1, 1), plate=a.plate)
    c.split, c.stack = (a, b), True
    c.text(0.0, end, ink.seam(W, HH))
    for k, s in enumerate(skits):
        t1 = skits[k + 1].t0 if k + 1 < len(skits) else end
        c.text(s.t0, t1, ink.slam(W / 2, LY, s.top, LS, delay=0.02))                # both labels from the start
        c.text(s.t0, t1, ink.slam(W / 2, HH + LY, s.bottom, LS, delay=0.14))
        hw = 0.24 * LS * len(s.bottom) + 24
        c.text(s.t0, t1, ink.stroke(W / 2 - hw, HH + LY + 24, W / 2 + hw, 14, delay=s.pay - s.t0, dur=0.22,
                                    seed=len(s.bottom)))
        c.sfx(s.t0 + 0.02, "sfx_brush", 0.45)
        c.sfx(s.pay, "sfx_stamp", 0.6)
        if s.top_hit is not None:
            c.sfx(s.top_hit, "sfx_stamp", 0.4)
        if k:
            c.text(s.t0 - 0.25, s.t0, ink.bleed(W, H, 0.25, cover=True, seed=30 + k))
            c.text(s.t0, s.t0 + 0.25, ink.bleed(W, H, 0.25, cover=False, seed=40 + k))
            c.sfx(s.t0 - 0.25, "sfx_bleed", 0.3)
        for e0, e1, svg in s.extra:
            c.text(e0, e1, svg)
    c.text(end - 0.5, end, ink.bleed(W, H, 0.5, cover=True, seed=59))                 # loops back to the start
    c.music(0.0, music, music_vol, until=end)
    return [c]
