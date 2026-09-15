"""DCA Planner — تخصیص پله‌ای با fee محاسبه‌شده.

3 risk profile:
- conservative: 20/40/40 — فقط در امتیاز سبز
- balanced: 30/40/30 (پیش‌فرض)
- aggressive: 50/30/20

هر tranche شامل:
- مبلغ سرمایه
- trigger شرطی
- vehicle پیشنهادی + fee تخمینی
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import VEHICLE_FEES


@dataclass(frozen=True)
class Tranche:
    tranche: int
    pct: float
    amount_irt: float
    trigger: str
    vehicle: str
    estimated_fee_irt: float


@dataclass(frozen=True)
class DCAPlan:
    total_capital_irt: float
    ladder: list[Tranche]
    recommended_vehicle: str
    total_fee_irt: float
    net_investable_irt: float
    stop_loss_pct: float
    take_profit_pct: float


# الگوی پله‌ای
LADDER_PATTERNS: dict[str, list[tuple[float, str]]] = {
    "conservative": [
        (0.20, "حباب سکه < 10٪ و امتیاز ≥ ۸۰"),
        (0.40, "اصلاح ۳-۵٪ + ورود پول حقیقی"),
        (0.40, "شکست مقاومت + حجم بالا"),
    ],
    "balanced": [
        (0.30, "حباب < 15٪ و شکاف درهم < 1.5٪"),
        (0.40, "اصلاح قیمتی ۳-۵٪ + BPR > 1.5"),
        (0.30, "شکست مقاومت کوتاه‌مدت"),
    ],
    "aggressive": [
        (0.50, "ورود با امتیاز ≥ ۵۰"),
        (0.30, "اصلاح ۲٪+"),
        (0.20, "شکست مقاومت"),
    ],
}


def _recommend_vehicle(score: int) -> str:
    """انتخاب vehicle بر اساس امتیاز فعلی."""
    if score >= 75:
        return "etf"  # نقدشوندگی بالا، کارمزد کم
    if score >= 60:
        return "cert"  # شمش
    return "melted"  # طلای آب‌شده (سرمایه‌گذاری بلندمدت)


def _calc_fee(amount_irt: float, vehicle: str) -> float:
    """کارمزد خرید تخمینی برای یک tranche."""
    fees = VEHICLE_FEES.get(vehicle, VEHICLE_FEES["etf"])
    buy_pct = fees["buy_pct"] / 100.0
    return amount_irt * buy_pct


def plan_dca(
    total_capital_irt: float,
    risk_profile: str = "balanced",
    current_score: int = 60,
    preferred_vehicle: str | None = None,
) -> DCAPlan:
    """ساخت پلن DCA.

    Args:
        total_capital_irt: کل سرمایه (تومان)
        risk_profile: conservative | balanced | aggressive
        current_score: امتیاز فعلی (۰-۱۰۰)
        preferred_vehicle: etf | cert | melted | coin | jewelry (None = auto)

    Returns:
        DCAPlan با ladder، total fee، stop/take profit.
    """
    if total_capital_irt <= 0:
        raise ValueError(f"capital must be > 0: {total_capital_irt}")
    if not 0 <= current_score <= 100:
        raise ValueError(f"score must be 0-100: {current_score}")
    if risk_profile not in LADDER_PATTERNS:
        raise ValueError(f"unknown risk profile: {risk_profile}")

    vehicle = preferred_vehicle or _recommend_vehicle(current_score)
    pattern = LADDER_PATTERNS[risk_profile]

    ladder: list[Tranche] = []
    total_fee = 0.0
    for i, (pct, trigger) in enumerate(pattern, start=1):
        amount = total_capital_irt * pct
        fee = _calc_fee(amount, vehicle)
        total_fee += fee
        ladder.append(
            Tranche(
                tranche=i,
                pct=pct,
                amount_irt=amount,
                trigger=trigger,
                vehicle=vehicle,
                estimated_fee_irt=fee,
            )
        )

    # Stop / Take Profit (بر اساس risk profile)
    if risk_profile == "conservative":
        stop_loss, take_profit = 5.0, 20.0
    elif risk_profile == "balanced":
        stop_loss, take_profit = 8.0, 25.0
    else:
        stop_loss, take_profit = 12.0, 35.0

    return DCAPlan(
        total_capital_irt=total_capital_irt,
        ladder=ladder,
        recommended_vehicle=vehicle,
        total_fee_irt=total_fee,
        net_investable_irt=total_capital_irt - total_fee,
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
    )
