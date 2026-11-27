"""Cost preflight and the operator's approval before any paid generation (CLAUDE.md: no silent spending).

Estimate (credits):
  Higgsfield  = images still to generate x price x (1 + retry reserve) + AI clips x clip price
  ElevenLabs  = narration characters (1 credit/char, eleven_v4) + missing sounds (mix.status())
Both must fit the episode budget (episode.yaml budget). `approve()` records the operator's go-ahead in
projects/<slug>/preflight.json; `require_approval()` is called by every step that prepares paid requests.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime

from . import align, mix, production
from . import frames as frames_mod
from .episode import ep


def estimate() -> dict:
    e = ep()
    frames = frames_mod.parse()
    img, anim, bud = e.cfg["image"], e.cfg["animation"], e.cfg["budget"]
    state = production.load_state() if (e.prod / "state.json").is_file() else {"frames": {}, "reference_media_ids": {}}
    dec = production.decisions(state) if (e.src / "prompts.jsonl").is_file() else {}
    todo = [f["n"] for f in frames if dec.get(f["n"], {}).get("decision") not in production.SKIP]
    if e.style().get("engine") == "whatif":
        todo = []        # drawn in code from the art library: no image per shot (new art is a separate paid step)
    images = len(todo) * img["price_credits"]
    reserve = math.ceil(images * bud["retry_reserve"] / img["price_credits"]) * img["price_credits"]
    clips_done = sum(1 for v in state.get("anim", {}).values() if v.get("decision") == "accepted")
    clips_left = max(0, min(anim["max_clips"], sum(1 for f in frames if f.get("ai_clip"))) - clips_done)
    clips = clips_left * anim["price_credits"]
    spent_hf = sum(x.get("used", 0) for x in state.get("ledger", []) if x.get("billing") in ("credits", None))
    chunks_missing = [c for c in align.chunks(write=False)
                      if not (e.audio / "narration" / f"ch{c['chunk']:02d}.mp3").is_file()]
    narration = sum(c["chars"] for c in chunks_missing)
    sounds = mix.status()["credits_missing"]
    hf_total, el_total = images + reserve + clips, narration + sounds
    res = {
        "higgsfield": {"images_to_generate": len(todo), "images": images, "retry_reserve": reserve,
                       "ai_clips": clips_left, "clips": clips, "total": hf_total, "already_spent": spent_hf,
                       "budget": bud["higgsfield_credits"],
                       "fits": spent_hf + hf_total <= bud["higgsfield_credits"] + 1e-9},
        "elevenlabs": {"narration_chars": narration, "sounds": round(sounds, 1), "total": round(el_total, 1),
                       "budget": bud["elevenlabs_credits"], "fits": el_total <= bud["elevenlabs_credits"]},
    }
    res["fits"] = res["higgsfield"]["fits"] and res["elevenlabs"]["fits"]
    return res


def _file():
    return ep().work / "preflight.json"


def approve(note: str = "") -> dict:
    est = estimate()
    if not est["fits"]:
        raise SystemExit("estimate exceeds the episode budget; lower the plan or raise the budget in episode.yaml")
    rec = {"approved": True, "at": datetime.now(UTC).isoformat(timespec="seconds"), "note": note,
           "estimate": est}
    ep().work.mkdir(parents=True, exist_ok=True)
    _file().write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def approved() -> dict | None:
    f = _file()
    if not f.is_file():
        return None
    rec = json.loads(f.read_text(encoding="utf-8"))
    return rec if rec.get("approved") else None


def require_approval() -> None:
    if ep().cfg.get("legacy_no_preflight"):
        return
    if approved() is None:
        raise SystemExit("paid steps need the operator's approval: run `studio pipe preflight` and, after the "
                         "operator agrees, `studio pipe approve`")
