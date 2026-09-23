"""⚖️ Gate engine for the pre-buy decision sheet.

Pure functions over :mod:`core.question_bank.bank` plus a dict of answers. No database,
no HTTP, no clock — the whole point is that the same answers always produce the same
verdict, so a sheet submitted last year can be re-evaluated today and audited.

Two rules come straight from the framework and are non-negotiable here:

* **Only ★ questions reject.** A negative answer to a normal question is recorded and
  shown, but never vetoes — the document reserves «رد یا تعلیق» for the starred ones.
* **«نمی‌دانم» is a real answer that blocks.** It suspends (تعلیق) rather than rejects,
  and it keeps its stage from completing, which is what stops the next stage opening.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.question_bank.registry import ResolvedBank, resolve
from core.question_bank.schema import (
    UNKNOWN,
    Answer,
    EvidenceValue,
    Question,
    Stage,
    StageStatus,
    Verdict,
)

VERDICT_LABELS: dict[Verdict, str] = {
    "not_started": "شروع نشده",
    "in_progress": "در حال تکمیل",
    "blocked_unknown": "معلق — «نمی‌دانم» ثبت شده",
    "hold": "معلق — شرط ستاره‌ای تکمیل نشده",
    "vetoed": "نخرید (رد)",
    "cleared": "تحلیل کامل شد — خرید مجاز مشروط به طرح فروش",
}

@dataclass(frozen=True)
class Veto:
    """A ★ question whose answer rejects the analysis."""

    code: str
    text: str
    answer_label: str
    stage: int


@dataclass(frozen=True)
class DerivedValue:
    """A figure the engine computes from recorded answers.

    ``available`` is False with a populated ``note`` whenever an input is missing or the
    maths is undefined — a derived number is never guessed into existence.
    """

    key: str
    label: str
    unit: str = ""
    value: float | None = None
    formula: str = ""
    available: bool = False
    note: str = ""


@dataclass(frozen=True)
class StageResult:
    stage: Stage
    total: int
    answered: int
    complete: bool
    locked: bool
    status: StageStatus
    missing: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    vetoed: tuple[str, ...] = ()
    missing_notes: tuple[str, ...] = ()
    #: ★ questions of this stage that are unanswered or «نمی‌دانم».
    stopper_gaps: tuple[str, ...] = ()

    @property
    def progress_pct(self) -> int:
        return round(self.answered / self.total * 100) if self.total else 0


@dataclass(frozen=True)
class GoldenResult:
    code: str
    text: str
    answered: bool
    blocking: bool
    answer_label: str = ""


@dataclass(frozen=True)
class Evaluation:
    """The full verdict for one sheet."""

    verdict: Verdict
    total: int
    answered: int
    completion_pct: int
    unlocked_stage: int
    stages: tuple[StageResult, ...] = ()
    vetoes: tuple[Veto, ...] = ()
    unknowns: tuple[str, ...] = ()
    stopper_gaps: tuple[str, ...] = ()
    missing_notes: tuple[str, ...] = ()
    weak_evidence: tuple[str, ...] = ()
    golden: tuple[GoldenResult, ...] = ()
    derived: tuple[DerivedValue, ...] = ()
    blocking_reasons: tuple[str, ...] = ()

    @property
    def verdict_label(self) -> str:
        return VERDICT_LABELS[self.verdict]

    @property
    def can_buy(self) -> bool:
        """Only a cleared sheet authorises a buy — and nothing else softens that."""
        return self.verdict == "cleared"

    @property
    def open_questions(self) -> tuple[str, ...]:
        return tuple(sorted({*self.stopper_gaps, *self.missing_notes, *self.unknowns}))

    def derived_map(self) -> dict[str, DerivedValue]:
        return {d.key: d for d in self.derived}


def _label_for(question: Question, answer: Answer) -> str:
    if answer.value is None:
        return "—"
    if answer.value == UNKNOWN:
        return "نمی‌دانم"
    for option in question.options:
        if option.id == answer.value:
            return option.label
    return answer.value


def _is_veto(question: Question, answer: Answer) -> bool:
    if not question.stopper or answer.value is None or answer.value == UNKNOWN:
        return False
    return answer.value in question.veto_values or answer.value in question.veto_options()


def _needs_written_note(question: Question, answer: Answer) -> bool:
    if question.kind == "text":
        return False
    return question.note_required and not (answer.note or "").strip()


def _number(rb: ResolvedBank, answers: dict[str, Answer], role: str) -> float | None:
    """First recorded answer exposing ``role`` — roles are declared in the bank."""
    for question in rb.questions():
        answer = answers.get(question.code)
        if answer is None:
            continue
        for inp in question.inputs:
            if inp.role == role:
                value = answer.numbers.get(inp.id)
                if value is not None:
                    return float(value)
    return None


def _dv(
    key: str,
    label: str,
    value: float | None,
    *,
    unit: str = "",
    formula: str,
    note: str = "",
) -> DerivedValue:
    ok = value is not None
    return DerivedValue(
        key=key, label=label, unit=unit, value=value, formula=formula,
        available=ok, note="" if ok else (note or "ورودی کافی ثبت نشده"),
    )


def _derive(
    rb: ResolvedBank, answers: dict[str, Answer], evidence: dict[str, EvidenceValue]
) -> tuple[DerivedValue, ...]:
    """Position sizing, R:R and the weight/sizing conflict — the framework's arithmetic.

    Stage 8 asks «طبق فرمول (زیان مجاز ÷ فاصله تا حد خروج) اندازه موقعیت چقدر می‌شود؟»; the
    formula is evaluated here rather than trusted to the user's own number, and both are
    shown side by side.
    """
    max_loss = _number(rb, answers, "max_loss_toman")
    drawdown_pct = _number(rb, answers, "max_drawdown_pct")
    entry = _number(rb, answers, "entry_price")
    stop = _number(rb, answers, "stop_price")
    target = _number(rb, answers, "target_price")
    weight_cap = _number(rb, answers, "weight_cap_pct")
    user_size = _number(rb, answers, "position_size_toman")

    implied_portfolio = None
    if max_loss is not None and drawdown_pct:
        implied_portfolio = max_loss / (drawdown_pct / 100)

    stop_distance_pct = None
    stop_note = ""
    if entry and stop is not None:
        if stop >= entry:
            stop_note = "حد ابطال نباید بالاتر از قیمت ورود باشد"
        else:
            stop_distance_pct = (entry - stop) / entry * 100

    rr_ratio = None
    rr_note = ""
    if entry and stop is not None and target is not None and stop < entry:
        risk = entry - stop
        reward = target - entry
        if reward <= 0:
            rr_note = "قیمت هدف باید بالای ورود باشد"
        else:
            rr_ratio = reward / risk

    formula_size = None
    formula_note = ""
    if max_loss is not None and stop_distance_pct:
        formula_size = max_loss / (stop_distance_pct / 100)
    elif max_loss is not None:
        formula_note = "برای محاسبه اندازه، قیمت ورود و حد ابطال لازم است"

    applied_size = user_size if user_size is not None else formula_size
    weight_pct = None
    weight_note = ""
    if applied_size is not None and implied_portfolio:
        weight_pct = applied_size / implied_portfolio * 100
    elif applied_size is not None:
        weight_note = "برای درصد وزن، سقف افت سبد (٪) لازم است"

    weight_conflict = None
    conflict_note = ""
    if weight_pct is not None and weight_cap is not None:
        weight_conflict = 1.0 if weight_pct > weight_cap else 0.0
    elif weight_pct is not None:
        conflict_note = "سقف وزن سهم ثبت نشده تا مقایسه ممکن شود"

    size_gap_pct = None
    gap_note = ""
    if user_size is not None and formula_size:
        size_gap_pct = (user_size - formula_size) / formula_size * 100
    else:
        gap_note = "هم اندازهٔ دستی و هم ورودی حد ابطال لازم است"

    daily_value = evidence.get("detail.trade_value")
    exit_days = None
    exit_note = ""
    if daily_value is not None and daily_value.value and applied_size is not None:
        dv = float(daily_value.value)
        if dv > 0:
            exit_days = applied_size / dv
        else:
            exit_note = "ارزش معاملات امروز صفر است"
    else:
        exit_note = "ارزش معاملات در دسترس نیست"

    price = evidence.get("detail.price_last")
    value_low = _number(rb, answers, "value_low")
    mos_from_range = None
    mos_note = ""
    if price is not None and price.value and value_low:
        pv = float(price.value)
        if pv > 0:
            mos_from_range = (value_low - pv) / pv * 100
    else:
        mos_note = "کف محدوده ارزش یا قیمت آخرین در دسترس نیست"

    open_risk = _number(rb, answers, "open_risk_pct")
    combined_risk = None
    risk_note = ""
    if open_risk is not None and max_loss is not None and implied_portfolio:
        combined_risk = open_risk + (max_loss / implied_portfolio * 100)
    else:
        risk_note = "مجموع ریسک باز یا سقف افت سبد ثبت نشده"

    return (
        _dv("implied_portfolio_toman", "ارزش ضمنی سبد از دو عدد مرحله ۰", implied_portfolio,
            unit="تومان", formula="زیان مجاز ÷ (حداکثر افت سبد ٪ ÷ ۱۰۰)"),
        _dv("stop_distance_pct", "فاصله ورود تا حد ابطال", stop_distance_pct,
            unit="٪", formula="(ورود − ابطال) ÷ ورود × ۱۰۰", note=stop_note),
        _dv("rr_ratio", "نسبت سود به زیان (R:R)", rr_ratio,
            unit="برابر", formula="(هدف − ورود) ÷ (ورود − ابطال)", note=rr_note),
        _dv("formula_position_toman", "اندازه موقعیت از فرمول", formula_size,
            unit="تومان", formula="زیان مجاز ÷ (فاصله تا حد ابطال ٪ ÷ ۱۰۰)", note=formula_note),
        _dv("position_weight_pct", "وزن ضمنی این موقعیت در سبد", weight_pct,
            unit="٪", formula="اندازه ÷ ارزش ضمنی سبد × ۱۰۰", note=weight_note),
        _dv("weight_conflict", "تعارض اندازه با سقف وزن (۱ = تعارض)", weight_conflict,
            formula="وزن ضمنی > سقف وزن سهم", note=conflict_note),
        _dv("size_gap_pct", "انحراف اندازهٔ دستی از فرمول", size_gap_pct,
            unit="٪", formula="(دستی − فرمول) ÷ فرمول × ۱۰۰", note=gap_note),
        _dv("exit_days_of_value", "سرپوش روزانهٔ نقدشوندگی", exit_days,
            unit="روز", formula="اندازه ÷ ارزش معاملات روزانه", note=exit_note),
        _dv("margin_from_value_low", "فاصله قیمت تا کف محدوده ارزش", mos_from_range,
            unit="٪", formula="(کف ارزش − قیمت) ÷ قیمت × ۱۰۰", note=mos_note),
        _dv("combined_open_risk_pct", "مجموع ریسک باز سبد با این معامله", combined_risk,
            unit="٪", formula="ریسک باز + ریسک این معامله", note=risk_note),
    )


def evaluate(
    answers: dict[str, Answer],
    evidence: dict[str, EvidenceValue] | None = None,
    rb: ResolvedBank | None = None,
) -> Evaluation:
    """Judge a sheet against the bank.

    ``answers`` is keyed by question code; unknown codes are ignored so a sheet saved
    under an older bank version still evaluates instead of crashing. ``rb`` is the bank
    resolved for the sheet's instrument class; defaulting to equity keeps every existing
    caller — and every stored equity sheet — behaving exactly as before.
    """
    rb = rb or resolve("equity")
    evidence = evidence or {}
    questions = rb.questions()
    known = {q.code: q for q in questions}
    answers = {c: a for c, a in answers.items() if c in known}

    vetoes: list[Veto] = []
    unknowns: list[str] = []
    weak_evidence: list[str] = []
    #: ★ gaps and missing justifications per stage, kept by stage id so the verdict can
    #: count only the region the gate has actually let the user work in.
    gaps_by_stage: dict[int, tuple[str, ...]] = {}
    notes_by_stage: dict[int, tuple[str, ...]] = {}

    per_stage: dict[int, StageResult] = {}
    ordered: list[StageResult] = []
    unlocked_stage = 0
    gate_open = True
    for stage in rb.stages():
        stage_questions = rb.questions_by_stage(stage.id)
        missing: list[str] = []
        stage_unknown: list[str] = []
        stage_veto: list[str] = []
        stage_stop: list[str] = []
        stage_notes: list[str] = []

        for question in stage_questions:
            answer = answers.get(question.code)
            if question.kind != "number":
                for item in question.evidence:
                    resolved = evidence.get(item.key)
                    if resolved is None or resolved.status == "missing":
                        weak_evidence.append(question.code)

            if answer is None or not question.is_answered(answer):
                missing.append(question.code)
                if question.stopper:
                    stage_stop.append(question.code)
                continue

            if answer.is_unknown:
                stage_unknown.append(question.code)
                unknowns.append(question.code)
                if question.stopper:
                    stage_stop.append(question.code)
                continue

            if _is_veto(question, answer):
                stage_veto.append(question.code)
                vetoes.append(Veto(question.code, question.text, _label_for(question, answer), stage.id))

            if _needs_written_note(question, answer):
                stage_notes.append(question.code)

        answered = len(stage_questions) - len(missing)
        complete = not missing and not stage_unknown and not stage_notes
        # Stage n is writable only while every earlier stage is complete — that is the
        # framework's «اگر نمی‌دانم، به مرحله بعد نرو» rule, enforced rather than suggested.
        locked = stage.id > 0 and not all(per_stage[s.id].complete for s in rb.stages() if s.id < stage.id)
        if complete and not locked and gate_open:
            unlocked_stage = stage.id + 1
        else:
            gate_open = False

        status: StageStatus
        if stage_veto:
            status = "vetoed"
        elif stage_unknown:
            status = "blocked_unknown"
        elif complete:
            status = "complete"
        elif answered:
            status = "in_progress"
        else:
            status = "empty"

        gaps_by_stage[stage.id] = tuple(stage_stop)
        notes_by_stage[stage.id] = tuple(stage_notes)
        result = StageResult(
            stage=stage, total=len(stage_questions), answered=answered, complete=complete,
            locked=locked,
            status=status, missing=tuple(missing), unknowns=tuple(stage_unknown),
            vetoed=tuple(stage_veto), missing_notes=tuple(stage_notes),
            stopper_gaps=tuple(stage_stop),
        )
        per_stage[stage.id] = result
        ordered.append(result)

    # Gaps inside the reachable region only: an unanswered ★ three stages ahead is
    # «not yet filled in», while one where the gate has let you work is actionable now.
    # Neither is a suspension — the sheet is simply in progress; the counts are surfaced
    # so the UI can say how many ★ are outstanding without alarming the user.
    def _reachable(mapping: dict[int, tuple[str, ...]]) -> tuple[str, ...]:
        codes = [code for s in range(unlocked_stage + 1) for code in mapping.get(s, ())]
        return tuple(sorted(set(codes)))

    stopper_gaps = _reachable(gaps_by_stage)
    missing_notes = _reachable(notes_by_stage)

    answered_total = sum(r.answered for r in ordered)
    total = len(questions)
    completion = round(answered_total / total * 100) if total else 0

    golden = tuple(
        GoldenResult(
            code=q.code,
            text=q.text,
            answered=q.code in answers and q.is_answered(answers[q.code]),
            blocking=(
                q.code not in answers
                or not q.is_answered(answers[q.code])
                or answers[q.code].is_unknown
            ),
            answer_label=_label_for(q, answers[q.code]) if q.code in answers else "بی‌پاسخ",
        )
        for q in questions
        if q.golden
    )

    reasons: list[str] = []
    if vetoes:
        reasons.extend(f"شرط ستاره‌ای {v.code} رد شد: {v.text}" for v in vetoes)
    if stopper_gaps:
        reasons.append(f"{len(stopper_gaps)} شرط ستاره‌ای بی‌پاسخ یا «نمی‌دانم» است.")
    if unknowns:
        reasons.append(f"{len(unknowns)} پاسخ «نمی‌دانم» ثبت شده — طبق قاعده، ادامهٔ تحلیل متوقف می‌شود.")
    if missing_notes:
        reasons.append(f"{len(missing_notes)} سؤال نیازمند توضیح نوشتاری دارد که ثبت نشده.")
    if weak_evidence:
        reasons.append(
            f"شواهد {len(set(weak_evidence))} سؤال از دادهٔ زنده قابل‌استخراج نیست؛ "
            "پاسخ‌هایشان باید مستند باشد."
        )

    verdict: Verdict
    if not answers:
        verdict = "not_started"
        reasons = ["هنوز هیچ پاسخی ثبت نشده است."]
    elif vetoes:
        verdict = "vetoed"
    elif unknowns:
        verdict = "blocked_unknown"
    elif answered_total < total:
        # Still being filled in. Outstanding ★/justification counts ride along in
        # stopper_gaps and missing_notes so the UI can show them without escalating.
        verdict = "in_progress"
    elif missing_notes or stopper_gaps or any(g.blocking for g in golden):
        verdict = "hold"
    else:
        verdict = "cleared"

    return Evaluation(
        verdict=verdict,
        total=total,
        answered=answered_total,
        completion_pct=completion,
        unlocked_stage=min(unlocked_stage, len(rb.stages()) - 1),
        stages=tuple(ordered),
        vetoes=tuple(vetoes),
        unknowns=tuple(sorted(set(unknowns))),
        stopper_gaps=tuple(sorted(set(stopper_gaps))),
        missing_notes=tuple(sorted(set(missing_notes))),
        weak_evidence=tuple(sorted(set(weak_evidence))),
        golden=golden,
        derived=_derive(rb, answers, evidence),
        blocking_reasons=tuple(reasons),
    )


__all__ = ["DerivedValue", "Evaluation", "GoldenResult", "StageResult", "Veto", "evaluate"]
