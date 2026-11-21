"""Episode scaffolding and the stage overview of the video pipeline.

Stages (resumable; each reads the files the previous one wrote):
   1 brief       projects/<slug>/input/ reference material (competitor script = starting point only)
   2 script      episodes/<slug>/frames.txt (VO per shot, CHAPTER lines) + factcheck_report.md
   3 originality originality.json passes (no wording carried over from the reference)
   4 preflight   preflight.json approved by the operator            <- CHECKPOINT 1 (script + cost)
   5 storyboard  prompts.jsonl, storyboard.md, overlays (studio pipe build)
   6 images      every frame accepted (Higgsfield MCP batches, QA, decisions)
   7 ai clips    accepted image-to-video clips for AI_CLIP frames
   8 narration   one ElevenLabs take per chapter (audio/narration/chNN.mp3)
   9 alignment   narration_timing.json
  10 sounds      every sounds.yaml asset present
  11 mix         audio/mix_full.wav
  12 titles      title_layout.json covers all titled frames (reviewed)
  13 render      final mix render + `studio pipe check` OK
  14 release     release kit                                        <- CHECKPOINT 2 (operator watches, uploads Private)
"""

from __future__ import annotations

import json
from pathlib import Path

from .episode import EPISODES, Episode, ep, use

EPISODE_YAML = """# Episode settings for the video pipeline (studio pipe ...). Media go to projects/{slug}/ (git-ignored).
slug: {slug}
title: "{title}"
brand: {brand}
channel: {channel}
language: en-US
style: enginovue_cartoon            # studio/pipeline/styles/<style>.yaml
storyboard_end: "0:00"              # m:ss end of the last storyboard slot (estimate; narration re-times it)
eras:                               # era codes used in the frames.txt header (style adds m and -)
  h: "Historical setting drawn in the same cartoon style; people are stylized cartoon humans in accurate period clothing, machines are period-accurate. Show nothing that did not exist yet at that time. Show every person's whole head, including any hat, with clear space above it; no head or hat cut by the frame edge."
image: {{model: gpt_image_2_6, params: {{aspect_ratio: "16:9", quality: low, resolution: 2k}}, price_credits: 1.25}}
animation: {{model: grok_video_v15_lite, resolution: 720p, duration: 4, price_credits: 4.0, max_clips: 2}}
budget: {{higgsfield_credits: 200, elevenlabs_credits: 25000, retry_reserve: 0.10}}
narration:
  voice_id: GQQpeRnV5mCWTgxKhGo5    # ElevenLabs library voice (no clones); confirm with the operator
  voice_name: Ryan - American Documentary Narrator
  model: eleven_v4
competitor:                         # starting point only; text goes to projects/{slug}/input/*.txt
  source: ""
release:
  hook: ""
  title_options: []
  tags: []
  hashtags: []
  sources: []                       # "Author, Title (year) — URL", verified in the fact-check
  notes:
    - "Illustrations are AI-generated in an original cartoon style; they are interpretations, not photographs. The narration voice and the music are AI-generated."
  thumbnails: []                    # - {{frame: 10, lines: [["IT DIED", 130], ["IN A MONTH", 130], ["SUBLINE", 40]], side: left}}
  known_items: []
"""

FRAMES_TXT = """# {title}
# One block per shot. Header: #n | m:ss | mode (A light / B dark) | shot | characters (codes from characters.yaml or -) | era | title (- = none)
# Lines: RU, VO, SCENE (required); ANIM (every 5th shot), GFX, CHAPTER, TITLE (main | small), FX, CAMERA, AMB, SFX, MUSIC, AI_CLIP.
# Full syntax: studio/pipeline/frames.py. VO is the approved script and is never rewritten by the pipeline.
"""

SOUNDS_YAML = """# Sound library: Claude generates missing assets with the ElevenLabs MCP (studio pipe sounds lists them).
duck_db: {music: 6, ambience: 4, sfx: 6}
chapter_whoosh: {sfx: whoosh, at: -0.9, gain_db: -12}
spots:
  whoosh: {prompt: "Soft deep airy whoosh transition, smooth and subtle"}
ambience: {}
music: {}
"""


def new_episode(slug: str, title: str, channel: str = "engineering_explained", brand: str = "Enginovue") -> Path:
    src = EPISODES / slug
    if src.exists():
        raise SystemExit(f"{src} already exists")
    src.mkdir(parents=True)
    (src / "episode.yaml").write_text(EPISODE_YAML.format(slug=slug, title=title, channel=channel, brand=brand),
                                      encoding="utf-8")
    (src / "frames.txt").write_text(FRAMES_TXT.format(title=title), encoding="utf-8")
    (src / "characters.yaml").write_text("# code: {name, ru, look, ref?, life, evidence: [], status, avoid}\n{}\n",
                                         encoding="utf-8")
    (src / "sounds.yaml").write_text(SOUNDS_YAML, encoding="utf-8")
    e = use(src)
    (e.work / "input").mkdir(parents=True, exist_ok=True)
    return src


def _exists(p: Path) -> bool:
    return p.is_file()


