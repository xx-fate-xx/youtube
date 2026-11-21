"""`studio pipe ...` — the video pipeline commands (local, free; paid generation runs through Claude's MCPs).

Every command takes --episode/-e (slug under episodes/ or a path); the STUDIO_EPISODE environment variable
is the default. See studio/pipeline/workflow.py for the stage order and the two operator checkpoints.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated

import typer

from .episode import ep, use

pipe_app = typer.Typer(no_args_is_help=True, help="Video pipeline: script -> images -> narration -> sound -> "
                       "render -> release (local; paid steps via Claude's MCPs after `pipe approve`)")
titles_app = typer.Typer(no_args_is_help=True, help="On-screen title placement (per frame)")
pipe_app.add_typer(titles_app, name="titles")

Ep = Annotated[str, typer.Option("--episode", "-e", envvar="STUDIO_EPISODE", help="episode slug or folder")]


def _use(e: str) -> None:
    use(e)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@pipe_app.command("new")
def new(slug: str, title: Annotated[str, typer.Option()], channel: str = "engineering_explained",
        brand: str = "Enginovue") -> None:
    """Create episodes/<slug>/ (episode.yaml, frames.txt, characters.yaml, sounds.yaml) and projects/<slug>/input/."""
    from .workflow import new_episode
    src = new_episode(slug, title, channel, brand)
    typer.echo(f"created {src}\nput reference material (competitor transcript, notes) in {ep().work / 'input'}")


@pipe_app.command("new-short")
def new_short(slug: str, title: Annotated[str, typer.Option()], parent: Annotated[str, typer.Option()]) -> None:
    """Create a YouTube Short (1080x1920) episode linked to the long video PARENT (reuses its voice, eras,
    characters and sound library)."""
    from .workflow import new_short as mk
    src = mk(slug, title, parent)
    typer.echo(f"created {src} (format: short, parent: {parent})")


@pipe_app.command("status")
def status(episode: Ep) -> None:
    """Stage overview: what is done and what is next."""
    _use(episode)
    from .workflow import status as st
    nxt = None
    for name, ok, info in st():
        typer.echo(f"{'[x]' if ok else '[ ]'} {name:<12} {info}")
        if not ok and nxt is None:
            nxt = name
    typer.echo(f"next: {nxt}" if nxt else "all stages done")


@pipe_app.command("build")
def build(episode: Ep) -> None:
    """frames.txt -> prompts.jsonl, storyboard.md, edit_timeline.csv, voiceover text, overlays."""
    _use(episode)
    from . import frames
    frames.build()


@pipe_app.command("originality")
def originality(episode: Ep, reference: Annotated[Path | None, typer.Option()] = None) -> None:
    """Compare the narration with the reference script(s) in projects/<slug>/input/ (must not reuse wording)."""
    _use(episode)
    from . import originality as o
    res = o.check(reference)
    typer.echo(json.dumps(res, ensure_ascii=False, indent=1))
    if not res["ok"]:
        raise typer.Exit(1)


@pipe_app.command("preflight")
def preflight_cmd(episode: Ep) -> None:
    """Credit estimate for the remaining paid steps vs the episode budget (generates nothing)."""
    _use(episode)
    from . import preflight
    typer.echo(json.dumps(preflight.estimate(), indent=1))


@pipe_app.command("approve")
def approve(episode: Ep, note: str = "") -> None:
    """Record the OPERATOR's approval of the script and the cost estimate (checkpoint 1). Run only after they agree."""
    _use(episode)
    from . import preflight
    rec = preflight.approve(note)
    typer.echo(f"approved {rec['at']}: Higgsfield {rec['estimate']['higgsfield']['total']:g} cr, "
               f"ElevenLabs {rec['estimate']['elevenlabs']['total']:g} cr")


# ---------------------------------------------------------------- images

@pipe_app.command("plan")
def plan(episode: Ep, batch: int = 8, reserve: float = 0.10) -> None:
    """Batches of frames still to generate + credits."""
    _use(episode)
    from . import production
    production.cmd_plan(SimpleNamespace(batch=batch, reserve=reserve))


@pipe_app.command("next")
def next_batch(episode: Ep, batch: int = 8) -> None:
    """Write the next batch as Higgsfield MCP requests (next_batch_mcp.json). Needs `pipe approve`."""
    _use(episode)
    from . import production
    production.cmd_next(SimpleNamespace(batch=batch))


@pipe_app.command("record")
def record(episode: Ep, n: int, job: str, url: str, via: str = "higgsfield-mcp",
           credits: Annotated[float | None, typer.Option()] = None, unlim: bool = False) -> None:
    """Save a generated frame (new version, read-only), run QA."""
    _use(episode)
    from . import production
    production.cmd_record(SimpleNamespace(n=n, job=job, url=url, via=via, credits=credits, unlim=unlim))


