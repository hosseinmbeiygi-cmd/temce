"""Phase 1 — P&L null-safety tests.

Two zero-division guards in get_holdings_grouped currently return 0 instead of None:

  pnl_pct = (pnl_irt / total_cost_sym * 100) if total_cost_sym else 0   ← line ~474
  total_pnl_pct = (total_pnl / priced_cost * 100) if priced_cost else 0  ← line ~499

RED: both assertions fail.  After fix: return None so callers know no data is
available rather than a fabricated zero.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _FakeHolding:
    """Minimal stand-in for GoldHoldingModel."""

    def __init__(self, symbol: str, display_name: str, quantity: float, buy_amount_irt: float):
        self.symbol = symbol
        self.display_name = display_name
        self.quantity = quantity
        self.buy_amount_irt = buy_amount_irt
        self.deleted_at = None
        self.user_id = "u1"
        self.id = 1
        self.bought_at = datetime(2026, 1, 1)


def _make_session(holdings: list[_FakeHolding]):
    """Return an AsyncMock session whose execute().scalars().all() yields holdings."""
    scalars = MagicMock()
    scalars.all.return_value = holdings
    result = MagicMock()
    result.scalars.return_value = scalars
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_unpriced_holdings_give_none_total_pnl_pct():
    """When ALL holdings lack a current price, total_pnl_pct must be None, not 0."""
    from src.gold_desk.portfolio import get_holdings_grouped

    h = _FakeHolding("IR_GOLD_18K", "طلای ۱۸ عیار", quantity=10.0, buy_amount_irt=1_000_000)
    session = _make_session([h])
    prices: dict[str, float] = {}  # no price available

    summary = await get_holdings_grouped(session, prices)

    assert summary.unpriced_holdings == 1
    assert summary.total_pnl_pct is None, (
        f"total_pnl_pct should be None when priced_cost==0, got {summary.total_pnl_pct!r}"
    )


@pytest.mark.asyncio
async def test_zero_cost_holding_gives_none_pnl_pct():
    """A holding with buy_amount_irt==0 and a live price: pnl_pct must be None."""
    from src.gold_desk.portfolio import get_holdings_grouped

    h = _FakeHolding("IR_GOLD_18K", "طلای ۱۸ عیار", quantity=10.0, buy_amount_irt=0.0)
    session = _make_session([h])
    prices = {"IR_GOLD_18K": 5_000_000.0}

    summary = await get_holdings_grouped(session, prices)

    pnl = summary.holdings[0]
    assert pnl.pnl_pct is None, (
        f"pnl_pct should be None when cost_basis==0, got {pnl.pnl_pct!r}"
    )
