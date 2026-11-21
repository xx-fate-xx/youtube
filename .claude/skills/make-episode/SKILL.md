---
name: make-episode
description: Produce a complete YouTube documentary episode end to end with the youtube-studio video pipeline — research, original fact-checked script, storyboard, Higgsfield images and clips, ElevenLabs narration, sound design and mix, animated render, titles, QA and release kit — from a topic or a competitor video/script used only as a starting point. Use when the user asks to make a new video/episode, "сделай видос", "вот сценарий конкурента", or runs /make-episode.
---

# make-episode — the video pipeline playbook

Repository: `c:\dev\youtube\youtube-studio` (commands below run there; CLI = `.venv/Scripts/studio.exe`,
abbreviated `studio`). Pipeline code: `studio/pipeline/`. Docs: `docs/VIDEO_PIPELINE.md`. Reference episode:
`episodes/enginovue_cable_1858/` (study its frames.txt, sounds.yaml, episode.yaml before writing a new one).

Input: `$ARGUMENTS` — a topic, a competitor video link, or a competitor script/transcript file.

## Non-negotiable rules (project CLAUDE.md + user decisions)
- **Originality.** A competitor script is a *starting point only* (topic, questions, claims to check). Never
  reuse its wording, its sentence order or its structure beat by beat. Write a new script from primary
  sources. Save the reference text to `projects/<slug>/input/*.txt` (git-ignored) and run
  `studio pipe originality` — it must pass before checkpoint 1.
- **Facts.** Every number, date, name and quote is checked against sources (fact-check subagents per chapter,
  as for the cable episode: `factcheck_report.md`). Unverified claims are rewritten or cut. Sources go to
  `episode.yaml` → `release.sources`. Never invent sources.
- **Money.** No paid call before the operator approved the script and the estimate (`studio pipe approve`,
  checkpoint 1). Budget per video: Higgsfield ≤ 200 credits total (images ~1.25 each + ≤ 2 AI clips à 4),
  ElevenLabs ≤ episode budget (a 9-minute video ≈ 7.7k narration + ≈ 9–10k sound/music credits). Check the
  balance before and after every paid batch and record it (`studio pipe report`, `--credits`).
- **Media are never overwritten** (originals read-only; new attempts become `_v2`, `_v3`).
- **Upload is never automatic.** The operator watches the video and uploads it as Private first (checkpoint 2).
- **House style:** titles in the editorial style, placed per frame where they do not cover the subject; no
  boxes, accent bars or border stripes; voice always on top of music/effects; no frozen pictures.
- Speak to the user in Russian, briefly, in plain words; every paid step shows the cost first.

## Stages (run `studio pipe status -e <slug>` any time; it resumes where it stopped)

### 1. Brief → episode folder
1. Pick a slug (`<brand>_<topic>`, lowercase). `studio pipe new <slug> --title "..."`.
2. Competitor material → `projects/<slug>/input/competitor.txt` (ask the user to paste the transcript if
   only a link is given; yt-dlp subtitles are fine if installed). Note what the competitor gets wrong or skips —
   that is our angle.

### 2. Research and script (free)
1. Research from primary/authoritative sources (books of the period, museums, archives, standards bodies);
   use parallel research subagents per chapter group for large topics.
2. Write `episodes/<slug>/frames.txt` (syntax: `studio/pipeline/frames.py` docstring). Targets: 8–12 min,
   1,200–2,000 words, ~2.5 words/s, **≤ 130 shots** (budget: 130 × 1.25 + 10 % reserve + 2 clips ≤ 200),
   8–12 `CHAPTER`s (the first frame always has one), a hook in the first 15 s that is true.
   Per shot: RU, VO, SCENE (+ ANIM on every 5th shot), optional GFX/TITLE/FX/CAMERA/AMB/SFX/MUSIC/AI_CLIP.
   Exact charts: `episodes/<slug>/overlays.py` (see the cable episode; computed from formulas).
   Real people: `characters.yaml` with evidence for their look.
3. `episode.yaml`: `storyboard_end`, eras for the period, voice (default Ryan `GQQpeRnV5mCWTgxKhGo5`,
   eleven_v4 — confirm with the user for a new channel), budget, release fields.
4. `sounds.yaml`: 25–35 spot effects (one clear sound each, no visual words), 6–8 ambience loops (20 s),
   3 music cues sized to chapter groups (instrumental, "made to sit under voice-over"). Place them in
   frames.txt with AMB / SFX / MUSIC.
5. Fact-check (subagents per chapter) → fix → `factcheck_report.md`.
6. `studio pipe build`, `studio pipe originality`, `studio pipe preflight`.

**CHECKPOINT 1** — show the user: topic angle, chapter list, word count/length, fact-check summary,
originality result, cost estimate (Higgsfield / ElevenLabs). Ask with AskUserQuestion. Only after "yes":
`studio pipe approve --note "..."`.

### 3. Images (Higgsfield MCP, paid)
Loop until `studio pipe images` shows all accepted:
1. `studio pipe next --batch 8` → read `projects/<slug>/production/next_batch_mcp.json`.
2. `mcp__higgsfield__balance` (before) → `mcp__higgsfield__generate_image_batch` with those requests
   (≤ 8 concurrent; 12 gives HTTP 429) → `mcp__higgsfield__jobs_wait` until terminal.
