"""YouTube release kit for an episode (local, free) -> projects/<slug>/release/.

  video.mp4             copy of the final render (full mix)
  captions_en.srt       captions timed to the spoken words (script text, Whisper word times)
  description.txt       hook, chapters (from CHAPTER lines), sources, production notes (episode.yaml release)
  titles.txt            title options + tags
  thumbnail_*.jpg       1280x720 thumbnails composed from accepted frames (episode.yaml release.thumbnails)
  RELEASE_CHECKLIST.md  what the operator still has to do before going public (upload is always Private first)
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import frames as frames_mod
from . import production, qa, render
from .episode import FONTS, ep


def mmss(t: float) -> str:
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


def srt_ts(t: float) -> str:
    ms = max(0, round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def duration(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True, check=True).stdout)


# ---------------------------------------------------------------- captions

def words(timing: dict) -> list[tuple[str, float, float]]:
    """Script words with the times of the recognised words they match (interpolated otherwise)."""
    AUDIO = ep().audio
    chunks = json.loads((AUDIO / "narration_chunks.json").read_text(encoding="utf-8"))
    rec_all = json.loads((AUDIO / "narration_words.json").read_text(encoding="utf-8"))
    t0, out = timing["intro_s"], []
    for c in chunks:
        script = c["text"].split()
        rec = rec_all[str(c["chunk"])]
        sm = difflib.SequenceMatcher(a=[norm(w) for w in script], b=[norm(w[0]) for w in rec], autojunk=False)
        st: dict[int, tuple[float, float]] = {}
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                st[a + k] = (rec[b + k][1], rec[b + k][2])
        known = sorted(st)
        for i, w in enumerate(script):
            if i not in st:          # interpolate between neighbouring anchors
                p = max((k for k in known if k < i), default=None)
                q = min((k for k in known if k > i), default=None)
                s = st[p][1] if p is not None else (st[q][0] if q is not None else 0.0)
                e = st[q][0] if q is not None else s + 0.3
                st[i] = (s + (e - s) * 0.1, e)
            out.append((w, t0 + st[i][0], t0 + st[i][1]))
        t0 += duration(AUDIO / "narration" / f"ch{c['chunk']:02d}.mp3") + timing["gap_s"]
    return out


def captions(timing: dict) -> str:
    """Word-timed script words grouped into cues of <= 42 characters / <= 5.5 s, broken preferably at sentence
    ends and commas."""
    cues, cur = [], []
    for w in words(timing):
        text = " ".join(x[0] for x in cur + [w])
        if cur and (len(text) > 42 or w[2] - cur[0][1] > 5.5):
            cues.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.?!]$", w[0]) or (re.search(r",$", w[0]) and len(" ".join(x[0] for x in cur)) > 24):
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)
    out = []
    for i, cue in enumerate(cues):
        start, end = cue[0][1], cue[-1][2] + 0.25
        if i + 1 < len(cues):
            end = min(end, cues[i + 1][0][1] - 0.02)
        end = max(end, start + 0.8)
        out.append(f"{i + 1}\n{srt_ts(start)} --> {srt_ts(end)}\n{' '.join(x[0] for x in cue)}\n")
    return "\n".join(out)


# ---------------------------------------------------------------- thumbnails

def frame(n: int) -> Image.Image:
    d = production.decisions(production.load_state())[n]
    return qa.to_frame(Image.open(ep().work / d["file"]).convert("RGB"))[0].resize((1280, 720), Image.Resampling.LANCZOS)


def thumb(n: int, lines: list[tuple[str, int]], anchor: str, out: Path, darken: str) -> None:
    img = frame(n).convert("RGBA")
    # directional darkening behind the text side for contrast (no boxes, no bars)
    g = Image.new("L", (1280, 720), 0)
    gd = ImageDraw.Draw(g)
    for x in range(1280):
        f = (1 - x / 1280) if darken == "left" else (x / 1280)
        gd.line([(x, 0), (x, 720)], fill=int(190 * max(0.0, f - 0.25) / 0.75))
    img = Image.alpha_composite(img, Image.merge("RGBA", (*[Image.new("L", (1280, 720), 6)] * 3, g)))
    x = 70 if anchor == "left" else 1210
    y = 720 / 2 - sum(s for _, s in lines) * 0.55
    for text, size in lines:
        f = ImageFont.truetype(str(FONTS / "InterDisplay-ExtraBold.ttf"), size)
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x, y + 5), text, font=f, fill=(0, 0, 0, 220), anchor="la" if anchor == "left" else "ra")
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
        col = (255, 255, 255) if size >= 90 else (190, 240, 245)
        ImageDraw.Draw(img).text((x, y), text, font=f, fill=col, anchor="la" if anchor == "left" else "ra",
                                 stroke_width=2, stroke_fill=(8, 18, 32))
        y += size * 1.12
    img.convert("RGB").save(out, quality=92)


# ---------------------------------------------------------------- kit

CHECKLIST = """# Release checklist — {title}

Package (this folder): `video.mp4`, `captions_en.srt` (word-timed), `description.txt` (chapters + sources +
production notes), `titles.txt` (title options + tags), thumbnails.

## Before upload (operator)
- [ ] Watch the whole video with headphones (automatic QA: `studio pipe check`).
- [ ] Pick a title (titles.txt) and a thumbnail.
- [ ] Check the image/video provider plan terms for commercial use of generated media.
- [ ] Optional: spot-check a few source links in description.txt.

