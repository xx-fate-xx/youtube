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

    def insert_video(self, video_path: Path, body: dict, thumbnail: Path | None) -> dict:
        self.inserted.append(body)
        return {"id": "VID123", "status": {"privacyStatus": self.echo}}

    def update_status(self, video_id: str, status: dict) -> dict:
        self.updates.append((video_id, status))
        return {"id": video_id, "status": status}


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
