"""Clean 2D stick hero drawn over Blender frames (the look of classic animated stickmen).

    python -m studio.ink3d.stick2d <frames_dir>      (needs <frames_dir>/joints2d.json from kit.export_2d)

The first run moves Blender's frames to raw/ and composites over them. Delete raw/ before re-rendering into the
same folder, or the old backgrounds are reused.

Each limb chain is one polyline of constant width with round caps and joins: an ink stroke, then a slightly
narrower white stroke on top, so every limb has its own outline and limbs never melt together. Chains are drawn
far to near (camera depth); the near arm is drawn over the head. Frames are written in place (originals kept in raw/).
"""

import io
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import resvg_py
from PIL import Image

INK, WHITE = "#16140F", "#FBF7EE"
CHAINS = {"legL": ["hipL", "kneeL", "ankleL", "toeL"], "legR": ["hipR", "kneeR", "ankleR", "toeR"],
          "armL": ["shL", "elbL", "wristL"], "armR": ["shR", "elbR", "wristR"],
          "body": ["pelvis", "chest", "neck"]}


# arms crossed over the face (running through a wall): the X's end points relative to the head centre, in head
# radii (x forward, y up), measured off the reference frame. "/" = the near arm, "\\" = the far forearm.
X_NEAR = ((-0.57, -0.85), (0.97, 0.17))
X_FAR = ((-0.74, 0.17), (0.80, -0.97))      # far forearm: hand (back, up) ... elbow (front, low)


def cover_arms(d: dict, w: float) -> dict:
    """Blend the arm joints towards the X over the face by weight w (0..1)."""
    if w <= 0:
        return d
    r = d["head_r"]
    hx, hy = d["head"][0], d["head"][1]
    fwd = 1.0 if (d["toeL"][0] - d["ankleL"][0]) + (d["toeR"][0] - d["ankleR"][0]) >= 0 else -1.0

    def pt(p):
        return [hx + fwd * p[0] * r, hy - p[1] * r]
    near = "R" if d["shR"][2] <= d["shL"][2] else "L"
    far = "L" if near == "R" else "R"
    p2 = pt(X_NEAR[1])                                   # the near arm: one straight line from the shoulder
    sh = d["sh" + near]
    tgt = {"elb" + near: [(sh[0] + p2[0]) / 2, (sh[1] + p2[1]) / 2], "wrist" + near: p2,
           "elb" + far: pt(X_FAR[1]), "wrist" + far: pt(X_FAR[0])}   # elbow front-low, hand up at the back
    out = dict(d)
    for j, (tx, ty) in tgt.items():
        x, y, z = d[j]
        out[j] = [x + (tx - x) * w, y + (ty - y) * w, z]
    return out


def svg(d: dict, w: int, h: int, near: str = "R", fill: str = WHITE, line: str = INK, wrap: bool = True,
        cover: float = 0.0) -> str:
    """Fixed layer order (no per-frame depth sort: near-equal depths flipped torso/arm every few frames):
    far arm, far leg, torso, near leg, near arm, head."""
    d = cover_arms(d, cover)
    r = d["head_r"]
    limb, torso, ol = 0.40 * r, 0.62 * r, max(3.0, 0.11 * r)
    far = "L" if near == "R" else "R"
    # the near arm goes over the head: in profile the near shoulder is the front-most part of the upper body
    order = [f"arm{far}", f"leg{far}", "body", f"leg{near}", "head", f"arm{near}"]
    if cover > 0.3:
        # arms crossed in front of the face: the far upper arm runs across the chest under the head, its forearm
        # rises back across the face; the near arm is one straight line over both
        order = [f"leg{far}", "body", f"leg{near}", f"upper{far}", "head", f"fore{far}", f"arm{near}"]
    body = []
    for name in order:
        if name == "head":
            hx, hy, _ = d["head"]
            body.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{line}" '
                        f'stroke-width="{ol * 1.6:.1f}"/>')
            continue
        if name.startswith(("upper", "fore")):
            sd = name[-1]
            pts = [d[f"sh{sd}"], d[f"elb{sd}"]] if name.startswith("upper") else [d[f"elb{sd}"], d[f"wrist{sd}"]]
            dd = "M" + " L".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
            body.append(f'<path d="{dd}" fill="none" stroke="{line}" stroke-width="{limb + 2 * ol:.1f}" '
                        f'stroke-linecap="round" stroke-linejoin="round"/>')
            body.append(f'<path d="{dd}" fill="none" stroke="{fill}" stroke-width="{limb:.1f}" '
                        f'stroke-linecap="round" stroke-linejoin="round"/>')
            continue
        js = CHAINS[name]
        pts = [d[j] for j in js]
        if name.startswith("leg"):                      # legs hang from the hip points: in profile these sit on
            pts = [d[f"hip{name[-1]}"]] + pts[1:]       # the pelvis, in a front view they spread the legs apart
        if name.startswith("arm"):                      # arms start at the shoulder, just under the head
            pts = [d[f"sh{name[-1]}"]] + pts[1:]
        width = torso if name == "body" else limb
        dd = "M" + " L".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
        body.append(f'<path d="{dd}" fill="none" stroke="{line}" stroke-width="{width + 2 * ol:.1f}" '
                    f'stroke-linecap="round" stroke-linejoin="round"/>')
        body.append(f'<path d="{dd}" fill="none" stroke="{fill}" stroke-width="{width:.1f}" '
                    f'stroke-linecap="round" stroke-linejoin="round"/>')
    inner = "".join(body)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{inner}</svg>' if wrap else inner


