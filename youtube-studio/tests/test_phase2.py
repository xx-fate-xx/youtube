"""Phase 2: ElevenLabs guard + alignment, assisted fact-checking, font licence, motion
engine and Shorts legibility."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import pytest

from studio.assets import bundled_font_issues, parse_steps
from studio.audio import NarrationItem, synthesize
from studio.budget import BudgetGuard, ConsentRequired, PaidProvidersDisabled
from studio.db import session_scope
from studio.diagrams import DIAGRAMS
from studio.models import LicenseClearance, ShortSpec, VerificationStatus
from studio.motion import Shot, beat_times, clamp_shot, plan_scene
from studio.providers.llm import MockLLMProvider
from studio.providers.voice import (
    ElevenLabsError,
    ElevenLabsVoiceProvider,
    NotArmed,
    words_from_alignment,
)
from studio.research import ResearchError
from studio.shorts import MIN_TEXT_PX, legibility_issues, prepare_short, short_plan
from studio.verification import apply_proposal, import_proposals, load_proposals
from studio.visuals import INTER_DIR, Theme, font_is_bundled_inter

KEY = "sk_test_SECRET_123"


def _alignment(text: str, per_char: float = 0.05) -> dict:
    return {"characters": list(text),
            "character_start_times_seconds": [i * per_char for i in range(len(text))],
            "character_end_times_seconds": [(i + 1) * per_char for i in range(len(text))]}


class FakeTransport:
    def __init__(self, statuses=(200,)):
        self.statuses = list(statuses)
        self.calls: list[tuple[str, dict, dict]] = []

    def __call__(self, url, headers, body):
        req = json.loads(body)
        self.calls.append((url, headers, req))
        status = self.statuses.pop(0) if self.statuses else 200
        if status != 200:
            return status, {}, json.dumps({"detail": {"code": "x", "message": "nope"}}).encode()
        pcm = b"\x00\x00" * 2205  # 0.1 s at 22.05 kHz
        return 200, {"request-id": "r1"}, json.dumps({
            "audio_base64": base64.b64encode(pcm).decode(),
            "alignment": _alignment(req["text"]), "normalized_alignment": None}).encode()


def _provider(transport, plan="creator", **kw):
    return ElevenLabsVoiceProvider(None, "voice123", api_key=KEY, plan=plan,
                                   transport=transport, sleep=lambda s: None, **kw)


# ------------------------------------------------------------------ ElevenLabs


def test_alignment_groups_characters_into_words():
    words = words_from_alignment(_alignment("Hi there."))
    assert [w for w, _, _ in words] == ["Hi", "there."]
    assert words[1][1] == pytest.approx(0.15) and words[1][2] == pytest.approx(0.45)
    assert words_from_alignment(None) == []


def test_elevenlabs_refuses_to_send_without_arming(tmp_path):
    t = FakeTransport()
    vp = _provider(t)
    with pytest.raises(NotArmed):
        vp.synthesize_sentence_timed("Hello.", tmp_path / "a.wav")
    assert t.calls == []  # nothing left the machine


def test_elevenlabs_arm_caps_characters(tmp_path):
    t = FakeTransport()
    vp = _provider(t)
    vp.arm(10)
    vp.synthesize_sentence_timed("Hello.", tmp_path / "a.wav")  # 6 chars
    with pytest.raises(NotArmed):
        vp.synthesize_sentence_timed("World again.", tmp_path / "b.wav")
    assert len(t.calls) == 1


def test_elevenlabs_request_shape_and_secret_hygiene(tmp_path):
    t = FakeTransport()
    vp = _provider(t, stitching="text", voice_settings={"stability": 0.6, "style": 0.0})
    vp.arm(1000)
    d, words = vp.synthesize_sentence_timed("Light in glass.", tmp_path / "a.wav",
                                            previous_text="Before.", next_text="After.")
    url, headers, body = t.calls[0]
    assert url.endswith("/v1/text-to-speech/voice123/with-timestamps?output_format=pcm_22050")
    assert headers["xi-api-key"] == KEY
    assert body["previous_text"] == "Before." and body["next_text"] == "After."
    assert body["voice_settings"] == {"stability": 0.6, "style": 0.0}
    assert d == pytest.approx(0.1)
    assert [w for w, _, _ in words] == ["Light", "in", "glass."]
    assert KEY not in repr(vp)
    align = json.loads((tmp_path / "a.align.json").read_text())
    assert KEY not in json.dumps(align)


def test_elevenlabs_retries_429_but_not_401(tmp_path):
    vp = _provider(FakeTransport([429, 503, 200]))
    vp.arm(100)
    vp.synthesize_sentence_timed("Ok.", tmp_path / "a.wav")
    assert vp.requests == 3
    vp2 = _provider(FakeTransport([401]))
    vp2.arm(100)
    with pytest.raises(ElevenLabsError) as exc:
        vp2.synthesize_sentence_timed("Ok.", tmp_path / "b.wav")
    assert "401" in str(exc.value) and KEY not in str(exc.value)
    assert vp2.requests == 1


def test_elevenlabs_licence_depends_on_plan():
    assert _provider(None, "creator").license().clearance == LicenseClearance.CLEARED
    assert _provider(None, "free").license().clearance == LicenseClearance.RESTRICTED
    assert _provider(None, "").license().clearance == LicenseClearance.UNKNOWN


def test_paid_voice_needs_flag_and_consent(settings, paid_settings):
    vp = _provider(FakeTransport())
    est = vp.estimate_usd("x" * 1000)
    assert est == pytest.approx(0.08)
    with session_scope(settings.db_path) as s, pytest.raises(PaidProvidersDisabled):
        BudgetGuard(s, settings).preflight(provider=vp.name, operation="tts",
                                           estimate_usd=est, paid=True, consent=True)
    with session_scope(paid_settings.db_path) as s, pytest.raises(ConsentRequired):
        BudgetGuard(s, paid_settings).preflight(provider=vp.name, operation="tts",
                                                estimate_usd=est, paid=True, consent=False)


def test_captions_use_exact_provider_timings_and_cache(tmp_path, settings):
    from studio.channels import get_channel

    ch = get_channel(settings.channels_dir, "engineering_explained")
    t = FakeTransport()
    vp = _provider(t)
    vp.arm(1000)
    items = [NarrationItem("sc1", "First sentence here. Second one.")]
    timings, _ = synthesize(items, vp, ch, tmp_path / "n.wav", tmp_path / "cache")
    words = timings[0].words
    assert [w.word for w in words][:3] == ["First", "sentence", "here."]
    # exact: "sentence" starts at char 6 * 0.05 s after the lead-in, not interpolated
    assert words[1].start == pytest.approx(0.4 + 0.30, abs=1e-3)
    calls = len(t.calls)
    synthesize(items, vp, ch, tmp_path / "n2.wav", tmp_path / "cache")
    assert len(t.calls) == calls  # cached audio + alignment: no second paid request


# ------------------------------------------------------------------ fact-check proposals


def test_proposals_never_verify_by_themselves(settings, episode):
    ep, ws, ch = episode
    pack = MockLLMProvider(settings.samples_dir).research(ep.id, ep.topic, "undersea_cables")
    pset = import_proposals(ws, pack, settings.samples_dir / "undersea_cables" /
                            "verification_proposals.json")
    assert len(pset.proposals) == 21
    assert all(c.status == VerificationStatus.UNVERIFIED for c in pack.claims)
    assert load_proposals(ws) is not None


def test_apply_proposal_requires_human_and_rewording_for_partial(settings, episode):
    ep, ws, ch = episode
    pack = MockLLMProvider(settings.samples_dir).research(ep.id, ep.topic, "undersea_cables")
    pset = import_proposals(ws, pack, settings.samples_dir / "undersea_cables" /
                            "verification_proposals.json")
    with pytest.raises(ResearchError):
        apply_proposal(pack, pset.get("C19"), by="", accept_rewording=False)
    partial = next(p for p in pset.proposals if p.verdict == "partially_supported")
    with pytest.raises(ResearchError):
        apply_proposal(pack, pset.get(partial.claim_id), by="Ann", accept_rewording=False)
    text = apply_proposal(pack, pset.get(partial.claim_id), by="Ann", accept_rewording=True)
    claim = pack.claim(partial.claim_id)
    assert claim.status == VerificationStatus.VERIFIED and claim.text == text
    assert claim.supporting_snippet == partial.snippet and "reworded from" in claim.notes
    assert any(pack.source(sid).url == partial.source_url for sid in claim.source_ids)


def test_unchecked_proposal_cannot_verify(settings, episode):
    ep, ws, ch = episode
    pack = MockLLMProvider(settings.samples_dir).research(ep.id, ep.topic, "undersea_cables")
    pset = import_proposals(ws, pack, settings.samples_dir / "undersea_cables" /
                            "verification_proposals.json")
    p = pset.get("C19").model_copy(update={"verdict": "not_checked"})
    with pytest.raises(ResearchError):
        apply_proposal(pack, p, by="Ann", accept_rewording=True)


def test_import_rejects_supported_without_snippet(tmp_path, settings, episode):
    ep, ws, ch = episode
    pack = MockLLMProvider(settings.samples_dir).research(ep.id, ep.topic, "undersea_cables")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"claim_id": "C1", "claim_text": "x", "verdict": "supported",
                                "snippet": ""}]))
    with pytest.raises(ResearchError):
        import_proposals(ws, pack, bad)


# ------------------------------------------------------------------ font licence


def test_bundled_inter_is_used_and_intact(tmp_path, monkeypatch):
    assert font_is_bundled_inter()
    assert bundled_font_issues() == []
    source = json.loads((INTER_DIR / "SOURCE.json").read_text())
    assert source["license"].startswith("SIL Open Font License 1.1")
    assert "does not apply" in source["license_key_sentence"]
    # tampering is detected
    copy = tmp_path / "inter"
    shutil.copytree(INTER_DIR, copy)
    (copy / "Inter-Bold.ttf").write_bytes(b"tampered")
    monkeypatch.setattr("studio.assets.INTER_DIR", copy)
    assert any("sha256 mismatch" in i for i in bundled_font_issues())


# ------------------------------------------------------------------ motion engine


def test_beats_snap_to_sentence_starts_and_stay_ordered():
    times = beat_times(3, 30.0, anchors=[0.0, 4.0, 9.5, 19.0, 25.0])
    assert times[0] == 0.0 and times == sorted(times)
    assert 9.5 in times or 19.0 in times
    assert all(b - a >= 2.0 for a, b in zip(times, times[1:], strict=False))
    assert beat_times(1, 10.0) == [0.0]


def test_camera_stays_inside_canvas():
    s = clamp_shot(Shot(10, 10, 600), 16 / 9)
    assert s.cx - s.vw / 2 >= 0 and s.cy - s.vw / (16 / 9) / 2 >= 0
    s = clamp_shot(Shot(1900, 1070, 5000), 16 / 9)
    assert s.vw == 1920


def test_every_diagram_plans_and_moves(settings):
    from studio.channels import get_channel

    theme = Theme.from_identity(get_channel(settings.channels_dir,
                                            "engineering_explained").visual)
    for ref, d in DIAGRAMS.items():
        c = d.build(theme)
        plan = plan_scene(c, parse_steps("", c.max_step), 20.0)
        assert plan.keys[0][0] == 0.0, ref
        shots = {(round(s.cx), round(s.cy), round(s.vw)) for _, s, _ in plan.keys}
        assert len(shots) > 1, f"{ref}: camera never moves"


def test_parse_steps_accepts_lists():
    assert parse_steps("2,4", 4) == [2, 4]
    assert parse_steps("0-1,3", 4) == [0, 1, 3]


# ------------------------------------------------------------------ Shorts legibility


def test_sample_shorts_are_legible_on_a_phone(settings):
    from studio.channels import get_channel

    theme = Theme.from_identity(get_channel(settings.channels_dir,
                                            "engineering_explained").visual)
    for spec in MockLLMProvider(settings.samples_dir).shorts("e", "t", None, 3,
                                                               "undersea_cables"):
        canvas, plan, dropped = prepare_short(spec, theme, 30.0)
        assert legibility_issues(spec, canvas, plan) == [], spec.id
        assert dropped == [], spec.id


def test_tiny_labels_are_flagged():
    theme = Theme("#000000", "#FFFFFF", "#00FFFF", "#FFFF00", "#888888", "#000000CC", "x")
    spec = ShortSpec(id="s", title="t", hook="h", narration="n", diagram="recap",
                     focus="0,0,1920,1080")
    canvas = DIAGRAMS["recap"].build(theme)  # unboosted, full-width framing
    plan = short_plan(spec, canvas, 10.0)
    issues = legibility_issues(spec, canvas, plan)
    assert any(f"< {MIN_TEXT_PX}px" in i for i in issues)


def test_default_stitching_sends_request_ids_not_extra_text(tmp_path):
    t = FakeTransport()
    vp = _provider(t)
    vp.arm(1000)
    vp.synthesize_sentence_timed("One.", tmp_path / "a.wav", previous_text="x", next_text="y")
    vp.synthesize_sentence_timed("Two.", tmp_path / "b.wav", previous_text="x", next_text="y")
    first, second = t.calls[0][2], t.calls[1][2]
    assert "previous_text" not in first and "next_text" not in second
    assert second["previous_request_ids"] == ["r1"]
    assert vp.chars_sent == len("One.") + len("Two.")


def test_voice_lookup_is_read_only_and_needs_key():
    seen = []

    def getter(url, headers):
        seen.append((url, headers))
        return 200, json.dumps({"voice_id": "v1", "name": "Caleb", "category": "professional",
                                "labels": {"accent": "american", "gender": "male"},
                                "sharing": {"disable_at_unix": None}}).encode()

    info = _provider(None).get_voice("v1", getter=getter)
    assert info["labels"]["accent"] == "american" and seen[0][0].endswith("/v1/voices/v1")
    with pytest.raises(ElevenLabsError):
        ElevenLabsVoiceProvider(None, "v").get_voice("v1", getter=getter)


def test_credit_estimate_by_model():
    assert _provider(None).estimate_credits(1000) == 1000  # multilingual v2: 1 credit/char
    flash = ElevenLabsVoiceProvider(None, "v", model_id="eleven_flash_v2_5")
    assert flash.estimate_credits(1000) == 500


def test_narration_change_is_exact_and_single_use(settings, episode):
    from studio.verification import apply_narration_change

    ep, ws, ch = episode
    pack = MockLLMProvider(settings.samples_dir).research(ep.id, ep.topic, "undersea_cables")
    script = MockLLMProvider(settings.samples_dir).script(ep.id, ep.title, ch, pack, 9,
                                                          "undersea_cables")
    pset = import_proposals(ws, pack, settings.samples_dir / "undersea_cables" /
                            "verification_proposals_rc.json")
    change = pset.get("C4").narration_change
    if change["proposed"] in script.narration_text:  # sample already carries the RC wording
        apply_narration_change(script, {"current": change["proposed"],
                                        "proposed": change["current"]})
    apply_narration_change(script, change)
    assert change["proposed"] in script.narration_text
    assert change["current"] not in script.narration_text
    with pytest.raises(ResearchError):
        apply_narration_change(script, change)  # already applied -> refuses


def test_rc_proposals_cite_no_wikipedia_and_table_lists_all(settings, episode):
    from studio.verification import confirmation_table

    ep, ws, ch = episode
    pack = MockLLMProvider(settings.samples_dir).research(ep.id, ep.topic, "undersea_cables")
    pset = import_proposals(ws, pack, settings.samples_dir / "undersea_cables" /
                            "verification_proposals_rc.json")
    assert not [p.claim_id for p in pset.proposals if "wikipedia.org" in p.source_url]
    table = confirmation_table(pack, pset, {c.id for c in pack.claims})
    assert all(f"| C{i} |" in table for i in range(1, 22))
    assert all(c.status == VerificationStatus.UNVERIFIED for c in pack.claims)


def test_voices_use_writes_only_the_voice_block(settings, monkeypatch):
    import yaml
    from typer.testing import CliRunner

    from studio.channels import get_channel
    from studio.cli import app

    monkeypatch.setenv("STUDIO_ROOT", str(settings.root))
    monkeypatch.setenv("STUDIO_PROJECTS_DIR", str(settings.projects_dir))
    repo = Path(__file__).resolve().parents[1]
    shutil.copytree(repo / "channels" / "voices", settings.channels_dir / "voices",
                    dirs_exist_ok=True)
    before = yaml.safe_load((settings.channels_dir / "engineering_explained.yaml").read_text())
    res = CliRunner().invoke(app, ["voices", "use", "wyatt"])
    assert res.exit_code == 0, res.output
    ch = get_channel(settings.channels_dir, "engineering_explained")
    assert ch.narration.elevenlabs.voice_id == "FrS6cKLB1wg4WYgPa9GW"
    assert ch.narration.elevenlabs.speed == 0.95
    after = yaml.safe_load((settings.channels_dir / "engineering_explained.yaml").read_text())
    assert {k: v for k, v in after.items() if k != "narration"} == {
        k: v for k, v in before.items() if k != "narration"}


def test_interactive_claim_review_needs_a_human_answer(settings, episode, monkeypatch):
    from typer.testing import CliRunner

    from studio.cli import app
    from studio.research import load_pack, save_pack

    ep, ws, ch = episode
    monkeypatch.setenv("STUDIO_ROOT", str(settings.root))
    monkeypatch.setenv("STUDIO_PROJECTS_DIR", str(settings.projects_dir))
    pack = MockLLMProvider(settings.samples_dir).research(ep.id, ep.topic, "undersea_cables")
    save_pack(ws, pack)
    import_proposals(ws, pack, settings.samples_dir / "undersea_cables" /
                     "verification_proposals_rc.json")
    # y for C1, n for C2 (+ reason), then quit
    res = CliRunner().invoke(app, ["claim", "review", ep.id, "--by", "Ann"],
                             input="y\nn\nwrong figure\nq\n")
    assert res.exit_code == 0, res.output
    after = load_pack(ws)
    assert after.claim("C1").status == VerificationStatus.VERIFIED
    assert after.claim("C1").verified_by == "Ann"
    assert after.claim("C2").status.value == "rejected"
    assert after.claim("C3").status == VerificationStatus.UNVERIFIED
