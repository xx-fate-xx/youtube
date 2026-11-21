"""Build Enginovue storyboard artifacts from frames.txt.

Outputs (next to this file):
  storyboard.md              - table: timecode, VO, frame, characters, mode, shot, animation, gfx
  prompts.jsonl              - one full image prompt (+ optional animation prompt) per frame
  prompts.md                 - the same prompts, human readable
  edit_timeline.csv          - timecode -> image/clip/overlay file names and durations for the editor
  voiceover_elevenlabs.txt   - clean narration text without visual notes
  characters_historical.md   - identity specs for recurring historical people (with evidence)
  overlays/*_gfx.svg|png     - exact chart overlays (overlays.py) for frames with a GFX line

Usage: python build.py
"""

from __future__ import annotations

import csv
import json
import re
from itertools import groupby
from pathlib import Path

import overlays

HERE = Path(__file__).resolve().parent
END_OF_VIDEO = "8:19"

# Chosen after the 4-frame model test (see projects/.../model_test): GPT Image 2.6, low quality,
# 2k output so frames reach 1920x1080 without upscaling. Changing this does not generate anything.
MODEL = "gpt_image_2_6"
PARAMS = {"aspect_ratio": "16:9", "quality": "low", "resolution": "2k"}

STYLE = (
    "ENGINOVUE TECH CARTOON style: professional digital 2D cartoon illustration for a YouTube "
    "engineering documentary. Bold, smooth, confident dark outlines; rounded friendly shapes; "
    "layered cel-shading with soft gradients inside shapes; glossy highlights on glass, metal and "
    "helmets; small local turquoise and sky-blue glows only on technological elements; clear "
    "separation of foreground, midground and background; moderate detail; one clear focal point. "
    "Color guide: deep navy #071B35, sea blue #0C5274, bright turquoise #22E5EF, sky blue #28BFF5, "
    "engineering orange #FFA51F, golden yellow #FFC342, silver-white #EDEAF1, dark graphite #242735. "
    "Stylized 2D with depth from color and shadow. Not photorealistic, not a 3D render, not anime, "
    "not stick figures, not MS Paint."
)

MODES = {
    "A": "LIGHT EXPLAINER look: by default a clean white, light grey or pale blue background, "
    "minimal clutter, large readable subjects, simple handsome engineering diagrams, soft contact "
    "shadows. For engineering analogies, charts, diagrams and equipment demonstrations keep the "
    "background plain: no random mountains, clouds, trees, landscapes or decorative props. When the "
    "scene names a specific setting (a lab, factory, ship, historical room or natural location), "
    "draw that setting as described, in the same light, uncluttered Enginovue cartoon style.",
    "B": "DARK CINEMATIC TECH look: deep navy background and atmosphere, turquoise rim light, warm "
    "orange light accents, cinematic depth, glow kept restrained.",
}

ERAS = {
    "h": "Historical setting, 1850s-1860s, drawn in the same cartoon style; people are stylized "
    "cartoon humans in accurate period clothing, ships and machines are period-accurate. Show "
    "nothing that did not exist yet at that time: no later bridges, buildings, landmarks or "
    "machines (for example no Brooklyn Bridge, which opened in 1883). Show every person's whole head, "
    "including any hat, with clear space above it; no head or hat cut by the frame edge.",
    "m": "Present-day or late 20th-century setting drawn in the same cartoon style; people are "
    "stylized cartoon humans.",
    "-": "",
}

# Each shot type carries its own composition guidance so consecutive frames vary in framing.
SHOTS = {
    "wide": "Wide establishing shot: people and machines small inside a large environment, strong "
    "sense of place and depth.",
    "medium": "Medium shot: main subject placed off-center on a rule-of-thirds line, with "
    "breathing room around it; show only the surroundings the scene describes.",
    "close": "Close-up shot: one subject large and clear, still fully inside the safe margins.",
    "macro": "Macro detail shot: a single mechanical detail large and sharp, background simplified.",
    "cutaway": "Clean technical cutaway / cross-section view, layers clearly separated.",
    "infographic": "Clean infographic composition: orderly flat layout with generous empty space.",
    "dynamic": "Dynamic dramatic angle: low or high camera, strong diagonal lines.",
}

