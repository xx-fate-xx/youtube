"""frames.txt for this Short, generated from the approved script.md (one shot per VO paragraph)."""

import re
from pathlib import Path

from studio.pipeline.scriptgen import Script

HERE = Path(__file__).resolve().parent
TITLE = re.search(r"^title: (.+)$", (HERE / "episode.yaml").read_text(encoding="utf-8"), re.M).group(1)
text = (HERE / "script.md").read_text(encoding="utf-8").split("\nVISUAL")[0]
paras = [" ".join(p.split()) for p in re.findall(r"^VO: (.*?)(?=\n\n|\Z)", text, re.M | re.S)]

s = Script(__file__, TITLE)
for k, vo in enumerate(paras):
    extra = {"CHAPTER": "Short"} if k == 0 else {}
    s.shot("B", "wide", "w", "-", "Шортс", vo, "-", **extra)

if __name__ == "__main__":
    s.write()
    for i, sh in enumerate(s.shots, 1):
        print(f"#{i:<3} {sh[5][:100]}")