3. For each job: `studio pipe record N JOB URL --credits 1.25` (runs QA), then `studio pipe decide N candidate`
   so the next batch moves on. Delegating 5 batches at a time to a background subagent (strictly sequential)
   keeps the long prompts out of the main context.
4. Balance (after) → `studio pipe report K BEFORE AFTER` (positional arguments).
5. Review by eye: `studio pipe sheet a-b` (contact sheets in projects/<slug>/review/frames). The automatic QA
   flags most frames on the left edge (buildings and streets legitimately run off the frame) — judge by eye.
   Accept with `studio pipe decide N accept`; add `--note "headroom tight ..."` when a head is close to the top
   (the render then never pushes toward that edge). Reject only real problems: wrong object (e.g. an engine
   crank instead of a clock movement), extra people, cut heads, anachronisms, text in the image. Fix the SCENE
   text, rebuild, park the frame with `decide N candidate --note "REDO: ..."` so later batches skip it, and
   regenerate all REDO frames together at the end (`decide N reject`, then `pipe next`).
6. GFX frames: composite each image with its chart PNG (`episodes/<slug>/overlays/<timecode>_gfx.png`) and check
   the chart card does not hide the icon. If it does, do not pay for a new image: move the icon locally on the
   plain background into the free corner, save it under `production/frames/edit/` (new file; the original is not
   touched) and accept it with `decide N accept --file production/frames/edit/<name>.png --note "..."`. A small icon on a plain background
   moves too little under the default chart camera (`breathe_in`) and `pipe check` reports a frozen picture —
   give such shots `CAMERA="push_in"` or `"pull_out"` in the script (not `drift`: too weak; the render never
   repeats a move back-to-back, so pick the one the previous shot does not use).

### 4. AI clips (≤ 2, paid)
For `AI_CLIP` frames: upload the accepted PNG (`mcp__higgsfield__media_upload` + curl PUT with
`If-None-Match: *` + `media_confirm`), `generate_video_batch` with `grok_video_v15_lite`, 720p, 4 s, 16:9,
role `start_image`, prompt = the frame's anim prompt (prompts.jsonl). Review frames of the clip; accept →
`studio pipe record-clip N JOB URL --credits 4`.

### 5. Narration (ElevenLabs MCP, paid)
1. `studio pipe chunks` → texts in `projects/<slug>/audio/narration_chunks.json`.
2. One `mcp__elevenlabs__creative_generate_speech` call per chunk (voice from episode.yaml, model eleven_v4,
   `generations_count: 1`; the first call creates the flow, pass its flow_id to the rest), poll
   `creative_get_flow_run_status` (concurrency limits retry automatically; signed URLs expire in ~2 h —
   download promptly) → `studio pipe save-audio narration K URL --credits <chars>`.
3. `studio pipe align` — every chapter should match ≥ 90 % of words; a low match means a skipped/extra
   phrase: check that spot (quiet ≈ breath, loud ≈ real extra words) and regenerate only that chunk.

### 6. Sounds and mix (ElevenLabs MCP, paid; mix free)
1. `studio pipe sounds` lists missing assets with prompts and credits.
2. Spots: `creative_generate_in_flow` node_type `sfx`, model `eleven_text_to_sound_v3`, count 1 (auto length
   ≈ 17 cr). Ambiences: same with `estimate_only` to create the node → `creative_update_node`
   `{duration_seconds: 20, prompt_influence: 0.4, loop: true}` → `creative_run_flow_nodes`. Music: node_type
   `music`, `eleven_music_v2_5`, `estimate_only` → update `{duration_seconds, lyrics_type: instrumental,
   instrumental: true}` → run. Save each: `studio pipe save-audio sfx|ambience|music ID URL --credits C`.
   ElevenLabs' up-front estimates for ambiences and music are about twice the real charge (music ≈ 15 cr/s);
   `studio pipe sounds` uses the real prices. Narration and sounds can run in parallel with the image batches
   (a background subagent can generate the whole sound library).
3. `studio pipe mix` — no frame may be reported under 8 dB voice-over-bed margin.

### 7. Titles
`studio pipe titles propose` → `studio pipe titles sheet` → open every sheet image and check each title does
not cover a face, the object the narration talks about or a chart; fix with
`studio pipe titles set N POS [--dx X --dy Y] -e <slug>` (positions: bottom/top center|left|right, mid_left/right); re-check. Titles are clamped to the safe
area (nothing below 85 % of the height: that band belongs to subtitles), so a large `--dy` may not move them.

### 8. Render and QA
`studio pipe render --only 1-20` (preview; look at sampled frames) → full `studio pipe render` in the
background (~7 min for 9 min of video) → `studio pipe check` must say OK → look at ~10 sampled frames of the
final file (titles, effects, AI clips).

### 9. Release kit
Fill `release` in episode.yaml (truthful hook, 3 title options, tags, thumbnails with truthful text on
frames that show the idea; text must not cover the key action) → `studio pipe release` → view thumbnails.
Commit `episodes/<slug>/` on a branch (never media; never secrets).

**CHECKPOINT 2** — tell the user where the release folder is, total credits spent (Higgsfield + ElevenLabs),
known minor issues, and that they should watch it with headphones and upload it as Private first.
