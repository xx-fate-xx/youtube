"""Review package, checklists and operator decisions (approve / reject / needs_changes)."""

from __future__ import annotations

import json
import os
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session, select

from studio.assets import load_manifest, manifest_issues
from studio.budget import cost_report
from studio.channels import ChannelProfile
from studio.config import Settings
from studio.editorial import load_script, script_issues
from studio.episodes import Workspace
from studio.fsutil import atomic_write_json, atomic_write_text, read_model, sha256_file
from studio.models import (
    CostEntry,
    Episode,
    EpisodeState,
    NarrationTrack,
    ReviewDecision,
    ReviewDecisionKind,
)
from studio.research import claim_blockers, load_pack
from studio.shorts import load_shorts, shorts_issues
from studio.state import transition
from studio.storyboard import load_storyboard
from studio.verification import load_proposals


class ReviewBlocked(RuntimeError):
    pass


@dataclass
class Checklist:
    name: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.blockers


@dataclass
class ReviewReport:
    episode_id: str
    video: Path | None
    checklists: list[Checklist]

    @property
    def blockers(self) -> list[str]:
        return [f"{c.name}: {b}" for c in self.checklists for b in c.blockers]

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "video": str(self.video) if self.video else None,
            "approvable": not self.blockers,
            "checklists": [
                {"name": c.name, "passed": c.passed, "blockers": c.blockers,
                 "warnings": c.warnings, "info": c.info}
                for c in self.checklists
            ],
        }


def final_video(ws: Workspace, episode_id: str) -> Path | None:
    master = ws.render / f"{episode_id}_master.mp4"
    return master if master.exists() else None


