"""AI Pattern Detector — کشف خودکار الگوهای bubble در داده‌های تاریخی.

الگوهای قابل تشخیص:
1. **Mean reversion**: bubble > 20% معمولاً به 5-10% برمی‌گردد
2. **Trend continuation**: bubble صعودی پایدار → ادامه می‌یابد
3. **Spike & crash**: bubble در ۳ روز > 10% افزایش → احتمال اصلاح
4. **Volatility regime**: نوسان بالا = ریسک بالا

قاعدهٔ واحد: هر آماری که در خروجی می‌نشیند (``historical_hit_rate``) یا از همان
سری محاسبه می‌شود یا صفر با ``sample_size`` کوچک گزارش می‌شود؛ عدد ثابتِ
«۶۲٪/۵۸٪» حذف شد (E-M13). میانگین متحرک هم فقط trailing است (E-H6).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable

import jdatetime
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import utc_now_naive

from . import indicators
from .constants import SMA_BUBBLE_WINDOW
from .dates import jalali_days_ago

logger = logging.getLogger(__name__)

# ── آستانه‌های الگو (واحد: روز معاملاتی یا درصد) ────────────────────
# پنجره‌ای که برای تأیید «روند» بررسی می‌شود و حداقل روزهای مثبت در آن.
TREND_CONFIRM_WINDOW: int = 10
TREND_MIN_POSITIVE_DAYS: int = 7
# افق سنجش موفقیت یک الگو: بازده قیمت پس از این تعداد روز.
FORWARD_HORIZON_DAYS: int = 5
# آستانهٔ «جهش»: درصد تغییر قیمت در ۳ روز.
SPIKE_3D_THRESHOLD_PCT: float = 5.0
# کمتر از این تعداد نمونهٔ تاریخی، نرخ موفقیت «ادعا» نیست؛ صفر با sample می‌آید.
MIN_HISTORY_SAMPLES: int = 3

# مقادیر مجاز recommendation — هر تغییری در متن توصیه باید اینجا ثبت شود.
RECOMMENDATION_WAIT = "صبر کنید"
RECOMMENDATION_CAUTIOUS_BUY = "خرید محتاطانه (صبر برای تأیید)"
RECOMMENDATION_WAIT_FOR_DIP = "صبر کنید (خرید در اصلاح)"
RECOMMENDATION_WAIT_VOLATILE = "صبر کنید (رژیم نوسانی)"
RECOMMENDATIONS: tuple[str, ...] = (
    RECOMMENDATION_WAIT,
    RECOMMENDATION_CAUTIOUS_BUY,
    RECOMMENDATION_WAIT_FOR_DIP,
    RECOMMENDATION_WAIT_VOLATILE,
)


@dataclass(frozen=True)
class DetectedPattern:
    """یک الگوی شناسایی‌شده."""

    pattern_type: str  # mean_reversion | trend_continuation | spike_crash | vol_regime
    confidence: float  # 0-1
    description: str
    expected_direction: str  # up | down | neutral
    expected_magnitude_pct: float
    historical_hit_rate: float  # درصد موفقیت در نمونهٔ تاریخی؛ ۰ با sample_size کوچک
    sample_size: int


@dataclass(frozen=True)
class PatternReport:
    """گزارش الگوهای شناسایی‌شده."""

    symbol: str
    period_start: datetime
    period_end: datetime
    patterns: list[DetectedPattern]
    summary: str
    recommendation: str  # یکی از مقادیر RECOMMENDATIONS


_TRIGGER = Callable[[np.ndarray, int], bool]


def _historical_hit_rate(
    prices, trigger: _TRIGGER, direction: str, horizon: int = FORWARD_HORIZON_DAYS
) -> tuple[float, int]:
    """نرخ موفقیت تاریخی یک trigger روی **همین** سری.

    موفقیت = حرکت قیمت در جهت انتظار الگو پس از ``horizon`` روز. فقط روزهایی
    شمرده می‌شوند که trigger در آن‌ها (با داده تا همان روز) فعال بوده است.
    """
    arr = np.asarray(prices, dtype=float)
    hits = trials = 0
    for i in range(len(arr) - horizon):
        if not trigger(arr, i):
            continue
        trials += 1
        change = arr[i + horizon] - arr[i]
        if (direction == "up" and change > 0) or (direction == "down" and change < 0):
            hits += 1
    if trials < MIN_HISTORY_SAMPLES:
        return 0.0, trials
    return hits / trials * 100.0, trials


def _trend_trigger(arr: np.ndarray, i: int) -> bool:
    """آیا در روز ``i`` شرط «روند صعودی پایدار» برقرار است؟"""
    if i + 1 < TREND_CONFIRM_WINDOW:
        return False
    window = arr[i + 1 - TREND_CONFIRM_WINDOW : i + 1]
    returns = np.diff(window) / window[:-1]
    return int((returns > 0).sum()) >= TREND_MIN_POSITIVE_DAYS


def _spike_trigger(arr: np.ndarray, i: int) -> bool:
    """آیا در روز ``i`` جهش > آستانه در ۳ روز رخ داده است؟"""
    if i < 2 or arr[i - 2] <= 0:
        return False
    return (arr[i] - arr[i - 2]) / arr[i - 2] * 100.0 > SPIKE_3D_THRESHOLD_PCT


def _parse_jalali(value: str) -> datetime | None:
    """تاریخ شمسی ``YYYY-MM-DD`` را به ``datetime`` میلادی تبدیل می‌کند."""
    parts = str(value).strip().replace("/", "-").split("-")
    if len(parts) != 3:
        return None
    try:
        j = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (TypeError, ValueError):
        return None
    return datetime.combine(j.togregorian(), time.min)


async def _fetch_closes(session: AsyncSession, symbol: str, days: int) -> list[tuple[str, float]]:
    try:
        from brsapi.models.commodity import GoldCoinHistoryModel

        # تاریخ‌ها ستون شمسی است؛ jalali_days_ago cutoff را به شمسی تبدیل می‌کند
        cutoff = jalali_days_ago(days)
        stmt = (
            select(GoldCoinHistoryModel.date, GoldCoinHistoryModel.price_close)
            .where(GoldCoinHistoryModel.symbol == symbol, GoldCoinHistoryModel.date >= cutoff)
            .order_by(GoldCoinHistoryModel.date)
        )
        # برخلاف cutoff میلادی قبلی، این-filter تاریخ میلادی را حذف می‌کند و
        #jalaali_days_ago اطمینان می‌دهد که فقط ردیف‌های شمسی برگردانده می‌شود (E-C3).
        result = await session.execute(stmt)
        return [(str(r[0]), float(r[1])) for r in result.all() if r[1] and r[1] > 0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("pattern fetch failed: %s", exc, exc_info=True)
        return []


def _detect_mean_reversion(prices: list[float]) -> DetectedPattern | None:
    """وقتی bubble > 20% باشد، آیا در ۳۰ روز بعد به < 10% برمی‌گردد؟"""
    if len(prices) < 60:
        return None

    arr = np.array(prices, dtype=float)
    rolling_mean = pd_rolling_mean(arr, SMA_BUBBLE_WINDOW)
    with np.errstate(invalid="ignore"):
        bubble = (arr - rolling_mean) / rolling_mean * 100

    signals = []
    for i in range(len(arr) - 30):
        if np.isnan(bubble[i]) or np.isnan(rolling_mean[i]):
            continue
        if bubble[i] > 20:
            future = arr[i + 30]
            future_bubble = (future - rolling_mean[i]) / rolling_mean[i] * 100
            signals.append(bool(future_bubble < 10))

    if len(signals) < MIN_HISTORY_SAMPLES:
        return None
    hit_rate = sum(signals) / len(signals) * 100
    return DetectedPattern(
        pattern_type="mean_reversion",
        confidence=min(0.9, len(signals) / 20),
        description="الگوی بازگشت به میانگین: bubble>20% معمولاً به <10% برمی‌گردد",
        expected_direction="down",
        expected_magnitude_pct=-12.0,
        historical_hit_rate=hit_rate,
        sample_size=len(signals),
    )


def _detect_trend(prices: list[float]) -> DetectedPattern | None:
    """تشخیص روند صعودی پایدار (۷+ روز مثبت در ۱۰ روز اخیر)."""
    if len(prices) < 5:
        return None
    arr = np.asarray(prices, dtype=float)
    if not _trend_trigger(arr, len(arr) - 1):
        return None
    window = arr[-TREND_CONFIRM_WINDOW:] if len(arr) >= TREND_CONFIRM_WINDOW else arr
    pos_days = int((np.diff(window) / window[:-1] > 0).sum())
    hit_rate, sample = _historical_hit_rate(prices, _trend_trigger, "up")
    return DetectedPattern(
        pattern_type="trend_continuation",
        confidence=0.6,
        description=f"روند صعودی قوی ({pos_days} روز مثبت در ۱۰ روز اخیر)",
        expected_direction="up",
        expected_magnitude_pct=2.5,
        historical_hit_rate=hit_rate,
        sample_size=sample,
    )


def _detect_spike(prices: list[float]) -> DetectedPattern | None:
    """تشخیص spike: افزایش > ۵٪ در ۳ روز."""
    if len(prices) < 4:
        return None
    arr = np.asarray(prices, dtype=float)
    if not _spike_trigger(arr, len(arr) - 1):
        return None
    change_3d = (arr[-1] - arr[-3]) / arr[-3] * 100
    hit_rate, sample = _historical_hit_rate(prices, _spike_trigger, "down")
    return DetectedPattern(
        pattern_type="spike_crash",
        confidence=0.55,
        description=f"جهش {change_3d:.1f}٪ در ۳ روز — احتمال اصلاح",
        expected_direction="down",
        expected_magnitude_pct=-3.0,
        historical_hit_rate=hit_rate,
        sample_size=sample,
    )


def _detect_vol_regime(prices: list[float]) -> DetectedPattern | None:
    """رژیم نوسان بالا = ریسک بالا."""
    if len(prices) < 20:
        return None
    arr = np.array(prices[-20:])
    returns = np.diff(arr) / arr[:-1]
    vol = np.std(returns) * 100
    if vol > 2.0:
        return DetectedPattern(
            pattern_type="vol_regime",
            confidence=0.7,
            description=f"نوسان روزانه {vol:.2f}٪ — رژیم پرنوسان (ریسک بالا)",
            expected_direction="neutral",
            expected_magnitude_pct=0.0,
            historical_hit_rate=0.0,
            sample_size=20,
        )
    return None


def pd_rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    """rolling mean ساده و **trailing** (بدون backfill).

    پیش‌تر عناصر ``window-1`` اول با میانگین پنجرهٔ آینده پر می‌شدند و bubble
    روزهای ابتدایی از دادهٔ آینده ساخته می‌شد (E-H6).
    """
    return indicators.sma(arr, window)


async def detect_patterns(
    session: AsyncSession,
    symbol: str = "IR_COIN_EMAMI",
    days: int = 90,
) -> PatternReport:
    """تشخیص همه الگوها."""
    closes = await _fetch_closes(session, symbol, days)
    if not closes:
        return PatternReport(
            symbol=symbol,
            period_start=utc_now_naive(),
            period_end=utc_now_naive(),
            patterns=[],
            summary="داده کافی نیست",
            recommendation=RECOMMENDATION_WAIT,
        )

    prices = [c for _, c in closes]
    patterns: list[DetectedPattern] = []
    for detector in (_detect_mean_reversion, _detect_trend, _detect_spike, _detect_vol_regime):
        try:
            p = detector(prices)
            if p:
                patterns.append(p)
        except Exception as exc:  # noqa: BLE001
            logger.debug("detector %s failed: %s", detector.__name__, exc)

    # خلاصه و توصیه
    if not patterns:
        summary = "هیچ الگوی قابل‌توجهی شناسایی نشد"
        recommendation = RECOMMENDATION_WAIT
    else:
        best = max(patterns, key=lambda p: p.confidence)
        summary = f"الگوی غالب: {best.pattern_type} (confidence: {best.confidence:.0%})"
        if best.expected_direction == "up":
            recommendation = RECOMMENDATION_CAUTIOUS_BUY
        elif best.expected_direction == "down":
            recommendation = RECOMMENDATION_WAIT_FOR_DIP
        else:
            recommendation = RECOMMENDATION_WAIT_VOLATILE

    # تاریخ‌ها شمسی ذخیره شده‌اند؛ fromisoformat آن‌ها را «سال ۱۴۰۵ میلادی»
    # می‌کرد (E-M12). پارس واقعی + fallback به زمان فعلی.
    period_start = _parse_jalali(closes[0][0]) or utc_now_naive()
    period_end = _parse_jalali(closes[-1][0]) or utc_now_naive()

    return PatternReport(
        symbol=symbol,
        period_start=period_start,
        period_end=period_end,
        patterns=patterns,
        summary=summary,
        recommendation=recommendation,
    )
