"""Claude (Anthropic API) drafting provider - PREPARED, NOT CONNECTED BY DEFAULT.

What it may do: draft a script / Shorts from the episode's EXISTING research claims, and
propose episode ideas. What it must not do: invent sources, facts, numbers or quotes - the
prompt forbids it, the output schema only lets it cite claim ids we gave it, and every
draft is re-checked with the normal editorial rules before a human adopts it.

Drafts are written to `authoring/*.draft.yaml`; nothing enters the pipeline until the
operator renames the file. Every call needs: STUDIO_ENABLE_PAID_PROVIDERS=1, Anthropic
credentials, `--i-consent-to-spend`, and a passed BudgetGuard preflight; the actual cost
from `response.usage` is written to the ledger.

API usage follows the Anthropic Python SDK docs (Messages API, structured outputs via
`output_config.format`, adaptive thinking is always on for Claude Opus 5.5, effort set
explicitly, server-side refusal fallbacks via `fallbacks: "default"`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Prices in USD per 1M tokens (Anthropic first-party API, cached 2026-11-03).
PRICES = {
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.10},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01},
}
DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000


class LLMError(RuntimeError):
    pass


class LLMNotArmed(RuntimeError):
    """A paid request was attempted without a passed budget preflight."""


def _strict(schema: dict) -> dict:
    """JSON schema for structured outputs: every object closed, every property required."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        schema["required"] = list(schema.get("properties", {}))
        for v in schema["properties"].values():
            _strict(v)
    if schema.get("type") == "array":
        _strict(schema["items"])
    return schema


def _str(desc: str = "") -> dict:
    return {"type": "string", "description": desc} if desc else {"type": "string"}


SCRIPT_SCHEMA = _strict({"type": "object", "properties": {
    "title": _str("working title, plain and accurate, no clickbait"),
    "sections": {"type": "array", "items": {"type": "object", "properties": {
        "id": _str("short slug"),
        "heading": _str(),
        "paragraphs": {"type": "array", "items": {"type": "object", "properties": {
            "text": _str("narration paragraph, original wording"),
            "claims": {"type": "array", "items": _str("a claim id from the list given")},
            "visual": {"type": "object", "properties": {
                "kind": {"type": "string", "enum": ["diagram", "card", "title"]},
                "ref": _str("diagram id from the list given, or card text"),
                "steps": _str("build steps such as '0-2', or empty"),
            }},
        }}},
    }}},
}})

SHORTS_SCHEMA = _strict({"type": "object", "properties": {"shorts": {"type": "array", "items": {
    "type": "object", "properties": {
        "id": _str("short-1, short-2, ..."),
        "title": _str(),
        "hook": _str("distinct opening line"),
        "layout": {"type": "string", "enum": ["diagram_center", "diagram_top", "hook_card"]},
        "diagram": _str("diagram id from the list given"),
        "claims": {"type": "array", "items": _str()},
        "narration": _str("20-60 s, written independently of the long script"),
    }}}}})

IDEAS_SCHEMA = _strict({"type": "object", "properties": {"ideas": {"type": "array", "items": {
    "type": "object", "properties": {
        "topic": _str(),
        "angle": _str("what makes this episode original for this channel"),
        "research_questions": {"type": "array", "items": _str()},
    }}}}})

RULES = """Rules you must follow:
- Use only the facts in the CLAIMS list. Cite the claim id on every paragraph that uses one.
- Never invent sources, statistics, dates, quotes, names of experts or product capabilities.
- A number may appear only if it appears in a cited claim's text.
- No quotations attributed to people.
- Write original narration in the channel's voice; do not copy claim wording verbatim.
- Visuals: use only the diagram ids provided; otherwise use a short text card.
- If the claims are not enough to cover a section, write a sentence that says what is
  still unknown instead of filling the gap."""


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def usd(self) -> float:
        p = PRICES.get(self.model, PRICES[DEFAULT_MODEL])
        return round((self.input_tokens + 1.25 * self.cache_creation_input_tokens) / 1e6
                     * p["input"] + self.cache_read_input_tokens / 1e6 * p["cache_read"]
                     + self.output_tokens / 1e6 * p["output"], 6)


@dataclass
class DraftResult:
    data: dict
    usage: Usage
    request_id: str = ""
    served_by: str = ""


