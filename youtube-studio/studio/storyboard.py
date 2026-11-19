"""Scene-by-scene storyboard derived from the script."""

from __future__ import annotations

from studio.channels import ChannelProfile
from studio.diagrams import diagram_claims, has_diagram
from studio.episodes import Workspace
from studio.fsutil import atomic_write_json, atomic_write_text, read_model
from studio.models import Scene, Script, Storyboard, VisualSpec


def split_sentences(text: str) -> list[str]:
    import re

    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])", " ".join(text.split()))
    return [p.strip() for p in parts if p.strip()]


def estimate_duration(text: str, channel: ChannelProfile) -> float:
    words = len(text.split())
    sentences = max(1, len(split_sentences(text)))
    n = channel.narration
    return words / n.words_per_minute * 60.0 + sentences * n.sentence_pause_s + n.scene_pause_s


def build_storyboard(script: Script, channel: ChannelProfile) -> tuple[Storyboard, list[str]]:
    warnings: list[str] = []
    scenes: list[Scene] = []
    for section in script.sections:
        count = len(section.paragraphs)
        for i, para in enumerate(section.paragraphs):
            visual = para.visual
            if visual.kind == "diagram" and not has_diagram(visual.ref):
                warnings.append(f"unknown diagram '{visual.ref}' in {section.id}; using a card")
                visual = VisualSpec(kind="card", ref=section.heading, note="fallback")
            if visual.kind == "diagram" and has_diagram(visual.ref):
                missing = [c for c in diagram_claims(visual.ref) if c not in para.claim_ids]
                if missing:
                    warnings.append(f"{section.id}: diagram '{visual.ref}' shows facts from "
                                    f"{missing} but the narration does not cite them")
            if visual.kind == "footage":
                warnings.append(f"{section.id}: footage '{visual.ref}' must be imported with a "
                                "licence via `studio assets add`")
            idx = len(scenes)
            scenes.append(Scene(
                id=f"sc{idx + 1:03d}", index=idx, section_id=section.id,
                section_heading=section.heading, narration=para.text,
                claim_ids=para.claim_ids, visual=visual,
                est_duration_s=round(estimate_duration(para.text, channel), 2),
                starts_section=i == 0, ends_section=i == count - 1,
            ))
    return Storyboard(episode_id=script.episode_id, scenes=scenes), warnings


def load_storyboard(ws: Workspace) -> Storyboard:
    if not ws.storyboard_file.exists():
        raise FileNotFoundError("No storyboard yet. Run `studio storyboard <episode>` first.")
    return read_model(ws.storyboard_file, Storyboard)


def save_storyboard(ws: Workspace, board: Storyboard) -> None:
    atomic_write_json(ws.storyboard_file, board)
    lines = [f"# Storyboard - {board.episode_id}", "",
             f"Estimated runtime: {board.est_duration_s / 60:.1f} min, {len(board.scenes)} scenes",
             "", "| scene | section | visual | claims | est s | narration |",
             "|---|---|---|---|---|---|"]
    for s in board.scenes:
        lines.append(f"| {s.id} | {s.section_heading} | {s.visual.kind}:{s.visual.ref[:40]} | "
                     f"{', '.join(s.claim_ids)} | {s.est_duration_s:.1f} | "
                     f"{s.narration[:80]}... |")
    atomic_write_text(ws.storyboard / "storyboard.md", "\n".join(lines) + "\n")
