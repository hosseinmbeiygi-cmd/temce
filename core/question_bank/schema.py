"""📋 Pre-buy question-bank contracts (بانک سؤالات پیش از خرید سهم).

The bank is *content*, the engine is *judgement*, and neither touches the database.
A question is an answerable unit with an explicit evidence contract: every number the
UI shows next to a question declares where it came from, and an absent value is
reported as missing rather than silently substituted by a proxy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BANK_VERSION = "1.0.0"

#: "unknown" is a legitimate recorded answer — it is also what stops progression.
#: The framework's execution rule is: a "نمی‌دانم" answer means do not go to the next stage.
UNKNOWN = "unknown"

AnswerKind = Literal["yes_no_unknown", "choice", "number", "text"]
EvidenceStatus = Literal["available", "missing"]
StageStatus = Literal["empty", "in_progress", "blocked_unknown", "vetoed", "complete"]
Verdict = Literal["not_started", "in_progress", "blocked_unknown", "vetoed", "hold", "cleared"]

#: What a tradable thing *is*, as far as this platform's tables can tell. Each value
#: exists because a stored column can evidence it (see ``services/pre_buy_instrument.py``)
#: — which is why there is no ``gold_fund`` or ``reit``: ``funds.fund_type`` types the gold
#: ETFs as «بخشی», so the only thing separating them from an equity fund is the word «طلا»
#: in a name, and a name match is a guess rather than data. REITs have no table at all.
#: Only ``equity`` has an authored bank today; the rest resolve to ``UnknownInstrument``
#: and must be reported as such rather than answered with the stock questions.
InstrumentType = Literal[
    "equity",
    "etf",
    "fund",
    "leveraged_fund",
    "fixed_income",
    "commodity_fund",
    "commodity_certificate",
    "future",
    "option",
    "portfolio_allocation",
    "unknown",
]

#: Stored order — the column's CHECK constraint and the API's enum are generated from
#: this tuple, so a type can never be accepted by one and refused by the other.
INSTRUMENT_TYPES: tuple[InstrumentType, ...] = (
    "equity", "etf", "fund", "leveraged_fund", "fixed_income", "commodity_fund",
    "commodity_certificate", "future", "option", "portfolio_allocation", "unknown",
)

INSTRUMENT_LABELS: dict[str, str] = {
    "equity": "سهام",
    "etf": "صندوق قابل‌معامله در بورس",
    "fund": "صندوق سرمایه‌گذاری",
    "leveraged_fund": "صندوق اهرمی",
    "fixed_income": "صندوق درآمد ثابت / اوراق",
    "commodity_fund": "صندوق کالایی یا طلا",
    "commodity_certificate": "گواهی سپردهٔ کالایی",
    "future": "قرارداد آتی",
    "option": "اختیار معامله",
    "portfolio_allocation": "تخصیص دارایی در سطح سبد",
    "unknown": "نوع نامشخص",
}


@dataclass(frozen=True)
class Option:
    """One selectable answer for a ``choice`` question.

    ``veto`` marks the option that *fails* the question — for a stopper it is what
    turns the sheet into «نخرید», so it must be authored explicitly, never inferred.
    """

    id: str
    label: str
    veto: bool = False


@dataclass(frozen=True)
class Input:
    """A numeric field inside a question that asks for more than one figure.

    ``role`` is the semantic handle the engine uses for derived maths (position size,
    R:R, implied portfolio value) so that rewording a question never breaks the maths.
    """

    id: str
    label: str
    unit: str = ""
    role: str = ""
    min: float | None = None
    max: float | None = None


@dataclass(frozen=True)
class Evidence:
    """A live figure the sheet surfaces beside a question.

    ``source`` is the literal API path or table the value is read from. It is shown to
    the user verbatim, so an evidence item that cannot be resolved is dropped to
    ``missing`` with its source kept visible.
    """

    key: str
    label: str
    source: str
    unit: str = ""


@dataclass(frozen=True)
class Question:
    """A single question of the bank."""

    code: str
    stage: int
    text: str
    kind: AnswerKind
    #: ★ stopper — an inappropriate answer rejects the analysis outright.
    stopper: bool = False
    hint: str = ""
    options: tuple[Option, ...] = ()
    #: Failing answers for ``yes_no_unknown`` questions. Only stoppers declare this — the
    #: framework reserves «رد» for ★ questions, so a non-stopper's negative answer is
    #: recorded and displayed but never vetoes the sheet.
    veto_values: tuple[str, ...] = ()
    inputs: tuple[Input, ...] = ()
    unit: str = ""
    #: Force a written justification. Used where the framework demands a *written* plan
    #: (exit rule, invalidation condition, two-sentence reason) rather than a click.
    note_required: bool = False
    evidence: tuple[Evidence, ...] = ()
    #: One of the five golden questions (خلاصهٔ همهٔ ۱۱۵).
    golden: bool = False

    def veto_options(self) -> frozenset[str]:
        return frozenset(o.id for o in self.options if o.veto)

    def is_answered(self, answer: Answer | None) -> bool:
        return answer is not None and answer.is_answered_for(self)


@dataclass(frozen=True)
class Stage:
    """One of the eleven stages (مرحله ۰ تا ۱۰)."""

    id: int
    key: str
    title: str
    purpose: str
    #: The stage's own execution rule, shown in the header.
    rule: str = ""


@dataclass(frozen=True)
class Answer:
    """A user's recorded answer for exactly one question."""

    code: str
    value: str | None = None
    numbers: dict[str, float] = field(default_factory=dict)
    note: str | None = None
    answered_at: str | None = None

    def is_answered_for(self, question: Question) -> bool:
        if question.kind == "number":
            return bool(self.numbers) and all(
                self.numbers.get(inp.id) is not None for inp in question.inputs
            )
        return self.value is not None and self.value != ""

    @property
    def is_unknown(self) -> bool:
        return self.value == UNKNOWN


@dataclass(frozen=True)
class EvidenceValue:
    """A resolved evidence figure, or an explicit absence.

    ``declared`` separates the two kinds of absence: no column anywhere holds this figure
    (the platform's gap) versus this symbol's row not carrying it (the user's gap).
    """

    key: str
    label: str
    source: str
    unit: str = ""
    value: float | str | None = None
    as_of: str | None = None
    status: EvidenceStatus = "missing"
    note: str = ""
    declared: bool = False


__all__ = [
    "BANK_VERSION",
    "UNKNOWN",
    "Answer",
    "AnswerKind",
    "Evidence",
    "EvidenceStatus",
    "EvidenceValue",
    "INSTRUMENT_LABELS",
    "INSTRUMENT_TYPES",
    "Input",
    "InstrumentType",
    "Option",
    "Question",
    "Stage",
    "StageStatus",
    "Verdict",
]
