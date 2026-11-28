"""Regression tests for audit finding F17 — the signal TP/SL evaluation path is wired
to a real scheduled job (ممیزی 2026-11-28).

Previously ``SignalEvaluationJob`` was a stub that only counted ids and
``signal_eval_daily.run_daily`` (the real evaluator, sync-session based) had no
production caller: signal-linked alert subscribers were never evaluated or recorded.
The job is now async-native, reuses the pure ``evaluate()`` contract, marks the
signal off ``pending`` (rerun-safe) and records ``alert_history`` rows with
``delivered=False`` (no transport on this path — audit F2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.definitions.signal_jobs import SignalEvaluationJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from models.alert import AlertHistoryModel


def _ctx() -> JobContext:
    return JobContext(job_id="job_sig_test", job_name="SignalEvaluationJob", params={})


def _signal_row() -> MagicMock:
    row = MagicMock()
    row.id = "sig_12345678"
    row.symbol = "فولاد"
    row.market = "stock"
    row.direction = "buy"
    row.entry = 100_000.0
    row.take_profit = 125_000.0
    row.stop_loss = 95_000.0
    row.generated_at = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    row.eval_due_at = datetime(2026, 11, 27, 10, 0, tzinfo=UTC)
    row.status = "pending"
    return row


def _linked_alert(**overrides) -> MagicMock:
    alert = MagicMock()
    alert.id = "alr_sig"
    alert.user_id = "usr_demo"
    alert.symbol = "فولاد"
    alert.enabled = True
    for key, value in overrides.items():
        setattr(alert, key, value)
    return alert


def _session(pending: list, quote_rows: list, linked_alerts: list) -> MagicMock:
    """Session double matching the job's read order: signals → quotes → alerts."""
    session = MagicMock()
    r_signals = MagicMock()
    r_signals.scalars.return_value.all.return_value = pending
    r_quotes = MagicMock()
    r_quotes.fetchall.return_value = quote_rows
    r_alerts = MagicMock()
    r_alerts.scalars.return_value.all.return_value = linked_alerts
    session.execute = AsyncMock(side_effect=[r_signals, r_quotes, r_alerts])
    session.commit = AsyncMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)
    session.add = MagicMock()
    return session


def _patched_factory(session) -> MagicMock:
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


@pytest.mark.asyncio
async def test_evaluates_pending_due_signal_and_records_history():
    sig = _signal_row()
    alert = _linked_alert()
    session = _session([sig], [(121_000.0, 119_000.0, 120_000.0)], [alert])
    with patch("core.database.async_session_factory", _patched_factory(session)):
        result = await SignalEvaluationJob().execute(_ctx())

    assert result.success
    assert result.data["evaluated"] == 1
    assert result.data["notified"] == 1
    # high 121k < TP 125k and low 119k > SL 95k → expired_neutral at the last close
    assert sig.status == "expired_neutral"
    assert sig.checked_at is not None
    histories = [c.args[0] for c in session.add.call_args_list
                 if isinstance(c.args[0], AlertHistoryModel)]
    assert len(histories) == 1
    assert histories[0].delivered is False          # F2: never claim delivery
    assert "hit" not in histories[0].message


@pytest.mark.asyncio
async def test_hit_target_is_detected_from_daily_bars():
    sig = _signal_row()
    session = _session([sig], [(130_000.0, 119_000.0, 128_000.0)], [])
    with patch("core.database.async_session_factory", _patched_factory(session)):
        result = await SignalEvaluationJob().execute(_ctx())
    assert result.success
    assert sig.status == "hit_target"
    assert sig.actual_outcome_price == 125_000.0    # fills at the take-profit price
    assert result.data["notified"] == 0             # no linked alert


@pytest.mark.asyncio
async def test_quarantined_alert_is_skipped():
    sig = _signal_row()
    orphan = _linked_alert(user_id=None)            # no owner → quarantined
    session = _session([sig], [(130_000.0, 119_000.0, 128_000.0)], [orphan])
    with patch("core.database.async_session_factory", _patched_factory(session)):
        result = await SignalEvaluationJob().execute(_ctx())
    assert result.success
    assert result.data["notified"] == 0
    assert not any(isinstance(c.args[0], AlertHistoryModel)
                   for c in session.add.call_args_list)


@pytest.mark.asyncio
async def test_no_pending_signals_is_a_clean_success():
    session = _session([], [], [])
    with patch("core.database.async_session_factory", _patched_factory(session)):
        result = await SignalEvaluationJob().execute(_ctx())
    assert result.success
    assert result.data["evaluated"] == 0


@pytest.mark.asyncio
async def test_one_bad_signal_never_aborts_the_pass():
    good = _signal_row()
    bad = _signal_row()
    bad.symbol = None                               # quotes query with symbol None → error path
    # Order: signals([good, bad]) → quotes(good) → alerts(good) → quotes(bad raises)
    session = MagicMock()
    r_signals = MagicMock()
    r_signals.scalars.return_value.all.return_value = [good, bad]
    r_quotes = MagicMock()
    r_quotes.fetchall.return_value = [(130_000.0, 119_000.0, 128_000.0)]
    r_alerts = MagicMock()
    r_alerts.scalars.return_value.all.return_value = []
    r_broken = MagicMock()
    r_broken.fetchall.side_effect = RuntimeError("bad row")
    session.execute = AsyncMock(side_effect=[r_signals, r_quotes, r_alerts, r_broken])
    session.commit = AsyncMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)
    session.add = MagicMock()
    with patch("core.database.async_session_factory", _patched_factory(session)):
        result = await SignalEvaluationJob().execute(_ctx())
    assert result.success
    assert result.data["errors"] == 1
    assert result.data["evaluated"] == 1            # the good signal still evaluated


@pytest.mark.asyncio
async def test_missing_database_fails():
    with patch("core.database.async_session_factory", None):
        result = await SignalEvaluationJob().execute(_ctx())
    assert not result.success
    assert "Database not available" in result.error