CHARACTERS = {
    "octo": (
        "refs/octopus_engineer.png",
        "the Enginovue Octopus Engineer, matching the attached octopus reference exactly: teal-blue "
        "octopus, yellow-orange hard hat with a gear badge, round gold-rimmed goggles with glowing "
        "blue eyes, dark harness and tool belt with orange details, glowing cyan suckers and circuit "
        "lines on the head. Gear badge plates on the helmet and tool belt must be dark graphite, "
        "never brown. All tentacles and tentacle tips must remain teal-blue, never green. Preserve "
        "the original golden goggles, orange-yellow helmet, cyan suckers and dark mechanical "
        "accessories exactly as in the reference. Do not introduce new colors into the character "
        "design",
    ),
    "lynx": (
        "refs/lynx_analyst.png",
        "the Enginovue Lynx Analyst, matching the attached lynx reference exactly: dark-grey feline "
        "with pointed ears and glowing turquoise eyes, blue-lens goggles pushed up on the head, white "
        "lab coat with gear patch and cyan accents, black shirt, blue tie, dark tablet with a gear icon",
    ),
    "bit": (
        "refs/bit_robot.png",
        "Bit the robot, matching the attached robot reference exactly: small round white-silver "
        "hovering robot, dark face screen with glowing cyan smiling arc eyes and smile, round side "
        "modules with cyan rings, three small pointed legs, floating above a soft shadow",
    ),
}

