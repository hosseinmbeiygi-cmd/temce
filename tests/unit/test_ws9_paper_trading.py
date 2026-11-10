"""WS9: Gold Desk paper trading — separate paper account + team view.

RED (before fixes):
  1. src.gold_desk.paper_trading does not exist — all tests ImportError.
  2. PaperGoldTrade dataclass does not exist.
  3. PaperGoldPosition dataclass does not exist.
  4. PaperGoldPortfolio dataclass does not exist.
  5. compute_paper_positions() does not exist.
  6. InsufficientPaperHoldingError does not exist.
  7. create_paper_portfolio() does not exist.
  8. add_paper_trade() does not exist.
  9. get_paper_portfolio() does not exist.
  10. list_paper_portfolios() does not exist.

GREEN (after fixes):
  1. src/gold_desk/paper_trading.py created:
     - PaperGoldTrade (frozen dataclass): trade_id, portfolio_id, symbol,
       direction ("buy"|"sell"), quantity, price, traded_at, note.
     - PaperGoldPosition (frozen dataclass): symbol, quantity, avg_cost,
       total_cost.
     - PaperGoldPortfolio (frozen dataclass): portfolio_id, display_name,
       created_at, initial_cash, trades.
     - InsufficientPaperHoldingError raised when sell > held quantity.
     - compute_paper_positions(trades) → list[PaperGoldPosition] using
       weighted average cost; raises InsufficientPaperHoldingError if
       oversell attempted.
     - create_paper_portfolio(id, name, cash, cache) → saves to Redis.
     - add_paper_trade(trade, cache) → validates positions, saves to Redis.
     - get_paper_portfolio(id, cache) → None if not found.
     - list_paper_portfolios(cache) → all portfolios (team view).

WS9 scope: Redis-backed (TTL 30 days). No DB. Completely separate from
both portfolio.py (real trades) and services/paper_trading_service.py
(stocks paper trading). Team view = all portfolios visible to all callers.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _MemCache:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None):
        self._store[key] = value


# ─── 1. Import check ─────────────────────────────────────────────────────────

def test_import_paper_trading():
    """src.gold_desk.paper_trading must be importable with all public names.

    RED: module does not exist.
    GREEN: module created with all required names.
    """
    from src.gold_desk.paper_trading import (  # noqa: F401
        InsufficientPaperHoldingError,
        PaperGoldPortfolio,
        PaperGoldPosition,
        PaperGoldTrade,
        add_paper_trade,
        compute_paper_positions,
        create_paper_portfolio,
        get_paper_portfolio,
        list_paper_portfolios,
    )


# ─── 2. PaperGoldTrade ───────────────────────────────────────────────────────

def test_paper_gold_trade_has_required_fields():
    """PaperGoldTrade must have trade_id, portfolio_id, symbol, direction,
    quantity, price, traded_at.

    RED: class does not exist.
    GREEN: frozen dataclass with all fields.
    """
    from src.gold_desk.paper_trading import PaperGoldTrade

    t = PaperGoldTrade(
        trade_id="t1",
        portfolio_id="team-alpha",
        symbol="IR_COIN_EMAMI",
        direction="buy",
        quantity=5.0,
        price=50_000_000.0,
        traded_at="2026-11-10T09:00:00Z",
    )
    assert t.trade_id == "t1"
    assert t.direction == "buy"
    assert t.quantity == 5.0
    assert t.note is None


def test_paper_gold_trade_to_dict():
    """to_dict() must include all fields.

    RED: class does not exist.
    GREEN: returns serializable dict.
    """
    from src.gold_desk.paper_trading import PaperGoldTrade

    t = PaperGoldTrade(
        trade_id="t2",
        portfolio_id="p1",
        symbol="XAUUSD",
        direction="sell",
        quantity=1.0,
        price=2600.0,
        traded_at="2026-11-10T10:00:00Z",
        note="test sell",
    )
    d = t.to_dict()
    assert d["direction"] == "sell"
    assert d["note"] == "test sell"
    assert "trade_id" in d


# ─── 3. compute_paper_positions ──────────────────────────────────────────────

def test_compute_positions_buy_only():
    """Single buy → position with correct quantity and avg_cost.

    RED: function does not exist.
    GREEN: positions list has one entry matching the buy.
    """
    from src.gold_desk.paper_trading import PaperGoldTrade, compute_paper_positions

    trades = [
        PaperGoldTrade(
            trade_id="t1", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="buy", quantity=3.0, price=60_000_000.0,
            traded_at="2026-11-10T09:00:00Z",
        )
    ]
    positions = compute_paper_positions(trades)
    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "IR_COIN_EMAMI"
    assert pos.quantity == pytest.approx(3.0)
    assert pos.avg_cost == pytest.approx(60_000_000.0)
    assert pos.total_cost == pytest.approx(180_000_000.0)


def test_compute_positions_weighted_avg_on_multiple_buys():
    """Two buys at different prices → weighted average cost.

    RED: function does not exist.
    GREEN: avg_cost = (q1*p1 + q2*p2) / (q1 + q2).
    """
    from src.gold_desk.paper_trading import PaperGoldTrade, compute_paper_positions

    trades = [
        PaperGoldTrade(
            trade_id="t1", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="buy", quantity=2.0, price=60_000_000.0,
            traded_at="2026-11-10T09:00:00Z",
        ),
        PaperGoldTrade(
            trade_id="t2", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="buy", quantity=3.0, price=65_000_000.0,
            traded_at="2026-11-10T10:00:00Z",
        ),
    ]
    positions = compute_paper_positions(trades)
    pos = {p.symbol: p for p in positions}["IR_COIN_EMAMI"]

    expected_avg = (2 * 60_000_000 + 3 * 65_000_000) / 5
    assert pos.quantity == pytest.approx(5.0)
    assert pos.avg_cost == pytest.approx(expected_avg)


def test_compute_positions_sell_reduces_quantity():
    """Buy then partial sell → reduced quantity, same avg_cost.

    RED: function does not exist.
    GREEN: quantity = buy_qty - sell_qty; avg_cost unchanged.
    """
    from src.gold_desk.paper_trading import PaperGoldTrade, compute_paper_positions

    trades = [
        PaperGoldTrade(
            trade_id="t1", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="buy", quantity=5.0, price=60_000_000.0,
            traded_at="2026-11-10T09:00:00Z",
        ),
        PaperGoldTrade(
            trade_id="t2", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="sell", quantity=2.0, price=65_000_000.0,
            traded_at="2026-11-10T10:00:00Z",
        ),
    ]
    positions = compute_paper_positions(trades)
    pos = {p.symbol: p for p in positions}["IR_COIN_EMAMI"]

    assert pos.quantity == pytest.approx(3.0)
    assert pos.avg_cost == pytest.approx(60_000_000.0)  # unchanged


def test_compute_positions_fully_closed_excludes_symbol():
    """Buy all then sell all → position removed (quantity == 0 not returned).

    RED: function does not exist.
    GREEN: symbols with zero quantity are excluded from result.
    """
    from src.gold_desk.paper_trading import PaperGoldTrade, compute_paper_positions

    trades = [
        PaperGoldTrade(
            trade_id="t1", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="buy", quantity=3.0, price=60_000_000.0,
            traded_at="2026-11-10T09:00:00Z",
        ),
        PaperGoldTrade(
            trade_id="t2", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="sell", quantity=3.0, price=65_000_000.0,
            traded_at="2026-11-10T10:00:00Z",
        ),
    ]
    positions = compute_paper_positions(trades)
    assert positions == [] or all(p.quantity > 1e-9 for p in positions)


def test_compute_positions_multiple_independent_symbols():
    """Trades on two symbols yield independent positions.

    RED: function does not exist.
    GREEN: positions dict has an entry for each symbol with correct qty.
    """
    from src.gold_desk.paper_trading import PaperGoldTrade, compute_paper_positions

    trades = [
        PaperGoldTrade(
            trade_id="t1", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="buy", quantity=2.0, price=60_000_000.0,
            traded_at="2026-11-10T09:00:00Z",
        ),
        PaperGoldTrade(
            trade_id="t2", portfolio_id="p1", symbol="XAUUSD",
            direction="buy", quantity=1.5, price=2600.0,
            traded_at="2026-11-10T09:30:00Z",
        ),
    ]
    positions = {p.symbol: p for p in compute_paper_positions(trades)}
    assert "IR_COIN_EMAMI" in positions
    assert "XAUUSD" in positions
    assert positions["IR_COIN_EMAMI"].quantity == pytest.approx(2.0)
    assert positions["XAUUSD"].quantity == pytest.approx(1.5)


def test_compute_positions_oversell_raises():
    """Selling more than the held quantity must raise InsufficientPaperHoldingError.

    RED: function/error do not exist.
    GREEN: raises InsufficientPaperHoldingError with symbol in message.
    """
    from src.gold_desk.paper_trading import (
        InsufficientPaperHoldingError,
        PaperGoldTrade,
        compute_paper_positions,
    )

    trades = [
        PaperGoldTrade(
            trade_id="t1", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="buy", quantity=1.0, price=60_000_000.0,
            traded_at="2026-11-10T09:00:00Z",
        ),
        PaperGoldTrade(
            trade_id="t2", portfolio_id="p1", symbol="IR_COIN_EMAMI",
            direction="sell", quantity=2.0, price=65_000_000.0,
            traded_at="2026-11-10T10:00:00Z",
        ),
    ]
    with pytest.raises(InsufficientPaperHoldingError, match="IR_COIN_EMAMI"):
        compute_paper_positions(trades)


# ─── 4. create_paper_portfolio + get_paper_portfolio ─────────────────────────

def test_create_and_get_paper_portfolio():
    """create_paper_portfolio() then get_paper_portfolio() must round-trip.

    RED: functions do not exist.
    GREEN: creates portfolio in cache; get retrieves it with matching fields.
    """
    from src.gold_desk.paper_trading import create_paper_portfolio, get_paper_portfolio

    cache = _MemCache()
    asyncio.run(create_paper_portfolio(
        portfolio_id="team-alpha",
        display_name="تیم آلفا",
        initial_cash=1_000_000_000.0,
        cache=cache,
    ))

    portfolio = asyncio.run(get_paper_portfolio("team-alpha", cache=cache))
    assert portfolio is not None
    assert portfolio.portfolio_id == "team-alpha"
    assert portfolio.display_name == "تیم آلفا"
    assert portfolio.initial_cash == pytest.approx(1_000_000_000.0)
    assert list(portfolio.trades) == []


def test_get_paper_portfolio_returns_none_on_miss():
    """get_paper_portfolio() must return None for an unknown portfolio_id.

    RED: function does not exist.
    GREEN: returns None, never raises.
    """
    from src.gold_desk.paper_trading import get_paper_portfolio

    cache = _MemCache()
    result = asyncio.run(get_paper_portfolio("does-not-exist", cache=cache))
    assert result is None


# ─── 5. add_paper_trade ──────────────────────────────────────────────────────

def test_add_paper_trade_records_trade():
    """add_paper_trade() must append the trade to the portfolio.

    RED: function does not exist.
    GREEN: trade retrievable via get_paper_portfolio().
    """
    from src.gold_desk.paper_trading import (
        PaperGoldTrade,
        add_paper_trade,
        create_paper_portfolio,
        get_paper_portfolio,
    )

    cache = _MemCache()
    asyncio.run(create_paper_portfolio("p1", "Portfolio 1", 500_000_000.0, cache=cache))

    trade = PaperGoldTrade(
        trade_id=str(uuid.uuid4()),
        portfolio_id="p1",
        symbol="IR_COIN_EMAMI",
        direction="buy",
        quantity=2.0,
        price=55_000_000.0,
        traded_at="2026-11-10T10:00:00Z",
    )
    asyncio.run(add_paper_trade(trade, cache=cache))

    portfolio = asyncio.run(get_paper_portfolio("p1", cache=cache))
    assert portfolio is not None
    assert len(list(portfolio.trades)) == 1
    assert list(portfolio.trades)[0].trade_id == trade.trade_id


def test_add_paper_trade_rejects_oversell():
    """add_paper_trade() must reject a sell that exceeds the held quantity.

    RED: function does not exist.
    GREEN: raises InsufficientPaperHoldingError; portfolio is NOT modified.
    """
    from src.gold_desk.paper_trading import (
        InsufficientPaperHoldingError,
        PaperGoldTrade,
        add_paper_trade,
        create_paper_portfolio,
        get_paper_portfolio,
    )

    cache = _MemCache()
    asyncio.run(create_paper_portfolio("p2", "Portfolio 2", 500_000_000.0, cache=cache))

    sell_trade = PaperGoldTrade(
        trade_id="bad-sell",
        portfolio_id="p2",
        symbol="IR_COIN_EMAMI",
        direction="sell",
        quantity=5.0,
        price=55_000_000.0,
        traded_at="2026-11-10T11:00:00Z",
    )
    with pytest.raises(InsufficientPaperHoldingError):
        asyncio.run(add_paper_trade(sell_trade, cache=cache))

    portfolio = asyncio.run(get_paper_portfolio("p2", cache=cache))
    assert portfolio is not None
    assert len(list(portfolio.trades)) == 0  # not modified


# ─── 6. list_paper_portfolios — team view ────────────────────────────────────

def test_list_paper_portfolios_returns_all():
    """list_paper_portfolios() (team view) must return all created portfolios.

    RED: function does not exist.
    GREEN: returns a list including every created portfolio.
    """
    from src.gold_desk.paper_trading import create_paper_portfolio, list_paper_portfolios

    cache = _MemCache()
    asyncio.run(create_paper_portfolio("team-a", "Team A", 1e9, cache=cache))
    asyncio.run(create_paper_portfolio("team-b", "Team B", 2e9, cache=cache))

    portfolios = asyncio.run(list_paper_portfolios(cache=cache))
    ids = {p.portfolio_id for p in portfolios}
    assert "team-a" in ids
    assert "team-b" in ids


def test_list_paper_portfolios_empty_cache():
    """list_paper_portfolios() on empty cache must return [], not raise.

    RED: function does not exist.
    GREEN: returns empty list.
    """
    from src.gold_desk.paper_trading import list_paper_portfolios

    cache = _MemCache()
    result = asyncio.run(list_paper_portfolios(cache=cache))
    assert result == []