@pipe_app.command("decide")
def decide(episode: Ep, n: int, decision: str, file: str | None = None, note: str = "") -> None:
    """accept | accept_fixed | candidate | reject"""
    _use(episode)
    from . import production
    production.cmd_decide(SimpleNamespace(n=n, decision=decision, file=file, note=note))


@pipe_app.command("images")
def images(episode: Ep, verbose: bool = False) -> None:
    """Per-frame image state."""
    _use(episode)
    from . import production
    production.cmd_status(SimpleNamespace(verbose=verbose))


@pipe_app.command("report")
def report(episode: Ep, batch: int, before: float, after: float) -> None:
    """Batch report + ledger entry from the balance before/after."""
    _use(episode)
    from . import production
    production.cmd_report(SimpleNamespace(batch=batch, before=before, after=after))


@pipe_app.command("sheet")
def sheet(episode: Ep, frames: str, out: Path | None = None) -> None:
    """Contact sheets (12 per page) of the latest attempt of frames a-b, labelled with QA status, for review."""
    _use(episode)
    from PIL import Image, ImageDraw, ImageFont

    from . import production, qa
    e = ep()
    lo, hi = (int(x) for x in frames.split("-"))
    out = out or e.work / "review" / "frames"
    out.mkdir(parents=True, exist_ok=True)
    st = production.load_state()
    font = ImageFont.truetype(str(qa.FONT), 22)
    colour = {"PASS": (0, 150, 80), "WARNING": (200, 130, 0), "NEEDS_FIX": (200, 30, 30)}
    ns, cols, tw, th = list(range(lo, hi + 1)), 4, 480, 270
    if e.vertical:
        cols, tw, th = 6, 270, 480
    for page in range(0, len(ns), 12):
        chunk = ns[page:page + 12]
        rows = (len(chunk) + cols - 1) // cols
        sh = Image.new("RGB", (cols * tw + (cols - 1) * 6, rows * (th + 6)), "white")
        d = ImageDraw.Draw(sh)
        for k, n in enumerate(chunk):
            att = st["frames"].get(str(n), {}).get("attempts", [])
            x, y = (k % cols) * (tw + 6), (k // cols) * (th + 6)
            if not att:
                d.rectangle([x, y, x + tw, y + th], fill=(60, 60, 60))
                d.text((x + 8, y + 8), f"#{n} -", font=font, fill="white")
                continue
            a = att[-1]
            im = qa.to_frame(Image.open(e.frames_dir / a["file"]).convert("RGB"))[0].resize((tw, th))
            sh.paste(im, (x, y))
            d.rectangle([x, y, x + 120, y + 30], fill=colour.get(a["qa_status"], (90, 90, 90)))
            d.text((x + 6, y + 4), f"#{n} v{len(att)}", font=font, fill="white")
        p = out / f"frames_{chunk[0]:03d}-{chunk[-1]:03d}.png"
        sh.save(p)
        typer.echo(p)


@pipe_app.command("qa")
def qa_cmd(episode: Ep, paths: list[str], no_fix: bool = False) -> None:
    """Composition QA for images or folders."""
    _use(episode)
    from . import qa
    files = qa.collect(paths)
    first = Path(paths[0])
    base = first if first.is_dir() else first.parent
    for r in qa.run(files, base / "qa", fix=not no_fix, base=base):
        typer.echo(f"{r.status:9} #{r.frame or '?':<4} {Path(r.file).name}")


@pipe_app.command("record-clip")
def record_clip(episode: Ep, n: int, job: str, url: str, credits: Annotated[float, typer.Option()] = 4.0,
                model: str = "",
                resolution: str = "", duration: int = 0) -> None:
    """Save an accepted image-to-video clip for frame N (projects/<slug>/production/anim/)."""
    _use(episode)
    from . import production
    e = ep()
    a = e.cfg["animation"]
    out = e.prod / "anim" / f"anim_{n:03d}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise typer.BadParameter(f"{out} exists; clips are never overwritten")
    urllib.request.urlretrieve(url, out)
    out.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    st = production.load_state()
    st.setdefault("anim", {})[str(n)] = {
        "model": model or a["model"], "params": {"resolution": resolution or a["resolution"],
                                                 "duration": duration or a["duration"], "aspect_ratio": "16:9"},
        "job_id": job, "file": str(out.relative_to(e.work)).replace("\\", "/"),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "credits": credits, "decision": "accepted"}
    st.setdefault("ledger", []).append({"batch": f"ai clip #{n}", "frames": [n], "billing": "credits",
                                        "used": credits, "at": _now()})
    production.save_state(st)
    typer.echo(f"#{n} clip -> {out}")


# ---------------------------------------------------------------- narration + sound

@pipe_app.command("chunks")
def chunks(episode: Ep) -> None:
    """Narration takes to generate (one per CHAPTER): text, characters, target file."""
    _use(episode)
    from . import align
    for c in align.chunks():
        mark = "ok " if align.take_path(c["chunk"]).is_file() else "-- "
        typer.echo(f"{mark}ch{c['chunk']:02d} frames {c['frames'][0]}-{c['frames'][1]} {c['chars']} chars -> "
                   f"{align.take_path(c['chunk'])}")
    typer.echo(f"texts: {ep().audio / 'narration_chunks.json'}")


@pipe_app.command("save-audio")
def save_audio(episode: Ep, kind: str, ident: str, url: str, credits: float = 0.0) -> None:
    """Download a generated take/sound: kind = narration (ident = chapter number) | sfx | ambience | music."""
    _use(episode)
    from . import align, mix, production
    if kind == "narration":
        out = align.take_path(int(ident))
    elif kind in ("sfx", "spot", "ambience", "music"):
        out = mix.asset_path("music" if kind == "music" else "spot", ident)
    else:
        raise typer.BadParameter("kind must be narration, sfx, ambience or music")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise typer.BadParameter(f"{out} exists; generated audio is never overwritten (delete it first to redo)")
    urllib.request.urlretrieve(url, out)
    out.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    if credits:
        st = production.load_state()
        st.setdefault("ledger", []).append({"batch": f"{kind} {ident}", "billing": "elevenlabs_credits",
                                            "used_elevenlabs": credits, "at": _now()})
        production.save_state(st)
    typer.echo(f"{kind} {ident} -> {out}")


@pipe_app.command("align")
def align_cmd(episode: Ep) -> None:
    """Word-align the takes (local faster-whisper) -> narration_timing.json + narration_full.wav."""
    _use(episode)
    from . import align
    align.align()


@pipe_app.command("sounds")
def sounds(episode: Ep) -> None:
    """Sound library: missing assets with their ElevenLabs prompts and credit estimate."""
    _use(episode)
    from . import mix
    st = mix.status()
    for it in st["missing"]:
        extra = f" duration={it['duration']}s loop={it['loop']}" if it["kind"] != "spot" else ""
        typer.echo(f"-- {it['kind']:<8} {it['id']:<22}{extra} ~{it['credits']:g} cr | {it['prompt']}")
    typer.echo(f"present {len(st['present'])}, missing {len(st['missing'])}, ~{st['credits_missing']:g} credits")


@pipe_app.command("mix")
def mix_cmd(episode: Ep) -> None:
    """Sound design from frames.txt + sounds.yaml, then the mix (voice always on top)."""
    _use(episode)
    from . import mix
    mix.mix()


# ---------------------------------------------------------------- titles, render, release

@titles_app.command("propose")
def titles_propose(episode: Ep) -> None:
    _use(episode)
    from . import titles
    titles.propose()


@titles_app.command("sheet")
def titles_sheet(episode: Ep, frames: str | None = None) -> None:
    _use(episode)
    from . import titles
    for p in titles.sheet(None, frames):
        typer.echo(p)


@titles_app.command("set")
def titles_set(episode: Ep, n: int, pos: str, dx: int = 0, dy: int = 0) -> None:
    _use(episode)
    from . import titles
    typer.echo(titles.set_manual(n, pos, dx, dy))


@pipe_app.command("render")
def render_cmd(episode: Ep, only: str | None = None, plan: bool = False, silent: bool = False,
               remux: bool = False, crf: int = 18) -> None:
    """Animated render (uses the mix/narration automatically). --only a-b for a preview, --plan to inspect."""
    _use(episode)
    from . import render
    render.run(only=only, crf=crf, plan_only=plan, silent=silent, remux=remux)


@pipe_app.command("check")
def check_cmd(episode: Ep, video: Path | None = None) -> None:
    """QA of the rendered file: frozen picture, unexpected black, audio gaps, A/V length."""
    _use(episode)
    from . import check
    problems = check.check(video)
    (ep().work / "render_check.json").write_text(json.dumps({"ok": not problems, "problems": problems,
                                                             "at": _now()}, indent=1), encoding="utf-8")
    if problems:
        raise typer.Exit(1)


@pipe_app.command("release")
def release_cmd(episode: Ep) -> None:
    """Release kit: video, word-timed captions, description with chapters + sources, titles, thumbnails."""
    _use(episode)
    from . import release
    release.build()


def default_episode() -> str | None:
    return os.environ.get("STUDIO_EPISODE")
