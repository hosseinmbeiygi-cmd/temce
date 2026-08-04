from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from services.codal_analysis.analysis_engine import FinancialSnapshot

logger = get_logger(__name__)


AUDIT_ASSERTIONS = [
    "occurrence", "completeness", "accuracy", "cutoff",
    "classification", "existence", "rights_obligations", "valuation",
]

FINANCIAL_STATEMENT_RISKS = [
    "management_override_of_controls",
    "fraud_in_revenue_recognition",
    "improper_asset_valuation",
    "related_party_transactions",
    "going_concern_risk",
    "it_system_general_controls",
    "complex_transactions",
    "regulatory_compliance",
]


@dataclass
class AssertionRisk:
    assertion: str
    inherent_risk: float = 0.5
    control_risk: float = 0.5
    detection_risk: float = 0.5
    combined_risk: float = 0.5
    risk_level: str = "medium"
    rationale: str = ""

    def calculate_combined(self) -> None:
        self.combined_risk = self.inherent_risk * self.control_risk * self.detection_risk
        self.combined_risk = max(0.05, min(1.0, self.combined_risk))
        if self.combined_risk >= 0.5:
            self.risk_level = "high"
        elif self.combined_risk >= 0.25:
            self.risk_level = "medium"
        else:
            self.risk_level = "low"


@dataclass
class AccountRiskProfile:
    account_name: str
    account_type: str
    assertion_risks: dict[str, AssertionRisk] = field(default_factory=dict)
    overall_risk_score: float = 0.5
    overall_risk_level: str = "medium"
    key_assertions: list[str] = field(default_factory=list)

    def calculate_overall(self) -> None:
        if not self.assertion_risks:
            return
        self.overall_risk_score = max(
            r.combined_risk for r in self.assertion_risks.values()
        )
        if self.overall_risk_score >= 0.5:
            self.overall_risk_level = "high"
        elif self.overall_risk_score >= 0.25:
            self.overall_risk_level = "medium"
        else:
            self.overall_risk_level = "low"

        self.key_assertions = [
            a for a, r in self.assertion_risks.items()
            if r.risk_level == "high"
        ]


@dataclass
class AuditRiskAssessment:
    assessment_date: str = ""
    entity_level_risks: dict[str, float] = field(default_factory=dict)
    entity_level_risk_level: str = "medium"
    account_risk_profiles: dict[str, AccountRiskProfile] = field(default_factory=dict)
    overall_audit_risk: float = 0.5
    is_complex_engagement: bool = False
    risk_summary: dict[str, Any] = field(default_factory=dict)


