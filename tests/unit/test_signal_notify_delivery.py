"""Regression test for audit finding F2 — signal TP/SL notifications claimed delivery
without sending anything (ممیزی 2026-11-28).

Fixed: ``jobs.signal_eval_daily.notify_subscribers`` now records ``delivered=False``.
This sync path has no delivery transport (the Telegram/Bale senders are async), so it
must never write a delivered=True claim — the history row is the in-platform record
only. Wiring real channel delivery for signal outcomes is audit finding F17 (the
whole ``run_daily`` path has no production caller today).

If this test fails with a delivered=True insert again, the false claim regressed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import jobs.signal_eval_daily as signal_eval


class _RecordingSession:
    """Minimal sync-session double that records every execute() call."""

    def __init__(self, select_rows: list[tuple]) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._select_rows = select_rows

    def execute(self, sql, params=None):
        text_sql = str(sql)
        self.calls.append((text_sql, dict(params or {})))
        result = MagicMock()
        result.fetchall.return_value = self._select_rows
        return result

    def commit(self) -> None:  # pragma: no cover — recorded behaviour only
        pass

    def rollback(self) -> None:  # pragma: no cover
        pass


def test_signal_notify_never_claims_delivery_without_send():
    session = _RecordingSession(select_rows=[("alr_sig", '["telegram"]')])

    notified = signal_eval.notify_subscribers(session, "sig_123", "فولاد",
                                              "hit_target", 125000.0)

    inserts = [(sql, params) for sql, params in session.calls if "alert_history" in sql]
    assert notified == 1 and inserts, "history row must exist for the subscriber"
    # The contract: this path has no transport, so it must record delivered=False
    # for every row — never claim a delivery that did not happen (F2).
    assert all(params.get("d") is False for _, params in inserts), \
        "alert_history must not claim delivery on the transport-less signal path"


def test_signal_notify_updates_counters():
    """The trigger bookkeeping (counter bump) is recorded alongside the history row."""
    session = _RecordingSession(select_rows=[("alr_sig", '["telegram"]')])
    signal_eval.notify_subscribers(session, "sig_123", "فولاد", "hit_target", 125000.0)
    updates = [params for sql, params in session.calls
               if "UPDATE alerts" in sql and "triggered_count" in sql]
    assert len(updates) == 1