# Recurring real people. `look` goes into prompts; the rest documents where it comes from.
# A reference sheet at `ref` is attached automatically once the file exists (none is generated yet).
HISTORICAL = {
    "field": {
        "name": "Cyrus West Field", "ru": "Филд", "ref": "refs/hist_field.png",
        "life": "born 30 Nov 1819; aged 34-39 in the 1854-1858 frames",
        "look": "Cyrus Field, American merchant in his mid-to-late thirties: slim, wiry build; long "
        "oval face with a high forehead and receding hairline; wavy medium-brown hair worn long and "
        "full over the ears; a chin-curtain beard along the jaw and chin with a clean-shaven upper "
        "lip (no moustache); dark 1850s frock coat, waistcoat, white high collar, black cravat",
        "evidence": [
            "Photograph 'CyrusField4.jpg', Wikimedia Commons (lead image of the English Wikipedia "
            "article; undated, 1860s-style carte de visite): high receding forehead, long wavy hair "
            "at the sides, chin beard with clean-shaven upper lip.",
            "Mathew Brady studio portrait, 1858, imperial salted paper print, Smithsonian National "
            "Portrait Gallery (npg.si.edu, 'Cyrus West Field, 1819-1892'): Field posed with a length "
            "of cable and a globe. Not inspected yet.",
        ],
        "status": "partly verified. Beard style and hairline come from a photo of uncertain date, "
        "probably the 1860s; compare with the 1858 Brady portrait before making a reference sheet. "
        "Hair colour cannot be read from monochrome photos (medium brown is an assumption).",
        "avoid": "Do not give him a moustache or a full beard; he is a businessman, not a sailor.",
    },
    "thomson": {
        "name": "William Thomson (later Lord Kelvin), 1855-1861", "ru": "Томсон",
        "ref": "refs/hist_thomson_1850s.png",
        "life": "born 26 Jun 1824; aged 31-37 in these frames; Glasgow professor from 1846",
        "look": "William Thomson, Belfast-born physics professor at Glasgow in his early thirties: slim young man "
        "with a lively, intelligent face, dark brown hair, a neat short dark beard; no spectacles, "
        "no walking stick; dark 1850s frock coat, waistcoat, white collar and dark cravat",
        "evidence": [
            "Late-life portraits (e.g. 'Heroes of the telegraph - William Thomson', 1891, and the "
            "engraving in 'Biographies of Scientific Men', Wikimedia Commons) show the full beard of "
            "his later years; they do not show how he looked in the 1850s.",
            "Silvanus P. Thompson, 'The Life of William Thomson, Baron Kelvin of Largs' (1910, "
            "2 vols, on Wikimedia Commons / Internet Archive) has dated plates. Not inspected yet.",
        ],
        "status": "NOT VERIFIED for the 1850s. The short dark beard is a provisional choice kept "
        "from the original storyboard. Check against a dated 1850s portrait before any reference "
        "sheet is generated. The spectacles in the old frame #32 had no source and were removed.",
        "avoid": "In December 1860 a curling accident broke his thigh and left him with a limp: no "
        "cane or limp in 1850s frames. No white beard (that belongs to thomson_late).",
    },
    "thomson_1866": {
        "name": "Sir William Thomson, 1866", "ru": "Томсон (1866)",
        "ref": "refs/hist_thomson_1866.png",
        "life": "aged 42 when knighted in 1866",
        "look": "William Thomson in his early forties: same face as his younger self, dark hair "
        "beginning to recede, a fuller dark beard; formal dark frock coat for a ceremony",
        "evidence": ["No dated 1866 portrait inspected yet."],
        "status": "NOT VERIFIED. Provisional bridge between the 1850s and late-life looks.",
        "avoid": "No white beard, no walking stick in the kneeling pose.",
    },
    "thomson_late": {
        "name": "William Thomson, Lord Kelvin, late life", "ru": "Кельвин",
        "ref": "refs/hist_thomson_late.png",
        "life": "Baron Kelvin from 1892, aged 68+",
        "look": "Lord Kelvin as an elderly man: full, long white beard and moustache, high balding "
        "forehead with white hair at the sides and back, thoughtful eyes, dark frock coat",
        "evidence": [
            "'Heroes of the telegraph - William Thomson' (1891) and 'Lord Kelvin (Biographies of "
            "Scientific Men)', Wikimedia Commons: long white beard and moustache, balding crown.",
        ],
        "status": "verified from late-life portraits.",
        "avoid": "Do not exaggerate age into frailty; he stays active and alert.",
    },
    "whitehouse": {
        "name": "Edward Orange Wildman Whitehouse", "ru": "Уайтхаус",
        "ref": "refs/hist_whitehouse.png",
        "life": "born 1816; aged about 40-42 in the 1856-1858 frames; surgeon from Brighton",
        "look": "Wildman Whitehouse, English surgeon turned electrician in his early forties: solid, "
        "sturdy build; full round face; high forehead with a receding hairline and thick wavy hair "
        "at the sides; bushy side-whiskers running down the cheeks to the jaw, chin and upper lip "
        "clean-shaven; dark frock coat, buttoned waistcoat with a watch chain, white shirt, dark "
        "bow tie; confident, self-assured posture",
        "evidence": [
            "Studio albumen portrait by Maull and Polyblank, London, dated 1856-1865, Science Museum "
            "Group collection object co8032132; reproduced on Wikimedia Commons as "
            "'Edward-orange-wildman-whitehouse.jpg' (lead image of the English Wikipedia article).",
        ],
        "status": "verified for the period (photograph dated 1856-1865). Hair colour cannot be read "
        "from the sepia print.",
        "avoid": "He is the story's mistaken expert, but draw him as a credible professional: no "
        "villain features, no grotesque caricature.",
    },
}

TECH = (
    "16:9 horizontal frame. Composition rules: keep safe margins of 8-10% of the frame on every "
    "side; no character, face, hand, tool, key machine part or diagram element touches or is cut by "
    "the frame edges (only scenery, water, sky and deliberately continuing objects such as long "
    "cables or pipes may run off the edge). Keep the bottom 15% of the frame a calm, uncluttered, "
    "low-detail area for subtitles, with no faces or key details in it. In medium and wide shots "
    "keep characters small enough that the whole figure fits with breathing room. Keep believable "
    "relative scale between people, tools, machines, ships and cables unless the scene is an "
    "explicit analogy; when the scene is about length, distance, size or quantity, make that scale "
    "visually obvious. Bold silhouettes, clear contrast and a few large shapes, so the image reads "
    "at small YouTube viewing size. No text, letters, numbers, captions, logos or watermarks in the "
    "image. Clean separable shapes suited to 2D image-to-video animation: clearly readable limbs, "
    "no extra limbs, no tangled overlaps, no distorted machinery."
)

