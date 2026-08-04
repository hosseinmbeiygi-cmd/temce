from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from services.codal_analysis.analysis_engine import FinancialSnapshot

logger = get_logger(__name__)


@dataclass
class AnalyticalProcedureResult:
    procedure_name: str
    status: str
    expected_value: float | None = None
    actual_value: float | None = None
    deviation: float | None = None
    deviation_threshold: float | None = None
    conclusion: str = ""
    risk_level: str = "low"


@dataclass
class GoingConcernAssessment:
    assessment_date: str = ""
    status: str = "going_concern"
    risk_level: str = "low"
    indicators: list[dict[str, Any]] = field(default_factory=list)
    debt_maturities: float = 0
    operating_cashflows: float = 0
    current_ratio: float | None = None
    negative_equity: bool = False
    consecutive_losses: int = 0
    adverse_audit_opinion: bool = False


@dataclass
class RiskBasedSample:
    population_value: float
    sample_size: int
    confidence_level: float
    materiality: float
    sampling_method: str
    selected_items: list[Any] = field(default_factory=list)
    projected_error: float | None = None
    upper_error_limit: float | None = None


class ProfessionalAuditWorkflow:
    """
    ISA 520: Analytical Procedures
    ISA 530: Audit Sampling
    ISA 570: Going Concern
    """

    def __init__(self):
        self.analytical_thresholds = {
            "revenue_growth": {"expected": 0.10, "threshold": 0.05},
            "gross_margin": {"expected": 0.25, "threshold": 0.08},
            "net_margin": {"expected": 0.08, "threshold": 0.05},
            "current_ratio": {"expected": 1.5, "threshold": 0.3},
            "inventory_turnover": {"expected": 4.0, "threshold": 1.5},
        }

    # ── ISA 520: Analytical Procedures ─────────────────────────────────

    def perform_analytical_procedures(self, snap: FinancialSnapshot, prev: FinancialSnapshot | None = None) -> list[AnalyticalProcedureResult]:
        results: list[AnalyticalProcedureResult] = []

        if prev:
            rev_growth = (snap.revenue - prev.revenue) / prev.revenue if prev.revenue else 0
            results.append(AnalyticalProcedureResult(
                procedure_name="revenue_trend",
                status="unusual" if abs(rev_growth) > 0.3 else "expected",
                expected_value=prev.revenue * (1 + self.analytical_thresholds["revenue_growth"]["expected"]),
                actual_value=snap.revenue,
                deviation=rev_growth,
                deviation_threshold=self.analytical_thresholds["revenue_growth"]["threshold"],
                conclusion=f"Revenue change: {rev_growth:+.1%}",
                risk_level="high" if abs(rev_growth) > 0.3 else "low",
            ))

        snap_gm = snap.gross_profit / snap.revenue if snap.revenue else 0
        prev_gm = prev.gross_profit / prev.revenue if prev and prev.revenue else snap_gm
        gm_deviation = snap_gm - prev_gm
        results.append(AnalyticalProcedureResult(
            procedure_name="gross_margin_consistency",
            status="unusual" if abs(gm_deviation) > self.analytical_thresholds["gross_margin"]["threshold"] else "expected",
            expected_value=prev_gm,
            actual_value=snap_gm,
            deviation=gm_deviation,
            deviation_threshold=self.analytical_thresholds["gross_margin"]["threshold"],
            conclusion=f"Gross margin: {snap_gm:.1%} vs prev {prev_gm:.1%}",
            risk_level="high" if abs(gm_deviation) > 0.1 else "low",
        ))

        snap_lr = snap.current_assets / snap.current_liabilities if snap.current_liabilities else 0
        results.append(AnalyticalProcedureResult(
            procedure_name="liquidity_ratio",
            status="unusual" if snap_lr < 1.0 else "expected",
            actual_value=snap_lr,
            deviation=snap_lr - self.analytical_thresholds["current_ratio"]["expected"],
            deviation_threshold=self.analytical_thresholds["current_ratio"]["threshold"],
            conclusion=f"Current ratio: {snap_lr:.2f}",
            risk_level="high" if snap_lr < 1.0 else "low",
        ))

        return results

    # ── ISA 530: Risk-Based Statistical Sampling ──────────────────────

    def risk_based_sampling(
        self,
        population_value: float,
        materiality: float,
        confidence_level: float = 0.95,
        expected_error_rate: float = 0.05,
    ) -> RiskBasedSample:
        if population_value <= 0:
            return RiskBasedSample(0, 0, confidence_level, materiality, "none")

        # MUS - Monetary Unit Sampling per ISA 530
        z_score = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence_level, 1.96)
        sample_size = max(1, int((z_score * population_value / materiality) ** 2 * expected_error_rate))
        sample_size = min(sample_size, 5000)

        sample_interval = population_value / sample_size if sample_size > 0 else 0

        return RiskBasedSample(
            population_value=population_value,
            sample_size=sample_size,
            confidence_level=confidence_level,
            materiality=materiality,
            sampling_method=f"MUS (interval: {sample_interval:,.0f})",
        )

    # ── ISA 570: Going Concern Assessment ──────────────────────────────

    def going_concern_assessment(
        self,
        snap: FinancialSnapshot,
        debt_maturities: float = 0,
        consecutive_loss_years: int = 0,
        adverse_opinion: bool = False,
    ) -> GoingConcernAssessment:
        assessment = GoingConcernAssessment(
            debt_maturities=debt_maturities,
            operating_cashflows=snap.operating_cash_flow,
            current_ratio=snap.current_assets / snap.current_liabilities if snap.current_liabilities else None,
            negative_equity=snap.total_equity < 0,
            consecutive_losses=consecutive_loss_years,
            adverse_audit_opinion=adverse_opinion,
        )

        if snap.net_profit < 0:
            assessment.indicators.append({
                "type": "financial",
                "indicator": "Net loss",
                "value": snap.net_profit,
                "severity": "high" if consecutive_loss_years >= 2 else "medium",
            })

        if assessment.negative_equity:
            assessment.indicators.append({
                "type": "financial",
                "indicator": "Negative equity",
                "value": snap.total_equity,
                "severity": "high",
            })

        if assessment.current_ratio and assessment.current_ratio < 0.8:
            assessment.indicators.append({
                "type": "liquidity",
                "indicator": "Low current ratio",
                "value": assessment.current_ratio,
                "severity": "high",
            })

        if debt_maturities > snap.operating_cash_flow * 1.5 and snap.operating_cash_flow > 0:
            assessment.indicators.append({
                "type": "debt",
                "indicator": "Debt service coverage",
                "value": snap.operating_cash_flow / debt_maturities if debt_maturities else 0,
                "severity": "high",
                "detail": "Operating cash flow insufficient to cover debt maturities (IAS 1, para 25)",
            })
            assessment.risk_level = "high"
            assessment.status = "going_concern_risk"

        if snap.operating_cash_flow < 0 and snap.net_profit < 0:
            assessment.risk_level = "high"
            assessment.status = "going_concern_risk"
            assessment.indicators.append({
                "type": "cash_flow",
                "indicator": "Negative operating cash flow AND net loss",
                "severity": "high",
            })

        if not assessment.indicators:
            assessment.indicators.append({
                "type": "positive",
                "indicator": "No material going concern indicators identified",
                "severity": "none",
            })

        return assessment


