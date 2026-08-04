"""Iran Fear & Greed Index (IGFI) — behavioral finance indicator for Iranian market.

Custom index combining 5 components specific to the Iranian market:

1. Real vs Legal Buy Ratio (30%) — retail sentiment
2. Trade Value vs 30-day Average (20%) — activity level
3. Distance from 200-day MA (20%) — trend extension
4. ATR Volatility vs 6-month Average (15%) — fear gauge
5. Negative News Count (15%) — sentiment

Output: 0-100 scale
  0-20: Extreme Fear (بحران ترس)
  20-40: Fear (ترس)
  40-60: Neutral (خنثی)
  60-80: Greed (طمع)
  80-100: Extreme Greed (طمع شدید)

Data sources:
  - brsapi_symbol_snapshots (real/legal flow, volume, price)
  - brsapi_historical_daily (for MA200, ATR calculation)
  - news_articles (for negative news count)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jdatetime

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FearGreedResult:
    """Iran Fear & Greed Index result."""
    overall_score: float = 50.0  # 0-100
    label: str = "خنثی"  # Persian label
    components: dict[str, float] | None = None
    details: dict[str, Any] | None = None
    date: str = ""


class IranFearGreedIndex:
    """Calculates the Iran-specific Fear & Greed Index."""

    # Component weights
    WEIGHTS = {
        "real_legal_ratio": 0.30,
        "activity_level": 0.20,
        "trend_extension": 0.20,
        "volatility": 0.15,
        "news_sentiment": 0.15,
    }

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def calculate(self) -> FearGreedResult:
        """Calculate the current Iran Fear & Greed Index."""
        from datetime import date

        components: dict[str, float] = {}

        # Component 1: Real vs Legal Buy Ratio (30%)
        components["real_legal_ratio"] = await self._calc_real_legal_ratio()

        # Component 2: Activity Level (20%)
        components["activity_level"] = await self._calc_activity_level()

        # Component 3: Trend Extension - Distance from MA200 (20%)
        components["trend_extension"] = await self._calc_trend_extension()

        # Component 4: Volatility - ATR vs average (15%)
        components["volatility"] = await self._calc_volatility()

        # Component 5: News Sentiment (15%)
        components["news_sentiment"] = await self._calc_news_sentiment()

        # Calculate weighted overall score
        overall = sum(
            components[k] * self.WEIGHTS[k]
            for k in self.WEIGHTS
            if k in components
        )

        # Clamp to 0-100
        overall = max(0.0, min(100.0, overall))

        # Determine label
        if overall <= 20:
            label = "ترس شدید"
        elif overall <= 40:
            label = "ترس"
        elif overall <= 60:
            label = "خنثی"
        elif overall <= 80:
            label = "طمع"
        else:
            label = "طمع شدید"

        return FearGreedResult(
            overall_score=round(overall, 1),
            label=label,
            components={k: round(v, 1) for k, v in components.items()},
            details={
                "weights": self.WEIGHTS,
                "formula": "w1*real_legal + w2*activity + w3*trend + w4*volatility + w5*news",
            },
            date=str(date.today()),
        )

    async def _calc_real_legal_ratio(self) -> float:
        """Component 1: Real vs Legal buy ratio over 10 days.

        High real buying = Greed (people are confident)
        Low real buying = Fear (people are cautious)
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        # Only today's rows, and only the LATEST snapshot per symbol: the
        # snapshots table keeps one row per symbol per 2-minute sync cycle
        # (unique on (symbol, fetched_at)), so DISTINCT ON (symbol) picks the
        # newest cycle and avoids inflating the sums across cycles.
        # NOTE: fetched_at is a TIMESTAMPTZ column — the cutoff MUST be a
        # datetime/date object (asyncpg raises DataError for strings) and use
        # the UTC day, NOT a Jalali date (jdatetime would be smaller and the
        # filter would match every row).
        cutoff_today = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
        result = await self._session.execute(text("""
            SELECT
                SUM(buy_real_volume) as total_real_buy,
                SUM(sell_real_volume) as total_real_sell,
                SUM(buy_legal_volume) as total_legal_buy,
                SUM(sell_legal_volume) as total_legal_sell
            FROM (
                SELECT DISTINCT ON (symbol)
                    symbol, buy_real_volume, sell_real_volume,
                    buy_legal_volume, sell_legal_volume, trade_volume
                FROM brsapi_symbol_snapshots
                WHERE trade_volume > 0
                  AND fetched_at >= :cutoff_today
                ORDER BY symbol, fetched_at DESC
            ) latest
        """), {"cutoff_today": cutoff_today})

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

        # Real buying ratio (higher = more greed)
        real_ratio = real_buy / (real_buy + real_sell) if (real_buy + real_sell) > 0 else 0.5

        # Map 0-1 to 0-100 (0.5 = neutral = 50)
        score = real_ratio * 100

        return max(0.0, min(100.0, score))

    async def _calc_activity_level(self) -> float:
        """Component 2: Trade value vs 30-day average.

        High activity = Greed (people are trading actively)
        Low activity = Fear (people are staying away)
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        # Current activity (today's total value)
        # Only today's rows and only the latest snapshot per symbol
        # (UTC cutoff — see note in _calc_real_legal_ratio).
        cutoff_today = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
        result = await self._session.execute(text("""
            SELECT SUM(trade_value) as total_value
            FROM (
                SELECT DISTINCT ON (symbol)
                    symbol, trade_value
                FROM brsapi_symbol_snapshots
                WHERE trade_value > 0
                  AND fetched_at >= :cutoff_today
                ORDER BY symbol, fetched_at DESC
            ) latest
        """), {"cutoff_today": cutoff_today})

        row = result.fetchone()
        current_value = float(row[0] or 0) if row else 0

        # 30-day average
        # NOTE: brsapi_historical_daily.date is a String(20) column storing
        # Jalali dates (e.g. "1405-05-01") — compare against a Jalali date
        # string, not CURRENT_DATE (Gregorian + wrong type). PostgreSQL has no
        # implicit `varchar >= date` operator, so the old query always failed.
        cutoff_30d = (jdatetime.date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        result2 = await self._session.execute(text("""
            SELECT AVG(daily_value) as avg_value
            FROM (
                SELECT SUM(trade_value) as daily_value
                FROM brsapi_historical_daily
                WHERE date >= :cutoff
                GROUP BY date
            ) subq
        """), {"cutoff": cutoff_30d})

        row2 = result2.fetchone()
        avg_value = float(row2[0] or 0) if row2 else 0

        if avg_value <= 0:
            return 50.0

        # Ratio of current to average (1.0 = normal)
        ratio = current_value / avg_value

        # Map ratio to 0-100 (1.0 = 50, 2.0 = 80, 0.5 = 20)
        score = 50 + (ratio - 1.0) * 50

        return max(0.0, min(100.0, score))

    async def _calc_trend_extension(self) -> float:
        """Component 3: Distance from 200-day moving average.

        Far above MA200 = Greed (overextended)
        Far below MA200 = Fear (oversold)
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        # Get current index level (use top 30 stocks as proxy)
        # Only today's rows and only the latest snapshot per symbol
        # (UTC cutoff — see note in _calc_real_legal_ratio).
        cutoff_today = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
        # ORDER BY ... LIMIT must run in an inner subquery BEFORE the AVG
        # aggregate — Postgres rejects an aggregate query whose ORDER BY
        # references a non-aggregated column.
        result = await self._session.execute(text("""
            SELECT AVG(price_last) as current_avg
            FROM (
                SELECT price_last
                FROM (
                    SELECT DISTINCT ON (symbol)
                        symbol, price_last, trade_value
                    FROM brsapi_symbol_snapshots
                    WHERE price_last > 0
                      AND fetched_at >= :cutoff_today
                    ORDER BY symbol, fetched_at DESC
                ) latest
                ORDER BY trade_value DESC
                LIMIT 30
            ) top30
        """), {"cutoff_today": cutoff_today})

        row = result.fetchone()
        current_avg = float(row[0] or 0) if row else 0

        # Get 200-day average
        cutoff_200d = (jdatetime.date.today() - timedelta(days=200)).strftime("%Y-%m-%d")
        result2 = await self._session.execute(text("""
            SELECT AVG(avg_price) as ma200
            FROM (
                SELECT AVG(price_close) as avg_price
                FROM brsapi_historical_daily
                WHERE date >= :cutoff
                  AND price_close > 0
                GROUP BY date
            ) subq
        """), {"cutoff": cutoff_200d})

        row2 = result2.fetchone()
        ma200 = float(row2[0] or 0) if row2 else 0

        if ma200 <= 0 or current_avg <= 0:
            return 50.0

        # Distance from MA200 as percentage
        distance_pct = (current_avg - ma200) / ma200 * 100

        # Map distance to 0-100 (0% = 50, +20% = 80, -20% = 20)
        score = 50 + distance_pct * 1.5

        return max(0.0, min(100.0, score))

    async def _calc_volatility(self) -> float:
        """Component 4: ATR volatility vs 6-month average.

        High volatility = Fear (uncertainty)
        Low volatility = Greed (calm markets)
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        # Current ATR (14-day)
        cutoff_14d = (jdatetime.date.today() - timedelta(days=14)).strftime("%Y-%m-%d")
        result = await self._session.execute(text("""
            SELECT AVG(atr) as current_atr
            FROM (
                SELECT symbol,
                       AVG(price_max - price_min) as atr
                FROM brsapi_historical_daily
                WHERE date >= :cutoff
                  AND price_max > 0 AND price_min > 0
                GROUP BY symbol
            ) subq
        """), {"cutoff": cutoff_14d})

        row = result.fetchone()
        current_atr = float(row[0] or 0) if row else 0

        # 6-month average ATR
        cutoff_180d = (jdatetime.date.today() - timedelta(days=180)).strftime("%Y-%m-%d")
        result2 = await self._session.execute(text("""
            SELECT AVG(atr) as avg_atr
            FROM (
                SELECT symbol, date,
                       AVG(price_max - price_min) OVER (
                           PARTITION BY symbol ORDER BY date
                           ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
                       ) as atr
                FROM brsapi_historical_daily
                WHERE date >= :cutoff
                  AND price_max > 0 AND price_min > 0
            ) subq
            WHERE atr > 0
        """), {"cutoff": cutoff_180d})

        row2 = result2.fetchone()
        avg_atr = float(row2[0] or 0) if row2 else 0

        if avg_atr <= 0 or current_atr <= 0:
            return 50.0

        # Ratio (higher = more volatile = more fear)
        ratio = current_atr / avg_atr

        # Map: high ratio = fear (low score), low ratio = greed (high score)
        score = 100 - (ratio - 1.0) * 50

        return max(0.0, min(100.0, score))

    async def _calc_news_sentiment(self) -> float:
        """Component 5: Negative news count in last 24 hours.

        Many negative news = Fear
        Few negative news = Greed
        """
        if self._session is None:
            return 50.0

        from sqlalchemy import text

        result = await self._session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count
            FROM news_articles
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """))

        row = result.fetchone()
        if not row or not row[0]:
            return 50.0

        total = int(row[0] or 0)
        negative = int(row[1] or 0)

        if total == 0:
            return 50.0

        # Negative ratio (higher = more fear)
        negative_ratio = negative / total

        # Map: high negative ratio = fear (low score)
        score = 100 - negative_ratio * 100

        return max(0.0, min(100.0, score))