def build_report(settings: Settings, session: Session, episode: Episode, ws: Workspace,
                 channel: ChannelProfile) -> ReviewReport:
    pack = load_pack(ws)
    script = load_script(ws)
    board = load_storyboard(ws)
    manifest = load_manifest(ws, episode.id)
    shorts = load_shorts(ws)

    factual = Checklist("factual")
    used = {c for s in script.sections for p in s.paragraphs for c in p.claim_ids}
    used |= {c for s in shorts for c in s.claim_ids}
    factual.blockers += claim_blockers(pack, used)
    for issue in script_issues(script, pack, channel, episode.target_minutes):
        (factual.blockers if issue.severity == "blocker" else factual.warnings).append(
            issue.message)
    factual.warnings += [f"open question: {q}" for q in pack.open_questions]
    factual.info.append(f"{len(used)} claims cited, {len(pack.sources)} sources")
    pset = load_proposals(ws)
    if pset:
        verdicts = Counter(p.verdict for p in pset.proposals)
        factual.info.append("source-check proposals: " + ", ".join(
            f"{k}={v}" for k, v in sorted(verdicts.items())) + " (see VERIFICATION_REPORT.md)")
        weak = [p.claim_id for p in pset.proposals if "wikipedia.org" in p.source_url]
        if weak:
            factual.warnings.append("claims resting on Wikipedia only (prefer a primary "
                                    f"source): {', '.join(weak)}")

    visual = Checklist("visual")
    video = final_video(ws, episode.id)
    preview = ws.render / f"{episode.id}_preview.mp4"
    if not video:
        visual.blockers.append("no master render (run `studio render <ep>` without --preview); "
                               "previews carry review badges and cannot be published")
    lo, hi = channel.runtime_minutes
    if ws.narration_file.exists():
        track = read_model(ws.narration_file, NarrationTrack)
        minutes = track.duration_s / 60
        if not lo <= minutes <= hi:
            visual.blockers.append(f"runtime {minutes:.1f} min outside {lo:g}-{hi:g} min")
        visual.info.append(f"runtime {minutes:.1f} min, {len(board.scenes)} scenes")
    else:
        track = None
        visual.blockers.append("no narration track")
    if not (ws.render / "thumbnail_draft.png").exists():
        visual.warnings.append("no thumbnail draft")
    visual.info.append("diagrams are schematic and labelled 'not to scale'")
    if preview.exists():
        visual.info.append(f"preview: {preview}")

    copyright_ = Checklist("copyright_and_licences")
    copyright_.blockers += manifest_issues(ws, manifest, board)
    copyright_.info.append(f"{len(manifest.assets)} assets in manifest")

    narration = Checklist("narration")
    if track:
        if track.is_placeholder:
            narration.blockers.append(f"narration is a placeholder ({track.provider})")
        narration.info.append(f"provider={track.provider} voice={track.voice} "
                              f"timing={track.timing_method}")
        if track.timing_method not in {"exact", "provider_alignment"}:
            narration.warnings.append(
                f"caption timings are {track.timing_method} (not word-exact); spot-check sync "
                "or narrate with a provider that returns alignment (ElevenLabs)")

    shorts_cl = Checklist("shorts")
    if not shorts:
        shorts_cl.warnings.append("no Shorts prepared")
    shorts_cl.blockers += shorts_issues(shorts, script, pack, channel) if shorts else []
    for s in shorts:
        if not list((ws.shorts / s.id).glob("*.mp4")):
            shorts_cl.warnings.append(f"{s.id} not rendered")
        meta_file = ws.shorts / s.id / "metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            shorts_cl.blockers += [f"phone legibility: {i}"
                                   for i in meta.get("legibility_issues", [])]
            hidden = meta.get("labels_hidden_for_vertical_frame", [])
            if hidden:
                shorts_cl.warnings.append(f"{s.id}: labels hidden in vertical frame: {hidden}")
            lic = meta.get("narration_license", {})
            if lic and lic.get("clearance") != "cleared":
                copyright_.blockers.append(
                    f"{s.id}: narration licence is {lic.get('clearance')} ({lic.get('license')})")
            elif not lic:
                copyright_.blockers.append(f"{s.id}: narration licence not recorded; re-render")

    disclosure = Checklist("ai_disclosure")
    ai_assets = [a for a in manifest.assets if a.ai_generated]
    realistic = [a for a in ai_assets if a.realistic]
    if realistic:
        disclosure.warnings.append(
            "realistic AI-generated/altered media present: " + ", ".join(a.id for a in realistic)
            + " - YouTube's altered/synthetic content disclosure is likely required")
    if ai_assets:
        disclosure.info.append("synthetic/AI assets: " + ", ".join(a.id for a in ai_assets))
    disclosure.info.append(
        "Operator must answer the disclosure question at approval (--ai-disclosure yes|no), "
        "applying YouTube's current rules. A synthetic narrator alone does not automatically "
        "require the label; realistic altered people/places/events do.")

    cost = Checklist("cost")
    rows = session.exec(select(CostEntry).where(CostEntry.episode_id == episode.id)).all()
    spent = sum(r.usd for r in rows if r.kind == "actual")
    cost.info.append(f"episode actual spend ${spent:.2f} over {len(rows)} ledger entries")
    rep = cost_report(session, settings)
    cost.info.append(f"month spend ${rep['month_spent_usd']:.2f} of "
                     f"${rep['monthly_cap_usd']:.2f}")

    return ReviewReport(episode.id, video,
                        [factual, visual, copyright_, narration, shorts_cl, disclosure, cost])


TOOLCHAIN = [
    ("FFmpeg (imageio-ffmpeg build) / libx264", "encoder only",
     "GPL/LGPL software licence covers the tool, not the videos it encodes", "cleared"),
    ("Python, Pillow, studio code", "rendering code",
     "Open-source licences cover the software; output is original work", "cleared"),
]


