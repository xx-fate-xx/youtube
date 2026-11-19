"""Shorts: independent 20-60 s scripts, distinct hooks/compositions, 1080x1920 renders."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from studio import ffmpeg
from studio.assets import parse_steps
from studio.audio import NarrationItem, synthesize
from studio.captions import cues_from_words, to_srt
from studio.channels import ChannelProfile
from studio.config import Settings
from studio.diagrams import DIAGRAMS
from studio.episodes import Workspace
from studio.fsutil import atomic_write_json, atomic_write_text
from studio.models import ResearchPack, Script, ShortSpec
from studio.motion import ScenePlan, SceneRenderer, blend, ease, frames_to_mp4, plan_scene
from studio.providers.voice import VoiceProvider
from studio.render import draw_badges, draw_caption
from studio.visuals import Canvas, Theme, element_bbox, get_font, rgba, wrap_text

SIZE = (1080, 1920)
MIN_S, MAX_S = 20.0, 60.0
END_CARD_S = 2.5
HOOK_CARD_S = 3.0
MAX_OVERLAP = 0.12


def _ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def overlap(a: str, b: str, n: int = 5) -> float:
    """Share of `a`'s word 5-grams that also appear in `b` (0 = fully independent)."""
    ga, gb = _ngrams(a, n), _ngrams(b, n)
    return len(ga & gb) / len(ga) if ga else 0.0


def shorts_issues(shorts: list[ShortSpec], script: Script, pack: ResearchPack,
                  channel: ChannelProfile) -> list[str]:
    issues: list[str] = []
    wpm = channel.narration.words_per_minute
    claim_ids = {c.id for c in pack.claims}
    hooks = [s.hook.strip().lower() for s in shorts]
    if len(set(hooks)) != len(hooks):
        issues.append("hooks are not distinct")
    layouts = [(s.layout, s.diagram) for s in shorts]
    if len(set(layouts)) != len(layouts):
        issues.append("two Shorts share the same composition (layout + diagram)")
    for s in shorts:
        est = len(s.narration.split()) / wpm * 60
        if not MIN_S <= est + END_CARD_S <= MAX_S:
            issues.append(f"{s.id}: estimated {est:.0f}s narration outside {MIN_S:.0f}-"
                          f"{MAX_S:.0f}s")
        if s.diagram not in DIAGRAMS:
            issues.append(f"{s.id}: unknown diagram {s.diagram}")
        for cid in s.claim_ids:
            if cid not in claim_ids:
                issues.append(f"{s.id}: cites unknown claim {cid}")
        ov = overlap(s.narration, script.narration_text)
        if ov > MAX_OVERLAP:
            issues.append(f"{s.id}: {ov:.0%} of its phrasing is copied from the long script; "
                          "rewrite it as an independent Short")
        for other in shorts:
            if other.id != s.id and overlap(s.narration, other.narration) > MAX_OVERLAP:
                issues.append(f"{s.id}: too similar to {other.id}")
        if not s.link_text.strip():
            issues.append(f"{s.id}: missing link back to the long video")
    return issues


def save_shorts(ws: Workspace, shorts: list[ShortSpec]) -> None:
    atomic_write_json(ws.shorts_file, [s.model_dump() for s in shorts])


def load_shorts(ws: Workspace) -> list[ShortSpec]:
    import json

    if not ws.shorts_file.exists():
        return []
    return [ShortSpec.model_validate(s) for s in json.loads(ws.shorts_file.read_text())]


# --------------------------------------------------------------------------- layout
# Phone-safe layout for 1080x1920. YouTube's Shorts UI covers roughly the top ~120 px, the
# bottom ~380 px (title, channel, sound) and a column of buttons on the right; important
# content stays inside SAFE.
SAFE = (60, 170, 940, 1520)  # x0, y0, x1, y1
MIN_TEXT_PX = 42  # ~15 pt on a typical phone (1080 px shown ~390 pt wide)
CAPTION_PX = 58
PANEL = {  # where the diagram camera picture goes: (y_offset, height)
    "diagram_center": (470, 820),
    "hook_card": (470, 820),
    "diagram_top": (170, 820),
}


def _text_block(img: Image.Image, text: str, theme: Theme, *, y: int, size: int,
                color: str, max_width: int = 880) -> int:
    d = ImageDraw.Draw(img, "RGBA")
    font = get_font(size, bold=True)
    for line in wrap_text(text, size, max_width, bold=True):
        d.text((500, y), line, font=font, fill=rgba(color), anchor="mt")
        y += int(size * 1.2)
    return y


def short_steps(spec: ShortSpec, max_step: int) -> list[int]:
    if spec.steps:
        return parse_steps(spec.steps, max_step)
    return parse_steps("" if spec.diagram_step is None else str(spec.diagram_step), max_step)


