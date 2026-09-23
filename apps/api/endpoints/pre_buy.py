"""🧭 Pre-buy decision sheet API (بانک سؤالات پیش از خرید).

Mounted at ``/api/v1/pre-buy``. Everything except ``/catalogue`` and ``/instruments`` is
scoped to the authenticated user; a sheet that is not yours answers 404, never 403 — the
same ownership convention ``saved_filters`` uses.

The verdict is always recomputed server-side from ``core.question_bank.engine``; the client
sends answers and gets a judgement back, so no request body can declare a sheet ``cleared``
on its own. The instrument class is the one thing a client *may* choose, because it is a
statement about what the user is buying — but it is validated against the modelled types and
only ever selects a bank, never a verdict.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db_session
from core.question_bank.registry import MODULES, UnknownInstrument, resolve
from core.question_bank.schema import BANK_VERSION, InstrumentType
from schemas.common.responses import ApiResponse
from services.pre_buy_instrument import (
    InstrumentUndetermined,
    UnknownInstrumentType,
    check_instrument_type,
    instrument_choices,
    normalize_symbol,
)
from services.pre_buy_service import (
    PreBuySheetService,
    bank_evaluate,
    bank_unavailable,
    catalogue,
    evaluation_to_json,
    evidence_from_json,
    evidence_to_json,
    parse_answers,
)

router = APIRouter()

router_tag = "Pre-Buy"


class SheetCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=60, description="نماد بورس/فرابورس/کالا")
    instrument: InstrumentType | None = Field(
        None,
        description="نوع ابزار؛ اگر نیاید از جداول برنامه تشخیص داده می‌شود. "
        "هیچ نوعی با سؤالات سهام جایگزین نمی‌شود.",
    )


class InstrumentIn(BaseModel):
    instrument: InstrumentType = Field(..., description="نوع ابزار این برگه")


class AnswerIn(BaseModel):
    value: str | None = Field(None, description="گزینهٔ انتخابی؛ 'unknown' یعنی نمی‌دانم")
    numbers: dict[str, float] = Field(default_factory=dict, description="مقادیر عددی با کلید id ورودی")
    note: str | None = Field(None, max_length=4000)


class AnswersIn(BaseModel):
    answers: dict[str, AnswerIn | None] = Field(
        default_factory=dict, description="به کلید کد سؤال؛ null یعنی حذف پاسخ"
    )
    refresh_evidence: bool = Field(True, description="شواهد از داده زنده دوباره خوانده شود")


class SubmitIn(BaseModel):
    statement: str | None = Field(None, max_length=2000, description="دلیل خرید در دو جمله")


def _service(session: AsyncSession) -> PreBuySheetService:
    return PreBuySheetService(session=session)


def _unavailable(exc: Exception) -> ApiResponse[dict[str, Any]]:
    """A bank that does not exist is reported as such — never answered with equity's."""

    key = getattr(exc, "key", "?")
    return ApiResponse[dict[str, Any]](
        success=False, error={"code": "BANK_NOT_AUTHORED", "message": bank_unavailable(str(key))}
    )


def _sheet_dict(sheet: Any, evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": sheet.id,
        "symbol": sheet.symbol,
        "instrument_name": sheet.instrument_name,
        "instrument_type": sheet.instrument_type,
        "instrument_basis": sheet.instrument_basis,
        "status": sheet.status,
        "bank_version": sheet.bank_version,
        "verdict": sheet.verdict,
        "completion_pct": sheet.completion_pct,
        "input_hash": sheet.input_hash,
        "answers": sheet.answers,
        "evidence": sheet.evidence,
        "detail": evaluation if evaluation is not None else sheet.detail,
        "updated_at": sheet.updated_at.isoformat() if sheet.updated_at else None,
        "submitted_at": sheet.submitted_at.isoformat() if sheet.submitted_at else None,
        "next_review_at": sheet.next_review_at.isoformat() if sheet.next_review_at else None,
    }


@router.get(
    "/instruments",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="انواع ابزار و اینکه کدام‌شان بانک سؤال دارد",
)
async def get_instruments() -> ApiResponse[list[dict[str, Any]]]:
    """Types the platform can recognise, with ``hasBank`` saying whether one exists to judge them.

    A type with ``hasBank: false`` is a declared gap, not a hidden one: the UI shows it as
    «بانک این ابزار هنوز نوشته نشده» instead of falling back to the stock questions.
    """

    return ApiResponse[list[dict[str, Any]]](success=True, data=instrument_choices())


