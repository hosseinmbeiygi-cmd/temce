"""Phase 1.5b code-layer tests — G-3 fix, NULL assertion, audit log.

RED baseline: three behaviours that do NOT hold before the fix.
GREEN: they all hold after the fix.
"""
from __future__ import annotations

import logging
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_desk.portfolio import HoldingNotFoundError, get_active_holding


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_holding(holding_id: int, symbol: str, user_id: str | None) -> MagicMock:
    h = MagicMock()
    h.id = holding_id
    h.symbol = symbol
    h.user_id = user_id
    h.deleted_at = None
    return h


# ─── G-3: allow_any_owner must inherit user_id from the holding ──────────────

@pytest.mark.asyncio
async def test_sell_trade_inherits_holding_user_id_when_allow_any_owner():
    """When allow_any_owner=True, the trade must carry the holding's user_id,
    not the caller's (admin) user_id.

    RED: _record_sell creates the trade with user_id=caller_user_id ("admin").
    GREEN: trade.user_id == "user123" (the holding owner).
    """
    from src.gold_desk import portfolio as _p

    holding = _make_holding(42, "GOLD_GRAM_18K", "user123")

    # Minimal session mock — flush and get do nothing, state is inspected via
    # the GoldTradeModel constructor argument captured in created_trades.
    created_trades: list = []

    class _TrackingSession:
        async def execute(self, stmt):
            r = MagicMock()
            r.scalar_one_or_none.return_value = holding
            return r

        async def get(self, model, pk):
            return holding

        async def flush(self, objs=None):
            pass

        def add(self, obj):
            created_trades.append(obj)

    with patch.object(_p, "get_active_holding", AsyncMock(return_value=holding)):
        with patch.object(_p, "_consume_lots", AsyncMock(return_value={"realized_cost_irt": 100.0})):
            trade = await _p._record_sell(
                _TrackingSession(),
                symbol="GOLD_GRAM_18K",
                quantity=1.0,
                price=5_000_000.0,
                amount_irt=5_000_000.0,
                fee_irt=0.0,
                holding_id=42,
                note=None,
                user_id="admin_id",
                allow_any_owner=True,
            )

    assert trade.user_id == "user123", (
        f"Expected trade.user_id='user123' (holding owner) but got {trade.user_id!r}. "
        "G-3: allow_any_owner must inherit user_id from the holding, not the caller."
    )


@pytest.mark.asyncio
async def test_sell_trade_keeps_caller_user_id_when_not_allow_any_owner():
    """When allow_any_owner=False, user_id must stay as the caller's (normal case)."""
    from src.gold_desk import portfolio as _p

    holding = _make_holding(42, "GOLD_GRAM_18K", "user123")

    with patch.object(_p, "get_active_holding", AsyncMock(return_value=holding)):
        with patch.object(_p, "_consume_lots", AsyncMock(return_value={"realized_cost_irt": 100.0})):
            trade = await _p._record_sell(
                MagicMock(**{"execute": AsyncMock(), "get": AsyncMock(return_value=holding),
                             "flush": AsyncMock(), "add": MagicMock()}),
                symbol="GOLD_GRAM_18K",
                quantity=1.0,
                price=5_000_000.0,
                amount_irt=5_000_000.0,
                fee_irt=0.0,
                holding_id=42,
                note=None,
                user_id="user123",
                allow_any_owner=False,
            )

    assert trade.user_id == "user123"


# ─── NULL assertion in get_active_holding ────────────────────────────────────

@pytest.mark.asyncio
async def test_get_active_holding_raises_on_null_user_id():
    """A holding whose user_id is NULL (legacy/corrupt row) must be rejected
    with HoldingNotFoundError, not silently returned.

    RED: get_active_holding returns the holding without checking user_id=None.
    GREEN: raises HoldingNotFoundError when holding.user_id is None.
    """
    null_user_holding = _make_holding(99, "GOLD_GRAM_18K", None)
    null_user_holding.deleted_at = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = null_user_holding

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HoldingNotFoundError, match="no owner"):
        await get_active_holding(mock_session, 99, user_id=None)


@pytest.mark.asyncio
async def test_get_active_holding_allows_valid_user_id():
    """A holding with a valid user_id is returned normally (regression guard)."""
    h = _make_holding(5, "GOLD_GRAM_18K", "user_abc")
    h.deleted_at = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = h

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await get_active_holding(mock_session, 5, user_id="user_abc")
    assert result is h


# ─── Audit log for admin hard-delete ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_hard_delete_holding_emits_audit_log(caplog):
    """When force=True (hard-delete), a WARNING must be emitted with
    holding_id, user_id, and deleted_by before the row is removed.

    RED: no log emitted on hard-delete.
    GREEN: caplog contains a WARNING with 'hard-delete' and the holding_id.
    """
    from src.gold_desk.api import delete_holding

    h = _make_holding(77, "GOLD_GRAM_18K", "owner_user")
    h.id = 77

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=h)
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    current_user = {"sub": "admin_id", "roles": ["admin"]}

    with caplog.at_level(logging.WARNING, logger="src.gold_desk.api"):
        await delete_holding(
            holding_id=77,
            force=True,
            session=mock_session,
            current_user=current_user,
        )

    assert any(
        "hard-delete" in r.message and "77" in r.message
        for r in caplog.records
    ), (
        "Expected a WARNING log containing 'hard-delete' and holding_id=77, "
        f"but got: {[r.message for r in caplog.records]}"
    )
