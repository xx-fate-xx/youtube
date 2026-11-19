from __future__ import annotations

import pytest

from studio.assets import build_assets, load_manifest, manifest_issues, parse_steps
from studio.editorial import script_issues
from studio.models import (
    AssetManifest,
    AssetRecord,
    Claim,
    LicenseClearance,
    ResearchPack,
    Script,
    ScriptParagraph,
    ScriptSection,
    Source,
    VerificationStatus,
)
from studio.providers.footage import import_local_asset
from studio.providers.llm import MockLLMProvider
from studio.research import ResearchError, claim_blockers, validate_pack, verify_claim
from studio.storyboard import build_storyboard


def _pack() -> ResearchPack:
    return ResearchPack(
        episode_id="e", topic="t", generated_by="test",
        sources=[Source(id="S1", url="https://example.org/a", title="A")],
        claims=[Claim(id="C1", text="x", source_ids=["S1"])],
    )


def test_sample_research_pack_is_valid_and_fully_unverified(settings):
    pack = MockLLMProvider(settings.samples_dir).research("e", "t", "undersea_cables")
    assert validate_pack(pack) == []
    assert pack.claims and all(c.status == VerificationStatus.UNVERIFIED for c in pack.claims)
    assert all(c.supporting_snippet == "" for c in pack.claims)


def test_mock_provider_without_sample_invents_nothing(settings):
    pack = MockLLMProvider(settings.samples_dir).research("e", "Some new topic", None)
    assert pack.sources == [] and pack.claims == []


def test_invalid_citations_are_detected():
    pack = _pack()
    pack.sources.append(Source(id="S2", url="not-a-url", title="B"))
    pack.claims.append(Claim(id="C2", text="y", source_ids=["S9"]))
    problems = validate_pack(pack)
    assert any("invalid URL" in p for p in problems)
    assert any("unknown source S9" in p for p in problems)


def test_verification_requires_snippet_and_name():
    pack = _pack()
    with pytest.raises(ResearchError):
        verify_claim(pack, "C1", snippet="  ", verified_by="Ann")
    with pytest.raises(ResearchError):
        verify_claim(pack, "C1", snippet="quote", verified_by="")
    c = verify_claim(pack, "C1", snippet="quote", verified_by="Ann")
    assert c.status == VerificationStatus.VERIFIED and c.verified_at is not None


def test_unverified_claims_block():
    pack = _pack()
    assert claim_blockers(pack, {"C1"})
    assert claim_blockers(pack, {"C404"}) == ["script cites unknown claim C404"]
    verify_claim(pack, "C1", snippet="quote", verified_by="Ann")
    assert claim_blockers(pack, {"C1"}) == []


def test_numbers_without_citation_are_blockers(settings):
    from studio.channels import get_channel

    ch = get_channel(settings.channels_dir, "engineering_explained")
    pack = _pack()
    script = Script(episode_id="e", title="t", generated_by="test", sections=[ScriptSection(
        id="s", heading="h", paragraphs=[ScriptParagraph(text="It opened in 1858. " * 200)])])
    issues = [i.message for i in script_issues(script, pack, ch, 9)]
    assert any("number/date but cites no claim" in m for m in issues)


def test_generated_assets_and_bundled_inter_font_are_cleared(settings, episode):
    ep, ws, ch = episode
    script = MockLLMProvider(settings.samples_dir).script(ep.id, ep.title, ch, _pack(), 9,
                                                          "undersea_cables")
    board, warnings = build_storyboard(script, ch)
    assert warnings == []
    build_assets(ws, board, ch)
    manifest = load_manifest(ws, ep.id)
    issues = manifest_issues(ws, manifest, board)
    assert issues == [], issues
    font = manifest.get("font-main")
    assert font.clearance == LicenseClearance.CLEARED
    assert "OFL" in font.license and "LICENSE.txt" in font.license_proof
    diagrams = [a for a in manifest.assets if a.kind == "diagram"]
    assert diagrams and all(a.clearance == LicenseClearance.CLEARED and a.sha256
                            for a in diagrams)
    # tampering with a recorded asset is detected
    (ws.root / diagrams[0].path).write_text("<svg/>")
    assert any("sha256 mismatch" in i for i in manifest_issues(ws, manifest, board))


def test_manifest_flags_missing_licence_and_attribution(tmp_path):
    from studio.episodes import Workspace

    ws = Workspace(tmp_path)
    (tmp_path / "clip.mp4").write_bytes(b"x")
    manifest = AssetManifest(episode_id="e", assets=[AssetRecord(
        id="clip", path="clip.mp4", kind="footage", origin="stock", author="someone",
        license="", license_proof="", clearance=LicenseClearance.UNKNOWN,
        attribution_required=True, source_url="https://example.org/v")])
    issues = " | ".join(manifest_issues(ws, manifest))
    for needle in ("missing licence", "missing licence proof", "clearance is unknown",
                   "attribution required", "without download timestamp"):
        assert needle in issues


def test_import_requires_licence_and_proof(tmp_path):
    src = tmp_path / "broll.mp4"
    src.write_bytes(b"fake")
    with pytest.raises(ValueError):
        import_local_asset(tmp_path, src, asset_id="b", kind="footage", author="me",
                           license="", license_proof="", clearance=LicenseClearance.CLEARED)
    rec = import_local_asset(tmp_path, src, asset_id="b", kind="footage", author="me",
                             license="Pexels License", license_proof="https://example.org/p",
                             clearance=LicenseClearance.CLEARED,
                             source_url="https://example.org/v")
    assert rec.downloaded_at is not None and rec.sha256


def test_parse_steps():
    assert parse_steps("", 3) == [0, 1, 2, 3]
    assert parse_steps("2", 3) == [2]
    assert parse_steps("1-9", 3) == [1, 2, 3]
