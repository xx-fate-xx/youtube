"""Storyboard source (frames.txt) -> prompts, storyboard table, timeline, narration text, overlays.

frames.txt: one block per shot.

  #12 | 0:40 | B | close | thomson | h | William Thomson · Glasgow
  RU: short Russian summary          (storyboard table)
  VO: narration for this shot        (approved script text, never rewritten by the pipeline)
  SCENE: English scene core for the image prompt
  ANIM: motion || camera || what stays still        (image-to-video prompt)
  GFX: overlay_id                    (exact chart from the episode's overlays.py)
  CHAPTER: Chapter title             (a chapter starts here: narration chunk, dip to black, YouTube chapter)
  TITLE: main line | small line      (on-screen title; overrides the header column; "|" = two-tier)
  FX: rain, bubbles, lightning@1.3, sparks, fire, lamp, nolamp   (local render effects)
  CAMERA: push_in | pull_out | pan_lr | pan_rl | tilt_up | tilt_down | drift | sway | snap | settle
  AMB: ambience_id | -               (ambience bed from sounds.yaml; persists until changed, "-" stops it)
  SFX: sfx_id @0.3 -4dB [max=5] [tail=1.2]; other_id @0 ...      (spot effects, offset from shot start)
  MUSIC: music_id [-1dB]             (music cue starts here and runs to the next MUSIC or the end)
  AI_CLIP: yes                       (candidate for a paid image-to-video clip)

Header: #n | m:ss | mode (A light / B dark) | shot | characters (codes from characters.yaml or -) |
        era (key from the style/episode eras) | title (- = none)
"""

from __future__ import annotations

import csv
import json
import re
from itertools import groupby
from pathlib import Path

from .episode import ep

HEADER = re.compile(
    r"^#(?P<n>\d+)\s*\|\s*(?P<t>\d+:\d{2})\s*\|\s*(?P<mode>[AB])\s*\|\s*(?P<shot>\w+)\s*\|"
    r"\s*(?P<chars>[\w,\-]+)\s*\|\s*(?P<era>[\w\-])\s*\|\s*(?P<overlay>.*)$"
)
KEYS = {"RU", "VO", "SCENE", "ANIM", "GFX", "CHAPTER", "TITLE", "FX", "CAMERA", "AMB", "SFX", "MUSIC", "AI_CLIP"}
SFX_RE = re.compile(r"^(?P<id>[\w\-]+)\s*@\s*(?P<at>-?[\d.]+)(?:\s+(?P<gain>-?[\d.]+)\s*dB)?(?P<rest>.*)$")


def tc_seconds(tc: str) -> int:
    m, s = tc.split(":")
    return int(m) * 60 + int(s)


def tc_filename(tc: str) -> str:
    sec = tc_seconds(tc)
    return f"{sec // 3600:02d}_{sec % 3600 // 60:02d}_{sec % 60:02d}_000"


def _sfx(val: str, n: int) -> list[dict]:
    out = []
    for part in filter(None, (p.strip() for p in val.split(";"))):
        m = SFX_RE.match(part)
        if not m:
            raise SystemExit(f"frame #{n}: bad SFX '{part}' (expected: id @offset [gain dB] [max=s] [tail=s])")
        d = {"sfx": m["id"], "frame": n, "at": float(m["at"]), "gain_db": float(m["gain"] or 0)}
        for k, v in re.findall(r"(max|tail)=([\d.]+)", m["rest"]):
            d["max_s" if k == "max" else "tail_s"] = float(v)
        out.append(d)
    return out