def license_audit_markdown(ws: Workspace, manifest, shorts: list) -> str:
    lines = ["# Licence audit", "",
             "Every ingredient of the long video, the Shorts and the thumbnail. Anything not "
             "`cleared` blocks approval (no material with unclear commercial rights).", "",
             "| asset | kind | origin | licence | clearance | commercial use | proof |",
             "|---|---|---|---|---|---|---|"]
    for a in manifest.assets:
        ok = "yes" if a.clearance.value == "cleared" else "**NO - blocks approval**"
        lines.append(f"| {a.id} | {a.kind} | {a.origin} | {a.license} | {a.clearance.value} | "
                     f"{ok} | {a.license_proof[:160]} |")
    for s in shorts:
        meta_file = ws.shorts / s.id / "metadata.json"
        meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        lic = meta.get("narration_license", {})
        clear = lic.get("clearance", "unknown")
        ok = "yes" if clear == "cleared" else "**NO - blocks approval**"
        lines.append(f"| {s.id} narration | narration | {meta.get('narration_provider', '?')} "
                     f"| {lic.get('license', 'not recorded')} | {clear} | {ok} | "
                     f"{lic.get('proof', '')[:160]} |")
        lines.append(f"| {s.id} music bed | music | generated_local | original sine synthesis "
                     "| cleared | yes | studio/ffmpeg.py:make_music_bed |")
    lines += ["", "## Toolchain (does not license the output)", "",
              "| tool | role | note | status |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in TOOLCHAIN]
    lines += ["", "## Not used", "",
              "- No stock footage, photos, third-party music, sound effects, logos, maps or "
              "screenshots are used. Place names appear only as text labels.",
              "- No voice cloning; no real person's likeness."]
    return "\n".join(lines) + "\n"


def _link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def write_release_candidate(ws: Workspace, report: ReviewReport, episode_title: str) -> Path:
    """review/package/: everything a human reviewer needs in one folder."""
    pkg = ws.review / "package"
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)
    master = ws.render / f"{report.episode_id}_master.mp4"
    preview = ws.render / f"{report.episode_id}_preview.mp4"
    files: list[tuple[str, Path]] = []
    if master.exists():
        files.append(("long/" + master.name, master))
    if preview.exists():
        files.append(("long/" + preview.name, preview))
    for srt in ws.render.glob("*.srt"):
        files.append(("long/" + srt.name, srt))
    thumb = ws.render / "thumbnail_draft.png"
    if thumb.exists():
        files.append(("thumbnail_draft.png", thumb))
    for d in sorted(p for p in ws.shorts.glob("*") if p.is_dir() and p.name != "frames"):
        for f in sorted(d.glob("*_master.mp4")) or sorted(d.glob("*_preview.mp4")):
            files.append((f"shorts/{f.name}", f))
        for f in [*d.glob("*.srt"), d / "metadata.json"]:
            if f.exists():
                files.append((f"shorts/{d.name}_{f.name}" if f.name == "metadata.json"
                              else f"shorts/{f.name}", f))
    for f in (ws.script / "script.md", ws.research / "VERIFICATION_REPORT.md",
              ws.research / "sources.md", ws.storyboard / "storyboard.md", ws.manifest_file,
              ws.review / "LICENSE_AUDIT.md", ws.review / "AI_DISCLOSURE_AUDIT.md",
              ws.research / "FACT_CONFIRMATION.md", ws.review / "REVIEW.md"):
        if f.exists():
            files.append((f.name, f))
    for rel, src in files:
        _link_or_copy(src, pkg / rel)
    blockers = ["# Blocking issues", "", f"{episode_title} (`{report.episode_id}`)", "",
                f"**{len(report.blockers)} blocker(s)** - approval and upload are refused "
                "until all are resolved.", ""]
    for c in report.checklists:
        if c.blockers:
            blockers += [f"## {c.name}", ""] + [f"- [ ] {b}" for b in c.blockers] + [""]
    warn = [(c.name, w) for c in report.checklists for w in c.warnings]
    if warn:
        blockers += ["## Warnings (not blocking)", ""] + [f"- {n}: {w}" for n, w in warn]
    atomic_write_text(pkg / "BLOCKERS.md", "\n".join(blockers) + "\n")
    index = ["# Review package", "", "| file | size |", "|---|---|"]
    for f in sorted(pkg.rglob("*")):
        if f.is_file():
            index.append(f"| {f.relative_to(pkg)} | {f.stat().st_size / 1e6:.1f} MB |")
    atomic_write_text(pkg / "INDEX.md", "\n".join(index) + "\n")
    return pkg


