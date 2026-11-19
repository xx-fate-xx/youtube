# ADR-001: Local-first architecture for AI YouTube Studio

- Status: accepted (MVP)
- Date: 2026-11-18

## Context

Three distinct editorial channels need a production assistant that a human editor drives
step by step: research → script → storyboard → assets → narration → render → shorts →
review → private upload → analytics. Hard requirements: no silent spending, no automatic
publishing, no invented sources, an auditable research and licence trail, and a pipeline
that works with zero paid APIs.

## Decision

1. **Plain Python 3.12 package (`studio/`) + Typer CLI.** No web server, no background
   daemon. Every step is an explicit CLI command an operator runs and can re-run.
2. **Two storage layers.**
   - SQLite (SQLModel) holds *control state*: episodes, the state machine, the transition
     log, job runs (for resumability), the cost ledger, analytics rows.
   - The episode folder `projects/<channel>/<episode-id>/` holds *editorial artifacts* as
     human-readable JSON/Markdown (research pack, script, storyboard, asset manifest,
     narration timings, review package). Every write is atomic (temp file + `os.replace`).
3. **Explicit state machine** (`studio/state.py`): `idea → research → script → storyboard →
   assets → rendered → review_pending → approved → private_uploaded → published → analyzed`,
   plus a small set of named rework edges (e.g. `review_pending → script`). Anything else
   raises `IllegalTransition`. Every transition is logged with actor + note.
4. **Provider interfaces with offline defaults.** `LLMProvider`, `VoiceProvider`,
   `FootageProvider`, `YouTubeClient` are protocols. Defaults are offline:
   `MockLLMProvider` (curated sample fixtures / clearly-marked placeholders — it never
   invents facts), `MockVoiceProvider` (silent placeholder track with estimated timings),
   `MacOSSayVoiceProvider` (local, free, *preview-only licence*), `UserRecordingVoiceProvider`.
   Paid providers must pass the `BudgetGuard` preflight (feature flag + explicit consent +
   monthly cap) before any network call.
5. **Visuals are code-generated vector diagrams.** A tiny `Canvas` abstraction emits both
   an editable SVG (the source asset) and a PNG raster via Pillow, so there is no Cairo /
   librsvg system dependency. Diagrams support build steps for restrained motion.
6. **FFmpeg does only simple, portable things**: still-image concat, fades, x264/AAC encode,
   audio ducking. All text (captions, cards, badges) is rasterised by Pillow, so the
   pipeline does not depend on FFmpeg being built with libass/freetype. FFmpeg is located via
   `STUDIO_FFMPEG` → `PATH` → the `imageio-ffmpeg` bundled binary.
7. **Safety guards are structural, not advisory.**
   - `YouTubePublisher.upload()` has no visibility parameter; it always sends `private`.
     Changing visibility is a separate method requiring the operator to retype the episode id.
   - Upload requires an `approved` review decision whose recorded video SHA-256 matches the
     file being uploaded.
   - Approval is refused while any referenced claim is not `verified`, any asset is not
     cleared for commercial use, or narration is a placeholder / preview-only licence.
8. **Resumability.** Each step records a `JobRun` with an input hash; render segments are
   cached by content hash so an interrupted render resumes instead of restarting.

## Consequences

- The MVP output is motion-graphics explainers (diagrams + cards + optional user B-roll),
  not AI video. This is deliberate and stated in the UI.
- macOS `say` voices are only licensed for personal, non-commercial use under the macOS
  licence, so they are marked `restricted` and block approval; final narration must be the
  operator's own recording or a licensed TTS provider.
- Word-level timing from mock/`say` providers is *estimated* (sentence-exact for `say`,
  word positions interpolated). The `timing_method` field records this honestly.
- YouTube OAuth code is behind `STUDIO_ENABLE_YOUTUBE=1` and is untested until real
  credentials are connected; without credentials `publish` exports a release folder.
