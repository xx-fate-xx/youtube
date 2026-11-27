"""Find library cuts that sound like the reference Shorts' track (dark melodic trap: melodic intro, 808 drop at ~5 s).

    python -m studio.ink3d.music_ref <library_dir> [preview_dir]

Reference = the @SimplyAnimatedVisuals Shorts audio (projects/ref_motivation/*.mp4, one song in all of them).
Features compared on the drop section: sub-bass share (<80 Hz), low share (80-250 Hz), spectral centroid,
tonalness (mid-band spectral flatness), beat period (half-time aware) and the chroma profile (key-invariant: best
of 12 rotations). Structure: each candidate is cut so its biggest low-end jump (the drop) lands at 5.0 s, like
the reference; the intro before it must be clearly lighter in the low end.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050
ROOT = Path(__file__).resolve().parents[2]
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def load(p: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def spectra(a: np.ndarray, n: int = 4096, hop: int = 2205):
    fr = np.lib.stride_tricks.sliding_window_view(a, n)[::hop] * np.hanning(n)
    return np.abs(np.fft.rfft(fr, axis=1)), np.fft.rfftfreq(n, 1 / SR), hop / SR


def low_env(a: np.ndarray) -> np.ndarray:
    """Sub/low-band energy per 0.1 s (dB)."""
    S, f, _ = spectra(a)
    return 10 * np.log10((S[:, f < 150] ** 2).sum(1) + 1e-9)


def features(a: np.ndarray) -> dict:
    S, f, _ = spectra(a)
    P = S ** 2
    tot = P.sum(1) + 1e-9
    sub = (P[:, f < 80].sum(1) / tot).mean()
    low = (P[:, (f >= 80) & (f < 250)].sum(1) / tot).mean()
    cen = ((S * f).sum(1) / (S.sum(1) + 1e-9)).mean()
    mid = S[:, (f > 300) & (f < 3000)] + 1e-9
    flat = (np.exp(np.log(mid).mean(1)) / mid.mean(1)).mean()          # 0 = pure tones, 1 = noise
    ok = (f > 80) & (f < 4000)
    pc = (np.round(12 * np.log2(f[ok] / 440)) % 12).astype(int)
    chroma = np.array([S[:, ok][:, pc == p].sum() for p in range(12)])
    chroma /= np.linalg.norm(chroma)
    e = low_env(a)
    fl = np.maximum(0, np.diff(e, prepend=e[0]))
    best = (0.0, 0.5)
    for per in np.arange(0.40, 1.05, 0.005):
        for ph in np.arange(0, per, 0.05):
            idx = (np.arange(ph, len(e) / 10, per) * 10).astype(int)
            s = fl[idx[idx < len(fl)]].mean()
            if s > best[0]:
                best = (float(s), float(per))
    return {"sub": sub, "low": low, "cen": cen, "flat": flat, "chroma": chroma, "beat": best[1]}


def chroma_sim(a: np.ndarray, b: np.ndarray) -> tuple[float, int]:
    return max((float(np.dot(np.roll(a, k), b)), k) for k in range(12))


def key_name(ch: np.ndarray) -> str:
    return NOTE[(int(np.argmax(ch)) + 9) % 12]


def main(lib: Path, preview: Path | None = None) -> None:
    ref_audio = load(ROOT / "projects" / "ref_motivation" / "65JbnU2wZbQ.mp4")
    ref = features(ref_audio[int(12 * SR): int(30 * SR)])             # its drop section
    print(f"REF  sub {ref['sub']:.2f} low {ref['low']:.2f} bright {ref['cen']:.0f} Hz tonal-flat {ref['flat']:.2f} "
          f"beat {ref['beat']:.3f}s key-root {key_name(ref['chroma'])}")
    rows = []
    for p in sorted(lib.glob("*.mp3")):
        a = load(p)
        e = low_env(a)
        if len(e) < 400:
            continue
        # the drop: biggest rise of low-end energy (next 3 s vs previous 3 s), not in the first 5 s of the file
        rise = np.array([e[i: i + 30].mean() - e[i - 30: i].mean() for i in range(50, len(e) - 260)])
        i = int(np.argmax(rise)) + 50
        t_drop, jump = i / 10, float(rise.max())
        t0 = max(0.0, t_drop - 5.0)
        drop = a[int(t_drop * SR): int((t_drop + 18) * SR)]
        F = features(drop)
        cs, rot = chroma_sim(F["chroma"], ref["chroma"])
        tempo = min(abs(F["beat"] - ref["beat"]), abs(F["beat"] * 2 - ref["beat"]), abs(F["beat"] / 2 - ref["beat"]))
        d = (abs(F["sub"] - ref["sub"]) * 6 + abs(F["low"] - ref["low"]) * 4 + abs(F["cen"] - ref["cen"]) / 600
             + abs(F["flat"] - ref["flat"]) * 4 + (1 - cs) * 4 + tempo * 4 + max(0.0, 10 - jump) * 0.15)
        rows.append((d, p, t0, t_drop, jump, F, cs))
    rows.sort(key=lambda r: r[0])
    names = {}
    lst = lib / "list.txt"
    if lst.is_file():
        for ln in lst.read_text(encoding="utf-8").splitlines():
            url, name, *_ = ln.split("|")
            names[Path(url).stem] = name.strip()
    for k, (d, p, t0, t_drop, jump, F, cs) in enumerate(rows[:12]):
        nm = names.get(p.stem, p.stem)
        print(f"{k + 1:2d} {d:5.2f}  {nm:<22} drop at {t_drop:5.1f}s (+{jump:4.1f} dB)  sub {F['sub']:.2f} low {F['low']:.2f} "
              f"bright {F['cen']:4.0f} flat {F['flat']:.2f} beat {F['beat']:.3f}s chroma {cs:.2f} key {key_name(F['chroma'])}")
        if preview and k < 8:
            preview.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in nm)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.2f}", "-t", "30", "-i", str(p), "-af",
                            "loudnorm=I=-14:TP=-1.5,afade=t=out:st=29:d=1", str(preview / f"{k + 1:02d}_{safe}.mp3")])


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
