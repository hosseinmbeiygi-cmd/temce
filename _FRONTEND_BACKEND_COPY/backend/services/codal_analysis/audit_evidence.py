from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

EVIDENCE_TYPES = [
    "inspection_of_records",
    "inspection_of_assets",
    "observation",
    "external_confirmation",
    "recalculation",
    "reperformance",
    "analytical_procedure",
    "inquiry",
    "scanning",
]

EVIDENCE_RELIABILITY: dict[str, float] = {
    "external_confirmation": 0.95,
    "inspection_of_assets": 0.90,
    "recalculation": 0.85,
    "reperformance": 0.85,
    "inspection_of_records": 0.75,
    "observation": 0.70,
    "analytical_procedure": 0.60,
    "scanning": 0.40,
    "inquiry": 0.30,
}


@dataclass
class EvidenceItem:
    assertion: str
    procedure_type: str
    description: str
    source: str
    reliability_score: float = 0.5
    is_sufficient: bool = True
    is_appropriate: bool = True
    reference: str = ""
    conclusion: str = ""


@dataclass
class EvidenceCollection:
    account: str = ""
    items: list[EvidenceItem] = field(default_factory=list)
    overall_sufficiency: str = "adequate"
    overall_appropriateness: str = "adequate"
    gaps: list[str] = field(default_factory=list)


class EvidenceEvaluator:
    """ISA 500: Audit Evidence"""

    @classmethod
    def reliability(cls, procedure_type: str) -> float:
        return EVIDENCE_RELIABILITY.get(procedure_type, 0.5)

    @classmethod
    def assess_evidence(cls, account: str, assertions: list[str]) -> EvidenceCollection:
        ec = EvidenceCollection(account=account)

        assertion_procedures = {
            "occurrence": ["inspection_of_records", "external_confirmation"],
            "completeness": ["inspection_of_records", "analytical_procedure"],
            "accuracy": ["recalculation", "inspection_of_records"],
            "cutoff": ["inspection_of_records", "analytical_procedure"],
            "classification": ["inspection_of_records", "inquiry"],
            "existence": ["inspection_of_assets", "external_confirmation", "observation"],
            "rights_obligations": ["inspection_of_records", "inquiry"],
            "valuation": ["recalculation", "analytical_procedure", "inspection_of_records"],
        }

        for assertion in assertions:
            procedures = assertion_procedures.get(assertion, ["inquiry"])
            for proc in procedures:
                rel = cls.reliability(proc)
                ec.items.append(
                    EvidenceItem(
                        assertion=assertion,
                        procedure_type=proc,
                        description=f"Evidence for {assertion} using {proc}",
                        source="internal"
                        if proc in ("recalculation", "reperformance", "analytical_procedure")
                        else "external",
                        reliability_score=rel,
                        is_sufficient=rel >= 0.4,
                        is_appropriate=rel >= 0.3,
                        reference=f"{account.upper()}_{assertion}_{proc[:3]}",
                        conclusion=f"{'Sufficient' if rel >= 0.4 else 'Insufficient'} appropriate evidence from {proc}",
                    )
                )

        high_risk_assertions = [a for a in assertions if a in ("valuation", "existence", "completeness")]
        for a in high_risk_assertions:
            max_rel = max((e.reliability_score for e in ec.items if e.assertion == a), default=0)
            if max_rel < 0.6:
                ec.gaps.append(f"Insufficient reliable evidence for {a} (max reliability: {max_rel:.0%})")

        if ec.gaps:
            ec.overall_sufficiency = "inadequate"
            ec.overall_appropriateness = "inadequate"

        return ec


def format_evidence_for_response(ec: EvidenceCollection) -> dict[str, Any]:
    return {
        "account": ec.account,
        "overall_sufficiency": ec.overall_sufficiency,
        "overall_appropriateness": ec.overall_appropriateness,
        "gaps": ec.gaps,
        "evidence_items": [
            {
                "assertion": e.assertion,
                "procedure_type": e.procedure_type,
                "description": e.description,
                "source": e.source,
                "reliability_score": e.reliability_score,
                "is_sufficient": e.is_sufficient,
                "conclusion": e.conclusion,
            }
            for e in ec.items
        ],
    }
