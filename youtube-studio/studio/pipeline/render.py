"""Render an episode as an animated 30 fps MP4 (FFmpeg): 1920x1080, or 1080x1920 for a Short.

For every storyboard shot (frames.txt):
  * picture = accepted image from the production state (production decisions), or an accepted
    image-to-video clip from state["anim"] (slowed with motion interpolation if the slot is longer, never
    frozen); a clearly marked placeholder card is used if a frame has no accepted image yet;
  * camera move from CAMERA in frames.txt, else from the ANIM camera hint, else by shot type: push-in,
    pull-out, pans, tilts, drift, handheld sway, snap shake; never the same move twice in a row; chart frames
    and "no push to edge" frames get a barely visible centred move;
  * local effects from FX: rain, lightning@t, rising bubbles and motes, lamp (auto from the scene text),
    fire and spark flicker; chart overlays fade in; editor titles (titles.py) fade in with a small rise;
    CHAPTER frames dip to black;
  * duration = the aligned narration slot (narration_timing.json) or, with --silent, the storyboard slot.
Shorts (format: short): no dips to black (the video loops), and word-timed captions are burned in
(2-3 words at a time, large bold type, above the YouTube interface at ~64 % height).
Original images are only read. Output: projects/<slug>/render/<name>.mp4 + .srt + render report.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import frames as frames_mod
from . import production, qa, titles
from .episode import FONTS, ep

W, H, FPS = 1920, 1080, 30      # set per episode format in run()
SRC = (3840, 2160)               # supersampled source: sub-pixel smooth camera moves
CAPTION_Y = 0.64                 # Shorts: caption centre (fraction of the height)
CAPTION_X = 0.50                 # Shorts: centred (operator preference 2026-11-22)
NAVY, TURQ, SILVER = (7, 27, 53), (34, 229, 239), (237, 234, 241)
FONT_B = FONTS / "Inter-Bold.ttf"
FONT_R = FONTS / "Inter-Regular.ttf"
LIGHTNING_T = 1.3                          # default lightning time when FX has no @t
LAMP_RE = re.compile(r"oil lamp|lamplight|candle|gas ?lamp|gaslight|lantern|firelight|fireplace|lamp", re.I)
STATIC_NOTES = ("push", "edge", "headroom")   # editing notes that forbid moving toward an edge

# Camera moves: zoom z0->z1, centre (fraction of the image) c0->c1. Ranges keep the crop inside.
MOVES = {
    "push_in":   (1.00, 1.07, (0.50, 0.50), (0.50, 0.50)),
    "pull_out":  (1.08, 1.01, (0.50, 0.50), (0.50, 0.50)),
    "pan_lr":    (1.08, 1.08, (0.470, 0.50), (0.530, 0.50)),
    "pan_rl":    (1.08, 1.08, (0.530, 0.50), (0.470, 0.50)),
    "tilt_up":   (1.08, 1.08, (0.50, 0.535), (0.50, 0.465)),
    "tilt_down": (1.08, 1.08, (0.50, 0.465), (0.50, 0.535)),
    "drift":     (1.03, 1.07, (0.485, 0.51), (0.515, 0.49)),
    "sway":      (1.10, 1.10, (0.50, 0.50), (0.50, 0.50)),
    "snap":      (1.08, 1.08, (0.50, 0.50), (0.50, 0.50)),
    "settle":    (1.04, 1.04, (0.50, 0.50), (0.50, 0.50)),   # sparks: tiny tremor only
    "breathe_in":  (1.000, 1.025, (0.50, 0.50), (0.50, 0.50)),  # chart frames: barely-there centred move
    "breathe_out": (1.025, 1.000, (0.50, 0.50), (0.50, 0.50)),  # "no push to edge" frames: ends on the full frame
}
BY_SHOT = {"wide": ["pan_lr", "pan_rl", "drift"], "medium": ["push_in", "drift", "pull_out"],
           "close": ["pull_out", "push_in", "drift"], "macro": ["drift", "pull_out", "push_in"],
           "cutaway": ["tilt_down", "push_in", "pan_lr"], "infographic": ["push_in", "drift", "pull_out"],
           "dynamic": ["push_in", "snap"]}


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        sys.exit("ffmpeg not found on PATH")
    return exe


def names() -> dict[str, str]:
    """Output names: silent picture, narration only, full mix (episode.yaml render_names)."""
    slug = ep().slug
    return {"silent": f"{slug}_silent", "voiced": f"{slug}_voiced", "mixed": f"{slug}_final",
            **(ep().cfg.get("render_names") or {})}


def timeline(frames: list[dict]) -> list[dict]:
    return [{"n": str(f["n"]), "duration_s": str(f["duration"]),
             "gfx_overlay": f"overlays/{f['gfx_file']}" if f["gfx_file"] else "",
             "overlay": f["overlay"], "voiceover": f["vo"]} for f in frames]


def ts(sec: float) -> str:
    ms = round(sec * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


# ---------------------------------------------------------------- layers

def gfx_layer(gfx: Path | None) -> Image.Image | None:
    """Exact chart overlay (overlays.py). Editor titles are a separate animated layer (titles.py)."""
    if not (gfx and gfx.is_file()):
        return None
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.alpha_composite(Image.open(gfx).convert("RGBA"))
    return layer


def placeholder(n: int, ru: str) -> Image.Image:
    img = Image.new("RGB", SRC, NAVY)
    d = ImageDraw.Draw(img)
    k = SRC[0] / 3840                     # narrower text on a vertical (Shorts) source
    big = ImageFont.truetype(str(FONT_B), round(160 * k))
    small = ImageFont.truetype(str(FONT_R), round(72 * k))
    d.text((SRC[0] / 2, SRC[1] / 2 - 100), f"FRAME #{n} — NOT GENERATED YET", font=big, fill=TURQ, anchor="mm")
    d.text((SRC[0] / 2, SRC[1] / 2 + 100), ru[:round(80 * k)], font=small, fill=SILVER, anchor="mm")
    return img


def particle_tiles(work: Path) -> dict[str, Path]:
    """Seamless 1920x2160 RGBA tiles (two identical stacked 1920x1080 halves) scrolled vertically."""
    out = {}
    for kind in ("rain", "bubbles"):
        p = work / f"tile_{kind}_{W}x{H}.png"
        out[kind] = p
        if p.is_file():
            continue
        rnd = random.Random(1858)
        k = W * H / (1920 * 1080)      # same density in either orientation
        half = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(half)
        if kind == "rain":
            for _ in range(round(520 * k)):
                x, y, ln = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(30, 70)
                a = rnd.randint(50, 120)
                for dy in (0, H, -H):           # wrap vertically so the tile is seamless
                    d.line([(x, y + dy), (x - ln * 0.18, y + dy + ln)], fill=(200, 225, 245, a), width=2)
        else:
            for _ in range(round(70 * k)):       # bubbles
                x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(3, 11)
                for dy in (0, H, -H):
                    d.ellipse([x - r, y + dy - r, x + r, y + dy + r], outline=(190, 245, 250, 120), width=2)
                    d.ellipse([x - r * 0.45, y + dy - r * 0.55, x - r * 0.05, y + dy - r * 0.15],
                              fill=(230, 255, 255, 110))
            for _ in range(round(160 * k)):      # suspended motes
                x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1, 2.6)
                for dy in (0, H, -H):
                    d.ellipse([x - r, y + dy - r, x + r, y + dy + r], fill=(170, 230, 235, rnd.randint(40, 100)))
        tile = Image.new("RGBA", (W, 2 * H))
        tile.paste(half, (0, 0))
        tile.paste(half, (0, H))
        tile.save(p)
    return out


# ---------------------------------------------------------------- planning

def camera_hint(anim: str) -> str | None:
    cam = anim.split("||")[1].lower() if anim.count("||") >= 1 else ""
    for key, move in (("pull-back", "pull_out"), ("pull back", "pull_out"), ("pull-out", "pull_out"),
                      ("crane-up", "tilt_up"), ("tilt upward", "tilt_up"), ("tilt toward the water", "tilt_down"),
                      ("left to right", "pan_lr"), ("right to left", "pan_rl"), ("pan", "pan_lr"),
                      ("orbit", "drift"), ("follows", "pan_rl"), ("handheld", "sway"), ("rocks", "sway"),
                      ("shake", "snap"), ("push-in", "push_in"), ("static", "static")):
        if key in cam:
            return move
    return None


def plan(rows: list[dict], frames: dict[int, dict], notes: dict[int, str], anim_ok: set[int]) -> dict[int, dict]:
    out, prev, rot = {}, None, {}
    prev_title = None
    chapter_frames = {k for k, _ in frames_mod.chapters(list(frames.values()))}
    for r in rows:
        n = int(r["n"])
        f = frames[n]
        gfx = bool(r["gfx_overlay"])
        hint = camera_hint(f.get("anim", ""))
        if n in anim_ok:
            move = "ai_clip"
        elif f.get("camera"):
            move = f["camera"]
        elif any(k in notes.get(n, "").lower() for k in STATIC_NOTES):
            move = "breathe_out"     # never a frozen picture; ends on the uncropped frame
        elif gfx:
            move = "breathe_in"
        elif hint and hint != "static":
            move = hint
        else:
            opts = BY_SHOT.get(f["shot"], ["push_in", "drift", "pull_out"])
            if hint == "static" and f["shot"] in ("infographic", "medium", "close", "macro"):
                opts = ["drift", "push_in", "pull_out"]
            i = rot.get(f["shot"], n) % len(opts)
            move = opts[i]
            if move == prev:
                move = opts[(i + 1) % len(opts)]
            rot[f["shot"]] = i + 1
        if move == prev and move not in ("static", "ai_clip"):     # never repeat a move back-to-back
            alt = {"pan_lr": "pan_rl", "pan_rl": "pan_lr", "push_in": "drift", "drift": "pull_out",
                   "pull_out": "push_in", "tilt_up": "drift", "tilt_down": "drift"}.get(move)
            if alt:
                move = alt
        tags = {t.split("@")[0]: t for t in f.get("fx", [])}
        fx, lt = [], LIGHTNING_T
        if "rain" in tags:
            fx.append("rain")
        if "lightning" in tags:
            fx.append("lightning")
            lt = float(tags["lightning"].split("@")[1]) if "@" in tags["lightning"] else LIGHTNING_T
        if "bubbles" in tags:
            fx.append("bubbles")
        if "sparks" in tags:
            fx.append("sparks")
        elif "fire" in tags:
            fx.append("fire")
        elif "lamp" in tags or ("nolamp" not in tags and LAMP_RE.search(f["scene"])):
            fx.append("lamp")
        title = (r["overlay"], r["gfx_overlay"])
        fade_title = title != prev_title and any(title)
        short = ep().vertical       # a Short starts on the hook and loops: no dips to black
        out[n] = {"move": move, "fx": fx, "lightning_t": lt, "fade_title": fade_title,
                  "dip_in": not short and (n in chapter_frames or n == int(rows[0]["n"])),
                  "dip_out": not short and ((n + 1) in chapter_frames or n == int(rows[-1]["n"]))}
        prev, prev_title = move, title
    return out


# ---------------------------------------------------------------- filters

def cam_filter(move: str, frames: int) -> str:
    if move == "static":
        return f"scale={W}:{H}:flags=lanczos"
    z0, z1, (cx0, cy0), (cx1, cy1) = MOVES[move]
    F = max(1, frames - 1)
    e = f"(0.5*on/{F}+0.5*(0.5-0.5*cos(PI*on/{F})))"            # half linear, half eased
    z = f"{z0}+({z1 - z0})*{e}"
    cx = f"({cx0}+({cx1 - cx0})*{e})*iw"
    cy = f"({cy0}+({cy1 - cy0})*{e})*ih"
    sx = sy = "0"
    if move == "sway":       # slow rolling ship, in source pixels
        sx, sy = "26*sin(on*0.071)+9*sin(on*0.19)", "40*sin(on*0.093+1)+8*sin(on*0.23)"
    elif move == "snap":     # sharp jolt around 0.35 s that dies away
        env = "exp(-pow(max(on-10,0)/9,1))*gte(on,10)"
        sx, sy = f"34*{env}*sin(on*2.3)", f"46*{env}*sin(on*2.9+0.7)"
    elif move == "settle":   # electric tremor
        sx, sy = "6*sin(on*3.1)+4*sin(on*5.3)", "6*sin(on*2.7+1)+4*sin(on*4.9)"
    x = f"clip({cx}-iw/zoom/2+{sx},0,iw-iw/zoom)"
    y = f"clip({cy}-ih/zoom/2+{sy},0,ih-ih/zoom)"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}"


def light_filter(fx: list[str], lightning_t: float = 1.3) -> str | None:
    terms = []
    if "lamp" in fx:
        terms.append("0.012*sin(t*9.1)+0.008*sin(t*23.3)+0.006*sin(t*4.1)")
    if "fire" in fx:
        terms.append("0.025*sin(t*11.3)+0.018*sin(t*27.1)+0.012*sin(t*5.7)")
    if "sparks" in fx:
        terms.append("0.05*pow(max(sin(t*13.7)*sin(t*7.3),0),3)+0.035*pow(max(sin(t*19.1),0),8)")
    if "lightning" in fx:
        t0 = lightning_t
        terms.append(f"0.32*exp(-pow((t-{t0})*9,2))+0.18*exp(-pow((t-{t0 + 0.22})*11,2))")
    return f"eq=eval=frame:brightness='{'+'.join(terms)}'" if terms else None



def render_clip(n: int, p: dict, src: Image.Image | Path, layer: Image.Image | None, title: Image.Image | None,
                dur: float,
                tiles: dict[str, Path], work: Path, crf: int) -> Path:
    clip = work / f"v2_clip_{n:03d}.mp4"
    frames = max(1, round(dur * FPS))
    inputs: list[str] = []
    if isinstance(src, Path):                    # AI clip: fill the frame, trim to the slot
        inputs += ["-i", str(src)]
        clip_s = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                       str(src)], capture_output=True, text=True, check=True).stdout)
        k = max(1.0, (dur + 0.05) / clip_s)        # slow down (never freeze) when the slot is longer than the clip
        slow = (f"setpts={k:.4f}*PTS,minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
                if k > 1.001 else f"fps={FPS},")
        chain = [f"[0]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{slow}"
                 f"trim=end_frame={frames},setpts=PTS-STARTPTS"]
    else:
        base = work / f"v2_base_{n:03d}.png"
        size = (W, H) if p["move"] == "static" else SRC
        src.resize(size, Image.Resampling.LANCZOS).save(base)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(base)]
        chain = [f"[0]{cam_filter(p['move'], frames)}"]
    chain[-1] += ",setsar=1,format=yuv420p"
    lf = light_filter(p["fx"], p.get("lightning_t", LIGHTNING_T))
    if lf:
        chain[-1] += "," + lf
    chain[-1] += "[v0]"
    cur, k = "v0", 1
    for kind, sign, speed in (("rain", 1, 1500), ("bubbles", -1, 70)):
        if kind in p["fx"]:
            inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(tiles[kind])]
            yexpr = f"mod(t*{speed},{H})-{H}" if sign > 0 else f"-mod(t*{speed},{H})"
            xexpr = "-30*t" if kind == "rain" else "8*sin(t*1.3)"
            chain.append(f"[{k}]format=rgba[p{k}];[{cur}][p{k}]overlay=x='{xexpr}':y='{yexpr}':eval=frame[v{k}]")
            cur, k = f"v{k}", k + 1
    if layer is not None:
        over = work / f"v2_over_{n:03d}.png"
        layer.save(over)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(over)]
        fade = ",fade=in:st=0.25:d=0.45:alpha=1" if p["fade_title"] else ""
        chain.append(f"[{k}]format=rgba{fade}[t];[{cur}][t]overlay=0:0[v{k}]")
        cur, k = f"v{k}", k + 1
    if title is not None:     # title: fades in with a small rise, fades out before the cut
        tpath = work / f"v2_title_{n:03d}.png"
        title.save(tpath)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(tpath)]
        t_in, t_out = 0.3, max(0.9, dur - 0.45)
        chain.append(f"[{k}]format=rgba,fade=in:st={t_in}:d=0.45:alpha=1,fade=out:st={t_out:.3f}:d=0.35:alpha=1[ti];"
                     f"[{cur}][ti]overlay=x=0:y='14*min(1,max(0,1-(t-{t_in})/0.55))':eval=frame[v{k}]")
        cur, k = f"v{k}", k + 1
    tail = []
    if p["dip_in"]:
        tail.append("fade=in:st=0:d=0.4")
    if p["dip_out"]:
        tail.append(f"fade=out:st={dur - 0.4:.3f}:d=0.4")
    tail.append("format=yuv420p")
    chain.append(f"[{cur}]{','.join(tail)}[o]")
    cmd = [ffmpeg(), "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", "[o]",
           "-frames:v", str(frames), "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", str(clip)]
    subprocess.run(cmd, check=True)
    return clip


# ---------------------------------------------------------------- Shorts captions

def caption_groups(words: list[tuple[str, float, float]], max_chars: int = 16,
                   max_words: int = 3) -> list[tuple[str, float, float]]:
    """2-3 spoken words per caption; a group also ends at a sentence end or comma."""
    groups: list[list[tuple[str, float, float]]] = []
    cur: list[tuple[str, float, float]] = []
    for w in words:
        if cur and (len(" ".join(x[0] for x in [*cur, w])) > max_chars or len(cur) >= max_words):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.?!,;:]$", w[0]):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    out = []
    for i, g in enumerate(groups):
        start, end = g[0][1], g[-1][2] + 0.15
        if i + 1 < len(groups):
            end = min(end, groups[i + 1][0][1])
        out.append((caption_text(" ".join(x[0] for x in g)), start, max(end, start + 0.35)))
    return [o for o in out if o[0]]


def caption_text(s: str) -> str:
    """Burned captions read cleaner without commas, full stops, colons, quotes or dashes; '?' and '!' stay, as do
    separators inside numbers (6,000 / 1.5) and apostrophes."""
    s = re.sub(r"(?<!\d)[.,](?!\d)|[.,](?=\s|$)|[;:…“”\"]|(?<!\w)[-–—]+(?!\w)", "", s)
    return re.sub(r"\s+", " ", s).strip()


def ass_time(t: float) -> str:
    cs = max(0, round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def captions_ass(groups: list[tuple[str, float, float]], offset: float = 0.0) -> str:
    """ASS script: white Inter Display ExtraBold with a dark outline, centred horizontally."""
    x, y = round(CAPTION_X * W), round(CAPTION_Y * H)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Cap,Inter Display ExtraBold,84,&H00FFFFFF,&H00FFFFFF,&H00201208,&H64000000,0,0,0,0,100,100,0,0,"
            "1,7,3,5,60,60,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = [f"Dialogue: 0,{ass_time(s - offset)},{ass_time(e - offset)},Cap,,0,0,0,,"
          f"{{\\pos({x},{y})\\fad(60,0)}}{text}" for text, s, e in groups if e > offset]
    return head + "\n".join(ev) + "\n"


def burn_captions(video: Path, t_start: float, length: float, work: Path) -> None:
    """Burn word-timed captions into a Short (re-encodes the picture, copies the audio)."""
    import os

    from . import release
    timing = json.loads((ep().audio / "narration_timing.json").read_text(encoding="utf-8"))
    groups = [g for g in caption_groups(release.words(timing)) if g[1] < t_start + length]
    ass = work / "captions.ass"
    ass.write_text(captions_ass(groups, offset=t_start), encoding="utf-8")
    fonts = Path(os.path.relpath(FONTS, work)).as_posix()
    tmp = video.with_name(video.stem + "_nocap.mp4")
    video.replace(tmp)
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(tmp), "-vf", f"subtitles=captions.ass:fontsdir={fonts}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", str(video)], check=True, cwd=work)
    tmp.unlink()


# ---------------------------------------------------------------- main

def run(only: str | None = None, crf: int = 18, plan_only: bool = False, silent: bool = False,
        remux: bool = False, out: Path | None = None) -> Path | None:
    """Render (or print the motion plan with plan_only). Returns the video path."""
    from types import SimpleNamespace
    if ep().style().get("engine") == "whatif" and not plan_only:     # mocap stickmen engine (studio/whatif)
        from ..whatif import render as whatif_render
        return whatif_render.run(only=only, crf=crf, silent=silent)
    a = SimpleNamespace(only=only, crf=crf, plan=plan_only, silent=silent, remux=remux)
    global W, H, SRC
    W, H = ep().size
    SRC = (2 * W, 2 * H)
    NARRATION = ep().audio
    out = Path(out) if out else ep().render_dir
    work = out / "work_v2"
    work.mkdir(parents=True, exist_ok=True)
    parsed = frames_mod.parse()
    rows = timeline(parsed)
    if a.only:
        lo, hi = (int(x) for x in a.only.split("-"))
        rows = [r for r in rows if lo <= int(r["n"]) <= hi]
    state = production.load_state()
    dec = production.decisions(state)
    notes = {int(n): f.get("note", "") for n, f in state["frames"].items()}
    frames = {f["n"]: f for f in parsed}
    anim = {int(n): v for n, v in state.get("anim", {}).items()
            if v.get("decision") == "accepted" and (ep().work / v["file"]).is_file()}
    pl = plan(rows, frames, notes, set(anim))
    if a.plan:
        for n, p in pl.items():
            print(f"#{n:<4} {frames[n]['shot']:<12} {p['move']:<10} {','.join(p['fx']) or '-':<16} "
                  f"{'title-fade ' if p['fade_title'] else ''}{'dip-in ' if p['dip_in'] else ''}"
                  f"{'dip-out' if p['dip_out'] else ''}")
        return None
    timing_file = NARRATION / "narration_timing.json"
    voiced = timing_file.is_file() and not a.silent
    timing = {f["n"]: f for f in json.loads(timing_file.read_text(encoding="utf-8"))["frames"]} if voiced else {}
    tiles = particle_tiles(work)
    layout = titles.specs()          # title text (frames.txt) + placement (title_layout.json)
    clips, report, srt, t = [], [], [], 0.0
    for r in rows:
        n = int(r["n"])
        dur = timing[n]["duration"] if voiced else float(r["duration_s"])
        p = pl[n]
        gfx = ep().src / r["gfx_overlay"] if r["gfx_overlay"] else None
        if n in anim:
            src: Image.Image | Path = ep().work / anim[n]["file"]
            source = anim[n]["file"]
        else:
            d = dec.get(n, {})
            path = ep().work / d["file"] if d.get("decision") in production.ACCEPTED and d.get("file") else None
            if path and path.is_file():
                src, source = qa.to_frame(Image.open(path).convert("RGB"))[0], d["file"]
            else:
                src, source = placeholder(n, frames[n]["ru"]), "PLACEHOLDER"
                p["move"] = "static"
        clip = work / f"v2_clip_{n:03d}.mp4"
        spec = layout.get(n)
        if a.remux and clip.is_file():
            clips.append(clip)
        else:
            clips.append(render_clip(n, p, src, gfx_layer(gfx), titles.draw(spec) if spec else None, dur, tiles,
                                     work, a.crf))
        fx = ", ".join(p["fx"]) or "—"
        trans = " ".join(x for x, on in (("dip-in", p["dip_in"]), ("dip-out", p["dip_out"])) if on) or "cut"
        report.append(f"| #{n} | {ts(t)[:8]} | {dur:.2f}s | {source} | {p['move']} | {fx} | {trans} | "
                      f"{(spec['main'] + (' / ' + spec['sub'] if spec.get('sub') else '') + ' @ ' + spec['pos']) if spec else '—'} | "
                      f"{Path(r['gfx_overlay']).name if gfx else '—'} |")
        srt.append(f"{len(srt) + 1}\n{ts(t)} --> {ts(t + dur)}\n{r['voiceover']}\n")
        t += dur
        print(f"#{n:<4} {p['move']:<9} {fx:<22} {source}", flush=True)
    nm = names()
    base_stem = (nm["mixed"] if (NARRATION / "mix_full.wav").is_file() else nm["voiced"]) if voiced else nm["silent"]
    stem = base_stem if not a.only else f"{base_stem}_preview_{a.only}"
    lst = work / f"concat_{stem}.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    video = out / f"{stem}.mp4"
    if voiced:      # narration track, cut to the rendered range, loudness-normalised for YouTube
        t_start = timing[int(rows[0]["n"])]["start"]
        mix = NARRATION / "mix_full.wav"            # full soundtrack from mix_audio.py, else narration only
        track = mix if mix.is_file() else NARRATION / "narration_full.wav"
        audio_in = ["-ss", f"{t_start:.3f}", "-t", f"{t:.3f}", "-i", str(track)]
        audio_f = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.89:level=disabled,aresample=48000", "-ac", "2", "-b:a", "192k"]
    else:
        audio_in = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        audio_f = []
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), *audio_in,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", *audio_f, "-shortest",
                    "-movflags", "+faststart", str(video)], check=True)
    (out / f"{stem}.srt").write_text("\n".join(srt), encoding="utf-8")
    if ep().vertical and voiced:
        burn_captions(video, t_start, t, work)
    missing = sum(1 for x in report if "PLACEHOLDER" in x)
    ai = sum(1 for x in report if "anim/" in x)
    (out / f"render_report_{stem}.md").write_text(
        f"# Render report — {stem}\n\nFrames: {len(report)}, duration {t:g} s, placeholders: {missing}, "
        f"AI image-to-video clips: {ai}. {W}x{H}, 30 fps, H.264"
        + (", word-timed captions burned in. " if ep().vertical and voiced else ". ")
        + (f"Narration: ElevenLabs ({ep().cfg['narration'].get('voice_name') or 'voice'}, "
           f"{ep().cfg['narration'].get('model')}); slot lengths follow the aligned narration.\n\n" if voiced
           else "Silent; the .srt holds the scripted narration per slot.\n\n")
        + "| Frame | Timecode | Slot | Picture | Camera | Effects | Transition | Title | Chart overlay |\n"
        "|---|---|---|---|---|---|---|---|---|\n" + "\n".join(report) + "\n", encoding="utf-8")
    print(f"video: {video}\nframes {len(report)}, {t:g} s, placeholders {missing}, AI clips {ai}")
    return video
