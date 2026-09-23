"""🧭 Pre-buy question bank — content (:mod:`.bank`), contracts (:mod:`.schema`), judgement (:mod:`.engine`).

Kept free of database and HTTP imports so the same engine can guard an API submit, a
background review sweep, and a unit test without any of them.
"""

from __future__ import annotations

from core.question_bank import bank, engine
from core.question_bank.bank import (
    GOLDEN_CODES,
    STOPPER_CODES,
    question,
    questions,
    questions_by_stage,
    stages,
)
from core.question_bank.engine import Evaluation, evaluate
from core.question_bank.schema import (
    BANK_VERSION,
    UNKNOWN,
    Answer,
    Evidence,
    EvidenceValue,
    Input,
    Option,
    Question,
    Stage,
)

__all__ = [
    "BANK_VERSION",
    "GOLDEN_CODES",
    "STOPPER_CODES",
    "Answer",
    "Evaluation",
    "Evidence",
    "EvidenceValue",
    "Input",
    "Option",
    "Question",
    "Stage",
    "UNKNOWN",
    "bank",
    "engine",
    "evaluate",
    "question",
    "questions",
    "questions_by_stage",
    "stages",
]
