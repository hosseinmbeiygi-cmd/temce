from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from services.codal_analysis.analysis_engine import FinancialSnapshot

logger = get_logger(__name__)

FRAUD_TRIANGLE = ["incentive_pressure", "opportunity", "rationalization"]

REVENUE_FRAUD_INDICATORS = [
    {"code": "RF1", "description": "Revenue growth significantly exceeds industry average", "weight": 0.7},
    {"code": "RF2", "description": "Cash flow from operations consistently lower than net income", "weight": 0.8},
    {"code": "RF3", "description": "Days sales outstanding increasing while revenue is growing", "weight": 0.6},
    {"code": "RF4", "description": "Significant related party revenue at non-arm's length", "weight": 0.9},
    {"code": "RF5", "description": "Unusual journal entries near period end affecting revenue", "weight": 0.8},
    {"code": "RF6", "description": "Gross margin anomalies unsupported by cost or price changes", "weight": 0.6},
    {"code": "RF7", "description": "Revenue recognized on consignment or bill-and-hold arrangements", "weight": 0.7},
]

ASSET_FRAUD_INDICATORS = [
    {"code": "AF1", "description": "Fictitious or duplicated vendor payments", "weight": 0.8},
    {"code": "AF2", "description": "Unexplained inventory shortages", "weight": 0.6},
    {"code": "AF3", "description": "Cash transfers to unknown accounts", "weight": 0.9},
    {"code": "AF4", "description": "Payroll to ghost employees", "weight": 0.8},
    {"code": "AF5", "description": "Unauthorized personal use of company assets", "weight": 0.5},
]

CORRUPTION_INDICATORS = [
    {"code": "CR1", "description": "Unusual consulting or agent fees", "weight": 0.8},
    {"code": "CR2", "description": "Kickbacks in procurement", "weight": 0.8},
    {"code": "CR3", "description": "Conflicts of interest in related party transactions", "weight": 0.7},
    {"code": "CR4", "description": "Politically exposed persons (PEP) as counterparties", "weight": 0.6},
]


@dataclass
class FraudIndicatorResult:
    code: str
    description: str
    weight: float
    is_present: bool = False
    severity: str = "low"
    evidence_note: str = ""


@dataclass
class FraudRiskFactor:
    factor_type: str
    description: str
    severity: str
    details: str = ""


@dataclass
class FraudAssessment:
    revenue_fraud_risk: float = 0
    asset_fraud_risk: float = 0
    corruption_risk: float = 0
    overall_fraud_risk: float = 0
    fraud_triangle_factors: list[FraudRiskFactor] = field(default_factory=list)
    revenue_indicators: list[FraudIndicatorResult] = field(default_factory=list)
    asset_indicators: list[FraudIndicatorResult] = field(default_factory=list)
    corruption_indicators: list[FraudIndicatorResult] = field(default_factory=list)
    journal_entry_testing_approach: list[str] = field(default_factory=list)
    risk_level: str = "low"
    conclusions: list[str] = field(default_factory=list)