def boost_text(canvas: Canvas, px_per_unit: float, min_px: int = MIN_TEXT_PX) -> Canvas:
    """Copy of the canvas with every label at least `min_px` tall on the phone frame."""
    out = Canvas(canvas.width, canvas.height, canvas.background, canvas.font_family,
                 [dict(e) for e in canvas.elements])
    for e in out.elements:
        if e["kind"] == "text" and e["size"] * px_per_unit < min_px:
            e["size"] = math.ceil(min_px / px_per_unit)
    return out


def short_plan(spec: ShortSpec, canvas: Canvas, duration: float, start_shot=None) -> ScenePlan:
    _, h = PANEL[spec.layout]
    aspect = SIZE[0] / h
    camera = f"focus:{spec.focus}" if spec.focus else "auto"
    return plan_scene(canvas, short_steps(spec, canvas.max_step), duration, aspect=aspect,
                      camera=camera, max_zoom=2.2, start_shot=start_shot, hud_frac=0.0)


def _views(plan: ScenePlan, samples: int):
    for k in range(samples):
        t = plan.duration * (k + 0.5) / samples
        if plan.moving(t):
            continue  # judged on settled framings; moves last about 1.6 s
        shot = plan.shot_at(t)
        vw = shot.vw
        vh = vw / plan.aspect
        view = (shot.cx - vw / 2, shot.cy - vh / 2, shot.cx + vw / 2, shot.cy + vh / 2)
        yield t, SIZE[0] / vw, view, plan.state_at(t)[0]


def _on_camera(box, view) -> bool:
    return not (box[2] < view[0] or box[0] > view[2] or box[3] < view[1] or box[1] > view[3])


RIGHT_SAFE = SAFE[2] / SIZE[0]  # the Shorts button column covers the right edge
LABEL_GAP = 8  # minimum gap between labels (diagram units)


def _safe_view(view):
    return (view[0], view[1], view[0] + (view[2] - view[0]) * RIGHT_SAFE, view[3])


def _cut(box, view, tol: float = 2) -> bool:
    view = _safe_view(view)
    return (box[0] < view[0] - tol or box[2] > view[2] + tol or box[1] < view[1] - tol
            or box[3] > view[3] + tol)


def _overlap(a, b, gap: float = LABEL_GAP) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) > -gap / 2
            and min(a[3], b[3]) - max(a[1], b[1]) > -gap / 2)


def legibility_issues(spec: ShortSpec, canvas: Canvas, plan: ScenePlan,
                      samples: int = 48) -> list[str]:
    """Text that would be unreadable on a phone: too small, overlapping or cut by the frame."""
    small: dict[str, float] = {}
    cut: set[str] = set()
    overlaps: set[str] = set()
    for _t, ppu, view, step in _views(plan, samples):
        texts = []
        for e in canvas.visible(step):
            if e["kind"] != "text" or e.get("hud"):
                continue
            box = element_bbox(e)
            if not _on_camera(box, view):
                continue
            px = e["size"] * ppu
            if px < MIN_TEXT_PX - 0.5:
                small[e["s"]] = min(px, small.get(e["s"], px))
            if _cut(box, view):
                cut.add(e["s"])
            texts.append((e["s"], box))
        for i, (sa, a) in enumerate(texts):
            for sb, b in texts[i + 1:]:
                if _overlap(a, b):
                    overlaps.add(f"'{sa[:28]}' / '{sb[:28]}'")
    out = [f"{spec.id}: label '{s[:40]}' only {px:.0f}px tall (< {MIN_TEXT_PX}px)"
           for s, px in sorted(small.items())]
    out += [f"{spec.id}: label '{s[:40]}' is cut by the frame" for s in sorted(cut)]
    out += [f"{spec.id}: labels overlap: {o}" for o in sorted(overlaps)]
    return out


def drop_cut_labels(canvas: Canvas, plan: ScenePlan, samples: int = 48) -> list[str]:
    """Remove labels that the vertical framing would cut; return what was removed."""
    doomed: set[int] = set()
    for _t, _ppu, view, step in _views(plan, samples):
        for e in canvas.visible(step):
            if e["kind"] == "text" and not e.get("hud"):
                box = element_bbox(e)
                if _on_camera(box, view) and _cut(box, view):
                    doomed.add(id(e))
    removed = [e["s"] for e in canvas.elements if id(e) in doomed]
    canvas.elements = [e for e in canvas.elements if id(e) not in doomed]
    return removed