def write_package(ws: Workspace, report: ReviewReport) -> Path:
    pkg = ws.review
    pkg.mkdir(parents=True, exist_ok=True)
    atomic_write_json(pkg / "checklist.json", report.to_dict())
    for src in (ws.script / "script.md", ws.research / "sources.md",
                ws.storyboard / "storyboard.md", ws.manifest_file):
        if src.exists():
            shutil.copy2(src, pkg / src.name)
    lines = [f"# Review package - {report.episode_id}", ""]
    lines.append("**APPROVABLE**" if not report.blockers else
                 f"**NOT APPROVABLE - {len(report.blockers)} blocker(s)**")
    lines.append("")
    if report.video:
        lines.append(f"Master video: `{report.video}`")
    for c in report.checklists:
        mark = "PASS" if c.passed else "BLOCKED"
        lines += ["", f"## {c.name} - {mark}", ""]
        lines += [f"- [ ] BLOCKER: {b}" for b in c.blockers]
        lines += [f"- WARNING: {w}" for w in c.warnings]
        lines += [f"- {i}" for i in c.info]
    lines += ["", "## Operator actions", "",
              f"- approve: `studio decide {report.episode_id} approve --reviewer NAME "
              "--ai-disclosure no|yes`",
              f"- needs changes: `studio decide {report.episode_id} needs_changes --back-to "
              "script --reviewer NAME --note '...'`",
              f"- reject: `studio decide {report.episode_id} reject --reviewer NAME --note '...'`"]
    path = pkg / "REVIEW.md"
    atomic_write_text(path, "\n".join(lines) + "\n")
    return path


def decide(settings: Settings, session: Session, episode: Episode, ws: Workspace,
           channel: ChannelProfile, kind: ReviewDecisionKind, *, reviewer: str, note: str = "",
           ai_disclosure: bool | None = None, back_to: EpisodeState | None = None
           ) -> ReviewDecision:
    if EpisodeState(episode.state) != EpisodeState.REVIEW_PENDING:
        raise ReviewBlocked(f"Episode is '{episode.state}'; decisions need 'review_pending' "
                            "(run `studio review <ep>`).")
    if not reviewer.strip():
        raise ReviewBlocked("reviewer name is required")
    report = build_report(settings, session, episode, ws, channel)
    write_package(ws, report)
    decision = ReviewDecision(episode_id=episode.id, decision=kind, reviewer=reviewer,
                              note=note, ai_disclosure_altered_content=ai_disclosure,
                              blockers_at_decision=report.blockers)
    if kind == ReviewDecisionKind.APPROVE:
        if report.blockers:
            raise ReviewBlocked("Cannot approve; blockers:\n- " + "\n- ".join(report.blockers))
        if ai_disclosure is None:
            raise ReviewBlocked("Answer the AI disclosure question: --ai-disclosure yes|no")
        assert report.video is not None
        decision.video_path = str(report.video)
        decision.video_sha256 = sha256_file(report.video)
        transition(session, episode, EpisodeState.APPROVED, actor=reviewer,
                   note=note or "approved")
    else:
        target = back_to or (EpisodeState.RESEARCH if kind == ReviewDecisionKind.REJECT
                             else EpisodeState.SCRIPT)
        transition(session, episode, target, actor=reviewer, note=f"{kind.value}: {note}")
    atomic_write_json(ws.decision_file, decision)
    history = ws.review / "decisions"
    history.mkdir(exist_ok=True)
    atomic_write_json(history / f"{decision.at:%Y%m%dT%H%M%S}-{kind.value}.json", decision)
    return decision


