"""🎯 Scenario-bank contracts — بانک سناریوی دستیار طلا و نقره.

The pre-buy bank (:mod:`core.question_bank`) is a *form*: it asks the investor 115
questions and refuses to clear a buy until they are answered. This bank is a *contract*
on the assistant's own behaviour: for each realistic request it declares the data the
answer may rely on, the shape the answer must take, and the sentences that make the
answer wrong.

Content lives in :mod:`.bank`, judgement in :mod:`.engine`; like the pre-buy bank neither
touches the database or HTTP, so the same check that guards a live answer also runs in a
unit test with no fixtures.

Two ideas are load-bearing and stated here rather than inferred later:

* **Mode.** A request is either ``advise`` (a buy/sell/hold view is expected — and then the
  four-part contract and source+time are mandatory), ``inform`` (explain, no view), or
  ``refuse`` (outside the non-physical gold/silver mandate). A refusal that still slips in
  a recommendation is a failure, which is why mode is declared, never guessed from the
  answer's tone.
* **Requirement.** Every figure the scenario needs is named with the endpoint or column it
  comes from. A requirement the caller cannot resolve must surface as «نامشخص» — a scenario
  never invents a stand-in number, and the checker fails an answer that decides anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.question_bank.schema import InstrumentType

BANK_VERSION = "1.0.0"

#: The spec's seven scenario groups (سند تجمیعی، بخش ۷).
Category = Literal["buy", "sell", "analyze", "portfolio", "learn", "alert", "edge"]

CATEGORIES: tuple[Category, ...] = (
    "buy", "sell", "analyze", "portfolio", "learn", "alert", "edge",
)

CATEGORY_LABELS: dict[str, str] = {
    "buy": "خرید",
    "sell": "فروش",
    "analyze": "تحلیل",
    "portfolio": "پرتفوی",
    "learn": "آموزش",
    "alert": "هشدار",
    "edge": "حاشیه‌ای — خارج از دامنه یا بدرفتار",
}

#: What the assistant owes the user: a view, an explanation, or a refusal.
Mode = Literal["advise", "inform", "refuse"]

MODE_LABELS: dict[str, str] = {
    "advise": "پیشنهاد با قرارداد چهاربخشی",
    "inform": "توضیح بدون توصیه",
    "refuse": "رد مؤدبانه + توضیح دامنه",
}

#: The four sections every ``advise`` answer must carry (سند تجمیعی، بخش ۴).
SECTION_IDS: tuple[str, ...] = ("summary", "reasons", "risk", "action")

SECTION_LABELS: dict[str, str] = {
    "summary": "جمع‌بندی",
    "reasons": "دلایل",
    "risk": "ریسک و نقطهٔ ابطال",
    "action": "گام اجرایی",
}


@dataclass(frozen=True)
class Requirement:
    """A figure the scenario needs, with the endpoint/column that supplies it.

    ``source`` is shown to the user verbatim, exactly as in the pre-buy bank: a figure the
    platform cannot produce names the absent column rather than being filled by a
    lookalike.
    """

    key: str
    label: str
    source: str
    unit: str = ""


@dataclass(frozen=True)
class Scenario:
    """One realistic request and the answer contract it imposes."""

    code: str
    category: Category
    question: str
    mode: Mode
    #: Instrument classes this scenario applies to (see ``core.question_bank.schema``).
    instrument_types: tuple[InstrumentType, ...] = ()
    #: Data the answer may rely on; anything unresolved must be declared «نامشخص».
    requires: tuple[Requirement, ...] = ()
    #: Requirement keys this scenario *knows* the platform cannot resolve. Declared so the
    #: model answer is checked against reality and the checker's default availability is the
    #: scenario's own truth rather than an optimistic all-present guess.
    unresolved: tuple[str, ...] = ()
    #: A model answer, used as documentation and as the fixture the checker must pass.
    expected: str = ""
    #: Sentences that make the answer wrong *for this scenario* (وعدهٔ سود، «حتماً بخر»…).
    forbidden: tuple[str, ...] = ()
    rationale: str = ""

    def requirement_keys(self) -> tuple[str, ...]:
        return tuple(r.key for r in self.requires)


@dataclass(frozen=True)
class Violation:
    """One broken rule, named so the caller can group and log it."""

    rule: str
    detail: str


@dataclass(frozen=True)
class CheckResult:
    """The verdict for one produced answer against one scenario."""

    code: str
    mode: Mode
    passed: bool
    missing_sections: tuple[str, ...] = ()
    unresolved_requirements: tuple[str, ...] = ()
    violations: tuple[Violation, ...] = ()

    @property
    def reasons(self) -> tuple[str, ...]:
        out = [f"{v.rule}: {v.detail}" for v in self.violations]
        if self.missing_sections:
            out.append("بخش‌های غایب: " + "، ".join(self.missing_sections))
        return tuple(out)


@dataclass(frozen=True)
class GateResult:
    """Where a free-text question belongs before any answer is composed."""

    question: str
    in_scope: bool
    mode: Mode
    category: Category
    matched: tuple[str, ...] = ()
    reason: str = ""


__all__ = [
    "BANK_VERSION",
    "CATEGORIES",
    "CATEGORY_LABELS",
    "CheckResult",
    "Category",
    "GateResult",
    "MODE_LABELS",
    "Mode",
    "Requirement",
    "SECTION_IDS",
    "SECTION_LABELS",
    "Scenario",
    "Violation",
]
