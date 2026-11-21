"""Build the YouTube release package for the Enginovue 1858 cable episode (local, free).

Writes projects/enginovue_cable_1858/release/:
  video.mp4                 copy of the final render (enginovue_1858_v4_mixed.mp4)
  captions_en.srt           captions timed to the spoken words (script text, Whisper word times)
  description.txt           description with chapters, sources and production notes
  titles.txt                title options + tags
  thumbnail_a/b/c.jpg       1280x720 thumbnail options composed from accepted frames
  RELEASE_CHECKLIST.md      what the operator still has to do before going public

Usage: py make_release.py
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import production
import qa

HERE = Path(__file__).resolve().parent
PROJ = production.PROJECT
AUDIO, OUT = PROJ / "audio", PROJ / "release"
FONTS = HERE.parents[1] / "assets" / "fonts" / "inter"
VIDEO = PROJ / "render" / "enginovue_1858_v4_mixed.mp4"

CHAPTERS = [(1, "A message across the ocean"), (14, "Ten days behind the news"), (25, "Cyrus Field's idea"),
            (31, "Thomson's warning"), (48, "The 1857 cable"), (71, "The 1858 plan"),
            (87, "The mirror galvanometer"), (107, "The inquiry"), (115, "The Great Eastern"),
            (132, "Two working cables"), (142, "Undersea cables today")]

SOURCES = [
    "Henry M. Field, History of the Atlantic Telegraph (1866) — https://archive.org/details/historyatlantic00fielrich",
    "Charles Bright, The Story of the Atlantic Cable (1903) — https://www.gutenberg.org/ebooks/34765",
    "Silvanus P. Thompson, The Life of William Thomson, Baron Kelvin of Largs (1910) — "
    "https://archive.org/details/lifeofwilliamtho01thomuoft",
    "Bruce J. Hunt, \"Wildman Whitehouse, William Thomson and the First Atlantic Cable\", in Imperial Science "
    "(Cambridge University Press, 2021) — https://www.cambridge.org/core/product/28CC0EE56CCC49F8170F92A364BBBEF9/core-reader",
    "Science Museum Group: Thomson's mirror galvanometer, 1858 — "
    "https://collection.sciencemuseumgroup.org.uk/objects/co32961/thomsons-mirror-galvanometer-1858",
    "Science Museum Group: Whitehouse's induction coil, 1858 — "
    "https://collection.sciencemuseumgroup.org.uk/objects/co32894/whitehouses-induction-coil-1858",
    "Science Museum Group: sample of the 1857–58 deep-sea cable — "
    "https://collection.sciencemuseumgroup.org.uk/objects/co33447/sample-of-deep-sea-section-of-first-transatlantic-cable-1857-1858-cable",
    "IET Archives: The first transatlantic telegraph cable, 1858 — "
    "https://www.theiet.org/membership/library-and-archives/the-iet-archives/archives-highlights/the-first-transatlantic-telegraph-cable-1858",
    "Royal Museums Greenwich: Celebrating the submarine telegraph cable, 1858 — "
    "https://rmg.co.uk/stories/blog/celebrating-submarine-telegraph-cable-1858",
    "Smithsonian Magazine on Tiffany & Co. and the cable souvenirs — "
    "https://www.smithsonianmag.com/history/to-make-tiffany-co-a-household-name-the-luxury-brands-founder-cashed-in-on-the-trans-atlantic-telegraph-craze-180983782/",
    "PBS American Experience: The cable attempts — "
    "https://www.pbs.org/wgbh/americanexperience/features/cable-attempts-lay-transatlantic-cable/",
    "University of Glasgow: Kelvin and the Atlantic cable — "
    "https://www.gla.ac.uk/myglasgow/library/files/special/exhibns/Kelvin/atlanticcable.html",
    "Canada's Historic Places: Heart's Content Cable Station — "
    "https://www.historicplaces.ca/en/rep-reg/place-lieu.aspx?id=3057",
    "ITU, Abuja declaration on submarine cable resilience (2025) — "
    "https://www.itu.int/digital-resilience/submarine-cables/wp-content/uploads/sites/2/2025/02/summit-declaration-nigeria-2025.pdf",
    "TeleGeography: Submarine cable FAQ — https://www2.telegeography.com/submarine-cable-faqs-frequently-asked-questions",
]


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

def captions(timing: dict) -> str:
    """Script words get the times of the recognised words they match (interpolated otherwise), then are grouped
    into cues of <= 42 characters / <= 5.5 s, broken preferably at sentence ends and commas."""
    chunks = json.loads((AUDIO / "narration_chunks.json").read_text(encoding="utf-8"))
    rec_all = json.loads((AUDIO / "narration_words.json").read_text(encoding="utf-8"))
    t0, words = timing["intro_s"], []
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
            words.append((w, t0 + st[i][0], t0 + st[i][1]))
        t0 += duration(AUDIO / "narration" / f"ch{c['chunk']:02d}.mp3") + timing["gap_s"]
    cues, cur = [], []
    for w in words:
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
    return qa.to_169(Image.open(PROJ / d["file"]).convert("RGB"))[0].resize((1280, 720), Image.Resampling.LANCZOS)


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


# ---------------------------------------------------------------- main

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    timing = json.loads((AUDIO / "narration_timing.json").read_text(encoding="utf-8"))
    start = {f["n"]: f["start"] for f in timing["frames"]}
    shutil.copy2(VIDEO, OUT / "video.mp4")
    (OUT / "captions_en.srt").write_text(captions(timing), encoding="utf-8")

    chapters = "\n".join(f"{'0:00' if n == 1 else mmss(start[n])} {name}" for n, name in CHAPTERS)
    desc = f"""In August 1858 a cable across the Atlantic carried Queen Victoria's 98-word message to President Buchanan — and it took about sixteen hours to get through. A month later the line was dead. This is the engineering story of why the first transatlantic telegraph failed, what William Thomson understood that others didn't, and how the Great Eastern finally made it work in 1866.

