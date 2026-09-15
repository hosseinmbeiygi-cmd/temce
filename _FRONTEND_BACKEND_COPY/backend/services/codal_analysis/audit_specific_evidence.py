from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class InventoryObservation:
    location: str = ""
    date: str = ""
    team_members: list[str] = field(default_factory=list)
    count_method: str = ""
    test_counts: int = 0
    test_differences: int = 0
    difference_rate: float = 0
    accuracy_assessment: str = "satisfactory"
    notes: list[str] = field(default_factory=list)


@dataclass
class LitigationAssessment:
    case_name: str = ""
    nature: str = ""
    claim_amount: float = 0
    likelihood: str = "possible"
    provision_required: bool = False
    recommended_provision: float = 0
    disclosure_required: bool = True
    legal_counsel_confirmation: str = ""


@dataclass
class OpeningBalanceAssessment:
    prior_period_audited: bool = False
    prior_opinion_type: str = ""
    consistency_policy: bool = True
    material_misstatements: bool = False
    adjustment_required: bool = False
    conclusion: str = ""


class SpecificEvidenceAssessor:
    """ISA 501: Audit Evidence — Specific Items"""

    @classmethod
    def inventory_observation(
        cls,
        location: str,
        date: str,
        test_counts: int = 100,
        test_differences: int = 0,
        count_method: str = "full",
    ) -> InventoryObservation:
        diff_rate = test_differences / test_counts if test_counts > 0 else 0
        accuracy = (
            "satisfactory" if diff_rate <= 0.02 else "needs_improvement" if diff_rate <= 0.05 else "unsatisfactory"
        )
        notes = []
        if diff_rate <= 0.02:
            notes.append("Inventory count differences within acceptable tolerance")
        elif diff_rate <= 0.05:
            notes.append(f"Differences at {diff_rate:.1%} require expanded testing")
        else:
            notes.append(f"Differences at {diff_rate:.1%} require significant additional procedures")

        return InventoryObservation(
            location=location,
            date=date,
            test_counts=test_counts,
            test_differences=test_differences,
            difference_rate=round(diff_rate, 4),
            count_method=count_method,
            accuracy_assessment=accuracy,
            notes=notes,
        )

    @classmethod
    def litigation_assessment(
        cls,
        case_name: str,
        nature: str,
        claim_amount: float,
        likelihood: str = "possible",
    ) -> LitigationAssessment:
        la = LitigationAssessment(
            case_name=case_name,
            nature=nature,
            claim_amount=claim_amount,
            likelihood=likelihood,
        )
        if likelihood == "probable":
            la.provision_required = True
            la.recommended_provision = claim_amount * 0.8
            la.disclosure_required = True
        elif likelihood == "remote":
            la.provision_required = False
            la.disclosure_required = False
        else:
            la.provision_required = False
            la.disclosure_required = True
            la.recommended_provision = claim_amount * 0.3
        return la

    @classmethod
    def opening_balances(
        cls,
        prior_audited: bool = False,
        prior_opinion: str = "unmodified",
        policy_consistent: bool = True,
        material_issues: bool = False,
    ) -> OpeningBalanceAssessment:
        ob = OpeningBalanceAssessment(
            prior_period_audited=prior_audited,
            prior_opinion_type=prior_opinion,
            consistency_policy=policy_consistent,
            material_misstatements=material_issues,
        )
        if not prior_audited:
            ob.conclusion = "Additional procedures on opening balances required - first audit engagement"
            ob.adjustment_required = True
        elif prior_opinion != "unmodified":
            ob.conclusion = f"Prior period opinion was {prior_opinion} - review opening balances impact"
            ob.adjustment_required = True
        elif not policy_consistent:
            ob.conclusion = "Change in accounting policy - verify retrospective application"
            ob.adjustment_required = True
        elif material_issues:
            ob.conclusion = "Material misstatements identified in opening balances"
            ob.adjustment_required = True
        else:
            ob.conclusion = "Opening balances consistent and supported"
        return ob


def format_specific_evidence_for_response(obj: Any) -> dict[str, Any]:
    if isinstance(obj, InventoryObservation):
        return {
            "type": "inventory_observation",
            "location": obj.location,
            "date": obj.date,
            "test_counts": obj.test_counts,
            "test_differences": obj.test_differences,
            "difference_rate": obj.difference_rate,
            "accuracy_assessment": obj.accuracy_assessment,
            "notes": obj.notes,
        }
    if isinstance(obj, LitigationAssessment):
        return {
            "type": "litigation_assessment",
            "case_name": obj.case_name,
            "nature": obj.nature,
            "claim_amount": obj.claim_amount,
            "likelihood": obj.likelihood,
            "provision_required": obj.provision_required,
            "recommended_provision": obj.recommended_provision,
            "disclosure_required": obj.disclosure_required,
        }
    if isinstance(obj, OpeningBalanceAssessment):
        return {
            "type": "opening_balances",
            "prior_period_audited": obj.prior_period_audited,
            "prior_opinion_type": obj.prior_opinion_type,
            "consistency_policy": obj.consistency_policy,
            "material_misstatements": obj.material_misstatements,
            "adjustment_required": obj.adjustment_required,
            "conclusion": obj.conclusion,
        }
    return {"type": "unknown", "data": str(obj)}
