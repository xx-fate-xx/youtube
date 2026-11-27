"""frames.txt for the teleport episode, generated from the approved script.md (single source of the narration).

Each "## " section of script.md is a chapter; its VO paragraphs are split into shots of whole sentences
(<= ~28 words). Visuals are not described here: they live in scenes.py (What If engine), which refers to the
shot numbers printed by this script.
Run:  python script_source.py   -> frames.txt (+ shot list)
"""

import re
from pathlib import Path

from studio.pipeline.scriptgen import Script

HERE = Path(__file__).resolve().parent
CHAPTERS = {0: "A door, not a brake", 1: "The window cleaner", 2: "The ground isn't still",
            3: "Go east, get launched", 4: "The safe zone", 5: "Other ways a jump goes wrong", 6: "Space",
            7: "The secret route", 8: "Jump small, jump smart"}
MAX_WORDS = 28


def sections() -> list[tuple[int, list[str]]]:
    body = (HERE / "script.md").read_text(encoding="utf-8").split("\n---\n")[1]
    out = []
    for sec in re.split(r"^## ", body, flags=re.M)[1:]:
        k = int(sec.split(".", 1)[0])
        paras = re.findall(r"^VO: (.*?)(?=\n\n|\nVISUAL|\Z)", sec, re.M | re.S)
        out.append((k, [" ".join(p.split()) for p in paras]))
    return out


def split(para: str) -> list[str]:
    sents = re.findall(r"[^.?!]+[.?!]+(?:\s|$)", para + " ")
    shots, cur = [], []
    for s in (x.strip() for x in sents):
        if cur and len(" ".join(cur + [s]).split()) > MAX_WORDS:
            shots.append(" ".join(cur))
            cur = []
        cur.append(s)
    if cur:
        shots.append(" ".join(cur))
    return shots


s = Script(__file__, "What If You Could Teleport? (Your Speed Comes Too)")
for k, paras in sections():
    first = True
    for para in paras:
        for vo in split(para):
            extra = {"CHAPTER": CHAPTERS[k]} if first else {}
            s.shot("B", "wide", "w", "-", f"Глава {k}" if 0 < k < 8 else ("Вступление" if k == 0 else "Финал"), vo, "-", **extra)
            first = False

if __name__ == "__main__":
    s.write()
    for i, sh in enumerate(s.shots, 1):
        print(f"#{i:<3} {sh[8].get('CHAPTER', ''):<30} {sh[5][:90]}")
