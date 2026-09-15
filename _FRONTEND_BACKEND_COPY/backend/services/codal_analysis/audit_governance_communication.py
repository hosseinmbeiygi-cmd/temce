from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

COMMUNICATION_ITEMS = [
    "Auditor's responsibilities under applicable auditing standards",
    "Planned scope and timing of the audit",
    "Significant risks identified",
    "Materiality levels applied",
    "Significant findings from the audit",
    "Views about significant accounting practices",
    "Management override of controls considerations",
    "Fraud identified or suspected",
    "Related party transactions identified",
    "Significant deficiencies in internal control",
    "Uncorrected misstatements and their effect",
    "Disagreements with management",
    "Consultations with other accountants",
    "Independence matters",
    "Going concern issues",
]

COMMITTEE_CYCLES = [
    "Planning meeting",
    "Progress/Interim meeting",
    "Final/Results meeting",
    "Special meeting (as needed)",
]


@dataclass
class CommunicationRecord:
    topic: str = ""
    date: str = ""
    communicated_to: str = ""
    method: str = "meeting"
    key_points: str = ""
    follow_up_needed: bool = False


@dataclass
class GovernanceCommunicationPlan:
    entity: str = ""
    period: str = ""
    committee_meetings: list[dict[str, Any]] = field(default_factory=list)
    communication_items: dict[str, bool] = field(default_factory=dict)
    records: list[CommunicationRecord] = field(default_factory=list)
    all_communicated: bool = False
    pending_items: list[str] = field(default_factory=list)


class GovernanceCommunicator:
    """ISA 260: Communication with Those Charged with Governance"""

    @classmethod
    def create_plan(cls, entity: str, period: str) -> GovernanceCommunicationPlan:
        plan = GovernanceCommunicationPlan(entity=entity, period=period)
        plan.committee_meetings = [{"cycle": c, "status": "scheduled", "date": ""} for c in COMMITTEE_CYCLES]
        for item in COMMUNICATION_ITEMS:
            plan.communication_items[item] = False
        return plan

    @classmethod
    def mark_communicated(cls, plan: GovernanceCommunicationPlan, topic: str) -> bool:
        if topic in plan.communication_items:
            plan.communication_items[topic] = True
            return True
        return False

    @classmethod
    def add_record(
        cls,
        plan: GovernanceCommunicationPlan,
        topic: str,
        date: str,
        communicated_to: str,
        method: str = "meeting",
        key_points: str = "",
    ) -> None:
        plan.records.append(
            CommunicationRecord(
                topic=topic,
                date=date,
                communicated_to=communicated_to,
                method=method,
                key_points=key_points,
            )
        )

    @classmethod
    def check_completeness(cls, plan: GovernanceCommunicationPlan) -> None:
        pending = [k for k, v in plan.communication_items.items() if not v]
        plan.pending_items = pending
        plan.all_communicated = len(pending) == 0


def format_governance_for_response(plan: GovernanceCommunicationPlan) -> dict[str, Any]:
    return {
        "entity": plan.entity,
        "period": plan.period,
        "all_communicated": plan.all_communicated,
        "pending_items": plan.pending_items,
        "committee_meetings": plan.committee_meetings,
        "communication_status": {
            "total_items": len(plan.communication_items),
            "communicated": sum(1 for v in plan.communication_items.values() if v),
            "pending": len(plan.pending_items),
        },
        "records": [
            {
                "topic": r.topic,
                "date": r.date,
                "communicated_to": r.communicated_to,
                "method": r.method,
                "key_points": r.key_points,
            }
            for r in plan.records
        ],
    }
