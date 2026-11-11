"""Monitoring must never report ``healthy`` when its alert source failed.

``MonitoringService.get_alerts`` swallowed any error by returning
``Result.ok([])`` and ``get_dashboard`` then computed
``status = "healthy" if not alerts.value else "degraded"``. An exception while
reading component health therefore produced an empty alert list, which the
dashboard rendered as ``status="healthy"`` â€” a false-healthy monitoring
signal (the exact P1 "success-empty masks source failure" pattern).

The handler must now surface the failure (``success=False``) and the dashboard
must not claim ``healthy`` when the alert source errored.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class _ExplodingHealthChecker:
    """Every ``_results`` read raises, standing in for a broken health source."""

    @property
    def _results(self):
        raise RuntimeError("health registry unavailable")

    async def check_all(self):
        raise RuntimeError("health registry unavailable")

    def get_overall_status(self):
        raise RuntimeError("health registry unavailable")


@pytest.mark.asyncio
async def test_get_alerts_error_is_success_false(monkeypatch) -> None:
    from services import monitoring_service as mod

    monkeypatch.setattr(mod, "health_checker", _ExplodingHealthChecker())
    service = mod.MonitoringService()

    result = await service.get_alerts()

    assert result.success is False
    assert result.error_code == "source_error"


@pytest.mark.asyncio
async def test_dashboard_never_reports_healthy_on_alert_error(monkeypatch) -> None:
    from services import monitoring_service as mod

    monkeypatch.setattr(mod, "health_checker", _ExplodingHealthChecker())
    service = mod.MonitoringService()

    result = await service.get_dashboard()

    assert result.success is False
    assert result.value["status"] != "healthy"
