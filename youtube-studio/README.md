# AI YouTube Studio (MVP)

A local-first production assistant for three distinct explainer channels
(**Business Uncovered**, **Engineering Explained**, **AI Workflow Lab** – working titles).
It helps a human editor research, script, illustrate, narrate, render, review and package
original videos plus up to three independently written Shorts per episode.

It does **not** publish anything on its own. Uploads are always `private`, need an approved
review artifact, and changing visibility is a separate explicit operator action.

Architecture: [docs/ADR-001-architecture.md](docs/ADR-001-architecture.md) ·
Plan: [docs/MVP-PLAN.md](docs/MVP-PLAN.md)

## Mac setup

```bash
# 1. uv (Python manager) - skip if installed
curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Dependencies (Python 3.12 is fetched by uv). FFmpeg is bundled via imageio-ffmpeg.
cd youtube-studio
uv sync
# Optional: a system FFmpeg is used automatically if present
#   brew install ffmpeg
# 3. Configuration (optional; defaults are safe: mock providers, no paid calls, no upload)
cp .env.example .env
# 4. Check
uv run studio init
uv run pytest -q
```

## Workflow (actual commands)

```bash
uv run studio ideas --channel engineering_explained --count 10
uv run studio episode create --channel engineering_explained \
    --topic "How undersea internet cables work" --minutes 9
uv run studio research ee-0001            # sources + per-claim citations (all unverified)
uv run studio claim list ee-0001
uv run studio claim verify ee-0001 C11 --snippet "<exact text from the source>" --by "Your Name"
uv run studio claim import-proposals ee-0001 samples/undersea_cables/verification_proposals_rc.json
uv run studio claim review ee-0001        # interactive: you confirm each claim (y/n/s/q)
uv run studio claim report ee-0001        # research/VERIFICATION_REPORT.md (proposals only)
uv run studio claim apply-proposal ee-0001 C19 --by "Your Name" [--accept-rewording]
uv run studio script ee-0001              # narration with claim ids; numbers need citations
uv run studio storyboard ee-0001          # scene-by-scene plan
uv run studio assets build ee-0001        # SVG + PNG diagrams, licence manifest
uv run studio assets check ee-0001        # exit code 2 if any licence blocks approval
uv run studio voice ee-0001 --dry-run     # cost preflight only
uv run studio voice ee-0001               # mock | --provider macos_say | --provider file --file my.wav
uv run studio render ee-0001 --preview    # burned captions + review badges
uv run studio render ee-0001              # clean master (+ .srt + thumbnail draft)
uv run studio shorts ee-0001 --count 3    # 1080x1920, independent scripts, captions
uv run studio review ee-0001              # REVIEW.md, LICENSE_AUDIT.md, review/package/
uv run studio decide ee-0001 approve --reviewer "Your Name" --ai-disclosure no
uv run studio publish ee-0001             # private upload, or a release folder without OAuth
uv run studio record-upload ee-0001 <video-id>     # after a manual private upload
uv run studio visibility ee-0001 --status public --confirm <full-episode-id>
uv run studio analytics --channel engineering_explained --days 30 [--import-csv export.csv | --mock]
uv run studio cost report
uv run studio cost preflight ee-0001
uv run studio episode show ee-0001        # state + full transition history
```

Episode ids accept a unique prefix (`ee-0001`). Every command is safe to re-run.

Full end-to-end smoke test in a throwaway folder (zero spending):

```bash
./scripts/smoke_test.sh                  # silent placeholder narration
VOICE=macos_say ./scripts/smoke_test.sh  # listenable local preview
```

## State machine

`idea → research → script → storyboard → assets → rendered → review_pending → approved →
private_uploaded → published → analyzed`, plus named rework edges (e.g. `review_pending →
script`). Illegal transitions raise `IllegalTransition`; every change is logged.

## What blocks approval (by design)

- any cited claim not `verified` (verification requires the exact source snippet + a name);
- numbers/dates in narration without a claim id; placeholder script text;
- any asset without licence + proof + `cleared` status, or a file changed after recording;
- placeholder narration, or narration with a preview-only licence (macOS `say`);
- no master render, or runtime outside the channel's 8–15 min;
- Shorts outside 20–60 s, sharing a composition, or copying >12 % of long-script phrasing;
- the operator not answering the AI-disclosure question.