def near_sides(joints: list, window: int = 15, margin: float = 0.02) -> list[str]:
    """Which side faces the camera, per frame: smoothed depth difference of the left/right shoulders and hips,
    with hysteresis, so the layer order only changes when he really turns."""
    diff = [(f["shL"][2] + f["hipL"][2]) - (f["shR"][2] + f["hipR"][2]) for f in joints]
    side, out = ("L" if sum(diff) < 0 else "R"), []
    for i in range(len(diff)):
        win = diff[max(0, i - window): i + window + 1]
        m = sum(win) / len(win)
        if m < -margin:
            side = "L"
        elif m > margin:
            side = "R"
        out.append(side)
    return out


STYLES = {"hero": (WHITE, INK), "shadow": ("#16140F", "#EDE6D6")}       # fill, outline


def shadow_svg(d: dict, sh: list) -> str:
    """A soft ink contact shadow on the ground under a figure: as wide as the parts touching the ground, fading
    out as the figure leaves the ground (sh = [ground x px, ground y px, lowest foot height m])."""
    gx, gy, hm = sh
    r = d["head_r"]
    near = [v[0] for k, v in d.items() if isinstance(v, list) and abs(v[1] - gy) < 1.6 * r]
    xs = near or [d[j][0] for j in ("ankleL", "ankleR", "toeL", "toeR")]
    cx = (min(xs) + max(xs)) / 2 if near else gx
    rx = (max(xs) - min(xs)) / 2 + 0.9 * r
    op = 0.32 * max(0.0, 1.0 - hm / 1.1)
    if op <= 0.01:
        return ""
    return (f'<ellipse cx="{cx:.1f}" cy="{gy + 0.05 * r:.1f}" rx="{rx:.1f}" ry="{0.2 * r:.1f}" fill="#16140F" '
            f'opacity="{op:.2f}" filter="url(#soft)"/>')


def frame_svg(figs: dict, i: int, w: int, h: int, sides: dict, front: list | None = None,
              shadow: dict | None = None, cover: dict | None = None) -> str:
    """All figures of frame i (contact shadows first, shadows behind, the hero on top), then foreground props in
    front of them (front[i]: polygons projected from Blender objects between the camera and the figures)."""
    parts = ['<defs><filter id="soft" x="-50%" y="-200%" width="200%" height="500%">'
             '<feGaussianBlur stdDeviation="6"/></filter></defs>']
    for name in figs:
        d = figs[name][i] if i < len(figs[name]) else None
        sh = (shadow or {}).get(name)
        if d is not None and sh and i < len(sh) and sh[i]:
            parts.append(shadow_svg(d, sh[i]))
    for name in sorted(figs, key=lambda n: n == "hero"):
        d = figs[name][i] if i < len(figs[name]) else None
        if d is None:
            continue
        fill, line = STYLES.get(name.split("_")[0], STYLES["hero"])
        cw = (cover or {}).get(name)
        parts.append(svg(d, w, h, sides[name][i], fill, line, wrap=False,
                         cover=cw[i] if cw and i < len(cw) else 0.0))
    for poly in (front[i] if front and i < len(front) else []):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly["pts"])
        parts.append(f'<polygon points="{pts}" fill="{poly["fill"]}"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{"".join(parts)}</svg>'


def _one(args):
    f, figs, i, w, h, sides, front, shadow, cover = args
    raw = f.parent / "raw" / f.name
    if not raw.exists():
        f.replace(raw)
    bg = Image.open(raw).convert("RGBA")
    fg = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=frame_svg(figs, i, w, h, sides, front, shadow, cover))))).convert("RGBA")
    bg.alpha_composite(fg)
    bg.convert("RGB").save(f)


def main(d: Path) -> None:
    data = json.loads((d / "joints2d.json").read_text(encoding="utf-8"))
    figs = data["figures"] if isinstance(data, dict) else {"hero": data}
    (d / "raw").mkdir(exist_ok=True)
    first = sorted([*d.glob("[0-9][0-9][0-9][0-9].png"), *(d / "raw").glob("*.png")])[0]
    w, h = Image.open(first).size
    sides = {}
    for name, fr in figs.items():
        seen = [x for x in fr if x is not None]
        s = near_sides(seen) if seen else []
        it = iter(s)
        sides[name] = [next(it) if x is not None else "R" for x in fr]
    n = max(len(v) for v in figs.values())
    front = data.get("front") if isinstance(data, dict) else None
    shadow = data.get("shadow") if isinstance(data, dict) else None
    cover = data.get("cover") if isinstance(data, dict) else None
    jobs = [(d / f"{i + 1:04d}.png", figs, i, w, h, sides, front, shadow, cover) for i in range(n)
            if (d / f"{i + 1:04d}.png").exists() or (d / "raw" / f"{i + 1:04d}.png").exists()]
    with ProcessPoolExecutor(4) as ex:
        list(ex.map(_one, jobs, chunksize=8))
    print(len(jobs), "frames drawn")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
