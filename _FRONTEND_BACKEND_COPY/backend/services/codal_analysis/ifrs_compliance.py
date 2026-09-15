from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IFRSLeaseResult:
    classification: str
    right_of_use_asset: float = 0
    lease_liability: float = 0
    annual_depreciation: float = 0
    interest_rate: float = 0
    lease_term_years: int = 0
    total_payments: float = 0
    present_value: float = 0
    reasoning: list[str] = field(default_factory=list)


@dataclass
class IFRSRevenueResult:
    performance_obligations: int = 0
    transaction_price: float = 0
    allocated_prices: list[float] = field(default_factory=list)
    timing_of_recognition: str = "point_in_time"
    steps_completed: list[bool] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)


@dataclass
class IFRSFairValueResult:
    asset_type: str = ""
    fair_value: float = 0
    hierarchy_level: int = 3
    valuation_technique: str = ""
    inputs_used: dict[str, Any] = field(default_factory=dict)
    reliability_score: float = 0


class IFRSComplianceEngine:
    """
    IFRS 16: Lease Classification
    IFRS 15: Revenue Recognition
    IFRS 13: Fair Value Measurement
    """

    def __init__(self, discount_rate: float = 0.18):
        self.discount_rate = discount_rate

    # ── IFRS 16: Leases ────────────────────────────────────────────────

    def lease_classification(
        self,
        annual_payment: float,
        lease_term_years: int,
        economic_life_years: int,
        estimated_asset_value: float,
        ownership_transfer: bool = False,
        purchase_option: bool = False,
        bargain_purchase: bool = False,
    ) -> IFRSLeaseResult:
        reasoning = []

        pv = self._present_value_annuity(annual_payment, lease_term_years, self.discount_rate)
        pv_percentage = pv / estimated_asset_value if estimated_asset_value else 0
        term_percentage = lease_term_years / economic_life_years if economic_life_years else 0

        lease_criteria = 0
        if ownership_transfer:
            lease_criteria += 1
            reasoning.append("Ownership transfers at end of lease term (IFRS 16.B1)")
        if bargain_purchase or purchase_option:
            lease_criteria += 1
            reasoning.append("Bargain purchase option exists (IFRS 16.B2)")
        if term_percentage >= 0.75:
            lease_criteria += 1
            reasoning.append(
                f"Lease term ({lease_term_years}yrs) is major part of economic life ({economic_life_years}yrs) at {term_percentage:.0%} (IFRS 16.B3)"
            )
        if pv_percentage >= 0.90:
            lease_criteria += 1
            reasoning.append(
                f"PV of payments ({pv_percentage:.1%} of fair value) substantially all of asset value (IFRS 16.B4)"
            )

        is_finance = lease_criteria >= 2 or ownership_transfer or (pv_percentage >= 0.90)
        classification = "finance_lease" if is_finance else "operating_lease"

        right_of_use = pv if is_finance else 0
        annual_depreciation = right_of_use / max(lease_term_years, 1)
        liability = pv

        return IFRSLeaseResult(
            classification=classification,
            right_of_use_asset=round(right_of_use),
            lease_liability=round(liability),
            annual_depreciation=round(annual_depreciation),
            interest_rate=self.discount_rate,
            lease_term_years=lease_term_years,
            total_payments=round(annual_payment * lease_term_years),
            present_value=round(pv),
            reasoning=reasoning,
        )

    # ── IFRS 15: Revenue Recognition ────────────────────────────────────

    def revenue_recognition(
        self,
        contract_price: float,
        performance_obligations_count: int,
        standalone_prices: list[float] | None = None,
        is_over_time: bool = False,
        progress_percentage: float | None = None,
    ) -> IFRSRevenueResult:
        reasoning = []
        steps = [False] * 5

        steps[0] = True
        reasoning.append("Step 1: Identify contract with customer (IFRS 15.9)")

        steps[1] = True
        reasoning.append(f"Step 2: Identify {performance_obligations_count} performance obligation(s) (IFRS 15.22)")

        steps[2] = True
        reasoning.append(f"Step 3: Determine transaction price: {contract_price:,.0f} (IFRS 15.47)")

        allocated = standalone_prices or [contract_price / max(performance_obligations_count, 1)] * max(
            performance_obligations_count, 1
        )
        if sum(allocated) > 0:
            allocated = [p / sum(allocated) * contract_price for p in allocated]
        steps[3] = True
        reasoning.append("Step 4: Allocate price to obligations based on relative standalone prices (IFRS 15.76)")

        timing = "over_time" if is_over_time else "point_in_time"
        steps[4] = True
        if is_over_time:
            reasoning.append(f"Step 5: Recognize revenue over time ({progress_percentage:.0%} complete) (IFRS 15.35)")
        else:
            reasoning.append("Step 5: Recognize revenue at point in time when control transfers (IFRS 15.38)")

        return IFRSRevenueResult(
            performance_obligations=performance_obligations_count,
            transaction_price=contract_price,
            allocated_prices=[round(p, 2) for p in allocated],
            timing_of_recognition=timing,
            steps_completed=steps,
            reasoning=reasoning,
        )

    # ── IFRS 13: Fair Value Measurement ────────────────────────────────

    def fair_value_measurement(
        self,
        asset_type: str,
        market_data: dict[str, float] | None = None,
        discounted_cashflows: list[float] | None = None,
        replacement_cost: float | None = None,
    ) -> IFRSFairValueResult:
        result = IFRSFairValueResult(asset_type=asset_type)

        # Level 1: Quoted prices in active markets
        if market_data and "quoted_price" in market_data:
            result.fair_value = market_data["quoted_price"]
            result.hierarchy_level = 1
            result.valuation_technique = "Market approach - quoted price"
            result.reliability_score = 0.95
            result.inputs_used = {"quoted_price": market_data["quoted_price"], "source": "active_market"}
            return result

        # Level 2: Observable inputs
        if market_data and "comparable_price" in market_data:
            adjustment = market_data.get("adjustment_factor", 1.0)
            result.fair_value = market_data["comparable_price"] * adjustment
            result.hierarchy_level = 2
            result.valuation_technique = "Market approach - comparable"
            result.reliability_score = 0.85
            result.inputs_used = market_data
            return result

        # Level 3: Unobservable inputs - DCF
        if discounted_cashflows:
            discount_rate = market_data.get("discount_rate", self.discount_rate) if market_data else self.discount_rate
            pv = sum(cf / (1 + discount_rate) ** (i + 1) for i, cf in enumerate(discounted_cashflows))
            terminal_value = (
                discounted_cashflows[-1] * (1 + 0.02) / (discount_rate - 0.02) if len(discounted_cashflows) > 0 else 0
            )
            result.fair_value = round(pv + terminal_value)
            result.hierarchy_level = 3
            result.valuation_technique = "Income approach - DCF"
            result.reliability_score = 0.65
            result.inputs_used = {
                "discount_rate": discount_rate,
                "cashflow_count": len(discounted_cashflows),
                "terminal_growth": 0.02,
            }
            return result

        if replacement_cost:
            result.fair_value = replacement_cost
            result.hierarchy_level = 3
            result.valuation_technique = "Cost approach - replacement cost"
            result.reliability_score = 0.7
            result.inputs_used = {"replacement_cost": replacement_cost}
            return result

        return result

    def _present_value_annuity(self, payment: float, periods: int, rate: float) -> float:
        if rate == 0:
            return payment * periods
        return payment * (1 - (1 + rate) ** -periods) / rate


class IFRSDisclosureChecker:
    """Checks required IFRS disclosures in management reports"""

    REQUIRED_DISCLOSURES: dict[str, list[str]] = {
        "IFRS 7": ["Financial instruments", "risk management", "credit risk", "liquidity risk", "market risk"],
        "IFRS 15": ["revenue recognition", "performance obligations", "transaction price"],
        "IFRS 16": ["leases", "right-of-use", "lease liability", "depreciation"],
        "IAS 1": ["going concern", "accounting policies", "judgments", "estimates"],
        "IAS 36": ["impairment", "recoverable amount", "cash generating unit"],
    }

    def check_disclosures(self, text: str) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for standard, keywords in self.REQUIRED_DISCLOSURES.items():
            found = [kw for kw in keywords if kw in text]
            results[standard] = {
                "status": "compliant" if len(found) >= len(keywords) * 0.5 else "partial",
                "keywords_found": found,
                "keywords_missing": [kw for kw in keywords if kw not in text],
                "compliance_score": len(found) / len(keywords) if keywords else 1.0,
            }
        return results