@dataclass
class AnthropicDraftProvider:
    model: str = DEFAULT_MODEL
    effort: str = "high"
    client: Any = None  # injected in tests; real anthropic.Anthropic() created lazily
    name: str = "anthropic"
    paid: bool = True
    _armed_usd: float = 0.0
    spent_usd: float = field(default=0.0)

    # ------------------------------------------------------------------ estimates
    def estimate_usd(self, prompt_chars: int, max_tokens: int = MAX_TOKENS) -> float:
        """Worst case: ~4 chars per input token, the full max_tokens of output (thinking
        tokens are billed as output)."""
        p = PRICES.get(self.model, PRICES[DEFAULT_MODEL])
        return round(prompt_chars / 4 / 1e6 * p["input"] + max_tokens / 1e6 * p["output"], 4)

    def arm(self, max_usd: float) -> None:
        self._armed_usd = max(0.0, float(max_usd))

    def _client(self):
        if self.client is None:
            try:
                import anthropic  # optional extra: `uv sync --extra llm`
            except ImportError as exc:
                raise LLMError("Install the SDK first: `uv sync --extra llm`") from exc
            self.client = anthropic.Anthropic()
        return self.client

    # ------------------------------------------------------------------ core call
    def _call(self, system: str, user: str, schema: dict) -> DraftResult:
        estimate = self.estimate_usd(len(system) + len(user))
        if self.spent_usd + estimate > self._armed_usd + 1e-9:
            raise LLMNotArmed(f"Claude request blocked: estimate ${estimate:.2f} exceeds the "
                              f"preflighted amount ${self._armed_usd:.2f}")
        client = self._client()
        resp = client.beta.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort,
                           "format": {"type": "json_schema", "schema": schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        usage = Usage(
            model=getattr(resp, "model", self.model) or self.model,
            input_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
            cache_read_input_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(resp.usage, "cache_creation_input_tokens",
                                                0) or 0)
        self.spent_usd += usage.usd()
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            cat = getattr(details, "category", None) if details else None
            raise LLMError(f"Claude declined the request (category: {cat}); nothing written")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Draft was cut off at max_tokens; nothing written")
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Unparseable draft: {exc}") from exc
        return DraftResult(data, usage, getattr(resp, "_request_id", "") or "",
                           usage.model)

    # ------------------------------------------------------------------ prompts
    @staticmethod
    def _channel_brief(channel) -> str:
        return "\n".join([
            f"Channel: {channel.name}. Audience: {channel.audience.strip()}",
            f"Positioning: {channel.positioning.strip()}",
            "Tone: " + "; ".join(channel.tone),
            "Structure: " + " | ".join(channel.storytelling_structure),
            "Do: " + "; ".join(channel.do),
            "Don't: " + "; ".join(channel.dont),
        ])

    @staticmethod
    def _claims_block(pack) -> str:
        return "\n".join(f"{c.id} [{c.status.value}]: {c.text}" for c in pack.claims)

    def build_script_prompt(self, channel, pack, title: str, target_minutes: float,
                            diagrams: list[str]) -> tuple[str, str]:
        words = int(target_minutes * channel.narration.words_per_minute)
        system = (f"You write narration for an educational YouTube channel.\n"
                  f"{self._channel_brief(channel)}\n\n{RULES}")
        user = (f"Episode: {title}\nTopic: {pack.topic}\nTarget length: about {words} words "
                f"({target_minutes:g} minutes).\n\nCLAIMS (id [status]: text):\n"
                f"{self._claims_block(pack)}\n\nDIAGRAM IDS: {', '.join(diagrams)}\n\n"
                "Write the full script following the channel structure.")
        return system, user

    def draft_script(self, channel, pack, title: str, target_minutes: float,
                     diagrams: list[str]) -> DraftResult:
        system, user = self.build_script_prompt(channel, pack, title, target_minutes,
                                                diagrams)
        res = self._call(system, user, SCRIPT_SCHEMA)
        known = {c.id for c in pack.claims}
        for sec in res.data.get("sections", []):
            for para in sec.get("paragraphs", []):
                bad = [c for c in para.get("claims", []) if c not in known]
                if bad:
                    raise LLMError(f"Draft cites unknown claims {bad}; rejected")
        return res

    def draft_shorts(self, channel, pack, title: str, script_text: str,
                     diagrams: list[str], count: int = 3) -> DraftResult:
        system = (f"You write YouTube Shorts (20-60 s) for an educational channel.\n"
                  f"{self._channel_brief(channel)}\n\n{RULES}\n- Each Short needs a distinct "
                  "hook, its own wording (do not reuse sentences from the long script) and a "
                  "different diagram or layout.")
        user = (f"Long episode: {title}\nCLAIMS:\n{self._claims_block(pack)}\n\n"
                f"DIAGRAM IDS: {', '.join(diagrams)}\n\nLONG SCRIPT (do not copy):\n"
                f"{script_text}\n\nWrite {count} Shorts.")
        return self._call(system, user, SHORTS_SCHEMA)

    def propose_ideas(self, channel, count: int, existing: list[str]) -> DraftResult:
        system = (f"You plan episodes for an educational YouTube channel.\n"
                  f"{self._channel_brief(channel)}\nPropose topics only; do not state facts "
                  "or numbers. Avoid topics that repeat existing episodes.")
        user = (f"Existing episodes: {', '.join(existing) or 'none'}\n"
                f"Propose {count} original episode ideas with research questions.")
        return self._call(system, user, IDEAS_SCHEMA)
