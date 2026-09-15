"""Fake Queue Detector — identifies manipulated buy/sell queues in Iranian market.

In the Iranian stock market, "fake queues" (صف کاذب) are a common manipulation
where large buy/sell orders are placed to create artificial demand/supply signals,
then cancelled before execution. This detector identifies them by analyzing:

1. Sudden queue volume changes without price movement
2. High queue volume relative to actual trade volume
3. Queue changes that don't align with order flow

Data sources:
  - brsapi_symbol_snapshots (bid_volume_1, ask_volume_1, price changes)
  - brsapi_historical_daily (for baseline comparison)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FakeQueueResult:
    """Result of fake queue analysis for one symbol."""

    symbol: str
    name: str
    fake_buy_queue: bool = False
    fake_sell_queue: bool = False
    confidence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class FakeQueueDetector:
    """Detects fake/manipulated queues in the Iranian stock market."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def detect_all(self, limit: int = 100) -> list[FakeQueueResult]:
        """Scan all symbols for fake queue patterns."""
        if self._session is None:
            return []

        from sqlalchemy import text

        # Fetch current snapshots with queue data
        result = await self._session.execute(
            text("""
            SELECT symbol, name, price_last, price_close, price_first,
                   trade_volume, trade_value,
                   buy_volume_1, buy_count_1, sell_volume_1, sell_count_1,
                   buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume
            FROM brsapi_symbol_snapshots
            WHERE price_last > 0 AND trade_volume > 0
            ORDER BY trade_value DESC
            LIMIT :lim
        """),
            {"lim": limit},
        )

        rows = [dict(row._mapping) for row in result.fetchall()]
        signals: list[FakeQueueResult] = []

        for row in rows:
            r = self._analyze_symbol(row)
            if r and (r.fake_buy_queue or r.fake_sell_queue):
                signals.append(r)

        return signals

    async def detect_symbol(self, symbol: str) -> FakeQueueResult | None:
        """Analyze a single symbol for fake queue patterns."""
        if self._session is None:
            return None

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT symbol, name, price_last, price_close, price_first,
                   trade_volume, trade_value,
                   buy_volume_1, buy_count_1, sell_volume_1, sell_count_1,
                   buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume
            FROM brsapi_symbol_snapshots
            WHERE symbol = :sym AND price_last > 0
        """),
            {"sym": symbol},
        )

        row = result.fetchone()
        if not row:
            return None

        return self._analyze_symbol(dict(row._mapping))

    def _analyze_symbol(self, snap: dict[str, Any]) -> FakeQueueResult | None:
        """Analyze a single snapshot for fake queue patterns."""
        symbol = snap.get("symbol", "")
        name = snap.get("name", "")

        price_last = float(snap.get("price_last") or 0)
        price_close = float(snap.get("price_close") or price_last)
        _price_first = float(snap.get("price_first") or price_close)

        trade_volume = int(snap.get("trade_volume") or 0)
        _trade_value = float(snap.get("trade_value") or 0)

        buy_vol_1 = int(snap.get("buy_volume_1") or 0)
        buy_cnt_1 = int(snap.get("buy_count_1") or 0)
        sell_vol_1 = int(snap.get("sell_volume_1") or 0)
        sell_cnt_1 = int(snap.get("sell_count_1") or 0)

        buy_real = int(snap.get("buy_real_volume") or 0)
        buy_legal = int(snap.get("buy_legal_volume") or 0)
        sell_real = int(snap.get("sell_real_volume") or 0)
        sell_legal = int(snap.get("sell_legal_volume") or 0)

        if price_last <= 0 or trade_volume <= 0:
            return None

        # Price change percentage
        price_change_pct = abs(price_last - price_close) / price_close * 100 if price_close > 0 else 0

        # Queue ratios
        buy_queue_ratio = buy_vol_1 / trade_volume if trade_volume > 0 else 0
        sell_queue_ratio = sell_vol_1 / trade_volume if trade_volume > 0 else 0

        # Average order size in queue
        avg_buy_order = buy_vol_1 / buy_cnt_1 if buy_cnt_1 > 0 else 0
        avg_sell_order = sell_vol_1 / sell_cnt_1 if sell_cnt_1 > 0 else 0

        # Average trade size
        avg_trade_size = trade_volume / max(buy_cnt_1 + sell_cnt_1, 1)

        details = {
            "price_change_pct": round(price_change_pct, 2),
            "buy_queue_ratio": round(buy_queue_ratio, 2),
            "sell_queue_ratio": round(sell_queue_ratio, 2),
            "avg_buy_order": round(avg_buy_order, 0),
            "avg_sell_order": round(avg_sell_order, 0),
            "avg_trade_size": round(avg_trade_size, 0),
        }

        fake_buy = False
        fake_sell = False
        confidence = 0.0
        reasons = []

        # Pattern 1: Large buy queue but price not moving up
        if buy_queue_ratio > 3.0 and price_change_pct < 0.5:
            confidence += 0.4
            reasons.append(f" صف خرید {buy_queue_ratio:.1f}x حجم معاملات با تغییر قیمت کمتر از ۰.۵٪")
            fake_buy = True

        # Pattern 2: Large sell queue but price not moving down
        if sell_queue_ratio > 3.0 and price_change_pct < 0.5:
            confidence += 0.4
            reasons.append(f" صف فروش {sell_queue_ratio:.1f}x حجم معاملات با تغییر قیمت کمتر از ۰.۵٪")
            fake_sell = True

        # Pattern 3: Very large average order in queue compared to trades
        if avg_buy_order > avg_trade_size * 10 and buy_queue_ratio > 2.0:
            confidence += 0.3
            reasons.append(f" اندازه متوسط سفارش خرید {avg_buy_order / avg_trade_size:.0f}x بزرگ‌تر از معاملات")
            fake_buy = True

        if avg_sell_order > avg_trade_size * 10 and sell_queue_ratio > 2.0:
            confidence += 0.3
            reasons.append(f" اندازه متوسط سفارش فروش {avg_sell_order / avg_trade_size:.0f}x بزرگ‌تر از معاملات")
            fake_sell = True

        # Pattern 4: High legal buying in queue but no real buying pressure
        if buy_legal > 0 and buy_real == 0 and buy_queue_ratio > 2.0:
            confidence += 0.2
            reasons.append(" صف خرید فقط حقوقی بدون خرید حقیقی")
            fake_buy = True

        if sell_legal > 0 and sell_real == 0 and sell_queue_ratio > 2.0:
            confidence += 0.2
            reasons.append(" صف فروش فقط حقوقی بدون فروش حقیقی")
            fake_sell = True

        confidence = min(1.0, confidence)

        if not fake_buy and not fake_sell:
            return None

        return FakeQueueResult(
            symbol=symbol,
            name=name,
            fake_buy_queue=fake_buy,
            fake_sell_queue=fake_sell,
            confidence=confidence,
            details=details,
            reason=" | ".join(reasons),
        )
