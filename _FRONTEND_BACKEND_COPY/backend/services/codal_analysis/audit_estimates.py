from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EstimateRange:
    low: float
    high: float
    point_estimate: float
    is_reasonable: bool = True
    management_bias_indicators: list[str] = field(default_factory=list)


@dataclass
class SensitivityResult:
    parameter: str
    base_value: float
    change_pct: float
    impact_on_profit: float
    impact_pct: float


@dataclass
class ProvisionTestResult:
    provision_type: str
    recorded_amount: float
    estimated_range_low: float
    estimated_range_high: float
    conclusion: str
    risk_level: str = "low"


@dataclass
class EstimatesAssessment:
    estimate_type: str = ""
    management_point_estimate: float = 0
    auditor_range: EstimateRange | None = None
    sensitivity_results: list[SensitivityResult] = field(default_factory=list)
    provisions_tested: list[ProvisionTestResult] = field(default_factory=list)
    bias_indicators: list[str] = field(default_factory=list)
    conclusion: str = ""


BIAS_INDICATORS = [
    "Consistent over/under estimation in prior periods",
    "Estimates at extreme end of possible range",
    "Changes in estimation methodology without justification",
    "Use of unreasonable assumptions (e.g., growth rates)",
    "Selecting discount rates inconsistent with market data",
    "Failure to adjust estimates for new information",
    "Pressure to meet targets or covenants",
]


class EstimatesAuditor:
    """ISA 540: Auditing Accounting Estimates and Related Disclosures"""

    def __init__(self):
        pass

    def test_range(self, point_estimate: float, low: float, high: float) -> EstimateRange:
        is_reasonable = low <= point_estimate <= high
        return EstimateRange(
            low=low,
            high=high,
            point_estimate=point_estimate,
            is_reasonable=is_reasonable,
        )

    def sensitivity_analysis(
        self,
        base_value: float,
        sensitivities: list[tuple[str, float, float]],
    ) -> list[SensitivityResult]:
        results = []
        for param_name, param_value, change_pct in sensitivities:
            impact = base_value * change_pct
            impact_pct = impact / abs(base_value) * 100 if base_value != 0 else 0
            results.append(
                SensitivityResult(
                    parameter=param_name,
                    base_value=param_value,
                    change_pct=change_pct,
                    impact_on_profit=round(impact),
                    impact_pct=round(impact_pct, 2),
                )
            )
        return results

    def assess_bias(self, indicators: list[str] | None = None) -> list[str]:
        indicators = indicators or []
        found = [b for b in BIAS_INDICATORS if b in indicators]
        return found

    def test_provision(
        self,
        provision_type: str,
        recorded: float,
        estimated_low: float,
        estimated_high: float,
    ) -> ProvisionTestResult:
        if estimated_low <= recorded <= estimated_high:
            conclusion = "Provision within acceptable range"
            risk = "low"
        elif recorded < estimated_low:
            conclusion = f"Provision possibly understated by at least {estimated_low - recorded:,.0f}"
            risk = "high"
        else:
            conclusion = f"Provision possibly overstated by at least {recorded - estimated_high:,.0f}"
            risk = "medium"

        return ProvisionTestResult(
            provision_type=provision_type,
            recorded_amount=recorded,
            estimated_range_low=estimated_low,
            estimated_range_high=estimated_high,
            conclusion=conclusion,
            risk_level=risk,
        )

    def assess_warranty_provision(
        self,
        revenue: float,
        historical_claim_rate: float,
        avg_cost_per_claim: float,
        recorded_provision: float,
    ) -> ProvisionTestResult:
        expected = revenue * historical_claim_rate * avg_cost_per_claim
        low = expected * 0.8
        high = expected * 1.2
        return self.test_provision("warranty", recorded_provision, low, high)

    def assess_doubtful_debts(
        self,
        receivables: float,
        historical_default_rate: float,
        aging_factors: dict[str, float] | None = None,
        recorded_allowance: float = 0,
    ) -> ProvisionTestResult:
        if aging_factors:
            expected = sum(amount * rate for amount, rate in aging_factors.items())
        else:
            expected = receivables * historical_default_rate
        low = expected * 0.7
        high = expected * 1.3
        return self.test_provision("doubtful_debts", recorded_allowance, low, high)


def format_estimates_for_response(assessment: EstimateRange | list[ProvisionTestResult] | Any) -> dict[str, Any]:
    if isinstance(assessment, EstimateRange):
        return {
            "type": "range_estimate",
            "low": assessment.low,
            "high": assessment.high,
            "point_estimate": assessment.point_estimate,
            "is_reasonable": assessment.is_reasonable,
            "management_bias_indicators": assessment.management_bias_indicators,
        }
    if isinstance(assessment, list):
        return {
            "type": "provision_tests",
            "provisions": [
                {
                    "provision_type": p.provision_type,
                    "recorded_amount": p.recorded_amount,
                    "estimated_range": {"low": p.estimated_range_low, "high": p.estimated_range_high},
                    "conclusion": p.conclusion,
                    "risk_level": p.risk_level,
                }
                for p in assessment
            ],
        }
    return {"type": "unknown", "data": str(assessment)}
