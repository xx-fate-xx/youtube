"""Hand-written episodes: research / script / Shorts authored as YAML in the episode folder.

`projects/<channel>/<episode>/authoring/{research,script,shorts}.yaml` use exactly the same
format as `samples/<slug>/`. When a file exists there, `studio research|script|shorts` read
it instead of the mock sample, so a new topic needs no code and no paid model.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from studio.channels import ChannelProfile
from studio.diagrams import DIAGRAMS, spec_ids
from studio.episodes import Workspace
from studio.fsutil import atomic_write_text, sha256_file
from studio.providers.llm import MockLLMProvider

AUTHOR_DIR = "authoring"
FILES = ("research.yaml", "script.yaml", "shorts.yaml")


def author_dir(ws: Workspace) -> Path:
    return ws.root / AUTHOR_DIR


def source_for(ws: Workspace, samples_dir: Path, sample: str | None,
               filename: str) -> tuple[MockLLMProvider, str | None, str]:
    """(provider, sample-name, input-hash) for research/script/shorts generation."""
    f = author_dir(ws) / filename
    if f.exists():
        return MockLLMProvider(ws.root), AUTHOR_DIR, f"authoring:{sha256_file(f)}"
    return MockLLMProvider(samples_dir), sample, f"sample:{sample}"


def _dump(data: dict, header: str) -> str:
    return header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=92)


def init_files(ws: Workspace, channel: ChannelProfile, title: str, topic: str,
               *, overwrite: bool = False) -> list[Path]:
    """Write skeleton YAML files (never overwrites unless asked)."""
    d = author_dir(ws)
    d.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    research = {
        "title": title,
        "topic_aliases": [topic],
        "sources": [{"id": "S1", "url": "https://example.org/REPLACE-with-a-real-page",
                     "title": "REPLACE: title of a page you actually opened",
                     "publisher": "REPLACE"}],
        "claims": [{"id": "C1", "text": "REPLACE: one checkable statement, as the source "
                    "says it", "sources": ["S1"], "numeric": False}],
        "open_questions": ["Which primary source backs each number?"],
    }
    sections = []
    for i, step in enumerate(channel.storytelling_structure, start=1):
        heading = step.split(":")[0].strip()
        sections.append({"id": f"s{i}", "heading": heading, "paragraphs": [{
            "text": f"[PLACEHOLDER NARRATION - {step}] Write original narration. Every "
                    "factual sentence lists its claim ids; numbers need a claim.",
            "claims": [],
            "visual": {"kind": "card", "ref": heading},
        }]})
    script = {"title": title, "editorial_notes": ["Hand-written; replace every placeholder."],
              "sections": sections}
    shorts = {"shorts": [{
        "id": f"short-{k}", "title": f"REPLACE short {k} title",
        "hook": "REPLACE: a distinct opening line", "layout": layout,
        "diagram": "REPLACE-with-a-diagram-id", "steps": "", "focus": "",
        "claims": [], "link_text": f"Full episode: {title}",
        "narration": "[PLACEHOLDER] 20-60 s of independently written narration (not copied "
                     "from the long script).",
    } for k, layout in ((1, "diagram_center"), (2, "diagram_top"), (3, "hook_card"))]}
    header = ("# Hand-written {kind} for {ep}. Same format as samples/undersea_cables/.\n"
              "# Rules: no invented sources or quotes; every number needs a claim id.\n")
    for name, data in (("research.yaml", research), ("script.yaml", script),
                       ("shorts.yaml", shorts)):
        path = d / name
        if path.exists() and not overwrite:
            continue
        atomic_write_text(path, _dump(data, header.format(kind=name[:-5], ep=ws.root.name)))
        written.append(path)
    guide = d / "README.md"
    if not guide.exists() or overwrite:
        diagrams = sorted(DIAGRAMS) + spec_ids()
        atomic_write_text(guide, "\n".join([
            f"# Authoring {ws.root.name}", "",
            "1. `research.yaml`: real sources you opened + one claim per checkable statement.",
            "2. `script.yaml`: narration paragraphs with `claims` and a `visual` each.",
            "3. `shorts.yaml`: up to three independent Shorts.",
            "4. `uv run studio author check <ep>` until it is clean, then",
            "   `studio research <ep>`, `studio script <ep>`, `studio storyboard <ep>` ...", "",
            "Visual kinds: `diagram` (ref = id below), `card` (ref = text, `|` = list), "
            "`title`, `footage` (import first with `studio assets add`).",
            "New diagrams: add `diagram_specs/<id>.yaml` (docs/DIAGRAM-LIBRARY.md).", "",
            "Available diagrams: " + ", ".join(diagrams), ""]))
        written.append(guide)
    return written


def check(ws: Workspace, channel: ChannelProfile, target_minutes: float) -> list[str]:
    """Dry validation of the authoring files: structure, citations, script and Shorts rules."""
    from studio.editorial import script_issues
    from studio.research import validate_pack
    from studio.shorts import shorts_issues
    from studio.storyboard import build_storyboard

    problems: list[str] = []
    d = author_dir(ws)
    if not d.exists():
        return [f"no {AUTHOR_DIR}/ folder; run `studio author init`"]
    prov = MockLLMProvider(ws.root)
    pack = None
    try:
        pack = prov.research("check", "check", AUTHOR_DIR)
        problems += [f"research: {p}" for p in validate_pack(pack)]
        placeholders = [s.id for s in pack.sources if "REPLACE" in s.url + s.title]
        placeholders += [c.id for c in pack.claims if "REPLACE" in c.text]
        if placeholders:
            problems.append(f"research: placeholders left in {placeholders}")
    except FileNotFoundError:
        problems.append("research.yaml missing")
    except Exception as exc:  # malformed YAML / schema
        problems.append(f"research.yaml: {exc}")
    script = None
    if pack is not None:
        try:
            script = prov.script("check", "check", channel, pack, target_minutes, AUTHOR_DIR)
            problems += [f"script [{i.severity}]: {i.message}"
                         for i in script_issues(script, pack, channel, target_minutes)]
            _, warnings = build_storyboard(script, channel)
            problems += [f"storyboard: {w}" for w in warnings]
        except FileNotFoundError:
            problems.append("script.yaml missing")
        except Exception as exc:
            problems.append(f"script.yaml: {exc}")
    if pack is not None and script is not None and (d / "shorts.yaml").exists():
        try:
            specs = prov.shorts("check", "check", pack, 3, AUTHOR_DIR)
            problems += [f"shorts: {i}" for i in shorts_issues(specs, script, pack, channel)]
        except Exception as exc:
            problems.append(f"shorts.yaml: {exc}")
    return problems