def parse(path: Path | None = None) -> list[dict]:
    path = path or ep().frames_txt
    style, chars = ep().style(), ep().characters()
    frames: list[dict] = []
    cur: dict | None = None
    amb = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        m = HEADER.match(line)
        if m:
            cur = m.groupdict()
            cur["n"] = int(cur["n"])
            cur["chars"] = [] if cur["chars"] == "-" else cur["chars"].split(",")
            cur["overlay"] = "" if cur["overlay"].strip() == "-" else cur["overlay"].strip()
            cur.update(fx=[], sfx=[], amb=amb)
            frames.append(cur)
            continue
        if cur is None or line.startswith("#") or not line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if key not in KEYS:
            continue
        if key == "FX":
            cur["fx"] = [x.strip() for x in val.split(",") if x.strip()]
        elif key == "SFX":
            cur["sfx"] = _sfx(val, cur["n"])
        elif key == "AMB":
            amb = None if val == "-" else val
            cur["amb"] = amb
        elif key == "TITLE":
            main, _, sub = val.partition("|")
            cur["title"] = (main.strip(), sub.strip() or None)
        elif key == "MUSIC":
            mid, *gain = val.split()
            cur["music"] = {"file": mid, "gain_db": float(gain[0].lower().replace("db", "")) if gain else 0.0}
        elif key == "AI_CLIP":
            cur["ai_clip"] = val.lower() in ("yes", "true", "1")
        else:
            cur[key.lower()] = val
    end = ep().cfg.get("storyboard_end")
    for i, f in enumerate(frames):
        if f["n"] != i + 1:
            raise SystemExit(f"frame numbering broken at #{f['n']}")
        for k in ("ru", "vo", "scene"):
            if not f.get(k):
                raise SystemExit(f"frame #{f['n']} missing {k}")
        if f["shot"] not in style["shots"]:
            raise SystemExit(f"frame #{f['n']} unknown shot {f['shot']}")
        if f["era"] not in style["eras"]:
            raise SystemExit(f"frame #{f['n']} unknown era {f['era']}")
        unknown = set(f["chars"]) - set(chars)
        if unknown:
            raise SystemExit(f"frame #{f['n']} unknown characters {unknown} (add them to characters.yaml)")
        if f["n"] % 5 == 0 and not f.get("anim"):
            raise SystemExit(f"frame #{f['n']} is every-5th but has no ANIM")
        if "title" not in f:
            f["title"] = (f["overlay"], None) if f["overlay"] else None
        nxt = frames[i + 1]["t"] if i + 1 < len(frames) else end
        if nxt is None:
            raise SystemExit("episode.yaml needs storyboard_end (m:ss end of the last slot)")
        f["start"] = tc_seconds(f["t"])
        f["duration"] = tc_seconds(nxt) - f["start"]
        if f["duration"] <= 0:
            raise SystemExit(f"frame #{f['n']} has non-positive duration")
        f["file"] = tc_filename(f["t"]) + ".png"
        f["gfx_file"] = tc_filename(f["t"]) + "_gfx.png" if f.get("gfx") else ""
        if f.get("gfx") and ep().vertical:
            raise SystemExit(f"frame #{f['n']}: chart overlays (GFX) are 16:9 only; not available in Shorts yet")
    if frames and not frames[0].get("chapter"):
        frames[0]["chapter"] = "Intro"
    return frames


def chapters(frames: list[dict]) -> list[tuple[int, str]]:
    return [(f["n"], f["chapter"]) for f in frames if f.get("chapter")]


# ---------------------------------------------------------------- prompts

def image_prompt(f: dict) -> tuple[str, list[str]]:
    style, chars = ep().style(), ep().characters()
    refs: list[str] = []
    people: list[str] = []
    for c in f["chars"]:
        h = chars[c]
        if h.get("ref") and (ep().src / h["ref"]).is_file():
            refs.append(h["ref"])
            people.append(f"Reference image {len(refs)} shows {h['look']}; match it.")
        else:
            people.append(h["look"] + ".")
    parts = [style["style"], style["modes"][f["mode"]], style["eras"][f["era"]], style["shots"][f["shot"]],
             "Scene: " + f["scene"], style.get("no_mascot_line", "")]
    if people:
        parts.append("Historical people: " + " ".join(people) + " " + style["hist_rule"])
    if f.get("gfx"):
        parts.append(style["gfx_rule"])
    parts.append(style.get("tech_short", style["tech"]) if ep().vertical else style["tech"])
    return " ".join(p for p in parts if p), refs


def anim_prompt(f: dict) -> str:
    if not f.get("anim"):
        return ""
    motion, camera, still = (s.strip() for s in f["anim"].split("||"))
    return f"Motion: {motion}. Camera: {camera}. Keep still: {still}. {ep().style()['anim_tail']}"


def shot_report(frames: list[dict]) -> list[str]:
    warnings = []
    for shot, group in groupby(frames, key=lambda f: f["shot"]):
        run = list(group)
        if len(run) >= 4:
            warnings.append(f"#{run[0]['n']}-#{run[-1]['n']}: {len(run)} x {shot} in a row")
    return warnings


def characters_doc(frames: list[dict]) -> str:
    chars = ep().characters()
    out = [
        f"# Historical character identity specs ({ep().cfg.get('brand', '')}, {ep().slug})\n",
        "Generated from `characters.yaml`; edit there, not here. "
        "The `look` line goes into every prompt where the code appears in the characters column "
        "of frames.txt. A reference sheet at `ref` is attached automatically once that file "
        "exists; none has been generated yet (paid step, needs explicit approval).\n",
    ]
    for code, h in chars.items():
        used = [f"#{f['n']}" for f in frames if code in f["chars"]]
        ref_state = "present" if h.get("ref") and (ep().src / h["ref"]).is_file() else "not generated"
        out += [
            f"## `{code}` — {h['name']}\n",
            f"- Life/age in frames: {h.get('life', '—')}",
            f"- Frames: {', '.join(used) or '—'}",
            f"- Reference sheet: `{h.get('ref', '—')}` ({ref_state})",
            f"- Verification: {h.get('status', '—')}",
            f"- Avoid: {h.get('avoid', '—')}\n",
            "Prompt identity:\n",
            f"> {h['look']}\n",
            "Evidence:\n",
            *[f"- {e}" for e in h.get("evidence", [])],
            "",
        ]
    return "\n".join(out)


