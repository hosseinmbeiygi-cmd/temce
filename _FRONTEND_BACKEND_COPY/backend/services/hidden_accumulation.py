"""Hidden Accumulation Detector — identifies stealth accumulation before price rallies.

In the Iranian market, "hidden accumulation" (انباشت پنهان) occurs when smart money
quietly buys shares without causing visible price movement. Key indicators:

1. Volume surge (>2x 20-day average) with minimal price change (<1%)
2. Increasing buy-side real money flow while price stays flat
3. Shrinking sell-side volume while buy-side grows

This is often a precursor to sharp rallies (especially in Iranian market where
institutional buying is concentrated).

Data sources:
  - brsapi_symbol_snapshots (volume, price, real/legal flow)
  - brsapi_historical_daily (for volume baseline)
  - brsapi_historical_real_legal (for real/legal breakdown)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import jdatetime

from core.db_utils import safe_row_float
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AccumulationResult:
    """Result of hidden accumulation analysis for one symbol."""

    symbol: str
    name: str
    is_accumulating: bool = False
    score: float = 0.0  # 0-100
    volume_ratio: float = 0.0
    price_change_pct: float = 0.0
    net_real_flow: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class HiddenAccumulationDetector:
    """Detects hidden accumulation patterns in the Iranian stock market."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def scan_all(self, limit: int = 200) -> list[AccumulationResult]:
        """Scan all symbols for hidden accumulation patterns."""
        if self._session is None:
            return []

        from sqlalchemy import text

        # Fetch current snapshots (latest row per symbol: the table stores one
        # row per symbol per 2-min sync cycle, so DISTINCT ON (symbol) picks
        # the newest cycle and avoids duplicate symbols).
        result = await self._session.execute(
            text("""
            SELECT symbol, name, price_last, price_close, price_first,
                   trade_volume, trade_value,
                   buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume,
                   buy_real_count, buy_legal_count, sell_real_count, sell_legal_count
            FROM (
                SELECT DISTINCT ON (symbol)
                    symbol, name, price_last, price_close, price_first,
                    trade_volume, trade_value,
                    buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume,
                    buy_real_count, buy_legal_count, sell_real_count, sell_legal_count
                FROM brsapi_symbol_snapshots
                WHERE price_last > 0 AND trade_volume > 0
                ORDER BY symbol, fetched_at DESC
            ) latest
            ORDER BY trade_value DESC
            LIMIT :lim
        """),
            {"lim": limit},
        )

        rows = [dict(row._mapping) for row in result.fetchall()]

        # Fetch 20-day volume averages
        vol_avgs = await self._fetch_volume_averages()

        signals: list[AccumulationResult] = []
        for row in rows:
            sym = row.get("symbol", "")
            avg_vol = vol_avgs.get(sym, 0)
            if avg_vol <= 0:
                continue
            r = self._analyze_symbol(row, avg_vol)
            if r and r.is_accumulating:
                signals.append(r)

        signals.sort(key=lambda x: x.score, reverse=True)
        return signals

    async def detect_symbol(self, symbol: str) -> AccumulationResult | None:
        """Analyze a single symbol for hidden accumulation."""
        if self._session is None:
            return None

        from sqlalchemy import text

        # Latest snapshot for the symbol (newest cycle wins — see scan_all).
        result = await self._session.execute(
            text("""
            SELECT symbol, name, price_last, price_close, price_first,
                   trade_volume, trade_value,
                   buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume,
                   buy_real_count, buy_legal_count, sell_real_count, sell_legal_count
            FROM brsapi_symbol_snapshots
            WHERE symbol = :sym AND price_last > 0
            ORDER BY fetched_at DESC
            LIMIT 1
        """),
            {"sym": symbol},
        )

        row = result.fetchone()
        if not row:
            return None

        avg_vol = await self._fetch_volume_average(symbol)
        return self._analyze_symbol(dict(row._mapping), avg_vol)

    async def _fetch_volume_averages(self) -> dict[str, float]:
        """Fetch 20-day average volume for all symbols."""
        if self._session is None:
            return {}

        from sqlalchemy import text

        # NOTE: brsapi_historical_daily.date is a String(20) column storing
        # Jalali dates (e.g. "1405-05-01") — compare against a Jalali date
        # string, not CURRENT_DATE (Gregorian + wrong type). PostgreSQL has no
        # implicit `varchar >= date` operator, so the old query always failed.
        cutoff_30d = (jdatetime.date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        result = await self._session.execute(
            text("""
            SELECT symbol, AVG(trade_volume) as avg_vol
            FROM brsapi_historical_daily
            WHERE date >= :cutoff
              AND trade_volume > 0
            GROUP BY symbol
        """),
            {"cutoff": cutoff_30d},
        )

        return {row[0]: float(row[1]) for row in result.fetchall()}

    async def _fetch_volume_average(self, symbol: str) -> float:
        """Fetch 20-day average volume for one symbol."""
        if self._session is None:
            return 0

        from sqlalchemy import text

        cutoff_30d = (jdatetime.date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        result = await self._session.execute(
            text("""
            SELECT AVG(trade_volume) as avg_vol
            FROM brsapi_historical_daily
            WHERE symbol = :sym
              AND date >= :cutoff
              AND trade_volume > 0
        """),
            {"sym": symbol, "cutoff": cutoff_30d},
        )

        row = result.fetchone()
        return safe_row_float(row, idx=0, default=0)

    def _analyze_symbol(self, snap: dict[str, Any], avg_vol_20d: float) -> AccumulationResult | None:
        """Analyze a single snapshot for hidden accumulation."""
        symbol = snap.get("symbol", "")
        name = snap.get("name", "")

        price_last = float(snap.get("price_last") or 0)
        price_close = float(snap.get("price_close") or price_last)

        trade_volume = int(snap.get("trade_volume") or 0)
        _trade_value = float(snap.get("trade_value") or 0)

        buy_real = int(snap.get("buy_real_volume") or 0)
        buy_legal = int(snap.get("buy_legal_volume") or 0)
        sell_real = int(snap.get("sell_real_volume") or 0)
        sell_legal = int(snap.get("sell_legal_volume") or 0)

        _buy_real_cnt = int(snap.get("buy_real_count") or 0)
        _buy_legal_cnt = int(snap.get("buy_legal_count") or 0)
        _sell_real_cnt = int(snap.get("sell_real_count") or 0)
        _sell_legal_cnt = int(snap.get("sell_legal_count") or 0)

        if price_last <= 0 or trade_volume <= 0 or avg_vol_20d <= 0:
            return None

        # Volume ratio vs 20-day average
        vol_ratio = trade_volume / avg_vol_20d

        # Price change percentage
        price_change_pct = abs(price_last - price_close) / price_close * 100 if price_close > 0 else 0

        # Net real money flow (positive = net buying)
        net_real_flow = (buy_real + buy_legal) - (sell_real + sell_legal)

        # Buy pressure ratio
        total_buy = buy_real + buy_legal
        total_sell = sell_real + sell_legal
        buy_pressure = total_buy / (total_buy + total_sell) if (total_buy + total_sell) > 0 else 0.5

        details = {
            "volume_ratio": round(vol_ratio, 2),
            "price_change_pct": round(price_change_pct, 2),
            "net_real_flow": net_real_flow,
            "buy_pressure": round(buy_pressure, 2),
        }

        score = 0.0
        reasons = []

        # Pattern 1: Volume surge with minimal price change (CORE SIGNAL)
        if vol_ratio >= 2.0 and price_change_pct < 1.0:
            score += 30
            reasons.append(f"حجم {vol_ratio:.1f}x میانگین با تغییر قیمت {price_change_pct:.1f}٪")

        # Pattern 2: Strong net buying pressure
        if net_real_flow > 0 and buy_pressure > 0.6:
            score += 25
            reasons.append(f"فشار خرید خالص {buy_pressure * 100:.0f}٪")

        # Pattern 3: Volume surge + net buying (strongest signal)
        if vol_ratio >= 2.5 and net_real_flow > 0:
            score += 20
            reasons.append("ترکیب حجم بالا و خرید خالص")

        # Pattern 4: High legal buying (smart money)
        if buy_legal > sell_legal and buy_legal > 0:
            score += 15
            reasons.append(f"خرید حقوقی {buy_legal:,} در برابر فروش {sell_legal:,}")

        # Pattern 5: Very high volume (3x+) regardless of other factors
        if vol_ratio >= 3.0:
            score += 10
            reasons.append(f"حجم فوق‌العاده {vol_ratio:.1f}x میانگین")

        score = min(100, score)

        if score < 30:
            return None

        return AccumulationResult(
            symbol=symbol,
            name=name,
            is_accumulating=True,
            score=score,
            volume_ratio=vol_ratio,
            price_change_pct=price_change_pct,
            net_real_flow=net_real_flow,
            details=details,
            reason=" | ".join(reasons),
        )
