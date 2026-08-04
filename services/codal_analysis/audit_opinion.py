from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

OPINION_MATRIX = {
    ("not_material", "not_pervasive"): "unmodified",
    ("material", "not_pervasive"): "qualified",
    ("material", "pervasive"): "adverse",
    ("unable_to_obtain", "not_pervasive"): "qualified_disclaimer",
    ("unable_to_obtain", "pervasive"): "disclaimer",
}


@dataclass
class OpinionBasisParagraph:
    section: str = ""
    description: str = ""
    amount: float = 0
    reference: str = ""


@dataclass
class EmphasisOfMatter:
    description: str = ""
    standard_ref: str = ""
    is_key_audit_matter: bool = False


@dataclass
class OtherMatter:
    description: str = ""
    standard_ref: str = ""


@dataclass
class AuditOpinion:
    opinion_type: str = "unmodified"
    basis_paragraphs: list[OpinionBasisParagraph] = field(default_factory=list)
    emphasis_of_matter: list[EmphasisOfMatter] = field(default_factory=list)
    other_matters: list[OtherMatter] = field(default_factory=list)
    key_audit_matters: list[str] = field(default_factory=list)
    opinion_text: str = ""
    basis_text: str = ""
    report_date: str = ""


class OpinionFormulator:
    """ISA 700/705: Forming an Opinion and Reporting on Financial Statements"""

    def __init__(self):
        pass

    def determine_opinion(
        self,
        is_material: bool = False,
        is_pervasive: bool = False,
        scope_limitation: bool = False,
    ) -> str:
        if not scope_limitation:
            key = ("material" if is_material else "not_material",
                   "pervasive" if is_pervasive else "not_pervasive")
        else:
            key = ("unable_to_obtain",
                   "pervasive" if is_pervasive else "not_pervasive")
        return OPINION_MATRIX.get(key, "unmodified")

    def form_opinion(
        self,
        uncorrected_misstatements: float = 0,
        planning_materiality: float = 0,
        scope_limitations: list[str] | None = None,
        material_weakness_internal_control: bool = False,
        emphasis_matters: list[dict[str, Any]] | None = None,
        key_audit_matters: list[str] | None = None,
    ) -> AuditOpinion:
        scope_limitations = scope_limitations or []
        emphasis_matters = emphasis_matters or []
        key_audit_matters = key_audit_matters or []

        is_material = uncorrected_misstatements > planning_materiality * 0.75
        is_pervasive = uncorrected_misstatements > planning_materiality * 2
        has_scope_limitation = len(scope_limitations) > 0

        opinion_type = self.determine_opinion(is_material, is_pervasive, has_scope_limitation)

        opinion = AuditOpinion(opinion_type=opinion_type)

        # Basis paragraphs
        if is_material:
            opinion.basis_paragraphs.append(OpinionBasisParagraph(
                section="Basis for Qualified/Adverse Opinion",
                description=f"Misstatements of {uncorrected_misstatements:,.0f} exceed materiality of {planning_materiality:,.0f}",
                amount=uncorrected_misstatements,
            ))
        for sl in scope_limitations:
            opinion.basis_paragraphs.append(OpinionBasisParagraph(
                section="Basis for Disclaimer",
                description=sl,
            ))

        # Emphasis of Matter
        for em in emphasis_matters:
            opinion.emphasis_of_matter.append(EmphasisOfMatter(
                description=em.get("description", ""),
                standard_ref=em.get("standard", ""),
            ))

        # Key Audit Matters
        opinion.key_audit_matters = key_audit_matters

        # Generate opinion text
        opinion.opinion_text = self._generate_opinion_text(opinion_type)
        opinion.basis_text = self._generate_basis_text(opinion_type, opinion.basis_paragraphs)

        return opinion

    def _generate_opinion_text(self, opinion_type: str) -> str:
        texts = {
            "unmodified": "In our opinion, the accompanying financial statements present fairly, in all material respects, the financial position of the Company as at [date], and its financial performance and cash flows for the year then ended in accordance with [applicable financial reporting framework].",
            "qualified": "In our opinion, except for the effects of the matter described in the Basis for Qualified Opinion section, the accompanying financial statements present fairly...",
            "adverse": "In our opinion, because of the significance of the matter described in the Basis for Adverse Opinion section, the accompanying financial statements do not present fairly...",
            "disclaimer": "We do not express an opinion on the accompanying financial statements. Because of the significance of the matter described in the Basis for Disclaimer of Opinion section, we have not been able to obtain sufficient appropriate audit evidence...",
            "qualified_disclaimer": "We do not express an opinion on the accompanying financial statements... [Mixed opinion structure]",
        }
        return texts.get(opinion_type, "")

    def _generate_basis_text(self, opinion_type: str, paragraphs: list[OpinionBasisParagraph]) -> str:
        if not paragraphs:
            return "We conducted our audit in accordance with [applicable auditing standards]."
        parts = ["We conducted our audit in accordance with [applicable auditing standards]."]
        for p in paragraphs:
            parts.append(f"{p.section}: {p.description}")
        return "\n".join(parts)


def format_opinion_for_response(opinion: AuditOpinion) -> dict[str, Any]:
    return {
        "opinion_type": opinion.opinion_type,
        "opinion_text": opinion.opinion_text,
        "basis_text": opinion.basis_text,
        "basis_paragraphs": [
            {"section": p.section, "description": p.description, "amount": p.amount}
            for p in opinion.basis_paragraphs
        ],
        "emphasis_of_matter": [
            {"description": e.description, "standard_ref": e.standard_ref}
            for e in opinion.emphasis_of_matter
        ],
        "other_matters": [
            {"description": o.description}
            for o in opinion.other_matters
        ],
        "key_audit_matters": opinion.key_audit_matters,
    }