GFX_RULE = (
    "An exact chart is composited over this frame in editing: do not draw any chart, graph, curve, "
    "axis, bar, waveform, scale ruler or numbers yourself, and keep the reserved area plain."
)

HIST_RULE = (
    "Draw these real people as stylized cartoon humans, recognisable by the listed traits, and keep "
    "the traits identical in every frame where they appear; respectful, no grotesque caricature. "
    "Always show the whole head, including any hat or tall hair, with clear empty space above it."
)

ANIM_TAIL = (
    "Smooth 2D animation of this exact frame. Keep the Enginovue cartoon drawing style, outlines, "
    "colors and every character design unchanged. No morphing, no new objects, no scene change."
)

HEADER = re.compile(
    r"^#(?P<n>\d+)\s*\|\s*(?P<t>\d+:\d{2})\s*\|\s*(?P<mode>[AB])\s*\|\s*(?P<shot>\w+)\s*\|"
    r"\s*(?P<chars>[\w,\-]+)\s*\|\s*(?P<era>[hm\-])\s*\|\s*(?P<overlay>.*)$"
)
NAMES = {"octo": "Осьминог", "lynx": "Линкс", "bit": "Бит"} | {
    k: v["ru"] for k, v in HISTORICAL.items()
}


def tc_seconds(tc: str) -> int:
    m, s = tc.split(":")
    return int(m) * 60 + int(s)


def tc_filename(tc: str) -> str:
    sec = tc_seconds(tc)
    return f"{sec // 3600:02d}_{sec % 3600 // 60:02d}_{sec % 60:02d}_000"


def parse(path: Path) -> list[dict]:
    frames: list[dict] = []
    cur: dict | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        m = HEADER.match(line)
        if m:
            cur = m.groupdict()
            cur["n"] = int(cur["n"])
            cur["chars"] = [] if cur["chars"] == "-" else cur["chars"].split(",")
            cur["overlay"] = "" if cur["overlay"].strip() == "-" else cur["overlay"].strip()
            frames.append(cur)
            continue
        if cur is None or line.startswith("#") or not line:
            continue
        key, _, val = line.partition(":")
        if key in {"RU", "VO", "SCENE", "ANIM", "GFX"}:
            cur[key.lower()] = val.strip()
    for i, f in enumerate(frames):
        if f["n"] != i + 1:
            raise SystemExit(f"frame numbering broken at #{f['n']}")
        for k in ("ru", "vo", "scene"):
            if not f.get(k):
                raise SystemExit(f"frame #{f['n']} missing {k}")
        if f["shot"] not in SHOTS:
            raise SystemExit(f"frame #{f['n']} unknown shot {f['shot']}")
        unknown = set(f["chars"]) - set(CHARACTERS) - set(HISTORICAL)
        if unknown:
            raise SystemExit(f"frame #{f['n']} unknown characters {unknown}")
        if f.get("gfx") and f["gfx"] not in overlays.OVERLAYS:
            raise SystemExit(f"frame #{f['n']} unknown GFX overlay {f['gfx']}")
        if f["n"] % 5 == 0 and not f.get("anim"):
            raise SystemExit(f"frame #{f['n']} is every-5th but has no ANIM")
        nxt = frames[i + 1]["t"] if i + 1 < len(frames) else END_OF_VIDEO
        f["start"] = tc_seconds(f["t"])
        f["duration"] = tc_seconds(nxt) - f["start"]
        if f["duration"] <= 0:
            raise SystemExit(f"frame #{f['n']} has non-positive duration")
        f["file"] = tc_filename(f["t"]) + ".png"
        f["gfx_file"] = tc_filename(f["t"]) + "_gfx.png" if f.get("gfx") else ""
    return frames


