# Phase 2 — Production Quality Pilot (ee-0001)

Goal: turn `ee-0001-how-undersea-internet-cables` into a commercially usable English video.
Constraints: no paid API calls, no uploads, no publishing without explicit operator consent;
keep the existing architecture (state machine, DB, artifacts, cached per-scene segments).

## 1. Audit of the MVP render (measured, not guessed)

| finding | evidence |
|---|---|
| Mostly static picture | 314 s of 556 s (56 %) are holds longer than 12 s with zero motion |
| Repetition | 26 scenes use only 10 diagrams; 13 scenes repeat the previous scene's image unchanged (sc005-006, sc010-012, sc015-016, sc018, sc020, sc023-024) |
| Longest dead holds | sc006 route map 25.2 s, sc015 cable laying 24.6 s, sc022 satellites 23.6 s, sc005 21.5 s, sc011 20.5 s, sc001 title 19.8 s |
| No camera language | every frame is a full-frame wide shot; no push-in on the detail being narrated |
| Hard cuts | cuts inside sections; fades only at section boundaries; no crossfades |
| Map defects | route map: chokepoint label collides with a landing station and island; chokepoint lines are not connected to the route network; nothing moves along routes |
| Shorts legibility | diagram text in Shorts is about 16-20 px on a 1080-wide frame (illegible on a phone); top 45 % holds the diagram, middle 40 % is empty |
| Font | Helvetica Neue (system font, licence unknown for video) blocks approval |
| Narration | mock (silent) or macOS `say` (licence: personal, non-commercial) blocks approval |
| Claims | 21/21 unverified, 5 cited only to Wikipedia (secondary) |

## 2. Workstreams

| # | task | approach | output |
|---|---|---|---|
| A | Font → Inter | download official Inter release (rsms/inter, SIL OFL 1.1), vendor into `assets/fonts/inter/` with `LICENSE.txt` + sha256; font is first candidate; manifest record `font-main` = cleared with proof (licence text + URL + hash) | font cleared |
| B | ElevenLabs provider | real client behind `STUDIO_ENABLE_PAID_PROVIDERS` + API key + `--i-consent-to-spend` + BudgetGuard; uses the *with-timestamps* endpoint; character alignment → word timings → SRT. Tested with a fake transport only (no network). Also: word-timing source recorded per track (`provider_alignment` vs `estimated`) and review warns when captions are estimated | provider + tests, **no paid call** |
| C | Claim verification | fetch each source (prefer primary sources over Wikipedia), extract **verbatim** supporting fragments; verdict `supported / partially / not_supported / not_checked` + proposed rewording. Nothing is marked `verified` automatically; new `studio claim apply-proposal` copies a proposed snippet only when the operator passes `--by` | `research/verification_report.md/json` |
| D | Motion engine | per-frame renderer piping raw frames to FFmpeg (no new deps): eased camera moves (push-in/pan/focus on a region), element animations (line draw-on, fade/scale-in, pulses travelling along routes), 0.5 s crossfades between scenes, still holds kept cheap. Cache per scene stays. Storyboard gets `camera` + `focus` per scene; repeated scenes get distinct framing | new `studio/motion.py`; `render.py` uses it |
| E | Visual variety | fix map layout; animated route drawing + data pulses; new diagrams (attenuation, EDFA inside, latency race fibre vs GEO, 1858 timeline hook) | fewer repeated shots, no hold > 8 s without motion |
| F | Shorts | diagram crop + scale per Short (focus box), minimum text ≥ 40 px at 1080 width, safe zones (top 12 %, bottom 22 %, right 12 %), automatic `legibility_issues` check + phone-scale contact sheet | readable Shorts |
| G | Licence audit | every output ingredient listed (diagrams, font, music bed, narration, FFmpeg toolchain); anything not commercially clear blocks approval | `review/LICENSE_AUDIT.md` |
| H | Review package | `review/package/`: long MP4, 3 Shorts, thumbnail, script, source report, BLOCKERS.md, licence audit | final package |

## 3. Order
A → D/E (engine) → F → B → C (runs in parallel from the start) → re-render → G → H → tests + smoke.

## 4. Known remaining blockers after Phase 2 (expected)
- Human verification of claims (by design).
- Commercial narration: operator's own recording or an approved ElevenLabs run.
- AI-disclosure answer by the operator.
