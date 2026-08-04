"""Unit tests for GET /queue-analysis/batch endpoint.

Tests cover:
  - Batch analysis with 3 symbols (mixed queues)
  - Empty symbols string → empty response
  - Single symbol
  - Max 20 symbols enforced
  - Exception in analyze_symbol → per-symbol error fallback
  - Dependency override with mock QueueAnalysisService
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ── Helpers ───────────────────────────────────────────────────────

from typing import Any

from apps.api.endpoints.queue_analysis import router as queue_analysis_router


class MockQueueAnalysisService:
    """Mock service that returns predefined results for each symbol."""

    def __init__(self, results: dict[str, dict[str, Any]] | None = None) -> None:
        self._results = results or {}

    async def analyze_symbol(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
        """Return mock result or default fallback."""
        default = {
            "symbol": symbol,
            "queue_status": "NONE",
            "queue_volume_ratio": 0.0,
            "queue_days_streak": 0,
            "queue_type_change": "NO_CHANGE",
            "distance_to_limit": 0.0,
            "last_price": 50000,
            "name": "",
            "market_type": "bours",
            "interpretation": {"status_fa": "⚪ بدون صف"},
            "adjustments": {},
            "final_decision": "NEUTRAL",
            "override_reason": "",
            "overridden": False,
        }
        return self._results.get(symbol, {**default, "symbol": symbol})

    async def analyze_market(self, **kwargs: Any) -> dict[str, Any]:
        return {"total_symbols": 0}


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def mock_service() -> MockQueueAnalysisService:
    """Create a default mock service with predefined symbol results."""
    return MockQueueAnalysisService({
        "فولاد": {
            "symbol": "فولاد",
            "name": "فولاد مبارکه اصفهان",
            "queue_status": "BUY_QUEUE",
            "queue_volume_ratio": 0.85,
            "queue_days_streak": 2,
            "queue_type_change": "NO_CHANGE",
            "distance_to_limit": 0.1,
            "last_price": 50925,
            "market_type": "bours",
            "interpretation": {
                "status_fa": "🟢 صف خرید",
                "volume_fa": "فشار خرید بسیار سنگین (85%)",
                "streak_fa": "روز 2 صف خرید — احتمال تداوم",
            },
            "adjustments": {"adjusted_liquidity": 75.0, "liquidity_delta": 15.0},
            "final_decision": "BUY",
            "override_reason": "Hard Rule: BUY_QUEUE + ratio > 0.7 + streak < 3 → BUY",
            "overridden": True,
        },
        "شستا": {
            "symbol": "شستا",
            "name": "شستا",
            "queue_status": "SELL_QUEUE",
            "queue_volume_ratio": 0.72,
            "queue_days_streak": 3,
            "queue_type_change": "NO_CHANGE",
            "distance_to_limit": 0.2,
            "last_price": 46075,
            "market_type": "bours",
            "interpretation": {
                "status_fa": "🔴 صف فروش",
                "volume_fa": "فشار فروش بسیار سنگین (72%)",
                "streak_fa": "تداوم صف فروش به مدت 3 روز — ریسک شدید",
            },
            "adjustments": {"adjusted_liquidity": 35.0, "liquidity_delta": -35.0},
            "final_decision": "REJECT",
            "override_reason": "Hard Rule: SELL_QUEUE + streak > 1 → REJECT",
            "overridden": True,
        },
        "وبملت": {
            "symbol": "وبملت",
            "name": "بانک ملت",
            "queue_status": "NONE",
            "queue_volume_ratio": 0.0,
            "queue_days_streak": 0,
            "queue_type_change": "NO_CHANGE",
            "distance_to_limit": 0.0,
            "last_price": 32000,
            "market_type": "bours",
            "interpretation": {"status_fa": "⚪ بدون صف"},
            "adjustments": {},
            "final_decision": "NEUTRAL",
            "override_reason": "",
            "overridden": False,
        },
    })


@pytest.fixture
def error_service() -> MockQueueAnalysisService:
    """Mock service where one symbol raises an exception."""
    class ErrorMockService(MockQueueAnalysisService):
        async def analyze_symbol(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
            if symbol == "خطایی":
                raise RuntimeError("Database connection failed")
            return await super().analyze_symbol(symbol, **kwargs)

    return ErrorMockService({
        "فولاد": {
            "symbol": "فولاد",
            "queue_status": "BUY_QUEUE",
            "queue_volume_ratio": 0.8,
            "queue_days_streak": 1,
            "queue_type_change": "NEW_BUY_QUEUE",
            "distance_to_limit": 0.3,
            "last_price": 50000,
            "name": "فولاد مبارکه",
            "market_type": "bours",
            "interpretation": {"status_fa": "🟢 صف خرید"},
            "adjustments": {},
            "final_decision": "BUY",
            "override_reason": "",
            "overridden": False,
        },
    })


def make_app(mock_svc: MockQueueAnalysisService) -> FastAPI:
    """Create a test app with the queue-analysis router and a mock dependency override."""

    # Create a minimal app with just the queue-analysis router
    app = FastAPI()

    # Register the router
    app.include_router(queue_analysis_router, prefix="/queue-analysis")

    # Override the dependency that provides the service
    async def override_get_service() -> MockQueueAnalysisService:
        return mock_svc

    from apps.api.endpoints.queue_analysis import get_queue_analysis_service
    app.dependency_overrides[get_queue_analysis_service] = override_get_service

    return app


# ═══════════════════════════════════════════════════════════════════════
# ── Tests
# ═══════════════════════════════════════════════════════════════════════


class TestQueueAnalysisBatchEndpoint:
    """Tests for GET /queue-analysis/batch."""

    @pytest.mark.asyncio
    async def test_batch_with_three_symbols_mixed_queues(
        self, mock_service: MockQueueAnalysisService,
    ):
        """3 نماد: فولاد (BUY_QUEUE), شستا (SELL_QUEUE), وبملت (NONE)."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "فولاد,شستا,وبملت"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

        # Assert order of results matches query order
        symbols_in_result = [item["symbol"] for item in data]
        assert symbols_in_result == ["فولاد", "شستا", "وبملت"]

        # Assert each has the expected queue status
        assert data[0]["queue_status"] == "BUY_QUEUE"
        assert data[0]["overridden"] is True
        assert data[0]["final_decision"] == "BUY"
        assert data[0]["queue_volume_ratio"] == 0.85

        assert data[1]["queue_status"] == "SELL_QUEUE"
        assert data[1]["overridden"] is True
        assert data[1]["final_decision"] == "REJECT"

        assert data[2]["queue_status"] == "NONE"
        assert data[2]["overridden"] is False
        assert data[2]["final_decision"] == "NEUTRAL"
        assert data[2]["queue_volume_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_batch_empty_symbols_string(self, mock_service: MockQueueAnalysisService):
        """رشته خالی → آرایه خالی برگردد."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": ""},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_batch_empty_symbols_with_whitespace(
        self, mock_service: MockQueueAnalysisService,
    ):
        """علامت کاما با فضای خالی → آرایه خالی."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": " , , "},
            )

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_batch_single_symbol(self, mock_service: MockQueueAnalysisService):
        """فقط یک نماد → یک نتیجه برگردد."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "فولاد"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "فولاد"
        assert data[0]["queue_status"] == "BUY_QUEUE"

    @pytest.mark.asyncio
    async def test_batch_max_20_symbols_enforced(
        self, mock_service: MockQueueAnalysisService,
    ):
        """حداکثر ۲۰ نماد — بقیه نادیده گرفته شوند."""
        symbols = [f"sym{i}" for i in range(30)]  # 30 symbols
        symbols_str = ",".join(symbols)

        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": symbols_str},
            )

        assert resp.status_code == 200
        data = resp.json()
        # mock_service returns NONE for unknown symbols
        assert len(data) == 20  # capped at 20

    @pytest.mark.asyncio
    async def test_batch_with_symbol_trimming(
        self, mock_service: MockQueueAnalysisService,
    ):
        """فضاهای خالی اطراف نمادها حذف شوند."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "  فولاد ,  شستا  "},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "فولاد"
        assert data[1]["symbol"] == "شستا"

    @pytest.mark.asyncio
    async def test_batch_contains_required_fields(
        self, mock_service: MockQueueAnalysisService,
    ):
        """هر نتیجه باید تمام فیلدهای کلیدی را داشته باشد."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "فولاد"},
            )

        assert resp.status_code == 200
        item = resp.json()[0]

        # 5 queue features
        assert "queue_status" in item
        assert "queue_volume_ratio" in item
        assert "queue_days_streak" in item
        assert "queue_type_change" in item
        assert "distance_to_limit" in item

        # Metadata
        assert "symbol" in item
        assert "last_price" in item
        assert "name" in item
        assert "market_type" in item

        # Analysis
        assert "interpretation" in item
        assert "adjustments" in item
        assert "final_decision" in item
        assert "overridden" in item

    @pytest.mark.asyncio
    async def test_batch_all_same_status(
        self, mock_service: MockQueueAnalysisService,
    ):
        """همه نمادها وضعیت یکسان (مثلاً BUY_QUEUE) داشته باشند."""
        # Override mock to return same status for all
        same_result = {
            "فولاد": {
                "symbol": "فولاد", "queue_status": "BUY_QUEUE",
                "queue_volume_ratio": 0.9, "queue_days_streak": 1,
                "queue_type_change": "NEW_BUY_QUEUE", "distance_to_limit": 0.05,
                "last_price": 51000, "name": "فولاد", "market_type": "bours",
                "interpretation": {"status_fa": "🟢 صف خرید"},
                "adjustments": {}, "final_decision": "BUY",
                "override_reason": "Hard Rule", "overridden": True,
            },
            "شستا": {
                "symbol": "شستا", "queue_status": "BUY_QUEUE",
                "queue_volume_ratio": 0.95, "queue_days_streak": 2,
                "queue_type_change": "NO_CHANGE", "distance_to_limit": 0.01,
                "last_price": 20000, "name": "شستا", "market_type": "bours",
                "interpretation": {"status_fa": "🟢 صف خرید"},
                "adjustments": {}, "final_decision": "BUY",
                "override_reason": "Hard Rule", "overridden": True,
            },
        }
        svc = MockQueueAnalysisService(same_result)
        app = make_app(svc)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "فولاد,شستا"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["queue_status"] == "BUY_QUEUE"
        assert data[1]["queue_status"] == "BUY_QUEUE"

    @pytest.mark.asyncio
    async def test_batch_symbol_not_in_mock(
        self, mock_service: MockQueueAnalysisService,
    ):
        """نمادی که در mock تعریف نشده → مقدار پیش‌فرض NONE برگردد."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "ناموجود"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "ناموجود"
        assert data[0]["queue_status"] == "NONE"

    @pytest.mark.asyncio
    async def test_batch_service_raises_exception(
        self, error_service: MockQueueAnalysisService,
    ):
        """یک نماد exception بدهد → آن نماد با error برگردد، بقیه正常工作."""
        app = make_app(error_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "فولاد,خطایی"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        # فولاد باید موفق باشد
        assert data[0]["symbol"] == "فولاد"
        assert data[0]["queue_status"] == "BUY_QUEUE"

        # خطایی باید error داشته باشد (endpoint exception message را لاگ می‌کند ولی در پاسخ فارسی برمی‌گرداند)
        assert data[1]["symbol"] == "خطایی"
        assert "error" in data[1]
        assert "تحلیل صف برای خطایی ناموفق" in data[1]["error"]
        assert data[1]["queue_status"] == "NONE"

    @pytest.mark.asyncio
    async def test_batch_preserves_queue_volume_ratio_precision(
        self, mock_service: MockQueueAnalysisService,
    ):
        """نسبت حجم صف با دقت کافی برگردد."""
        app = make_app(mock_service)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/queue-analysis/batch",
                params={"symbols": "فولاد"},
            )

        assert resp.status_code == 200
        data = resp.json()[0]
        # 0.85 should not be rounded to 0 or 1
        assert data["queue_volume_ratio"] == 0.85
