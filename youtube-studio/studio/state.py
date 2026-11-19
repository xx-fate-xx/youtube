"""Episode state machine. The only way to change Episode.state is `transition()`."""

from __future__ import annotations

from sqlmodel import Session

from studio.models import Episode, EpisodeState, StateTransition, utcnow

S = EpisodeState

# Forward edges follow the production pipeline; the few backward edges are named
# rework paths (re-research, re-script, re-storyboard, re-render, revoke approval).
ALLOWED: dict[EpisodeState, frozenset[EpisodeState]] = {
    S.IDEA: frozenset({S.RESEARCH}),
    S.RESEARCH: frozenset({S.SCRIPT}),
    S.SCRIPT: frozenset({S.STORYBOARD, S.RESEARCH}),
    S.STORYBOARD: frozenset({S.ASSETS, S.SCRIPT, S.RESEARCH}),
    S.ASSETS: frozenset({S.RENDERED, S.STORYBOARD, S.SCRIPT, S.RESEARCH}),
    S.RENDERED: frozenset({S.REVIEW_PENDING, S.ASSETS, S.STORYBOARD, S.SCRIPT, S.RESEARCH}),
    S.REVIEW_PENDING: frozenset({S.APPROVED, S.ASSETS, S.STORYBOARD, S.SCRIPT, S.RESEARCH}),
    S.APPROVED: frozenset({S.PRIVATE_UPLOADED, S.REVIEW_PENDING}),
    S.PRIVATE_UPLOADED: frozenset({S.PUBLISHED}),
    S.PUBLISHED: frozenset({S.ANALYZED}),
    S.ANALYZED: frozenset({S.ANALYZED}),
}

ORDER = list(EpisodeState)


class IllegalTransition(RuntimeError):
    pass


def can_transition(current: EpisodeState, target: EpisodeState) -> bool:
    return target in ALLOWED[current]


def transition(
    session: Session,
    episode: Episode,
    target: EpisodeState,
    *,
    actor: str = "operator",
    note: str = "",
    allow_same: bool = True,
) -> bool:
    """Move an episode to `target`. Returns False if it was already there (idempotent re-run)."""
    current = EpisodeState(episode.state)
    if current == target and allow_same and target != S.ANALYZED:
        return False
    if not can_transition(current, target):
        allowed = ", ".join(sorted(s.value for s in ALLOWED[current])) or "none"
        raise IllegalTransition(
            f"Episode {episode.id}: cannot go {current.value} -> {target.value} "
            f"(allowed: {allowed})"
        )
    session.add(
        StateTransition(
            episode_id=episode.id,
            from_state=current.value,
            to_state=target.value,
            actor=actor,
            note=note,
        )
    )
    episode.state = target.value
    episode.updated_at = utcnow()
    session.add(episode)
    session.flush()
    return True


def require_at_least(episode: Episode, minimum: EpisodeState, action: str) -> None:
    """Guard: `action` needs the episode to have reached `minimum` in the pipeline."""
    current = EpisodeState(episode.state)
    if ORDER.index(current) < ORDER.index(minimum):
        raise IllegalTransition(
            f"Cannot {action}: episode {episode.id} is in '{current.value}', "
            f"needs at least '{minimum.value}'."
        )


def enter_step(session: Session, episode: Episode, target: EpisodeState, *, note: str = "") -> None:
    """Enter a (re-)runnable step: idempotent if already there, else a legal transition.

    Running an earlier step on an episode that is further along is a rework path and
    goes through the same transition table (e.g. rendered -> script).
    """
    transition(session, episode, target, note=note)
