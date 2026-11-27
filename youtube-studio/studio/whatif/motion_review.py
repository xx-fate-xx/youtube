"""Motion review: for every moving key segment of every cast member, a 3-frame strip (start / middle / end), so
the pose can be checked against the direction of travel (falls head-first and vertical, fire tails behind the
fireball, no jumps between segments, nothing leaving the frame). Look at every sheet before a full render.

    python -m studio.whatif.motion_review episodes/<slug> projects/<slug>/review/motion.jpg
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from ..pipeline import episode as em
from . import comic, render

src_ep, out = sys.argv[1], Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
em.use(src_ep)
size = em.ep().size
durs, _ = render.durations(False)
rows = []
t0 = 0.0
for s in render.plan(size):
    if not isinstance(s, comic.Comic):
        continue
    s.art = render.library("art")
    n = s.layout(durs)
    parts = [("", s)] + [(f"[{'LR'[k]}] ", sub) for k, sub in enumerate(s.split or ())]
    for tag, name, cast in [(tg, nm, ca) for tg, sub in parts for nm, ca in sub.casts.items()]:
        ks = cast.keys
        name = tag + name
        for a, b in zip(ks, ks[1:], strict=False):
            if b.tween == "hold" or a.sprite is None or b.sprite is None:
                continue
            ta, tb = s.T(a.t), s.T(b.t)
            if tb - ta < 0.15 or (abs(b.x - a.x) + abs(b.y - a.y)) < 60:
                continue
            strip = []
            for f in (0.15, 0.5, 0.92):
                t = ta + (tb - ta) * f
                im = comic.frame(s, int(round(t * comic.FPS)), size)
                im = im.resize((320, 180) if im.width > im.height else (180, 320))
                strip.append(im)
            cw, chh = strip[0].width + 2, strip[0].height + 2
            row = Image.new("RGB", (3 * cw + 360, chh), (25, 25, 25))
            for k, im in enumerate(strip):
                row.paste(im, (360 + k * cw, 1))
            d = ImageDraw.Draw(row)
            d.text((6, 6), f"{t0 + ta:6.1f}-{t0 + tb:6.1f}s", fill=(255, 255, 0))
            d.text((6, 30), f"{name}: {a.sprite}->{b.sprite}", fill=(255, 255, 255))
            d.text((6, 54), f"({a.x:.0f},{a.y:.0f})->({b.x:.0f},{b.y:.0f})", fill=(200, 200, 200))
            d.text((6, 78), f"ang {a.ang:.0f}->{b.ang:.0f} {b.tween}", fill=(200, 200, 200))
            rows.append(row)
    t0 += n
per = 14
for p in range(0, len(rows), per):
    chunk = rows[p:p + per]
    rh = chunk[0].height + 2
    sheet = Image.new("RGB", (max(r.width for r in chunk), rh * len(chunk)), (10, 10, 10))
    for k, r in enumerate(chunk):
        sheet.paste(r, (0, k * rh))
    o = out.with_name(f"{out.stem}_{p // per + 1}{out.suffix}")
    sheet.save(o, quality=82)
    print(o)
print(len(rows), "moving segments")
