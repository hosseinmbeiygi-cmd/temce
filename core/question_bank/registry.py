"""🧬 Instrument axis: one shared core + one module per instrument class.

The bank was transcribed from «بانک سؤالات پیش از خرید **سهم**», but the framework itself
says three of its layers are instrument-invariant: stage 0 (questions to yourself, before
looking at any symbol), and stages 8-10 (position sizing, the sell plan, the mirror).
Those form the shared core; everything between them is per-instrument content.

    resolved = [ core head ] + [ module stages ] + [ core tail ]

Stage numbers are re-sequenced by position after composition, so a module with four
stages still yields a contiguous 0..N rail. Question codes never change, which is what
keeps an already-saved sheet readable after the bank grows. For ``equity`` the
composition is provably the identity — the same eleven stages, the same 115 questions,
the same order — which existing tests pin down.

A module may *tighten* a core question (``replaces``) but never drop one: the sizing
formula is the same arithmetic whether the instrument is a stock or a call option, and
for derivatives it should ask more, not less.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from core.question_bank import bank
from core.question_bank.schema import (
    BANK_VERSION,
    INSTRUMENT_LABELS,
    Evidence,
    InstrumentType,
    Question,
    Stage,
)

#: Stage 0 — the investor, before any symbol is opened.
_CORE_HEAD: tuple[int, ...] = (0,)
#: Stages 8-10 — sizing and the sell plan (written before buying) and the mirror.
_CORE_TAIL: tuple[int, ...] = (8, 9, 10)

CORE_STAGE_IDS = frozenset((*_CORE_HEAD, *_CORE_TAIL))


def _core_stages(ids: tuple[int, ...]) -> tuple[Stage, ...]:
    wanted = set(ids)
    return tuple(s for s in bank.stages() if s.id in wanted)


def _core_questions(stage_id: int) -> tuple[Question, ...]:
    return bank.questions_by_stage(stage_id)


@dataclass(frozen=True)
class InstrumentModule:
    """One instrument class: its own stages, questions, evidence catalogue and wording."""

    key: InstrumentType
    label: str
    stages: tuple[Stage, ...] = ()
    questions: tuple[Question, ...] = ()
    #: Handle → label/source. The resolver implements exactly this set and nothing else.
    evidence: Mapping[str, Evidence] = field(default_factory=lambda: MappingProxyType({}))
    #: Core question code → instrument-worded replacement (e.g. «سقف وزن هر سهم» → «هر واحد»).
    replaces: Mapping[str, Question] = field(default_factory=lambda: MappingProxyType({}))


EQUITY = InstrumentModule(
    key="equity",
    label=INSTRUMENT_LABELS["equity"],
    stages=tuple(s for s in bank.stages() if s.id not in CORE_STAGE_IDS),
    questions=tuple(q for q in bank.questions() if q.stage not in CORE_STAGE_IDS),
    evidence=bank.evidence_by_key(),
)

#: Only the classes with authored questions. A class that is not here must be reported as
#: «this bank does not exist yet» — never rendered with stock questions bolted on.
def _authored() -> dict[InstrumentType, InstrumentModule]:
    """Imported lazily: :mod:`.modules` needs this module's ``InstrumentModule``."""

    from core.question_bank.modules import build_modules

    return build_modules()


MODULES: dict[InstrumentType, InstrumentModule] = {EQUITY.key: EQUITY, **_authored()}

