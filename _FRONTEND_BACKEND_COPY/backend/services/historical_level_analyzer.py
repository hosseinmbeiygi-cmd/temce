"""Historical Level Analyzer — identifies key support/resistance from 25 years of data.

Uses clustering algorithms on historical price peaks and troughs to identify
"price congestion zones" — areas where the price has reacted multiple times
in the past. These zones are more reliable than simple recent S/R levels.

Data sources:
  - brsapi_historical_daily (2.6M+ records from year 1380)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.db_utils import safe_row_str
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PriceLevel:
    """A identified support/resistance level."""

    price: float
    level_type: str  # support, resistance
    strength: int  # number of touches
    date_range: str  # e.g., "1390-1403"
    confidence: float = 0.0  # 0-1


@dataclass
class HistoricalLevelResult:
    """Result of historical level analysis for one symbol."""

    symbol: str
    current_price: float = 0.0
    levels: list[PriceLevel] = field(default_factory=list)
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0
    support_distance_pct: float = 0.0
    resistance_distance_pct: float = 0.0
    congestion_zone: bool = False
    congestion_details: str = ""


class HistoricalLevelAnalyzer:
    """Identifies key historical support/resistance levels using clustering."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def analyze_symbol(self, symbol: str) -> HistoricalLevelResult | None:
        """Analyze historical levels for a single symbol."""
        if self._session is None:
            return None

        from sqlalchemy import text

        # Fetch all historical data
        result = await self._session.execute(
            text("""
            SELECT date, price_close, price_high, price_low
            FROM brsapi_historical_daily
            WHERE symbol = :sym AND price_close > 0
            ORDER BY date ASC
        """),
            {"sym": symbol},
        )

        rows = result.fetchall()
        if len(rows) < 50:
            return None

        prices = [float(row[1]) for row in rows if row[1]]
        _highs = [float(row[2]) for row in rows if row[2]]
        _lows = [float(row[3]) for row in rows if row[3]]
        _dates = [safe_row_str(row, idx=0) for row in rows]

        current_price = prices[-1] if prices else 0

        # Find peaks and troughs
        peaks = self._find_peaks(prices)
        troughs = self._find_troughs(prices)

        # Cluster peaks and troughs into levels
        resistance_levels = self._cluster_levels(peaks, "resistance")
        support_levels = self._cluster_levels(troughs, "support")

        all_levels = resistance_levels + support_levels
        all_levels.sort(key=lambda x: x.price)

        # Find nearest support and resistance
        supports_below = [lv for lv in support_levels if lv.price < current_price]
        resistances_above = [lv for lv in resistance_levels if lv.price > current_price]

        nearest_support = max([lv.price for lv in supports_below], default=0)
        nearest_resistance = min([lv.price for lv in resistances_above], default=float("inf"))

        if nearest_resistance == float("inf"):
            nearest_resistance = 0

        support_dist = (
            ((current_price - nearest_support) / current_price * 100)
            if nearest_support > 0 and current_price > 0
            else 0
        )
        resistance_dist = (
            ((nearest_resistance - current_price) / current_price * 100)
            if nearest_resistance > 0 and current_price > 0
            else 0
        )

        # Check if in congestion zone (within 5% of a strong level)
        congestion = False
        congestion_detail = ""
        for level in all_levels:
            if level.strength >= 3 and abs(current_price - level.price) / current_price < 0.05:
                congestion = True
                congestion_detail = f"قیمت فعلی در منطقه ازدحام {level.level_type} با {level.strength} برخورد قرار دارد"
                break

        return HistoricalLevelResult(
            symbol=symbol,
            current_price=current_price,
            levels=all_levels,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            support_distance_pct=round(support_dist, 2),
            resistance_distance_pct=round(resistance_dist, 2),
            congestion_zone=congestion,
            congestion_details=congestion_detail,
        )

    async def analyze_batch(self, symbols: list[str]) -> list[HistoricalLevelResult]:
        """Analyze historical levels for multiple symbols."""
        results: list[HistoricalLevelResult] = []
        for sym in symbols:
            r = await self.analyze_symbol(sym)
            if r:
                results.append(r)
        return results

    def _find_peaks(self, prices: list[float], window: int = 5) -> list[tuple[float, int]]:
        """Find local maxima (peaks) in price series."""
        peaks: list[tuple[float, int]] = []
        for i in range(window, len(prices) - window):
            if all(prices[i] >= prices[i - j] for j in range(1, window + 1)) and all(
                prices[i] >= prices[i + j] for j in range(1, window + 1)
            ):
                peaks.append((prices[i], i))
        return peaks

    def _find_troughs(self, prices: list[float], window: int = 5) -> list[tuple[float, int]]:
        """Find local minima (troughs) in price series."""
        troughs: list[tuple[float, int]] = []
        for i in range(window, len(prices) - window):
            if all(prices[i] <= prices[i - j] for j in range(1, window + 1)) and all(
                prices[i] <= prices[i + j] for j in range(1, window + 1)
            ):
                troughs.append((prices[i], i))
        return troughs

    def _cluster_levels(
        self,
        points: list[tuple[float, int]],
        level_type: str,
        tolerance_pct: float = 2.0,
    ) -> list[PriceLevel]:
        """Cluster nearby price points into support/resistance levels."""
        if not points:
            return []

        sorted_points = sorted(points, key=lambda x: x[0])
        levels: list[PriceLevel] = []

        i = 0
        while i < len(sorted_points):
            cluster = [sorted_points[i]]
            j = i + 1
            while j < len(sorted_points):
                if abs(sorted_points[j][0] - cluster[0][0]) / cluster[0][0] * 100 < tolerance_pct:
                    cluster.append(sorted_points[j])
                    j += 1
                else:
                    break

            if len(cluster) >= 2:
                avg_price = sum(p[0] for p in cluster) / len(cluster)
                min_idx = min(p[1] for p in cluster)
                max_idx = max(p[1] for p in cluster)

                levels.append(
                    PriceLevel(
                        price=round(avg_price, 0),
                        level_type=level_type,
                        strength=len(cluster),
                        date_range=f"index {min_idx}-{max_idx}",
                        confidence=min(1.0, len(cluster) / 5.0),
                    )
                )

            i = j

        return levels
