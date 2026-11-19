"""Caption cues from word timings, and SRT output."""

from __future__ import annotations

from dataclasses import dataclass

from studio.models import WordTiming


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def cues_from_words(words: list[WordTiming], *, max_chars: int = 42,
                    max_duration: float = 3.5) -> list[Cue]:
    cues: list[Cue] = []
    current: list[WordTiming] = []

    def flush() -> None:
        if current:
            cues.append(Cue(current[0].start, current[-1].end,
                            " ".join(w.word for w in current)))
            current.clear()

    for w in words:
        if current:
            text_len = len(" ".join(x.word for x in current)) + 1 + len(w.word)
            if text_len > max_chars or w.end - current[0].start > max_duration:
                flush()
        current.append(w)
        if w.word.endswith((".", "?", "!")):
            flush()
    flush()
    # Avoid overlaps and zero-length cues.
    fixed: list[Cue] = []
    for i, c in enumerate(cues):
        end = min(c.end, cues[i + 1].start) if i + 1 < len(cues) else c.end
        fixed.append(Cue(c.start, max(end, c.start + 0.2), c.text))
    return fixed


def srt_time(t: float) -> str:
    ms = max(0, round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [f"{i}\n{srt_time(c.start)} --> {srt_time(c.end)}\n{c.text}\n"
              for i, c in enumerate(cues, start=1)]
    return "\n".join(blocks)


def parse_srt(text: str) -> list[Cue]:
    def parse_t(s: str) -> float:
        hms, ms = s.strip().split(",")
        h, m, sec = (int(x) for x in hms.split(":"))
        return h * 3600 + m * 60 + sec + int(ms) / 1000

    cues = []
    for block in text.strip().split("\n\n"):
        lines = block.strip().splitlines()
        if len(lines) >= 3:
            a, b = lines[1].split("-->")
            cues.append(Cue(parse_t(a), parse_t(b), " ".join(lines[2:])))
    return cues
