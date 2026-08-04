from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IndependenceCheck:
    financial_interest: bool = False
    employment_relationship: bool = False
    business_relationship: bool = False
    family_relationship: bool = False
    non_audit_services: list[str] = field(default_factory=list)
    safeguards_applied: list[str] = field(default_factory=list)
    is_independent: bool = True
    conclusion: str = ""


@dataclass
class EQCRFinding:
    area: str = ""
    finding: str = ""
    severity: str = "medium"
    resolution: str = ""
    is_resolved: bool = False


@dataclass
class QualityControlReview:
    engagement_partner: str = ""
    eqcr_partner: str = ""
    date: str = ""
    findings: list[EQCRFinding] = field(default_factory=list)
    all_resolved: bool = True
    overall_conclusion: str = ""


EQCR_CHECKLIST = [
    "Significant audit risks identified and addressed",
    "Materiality assessments are appropriate",
    "Management override of controls addressed",
    "Fraud risks properly considered",
    "Related party transactions reviewed",
    "Going concern assessment completed",
    "Use of management experts evaluated",
    "Sufficient appropriate audit evidence obtained",
    "Significant judgments and conclusions documented",
    "Financial statement disclosures reviewed for compliance",
    "Subsequent events review completed",
    "Management representation letter obtained",
    "Independence confirmed",
    "Consultation on significant technical matters documented",
]


class QualityControlManager:
    """ISA 220: Quality Control for an Audit"""

    @classmethod
    def check_independence(
        cls,
        has_financial_interest: bool = False,
        has_employment: bool = False,
        has_business: bool = False,
        has_family: bool = False,
        non_audit: list[str] | None = None,
    ) -> IndependenceCheck:
        ic = IndependenceCheck(
            financial_interest=has_financial_interest,
            employment_relationship=has_employment,
            business_relationship=has_business,
            family_relationship=has_family,
            non_audit_services=non_audit or [],
        )
        threats = [has_financial_interest, has_employment, has_business, has_family]
        if any(threats):
            ic.is_independent = False
            ic.conclusion = "Independence impaired - cannot accept or continue engagement"
        else:
            ic.is_independent = True
            ic.conclusion = "Independence confirmed - no threats identified"
        return ic

    @classmethod
    def eqc_review(
        cls, engagement_partner: str, eqcr_partner: str,
        date: str, findings: list[dict[str, Any]] | None = None,
    ) -> QualityControlReview:
        review = QualityControlReview(
            engagement_partner=engagement_partner,
            eqcr_partner=eqcr_partner,
            date=date,
        )
        findings = findings or []
        for f in findings:
            finding = EQCRFinding(
                area=f.get("area", ""),
                finding=f.get("finding", ""),
                severity=f.get("severity", "medium"),
                resolution=f.get("resolution", ""),
                is_resolved=f.get("is_resolved", False),
            )
            review.findings.append(finding)

        unresolved = [f for f in review.findings if not f.is_resolved]
        review.all_resolved = len(unresolved) == 0

        if not review.all_resolved:
            review.overall_conclusion = f"EQCR incomplete - {len(unresolved)} unresolved findings"
        else:
            review.overall_conclusion = "EQCR completed - all findings resolved"

        return review

    @classmethod
    def eqcr_checklist_items(cls) -> list[str]:
        return list(EQCR_CHECKLIST)


def format_qc_for_response(obj: Any) -> dict[str, Any]:
    if isinstance(obj, IndependenceCheck):
        return {
            "type": "independence_check",
            "is_independent": obj.is_independent,
            "threats": {
                "financial_interest": obj.financial_interest,
                "employment": obj.employment_relationship,
                "business": obj.business_relationship,
                "family": obj.family_relationship,
            },
            "non_audit_services": obj.non_audit_services,
            "conclusion": obj.conclusion,
        }
    if isinstance(obj, QualityControlReview):
        return {
            "type": "eqcr_review",
            "engagement_partner": obj.engagement_partner,
            "eqcr_partner": obj.eqcr_partner,
            "date": obj.date,
            "all_resolved": obj.all_resolved,
            "overall_conclusion": obj.overall_conclusion,
            "findings": [
                {"area": f.area, "finding": f.finding, "severity": f.severity,
                 "resolution": f.resolution, "is_resolved": f.is_resolved}
                for f in obj.findings
            ],
        }
    return {"type": "unknown", "data": str(obj)}
