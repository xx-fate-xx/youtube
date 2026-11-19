"""SQLite engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from studio import models  # noqa: F401  (register tables)

_ENGINES: dict[Path, Engine] = {}


def get_engine(db_path: Path) -> Engine:
    db_path = db_path.resolve()
    if db_path not in _ENGINES:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"timeout": 30})

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        SQLModel.metadata.create_all(engine)
        _ENGINES[db_path] = engine
    return _ENGINES[db_path]


@contextmanager
def session_scope(db_path: Path) -> Iterator[Session]:
    session = Session(get_engine(db_path), expire_on_commit=False)
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
