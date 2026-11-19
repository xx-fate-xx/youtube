"""Data-driven diagram templates: describe a diagram in YAML, no code per episode.

Types: map, cross_section, process, comparison, timeline, flow, stat.
All coordinates are in the 1920x1080 logical canvas; content should stay between y=150
(below the title strip) and y=880 (above the caption band). Build steps (`step`) reveal
elements progressively and drive the motion engine (camera, draw-on, pulses).

Fact safety: any on-screen text containing a digit requires `claims` on the diagram (the
claim ids that back it); the storyboard warns when a scene shows such a diagram without
citing those claims.
"""

from __future__ import annotations

import math
import re
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from studio.visuals import Canvas, Theme, base_frame, blob, quad_curve, wrap_text

LIGHT = "#E6FFFB"
TOP, BOTTOM = 170, 860  # usable vertical band (title strip above, captions below)


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


def color(theme: Theme, name: str | None, default: str = "accent") -> str:
    name = name or default
    palette = {"accent": theme.accent, "accent2": theme.accent2, "fg": theme.fg,
               "muted": theme.muted, "danger": theme.danger, "bg": theme.bg}
    if name in palette:
        return palette[name]
    if re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", name):
        return name
    raise ValueError(f"unknown colour {name!r} (use accent|accent2|fg|muted|danger or #RRGGBB)")


class Caption(_M):
    text: str
    step: int = 0
    until: int | None = None
    color: str = "fg"


class Base(_M):
    id: str = ""
    title: str
    schematic: bool = True
    claims: list[str] = []  # claim ids backing any number shown on screen
    caption: list[Caption] = []  # bottom-centre messages (y ~ 830)
    camera: str = ""  # default camera for scenes using this diagram ("" = type default)

    DEFAULT_CAMERA: ClassVar[str] = "auto"

    def default_camera(self) -> str:
        return self.camera or self.DEFAULT_CAMERA

    def texts(self) -> list[str]:
        out = [self.title] + [c.text for c in self.caption]
        for _name, value in self:
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, BaseModel):
                    for f in ("label", "text", "title", "when", "value", "note", "source"):
                        v = getattr(item, f, None)
                        if isinstance(v, str):
                            out.append(v)
        for f in ("value", "label", "source", "footnote"):
            v = getattr(self, f, None)
            if isinstance(v, str):
                out.append(v)
        return out

    @model_validator(mode="after")
    def _numbers_need_claims(self):
        with_digits = [t for t in self.texts() if re.search(r"\d", t)]
        if with_digits and not self.claims:
            raise ValueError("on-screen numbers need `claims` (claim ids that back them): "
                             + "; ".join(repr(t) for t in with_digits[:4]))
        return self

    def frame(self, t: Theme) -> Canvas:
        return base_frame(t, self.title, schematic=self.schematic)

    def add_captions(self, c: Canvas, t: Theme) -> None:
        for cap in self.caption:
            c.text(960, 830, cap.text, size=34, color=color(t, cap.color, "fg"), anchor="mm",
                   bold=True, step=cap.step, until=cap.until, delay=0.6)


# ------------------------------------------------------------------------------ map


class Region(_M):
    shape: Literal["blob", "polygon"] = "blob"
    x: float = 0
    y: float = 0
    rx: float = 200
    ry: float = 160
    seed: int = 1
    points: list[tuple[float, float]] = []
    label: str = ""
    step: int = 0
    color: str = "muted"


class Node(_M):
    id: str
    x: float
    y: float
    label: str = ""
    label_pos: Literal["above", "below", "left", "right"] = "above"
    step: int = 0
    until: int | None = None
    pulse: bool = False


class Route(_M):
    a: str = Field(alias="from")
    b: str = Field(alias="to")
    bend: float = 0.12  # sideways offset of the curve, as a share of its length
    step: int = 0
    until: int | None = None
    flow: bool = True
    color: str = "accent"
    width: float = 5
    label: str = ""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Cut(_M):
    route: str  # "A-B"
    at: float = 0.5
    step: int = 1


class Highlight(_M):
    x: float
    y: float
    w: float
    h: float
    label: str = ""
    step: int = 1
    color: str = "accent2"


