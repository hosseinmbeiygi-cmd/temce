from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from services.codal_analysis.analysis_engine import FinancialSnapshot

logger = get_logger(__name__)

MATERIALITY_BENCHMARKS = {
    "revenue": {"rate_low": 0.005, "rate_high": 0.01, "description": "Revenue (0.5%-1%)"},
    "total_assets": {"rate_low": 0.01, "rate_high": 0.02, "description": "Total Assets (1%-2%)"},
    "net_profit": {"rate_low": 0.05, "rate_high": 0.10, "description": "Net Profit (5%-10%)"},
    "total_equity": {"rate_low": 0.01, "rate_high": 0.02, "description": "Total Equity (1%-2%)"},
}


@dataclass
class MaterialityLevel:
    benchmark_name: str
    benchmark_value: float
    percentage: float
    amount: float
    is_primary: bool = False


@dataclass
class AuditMateriality:
    planning_materiality: float = 0
    performance_materiality: float = 0
    clearly_trivial_threshold: float = 0
    specific_materialities: dict[str, float] = field(default_factory=dict)
    primary_benchmark: str = ""
    primary_benchmark_value: float = 0
    levels: list[MaterialityLevel] = field(default_factory=list)
    revision_history: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""


class MaterialityCalculator:
    """ISA 320: Materiality in Planning and Performing an Audit"""

    def __init__(self, performance_pct: float = 0.75, trivial_pct: float = 0.05):
        self.performance_pct = performance_pct
        self.trivial_pct = trivial_pct

    def calculate_levels(self, snap: FinancialSnapshot) -> list[MaterialityLevel]:
        levels = []
        benchmarks = [
            ("revenue", snap.revenue or 0),
            ("total_assets", snap.total_assets or 0),
            ("net_profit", abs(snap.net_profit or 0)),
            ("total_equity", abs(snap.total_equity or 0)),
        ]

        for bm_name, bm_value in benchmarks:
            config = MATERIALITY_BENCHMARKS[bm_name]
            if bm_value <= 0:
                continue
            rate = config["rate_high"]
            amount = bm_value * rate
            levels.append(MaterialityLevel(
                benchmark_name=bm_name,
                benchmark_value=bm_value,
                percentage=rate,
                amount=round(amount),
                is_primary=False,
            ))

        if not levels:
            return []

        levels.sort(key=lambda x: x.amount, reverse=True)

        primary_bm = levels[0].benchmark_name

        primary_value = snap.revenue or snap.total_assets or abs(snap.net_profit or 0) or abs(snap.total_equity or 0)
        # For profit-oriented entities, use net profit; for asset-heavy, use total assets
        if snap.net_profit and snap.net_profit > 0 and snap.revenue and snap.revenue > 0:
            if abs(snap.net_profit) / snap.revenue > 0.05:
                primary_bm = "net_profit"
        elif snap.total_assets and snap.total_assets > 0:
            primary_bm = "total_assets"

        config = MATERIALITY_BENCHMARKS[primary_bm]
        pm_amount = round(primary_value * config["rate_high"])

        for level in levels:
            level.is_primary = level.benchmark_name == primary_bm

        self._levels = levels
        self._primary_benchmark = primary_bm
        self._primary_value = primary_value
        self._planning_materiality = pm_amount
        self._performance_materiality = round(pm_amount * self.performance_pct)
        self._clearly_trivial = round(pm_amount * self.trivial_pct)

        return levels

    def calculate_specific_materialities(
        self, snap: FinancialSnapshot
    ) -> dict[str, float]:
        specific: dict[str, float] = {}
        pm = self._planning_materiality

        raw_data = getattr(snap, "raw_data", {}) or {}
        related_party = raw_data.get("RELATED_PARTY_TRANSACTIONS") or raw_data.get("related_party_transactions") or 0
        if related_party > 0:
            specific["related_party_transactions"] = round(pm * 0.5)

        raw_data = getattr(snap, "raw_data", {}) or {}
        litigation = raw_data.get("LITIGATION_CONTINGENCIES") or raw_data.get("litigation_contingencies") or 0
        if litigation > 0:
            specific["litigation_contingencies"] = round(pm * 0.3)

        return specific

    def assess_all(self, snap: FinancialSnapshot) -> AuditMateriality:
        levels = self.calculate_levels(snap)
        specific = self.calculate_specific_materialities(snap)

        rationale_parts = []
        if levels:
            rationale_parts.append(
                f"Primary benchmark: {self._primary_benchmark} "
                f"(value: {self._primary_value:,.0f}, "
                f"rate: {MATERIALITY_BENCHMARKS[self._primary_benchmark]['rate_high']:.1%})"
            )
            for lvl in levels:
                rationale_parts.append(
                    f"  {lvl.benchmark_name}: {lvl.benchmark_value:,.0f} x {lvl.percentage:.1%} = {lvl.amount:,.0f}"
                    f"{' [PRIMARY]' if lvl.is_primary else ''}"
                )

        return AuditMateriality(
            planning_materiality=self._planning_materiality,
            performance_materiality=self._performance_materiality,
            clearly_trivial_threshold=self._clearly_trivial,
            specific_materialities=specific,
            primary_benchmark=self._primary_benchmark,
            primary_benchmark_value=self._primary_value,
            levels=levels,
            rationale="\n".join(rationale_parts),
        )

    def revise_materiality(
        self,
        current: AuditMateriality,
        new_snap: FinancialSnapshot,
        reason: str,
    ) -> AuditMateriality:
        revised = self.assess_all(new_snap)
        revised.revision_history = list(current.revision_history) + [{
            "previous_pm": current.planning_materiality,
            "new_pm": revised.planning_materiality,
            "previous_performance_pm": current.performance_materiality,
            "new_performance_pm": revised.performance_materiality,
            "reason": reason,
        }]
        return revised


def format_materiality_for_response(mat: AuditMateriality) -> dict[str, Any]:
    return {
        "planning_materiality": mat.planning_materiality,
        "performance_materiality": mat.performance_materiality,
        "clearly_trivial_threshold": mat.clearly_trivial_threshold,
        "specific_materialities": mat.specific_materialities,
        "primary_benchmark": mat.primary_benchmark,
        "primary_benchmark_value": mat.primary_benchmark_value,
        "levels": [
            {
                "benchmark_name": idx.benchmark_name,
                "benchmark_value": idx.benchmark_value,
                "percentage": idx.percentage,
                "amount": idx.amount,
                "is_primary": idx.is_primary,
            }
            for idx in mat.levels
        ],
        "revision_history": mat.revision_history,
        "rationale": mat.rationale,
    }