@router.get(
    "/catalogue",
    response_model=ApiResponse[dict[str, Any]],
    summary="پرسش‌نامهٔ یک نوع ابزار (پیش‌فرض: سهام — ۱۱ مرحله، ۱۱۵ سؤال، ۱۵ شرط ★)",
)
async def get_catalogue(
    instrument: str = Query("equity", description="نوع ابزار"),
) -> ApiResponse[dict[str, Any]]:
    """Static content + version. Cached hard by the client; answers store this version."""

    try:
        kind = check_instrument_type(instrument)
        return ApiResponse[dict[str, Any]](success=True, data=catalogue(kind or "equity"))
    except UnknownInstrument as exc:
        return _unavailable(exc)
    except UnknownInstrumentType as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get(
    "/resolve/{symbol}",
    response_model=ApiResponse[dict[str, Any]],
    summary="تشخیص نوع ابزار یک نماد از جداول برنامه",
)
async def resolve_instrument(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
    _: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    name = normalize_symbol(symbol)
    decided = await _service(session).classify(name)
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "symbol": name,
            **decided.as_dict(),
            "authoredTypes": sorted(MODULES),
            "message": None if decided.evidenced else bank_unavailable("unknown"),
        },
    )


@router.get(
    "/evidence/{symbol}",
    response_model=ApiResponse[dict[str, Any]],
    summary="شواهد زنده یک نماد، بدون ساخت برگه",
)
async def get_evidence(
    symbol: str,
    instrument: str = Query("equity", description="نوع ابزار"),
    session: AsyncSession = Depends(get_db_session),
    _: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    svc = _service(session)
    name = normalize_symbol(symbol)
    try:
        kind = check_instrument_type(instrument) or "equity"
        rb = resolve(kind)
    except UnknownInstrument as exc:
        return _unavailable(exc)
    except UnknownInstrumentType as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})
    evidence = await svc.evidence.resolve(name, rb.evidence_by_key())
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "symbol": name,
            "instrument": kind,
            "evidence": evidence_to_json(evidence),
            "bank_version": BANK_VERSION,
        },
    )


@router.get("/sheets", response_model=ApiResponse[list[dict[str, Any]]], summary="برگه‌های من")
async def list_sheets(
    status: str | None = Query(None, description="DRAFT | SUBMITTED | ABANDONED"),
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[list[dict[str, Any]]]:
    rows = await _service(session).list_for_user(current_user["sub"])
    data = [_sheet_dict(r) for r in rows if status is None or r.status == status]
    return ApiResponse[list[dict[str, Any]]](success=True, data=data)


@router.post("/sheets", response_model=ApiResponse[dict[str, Any]], summary="ساخت/بازکردن برگه یک نماد")
async def open_sheet(
    body: SheetCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    svc = _service(session)
    try:
        sheet, created = await svc.get_or_create(
            current_user["sub"], body.symbol, instrument_type=body.instrument
        )
    except InstrumentUndetermined as exc:
        return ApiResponse[dict[str, Any]](
            success=False, error={"code": "INSTRUMENT_UNDETERMINED", "message": str(exc)}
        )
    except UnknownInstrument as exc:
        return _unavailable(exc)
    except UnknownInstrumentType as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})
    return ApiResponse[dict[str, Any]](success=True, data={**_sheet_dict(sheet), "created": created})


