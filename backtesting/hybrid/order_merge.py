from __future__ import annotations

import heapq
from dataclasses import dataclass
from datetime import datetime

from backtesting.engine.event_builder import MarketEvent
from backtesting.types import OrderEvent


@dataclass(order=True)
class MergedOrder:
    timestamp: datetime
    priority: int = 0
    order_id: str = ""
    source: str = "historical"  # historical, strategy, agent
    event: MarketEvent | None = None
    order: OrderEvent | None = None
    latency_us: float = 0.0


class OrderMergeLayer:
    """Merges historical events, strategy orders, and agent orders into a single time-sorted flow."""

    def __init__(self) -> None:
        self._heap: list[MergedOrder] = []

    def add_historical_event(self, event: MarketEvent) -> None:
        heapq.heappush(
            self._heap,
            MergedOrder(
                timestamp=event.timestamp,
                priority=event.priority,
                order_id=event.event_id,
                source="historical",
                event=event,
            ),
        )

    def add_strategy_orders(self, orders: list[OrderEvent], timestamp: datetime) -> None:
        for i, order in enumerate(orders):
            heapq.heappush(
                self._heap,
                MergedOrder(
                    timestamp=timestamp,
                    priority=10,
                    order_id=f"strategy_{timestamp.timestamp()}_{i}",
                    source="strategy",
                    order=order,
                ),
            )

    def add_agent_orders(self, orders: list[OrderEvent], timestamp: datetime, latency_us: float = 50.0) -> None:
        for i, order in enumerate(orders):
            heapq.heappush(
                self._heap,
                MergedOrder(
                    timestamp=timestamp,
                    priority=20,
                    order_id=f"agent_{timestamp.timestamp()}_{i}",
                    source="agent",
                    order=order,
                    latency_us=latency_us,
                ),
            )

    def add_custom_order(
        self,
        timestamp: datetime,
        source: str,
        order: OrderEvent | None = None,
        event: MarketEvent | None = None,
        priority: int = 5,
        latency_us: float = 0.0,
    ) -> None:
        heapq.heappush(
            self._heap,
            MergedOrder(
                timestamp=timestamp,
                priority=priority,
                order_id=f"{source}_{timestamp.timestamp()}",
                source=source,
                event=event,
                order=order,
                latency_us=latency_us,
            ),
        )

    def pop_next(self) -> MergedOrder | None:
        if self._heap:
            return heapq.heappop(self._heap)
        return None

    def peek_next(self) -> MergedOrder | None:
        if self._heap:
            return self._heap[0]
        return None

    def __len__(self) -> int:
        return len(self._heap)

    def clear(self) -> None:
        self._heap.clear()

    def merge_flows(
        self,
        historical_events: list[MarketEvent],
        strategy_orders: list[tuple[datetime, list[OrderEvent]]],
        agent_orders: list[tuple[datetime, list[OrderEvent]]],
    ) -> list[MergedOrder]:
        """Merge all three flows at once."""
        self.clear()

        for event in historical_events:
            self.add_historical_event(event)

        for ts, orders in strategy_orders:
            self.add_strategy_orders(orders, ts)

        for ts, orders in agent_orders:
            self.add_agent_orders(orders, ts)

        result: list[MergedOrder] = []
        while self._heap:
            item = heapq.heappop(self._heap)
            result.append(item)

        return result

    def get_flow_mix(self) -> dict[str, int]:
        """Get the count of orders by source type."""
        counts: dict[str, int] = {"historical": 0, "strategy": 0, "agent": 0}
        for item in self._heap:
            source = item.source
            counts[source] = counts.get(source, 0) + 1
        return counts
