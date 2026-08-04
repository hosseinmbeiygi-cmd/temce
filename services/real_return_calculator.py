"""Real Return Calculator — adjusts nominal returns for inflation and FX changes.

In Iran, nominal returns can be misleading. A stock that gains 30% while the
dollar gains 40% is actually a loss in real purchasing power. This calculator
adjusts returns based on:

1. Official inflation rate (from CBI/macro_indicators)
2. USD/IRR exchange rate changes (from brsapi_gold_currency_pro_prices)
3. Gold price changes (alternative inflation hedge)

Data sources:
  - macro_indicators (inflation rate)
  - brsapi_gold_currency_pro_prices (USD/IRR rates)
  - brsapi_historical_daily (stock prices for return calculation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.db_utils import safe_row_float
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RealReturnResult:
    """Real return calculation for a symbol."""
    symbol: str
    nominal_return_pct: float = 0.0
    inflation_adjustment_pct: float = 0.0
    fx_adjustment_pct: float = 0.0
    real_return_pct: float = 0.0
    period_days: int = 30
    details: dict[str, Any] | None = None


class RealReturnCalculator:
    """Calculates real (inflation-adjusted) returns for Iranian market assets."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def calculate_real_return(
        self,
        symbol: str,
        period_days: int = 30,
    ) -> RealReturnResult | None:
        """Calculate real return for a symbol over a given period."""
        if self._session is None:
            return None

        from sqlalchemy import text

        # Get current and historical price
        result = await self._session.execute(text("""
            SELECT price_close, date
            FROM brsapi_historical_daily
            WHERE symbol = :sym AND price_close > 0
            ORDER BY date DESC
            LIMIT 2
        """), {"sym": symbol})

        rows = result.fetchall()
        if len(rows) < 2:
            return None

        current_price = safe_row_float(rows[0], idx=0)
        old_price = safe_row_float(rows[1], idx=0)
        current_date = rows[0][1]
        old_date = rows[1][1]

        if old_price <= 0:
            return None

        nominal_return_pct = (current_price - old_price) / old_price * 100

        # Get inflation adjustment
        inflation_adj = await self._get_inflation_adjustment(period_days)

        # Get FX adjustment
        fx_adj = await self._get_fx_adjustment(period_days)

        real_return_pct = nominal_return_pct - inflation_adj - fx_adj

        return RealReturnResult(
            symbol=symbol,
            nominal_return_pct=round(nominal_return_pct, 2),
            inflation_adjustment_pct=round(inflation_adj, 2),
            fx_adjustment_pct=round(fx_adj, 2),
            real_return_pct=round(real_return_pct, 2),
            period_days=period_days,
            details={
                "current_price": current_price,
                "old_price": old_price,
                "current_date": str(current_date),
                "old_date": str(old_date),
            },
        )

    async def calculate_batch_real_returns(
        self,
        symbols: list[str],
        period_days: int = 30,
    ) -> list[RealReturnResult]:
        """Calculate real returns for multiple symbols."""
        results: list[RealReturnResult] = []
        for sym in symbols:
            r = await self.calculate_real_return(sym, period_days)
            if r:
                results.append(r)
        results.sort(key=lambda x: x.real_return_pct, reverse=True)
        return results

    async def _get_inflation_adjustment(self, period_days: int) -> float:
        """Get annualized inflation adjustment scaled to period."""
        if self._session is None:
            return 0.0

        from sqlalchemy import text

        result = await self._session.execute(text("""
            SELECT value
            FROM macro_indicators
            WHERE indicator_name IN ('inflation_rate', 'cpi_yoy')
            ORDER BY date DESC
            LIMIT 1
        """))

        row = result.fetchone()
        if not row:
            return 40.0 / 365 * period_days  # Default: ~40% annual inflation for Iran

        annual_inflation = safe_row_float(row, idx=0, default=40.0)
        return annual_inflation / 365 * period_days

    async def _get_fx_adjustment(self, period_days: int) -> float:
        """Get USD/IRR change adjustment over the period."""
        if self._session is None:
            return 0.0

        from sqlalchemy import text

        # Get current USD/IRR rate
        result = await self._session.execute(text("""
            SELECT price
            FROM brsapi_gold_currency_pro_prices
            WHERE symbol LIKE '%USD%' OR symbol LIKE '%DOLLAR%'
            ORDER BY updated_at DESC
            LIMIT 1
        """))

        row = result.fetchone()
        if not row:
            return 0.0

        current_fx = safe_row_float(row, idx=0, default=0.0)

        # Get historical FX rate (approximate from daily data)
        result2 = await self._session.execute(text("""
            SELECT price
            FROM brsapi_gold_currency_pro_prices
            WHERE (symbol LIKE '%USD%' OR symbol LIKE '%DOLLAR%')
              AND updated_at >= NOW() - INTERVAL ':days days'
            ORDER BY updated_at ASC
            LIMIT 1
        """), {"days": period_days})

        row2 = result2.fetchone()
        old_fx = float(row2[0]) if row2 else current_fx

        if old_fx <= 0:
            return 0.0

        fx_change_pct = (current_fx - old_fx) / old_fx * 100
        return fx_change_pct

    async def get_market_real_return_summary(self) -> dict[str, Any]:
        """Get overall market real return summary."""
        if self._session is None:
            return {}

        from sqlalchemy import text

        # Get top 30 stocks by value
        result = await self._session.execute(text("""
            SELECT symbol
            FROM brsapi_symbol_snapshots
            WHERE price_last > 0 AND trade_value > 0
            ORDER BY trade_value DESC
            LIMIT 30
        """))

        symbols = [row[0] for row in result.fetchall()]
        returns = await self.calculate_batch_real_returns(symbols, 30)

        if not returns:
            return {}

        positive_real = [r for r in returns if r.real_return_pct > 0]
        negative_real = [r for r in returns if r.real_return_pct < 0]

        return {
            "total_symbols": len(returns),
            "positive_real_return": len(positive_real),
            "negative_real_return": len(negative_real),
            "avg_nominal_return": round(sum(r.nominal_return_pct for r in returns) / len(returns), 2),
            "avg_real_return": round(sum(r.real_return_pct for r in returns) / len(returns), 2),
            "best_real_return": round(max(r.real_return_pct for r in returns), 2),
            "worst_real_return": round(min(r.real_return_pct for r in returns), 2),
            "inflation_adjustment": round(returns[0].inflation_adjustment_pct, 2),
            "fx_adjustment": round(returns[0].fx_adjustment_pct, 2),
        }
