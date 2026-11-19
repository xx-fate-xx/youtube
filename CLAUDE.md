# AI YouTube Studio — Claude Code implementation brief

## Product goal
Build a LOCAL-FIRST, production-grade content production assistant for three **distinct** English-language YouTube channels. It helps a human editor research, script, illustrate, narrate, render, review and upload original documentary/explainer videos, plus up to three independently edited Shorts per long video. It is **not** a content-spam bot. Never automatically publish or mass-produce materially repetitive videos. All uploads must start as private drafts and require explicit human approval to schedule or publish.

## Initial channels
1. **Business Uncovered** — well-sourced business-model and corporate-history documentaries (8–15 min). Clear original business analysis, avoid stock investment advice.
2. **Engineering Explained** — physical engineering, infrastructure, inventions (8–15 min). Prioritize accurate diagrams and mechanisms over generic image montages.
3. **AI Workflow Lab** — genuine, repeatable AI automation tutorials for small-business workflows (8–15 min), using authentic screen recordings and tests; never fabricate tool capabilities or demos.

Names are working titles; do not assume YouTube handles are available. Default language en-US. Generate a *separate editorial style profile* per channel, including tone, storytelling structure, narration settings, and visual identity. Avoid cross-posting the same narrative to multiple channels.

## MVP scope (build before adding any paid API integration)
- Python 3.12+, typed modules, `pyproject.toml`, `uv` optional, `ruff`, `pytest`, Pydantic v2, SQLite via SQLAlchemy or SQLModel, Typer CLI.
- A local project and episode database, project directories, atomic saves, resumable job state, and cost ledger.
- Research pack with per-claim citations: source URL, title, date accessed, claim text, supporting snippet/notes, verification status. Research may propose topics, but must not invent citations. Claims marked `unverified` block final approval.
- Original editorial outline, 1,200–2,200 word scripted narration depending on target runtime, scene-by-scene storyboard and asset manifest. Do not invent quotes, numerical facts, or product capabilities.
- Voice provider interface (`MockVoiceProvider` by default; optional ElevenLabs integration after API key and cost preflight). Preserve timestamps and spoken-word alignment.
- Visual provider interface: locally supplied licensed footage, user-created SVG charts and diagrams, permitted commercial-use stock, optional paid image generation later. Keep an asset license manifest with author/source, download timestamp, license/permission proof, and attribution requirements.
- Local video renderer using FFmpeg: 1920x1080 landscape output, mixed soundtrack with narration priority, captions/subtitles as separate `.srt` and optional burned-in preview, scene cards, restrained transitions, thumbnail draft. First version may be motion graphics + manually supplied B-roll; do not pretend it supports full AI video generation.
- Shorts generator: 1080x1920; independent 20–60 second narration scripts, distinct opening hooks and compositions, clear linkage to long video; never simply crop arbitrary footage without editorial adaptation.
- Review package: preview MP4, script and sources, all assets/license proofs, factual/visual/copyright/AI-disclosure checklists, estimated/actual cost and operator approve/reject/needs_changes actions.
- YouTube OAuth integration behind a feature flag. `upload` always defaults to `private`; separate explicit operator action controls any `scheduled` or `public` state. Record channel mapping and remote video IDs; never print credentials or tokens. If no credentials, create a local publish-ready package instead.
- Analytics: pull legitimate creator statistics if OAuth permits; otherwise accept CSV export. Store per-video impressions, CTR, average view duration, audience retention where available, traffic sources, subscribers gained, views and production cost. Produce a channel comparison report.
- Budget guard: default `monthly_usd=250`, per-episode preflight, no paid call without consent/feature flag, a hard stop before exceeding monthly cap, daily and monthly usage logs. Pro subscription is *not* an Anthropic API entitlement.

## Suggested repo layout
```
youtube-studio/
  pyproject.toml
  .env.example
  README.md
  channels/
    business_uncovered.yaml
    engineering_explained.yaml
    ai_workflow_lab.yaml
  studio/
    cli.py
    config.py
    models.py
    db.py
    research.py
    editorial.py
    storyboard.py
    assets.py
    audio.py
    captions.py
    render.py
    shorts.py
    review.py
    publish.py
    analytics.py
    budget.py
    providers/
      llm.py
      voice.py
      footage.py
      youtube.py
  projects/
  tests/
```

