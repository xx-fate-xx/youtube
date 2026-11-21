"""Originality gate: our narration must not reuse the wording of a reference (competitor) script.

A competitor video or script is only a starting point (topic, questions, claims to verify). The script is
written from primary sources; this gate compares it with the reference text and fails when wording was
carried over. Reference material stays in projects/<slug>/input/ (git-ignored; it is someone else's text).

Measures (case- and punctuation-insensitive word sequences):
  * share of our 8-word sequences that also occur in the reference  -> must be <= MAX_SHARED (2 %)
  * longest run of consecutive shared words                         -> must be <  MAX_RUN (12 words)
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from . import frames as frames_mod
from .episode import ep

N, MAX_SHARED, MAX_RUN = 8, 0.02, 12


def words(text: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z0-9' ]", " ", text.lower()).split() if w]


def compare(ours: str, ref: str) -> dict:
    a, b = words(ours), words(ref)
    grams_b = {tuple(b[i:i + N]) for i in range(len(b) - N + 1)}
    grams_a = [tuple(a[i:i + N]) for i in range(len(a) - N + 1)]
    shared = sum(1 for g in grams_a if g in grams_b)
    share = shared / max(1, len(grams_a))
    # longest common run of words (dynamic programming over word positions, sparse via an index)
    pos: dict[str, list[int]] = {}
    for j, w in enumerate(b):
        pos.setdefault(w, []).append(j)
    best, best_at, prev = 0, 0, {}
    for i, w in enumerate(a):
        cur = {}
        for j in pos.get(w, ()):
            cur[j] = prev.get(j - 1, 0) + 1
            if cur[j] > best:
                best, best_at = cur[j], i
        prev = cur
    longest = " ".join(a[best_at - best + 1:best_at + 1]) if best else ""
    ok = share <= MAX_SHARED and best < MAX_RUN
    return {"ok": ok, "shared_8gram_share": round(share, 4), "longest_shared_run": best,
            "longest_shared_text": longest, "our_words": len(a), "reference_words": len(b),
            "limits": {"max_shared_share": MAX_SHARED, "max_run": MAX_RUN - 1}}


def check(reference: Path | None = None) -> dict:
    inp = ep().work / "input"
    refs = [Path(reference)] if reference else sorted(inp.glob("*.txt"))
    if not refs:
        res = {"ok": True, "note": "no reference script in projects/<slug>/input/ — nothing to compare"}
    else:
        ours = " ".join(f["vo"] for f in frames_mod.parse())
        res = {"ok": True, "references": {}}
        for r in refs:
            c = compare(ours, r.read_text(encoding="utf-8", errors="ignore"))
            res["references"][r.name] = c
            res["ok"] &= c["ok"]
    res["checked"] = datetime.now(UTC).isoformat(timespec="seconds")
    ep().work.mkdir(parents=True, exist_ok=True)
    (ep().work / "originality.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res