def reflow_cut_labels(canvas: Canvas, plan: ScenePlan, samples: int = 48) -> int:
    """Wrap and shift labels the vertical frame would cut so they fit inside every view
    that shows them. Returns how many labels were reflowed."""
    first_view: dict[int, tuple] = {}  # intersection of every view showing the label
    for _t, _ppu, view, step in _views(plan, samples):
        for e in canvas.visible(step):
            if e["kind"] == "text" and not e.get("hud"):
                box = element_bbox(e)
                if _on_camera(box, view):
                    v = first_view.get(id(e), view)
                    first_view[id(e)] = (max(v[0], view[0]), max(v[1], view[1]),
                                         min(v[2], view[2]), min(v[3], view[3]))
    new_elements: list[dict] = []
    count = 0
    for e in canvas.elements:
        view = first_view.get(id(e))
        if view is None or not _cut(element_bbox(e), view):
            continue_flag = True
        else:
            continue_flag = False
            view = _safe_view(view)
        if continue_flag:
            new_elements.append(e)
            continue
        count += 1
        margin = 24
        max_w = (view[2] - view[0]) - 2 * margin
        if max_w < e["size"] * 4:
            new_elements.append(e)  # no room; drop_cut_labels will report it
            continue
        lines = wrap_text(e["s"], e["size"], max_w, e["bold"])
        line_h = e["size"] * 1.2
        font = get_font(e["size"], e["bold"])
        width = max(font.getlength(line) for line in lines)
        x0, y0, _, _ = element_bbox(e)
        x0 = min(max(x0, view[0] + margin), view[2] - margin - width)
        y0 = min(max(y0, view[1] + margin), view[3] - margin - line_h * len(lines))
        for k, line in enumerate(lines):
            new_elements.append({**e, "s": line, "x": x0, "y": y0 + k * line_h,
                                 "anchor": "lt"})
    canvas.elements = new_elements
    return count


def separate_labels(canvas: Canvas, plan: ScenePlan, samples: int = 48) -> int:
    """Push apart labels that touch on screen (the lower one moves down, else up)."""
    moved = 0
    for _ in range(4):
        changed = False
        for _t, _ppu, view, step in _views(plan, samples):
            texts = [e for e in canvas.visible(step) if e["kind"] == "text"
                     and not e.get("hud") and _on_camera(element_bbox(e), view)]
            for i, a in enumerate(texts):
                for b in texts[i + 1:]:
                    ba, bb = element_bbox(a), element_bbox(b)
                    if not _overlap(ba, bb):
                        continue
                    upper, lower = (a, b) if ba[1] <= bb[1] else (b, a)
                    bu, bl = element_bbox(upper), element_bbox(lower)
                    down = bu[3] + LABEL_GAP - bl[1]
                    if bl[3] + down <= view[3] - 4:
                        lower["y"] += down
                    else:
                        upper["y"] -= bu[3] + LABEL_GAP - bl[1]
                    moved += 1
                    changed = True
        if not changed:
            break
    return moved


def prepare_short(spec: ShortSpec, theme: Theme,
                  duration: float) -> tuple[Canvas, ScenePlan, list[str]]:
    """Boost labels for the widest framing used, drop labels the frame would cut, plan."""
    canvas = DIAGRAMS[spec.diagram].build(theme)
    plan = short_plan(spec, canvas, duration)
    widest = max(s.vw for _, s, _ in plan.keys)
    canvas = boost_text(canvas, SIZE[0] / widest)
    plan = short_plan(spec, canvas, duration)
    reflow_cut_labels(canvas, plan)
    separate_labels(canvas, plan)
    removed = drop_cut_labels(canvas, plan)
    return canvas, plan, removed


def _static_overlay(spec: ShortSpec, theme: Theme, channel_name: str, phase: str,
                    badges: list[str]) -> Image.Image:
    img = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    if phase == "end":
        _text_block(img, "Want the whole story?", theme, y=640, size=68, color=theme.accent2)
        _text_block(img, spec.link_text, theme, y=790, size=60, color=theme.fg)
        _text_block(img, channel_name.upper(), theme, y=1200, size=44, color=theme.accent)
        return img
    if phase == "hook_card":
        d = ImageDraw.Draw(img)
        d.rectangle([90, 700, 104, 1140], fill=rgba(theme.accent))
        _text_block(img, spec.hook, theme, y=720, size=86, color=theme.fg, max_width=820)
        return img
    y_off, h = PANEL[spec.layout]
    d = ImageDraw.Draw(img)
    note_y = y_off + h + 40  # just below the diagram panel
    d.text((70, note_y), "SCHEMATIC - NOT TO SCALE", font=get_font(28, bold=True),
           fill=rgba(theme.muted), anchor="ls")
    if spec.layout == "diagram_top":
        _text_block(img, spec.hook, theme, y=note_y + 30, size=60, color=theme.accent2)
    else:
        _text_block(img, spec.hook, theme, y=200, size=60, color=theme.fg)
    if badges:
        draw_badges(img, badges, x=1050, y=40, size=26)
    return img


