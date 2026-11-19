"""Assisted fact-checking: proposals produced by a (human or automated) checker.

A proposal records, for one claim: the source page actually read, a verbatim snippet, a
verdict and a suggested rewording. Proposals NEVER change a claim's status by themselves.
`apply_proposal` is the operator's explicit act: it requires a named human and, for a
partially supported claim, acceptance of the reworded text (the original wording is not
what the source says).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from studio.episodes import Workspace
from studio.fsutil import atomic_write_json, atomic_write_text
from studio.models import ResearchPack, VerificationStatus
from studio.research import ResearchError, add_source, verify_claim

VERDICTS = ("supported", "partially_supported", "not_supported", "not_checked")


class ClaimProposal(BaseModel):
    claim_id: str
    claim_text: str
    verdict: str
    source_url: str = ""
    source_title: str = ""
    accessed: str = ""
    snippet: str = ""
    snippet_location: str = ""  # e.g. "PDF full text, section 1.1" when not on the HTML page
    proposed_text: str = ""
    notes: str = ""
    other_urls_checked: list[str] = []
    checked_by: str = "assistant (automated fetch; not a human verification)"
    recheck: str = ""  # independent re-fetch result: MATCH / NO-MATCH / ...
    source_publisher: str = ""
    extra_evidence: list[dict] = []  # further verbatim quotes: {url, title, location, snippet}
    narration_change: dict = {}  # {scene, current, proposed} - applied only after confirmation
    replaces_source: str = ""  # e.g. the Wikipedia URL this primary source supersedes


class ProposalSet(BaseModel):
    episode_id: str
    created_at: datetime
    method: str
    proposals: list[ClaimProposal]

    def get(self, claim_id: str) -> ClaimProposal:
        for p in self.proposals:
            if p.claim_id == claim_id:
                return p
        raise KeyError(f"No proposal for claim {claim_id}")


def proposals_file(ws: Workspace) -> Path:
    return ws.research / "verification_proposals.json"


def load_proposals(ws: Workspace) -> ProposalSet | None:
    f = proposals_file(ws)
    if not f.exists():
        return None
    return ProposalSet.model_validate_json(f.read_text(encoding="utf-8"))


def import_proposals(ws: Workspace, pack: ResearchPack, src: Path) -> ProposalSet:
    data = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"episode_id": pack.episode_id, "created_at": datetime.now(UTC).isoformat(),
                "method": "imported list", "proposals": data}
    data["episode_id"] = pack.episode_id
    pset = ProposalSet.model_validate(data)
    known = {c.id for c in pack.claims}
    problems = []
    for p in pset.proposals:
        if p.claim_id not in known:
            problems.append(f"{p.claim_id}: unknown claim")
        if p.verdict not in VERDICTS:
            problems.append(f"{p.claim_id}: verdict must be one of {VERDICTS}")
        if p.verdict in {"supported", "partially_supported"} and not p.snippet.strip():
            problems.append(f"{p.claim_id}: '{p.verdict}' without a verbatim snippet")
    if problems:
        raise ResearchError("Invalid proposals:\n- " + "\n- ".join(problems))
    atomic_write_json(proposals_file(ws), pset)
    return pset


def apply_proposal(pack: ResearchPack, proposal: ClaimProposal, *, by: str,
                   accept_rewording: bool) -> str:
    """Operator-confirmed verification from a proposal. Returns the final claim text."""
    if not by.strip():
        raise ResearchError("A named human reviewer (--by) is required")
    if proposal.verdict not in {"supported", "partially_supported"}:
        raise ResearchError(f"{proposal.claim_id}: verdict is {proposal.verdict}; "
                            "it cannot be verified from this proposal")
    if not proposal.snippet.strip():
        raise ResearchError(f"{proposal.claim_id}: no verbatim snippet in the proposal")
    claim = pack.claim(proposal.claim_id)
    rewrite = proposal.proposed_text.strip() and proposal.proposed_text.strip() != claim.text
    if proposal.verdict == "partially_supported" and not accept_rewording:
        raise ResearchError(
            f"{proposal.claim_id} is only partially supported: the original wording is not "
            "what the source says. Re-run with --accept-rewording (and make the narration "
            "match) or verify manually with a different source.")
    src = next((s for s in pack.sources if s.url == proposal.source_url), None)
    if src is None:
        src = add_source(pack, url=proposal.source_url,
                         title=proposal.source_title or proposal.source_url,
                         notes=f"added from verification proposal for {proposal.claim_id}")
    if src.id not in claim.source_ids:
        claim.source_ids = [src.id, *claim.source_ids]
    note = f"verified from proposal ({proposal.checked_by}); source {src.id}"
    if rewrite and accept_rewording:
        note += f"; reworded from: {claim.text!r}"
        claim.text = proposal.proposed_text.strip()
    if proposal.snippet_location:
        note += f"; snippet location: {proposal.snippet_location}"
    verify_claim(pack, claim.id, snippet=proposal.snippet, verified_by=by, notes=note)
    return claim.text


def report_markdown(pack: ResearchPack, pset: ProposalSet, used: set[str]) -> str:
    counts = {v: sum(p.verdict == v for p in pset.proposals) for v in VERDICTS}
    lines = [
        f"# Source verification report - {pack.topic}",
        "",
        f"Episode `{pack.episode_id}` - proposals created {pset.created_at:%Y-%m-%d} - "
        f"method: {pset.method}",
        "",
        "> These are **proposals**, not verification. Each claim stays blocking until a named "
        "human opens the URL, confirms the snippet and runs "
        "`studio claim apply-proposal <episode> <claim> --by \"Name\"` "
        "(plus `--accept-rewording` for partially supported claims).",
        "",
        "| verdict | count |",
        "|---|---|",
        *[f"| {v} | {n} |" for v, n in counts.items()],
        "",
        "| id | in script | verdict | human status | source |",
        "|---|---|---|---|---|",
    ]
    for p in pset.proposals:
        claim = pack.claim(p.claim_id)
        lines.append(f"| {p.claim_id} | {'yes' if p.claim_id in used else 'no'} | "
                     f"**{p.verdict}** | {claim.status.value} | {p.source_url} |")
    lines.append("")
    for p in pset.proposals:
        claim = pack.claim(p.claim_id)
        status = claim.status.value
        if claim.status == VerificationStatus.VERIFIED:
            status += f" by {claim.verified_by}"
        lines += [
            f"## {p.claim_id} - {p.verdict}",
            "",
            f"- **Claim (as in pack):** {claim.text}",
            f"- **Source:** [{p.source_title or p.source_url}]({p.source_url}) "
            f"(accessed {p.accessed})",
        ]
        if p.snippet_location:
            lines.append(f"- **Snippet location:** {p.snippet_location}")
        lines += [
            f"- **Exact supporting fragment:** {'> ' + p.snippet if p.snippet else '_none found_'}",
            f"- **Verdict:** {p.verdict}",
            f"- **Proposed wording:** {p.proposed_text or '_n/a_'}",
            f"- **Notes:** {p.notes or '-'}",
            f"- **Independent re-fetch:** {p.recheck or 'not run'}",
            f"- **Human status:** {status}",
        ]
        if p.other_urls_checked:
            lines.append("- **Other pages checked:** " + ", ".join(p.other_urls_checked))
        lines.append("")
    return "\n".join(lines)


def write_report(ws: Workspace, pack: ResearchPack, pset: ProposalSet, used: set[str]) -> Path:
    out = ws.research / "VERIFICATION_REPORT.md"
    atomic_write_text(out, report_markdown(pack, pset, used))
    return out


# --------------------------------------------------------------------------- confirmation


SHORT_PUBLISHER = (("Congressional Research", "CRS"), ("ICPC Ltd / UNEP", "ICPC/UNEP 2009"),
                   ("International Cable Protection", "ICPC"), ("ITU", "ITU/ICPC IAB 2026"),
                   ("IEEE History", "IEEE ETHW"), ("ETHW", "IEEE ETHW"),
                   ("European Space", "ESA"), ("ACM Internet", "ACM IMC 2022"),
                   ("Ericsson", "Ericsson (arXiv)"), ("arXiv", "arXiv preprint"),
                   ("RP Photonics", "RP Photonics"), ("The Fiber Optic", "FOA"),
                   ("The Oceanography", "Carter et al. 2014"), ("TeleGeography", "TeleGeography"))


def _short(publisher: str, title: str) -> str:
    for key, short in SHORT_PUBLISHER:
        if publisher.startswith(key) or (not publisher and title.startswith(key)):
            return short
    return (publisher or title)[:24]


def confirmation_table(pack: ResearchPack, pset: ProposalSet, used: set[str]) -> str:
    """Compact one-row-per-claim table for the operator's final decision."""
    lines = [
        f"# Fact confirmation - {pack.topic}",
        "",
        "Nothing is applied automatically. Per row: open the source, read the quote, then",
        "`studio claim apply-proposal ee-0001 <ID> --by NAME --accept-rewording` (stores the",
        "proposed wording + source), then `studio script-change ee-0001 <ID> --by NAME` where",
        "Narr. names a scene.",
        "Reject with `studio claim set-status ee-0001 <ID> --status rejected --by NAME`.",
        "V: S = supported as proposed; P = the original wording overstated the source.",
        "",
        "| ID | V | Proposed wording | Source | Quote (start) | Narr. |",
        "|---|---|---|---|---|---|",
    ]
    for p in pset.proposals:
        claim = pack.claim(p.claim_id)
        v = {"supported": "S", "partially_supported": "P"}.get(p.verdict, p.verdict)
        if claim.status == VerificationStatus.VERIFIED:
            v += " ✓"
        quote = p.snippet.replace("|", "/").replace("\n", " ")
        quote = quote[:80] + ("…" if len(quote) > 80 else "")
        src = f"[{_short(p.source_publisher, p.source_title)}]({p.source_url})"
        narr = p.narration_change.get("scene", "") if p.narration_change else ""
        cid = p.claim_id + ("" if p.claim_id in used else " (unused)")
        lines.append(f"| {cid} | {v} | {p.proposed_text.replace('|', '/')} | {src} "
                     f"| “{quote}” | {narr} |")
    changes = [p for p in pset.proposals if p.narration_change]
    if changes:
        lines += ["", "## Narration changes", ""]
        for p in changes:
            c = p.narration_change
            lines += [f"**{p.claim_id} - {c['scene']}**", "",
                      f"- now: {c['current']}", f"- new: {c['proposed']}", ""]
    return "\n".join(lines) + "\n"


def apply_narration_change(script, change: dict) -> str:
    """Replace one exact sentence in the script. Returns the paragraph id-ish location."""
    hits = [(s, p) for s in script.sections for p in s.paragraphs if change["current"] in p.text]
    if len(hits) != 1:
        raise ResearchError(
            f"expected exactly one paragraph containing {change['current'][:60]!r}, "
            f"found {len(hits)} (was the script already changed?)")
    section, para = hits[0]
    para.text = para.text.replace(change["current"], change["proposed"])
    return section.id
