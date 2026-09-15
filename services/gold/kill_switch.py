"""Kill-Switch — آشکارساز بحران برای بازار طلا.

قوانین (طبق پرامپت):
  1. volatility_circuit_breaker: نوسان اونس یا دلار > 5% در < 2h
  2. futures_margin_shock: افزایش ناگهانی وجه تضمین اولیه توسط بورس کالا
  3. systemic_freeze: توقف نمادهای طلا در بورس یا تعطیلی بازار

خروجی: وضعیت NORMAL / WARNING / ACTIVE + دلیل + قانون فعال
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

VOLATILITY_THRESHOLD_PCT = 5.0  # % تغییر
VOLATILITY_WINDOW_MINUTES = 120  # 2 ساعت


@dataclass
class KillSwitchEvaluation:
    status: str  # NORMAL / WARNING / ACTIVE
    reason: str | None = None
    triggered_at: str | None = None
    active_rules: list[str] = field(default_factory=list)
    directive: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


def _pct_change(old: float, new: float) -> float:
    if old <= 0:
        return 0.0
    return ((new - old) / old) * 100.0


def evaluate_kill_switch(
    current_oz_usd: float,
    current_usd_irr: float,
    oz_history: list[tuple[datetime, float]] | None = None,
    usd_history: list[tuple[datetime, float]] | None = None,
    market_frozen: bool = False,
) -> KillSwitchEvaluation:
    """ارزیابی وضعیت فعلی.

    Args:
        current_oz_usd, current_usd_irr: قیمت لحظه‌ای
        oz_history, usd_history: [(datetime, price), ...] — اگر خالی باشد NORMAL برمی‌گردد
        market_frozen: آیا نمادهای طلا در بورس متوقف هستند؟
    """
    active: list[str] = []
    metrics: dict[str, Any] = {}

    # 1. Systemic freeze → ACTIVE فوری
    if market_frozen:
        return KillSwitchEvaluation(
            status="ACTIVE",
            reason="توقف نمادهای طلا در بورس یا تعطیلی بازار",
            triggered_at=datetime.utcnow().isoformat() + "Z",
            active_rules=["systemic_freeze"],
            directive=("لغو تمامی سفارش‌های در صف، خروج از موقعیت‌های اهرمی آتی (IME)، حفظ موقعیت‌های ETF بدون اهرم."),
            metrics={"market_frozen": True},
        )

    # 2. volatility circuit breaker
    if oz_history:
        oz_pct = _max_pct_in_window(oz_history, current_oz_usd, VOLATILITY_WINDOW_MINUTES)
        metrics["oz_pct_change"] = oz_pct
        if abs(oz_pct) > VOLATILITY_THRESHOLD_PCT:
            active.append("volatility_circuit_breaker")
    if usd_history:
        usd_pct = _max_pct_in_window(usd_history, current_usd_irr, VOLATILITY_WINDOW_MINUTES)
        metrics["usd_pct_change"] = usd_pct
        if abs(usd_pct) > VOLATILITY_THRESHOLD_PCT:
            active.append("volatility_circuit_breaker")

    if not active:
        return KillSwitchEvaluation(status="NORMAL", metrics=metrics)

    # همه چیز ACTIVE می‌شود چون سیگنال طلا یک بازار ریسکی است
    return KillSwitchEvaluation(
        status="ACTIVE",
        reason=(
            f"نوسان شدید در بازه {VOLATILITY_WINDOW_MINUTES // 60}h: "
            f"اونس {metrics.get('oz_pct_change', 0):.2f}% | "
            f"دلار {metrics.get('usd_pct_change', 0):.2f}%"
        ),
        triggered_at=datetime.utcnow().isoformat() + "Z",
        active_rules=active,
        directive=(
            "توقف صدور سیگنال‌های خرید جدید. بازنگری پوزیشن‌های اهرمی. صندوق‌های ETF بدون اهرم قابل نگهداری هستند."
        ),
        metrics=metrics,
    )


def _max_pct_in_window(history: list[tuple[datetime, float]], current: float, window_minutes: int) -> float:
    if not history:
        return 0.0
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    relevant = [p for t, p in history if t >= cutoff]
    if not relevant:
        return 0.0
    base = relevant[0]
    return _pct_change(base, current)
