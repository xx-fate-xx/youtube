# Diagram library (YAML templates)

New episodes no longer need diagram code. Describe a diagram in
`diagram_specs/<id>.yaml`, reference it from the script like any diagram, and it gets the
channel's colours, Inter, build steps, camera moves, draw-on/pulse animation, Shorts
legibility handling and licence records automatically.

```yaml
# script.yaml paragraph
visual: {kind: diagram, ref: ee_cable_lifecycle, steps: "0-4"}
```

```bash
uv run studio diagrams list                      # code diagrams + templates
uv run studio diagrams check                     # validation + layout QA (exit 2 on issues)
uv run studio diagrams preview ee_cable_timeline --video 8   # PNG step sheet + MP4
```

## Rules for every template

| key | meaning |
|---|---|
| `type` | `map`, `cross_section`, `process`, `comparison`, `timeline`, `flow`, `stat` |
| `title` | title strip text |
| `schematic` | show "SCHEMATIC - NOT TO SCALE" (default true) |
| `claims` | claim ids backing **any digit shown on screen**; required if text contains a number |
| `caption` | list of `{text, step, until}` messages at the bottom (y≈830) |
| `camera` | override the scene camera (`auto`, `wide`, `static`, `focus:x,y,w,h|…`) |
| `step` / `until` | when an element appears / disappears (build steps) |

Canvas is 1920×1080; keep content between y=150 (title strip) and y=880 (captions).
Colours: `accent`, `accent2`, `fg`, `muted`, `danger` or `#RRGGBB`. Unknown keys are
rejected (typos fail loudly). If a scene shows a diagram whose `claims` the narration does
not cite, `studio storyboard` warns.

## Types

| type | you give | the template does | example |
|---|---|---|---|
| `map` | `regions` (blob or polygon), `nodes` (id, x, y, label), `routes` (from, to, bend), `cuts`, `highlights` | curved routes with travelling pulses, cut = grey + ✕, highlight box | `ee_route_diversity_map` |
| `cross_section` | `layers` inner→outer (`core`/`ring`/`wires`, thickness, colour) | scales to fit, radial leader lines that never cross, labels column | `ee_cable_layers` |
| `process` | 2–6 `steps` (title, text) | content-sized boxes, numbers, arrows, one step per build step | `ee_cable_lifecycle`, `bu_subscription_loop` |
| `comparison` | 2–6 `items` (label, value 0–1) | sliding bars; qualitative footnote unless `data: true` (+ claims) | `ee_capacity_comparison` |
| `timeline` | 2–7 `events` (when, label) | axis, alternating labels, `spacing: even|proportional` | `ee_cable_timeline` |
| `flow` | `blocks` (id, x, y, w, h, label), `links` (from, to, label), `notes` | edge-to-edge arrows with pulses, labels beside vertical links | `ee_landing_flow`, `awl_invoice_workflow` |
| `stat` | `value`, `label`, `source` (+ claims) | big number with source line on screen | `ee_fault_causes` |

Default camera: `auto` (follows newly revealed elements) for map, flow, cross_section;
`wide` (one gentle push-in) for process, comparison, timeline, stat.

## Quality gates

- `layout_issues`: overlapping labels, text off-canvas, text under the title strip or in
  the caption band — all examples and all pilot diagrams pass.
- Shorts: templates go through the same label boost / reflow / legibility check.
- Facts: numbers need `claims`; comparison bars are labelled illustrative unless sourced.
