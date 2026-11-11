"""Regression tests for audit CFG-05 — the read replica is now actually used.

Two guarantees are covered:

1. ``get_replica_session`` marks the yielded session read-only and falls back to
   the primary factory when no replica is configured.
2. A write attempted through a read-only session raises instead of being
   silently discarded (the failure mode that made wiring the replica risky).
"""

from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

import core.database as db

# ── Read-only session guard ──────────────────────────────────────────────
# Importing ``core.database`` registers the do_orm_execute / before_flush
# listeners on ``sqlalchemy.orm.Session``; the tests below rely on that.


class _Base(DeclarativeBase):
    pass


class _Thing(_Base):
    __tablename__ = "readonly_guard_things"
    id = Column(Integer, primary_key=True)


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    _Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_flush_write_on_readonly_session_raises(engine) -> None:
    with Session(engine) as session:
        session.info["_readonly"] = True
        session.add(_Thing(id=1))
        with pytest.raises(RuntimeError, match="read-only"):
            session.flush()
        session.rollback()


def test_raw_insert_on_readonly_session_raises(engine) -> None:
    with Session(engine) as session:
        session.info["_readonly"] = True
        with pytest.raises(RuntimeError, match="read-only"):
            session.execute(text("INSERT INTO readonly_guard_things (id) VALUES (1)"))


def test_raw_select_on_readonly_session_is_allowed(engine) -> None:
    with Session(engine) as session:
        session.info["_readonly"] = True
        assert session.execute(text("SELECT 1")).scalar() == 1


def test_writes_still_work_without_the_readonly_marker(engine) -> None:
    """The guard must not affect primary (write) sessions."""
    with Session(engine) as session:
        session.add(_Thing(id=7))
        session.flush()
        session.commit()
        assert session.execute(text("SELECT count(*) FROM readonly_guard_things")).scalar() == 1


# ── get_replica_session ──────────────────────────────────────────────────


class _FakeSession:
    def __init__(self) -> None:
        self.info: dict[str, object] = {}


class _FakeFactory:
    """Minimal async-sessionmaker stand-in."""

    def __init__(self) -> None:
        self.created = 0

    def __call__(self) -> _FakeFactory:
        self.created += 1
        return self

    async def __aenter__(self) -> _FakeSession:
        self.session = _FakeSession()
        return self.session

    async def __aexit__(self, *exc_info: object) -> None:
        return None


async def _collect(agen) -> _FakeSession:
    session = await agen.__anext__()
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    return session


async def test_replica_session_is_marked_readonly(monkeypatch: pytest.MonkeyPatch) -> None:
    replica = _FakeFactory()
    monkeypatch.setattr(db, "replica_session_factory", replica)
    monkeypatch.setattr(db, "async_session_factory", _FakeFactory())

    session = await _collect(db.get_replica_session())

    assert session.info["_readonly"] is True
    assert replica.created == 1


async def test_replica_session_falls_back_to_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _FakeFactory()
    monkeypatch.setattr(db, "replica_session_factory", None)
    monkeypatch.setattr(db, "async_session_factory", primary)

    session = await _collect(db.get_replica_session())

    assert session.info["_readonly"] is True
    assert primary.created == 1


async def test_replica_session_without_any_factory_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "replica_session_factory", None)
    monkeypatch.setattr(db, "async_session_factory", None)

    with pytest.raises(RuntimeError, match="not initialized"):
        await _collect(db.get_replica_session())