## Workflow / CLI UX
Provide commands (exact CLI names are suggestions, document actual ones):
- `studio init`
- `studio ideas --channel engineering_explained --count 10`
- `studio episode create --channel engineering_explained --topic "How undersea internet cables work"`
- `studio research <episode-id>` (human source verification required)
- `studio script <episode-id>`
- `studio storyboard <episode-id>`
- `studio assets check <episode-id>`
- `studio voice <episode-id> --dry-run`
- `studio render <episode-id> --preview`
- `studio shorts <episode-id> --count 3`
- `studio review <episode-id>`
- `studio publish <episode-id> --private` (never public by default)
- `studio analytics --channel engineering_explained --days 30`
- `studio cost report`

Track the explicit state transition `idea -> research -> script -> storyboard -> assets -> rendered -> review_pending -> approved -> private_uploaded -> published -> analyzed`. Prevent illegal transitions and refuse upload without an approved review artifact. Make provider calls idempotent or safely retryable.

## Editorial and platform constraints
- Create useful, original educational content, NOT low-effort quote compilations, mass-produced repetitive videos, or scraped creator footage.
- All factual claims must have traceable sources; any missing evidence is visibly marked and held for review.
- Protect copyright: do not assume images, music, book text or competitor clips may be reused. Pexels stock can be used in transformed original videos subject to its license; YouTube Audio Library tracks may have attribution conditions.
- Do not clone a real person's voice, imply invented interviews are authentic, or fabricate real screen recordings.
- Prompt operator to consider YouTube disclosure for realistic AI-generated/altered media. An AI narrator alone does not mean every video necessarily needs the same disclosure; apply current YouTube rules.
- Follow YouTube anti-spam policies and API limits. Don't use bought views/subscribers, deceptive geolocation, or fake AdSense identity.
- No implementation should assume that a US phone number, US LLC, or a U.S.-targeted audience grants YPP eligibility. Treat YPP/AdSense readiness as an independent compliance blocker; production and audience building may proceed separately.

## Delivery requirements
1. First inspect working directory and user environment. Do not overwrite existing files.
2. Write a short architecture decision record and step-by-step MVP plan, then implement the MVP incrementally.
3. Implement **mock/offline providers first**, with at least one complete renderable demo episode using locally generated SVG visuals, an existing user-provided narration track OR an openly licensed/locally synthesized narration provider; if voice input is absent, render a video with placeholders and say so explicitly.
4. Add pytest tests for state transitions, budget enforcement, sources/asset manifests, and the `private` upload safety guard.
5. Supply `.env.example`, README with Mac setup steps, example channel YAML files and sample episode metadata. Do not commit secrets.
6. Run available tests and a local smoke test; present exact commands, generated files, any failures and trade-offs. No claimed successful YouTube publishing without an actual authenticated API result.
7. Propose paid provider integrations and enhancements only after demonstrating the zero-cost local pipeline.

## Definition of success for first release
- One fact-checked 8–15 minute pilot can be produced from original narration and rights-cleared visuals with an auditable research and asset trail.
- Three stand-alone Shorts can be rendered with working captions.
- A human can review all artifacts and create a private YouTube upload, or export a release folder when OAuth is not available.
- Analytics and cost reports work with mocks and optional CSV import.
- No silent spending, no unapproved publishing, no invented sources.

## First suggested pilot
Channel: **Engineering Explained**
Working topic: **How Undersea Internet Cables Actually Work**.
Outline: open with a surprising but verifiable hook; global cable routes; fiber-optic signal and repeaters; cable laying and repair; failure modes; why satellites do not fully replace fiber; concise recap. Use sourced, original diagrams and maps. Verify all numerical claims during research instead of relying on memory.

Begin now by planning and scaffolding the repository, implementing the local mock workflow and demonstrating a first dry run. Request API keys only when the corresponding optional provider is actually being connected.
