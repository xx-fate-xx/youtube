"""A long stair climb from a short CMU clip: 111_27 climbs one step per ~1.6 s (2.4-4.0 s is one clean cycle).
The cycle is repeated, each copy shifted one step forward and up, with short cross-fades at the seams; the
step geometry is derived from the measured foot plants so the brick staircase sits exactly under the feet.

    python -m studio.ink3d.stairs [steps] [speed]   -> projects/ink_proto3d/mocap/stairs_track.json
"""

import json
import sys
from pathlib import Path

import numpy as np

MOCAP = Path(__file__).resolve().parents[2] / "projects" / "ink_proto3d" / "mocap"
FPS = 30


def track(steps: int = 6, speed: float = 1.5) -> dict:
    fr = json.loads((MOCAP / "111_27.json").read_text())
    joints = list(fr[0])
    arr = np.array([[f[j] for j in joints] for f in fr])          # (n, J, 3): x fwd, y up, z lateral (height 1)
    a, b = int(2.4 * FPS), int(4.0 * FPS)
    lead = arr[:a]
    cyc = arr[a:b]
    d = arr[b] - arr[a]                                           # per-cycle shift of every joint
    shift = d[joints.index("pelvis")].copy()                       # one step forward / up / sideways
    out = [lead]
    for k in range(steps):
        c = cyc + shift * k
        if k:                                                     # cross-fade the seam over 4 frames
            prev = out[-1][-4:]
            w = np.linspace(0, 1, 4)[:, None, None]
            out[-1] = out[-1][:-4]
            c = np.concatenate([prev * (1 - w) + c[:4] * w, c[4:]])
        out.append(c)
    allf = np.concatenate(out)
    allf[:, :, 2] -= np.linspace(0, shift[2] * steps, len(allf))[:, None]   # remove the sideways drift
    # speed up by resampling
    t = np.arange(0, len(allf) - 1, speed)
    i0 = np.floor(t).astype(int)
    u = (t - i0)[:, None, None]
    res = allf[i0] * (1 - u) + allf[i0 + 1] * u
    # step geometry from the first cycle's plants (ankle heights ~0.19 h above the floor = step 0 surface)
    rise = float(shift[1])
    depth = float(shift[0])
    x0 = float(arr[a, joints.index("ankleR"), 0]) - 0.06          # right foot lands on step 0 at frame a
    return {"joints": joints, "frames": res.round(4).tolist(), "rise": rise, "depth": depth,
            "step0_x": x0, "steps": steps}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    sp = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    tr = track(n, sp)
    (MOCAP / "stairs_track.json").write_text(json.dumps(tr), encoding="utf-8")
    print(len(tr["frames"]), "frames", f"rise {tr['rise']:.3f} depth {tr['depth']:.3f} step0_x {tr['step0_x']:.3f}")
