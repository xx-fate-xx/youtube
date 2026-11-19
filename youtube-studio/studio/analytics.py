"""Analytics: CSV import (YouTube Studio export), clearly-labelled mock data, comparison report."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from sqlmodel import Session, select

from studio.models import CostEntry, Episode, EpisodeState, VideoStats
from studio.state import transition

# Accept several header spellings from YouTube Studio exports.
COLUMN_ALIASES: dict[str, list[str]] = {
    "remote_video_id": ["content", "video id", "video_id"],
    "title": ["video title", "title"],
    "views": ["views"],
    "impressions": ["impressions"],
    "ctr_pct": ["impressions click-through rate (%)", "ctr", "ctr (%)"],
    "avg_view_duration_s": ["average view duration", "avg view duration"],
    "avg_pct_viewed": ["average percentage viewed (%)", "average percentage viewed"],
    "subscribers_gained": ["subscribers gained", "subscribers"],
}


def _num(value: str) -> float | None:
    value = (value or "").strip().replace(",", "").replace("%", "")
    if not value:
        return None
    if re.fullmatch(r"\d+:\d{2}(:\d{2})?", value):  # h:mm:ss or m:ss
        parts = [int(p) for p in value.split(":")]
        secs = 0
        for p in parts:
            secs = secs * 60 + p
        return float(secs)
    try:
        return float(value)
    except ValueError:
        return None


def import_csv(session: Session, channel: str, path: Path, days: int = 30) -> int:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = {h.strip().lower(): h for h in reader.fieldnames or []}
        mapping = {field: next((header[a] for a in aliases if a in header), None)
                   for field, aliases in COLUMN_ALIASES.items()}
        if not mapping["views"]:
            raise ValueError(f"CSV has no Views column. Columns: {list(header)}")
        n = 0
        for row in reader:
            if (row.get(mapping["remote_video_id"] or "", "") or "").lower() == "total":
                continue
            def get(field: str, row: dict = row):
                col = mapping[field]
                return _num(row.get(col, "")) if col else None
            vid = row.get(mapping["remote_video_id"], "").strip() if mapping[
                "remote_video_id"] else None
            ep = session.exec(select(Episode).where(Episode.remote_video_id == vid)).first() \
                if vid else None
            session.add(VideoStats(
                channel=channel, episode_id=ep.id if ep else None, remote_video_id=vid,
                title=row.get(mapping["title"], "") if mapping["title"] else "",
                days=days, views=int(get("views") or 0),
                impressions=int(v) if (v := get("impressions")) is not None else None,
                ctr_pct=get("ctr_pct"), avg_view_duration_s=get("avg_view_duration_s"),
                avg_pct_viewed=get("avg_pct_viewed"),
                subscribers_gained=int(v) if (v := get("subscribers_gained")) is not None
                else None,
                production_cost_usd=_episode_cost(session, ep.id) if ep else None,
                source="csv",
            ))
            if ep and ep.state == EpisodeState.PUBLISHED.value:
                transition(session, ep, EpisodeState.ANALYZED, note="csv analytics imported")
            n += 1
    return n


def _episode_cost(session: Session, episode_id: str) -> float:
    rows = session.exec(select(CostEntry).where(CostEntry.episode_id == episode_id,
                                                CostEntry.kind == "actual")).all()
    return round(sum(r.usd for r in rows), 4)


def add_mock_stats(session: Session, channel: str, episodes: list[Episode], days: int) -> int:
    """Deterministic fake numbers for pipeline testing. Always stored with source='mock'."""
    for ep in episodes:
        h = int(hashlib.sha256(ep.id.encode()).hexdigest(), 16)
        impressions = 2000 + h % 18000
        ctr = 2.0 + (h >> 8) % 60 / 10
        views = int(impressions * ctr / 100)
        session.add(VideoStats(
            channel=channel, episode_id=ep.id, remote_video_id=ep.remote_video_id,
            title=f"[MOCK] {ep.title}", days=days, views=views, impressions=impressions,
            ctr_pct=round(ctr, 1), avg_view_duration_s=float(120 + (h >> 16) % 300),
            avg_pct_viewed=float(25 + (h >> 24) % 30), subscribers_gained=(h >> 32) % 40,
            traffic_sources_json=json.dumps({"browse": 0.4, "search": 0.35, "suggested": 0.25}),
            production_cost_usd=_episode_cost(session, ep.id), source="mock",
        ))
    return len(episodes)


def channel_report(session: Session, channel: str | None = None) -> dict:
    stmt = select(VideoStats)
    if channel:
        stmt = stmt.where(VideoStats.channel == channel)
    rows = session.exec(stmt).all()
    report: dict[str, dict] = {}
    for r in rows:
        c = report.setdefault(r.channel, {"videos": 0, "views": 0, "impressions": 0,
                                          "subscribers_gained": 0, "cost_usd": 0.0,
                                          "_ctr": [], "_avd": [], "sources": set()})
        c["videos"] += 1
        c["views"] += r.views
        c["impressions"] += r.impressions or 0
        c["subscribers_gained"] += r.subscribers_gained or 0
        c["cost_usd"] += r.production_cost_usd or 0.0
        if r.ctr_pct is not None:
            c["_ctr"].append(r.ctr_pct)
        if r.avg_view_duration_s is not None:
            c["_avd"].append(r.avg_view_duration_s)
        c["sources"].add(r.source)
    for c in report.values():
        ctr, avd = c.pop("_ctr"), c.pop("_avd")
        c["avg_ctr_pct"] = round(sum(ctr) / len(ctr), 2) if ctr else None
        c["avg_view_duration_s"] = round(sum(avd) / len(avd), 1) if avd else None
        c["cost_per_1k_views_usd"] = (round(c["cost_usd"] / c["views"] * 1000, 2)
                                      if c["views"] else None)
        c["sources"] = sorted(c["sources"])
    return report


def report_markdown(report: dict) -> str:
    lines = ["# Channel comparison", "",
             "| channel | videos | views | impressions | avg CTR % | avg view dur s | subs + | "
             "cost $ | $/1k views | data |", "|---|---|---|---|---|---|---|---|---|---|"]
    for ch, c in sorted(report.items()):
        lines.append(f"| {ch} | {c['videos']} | {c['views']} | {c['impressions']} | "
                     f"{c['avg_ctr_pct']} | {c['avg_view_duration_s']} | "
                     f"{c['subscribers_gained']} | {c['cost_usd']:.2f} | "
                     f"{c['cost_per_1k_views_usd']} | {', '.join(c['sources'])} |")
    if any("mock" in c["sources"] for c in report.values()):
        lines += ["", "> Rows from `mock` are synthetic test data, not real performance."]
    return "\n".join(lines) + "\n"