## Files per episode

`projects/<channel>/<episode-id>/`

| folder | contents |
|---|---|
| `research/` | `research_pack.json`, `sources.md` (claims table with status) |
| `script/` | `script.json`, `script.md` (claim status inline) |
| `storyboard/` | `storyboard.json`, `storyboard.md` |
| `assets/` | `svg/*.svg` (editable sources), `rendered/*/step_*.png`, `asset_manifest.json` |
| `audio/` | `narration.wav`, `narration.json` (scene + word timings), sentence cache, music bed |
| `render/` | `<id>_preview.mp4`, `<id>_master.mp4`, `<id>.en.srt`, `thumbnail_draft.png` |
| `shorts/` | one folder per Short: MP4, `.srt`, `metadata.json` |
| `review/` | `REVIEW.md`, `checklist.json`, `decision.json`, decision history |
| `release/` | upload receipt or manual-upload package |

## Providers

| kind | default | optional |
|---|---|---|
| LLM | `MockLLMProvider` – curated sample fixtures or clearly-marked placeholders; never invents facts | paid LLM (not connected) |
| Voice | `MockVoiceProvider` – silent placeholder, estimated timings | `macos_say` (free, preview-only licence), `file` (your recording), ElevenLabs (implemented, guarded, exact word timings; never called without flag + key + `--i-consent-to-spend`) |
| Visuals | code-generated diagrams/cards | `studio assets add` for your own / Pexels footage with licence proof |
| YouTube | release folder | OAuth upload (`STUDIO_ENABLE_YOUTUBE=1`, `uv sync --extra youtube`) |

## Connecting services

All paid/external integrations are implemented but switched off; see
[docs/CONNECT.md](docs/CONNECT.md) and `studio connect status`. Free extras: hand-written
episodes (`studio author init|check`), pause-aligned own narration, chapters/description,
thumbnail variants (`studio thumbnail`), licensed music import.

## Diagram library

New diagrams are YAML, not code: `diagram_specs/<id>.yaml` with one of seven templates
(map, cross_section, process, comparison, timeline, flow, stat). See
[docs/DIAGRAM-LIBRARY.md](docs/DIAGRAM-LIBRARY.md); `studio diagrams list|check|preview`.

## Motion engine (Phase 2)

Frames are rendered per scene with Pillow and piped to FFmpeg (`studio/motion.py`):
eased camera moves that follow what the narrator introduces, staggered draw-on / grow /
fade reveals, pulses travelling along cables, 0.6 s crossfades inside a section and dips
between sections. Build steps start on sentence boundaries. Per-scene camera hints in the
script: `camera: auto | static | wide | focus:x,y,w,h|x,y,w,h`. Segments are cached and
rendered in parallel (`STUDIO_RENDER_WORKERS`).

Shorts use the same engine with a phone-safe layout: labels are enlarged to at least 42 px
(about 15 pt on a phone), reflowed to stay inside the frame and the button column, pushed
apart if they touch; `legibility_issues` blocks approval if anything is still too small,
cut or overlapping.

## ElevenLabs (optional, paid)

Not used unless you set `STUDIO_ENABLE_PAID_PROVIDERS=1`, `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID`, `ELEVENLABS_PLAN` and pass `--i-consent-to-spend`. The provider is
"armed" with exactly the preflighted character count. It calls `with-timestamps` and turns
the character alignment into word timings, so captions follow the real voice. Commercial
use needs a paid plan at generation time (free plan output is marked `restricted`).

```bash
uv run studio voice ee-0001 --provider elevenlabs --dry-run            # estimate only
uv run studio voice ee-0001 --provider elevenlabs --i-consent-to-spend # real, paid
```

## Known limitations

- Caption word timings are estimated (sentence-exact with `macos_say`); use your own
  recording plus forced alignment for frame-accurate captions.
- Visuals are motion-graphics stills with build steps and fades; there is no AI video
  generation. Diagram labels are small when reused inside Shorts.
- The YouTube OAuth client is written but **untested** until real credentials are connected.
- Rendered text uses the bundled Inter 4.1 (SIL OFL 1.1, `assets/fonts/inter/`, hashes in
  `SOURCE.json`). A system fallback font would be flagged `unknown`.
- YPP/AdSense eligibility is out of scope and treated as a separate compliance question.
