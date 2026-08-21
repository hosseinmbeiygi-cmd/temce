"""Regression tests for the confirmed runtime fixes from the code audit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backtesting.analytics.engine import AnalyticsEngine
from backtesting.calibration.impact_calibration import calibrate_impact
from backtesting.metrics.trade_metrics import TradeMetrics
from backtesting.types import BacktestResult, EquityPoint, FillEvent
from domain.common.enum_types import OrderSide


def _fill(side: OrderSide, quantity: int, price: float, commission: float, minute: int) -> FillEvent:
    return FillEvent(
        order_id=f"o-{minute}",
        instrument_id="TEST",
        side=side,
        quantity=quantity,
        price=price,
        commission=commission,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
    )


def _result(trades: list[FillEvent]) -> BacktestResult:
    points = [
        EquityPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), nav=100_000, cash=100_000, positions_value=0),
        EquityPoint(timestamp=datetime(2025, 1, 2, tzinfo=UTC), nav=100_000, cash=100_000, positions_value=0),
    ]
    return BacktestResult(trades=trades, equity_curve=points)


def test_table_browser_denylist_contains_credentials() -> None:
    from apps.api.endpoints.tables import _SENSITIVE_COLUMNS

    assert {"hashed_password", "refresh_token", "totp_secret"}.issubset(_SENSITIVE_COLUMNS)


def test_backtest_collector_rate_limiter_rechecks_after_sleep() -> None:
    """The full-window path must loop, not recurse while holding the lock."""
    import backtest_collector

    limiter = backtest_collector.RateLimiter(max_requests=1, window_seconds=10)
    with patch.object(backtest_collector.time, "time", side_effect=[0.0, 0.0, 10.2]), patch.object(
        backtest_collector.time, "sleep"
    ) as sleep:
        limiter.wait_if_needed()
        limiter.wait_if_needed()

    sleep.assert_called_once()
    assert len(limiter.requests) == 1


def test_trade_metrics_matches_sell_across_multiple_buy_lots() -> None:
    trades = [
        _fill(OrderSide.BUY, 100, 100.0, 10.0, 1),
        _fill(OrderSide.BUY, 100, 200.0, 10.0, 2),
        _fill(OrderSide.SELL, 150, 150.0, 15.0, 3),
    ]
    metrics = TradeMetrics.compute(_result(trades))

    # FIFO: first 100 shares + half of the second lot are matched.
    expected = (150 - 100.1) * 100 - 10 + (150 - 200.1) * 50 - 5
    assert metrics["total_pnl"] == pytest.approx(expected)


def test_analytics_matches_sell_across_multiple_buy_lots() -> None:
    trades = [
        _fill(OrderSide.BUY, 100, 100.0, 10.0, 1),
        _fill(OrderSide.BUY, 100, 200.0, 10.0, 2),
        _fill(OrderSide.SELL, 150, 150.0, 15.0, 3),
    ]
    analytics = AnalyticsEngine().compute(_result(trades))

    expected = (150 - 100.1) * 100 - 10 + (150 - 200.1) * 50 - 5
    assert analytics.avg_win == pytest.approx((150 - 100.1) * 100 - 10)
    assert analytics.avg_loss == pytest.approx((150 - 200.1) * 50 - 5)
    assert analytics.winning_trades == 1
    assert analytics.losing_trades == 1
    assert expected != 0


def test_zero_pnl_breaks_win_loss_streaks() -> None:
    trades = [
        _fill(OrderSide.BUY, 1, 100.0, 0.0, 1),
        _fill(OrderSide.SELL, 1, 100.0, 0.0, 2),
        _fill(OrderSide.BUY, 1, 100.0, 0.0, 3),
        _fill(OrderSide.SELL, 1, 99.0, 0.0, 4),
    ]
    metrics = TradeMetrics.compute(_result(trades))
    assert metrics["max_consecutive_wins"] == 0
    assert metrics["max_consecutive_losses"] == 1


def test_impact_calibration_rejects_unexplained_data() -> None:
    eta, alpha = calibrate_impact(
        trade_sizes=[1, 2, 3, 4, 5, 6],
        price_moves=[0, 0, 0, 0, 0, 0],
        adv=100,
    )
    assert (eta, alpha) == (0.1, 0.6)


def test_impact_calibration_accepts_high_quality_log_fit() -> None:
    sizes = [1, 2, 4, 8, 16, 32]
    moves = [0.02 * (size / 100) ** 0.6 for size in sizes]
    eta, alpha = calibrate_impact(sizes, moves, adv=100)
    assert eta == pytest.approx(0.02, rel=1e-5)
    assert alpha == pytest.approx(0.6, rel=1e-5)


@pytest.mark.asyncio
async def test_rate_limiter_uses_local_fallback_when_redis_is_unavailable() -> None:
    from core.rate_limit.limiter import RateLimiter

    cache = MagicMock(client=None)
    limiter = RateLimiter()
    with patch("core.cache.get_cache", return_value=cache):
        allowed, remaining = await limiter.allow_async("test:key", max_calls=1)
        blocked, blocked_remaining = await limiter.allow_async("test:key", max_calls=1)

    assert allowed is True
    assert remaining == 0
    assert blocked is False
    assert blocked_remaining == 0


@pytest.mark.asyncio
async def test_readiness_checks_database_and_redis() -> None:
    from apps.api.endpoints.health import readiness

    session = MagicMock()
    session.execute = AsyncMock()
    factory = MagicMock()
    context = AsyncMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = context

    cache = MagicMock(is_connected=True)
    cache.ping = AsyncMock(return_value=True)
    with patch("core.database.async_session_factory", factory), patch(
        "core.cache.get_cache", return_value=cache
    ):
        response = await readiness()

    assert response.status_code == 200
    body = response.body.decode()
    assert '"status":"ready"' in body
    assert '"database":{"status":"ok"}' in body
    assert '"redis":{"status":"ok"}' in body


def test_settings_reject_invalid_runtime_values() -> None:
    from pydantic import ValidationError

    from core.config import Settings

    with pytest.raises(ValidationError):
        Settings(ml_device="tpu")
    with pytest.raises(ValidationError):
        Settings(auth_cookie_samesite="sometimes")


def test_iran_calendar_uses_thursday_and_friday_as_weekend() -> None:
    from datetime import date

    from core.time import is_market_open
    from core.time.calendar_utils import CalendarUtils
    from core.time.market_sessions import get_current_session

    # 2026-01-08 is Thursday; 2026-01-10 is Saturday.
    thursday = datetime(2026, 1, 8, 10, 0)
    saturday = datetime(2026, 1, 10, 10, 0)
    assert is_market_open(thursday) is False
    assert get_current_session(thursday).name == "closed"
    assert is_market_open(saturday) is True
    assert CalendarUtils.is_weekend(date(2026, 1, 8)) is True
    assert CalendarUtils.is_weekend(date(2026, 1, 10)) is False


def test_legacy_sql_helpers_reject_injected_identifiers(monkeypatch) -> None:
    import importlib

    for key in ("PG_HOST", "PG_PORT", "PG_DATABASE", "PG_USER", "PG_PASSWORD"):
        monkeypatch.setenv(key, "test")
    module = importlib.import_module("database_handler")
    assert module._safe_identifier("symbol") == '"symbol"'
    with pytest.raises(ValueError):
        module._safe_identifier('symbol"; DROP TABLE users; --')
    with pytest.raises(ValueError):
        module._safe_columns(["symbol", "bad column"])


def test_queue_trade_volume_consumes_ahead_before_filling() -> None:
    from backtesting.microstructure.queue_state import QueueState, SimulatedOrder

    queue = QueueState(instrument_id="TEST")
    order = SimulatedOrder(
        order_id="order-1", instrument_id="TEST", side="buy", price=100.0, quantity=100,
    )
    order.queue_ahead = 50
    queue.bids.append(order)
    queue.bid_queue_volume = 100

    fills = queue.update_from_trade(100, 100.0, "buy")

    assert len(fills) == 1
    assert fills[0].quantity == 50
    assert order.remaining == 50


def test_cancel_model_uses_poisson_sampler() -> None:
    from backtesting.microstructure.cancel_model import CancelModel

    with patch("backtesting.microstructure.cancel_model.np.random.poisson", return_value=7) as poisson:
        result = CancelModel(base_cancel_rate=0.5).sample_cancel_events(10)

    poisson.assert_called_once()
    assert result == 7


def test_json_serializer_does_not_embed_model_as_json_string() -> None:
    from dataclasses import dataclass

    from core.json.encoding import dumps

    @dataclass
    class Payload:
        value: int

    encoded = dumps({"payload": Payload(7)})
    assert '"payload":{"value":7}' in encoded
