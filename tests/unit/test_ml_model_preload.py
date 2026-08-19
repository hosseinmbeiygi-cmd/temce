"""Tests for the ``_ml_model_preload`` startup task in ``apps/api/app.py``.

Covers:
  1. Loads the union of watchlist + screener symbols into ModelLoader.preload
  2. Deduplicates symbols appearing in both lists
  3. Skips gracefully when no active symbols exist
  4. Tolerates a missing watchlist table (falls back to screener symbols)
  5. Tolerates a missing screener table (falls back to watchlist symbols)
  6. Tolerates no DB session (logs warning, no crash)
  7. Tolerates preload failure (non-fatal)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on sys.path (mirrors test_cron_alerts_real.py)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResult:
    """Mimic an asyncpg/SQLAlchemy result with .fetchall()."""

    def __init__(self, rows: list[tuple]):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """Mimic an AsyncSession whose execute() returns rows per table name."""

    def __init__(self, watchlist: list[str], symbols: list[str]) -> None:
        self._watchlist = watchlist
        self._symbols = symbols
        self.executed: list[str] = []

    async def execute(self, stmt) -> _FakeResult:
        sql = str(stmt)
        self.executed.append(sql)
        if "FROM watchlist" in sql:
            return _FakeResult([(s,) for s in self._watchlist])
        return _FakeResult([(s,) for s in self._symbols])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSessionForErrors:
    """Session whose execute() raises for a specific table keyword."""

    def __init__(self, fail_on: str) -> None:
        self._fail_on = fail_on

    async def execute(self, stmt):
        sql = str(stmt)
        if self._fail_on in sql:
            raise RuntimeError(f"table missing: {self._fail_on}")
        if "FROM watchlist" in sql:
            return _FakeResult([("فولاد",), ("وبملت",)])
        return _FakeResult([("خودرو",)])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _make_session_cm(session):
    """Wrap a fake session so ``async for session in get_session()`` works."""

    class _CM:
        def __init__(self, s):
            self._s = s

        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "_done", False):
                raise StopAsyncIteration
            self._done = True
            return self._s

    return _CM(session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preload_loads_union_of_watchlist_and_screener():
    """preload must be called with the union of watchlist + screener symbols."""
    import apps.api.app as app_mod

    session = _FakeSession(watchlist=["فولاد", "وبملت"], symbols=["خودرو", "فولاد"])
    loader = MagicMock()
    loader.preload = AsyncMock(return_value={"loaded": 3, "missing": ["خودرو"], "symbols": ["فولاد", "وبملت", "خودرو"]})

    with (
        patch.object(app_mod, "get_session", return_value=_make_session_cm(session)),
        patch("ml.model_loader.get_model_loader", return_value=loader),
    ):
        await app_mod._ml_model_preload()

    loader.preload.assert_awaited_once()
    symbols = loader.preload.call_args.kwargs["symbols"]
    # Union, screener first so watchlist stays hot in the LRU (loaded last)
    assert symbols == ["خودرو", "فولاد", "وبملت"]


@pytest.mark.asyncio
async def test_preload_deduplicates_symbols():
    """A symbol in both watchlist and screener must appear only once."""
    import apps.api.app as app_mod

    session = _FakeSession(watchlist=["فولاد", "وبملت"], symbols=["فولاد", "وبملت", "خودرو"])
    loader = MagicMock()
    loader.preload = AsyncMock(return_value={"loaded": 3, "missing": [], "symbols": ["فولاد", "وبملت", "خودرو"]})

    with (
        patch.object(app_mod, "get_session", return_value=_make_session_cm(session)),
        patch("ml.model_loader.get_model_loader", return_value=loader),
    ):
        await app_mod._ml_model_preload()

    symbols = loader.preload.call_args.kwargs["symbols"]
    assert len(symbols) == len(set(symbols)) == 3


@pytest.mark.asyncio
async def test_preload_skips_when_no_symbols():
    """Empty watchlist + screener → preload must NOT be called."""
    import apps.api.app as app_mod

    session = _FakeSession(watchlist=[], symbols=[])
    loader = MagicMock()
    loader.preload = AsyncMock()

    with (
        patch.object(app_mod, "get_session", return_value=_make_session_cm(session)),
        patch("ml.model_loader.get_model_loader", return_value=loader),
    ):
        await app_mod._ml_model_preload()

    loader.preload.assert_not_called()


@pytest.mark.asyncio
async def test_preload_falls_back_when_watchlist_table_missing():
    """Missing watchlist table → still preloads screener symbols."""
    import apps.api.app as app_mod

    session = _FakeSessionForErrors(fail_on="watchlist")
    loader = MagicMock()
    loader.preload = AsyncMock(return_value={"loaded": 1, "missing": [], "symbols": ["خودرو"]})

    with (
        patch.object(app_mod, "get_session", return_value=_make_session_cm(session)),
        patch("ml.model_loader.get_model_loader", return_value=loader),
    ):
        await app_mod._ml_model_preload()

    loader.preload.assert_awaited_once()
    symbols = loader.preload.call_args.kwargs["symbols"]
    assert symbols == ["خودرو"]


@pytest.mark.asyncio
async def test_preload_falls_back_when_screener_table_missing():
    """Missing screener symbols table → still preloads watchlist symbols."""
    import apps.api.app as app_mod

    session = _FakeSessionForErrors(fail_on="FROM symbols")
    loader = MagicMock()
    loader.preload = AsyncMock(return_value={"loaded": 2, "missing": [], "symbols": ["فولاد", "وبملت"]})

    with (
        patch.object(app_mod, "get_session", return_value=_make_session_cm(session)),
        patch("ml.model_loader.get_model_loader", return_value=loader),
    ):
        await app_mod._ml_model_preload()

    loader.preload.assert_awaited_once()
    symbols = loader.preload.call_args.kwargs["symbols"]
    assert symbols == ["فولاد", "وبملت"]


@pytest.mark.asyncio
async def test_preload_handles_missing_session():
    """No DB session available → warning, no crash, no preload."""
    import apps.api.app as app_mod

    loader = MagicMock()
    loader.preload = AsyncMock()

    async def _no_session():
        """Async generator that yields no sessions."""
        if False:
            yield None  # pragma: no cover

    with (
        patch.object(app_mod, "get_session", new=_no_session),
        patch("ml.model_loader.get_model_loader", return_value=loader),
    ):
        await app_mod._ml_model_preload()

    loader.preload.assert_not_called()


@pytest.mark.asyncio
async def test_preload_tolerates_preload_failure():
    """preload() raising must not propagate (non-fatal at startup)."""
    import apps.api.app as app_mod

    session = _FakeSession(watchlist=["فولاد"], symbols=["خودرو"])
    loader = MagicMock()
    loader.preload = AsyncMock(side_effect=RuntimeError("disk error"))

    with (
        patch.object(app_mod, "get_session", return_value=_make_session_cm(session)),
        patch("ml.model_loader.get_model_loader", return_value=loader),
    ):
        # Must not raise
        await app_mod._ml_model_preload()


@pytest.mark.asyncio
async def test_preload_uses_loader_singleton():
    """get_model_loader() must be the source of the loader instance."""
    import apps.api.app as app_mod

    session = _FakeSession(watchlist=["فولاد"], symbols=[])
    loader = MagicMock()
    loader.preload = AsyncMock(return_value={"loaded": 1, "missing": [], "symbols": ["فولاد"]})

    with (
        patch.object(app_mod, "get_session", return_value=_make_session_cm(session)),
        patch("ml.model_loader.get_model_loader", return_value=loader) as mock_get,
    ):
        await app_mod._ml_model_preload()

    mock_get.assert_called_once_with()
