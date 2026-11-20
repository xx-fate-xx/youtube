# Enginovue Visual Pipeline v1.0

Adopted 2026-11-20 after the 6-frame pilot (#12, #25, #41, #44, #47, #57). No further model comparisons are planned.

## Generation standard
| Setting | Value |
|---|---|
| Provider | Higgsfield **MCP** (the CLI is blocked on this account: `only_mcp_usage_on_trial_is_available`) |
| Model | `gpt_image_2_6` |
| Quality / resolution | `low` / `2k` → 2688×1520 output, downscaled to 1920×1080 (≈1.4× zoom reserve) |
| Aspect ratio | `16:9` |
| Price | 0.5 credit per frame (152 frames ≈ 76 credits) |
| Mascot references | `refs/octopus_engineer.png`, `refs/lynx_analyst.png`, `refs/bit_robot.png` (original files; hashes in `pilot_v1_manifest.json`) |
| Historical people | text identity specs (`characters_historical.md`, source: `HISTORICAL` in `build.py`); no paid reference sheets yet |

Rules: no paid call without explicit approval per batch; no automatic regeneration on QA warnings; original PNGs are never overwritten.

## Source of truth and build
1. Edit `frames.txt` (scenes, VO, shots, characters, `GFX:` overlays) and the tables in `build.py` (style, composition rules, character specs).
2. `py build.py` regenerates `prompts.jsonl`, `prompts.md`, `storyboard.md`, `edit_timeline.csv`, `voiceover_elevenlabs.txt`, `characters_historical.md`, `overlays/*_gfx.svg|png`.
3. Never hand-edit the derived files. Timecodes (152 frames, 8:19) must stay unchanged.

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
