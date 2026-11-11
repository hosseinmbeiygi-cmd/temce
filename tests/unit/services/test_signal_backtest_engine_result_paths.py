"""STEP 7D-3 — the engine's error paths must return a failed ``Result``.

``core.typing.Result`` exposes ``ok`` and ``fail`` only; ``Result.err`` never
existed, so both error branches of ``backtest_signals`` raised
``AttributeError`` instead of reporting the failure to the caller.
"""

from __future__ import annotations

import core.database as database
from core.result import Result
from services.signal_backtest_engine import SignalBacktestEngine

_SIGNAL = {"symbol": "AAP", "market": "stock", "direction": "buy", "current_price": 100.0}


async def test_missing_session_factory_reports_failure(monkeypatch) -> None:
    monkeypatch.setattr(database, "async_session_factory", None, raising=False)

    result = await SignalBacktestEngine().backtest_signals([_SIGNAL])

    assert isinstance(result, Result)
    assert result.success is False
    assert result.error == "No database session available"
    assert result.value is None


async def test_any_inner_exception_becomes_a_failed_result(monkeypatch) -> None:
    class _Boom:
        def __call__(self) -> None:
            raise RuntimeError("session exploded")

    monkeypatch.setattr(database, "async_session_factory", _Boom(), raising=False)

    result = await SignalBacktestEngine().backtest_signals([_SIGNAL])

    assert result.success is False
    assert result.error == "session exploded"


async def test_empty_signal_list_still_needs_the_session(monkeypatch) -> None:
    """No session is a failure, not a silently empty success."""
    monkeypatch.setattr(database, "async_session_factory", None, raising=False)

    result = await SignalBacktestEngine().backtest_signals([])

    assert result.success is False
    assert result.error == "No database session available"
