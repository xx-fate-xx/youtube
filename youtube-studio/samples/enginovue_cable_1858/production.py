"""Production bookkeeping for Enginovue stills (Visual Pipeline v1.0). Never calls a paid API.

Generation itself runs through Higgsfield MCP after explicit approval of each batch; this tool
decides WHAT to generate, records what came back and keeps accepted frames out of later batches.

Commands:
  py production.py plan [--batch 10] [--reserve 0.15]   batches of frames still to generate + budget
  py production.py next                                 the next batch, with prompts/params/refs
  py production.py record N JOB_ID URL                  save PNG + JSON as a new version, run qa.py
  py production.py decide N accept|accept_fixed|reject [--file NAME] [--note TEXT]
  py production.py status                               per-frame state

State (account-specific, git-ignored): projects/enginovue_cable_1858/production/state.json
Frames:                                 projects/enginovue_cable_1858/production/frames/
Accepted pilot frames are read from pilot_v1_manifest.json and skipped automatically.
Existing PNGs are never overwritten: a new attempt becomes <file>_v2.png, _v3.png, ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "projects" / "enginovue_cable_1858"
PROD = PROJECT / "production"
FRAMES = PROD / "frames"
STATE = PROD / "state.json"
PILOT_MANIFEST = HERE / "pilot_v1_manifest.json"
PRICE = 0.5                      # credits per frame, gpt_image_2_6 low/2k (Higgsfield quote 2026-11-20)
ACCEPTED = {"accepted", "accepted_with_note", "accepted_fixed"}


def prompts() -> dict[int, dict]:
    return {r["n"]: r for r in (json.loads(x) for x in (HERE / "prompts.jsonl").read_text(encoding="utf-8").splitlines())}


def load_state() -> dict:
    if STATE.is_file():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"frames": {}, "reference_media_ids": {}}


def save_state(state: dict) -> None:
    PROD.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)           # atomic save


def decisions(state: dict) -> dict[int, dict]:
    """Current decision per frame: production state overrides the pilot manifest."""
    out: dict[int, dict] = {}
    if PILOT_MANIFEST.is_file():
        for f in json.loads(PILOT_MANIFEST.read_text(encoding="utf-8"))["frames"]:
            out[f["frame"]] = {"decision": f["decision"], "file": f["accepted_file"], "source": "pilot"}
    for n, f in state["frames"].items():
        if f.get("decision"):
            out[int(n)] = {"decision": f["decision"], "file": f.get("accepted_file"), "source": "production"}
    return out


def todo(state: dict) -> list[int]:
    dec = decisions(state)
    return [n for n in sorted(prompts()) if dec.get(n, {}).get("decision") not in ACCEPTED]


def cmd_plan(a) -> None:
    state = load_state()
    left = todo(state)
    dec = decisions(state)
    batches = [left[i:i + a.batch] for i in range(0, len(left), a.batch)]
    base = len(left) * PRICE
    reserve = math.ceil(base * a.reserve / PRICE) * PRICE      # whole frames of headroom
    plan = {"created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "price_per_frame": PRICE, "frames_total": len(prompts()),
            "accepted": sorted(n for n, d in dec.items() if d["decision"] in ACCEPTED),
            "to_generate": len(left), "base_credits": base, "reserve_share": a.reserve,
            "reserve_credits": reserve, "total_credits": base + reserve,
            "batches": [{"batch": i + 1, "frames": b, "credits": len(b) * PRICE} for i, b in enumerate(batches)]}
    PROD.mkdir(parents=True, exist_ok=True)
    (PROD / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"frames {plan['frames_total']}, accepted {len(plan['accepted'])} {plan['accepted']}, "
          f"to generate {len(left)}")
    print(f"base {base:g} cr + reserve {a.reserve:.0%} ≈ {reserve:g} cr = {base + reserve:g} credits")
    for b in plan["batches"]:
        print(f"  batch {b['batch']:>2}: {len(b['frames']):>2} frames {b['frames'][0]}–{b['frames'][-1]} "
              f"({b['credits']:g} cr)")
    print(f"plan saved to {PROD / 'plan.json'}")


def cmd_next(a) -> None:
    state = load_state()
    left = todo(state)
    rows = prompts()
    batch = [rows[n] for n in left[:a.batch]]
    out = [{"n": r["n"], "file": r["file"], "model": r["model"], "params": r["params"],
            "image_references": r["image_references"],
            "reference_media_ids": [state["reference_media_ids"].get(x) for x in r["image_references"]],
            "prompt": r["prompt"]} for r in batch]
    (PROD / "next_batch.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"next batch: {[r['n'] for r in out]} ({len(out) * PRICE:g} credits) -> {PROD / 'next_batch.json'}")


def new_version_path(file: str) -> Path:
    path = FRAMES / file
    k = 2
    while path.exists():
        path = FRAMES / file.replace(".png", f"_v{k}.png")
        k += 1
    return path


def cmd_record(a) -> None:
    import qa  # local import: qa needs numpy, the planning commands do not
    rows = prompts()
    row = rows[a.n]
    FRAMES.mkdir(parents=True, exist_ok=True)
    png = new_version_path(row["file"])
    urllib.request.urlretrieve(a.url, png)
    state = load_state()
    meta = {"frame": a.n, "timecode": row["timecode"], "job_id": a.job, "result_url": a.url,
            "model": row["model"], "params": row["params"], "image_references": row["image_references"],
            "reference_media_ids": [state["reference_media_ids"].get(x) for x in row["image_references"]],
            "prompt_sha256": hashlib.sha256(row["prompt"].encode()).hexdigest(), "prompt": row["prompt"],
            "gfx_file": row["gfx_file"], "credits_estimate": PRICE,
            "saved": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    png.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    r = qa.run([png], FRAMES / "qa", base=FRAMES)[0]
    f = state["frames"].setdefault(str(a.n), {"attempts": []})
    f["attempts"].append({"file": png.name, "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                          "job_id": a.job, "qa_status": r.status, "qa_fixed_status": r.fixed_status or None,
                          "qa_fixed_file": Path(r.fixed_file).name if r.fixed_file else None})
    save_state(state)
    issue = next((i.message for i in sorted(r.issues, key=lambda i: -qa.RANK[i.status]) if i.status != "PASS"), "")
    print(f"#{a.n} -> {png.name}  QA {r.status}{': ' + issue if issue else ''}"
          + (f"  | fixed copy {r.fixed_status}" if r.fixed_file else ""))


def cmd_decide(a) -> None:
    state = load_state()
    f = state["frames"].setdefault(str(a.n), {"attempts": []})
    if a.decision == "reject":
        f.update(decision="rejected", accepted_file=None)
    else:
        if not f["attempts"] and not a.file:
            raise SystemExit("no recorded attempt; pass --file")
        last = f["attempts"][-1] if f["attempts"] else {}
        name = a.file or (last.get("qa_fixed_file") if a.decision == "accept_fixed" else last.get("file"))
        sub = "qa/" if a.decision == "accept_fixed" and not a.file else ""
        f.update(decision="accepted_fixed" if a.decision == "accept_fixed" else "accepted",
                 accepted_file=f"{sub}{name}")
    f["note"] = a.note
    f["decided"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_state(state)
    print(f"#{a.n}: {f['decision']} {f.get('accepted_file') or ''}")


def cmd_status(a) -> None:
    state = load_state()
    dec = decisions(state)
    counts: dict[str, int] = {}
    for n in sorted(prompts()):
        d = dec.get(n, {}).get("decision", "todo")
        counts[d] = counts.get(d, 0) + 1
        if a.verbose or d not in ("todo",):
            att = state["frames"].get(str(n), {}).get("attempts", [])
            print(f"#{n:<4} {d:<20} {dec.get(n, {}).get('file') or ''}  attempts={len(att)}")
    print(counts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("--batch", type=int, default=10); p.add_argument("--reserve", type=float, default=0.15)
    p.set_defaults(fn=cmd_plan)
    p = sp.add_parser("next"); p.add_argument("--batch", type=int, default=10); p.set_defaults(fn=cmd_next)
    p = sp.add_parser("record"); p.add_argument("n", type=int); p.add_argument("job"); p.add_argument("url")
    p.set_defaults(fn=cmd_record)
    p = sp.add_parser("decide"); p.add_argument("n", type=int)
    p.add_argument("decision", choices=["accept", "accept_fixed", "reject"])
    p.add_argument("--file"); p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_decide)
    p = sp.add_parser("status"); p.add_argument("-v", "--verbose", action="store_true"); p.set_defaults(fn=cmd_status)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