@dataclass(frozen=True)
class ShortResult:
    id: str
    video: Path
    srt: Path
    duration_s: float
    legibility: list[str]


def render_short(settings: Settings, ws: Workspace, spec: ShortSpec, channel: ChannelProfile,
                 provider: VoiceProvider, *, preview: bool, badges: list[str]) -> ShortResult:
    binary = settings.ffmpeg_binary()
    profile = ffmpeg.PREVIEW if preview else ffmpeg.MASTER
    theme = Theme.from_identity(channel.visual)
    fps = profile.fps
    out_dir = ws.shorts / spec.id
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / "narration.wav"
    timings, narr_dur = synthesize([NarrationItem(spec.id, spec.narration)], provider, channel,
                                   wav, ws.audio / "sentences", lead_in_s=0.3)
    if not MIN_S <= narr_dur + END_CARD_S <= MAX_S:
        raise ValueError(f"{spec.id}: narration is {narr_dur:.1f}s; Shorts must be "
                         f"{MIN_S:.0f}-{MAX_S:.0f}s including the end card")
    total = narr_dur + END_CARD_S
    cues = cues_from_words(timings[0].words, max_chars=28, max_duration=2.2)
    srt = out_dir / f"{spec.id}.en.srt"
    atomic_write_text(srt, to_srt(cues))

    body_start = HOOK_CARD_S if spec.layout == "hook_card" else 0.0
    body_dur = max(1.0, narr_dur - body_start)
    canvas, plan, dropped = prepare_short(spec, theme, body_dur)
    legibility = legibility_issues(spec, canvas, plan)
    y_off, h = PANEL[spec.layout]
    rend = SceneRenderer(canvas, plan, SIZE, layer_scale=2.0, view_size=(SIZE[0], h),
                         view_offset=(0, y_off), hud=False)
    overlays = {ph: _static_overlay(spec, theme, channel.name, ph, badges if ph == "body"
                                    else []) for ph in ("hook_card", "body", "end")}
    bg = Image.new("RGB", SIZE, rgba(theme.bg)[:3])
    n = round(total * fps)

    def frames():
        for i in range(n):
            t = i / fps
            if t < body_start:
                img = bg.copy()
                img.paste(overlays["hook_card"], (0, 0), overlays["hook_card"])
            elif t < narr_dur:
                img = rend.frame(t - body_start)
                img.paste(overlays["body"], (0, 0), overlays["body"])
                if body_start and t - body_start < 0.5:
                    hook = bg.copy()
                    hook.paste(overlays["hook_card"], (0, 0), overlays["hook_card"])
                    img = blend(hook, img, ease((t - body_start) / 0.5))
            else:
                img = bg.copy()
                img.paste(overlays["end"], (0, 0), overlays["end"])
                if t - narr_dur < 0.4:
                    body = rend.frame(body_dur)
                    body.paste(overlays["body"], (0, 0), overlays["body"])
                    img = blend(body, img, ease((t - narr_dur) / 0.4))
            cue = next((c.text for c in cues if c.start <= t < c.end), None)
            if cue and t < narr_dur:
                draw_caption(img, cue, theme, center_x=500, bottom_y=1480, max_width=860,
                             size=CAPTION_PX)
            yield img

    video_only = out_dir / "video_only.mp4"
    frames_to_mp4(binary, frames(), n, SIZE, fps, video_only, preset=profile.preset,
                  crf=profile.crf)
    music = out_dir / "music_bed.wav"
    ffmpeg.make_music_bed(binary, music, total + 1)
    out = out_dir / f"{spec.id}_{'preview' if preview else 'master'}.mp4"
    ffmpeg.mux_with_ducking(binary, video_only, wav, music, out, total, profile)
    atomic_write_json(out_dir / "metadata.json", {
        "title": spec.title[:100],
        "description": f"{spec.hook}\n\n{spec.link_text}\n\n#Shorts",
        "privacyStatus": "private",
        "claims": spec.claim_ids,
        "narration_provider": provider.name,
        "narration_license": {"license": provider.license().license,
                              "clearance": provider.license().clearance.value,
                              "proof": provider.license().proof},
        "timing_method": provider.timing_method,
        "legibility_issues": legibility,
        "labels_hidden_for_vertical_frame": dropped,
    })
    return ShortResult(spec.id, out, srt, ffmpeg.probe_duration(binary, out), legibility)
