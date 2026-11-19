"""Claude drafting provider with a fake client: no network, no spending."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from studio.providers.anthropic_llm import (
    SCRIPT_SCHEMA,
    AnthropicDraftProvider,
    LLMError,
    LLMNotArmed,
    Usage,
)
from studio.providers.llm import MockLLMProvider


class FakeClient:
    def __init__(self, payload: dict | None = None, stop_reason="end_turn", category=None):
        self.calls = []
        self.payload = payload
        self.stop_reason = stop_reason
        self.category = category
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        text = json.dumps(self.payload or {})
        return SimpleNamespace(
            model=kwargs["model"], stop_reason=self.stop_reason,
            stop_details=SimpleNamespace(category=self.category) if self.category else None,
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=3000, output_tokens=5000,
                                  cache_read_input_tokens=0, cache_creation_input_tokens=0),
            _request_id="req_test")


def _setup(settings, episode):
    ep, ws, ch = episode
    llm = MockLLMProvider(settings.samples_dir)
    pack = llm.research(ep.id, ep.topic, "undersea_cables")
    return ep, ch, pack


GOOD = {"title": "T", "sections": [{"id": "hook", "heading": "Hook", "paragraphs": [
    {"text": "Light in glass.", "claims": ["C3"],
     "visual": {"kind": "diagram", "ref": "fiber_tir", "steps": ""}}]}]}


def test_request_shape_follows_current_api(settings, episode):
    ep, ch, pack = _setup(settings, episode)
    fake = FakeClient(GOOD)
    d = AnthropicDraftProvider(client=fake)
    d.arm(1.0)
    res = d.draft_script(ch, pack, ep.title, 9, ["fiber_tir"])
    kw = fake.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"]["effort"] == "high"
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": SCRIPT_SCHEMA}
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in kw and "temperature" not in kw  # 400s on Claude Opus 5.5
    assert "C3 [unverified]" in kw["messages"][0]["content"]
    assert res.data == GOOD and res.request_id == "req_test"
    assert res.usage.usd() == pytest.approx(3000 / 1e6 * 4 + 5000 / 1e6 * 20)


def test_schema_is_strict_everywhere():
    def walk(node):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for v in node["properties"].values():
                walk(v)
        if node.get("type") == "array":
            walk(node["items"])

    walk(SCRIPT_SCHEMA)


def test_not_armed_means_no_request(settings, episode):
    ep, ch, pack = _setup(settings, episode)
    fake = FakeClient(GOOD)
    with pytest.raises(LLMNotArmed):
        AnthropicDraftProvider(client=fake).draft_script(ch, pack, ep.title, 9, [])
    assert fake.calls == []


def test_refusal_and_truncation_write_nothing(settings, episode):
    ep, ch, pack = _setup(settings, episode)
    for fake in (FakeClient(GOOD, stop_reason="refusal", category="general_harms"),
                 FakeClient(GOOD, stop_reason="max_tokens")):
        d = AnthropicDraftProvider(client=fake)
        d.arm(1.0)
        with pytest.raises(LLMError):
            d.draft_script(ch, pack, ep.title, 9, [])
        assert d.spent_usd > 0  # the attempt still costs money and must be recorded


def test_invented_claim_ids_are_rejected(settings, episode):
    ep, ch, pack = _setup(settings, episode)
    bad = json.loads(json.dumps(GOOD))
    bad["sections"][0]["paragraphs"][0]["claims"] = ["C99"]
    d = AnthropicDraftProvider(client=FakeClient(bad))
    d.arm(1.0)
    with pytest.raises(LLMError, match="unknown claims"):
        d.draft_script(ch, pack, ep.title, 9, [])


def test_worst_case_estimate_covers_full_output():
    d = AnthropicDraftProvider()
    assert d.estimate_usd(4000) == pytest.approx(1000 / 1e6 * 4 + 16000 / 1e6 * 20, abs=1e-4)
    assert Usage("claude-sonnet-5-5", 1_000_000, 0).usd() == pytest.approx(2.0)


def test_cli_refuses_without_flag(settings, monkeypatch):
    from typer.testing import CliRunner

    from studio.cli import app

    monkeypatch.setenv("STUDIO_ROOT", str(settings.root))
    monkeypatch.setenv("STUDIO_PROJECTS_DIR", str(settings.projects_dir))
    res = CliRunner().invoke(app, ["draft", "ideas", "engineering_explained",
                                   "--i-consent-to-spend"])
    assert res.exit_code == 1 and "paid providers are disabled" in res.output


def test_connect_status_never_prints_secret_values(settings, monkeypatch):
    from dataclasses import replace

    from studio.connect import status, status_markdown

    assert not any(sv.ready for sv in status(settings))
    secret = "sk_live_VERYSECRET123"
    monkeypatch.setenv("ELEVENLABS_API_KEY", secret)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    s2 = replace(settings, elevenlabs_key_present=True, anthropic_credentials_hint=True,
                 enable_paid=True, elevenlabs_plan="starter")
    md = status_markdown(status(s2), 0.0, 250.0)
    assert secret not in md
    el = next(sv for sv in status(s2) if sv.name.startswith("ElevenLabs"))
    assert [c.ok for c in el.checks][:3] == [True, True, True]
