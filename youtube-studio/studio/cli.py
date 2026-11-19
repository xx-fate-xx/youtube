"""`studio` command-line interface."""

from __future__ import annotations

import functools
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from studio import analytics as analytics_mod
from studio import visuals
from studio.assets import (
    build_assets,
    load_manifest,
    manifest_issues,
    music_record,
    save_manifest,
)
from studio.audio import NarrationItem, build_narration, narration_from_user_file
from studio.authoring import check as author_check
from studio.authoring import init_files, source_for
from studio.budget import BudgetError, BudgetGuard, cost_report
from studio.channels import ChannelProfile, get_channel, load_channels
from studio.config import Settings, load_settings
from studio.db import session_scope
from studio.editorial import load_script, save_script, script_issues
from studio.episodes import Workspace, create_episode, get_episode, workspace
from studio.fsutil import atomic_write_text, read_model, sha256_file
from studio.jobs import run_job
from studio.models import (
    Episode,
    EpisodeState,
    LicenseClearance,
    NarrationTrack,
    ReviewDecisionKind,
    StateTransition,
    VerificationStatus,
)
from studio.providers.footage import import_local_asset
from studio.providers.llm import MockLLMProvider, find_sample
from studio.providers.voice import (
    ElevenLabsVoiceProvider,
    MacOSSayVoiceProvider,
    MockVoiceProvider,
    VoiceProvider,
)
from studio.publish import PublishBlocked, change_visibility, publish_private, record_manual_upload
from studio.research import (
    ResearchError,
    add_claim,
    add_source,
    load_pack,
    save_pack,
    set_claim_status,
    verify_claim,
)
from studio.review import (
    ReviewBlocked,
    ai_disclosure_audit,
    build_report,
    license_audit_markdown,
    write_package,
    write_release_candidate,
)
from studio.state import IllegalTransition, enter_step, require_at_least, transition
from studio.storyboard import build_storyboard, load_storyboard, save_storyboard
from studio.verification import (
    apply_narration_change,
    apply_proposal,
    confirmation_table,
    import_proposals,
    load_proposals,
    write_report,
)
from studio.visuals import Theme

app = typer.Typer(no_args_is_help=True, help="AI YouTube Studio - local-first production "
                  "assistant. Nothing is published automatically.")
episode_app = typer.Typer(no_args_is_help=True, help="Create and inspect episodes")
claim_app = typer.Typer(no_args_is_help=True, help="Add and verify research claims")
assets_app = typer.Typer(no_args_is_help=True, help="Build and check visual assets/licences")
cost_app = typer.Typer(no_args_is_help=True, help="Budget and cost ledger")
channels_app = typer.Typer(no_args_is_help=True, help="Channel style profiles")
voices_app = typer.Typer(no_args_is_help=True, help="ElevenLabs voice candidates (no generation)")
connect_app = typer.Typer(no_args_is_help=True, help="Paid/external service readiness")
draft_app = typer.Typer(no_args_is_help=True,
                        help="Claude drafts (PAID; needs flag + consent; writes *.draft.yaml)")
author_app = typer.Typer(no_args_is_help=True, help="Hand-write an episode (no LLM needed)")
diagrams_app = typer.Typer(no_args_is_help=True, help="Diagram library (code + YAML templates)")
app.add_typer(episode_app, name="episode")
app.add_typer(claim_app, name="claim")
app.add_typer(assets_app, name="assets")
app.add_typer(cost_app, name="cost")
app.add_typer(channels_app, name="channels")
app.add_typer(voices_app, name="voices")
app.add_typer(diagrams_app, name="diagrams")
app.add_typer(author_app, name="author")
app.add_typer(draft_app, name="draft")
app.add_typer(connect_app, name="connect")

KNOWN_ERRORS = (IllegalTransition, BudgetError, ResearchError, ReviewBlocked, PublishBlocked,
                KeyError, ValueError, FileNotFoundError, RuntimeError)


