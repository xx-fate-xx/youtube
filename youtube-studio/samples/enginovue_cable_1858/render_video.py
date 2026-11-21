"""Render the Enginovue episode as an animated silent 1920x1080 30 fps MP4 (FFmpeg), v2.

For every timecode of edit_timeline.csv:
  * picture = accepted image from the production manifest (production.py decisions), or an accepted
    image-to-video clip from state["anim"] (AI clip, scaled to 1080p and trimmed to the slot);
    a clearly marked placeholder card is used if a frame has no accepted image yet;
  * camera move chosen per frame from the ANIM camera hint, else from the shot type: push-in, pull-out,
    pans, tilts, drift, handheld sway, snap shake; never the same move twice in a row; static for
    chart frames, frames whose editing note forbids a push toward an edge, and placeholders;
  * local effects: rain + lightning (storm), rising bubbles and motes (underwater), lamp / fire / spark
    flicker; chart overlays and editor titles fade in; chapter changes dip to black;
  * duration = the frame's slot in the timeline (total 8:19). Original images are only read.
Narration is added later (ElevenLabs); an .srt with the scripted narration per slot is written.

Usage: py render_video.py [--out DIR] [--only 1-20] [--crf 18] [--plan]
Output: <out>/enginovue_1858_v2_animated.mp4, .srt, render_report_v2.md (default out: projects/.../render)
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import build
import production
import qa
import titles

HERE = Path(__file__).resolve().parent
W, H, FPS = 1920, 1080, 30
SRC = (3840, 2160)               # supersampled source: sub-pixel smooth camera moves
NAVY, TURQ, SILVER = (7, 27, 53), (34, 229, 239), (237, 234, 241)
FONT_B = HERE.parents[1] / "assets" / "fonts" / "inter" / "Inter-Bold.ttf"
FONT_R = HERE.parents[1] / "assets" / "fonts" / "inter" / "Inter-Regular.ttf"
STEM = "enginovue_1858_v2_animated"
STEM_VOICED = "enginovue_1858_v3_voiced"
STEM_MIXED = "enginovue_1858_v4_mixed"     # narration + music + ambiences + effects (mix_audio.py)
NARRATION = production.PROJECT / "audio"   # narration_timing.json + narration_full.wav (align_narration.py)

# Narrative chapters: the first frame of each chapter opens with a dip from black.
CHAPTERS = {14: "The ten-day gap", 25: "Cyrus Field", 31: "Thomson's warning", 48: "The 1857 cable",
            71: "The 1858 plan", 87: "The mirror galvanometer", 107: "The inquiry",
            115: "The Great Eastern", 132: "Two working cables", 142: "Today"}
STORM = {75, 76, 77}                       # rain + handheld sway
LIGHTNING = {75}                           # lightning flashes (at LIGHTNING_T s)
LIGHTNING_T = 1.3
SNAP = {68, 121, 124}                      # decaying shake at the moment of the snap
SPARKS = {47, 100}                         # strong electric flicker
FIRE = {7}                                 # fire flicker
UNDERWATER = {10, 12, 101, 102, 103, 104, 122, 123, 129, 130, 142, 151}
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


def timeline() -> list[dict]:
    return list(csv.DictReader(open(HERE / "edit_timeline.csv", encoding="utf-8")))


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
    big = ImageFont.truetype(str(FONT_B), 160)
    small = ImageFont.truetype(str(FONT_R), 72)
    d.text((SRC[0] / 2, SRC[1] / 2 - 100), f"FRAME #{n} — NOT GENERATED YET", font=big, fill=TURQ, anchor="mm")
    d.text((SRC[0] / 2, SRC[1] / 2 + 100), ru[:80], font=small, fill=SILVER, anchor="mm")
    return img


def particle_tiles(work: Path) -> dict[str, Path]:
    """Seamless 1920x2160 RGBA tiles (two identical stacked 1920x1080 halves) scrolled vertically."""
    out = {}
    for kind in ("rain", "bubbles"):
        p = work / f"tile_{kind}.png"
        out[kind] = p
        if p.is_file():
            continue
        rnd = random.Random(1858)
        half = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(half)
        if kind == "rain":
            for _ in range(520):
                x, y, ln = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(30, 70)
                a = rnd.randint(50, 120)
                for dy in (0, H, -H):           # wrap vertically so the tile is seamless
                    d.line([(x, y + dy), (x - ln * 0.18, y + dy + ln)], fill=(200, 225, 245, a), width=2)
        else:
            for _ in range(70):                  # bubbles
                x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(3, 11)
                for dy in (0, H, -H):
                    d.ellipse([x - r, y + dy - r, x + r, y + dy + r], outline=(190, 245, 250, 120), width=2)
                    d.ellipse([x - r * 0.45, y + dy - r * 0.55, x - r * 0.05, y + dy - r * 0.15],
                              fill=(230, 255, 255, 110))
            for _ in range(160):                 # suspended motes
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
    for r in rows:
        n = int(r["n"])
        f = frames[n]
        gfx = bool(r["gfx_overlay"])
        hint = camera_hint(f.get("anim", ""))
        if n in anim_ok:
            move = "ai_clip"
        elif n in STORM:
            move = "sway"
        elif n in SNAP:
            move = "snap"
        elif n in SPARKS and n != 47:
            move = "settle"
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
        fx = []
        if n in STORM:
            fx.append("rain")
        if n in LIGHTNING:
            fx.append("lightning")
        if n in UNDERWATER:
            fx.append("bubbles")
        if n in SPARKS:
            fx.append("sparks")
        elif n in FIRE:
            fx.append("fire")
        elif LAMP_RE.search(f["scene"]):
            fx.append("lamp")
        title = (r["overlay"], r["gfx_overlay"])
        fade_title = title != prev_title and any(title)
        out[n] = {"move": move, "fx": fx, "fade_title": fade_title,
                  "dip_in": n in CHAPTERS or n == int(rows[0]["n"]),
                  "dip_out": (n + 1) in CHAPTERS or n == int(rows[-1]["n"])}
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


def light_filter(fx: list[str]) -> str | None:
    terms = []
    if "lamp" in fx:
        terms.append("0.012*sin(t*9.1)+0.008*sin(t*23.3)+0.006*sin(t*4.1)")
    if "fire" in fx:
        terms.append("0.025*sin(t*11.3)+0.018*sin(t*27.1)+0.012*sin(t*5.7)")
    if "sparks" in fx:
        terms.append("0.05*pow(max(sin(t*13.7)*sin(t*7.3),0),3)+0.035*pow(max(sin(t*19.1),0),8)")
    if "lightning" in fx:
        t0 = LIGHTNING_T
        terms.append(f"0.32*exp(-pow((t-{t0})*9,2))+0.18*exp(-pow((t-{t0 + 0.22})*11,2))")
    return f"eq=eval=frame:brightness='{'+'.join(terms)}'" if terms else None



def render_clip(n: int, p: dict, src: Image.Image | Path, layer: Image.Image | None, title: Image.Image | None,
                dur: float,
                tiles: dict[str, Path], work: Path, crf: int) -> Path:
    clip = work / f"v2_clip_{n:03d}.mp4"
    frames = max(1, round(dur * FPS))
    inputs: list[str] = []
    if isinstance(src, Path):                    # AI clip: fill 1080p, trim to the slot
        inputs += ["-i", str(src)]
        clip_s = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                       str(src)], capture_output=True, text=True, check=True).stdout)
        k = max(1.0, (dur + 0.05) / clip_s)        # slow down (never freeze) when the slot is longer than the clip
        slow = (f"setpts={k:.4f}*PTS,minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
                if k > 1.001 else f"fps={FPS},")
        chain = [f"[0]scale={W}:-2:flags=lanczos,crop={W}:{H},{slow}trim=end_frame={frames},setpts=PTS-STARTPTS"]
    else:
        base = work / f"v2_base_{n:03d}.png"
        size = (W, H) if p["move"] == "static" else SRC
        src.resize(size, Image.Resampling.LANCZOS).save(base)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(base)]
        chain = [f"[0]{cam_filter(p['move'], frames)}"]
    chain[-1] += ",setsar=1,format=yuv420p"
    lf = light_filter(p["fx"])
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


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(production.PROJECT / "render"))
    ap.add_argument("--only", help="frame range a-b for a preview")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--plan", action="store_true", help="print the motion plan and exit")
    ap.add_argument("--silent", action="store_true", help="ignore the narration; use the storyboard slot lengths")
    ap.add_argument("--remux", action="store_true", help="reuse the rendered clips; only rebuild the soundtrack mux")
    a = ap.parse_args()
    out = Path(a.out); work = out / "work_v2"; work.mkdir(parents=True, exist_ok=True)
    rows = timeline()
    if a.only:
        lo, hi = (int(x) for x in a.only.split("-"))
        rows = [r for r in rows if lo <= int(r["n"]) <= hi]
    state = production.load_state()
    dec = production.decisions(state)
    notes = {int(n): f.get("note", "") for n, f in state["frames"].items()}
    frames = {f["n"]: f for f in build.parse(HERE / "frames.txt")}
    anim = {int(n): v for n, v in state.get("anim", {}).items()
            if v.get("decision") == "accepted" and (production.PROJECT / v["file"]).is_file()}
    pl = plan(rows, frames, notes, set(anim))
    if a.plan:
        for n, p in pl.items():
            print(f"#{n:<4} {frames[n]['shot']:<12} {p['move']:<10} {','.join(p['fx']) or '-':<16} "
                  f"{'title-fade ' if p['fade_title'] else ''}{'dip-in ' if p['dip_in'] else ''}"
                  f"{'dip-out' if p['dip_out'] else ''}")
        return
    timing_file = NARRATION / "narration_timing.json"
    voiced = timing_file.is_file() and not a.silent
    timing = {f["n"]: f for f in json.loads(timing_file.read_text(encoding="utf-8"))["frames"]} if voiced else {}
    tiles = particle_tiles(work)
    layout = titles.load()           # per-frame title placement (title_layout.json)
    clips, report, srt, t = [], [], [], 0.0
    for r in rows:
        n = int(r["n"])
        dur = timing[n]["duration"] if voiced else float(r["duration_s"])
        p = pl[n]
        gfx = HERE / r["gfx_overlay"] if r["gfx_overlay"] else None
        if n in anim:
            src: Image.Image | Path = production.PROJECT / anim[n]["file"]
            source = anim[n]["file"]
        else:
            d = dec.get(n, {})
            path = production.PROJECT / d["file"] if d.get("decision") in production.ACCEPTED and d.get("file") else None
            if path and path.is_file():
                src, source = qa.to_169(Image.open(path).convert("RGB"))[0], d["file"]
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
    base_stem = (STEM_MIXED if (NARRATION / "mix_full.wav").is_file() else STEM_VOICED) if voiced else STEM
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
    missing = sum(1 for x in report if "PLACEHOLDER" in x)
    ai = sum(1 for x in report if "anim/" in x)
    (out / f"render_report_{stem}.md").write_text(
        f"# Render report — {stem}\n\nFrames: {len(report)}, duration {t:g} s, placeholders: {missing}, "
        f"AI image-to-video clips: {ai}. 1920x1080, 30 fps, H.264. "
        + ("Narration: ElevenLabs (Ryan, eleven_v4); slot lengths follow the aligned narration.\n\n" if voiced
           else "Silent; the .srt holds the scripted narration per slot.\n\n")
        + "| Frame | Timecode | Slot | Picture | Camera | Effects | Transition | Title | Chart overlay |\n"
        "|---|---|---|---|---|---|---|---|---|\n" + "\n".join(report) + "\n", encoding="utf-8")
    print(f"video: {video}\nframes {len(report)}, {t:g} s, placeholders {missing}, AI clips {ai}")


if __name__ == "__main__":
    main()
