"""
Dynamic Weighting — وزندهی پویای زیر-نمرهها بر اساس رژیم بازار
===============================================================

وزنهای ثابت مدل ۱۱۰ ستونه (Screener110Service.WEIGHTS) را با توجه به
شرایط جاری بازار تعدیل میکند:

  * رژیم رکودی (نوسان ۳ روز اخیر شاخص < ۲٪):
      → وزن تکنیکال کم میشود، وزن بنیادی/ارزشگذاری زیاد میشود
  * رژیم جهش حجمی (حجم بازار ≥ ۳ برابر میانگین ۲۰ روزه):
      → وزن تکنیکال و نهادی (جریان پول) زیاد میشود
  * رژیم نزولی (شاخص ۳ روز اخیر منفی):
      → وزن نقدشوندگی زیاد، وزن حمایت دولتی کم میشود

دادههای ورودی از:
  * brsapi_index_values        (شاخص کل — نوسان و روند)
  * brsapi_symbol_snapshots    (حجم معاملات کل بازار)

Usage:
    weights = await get_dynamic_weights(session)
    weights = await get_dynamic_weights(session, base_weights=my_weights)
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.screener110_service import WEIGHTS as BASE_WEIGHTS

logger = get_logger(__name__)

# آستانههای رژیم
LOW_VOLATILITY_3D_PCT = 2.0     # نوسان ۳ روزه شاخص (درصد) — زیر این مقدار = رکود
VOLUME_SPIKE_MULTIPLIER = 3.0   # جهش حجم بازار نسبت به میانگین ۲۰ روزه

# دامنه تغییر هر وزن (نسبت به وزن پایه)
MAX_WEIGHT_SCALE = 1.30
MIN_WEIGHT_SCALE = 0.70


class MarketSignalProvider:
    """مقادیر خام رژیم بازار از دیتابیس."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_index_signal(self) -> dict[str, float]:
        """نوسان ۳ روزه و تغییر ۳ روزه شاخص کل (درصد)."""
        try:
            rows = (await self._session.execute(text("""
                SELECT value, created_at
                FROM brsapi_index_values
                WHERE name = 'شاخص کل' OR name = 'TEDIX' OR name LIKE '%کل%'
                ORDER BY created_at DESC
                LIMIT 4
            """))).fetchall()
            values = [float(r[0]) for r in rows if r[0] is not None]
            if len(values) < 2:
                return {"volatility_3d": 0.0, "change_3d": 0.0, "available": False}
            changes = [abs(values[i] - values[i + 1]) / values[i + 1] * 100
                       for i in range(min(3, len(values) - 1))]
            vol = sum(changes) / max(len(changes), 1)
            change_3d = (values[0] - values[-1]) / values[-1] * 100 if values[-1] else 0.0
            return {"volatility_3d": vol, "change_3d": change_3d, "available": True}
        except Exception:  # noqa: BLE001
            logger.exception("Failed to read index signal")
            return {"volatility_3d": 0.0, "change_3d": 0.0, "available": False}

    async def get_volume_signal(self) -> dict[str, float]:
        """نسبت حجم معاملات امروز بازار به میانگین ۲۰ روزه."""
        try:
            rows = (await self._session.execute(text("""
                SELECT trade_value, created_at
                FROM brsapi_symbol_snapshots
                WHERE trade_value IS NOT NULL AND trade_value > 0
                ORDER BY created_at DESC
            """))).fetchall()
            if not rows:
                return {"volume_ratio": 0.0, "available": False}

            # گروهبندی بر اساس تاریخ (هر روز = مجموع ارزش معاملات)
            daily: dict[str, float] = {}
            for r in rows:
                day = str(r[1])[:10]
                daily[day] = daily.get(day, 0.0) + float(r[0])
            day_values = [v for _, v in sorted(daily.items(), reverse=True)]
            if len(day_values) < 2:
                return {"volume_ratio": 1.0, "available": False}

            today = day_values[0]
            avg_20 = sum(day_values[1:21]) / max(len(day_values[1:21]), 1)
            ratio = today / avg_20 if avg_20 else 1.0
            return {"volume_ratio": ratio, "available": True}
        except Exception:  # noqa: BLE001
            logger.exception("Failed to read volume signal")
            return {"volume_ratio": 1.0, "available": False}


class DynamicWeighting:
    """وزنهای پویا برای مدل ۱۱۰ ستونه."""

    def __init__(self, session: AsyncSession) -> None:
        self._provider = MarketSignalProvider(session)

    async def compute(
        self,
        base_weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        base = dict(base_weights or BASE_WEIGHTS)
        weights = dict(base)
        index = await self._provider.get_index_signal()
        volume = await self._provider.get_volume_signal()

        adjustments: dict[str, str] = {}

        # ── رژیم رکودی: نوسان کم → تکنیکال کم، بنیادی/ارزش زیاد ──
        if index.get("volatility_3d", 0) < LOW_VOLATILITY_3D_PCT and index.get("available"):
            weights["technical"] *= 0.85
            weights["fundamental"] *= 1.10
            weights["valuation"] *= 1.10
            adjustments["regime"] = "low_volatility"

        # ── رژیم جهش حجمی: حجم ≥ ۳x میانگین → تکنیکال/نهادی زیاد ──
        if volume.get("volume_ratio", 0) >= VOLUME_SPIKE_MULTIPLIER and volume.get("available"):
            weights["technical"] *= 1.20
            weights["institutional"] *= 1.15
            adjustments["volume"] = "spike"

        # ── رژیم نزولی: شاخص ۳ روز اخیر منفی → نقدشوندگی زیاد، حمایت دولتی کم ──
        if index.get("change_3d", 0) < 0 and index.get("available"):
            weights["liquidity"] *= 1.15
            weights["gov_support"] *= 0.90
            adjustments["trend"] = "bearish"

        # ── محدودسازی مقیاس نسبت به وزن پایه (نه محدوده مطلق) ──
        for key in weights:
            if base.get(key, 0) > 0:
                scale = weights[key] / base[key]
                clamped = max(MIN_WEIGHT_SCALE, min(MAX_WEIGHT_SCALE, scale))
                weights[key] = base[key] * clamped

        # ── نرمالسازی: مجموع = ۱ ──
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

        logger.info("Dynamic weights: %s (%s)", weights, adjustments or "no adjustment")
        return weights


async def get_dynamic_weights(
    session: AsyncSession,
    base_weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """Convenience wrapper."""
    service = DynamicWeighting(session)
    return await service.compute(base_weights=base_weights)
