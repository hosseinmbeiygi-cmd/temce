from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AuditTeamMember:
    role: str = ""
    name: str = ""
    responsibilities: list[str] = field(default_factory=list)
    hours_budgeted: float = 0


@dataclass
class AuditTimeline:
    phase: str = ""
    start_date: str = ""
    end_date: str = ""
    key_deliverables: list[str] = field(default_factory=list)


@dataclass
class PreliminaryAnalyticalResult:
    procedure: str = ""
    current_year: float = 0
    prior_year: float = 0
    variance: float = 0
    variance_pct: float = 0
    explanation: str = ""
    risk_flag: bool = False


@dataclass
class AuditStrategy:
    entity: str = ""
    period: str = ""
    overall_approach: str = ""  # substantive, combined
    materiality_levels: dict[str, float] = field(default_factory=dict)
    team: list[AuditTeamMember] = field(default_factory=list)
    timeline: list[AuditTimeline] = field(default_factory=list)
    preliminary_analytics: list[PreliminaryAnalyticalResult] = field(default_factory=list)
    significant_risks: list[str] = field(default_factory=list)
    planned_coverage: dict[str, str] = field(default_factory=dict)
    strategy_memo: str = ""


class AuditPlanner:
    """ISA 300: Planning an Audit of Financial Statements"""

    def __init__(self):
        pass

    def create_strategy(
        self,
        entity: str,
        period: str,
        overall_approach: str = "combined",
    ) -> AuditStrategy:
        strategy = AuditStrategy(
            entity=entity,
            period=period,
            overall_approach=overall_approach,
        )

        strategy.team = [
            AuditTeamMember(role="Engagement Partner", responsibilities=["Overall supervision", "Final review"]),
            AuditTeamMember(role="Engagement Manager", responsibilities=["Day-to-day management", "Technical review"]),
            AuditTeamMember(role="Senior Auditor", responsibilities=["Supervision of staff", "Complex areas"]),
            AuditTeamMember(role="Staff Auditor", responsibilities=["Execution of procedures", "Documentation"]),
        ]

        strategy.timeline = [
            AuditTimeline(phase="Planning", key_deliverables=["Audit strategy", "Audit plan", "Risk assessment"]),
            AuditTimeline(phase="Interim", key_deliverables=["Control testing", "Preliminary analytics"]),
            AuditTimeline(phase="Final", key_deliverables=["Substantive procedures", "Completion"]),
            AuditTimeline(phase="Reporting", key_deliverables=["Draft report", "Final report", "Management letter"]),
        ]

        strategy.planned_coverage = {
            "revenue": "full_detail",
            "receivables": "full_detail",
            "inventory": "test_of_details",
            "cash": "full_detail",
            "payables": "sampling",
            "ppe": "analytical",
            "equity": "analytical",
        }

        return strategy

    def preliminary_analytical_procedures(
        self,
        current_data: dict[str, float],
        prior_data: dict[str, float] | None = None,
    ) -> list[PreliminaryAnalyticalResult]:
        results = []
        prior_data = prior_data or {}

        for item, current_val in current_data.items():
            prior_val = prior_data.get(item, 0)
            variance = current_val - prior_val
            variance_pct = variance / abs(prior_val) * 100 if prior_val else 0

            risk_flag = abs(variance_pct) > 20 if prior_val else False

            results.append(PreliminaryAnalyticalResult(
                procedure=f"{item} variance analysis",
                current_year=current_val,
                prior_year=prior_val,
                variance=variance,
                variance_pct=round(variance_pct, 1),
                risk_flag=risk_flag,
            ))

        return results

    def assess_scope(
        self,
        locations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        locations = locations or []
        scope = {
            "total_locations": len(locations),
            "significant_locations": 0,
            "coverage_pct": 0,
        }
        for loc in locations:
            if loc.get("revenue_pct", 0) > 15:
                scope["significant_locations"] += 1
        if scope["total_locations"] > 0:
            scope["coverage_pct"] = round(
                scope["significant_locations"] / scope["total_locations"] * 100, 1
            )
        return scope


def format_planning_for_response(strategy: AuditStrategy) -> dict[str, Any]:
    return {
        "entity": strategy.entity,
        "period": strategy.period,
        "overall_approach": strategy.overall_approach,
        "team": [
            {"role": m.role, "name": m.name, "responsibilities": m.responsibilities}
            for m in strategy.team
        ],
        "timeline": [
            {"phase": t.phase, "key_deliverables": t.key_deliverables}
            for t in strategy.timeline
        ],
        "planned_coverage": strategy.planned_coverage,
    }