class AuditRiskAssessor:
    """ISA 315: Identifying and Assessing the Risks of Material Misstatement"""

    def __init__(self, audit_risk_target: float = 0.05):
        self.audit_risk_target = audit_risk_target

    def assess_entity_level_risks(self, snap: FinancialSnapshot) -> dict[str, float]:
        risks: dict[str, float] = {}
        risks["management_override_of_controls"] = 0.4

        revenue = snap.revenue or 0
        net_profit = snap.net_profit or 0
        if revenue > 0 and net_profit / revenue < 0.02:
            risks["fraud_in_revenue_recognition"] = 0.6
        else:
            risks["fraud_in_revenue_recognition"] = 0.3

        asset_volatility = abs(snap.total_assets - (snap.prev.total_assets if snap.prev else 0))
        volatility_ratio = asset_volatility / snap.prev.total_assets if snap.prev and snap.prev.total_assets else 0
        if volatility_ratio > 0.3:
            risks["improper_asset_valuation"] = 0.6
        else:
            risks["improper_asset_valuation"] = 0.3

        related_party_indicators = 0
        raw_data = getattr(snap, "raw_data", {}) or {}
        other_receivables = raw_data.get("OTHER_RECEIVABLES") or raw_data.get("other_receivables") or 0
        other_payables = raw_data.get("OTHER_PAYABLES") or raw_data.get("other_payables") or 0
        if other_receivables and other_receivables > revenue * 0.1:
            related_party_indicators += 0.2
        if other_payables and other_payables > revenue * 0.1:
            related_party_indicators += 0.2
        risks["related_party_transactions"] = min(0.8, 0.3 + related_party_indicators)

        if snap.net_profit and snap.net_profit < 0:
            risks["going_concern_risk"] = 0.6
        else:
            risks["going_concern_risk"] = 0.2

        risks["it_system_general_controls"] = 0.4
        risks["complex_transactions"] = 0.5 if volatility_ratio > 0.2 else 0.3
        risks["regulatory_compliance"] = 0.4

        self.entity_level_risks = risks
        return risks

    def assess_account_risks(
        self,
        snap: FinancialSnapshot,
        entity_risks: dict[str, float] | None = None,
    ) -> dict[str, AccountRiskProfile]:
        if entity_risks is None:
            entity_risks = self.assess_entity_level_risks(snap)

        entity_risk_factor = max(entity_risks.values()) if entity_risks else 0.5

        profiles: dict[str, AccountRiskProfile] = {}

        revenue = snap.revenue or 0
        if revenue > 0:
            ar = self._assess_revenue_assertions(snap, entity_risk_factor)
            profiles["revenue"] = ar

        receivables = snap.accounts_receivable or 0
        if receivables > 0:
            ar = self._assess_receivables_assertions(snap, entity_risk_factor)
            profiles["receivables"] = ar

        inventory = snap.inventory or 0
        if inventory > 0:
            ar = self._assess_inventory_assertions(snap, entity_risk_factor)
            profiles["inventory"] = ar

        ppe = snap.net_fixed_assets or snap.total_assets * 0.3 if snap.total_assets else 0
        if ppe > 0:
            ar = self._assess_ppe_assertions(snap, entity_risk_factor)
            profiles["property_plant_equipment"] = ar

        payables = snap.accounts_payable or snap.total_liabilities * 0.3 if snap.total_liabilities else 0
        if payables > 0:
            ar = self._assess_payables_assertions(snap, entity_risk_factor)
            profiles["payables"] = ar

        cash = snap.cash or 0
        if cash > 0:
            ar = AccountRiskProfile(account_name="cash_and_equivalents", account_type="current_asset")
            for assertion in AUDIT_ASSERTIONS:
                assertion_risk = AssertionRisk(
                    assertion=assertion,
                    inherent_risk=0.3,
                    control_risk=0.3,
                    detection_risk=0.3,
                    rationale="Cash is generally low risk with high auditability",
                )
                assertion_risk.calculate_combined()
                ar.assertion_risks[assertion] = assertion_risk
            ar.calculate_overall()
            profiles["cash_and_equivalents"] = ar

        equity = snap.total_equity or 0
        if equity > 0:
            ar = AccountRiskProfile(account_name="equity", account_type="equity")
            for assertion in AUDIT_ASSERTIONS:
                ir = 0.3 if assertion in ("completeness", "valuation") else 0.2
                assertion_risk = AssertionRisk(
                    assertion=assertion,
                    inherent_risk=ir,
                    control_risk=0.3,
                    detection_risk=0.3,
                    rationale="Equity transactions are typically infrequent and high-level",
                )
                assertion_risk.calculate_combined()
                ar.assertion_risks[assertion] = assertion_risk
            ar.calculate_overall()
            profiles["equity"] = ar

        self.account_risk_profiles = profiles
        return profiles

    def _assess_revenue_assertions(
        self, snap: FinancialSnapshot, entity_factor: float
    ) -> AccountRiskProfile:
        profile = AccountRiskProfile(account_name="revenue", account_type="revenue")
        revenue = snap.revenue or 0
        net_profit = snap.net_profit or 0
        profit_margin = net_profit / revenue if revenue else 0

        margin_pressure = 1.0 if profit_margin < 0.02 else 0.5 if profit_margin < 0.08 else 0.2

        for assertion in AUDIT_ASSERTIONS:
            if assertion == "occurrence":
                ir = 0.4 + margin_pressure * 0.3
                rationale = "Fictitious revenue risk increases with profit pressure"
            elif assertion == "completeness":
                ir = 0.3
                rationale = "Understatement risk generally lower"
            elif assertion == "accuracy":
                ir = 0.3
                rationale = "Standard accuracy risk for revenue"
            elif assertion == "cutoff":
                ir = 0.5 + margin_pressure * 0.3
                rationale = "Cutoff misstatements common near period end"
            elif assertion == "classification":
                ir = 0.3
                rationale = "Classification risk for revenue streams"
            elif assertion in ("existence", "rights_obligations"):
                ir = 0.4 + margin_pressure * 0.2
                rationale = "Existence risk for recorded revenue"
            elif assertion == "valuation":
                ir = 0.3
                rationale = "Revenue usually measured at transaction price"
            else:
                ir = 0.3
                rationale = ""

            ar = AssertionRisk(
                assertion=assertion,
                inherent_risk=min(1.0, ir),
                control_risk=0.4,
                detection_risk=min(1.0, self.audit_risk_target / max(0.05, ir * 0.4)),
                rationale=rationale,
            )
            ar.calculate_combined()
            profile.assertion_risks[assertion] = ar

        profile.calculate_overall()
        return profile

    def _assess_receivables_assertions(
        self, snap: FinancialSnapshot, entity_factor: float
    ) -> AccountRiskProfile:
        profile = AccountRiskProfile(account_name="receivables", account_type="current_asset")
        receivables = snap.accounts_receivable or 0
        revenue = snap.revenue or 1
        days_outstanding = (receivables / revenue) * 365 if revenue else 0
        aging_risk = min(0.8, days_outstanding / 365) if days_outstanding > 90 else 0.2

        for assertion in AUDIT_ASSERTIONS:
            if assertion == "valuation":
                ir = min(0.9, 0.4 + aging_risk * 0.5)
                rationale = f"High AR aging risk ({days_outstanding:.0f} days)"
            elif assertion == "existence":
                ir = 0.4 + aging_risk * 0.2
                rationale = "Existence of aged receivables is questionable"
            elif assertion == "rights_obligations":
                ir = 0.3
                rationale = "Standard rights assessment"
            else:
                ir = 0.3
                rationale = "Standard risk for this assertion"

            ar = AssertionRisk(
                assertion=assertion,
                inherent_risk=min(1.0, ir),
                control_risk=0.4,
                detection_risk=min(1.0, self.audit_risk_target / max(0.05, ir * 0.4)),
                rationale=rationale,
            )
            ar.calculate_combined()
            profile.assertion_risks[assertion] = ar

        profile.calculate_overall()
        return profile

    def _assess_inventory_assertions(
        self, snap: FinancialSnapshot, entity_factor: float
    ) -> AccountRiskProfile:
        profile = AccountRiskProfile(account_name="inventory", account_type="current_asset")
        inventory = snap.inventory or 0
        cogs = snap.cost_of_goods_sold or 1
        turnover_days = (inventory / cogs) * 365 if cogs else 0
        obsolescence_risk = min(0.7, turnover_days / 365) if turnover_days > 180 else 0.2

        for assertion in AUDIT_ASSERTIONS:
            if assertion == "valuation":
                ir = min(0.85, 0.4 + obsolescence_risk * 0.5)
                rationale = f"Obsolescence risk (turnover: {turnover_days:.0f} days)"
            elif assertion == "existence":
                ir = 0.4
                rationale = "Physical existence requires observation"
            elif assertion == "completeness":
                ir = 0.3
                rationale = "Unrecorded inventory liability risk"
            elif assertion == "rights_obligations":
                ir = 0.4
                rationale = "Consignment/third-party inventory risk"
            else:
                ir = 0.3
                rationale = "Standard risk for this assertion"

            ar = AssertionRisk(
                assertion=assertion,
                inherent_risk=min(1.0, ir),
                control_risk=0.5,
                detection_risk=min(1.0, self.audit_risk_target / max(0.05, ir * 0.4)),
                rationale=rationale,
            )
            ar.calculate_combined()
            profile.assertion_risks[assertion] = ar

        profile.calculate_overall()
        return profile

    def _assess_ppe_assertions(
        self, snap: FinancialSnapshot, entity_factor: float
    ) -> AccountRiskProfile:
        profile = AccountRiskProfile(account_name="property_plant_equipment", account_type="non_current_asset")
        snap.net_fixed_assets or snap.total_assets * 0.3 if snap.total_assets else 0

        for assertion in AUDIT_ASSERTIONS:
            if assertion == "valuation":
                ir = 0.5
                rationale = "Depreciation method and useful life estimates"
            elif assertion == "existence":
                ir = 0.3
                rationale = "Physical verification possible"
            elif assertion == "rights_obligations":
                ir = 0.5
                rationale = "Legal ownership verification required"
            elif assertion == "completeness":
                ir = 0.3
                rationale = "Unrecorded asset additions"
            else:
                ir = 0.2
                rationale = "Standard risk for this assertion"

            ar = AssertionRisk(
                assertion=assertion,
                inherent_risk=min(1.0, ir),
                control_risk=0.4,
                detection_risk=min(1.0, self.audit_risk_target / max(0.05, ir * 0.4)),
                rationale=rationale,
            )
            ar.calculate_combined()
            profile.assertion_risks[assertion] = ar

        profile.calculate_overall()
        return profile

    def _assess_payables_assertions(
        self, snap: FinancialSnapshot, entity_factor: float
    ) -> AccountRiskProfile:
        profile = AccountRiskProfile(account_name="payables", account_type="current_liability")
        snap.accounts_payable or snap.total_liabilities * 0.3 if snap.total_liabilities else 0

        for assertion in AUDIT_ASSERTIONS:
            if assertion == "completeness":
                ir = 0.6
                rationale = "Understatement of liabilities is a common risk"
            elif assertion == "valuation":
                ir = 0.3
                rationale = "Payables usually at invoice amount"
            elif assertion == "cutoff":
                ir = 0.5
                rationale = "Cutoff around period end for goods received"
            else:
                ir = 0.3
                rationale = "Standard risk for this assertion"

            ar = AssertionRisk(
                assertion=assertion,
                inherent_risk=min(1.0, ir),
                control_risk=0.4,
                detection_risk=min(1.0, self.audit_risk_target / max(0.05, ir * 0.4)),
                rationale=rationale,
            )
            ar.calculate_combined()
            profile.assertion_risks[assertion] = ar

        profile.calculate_overall()
        return profile

    def assess_all(self, snap: FinancialSnapshot) -> AuditRiskAssessment:
        entity_risks = self.assess_entity_level_risks(snap)
        account_profiles = self.assess_account_risks(snap, entity_risks)

        entity_risk_level_val = max(entity_risks.values()) if entity_risks else 0.5
        if entity_risk_level_val >= 0.5:
            entity_level = "high"
        elif entity_risk_level_val >= 0.25:
            entity_level = "medium"
        else:
            entity_level = "low"

        account_risk_scores = [
            p.overall_risk_score for p in account_profiles.values()
        ] if account_profiles else [0.5]
        max_account_risk = max(account_risk_scores)
        overall_audit_risk = max(entity_risk_level_val, max_account_risk)

        high_risk_accounts = [
            name for name, p in account_profiles.items()
            if p.overall_risk_level == "high"
        ]
        key_assertions_by_account = {
            name: p.key_assertions
            for name, p in account_profiles.items()
        }

        return AuditRiskAssessment(
            entity_level_risks=entity_risks,
            entity_level_risk_level=entity_level,
            account_risk_profiles=account_profiles,
            overall_audit_risk=round(overall_audit_risk, 4),
            is_complex_engagement=overall_audit_risk > 0.6,
            risk_summary={
                "entity_risk_level": entity_level,
                "high_risk_accounts": high_risk_accounts,
                "key_assertions_by_account": key_assertions_by_account,
                "overall_audit_risk": round(overall_audit_risk, 4),
                "high_risk_count": len(high_risk_accounts),
                "total_accounts_risked": len(account_profiles),
            },
        )


def format_risks_for_response(assessment: AuditRiskAssessment) -> dict[str, Any]:
    return {
        "entity_level_risk_level": assessment.entity_level_risk_level,
        "entity_level_risks": {
            k: {
                "score": v,
                "level": "high" if v >= 0.5 else "medium" if v >= 0.25 else "low",
            }
            for k, v in assessment.entity_level_risks.items()
        },
        "account_risk_profiles": {
            name: {
                "account_type": p.account_type,
                "overall_risk_score": p.overall_risk_score,
                "overall_risk_level": p.overall_risk_level,
                "key_assertions": p.key_assertions,
                "assertion_risks": {
                    a: {
                        "inherent_risk": r.inherent_risk,
                        "control_risk": r.control_risk,
                        "detection_risk": r.detection_risk,
                        "combined_risk": r.combined_risk,
                        "risk_level": r.risk_level,
                        "rationale": r.rationale,
                    }
                    for a, r in p.assertion_risks.items()
                },
            }
            for name, p in assessment.account_risk_profiles.items()
        },
        "overall_audit_risk": assessment.overall_audit_risk,
        "is_complex_engagement": assessment.is_complex_engagement,
        "risk_summary": assessment.risk_summary,
    }
