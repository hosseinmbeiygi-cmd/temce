from __future__ import annotations

from dataclasses import dataclass, field

from core.logging import get_logger
from services.codal_analysis.analysis_engine import ComprehensiveAnalysis

logger = get_logger(__name__)

INDUSTRY_BENCHMARKS: dict[str, dict[str, dict[str, float]]] = {
    "تولیدی": {
        "gross_margin": {"median": 0.25, "q1": 0.15, "q3": 0.35},
        "net_margin": {"median": 0.10, "q1": 0.05, "q3": 0.18},
        "current_ratio": {"median": 1.5, "q1": 1.1, "q3": 2.0},
        "debt_to_equity": {"median": 1.0, "q1": 0.5, "q3": 1.8},
        "roe": {"median": 0.20, "q1": 0.10, "q3": 0.30},
        "roa": {"median": 0.10, "q1": 0.05, "q3": 0.18},
        "asset_turnover": {"median": 0.8, "q1": 0.5, "q3": 1.2},
    },
    "بانک": {
        "net_margin": {"median": 0.30, "q1": 0.20, "q3": 0.45},
        "roe": {"median": 0.25, "q1": 0.15, "q3": 0.35},
        "roa": {"median": 0.02, "q1": 0.01, "q3": 0.03},
        "debt_to_equity": {"median": 8.0, "q1": 5.0, "q3": 12.0},
    },
    "پتروشیمی": {
        "gross_margin": {"median": 0.35, "q1": 0.20, "q3": 0.50},
        "net_margin": {"median": 0.15, "q1": 0.08, "q3": 0.25},
        "current_ratio": {"median": 1.8, "q1": 1.3, "q3": 2.5},
        "debt_to_equity": {"median": 0.8, "q1": 0.3, "q3": 1.5},
        "roe": {"median": 0.25, "q1": 0.15, "q3": 0.40},
    },
    "فولاد": {
        "gross_margin": {"median": 0.20, "q1": 0.12, "q3": 0.30},
        "net_margin": {"median": 0.08, "q1": 0.04, "q3": 0.15},
        "current_ratio": {"median": 1.3, "q1": 1.0, "q3": 1.8},
        "debt_to_equity": {"median": 1.2, "q1": 0.6, "q3": 2.0},
        "roe": {"median": 0.18, "q1": 0.08, "q3": 0.28},
    },
    "سیمانی": {
        "gross_margin": {"median": 0.30, "q1": 0.20, "q3": 0.40},
        "net_margin": {"median": 0.12, "q1": 0.06, "q3": 0.20},
        "current_ratio": {"median": 1.2, "q1": 0.8, "q3": 1.6},
        "debt_to_equity": {"median": 1.5, "q1": 0.8, "q3": 2.5},
        "roe": {"median": 0.15, "q1": 0.08, "q3": 0.25},
    },
}


@dataclass
class BenchmarkComparison:
    metric: str
    company_value: float | None
    industry_median: float | None
    percentile: float | None
    status: str


@dataclass
class IndustryBenchmarkResult:
    industry: str
    comparisons: list[BenchmarkComparison] = field(default_factory=list)
    above_median_count: int = 0
    total_comparisons: int = 0


def compare_with_industry(analysis: ComprehensiveAnalysis, industry: str) -> IndustryBenchmarkResult:
    benchmarks = INDUSTRY_BENCHMARKS.get(industry)
    if not benchmarks:
        for key, val in INDUSTRY_BENCHMARKS.items():
            if key in industry:
                benchmarks = val
                break
    if not benchmarks:
        return IndustryBenchmarkResult(industry=industry)

    result = IndustryBenchmarkResult(industry=industry)
    metric_map = {
        "gross_margin": analysis.ratios.profitability.get("gross_margin"),
        "net_margin": analysis.ratios.profitability.get("net_margin"),
        "roe": analysis.ratios.profitability.get("roe"),
        "roa": analysis.ratios.profitability.get("roa"),
        "current_ratio": analysis.ratios.liquidity.get("current_ratio"),
        "debt_to_equity": analysis.ratios.leverage.get("debt_to_equity"),
        "asset_turnover": analysis.ratios.activity.get("asset_turnover"),
    }

    for metric, company_value in metric_map.items():
        bench = benchmarks.get(metric)
        if not bench or company_value is None:
            continue

        median = bench["median"]
        q1 = bench["q1"]
        q3 = bench["q3"]

        if company_value <= median:
            percentile = 50 * (company_value - q1) / (median - q1) if q1 != median else 25
        else:
            percentile = 50 + 50 * (company_value - median) / (q3 - median) if q3 != median else 75

        percentile = max(0, min(100, percentile))

        if company_value > q3:
            status = "above_industry"
        elif company_value < q1:
            status = "below_industry"
        else:
            status = "within_industry"

        result.comparisons.append(BenchmarkComparison(
            metric=metric,
            company_value=company_value,
            industry_median=median,
            percentile=round(percentile, 1),
            status=status,
        ))
        if status == "above_industry":
            result.above_median_count += 1

    result.total_comparisons = len(result.comparisons)
    return result
