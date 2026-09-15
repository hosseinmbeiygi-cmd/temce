from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SubsequentEvent:
    description: str = ""
    date_occurred: str = ""
    date_identified: str = ""
    financial_impact: float = 0
    event_type: str = ""  # adjusting, non_adjusting
    accounting_requirement: str = ""
    disclosure_status: str = ""


@dataclass
class SubsequentEventsAssessment:
    period_end: str = ""
    report_approval_date: str = ""
    events: list[SubsequentEvent] = field(default_factory=list)
    adjusting_events: list[dict[str, Any]] = field(default_factory=list)
    non_adjusting_events: list[dict[str, Any]] = field(default_factory=list)
    procedures_performed: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)


class SubsequentEventsAuditor:
    """ISA 560: Subsequent Events"""

    PROCEDURES = [
        "Review minutes of board meetings after period end",
        "Review latest interim financial statements",
        "Inquire of management about subsequent events",
        "Review subsequent cash receipts and payments",
        "Review subsequent legal correspondence",
        "Check for debt covenant violations after period end",
        "Review subsequent asset valuation changes",
        "Inquire about status of items subject to estimation uncertainty",
    ]

    @classmethod
    def classify_event(
        cls,
        description: str,
        amount: float,
        conditions_met: list[str] | None = None,
    ) -> SubsequentEvent:
        conditions_met = conditions_met or []

        adjusting_indicators = [
            "bankruptcy of customer",
            "settlement of litigation",
            "receipt of information about asset valuation",
            "resolution of estimation uncertainty",
            "correction of error",
        ]
        non_adjusting_indicators = [
            "business combination",
            "issue of shares",
            "natural disaster",
            "major restructuring announced",
            "change in foreign exchange rates",
            "decline in market value of investments",
        ]

        is_adjusting = any(ind in description.lower() for ind in adjusting_indicators)
        is_non_adjusting = any(ind in description.lower() for ind in non_adjusting_indicators)

        if is_adjusting:
            event_type = "adjusting"
            requirement = "Adjust financial statements (IAS 10 para 8)"
            disclosure = "disclose_in_financials"
        elif is_non_adjusting:
            event_type = "non_adjusting"
            requirement = "Disclose nature and estimate (IAS 10 para 21)"
            disclosure = "disclose_in_notes"
        else:
            event_type = "non_adjusting" if amount > 0 else "adjusting"
            requirement = "Evaluate materiality and disclose if material"
            disclosure = "evaluate"

        return SubsequentEvent(
            description=description,
            financial_impact=amount,
            event_type=event_type,
            accounting_requirement=requirement,
            disclosure_status=disclosure,
        )

    def assess(self, events: list[dict[str, Any]] | None = None) -> SubsequentEventsAssessment:
        events = events or []
        assessment = SubsequentEventsAssessment()

        for evt in events:
            se = self.classify_event(
                evt.get("description", ""),
                evt.get("amount", 0),
            )
            assessment.events.append(se)

            event_dict = {
                "description": se.description,
                "financial_impact": se.financial_impact,
                "accounting_requirement": se.accounting_requirement,
                "disclosure_status": se.disclosure_status,
            }
            if se.event_type == "adjusting":
                assessment.adjusting_events.append(event_dict)
            else:
                assessment.non_adjusting_events.append(event_dict)

        assessment.procedures_performed = list(self.PROCEDURES)

        if assessment.adjusting_events:
            assessment.conclusions.append(
                f"{len(assessment.adjusting_events)} adjusting events identified - financial statements must be adjusted"
            )
        if assessment.non_adjusting_events:
            assessment.conclusions.append(
                f"{len(assessment.non_adjusting_events)} non-adjusting events identified - disclosure required"
            )
        if not events:
            assessment.conclusions.append("No subsequent events noted")

        return assessment


def format_subsequent_for_response(assessment: SubsequentEventsAssessment) -> dict[str, Any]:
    return {
        "adjusting_events": assessment.adjusting_events,
        "non_adjusting_events": assessment.non_adjusting_events,
        "total_events": len(assessment.events),
        "procedures_performed": assessment.procedures_performed,
        "conclusions": assessment.conclusions,
    }