## Upload (YouTube Studio)
- [ ] Upload `video.mp4` with visibility **Private** (or Unlisted) first — never public directly.
- [ ] Paste the description; chapters start at 0:00 and are parsed automatically.
- [ ] Subtitles -> upload file -> `captions_en.srt` (English, with timing).
- [ ] Upload the chosen thumbnail.
- [ ] Altered or synthetic content: decide per current YouTube rules (realistic-looking AI media needs
      disclosure; stylised cartoons and an AI narrator alone usually do not). Ticking "yes" is allowed if unsure.
- [ ] Audience: not made for kids unless you decide otherwise.
- [ ] Check the private upload on YouTube (quality, captions, chapters), then schedule or publish.

## Known items
{known}
"""


CHECKLIST_SHORT = """# Release checklist (Short) — {title}

Package (this folder): `video.mp4` (1080x1920, captions burned in), `captions_en.srt` (same words, for the
transcript), `description.txt` (hook + link line + sources), `titles.txt` (title options + tags).

## Before upload (operator)
- [ ] Watch the Short on a phone with sound: captions readable, nothing important under the app buttons.
- [ ] The long video it points to ({parent}) is already uploaded; put its link into the description line
      "Full story".
- [ ] Check the image/video provider plan terms for commercial use of generated media.

## Upload (YouTube Studio / app)
- [ ] Upload `video.mp4` with visibility **Private** first — never public directly. Vertical and under
      60 s, so YouTube files it as a Short.
- [ ] Title from titles.txt; paste the description.
- [ ] Related video: choose the long video ({parent}), so viewers can jump to it from the Short.
- [ ] Captions are burned in: leave YouTube's automatic captions off, or upload `captions_en.srt` only as a
      transcript if you want one.
- [ ] Altered or synthetic content: decide per current YouTube rules (stylised cartoons and an AI narrator
      alone usually do not need disclosure).
- [ ] Check the private upload, then schedule or publish (max. 3 Shorts a week per the channel plan).

## Known items
{known}
"""


def build() -> Path:
    e = ep()
    rel = e.cfg.get("release") or {}
    out = e.release_dir
    out.mkdir(parents=True, exist_ok=True)
    timing = json.loads((e.audio / "narration_timing.json").read_text(encoding="utf-8"))
    start = {f["n"]: f["start"] for f in timing["frames"]}
    video = e.render_dir / f"{render.names()['mixed']}.mp4"
    if not video.is_file():
        raise SystemExit(f"{video} not found: render the final mix first")
    shutil.copy2(video, out / "video.mp4")
    (out / "captions_en.srt").write_text(captions(timing), encoding="utf-8")
    if e.vertical:     # a Short: no chapters, a line pointing to the long video, #Shorts
        tags = list(dict.fromkeys([*rel.get("hashtags", []), "#Shorts"]))
        desc = rel.get("hook", "").strip() + "\n\nFull story: " + (rel.get("long_video") or "(link to the long video)")
        desc += "\n\nSources\n" + "\n".join(f"• {s}" for s in rel.get("sources", []))
        if rel.get("notes"):
            desc += "\n\nNotes\n" + "\n".join(f"• {s}" for s in rel["notes"])
        (out / "description.txt").write_text(desc + "\n\n" + " ".join(tags) + "\n", encoding="utf-8")
        opts = rel.get("title_options", [])
        (out / "titles.txt").write_text(
            "Title options (pick one, <= 60 characters):\n" + "".join(f"{i + 1}. {t}\n" for i, t in enumerate(opts))
            + "\nTags: " + ", ".join(rel.get("tags", [])) + "\n", encoding="utf-8")
        known = "\n".join(f"- {x}" for x in rel.get("known_items", [])) or "- none recorded"
        (out / "RELEASE_CHECKLIST.md").write_text(CHECKLIST_SHORT.format(
            title=e.cfg.get("title", e.slug), parent=e.cfg.get("parent") or "the long video", known=known),
            encoding="utf-8")
        print("\n".join(str(p) for p in sorted(out.iterdir())))
        return out
    chs = frames_mod.chapters(frames_mod.parse())
    chapters = "\n".join(f"{'0:00' if n == 1 else mmss(start[n])} {name}" for n, name in chs)
    desc = rel.get("hook", "").strip() + "\n\nChapters\n" + chapters + "\n\nSources\n" + \
        "\n".join(f"• {s}" for s in rel.get("sources", []))
    if rel.get("notes"):
        desc += "\n\nNotes\n" + "\n".join(f"• {s}" for s in rel["notes"])
    if rel.get("hashtags"):
        desc += "\n\n" + " ".join(rel["hashtags"])
    (out / "description.txt").write_text(desc + "\n", encoding="utf-8")
    opts = rel.get("title_options", [])
    (out / "titles.txt").write_text(
        "Title options (pick one, <= 70 characters):\n" + "".join(f"{i + 1}. {t}\n" for i, t in enumerate(opts))
        + "\nTags: " + ", ".join(rel.get("tags", [])) + "\n", encoding="utf-8")
    for k, th in enumerate(rel.get("thumbnails", [])):
        name = th.get("name") or f"thumbnail_{chr(97 + k)}"
        thumb(th["frame"], [tuple(x) for x in th["lines"]], th.get("side", "right"), out / f"{name}.jpg",
              th.get("side", "right"))
    known = "\n".join(f"- {x}" for x in rel.get("known_items", [])) or "- none recorded"
    (out / "RELEASE_CHECKLIST.md").write_text(CHECKLIST.format(title=e.cfg.get("title", e.slug), known=known),
                                              encoding="utf-8")
    print("\n".join(str(p) for p in sorted(out.iterdir())))
    return out
