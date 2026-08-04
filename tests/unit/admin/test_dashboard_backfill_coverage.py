"""Tests for the admin dashboard backfill coverage endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.dashboard import router as dashboard_router
from core.database import get_session


class _FakeResult:
    """Minimal SQLAlchemy result stand-in for dashboard tests."""

    def __init__(self, rows: list | None = None, one: tuple | None = None) -> None:
        self._rows = rows or []
        self._one = one

    def fetchall(self) -> list:
        return self._rows

    def one_or_none(self) -> tuple | None:
        return self._one


@pytest.fixture
def client():
    """Create a FastAPI test client with mocked database session."""
    app = FastAPI()
    app.include_router(dashboard_router, prefix="/dashboard")

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(
        return_value=_FakeResult(
            rows=[("instruments", 100)],
            one=(1, 1, 1, 1, 1, 1, 1, 1),
        )
    )
    app.dependency_overrides[get_session] = lambda: mock_session

    with TestClient(app) as test_client:
        yield test_client


def test_backfill_coverage_success(client: TestClient) -> None:
    """The backfill coverage endpoint should return coverage stats for all three data types."""
    with patch("apps.admin.dashboard.get_backfill_stats") as mock_get_stats:
        mock_get_stats.return_value = {
            "total_instruments": 100,
            "with_data": 75,
            "missing": 25,
            "total_rows": 5000,
            "avg_rows_per_symbol": 66.7,
        }
        response = client.get("/dashboard/backfill-coverage")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3

    for item in data:
        assert "data_type" in item
        assert "table_name" in item
        assert "coverage_pct" in item
        assert item["total_instruments"] == 100
        assert item["with_data"] == 75
        assert item["missing"] == 25

    data_types = {item["data_type"] for item in data}
    assert data_types == {"history", "candlestick", "shareholder"}


def test_backfill_coverage_zero_instruments(client: TestClient) -> None:
    """Coverage percentage should be 0 when there are no active instruments."""
    with patch("apps.admin.dashboard.get_backfill_stats") as mock_get_stats:
        mock_get_stats.return_value = {
            "total_instruments": 0,
            "with_data": 0,
            "missing": 0,
            "total_rows": 0,
            "avg_rows_per_symbol": 0.0,
        }
        response = client.get("/dashboard/backfill-coverage")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert item["coverage_pct"] == 0.0


def test_backfill_coverage_full_coverage(client: TestClient) -> None:
    """Coverage percentage should be 100 when all instruments have data."""
    with patch("apps.admin.dashboard.get_backfill_stats") as mock_get_stats:
        mock_get_stats.return_value = {
            "total_instruments": 50,
            "with_data": 50,
            "missing": 0,
            "total_rows": 1500,
            "avg_rows_per_symbol": 30.0,
        }
        response = client.get("/dashboard/backfill-coverage")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert item["coverage_pct"] == 100.0


def test_backfill_coverage_error(client: TestClient) -> None:
    """The backfill coverage endpoint should surface errors gracefully."""
    with patch("apps.admin.dashboard.get_backfill_stats") as mock_get_stats:
        mock_get_stats.side_effect = RuntimeError("db down")
        response = client.get("/dashboard/backfill-coverage")

    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_dashboard_overview_includes_backfill_coverage(client: TestClient) -> None:
    """The main dashboard overview should include backfill_coverage in its response."""
    with patch("apps.admin.dashboard.get_backfill_stats") as mock_get_stats:
        mock_get_stats.return_value = {
            "total_instruments": 100,
            "with_data": 80,
            "missing": 20,
            "total_rows": 4000,
            "avg_rows_per_symbol": 50.0,
        }
        response = client.get("/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert "backfill_coverage" in data
    assert len(data["backfill_coverage"]) == 3
    data_types = {item["data_type"] for item in data["backfill_coverage"]}
    assert data_types == {"history", "candlestick", "shareholder"}