class AnalyticalReview:
    """ISA 520: Analytical review procedures for financial statements"""

    def __init__(self, industry_averages: dict[str, float] | None = None):
        self.industry_averages = industry_averages or {}

    def ratio_analysis_procedure(self, snap: FinancialSnapshot, ratio_name: str, value: float) -> AnalyticalProcedureResult:
        expected = self.industry_averages.get(ratio_name)
        if expected is None:
            return AnalyticalProcedureResult(
                procedure_name=ratio_name,
                status="no_benchmark",
                actual_value=value,
                conclusion="Industry benchmark not available",
            )

        deviation = abs(value - expected) / expected if expected else 0
        risk = "high" if deviation > 0.3 else ("medium" if deviation > 0.15 else "low")

        return AnalyticalProcedureResult(
            procedure_name=ratio_name,
            status="unusual" if risk != "low" else "expected",
            expected_value=expected,
            actual_value=value,
            deviation=deviation,
            conclusion=f"{ratio_name}: {value:.4f} vs industry {expected:.4f} ({deviation:.1%} deviation)",
            risk_level=risk,
        )

    def substantive_analytical_procedure(self, snap: FinancialSnapshot, prev: FinancialSnapshot | None) -> list[AnalyticalProcedureResult]:
        results = []
        if not prev:
            return results
        for line_item, field_name in [
            ("Revenue", "revenue"),
            ("COGS", "cost_of_goods_sold"),
            ("Operating Expenses", "operating_expenses"),
            ("Net Profit", "net_profit"),
        ]:
            current = getattr(snap, field_name, 0)
            prior = getattr(prev, field_name, 0)
            if prior == 0:
                continue
            change = (current - prior) / abs(prior)
            if abs(change) > 0.2:
                results.append(AnalyticalProcedureResult(
                    procedure_name=f"substantive_{field_name}",
                    status="unusual",
                    expected_value=prior,
                    actual_value=current,
                    deviation=change,
                    conclusion=f"{line_item} changed by {change:+.1%} vs prior period (threshold: 20%)",
                    risk_level="high" if abs(change) > 0.3 else "medium",
                ))
        return results
