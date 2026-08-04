from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WorkingPaper:
    wp_ref: str = ""
    title: str = ""
    prepared_by: str = ""
    reviewed_by: str = ""
    date_prepared: str = ""
    date_reviewed: str = ""
    status: str = "draft"
    objectives: list[str] = field(default_factory=list)
    procedures_performed: list[str] = field(default_factory=list)
    conclusions: str = ""
    cross_references: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)


@dataclass
class AuditFile:
    file_name: str = ""
    period: str = ""
    entity: str = ""
    sections: dict[str, list[WorkingPaper]] = field(default_factory=dict)
    assembly_status: str = "in_progress"
    sign_offs: dict[str, str] = field(default_factory=dict)
    file_complete: bool = False


WP_STRUCTURE = {
    "A": "Planning & Risk Assessment",
    "B": "Internal Control & Control Testing",
    "C": "Substantive Procedures - Balance Sheet",
    "D": "Substantive Procedures - Income Statement",
    "E": "Substantive Procedures - Cash Flow & Notes",
    "F": "Completion & Reporting",
    "G": "Management Letters & Communications",
}


class AuditDocumenter:
    """ISA 230: Audit Documentation"""

    @classmethod
    def create_working_paper(
        cls, wp_ref: str, title: str,
        objectives: list[str] | None = None,
        procedures: list[str] | None = None,
    ) -> WorkingPaper:
        return WorkingPaper(
            wp_ref=wp_ref,
            title=title,
            objectives=objectives or [],
            procedures_performed=procedures or [],
        )

    @classmethod
    def create_audit_file(cls, entity: str, period: str) -> AuditFile:
        af = AuditFile(
            file_name=f"{entity}_{period}_audit_file",
            period=period,
            entity=entity,
        )
        for _section_ref, section_name in WP_STRUCTURE.items():
            af.sections[section_name] = []
        return af

    @classmethod
    def add_working_paper(cls, af: AuditFile, section: str, wp: WorkingPaper) -> None:
        if section in af.sections:
            af.sections[section].append(wp)

    @classmethod
    def add_review_note(cls, wp: WorkingPaper, note: str) -> None:
        wp.review_notes.append(note)

    @classmethod
    def sign_off(cls, af: AuditFile, reviewer: str, date: str) -> None:
        af.sign_offs[reviewer] = date

    @classmethod
    def check_completeness(cls, af: AuditFile) -> bool:
        for _section, wps in af.sections.items():
            for wp in wps:
                if wp.status != "approved":
                    return False
        af.file_complete = True
        af.assembly_status = "complete"
        return True

    @classmethod
    def generate_wp_index(cls, af: AuditFile) -> dict[str, Any]:
        index = {}
        for section_name, wps in af.sections.items():
            index[section_name] = [
                {"wp_ref": wp.wp_ref, "title": wp.title, "status": wp.status}
                for wp in wps
            ]
        return index


def format_documentation_for_response(af: AuditFile) -> dict[str, Any]:
    return {
        "file_name": af.file_name,
        "entity": af.entity,
        "period": af.period,
        "assembly_status": af.assembly_status,
        "file_complete": af.file_complete,
        "sign_offs": af.sign_offs,
        "section_summary": {
            section: {
                "total_wps": len(wps),
                "approved": sum(1 for wp in wps if wp.status == "approved"),
                "draft": sum(1 for wp in wps if wp.status == "draft"),
            }
            for section, wps in af.sections.items()
            if wps
        },
        "wp_index": AuditDocumenter.generate_wp_index(af),
    }
