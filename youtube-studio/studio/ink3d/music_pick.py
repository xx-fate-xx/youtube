"""Find the best ~N-second cut of each library track for a Short with a build and a big payoff.

    python -m studio.ink3d.music_pick [seconds=30] [payoff_at=21]

Score per window: overall loudness, the rise from the first third to the last third, a strong hit near
`payoff_at` (the finale), and a steady beat. Prints the top windows with their beat grid (period, phase).
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

LIB = Path(__file__).resolve().parents[2] / "assets" / "music" / "library"
SR = 22050


def load(p: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def envelope(a: np.ndarray, hop: int = SR // 20) -> np.ndarray:
    n = len(a) // hop
    return 20 * np.log10(np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-6)


def grid(db: np.ndarray, fps: int = 20) -> tuple[float, float, float]:
    fl = np.maximum(0, np.diff(db, prepend=db[0]))
    best = (0.0, 0.5, 0.0)
    for per in np.arange(0.40, 0.90, 0.005):
        for ph in np.arange(0, per, 0.025):
            idx = (np.arange(ph, len(db) / fps, per) * fps).astype(int)
            s = fl[idx[idx < len(fl)]].mean()
            if s > best[0]:
                best = (float(s), float(per), float(ph))
    return best


def main(seconds: float = 30, payoff: float = 21) -> None:
    rows = []
    for p in sorted(LIB.glob("*.mp3")):
        a = load(p)
        db = envelope(a)
        W = int(seconds * 20)
        for s in range(0, len(db) - W, 20):
            w = db[s: s + W]
            third = W // 3
            rise = w[-third:].mean() - w[:third].mean()
            pi = int(payoff * 20)
            hit = (w[pi: pi + 10].max() - w[pi - 20: pi].mean()) if pi + 10 < W else 0
            score = w.mean() + 1.2 * rise + 0.6 * hit
            rows.append((score, p.stem, s / 20, w.mean(), rise, hit))
    rows.sort(reverse=True)
    seen = set()
    for score, name, t0, loud, rise, hit in rows:
        if name in seen:
            continue
        seen.add(name)
        a = load(LIB / f"{name}.mp3")[int(t0 * SR): int((t0 + seconds) * SR)]
        _, per, ph = grid(envelope(a))
        print(f"{score:6.1f}  {name[12:]:<22} {t0:5.0f}s  loud {loud:5.1f}  rise {rise:+4.1f}  hit {hit:+4.1f}  "
              f"beat {per:.3f}s ({60 / per:.0f} bpm) phase {ph:.2f}")
        if len(seen) >= 10:
            break


if __name__ == "__main__":
    main(*(float(x) for x in sys.argv[1:3]))
