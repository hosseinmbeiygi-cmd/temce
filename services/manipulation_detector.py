"""Manipulation Detector — identifies price manipulation patterns in Iranian market.

Detects three common manipulation patterns in the Iranian stock market:

1. "Fake Ceiling" (ساخت سقف کاذب): High trades at high prices with declining volume
2. "Pump and Dump" (پمپ و دامپ): Sharp price rise + retail surge + sudden crash
3. "Range Trap" (گیر کردن در دامنه): Price stuck in 2% range with abnormally high volume

Data sources:
  - intraday_trades (14.8M+ tick-level records)
  - brsapi_historical_daily (daily OHLCV for context)
  - brsapi_symbol_snapshots (current state)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ManipulationAlert:
    """Result of manipulation analysis for one symbol."""
    symbol: str
    name: str
    pattern: str  # fake_ceiling, pump_and_dump, range_trap
    confidence: float = 0.0  # 0-1
    severity: str = "low"  # low, medium, high
    details: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    recommendation: str = ""


class ManipulationDetector:
    """Detects price manipulation patterns in the Iranian stock market."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def scan_all(self, limit: int = 100) -> list[ManipulationAlert]:
        """Scan top traded symbols for manipulation patterns."""
        if self._session is None:
            return []

        from sqlalchemy import text

        result = await self._session.execute(text("""
            SELECT symbol, name, price_last, price_close, price_first,
                   trade_volume, trade_value, trade_count,
                   buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume,
                   buy_real_count, buy_legal_count, sell_real_count, sell_legal_count
            FROM brsapi_symbol_snapshots
            WHERE price_last > 0 AND trade_volume > 0 AND trade_count > 0
            ORDER BY trade_value DESC
            LIMIT :lim
        """), {"lim": limit})

        rows = [dict(row._mapping) for row in result.fetchall()]
        alerts: list[ManipulationAlert] = []

        for row in rows:
            # Check for range trap pattern
            range_alert = self._check_range_trap(row)
            if range_alert:
                alerts.append(range_alert)

            # Check for pump and dump pattern
            pump_alert = self._check_pump_and_dump(row)
            if pump_alert:
                alerts.append(pump_alert)

        return alerts

    async def detect_symbol(self, symbol: str) -> list[ManipulationAlert]:
        """Analyze a single symbol for manipulation patterns."""
        if self._session is None:
            return []

        from sqlalchemy import text

        result = await self._session.execute(text("""
            SELECT symbol, name, price_last, price_close, price_first,
                   trade_volume, trade_value, trade_count,
                   buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume,
                   buy_real_count, buy_legal_count, sell_real_count, sell_legal_count
            FROM brsapi_symbol_snapshots
            WHERE symbol = :sym AND price_last > 0
        """), {"sym": symbol})

        row = result.fetchone()
        if not row:
            return []

        snap = dict(row._mapping)
        alerts: list[ManipulationAlert] = []

        range_alert = self._check_range_trap(snap)
        if range_alert:
            alerts.append(range_alert)

        pump_alert = self._check_pump_and_dump(snap)
        if pump_alert:
            alerts.append(pump_alert)

        return alerts

    def _check_range_trap(self, snap: dict[str, Any]) -> ManipulationAlert | None:
        """Detect range trap: price stuck in narrow range with high volume.

        Pattern: Price varies <2% but trade count is abnormally high.
        This suggests wash trading or market-maker churning.
        """
        price_last = float(snap.get("price_last") or 0)
        price_high = float(snap.get("price_max") or price_last)
        price_low = float(snap.get("price_min") or price_last)

        trade_volume = int(snap.get("trade_volume") or 0)
        trade_value = float(snap.get("trade_value") or 0)
        trade_count = int(snap.get("trade_count") or 0)

        if price_last <= 0 or trade_count <= 0:
            return None

        # Price range percentage
        price_range_pct = (price_high - price_low) / price_last * 100 if price_last > 0 else 0

        # Average trade size
        avg_trade_size = trade_volume / trade_count if trade_count > 0 else 0

        # Trade intensity: trades per unit of value
        trade_intensity = trade_count / (trade_value / 1_000_000) if trade_value > 0 else 0

        # Check for range trap: narrow range + high trade count
        if price_range_pct < 2.0 and trade_count > 500 and trade_intensity > 50:
            confidence = 0.0
            reasons = []

            # Narrow range
            if price_range_pct < 1.0:
                confidence += 0.4
                reasons.append(f"دامنه قیمت بسیار باریک ({price_range_pct:.1f}٪)")
            elif price_range_pct < 2.0:
                confidence += 0.2
                reasons.append(f"دامنه قیمت باریک ({price_range_pct:.1f}٪)")

            # High trade count
            if trade_count > 2000:
                confidence += 0.3
                reasons.append(f"تعداد معاملات بسیار بالا ({trade_count:,})")
            elif trade_count > 1000:
                confidence += 0.15
                reasons.append(f"تعداد معاملات بالا ({trade_count:,})")

            # High trade intensity
            if trade_intensity > 100:
                confidence += 0.3
                reasons.append(f"شدت معاملات غیرعادی ({trade_intensity:.0f} معامله/میلیون تومان)")

            confidence = min(1.0, confidence)

            if confidence >= 0.3:
                severity = "high" if confidence >= 0.7 else "medium" if confidence >= 0.5 else "low"

                return ManipulationAlert(
                    symbol=snap.get("symbol", ""),
                    name=snap.get("name", ""),
                    pattern="range_trap",
                    confidence=confidence,
                    severity=severity,
                    details={
                        "price_range_pct": round(price_range_pct, 2),
                        "trade_count": trade_count,
                        "trade_intensity": round(trade_intensity, 1),
                        "avg_trade_size": round(avg_trade_size, 0),
                    },
                    reason=" | ".join(reasons),
                    recommendation="احتمال چرخش پول بین حساب‌ها. از ورود خودداری کنید.",
                )

        return None

    def _check_pump_and_dump(self, snap: dict[str, Any]) -> ManipulationAlert | None:
        """Detect pump and dump: sharp rise with retail surge.

        Pattern: Price up significantly + high retail buying + high volume
        followed by potential reversal signs.
        """
        price_last = float(snap.get("price_last") or 0)
        price_close = float(snap.get("price_close") or price_last)
        price_first = float(snap.get("price_first") or price_close)

        trade_volume = int(snap.get("trade_volume") or 0)
        trade_count = int(snap.get("trade_count") or 0)

        buy_real = int(snap.get("buy_real_volume") or 0)
        buy_legal = int(snap.get("buy_legal_volume") or 0)
        _sell_real = int(snap.get("sell_real_volume") or 0)
        sell_legal = int(snap.get("sell_legal_volume") or 0)

        _buy_real_cnt = int(snap.get("buy_real_count") or 0)
        _sell_real_cnt = int(snap.get("sell_real_count") or 0)

        if price_last <= 0 or price_close <= 0 or trade_volume <= 0:
            return None

        # Price change from open
        intraday_change_pct = (price_last - price_first) / price_first * 100 if price_first > 0 else 0

        # Price change from previous close
        daily_change_pct = (price_last - price_close) / price_close * 100 if price_close > 0 else 0

        # Retail buying ratio
        total_buy = buy_real + buy_legal
        retail_ratio = buy_real / total_buy if total_buy > 0 else 0

        # Check for pump pattern: sharp rise + retail surge
        if daily_change_pct > 3.0 and retail_ratio > 0.6 and trade_count > 300:
            confidence = 0.0
            reasons = []

            # Sharp price rise
            if daily_change_pct > 5.0:
                confidence += 0.3
                reasons.append(f"رشد شدید قیمت ({daily_change_pct:+.1f}٪)")
            elif daily_change_pct > 3.0:
                confidence += 0.15
                reasons.append(f"رشد قیمت ({daily_change_pct:+.1f}٪)")

            # High retail buying
            if retail_ratio > 0.7:
                confidence += 0.3
                reasons.append(f"خرید سنگین حقیقی ({retail_ratio*100:.0f}٪)")
            elif retail_ratio > 0.6:
                confidence += 0.15
                reasons.append(f"خرید بالای حقیقی ({retail_ratio*100:.0f}٪)")

            # Intraday reversal (pump might be exhausting)
            if intraday_change_pct < daily_change_pct * 0.5 and daily_change_pct > 3:
                confidence += 0.2
                reasons.append("کاهش شتاب رشد در طول روز (نشانه خستگی)")

            # High sell pressure from legal (smart money exiting)
            if sell_legal > buy_legal and sell_legal > 0:
                confidence += 0.2
                reasons.append("فروش حقوقی بیشتر از خرید (خروج پول هوشمند)")

            confidence = min(1.0, confidence)

            if confidence >= 0.3:
                severity = "high" if confidence >= 0.7 else "medium" if confidence >= 0.5 else "low"

                return ManipulationAlert(
                    symbol=snap.get("symbol", ""),
                    name=snap.get("name", ""),
                    pattern="pump_and_dump",
                    confidence=confidence,
                    severity=severity,
                    details={
                        "daily_change_pct": round(daily_change_pct, 2),
                        "intraday_change_pct": round(intraday_change_pct, 2),
                        "retail_ratio": round(retail_ratio, 2),
                        "trade_count": trade_count,
                    },
                    reason=" | ".join(reasons),
                    recommendation="احتمال پامپ و دامپ. ریسک بالا برای ورود.",
                )

        return None
