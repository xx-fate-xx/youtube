# MVP plan (incremental)

| # | Increment | Modules | Done when |
|---|-----------|---------|-----------|
| 1 | Skeleton: config, `.env` loading, atomic file IO, SQLite, models | `config.py`, `fsutil.py`, `db.py`, `models.py` | `studio init` creates DB + folders |
| 2 | Channels: 3 distinct YAML style profiles | `channels/*.yaml`, `channels.py` | `studio channels list` |
| 3 | Episode lifecycle + state machine + transition log | `state.py`, `episodes.py` | illegal transitions raise; tests |
| 4 | Budget guard + cost ledger | `budget.py` | paid call w/o flag/consent/cap is refused; tests |
| 5 | Research pack with per-claim citations + human verification | `research.py`, `providers/llm.py` | unverified claims listed as blockers |
| 6 | Script + storyboard (mock LLM / sample fixture) | `editorial.py`, `storyboard.py` | word count + citation checks |
| 7 | Vector diagrams (SVG + PNG), cards, asset licence manifest | `visuals.py`, `diagrams/`, `assets.py` | `assets check` passes for generated assets |
| 8 | Narration providers + timings + SRT | `providers/voice.py`, `audio.py`, `captions.py` | WAV + timings + `.srt` |
| 9 | FFmpeg renderer (1920x1080, captions burn-in preview, music ducking, thumbnail) | `render.py`, `ffmpeg.py` | MP4 plays, duration matches narration |
| 10 | Shorts (1080x1920, independent scripts, originality check) | `shorts.py` | 3 shorts rendered with captions |
| 11 | Review package + approve/reject/needs_changes | `review.py` | blockers prevent approval |
| 12 | Publish: private-only upload guard, release-folder export | `publish.py`, `providers/youtube.py` | tests prove private-only |
| 13 | Analytics (CSV import + mock) + cost report | `analytics.py` | channel comparison report |
| 14 | Tests + smoke test on the Engineering Explained pilot | `tests/`, `scripts/smoke_test.sh` | all green |

Out of scope for MVP (proposed later, each behind budget preflight): Anthropic API LLM
provider, ElevenLabs voice, paid image generation, Pexels search API, YouTube Analytics API.
