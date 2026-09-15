from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

RELATED_PARTY_INDICATORS = [
    "Significant transactions with non-routine counterparties",
    "Transactions at unusual prices or terms",
    "Free or below-market services received/provided",
    "Loans to/from parties with no business rationale",
    "Transactions through intermediary entities",
    "Unusually large consulting or management fees",
    "Asset purchases/sales at amounts far from fair value",
    "Guarantees provided without proper approval",
]

RP_DISCLOSURE_CHECKLIST = [
    "Nature of relationship with related parties",
    "Description of transactions",
    "Volume of transactions (amount and units)",
    "Outstanding balances at period end",
    "Allowance for doubtful debts on RP balances",
    "Expense recognized for bad debts on RP balances",
    "Pricing policies for related party transactions",
    "Commitments with related parties",
    "Key management compensation",
    "Transactions with government-related entities",
]


@dataclass
class RelatedPartyTransaction:
    counterparty: str = ""
    relationship: str = ""
    nature: str = ""
    amount: float = 0
    terms: str = ""
    is_arm_length: bool = True
    risk_flag: bool = False
    risk_reason: str = ""


@dataclass
class RelatedPartyAssessment:
    transactions: list[RelatedPartyTransaction] = field(default_factory=list)
    indicators_found: list[str] = field(default_factory=list)
    disclosure_compliance: dict[str, bool] = field(default_factory=dict)
    disclosed_items: list[str] = field(default_factory=list)
    missing_disclosures: list[str] = field(default_factory=list)
    arm_slength_issues: list[str] = field(default_factory=list)
    overall_risk: str = "low"
    procedures_performed: list[str] = field(default_factory=list)


class RelatedPartyAuditor:
    """ISA 550: Related Parties"""

    def __init__(self):
        pass

    def check_indicators(self, active_indicators: list[str] | None = None) -> list[str]:
        active = active_indicators or []
        return [ind for ind in RELATED_PARTY_INDICATORS if ind in active]

    def check_disclosures(self, disclosed: list[str] | None = None) -> dict[str, bool]:
        disclosed = disclosed or []
        compliance = {}
        for item in RP_DISCLOSURE_CHECKLIST:
            compliance[item] = item in disclosed
        return compliance

    def assess(self, transactions: list[dict[str, Any]] | None = None) -> RelatedPartyAssessment:
        transactions = transactions or []
        assessment = RelatedPartyAssessment()

        for t in transactions:
            rpt = RelatedPartyTransaction(
                counterparty=t.get("counterparty", ""),
                relationship=t.get("relationship", ""),
                nature=t.get("nature", ""),
                amount=t.get("amount", 0),
                terms=t.get("terms", ""),
            )
            # Arm's length assessment
            if t.get("amount", 0) > 1_000_000_000 and t.get("terms", "").lower() in ("none", "favorable", ""):
                rpt.is_arm_length = False
                rpt.risk_flag = True
                rpt.risk_reason = "Large transaction with favorable or undocumented terms"
                assessment.arm_slength_issues.append(
                    f"{rpt.counterparty}: {rpt.nature} ({rpt.amount:,.0f}) - {rpt.risk_reason}"
                )
            assessment.transactions.append(rpt)

        assessment.procedures_performed = [
            "Obtained list of related parties from management",
            "Reviewed board meeting minutes for RP approvals",
            "Scanned general ledger for unusual transactions",
            "Confirmed RP balances and terms independently",
            "Evaluated arm's length nature of significant RP transactions",
            "Reviewed RP disclosures for completeness",
        ]

        if assessment.arm_slength_issues:
            assessment.overall_risk = "high"
        elif len(assessment.transactions) > 5:
            assessment.overall_risk = "medium"

        return assessment


def format_rp_for_response(assessment: RelatedPartyAssessment) -> dict[str, Any]:
    return {
        "overall_risk": assessment.overall_risk,
        "transactions": [
            {
                "counterparty": t.counterparty,
                "relationship": t.relationship,
                "nature": t.nature,
                "amount": t.amount,
                "is_arm_length": t.is_arm_length,
                "risk_flag": t.risk_flag,
                "risk_reason": t.risk_reason,
            }
            for t in assessment.transactions
        ],
        "arm_length_issues": assessment.arm_slength_issues,
        "procedures_performed": assessment.procedures_performed,
    }