class FraudAssessor:
    """ISA 240: The Auditor's Responsibilities Relating to Fraud"""

    def __init__(self):
        pass

    def assess_fraud_triangle(self, snap: FinancialSnapshot) -> list[FraudRiskFactor]:
        factors = []

        # Incentive/Pressure
        if snap.net_profit and snap.net_profit < 0:
            factors.append(FraudRiskFactor(
                "incentive_pressure",
                "Net loss creates pressure to manipulate financial results",
                "high",
            ))
        if snap.total_liabilities and snap.total_equity:
            debt_eq = snap.total_liabilities / snap.total_equity if snap.total_equity else 0
            if debt_eq > 2:
                factors.append(FraudRiskFactor(
                    "incentive_pressure",
                    f"High leverage (D/E: {debt_eq:.1f}) increases pressure to meet debt covenants",
                    "high",
                ))

        # Opportunity
        raw_data = getattr(snap, "raw_data", {}) or {}
        rpt = raw_data.get("RELATED_PARTY_TRANSACTIONS") or raw_data.get("related_party_transactions") or 0
        if rpt > snap.revenue * 0.1:
            factors.append(FraudRiskFactor(
                "opportunity",
                "Significant related party transactions provide opportunity for fraud",
                "high",
            ))

        return factors

    def assess_revenue_fraud(self, snap: FinancialSnapshot) -> list[FraudIndicatorResult]:
        results = []
        revenue = snap.revenue or 0
        net_profit = snap.net_profit or 0
        operating_cf = snap.operating_cash_flow or 0
        accounts_rec = snap.accounts_receivable or 0

        for ind in REVENUE_FRAUD_INDICATORS:
            is_present = False
            severity = "low"
            note = ""

            if ind["code"] == "RF2" and revenue > 0 and operating_cf < net_profit * 0.5:
                is_present = True
                severity = "high"
                note = f"Operating CF ({operating_cf:,.0f}) < 50% of Net Income ({net_profit:,.0f})"
            elif ind["code"] == "RF3" and revenue > 0 and accounts_rec > revenue * 0.3:
                is_present = True
                severity = "medium"
                note = f"AR ({accounts_rec:,.0f}) is {accounts_rec / revenue * 100:.0f}% of revenue"
            elif ind["code"] == "RF6" and snap.prev and snap.prev.revenue:
                curr_gm = (snap.gross_profit / revenue) if revenue else 0
                prev_gm = (snap.prev.gross_profit / snap.prev.revenue) if snap.prev.revenue else 0
                if abs(curr_gm - prev_gm) > 0.1:
                    is_present = True
                    severity = "medium"
                    note = f"Gross margin change: {prev_gm:.1%} -> {curr_gm:.1%}"

            results.append(FraudIndicatorResult(
                code=ind["code"],
                description=ind["description"],
                weight=ind["weight"],
                is_present=is_present,
                severity=severity,
                evidence_note=note,
            ))

        return results

    def assess_asset_fraud(self, snap: FinancialSnapshot) -> list[FraudIndicatorResult]:
        results = []
        revenue = snap.revenue or 0
        inventory = snap.inventory or 0
        raw = snap.raw_data or {}
        prev_inventory = snap.prev.inventory if snap.prev else None
        prev_cogs = snap.prev.cost_of_goods_sold if snap.prev else None
        # payroll / other_expenses may live in raw_data if not mapped to attrs
        payroll = float(raw.get("PAYROLL_EXPENSE", 0) or 0)
        prev_payroll = float((snap.prev.raw_data or {}).get("PAYROLL_EXPENSE", 0) or 0) if snap.prev else None
        other_expenses = float(raw.get("OTHER_EXPENSES", 0) or 0)

        for ind in ASSET_FRAUD_INDICATORS:
            is_present = False
            severity = "low"
            note = ""

            if ind["code"] == "AF1" and revenue > 0 and other_expenses > revenue * 0.3:
                # High "other expenses" relative to revenue may indicate
                # fictitious vendor payments.
                is_present = True
                severity = "medium"
                note = f"Other expenses ({other_expenses:,.0f}) = {other_expenses / revenue * 100:.0f}% of revenue"

            elif (
                ind["code"] == "AF2"
                and prev_inventory is not None
                and prev_cogs is not None
                and prev_cogs > 0
            ):
                # Inventory should roughly track COGS; a large unexplained
                # drop signals potential shortages.
                inv_change = inventory - prev_inventory
                if inv_change < -prev_cogs * 0.2:
                    is_present = True
                    severity = "medium"
                    note = f"Inventory dropped {abs(inv_change):,.0f} ({abs(inv_change) / prev_cogs * 100:.0f}% of COGS)"

            elif ind["code"] == "AF4" and prev_payroll is not None and prev_payroll > 0:
                # Payroll growing much faster than revenue → ghost employees
                if revenue > 0 and snap.prev and snap.prev.revenue:
                    payroll_growth = (payroll - prev_payroll) / prev_payroll
                    revenue_growth = (revenue - snap.prev.revenue) / snap.prev.revenue
                    if payroll_growth > revenue_growth + 0.2 and payroll_growth > 0.15:
                        is_present = True
                        severity = "high"
                        note = f"Payroll growth {payroll_growth:.0%} far exceeds revenue growth {revenue_growth:.0%}"

            results.append(FraudIndicatorResult(
                code=ind["code"],
                description=ind["description"],
                weight=ind["weight"],
                is_present=is_present,
                severity=severity,
                evidence_note=note,
            ))

        return results

    def assess_corruption(self, snap: FinancialSnapshot) -> list[FraudIndicatorResult]:
        results = []
        revenue = snap.revenue or 0
        cogs = snap.cost_of_goods_sold or 0
        raw = snap.raw_data or {}
        other_expenses = float(raw.get("OTHER_EXPENSES", 0) or 0)
        prev_cogs = snap.prev.cost_of_goods_sold if snap.prev else None
        rpt = float(raw.get("RELATED_PARTY_TRANSACTIONS", 0) or raw.get("related_party_transactions", 0) or 0)

        for ind in CORRUPTION_INDICATORS:
            is_present = False
            severity = "low"
            note = ""

            if ind["code"] == "CR1" and revenue > 0 and other_expenses > revenue * 0.2:
                is_present = True
                severity = "medium"
                note = f"High other expenses ({other_expenses / revenue * 100:.0f}% of revenue) — possible consulting fees"

            elif ind["code"] == "CR2" and revenue > 0 and prev_cogs and prev_cogs > 0:
                # COGS growing faster than revenue without explanation
                cogs_growth = (cogs - prev_cogs) / prev_cogs
                rev_growth = (snap.revenue - snap.prev.revenue) / snap.prev.revenue if snap.prev and snap.prev.revenue else 0
                if cogs_growth > rev_growth + 0.15:
                    is_present = True
                    severity = "high"
                    note = f"COGS growth {cogs_growth:.0%} exceeds revenue growth {rev_growth:.0%}"

            elif ind["code"] == "CR3" and revenue > 0 and rpt > revenue * 0.1:
                is_present = True
                severity = "high"
                note = f"Related party transactions ({rpt:,.0f}) = {rpt / revenue * 100:.0f}% of revenue"

            results.append(FraudIndicatorResult(
                code=ind["code"],
                description=ind["description"],
                weight=ind["weight"],
                is_present=is_present,
                severity=severity,
                evidence_note=note,
            ))

        return results

    def journal_entry_testing(self) -> list[str]:
        return [
            "Select journal entries posted near period end (last 2 weeks)",
            "Focus on entries with round amounts, unusual account combinations",
            "Review entries made by non-standard users or outside normal hours",
            "Examine reversing journal entries shortly after period end",
            "Test entries to/from related party accounts",
            "Review consolidation adjusting entries",
        ]

    def assess_all(self, snap: FinancialSnapshot) -> FraudAssessment:
        triangle = self.assess_fraud_triangle(snap)
        revenue_indicators = self.assess_revenue_fraud(snap)
        asset_indicators = self.assess_asset_fraud(snap)
        corruption_indicators = self.assess_corruption(snap)
        je_approach = self.journal_entry_testing()

        revenue_score = sum(
            ind.weight for ind in revenue_indicators if ind.is_present
        ) / sum(ind["weight"] for ind in REVENUE_FRAUD_INDICATORS) * 100 if REVENUE_FRAUD_INDICATORS else 0

        asset_score = sum(
            ind.weight for ind in asset_indicators if ind.is_present
        ) / sum(ind["weight"] for ind in ASSET_FRAUD_INDICATORS) * 100 if ASSET_FRAUD_INDICATORS else 0

        corruption_score = sum(
            ind.weight for ind in corruption_indicators if ind.is_present
        ) / sum(ind["weight"] for ind in CORRUPTION_INDICATORS) * 100 if CORRUPTION_INDICATORS else 0

        overall = (revenue_score * 0.5 + asset_score * 0.3 + corruption_score * 0.2)

        if overall > 50:
            risk_level = "high"
        elif overall > 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        conclusions = []
        if risk_level == "high":
            conclusions.append("Significant fraud risk identified - extensive procedures required")
        elif risk_level == "medium":
            conclusions.append("Moderate fraud risk - additional procedures recommended")

        high_sev_triangle = [f for f in triangle if f.severity == "high"]
        if high_sev_triangle:
            conclusions.append(f"Fraud triangle factors: {len(high_sev_triangle)} high severity items")

        return FraudAssessment(
            revenue_fraud_risk=round(revenue_score, 1),
            asset_fraud_risk=round(asset_score, 1),
            corruption_risk=round(corruption_score, 1),
            overall_fraud_risk=round(overall, 1),
            fraud_triangle_factors=triangle,
            revenue_indicators=revenue_indicators,
            asset_indicators=asset_indicators,
            corruption_indicators=corruption_indicators,
            journal_entry_testing_approach=je_approach,
            risk_level=risk_level,
            conclusions=conclusions,
        )


def format_fraud_for_response(fa: FraudAssessment) -> dict[str, Any]:
    return {
        "overall_fraud_risk": fa.overall_fraud_risk,
        "risk_level": fa.risk_level,
        "revenue_fraud_risk": fa.revenue_fraud_risk,
        "asset_fraud_risk": fa.asset_fraud_risk,
        "corruption_risk": fa.corruption_risk,
        "fraud_triangle_factors": [
            {"type": f.factor_type, "description": f.description, "severity": f.severity}
            for f in fa.fraud_triangle_factors
        ],
        "revenue_indicators": [
            {"code": i.code, "description": i.description, "is_present": i.is_present, "severity": i.severity, "evidence": i.evidence_note}
            for i in fa.revenue_indicators
        ],
        "asset_indicators": [
            {"code": i.code, "description": i.description, "is_present": i.is_present}
            for i in fa.asset_indicators
        ],
        "corruption_indicators": [
            {"code": i.code, "description": i.description, "is_present": i.is_present}
            for i in fa.corruption_indicators
        ],
        "journal_entry_testing_approach": fa.journal_entry_testing_approach,
        "conclusions": fa.conclusions,
    }