def status(episode: Episode | None = None) -> list[tuple[str, bool, str]]:
    from . import frames as frames_mod
    from . import mix, preflight, production, titles
    e = episode or ep()
    rows: list[tuple[str, bool, str]] = []
    inputs = sorted((e.work / "input").glob("*.txt")) if (e.work / "input").is_dir() else []
    rows.append(("brief", True, f"{len(inputs)} reference file(s) in input/"))
    try:
        fr = frames_mod.parse()
    except SystemExit as err:
        rows.append(("script", False, f"frames.txt: {err}"))
        return rows
    words = sum(len(f["vo"].split()) for f in fr)
    fc = _exists(e.src / "factcheck_report.md")
    rows.append(("script", bool(fr) and fc, f"{len(fr)} shots, {words} words, "
                 f"{len(frames_mod.chapters(fr))} chapters, fact-check {'present' if fc else 'MISSING'}"))
    orig = e.work / "originality.json"
    ok = json.loads(orig.read_text(encoding="utf-8"))["ok"] if orig.is_file() else not inputs
    rows.append(("originality", ok, "passed" if orig.is_file() and ok else ("not run" if not orig.is_file() else "FAILED")))
    appr = preflight.approved()
    legacy = bool(e.cfg.get("legacy_no_preflight"))
    rows.append(("preflight", bool(appr) or legacy, f"approved {appr['at']}" if appr else
                 ("legacy episode (produced before preflight existed)" if legacy else "waiting for the operator")))
    rows.append(("storyboard", _exists(e.src / "prompts.jsonl"), "prompts.jsonl"))
    if _exists(e.src / "prompts.jsonl"):
        st = production.load_state()
        dec = production.decisions(st)
        acc = sum(1 for f in fr if dec.get(f["n"], {}).get("decision") in production.ACCEPTED)
        rows.append(("images", acc == len(fr), f"{acc}/{len(fr)} accepted"))
        want = min(e.cfg["animation"]["max_clips"], sum(1 for f in fr if f.get("ai_clip")))
        got = sum(1 for v in st.get("anim", {}).values() if v.get("decision") == "accepted")
        rows.append(("ai clips", got >= want, f"{got}/{want} accepted"))
    from . import align
    chs = align.chunks(write=False)
    takes = sum(1 for c in chs if align.take_path(c["chunk"]).is_file())
    rows.append(("narration", takes == len(chs), f"{takes}/{len(chs)} chapter takes"))
    rows.append(("alignment", _exists(e.audio / "narration_timing.json"), "narration_timing.json"))
    ms = mix.status()
    rows.append(("sounds", not ms["missing"], f"{len(ms['present'])} present, {len(ms['missing'])} missing"))
    rows.append(("mix", _exists(e.audio / "mix_full.wav"), "mix_full.wav"))
    tl = titles.load()
    tf = titles.titled_frames()
    rows.append(("titles", all(f["n"] in tl for f in tf), f"{sum(1 for f in tf if f['n'] in tl)}/{len(tf)} placed"))
    from . import render
    final = e.render_dir / f"{render.names()['mixed']}.mp4"
    rows.append(("render", final.is_file(), final.name))
    rows.append(("release", _exists(e.release_dir / "description.txt"), "release kit"))
    return rows


SHORT_NOTE = ("Illustrations are AI-generated in an original cartoon style; they are interpretations, not "
              "historical photographs. The narration voice, sound effects and music are AI-generated.")


def new_short(slug: str, title: str, parent: str) -> Path:
    """Scaffold a YouTube Short (1080x1920) that links to the long video `parent` and reuses its eras, narration
    voice, characters and sound library. The narration is written new for the Short (never cut from the long one)."""
    import shutil

    import yaml
    src = EPISODES / slug
    if src.exists():
        raise SystemExit(f"{src} already exists")
    par = Episode.load(parent)
    cfg = {
        "slug": slug, "title": title, "brand": par.cfg.get("brand", "Enginovue"),
        "channel": par.cfg.get("channel", "engineering_explained"),
        "format": "short", "parent": par.slug, "sound_library": par.slug,
        "language": par.cfg.get("language", "en-US"), "style": par.cfg.get("style", "enginovue_cartoon"),
        "storyboard_end": "0:45",
        "eras": dict(par.cfg.get("eras") or {}),
        "image": {"model": par.cfg["image"]["model"],
                  "params": {**par.cfg["image"]["params"], "aspect_ratio": "9:16"},
                  "price_credits": par.cfg["image"]["price_credits"]},
        "animation": {**par.cfg["animation"], "max_clips": 1},
        "budget": {"higgsfield_credits": 20, "elevenlabs_credits": 1500, "retry_reserve": 0.10},
        "narration": {**par.cfg["narration"], "intro_s": 0.2, "gap_s": 0.0, "outro_s": 0.8},
        "release": {"hook": "", "title_options": [], "tags": [], "hashtags": [], "long_video": "",
                    "sources": [], "notes": [SHORT_NOTE],
                    "known_items": []},
    }
    src.mkdir(parents=True)
    (src / "episode.yaml").write_text(
        f"# YouTube Short (1080x1920) linked to {par.slug}; media go to projects/{slug}/ (git-ignored).\n"
        + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=120)
        .replace("storyboard_end: 0:45", 'storyboard_end: "0:45"'), encoding="utf-8")
    (src / "frames.txt").write_text(FRAMES_TXT.format(title=title), encoding="utf-8")
    if (par.src / "characters.yaml").is_file():
        shutil.copy2(par.src / "characters.yaml", src / "characters.yaml")
    else:
        (src / "characters.yaml").write_text("{}\n", encoding="utf-8")
    (src / "sounds.yaml").write_text(
        f"# Uses the sound library of {par.slug} (sound_library in episode.yaml); add Short-only sounds here.\n"
        "spots: {}\nambience: {}\nmusic: {}\n", encoding="utf-8")
    e = use(src)
    (e.work / "input").mkdir(parents=True, exist_ok=True)
    return src
