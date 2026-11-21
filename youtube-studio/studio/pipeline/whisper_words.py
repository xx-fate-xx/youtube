"""Word timestamps for narration takes (faster-whisper, local, free).

Runs inside the separate alignment venv (projects/.tools/align-venv) so the main environment does not
need faster-whisper. Usage: python whisper_words.py OUT.json take1.mp3 [take2.mp3 ...]
Writes {"<path>": [[word, start, end], ...], "_device": "cuda|cpu"}.
No initial prompt is passed: it makes Whisper skip the start of the audio.
"""

from __future__ import annotations

import json
import subprocess
import sys


def pcm16k(path: str):
    """Decode to 16 kHz mono float32 with ffmpeg (avoids the PyAV version faster-whisper pins)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def load_model(probe: str):
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel("small.en", device="cuda", compute_type="float16")
        list(m.transcribe(pcm16k(probe)[:16000 * 5], word_timestamps=False)[0])
        return m, "cuda"
    except Exception as e:  # noqa: BLE001 - missing CUDA libraries -> CPU
        print(f"CUDA unavailable ({type(e).__name__}); using CPU", flush=True)
        return WhisperModel("small.en", device="cpu", compute_type="int8"), "cpu"


def main() -> None:
    out, paths = sys.argv[1], sys.argv[2:]
    model, device = load_model(paths[0])
    res: dict = {"_device": device}
    for p in paths:
        segs, _ = model.transcribe(pcm16k(p), language="en", word_timestamps=True, beam_size=5,
                                   condition_on_previous_text=False)
        res[p] = [[w.word.strip(), w.start, w.end] for s in segs for w in s.words]
        print(f"{p}: {len(res[p])} words", flush=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh)


if __name__ == "__main__":
    main()