async def _owned(sheet_id: int, session: AsyncSession, current_user: dict) -> Any:
    sheet = await _service(session).owned(current_user["sub"], sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Sheet not found")
    return sheet


@router.get("/sheets/{sheet_id}", response_model=ApiResponse[dict[str, Any]], summary="یک برگه")
async def get_sheet(
    sheet_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse[dict[str, Any]](success=True, data=_sheet_dict(await _owned(sheet_id, session, current_user)))


@router.put("/sheets/{sheet_id}/answers", response_model=ApiResponse[dict[str, Any]], summary="ثبت پاسخ‌ها")
async def save_answers(
    sheet_id: int,
    body: AnswersIn,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    svc = _service(session)
    sheet = await _owned(sheet_id, session, current_user)
    if sheet.status != "DRAFT":
        return ApiResponse[dict[str, Any]](
            success=False, error={"message": "برگهٔ ثبت‌شده قابل ویرایش نیست؛ آن را دوباره باز کنید."}
        )
    payload = {code: (item.model_dump() if item else None) for code, item in body.answers.items()}
    try:
        _, evaluation, _evidence = await svc.save(sheet, payload, refresh_evidence=body.refresh_evidence)
    except UnknownInstrument as exc:
        return _unavailable(exc)
    except ValueError as exc:
        # The service re-checks the draft rule because it is the only writer; a client that
        # raced a submit gets the domain error rather than a 500.
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})
    return ApiResponse[dict[str, Any]](
        success=True,
        data={"sheet": _sheet_dict(sheet, evaluation_to_json(evaluation)), "evaluation": evaluation_to_json(evaluation)},
    )


@router.post(
    "/sheets/{sheet_id}/instrument",
    response_model=ApiResponse[dict[str, Any]],
    summary="تغییر نوع ابزار یک پیش‌نویس",
)
async def set_instrument(
    sheet_id: int,
    body: InstrumentIn,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    """Use it when the automatic classification is wrong or a bank is not authored for it.

    Only a draft may change: a submitted review records what was judged, and rewriting its
    instrument would rewrite that history. Answers that the new bank does not contain stay
    in the row and are reported, so switching type never silently discards work.
    """

    svc = _service(session)
    sheet = await _owned(sheet_id, session, current_user)
    try:
        changed, dropped = await svc.set_instrument(sheet, body.instrument)
    except UnknownInstrument as exc:
        return _unavailable(exc)
    except ValueError as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})
    return ApiResponse[dict[str, Any]](
        success=True,
        data={**_sheet_dict(changed), "ignoredAnswers": dropped},
    )


@router.post("/sheets/{sheet_id}/evaluate", response_model=ApiResponse[dict[str, Any]], summary="قضاوت بدون ذخیره")
async def evaluate_sheet(
    sheet_id: int,
    body: AnswersIn,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    """What-if: judge a candidate answer set without touching the stored draft."""

    svc = _service(session)
    sheet = await _owned(sheet_id, session, current_user)
    try:
        rb = svc.bank_for(sheet)
    except UnknownInstrument as exc:
        return _unavailable(exc)
    evidence = (
        await svc.evidence.resolve(sheet.symbol, rb.evidence_by_key())
        if body.refresh_evidence
        else evidence_from_json(sheet.evidence)
    )
    answers = parse_answers(sheet.answers)
    incoming = {c: (i.model_dump() if i else None) for c, i in body.answers.items()}
    # An explicit null removes the answer — mirrors the PUT contract so what-if and save
    # behave identically.
    for code, item in incoming.items():
        if item is None:
            answers.pop(code, None)
        else:
            answers.update(parse_answers({code: item}))
    evaluation = bank_evaluate(answers, evidence, rb)
    return ApiResponse[dict[str, Any]](success=True, data=evaluation_to_json(evaluation))


@router.post("/sheets/{sheet_id}/submit", response_model=ApiResponse[dict[str, Any]], summary="ثبت و بایگانی برگه")
async def submit_sheet(
    sheet_id: int,
    body: SubmitIn,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    svc = _service(session)
    sheet = await _owned(sheet_id, session, current_user)
    if sheet.verdict == "not_started":
        return ApiResponse[dict[str, Any]](
            success=False, error={"message": "برگه هنوز هیچ پاسخی ندارد؛ ثبت بایگانی معنادار نیست."}
        )
    try:
        review = await svc.submit(sheet, body.statement)
    except ValueError as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "review_id": review.id,
            "instrument_type": sheet.instrument_type,
            "verdict": sheet.verdict,
            "input_hash": sheet.input_hash,
            "completion_pct": sheet.completion_pct,
        },
    )


