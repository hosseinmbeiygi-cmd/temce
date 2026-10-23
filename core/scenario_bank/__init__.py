"""🎯 بانک سناریوی دستیار طلا و نقره — content (:mod:`.bank`), contracts (:mod:`.schema`),
judgement (:mod:`.engine`).

Free of database and HTTP imports, like :mod:`core.question_bank`, so the same check that
guards a live answer also runs in a unit test. The bank answers «what must this assistant
do when asked this?» — the four-part contract, the ban on profit promises, and the rule
that missing data is declared rather than decided on.
"""

from __future__ import annotations

from core.scenario_bank import bank, engine
from core.scenario_bank.bank import (
    ADVICE_CODES,
    REFUSAL_CODES,
    evidence_by_key,
    scenario,
    scenario_codes,
    scenarios,
    scenarios_by_category,
)
from core.scenario_bank.engine import check, gate
from core.scenario_bank.schema import (
    BANK_VERSION,
    CATEGORIES,
    CATEGORY_LABELS,
    MODE_LABELS,
    SECTION_IDS,
    SECTION_LABELS,
    CheckResult,
    GateResult,
    Requirement,
    Scenario,
    Violation,
)

__all__ = [
    "ADVICE_CODES",
    "BANK_VERSION",
    "CATEGORIES",
    "CATEGORY_LABELS",
    "MODE_LABELS",
    "REFUSAL_CODES",
    "SECTION_IDS",
    "SECTION_LABELS",
    "CheckResult",
    "GateResult",
    "Requirement",
    "Scenario",
    "Violation",
    "bank",
    "check",
    "engine",
    "evidence_by_key",
    "gate",
    "scenario",
    "scenario_codes",
    "scenarios",
    "scenarios_by_category",
]
