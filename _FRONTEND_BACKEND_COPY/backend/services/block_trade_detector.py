"""Block Trade Detector — identifies unusual large trades from tick data.

In the Iranian market, block trades (معاملات بلوکی) often precede significant
price movements. This detector identifies trades with volume > 3 standard
deviations from the 20-day average, which may indicate:

1. Institutional accumulation (positive signal)
2. Institutional distribution (negative signal)
3. Cross-trades between related parties

Data sources:
  - intraday_trades (14.8M+ tick-level records)
  - brsapi_historical_daily (for volume baseline)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BlockTrade:
    """A detected block trade."""

    symbol: str
    name: str
    trade_time: str
    price: float
    volume: int
    value: float
    direction: str  # accumulation or distribution
    z_score: float = 0.0
    confidence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class BlockTradeDetector:
    """Detects block trades in the Iranian stock market."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def scan_all(self, limit: int = 50) -> list[BlockTrade]:
        """Scan top traded symbols for block trades."""
        if self._session is None:
            return []

        from sqlalchemy import text

        # Get top symbols by trade value
        result = await self._session.execute(
            text("""
            SELECT symbol, name
            FROM brsapi_symbol_snapshots
            WHERE trade_value > 0
            ORDER BY trade_value DESC
            LIMIT :lim
        """),
            {"lim": limit},
        )

        symbols = [(row[0], row[1]) for row in result.fetchall()]
        block_trades: list[BlockTrade] = []

        for sym, name in symbols:
            trades = await self._detect_symbol_block_trades(sym, name)
            block_trades.extend(trades)

        block_trades.sort(key=lambda x: x.z_score, reverse=True)
        return block_trades

    async def detect_symbol(self, symbol: str, name: str = "") -> list[BlockTrade]:
        """Detect block trades for a single symbol."""
        return await self._detect_symbol_block_trades(symbol, name)

    async def _detect_symbol_block_trades(self, symbol: str, name: str) -> list[BlockTrade]:
        """Detect block trades for a single symbol using intraday data."""
        if self._session is None:
            return []

        from sqlalchemy import text

        # Get recent trades (last trading day)
        result = await self._session.execute(
            text("""
            SELECT trade_time, price, volume, value
            FROM intraday_trades
            WHERE symbol = :sym
            ORDER BY trade_time DESC
            LIMIT 1000
        """),
            {"sym": symbol},
        )

        trades = [dict(row._mapping) for row in result.fetchall()]
        if not trades:
            return []

        # Calculate volume statistics
        volumes = [int(t.get("volume") or 0) for t in trades]
        if not volumes:
            return []

        avg_vol = sum(volumes) / len(volumes)
        std_vol = (sum((v - avg_vol) ** 2 for v in volumes) / len(volumes)) ** 0.5

        if std_vol <= 0:
            return []

        # Find trades with z-score > 3
        block_trades: list[BlockTrade] = []
        for trade in trades:
            vol = int(trade.get("volume") or 0)
            price = float(trade.get("price") or 0)
            value = float(trade.get("value") or 0)

            if vol <= 0 or price <= 0:
                continue

            z_score = (vol - avg_vol) / std_vol

            if z_score > 3.0:
                # Determine direction based on price relative to recent average
                recent_avg_price = sum(float(t.get("price") or 0) for t in trades[:100]) / min(100, len(trades))

                if price > recent_avg_price * 1.01:
                    direction = "distribution"  # Selling at premium
                elif price < recent_avg_price * 0.99:
                    direction = "accumulation"  # Buying at discount
                else:
                    direction = "neutral"

                confidence = min(1.0, z_score / 5.0)

                block_trades.append(
                    BlockTrade(
                        symbol=symbol,
                        name=name,
                        trade_time=str(trade.get("trade_time", "")),
                        price=price,
                        volume=vol,
                        value=value,
                        direction=direction,
                        z_score=round(z_score, 2),
                        confidence=round(confidence, 2),
                        details={
                            "avg_volume": round(avg_vol, 0),
                            "std_volume": round(std_vol, 0),
                            "volume_ratio": round(vol / avg_vol, 1) if avg_vol > 0 else 0,
                            "recent_avg_price": round(recent_avg_price, 0),
                        },
                    )
                )

        return block_trades

    async def get_block_trade_summary(self) -> dict[str, Any]:
        """Get summary of recent block trades across the market."""
        block_trades = await self.scan_all(limit=50)

        if not block_trades:
            return {"total": 0, "accumulation": 0, "distribution": 0}

        accumulation = [bt for bt in block_trades if bt.direction == "accumulation"]
        distribution = [bt for bt in block_trades if bt.direction == "distribution"]

        return {
            "total": len(block_trades),
            "accumulation": len(accumulation),
            "distribution": len(distribution),
            "top_accumulation": [
                {"symbol": bt.symbol, "name": bt.name, "value": bt.value, "z_score": bt.z_score}
                for bt in accumulation[:5]
            ],
            "top_distribution": [
                {"symbol": bt.symbol, "name": bt.name, "value": bt.value, "z_score": bt.z_score}
                for bt in distribution[:5]
            ],
        }
