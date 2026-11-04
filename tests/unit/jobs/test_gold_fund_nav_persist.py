"""``_persist_fund_nav`` must not turn a missing quote into a 0% premium.

The production table showed rows like ``market_price=0, bubble_pct=0`` for
every fund; the feature layer then read ``gold_fund_pnav_pct = 0.0``.  A fund
without a traded price has no P/NAV observation and must not be persisted.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from brsapi.jobs.gold_desk_jobs import _persist_fund_nav


def _fund(*, symbol: str, nav: float, price: float | None, bubble: float | None):
    return SimpleNamespace(
        symbol=symbol,
        fund_name=symbol,
        nav_per_unit=nav,
        market_price=price,
        bubble_pct=bubble,
        real_buy_value=0,
        real_sell_value=0,
        bpr=0.0,
    )


@pytest.mark.asyncio
async def test_persist_fund_nav_skips_a_missing_market_price() -> None:
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    session.commit = AsyncMock()
    snap = SimpleNamespace(
        snapshot_at=datetime(2026, 10, 14, 12, 0),
        funds=[
            _fund(symbol="missing", nav=1_000_000.0, price=None, bubble=None),
            _fund(symbol="traded", nav=1_000_000.0, price=980_000.0, bubble=-2.0),
        ],
    )

    written = await _persist_fund_nav(session, snap)

    assert written == 1
    assert session.add.call_count == 1
    row = session.add.call_args.args[0]
    assert row.symbol == "traded"
    assert row.market_price == 980_000.0
    assert row.bubble_pct == -2.0


@pytest.mark.asyncio
async def test_persist_fund_nav_skips_zero_price_instead_of_coercing() -> None:
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    session.commit = AsyncMock()
    snap = SimpleNamespace(
        snapshot_at=datetime(2026, 10, 14, 12, 0),
        funds=[_fund(symbol="zero", nav=1_868_910.0, price=0.0, bubble=0.0)],
    )

    written = await _persist_fund_nav(session, snap)

    assert written == 0
    session.add.assert_not_called()