# --------------------------------------------------------------------------- AI disclosure
YT_DISCLOSURE_URL = "https://support.google.com/youtube/answer/14328491"
YT_REQUIRED = [  # verbatim, checked against the live page on 2026-11-18
    "Makes a real person appear to say or do something they didn’t do.",
    "Alters footage of a real event or place.",
    "Generates a realistic scene that didn’t actually occur.",
    "Creates music that’s the main focus of the video.",
]
YT_EXEMPT = [
    "Production assistance, like using generative AI tools to create or improve a video "
    "outline, script, thumbnail, title, or infographic",
    "Caption creation",
    "Cloning one’s own voice to create voice overs or dubs",
]


def ai_disclosure_audit(ws: Workspace, manifest, shorts: list, planned_voice: str) -> str:
    """Map the episode's real ingredients onto YouTube's disclosure criteria."""
    rows = []
    realistic = [a for a in manifest.assets if a.realistic]
    visuals = [a for a in manifest.assets if a.kind in {"diagram", "card", "footage", "image"}]
    gen_visual = all(a.origin == "generated_local" for a in visuals)
    rows.append(("Visuals", f"{len(visuals)} code-generated schematic diagrams/cards "
                 "(labelled 'schematic - not to scale'), no photos, no footage, no real people"
                 if gen_visual else "includes imported footage/images - review each",
                 "no" if gen_visual and not realistic else "CHECK"))
    narr = manifest.get("narration")
    rows.append(("Narration (long)", f"current: {narr.license if narr else 'none'}; planned: "
                 f"{planned_voice} - a stock synthetic voice, not a clone of a real person",
                 "no (not a real person's likeness)"))
    for s in shorts:
        meta_file = ws.shorts / s.id / "metadata.json"
        meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        rows.append((f"Narration ({s.id})", meta.get("narration_provider", "?") +
                     f" now; planned: {planned_voice}", "no (same reasoning)"))
    rows += [
        ("Script", "drafted with AI assistance, fact-checked and approved by a human",
         "no - listed as exempt production assistance"),
        ("Captions", "generated from narration timings", "no - 'Caption creation' is exempt"),
        ("Music", "synthesised sine-wave ambient bed (not generative AI, not the focus)",
         "no"),
        ("Thumbnail", "code-generated title + schematic cable cross-section", "no"),
    ]
    needs = any(r[2] == "CHECK" for r in rows) or bool(realistic)
    lines = ["# AI disclosure audit", "",
             f"Rules: YouTube Help, 'Disclosing use of GenAI content' ({YT_DISCLOSURE_URL}), "
             "checked 2026-11-18.", "",
             "Disclosure is required when content seems realistic and:", ""]
    lines += [f"> {q}" for q in YT_REQUIRED]
    lines += ["", "Examples YouTube lists as NOT requiring disclosure include:", ""]
    lines += [f"> {q}" for q in YT_EXEMPT]
    lines += ["", "| ingredient | what it is | disclosure required? |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    lines += ["", "## Conclusion", ""]
    if needs:
        lines.append("**CHECK REQUIRED**: realistic or imported media present - decide per asset.")
    else:
        lines += [
            "**Not required** for this episode and its Shorts as composed: nothing realistic, "
            "no real person's likeness or voice, no altered real footage, music is not the "
            "focus. A stock AI voiceover is not named by YouTube either way; it does not match "
            "any required criterion (our inference).",
            "",
            "Recommended: answer 'No' to 'AI use' in Studio and add a voluntary line to the "
            "description: *\"Narration uses a synthetic AI voice. Script researched and "
            "fact-checked by a human editor. Diagrams are schematic, not to scale.\"*",
            "",
            "Re-run this audit if any of these are added: photorealistic AI images or video, "
            "a voice resembling a real person, AI-generated music as a focal element, or files "
            "carrying AI C2PA metadata. The larger monetisation risk is YPP's 'inauthentic "
            "content' policy (mass-produced/templated content): keep each episode and Short "
            "substantively distinct.",
        ]
    return "\n".join(lines) + "\n"