def build() -> list[dict]:
    """Write prompts.jsonl, prompts.md, storyboard.md, edit_timeline.csv, voiceover text, character doc
    and the chart overlays into the episode source folder."""
    e = ep()
    frames = parse()
    style, chars = e.style(), e.characters()
    img = e.cfg["image"]
    end = e.cfg["storyboard_end"]
    with (e.src / "prompts.jsonl").open("w", encoding="utf-8") as fh:
        for f in frames:
            prompt, refs = image_prompt(f)
            fh.write(json.dumps({
                "n": f["n"], "timecode": f["t"], "start_s": f["start"], "duration_s": f["duration"],
                "file": f["file"], "anim_file": f["file"].replace(".png", ".mp4") if f.get("anim") else "",
                "gfx_file": f["gfx_file"], "model": img["model"], "params": dict(img["params"]),
                "image_references": refs, "overlay_text": f["overlay"],
                "prompt": prompt, "anim_prompt": anim_prompt(f),
            }, ensure_ascii=False) + "\n")

    names = {k: v.get("ru", k) for k, v in chars.items()}
    sb = [
        f"# Раскадровка {e.cfg.get('brand', '')}: {e.cfg.get('title', e.slug)}\n",
        f"Кадров: {len(frames)}. Хронометраж: {end}. "
        f"С анимацией: {sum(1 for f in frames if f.get('anim'))}. "
        f"С точной графикой: {sum(1 for f in frames if f.get('gfx'))}. "
        "Надписи из колонки «Титр» и графика из колонки «Графика» добавляются в монтаже, "
        "в изображение не запекаются.\n",
        "| # | Таймкод | Диктор | Кадр | Герои | Режим | План | Анимация | Титр | Графика | Файл |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in frames:
        sb.append("| {n} | {t} | {vo} | {ru} | {ch} | {mode} | {shot} | {an} | {ov} | {gfx} | {file} |".format(
            n=f["n"], t=f["t"], vo=f["vo"].replace("|", "/"), ru=f["ru"],
            ch=", ".join(names[c] for c in f["chars"]) or "—", mode=style["mode_names"][f["mode"]],
            shot=f["shot"], an="да" if f.get("anim") else "—", ov=f["overlay"] or "—",
            gfx=f["gfx_file"] or "—", file=f["file"],
        ))
    (e.src / "storyboard.md").write_text("\n".join(sb) + "\n", encoding="utf-8")

    pm = [f"# Image and animation prompts ({img['model']} {img['params'].get('quality')}/"
          f"{img['params'].get('resolution')} via Higgsfield)\n"]
    for f in frames:
        prompt, refs = image_prompt(f)
        pm.append(f"## #{f['n']} [{f['t']}] -> {f['file']}\n")
        pm.append(f"VO: {f['vo']}\n")
        pm.append(f"References: {', '.join(refs) if refs else 'none'}\n")
        if f.get("gfx"):
            pm.append(f"Overlay (composited in editing): overlays/{f['gfx_file']}\n")
        pm.append(f"```text\n{prompt}\n```\n")
        if f.get("anim"):
            pm.append(f"Animation prompt -> {f['file'].replace('.png', '.mp4')}\n")
            pm.append(f"```text\n{anim_prompt(f)}\n```\n")
    (e.src / "prompts.md").write_text("\n".join(pm), encoding="utf-8")

    with (e.src / "edit_timeline.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["n", "timecode", "start_s", "duration_s", "image", "anim_clip", "gfx_overlay",
                    "overlay", "voiceover"])
        for f in frames:
            w.writerow([f["n"], f["t"], f["start"], f["duration"], f["file"],
                        f["file"].replace(".png", ".mp4") if f.get("anim") else "",
                        f"overlays/{f['gfx_file']}" if f["gfx_file"] else "", f["overlay"], f["vo"]])

    text = " ".join(f["vo"] for f in frames)
    (e.src / "voiceover_elevenlabs.txt").write_text(text + "\n", encoding="utf-8")
    (e.src / "characters_historical.md").write_text(characters_doc(frames), encoding="utf-8")

    from . import overlay_kit
    rendered = overlay_kit.render_all([(f["gfx"], f["file"][:-4]) for f in frames if f.get("gfx")])
    words = len(text.split())
    print(f"frames={len(frames)} anim={sum(1 for f in frames if f.get('anim'))} "
          f"with_people={sum(1 for f in frames if f['chars'])} gfx={len(rendered) // 2} "
          f"chapters={len(chapters(frames))} words={words} wps={words / tc_seconds(end):.2f}")
    for warn in shot_report(frames):
        print("shot variety:", warn)
    return frames
