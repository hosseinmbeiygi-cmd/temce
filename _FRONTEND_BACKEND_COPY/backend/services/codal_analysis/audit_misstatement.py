from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Misstatement:
    reference: str
    description: str
    amount: float
    category: str  # factual, judgmental, projected
    account: str
    impact_on_profit: float = 0
    impact_on_assets: float = 0
    impact_on_liabilities: float = 0
    impact_on_equity: float = 0
    is_corrected: bool = False
    root_cause: str = ""


@dataclass
class MisstatementSummary:
    total_factual: float = 0
    total_judgmental: float = 0
    total_projected: float = 0
    total_uncorrected: float = 0
    factual_count: int = 0
    judgmental_count: int = 0
    projected_count: int = 0
    corrected_amount: float = 0
    net_impact_on_profit: float = 0


@dataclass
class MisstatementEvaluation:
    misstatements: list[Misstatement] = field(default_factory=list)
    summary: MisstatementSummary = field(default_factory=MisstatementSummary)
    planning_materiality: float = 0
    performance_materiality: float = 0
    clearly_trivial_threshold: float = 0
    is_material: bool = False
    is_pervasive: bool = False
    proposed_opinion: str = "unmodified"
    rationale: str = ""


class MisstatementEvaluator:
    """ISA 450: Evaluation of Misstatements Identified During the Audit"""

    def __init__(self):
        self.misstatements: list[Misstatement] = []

    def record_misstatement(
        self,
        reference: str,
        description: str,
        amount: float,
        category: str,
        account: str,
        impact_fields: dict[str, float] | None = None,
        root_cause: str = "",
    ) -> Misstatement:
        impact = impact_fields or {}
        ms = Misstatement(
            reference=reference,
            description=description,
            amount=abs(amount),
            category=category,
            account=account,
            impact_on_profit=impact.get("profit", 0),
            impact_on_assets=impact.get("assets", 0),
            impact_on_liabilities=impact.get("liabilities", 0),
            impact_on_equity=impact.get("equity", 0),
            root_cause=root_cause,
        )
        self.misstatements.append(ms)
        return ms

    def mark_corrected(self, reference: str) -> bool:
        for ms in self.misstatements:
            if ms.reference == reference:
                ms.is_corrected = True
                return True
        return False

    def evaluate(
        self,
        planning_materiality: float,
        performance_materiality: float | None = None,
    ) -> MisstatementEvaluation:
        if performance_materiality is None:
            performance_materiality = planning_materiality * 0.75

        clearly_trivial = planning_materiality * 0.05

        total_factual = sum(ms.amount for ms in self.misstatements if ms.category == "factual" and not ms.is_corrected)
        total_judgmental = sum(
            ms.amount for ms in self.misstatements if ms.category == "judgmental" and not ms.is_corrected
        )
        total_projected = sum(
            ms.amount for ms in self.misstatements if ms.category == "projected" and not ms.is_corrected
        )
        total_uncorrected = total_factual + total_judgmental + total_projected
        corrected_amount = sum(ms.amount for ms in self.misstatements if ms.is_corrected)
        net_profit_impact = sum(ms.impact_on_profit for ms in self.misstatements if not ms.is_corrected)

        factual_count = sum(1 for ms in self.misstatements if ms.category == "factual")
        judgmental_count = sum(1 for ms in self.misstatements if ms.category == "judgmental")
        projected_count = sum(1 for ms in self.misstatements if ms.category == "projected")

        summary = MisstatementSummary(
            total_factual=round(total_factual),
            total_judgmental=round(total_judgmental),
            total_projected=round(total_projected),
            total_uncorrected=round(total_uncorrected),
            factual_count=factual_count,
            judgmental_count=judgmental_count,
            projected_count=projected_count,
            corrected_amount=round(corrected_amount),
            net_impact_on_profit=round(net_profit_impact),
        )

        is_material = total_uncorrected > performance_materiality
        is_pervasive = total_uncorrected > planning_materiality * 2

        if is_pervasive:
            opinion = "adverse" if total_uncorrected > 0 else "disclaimer"
        elif is_material:
            opinion = "qualified"
        else:
            opinion = "unmodified"

        rationale_parts = []
        rationale_parts.append(f"Planning Materiality: {planning_materiality:,.0f}")
        rationale_parts.append(f"Performance Materiality: {performance_materiality:,.0f}")
        rationale_parts.append(f"Clearly Trivial Threshold: {clearly_trivial:,.0f}")
        rationale_parts.append(f"Total Uncorrected Misstatements: {total_uncorrected:,.0f}")
        rationale_parts.append(f"  - Factual: {total_factual:,.0f} ({factual_count} items)")
        rationale_parts.append(f"  - Judgmental: {total_judgmental:,.0f} ({judgmental_count} items)")
        rationale_parts.append(f"  - Projected: {total_projected:,.0f} ({projected_count} items)")

        if is_pervasive:
            rationale_parts.append("CONCLUSION: Misstatements are pervasive - material and widespread")
        elif is_material:
            rationale_parts.append("CONCLUSION: Misstatements are material but not pervasive")
        else:
            rationale_parts.append("CONCLUSION: Misstatements are below materiality threshold")

        rationale_parts.append(f"Proposed Audit Opinion: {opinion}")

        return MisstatementEvaluation(
            misstatements=list(self.misstatements),
            summary=summary,
            planning_materiality=planning_materiality,
            performance_materiality=performance_materiality,
            clearly_trivial_threshold=clearly_trivial,
            is_material=is_material,
            is_pervasive=is_pervasive,
            proposed_opinion=opinion,
            rationale="\n".join(rationale_parts),
        )

    def project_misstatement(
        self,
        sample_misstatement: float,
        population_value: float,
        sample_value: float,
        description: str,
        account: str,
    ) -> Misstatement:
        if sample_value <= 0:
            return Misstatement(
                reference=f"PROJ-{len(self.misstatements) + 1}",
                description=description,
                amount=0,
                category="projected",
                account=account,
            )
        projected = sample_misstatement * (population_value / sample_value)
        return Misstatement(
            reference=f"PROJ-{len(self.misstatements) + 1}",
            description=f"Projected: {description}",
            amount=round(projected),
            category="projected",
            account=account,
            impact_on_profit=projected if account != "asset" else 0,
            impact_on_assets=projected if account == "asset" else 0,
            root_cause="extrapolation_from_sample",
        )


