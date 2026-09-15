"""Gap Prediction — predicts opening price gaps for Iranian market.

In the Iranian market, overnight news and global price changes often cause
significant opening gaps. This module predicts the likely opening gap based on:

1. Global commodity prices (gold, oil) changes overnight
2. USD/IRR exchange rate changes
3. End-of-day queue status (buy/sell pressure)
4. Recent news sentiment

Output: Predicted gap percentage and recommended limit order range.

Data sources:
  - brsapi_gold_currency_pro_prices (FX rates)
  - brsapi_commodity_prices (global commodities)
  - brsapi_symbol_snapshots (end-of-day queues)
  - news_articles (overnight news)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GapPrediction:
    """Gap prediction for a single symbol."""

    symbol: str
    name: str
    predicted_gap_pct: float = 0.0  # positive = gap up, negative = gap down
    confidence: float = 0.0  # 0-1
    recommended_buy_price: float = 0.0
    recommended_sell_price: float = 0.0
    factors: dict[str, float] | None = None
    reason: str = ""


class GapPredictor:
    """Predicts opening price gaps for the Iranian market."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def predict_all(self, limit: int = 50) -> list[GapPrediction]:
        """Predict gaps for top traded symbols."""
        if self._session is None:
            return []

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT symbol, name, price_last, price_close,
                   buy_volume_1, sell_volume_1, buy_count_1, sell_count_1
            FROM brsapi_symbol_snapshots
            WHERE price_last > 0 AND trade_value > 0
            ORDER BY trade_value DESC
            LIMIT :lim
        """),
            {"lim": limit},
        )

        rows = [dict(row._mapping) for row in result.fetchall()]

        # Get global factor adjustments
        gold_factor = await self._get_gold_factor()
        fx_factor = await self._get_fx_factor()
        oil_factor = await self._get_oil_factor()

        predictions: list[GapPrediction] = []
        for row in rows:
            pred = self._predict_symbol(row, gold_factor, fx_factor, oil_factor)
            if pred:
                predictions.append(pred)

        predictions.sort(key=lambda x: abs(x.predicted_gap_pct), reverse=True)
        return predictions

    async def predict_symbol(self, symbol: str) -> GapPrediction | None:
        """Predict gap for a single symbol."""
        if self._session is None:
            return None

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT symbol, name, price_last, price_close,
                   buy_volume_1, sell_volume_1, buy_count_1, sell_count_1
            FROM brsapi_symbol_snapshots
            WHERE symbol = :sym AND price_last > 0
        """),
            {"sym": symbol},
        )

        row = result.fetchone()
        if not row:
            return None

        gold_factor = await self._get_gold_factor()
        fx_factor = await self._get_fx_factor()
        oil_factor = await self._get_oil_factor()

        return self._predict_symbol(dict(row._mapping), gold_factor, fx_factor, oil_factor)

    def _predict_symbol(
        self,
        snap: dict[str, Any],
        gold_factor: float,
        fx_factor: float,
        oil_factor: float,
    ) -> GapPrediction | None:
        """Predict gap for a symbol based on multiple factors."""
        symbol = snap.get("symbol", "")
        name = snap.get("name", "")
        price_last = float(snap.get("price_last") or 0)
        _price_close = float(snap.get("price_close") or price_last)

        buy_vol = int(snap.get("buy_volume_1") or 0)
        sell_vol = int(snap.get("sell_volume_1") or 0)
        _buy_cnt = int(snap.get("buy_count_1") or 0)
        _sell_cnt = int(snap.get("sell_count_1") or 0)

        if price_last <= 0:
            return None

        factors: dict[str, float] = {}

        # Factor 1: Queue imbalance (buy pressure vs sell pressure)
        total_queue = buy_vol + sell_vol
        queue_imbalance = (buy_vol - sell_vol) / total_queue if total_queue > 0 else 0.0
        factors["queue_imbalance"] = queue_imbalance * 10  # Scale to ~±10%

        # Factor 2: Global gold impact (for gold-related stocks)
        factors["gold_impact"] = gold_factor * 0.3  # 30% correlation

        # Factor 3: FX impact (for export-oriented stocks)
        factors["fx_impact"] = fx_factor * 0.5  # 50% correlation for exporters

        # Factor 4: Oil impact (for energy/petrochemical stocks)
        factors["oil_impact"] = oil_factor * 0.4  # 40% correlation

        # Combined prediction
        predicted_gap = sum(factors.values())

        # Clamp to reasonable range
        predicted_gap = max(-10.0, min(10.0, predicted_gap))

        # Calculate recommended prices
        if predicted_gap > 0:
            recommended_buy = price_last * (1 + predicted_gap / 100 * 0.5)
            recommended_sell = price_last * (1 + predicted_gap / 100 * 1.2)
        else:
            recommended_buy = price_last * (1 + predicted_gap / 100 * 0.8)
            recommended_sell = price_last * (1 + predicted_gap / 100 * 0.3)

        confidence = min(1.0, abs(predicted_gap) / 5.0)

        reasons = []
        if abs(factors.get("queue_imbalance", 0)) > 1:
            direction = "خرید" if factors["queue_imbalance"] > 0 else "فروش"
            reasons.append(f"فشار {direction} در صف")
        if abs(gold_factor) > 1:
            reasons.append(f"تغییر طلا: {gold_factor:+.1f}٪")
        if abs(fx_factor) > 1:
            reasons.append(f"تغییر دلار: {fx_factor:+.1f}٪")

        return GapPrediction(
            symbol=symbol,
            name=name,
            predicted_gap_pct=round(predicted_gap, 2),
            confidence=round(confidence, 2),
            recommended_buy_price=round(recommended_buy, 0),
            recommended_sell_price=round(recommended_sell, 0),
            factors={k: round(v, 2) for k, v in factors.items()},
            reason=" | ".join(reasons) if reasons else "بدون سیگنال قوی",
        )

    async def _get_gold_factor(self) -> float:
        """Get overnight gold price change factor (percentage)."""
        if self._session is None:
            return 0.0

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT price FROM brsapi_gold_currency_pro_prices
            WHERE symbol LIKE '%GOLD%' OR symbol LIKE '%طلا%'
            ORDER BY updated_at DESC LIMIT 2
        """)
        )
        rows = result.fetchall()
        if not rows or len(rows) < 2:
            return 0.0
        current = float(rows[0][0]) if rows[0][0] else 0.0
        previous = float(rows[1][0]) if rows[1][0] else 0.0
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100

    async def _get_fx_factor(self) -> float:
        """Get overnight USD/IRR change factor (percentage)."""
        if self._session is None:
            return 0.0

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT price FROM brsapi_gold_currency_pro_prices
            WHERE symbol LIKE '%USD%' OR symbol LIKE '%DOLLAR%'
            ORDER BY updated_at DESC LIMIT 2
        """)
        )
        rows = result.fetchall()
        if not rows or len(rows) < 2:
            return 0.0
        current = float(rows[0][0]) if rows[0][0] else 0.0
        previous = float(rows[1][0]) if rows[1][0] else 0.0
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100

    async def _get_oil_factor(self) -> float:
        """Get overnight oil price change factor (percentage)."""
        if self._session is None:
            return 0.0

        from sqlalchemy import text

        result = await self._session.execute(
            text("""
            SELECT price FROM brsapi_commodity_prices
            WHERE symbol LIKE '%OIL%' OR symbol LIKE '%نفت%'
            ORDER BY updated_at DESC LIMIT 2
        """)
        )
        rows = result.fetchall()
        if not rows or len(rows) < 2:
            return 0.0
        current = float(rows[0][0]) if rows[0][0] else 0.0
        previous = float(rows[1][0]) if rows[1][0] else 0.0
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100
