"""
📊 Queue Analysis Engine — تحلیل صف‌های خرید و فروش در بورس تهران

این ماژول ۵ ویژگی جدید صف را محاسبه می‌کند:
  1. queue_status  — وضعیت صف (BUY_QUEUE / SELL_QUEUE / NONE)
  2. queue_volume_ratio  — نسبت حجم صف به معاملات (0-1)
  3. queue_days_streak  — تعداد روزهای متوالی در صف
  4. queue_type_change  — تغییر وضعیت صف نسبت به روز قبل
  5. distance_to_limit  — فاصله تا سقف/کف دامنه نوسان (%)

با پشتیبانی از دامنه نوسان ۳٪ بورس تهران و ۵٪ فرابورس.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

# ── Enums ──────────────────────────────────────────────────────────


class QueueStatus(StrEnum):
    """وضعیت صف در پایان روز معاملاتی."""
    BUY_QUEUE = "BUY_QUEUE"      # صف خرید (قیمت به سقف چسبیده)
    SELL_QUEUE = "SELL_QUEUE"    # صف فروش (قیمت به کف چسبیده)
    NONE = "NONE"                # بدون صف


class QueueTypeChange(StrEnum):
    """نوع تغییر وضعیت صف نسبت به روز قبل."""
    NEW_BUY_QUEUE = "NEW_BUY_QUEUE"      # صف خرید جدید
    NEW_SELL_QUEUE = "NEW_SELL_QUEUE"    # صف فروش جدید
    QUEUE_BROKEN = "QUEUE_BROKEN"        # شکسته شدن صف
    NO_CHANGE = "NO_CHANGE"              # بدون تغییر


# ── Data Models ─────────────────────────────────────────────────────


@dataclass
class QueueFeatures:
    """5 ویژگی صف برای یک نماد در یک روز معاملاتی."""
    queue_status: QueueStatus          # وضعیت صف
    queue_volume_ratio: float          # نسبت حجم صف (0-1)
    queue_days_streak: int             # تداوم صف (روز)
    queue_type_change: QueueTypeChange # نوع تغییر صف
    distance_to_limit: float           # فاصله تا دامنه (%)
    # Metadata
    last_price: float                  # آخرین قیمت
    limit_up: float                    # سقف مجاز
    limit_down: float                  # کف مجاز
    queue_buy_volume: float            # حجم صف خرید
    queue_sell_volume: float           # حجم صف فروش


@dataclass
class QueueHistoryEntry:
    """تاریخچه صف برای یک روز."""
    date: date
    queue_status: QueueStatus
    queue_buy_volume: float
    queue_sell_volume: float
    total_buy_volume: float
    total_sell_volume: float


# ── Price Limit Calculator ─────────────────────────────────────────


def get_price_limits(
    last_close: float,
    market_type: str = "bours",
) -> tuple[float, float]:
    """محاسبه سقف و کف مجاز روزانه بر اساس نوع بازار.

    Args:
        last_close: قیمت پایانی روز قبل
        market_type: نوع بازار (bours=3%, farabours=5%, base=1-3%)

    Returns:
        (limit_up, limit_down) — سقف و کف مجاز
    """
    if market_type in ("bours", "etf"):
        limit_pct = 0.05  # 5% برای بورس و ETF
    elif market_type == "farabours":
        limit_pct = 0.05  # 5% برای فرابورس
    elif market_type.startswith("base"):
        limit_pct = 0.03  # 3% برای بازار پایه
    else:
        limit_pct = 0.05  # پیش‌فرض

    limit_up = round(last_close * (1 + limit_pct), 0)
    limit_down = round(last_close * (1 - limit_pct), 0)
    return limit_up, limit_down


# ── Queue Status Detection ─────────────────────────────────────────


def detect_queue_status(
    last_price: float,
    limit_up: float,
    limit_down: float,
) -> QueueStatus:
    """تشخیص وضعیت صف بر اساس برخورد قیمت به سقف/کف مجاز.

    Args:
        last_price: آخرین قیمت معامله‌شده
        limit_up: سقف مجاز روزانه
        limit_down: کف مجاز روزانه

    Returns:
        QueueStatus: وضعیت صف
    """
    if last_price >= limit_up:
        return QueueStatus.BUY_QUEUE
    elif last_price <= limit_down:
        return QueueStatus.SELL_QUEUE
    else:
        return QueueStatus.NONE


def compute_queue_volume_ratio(
    queue_buy_volume: float,
    queue_sell_volume: float,
    total_buy_volume: float,
    total_sell_volume: float,
    queue_status: QueueStatus,
) -> float:
    """محاسبه نسبت حجم صف به کل حجم ثبت‌شده.

    Formula:
        BUY_QUEUE:  queue_buy_volume / (queue_buy_volume + total_sell_volume)
        SELL_QUEUE: queue_sell_volume / (queue_sell_volume + total_buy_volume)
        NONE:       0

    Returns:
        نسبت 0 تا 1. اگر > 0.7 باشد، صف بسیار سنگین است.
    """
    if queue_status == QueueStatus.BUY_QUEUE:
        denominator = queue_buy_volume + total_sell_volume
        if denominator > 0:
            return round(queue_buy_volume / denominator, 4)
    elif queue_status == QueueStatus.SELL_QUEUE:
        denominator = queue_sell_volume + total_buy_volume
        if denominator > 0:
            return round(queue_sell_volume / denominator, 4)
    return 0.0


def compute_queue_days_streak(
    current_status: QueueStatus,
    history: list[QueueHistoryEntry],
) -> int:
    """محاسبه تعداد روزهای متوالی در وضعیت صف یکسان.

    Args:
        current_status: وضعیت صف امروز
        history: تاریخچه صف (از جدیدترین به قدیمی‌ترین)

    Returns:
        تعداد روزهای متوالی. اگر صف نباشد، 0 برمی‌گرداند.
    """
    if current_status == QueueStatus.NONE:
        return 0

    streak = 1  # امروز
    for entry in history:
        if entry.queue_status == current_status:
            streak += 1
        else:
            break
    return streak


def detect_queue_type_change(
    current_status: QueueStatus,
    previous_status: QueueStatus | None,
) -> QueueTypeChange:
    """تشخیص نوع تغییر وضعیت صف نسبت به روز قبل.

    Args:
        current_status: وضعیت صف امروز
        previous_status: وضعیت صف دیروز (None اگر داده موجود نیست)

    Returns:
        QueueTypeChange: نوع تغییر
    """
    if previous_status is None:
        return QueueTypeChange.NO_CHANGE

    if current_status == QueueStatus.BUY_QUEUE and previous_status != QueueStatus.BUY_QUEUE:
        return QueueTypeChange.NEW_BUY_QUEUE
    elif current_status == QueueStatus.SELL_QUEUE and previous_status != QueueStatus.SELL_QUEUE:
        return QueueTypeChange.NEW_SELL_QUEUE
    elif current_status == QueueStatus.NONE and previous_status != QueueStatus.NONE:
        return QueueTypeChange.QUEUE_BROKEN
    else:
        return QueueTypeChange.NO_CHANGE


def compute_distance_to_limit(
    last_price: float,
    limit_up: float,
    limit_down: float,
    queue_status: QueueStatus,
) -> float:
    """محاسبه فاصله قیمت فعلی تا سقف/کف مجاز (درصد).

    Formula:
        BUY_QUEUE یا قیمت صعودی: ((limit_up - last_price) / last_price) × 100
        SELL_QUEUE یا قیمت نزولی: ((last_price - limit_down) / last_price) × 100
        NONE: 0

    Returns:
        فاصله به درصد. اگر < 0.5٪ باشد، احتمال تشکیل صف در روز بعد بالاست.
    """
    if queue_status == QueueStatus.BUY_QUEUE:
        return round(((limit_up - last_price) / last_price) * 100, 2)
    elif queue_status == QueueStatus.SELL_QUEUE:
        return round(((last_price - limit_down) / last_price) * 100, 2)
    else:
        return 0.0


# ── Pipeline ───────────────────────────────────────────────────────


def compute_queue_features(
    last_price: float,
    last_close: float,
    queue_buy_volume: float,
    queue_sell_volume: float,
    total_buy_volume: float,
    total_sell_volume: float,
    history: list[QueueHistoryEntry],
    market_type: str = "bours",
) -> QueueFeatures:
    """محاسبه تمام ۵ ویژگی صف در یک فراخوانی.

    Args:
        last_price: آخرین قیمت معامله‌شده
        last_close: قیمت پایانی روز قبل
        queue_buy_volume: حجم سفارشات خرید باقی‌مانده در صف
        queue_sell_volume: حجم سفارشات فروش باقی‌مانده در صف
        total_buy_volume: حجم کل سفارشات خرید ثبت‌شده
        total_sell_volume: حجم کل سفارشات فروش ثبت‌شده
        history: تاریخچه صف (برای محاسبه streak و type_change)
        market_type: نوع بازار

    Returns:
        QueueFeatures: تمام ۵ ویژگی صف + متادیتا
    """
    limit_up, limit_down = get_price_limits(last_close, market_type)

    # 1. وضعیت صف
    queue_status = detect_queue_status(last_price, limit_up, limit_down)

    # 2. نسبت حجم صف
    queue_volume_ratio = compute_queue_volume_ratio(
        queue_buy_volume, queue_sell_volume,
        total_buy_volume, total_sell_volume,
        queue_status,
    )

    # 3. تداوم صف
    queue_days_streak = compute_queue_days_streak(queue_status, history)

    # 4. تغییر وضعیت صف
    previous_status = history[0].queue_status if history else None
    queue_type_change = detect_queue_type_change(queue_status, previous_status)

    # 5. فاصله تا دامنه
    distance_to_limit = compute_distance_to_limit(last_price, limit_up, limit_down, queue_status)

    return QueueFeatures(
        queue_status=queue_status,
        queue_volume_ratio=queue_volume_ratio,
        queue_days_streak=queue_days_streak,
        queue_type_change=queue_type_change,
        distance_to_limit=distance_to_limit,
        last_price=last_price,
        limit_up=limit_up,
        limit_down=limit_down,
        queue_buy_volume=queue_buy_volume,
        queue_sell_volume=queue_sell_volume,
    )


# ── Score Adjustment Rules ─────────────────────────────────────────


def adjust_score_liquidity(base_liquidity_score: float, queue: QueueFeatures) -> float:
    """تعدیل S_L (نمره نقدشوندگی) بر اساس وضعیت صف.

    Rules:
        - BUY_QUEUE: افزایش نمره (+15) به دلیل وجود تقاضای بالا
        - SELL_QUEUE: کاهش شدید نمره (×0.5) چون معامله‌ای انجام نمی‌شود
        - NONE: بدون تغییر
    """
    if queue.queue_status == QueueStatus.BUY_QUEUE:
        return base_liquidity_score + 15
    elif queue.queue_status == QueueStatus.SELL_QUEUE:
        return base_liquidity_score * 0.5
    return base_liquidity_score


def adjust_score_technical(
    base_technical_score: float,
    queue: QueueFeatures,
    rsi: float | None = None,
    macd: float | None = None,
) -> float:
    """تعدیل S_T (نمره تکنیکال) بر اساس وضعیت صف.

    Rules:
        - اگر queue_days_streak >= 2:
            RSI و MACD نادیده گرفته می‌شوند.
            S_T = (queue_volume_ratio × 50) + ((100 - distance_to_limit) × 50)
        - در غیر این صورت: بدون تغییر
    """
    if queue.queue_days_streak >= 2:
        volume_component = queue.queue_volume_ratio * 50
        distance_component = (100 - min(queue.distance_to_limit, 100)) * 50
        return round(volume_component + distance_component, 1)
    return base_technical_score


def adjust_score_orderflow(
    base_orderflow_score: float,
    queue: QueueFeatures,
) -> float:
    """تعدیل S_O (نمره جریان پول) بر اساس وضعیت صف.

    Rules:
        - NEW_BUY_QUEUE: +20 امتیاز
        - NEW_SELL_QUEUE: -20 امتیاز
        - queue_volume_ratio به‌عنوان ضریب تقویت‌کننده: S_O × (1 + queue_volume_ratio)
    """
    adjusted = base_orderflow_score

    if queue.queue_type_change == QueueTypeChange.NEW_BUY_QUEUE:
        adjusted += 20
    elif queue.queue_type_change == QueueTypeChange.NEW_SELL_QUEUE:
        adjusted -= 20

    # ضریب تقویت بر اساس شدت صف
    adjusted = adjusted * (1 + queue.queue_volume_ratio)

    return round(adjusted, 1)


def adjust_penalty(
    base_penalty: float,
    queue: QueueFeatures,
) -> tuple[float, dict[str, Any]]:
    """تعدیل ضریب جریمه بر اساس وضعیت صف فروش.

    Rules:
        - SELL_QUEUE + queue_days_streak >= 3:
            penalty = min(penalty + 0.25, 0.50)
            risk_level = "CRITICAL"
        - BUY_QUEUE + queue_days_streak >= 2:
            GapRisk غیرفعال (کاهش 0.10 از جریمه)

    Returns:
        (penalty_adjusted, risk_info)
    """
    risk_info: dict[str, Any] = {
        "gap_risk_disabled": False,
        "queue_risk_level": "NORMAL",
    }

    if queue.queue_status == QueueStatus.SELL_QUEUE and queue.queue_days_streak >= 3:
        base_penalty = min(base_penalty + 0.25, 0.50)
        risk_info["queue_risk_level"] = "CRITICAL"

    if queue.queue_status == QueueStatus.BUY_QUEUE and queue.queue_days_streak >= 2:
        # غیرفعال کردن GapRisk — کاهش 0.10 از جریمه
        base_penalty = max(base_penalty - 0.10, 0.0)
        risk_info["gap_risk_disabled"] = True

    return round(base_penalty, 2), risk_info


def apply_hard_rules(
    queue: QueueFeatures,
    base_decision: str,
    base_score: float,
) -> tuple[str, str]:
    """اعمال قوانین سخت (Hard Rules) صف در موتور تصمیم‌گیری.

    Rules:
        1. BUY_QUEUE + streak < 3 + volume_ratio > 0.7 → BUY (override)
        2. SELL_QUEUE + streak > 1 → REJECT (override)

    Returns:
        (final_decision, override_reason)
    """
    override_reason = ""

    # قانون 1: صف خرید سنگین
    if (
        queue.queue_status == QueueStatus.BUY_QUEUE
        and queue.queue_days_streak < 3
        and queue.queue_volume_ratio > 0.7
    ):
        return "BUY", (
            f"Hard Rule: BUY_QUEUE با شدت {queue.queue_volume_ratio:.0%} "
            f"و تداوم {queue.queue_days_streak} روز — override به BUY "
            f"(حتی با امتیاز {base_score})"
        )

    # قانون 2: صف فروش
    if (
        queue.queue_status == QueueStatus.SELL_QUEUE
        and queue.queue_days_streak > 1
    ):
        return "REJECT", (
            f"Hard Rule: SELL_QUEUE با تداوم {queue.queue_days_streak} روز — "
            f"override به REJECT"
        )

    return base_decision, override_reason
