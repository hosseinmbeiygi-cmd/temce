from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.codal_analysis.analysis_engine import (
    ComprehensiveAnalysis,
    RatioAnalysis,
)


@dataclass
class FinancialHealthScore:
    overall_score: float
    classification: str
    financial_strength: float = 0
    earnings_quality: float = 0
    liquidity_stability: float = 0
    leverage_risk: float = 0
    profitability: float = 0
    details: dict[str, Any] = field(default_factory=dict)


SCORING_CONFIG: dict[str, dict[str, Any]] = {
    "profitability": {
        "weight": 0.25,
        "metrics": {
            "net_margin": {"min": 0, "max": 0.3, "good": 0.1},
            "roe": {"min": 0, "max": 0.4, "good": 0.2},
            "roa": {"min": 0, "max": 0.2, "good": 0.1},
        },
    },
    "liquidity": {
        "weight": 0.20,
        "metrics": {
            "current_ratio": {"min": 0.5, "max": 3.0, "good": 1.5},
            "quick_ratio": {"min": 0.2, "max": 2.0, "good": 1.0},
        },
    },
    "leverage": {
        "weight": 0.20,
        "metrics": {
            "debt_to_equity": {"min": 0, "max": 3.0, "good": 0.5, "inverse": True},
            "interest_coverage": {"min": 0, "max": 10, "good": 3},
        },
    },
    "efficiency": {
        "weight": 0.15,
        "metrics": {
            "asset_turnover": {"min": 0, "max": 2, "good": 0.8},
        },
    },
    "earnings_quality": {
        "weight": 0.20,
        "metrics": {
            "cash_conversion_ratio": {"min": 0, "max": 2, "good": 1.0},
        },
    },
}


def _score_metric(value: float | None, config: dict) -> float:
    if value is None:
        return 0.5
    min_v = config["min"]
    max_v = config["max"]
    config["good"]
    inverse = config.get("inverse", False)

    if inverse:
        raw = 1 - (value - min_v) / (max_v - min_v) if max_v != min_v else 0.5
    else:
        raw = (value - min_v) / (max_v - min_v) if max_v != min_v else 0.5

    return max(0, min(1, raw))


def compute_health_score(analysis: ComprehensiveAnalysis) -> FinancialHealthScore:
    ratios = analysis.ratios

    category_scores: dict[str, float] = {}
    for category_name, category_cfg in SCORING_CONFIG.items():
        metric_scores = []
        for metric_name, metric_cfg in category_cfg["metrics"].items():
            value = _get_ratio_value(ratios, metric_name)
            score = _score_metric(value, metric_cfg)
            metric_scores.append(score)
        category_scores[category_name] = sum(metric_scores) / len(metric_scores) if metric_scores else 0.5

    category_scores["earnings_quality"] = analysis.earnings_quality.quality_score

    overall = sum(
        category_scores.get(cat, 0) * cfg["weight"]
        for cat, cfg in SCORING_CONFIG.items()
    )
    overall = max(0, min(1, overall))

    if overall >= 0.75:
        classification = "Strong"
    elif overall >= 0.55:
        classification = "Stable"
    elif overall >= 0.35:
        classification = "Watchlist"
    else:
        classification = "Risky"

    return FinancialHealthScore(
        overall_score=round(overall, 4),
        classification=classification,
        financial_strength=round(category_scores.get("profitability", 0) * 0.5 + category_scores.get("efficiency", 0) * 0.3 + category_scores.get("earnings_quality", 0) * 0.2, 4),
        earnings_quality=round(analysis.earnings_quality.quality_score, 4),
        liquidity_stability=round(category_scores.get("liquidity", 0), 4),
        leverage_risk=round(1 - category_scores.get("leverage", 0), 4),
        profitability=round(category_scores.get("profitability", 0), 4),
        details={
            "category_scores": {k: round(v, 4) for k, v in category_scores.items()},
            "warnings": analysis.earnings_quality.warnings,
        },
    )


def _get_ratio_value(ratios: RatioAnalysis, name: str) -> float | None:
    for category in [ratios.profitability, ratios.liquidity, ratios.leverage, ratios.activity, ratios.cash_flow]:
        if name in category:
            return category[name]
    return None


INTERPRETATION_TEMPLATES: dict[str, dict[str, str]] = {
    "net_margin": {
        "high": "حاشیه سود خالص مطلوب نشان‌دهنده سودآوری مناسب شرکت است",
        "low": "حاشیه سود خالص پایین نشان‌دهنده فشار بر سودآوری شرکت است",
    },
    "roe": {
        "high": "بازده حقوق صاحبان سهام خوب نشان‌دهنده استفاده مؤثر از سرمایه سهامداران است",
        "low": "بازده حقوق صاحبان سهام پایین است",
    },
    "debt_to_equity": {
        "high": "نسبت بدهی به حقوق صاحبان سهام بالا نشان‌دهنده ریسک مالی بالاست",
        "low": "نسبت بدهی به حقوق صاحبان سهام در محدوده قابل قبول است",
    },
    "current_ratio": {
        "high": "نسبت جاری در محدوده مطلوب نشان‌دهنده نقدینگی مناسب است",
        "low": "نسبت جاری پایین نشان‌دهنده تنش نقدینگی است",
    },
}


def generate_interpretations(analysis: ComprehensiveAnalysis) -> list[str]:
    texts = []
    for metric_name, templates in INTERPRETATION_TEMPLATES.items():
        value = _get_ratio_value(analysis.ratios, metric_name)
        if value is None:
            continue
        for condition, text in templates.items():
            if condition == "high" and value > 0.15 or condition == "low" and value < 0.05:
                texts.append(f"{text} ({value:.1%})")
    return texts
