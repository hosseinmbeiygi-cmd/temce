"""Market Health Index — composite indicator of overall market condition.

Combines 4 structural metrics into a single 0-100 health score:

1. Real vs Legal Buy/Sell Ratio (30%) — smart money direction
2. Price Dispersion Across Sectors (30%) — market breadth
3. Block Trade Ratio (20%) — institutional activity
4. VWAP Stability in Final 10 Minutes (20%) — end-of-day confidence

Output: 0-100 scale
  0-30: Market is "sick" — avoid trading
  30-50: Weak market — selective trading only
  50-70: Normal market — standard strategies
  70-100: Healthy market — full participation

Data sources:
  - brsapi_symbol_snapshots (flow, volume, price)
  - brsapi_historical_daily (for baseline comparison)
  - intraday_trades (for VWAP analysis)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MarketHealthResult:
    """Market Health Index result."""

    overall_score: float = 50.0  # 0-100
    label: str = "عادی"
    components: dict[str, float] | None = None
    recommendations: list[str] | None = None
    date: str = ""


class MarketHealthIndex:
    """Calculates the overall market health index for the Iranian market."""

    WEIGHTS = {
        "real_legal_flow": 0.30,
        "price_dispersion": 0.30,
        "block_trade_ratio": 0.20,
        "vwap_stability": 0.20,
    }

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def calculate(self) -> MarketHealthResult:
        """Calculate the current Market Health Index."""
        from datetime import date

        components: dict[str, float] = {}

        # Component 1: Real vs Legal Flow (30%)
        components["real_legal_flow"] = await self._calc_real_legal_flow()

        # Component 2: Price Dispersion (30%)
        components["price_dispersion"] = await self._calc_price_dispersion()

        # Component 3: Block Trade Ratio (20%)
        components["block_trade_ratio"] = await self._calc_block_trade_ratio()

        # Component 4: VWAP Stability (20%)
        components["vwap_stability"] = await self._calc_vwap_stability()

        # Calculate weighted overall score
        overall = sum(components[k] * self.WEIGHTS[k] for k in self.WEIGHTS if k in components)

        overall = max(0.0, min(100.0, overall))

        # Determine label and recommendations
        if overall <= 30:
            label = "بازار بیمار"
            recommendations = [
                "از معامله خودداری کنید",
                "рیسک بالا در تمام استراتژی‌ها",
                "منتظر بهبود شرایط باشید",
            ]
        elif overall <= 50:
            label = "بازار ضعیف"
            recommendations = [
                "فقط معاملات کوتاه‌مدت",
                "حجم معاملات را کاهش دهید",
                "فقط نمادهای بسیار قوی",
            ]
        elif overall <= 70:
            label = "بازار عادی"
            recommendations = [
                "استراتژی‌های معمول قابل اجراست",
                "تنوع‌بخشی را رعایت کنید",
            ]
        else:
            label = "بازار سالم"
            recommendations = [
                "شرایط مساعد برای معامله",
                "می‌توانید حجم معاملات را افزایش دهید",
                "استراتژی‌های رشد مناسب هستند",
            ]

        return MarketHealthResult(
            overall_score=round(overall, 1),
            label=label,
            components={k: round(v, 1) for k, v in components.items()},
            recommendations=recommendations,
            date=str(date.today()),
        )

    async def _calc_real_legal_flow(self) -> float:
        """Component 1: Real vs Legal buy/sell ratio.

        Positive net flow = healthy market
        Negative net flow = unhealthy market
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT
                SUM(buy_real_volume) as total_real_buy,
                SUM(sell_real_volume) as total_real_sell,
                SUM(buy_legal_volume) as total_legal_buy,
                SUM(sell_legal_volume) as total_legal_sell
            FROM brsapi_symbol_snapshots
            WHERE trade_volume > 0
        """)
        )

        row = result.fetchone()
        if not row or not row[0]:
            return 50.0

        real_buy = float(row[0] or 0)
        real_sell = float(row[1] or 0)
        legal_buy = float(row[2] or 0)
        legal_sell = float(row[3] or 0)

        total_buy = real_buy + legal_buy
        total_sell = real_sell + legal_sell

        if total_buy + total_sell == 0:
            return 50.0

        # Net flow ratio (-1 to +1)
        net_flow = (total_buy - total_sell) / (total_buy + total_sell)

        # Map to 0-100 (-1 = 0, 0 = 50, +1 = 100)
        score = (net_flow + 1) * 50

        return max(0.0, min(100.0, score))

    async def _calc_price_dispersion(self) -> float:
        """Component 2: Price dispersion across sectors.

        Low dispersion = uniform market (healthy)
        High dispersion = fragmented market (unhealthy)
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        # Get average change by symbol group (approximate sectors)
        result = await self._session.execute(
            text("""
            SELECT
                AVG(CASE WHEN trade_value > 10000000000 THEN price_last_change_pct ELSE NULL END) as large_cap_avg,
                AVG(CASE WHEN trade_value BETWEEN 1000000000 AND 10000000000 THEN price_last_change_pct ELSE NULL END) as mid_cap_avg,
                AVG(CASE WHEN trade_value < 1000000000 THEN price_last_change_pct ELSE NULL END) as small_cap_avg
            FROM brsapi_symbol_snapshots
            WHERE price_last > 0 AND trade_value > 0
        """)
        )

        row = result.fetchone()
        if not row:
            return 50.0

        large_avg = float(row[0] or 0)
        mid_avg = float(row[1] or 0)
        small_avg = float(row[2] or 0)

        # Calculate dispersion (standard deviation of averages)
        avgs = [a for a in [large_avg, mid_avg, small_avg] if a is not None]
        if len(avgs) < 2:
            return 50.0

        mean_avg = sum(avgs) / len(avgs)
        variance = sum((a - mean_avg) ** 2 for a in avgs) / len(avgs)
        dispersion = variance**0.5

        # Low dispersion = healthy (score high)
        # Map: 0% dispersion = 80, 5% dispersion = 50, 10%+ = 20
        score = 80 - dispersion * 6

        return max(0.0, min(100.0, score))

    async def _calc_block_trade_ratio(self) -> float:
        """Component 3: Ratio of large trades to total trades.

        Moderate block trades = healthy institutional participation
        Too few or too many = unhealthy
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN trade_value > 5000000000 THEN 1 ELSE 0 END) as block_trades
            FROM brsapi_symbol_snapshots
            WHERE trade_value > 0
        """)
        )

        row = result.fetchone()
        if not row or not row[0]:
            return 50.0

        total = int(row[0] or 0)
        blocks = int(row[1] or 0)

        if total == 0:
            return 50.0

        block_ratio = blocks / total

        # Optimal range: 5-15% block trades
        if 0.05 <= block_ratio <= 0.15:
            score = 70 + (0.15 - abs(block_ratio - 0.10)) * 200
        elif block_ratio < 0.05:
            score = 40 + block_ratio * 600
        else:
            score = 70 - (block_ratio - 0.15) * 200

        return max(0.0, min(100.0, score))

    async def _calc_vwap_stability(self) -> float:
        """Component 4: VWAP stability in final trading minutes.

        Stable VWAP = confident market
        Erratic VWAP = uncertain market
        """
        if self._session is None:
            return 50.0

        # Simplified: use price consistency as proxy
        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT
                AVG(ABS(price_last - price_first) / price_first * 100) as avg_intraday_range
            FROM brsapi_symbol_snapshots
            WHERE price_first > 0 AND price_last > 0
        """)
        )

        row = result.fetchone()
        if not row or not row[0]:
            return 50.0

        avg_range = float(row[0] or 0)

        # Low intraday range = stable VWAP
        # Map: 0% range = 80, 3% range = 50, 6%+ = 20
        score = 80 - avg_range * 10

        return max(0.0, min(100.0, score))
