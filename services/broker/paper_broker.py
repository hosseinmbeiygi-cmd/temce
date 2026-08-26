"""Paper Broker — PoC فاز ۱-۱: شبیه‌سازی بدون پول واقعی."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrokerResult:
    broker_order_id: str
    status: str  # accepted | filled | rejected | cancelled | partial
    filled_qty: int = 0
    avg_price: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class PaperBrokerAdapter:
    """Paper broker — دفتر داخلی، idempotent، بدون اتصال خارجی."""

    def __init__(self) -> None:
        self._orders: dict[str, BrokerResult] = {}  # idempotency_key -> result
        self._by_id: dict[str, BrokerResult] = {}

    def _key(self, proposal_id: str, price: float) -> str:
        return hashlib.sha256(f"{proposal_id}:{price}".encode()).hexdigest()[:16]

    async def send_order(self, proposal: dict[str, Any], idempotency_key: str | None = None) -> BrokerResult:
        key = idempotency_key or self._key(proposal["id"], proposal.get("proposed_price", 0))
        if key in self._orders:
            return self._orders[key]  # idempotent replay
        await asyncio.sleep(0.05)  # simulate latency
        # Risk قبلاً چک شده — اینجا فقط fill شبیه‌سازی
        qty = sum(leg.get("quantity", 1) for leg in proposal.get("legs", []))
        result = BrokerResult(
            broker_order_id=f"paper-{uuid.uuid4().hex[:8]}",
            status="filled",
            filled_qty=qty,
            avg_price=float(proposal.get("proposed_price", 0)),
            raw={"proposal_id": proposal["id"], "ts": time.time()},
        )
        self._orders[key] = result
        self._by_id[result.broker_order_id] = result
        return result

    async def cancel_order(self, broker_order_id: str, idempotency_key: str | None = None) -> BrokerResult:
        r = self._by_id.get(broker_order_id)
        if r is None:
            return BrokerResult(broker_order_id=broker_order_id, status="rejected", raw={"error": "not found"})
        r.status = "cancelled"
        return r

    async def get_order(self, broker_order_id: str) -> BrokerResult | None:
        return self._by_id.get(broker_order_id)

    async def get_positions(self) -> list[dict[str, Any]]:
        return [{"broker_order_id": r.broker_order_id, "status": r.status} for r in self._by_id.values()]