class MapSpec(Base):
    type: Literal["map"]
    regions: list[Region] = []
    nodes: list[Node]
    routes: list[Route] = []
    cuts: list[Cut] = []
    highlights: list[Highlight] = []

    @model_validator(mode="after")
    def _refs(self):
        ids = [n.id for n in self.nodes]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"duplicate node ids: {sorted(dup)}")
        for r in self.routes:
            for end in (r.a, r.b):
                if end not in ids:
                    raise ValueError(f"route {r.a}-{r.b}: unknown node {end!r}")
        keys = {f"{r.a}-{r.b}" for r in self.routes}
        for cut in self.cuts:
            if cut.route not in keys:
                raise ValueError(f"cut refers to unknown route {cut.route!r} (have {keys})")
        return self

    def curve(self, r: Route):
        n = {x.id: x for x in self.nodes}
        (x0, y0), (x1, y1) = (n[r.a].x, n[r.a].y), (n[r.b].x, n[r.b].y)
        length = math.hypot(x1 - x0, y1 - y0) or 1
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        nx, ny = -(y1 - y0) / length, (x1 - x0) / length
        ctrl = (mx + nx * r.bend * length, my + ny * r.bend * length)
        return quad_curve((x0, y0), ctrl, (x1, y1), n=60)

    def build(self, t: Theme) -> Canvas:
        c = self.frame(t)
        for g in self.regions:
            pts = (blob(g.x, g.y, g.rx, g.ry, seed=g.seed) if g.shape == "blob"
                   else [tuple(p) for p in g.points])
            base = color(t, g.color, "muted")
            c.polygon(pts, fill=base + "66" if len(base) == 7 else base, stroke=base, sw=2,
                      step=g.step)
            if g.label:
                c.text(g.x, g.y, g.label, size=30, color=t.fg, anchor="mm", step=g.step,
                       nofocus=True)
        cut_routes = {cut.route: cut for cut in self.cuts}
        for r in self.routes:
            pts = self.curve(r)
            key = f"{r.a}-{r.b}"
            until = r.until
            cut = cut_routes.get(key)
            if cut:
                until = cut.step - 1 if until is None else min(until, cut.step - 1)
            col = color(t, r.color)
            c.line(pts, color=col, width=r.width, step=r.step, until=until, dur=1.5,
                   flow=LIGHT if r.flow else None)
            if r.label:
                lx, ly = pts[len(pts) // 2]
                c.text(lx, ly - 18, r.label, size=28, color=col, anchor="mb", step=r.step,
                       until=until, delay=0.8)
            if cut:
                k = max(1, min(len(pts) - 2, round(cut.at * (len(pts) - 1))))
                gap = max(2, len(pts) // 14)
                c.line(pts[:k - gap], color=t.muted, width=r.width, step=cut.step,
                       anim="fade")
                c.line(pts[k + gap:], color=t.muted, width=r.width, step=cut.step,
                       anim="fade")
                x, y = pts[k]
                for d in (1, -1):
                    c.line([(x - 28, y - 28 * d), (x + 28, y + 28 * d)], color=t.danger,
                           width=9, step=cut.step, anim="fade", delay=0.2)
        for h in self.highlights:
            col = color(t, h.color, "accent2")
            c.rect(h.x, h.y, h.w, h.h, stroke=col, sw=4, r=18, step=h.step, anim="grow")
            if h.label:
                c.text(h.x + h.w / 2, h.y + h.h + 14, h.label, size=30, color=col,
                       anchor="mt", bold=True, step=h.step, delay=0.6)
        for nd in self.nodes:
            c.circle(nd.x, nd.y, 13, fill=t.accent2, stroke=t.bg, sw=4, step=nd.step,
                     until=nd.until, pulse=nd.pulse)
            if nd.label:
                dx, dy, anchor = {"above": (0, -24, "mb"), "below": (0, 24, "mt"),
                                  "left": (-24, 0, "rm"), "right": (24, 0, "lm")}[nd.label_pos]
                c.text(nd.x + dx, nd.y + dy, nd.label, size=28, color=t.fg, anchor=anchor,
                       step=nd.step, until=nd.until, delay=0.4)
        self.add_captions(c, t)
        return c


# ------------------------------------------------------------------------------ cross-section


class Layer(_M):
    label: str
    kind: Literal["core", "ring", "wires"] = "ring"
    thickness: float = 40
    color: str = "muted"
    count: int = 18  # wires only
    step: int = 0


class CrossSectionSpec(Base):
    type: Literal["cross_section"]
    layers: list[Layer] = Field(min_length=1, max_length=7)  # inner -> outer
    footnote: str = ""
    cx: float = 620
    cy: float = 515

    def build(self, t: Theme) -> Canvas:
        c = self.frame(t)
        radii = []
        r = 0.0
        for layer in self.layers:
            r_in, r = r, r + layer.thickness
            radii.append((r_in, r))
        scale = min(1.0, 320 / r)  # fit the outer layer into the left half
        radii = [(a * scale, b * scale) for a, b in radii]
        # draw outer -> inner so inner layers sit on top
        for layer, (r_in, r_out) in reversed(list(zip(self.layers, radii, strict=True))):
            col = color(t, layer.color, "muted")
            if layer.kind == "wires":
                rw = (r_out - r_in) / 2
                rm = r_in + rw
                n = max(6, layer.count)
                for i in range(n):
                    a = 2 * math.pi * i / n
                    c.circle(self.cx + rm * math.cos(a), self.cy + rm * math.sin(a), rw * 0.95,
                             fill=col, stroke=t.bg, sw=2, step=layer.step, delay=i * 0.02)
            else:
                c.circle(self.cx, self.cy, r_out, fill=col, stroke=t.bg, sw=2,
                         step=layer.step)
        n = len(self.layers)
        ys = ([TOP + 60 + i * (BOTTOM - TOP - 160) / max(1, n - 1) for i in range(n)]
              if n > 1 else [self.cy])
        lx = 1080
        for slot, i in enumerate(sorted(range(n), key=lambda i: -i)):  # outer label on top
            layer = self.layers[i]
            r_in, r_out = radii[i]
            rm = (r_in + r_out) / 2 if layer.kind != "core" else r_out * 0.45
            ly = ys[slot]
            ang = math.atan2(ly - self.cy, lx - 20 - self.cx)  # radial leaders never cross
            px, py = self.cx + rm * math.cos(ang), self.cy + rm * math.sin(ang)
            c.line([(px, py), (lx - 20, ly)], color=t.fg, width=2, step=layer.step, delay=0.5)
            c.circle(px, py, 6, fill=t.fg, step=layer.step)
            c.text(lx, ly, layer.label, size=32, color=t.fg, anchor="lm", step=layer.step,
                   delay=0.9)
        if self.footnote:
            c.text(1080, BOTTOM - 20, self.footnote, size=26, color=t.muted, anchor="lm",
                   step=max(x.step for x in self.layers))
        self.add_captions(c, t)
        return c


# ------------------------------------------------------------------------------ process


class ProcessStep(_M):
    title: str
    text: str = ""
    step: int | None = None  # default: its position


class ProcessSpec(Base):
    DEFAULT_CAMERA: ClassVar[str] = "wide"  # horizontal layouts read best as one gentle push-in

    type: Literal["process"]
    steps: list[ProcessStep] = Field(min_length=2, max_length=6)
    numbered: bool = True

    def build(self, t: Theme) -> Canvas:
        c = self.frame(t)
        n = len(self.steps)
        gap = 70
        w = (1920 - 2 * 110 - gap * (n - 1)) / n
        tsize, bsize = (34, 28) if n <= 4 else (30, 26)
        heights = []
        for st in self.steps:
            h = 70 + len(wrap_text(st.title, tsize, w - 40, True)) * tsize * 1.25
            if st.text:
                h += 16 + len(wrap_text(st.text, bsize, w - 44)) * bsize * 1.25
            heights.append(h + 36)
        h = max(heights)
        y = max(TOP + 80, 500 - h / 2)
        for i, st in enumerate(self.steps):
            s = i if st.step is None else st.step
            x = 110 + i * (w + gap)
            c.rect(x, y, w, h, fill=t.muted + "22", stroke=t.accent, sw=3, r=22, step=s)
            if self.numbered:
                c.circle(x + w / 2, y, 34, fill=t.accent, stroke=t.bg, sw=4, step=s,
                         delay=0.2)
                c.text(x + w / 2, y, str(i + 1), size=34, color=t.bg, anchor="mm", bold=True,
                       step=s, delay=0.3, anim="fade")
            ty = c.paragraph(x + w / 2, y + 60, st.title, size=tsize, color=t.fg,
                             max_width=w - 40, bold=True, anchor_h="m", step=s, delay=0.4)
            if st.text:
                c.paragraph(x + w / 2, ty + 16, st.text, size=bsize, color=t.fg + "CC",
                            max_width=w - 44, anchor_h="m", step=s, delay=0.6)
            if i < n - 1:
                nxt = i + 1 if self.steps[i + 1].step is None else self.steps[i + 1].step
                c.arrow(x + w + 8, y + h / 2, x + w + gap - 8, y + h / 2, color=t.accent2,
                        width=5, head=20, step=nxt, nofocus=True)
        self.add_captions(c, t)
        return c

    def texts(self) -> list[str]:
        # step numbers are drawn by the template, not facts
        return [self.title] + [c.text for c in self.caption] + [
            x for st in self.steps for x in (st.title, st.text)]


# ------------------------------------------------------------------------------ comparison


class Item(_M):
    label: str
    value: float = Field(ge=0, le=1)  # relative bar length (qualitative unless data=true)
    color: str = "accent"
    note: str = ""
    step: int = 0


class ComparisonSpec(Base):
    DEFAULT_CAMERA: ClassVar[str] = "wide"  # horizontal layouts read best as one gentle push-in

    type: Literal["comparison"]
    items: list[Item] = Field(min_length=2, max_length=6)
    data: bool = False  # true = bar lengths are measured values -> claims required
    footnote: str = "Bar lengths illustrate the relationship only; not measured values."

    @model_validator(mode="after")
    def _data_needs_claims(self):
        if self.data and not self.claims:
            raise ValueError("comparison with data=true needs `claims`")
        if self.data and self.footnote.startswith("Bar lengths illustrate"):
            self.footnote = ""
        return self

    def build(self, t: Theme) -> Canvas:
        c = self.frame(t)
        n = len(self.items)
        bar_h = min(110, (BOTTOM - TOP - 140) / n - 30)
        y = TOP + 60
        for it in self.items:
            col = color(t, it.color)
            w = max(40.0, 1500 * it.value)
            c.rect(160, y, w, bar_h, fill=col, r=12, step=it.step, anim="slide",
                   slide_from=(-w, 0.0), dur=1.5)
            inside = w > 520
            c.text(190 if inside else 160 + w + 24, y + bar_h / 2, it.label, size=32,
                   color=t.bg if inside else t.fg, anchor="lm", bold=True, step=it.step,
                   delay=1.0)
            if it.note:
                c.text(160, y + bar_h + 10, it.note, size=24, color=t.muted, step=it.step,
                       delay=1.2)
                y += 34
            y += bar_h + 34
        if self.footnote:
            c.text(160, min(y + 10, BOTTOM - 40), self.footnote, size=24, color=t.muted,
                   step=max(i.step for i in self.items))
        self.add_captions(c, t)
        return c


# ------------------------------------------------------------------------------ timeline


class Event(_M):
    when: str
    label: str
    step: int | None = None


class TimelineSpec(Base):
    DEFAULT_CAMERA: ClassVar[str] = "wide"  # horizontal layouts read best as one gentle push-in

    type: Literal["timeline"]
    events: list[Event] = Field(min_length=2, max_length=7)
    spacing: Literal["even", "proportional"] = "even"

    def build(self, t: Theme) -> Canvas:
        c = self.frame(t)
        y = 520
        x0, x1 = 300, 1620
        c.line([(x0 - 40, y), (x1 + 40, y)], color=t.muted, width=4, dur=1.5)
        n = len(self.events)
        if self.spacing == "proportional":
            years = [float(re.sub(r"[^0-9.]", "", e.when) or 0) for e in self.events]
            lo, hi = min(years), max(years)
            xs = [x0 + (x1 - x0) * ((v - lo) / (hi - lo) if hi > lo else i / max(1, n - 1))
                  for i, v in enumerate(years)]
        else:
            xs = [x0 + (x1 - x0) * i / max(1, n - 1) for i in range(n)]
        maxw = min(400, (x1 - x0) / max(1, n - 1) * 1.6)
        for i, (ev, x) in enumerate(zip(self.events, xs, strict=True)):
            s = i if ev.step is None else ev.step
            up = i % 2 == 0
            c.circle(x, y, 14, fill=t.accent2, stroke=t.bg, sw=4, step=s, pulse=True)
            c.line([(x, y - 18), (x, y - 70)] if up else [(x, y + 18), (x, y + 70)],
                   color=t.muted, width=2, step=s)
            wy = y - 92 if up else y + 92
            c.text(x, wy, ev.when, size=36, color=t.accent2, anchor="mb" if up else "mt",
                   bold=True, step=s, delay=0.3)
            lines = wrap_text(ev.label, 28, maxw)
            for k, line in enumerate(lines[:3]):
                ly = (wy - 48 - (len(lines[:3]) - 1 - k) * 34) if up else (wy + 48 + k * 34)
                c.text(x, ly, line, size=28, color=t.fg, anchor="mb" if up else "mt",
                       step=s, delay=0.5, group=f"ev{i}")
        self.add_captions(c, t)
        return c


# ------------------------------------------------------------------------------ flow


class Block(_M):
    id: str
    x: float
    y: float
    w: float = 240
    h: float = 130
    label: str
    step: int = 0
    color: str = "fg"


class Link(_M):
    a: str = Field(alias="from")
    b: str = Field(alias="to")
    label: str = ""
    step: int = 0
    color: str = "accent"
    flow: bool = True
    width: float = 5

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Note(_M):
    x: float
    y: float
    text: str
    step: int = 0
    color: str = "muted"
    anchor: str = "mm"


class FlowSpec(Base):
    type: Literal["flow"]
    blocks: list[Block] = Field(min_length=2)
    links: list[Link] = []
    notes: list[Note] = []

    @model_validator(mode="after")
    def _refs(self):
        ids = {b.id for b in self.blocks}
        for link in self.links:
            for end in (link.a, link.b):
                if end not in ids:
                    raise ValueError(f"link {link.a}->{link.b}: unknown block {end!r}")
        return self

    def build(self, t: Theme) -> Canvas:
        c = self.frame(t)
        bl = {b.id: b for b in self.blocks}
        for link in self.links:
            a, b = bl[link.a], bl[link.b]
            acx, acy, bcx, bcy = a.x + a.w / 2, a.y + a.h / 2, b.x + b.w / 2, b.y + b.h / 2
            if abs(bcx - acx) >= abs(bcy - acy):
                sx = a.x + a.w if bcx > acx else a.x
                ex = b.x if bcx > acx else b.x + b.w
                start, end = (sx, acy), (ex, bcy)
            else:
                sy = a.y + a.h if bcy > acy else a.y
                ey = b.y if bcy > acy else b.y + b.h
                start, end = (acx, sy), (bcx, ey)
            col = color(t, link.color)
            c.arrow(*start, *end, color=col, width=link.width, head=20, step=link.step,
                    dur=1.2)
            if link.flow:
                c.line([start, end], color=col, width=1, step=link.step, anim="none",
                       flow=LIGHT, flow_gap=140, nofocus=True)
            if link.label:
                mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
                vertical = abs(end[0] - start[0]) < abs(end[1] - start[1])
                c.text(mx + 16 if vertical else mx, my if vertical else my - 16, link.label,
                       size=26, color=col, anchor="lm" if vertical else "mb", step=link.step,
                       delay=0.8)
        for b in self.blocks:
            col = color(t, b.color, "fg")
            c.rect(b.x, b.y, b.w, b.h, fill=t.bg, stroke=col, sw=3, r=16, step=b.step)
            c.paragraph(b.x + b.w / 2, b.y + b.h / 2 - 20, b.label, size=30, color=col,
                        max_width=b.w - 24, bold=True, anchor_h="m", step=b.step, delay=0.3)
        for nt in self.notes:
            c.text(nt.x, nt.y, nt.text, size=28, color=color(t, nt.color, "muted"),
                   anchor=nt.anchor, step=nt.step, delay=0.6)
        self.add_captions(c, t)
        return c


# ------------------------------------------------------------------------------ stat


class StatSpec(Base):
    DEFAULT_CAMERA: ClassVar[str] = "wide"  # horizontal layouts read best as one gentle push-in

    type: Literal["stat"]
    value: str  # e.g. "70-80%"
    label: str
    source: str  # shown on screen, e.g. "International Cable Protection Committee, 2025"
    schematic: bool = False

    def build(self, t: Theme) -> Canvas:
        c = self.frame(t)
        c.text(960, 440, self.value, size=200, color=t.accent2, anchor="mm", bold=True,
               intro=True, anim="slide", slide_from=(0.0, 40.0), dur=1.2)
        c.paragraph(960, 600, self.label, size=48, color=t.fg, max_width=1400, bold=True,
                    anchor_h="m", intro=True, delay=0.8)
        c.text(960, 800, f"Source: {self.source}", size=28, color=t.muted, anchor="mm",
               intro=True, delay=1.2)
        self.add_captions(c, t)
        return c


DiagramSpec = Annotated[MapSpec | CrossSectionSpec | ProcessSpec | ComparisonSpec |
                        TimelineSpec | FlowSpec | StatSpec, Field(discriminator="type")]

TEMPLATE_TYPES = ("map", "cross_section", "process", "comparison", "timeline", "flow", "stat")
