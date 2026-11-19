from __future__ import annotations

import pytest
from sqlmodel import select

from studio.db import session_scope
from studio.episodes import get_episode
from studio.models import EpisodeState as S
from studio.models import StateTransition
from studio.state import ALLOWED, IllegalTransition, can_transition, transition

HAPPY_PATH = [S.RESEARCH, S.SCRIPT, S.STORYBOARD, S.ASSETS, S.RENDERED, S.REVIEW_PENDING,
              S.APPROVED, S.PRIVATE_UPLOADED, S.PUBLISHED, S.ANALYZED]


def test_happy_path_is_legal_and_logged(settings, episode):
    ep, _, _ = episode
    with session_scope(settings.db_path) as session:
        ep = get_episode(session, ep.id)
        for target in HAPPY_PATH:
            transition(session, ep, target)
        assert ep.state == S.ANALYZED.value
        log = session.exec(select(StateTransition).where(
            StateTransition.episode_id == ep.id)).all()
        assert [t.to_state for t in log] == ["idea"] + [s.value for s in HAPPY_PATH]


@pytest.mark.parametrize("target", [S.SCRIPT, S.RENDERED, S.APPROVED, S.PRIVATE_UPLOADED,
                                    S.PUBLISHED])
def test_cannot_skip_ahead_from_idea(settings, episode, target):
    ep, _, _ = episode
    with session_scope(settings.db_path) as session:
        ep = get_episode(session, ep.id)
        with pytest.raises(IllegalTransition):
            transition(session, ep, target)
        assert ep.state == S.IDEA.value


def test_cannot_publish_or_upload_without_approval():
    for state in (S.RENDERED, S.REVIEW_PENDING):
        assert not can_transition(state, S.PRIVATE_UPLOADED)
        assert not can_transition(state, S.PUBLISHED)
    assert not can_transition(S.APPROVED, S.PUBLISHED)  # must be uploaded private first


def test_rework_edges_exist_but_not_after_upload():
    assert can_transition(S.REVIEW_PENDING, S.SCRIPT)
    assert can_transition(S.RENDERED, S.ASSETS)
    assert can_transition(S.APPROVED, S.REVIEW_PENDING)
    assert ALLOWED[S.PRIVATE_UPLOADED] == frozenset({S.PUBLISHED})


def test_same_state_is_idempotent(settings, episode):
    ep, _, _ = episode
    with session_scope(settings.db_path) as session:
        ep = get_episode(session, ep.id)
        assert transition(session, ep, S.RESEARCH) is True
        assert transition(session, ep, S.RESEARCH) is False


def test_duplicate_topic_is_refused(settings, episode):
    from studio.channels import get_channel
    from studio.episodes import create_episode

    ch = get_channel(settings.channels_dir, "engineering_explained")
    with session_scope(settings.db_path) as session, pytest.raises(ValueError,
                                                                   match="repetitive"):
        create_episode(session, settings, ch, "How Undersea Internet Cables Work!",
                       target_minutes=9)