@router.post("/sheets/{sheet_id}/reopen", response_model=ApiResponse[dict[str, Any]], summary="بازگشت برگه به پیش‌نویس")
async def reopen_sheet(
    sheet_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    svc = _service(session)
    sheet = await _owned(sheet_id, session, current_user)
    await svc.reopen(sheet)
    return ApiResponse[dict[str, Any]](success=True, data=_sheet_dict(sheet))


@router.get("/sheets/{sheet_id}/reviews", response_model=ApiResponse[list[dict[str, Any]]], summary="تاریخچهٔ ثبت‌ها")
async def sheet_reviews(
    sheet_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[list[dict[str, Any]]]:
    await _owned(sheet_id, session, current_user)
    rows = await _service(session).list_reviews(current_user["sub"], sheet_id)
    return ApiResponse[list[dict[str, Any]]](
        success=True,
        data=[
            {
                "id": r.id, "symbol": r.symbol, "verdict": r.verdict,
                "instrument_type": r.instrument_type,
                "completion_pct": r.completion_pct, "input_hash": r.input_hash,
                "bank_version": r.bank_version, "statement": r.statement,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    )


@router.get("/sheets/{sheet_id}/export", response_model=ApiResponse[dict[str, Any]], summary="برگهٔ تصمیم قابل‌چاپ")
async def export_sheet(
    sheet_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    """Everything needed to print the A4 decision sheet, resolved by question code."""

    sheet = await _owned(sheet_id, session, current_user)
    answers = parse_answers(sheet.answers)
    stored = evidence_from_json(sheet.evidence)
    try:
        rb = _service(session).bank_for(sheet)
    except UnknownInstrument as exc:
        return _unavailable(exc)
    bank_qmap = {q.code: q for q in rb.questions()}
    # Answers left over from another instrument bank (the sheet changed type) are not part of
    # this printout, so name them instead of letting a signed sheet look complete.
    orphans = sorted(set(answers) - set(bank_qmap))

    def _ev(item: Any) -> dict[str, Any]:
        resolved = stored.get(item.key)
        return {
            "key": item.key, "label": item.label, "source": item.source, "unit": item.unit,
            "value": resolved.value if resolved else None,
            "status": resolved.status if resolved else "missing",
            "asOf": resolved.as_of if resolved else None,
            "declared": resolved.declared if resolved else False,
            "note": resolved.note if resolved else "برای این برگه ثبت نشده است.",
        }

    rows = [
        {
            "code": code,
            "stage": question.stage,
            "text": question.text,
            "stopper": question.stopper,
            "answer": answers[code].value if code in answers else None,
            "numbers": answers[code].numbers if code in answers else {},
            "note": answers[code].note if code in answers else None,
            "evidence": [_ev(e) for e in question.evidence],
        }
        for code, question in bank_qmap.items()
    ]
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "symbol": sheet.symbol,
            "instrument_name": sheet.instrument_name,
            "instrument_type": sheet.instrument_type,
            "instrument_label": rb.label,
            "instrument_basis": sheet.instrument_basis,
            "bank_version": sheet.bank_version,
            "verdict": sheet.verdict,
            "detail": sheet.detail,
            "input_hash": sheet.input_hash,
            "submitted_at": sheet.submitted_at.isoformat() if sheet.submitted_at else None,
            "orphanAnswerCodes": orphans,
            "rows": rows,
        },
    )


@router.get("/meta", response_model=ApiResponse[dict[str, Any]], summary="شمارش‌های بانک هر نوع ابزار")
async def meta() -> ApiResponse[dict[str, Any]]:
    equity = resolve("equity")
    counts = []
    for key, module in MODULES.items():
        rb = resolve(key)
        counts.append(
            {
                "key": key,
                "label": module.label,
                "stages": len(rb.stages()),
                "questions": len(rb.questions()),
                "stoppers": len(rb.stopper_codes),
                "golden": len(rb.golden_codes),
                "per_stage": [len(rb.questions_by_stage(s.id)) for s in rb.stages()],
            }
        )
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "bank_version": BANK_VERSION,
            # The stock bank is the document contract (۱۱/۱۱۵/۱۵★/۵), so its counts stay at
            # the top level; the instrument axis is additive below it.
            "stages": len(equity.stages()),
            "questions": len(equity.questions()),
            "stoppers": len(equity.stopper_codes),
            "golden": len(equity.golden_codes),
            "per_stage": [len(equity.questions_by_stage(s.id)) for s in equity.stages()],
            "instruments": counts,
            "unauthored": [t["key"] for t in instrument_choices() if not t["hasBank"]],
        },
    )
