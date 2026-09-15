"""Scorer — 6-component امتیازدهی ۰-۱۰۰.

هر component حداکثر weight خود. جمع = 100.
Decision: GREEN >= 80, YELLOW >= 55, RED < 55.

اگر hard_stop فعال باشد → RED مطلق (score حفظ می‌شود ولی decision قرمز).
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    BUBBLE_GREEN_MAX,
    BUBBLE_ORANGE_MAX,
    BUBBLE_YELLOW_MAX,
    FUND_FLOW_GREEN_MIN,
    FUND_FLOW_YELLOW_MIN,
    NAV_GREEN_MAX,
    NAV_RED_MAX,
    NAV_YELLOW_MAX,
    PARITY_GREEN_MAX,
    PARITY_RED_MAX,
    PARITY_YELLOW_MAX,
    RSI_DANGER,
    RSI_GREEN_MAX,
    RSI_GREEN_MIN,
    RSI_YELLOW_MAX,
    SCORE_GREEN_MIN,
    SCORE_WEIGHTS,
    SCORE_YELLOW_MIN,
    TSETMC_BPR_GREEN,
    TSETMC_BPR_ORANGE,
    TSETMC_BPR_YELLOW,
    TSETMC_INFLOW_GREEN,
    TSETMC_INFLOW_YELLOW,
)


@dataclass(frozen=True)
class ScoreComponent:
    value: int
    max_value: int
    reason: str


@dataclass(frozen=True)
class ScoreResult:
    total: int
    decision: str  # GREEN | YELLOW | RED
    components: dict[str, ScoreComponent]
    hard_stop_active: bool
    hard_stop_reason: str | None


def _clip(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def score_bubble(bubble_pct: float | None) -> ScoreComponent:
    """حباب سکه امامی."""
    max_v = SCORE_WEIGHTS["bubble"]
    if bubble_pct is None:
        return ScoreComponent(0, max_v, "داده حباب موجود نیست")
    if bubble_pct < BUBBLE_GREEN_MAX:
        return ScoreComponent(max_v, max_v, f"حباب {bubble_pct:.1f}٪ < {BUBBLE_GREEN_MAX}٪ — عالی")
    if bubble_pct < BUBBLE_YELLOW_MAX:
        v = _clip(int(max_v * 0.75), 0, max_v)
        return ScoreComponent(v, max_v, f"حباب {bubble_pct:.1f}٪ — سبز کم‌رنگ")
    if bubble_pct < BUBBLE_ORANGE_MAX:
        v = _clip(int(max_v * 0.4), 0, max_v)
        return ScoreComponent(v, max_v, f"حباب {bubble_pct:.1f}٪ — نارنجی (احتیاط)")
    return ScoreComponent(0, max_v, f"حباب {bubble_pct:.1f}٪ > {BUBBLE_ORANGE_MAX}٪ — قرمز")


def score_nav(nav_bubble_pct: float | None) -> ScoreComponent:
    """P/NAV صندوق عیار."""
    max_v = SCORE_WEIGHTS["nav"]
    if nav_bubble_pct is None:
        return ScoreComponent(0, max_v, "NAV موجود نیست")
    if nav_bubble_pct <= NAV_GREEN_MAX:
        return ScoreComponent(max_v, max_v, f"NAV {nav_bubble_pct:.2f}٪ — تخفیف/نزدیک")
    if nav_bubble_pct <= NAV_YELLOW_MAX:
        v = _clip(int(max_v * 0.75), 0, max_v)
        return ScoreComponent(v, max_v, f"NAV {nav_bubble_pct:.2f}٪ — حباب کم")
    if nav_bubble_pct <= NAV_RED_MAX:
        v = _clip(int(max_v * 0.3), 0, max_v)
        return ScoreComponent(v, max_v, f"NAV {nav_bubble_pct:.2f}٪ — بالا")
    return ScoreComponent(0, max_v, f"NAV {nav_bubble_pct:.2f}٪ — حباب شدید")


def score_tsetmc(bpr: float | None, net_inflow: float | None) -> ScoreComponent:
    """قدرت خریدار + ورود پول حقیقی."""
    max_v = SCORE_WEIGHTS["tsetmc"]
    if bpr is None:
        return ScoreComponent(0, max_v, "BPR موجود نیست")

    # توزیع ثابت: 11 امتیاز BPR + 7 امتیاز inflow = 18 (max)
    bpr_pts = 0
    if bpr >= TSETMC_BPR_GREEN:
        bpr_pts = 11
    elif bpr >= TSETMC_BPR_YELLOW:
        bpr_pts = 8
    elif bpr >= TSETMC_BPR_ORANGE:
        bpr_pts = 4
    else:
        bpr_pts = 0

    inflow_pts = 0
    if net_inflow is not None and net_inflow > TSETMC_INFLOW_GREEN:
        inflow_pts = 7
    elif net_inflow is not None and net_inflow > TSETMC_INFLOW_YELLOW:
        inflow_pts = 4

    total = _clip(bpr_pts + inflow_pts, 0, max_v)
    reason = f"BPR={bpr:.2f}، Inflow={net_inflow or 0:,.0f}"
    return ScoreComponent(total, max_v, reason)


def score_technical(rsi: float | None) -> ScoreComponent:
    """RSI ۱۴ روزه XAU."""
    max_v = SCORE_WEIGHTS["technical"]
    if rsi is None:
        return ScoreComponent(0, max_v, "RSI موجود نیست")
    if RSI_GREEN_MIN <= rsi <= RSI_GREEN_MAX:
        return ScoreComponent(max_v, max_v, f"RSI={rsi:.0f} — ناحیه خرید")
    if rsi < RSI_GREEN_MIN:
        # اشباع فروش شدید = فرصت (اما کمی ریسک)
        return ScoreComponent(int(max_v * 0.6), max_v, f"RSI={rsi:.0f} — اشباع فروش")
    if rsi <= RSI_YELLOW_MAX:
        return ScoreComponent(int(max_v * 0.7), max_v, f"RSI={rsi:.0f} — خنثی")
    if rsi <= RSI_DANGER:
        return ScoreComponent(int(max_v * 0.3), max_v, f"RSI={rsi:.0f} — گرم")
    return ScoreComponent(0, max_v, f"RSI={rsi:.0f} — اشباع خرید")


def score_parity(aed_gap_pct: float | None) -> ScoreComponent:
    """|شکاف درهم| (هرچه کمتر، بهتر)."""
    max_v = SCORE_WEIGHTS["parity"]
    if aed_gap_pct is None:
        return ScoreComponent(0, max_v, "AED gap موجود نیست")
    gap = abs(aed_gap_pct)
    if gap < PARITY_GREEN_MAX:
        return ScoreComponent(max_v, max_v, f"|gap|={gap:.2f}٪ — متعادل")
    if gap < PARITY_YELLOW_MAX:
        return ScoreComponent(int(max_v * 0.7), max_v, f"|gap|={gap:.2f}٪ — کمی偏离")
    if gap < PARITY_RED_MAX:
        return ScoreComponent(int(max_v * 0.3), max_v, f"|gap|={gap:.2f}٪ — انحراف")
    return ScoreComponent(0, max_v, f"|gap|={gap:.2f}٪ — آربیتراژ شدید")


def score_fund_flow(nav_7d_pct: float | None) -> ScoreComponent:
    """بازدهی NAV صندوق عیار در ۷ روز اخیر."""
    max_v = SCORE_WEIGHTS["fund_flow"]
    if nav_7d_pct is None:
        return ScoreComponent(0, max_v, "NAV 7d موجود نیست")
    if nav_7d_pct >= FUND_FLOW_GREEN_MIN:
        return ScoreComponent(max_v, max_v, f"NAV 7d: +{nav_7d_pct:.2f}٪ — صعودی")
    if nav_7d_pct >= FUND_FLOW_YELLOW_MIN:
        return ScoreComponent(int(max_v * 0.6), max_v, f"NAV 7d: {nav_7d_pct:.2f}٪ — خنثی")
    if nav_7d_pct >= -1.0:
        return ScoreComponent(int(max_v * 0.3), max_v, f"NAV 7d: {nav_7d_pct:.2f}٪ — کاهش جزئی")
    return ScoreComponent(0, max_v, f"NAV 7d: {nav_7d_pct:.2f}٪ — نزولی")


def compute_score(
    *,
    bubble_pct: float | None,
    nav_bubble_pct: float | None,
    bpr: float | None,
    net_inflow: float | None,
    xau_rsi: float | None,
    aed_gap_pct: float | None,
    nav_7d_pct: float | None,
    hard_stop_active: bool = False,
    hard_stop_reason: str | None = None,
) -> ScoreResult:
    """محاسبه امتیاز کلی.

    اگر hard_stop → decision = RED بدون تغییر در total.
    """
    comps = {
        "bubble": score_bubble(bubble_pct),
        "nav": score_nav(nav_bubble_pct),
        "tsetmc": score_tsetmc(bpr, net_inflow),
        "technical": score_technical(xau_rsi),
        "parity": score_parity(aed_gap_pct),
        "fund_flow": score_fund_flow(nav_7d_pct),
    }
    total = sum(c.value for c in comps.values())

    if hard_stop_active:
        decision = "RED"
    elif total >= SCORE_GREEN_MIN:
        decision = "GREEN"
    elif total >= SCORE_YELLOW_MIN:
        decision = "YELLOW"
    else:
        decision = "RED"

    return ScoreResult(
        total=total,
        decision=decision,
        components=comps,
        hard_stop_active=hard_stop_active,
        hard_stop_reason=hard_stop_reason,
    )
