"""The `private` upload safety guard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from studio.db import session_scope
from studio.episodes import get_episode
from studio.fsutil import atomic_write_json, sha256_file
from studio.models import EpisodeState as S
from studio.models import ReviewDecision, ReviewDecisionKind
from studio.providers.llm import MockLLMProvider
from studio.providers.youtube import UnsafeVisibilityError, YouTubePublisher
from studio.publish import PublishBlocked, change_visibility, publish_private
from studio.research import save_pack
from studio.state import transition


class FakeClient:
    def __init__(self, echo: str = "private"):
        self.echo = echo
        self.inserted: list[dict[str, Any]] = []
        self.updates: list[tuple[str, dict]] = []
        self.captions: list[tuple[str, str, str]] = []
        self._n = 0

    def insert_video(self, video_path: Path, body: dict, thumbnail: Path | None) -> dict:
        self.inserted.append(body)
        self._n += 1
        vid = "VID123" if self._n == 1 else f"SHORT{self._n - 1}"
        return {"id": vid, "status": {"privacyStatus": self.echo}}

    def update_status(self, video_id: str, status: dict) -> dict:
        self.updates.append((video_id, status))
        return {"id": video_id, "status": status}

    def insert_caption(self, video_id: str, srt: Path, language: str, name: str) -> dict:
        self.captions.append((video_id, srt.name, language))
        return {"id": f"CAP-{video_id}"}


def test_upload_has_no_visibility_parameter_and_is_private(tmp_path):
    client = FakeClient()
    YouTubePublisher(client).upload(tmp_path / "v.mp4", title="t", description="d", tags=[])
    assert client.inserted[0]["status"]["privacyStatus"] == "private"
    with pytest.raises(TypeError):
        YouTubePublisher(client).upload(tmp_path / "v.mp4", title="t", description="d",
                                        tags=[], privacy="public")  # type: ignore[call-arg]


def test_upload_fails_loudly_if_api_echoes_non_private(tmp_path):
    with pytest.raises(UnsafeVisibilityError):
        YouTubePublisher(FakeClient(echo="public")).upload(tmp_path / "v.mp4", title="t",
                                                           description="d", tags=[])


def test_visibility_change_requires_matching_confirmation():
    client = FakeClient()
    pub = YouTubePublisher(client)
    with pytest.raises(UnsafeVisibilityError):
        pub.set_visibility("VID", episode_id="ee-0001-x", confirm_episode_id="ee-0001",
                           visibility="public")
    assert client.updates == []
    pub.set_visibility("VID", episode_id="ee-0001-x", confirm_episode_id="ee-0001-x",
                       visibility="public")
    assert client.updates == [("VID", {"privacyStatus": "public"})]


def _approve(settings, ep_id, ws, *, decision=ReviewDecisionKind.APPROVE) -> Path:
    save_pack(ws, MockLLMProvider(settings.samples_dir).research(ep_id, "t", "undersea_cables"))
    video = ws.render / f"{ep_id}_master.mp4"
    video.write_bytes(b"fake mp4 bytes")
    with session_scope(settings.db_path) as session:
        ep = get_episode(session, ep_id)
        for target in (S.RESEARCH, S.SCRIPT, S.STORYBOARD, S.ASSETS, S.RENDERED,
                       S.REVIEW_PENDING, S.APPROVED):
            transition(session, ep, target)
    atomic_write_json(ws.decision_file, ReviewDecision(
        episode_id=ep_id, decision=decision, reviewer="Ann", video_path=str(video),
        video_sha256=sha256_file(video), ai_disclosure_altered_content=False))
    return video


def test_publish_refused_without_approval(settings, episode):
    ep, ws, ch = episode
    with session_scope(settings.db_path) as session:
        e = get_episode(session, ep.id)
        with pytest.raises(PublishBlocked, match="requires 'approved'"):
            publish_private(settings, session, e, ws, ch, client=FakeClient())


def test_publish_refused_without_approve_artifact(settings, episode):
    ep, ws, ch = episode
    _approve(settings, ep.id, ws)
    ws.decision_file.unlink()
    with session_scope(settings.db_path) as session:
        e = get_episode(session, ep.id)
        with pytest.raises(PublishBlocked, match="No review decision"):
            publish_private(settings, session, e, ws, ch, client=FakeClient())


def test_publish_refused_if_video_changed_after_approval(settings, episode):
    ep, ws, ch = episode
    video = _approve(settings, ep.id, ws)
    video.write_bytes(b"edited after approval")
    with session_scope(settings.db_path) as session:
        e = get_episode(session, ep.id)
        with pytest.raises(PublishBlocked, match="sha256"):
            publish_private(settings, session, e, ws, ch, client=FakeClient())


def test_approved_upload_is_private_then_visibility_is_separate(settings, episode):
    ep, ws, ch = episode
    _approve(settings, ep.id, ws)
    client = FakeClient()
    with session_scope(settings.db_path) as session:
        e = get_episode(session, ep.id)
        res = publish_private(settings, session, e, ws, ch, client=client)
        assert res.remote_video_id == "VID123"
        assert e.state == S.PRIVATE_UPLOADED.value and e.youtube_privacy == "private"
        assert client.inserted[0]["status"]["privacyStatus"] == "private"
        assert client.updates == []  # nothing made public by the upload itself
        with pytest.raises(UnsafeVisibilityError):
            change_visibility(settings, session, e, visibility="public",
                              confirm_episode_id="wrong", client=client)
        assert e.state == S.PRIVATE_UPLOADED.value
        change_visibility(settings, session, e, visibility="public",
                          confirm_episode_id=e.id, client=client)
        assert e.state == S.PUBLISHED.value


def test_no_credentials_exports_release_folder(settings, episode):
    ep, ws, ch = episode
    _approve(settings, ep.id, ws)
    with session_scope(settings.db_path) as session:
        e = get_episode(session, ep.id)
        res = publish_private(settings, session, e, ws, ch)  # flag off, no client
        assert res.mode == "release_folder"
        assert e.state == S.APPROVED.value
        meta = (res.path / "metadata.json").read_text()
        assert '"privacyStatus": "private"' in meta
        assert (res.path / "UPLOAD_INSTRUCTIONS.md").exists()


def test_full_private_upload_includes_captions_and_private_shorts(settings, episode):
    import json

    ep, ws, ch = episode
    _approve(settings, ep.id, ws)
    (ws.render / f"{ep.id}.en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
    for k in (1, 2):
        d = ws.shorts / f"short-{k}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"short-{k}_master.mp4").write_bytes(b"x")
        (d / f"short-{k}.en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
        (d / "metadata.json").write_text(json.dumps({"title": f"S{k}", "description": "d"}))
    client = FakeClient()
    with session_scope(settings.db_path) as session:
        e = get_episode(session, ep.id)
        publish_private(settings, session, e, ws, ch, client=client)
    assert [b["status"]["privacyStatus"] for b in client.inserted] == ["private"] * 3
    assert "youtu.be/VID123" in client.inserted[1]["snippet"]["description"]
    assert [c[0] for c in client.captions] == ["VID123", "SHORT1", "SHORT2"]
    meta = json.loads((ws.shorts / "short-1" / "metadata.json").read_text())
    assert meta["remote_video_id"] == "SHORT1"
    receipt = (ws.release / "upload_receipt.json").read_text()
    assert "SHORT2" in receipt


def test_analytics_api_rows_are_mapped_per_video():
    from studio.providers.youtube import fetch_video_stats

    class FakeAnalytics:
        def __init__(self):
            self.params = None

        def query(self, **params):
            self.params = params
            return {"columnHeaders": [{"name": "video"}, {"name": "views"},
                                      {"name": "averageViewDuration"}],
                    "rows": [["VID123", 120, 95], ["SHORT1", 900, 21]]}

    fa = FakeAnalytics()
    out = fetch_video_stats(fa, ["VID123", "SHORT1"], "2026-11-01", "2026-11-18")
    assert out["VID123"] == {"views": 120.0, "averageViewDuration": 95.0}
    assert fa.params["ids"] == "channel==MINE" and "VID123" in fa.params["filters"]
    assert fetch_video_stats(fa, [], "a", "b") == {}


def test_analytics_api_import_stores_rows_for_uploaded_episodes(settings, episode):
    from datetime import UTC, datetime

    from sqlmodel import select

    from studio.analytics import import_api
    from studio.models import VideoStats

    ep, ws, ch = episode

    class FakeAnalytics:
        def query(self, **params):
            return {"columnHeaders": [{"name": "video"}, {"name": "views"},
                                      {"name": "subscribersGained"}],
                    "rows": [["VIDX", 321, 4]]}

    with session_scope(settings.db_path) as session:
        e = get_episode(session, ep.id)
        e.remote_video_id = "VIDX"
        session.add(e)
        session.flush()
        n = import_api(session, ch.key, FakeAnalytics(), 28,
                       today=datetime(2026, 11, 18, tzinfo=UTC))
        rows = session.exec(select(VideoStats).where(VideoStats.source == "api")).all()
    assert n == 1 and rows[0].views == 321 and rows[0].subscribers_gained == 4
