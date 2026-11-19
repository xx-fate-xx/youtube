# Phase 2 — Production Quality Pilot: report (ee-0001)

Date: 2026-11-18. No paid API calls, no uploads, nothing published. Cost ledger: $0.00.

## 1. Visual audit — before / after

Measured on the full render (2 samples/s, bottom caption band excluded; a frame counts as
"static" when the mean pixel change vs the previous sample is < 0.15/255).

| metric | MVP render | Phase 2 render |
|---|---|---|
| time with any picture change | 7 % | 100 % |
| holds > 8 s with no motion | 17 | 0 |
| longest static hold | 18.5 s | 0.5 s |
| distinct diagrams | 10 | 16 (+ animated title, chapter card) |
| scenes repeating the previous image unchanged | 13 | 0 (continuations now advance a step or move the camera) |
| transitions | hard cuts + section fades | 0.6 s crossfades inside sections, dips between sections, continuous camera on continuation scenes |

Defects fixed in the audit: route-map chokepoint label colliding with a station and an island;
chokepoint lines not connected to anything; diagram labels at 16–20 px inside Shorts; HUD
title strip covered by zoomed content.

New diagrams: `atlantic_telegraph` (cold open), `landing_station` (+ narrow corridors),
`route_diversity`, `edfa_inside`, `quake_landslide`, `satellite_roles`.

## 2. Font

Helvetica Neue replaced by **Inter 4.1** (rsms/inter release v4.1, SIL OFL 1.1), vendored in
`assets/fonts/inter/` with `LICENSE.txt` and `SOURCE.json` (archive URL + SHA-256, per-file
SHA-256, key clause: *"The requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives."*). Manifest record
`font-main` is `cleared`; any change to the font files is detected (`sha256 mismatch`).

## 3. ElevenLabs

`ElevenLabsVoiceProvider` is implemented against the official docs (checked 2026-11-18):
`POST /v1/text-to-speech/{voice_id}/with-timestamps?output_format=pcm_22050`, header
`xi-api-key`, `previous_text`/`next_text` for continuity, character alignment → word timings
→ SRT. Retries 429/5xx with backoff, never retries 400/401/402/403/422. Cached per sentence
(audio + alignment), so re-renders cost nothing.

Guards: flag + key + `--i-consent-to-spend` + BudgetGuard cap + `arm(max_chars)` ceiling.
Tested only with a fake transport — **no request has been sent**.

Facts from the docs: multilingual v2 / v4 API price $0.08 per 1,000 characters → this
episode (~7.4k chars) ≈ $0.60, three Shorts (~1.3k chars) ≈ $0.11. Commercial use requires a paid plan at
generation time ("The free plan does not include a commercial license"); Starter is the
cheapest plan with a commercial licence.

## 4. Source verification

See `research/VERIFICATION_REPORT.md` (per claim: wording, URL, verbatim fragment, verdict,
proposed rewording). Summary: 14 supported, 7 partially supported, 0 unsupported. Every
snippet was re-fetched independently and matched verbatim (C4 in the arXiv PDF full text).
**No claim is marked verified**; each needs `studio claim apply-proposal ... --by NAME`.

Narration changed where sources did not support the wording: 1858 "minutes instead of
weeks" (unsupported; early telegraph was slow) → "without travelling on a ship"; copper →
"a conductor" / "copper or aluminium"; cable "tanks" → "holds", payout-vs-speed → "slow and
steady"; repair buoy/testing detail removed; ICPC attribution → TeleGeography; 2006 Taiwan
wording aligned with the peer-reviewed abstract; satellites for "ships, aircraft and backup"
→ "places not yet wired" and "one source to many locations"; "fibre pairs" removed.

Weak spots for the human reviewer: C1/C3/C5/C7/C8/C11/C12/C14/C15/C18/C19 rest on Wikipedia;
C17 rests on a news report of the ITU/ICPC advisory-body report (cite the report itself).

## 5. Shorts on a phone

All labels ≥ 42 px on the 1080×1920 frame (≈ 15 pt on a phone shown 390 pt wide); captions
58 px; content kept out of the top bar, bottom title area and right button column. Automatic
`legibility_issues` (size / cut by frame / overlap) is empty for all three Shorts and is a
review blocker if it is not.

## 6. Licences

`review/LICENSE_AUDIT.md`: diagrams/cards/title (original code), music bed (original sine
synthesis), Inter (OFL) — cleared. Narration (macOS `say`) — restricted: personal,
non-commercial; blocks approval. No stock, third-party music, maps, logos or footage.
