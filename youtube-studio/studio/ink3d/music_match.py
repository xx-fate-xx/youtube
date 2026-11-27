"""Rank library cuts by how close they are to the reference Shorts' sound (loud from second one, ~125 bpm, bright).

    python -m studio.ink3d.music_match [seconds=30]

Reference profile measured on three @SimplyAnimatedVisuals Shorts (projects/ref_motivation): loudness about -8 dB
RMS per second from the first second, beat ~0.95 s (126 bpm double-time), spectral centroid ~1550 Hz.
"""

import sys

import numpy as np

from .music_pick import LIB, SR, load

REF_DB, REF_CEN, REF_BEAT = -8.0, 1550.0, 0.955


def profile(a: np.ndarray):
    hop = SR // 10
    n = len(a) // hop
    fr = a[: n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-6)
    spec = np.abs(np.fft.rfft(fr * np.hanning(hop), axis=1))
    f = np.fft.rfftfreq(hop, 1 / SR)
    cen = (spec * f).sum(1) / (spec.sum(1) + 1e-9)
    return db, cen


def beat(a: np.ndarray) -> float:
    lp = np.convolve(a, np.ones(60) / 60, "same")
    h = SR // 100
    m = len(lp) // h
    e = 20 * np.log10(np.sqrt((lp[: m * h].reshape(m, h) ** 2).mean(1)) + 1e-6)
    fl = np.maximum(0, np.diff(e, prepend=e[0]))
    best = (0.0, 0.5)
    for per in np.arange(0.40, 1.05, 0.004):
        for ph in np.arange(0, per, 0.02):
            idx = (np.arange(ph, len(e) / 100, per) * 100).astype(int)
            s = fl[idx[idx < len(fl)]].mean()
            if s > best[0]:
                best = (float(s), float(per))
    return best[1]


def main(seconds: float = 30) -> None:
    rows = []
    for p in sorted(LIB.glob("*.mp3")):
        a = load(p)
        db, cen = profile(a)
        W = int(seconds * 10)
        best = None
        for s in range(0, len(db) - W, 10):
            w, c = db[s: s + W], cen[s: s + W]
            start = w[:20].mean()                                 # first 2 s must already hit
            dist = abs(w.mean() - REF_DB) + 1.5 * max(0.0, REF_DB - 4 - start) + abs(c.mean() - REF_CEN) / 150
            if best is None or dist < best[0]:
                best = (dist, s / 10, w.mean(), start, c.mean())
        if best is None:
            continue
        cut = a[int(best[1] * SR): int((best[1] + seconds) * SR)]
        per = beat(cut)
        bpm = 60 / per
        tempo_pen = min(abs(bpm - 126), abs(bpm * 2 - 126), abs(bpm / 2 - 126)) / 10
        rows.append((best[0] + tempo_pen, p.stem[12:], best[1], best[2], best[3], best[4], per))
    for d, name, t0, loud, start, cen, per in sorted(rows)[:10]:
        print(f"{d:5.1f}  {name:<24} from {t0:5.1f}s  loud {loud:5.1f}  first2s {start:5.1f}  bright {cen:5.0f} Hz  "
              f"beat {per:.3f}s ({60 / per:.0f} bpm)")


if __name__ == "__main__":
    main(*(float(x) for x in sys.argv[1:2]))
