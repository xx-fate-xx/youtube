"""Long-form renderer: 1920x1080 stills timeline + fades + ducked music + SRT + thumbnail.

Captions are always written as a separate .srt. In --preview mode they are also burned in,
together with review badges (unverified claims, placeholder narration).
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from studio import ffmpeg, visuals
from studio.assets import parse_steps, scene_asset_id, scene_canvas
from studio.captions import Cue, cues_from_words, to_srt
from studio.channels import ChannelProfile
from studio.config import Settings
from studio.diagrams import DIAGRAMS
from studio.episodes import Workspace
from studio.fsutil import atomic_write_text, sha256_text
from studio.models import AssetManifest, NarrationTrack, Storyboard
from studio.motion import (
    ENGINE_VERSION,
    SceneRenderer,
    blend,
    canvas_digest,
    ease,
    frames_to_mp4,
    plan_digest,
    plan_scene,
)
from studio.visuals import Theme, font_paths, get_font, rgba, wrap_text

SIZE = (1920, 1080)


@dataclass(frozen=True)
class RenderResult:
    video: Path
    srt: Path
    thumbnail: Path
    duration_s: float
    scenes: int
    preview: bool
    segments_reused: int


def draw_caption(img: Image.Image, text: str, theme: Theme, *, center_x: int, bottom_y: int,
                 max_width: int, size: int) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    font = get_font(size, bold=True)
    lines = wrap_text(text, size, max_width, bold=True)[:3]
    line_h = int(size * 1.25)
    widths = [font.getlength(line) for line in lines]
    box_w = int(max(widths)) + size
    box_h = line_h * len(lines) + size // 2
    x0, y0 = center_x - box_w // 2, bottom_y - box_h
    draw.rounded_rectangle([x0, y0, x0 + box_w, bottom_y], radius=size // 3,
                           fill=rgba(theme.caption_bg))
    y = y0 + size // 4
    for line in lines:
        draw.text((center_x, y), line, font=font, fill=rgba("#FFFFFF"), anchor="mt")
        y += line_h


def draw_badges(img: Image.Image, badges: list[str], *, x: int, y: int, size: int = 26) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    font = get_font(size, bold=True)
    for text in badges:
        w = int(font.getlength(text)) + size
        draw.rounded_rectangle([x - w, y, x, y + int(size * 1.6)], radius=8,
                               fill=rgba("#C62828E6"))
        draw.text((x - w // 2, y + int(size * 0.8)), text, font=font, fill="white", anchor="mm")
        y += int(size * 1.6) + 10


def _cache_png(cache_dir: Path, key_parts: list[str], make) -> Path:
    path = cache_dir / f"{sha256_text(*key_parts)[:24]}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        img = make()
        tmp = path.with_suffix(".part.png")
        img.save(tmp, format="PNG", compress_level=1)
        tmp.replace(path)
    return path


def _file_key(path: Path) -> str:
    st = path.stat()
    return f"{path}:{st.st_size}:{st.st_mtime_ns}"


def assign_cues(cues: list[Cue], start: float, end: float) -> list[Cue]:
    return [c for c in cues if start <= c.start < end]


def timeline_intervals(start: float, end: float, steps: list[int],
                       cues: list[Cue]) -> list[tuple[float, float, int, str | None]]:
    """Split [start, end) into intervals with a constant (step, caption)."""
    dur = end - start
    step_times = [(start + i * dur / len(steps), s) for i, s in enumerate(steps)]
    marks = {start, end} | {t for t, _ in step_times}
    for c in cues:
        marks |= {max(start, c.start), min(end, c.end)}
    points = sorted(m for m in marks if start <= m <= end)
    out = []
    for a, b in zip(points, points[1:], strict=False):
        if b - a < 1e-3:
            continue
        mid = (a + b) / 2
        step = [s for t, s in step_times if t <= mid + 1e-9][-1]
        cue = next((c.text for c in cues if c.start <= mid < c.end), None)
        out.append((a, b, step, cue))
    return out


def quantize(intervals, fps: int):
    """Round boundaries to whole frames so the video never drifts from the audio."""
    out = []
    for a, b, step, cue in intervals:
        fa, fb = round(a * fps), round(b * fps)
        if fb > fa:
            out.append(((fb - fa) / fps, step, cue))
    return out


def make_thumbnail(ws: Workspace, title: str, channel: ChannelProfile, board: Storyboard,
                   out: Path) -> Path:
    theme = Theme.from_identity(channel.visual)
    img = Image.new("RGB", (1280, 720), rgba(theme.bg)[:3])
    ref = next((s.visual.ref for s in board.scenes if s.visual.kind == "diagram"
                and s.visual.ref == "cable_cross_section"), None) or next(
        (s.visual.ref for s in board.scenes if s.visual.kind == "diagram"), None)
    if ref:
        canvas = DIAGRAMS[ref].build(theme)
        # artwork only: no labels, leader lines or grid in a thumbnail
        canvas.elements = [e for e in canvas.elements if e["kind"] not in {"text", "line"}
                           and not e.get("hud")
                           and not (e["kind"] == "circle" and e["r"] <= 8)]
        art = canvas.to_image(None, (1920, 1080))
        # Crop the diagram's subject (cross-section: the cable circle; others: centre).
        box = (270, 150, 970, 850) if ref == "cable_cross_section" else (460, 140, 1460, 860)
        art = art.crop(box)
        art.thumbnail((580, 580))
        img.paste(art, (1280 - art.width - 24, (720 - art.height) // 2))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 120, 72, 560], fill=rgba(theme.accent)[:3])
    y = 130
    for line in wrap_text(title.upper(), 62, 520, bold=True)[:5]:
        d.text((100, y), line, font=get_font(62, bold=True), fill=rgba(theme.fg)[:3])
        y += 80
    d.text((100, 640), channel.name.upper(), font=get_font(30, bold=True),
           fill=rgba(theme.accent)[:3])
    d.text((1240, 690), "DRAFT THUMBNAIL", font=get_font(18), fill=rgba(theme.muted)[:3],
           anchor="rs")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


SECTION_FADE_S = 0.4
CROSSFADE_S = 0.6


def _render_scene_job(job: dict) -> tuple[str, bool]:
    """Worker: render one scene to an H.264 segment (runs in a separate process)."""
    from studio import visuals as _v

    _v.FONT_OVERRIDE = job["font_override"]
    out = Path(job["out"])
    if out.exists():
        return str(out), True
    size = job["size"]
    fps = job["fps"]
    rend = SceneRenderer(job["canvas"], job["plan"], size, layer_scale=job["layer_scale"])
    prev_img = None
    if job["prev"] is not None:
        pc, pp = job["prev"]
        prev_img = SceneRenderer(pc, pp, size, layer_scale=job["layer_scale"]).frame(
            pp.duration)
    theme: Theme = job["theme"]
    bg = Image.new("RGB", size, rgba(theme.bg)[:3])
    n = job["n_frames"]
    total = n / fps

    def frames():
        for i in range(n):
            t = job["t0"] + i / fps
            img = rend.frame(t)
            tt = i / fps
            if prev_img is not None and tt < CROSSFADE_S:
                img = blend(prev_img, img, ease(tt / CROSSFADE_S))
            if job["fade_in"] and tt < SECTION_FADE_S:
                img = blend(bg, img, tt / SECTION_FADE_S)
            if job["fade_out"] and tt > total - SECTION_FADE_S:
                img = blend(bg, img, max(0.0, (total - tt) / SECTION_FADE_S))
            cue = next((c for a, b, c in job["cues"] if a <= t < b), None)
            if cue:
                draw_caption(img, cue, theme, center_x=size[0] // 2, bottom_y=size[1] - 50,
                             max_width=int(size[0] * 0.78), size=44)
            if job["badges"]:
                draw_badges(img, job["badges"], x=size[0] - 40, y=170)
            yield img

    frames_to_mp4(job["binary"], frames(), n, size, fps, out, preset=job["preset"],
                  crf=job["crf"])
    return str(out), False


def render_workers() -> int:
    env = os.environ.get("STUDIO_RENDER_WORKERS", "").strip()
    if env.isdigit() and int(env) > 0:
        return int(env)
    return max(1, min(6, (os.cpu_count() or 2) - 2))


def plan_episode(board: Storyboard, track: NarrationTrack, theme: Theme,
                 channel: ChannelProfile, fps: int):
    """Scene canvases + motion plans with camera/step continuity between scenes."""
    timing = {s.scene_id: s for s in track.scenes}
    missing = [s.id for s in board.scenes if s.id not in timing]
    if missing:
        raise RuntimeError(f"Narration timings missing for scenes {missing}; re-run `voice`.")
    out = []
    prev = None  # (asset_id, canvas, plan)
    for i, scene in enumerate(board.scenes):
        start = 0.0 if i == 0 else timing[scene.id].start
        end = (timing[board.scenes[i + 1].id].start if i + 1 < len(board.scenes)
               else track.duration_s)
        f0, f1 = round(start * fps), round(end * fps)
        asset_id = scene_asset_id(scene)
        if scene.visual.kind == "footage":
            out.append(dict(scene=scene, asset_id=asset_id, start=start, end=end, f0=f0, f1=f1,
                            canvas=None, plan=None, prev=None, continuation=False))
            prev = None
            continue
        canvas = scene_canvas(scene, theme, channel)
        assert canvas is not None
        steps = parse_steps(scene.visual.steps, canvas.max_step)
        cont = (prev is not None and prev[0] == asset_id and not scene.starts_section
                and prev[2].last_step <= steps[0])
        words = timing[scene.id].words
        anchors = [w.start - start for k, w in enumerate(words)
                   if k == 0 or words[k - 1].word.rstrip('"\')').endswith((".", "?", "!"))]
        plan = plan_scene(canvas, steps, end - start, camera=scene.visual.camera,
                          anchors=anchors,
                          start_shot=prev[2].end_shot if cont else None,
                          start_prev_step=prev[2].last_step if cont else -1)
        out.append(dict(scene=scene, asset_id=asset_id, start=start, end=end, f0=f0, f1=f1,
                        canvas=canvas, plan=plan, continuation=cont,
                        prev=None if (cont or prev is None or scene.starts_section)
                        else (prev[1], prev[2])))
        prev = (asset_id, canvas, plan)
    return out


def render_episode(settings: Settings, ws: Workspace, title: str, channel: ChannelProfile,
                   board: Storyboard, track: NarrationTrack, manifest: AssetManifest, *,
                   preview: bool, scene_badges: dict[str, list[str]],
                   progress=None) -> RenderResult:
    binary = settings.ffmpeg_binary()
    profile = ffmpeg.PREVIEW if preview else ffmpeg.MASTER
    theme = Theme.from_identity(channel.visual)
    fps = profile.fps
    all_words = [w for s in track.scenes for w in s.words]
    cues = cues_from_words(all_words)
    srt_path = ws.render / f"{board.episode_id}.en.srt"
    atomic_write_text(srt_path, to_srt(cues))

    seg_dir = ws.render / f"segments_{profile.name}"
    seg_dir.mkdir(parents=True, exist_ok=True)
    fonts = "|".join(font_paths() or ("default",))
    jobs: list[dict] = []
    segments: list[Path] = []
    reused = 0
    for item in plan_episode(board, track, theme, channel, fps):
        scene = item["scene"]
        n = item["f1"] - item["f0"]
        if n <= 0:
            continue
        if item["canvas"] is None:  # user-supplied footage
            rec = manifest.get(item["asset_id"])
            if not rec:
                raise RuntimeError(f"{scene.id}: footage {item['asset_id']} not in manifest")
            src = ws.root / rec.path
            key = sha256_text(_file_key(src), str(n), profile.name)[:24]
            seg = seg_dir / f"{scene.id}-{key}.mp4"
            if seg.exists():
                reused += 1
            else:
                ffmpeg.encode_footage(binary, src, seg, n / fps, SIZE, profile)
            segments.append(seg)
            continue
        t0 = item["f0"] / fps - item["start"]
        scene_cues = []
        if preview:
            for c in assign_cues(cues, item["start"] - 5, item["end"] + 5):
                scene_cues.append((c.start - item["start"], c.end - item["start"], c.text))
        badges = scene_badges.get(scene.id, []) if preview else []
        prev = item["prev"]
        key = sha256_text(
            ENGINE_VERSION, canvas_digest(item["canvas"]), plan_digest(item["plan"]),
            canvas_digest(prev[0]) + plan_digest(prev[1]) if prev else "-",
            f"{n}:{t0:.5f}:{scene.starts_section}:{scene.ends_section}",
            repr(scene_cues), "|".join(badges), profile.name, fonts)[:24]
        seg = seg_dir / f"{scene.id}-{key}.mp4"
        segments.append(seg)
        if seg.exists():
            reused += 1
            continue
        jobs.append(dict(
            canvas=item["canvas"], plan=item["plan"], prev=prev, n_frames=n, t0=t0, fps=fps,
            size=SIZE, layer_scale=2.0, cues=scene_cues, badges=badges, theme=theme,
            fade_in=scene.starts_section, fade_out=scene.ends_section,
            font_override=visuals.FONT_OVERRIDE, binary=binary, preset=profile.preset,
            crf=profile.crf, out=str(seg)))
    if jobs:
        workers = min(render_workers(), len(jobs))
        if workers == 1:
            for j in jobs:
                _render_scene_job(j)
                if progress:
                    progress(Path(j["out"]).name)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for path, _ in pool.map(_render_scene_job, jobs):
                    if progress:
                        progress(Path(path).name)

    video_only = ws.render / f"video_only_{profile.name}.mp4"
    ffmpeg.concat_segments(binary, segments, video_only)
    music = ws.audio / "music_bed.wav"
    if not music.exists() or ffmpeg.probe_duration(binary, music) + 0.05 < track.duration_s:
        ffmpeg.make_music_bed(binary, music, track.duration_s + 1)
    suffix = "preview" if preview else "master"
    out = ws.render / f"{board.episode_id}_{suffix}.mp4"
    ffmpeg.mux_with_ducking(binary, video_only, ws.root / track.audio_path, music, out,
                            track.duration_s, profile)
    thumb = make_thumbnail(ws, title, channel, board, ws.render / "thumbnail_draft.png")
    return RenderResult(out, srt_path, thumb, ffmpeg.probe_duration(binary, out),
                        len(board.scenes), preview, reused)
