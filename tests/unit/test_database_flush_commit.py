"""Regression tests for ``core.database.get_session`` write persistence.

Background
----------
``get_session`` used to COMMIT only when the session *looked* write-touched::

    session.info.get("_audit_wrote") or session.dirty or session.new or session.deleted

``do_orm_execute`` never fires for the INSERT/UPDATE/DELETE that ``session.flush()``
emits, and after a flush ``new`` / ``dirty`` / ``deleted`` are all empty — so the
old predicate was ``False`` and the COMMIT was skipped.  The write silently
vanished (observed with ``UserService.register``: the endpoint returned success
while the user row was never persisted).

The flag that briefly bridged that gap is gone: ``get_session`` now commits
unconditionally after the handler returns and rolls back when it raises, which is
the stronger contract.  These tests lock that behaviour in — a flush-only write
(and even an un-flushed ``add``) must be persisted, and a failing handler must
leave nothing behind.  The read-only session guard is covered separately in
``tests/unit/test_replica_readonly_session.py``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

import core.database as db

# ── Standalone schema (never touches the app's own tables) ────────────────


class _Base(DeclarativeBase):
    pass


class _Thing(_Base):
    __tablename__ = "thing_flush_audit_test"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(default="x")


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """File-backed SQLite so a *second* connection can observe the commit."""
    return tmp_path / "flush_commit.db"


@pytest.fixture
def _patched_factory(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session_factory", factory)
    sync = create_engine(f"sqlite:///{db_path}")
    _Base.metadata.create_all(sync)
    sync.dispose()
    yield


def _persisted_names(db_path: Path) -> list[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with Session(engine) as session:
            return list(session.execute(select(_Thing.name)).scalars().all())
    finally:
        engine.dispose()


_open_dependency = db.get_session  # the dependency under test, unmodified


# ── Contract: "the handler returned, so the write is persisted" ──────────


@pytest.mark.asyncio
async def test_flush_only_write_is_committed(_patched_factory: None, db_path: Path) -> None:
    """A flushed INSERT leaves no pending state but must still be persisted."""
    gen: AsyncGenerator[AsyncSession, None] = _open_dependency()
    session = await gen.__anext__()

    session.add(_Thing(name="inserted"))
    await session.flush()

    # This is precisely why the old predicate missed the write.
    assert not session.new

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()  # handler returned → get_session commits

    assert _persisted_names(db_path) == ["inserted"]


@pytest.mark.asyncio
async def test_unflushed_add_is_committed(_patched_factory: None, db_path: Path) -> None:
    """The common service shape — ``session.add(x)`` and no explicit flush."""
    gen: AsyncGenerator[AsyncSession, None] = _open_dependency()
    session = await gen.__anext__()

    session.add(_Thing(name="pending"))

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    assert _persisted_names(db_path) == ["pending"]


@pytest.mark.asyncio
async def test_flush_only_update_is_committed(_patched_factory: None, db_path: Path) -> None:
    """An UPDATE flushed by the handler must survive too, not just an INSERT."""
    gen: AsyncGenerator[AsyncSession, None] = _open_dependency()
    session = await gen.__anext__()
    session.add(_Thing(name="before"))
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    gen = _open_dependency()
    session = await gen.__anext__()
    thing = (await session.execute(select(_Thing))).scalar_one()
    thing.name = "after"
    await session.flush()
    assert not session.dirty

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    assert _persisted_names(db_path) == ["after"]


@pytest.mark.asyncio
async def test_failing_handler_rolls_back_the_write(_patched_factory: None, db_path: Path) -> None:
    """A raise must roll back, otherwise a failed request would half-commit."""
    gen: AsyncGenerator[AsyncSession, None] = _open_dependency()
    session = await gen.__anext__()

    session.add(_Thing(name="doomed"))
    await session.flush()

    with pytest.raises(RuntimeError, match="boom"):
        await gen.athrow(RuntimeError("boom"))

    assert _persisted_names(db_path) == []


@pytest.mark.asyncio
async def test_read_only_handler_is_a_harmless_commit(_patched_factory: None, db_path: Path) -> None:
    """SELECT-only handlers must not error out on the unconditional commit."""
    gen: AsyncGenerator[AsyncSession, None] = _open_dependency()
    session = await gen.__anext__()

    assert (await session.execute(select(_Thing))).scalars().all() == []

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    assert _persisted_names(db_path) == []


def test_get_session_still_commits_unconditionally() -> None:
    """Pin the mechanism, so the old write-detection predicate cannot come back.

    The bug was a *conditional* commit that guessed wrong. Read the source rather
    than trusting the tests above to notice a future re-introduction.
    """
    import inspect

    source = inspect.getsource(db.get_session)
    assert "await session.commit()" in source
    assert "_audit_wrote" not in source
    assert "session.dirty" not in source
