"""CMU ASF/AMC motion capture -> 2D side-view stickman joints.

Clip(asf, amc).joints2d(fps=30) gives per-frame dict of 2D points (x = along the body's forward axis,
y = up, both in body-heights, floor at y=0) plus a per-point depth so the far limbs can be drawn behind.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np


def rot(ax: str, deg: float) -> np.ndarray:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if ax == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if ax == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(x: float, y: float, z: float) -> np.ndarray:        # static xyz: R = Rz Ry Rx
    return rot("z", z) @ rot("y", y) @ rot("x", x)


class Skeleton:
    def __init__(self, asf: Path):
        self.bones: dict[str, dict] = {}
        self.children: dict[str, list[str]] = {"root": []}
        lines = [ln.strip() for ln in asf.read_text().splitlines()]
        i = 0
        while i < len(lines):
            ln = lines[i]
            if ln == "begin":
                b: dict = {"dof": []}
                i += 1
                while lines[i] != "end":
                    k, *v = lines[i].split()
                    if k == "name":
                        b["name"] = v[0]
                    elif k == "direction":
                        b["dir"] = np.array([float(x) for x in v])
                    elif k == "length":
                        b["len"] = float(v[0])
                    elif k == "axis":
                        b["axis"] = [float(x) for x in v[:3]]
                    elif k == "dof":
                        b["dof"] = [x.lower() for x in v]
                    i += 1
                c = euler(*b["axis"])
                b["C"], b["Ci"] = c, c.T
                self.bones[b["name"]] = b
            elif ln.startswith(":hierarchy"):
                i += 2                                  # skip 'begin'
                while lines[i] != "end":
                    p, *cs = lines[i].split()
                    self.children.setdefault(p, []).extend(cs)
                    i += 1
            i += 1

    def pose(self, frame: dict[str, list[float]]) -> dict[str, np.ndarray]:
        r = frame["root"]
        pos = {"root": np.array(r[:3])}
        mat = {"root": euler(*r[3:6])}

        def walk(parent: str) -> None:
            for c in self.children.get(parent, []):
                b = self.bones[c]
                ang = {"rx": 0.0, "ry": 0.0, "rz": 0.0}
                for d, v in zip(b["dof"], frame.get(c, []), strict=False):
                    ang[d] = v
                m = mat[parent] @ b["C"] @ euler(ang["rx"], ang["ry"], ang["rz"]) @ b["Ci"]
                mat[c] = m
                pos[c] = pos[parent] + b["len"] * (m @ b["dir"])
                walk(c)
        walk("root")
        return pos


def read_amc(amc: Path) -> list[dict[str, list[float]]]:
    frames, cur = [], None
    for ln in amc.read_text().splitlines():
        ln = ln.strip()
        if not ln or ln[0] in "#:":
            continue
        if ln.isdigit():
            cur = {}
            frames.append(cur)
            continue
        k, *v = ln.split()
        cur[k] = [float(x) for x in v]
    return frames


# joints used by the stickman (bone END positions)
JOINTS = {"pelvis": "root", "hipL": "lhipjoint", "hipR": "rhipjoint", "kneeL": "lfemur", "kneeR": "rfemur",
          "ankleL": "ltibia", "ankleR": "rtibia", "toeL": "lfoot", "toeR": "rfoot", "chest": "upperback",
          "neck": "lowerneck", "headbase": "upperneck", "headtop": "head", "shL": "lclavicle", "shR": "rclavicle",
          "elbL": "lhumerus", "elbR": "rhumerus", "wristL": "lradius", "wristR": "rradius"}


class Clip:
    def __init__(self, asf: Path, amc: Path, src_fps: int = 120):
        self.sk = Skeleton(asf)
        self.raw = read_amc(amc)
        self.src_fps = src_fps

    def joints3d(self, fps: int = 30) -> list[dict[str, np.ndarray]]:
        step = self.src_fps / fps
        out, k = [], 0.0
        while int(k) < len(self.raw):
            p = self.sk.pose(self.raw[int(k)])
            out.append({j: p[b] for j, b in JOINTS.items()})
            k += step
        return out

    def joints2d(self, fps: int = 30, facing: np.ndarray | None = None):
        f3 = self.joints3d(fps)
        # forward axis: perpendicular to the average hip line (left->right), horizontal
        lr = np.mean([f["hipL"] - f["hipR"] for f in f3], axis=0)
        lr[1] = 0
        lr /= np.linalg.norm(lr)
        fwd = np.cross(lr, np.array([0.0, 1.0, 0.0])) if facing is None else facing
        fwd = fwd / np.linalg.norm(fwd)
        # check sign against travel direction (walks); keep for stationary clips
        trav = f3[-1]["pelvis"] - f3[0]["pelvis"]
        trav[1] = 0
        if np.linalg.norm(trav) > 5 and np.dot(trav, fwd) < 0:
            fwd = -fwd
        floor = min(min(f["toeL"][1], f["toeR"][1], f["ankleL"][1], f["ankleR"][1]) for f in f3)
        h = np.mean([f["headtop"][1] for f in f3[:10]]) - floor
        origin = f3[0]["pelvis"]
        out = []
        for f in f3:
            d = {}
            for j, p in f.items():
                v = p - origin
                d[j] = (float(np.dot(v, fwd) / h), float((p[1] - floor) / h), float(np.dot(v, lr) / h))
            out.append(d)
        return out


# ---------------------------------------------------------------- clip library (cached CMU data)

import urllib.request  # noqa: E402
from functools import lru_cache  # noqa: E402

CACHE = Path(__file__).resolve().parents[2] / "projects" / "_assets" / "mocap"
CMU = "http://mocap.cs.cmu.edu/subjects"

# name -> (cmu clip id, start s, end s or None). Checked on contact sheets (MOCAP_CLIPS.md).
CLIPS: dict[str, tuple[str, float, float | None]] = {
    "walk": ("02_01", 0.0, None),
    "walk_b": ("16_33", 0.0, 1.9),
    "stand": ("16_33", 2.3, None),
    "run": ("09_01", 0.0, None),
    "surprised": ("120_15", 3.45, None),
    "scared": ("79_73", 0.5, None),
    "look_around": ("77_01", 0.0, None),
    "freezing": ("80_41", 0.0, None),
}


def fetch(cid: str) -> tuple[Path, Path]:
    """The .asf/.amc files of a CMU clip, downloaded into the cache when missing."""
    subj = cid.split("_")[0]
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for name in (f"{subj}.asf", f"{cid}.amc"):
        p = CACHE / name
        if not p.is_file():
            urllib.request.urlretrieve(f"{CMU}/{subj}/{name}", p)
        out.append(p)
    return out[0], out[1]


@lru_cache(maxsize=64)
def load_cmu(cid: str, fps: int = 30) -> tuple:
    """Whole clip as 2D frames, normalised to face +x (toes ahead of ankles)."""
    asf, amc = fetch(cid)
    fr = Clip(asf, amc).joints2d(fps)
    fwd = sum((f["toeL"][0] - f["ankleL"][0]) + (f["toeR"][0] - f["ankleR"][0]) for f in fr)
    if fwd < 0:
        fr = [{j: (-x, y, z) for j, (x, y, z) in f.items()} for f in fr]
    return tuple(fr)


# clips whose captured stance has bent knees (subject 16 ends 16_33 in a ~32 deg crouch): legs straightened to
# a relaxed standing knee angle so the figure doesn't look like it's squatting with its feet pushed forward
STRAIGHTEN = {"stand": 5.0}


def straighten(f: dict, flex_deg: float = 5.0) -> dict:
    """Same pose with the knees opened to `flex_deg`: feet stay where they are, hips and everything above rise,
    knees are re-solved (two-bone IK in the side view, knee bending forward)."""
    import math
    out = dict(f)
    dys, legs = [], {}
    for s in "LR":
        (hx, hy, _), (kx, ky, _), (ax, ay, _) = f["hip" + s], f["knee" + s], f["ankle" + s]
        lt, ls = math.hypot(hx - kx, hy - ky), math.hypot(kx - ax, ky - ay)
        d = math.sqrt(lt * lt + ls * ls + 2 * lt * ls * math.cos(math.radians(flex_deg)))
        dx = hx - ax
        dys.append(math.sqrt(max(d * d - dx * dx, 0.0)) - (hy - ay))
        legs[s] = (lt, ls)
    dy = max(0.0, sum(dys) / 2)                              # both legs near the target (one may end fully straight)
    leg = {"knee", "ankle", "toe"}
    for j, (x, y, z) in f.items():
        if not any(j.startswith(b) for b in leg):
            out[j] = (x, y + dy, z)
    for s in "LR":
        (hx, hy, _), (ax, ay, _) = out["hip" + s], f["ankle" + s]
        lt, ls = legs[s]
        dist = math.hypot(hx - ax, hy - ay)
        d = min(dist, lt + ls - 1e-6)                            # out of reach: leg fully straight
        a = (lt * lt - ls * ls + d * d) / (2 * d)
        hgt = math.sqrt(max(lt * lt - a * a, 0.0))
        ux, uy = (ax - hx) / dist, (ay - hy) / dist            # unit hip -> ankle
        mx, my = hx + ux * a, hy + uy * a
        k1, k2 = (mx - uy * hgt, my + ux * hgt), (mx + uy * hgt, my - ux * hgt)
        out["knee" + s] = (*max(k1, k2, key=lambda p: p[0]), f["knee" + s][2])   # knee bends forward (+x)
    return out


def clip(name: str, fps: int = 30) -> list[dict]:
    """A named library clip (segment of a CMU clip) as 2D frames."""
    cid, t0, t1 = CLIPS[name]
    fr = load_cmu(cid, fps)
    seg = list(fr[int(t0 * fps): int(t1 * fps) if t1 else None])
    if name in STRAIGHTEN:
        seg = [straighten(f, STRAIGHTEN[name]) for f in seg]
    return seg
