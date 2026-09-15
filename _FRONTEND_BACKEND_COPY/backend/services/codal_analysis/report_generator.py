from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.logging import get_logger
from services.codal_analysis.analysis_engine import (
    ComprehensiveAnalysis,
    DuPontAnalysis,
    HorizontalAnalysis,
    RatioAnalysis,
)
from services.codal_analysis.benchmark import IndustryBenchmarkResult, compare_with_industry
from services.codal_analysis.scoring import FinancialHealthScore, compute_health_score, generate_interpretations

logger = get_logger(__name__)


@dataclass
class ReportSection:
    title: str
    content: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisReport:
    symbol: str
    fiscal_period: str
    generated_at: str
    overall_score: float
    classification: str
    sections: list[ReportSection] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    analysis_status: str = "full"
    missing_components: list[str] = field(default_factory=list)


def generate_report(analysis: ComprehensiveAnalysis) -> AnalysisReport:
    health = compute_health_score(analysis)
    industry = "تولیدی"
    benchmark = compare_with_industry(analysis, industry)
    interpretations = generate_interpretations(analysis)

    report = AnalysisReport(
        symbol=analysis.symbol,
        fiscal_period=analysis.fiscal_period,
        generated_at=datetime.now().isoformat(),
        overall_score=health.overall_score,
        classification=health.classification,
        analysis_status=analysis.analysis_status,
        missing_components=analysis.missing_components,
    )

    report.sections.append(_executive_summary(health, analysis))
    report.sections.append(_financial_highlights(analysis))
    report.sections.append(_ratio_analysis_section(analysis.ratios))
    report.sections.append(_dupont_section(analysis.dupont))
    report.sections.append(_earnings_quality_section(analysis))
    report.sections.append(_benchmark_section(benchmark))
    report.sections.append(_interpretations_section(interpretations))
    report.sections.append(_horizontal_section(analysis.horizontal))

    for warning in analysis.earnings_quality.warnings:
        report.alerts.append(
            {
                "type": "warning",
                "severity": "medium",
                "message": warning,
            }
        )

    return report


def _executive_summary(health: FinancialHealthScore, analysis: ComprehensiveAnalysis) -> ReportSection:
    return ReportSection(
        title="خلاصه اجرایی",
        content={
            "symbol": analysis.symbol,
            "period": analysis.fiscal_period,
            "overall_score": health.overall_score,
            "classification": health.classification,
            "financial_strength": health.financial_strength,
            "earnings_quality": health.earnings_quality,
            "liquidity_stability": health.liquidity_stability,
            "leverage_risk": health.leverage_risk,
            "profitability": health.profitability,
            "score_label": _get_score_label(health.overall_score),
        },
    )


def _financial_highlights(analysis: ComprehensiveAnalysis) -> ReportSection:
    snap = analysis.snapshot
    return ReportSection(
        title="ارقام کلیدی صورت‌های مالی",
        content={
            "revenue": snap.revenue,
            "gross_profit": snap.gross_profit,
            "operating_profit": snap.operating_profit,
            "net_profit": snap.net_profit,
            "total_assets": snap.total_assets,
            "total_liabilities": snap.total_liabilities,
            "equity": snap.total_equity,
            "operating_cash_flow": snap.operating_cash_flow,
        },
    )


def _ratio_analysis_section(ratios: RatioAnalysis) -> ReportSection:
    return ReportSection(
        title="تحلیل نسبت‌های مالی",
        content={
            "profitability": {k: _safe_pct(v) for k, v in ratios.profitability.items()},
            "liquidity": {k: _safe_val(v) for k, v in ratios.liquidity.items()},
            "leverage": {k: _safe_val(v) for k, v in ratios.leverage.items()},
            "activity": {k: _safe_val(v) for k, v in ratios.activity.items()},
            "cash_flow": {k: _safe_val(v) for k, v in ratios.cash_flow.items()},
        },
    )


def _dupont_section(dupont: DuPontAnalysis) -> ReportSection:
    return ReportSection(
        title="تحلیل دوپونت",
        content={
            "net_profit_margin": _safe_pct(dupont.net_profit_margin),
            "asset_turnover": _safe_val(dupont.asset_turnover),
            "equity_multiplier": _safe_val(dupont.equity_multiplier),
            "roe_direct": _safe_pct(dupont.roe),
            "roe_dupont": _safe_pct(dupont.roe_dupont),
            "breakdown": {
                "profit_margin_contribution": dupont.net_profit_margin if dupont.net_profit_margin else 0,
                "turnover_contribution": dupont.asset_turnover if dupont.asset_turnover else 0,
                "leverage_contribution": dupont.equity_multiplier if dupont.equity_multiplier else 0,
            },
        },
    )


def _earnings_quality_section(analysis: ComprehensiveAnalysis) -> ReportSection:
    eq = analysis.earnings_quality
    return ReportSection(
        title="کیفیت سود",
        content={
            "cash_conversion_ratio": _safe_val(eq.cash_conversion_ratio),
            "accruals_ratio": _safe_val(eq.accruals_ratio),
            "receivables_growth_vs_revenue": _safe_val(eq.receivables_growth_vs_revenue),
            "quality_score": eq.quality_score,
            "warnings": eq.warnings,
        },
    )


def _benchmark_section(benchmark: IndustryBenchmarkResult) -> ReportSection:
    return ReportSection(
        title="مقایسه با صنعت",
        content={
            "industry": benchmark.industry,
            "above_median_count": benchmark.above_median_count,
            "total_comparisons": benchmark.total_comparisons,
            "comparisons": [
                {
                    "metric": c.metric,
                    "company_value": _safe_val(c.company_value),
                    "industry_median": _safe_val(c.industry_median),
                    "percentile": c.percentile,
                    "status": c.status,
                }
                for c in benchmark.comparisons
            ],
        },
    )


def _interpretations_section(interpretations: list[str]) -> ReportSection:
    return ReportSection(
        title="تفسیر خودکار",
        content={"items": interpretations},
    )


def _horizontal_section(horizontal: HorizontalAnalysis) -> ReportSection:
    return ReportSection(
        title="تحلیل روند",
        content={
            "revenue_growth": _safe_pct(horizontal.revenue_growth),
            "gross_profit_growth": _safe_pct(horizontal.gross_profit_growth),
            "operating_profit_growth": _safe_pct(horizontal.operating_profit_growth),
            "net_profit_growth": _safe_pct(horizontal.net_profit_growth),
            "total_assets_growth": _safe_pct(horizontal.total_assets_growth),
            "total_liabilities_growth": _safe_pct(horizontal.total_liabilities_growth),
            "equity_growth": _safe_pct(horizontal.equity_growth),
        },
    )


def _safe_pct(val: float | None) -> float | None:
    if val is None:
        return None
    if val == float("inf"):
        return None
    return round(val * 100, 2)


def _safe_val(val: float | None) -> float | None:
    if val is None:
        return None
    if val == float("inf") or val == float("-inf"):
        return None
    return round(val, 4)


def _get_score_label(score: float) -> str:
    if score >= 0.75:
        return "قوی"
    if score >= 0.55:
        return "باثبات"
    if score >= 0.35:
        return "تحت نظر"
    return "پرخطر"


def report_to_json(report: AnalysisReport) -> str:
    data = {
        "symbol": report.symbol,
        "fiscal_period": report.fiscal_period,
        "generated_at": report.generated_at,
        "overall_score": report.overall_score,
        "classification": report.classification,
        "analysis_status": report.analysis_status,
        "sections": {s.title: s.content for s in report.sections},
        "alerts": report.alerts,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
