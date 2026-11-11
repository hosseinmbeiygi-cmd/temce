"""Phase 1 deferred items 5 & 6 — TDD red→green.

Item 5 (FIFO sell): _consume_lots_by_symbol() has two bugs:
  Bug A — second loop uses `quantity` (total) not `remaining` per holding,
           so excess quantity is consumed from later holdings.
  Bug B — buy_amount_irt cost formula divides by already-reduced qty instead
           of original qty, producing wrong remaining cost.

Item 6 (token lifecycle): save_token() uses cache.set(ttl=None) which
  falls back to self._default_ttl via setex(), so API tokens expire after
  the default cache TTL instead of being persistent. The index uses
  set_persistent() correctly; the hash and meta keys do not.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("GOLD_API_TOKEN_SALT", "test-salt-value")


# ─── Item 5: FIFO sell ────────────────────────────────────────────────────────

def _holding(holding_id, qty, cost, symbol="GOLD_GRAM_18K", user_id="user1"):
    h = MagicMock()
    h.id = holding_id
    h.quantity = qty
    h.buy_amount_irt = cost
    h.symbol = symbol
    h.user_id = user_id
    h.deleted_at = None
    h.bought_at = datetime(2026, 1, 1, holding_id)
    return h


@pytest.mark.asyncio
async def test_fifo_consume_by_symbol_does_not_over_consume_later_holdings():
    """Bug A: when selling 3 from [H1:qty=5, H2:qty=5], only H1 is consumed.

    RED: second holding also loses 3 units (loop uses `quantity`, not `remaining`).
    GREEN: H2.quantity stays at 5.
    """
    from src.gold_desk.portfolio import _consume_lots_by_symbol, _QTY_EPS

    h1 = _holding(1, qty=5.0, cost=10.0)
    h2 = _holding(2, qty=5.0, cost=10.0)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [h1, h2]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await _consume_lots_by_symbol(
        mock_session, symbol="GOLD_GRAM_18K", quantity=3.0, user_id="user1"
    )

    assert h2.quantity == pytest.approx(5.0, abs=_QTY_EPS), (
        f"Bug A: H2.quantity should be 5.0 (untouched) but got {h2.quantity}. "
        "_consume_lots_by_symbol must track `remaining` per holding, not reuse `quantity`."
    )
    assert h1.quantity == pytest.approx(2.0, abs=_QTY_EPS), (
        f"H1 should have 2.0 left after selling 3 from 5, got {h1.quantity}."
    )


@pytest.mark.asyncio
async def test_fifo_consume_buy_amount_irt_uses_original_quantity():
    """Bug B: remaining cost must use original qty for unit_cost, not post-reduction qty.

    Example: H1 qty=5, cost=10. Sell 3.
      unit_cost = 10/5 = 2
      consumed_cost = 3*2 = 6
      remaining_cost = 10 - 6 = 4

    RED: formula divides by already-reduced qty=2 → 10 - 3*(10/2) = max(-5,0) = 0.
    GREEN: remaining cost = 4.0.
    """
    from src.gold_desk.portfolio import _consume_lots_by_symbol, _QTY_EPS

    h1 = _holding(1, qty=5.0, cost=10.0)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [h1]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await _consume_lots_by_symbol(
        mock_session, symbol="GOLD_GRAM_18K", quantity=3.0, user_id="user1"
    )

    assert h1.buy_amount_irt == pytest.approx(4.0, abs=0.01), (
        f"Bug B: remaining cost should be 4.0 but got {h1.buy_amount_irt}. "
        "Unit cost must use the ORIGINAL quantity (5), not the reduced (2)."
    )


@pytest.mark.asyncio
async def test_fifo_consume_realized_cost_is_correct():
    """The returned realized_cost_irt must equal consumed qty * unit_cost."""
    from src.gold_desk.portfolio import _consume_lots_by_symbol

    h1 = _holding(1, qty=5.0, cost=10.0)  # unit_cost = 2.0 IRT

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [h1]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await _consume_lots_by_symbol(
        mock_session, symbol="GOLD_GRAM_18K", quantity=3.0, user_id="user1"
    )

    assert result["realized_cost_irt"] == pytest.approx(6.0, abs=0.01), (
        f"realized_cost_irt should be 6.0 (3 * 2.0) but got {result['realized_cost_irt']}."
    )


# ─── Item 6: API token lifecycle ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_token_uses_set_persistent_not_setex():
    """save_token() must use set_persistent() for hash and meta keys.

    RED: save_token calls cache.set(ttl=None) which falls back to default_ttl
         via setex — tokens expire silently after the default cache TTL.
    GREEN: set_persistent() is called for hash and meta keys.
    """
    from src.gold_desk.api_token import generate_token, save_token

    plain, info = generate_token("test", ["read"])

    set_calls: list[str] = []
    persistent_calls: list[str] = []

    class _TrackingCache:
        async def set(self, key: str, value, ttl=None):
            set_calls.append(key)

        async def set_persistent(self, key: str, value) -> bool:
            persistent_calls.append(key)
            return True

        async def get(self, key: str):
            return []

    tracking = _TrackingCache()
    with patch("core.cache.get_cache", return_value=tracking):
        await save_token(plain, info)

    hash_key = next((k for k in set_calls + persistent_calls if ":hash:" in k), None)
    meta_key = next((k for k in set_calls + persistent_calls if ":meta:" in k), None)

    assert hash_key in persistent_calls, (
        f"Bug: hash key {hash_key!r} was stored with cache.set() (uses default TTL), "
        "not set_persistent(). Tokens will expire after default_ttl."
    )
    assert meta_key in persistent_calls, (
        f"Bug: meta key {meta_key!r} was stored with cache.set() (uses default TTL), "
        "not set_persistent(). Token metadata will expire after default_ttl."
    )


@pytest.mark.asyncio
async def test_verify_token_update_uses_set_persistent():
    """verify_token() updates last_used_at — must also use set_persistent."""
    from src.gold_desk.api_token import generate_token, info_to_dict, verify_token

    plain, info = generate_token("test", ["read"])
    payload = info_to_dict(info)
    payload["token_hash"] = f"fakehash_{info.token_id}"

    set_calls: list[str] = []
    persistent_calls: list[str] = []

    class _TrackingCache:
        async def set(self, key: str, value, ttl=None):
            set_calls.append(key)

        async def set_persistent(self, key: str, value) -> bool:
            persistent_calls.append(key)
            return True

        async def get(self, key: str):
            if ":hash:" in key:
                return dict(payload)
            if ":meta:" in key:
                return dict(payload)
            return None

    tracking = _TrackingCache()
    with patch("core.cache.get_cache", return_value=tracking):
        await verify_token(plain)

    update_via_set = [k for k in set_calls if ":hash:" in k or ":meta:" in k]
    assert not update_via_set, (
        f"verify_token updated {update_via_set} with cache.set() (uses TTL). "
        "Must use set_persistent() to avoid shortening the token's lifetime."
    )
