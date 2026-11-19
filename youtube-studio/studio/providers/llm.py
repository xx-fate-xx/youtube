"""LLM provider interface.

`MockLLMProvider` never invents facts. It either loads an editor-curated sample fixture
(samples/<slug>/) or returns clearly-marked placeholders with zero claims, which are
visibly flagged and cannot pass review.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import yaml

from studio.channels import ChannelProfile
from studio.episodes import slugify
from studio.models import (
    Claim,
    ResearchPack,
    Script,
    ScriptParagraph,
    ScriptSection,
    ShortSpec,
    Source,
    VisualSpec,
)


class LLMProvider(Protocol):
    name: str
    paid: bool

    def estimate_usd(self, operation: str, chars: int) -> float: ...

    def propose_ideas(self, channel: ChannelProfile, count: int) -> list[str]: ...

    def research(self, episode_id: str, topic: str, sample: str | None) -> ResearchPack: ...

    def script(self, episode_id: str, title: str, channel: ChannelProfile,
               pack: ResearchPack, target_minutes: float, sample: str | None) -> Script: ...

    def shorts(self, episode_id: str, title: str, pack: ResearchPack, count: int,
               sample: str | None) -> list[ShortSpec]: ...


def find_sample(samples_dir: Path, topic: str) -> str | None:
    """Return the sample slug whose topic_aliases match `topic`, if any."""
    wanted = slugify(topic, 200)
    for research in sorted(samples_dir.glob("*/research.yaml")):
        data = yaml.safe_load(research.read_text(encoding="utf-8"))
        aliases = [data.get("title", "")] + list(data.get("topic_aliases", []))
        if any(slugify(a, 200) == wanted for a in aliases):
            return research.parent.name
    return None


class MockLLMProvider:
    name = "mock_llm"
    paid = False

    def __init__(self, samples_dir: Path):
        self.samples_dir = samples_dir

    def estimate_usd(self, operation: str, chars: int) -> float:
        return 0.0

    def _load(self, sample: str, name: str) -> dict:
        return yaml.safe_load((self.samples_dir / sample / name).read_text(encoding="utf-8"))

    def propose_ideas(self, channel: ChannelProfile, count: int) -> list[str]:
        # Offline: return the editor-curated backlog only. Never fabricate topics as facts.
        return channel.idea_backlog[:count]

    def research(self, episode_id: str, topic: str, sample: str | None) -> ResearchPack:
        if sample:
            data = self._load(sample, "research.yaml")
            return ResearchPack(
                episode_id=episode_id,
                topic=topic,
                generated_by=f"{self.name}:sample:{sample}",
                sources=[Source(**{k: v for k, v in s.items()}) for s in data["sources"]],
                claims=[
                    Claim(id=c["id"], text=c["text"], source_ids=c["sources"],
                          numeric=bool(c.get("numeric", False)))
                    for c in data["claims"]
                ],
                open_questions=list(data.get("open_questions", [])),
            )
        return ResearchPack(
            episode_id=episode_id,
            topic=topic,
            generated_by=f"{self.name}:placeholder",
            open_questions=[
                "MOCK PROVIDER: no research performed. Add sources and claims manually with "
                "`studio claim add` or connect a research-capable provider.",
            ],
        )

    def script(self, episode_id: str, title: str, channel: ChannelProfile,
               pack: ResearchPack, target_minutes: float, sample: str | None) -> Script:
        if sample:
            data = self._load(sample, "script.yaml")
            sections = [
                ScriptSection(
                    id=s["id"],
                    heading=s["heading"],
                    paragraphs=[
                        ScriptParagraph(text=p["text"].strip(), claim_ids=p.get("claims", []),
                                        visual=VisualSpec(**p.get("visual", {})))
                        for p in s["paragraphs"]
                    ],
                )
                for s in data["sections"]
            ]
            return Script(episode_id=episode_id, title=data.get("title", title),
                          generated_by=f"{self.name}:sample:{sample}", sections=sections,
                          editorial_notes=data.get("editorial_notes", []))
        # Placeholder: structure only, explicitly marked, no facts.
        sections = [
            ScriptSection(
                id=f"s{i}",
                heading=step.split(":")[0],
                paragraphs=[ScriptParagraph(
                    text=f"[PLACEHOLDER NARRATION - {step}. Write original narration here and "
                         f"attach claim ids for every factual statement.]",
                    visual=VisualSpec(kind="card", ref=step.split(":")[0]),
                )],
            )
            for i, step in enumerate(channel.storytelling_structure, start=1)
        ]
        return Script(episode_id=episode_id, title=title, generated_by=f"{self.name}:placeholder",
                      is_placeholder=True, sections=sections,
                      editorial_notes=["Placeholder script from mock provider - not publishable."])

    def shorts(self, episode_id: str, title: str, pack: ResearchPack, count: int,
               sample: str | None) -> list[ShortSpec]:
        if sample and (self.samples_dir / sample / "shorts.yaml").exists():
            data = self._load(sample, "shorts.yaml")
            return [
                ShortSpec(id=s["id"], title=s["title"], hook=s["hook"],
                          narration=" ".join(s["narration"].split()),
                          claim_ids=s.get("claims", []), diagram=s["diagram"],
                          diagram_step=s.get("diagram_step"), steps=str(s.get("steps", "")),
                          focus=s.get("focus", ""),
                          layout=s.get("layout", "diagram_center"),
                          link_text=s.get("link_text", f"Full episode: {title}"))
                for s in data["shorts"][:count]
            ]
        return []


class PaidLLMProviderNotConnected:
    """Placeholder for a future paid LLM provider (e.g. Anthropic API).

    A Claude Pro subscription is NOT an API entitlement; API usage is billed separately.
    Implementation is intentionally deferred until the operator asks to connect it.
    """

    name = "paid_llm"
    paid = True

    def __getattr__(self, item: str):
        raise NotImplementedError(
            "No paid LLM provider is connected. This is deliberate for the MVP; ask to connect "
            "one, then it will run behind the BudgetGuard preflight."
        )
