"""Regression tests for audit finding F5 — EvaluateAlertsJob must not evaluate outside
Tehran trading hours (ممیزی 2026-11-28).

Fixed: the job now gates on ``is_tehran_market_open()`` and reports ``skipped`` (not
success) when the market is closed — outside the session the "today" snapshot is the
closing state and price/volume/RSI alerts would fire hours after close.

The second test preserves the pre-existing DB-availability behaviour for when the
market is open.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from jobs.definitions.alert_jobs import EvaluateAlertsJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult


def _ctx() -> JobContext:
    return JobContext(job_id="job_gate_test", job_name="EvaluateAlertsJob", params={})


@pytest.mark.asyncio
async def test_market_closed_pass_is_skipped():
    with patch("jobs.market_hours.is_tehran_market_open", return_value=False):
        result = await EvaluateAlertsJob().execute(_ctx())
    assert result.skipped and not result.success
    assert "market closed" in result.message
    assert result.data == {}  # nothing was evaluated


@pytest.mark.asyncio
async def test_market_open_still_requires_database():
    """When the gate is open, the pre-existing behaviour stands: no DB → failure."""
    with patch("jobs.market_hours.is_tehran_market_open", return_value=True), \
         patch("core.database.async_session_factory", None):
        result = await EvaluateAlertsJob().execute(_ctx())
    assert not result.success
    assert "Database not available" in result.error
