from __future__ import annotations

"""Phase exit criteria for the trading simulator roadmap.

Each phase has defined, measurable criteria that must be met before
proceeding to the next phase. This module provides both the definition
and the evaluation logic.
"""

from dataclasses import dataclass, field


@dataclass
class PhaseCriterion:
    name: str
    description: str
    passed: bool = False
    value: float = 0.0
    threshold: float = 0.0
    details: str = ""


@dataclass
class PhaseExitResult:
    phase_name: str
    phase_number: int
    all_passed: bool = False
    criteria: list[PhaseCriterion] = field(default_factory=list)
    summary: str = ""


PHASE_1_CRITERIA = [
    PhaseCriterion("architecture_stable", "معماری فنی و ابزارها تثبیت شده", threshold=1.0),
    PhaseCriterion("cost_model_verified", "مدل هزینه معاملات با داده واقعی تایید شده", threshold=1.0),
    PhaseCriterion("data_source_selected", "منبع داده قطعی برای هر بازار مشخص شده", threshold=1.0),
]

PHASE_2_CRITERIA = [
    PhaseCriterion("spread_estimator_ready", "تخمین‌گر اسپرد کرون-شولتز پیاده‌سازی شده", threshold=1.0),
    PhaseCriterion("slippage_dynamic", "مدل اسلیپیج پویا بر اساس حجم+نوسان فعال است", threshold=1.0),
    PhaseCriterion("latency_sensitivity", "تحلیل حساسیت تأخیر پیاده‌سازی شده", threshold=1.0),
    PhaseCriterion("partial_fill_model", "مدل پر شدن جزئی سفارش تعریف شده", threshold=1.0),
]

PHASE_3_CRITERIA = [
    PhaseCriterion("data_quality_report", "گزارش کیفیت داده برای هر بازار تولید می‌شود", threshold=1.0),
    PhaseCriterion("missing_data_policy", "خط مشی داده‌های گمشده پیاده‌سازی شده", threshold=1.0),
    PhaseCriterion("no_synthetic_fill", "داده گمشده با داده ساختگی پر نمی‌شود", threshold=1.0),
]

PHASE_4_CRITERIA = [
    PhaseCriterion("correlation_module", "تحلیل همبستگی با بنچمارک پیاده‌سازی شده", threshold=1.0),
    PhaseCriterion("regime_detection", "تشخیص رژیم بازار (عادی/روند/وحشت/...) فعال است", threshold=1.0),
    PhaseCriterion("confidence_scoring", "امتیاز اطمینان مبتنی بر عوامل چندگانه محاسبه می‌شود", threshold=1.0),
]

PHASE_5_CRITERIA = [
    PhaseCriterion("bootstrap_test", "آزمون بوت‌استرپ برای معناداری Expectancy جایگزین t-test شده", threshold=1.0),
    PhaseCriterion("sign_test", "آزمون Sign برای میانه PnL پیاده‌سازی شده", threshold=1.0),
    PhaseCriterion("wilcoxon_test", "آزمون Wilcoxon Signed-Rank برای توزیع غیرنرمال پیاده‌سازی شده", threshold=1.0),
    PhaseCriterion("sortino_for_options", "Sortino Ratio برای استراتژی‌های غیرنرمال استفاده می‌شود", threshold=1.0),
]

PHASE_6_CRITERIA = [
    PhaseCriterion(
        "wf_positive_80pct", "حداقل ۸۰٪ پنجره‌های Walk-Forward Expectancy مثبت با فاصله اطمینان ۹۵٪", threshold=80.0
    ),
    PhaseCriterion(
        "regime_target_positive", "Expectancy در رژیم‌های هدف مثبت و در سایر رژیم‌ها بدون ضرر چشمگیر", threshold=1.0
    ),
    PhaseCriterion("slippage_error_below", "میانگین خطای اسلیپیج تخمینی کمتر از X٪", threshold=1.0),
]

PHASE_7_CRITERIA = [
    PhaseCriterion("min_30_trades", "حداقل ۳۰ معامله در Paper Trading ثبت شده", threshold=30.0),
    PhaseCriterion(
        "paper_vs_backtest_tracked", "مقایسه هفتگی نتایج Paper Trading با پیش‌بینی بک‌تست ثبت می‌شود", threshold=1.0
    ),
]

PHASE_8_CRITERIA = [
    PhaseCriterion("stress_scenarios_defined", "سناریوهای استرس (نقدشوندگی، نوسان، شوک قیمت) تعریف شده", threshold=1.0),
    PhaseCriterion("slippage_3x_stress", "سناریوی استرس با اسلیپیج ۳-۵ برابر عادی طراحی شده", threshold=1.0),
    PhaseCriterion("missing_data_stress", "سناریوی قطع داده و شکست سیستمی تعریف شده", threshold=1.0),
]

ALL_PHASES = {
    1: ("Phase 1: Architecture & Tools", PHASE_1_CRITERIA),
    2: ("Phase 2: Trading Costs", PHASE_2_CRITERIA),
    3: ("Phase 3: Data Quality", PHASE_3_CRITERIA),
    4: ("Phase 4: Scoring & Regime", PHASE_4_CRITERIA),
    5: ("Phase 5: Statistical Tests", PHASE_5_CRITERIA),
    6: ("Phase 6: Exit Criteria", PHASE_6_CRITERIA),
    7: ("Phase 7: Paper Trading", PHASE_7_CRITERIA),
    8: ("Phase 8: Stress Scenarios", PHASE_8_CRITERIA),
}


def evaluate_phase(phase_number: int, criteria_values: dict[str, float]) -> PhaseExitResult:
    phase_info = ALL_PHASES.get(phase_number)
    if not phase_info:
        return PhaseExitResult(phase_name=f"Phase {phase_number}", phase_number=phase_number, summary="Unknown phase")
    name, criteria_defs = phase_info
    evaluated = []
    all_pass = True
    for c in criteria_defs:
        val = criteria_values.get(c.name, 0.0)
        passed = val >= c.threshold
        evaluated.append(
            PhaseCriterion(name=c.name, description=c.description, passed=passed, value=val, threshold=c.threshold)
        )
        if not passed:
            all_pass = False
    return PhaseExitResult(
        phase_name=name,
        phase_number=phase_number,
        all_passed=all_pass,
        criteria=evaluated,
        summary="Passed" if all_pass else "Failed - criteria not met",
    )