def check_refs() -> None:
    """Mascot references must exist; historical sheets are optional until generated."""
    missing = [ref for ref, _ in CHARACTERS.values() if not (HERE / ref).is_file()]
    if missing:
        raise SystemExit(f"missing character reference images: {missing}")


def image_prompt(f: dict) -> tuple[str, list[str]]:
    refs: list[str] = []
    mascot_lines: list[str] = []
    people_lines: list[str] = []
    for c in f["chars"]:
        if c in CHARACTERS:
            ref, desc = CHARACTERS[c]
            refs.append(ref)
            mascot_lines.append(f"Reference image {len(refs)} shows {desc}.")
        else:
            h = HISTORICAL[c]
            if (HERE / h["ref"]).is_file():
                refs.append(h["ref"])
                people_lines.append(f"Reference image {len(refs)} shows {h['look']}; match it.")
            else:
                people_lines.append(h["look"] + ".")
    parts = [STYLE, MODES[f["mode"]], ERAS[f["era"]], SHOTS[f["shot"]], "Scene: " + f["scene"]]
    if mascot_lines:
        parts.append(
            "Characters: " + " ".join(mascot_lines) + " Keep each character's design, outfit, "
            "colors and silhouette identical to its reference; only pose, expression, angle and "
            "scale may change."
        )
    else:
        parts.append("No mascot characters in this frame.")
    if people_lines:
        parts.append("Historical people: " + " ".join(people_lines) + " " + HIST_RULE)
    if f.get("gfx"):
        parts.append(GFX_RULE)
    parts.append(TECH)
    return " ".join(p for p in parts if p), refs


def anim_prompt(f: dict) -> str:
    if not f.get("anim"):
        return ""
    motion, camera, still = (s.strip() for s in f["anim"].split("||"))
    return f"Motion: {motion}. Camera: {camera}. Keep still: {still}. {ANIM_TAIL}"


def shot_report(frames: list[dict]) -> list[str]:
    """Warn about long runs of the same shot type (monotonous framing)."""
    warnings = []
    for shot, group in groupby(frames, key=lambda f: f["shot"]):
        run = list(group)
        if len(run) >= 4:
            warnings.append(f"#{run[0]['n']}-#{run[-1]['n']}: {len(run)} x {shot} in a row")
    return warnings


def characters_doc(frames: list[dict]) -> str:
    out = [
        "# Historical character identity specs (Enginovue, 1858 cable)\n",
        "Generated by build.py from the `HISTORICAL` table; edit there, not here. "
        "The `look` line goes into every prompt where the code appears in the characters column "
        "of frames.txt. A reference sheet at `ref` is attached automatically once that file "
        "exists; none has been generated yet (paid step, needs explicit approval).\n",
    ]
    for code, h in HISTORICAL.items():
        used = [f"#{f['n']}" for f in frames if code in f["chars"]]
        ref_state = "present" if (HERE / h["ref"]).is_file() else "not generated"
        out += [
            f"## `{code}` — {h['name']}\n",
            f"- Life/age in frames: {h['life']}",
            f"- Frames: {', '.join(used) or '—'}",
            f"- Reference sheet: `{h['ref']}` ({ref_state})",
            f"- Verification: {h['status']}",
            f"- Avoid: {h['avoid']}\n",
            "Prompt identity:\n",
            f"> {h['look']}\n",
            "Evidence:\n",
            *[f"- {e}" for e in h["evidence"]],
            "",
        ]
    return "\n".join(out)


