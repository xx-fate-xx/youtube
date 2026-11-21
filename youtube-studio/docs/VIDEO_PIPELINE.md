# Video pipeline (`studio pipe`)

From a topic (or a competitor video used only as a starting point) to a finished, fact-checked,
animated and narrated video with a release kit. Code: `studio/pipeline/`. Claude runs it with the
`/make-episode` skill (`.claude/skills/make-episode/SKILL.md`); the operator only approves twice.

## Layout
| Where | What |
|---|---|
| `episodes/<slug>/` (git) | `episode.yaml` settings, `frames.txt` storyboard + script, `characters.yaml`, `sounds.yaml`, `overlays.py` (exact charts), `title_layout.json`, `factcheck_report.md`, derived prompts/storyboard/timeline |
| `projects/<slug>/` (ignored) | `input/` reference material, `production/` frames + state + ledger, `audio/` takes, sounds, mix, `render/`, `release/` |
| `studio/pipeline/styles/` | channel visual styles (prompt building blocks) |

## Stages and checkpoints
1. Brief — `studio pipe new <slug> --title "..."`; reference text to `projects/<slug>/input/`.
2. Research + original script in `frames.txt`, fact-check report, `studio pipe build`.
3. `studio pipe originality` — fails if wording was carried over from the reference (≤ 2 % shared 8-word sequences, no shared run of 12+ words).
4. `studio pipe preflight` → **checkpoint 1: the operator approves the script and the cost** → `studio pipe approve`.
5. Images: `pipe next` (Higgsfield MCP batches) → `pipe record` (QA) → `pipe decide` → `pipe report`.
6. AI clips for `AI_CLIP` frames → `pipe record-clip`.
7. Narration: `pipe chunks` → ElevenLabs takes → `pipe save-audio narration K URL` → `pipe align`.
8. Sounds: `pipe sounds` → ElevenLabs effects/ambiences/music → `pipe save-audio ...` → `pipe mix`.
9. Titles: `pipe titles propose|sheet|set`.
10. `pipe render` (preview with `--only a-b`) → `pipe check`.
11. `pipe release` → **checkpoint 2: the operator watches and uploads as Private first.**

`studio pipe status -e <slug>` shows the state of every stage; every step is resumable.

## frames.txt
```
#12 | 0:40 | B | close | thomson | h | William Thomson · Glasgow
RU: короткое описание кадра
VO: narration for this shot (approved script; the pipeline never rewrites it)
SCENE: English scene core for the image prompt
ANIM: motion || camera || what stays still          (every 5th shot)
GFX: overlay_id                                     (exact chart from overlays.py)
CHAPTER: Chapter title                              (narration chunk, dip to black, YouTube chapter)
TITLE: main line | small line                       (on-screen title; overrides the header column)
FX: rain, bubbles, lightning@1.3, sparks, fire, lamp, nolamp
CAMERA: push_in | pull_out | pan_lr | pan_rl | tilt_up | tilt_down | drift | sway | snap | settle
AMB: ambience_id | -                                (persists until changed; "-" stops it)
SFX: sfx_id @0.3 -4dB [max=5] [tail=1.2]; other_id @0
MUSIC: music_id [-1dB]                              (runs to the next MUSIC or the end)
AI_CLIP: yes
```

## Built-in rules
- Images: 8 % safe margins, calm bottom 15 % for subtitles, whole heads with headroom, period-accurate eras, no text in images; QA flags violations.
- Render: 1920×1080, 30 fps, H.264; varied camera moves, never the same twice in a row, never a frozen picture (AI clips are slowed with motion interpolation); chapter dips to black.
- Titles: editorial style (no boxes or accent bars), placed per frame, never over the subject.
- Sound: assets loudness-matched to the voice; music, ambiences and effects ducked; a rider keeps the bed ≥ 12 dB under the voice while it speaks; a spot effect never outlives its own shot.
- QA of the final file: frozen picture (edge-based), unexpected black, audio gaps, A/V length.
- Money: no paid call without the recorded approval; every batch is ledgered from the balance.

## Environment
`py -m venv .venv && .venv/Scripts/python -m pip install -e . pytest ruff numpy fonttools` (Windows);
FFmpeg on PATH. Word alignment uses a separate venv with faster-whisper, created automatically on first
`pipe align` (`projects/.tools/align-venv`).

## Regression
The 1858 cable episode was migrated without changes: prompts, storyboard, timeline, render plan, sound
design, title placement, narration timing, every audio stem, captions and a rendered preview are
byte-identical to the output of the original per-episode scripts.
