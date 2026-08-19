"""Unit tests for the paper-trading service.

Covers:
  - ``_signal_to_snapshot`` mapping (aliases, datetime parsing, None handling)
  - ``snapshot_signals`` journaling with dedupe keys
  - ``open_trade`` validation + derived target/stop prices
  - ``close_trade`` P&L computation
  - ``auto_close_due_trades`` (stop-loss / target / max-hold)
  - ``get_dashboard`` aggregation
  - ``_parse_price`` helper
  - ``_latest_price`` table routing + fallback

Uses a fake AsyncSession and plain model instances — no DB.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import Result
from services.paper_trading_service import (
    DEFAULT_INITIAL_CAPITAL,
    MAX_HOLDING_DAYS,
    PaperTradingService,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_session() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _make_snapshot(**overrides: Any) -> MagicMock:
    """Minimal PaperSignalSnapshotModel-like object for trade flows."""
    from models.paper_trading import PaperSignalSnapshotModel

    defaults: dict[str, Any] = {
        "id": "psnap_1",
        "symbol": "فولاد",
        "name": "فولاد مبارکه",
        "market": "stock",
        "timeframe": "daily",
        "source": "quant",
        "confidence": 0.8,
        "score": 85.0,
        "direction": "buy",
        "price": 5000.0,
        "stop_loss": "4500",
        "targets": "5400",
        "reason": "strong setup",
    }
    defaults.update(overrides)
    return PaperSignalSnapshotModel(**defaults)


def _make_trade(**overrides: Any) -> MagicMock:
    from models.paper_trading import PaperTradeModel

    defaults: dict[str, Any] = {
        "id": "ptrade_1",
        "symbol": "فولاد",
        "name": "فولاد مبارکه",
        "market": "stock",
        "timeframe": "daily",
        "source": "quant",
        "confidence": 0.8,
        "score": 85.0,
        "entry_price": 5000.0,
        "stop_loss_price": 4500.0,
        "target1_price": 5400.0,
        "target2_price": 5832.0,
        "quantity": 100.0,
        "capital_allocated": 500_000.0,
        "opened_at": datetime.now() - timedelta(days=2),
        "entry_notes": "entry",
        "status": "open",
        "exit_price": None,
        "exit_reason": None,
        "closed_at": None,
        "exit_notes": None,
        "pnl": None,
        "pnl_pct": None,
        "holding_days": None,
    }
    defaults.update(overrides)
    return PaperTradeModel(**defaults)


# ── _signal_to_snapshot ───────────────────────────────────────────────────


class TestSignalToSnapshot:
    def test_maps_core_fields_and_aliases(self) -> None:
        svc = PaperTradingService(session=_make_session())
        sig = {
            "symbol": "فولاد",
            "company_name": "فولاد مبارکه",
            "market": "stock",
            "direction": "buy",
            "timeframe_filter": "weekly",
            "signal_source": "ml",
            "entry": "5000-5100",
            "sl": "4600",
            "target": "5600",
            "rr": "2.1",
            "position_size": "5%",
            "confirmation": "volume",
            "message": "روند صعودی",
            "price": "5100",
            "total_score": 88.0,
            "signal_strength": 0.9,
            "confidence_score": 0.77,
            "generated_at": "2026-01-15T10:00:00Z",
        }
        snap = svc._signal_to_snapshot(sig, batch_id="batch-1")

        assert snap.batch_id == "batch-1"
        assert snap.symbol == "فولاد"
        assert snap.name == "فولاد مبارکه"
        assert snap.market == "stock"
        assert snap.direction == "buy"
        assert snap.timeframe == "weekly"
        assert snap.source == "ml"
        assert snap.entry_zone == "5000-5100"
        assert snap.stop_loss == "4600"
        assert snap.targets == "5600"
        assert snap.risk_reward == "2.1"
        assert snap.position_sizing == "5%"
        assert snap.confirmation_condition == "volume"
        assert snap.reason == "روند صعودی"
        assert snap.price == 5100.0
        assert snap.score == 88.0
        assert snap.strength == 0.9
        assert snap.confidence == 0.77
        assert snap.full_signal == sig
        # ISO timestamp is parsed (UTC) then converted to local naive time —
        # mirror the service logic so the test is timezone-independent.
        expected = (
            datetime.fromisoformat("2026-01-15T10:00:00+00:00")
            .astimezone()
            .replace(tzinfo=None)
        )
        assert snap.generated_at == expected

    def test_missing_optional_fields_become_none(self) -> None:
        svc = PaperTradingService(session=_make_session())
        snap = svc._signal_to_snapshot({"symbol": "خودرو", "direction": "hold"}, batch_id="b")

        assert snap.name == ""
        assert snap.price is None
        assert snap.change_pct is None
        assert snap.score is None
        assert snap.strength is None
        assert snap.confidence is None
        assert snap.market == "stock"
        assert snap.timeframe == "daily"
        assert snap.direction == "hold"
        assert snap.generated_at is not None  # defaults to now


# ── snapshot_signals ──────────────────────────────────────────────────────


class TestSnapshotSignals:
    @pytest.mark.asyncio
    async def test_persists_new_signals(self) -> None:
        session = _make_session()
        svc = PaperTradingService(session=session)
        # No previously journaled keys.
        svc._existing_snapshot_keys = AsyncMock(return_value=set())

        result = await svc.snapshot_signals(
            [{"symbol": "فولاد", "direction": "buy", "timeframe": "daily", "generated_at": "2026-01-15T10:00:00Z"}]
        )

        assert result.success is True
        assert result.value == 1
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedupes_already_journaled_signals(self) -> None:
        session = _make_session()
        svc = PaperTradingService(session=session)
        # Build the snapshot first to learn the *actual* local-date key the
        # service computes (timezone-independent, mirrors _signal_to_snapshot).
        snap = svc._signal_to_snapshot(
            {"symbol": "فولاد", "direction": "buy", "timeframe": "daily", "generated_at": "2026-01-15T10:00:00Z"},
            batch_id="b",
        )
        key = (snap.generated_at.strftime("%Y-%m-%d"), "فولاد", "buy", "daily")
        svc._existing_snapshot_keys = AsyncMock(return_value={key})

        result = await svc.snapshot_signals(
            [{"symbol": "فولاد", "direction": "buy", "timeframe": "daily", "generated_at": "2026-01-15T10:00:00Z"}]
        )

        assert result.success is True
        assert result.value == 0
        session.add.assert_not_called()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_failure_rolls_back(self) -> None:
        session = _make_session()
        session.commit = AsyncMock(side_effect=RuntimeError("db down"))
        svc = PaperTradingService(session=session)
        svc._existing_snapshot_keys = AsyncMock(return_value=set())

        result = await svc.snapshot_signals([{"symbol": "فولاد", "direction": "buy"}])

        assert result.success is False
        assert "db down" in (result.error or "")
        session.rollback.assert_awaited_once()


# ── open_trade ────────────────────────────────────────────────────────────


class TestOpenTrade:
    @pytest.mark.asyncio
    async def test_opens_long_position_from_buy_signal(self) -> None:
        session = _make_session()
        snap = _make_snapshot()
        session.get = AsyncMock(return_value=snap)
        svc = PaperTradingService(session=session)

        result = await svc.open_trade(snapshot_id="psnap_1")

        assert result.success is True
        trade = result.value
        assert trade["symbol"] == "فولاد"
        assert trade["entry_price"] == 5000.0
        assert trade["status"] == "open"
        # Targets/stops derived from signal strings.
        assert trade["stop_loss_price"] == 4500.0
        assert trade["target1_price"] == 5400.0
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_missing_snapshot(self) -> None:
        session = _make_session()
        session.get = AsyncMock(return_value=None)
        svc = PaperTradingService(session=session)

        result = await svc.open_trade(snapshot_id="nope")

        assert result.success is False
        assert "not found" in (result.error or "")

    @pytest.mark.asyncio
    async def test_rejects_non_buy_signal(self) -> None:
        session = _make_session()
        session.get = AsyncMock(return_value=_make_snapshot(direction="hold"))
        svc = PaperTradingService(session=session)

        result = await svc.open_trade(snapshot_id="psnap_1")

        assert result.success is False
        assert "buy" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_rejects_zero_price(self) -> None:
        session = _make_session()
        session.get = AsyncMock(return_value=_make_snapshot(price=None))
        svc = PaperTradingService(session=session)

        result = await svc.open_trade(snapshot_id="psnap_1")

        assert result.success is False
        assert "entry price" in (result.error or "")


# ── close_trade ───────────────────────────────────────────────────────────


class TestCloseTrade:
    @pytest.mark.asyncio
    async def test_computes_pnl_on_close(self) -> None:
        session = _make_session()
        trade = _make_trade()
        session.get = AsyncMock(return_value=trade)
        svc = PaperTradingService(session=session)
        svc._latest_price = AsyncMock(return_value=5400.0)
        svc._record_equity = AsyncMock()

        result = await svc.close_trade(trade_id="ptrade_1", exit_reason="target_hit")

        assert result.success is True
        assert trade.status == "closed"
        assert trade.exit_reason == "target_hit"
        assert trade.exit_price == 5400.0
        assert trade.pnl == (5400.0 - 5000.0) * 100.0  # 40_000
        assert trade.pnl_pct == pytest.approx(8.0)
        svc._record_equity.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_closed_trade(self) -> None:
        session = _make_session()
        session.get = AsyncMock(return_value=_make_trade(status="closed"))
        svc = PaperTradingService(session=session)

        result = await svc.close_trade(trade_id="ptrade_1")

        assert result.success is False
        assert "already closed" in (result.error or "")


# ── auto_close_due_trades ─────────────────────────────────────────────────


class TestAutoCloseDueTrades:
    @pytest.mark.asyncio
    async def test_closes_stop_loss_and_target(self) -> None:
        """A trade below stop-loss and one above target are both auto-closed."""
        session = _make_session()
        # t1: symbol "فولاد" → price 4400 ≤ stop 4500 → stop_loss branch
        # t2: symbol "خودرو" → price 6000 ≥ target1 5400 → target_hit branch
        trade_stop = _make_trade(id="t1", symbol="فولاد")
        trade_target = _make_trade(id="t2", symbol="خودرو")
        session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[trade_stop, trade_target]))))
        )
        svc = PaperTradingService(session=session)

        async def _price(symbol: str, market: str) -> float | None:
            return {"فولاد": 4400.0, "خودرو": 6000.0}.get(symbol)

        svc._latest_price = AsyncMock(side_effect=_price)
        svc.close_trade = AsyncMock(side_effect=lambda trade_id, **kw: Result.ok({"id": trade_id}))

        result = await svc.auto_close_due_trades()

        assert result.success is True
        assert result.value == 2
        # Verify the two distinct exit reasons were actually used.
        reasons = [call.kwargs.get("exit_reason") for call in svc.close_trade.await_args_list]
        assert "stop_loss" in reasons
        assert "target_hit" in reasons

    @pytest.mark.asyncio
    async def test_auto_closes_stale_max_hold_trade(self) -> None:
        """An open trade older than MAX_HOLDING_DAYS is force-closed."""
        session = _make_session()
        stale = _make_trade(id="t3", symbol="فولاد", opened_at=datetime.now() - timedelta(days=MAX_HOLDING_DAYS + 1))
        session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[stale]))))
        )
        svc = PaperTradingService(session=session)
        # Price is inside the normal range (not stop, not target) → max_hold fires.
        svc._latest_price = AsyncMock(return_value=4800.0)
        svc.close_trade = AsyncMock(side_effect=lambda trade_id, **kw: Result.ok({"id": trade_id}))

        result = await svc.auto_close_due_trades()

        assert result.value == 1
        assert svc.close_trade.await_args.kwargs["exit_reason"] == "max_hold"

    @pytest.mark.asyncio
    async def test_no_price_skips_trade(self) -> None:
        session = _make_session()
        trade = _make_trade()
        session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[trade]))))
        )
        svc = PaperTradingService(session=session)
        svc._latest_price = AsyncMock(return_value=None)
        svc.close_trade = AsyncMock()

        result = await svc.auto_close_due_trades()

        assert result.value == 0
        svc.close_trade.assert_not_awaited()


# ── get_dashboard ─────────────────────────────────────────────────────────


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_aggregates_realized_pnl_and_win_rate(self) -> None:
        session = _make_session()
        win = _make_trade(id="w", status="closed", pnl=10_000, pnl_pct=2.0, exit_price=5100.0)
        loss = _make_trade(id="l", status="closed", pnl=-5_000, pnl_pct=-1.0, exit_price=4900.0)
        open_t = _make_trade(id="o", status="open")

        # get_dashboard executes exactly three queries in order:
        # 1. COUNT(*) over all trades
        # 2. closed trades
        # 3. open trades
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar=MagicMock(return_value=3)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[win, loss])))),
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[open_t])))),
            ]
        )
        svc = PaperTradingService(session=session)
        svc._latest_price = AsyncMock(return_value=5200.0)

        dash = await svc.get_dashboard()

        assert dash["total_trades"] == 3
        assert dash["closed_trades"] == 2
        assert dash["open_trades"] == 1
        assert dash["realized_pnl"] == 5000.0  # 10K - 5K
        assert dash["win_rate"] == 50.0
        assert dash["profit_factor"] == 2.0  # 10000 / 5000
        assert dash["equity"] == pytest.approx(DEFAULT_INITIAL_CAPITAL + 5000 + (5200 - 5000) * 100)


# ── helpers ───────────────────────────────────────────────────────────────


class TestHelpers:
    def test_parse_price_extracts_first_number(self) -> None:
        assert PaperTradingService._parse_price("حدود 4,500 ریال") == 4500.0
        assert PaperTradingService._parse_price("4.8") == 4.8
        assert PaperTradingService._parse_price(None) is None
        assert PaperTradingService._parse_price("بدون قیمت") is None

    @pytest.mark.asyncio
    async def test_latest_price_uses_market_table(self) -> None:
        session = _make_session()
        # First query (market table) returns a row; fallback never called.
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda i: 5100.0)
        first = MagicMock(fetchone=MagicMock(return_value=row))
        session.execute = AsyncMock(return_value=first)
        svc = PaperTradingService(session=session)

        price = await svc._latest_price("فولاد", "stock")

        assert price == 5100.0
        assert "brsapi_historical_daily" in str(session.execute.await_args.args[0])

    @pytest.mark.asyncio
    async def test_latest_price_falls_back_to_snapshot(self) -> None:
        session = _make_session()
        empty = MagicMock(fetchone=MagicMock(return_value=None))
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda i: 4900.0)
        snap = MagicMock(fetchone=MagicMock(return_value=row))
        session.execute = AsyncMock(side_effect=[empty, snap])
        svc = PaperTradingService(session=session)

        price = await svc._latest_price("فولاد", "stock")

        assert price == 4900.0
        assert "brsapi_symbol_snapshots" in str(session.execute.await_args_list[1].args[0])
