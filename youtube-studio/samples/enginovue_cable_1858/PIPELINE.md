# Enginovue Visual Pipeline v1.0

Adopted 2026-11-20 after the 6-frame pilot (#12, #25, #41, #44, #47, #57). No further model comparisons are planned.

## Generation standard
| Setting | Value |
|---|---|
| Provider | Higgsfield **MCP** (the CLI is blocked on this account: `only_mcp_usage_on_trial_is_available`) |
| Model | `gpt_image_2_6` |
| Quality / resolution | `low` / `2k` → 2688×1520 output, downscaled to 1920×1080 (≈1.4× zoom reserve) |
| Aspect ratio | `16:9` |
| Price | 1.25 credits per frame on the current Plus account (0.5 on the earlier trial account) |
| Mascots | dropped on 2026-11-21: no Octopus / Lynx / Bit in any frame; `refs/*.png` stay in the repo but are unused |
| Historical people | text identity specs (`characters_historical.md`, source: `HISTORICAL` in `build.py`); no paid reference sheets yet |

Rules: no paid call without explicit approval per batch; no automatic regeneration on QA warnings; original PNGs are never overwritten.

## Source of truth and build
1. Edit `frames.txt` (scenes, VO, shots, characters, `GFX:` overlays) and the tables in `build.py` (style, composition rules, character specs).
2. `py build.py` regenerates `prompts.jsonl`, `prompts.md`, `storyboard.md`, `edit_timeline.csv`, `voiceover_elevenlabs.txt`, `characters_historical.md`, `overlays/*_gfx.svg|png`.
3. Never hand-edit the derived files. Timecodes (152 frames, 8:19) must stay unchanged.

## Batches and bookkeeping (`production.py`)
- `py production.py plan` — frames still to generate (accepted pilot/production frames are skipped via the manifests), batches of 10, budget with a 15% re-generation reserve.
- `py production.py next` — the next batch with exact prompts, params and reference media ids.
- `py production.py record N JOB_ID URL` — saves a new version (`_v2`, `_v3`… never overwrites), writes JSON, runs QA.
- `py production.py decide N accept|accept_fixed|reject` — records the editorial decision; accepted frames drop out of later batches.
- State lives in `projects/enginovue_cable_1858/production/` (git-ignored: account-specific media ids, images).

## Running one batch (only after explicit approval of that batch)
1. `py production.py plan` and `py production.py next` → `next_batch.json` (frames, timecodes, files) and `next_batch_mcp.json` (exact requests).
2. Check the Higgsfield balance ≥ batch cost and note it (`before`).
3. Higgsfield MCP `generate_image_batch` with the requests from `next_batch_mcp.json` (index = frame number); wait until all jobs are terminal. Failed jobs are not retried automatically.
4. For every completed job: `py production.py record N JOB_ID URL` → PNG + JSON in `production/frames/` (read-only), QA report and previews in `production/frames/qa/`.
5. Check the balance again (`after`): `py production.py report --batch K --before B --after A` → `production/batch_KK_report.md` and the credit ledger in `state.json`.
6. Show the batch (gallery + QA) to the editor; record decisions with `py production.py decide N accept|accept_fixed|reject`. Re-generations need separate approval.
7. Stop. The next batch is never started automatically.

## Per-frame flow (after approval)
1. Generate through Higgsfield MCP with the exact `prompt`, `params` and references from `prompts.jsonl`.
2. Save the original PNG and a JSON with job id, parameters, reference media ids and prompt.
3. Run `py qa.py <folder>`; read `qa/qa_report.md` and the previews (`*_preview.png`).
4. Use `qa/*_fixed.png` only where QA produced a fixed copy that passes; otherwise decide manually.
5. Composite `GFX` overlays in editing (charts are never drawn by the image model).

## QA (`qa.py`)
- PASS / WARNING / NEEDS_FIX with reason and recommended action; previews show 8% and 10% safe zones, the 15% subtitle band, detected objects and head tops.
- Light plain scenes: measured margins, continuing objects allowed, auto-fix by small scale/shift with modelled background.
- Dark or full-bleed scenes: estimates only → WARNING for manual review; never padded.
- Headroom check for human figures (hats, hair, top of the head); pilot frame #44 is the control case (`py qa.py --selftest`).

## Pilot record
`pilot_v1_manifest.json` (copy of `projects/enginovue_cable_1858/pilot_low_2k/PILOT_v1_manifest.json`): accepted file per frame, SHA-256 of originals and accepted copies, job ids, parameters, references and QA status. Pilot PNGs are marked read-only.

## Render (`render_video.py`, v2 animated)
- `py render_video.py --plan` prints the per-frame motion plan; `--only 1-20` renders a preview; no flag renders the whole episode to `projects/enginovue_cable_1858/render/enginovue_1858_v2_animated.mp4` (+ `.srt`, `render_report_*.md`). The v1 silent render (`enginovue_1858_v1_silent.mp4`) is kept.
- Camera per frame: from the ANIM camera hint, else by shot type (push-in, pull-out, pans, tilts, drift); never the same move twice in a row; static for chart frames and "no push toward edge" notes. Storm frames sway, snap frames get a decaying shake, spark frames a tremor.
- Free local effects: rain + lightning (#75–#77), rising bubbles and motes (underwater frames), lamp / fire / spark flicker; titles and charts fade in; chapter starts (`CHAPTERS`) dip to black.
- AI image-to-video clips are used where `state.json["anim"]` has an accepted clip: #1 and #152, Grok Video 1.5 Lite 720p 4 s, 4 credits each, scaled to 1080p and trimmed to the slot.
- Budget: 200 credits per video in total. This episode: 151 stills × 1.25 + 2 clips × 4 = 196.75 credits.

## House style rules for editor overlays
- Editor titles use the "editorial" style (`titles.py`): white InterDisplay Bold with a soft shadow, optional small letter-spaced second line for "name · place" / "event · date" titles, and a soft local dark glow behind the text. No boxes, no accent bars / border stripes, no full-width bands. Same rule for chart cards and any future lower-thirds.
- Placement is decided per frame, never one fixed spot: `py titles.py propose` suggests the calmest area (edge density), `py titles.py sheet OUT` makes review sheets, `py titles.py set N POS [dx dy]` records a manual decision in `title_layout.json`. Titles must not cover the subject of the frame (faces, the clock on #3, the snapping cable on #121) and stay inside the 8 % safe area, above the bottom subtitle band. Frames with an exact chart carry no title (the chart already shows the number).
- Titles fade in with a 14 px rise after 0.3 s and fade out 0.45 s before the cut.

## Narration (ElevenLabs MCP + local alignment)
- Voice: Ryan – American Documentary Narrator (`GQQpeRnV5mCWTgxKhGo5`, ElevenLabs library voice, no clone), model `eleven_v4`, one take per chapter (11 chapters, 7,644 characters ≈ 7,644 ElevenLabs credits). Chapter texts: `projects/.../audio/narration_chunks.json`; takes: `audio/narration/chNN.mp3` (read-only).
- `projects/.tools/align-venv/Scripts/python.exe align_narration.py` — free, offline faster-whisper word times (no initial prompt: it makes Whisper skip audio). Script text is never changed; recognised words are only time anchors (96–100 % matched). Writes `narration_timing.json` (per-frame start/duration, snapped to 30 fps), `narration_full.wav` (chapters with 1 s pauses), `narration_words.json`.
- `py render_video.py` uses the narration timing and track automatically (→ `enginovue_1858_v3_voiced.mp4`, loudness-normalised); `--silent` renders with the storyboard slot lengths instead.

## Sound (ElevenLabs MCP + local mix)
- Assets (ElevenLabs, Creator plan): 30 spot effects and 8 looping 20 s ambiences (`eleven_text_to_sound_v3`), 3 instrumental music cues 58/250/245 s (`eleven_music_v2_5`) in `projects/.../audio/{sfx,music}` (read-only). Cost: 9,339 ElevenLabs credits (music 8,293).
- `sound_design.json` is the cue sheet: ambience frame ranges, spot effects (frame + offset + gain), chapter whooshes, music cues per chapter group, ducking depth. Times are relative to frame starts, so the mix follows any narration re-timing.
- `py mix_audio.py` → `audio/mix_full.wav` + stems (`stem_music`, `stem_ambience`, `stem_sfx`): loudness-matched to the narration, music/ambience ducked under speech, 2 s music crossfades inside the chapter dips.
- `py render_video.py --remux` reuses the rendered clips and muxes the mix (→ `enginovue_1858_v4_mixed.mp4`, −16 LUFS, limiter). A full render picks up the mix automatically.
- Voice stays on top: spot effects are cut at the end of their own frame (+0.5 s tail, `tail_s` for natural decays) and ducked under speech like music/ambience; a rider keeps the whole bed ≥ 12 dB under the voice while it speaks and ≤ voice average −3 dB in pauses. `mix_audio.py` prints the per-frame voice-over-bed margin (5th percentile; flags frames under 8 dB).
- No frozen picture: AI clips shorter than their slot are slowed with motion interpolation (never a held frame); chart frames and "no push to edge" frames get a barely visible centred move (2.5 %).
- `py check_render.py [video]` — automatic QA of the final file: frozen picture (edge-based, so lamp flicker cannot hide it), unexpected black outside chapter dips, audio gaps, A/V length. Run it before every hand-off.
