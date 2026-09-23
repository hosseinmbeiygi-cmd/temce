"""⚖️ Gate-engine behaviour — the truth table of «نمی‌دانم», ★ and completion.

The engine is the only thing that decides whether a sheet authorises a buy, so every
verdict it can produce is pinned here, including the two rules the framework states and
that a careless implementation would get wrong:

* «نمی‌دانم» is a *recorded answer* that suspends the sheet; it is not "unanswered".
* Only ★ questions reject. A negative answer anywhere else never vetoes.
"""

from __future__ import annotations

from core.question_bank import bank, evaluate
from core.question_bank.engine import Evaluation
from core.question_bank.schema import UNKNOWN, Answer, EvidenceValue

ORDER = [q.code for q in bank.questions()]
BY_CODE = {q.code: q for q in bank.questions()}


def _safe_value(q) -> str:
    bad = set(q.veto_values) | {UNKNOWN}
    for option in q.options:
        if option.id not in bad and not option.veto:
            return option.id
    return "yes" if q.kind == "yes_no_unknown" else "clean"


def fill(stage: int, overrides: dict[str, Answer] | None = None) -> dict[str, Answer]:
    """Well-formed answers for every question up to ``stage``, built from the bank itself."""

    out: dict[str, Answer] = {}
    for code in ORDER:
        q = BY_CODE[code]
        if q.stage > stage:
            continue
        if q.kind == "number":
            out[code] = Answer(code=code, numbers={i.id: 10.0 for i in q.inputs},
                               note="توضیح" if q.note_required else None)
        elif q.kind == "text":
            out[code] = Answer(code=code, value="متن آزمون")
        else:
            out[code] = Answer(code=code, value=_safe_value(q), note="توضیح" if q.note_required else None)
    out.update(overrides or {})
    return out


def _ev(**overrides: EvidenceValue) -> dict[str, EvidenceValue]:
    base = {
        k: EvidenceValue(key=k, label=k, source="test", status="available", value=1000.0)
        for k in bank.evidence_by_key()
    }
    base.update(overrides)
    return base


def test_empty_sheet_is_not_started_and_opens_only_stage_zero() -> None:
    ev = evaluate({})
    assert ev.verdict == "not_started"
    assert ev.answered == 0
    assert ev.completion_pct == 0
    assert ev.unlocked_stage == 0
    assert [s.stage.id for s in ev.stages if s.locked] == list(range(1, 11))
    assert not ev.can_buy


def test_filling_stage_zero_unlocks_stage_one_only() -> None:
    ev = evaluate(fill(0))
    assert ev.stages[0].complete
    assert ev.stages[0].status == "complete"
    assert not ev.stages[1].locked
    assert ev.stages[2].locked
    assert ev.unlocked_stage == 1
    # The rest of the bank is still empty, so nothing is authorised yet.
    assert ev.verdict == "in_progress"
    assert not ev.can_buy


def test_full_clean_sheet_clears_and_authorises() -> None:
    ev = evaluate(fill(10), _ev())
    assert ev.verdict == "cleared", ev.blocking_reasons
    assert ev.completion_pct == 100
    assert ev.answered == 115
    assert ev.can_buy
    assert not ev.vetoes and not ev.unknowns and not ev.stopper_gaps
    assert all(s.complete for s in ev.stages)


def test_unknown_is_answered_but_blocks_and_suspends() -> None:
    answers = fill(10)
    answers["PB-047"] = Answer(code="PB-047", value=UNKNOWN)  # ★ choice
    ev = evaluate(answers, _ev())

    assert ev.verdict == "blocked_unknown"
    assert "PB-047" in ev.unknowns
    assert "PB-047" in ev.stopper_gaps
    assert not ev.can_buy
    # «نمی‌دانم» counts as answered — it is a real answer, and it is what stops the stage.
    stage4 = next(s for s in ev.stages if s.stage.id == 4)
    assert stage4.answered == stage4.total
    assert stage4.status == "blocked_unknown"
    assert not stage4.complete


def test_non_stopper_negative_answer_never_vetoes() -> None:
    answers = fill(10)
    # PB-017 («سود از اقلام یک‌باره») is a non-★ choice that carries a veto option.
    question = BY_CODE["PB-017"]
    assert not question.stopper and any(o.veto for o in question.options)
    answers["PB-017"] = Answer(code="PB-017", value=next(o.id for o in question.options if o.veto))
    ev = evaluate(answers, _ev())
    assert "PB-017" not in [v.code for v in ev.vetoes]
    assert ev.verdict != "vetoed"


