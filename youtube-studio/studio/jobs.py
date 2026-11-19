"""Resumable job runs: each step records an input hash so unchanged work can be skipped."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from sqlmodel import Session, col, select

from studio.models import JobRun, utcnow

T = TypeVar("T")


def last_success(session: Session, episode_id: str, step: str) -> JobRun | None:
    stmt = (
        select(JobRun)
        .where(JobRun.episode_id == episode_id, JobRun.step == step, JobRun.status == "succeeded")
        .order_by(col(JobRun.id).desc())
    )
    return session.exec(stmt).first()


def is_fresh(session: Session, episode_id: str, step: str, input_hash: str) -> bool:
    run = last_success(session, episode_id, step)
    return bool(
        run and run.input_hash == input_hash and run.output_path and Path(run.output_path).exists()
    )


def run_job(
    session: Session,
    episode_id: str,
    step: str,
    input_hash: str,
    fn: Callable[[], tuple[T, Path]],
) -> T:
    """Run `fn`, recording a JobRun. Failures are recorded and re-raised."""
    job = JobRun(episode_id=episode_id, step=step, input_hash=input_hash)
    session.add(job)
    session.commit()
    try:
        result, output = fn()
    except BaseException as exc:
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"[:2000]
        job.finished_at = utcnow()
        session.add(job)
        session.commit()
        raise
    job.status = "succeeded"
    job.output_path = str(output)
    job.finished_at = utcnow()
    session.add(job)
    session.commit()
    return result
