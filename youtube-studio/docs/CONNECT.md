# Connecting paid and external services

Everything below is implemented and tested offline (fake clients). Nothing is connected,
nothing has been sent, nothing has been spent. Check the state any time:

```bash
uv run studio connect status        # readiness per service; never prints secret values
```

Common safety rails for every paid call: `STUDIO_ENABLE_PAID_PROVIDERS=1` in `.env`,
an explicit `--i-consent-to-spend` per command, a BudgetGuard preflight under the monthly
cap ($250 default), a hard ceiling on the size of the request ("arming"), and the real cost
written to the ledger (`studio cost report`). `--dry-run` always shows the estimate first.

## 1. ElevenLabs narration (paid) — see also docs/RC-ee-0001.md

| you do | then run |
|---|---|
| Subscribe to **Starter** ($6/month, first month $1; commercial licence) | — |
| Create an API key in the ElevenLabs dashboard | add `ELEVENLABS_API_KEY=…`, `ELEVENLABS_PLAN=starter`, `STUDIO_ENABLE_PAID_PROVIDERS=1` to `.env` |
| — | `studio voices check` (free GET, labels + preview links) → `studio voices use wyatt` |
| — | `studio cost tts ee-0001` and `studio voice ee-0001 --provider elevenlabs --dry-run` |
| say "go" | `studio voice ee-0001 --provider elevenlabs --i-consent-to-spend`, then Shorts with the same flag |

Cost for ee-0001 + 3 Shorts: ~8.5k characters ≈ 11 % of one Starter month.

## 2. Claude drafts — Anthropic API (paid)

Drafts only: `authoring/script.draft.yaml`, `authoring/shorts.draft.yaml`,
`projects/ideas_<channel>.draft.yaml`. The model only sees your research claims, may cite
only those ids, may not add numbers that are not in a claim, and every draft is re-checked
by `studio author check`. Nothing enters the pipeline until you rename the file.

| you do | then run |
|---|---|
| Create an API key at platform.claude.com (a Claude Pro/Max subscription is **not** API credit) and add billing | `uv sync --extra llm`; `ANTHROPIC_API_KEY=…` in `.env` (or `ant auth login`) |
| — | `studio draft script <ep> --dry-run` (shows prompt size and worst-case cost) |
| say "go" | `studio draft script <ep> --i-consent-to-spend` |

Default model `claude-opus-5-5` ($4 / $20 per 1M tokens in/out), effort `high`;
override with `STUDIO_LLM_MODEL` / `STUDIO_LLM_EFFORT`. Worst case per script draft
≈ $0.33 (16k output tokens); typical is lower. Refusals fall back server-side to
Anthropic's recommended model (`fallbacks: "default"`); a refusal or truncated answer writes
nothing but is still recorded in the ledger.

## 3. YouTube upload (free, quota-limited) and Analytics

Uploads are **always private**; publishing is a separate command that requires retyping
the episode id. Without OAuth, `studio publish` exports a manual-upload folder instead.

| you do | then run |
|---|---|
| Google Cloud Console: create a project, enable **YouTube Data API v3** and **YouTube Analytics API**, OAuth consent screen (External, add yourself as test user), create an **OAuth client ID → Desktop app**, download the JSON | `uv sync --extra youtube`; `.env`: `STUDIO_ENABLE_YOUTUBE=1`, `YOUTUBE_CLIENT_SECRETS_FILE=/path/client_secret.json` |
| Put the channel id in `channels/<channel>.yaml` → `youtube_channel_id` | `studio connect status` |
| Approve the episode (`studio decide … approve`) | `studio publish <ep>` → browser consent once; uploads video + captions + 3 Shorts, all private |
| Later | `studio analytics --channel engineering_explained --api` (views, watch time, retention, subs) |

Scopes requested: `youtube.upload`, `youtube.readonly`, `youtube.force-ssl` (captions),
`yt-analytics.readonly`. The token is stored with mode 600 under
`projects/.secrets/` (git-ignored). Default quota is 10,000 units/day; one episode with
captions and three Shorts uses about 8,000. Impressions and CTR still come from the
Studio CSV export (`--import-csv`).

## Free features that need no connection

| feature | command |
|---|---|
| hand-written episodes | `studio author init <ep>` → edit YAML → `studio author check <ep>` |
| your own narration | `studio voice <ep> --provider file --file voice.wav` (sentence-aligned to pauses) |
| licensed music (e.g. YouTube Audio Library) | `studio assets add <ep> track.mp3 --id music-track --kind music --author "…" --license "…" --proof <url-or-screenshot> --clearance cleared [--attribution "…"]` |
| thumbnail variants | `studio thumbnail <ep> --hook "2-5 words"` |
| chapters + description | written by `studio review` to `review/description.txt` |
| diagrams without code | `diagram_specs/*.yaml`, `studio diagrams check` |