def format_misstatements_for_response(evaluation: MisstatementEvaluation) -> dict[str, Any]:
    return {
        "summary": {
            "total_factual": evaluation.summary.total_factual,
            "total_judgmental": evaluation.summary.total_judgmental,
            "total_projected": evaluation.summary.total_projected,
            "total_uncorrected": evaluation.summary.total_uncorrected,
            "factual_count": evaluation.summary.factual_count,
            "judgmental_count": evaluation.summary.judgmental_count,
            "projected_count": evaluation.summary.projected_count,
            "corrected_amount": evaluation.summary.corrected_amount,
            "net_impact_on_profit": evaluation.summary.net_impact_on_profit,
        },
        "materiality_thresholds": {
            "planning_materiality": evaluation.planning_materiality,
            "performance_materiality": evaluation.performance_materiality,
            "clearly_trivial_threshold": evaluation.clearly_trivial_threshold,
        },
        "is_material": evaluation.is_material,
        "is_pervasive": evaluation.is_pervasive,
        "proposed_opinion": evaluation.proposed_opinion,
        "misstatements": [
            {
                "reference": m.reference,
                "description": m.description,
                "amount": m.amount,
                "category": m.category,
                "account": m.account,
                "is_corrected": m.is_corrected,
                "root_cause": m.root_cause,
                "impact": {
                    "profit": m.impact_on_profit,
                    "assets": m.impact_on_assets,
                    "liabilities": m.impact_on_liabilities,
                    "equity": m.impact_on_equity,
                },
            }
            for m in evaluation.misstatements
        ],
        "rationale": evaluation.rationale,
    }