def test_every_stopper_veto_value_rejects() -> None:
    for question in (q for q in bank.questions() if q.stopper and q.veto_values):
        answers = fill(10)
        answers[question.code] = Answer(code=question.code, value=question.veto_values[0],
                                        note=question.text if question.note_required else None)
        ev = evaluate(answers, _ev())
        assert ev.verdict == "vetoed", question.code
        assert [v.code for v in ev.vetoes] == [question.code], question.code
        assert not ev.can_buy


def test_blank_star_is_counted_but_does_not_alarm_a_sheet_still_being_filled() -> None:
    """An unanswered ★ keeps the sheet «در حال تکمیل» with the gap reported; only a sheet
    that is complete on its face yet still owes something is «معلق»."""

    answers = fill(10)
    answers.pop("PB-099")  # «شرط ابطال تحلیل» — a required ★ prose answer
    ev = evaluate(answers, _ev())
    assert ev.verdict == "in_progress"
    assert "PB-099" in ev.stopper_gaps
    assert ev.completion_pct < 100
    assert not ev.can_buy


def test_missing_written_note_blocks_a_required_justification() -> None:
    answers = fill(10)
    # PB-020 is a choice question whose justification the framework demands in writing.
    question = BY_CODE["PB-020"]
    assert question.note_required and question.kind != "text"
    answers["PB-020"] = Answer(code="PB-020", value="yes", note="   ")
    ev = evaluate(answers, _ev())
    assert "PB-020" in ev.missing_notes
    assert ev.verdict == "hold"
    assert not ev.can_buy


def test_unknown_question_codes_are_ignored_not_fatal() -> None:
    """A draft saved under an older bank version must still evaluate."""

    answers = fill(0)
    answers["PB-900"] = Answer(code="PB-900", value="yes")
    ev = evaluate(answers, _ev())
    assert ev.total == 115
    assert ev.answered == 11


def test_derived_position_sizing_and_risk_ratio() -> None:
    answers = fill(10)
    answers["PB-004"] = Answer(code="PB-004", numbers={"drawdown_pct": 20.0, "drawdown_toman": 4e8})
    answers["PB-005"] = Answer(code="PB-005", numbers={"max_loss_toman": 4e7}, note="زیان مجاز")
    answers["PB-006"] = Answer(code="PB-006", numbers={"stock_cap_pct": 10.0, "sector_cap_pct": 25.0})
    answers["PB-084"] = Answer(
        code="PB-084", numbers={"entry": 100_000.0, "stop": 90_000.0, "target": 130_000.0},
        note="ورود/ابطال/هدف",
    )
    answers["PB-091"] = Answer(code="PB-091", numbers={"position_toman": 5e8})
    ev = evaluate(answers, _ev(**{"detail.trade_value": EvidenceValue(
        key="detail.trade_value", label="ارزش معاملات", source="t", unit="ریال",
        value=1e10, status="available")}))
    d = ev.derived_map()

    assert d["stop_distance_pct"].value == 10.0
    assert d["rr_ratio"].value == 3.0
    assert d["implied_portfolio_toman"].value == 2e8
    assert d["formula_position_toman"].value == 4e8
    assert d["position_weight_pct"].value == 250.0
    assert d["weight_conflict"].value == 1.0, "250% weight against a 10% cap must flag"
    assert d["size_gap_pct"].value == 25.0
    assert d["exit_days_of_value"].value == 0.05
    assert d["margin_from_value_low"].value == -99.0, "(10 − 1000) / 1000 × ۱۰۰"


def test_derived_math_is_honest_about_missing_inputs() -> None:
    ev: Evaluation = evaluate({}, _ev())
    d = ev.derived_map()
    assert not any(x.available for x in ev.derived)
    assert all(x.note for x in ev.derived)
    assert d["rr_ratio"].value is None


def test_stop_above_entry_is_reported_not_computed() -> None:
    answers = fill(10)
    answers["PB-084"] = Answer(code="PB-084", numbers={"entry": 90_000.0, "stop": 100_000.0,
                                                       "target": 120_000.0}, note="x")
    d = evaluate(answers, _ev()).derived_map()
    assert not d["stop_distance_pct"].available
    assert "ابطال" in d["stop_distance_pct"].note


def test_golden_questions_are_reported_and_block_clearance() -> None:
    answers = fill(10)
    answers.pop("PB-091")
    ev = evaluate(answers, _ev())
    golden = {g.code: g for g in ev.golden}
    assert set(golden) == set(bank.GOLDEN_CODES)
    assert golden["PB-091"].blocking is True
    assert ev.verdict == "in_progress"
    assert not ev.can_buy


def test_verdict_is_deterministic() -> None:
    answers = fill(10)
    first = evaluate(answers, _ev())
    second = evaluate(answers, _ev())
    assert first.verdict == second.verdict
    assert [d.value for d in first.derived] == [d.value for d in second.derived]
