"""Regression tests for Phase 1 plan fixes (.claude/plan.md).

F3: double-fill in MicrostructureEngine — a single TRADE/AUCTION event must
not generate simulated fill volume exceeding the real executed trade volume.
"""

from __future__ import annotations

from datetime import UTC, datetime

from backtesting.engine.event_builder import EventBuilder
from backtesting.microstructure.microstructure_engine import MicrostructureEngine
from backtesting.microstructure.queue_state import SimulatedOrder


def _seeded_engine(bid_qty: int = 1000, ask_qty: int = 1000) -> MicrostructureEngine:
    engine = MicrostructureEngine()
    queue = engine.get_or_create_queue("X")
    queue.add_order(
        SimulatedOrder(order_id="b1", side="buy", price=99.0, quantity=bid_qty, instrument_id="X")
    )
    queue.add_order(
        SimulatedOrder(order_id="a1", side="sell", price=101.0, quantity=ask_qty, instrument_id="X")
    )
    for order in queue.bids + queue.asks:
        order.queue_ahead = 0
    return engine


class TestF3DoubleFillFix:
    def test_trade_event_fills_at_most_the_traded_volume(self):
        engine = _seeded_engine()
        trade_event = EventBuilder().build_trade(
            "e1", datetime(2026, 1, 1, tzinfo=UTC), "X", "tse", price=100.0, volume=500
        )
        fills = engine.process_event(trade_event)
        total_filled = sum(f.quantity for f in fills)
        assert total_filled == 500, (
            f"a 500-volume trade produced {total_filled} filled units — "
            "fills must not exceed real executed volume"
        )

    def test_auction_fills_at_most_the_auction_volume(self):
        engine = _seeded_engine()
        auction_fills = engine._process_auction_fills("X", price=100.0, volume=400)
        total_filled = sum(f.quantity for f in auction_fills)
        assert total_filled == 400

    def test_large_trade_still_bounded_by_available_liquidity(self):
        # Bid/ask queues only have 1000 each; a 3000-volume trade is split
        # 1500/1500 but each side can only supply 1000 → total filled <= 2000,
        # never anywhere near the old double-counted 6000.
        engine = _seeded_engine(bid_qty=1000, ask_qty=1000)
        trade_event = EventBuilder().build_trade(
            "e2", datetime(2026, 1, 1, tzinfo=UTC), "X", "tse", price=100.0, volume=3000
        )
        fills = engine.process_event(trade_event)
        total_filled = sum(f.quantity for f in fills)
        assert total_filled <= 2000