Chapters
{chapters}

Sources
""" + "\n".join(f"• {s}" for s in SOURCES) + """

Notes
• All facts in the narration were checked against the sources above; where sources disagree (for example 98 vs 99 words in the Queen's message, or the coil voltages) the script uses the commonly cited figure or a rounded value.
• Illustrations and the two short animated shots are AI-generated in an original cartoon style; they are interpretations, not historical photographs. The narration voice and the music are AI-generated. Diagrams and charts were made for this video.

#history #engineering #telegraph
"""
    (OUT / "description.txt").write_text(desc, encoding="utf-8")
    (OUT / "titles.txt").write_text(
        "Title options (pick one, ≤ 70 characters):\n"
        "1. The Cable That Changed the World: The First Transatlantic Telegraph\n"
        "2. 98 Words in 16 Hours: Why the First Atlantic Cable Failed\n"
        "3. The 1858 Atlantic Cable Died in a Month. Here's Why.\n\n"
        "Tags: transatlantic cable, atlantic telegraph, 1858, cyrus field, lord kelvin, william thomson, "
        "great eastern, submarine cable, telegraph history, engineering history, undersea cables\n", encoding="utf-8")

    thumb(10, [("IT DIED", 130), ("IN A MONTH", 130), ("THE 1858 ATLANTIC CABLE", 40)], "left", OUT / "thumbnail_a.jpg", "left")
    thumb(1, [("98 WORDS.", 120), ("16 HOURS.", 120), ("THE FIRST MESSAGE ACROSS THE ATLANTIC", 34)], "right",
          OUT / "thumbnail_b.jpg", "right")
    thumb(75, [("2,000 MILES", 118), ("OF OCEAN", 118), ("THE FIRST ATLANTIC CABLE, 1858", 40)], "left", OUT / "thumbnail_c.jpg", "left")
    print("\n".join(str(p) for p in sorted(OUT.iterdir())))


if __name__ == "__main__":
    main()