def main() -> None:
    check_refs()
    frames = parse(HERE / "frames.txt")
    mode_names = {"A": "Light Explainer", "B": "Dark Cinematic Tech"}

    with (HERE / "prompts.jsonl").open("w", encoding="utf-8") as fh:
        for f in frames:
            prompt, refs = image_prompt(f)
            fh.write(json.dumps({
                "n": f["n"], "timecode": f["t"], "start_s": f["start"], "duration_s": f["duration"],
                "file": f["file"], "anim_file": f["file"].replace(".png", ".mp4") if f.get("anim") else "",
                "gfx_file": f["gfx_file"], "model": MODEL, "params": dict(PARAMS),
                "image_references": refs, "overlay_text": f["overlay"],
                "prompt": prompt, "anim_prompt": anim_prompt(f),
            }, ensure_ascii=False) + "\n")

    sb = [
        "# Раскадровка Enginovue: The Cable That Changed The World\n",
        f"Кадров: {len(frames)}. Хронометраж: {END_OF_VIDEO}. "
        f"С анимацией: {sum(1 for f in frames if f.get('anim'))}. "
        f"С точной графикой: {sum(1 for f in frames if f.get('gfx'))}. "
        "Надписи из колонки «Титр» и графика из колонки «Графика» добавляются в монтаже, "
        "в изображение не запекаются.\n",
        "| # | Таймкод | Диктор | Кадр | Герои | Режим | План | Анимация | Титр | Графика | Файл |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in frames:
        sb.append("| {n} | {t} | {vo} | {ru} | {ch} | {mode} | {shot} | {an} | {ov} | {gfx} | {file} |".format(
            n=f["n"], t=f["t"], vo=f["vo"].replace("|", "/"), ru=f["ru"],
            ch=", ".join(NAMES[c] for c in f["chars"]) or "—", mode=mode_names[f["mode"]],
            shot=f["shot"], an="да" if f.get("anim") else "—", ov=f["overlay"] or "—",
            gfx=f["gfx_file"] or "—", file=f["file"],
        ))
    (HERE / "storyboard.md").write_text("\n".join(sb) + "\n", encoding="utf-8")

    pm = [f"# Image and animation prompts ({MODEL} {PARAMS['quality']}/{PARAMS['resolution']} via Higgsfield)\n"]
    for f in frames:
        prompt, refs = image_prompt(f)
        pm.append(f"## #{f['n']} [{f['t']}] -> {f['file']}\n")
        pm.append(f"VO: {f['vo']}\n")
        pm.append(f"References: {', '.join(refs) if refs else 'none'}\n")
        if f.get("gfx"):
            pm.append(f"Overlay (composited in editing): overlays/{f['gfx_file']}\n")
        pm.append(f"```text\n{prompt}\n```\n")
        if f.get("anim"):
            pm.append(f"Animation prompt -> {f['file'].replace('.png', '.mp4')}\n")
            pm.append(f"```text\n{anim_prompt(f)}\n```\n")
    (HERE / "prompts.md").write_text("\n".join(pm), encoding="utf-8")

    with (HERE / "edit_timeline.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["n", "timecode", "start_s", "duration_s", "image", "anim_clip", "gfx_overlay",
                    "overlay", "voiceover"])
        for f in frames:
            w.writerow([f["n"], f["t"], f["start"], f["duration"], f["file"],
                        f["file"].replace(".png", ".mp4") if f.get("anim") else "",
                        f"overlays/{f['gfx_file']}" if f["gfx_file"] else "", f["overlay"], f["vo"]])

    # Frames often split one sentence across shots; join them back into flowing narration.
    text = " ".join(f["vo"] for f in frames)
    (HERE / "voiceover_elevenlabs.txt").write_text(text + "\n", encoding="utf-8")
    (HERE / "characters_historical.md").write_text(characters_doc(frames), encoding="utf-8")

    rendered = overlays.render_all([(f["gfx"], f["file"][:-4]) for f in frames if f.get("gfx")])

    words = len(text.split())
    print(f"frames={len(frames)} anim={sum(1 for f in frames if f.get('anim'))} "
          f"with_mascots={sum(1 for f in frames if set(f['chars']) & set(CHARACTERS))} "
          f"with_historical={sum(1 for f in frames if set(f['chars']) & set(HISTORICAL))} "
          f"gfx={len(rendered) // 2} words={words} wps={words / tc_seconds(END_OF_VIDEO):.2f}")
    for warn in shot_report(frames):
        print("shot variety:", warn)


if __name__ == "__main__":
    main()