#: Why a class cannot be evaluated even though it can be recognised, stated in data terms
#: rather than as a TODO. The API returns this as ``missingBecause``: the user's framework
#: lists REITs and bonds as instrument classes, and the honest answer for the ones with no
#: table behind them is the missing column, not silence and not a substitute bank.
GAP_REASONS: dict[str, str] = {
    "reit": (
        "REIT در بانک ابزار این برنامه نیست: هیچ جدولی صندوق املاک، نرخ اشغال یا تاریخ ارزیابی "
        "املاک را ذخیره نمی‌کند، پس سؤالات ۱۶۶–۱۷۵ هیچ داده‌ای برای بررسی ندارند."
    ),
    "fixed_income": (
        "اوراق با درآمد ثابت (اخزا/صکوک/گواهی سپرده بانکی) جدولی در برنامه ندارد: تنها چیزی که "
        "هست برچسب «درآمد ثابت» در `funds.fund_type` برای ۹۳ صندوق است — بدون نرخ کوپن، سررسید "
        "یا رتبهٔ اعتباری ناشر، پس شواهد سؤالات ۱۱۶–۱۳۵ اعلام‌شدهٔ نبودِ داده‌اند."
    ),
    "unknown": "نوع ابزار از هیچ جدولی قابل تشخیص نیست؛ کاربر باید نوع را صریحاً انتخاب کند.",
}


class UnknownInstrument(KeyError):
    """No question bank is authored for this instrument class."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


class EvidenceContractError(RuntimeError):
    """A question references an evidence handle the module's catalogue does not define."""


@dataclass(frozen=True)
class ResolvedBank:
    """The bank one sheet is judged against — same surface as :mod:`bank`."""

    instrument_type: InstrumentType
    label: str
    version: str = BANK_VERSION
    _stage_list: tuple[Stage, ...] = field(default=())
    _question_list: tuple[Question, ...] = field(default=())
    _evidence: Mapping[str, Evidence] = field(default_factory=lambda: MappingProxyType({}))

    def stages(self) -> tuple[Stage, ...]:
        return self._stage_list

    def questions(self) -> tuple[Question, ...]:
        return self._question_list

    def questions_by_stage(self, stage_id: int) -> tuple[Question, ...]:
        return tuple(q for q in self._question_list if q.stage == stage_id)

    def question(self, code: str) -> Question | None:
        return next((q for q in self._question_list if q.code == code), None)

    def evidence_by_key(self) -> Mapping[str, Evidence]:
        return self._evidence

    @property
    def golden_codes(self) -> tuple[str, ...]:
        return tuple(q.code for q in self._question_list if q.golden)

    @property
    def stopper_codes(self) -> tuple[str, ...]:
        return tuple(q.code for q in self._question_list if q.stopper)

    @property
    def roles(self) -> frozenset[str]:
        return frozenset(
            inp.role for q in self._question_list for inp in q.inputs if inp.role
        )


def resolve(instrument_type: InstrumentType) -> ResolvedBank:
    """Compose the shared core with one instrument module, re-sequenced into play order."""

    module = MODULES.get(instrument_type)
    if module is None:
        raise UnknownInstrument(instrument_type)

    groups: list[tuple[Stage, tuple[Question, ...]]] = []
    for stage in _core_stages(_CORE_HEAD):
        groups.append((stage, _core_questions(stage.id)))
    for stage in module.stages:
        groups.append((stage, tuple(q for q in module.questions if q.stage == stage.id)))
    for stage in _core_stages(_CORE_TAIL):
        groups.append((stage, _core_questions(stage.id)))

    stage_list: list[Stage] = []
    question_list: list[Question] = []
    for new_id, (stage, questions) in enumerate(groups):
        stage_list.append(replace(stage, id=new_id))
        for original in questions:
            question = module.replaces.get(original.code, original)
            question_list.append(replace(question, stage=new_id))

    evidence = dict(module.evidence)
    missing = sorted(
        {e.key for q in question_list for e in q.evidence} - set(evidence)
    )
    if missing:
        raise EvidenceContractError(
            f"{instrument_type}: questions reference unbound evidence handles: {missing}"
        )

    return ResolvedBank(
        instrument_type=instrument_type,
        label=module.label,
        _stage_list=tuple(stage_list),
        _question_list=tuple(question_list),
        _evidence=MappingProxyType(evidence),
    )


__all__ = [
    "CORE_STAGE_IDS",
    "EQUITY",
    "GAP_REASONS",
    "EvidenceContractError",
    "InstrumentModule",
    "MODULES",
    "ResolvedBank",
    "UnknownInstrument",
    "resolve",
]
