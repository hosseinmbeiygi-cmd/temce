"""🧾 Pre-buy decision-sheet service — the only place a sheet is written.

Owns the whole lifecycle: instrument → draft → answers → evidence → verdict → immutable review.

Three invariants the router depends on and the unit tests pin down:

* **The verdict is never accepted from the client.** Callers send answers; the verdict is
  recomputed from ``core.question_bank.engine`` every time, so a tampered client cannot
  mark its own sheet ``cleared``.
* **Evidence is frozen with the verdict.** What the user saw while answering is stored
  next to what they answered, which is the whole point of keeping reviews append-only.
* **A sheet is judged by the bank of its own instrument class.** ``instrument_type`` picks
  the resolved bank; a class with no authored questions is a refusal, not a fallback to the
  stock bank — answering «آیا سهم بنیاد قوی دارد؟» for a futures contract would be a fabricated
  analysis of the very kind the platform forbids.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.question_bank.engine import Evaluation
from core.question_bank.registry import ResolvedBank, resolve
from core.question_bank.schema import (
    BANK_VERSION,
    INSTRUMENT_LABELS,
    Answer,
    EvidenceValue,
    InstrumentType,
)
from models.pre_buy import PreBuyReview, PreBuySheet
from services.pre_buy_evidence import PreBuyEvidenceService
from services.pre_buy_instrument import (
    Classification,
    InstrumentUndetermined,
    classify,
    normalize_symbol,
)


def bank_unavailable(instrument: str) -> str:
    """The Persian reason a sheet cannot be judged, for a class with no authored bank."""

    label = INSTRUMENT_LABELS.get(instrument, instrument)
    return (
        f"بانک سؤالات «{label}» هنوز در برنامه نوشته نشده است. "
        "برگه را با سؤالات سهام پر نمی‌کنیم؛ نوع ابزار را عوض کنید یا صبر کنید تا این ماژول افزوده شود."
    )


#: Domain errors surfaced to the client as `success:false`, so they speak the user's language.
READ_ONLY = "برگهٔ ثبت‌شده قابل ویرایش نیست؛ پیش از تغییر آن را دوباره باز کنید (read-only)."
ALREADY_ARCHIVED = "این برگه پیش‌تر بایگانی شده است؛ برای پاسخ دوباره آن را باز کنید."


def question_to_dict(q: Any) -> dict[str, Any]:
    return {
        "code": q.code,
        "stage": q.stage,
        "text": q.text,
        "kind": q.kind,
        "stopper": q.stopper,
        "hint": q.hint,
        "unit": q.unit,
        "noteRequired": q.note_required,
        "golden": q.golden,
        "vetoValues": list(q.veto_values),
        "options": [{"id": o.id, "label": o.label, "veto": o.veto} for o in q.options],
        "inputs": [
            {"id": i.id, "label": i.label, "unit": i.unit, "role": i.role, "min": i.min, "max": i.max}
            for i in q.inputs
        ],
        "evidence": [
            {"key": e.key, "label": e.label, "source": e.source, "unit": e.unit} for e in q.evidence
        ],
    }


def stage_to_dict(s: Any) -> dict[str, Any]:
    return {"id": s.id, "key": s.key, "title": s.title, "purpose": s.purpose, "rule": s.rule}


def catalogue(instrument: InstrumentType = "equity") -> dict[str, Any]:
    """The bank for one instrument class, for the UI to render and mirror the gate locally.

    Raises :class:`UnknownInstrument` for a class with no authored module — the router turns
    that into a domain error rather than serving the stock questions under a fund's name.
    """

    rb = resolve(instrument)
    questions = rb.questions()
    return {
        "bankVersion": rb.version,
        "instrument": rb.instrument_type,
        "instrumentLabel": rb.label,
        "stages": [stage_to_dict(s) for s in rb.stages()],
        "questions": [question_to_dict(q) for q in questions],
        "goldenCodes": list(rb.golden_codes),
        "stopperCodes": list(rb.stopper_codes),
        "total": len(questions),
    }


def parse_answers(raw: dict[str, Any] | None) -> dict[str, Answer]:
    out: dict[str, Answer] = {}
    for code, item in (raw or {}).items():
        if not isinstance(item, dict):
            continue
        numbers = item.get("numbers") or {}
        clean = {k: float(v) for k, v in numbers.items() if isinstance(v, (int, float))}
        value = item.get("value")
        out[code] = Answer(
            code=code,
            value=str(value) if value not in (None, "") else None,
            numbers=clean,
            note=item.get("note"),
            answered_at=item.get("answeredAt"),
        )
    return out


def answers_to_json(answers: dict[str, Answer]) -> dict[str, Any]:
    return {
        code: {
            "value": a.value,
            "numbers": a.numbers,
            "note": a.note,
            "answeredAt": a.answered_at,
        }
        for code, a in answers.items()
    }


def evidence_to_json(evidence: dict[str, EvidenceValue]) -> dict[str, Any]:
    return {
        key: {
            "value": e.value, "unit": e.unit, "source": e.source, "label": e.label,
            "asOf": e.as_of, "status": e.status, "note": e.note, "declared": e.declared,
        }
        for key, e in evidence.items()
    }


def evidence_from_json(raw: dict[str, Any] | None) -> dict[str, EvidenceValue]:
    out: dict[str, EvidenceValue] = {}
    for key, item in (raw or {}).items():
        if not isinstance(item, dict):
            continue
        out[key] = EvidenceValue(
            key=key, label=str(item.get("label") or key), source=str(item.get("source") or ""),
            unit=str(item.get("unit") or ""), value=item.get("value"), as_of=item.get("asOf"),
            status="available" if item.get("status") == "available" else "missing",
            note=str(item.get("note") or ""), declared=bool(item.get("declared")),
        )
    return out


def evaluation_to_json(ev: Evaluation) -> dict[str, Any]:
    return {
        "verdict": ev.verdict,
        "verdictLabel": ev.verdict_label,
        "canBuy": ev.can_buy,
        "completionPct": ev.completion_pct,
        "answered": ev.answered,
        "total": ev.total,
        "unlockedStage": ev.unlocked_stage,
        "vetoes": [{"code": v.code, "text": v.text, "answer": v.answer_label} for v in ev.vetoes],
        "unknowns": list(ev.unknowns),
        "stopperGaps": list(ev.stopper_gaps),
        "missingNotes": list(ev.missing_notes),
        "weakEvidence": list(ev.weak_evidence),
        "blockingReasons": list(ev.blocking_reasons),
        "golden": [
            {"code": g.code, "text": g.text, "answered": g.answered,
             "blocking": g.blocking, "answer": g.answer_label}
            for g in ev.golden
        ],
        "derived": [
            {"key": d.key, "label": d.label, "value": d.value, "unit": d.unit,
             "formula": d.formula, "available": d.available, "note": d.note}
            for d in ev.derived
        ],
        "stages": [
            {"id": r.stage.id, "key": r.stage.key, "title": r.stage.title, "rule": r.stage.rule,
             "total": r.total, "answered": r.answered, "complete": r.complete, "locked": r.locked,
             "status": r.status, "progressPct": r.progress_pct, "missing": list(r.missing),
             "unknowns": list(r.unknowns), "vetoed": list(r.vetoed), "missingNotes": list(r.missing_notes)}
            for r in ev.stages
        ],
    }


def _input_hash(
    instrument_type: str, answers: dict[str, Answer], evidence: dict[str, EvidenceValue]
) -> str:
    """sha256 over (instrument, bank, answers, evidence).

    The instrument is in the payload because the same answer dict under two banks is two
    different claims — without it, an equity sheet and a fund sheet could carry the same
    ``input_hash`` and the review index would tie them together.
    """

    payload = json.dumps(
        {
            "instrument": instrument_type,
            "bank": BANK_VERSION,
            "answers": answers_to_json(answers),
            "evidence": {k: v.value for k, v in sorted(evidence.items())},
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _next_review_at(answers: dict[str, Answer], now: datetime) -> datetime | None:
    days = next((a.numbers.get("review_days") for a in answers.values() if a.numbers.get("review_days")), None)
    return now + timedelta(days=float(days)) if days else None


class PreBuySheetService:
    """Draft + review persistence for one user."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.evidence = PreBuyEvidenceService(session=session)

    async def classify(self, symbol: str) -> Classification:
        """What the stored tables say a symbol is — without creating anything."""

        return await classify(self.session, normalize_symbol(symbol))

    @staticmethod
    def bank_for(sheet: PreBuySheet) -> ResolvedBank:
        """The bank this sheet is judged against. Raises ``UnknownInstrument`` if none exists.

        ``instrument_type`` is NOT NULL with an 'equity' default in the database, so an
        instance that has not been flushed yet is the only way it can read back empty —
        equity is what such an object was before this column existed.
        """

        return resolve(sheet.instrument_type or "equity")  # type: ignore[arg-type]

    async def get_or_create(
        self,
        user_id: str,
        symbol: str,
        *,
        instrument_type: InstrumentType | None = None,
    ) -> tuple[PreBuySheet, bool]:
        """The open draft for ``symbol``, created (unfilled) if none exists.

        ``instrument_type`` is the user's own choice and wins; without it the symbol is
        classified from the database, and a symbol no table recognises raises rather than
        defaulting to equity.
        """

        symbol = normalize_symbol(symbol)
        row = (
            await self.session.execute(
                select(PreBuySheet)
                .where(PreBuySheet.user_id == user_id, PreBuySheet.symbol == symbol,
                       PreBuySheet.status == "DRAFT")
                .order_by(PreBuySheet.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is not None:
            return row, False

        if instrument_type is not None:
            kind = instrument_type
            basis = f"انتخاب کاربر ({INSTRUMENT_LABELS.get(kind, kind)})"
        else:
            decided = await self.classify(symbol)
            if not decided.evidenced:
                raise InstrumentUndetermined(symbol)
            kind = decided.instrument_type
            basis = decided.basis

        rb = resolve(kind)
        evidence = await self.evidence.resolve(symbol, rb.evidence_by_key())
        name = evidence.get("detail.name")
        row = PreBuySheet(
            user_id=user_id, symbol=symbol, bank_version=BANK_VERSION, status="DRAFT",
            answers={}, evidence=evidence_to_json(evidence),
            detail=evaluation_to_json(bank_evaluate({}, {}, rb)),
            verdict="not_started", completion_pct=0, input_hash=_input_hash(kind, {}, evidence),
            instrument_type=kind, instrument_basis=basis[:240],
            instrument_name=str(name.value) if name and name.value else None,
            updated_at=datetime.utcnow(),
        )
        self.session.add(row)
        await self.session.flush()
        return row, True

    async def set_instrument(
        self, sheet: PreBuySheet, instrument_type: InstrumentType, *, now: datetime | None = None
    ) -> tuple[PreBuySheet, int]:
        """Re-point a draft at another instrument bank, returning how many answers stop applying.

        Only a draft can change type: a submitted review is a record of what was judged, and
        rewriting its instrument would rewrite history. Answers from the previous bank are
        kept in the row but ignored by the engine (unknown codes are dropped), which is why
        the count of them is returned instead of silently dropping them.
        """

        if sheet.status != "DRAFT":
            raise ValueError(READ_ONLY)
        rb = resolve(instrument_type)
        known = {q.code for q in rb.questions()}
        kept = parse_answers(sheet.answers)
        dropped = sum(1 for code in kept if code not in known)

        sheet.instrument_type = instrument_type
        sheet.instrument_basis = f"انتخاب کاربر ({INSTRUMENT_LABELS.get(instrument_type, instrument_type)})"[:240]
        evidence = await self.evidence.resolve(sheet.symbol, rb.evidence_by_key())
        sheet.evidence = evidence_to_json(evidence)
        evaluation = bank_evaluate({c: a for c, a in kept.items() if c in known}, evidence, rb)
        sheet.detail = evaluation_to_json(evaluation)
        sheet.verdict = evaluation.verdict
        sheet.completion_pct = evaluation.completion_pct
        sheet.input_hash = _input_hash(instrument_type, kept, evidence)
        sheet.updated_at = now or datetime.utcnow()
        await self.session.flush()
        return sheet, dropped

    async def owned(self, user_id: str, sheet_id: int) -> PreBuySheet | None:
        return (
            await self.session.execute(
                select(PreBuySheet).where(PreBuySheet.id == sheet_id, PreBuySheet.user_id == user_id)
            )
        ).scalar_one_or_none()

    async def save(
        self,
        sheet: PreBuySheet,
        answers: dict[str, Any] | None,
        *,
        refresh_evidence: bool,
        now: datetime | None = None,
    ) -> tuple[PreBuySheet, Evaluation, dict[str, EvidenceValue]]:
        """Merge answers, re-resolve evidence if asked, recompute the verdict.

        Unknown codes and codes outside the bank are dropped here, which is what keeps an
        old draft readable after the bank changes.
        """

        now = now or datetime.utcnow()
        if sheet.status != "DRAFT":
            raise ValueError(READ_ONLY)
        rb = self.bank_for(sheet)
        known = {q.code for q in rb.questions()}
        merged = parse_answers(sheet.answers)
        for code, item in (answers or {}).items():
            if code not in known:
                continue
            if item is None:
                merged.pop(code, None)
                continue
            parsed = parse_answers({code: item}).get(code)
            if parsed is not None:
                # `Answer` is frozen: the stamp is a new value, not an assignment.
                merged[code] = replace(parsed, answered_at=now.isoformat(timespec="seconds"))

        evidence = (
            await self.evidence.resolve(sheet.symbol, rb.evidence_by_key())
            if refresh_evidence
            else evidence_from_json(sheet.evidence)
        )
        evaluation = bank_evaluate(merged, evidence, rb)

        sheet.answers = answers_to_json(merged)
        sheet.evidence = evidence_to_json(evidence)
        sheet.detail = evaluation_to_json(evaluation)
        sheet.verdict = evaluation.verdict
        sheet.completion_pct = evaluation.completion_pct
        sheet.input_hash = _input_hash(sheet.instrument_type, merged, evidence)
        sheet.updated_at = now
        if evaluation.verdict != "not_started":
            sheet.next_review_at = _next_review_at(merged, now)
        name = evidence.get("detail.name")
        if name and name.value:
            sheet.instrument_name = str(name.value)
        await self.session.flush()
        return sheet, evaluation, evidence

    async def submit(self, sheet: PreBuySheet, statement: str | None) -> PreBuyReview:
        """Freeze the current answers + evidence into an append-only review row."""

        now = datetime.utcnow()
        if sheet.status == "SUBMITTED":
            raise ValueError(ALREADY_ARCHIVED)
        review = PreBuyReview(
            sheet_id=sheet.id, user_id=sheet.user_id, symbol=sheet.symbol,
            instrument_type=sheet.instrument_type,
            bank_version=BANK_VERSION, answers=dict(sheet.answers), evidence=dict(sheet.evidence),
            detail=dict(sheet.detail or {}), verdict=sheet.verdict,
            completion_pct=sheet.completion_pct, input_hash=sheet.input_hash or "",
            statement=statement,
        )
        self.session.add(review)
        sheet.status = "SUBMITTED"
        sheet.submitted_at = now
        sheet.updated_at = now
        await self.session.flush()
        return review

    async def reopen(self, sheet: PreBuySheet) -> PreBuySheet:
        """Put a submitted sheet back into draft (e.g. after a new quarterly report)."""

        sheet.status = "DRAFT"
        sheet.submitted_at = None
        sheet.updated_at = datetime.utcnow()
        await self.session.flush()
        return sheet

    async def list_for_user(self, user_id: str) -> list[PreBuySheet]:
        rows = (
            await self.session.execute(
                select(PreBuySheet)
                .where(PreBuySheet.user_id == user_id)
                .order_by(PreBuySheet.updated_at.desc().nullslast())
                .limit(200)
            )
        ).scalars().all()
        return list(rows)

    async def list_reviews(self, user_id: str, sheet_id: int) -> list[PreBuyReview]:
        rows = (
            await self.session.execute(
                select(PreBuyReview)
                .where(PreBuyReview.user_id == user_id, PreBuyReview.sheet_id == sheet_id)
                .order_by(PreBuyReview.created_at.desc())
            )
        ).scalars().all()
        return list(rows)


def bank_evaluate(
    answers: dict[str, Answer],
    evidence: dict[str, EvidenceValue],
    rb: ResolvedBank | None = None,
) -> Evaluation:
    """Thin indirection so tests can monkeypatch the engine in one place."""

    from core.question_bank.engine import evaluate

    return evaluate(answers, evidence, rb)


__all__ = [
    "PreBuySheetService",
    "bank_evaluate",
    "bank_unavailable",
    "catalogue",
    "evaluation_to_json",
    "evidence_from_json",
    "evidence_to_json",
    "parse_answers",
    "answers_to_json",
    "question_to_dict",
    "stage_to_dict",
]
