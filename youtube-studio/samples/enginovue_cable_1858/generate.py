"""Generate Enginovue storyboard frames through the Higgsfield CLI (paid).

Safety rules:
  * Dry run by default: prints what would be generated and the credit estimate.
  * Real generation only with --confirm, at most 10 frames per run.
  * Checks the workspace credit balance first and stops if the batch would not fit.
  * Idempotent: frames whose PNG already exists are skipped (use --force to redo one).
  * Every saved frame is checked by qa.py (margins, subtitle band, 16:9, overlay area);
    results go to <output>/qa/qa_report.md, fixed copies to <output>/qa/*_fixed.png.
    Frames generated through Higgsfield MCP instead of the CLI: run `py qa.py <folder>`.

Examples:
  python generate.py --from 1 --to 1                 # dry run for frame #1
  python generate.py --from 1 --to 1 --confirm       # generate frame #1
  python generate.py --only 12,36,152 --confirm      # specific frames
  python generate.py --from 11 --to 20 --confirm     # next batch of 10

Output: youtube-studio/projects/enginovue_cable_1858/frames/HH_MM_SS_mmm.png
(+ .json job record per frame). projects/ is gitignored.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import qa

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "projects" / "enginovue_cable_1858" / "frames"
MAX_BATCH = 10


def cli() -> str:
    exe = shutil.which("higgsfield")
    if not exe:
        sys.exit("higgsfield CLI not found on PATH")
    return exe


def estimate(model: str, params: dict) -> float:
    """Ask Higgsfield for the credit cost of one frame with these settings."""
    cmd = [cli(), "generate", "cost", model, "--prompt", "estimate"]
    for k, v in params.items():
        cmd += [f"--{k}", v]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    m = re.search(r"([\d.]+)\s+credits", out)
    if not m:
        sys.exit(f"could not estimate cost: {out.strip()[:200]}")
    return float(m.group(1))


def balance() -> float:
    out = subprocess.run([cli(), "account", "status"], capture_output=True, text=True).stdout
    m = re.search(r"([\d.]+)\s+credits", out)
    if not m:
        sys.exit("could not read credit balance from `higgsfield account status`")
    return float(m.group(1))


def find_image_url(obj) -> str | None:
    if isinstance(obj, str):
        if obj.startswith("http") and re.search(r"\.(png|jpe?g|webp)(\?|$)", obj, re.I):
            return obj
        return None
    if isinstance(obj, dict):
        items = obj.values()
    elif isinstance(obj, list):
        items = obj
    else:
        return None
    for v in items:
        url = find_image_url(v)
        if url:
            return url
    return None


def select(frames: list[dict], args) -> list[dict]:
    if args.only:
        wanted = {int(x) for x in args.only.split(",")}
        return [f for f in frames if f["n"] in wanted]
    return [f for f in frames if args.start <= f["n"] <= args.end]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="start", type=int, default=1)
    p.add_argument("--to", dest="end", type=int, default=1)
    p.add_argument("--only", help="comma-separated frame numbers")
    p.add_argument("--confirm", action="store_true", help="actually spend credits")
    p.add_argument("--force", action="store_true", help="regenerate even if the PNG exists")
    p.add_argument("--model", help="override model, e.g. gpt_image_2_6")
    p.add_argument("--quality", help="override quality (low/medium/high/...)")
    p.add_argument("--resolution", help="override resolution (1k/2k/4k)")
    p.add_argument("--subdir", help="save under projects/enginovue_cable_1858/<subdir> instead of frames/")
    args = p.parse_args()

    out = OUT.parent / args.subdir if args.subdir else OUT
    frames = [json.loads(line) for line in (HERE / "prompts.jsonl").read_text(encoding="utf-8").splitlines()]
    for f in frames:
        if args.model:
            f["model"] = args.model
        if args.quality:
            f["params"]["quality"] = args.quality
        if args.resolution:
            f["params"]["resolution"] = args.resolution
    batch = [f for f in select(frames, args) if args.force or not (out / f["file"]).exists()]
    if not batch:
        print("nothing to generate")
        return
    if len(batch) > MAX_BATCH:
        sys.exit(f"{len(batch)} frames selected; the limit is {MAX_BATCH} per run")

    per_frame = estimate(batch[0]["model"], batch[0]["params"])
    est = len(batch) * per_frame
    print(f"model: {batch[0]['model']} {batch[0]['params']}  output: {out}")
    print(f"frames: {[f['n'] for f in batch]}  estimate: {per_frame:g} x {len(batch)} = {est:g} credits")
    if not args.confirm:
        for f in batch:
            print(f"  #{f['n']} {f['timecode']} -> {f['file']}  refs={f['image_references'] or '-'}")
        print("dry run: add --confirm to generate")
        return

    have = balance()
    if have < est:
        sys.exit(f"balance {have:g} credits < estimate {est:g}; top up or pick fewer frames")

    out.mkdir(parents=True, exist_ok=True)
    for f in batch:
        cmd = [cli(), "generate", "create", f["model"], "--prompt", f["prompt"]]
        for k, v in f["params"].items():
            cmd += [f"--{k}", v]
        for ref in f["image_references"]:
            cmd += ["--image-references", str(HERE / ref)]
        cmd += ["--wait", "--wait-timeout", "15m", "--json"]
        print(f"#{f['n']} {f['timecode']} generating...", flush=True)
        res = subprocess.run(cmd, capture_output=True, text=True)
        record = out / f["file"].replace(".png", ".json")
        record.write_text(res.stdout or res.stderr, encoding="utf-8")
        if res.returncode != 0:
            print(f"  FAILED (exit {res.returncode}): {(res.stderr or res.stdout).strip()[:300]}")
            continue
        try:
            url = find_image_url(json.loads(res.stdout))
        except json.JSONDecodeError:
            url = find_image_url(res.stdout.split())
        if not url:
            print(f"  no image URL in response; see {record.name}")
            continue
        urllib.request.urlretrieve(url, out / f["file"])
        print(f"  saved {f['file']}")
        r = qa.run([out / f["file"]], out / "qa", base=out)[0]
        issue = next((i.message for i in r.issues if i.status != "PASS"), "")
        fixed = f"; auto-fixed copy {r.fixed_status}" if r.fixed_file else ""
        print(f"  QA {r.status}{': ' + issue if issue else ''}{fixed}")


if __name__ == "__main__":
    main()
