"""``OrderBookService.get_history`` must not mask a source failure as success.

Before the fix, a DB read failure fell into an ``except`` block that returned
``Result.ok([])`` â€” identical to a genuine "no history yet". The public
endpoint ``GET /orderbooks/{symbol}/history`` forwards ``result.success``
straight into the API envelope, so a broken table read was reported to the
frontend as ``success=True`` with empty data.

The handler must now answer ``Result.fail(...)`` with a machine-readable
``error_code`` so callers can tell source failure apart from success-empty.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class _FailingSession:
    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("brsapi_historical_daily read failed")


@pytest.mark.asyncio
async def test_get_history_source_error_is_success_false() -> None:
    from services.orderbook_service import OrderBookService

    service = OrderBookService(session=_FailingSession())
    result = await service.get_history("TEST", limit=10)

    assert result.success is False
    assert result.value is None
    assert result.error_code == "source_error"
    assert "history" in (result.error or "").lower()


class _Row:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping


class _OkResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def fetchall(self) -> list:
        return self._rows


class _OkSession:
    async def execute(self, *_args, **_kwargs):
        return _OkResult([_Row({"symbol": "TEST", "date": "2026-01-01", "volume": 5})])


@pytest.mark.asyncio
async def test_get_history_returns_rows_on_success() -> None:
    from services.orderbook_service import OrderBookService

    service = OrderBookService(session=_OkSession())
    result = await service.get_history("TEST", limit=10)

    assert result.success is True
    assert result.error_code is None
    assert result.value == [{"symbol": "TEST", "date": "2026-01-01", "volume": 5}]