def handled(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (typer.Exit, typer.Abort, typer.BadParameter):
            raise
        except KNOWN_ERRORS as exc:
            msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
            typer.secho(f"ERROR ({type(exc).__name__}): {msg}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
    return wrapper


def settings() -> Settings:
    s = load_settings()
    if s.font_path:
        visuals.FONT_OVERRIDE = s.font_path
    return s


def ok(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.GREEN)


def warn(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.YELLOW)


def _ctx(ep_ref: str):
    s = settings()
    return s, ep_ref


def _load(session, s: Settings, ep_ref: str) -> tuple[Episode, Workspace, ChannelProfile]:
    ep = get_episode(session, ep_ref)
    return ep, workspace(s, ep).ensure(), get_channel(s.channels_dir, ep.channel)


def make_voice(name: str, channel: ChannelProfile, s: Settings) -> VoiceProvider:
    wpm = channel.narration.words_per_minute
    if name == "mock":
        return MockVoiceProvider(wpm)
    if name == "macos_say":
        return MacOSSayVoiceProvider(channel.narration.local_voice or "Samantha", wpm)
    if name == "elevenlabs":
        import os

        # The key is read here, passed to the provider only, and never stored or printed.
        cfg = channel.narration.elevenlabs
        return ElevenLabsVoiceProvider(
            s.elevenlabs_usd_per_1k_chars, s.elevenlabs_voice_id or cfg.voice_id,
            api_key=os.environ.get("ELEVENLABS_API_KEY", "").strip(),
            model_id=s.elevenlabs_model_id_env or cfg.model_id, plan=s.elevenlabs_plan,
            voice_settings=cfg.voice_settings())
    raise ValueError(f"Unknown voice provider '{name}' (mock | macos_say | elevenlabs | file)")


# ------------------------------------------------------------------ setup / channels


@app.command()
@handled
def init() -> None:
    """Create the projects folder and database; check local tools."""
    s = settings()
    s.projects_dir.mkdir(parents=True, exist_ok=True)
    with session_scope(s.db_path):
        pass
    channels = load_channels(s.channels_dir)
    ok(f"Database: {s.db_path}")
    ok(f"Channels: {', '.join(channels)}")
    try:
        ok(f"FFmpeg: {s.ffmpeg_binary()}")
    except RuntimeError as exc:
        warn(str(exc))
    typer.echo(f"Monthly budget cap: ${s.monthly_budget_usd:.2f}; paid providers "
               f"{'ENABLED' if s.enable_paid else 'disabled'}; YouTube upload "
               f"{'enabled' if s.enable_youtube else 'disabled (release-folder mode)'}")
    if not (s.root / ".env").exists():
        typer.echo("No .env found - defaults in use (copy .env.example to .env to configure).")


@channels_app.command("list")
@handled
def channels_list() -> None:
    for key, c in load_channels(settings().channels_dir).items():
        typer.echo(f"{key:24} {c.name:24} {c.runtime_minutes[0]:g}-{c.runtime_minutes[1]:g} min "
                   f"| {c.narration.words_per_minute} wpm | {c.positioning.strip()[:60]}...")


@channels_app.command("show")
@handled
def channels_show(key: str) -> None:
    c = get_channel(settings().channels_dir, key)
    typer.echo(json.dumps(c.model_dump(), indent=2))


@app.command()
@handled
def ideas(channel: Annotated[str, typer.Option(help="channel key")],
          count: int = 10) -> None:
    """List topic proposals (offline: the editor-curated backlog; never invented facts)."""
    s = settings()
    ch = get_channel(s.channels_dir, channel)
    proposals = MockLLMProvider(s.samples_dir).propose_ideas(ch, count)
    if len(proposals) < count:
        warn(f"Only {len(proposals)} curated ideas available offline (asked for {count}).")
    out = s.projects_dir / channel / "ideas.md"
    atomic_write_text(out, f"# Idea proposals - {ch.name}\n\nEach needs research before "
                      "scripting.\n\n" + "".join(f"- {p}\n" for p in proposals))
    for i, p in enumerate(proposals, 1):
        typer.echo(f"{i:2}. {p}")
    ok(f"Saved {out}")


# ------------------------------------------------------------------ episodes


@episode_app.command("create")
@handled
def episode_create(channel: Annotated[str, typer.Option()],
                   topic: Annotated[str, typer.Option()],
                   title: str | None = None,
                   minutes: Annotated[float, typer.Option(help="target runtime")] = 10.0) -> None:
    s = settings()
    ch = get_channel(s.channels_dir, channel)
    sample = find_sample(s.samples_dir, topic)
    with session_scope(s.db_path) as session:
        ep = create_episode(session, s, ch, topic, title=title, target_minutes=minutes,
                            sample=sample)
        ok(f"Created {ep.id} [{ep.state}] in {workspace(s, ep).root}")
        if sample:
            typer.echo(f"Using curated sample fixture '{sample}' for the mock providers.")


@episode_app.command("list")
@handled
def episode_list(channel: str | None = None) -> None:
    s = settings()
    from sqlmodel import select

    with session_scope(s.db_path) as session:
        stmt = select(Episode)
        if channel:
            stmt = stmt.where(Episode.channel == channel)
        for ep in session.exec(stmt).all():
            typer.echo(f"{ep.id:48} {ep.state:16} {ep.title}")


@episode_app.command("show")
@handled
def episode_show(episode: str) -> None:
    s = settings()
    from sqlmodel import col, select

    with session_scope(s.db_path) as session:
        ep, ws, _ = _load(session, s, episode)
        typer.echo(f"{ep.id}\n  channel: {ep.channel}\n  title: {ep.title}\n  state: {ep.state}"
                   f"\n  remote video: {ep.remote_video_id or '-'} ({ep.youtube_privacy or '-'})"
                   f"\n  folder: {ws.root}")
        typer.echo("  history:")
        rows = session.exec(select(StateTransition).where(
            StateTransition.episode_id == ep.id).order_by(col(StateTransition.id))).all()
        for t in rows:
            typer.echo(f"    {t.at:%Y-%m-%d %H:%M} {t.from_state or '-':>15} -> {t.to_state:15}"
                       f" {t.actor}: {t.note}")


# ------------------------------------------------------------------ research


@app.command()
@handled
def research(episode: str) -> None:
    """Build the research pack (sources + per-claim citations). Human verification required."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, _ = _load(session, s, episode)
        enter_step(session, ep, EpisodeState.RESEARCH, note="research pack generated")
        provider, sample, src_hash = source_for(ws, s.samples_dir, ep.sample, "research.yaml")
        BudgetGuard(session, s).preflight(provider=provider.name, operation="research",
                                          estimate_usd=0.0, paid=provider.paid)

        def work():
            pack = provider.research(ep.id, ep.topic, sample)
            if ws.research_file.exists():  # keep human verification on re-run
                old = load_pack(ws)
                for c in pack.claims:
                    prev = next((o for o in old.claims if o.id == c.id and o.text == c.text),
                                None)
                    if prev:
                        pack.claims[pack.claims.index(c)] = prev
            save_pack(ws, pack)
            return pack, ws.research_file

        pack = run_job(session, ep.id, "research", src_hash, work)
        BudgetGuard(session, s).record(provider=provider.name, operation="research",
                                       episode_id=ep.id)
        unverified = [c for c in pack.claims if c.status != VerificationStatus.VERIFIED]
        ok(f"Research pack: {len(pack.sources)} sources, {len(pack.claims)} claims "
           f"-> {ws.research / 'sources.md'}")
        if unverified:
            warn(f"{len(unverified)} claims are NOT verified. Open each source and run "
                 f"`studio claim verify {ep.id} <claim-id> --snippet '...' --by NAME`. "
                 "Unverified claims block approval.")


@claim_app.command("list")
@handled
def claim_list(episode: str) -> None:
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        for c in pack.claims:
            typer.echo(f"{c.id:4} {c.status.value:10} [{','.join(c.source_ids)}] {c.text}")


@claim_app.command("verify")
@handled
def claim_verify(episode: str, claim_id: str,
                 snippet: Annotated[str, typer.Option(help="exact supporting text from source")],
                 by: Annotated[str, typer.Option(help="verifier name")],
                 note: str = "") -> None:
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        verify_claim(pack, claim_id, snippet=snippet, verified_by=by, notes=note)
        save_pack(ws, pack)
        ok(f"{claim_id} verified by {by}")


@claim_app.command("set-status")
@handled
def claim_set_status(episode: str, claim_id: str,
                     status: Annotated[str, typer.Option(help="disputed | rejected | unverified")],
                     by: Annotated[str, typer.Option()], note: str = "") -> None:
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        set_claim_status(pack, claim_id, VerificationStatus(status), by=by, notes=note)
        save_pack(ws, pack)
        ok(f"{claim_id} -> {status}")


def _used_claims(ws: Workspace) -> set[str]:
    if not ws.script_file.exists():
        return set()
    sc = load_script(ws)
    return {cid for sec in sc.sections for p in sec.paragraphs for cid in p.claim_ids}


@claim_app.command("import-proposals")
@handled
def claim_import_proposals(episode: str, file: Path) -> None:
    """Import fact-check proposals (verdict + verbatim snippet). Statuses do NOT change."""
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        pset = import_proposals(ws, pack, file)
        out = write_report(ws, pack, pset, _used_claims(ws))
        ok(f"Imported {len(pset.proposals)} proposals -> {out}")
        warn("No claim was verified. Review each one, then run `studio claim apply-proposal`.")


@claim_app.command("report")
@handled
def claim_report(episode: str) -> None:
    """Write research/VERIFICATION_REPORT.md from the imported proposals."""
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        pset = load_proposals(ws)
        if pset is None:
            raise FileNotFoundError("No proposals; run `studio claim import-proposals` first")
        ok(f"Report -> {write_report(ws, pack, pset, _used_claims(ws))}")


@claim_app.command("apply-proposal")
@handled
def claim_apply_proposal(
        episode: str, claim_id: str,
        by: Annotated[str, typer.Option(help="name of the human who checked the source")],
        accept_rewording: Annotated[bool, typer.Option(
            help="replace the claim text with the proposed wording")] = False) -> None:
    """Human confirmation of one proposal (you opened the URL and read the snippet)."""
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        pset = load_proposals(ws)
        if pset is None:
            raise FileNotFoundError("No proposals; run `studio claim import-proposals` first")
        text = apply_proposal(pack, pset.get(claim_id), by=by,
                              accept_rewording=accept_rewording)
        save_pack(ws, pack)
        write_report(ws, pack, pset, _used_claims(ws))
        ok(f"{claim_id} verified by {by}: {text}")
        if accept_rewording:
            warn("Claim text changed: make sure the narration says the same thing, then "
                 "re-run `studio script`/`storyboard` checks.")


@claim_app.command("table")
@handled
def claim_table(episode: str) -> None:
    """Write research/FACT_CONFIRMATION.md: one row per claim for the final human decision."""
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        pset = load_proposals(ws)
        if pset is None:
            raise FileNotFoundError("No proposals; run `studio claim import-proposals` first")
        out = ws.research / "FACT_CONFIRMATION.md"
        atomic_write_text(out, confirmation_table(pack, pset, _used_claims(ws)))
        ok(f"Confirmation table -> {out}")


@claim_app.command("add")
@handled
def claim_add(episode: str, text: Annotated[str, typer.Option()],
              source_url: Annotated[str, typer.Option()],
              source_title: Annotated[str, typer.Option()],
              publisher: str = "", numeric: bool = False) -> None:
    """Add a claim with a real source you have opened (no invented citations)."""
    s = settings()
    with session_scope(s.db_path) as session:
        _, ws, _ = _load(session, s, episode)
        pack = load_pack(ws)
        existing = next((x for x in pack.sources if x.url == source_url), None)
        src = existing or add_source(pack, url=source_url, title=source_title,
                                     publisher=publisher)
        c = add_claim(pack, text=text, source_ids=[src.id], numeric=numeric)
        save_pack(ws, pack)
        ok(f"Added {c.id} citing {src.id} (unverified)")


# ------------------------------------------------------------------ script / storyboard


@app.command()
@handled
def script(episode: str) -> None:
    """Write the narration script (mock provider: curated sample or marked placeholder)."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        pack = load_pack(ws)
        enter_step(session, ep, EpisodeState.SCRIPT, note="script generated")
        provider, sample, src_hash = source_for(ws, s.samples_dir, ep.sample, "script.yaml")

        def work():
            sc = provider.script(ep.id, ep.title, ch, pack, ep.target_minutes, sample)
            save_script(ws, sc, pack)
            return sc, ws.script_file

        sc = run_job(session, ep.id, "script", f"{sha256_file(ws.research_file)}:{src_hash}",
                     work)
        BudgetGuard(session, s).record(provider=provider.name, operation="script",
                                       episode_id=ep.id)
        if sc.title != ep.title:
            ep.title = sc.title
            session.add(ep)
        ok(f"Script: {sc.word_count} words, {len(sc.sections)} sections -> "
           f"{ws.script / 'script.md'}")
        for issue in script_issues(sc, pack, ch, ep.target_minutes):
            (warn if issue.severity == "warning" else typer.echo)(f"  {issue}")


@app.command("script-change")
@handled
def script_apply_change(episode: str, claim_id: str,
                        by: Annotated[str, typer.Option(help="who approved the wording")]
                        ) -> None:
    """Apply the narration change proposed for a claim (exact sentence replacement)."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        pset = load_proposals(ws)
        if pset is None:
            raise FileNotFoundError("No proposals; run `studio claim import-proposals` first")
        change = pset.get(claim_id).narration_change
        if not change:
            raise ValueError(f"{claim_id} has no proposed narration change")
        script_obj = load_script(ws)
        section = apply_narration_change(script_obj, change)
        backup = ws.script / f"script.before-{claim_id}.json"
        backup.write_text(ws.script_file.read_text(encoding="utf-8"), encoding="utf-8")
        save_script(ws, script_obj, load_pack(ws))
        transition(session, ep, EpisodeState.SCRIPT, note=f"narration change {claim_id} by {by}")
        ok(f"{claim_id}: section '{section}' updated (backup {backup.name}). Re-run storyboard, "
           "assets, voice and render.")


@app.command()
@handled
def storyboard(episode: str) -> None:
    """Split the script into scenes with visuals and duration estimates."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        sc = load_script(ws)
        enter_step(session, ep, EpisodeState.STORYBOARD, note="storyboard built")
        board, warnings = build_storyboard(sc, ch)
        save_storyboard(ws, board)
        ok(f"Storyboard: {len(board.scenes)} scenes, est. {board.est_duration_s / 60:.1f} min "
           f"-> {ws.storyboard / 'storyboard.md'}")
        for w in warnings:
            warn(f"  {w}")


# ------------------------------------------------------------------ assets


@assets_app.command("build")
@handled
def assets_build(episode: str) -> None:
    """Render diagrams/cards (SVG + PNG build steps) and update the licence manifest."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        board = load_storyboard(ws)
        enter_step(session, ep, EpisodeState.ASSETS, note="assets built")
        manifest = run_job(session, ep.id, "assets", sha256_file(ws.storyboard_file),
                           lambda: (build_assets(ws, board, ch), ws.manifest_file))
        ok(f"Assets: {len(manifest.assets)} manifest entries -> {ws.assets}")


@assets_app.command("check")
@handled
def assets_check(episode: str) -> None:
    """Check licence/provenance of every asset; non-zero exit if anything blocks approval."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, _ = _load(session, s, episode)
        board = load_storyboard(ws)
        manifest = load_manifest(ws, ep.id)
        issues = manifest_issues(ws, manifest, board)
        for a in manifest.assets:
            typer.echo(f"  {a.id:28} {a.kind:9} {a.origin:16} {a.clearance.value:10} {a.license}")
        if issues:
            warn(f"{len(issues)} licence/provenance issue(s):")
            for i in issues:
                typer.echo(f"  - {i}")
            raise typer.Exit(2)
        ok("All assets cleared with proof on file.")


@assets_app.command("add")
@handled
def assets_add(episode: str, file: Path, asset_id: Annotated[str, typer.Option("--id")],
               kind: Annotated[str, typer.Option()], author: Annotated[str, typer.Option()],
               license: Annotated[str, typer.Option()],
               proof: Annotated[str, typer.Option(help="URL or file path of licence proof")],
               clearance: Annotated[str, typer.Option()] = "unknown",
               source_url: str = "", attribution: str = "", ai_generated: bool = False,
               realistic: bool = False) -> None:
    """Import licensed footage/images you supplied (e.g. own B-roll, Pexels download)."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, _ = _load(session, s, episode)
        rec = import_local_asset(ws.root, file, asset_id=asset_id, kind=kind, author=author,
                                 license=license, license_proof=proof,
                                 clearance=LicenseClearance(clearance), source_url=source_url,
                                 attribution_text=attribution, ai_generated=ai_generated,
                                 realistic=realistic,
                                 origin="stock" if source_url else "user_supplied")
        manifest = load_manifest(ws, ep.id)
        manifest.upsert(rec)
        save_manifest(ws, manifest)
        ok(f"Imported {asset_id} -> {rec.path} ({rec.clearance.value})")


@assets_app.command("license")
@handled
def assets_license(episode: str, asset_id: str,
                   clearance: Annotated[str, typer.Option()],
                   license: Annotated[str, typer.Option()],
                   proof: Annotated[str, typer.Option()]) -> None:
    """Record licence evidence for an existing manifest entry (operator statement)."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, _ = _load(session, s, episode)
        manifest = load_manifest(ws, ep.id)
        rec = manifest.get(asset_id)
        if not rec:
            raise KeyError(f"No asset {asset_id}")
        rec.clearance = LicenseClearance(clearance)
        rec.license = license
        rec.license_proof = proof
        save_manifest(ws, manifest)
        ok(f"{asset_id}: {clearance} ({license})")


# ------------------------------------------------------------------ voice / render


def _scene_items(ws: Workspace) -> list[NarrationItem]:
    return [NarrationItem(sc.id, sc.narration) for sc in load_storyboard(ws).scenes]


@app.command()
@handled
def voice(episode: str,
          provider: Annotated[str, typer.Option(help="mock | macos_say | elevenlabs | file")]
          = "",
          file: Annotated[Path | None, typer.Option(help="your own narration recording")]
          = None,
          speaker: str = "operator",
          dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
          i_consent_to_spend: Annotated[bool, typer.Option("--i-consent-to-spend")] = False
          ) -> None:
    """Generate narration + timings. --dry-run shows the cost preflight only."""
    s = settings()
    provider = provider or s.default_voice_provider
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        require_at_least(ep, EpisodeState.STORYBOARD, "generate narration")
        if EpisodeState(ep.state) in {EpisodeState.APPROVED, EpisodeState.PRIVATE_UPLOADED,
                                      EpisodeState.PUBLISHED, EpisodeState.ANALYZED}:
            raise IllegalTransition("Narration is locked after approval.")
        items = _scene_items(ws)
        chars = sum(len(i.text) for i in items)
        guard = BudgetGuard(session, s)
        if provider == "file":
            if not file:
                raise ValueError("--file is required with --provider file")
            if dry_run:
                typer.echo("Dry run: would import your recording; cost $0.00")
                return
            from studio import ffmpeg as ff

            wav = ws.audio / "user_narration_22k.wav"
            ff.to_wav_22k_mono(s.ffmpeg_binary(), file, wav)
            track, record = narration_from_user_file(ws, ep.id, items, wav, speaker=speaker,
                                                     binary=s.ffmpeg_binary())
        else:
            vp = make_voice(provider, ch, s)
            est = vp.estimate_usd(" ".join(i.text for i in items))
            typer.echo(f"Preflight: provider={vp.name} chars={chars} estimate=${est:.2f} "
                       f"month spent=${guard.month_spent():.2f}/{s.monthly_budget_usd:.2f}")
            if dry_run:
                try:
                    guard.preflight(provider=vp.name, operation="tts", estimate_usd=est,
                                    paid=vp.paid, consent=True, episode_id=ep.id)
                    ok("Dry run: preflight would pass (no audio generated, nothing spent).")
                except BudgetError as exc:
                    warn(f"Dry run: preflight would FAIL: {exc}")
                session.rollback()
                return
            guard.preflight(provider=vp.name, operation="tts", estimate_usd=est, paid=vp.paid,
                            consent=i_consent_to_spend, episode_id=ep.id)
            if vp.paid:
                vp.arm(chars)  # hard ceiling: exactly the characters that were preflighted
            track, record = run_job(session, ep.id, "voice", f"{vp.name}:{vp.voice}",
                                    lambda: (build_narration(ws, ep.id, items, vp, ch),
                                             ws.narration_file))
            guard.record(provider=vp.name, operation="tts", usd=est, units=chars, unit="chars",
                         paid=vp.paid, episode_id=ep.id)
        manifest = load_manifest(ws, ep.id)
        manifest.upsert(record)
        save_manifest(ws, manifest)
        if EpisodeState(ep.state) != EpisodeState.ASSETS:
            transition(session, ep, EpisodeState.ASSETS, note=f"narration via {track.provider}")
        ok(f"Narration: {track.duration_s / 60:.2f} min via {track.provider} "
           f"(timings: {track.timing_method}) -> {ws.root / track.audio_path}")
        if track.is_placeholder:
            warn("PLACEHOLDER narration (silent). The render will have no voice; approval is "
                 "blocked until real narration is supplied.")
        if record.clearance != LicenseClearance.CLEARED:
            warn(f"Narration licence: {record.clearance.value} - {record.notes}")


@app.command()
@handled
def render(episode: str, preview: Annotated[bool, typer.Option("--preview")] = False) -> None:
    """Render the long video with FFmpeg (1920x1080). --preview burns captions + review badges."""
    from studio.render import render_episode

    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        state = EpisodeState(ep.state)
        if state in {EpisodeState.APPROVED, EpisodeState.PRIVATE_UPLOADED,
                     EpisodeState.PUBLISHED, EpisodeState.ANALYZED}:
            raise IllegalTransition("Re-rendering after approval would invalidate it; revoke "
                                    "approval first.")
        require_at_least(ep, EpisodeState.ASSETS, "render")
        if not ws.narration_file.exists():
            raise FileNotFoundError("No narration yet. Run `studio voice <ep>` first.")
        if state == EpisodeState.REVIEW_PENDING:
            transition(session, ep, EpisodeState.ASSETS, note="re-render requested")
        board = load_storyboard(ws)
        track = read_model(ws.narration_file, NarrationTrack)
        manifest = load_manifest(ws, ep.id)
        pack = load_pack(ws)
        status = {c.id: c.status for c in pack.claims}
        badges: dict[str, list[str]] = {}
        for sc in board.scenes:
            b = []
            unv = [c for c in sc.claim_ids if status.get(c) != VerificationStatus.VERIFIED]
            if unv:
                b.append(f"UNVERIFIED: {', '.join(unv)}")
            if track.is_placeholder:
                b.append("PLACEHOLDER NARRATION (silent)")
            badges[sc.id] = b
        typer.echo(f"Rendering {'preview' if preview else 'master'} with {s.ffmpeg_binary()}")
        result = run_job(session, ep.id, "render_preview" if preview else "render_master",
                         sha256_file(ws.storyboard_file),
                         lambda: (r := render_episode(s, ws, ep.title, ch, board, track,
                                                      manifest, preview=preview,
                                                      scene_badges=badges), r.video))
        music = ws.audio / "music_bed.wav"
        manifest = load_manifest(ws, ep.id)
        if music.exists() and not manifest.get("music-track"):
            manifest.upsert(music_record(ws, music))
            save_manifest(ws, manifest)
        mode = "preview" if preview else "master"
        transition(session, ep, EpisodeState.RENDERED, note=f"render {mode}")
        BudgetGuard(session, s).record(provider="ffmpeg_local", operation="render",
                                       episode_id=ep.id)
        ok(f"Video: {result.video} ({result.duration_s / 60:.2f} min, {result.scenes} scenes, "
           f"{result.segments_reused} cached segments reused)")
        ok(f"Captions: {result.srt}")
        ok(f"Thumbnail draft: {result.thumbnail}")


@app.command()
@handled
def shorts(episode: str, count: int = 3,
           do_render: Annotated[bool, typer.Option("--render/--no-render")] = True,
           preview: Annotated[bool, typer.Option("--preview")] = False,
           provider: str = "",
           i_consent_to_spend: Annotated[bool, typer.Option("--i-consent-to-spend")] = False
           ) -> None:
    """Prepare up to N independent Shorts (1080x1920) with captions."""
    from studio.shorts import render_short, save_shorts, shorts_issues

    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        require_at_least(ep, EpisodeState.STORYBOARD, "prepare Shorts")
        if EpisodeState(ep.state) in {EpisodeState.APPROVED, EpisodeState.PRIVATE_UPLOADED,
                                      EpisodeState.PUBLISHED}:
            raise IllegalTransition("Shorts are locked after approval.")
        count = min(count, 3)
        pack = load_pack(ws)
        sc = load_script(ws)
        text_source, sample, _ = source_for(ws, s.samples_dir, ep.sample, "shorts.yaml")
        specs = text_source.shorts(ep.id, ep.title, pack, count, sample)
        if not specs:
            warn("No Shorts for this topic: write authoring/shorts.yaml (`studio author init`).")
            return
        issues = shorts_issues(specs, sc, pack, ch)
        save_shorts(ws, specs)
        for i in issues:
            warn(f"  {i}")
        if issues:
            raise ValueError("Shorts failed editorial checks; fix them before rendering.")
        ok(f"{len(specs)} Shorts scripted -> {ws.shorts_file}")
        if not do_render:
            return
        vp = make_voice(provider or s.default_voice_provider, ch, s)
        shorts_text = " ".join(x.narration for x in specs)
        shorts_est = vp.estimate_usd(shorts_text)
        guard = BudgetGuard(session, s)
        guard.preflight(provider=vp.name, operation="tts_shorts", estimate_usd=shorts_est,
                        paid=vp.paid, consent=i_consent_to_spend, episode_id=ep.id)
        if vp.paid:
            vp.arm(len(shorts_text))
        status = {c.id: c.status for c in pack.claims}
        for spec in specs:
            badges = []
            unv = [c for c in spec.claim_ids if status.get(c) != VerificationStatus.VERIFIED]
            if preview and unv:
                badges.append(f"UNVERIFIED: {', '.join(unv)}")
            if preview and vp.is_placeholder:
                badges.append("PLACEHOLDER NARRATION")
            res = render_short(s, ws, spec, ch, vp, preview=preview, badges=badges)
            ok(f"  {res.id}: {res.video} ({res.duration_s:.1f}s) + {res.srt.name}")
            for issue in res.legibility:
                warn(f"    legibility: {issue}")
        if vp.paid:
            sent = getattr(vp, "chars_sent", len(shorts_text))
            guard.record(provider=vp.name, operation="tts_shorts", usd=vp.estimate_usd(
                "x" * sent), units=sent, unit="chars", paid=True, episode_id=ep.id)


# ------------------------------------------------------------------ review / publish


@app.command()
@handled
def review(episode: str) -> None:
    """Assemble the review package and checklists; moves the episode to review_pending."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        if EpisodeState(ep.state) not in {EpisodeState.RENDERED, EpisodeState.REVIEW_PENDING}:
            raise IllegalTransition(f"Episode is '{ep.state}'; render it first.")
        transition(session, ep, EpisodeState.REVIEW_PENDING, note="review package built")
        report = build_report(s, session, ep, ws, ch)
        path = write_package(ws, report)
        from studio.shorts import load_shorts

        atomic_write_text(ws.review / "LICENSE_AUDIT.md", license_audit_markdown(
            ws, load_manifest(ws, ep.id), load_shorts(ws)))
        cfg = ch.narration.elevenlabs
        planned = (f"ElevenLabs {cfg.name or cfg.voice_id or '(voice not chosen yet)'} "
                   f"({cfg.model_id})")
        atomic_write_text(ws.review / "AI_DISCLOSURE_AUDIT.md", ai_disclosure_audit(
            ws, load_manifest(ws, ep.id), load_shorts(ws), planned))
        pset = load_proposals(ws)
        if pset:
            write_report(ws, load_pack(ws), pset, _used_claims(ws))
        from studio.publish import build_metadata

        meta = build_metadata(ep, ws, ch, None)
        atomic_write_text(ws.review / "description.txt", meta["description"] + "\n")
        atomic_write_text(ws.review / "upload_metadata.json",
                          json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
        pkg = write_release_candidate(ws, report, ep.title)
        for c in report.checklists:
            color = typer.colors.GREEN if c.passed else typer.colors.RED
            typer.secho(f"[{'PASS' if c.passed else 'BLOCKED'}] {c.name}", fg=color)
            for b in c.blockers[:12]:
                typer.echo(f"    blocker: {b}")
            if len(c.blockers) > 12:
                typer.echo(f"    ... {len(c.blockers) - 12} more in {path}")
            for w in c.warnings[:5]:
                typer.echo(f"    warning: {w}")
        typer.echo(f"Review checklist: {path}")
        typer.echo(f"Review package folder: {pkg} (see INDEX.md, BLOCKERS.md)")
        if report.blockers:
            warn(f"NOT approvable yet: {len(report.blockers)} blocker(s).")
        else:
            ok("No blockers. A human reviewer may now approve.")


@app.command()
@handled
def decide(episode: str, decision: Annotated[str, typer.Argument(
        help="approve | reject | needs_changes")],
           reviewer: Annotated[str, typer.Option()], note: str = "",
           ai_disclosure: Annotated[str | None, typer.Option(help="yes | no")] = None,
           back_to: Annotated[str | None, typer.Option(
               help="research | script | storyboard | assets")] = None) -> None:
    """Record the operator's review decision."""
    from studio.review import decide as do_decide

    s = settings()
    disclosure = None if ai_disclosure is None else ai_disclosure.lower() in {"yes", "y", "true"}
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        d = do_decide(s, session, ep, ws, ch, ReviewDecisionKind(decision), reviewer=reviewer,
                      note=note, ai_disclosure=disclosure,
                      back_to=EpisodeState(back_to) if back_to else None)
        ok(f"{d.decision.value} recorded by {d.reviewer}; episode now '{ep.state}'")


@app.command()
@handled
def publish(episode: str,
            private: Annotated[bool, typer.Option("--private/--not-private",
                                                  help="always private")] = True) -> None:
    """Upload as PRIVATE (needs OAuth + STUDIO_ENABLE_YOUTUBE=1) or export a release folder."""
    if not private:
        raise typer.BadParameter("Uploads are always private. Use `studio visibility` later.")
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        res = publish_private(s, session, ep, ws, ch)
        if res.mode == "youtube_private":
            ok(f"Uploaded PRIVATE: video id {res.remote_video_id}. Receipt: {res.path}")
        else:
            ok(f"YouTube upload not configured - release package exported: {res.path}")
            typer.echo("Upload it manually as Private, then run "
                       f"`studio record-upload {ep.id} <video-id>`.")


@app.command("record-upload")
@handled
def record_upload(episode: str, video_id: str) -> None:
    """Record a manual private upload done in YouTube Studio."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, _ = _load(session, s, episode)
        record_manual_upload(session, ep, ws, video_id)
        ok(f"{ep.id} -> private_uploaded ({video_id})")


@app.command()
@handled
def visibility(episode: str, status: Annotated[str, typer.Option(
        help="private | unlisted | public | scheduled")],
               confirm: Annotated[str, typer.Option(help="retype the full episode id")],
               publish_at: datetime | None = None) -> None:
    """Explicit operator action to change visibility of an uploaded video."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, _, _ = _load(session, s, episode)
        change_visibility(s, session, ep, visibility=status, confirm_episode_id=confirm,
                          publish_at=publish_at)
        ok(f"{ep.id}: visibility -> {status}")


# ------------------------------------------------------------------ analytics / cost


@app.command()
@handled
def analytics(channel: str | None = None, days: int = 30,
              import_csv: Annotated[Path | None, typer.Option(help="YouTube Studio CSV")] = None,
              mock: Annotated[bool, typer.Option(help="add synthetic test rows")] = False,
              api: Annotated[bool, typer.Option(
                  help="pull from the YouTube Analytics API (needs OAuth)")] = False
              ) -> None:
    """Import stats (CSV or mock) and print the channel comparison report."""
    from sqlmodel import select

    s = settings()
    with session_scope(s.db_path) as session:
        if import_csv:
            if not channel:
                raise ValueError("--channel is required with --import-csv")
            n = analytics_mod.import_csv(session, channel, import_csv, days)
            ok(f"Imported {n} rows from {import_csv}")
        if api:
            if not channel:
                raise ValueError("--channel is required with --api")
            if not (s.enable_youtube and s.youtube_client_secrets
                    and s.youtube_client_secrets.exists()):
                raise PublishBlocked("YouTube OAuth not connected (STUDIO_ENABLE_YOUTUBE=1 + "
                                     "YOUTUBE_CLIENT_SECRETS_FILE); use --import-csv instead")
            from studio.providers.youtube import GoogleAnalyticsClient

            client = GoogleAnalyticsClient(s.youtube_client_secrets, s.youtube_token_file)
            n = analytics_mod.import_api(session, channel, client, days)
            ok(f"Imported {n} rows from the YouTube Analytics API")
        if mock:
            channels = [channel] if channel else list(load_channels(s.channels_dir))
            for ch in channels:
                eps = session.exec(select(Episode).where(Episode.channel == ch)).all()
                analytics_mod.add_mock_stats(session, ch, eps, days)
            warn("Added MOCK analytics rows (synthetic, for pipeline testing only).")
        session.flush()
        rep = analytics_mod.channel_report(session, channel)
        md = analytics_mod.report_markdown(rep)
        out = s.projects_dir / "reports" / f"analytics_{datetime.now():%Y%m%d}.md"
        atomic_write_text(out, md)
        typer.echo(md)
        ok(f"Saved {out}")


@cost_app.command("report")
@handled
def cost_report_cmd() -> None:
    s = settings()
    with session_scope(s.db_path) as session:
        rep = cost_report(session, s)
        typer.echo(json.dumps(rep, indent=2))


@cost_app.command("preflight")
@handled
def cost_preflight(episode: str, voice_provider: str = "") -> None:
    """Estimate the cost of producing an episode with the configured providers."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        vp = make_voice(voice_provider or s.default_voice_provider, ch, s)
        text = " ".join(i.text for i in _scene_items(ws)) if ws.storyboard_file.exists() else ""
        lines = [("llm (mock)", 0.0), (f"voice ({vp.name})", vp.estimate_usd(text)),
                 ("visuals (local diagrams)", 0.0), ("render (local ffmpeg)", 0.0)]
        guard = BudgetGuard(session, s)
        total = sum(v for _, v in lines)
        for name, v in lines:
            typer.echo(f"  {name:28} ${v:8.2f}")
        typer.echo(f"  {'TOTAL':28} ${total:8.2f}")
        typer.echo(f"  month spent ${guard.month_spent():.2f} / cap ${s.monthly_budget_usd:.2f}")


@cost_app.command("tts")
@handled
def cost_tts(episode: str, voice_provider: str = "elevenlabs",
             retakes: Annotated[float, typer.Option(
                 help="buffer for re-takes, e.g. 0.2 = 20%")] = 0.0,
             with_proposed_changes: Annotated[bool, typer.Option(
                 help="count the text as it would be after the proposed narration changes")]
             = False) -> None:
    """Exact TTS size from the real text (per-sentence requests): characters, credits, USD.
    Sends nothing."""
    from studio.providers.voice import ELEVENLABS_PLAN_UI_CREDITS, ELEVENLABS_PLAN_USD
    from studio.shorts import load_shorts
    from studio.storyboard import split_sentences

    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        vp = make_voice(voice_provider, ch, s)
        scene_texts = [i.text for i in _scene_items(ws)]
        if with_proposed_changes:
            pset = load_proposals(ws)
            for p in (pset.proposals if pset else []):
                c = p.narration_change
                if c:
                    scene_texts = [t.replace(c["current"], c["proposed"]) for t in scene_texts]
        groups = [("long video", scene_texts)]
        groups += [(sp.id, [sp.narration]) for sp in load_shorts(ws)]
        credits_of = getattr(vp, "estimate_credits", lambda n: float(n))
        typer.echo(f"provider={vp.name} model={getattr(vp, 'model_id', '-')} "
                   f"voice={vp.voice or '(not chosen)'} "
                   f"stitching={getattr(vp, 'stitching', '-')}"
                   + (" [text after proposed changes]" if with_proposed_changes else ""))
        typer.echo(f"  {'item':20} {'requests':>8} {'chars':>7} {'credits':>8} {'USD@PAYG':>9}")
        tot_c = tot_cr = tot_usd = 0.0
        tot_req = 0
        for name, texts in groups:
            sents = [x for t in texts for x in split_sentences(t)]
            chars = sum(len(x) for x in sents) * (1 + retakes)
            cr = credits_of(chars)
            usd = vp.estimate_usd("x" * round(chars))
            tot_c, tot_cr, tot_usd, tot_req = (tot_c + chars, tot_cr + cr, tot_usd + usd,
                                               tot_req + len(sents))
            typer.echo(f"  {name:20} {len(sents):8d} {chars:7.0f} {cr:8.0f} {usd:9.2f}")
        typer.echo(f"  {'TOTAL':20} {tot_req:8d} {tot_c:7.0f} {tot_cr:8.0f} {tot_usd:9.2f}")
        plan = (s.elevenlabs_plan or "starter").lower()
        if plan in ELEVENLABS_PLAN_USD and getattr(vp, "usd_per_1k_chars", 0):
            allowance = ELEVENLABS_PLAN_USD[plan] / vp.usd_per_1k_chars * 1000
            typer.echo(f"  {plan}: ${ELEVENLABS_PLAN_USD[plan]:.0f}/month includes "
                       f"~{allowance:,.0f} API chars on this model -> {tot_c / allowance:.0%} "
                       f"of one month; UI credits {ELEVENLABS_PLAN_UI_CREDITS[plan]:,} "
                       "(web app only)")


def _voice_candidates(s: Settings, channel: str) -> tuple[Path, dict]:
    import yaml

    path = s.channels_dir / "voices" / f"{channel}.elevenlabs.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No voice candidates file {path}")
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


@voices_app.command("list")
@handled
def voices_list(channel: str = "engineering_explained") -> None:
    """Show candidate voices and their settings (offline)."""
    s = settings()
    path, data = _voice_candidates(s, channel)
    ch = get_channel(s.channels_dir, channel)
    chosen = s.elevenlabs_voice_id or ch.narration.elevenlabs.voice_id
    typer.echo(f"{path}  (model {data.get('model_id')})")
    for c in data["candidates"]:
        mark = "*" if c["voice_id"] == chosen else " "
        st = c["settings"]
        typer.echo(f" {mark} {c['key']:7} {c['voice_id']}  {c['name']}")
        typer.echo(f"           style: {c['intended_style']}")
        typer.echo(f"           stability={st['stability']} similarity={st['similarity_boost']} "
                   f"style={st['style']} speaker_boost={st['use_speaker_boost']} "
                   f"speed={st['speed']}")


@voices_app.command("check")
@handled
def voices_check(channel: str = "engineering_explained") -> None:
    """Read each candidate's labels from the API (free GET; generates no audio)."""
    s = settings()
    _, data = _voice_candidates(s, channel)
    vp = make_voice("elevenlabs", get_channel(s.channels_dir, channel), s)
    for c in data["candidates"]:
        info = vp.get_voice(c["voice_id"])
        labels = ", ".join(f"{k}={v}" for k, v in sorted(info["labels"].items()))
        typer.echo(f"{c['key']:7} {info['name']} [{info['category']}] {labels}")
        typer.echo(f"        preview: {info['preview_url'] or '-'}")
        if info.get("disable_at_unix"):
            warn(f"        voice scheduled for removal at unix {info['disable_at_unix']}")


@voices_app.command("use")
@handled
def voices_use(key: str, channel: str = "engineering_explained") -> None:
    """Write the chosen candidate (voice_id + settings) into the channel profile."""
    import yaml

    s = settings()
    _, data = _voice_candidates(s, channel)
    cand = next((c for c in data["candidates"] if c["key"] == key), None)
    if cand is None:
        raise KeyError(f"No candidate '{key}'")
    path = s.channels_dir / f"{channel}.yaml"
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    block = {"voice_id": cand["voice_id"], "name": cand["name"],
             "model_id": data.get("model_id", "eleven_multilingual_v2"), **cand["settings"]}
    start = text.index("  elevenlabs:\n")
    end = start + len("  elevenlabs:\n")
    lines = text[end:].splitlines(keepends=True)
    n = 0
    while n < len(lines) and lines[n].startswith("    "):
        n += 1
    new_block = "".join(f"    {k}: {json.dumps(v)}\n" for k, v in block.items())
    path.write_text(text[:end] + new_block + "".join(lines[n:]), encoding="utf-8")
    doc2 = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc2["narration"]["elevenlabs"]["voice_id"] == cand["voice_id"]
    assert {k: v for k, v in doc2.items() if k != "narration"} == {
        k: v for k, v in doc.items() if k != "narration"}
    ok(f"{channel}: ElevenLabs voice set to {cand['name']} ({cand['voice_id']})")


@diagrams_app.command("list")
@handled
def diagrams_list() -> None:
    """All diagrams: hand-coded ones and YAML templates in diagram_specs/."""
    from studio.diagrams import DIAGRAMS, get_diagram, spec_ids, specs_dir

    typer.echo("code:")
    for k, d in DIAGRAMS.items():
        typer.echo(f"  {k:28} {d.title}")
    typer.echo(f"templates ({specs_dir()}):")
    for k in spec_ids():
        try:
            d = get_diagram(k)
            typer.echo(f"  {k:28} {d.spec.type:13} {d.title}")  # type: ignore[attr-defined]
        except ValueError as exc:
            typer.secho(f"  {k:28} INVALID: {exc}", fg=typer.colors.RED)


@diagrams_app.command("check")
@handled
def diagrams_check(channel: str = "engineering_explained") -> None:
    """Validate every template and run layout QA (overlaps, off-canvas, caption band)."""
    from studio.diagrams import DIAGRAMS, get_diagram, layout_issues, spec_ids

    s = settings()
    theme = Theme.from_identity(get_channel(s.channels_dir, channel).visual)
    bad = 0
    for ref in [*DIAGRAMS, *spec_ids()]:
        try:
            issues = layout_issues(get_diagram(ref).build(theme))
        except ValueError as exc:
            issues = [str(exc)]
        if issues:
            bad += 1
            typer.secho(f"{ref}:", fg=typer.colors.YELLOW)
            for i in issues:
                typer.echo(f"   {i}")
    if bad:
        raise typer.Exit(2)
    ok("All diagrams pass validation and layout QA.")


@diagrams_app.command("preview")
@handled
def diagrams_preview(ref: str, channel: str = "engineering_explained",
                     out: Path = Path("diagram_previews"),
                     video: Annotated[float, typer.Option(
                         help="also render an animated MP4 of N seconds (0 = off)")] = 0.0
                     ) -> None:
    """Render a step-by-step contact sheet (PNG) and optionally a short motion preview."""
    from PIL import Image

    from studio.diagrams import get_diagram, layout_issues
    from studio.motion import SceneRenderer, frames_to_mp4, plan_scene

    s = settings()
    theme = Theme.from_identity(get_channel(s.channels_dir, channel).visual)
    canvas = get_diagram(ref).build(theme)
    n = canvas.max_step + 1
    tiles = [canvas.to_image(k, (960, 540), supersample=1) for k in range(n)]
    sheet = Image.new("RGB", (960 * min(2, n), 540 * ((n + 1) // 2)), "white")
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 2) * 960, (i // 2) * 540))
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"{ref}.png"
    sheet.save(png)
    ok(f"{n} steps -> {png}")
    for issue in layout_issues(canvas):
        warn(f"  layout: {issue}")
    if video > 0:
        plan = plan_scene(canvas, list(range(n)), video,
                          camera=get_diagram(ref).default_camera)
        rend = SceneRenderer(canvas, plan, (1280, 720), layer_scale=1.5)
        fps = 30
        frames = (rend.frame(i / fps) for i in range(round(video * fps)))
        mp4 = out / f"{ref}.mp4"
        frames_to_mp4(s.ffmpeg_binary(), frames, round(video * fps), (1280, 720), fps, mp4,
                      preset="veryfast", crf=24)
        ok(f"motion preview -> {mp4}")


@author_app.command("init")
@handled
def author_init(episode: str, overwrite: bool = False) -> None:
    """Create authoring/ skeletons (research, script, Shorts) from the channel structure."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        for path in init_files(ws, ch, ep.title, ep.topic, overwrite=overwrite):
            ok(f"wrote {path}")
        typer.echo("Edit the files, then `studio author check` until clean.")


@author_app.command("check")
@handled
def author_check_cmd(episode: str) -> None:
    """Validate the hand-written files without changing the episode state."""
    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        problems = author_check(ws, ch, ep.target_minutes)
        for p_ in problems:
            typer.echo(f"  - {p_}")
        if problems:
            raise typer.Exit(2)
        ok("Authoring files pass all checks.")


@app.command()
@handled
def thumbnail(episode: str,
              hook: Annotated[str, typer.Option(help="2-5 punchy words for variants B/C")] = "",
              diagram: Annotated[str, typer.Option(help="diagram id for the artwork")] = ""
              ) -> None:
    """Render three thumbnail variants (classic / big hook / split) for an A/B choice."""
    from studio.thumbnails import readability_issues, render_variants

    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        board = load_storyboard(ws)
        ref = diagram or next((sc.visual.ref for sc in board.scenes
                               if sc.visual.kind == "diagram"
                               and "cross_section" in sc.visual.ref), None) or next(
            (sc.visual.ref for sc in board.scenes if sc.visual.kind == "diagram"), "")
        if not ref:
            raise ValueError("No diagram in the storyboard; pass --diagram <id>")
        variants = render_variants(ws.render / "thumbnails", title=ep.title,
                                   hook=hook or ep.title, channel=ch, diagram=ref)
        for v in variants:
            ok(f"{v.key}: {v.path} ({v.size_bytes / 1e3:.0f} KB, text "
               f"{v.min_text_px_at_mobile:.0f}px on a phone)")
        for issue in readability_issues(variants):
            warn(f"  {issue}")
        typer.echo("Pick one and copy it to render/thumbnail_draft.png (or keep the default).")


def _drafter(s: Settings):
    from studio.providers.anthropic_llm import AnthropicDraftProvider

    return AnthropicDraftProvider(model=s.llm_model, effort=s.llm_effort)


def _run_draft(session, s: Settings, ep_id: str, operation: str, prompt_chars: int,
               dry_run: bool, consent: bool, call):
    """Shared guard for every paid Claude call: estimate -> preflight -> arm -> call -> ledger."""
    drafter = _drafter(s)
    est = drafter.estimate_usd(prompt_chars)
    guard = BudgetGuard(session, s)
    typer.echo(f"{operation}: model={drafter.model} effort={drafter.effort} prompt "
               f"~{prompt_chars:,} chars; worst-case estimate ${est:.2f}")
    if dry_run:
        try:
            guard.preflight(provider="anthropic", operation=operation, estimate_usd=est,
                            paid=True, consent=True, episode_id=ep_id)
            ok("Dry run: preflight would pass (nothing sent, nothing spent).")
        except BudgetError as exc:
            warn(f"Dry run: preflight would FAIL: {exc}")
        session.rollback()
        return None
    guard.preflight(provider="anthropic", operation=operation, estimate_usd=est, paid=True,
                    consent=consent, episode_id=ep_id)
    drafter.arm(est)
    try:
        result = call(drafter)
    finally:
        if drafter.spent_usd:
            guard.record(provider="anthropic", operation=operation, usd=drafter.spent_usd,
                          paid=True, episode_id=ep_id)
    ok(f"Claude ({result.served_by}) cost ${result.usage.usd():.4f} "
       f"[in {result.usage.input_tokens} / out {result.usage.output_tokens} tokens]")
    return result


def _diagram_ids() -> list[str]:
    from studio.diagrams import DIAGRAMS, spec_ids

    return sorted(DIAGRAMS) + spec_ids()


@draft_app.command("script")
@handled
def draft_script(episode: str,
                 dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
                 i_consent_to_spend: Annotated[bool, typer.Option("--i-consent-to-spend")]
                 = False) -> None:
    """Draft a script from the research claims -> authoring/script.draft.yaml."""
    import yaml

    from studio.authoring import author_dir

    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        pack = load_pack(ws)
        diagrams = _diagram_ids()
        system, user = _drafter(s).build_script_prompt(ch, pack, ep.title, ep.target_minutes,
                                                       diagrams)
        res = _run_draft(session, s, ep.id, "draft_script", len(system) + len(user), dry_run,
                         i_consent_to_spend,
                         lambda d: d.draft_script(ch, pack, ep.title, ep.target_minutes,
                                                  diagrams))
        if res is None:
            return
        out = author_dir(ws) / "script.draft.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out, "# DRAFT by Claude - review every sentence, then rename to "
                          "script.yaml\n" + yaml.safe_dump(res.data, sort_keys=False,
                                                           allow_unicode=True, width=92))
        ok(f"Draft -> {out}  (not used until you rename it)")


@draft_app.command("shorts")
@handled
def draft_shorts(episode: str, count: int = 3,
                 dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
                 i_consent_to_spend: Annotated[bool, typer.Option("--i-consent-to-spend")]
                 = False) -> None:
    """Draft up to 3 independent Shorts -> authoring/shorts.draft.yaml."""
    import yaml

    from studio.authoring import author_dir

    s = settings()
    with session_scope(s.db_path) as session:
        ep, ws, ch = _load(session, s, episode)
        pack = load_pack(ws)
        text = load_script(ws).narration_text
        diagrams = _diagram_ids()
        chars = len(text) + sum(len(c.text) for c in pack.claims) + 3000
        res = _run_draft(session, s, ep.id, "draft_shorts", chars, dry_run, i_consent_to_spend,
                         lambda d: d.draft_shorts(ch, pack, ep.title, text, diagrams,
                                                  min(count, 3)))
        if res is None:
            return
        for sh in res.data.get("shorts", []):
            sh["link_text"] = f"Full episode: {ep.title}"
        out = author_dir(ws) / "shorts.draft.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out, "# DRAFT by Claude - review, then rename to shorts.yaml\n"
                          + yaml.safe_dump(res.data, sort_keys=False, allow_unicode=True,
                                           width=92))
        ok(f"Draft -> {out}")


@draft_app.command("ideas")
@handled
def draft_ideas(channel: str, count: int = 10,
                dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
                i_consent_to_spend: Annotated[bool, typer.Option("--i-consent-to-spend")]
                = False) -> None:
    """Propose episode ideas with research questions (no facts) -> ideas_<channel>.draft.yaml."""
    import yaml
    from sqlmodel import select

    s = settings()
    ch = get_channel(s.channels_dir, channel)
    with session_scope(s.db_path) as session:
        existing = [e.title for e in session.exec(select(Episode).where(
            Episode.channel == channel)).all()]
        res = _run_draft(session, s, "", "draft_ideas", 3000, dry_run, i_consent_to_spend,
                         lambda d: d.propose_ideas(ch, count, existing))
        if res is None:
            return
        out = s.projects_dir / f"ideas_{channel}.draft.yaml"
        atomic_write_text(out, yaml.safe_dump(res.data, sort_keys=False, allow_unicode=True,
                                              width=92))
        ok(f"Ideas -> {out}")


@connect_app.command("status")
@handled
def connect_status() -> None:
    """What is connected, what is missing, and the next command - no secrets printed."""
    from studio.connect import status, status_markdown

    s = settings()
    with session_scope(s.db_path) as session:
        spent = BudgetGuard(session, s).month_spent()
    typer.echo(status_markdown(status(s), spent, s.monthly_budget_usd))


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
