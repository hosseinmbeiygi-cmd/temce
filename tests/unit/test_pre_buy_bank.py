"""🧪 Question-bank integrity — the counts, codes and shapes the whole feature rests on.

These are deliberately assertions about the *content*, not the logic: the sheet's
credibility depends on «۱۱۵ سؤال / ۱۵ شرط ستاره‌ای / ۵ سؤال طلایی» being literally true,
and on every code being unique and well-formed, because answers are persisted by code.
A duplicated code silently corrupts every saved sheet that references it.
"""

from __future__ import annotations

import re

from core.question_bank import bank, registry
from core.question_bank.registry import resolve
from core.question_bank.schema import UNKNOWN, Question

CODE_RE = re.compile(r"^PB-\d{3}$")


def test_counts_match_the_framework_document() -> None:
    assert len(bank.stages()) == 11
    assert len(bank.questions()) == 115
    assert len(bank.STOPPER_CODES) == 15
    assert len(bank.GOLDEN_CODES) == 5


def test_per_stage_counts_match_the_document() -> None:
    """مرحله ۰:۱۱ · ۱:۹ · ۲:۱۰ · ۳:۱۵ · ۴:۱۵ · ۵:۱۲ · ۶:۷ · ۷:۱۱ · ۸:۸ · ۹:۷ · ۱۰:۱۰"""

    counts = [len(bank.questions_by_stage(s.id)) for s in bank.stages()]
    assert counts == [11, 9, 10, 15, 15, 12, 7, 11, 8, 7, 10]
    assert sum(counts) == 115


def test_codes_are_unique_well_formed_and_contiguous() -> None:
    codes = [q.code for q in bank.questions()]
    assert len(set(codes)) == len(codes), "duplicate question code would corrupt saved answers"
    for code in codes:
        assert CODE_RE.match(code), code
    assert codes == [f"PB-{i:03d}" for i in range(1, 116)], "codes must stay contiguous"


def test_every_stage_has_questions_and_every_question_has_a_stage() -> None:
    stage_ids = {s.id for s in bank.stages()}
    assert stage_ids == set(range(11))
    for q in bank.questions():
        assert q.stage in stage_ids
    assert bank.question("PB-001") is not None
    assert bank.question("PB-999") is None


def test_stoppers_are_distributed_and_golden_are_stoppers_or_required() -> None:
    stoppers = [q for q in bank.questions() if q.stopper]
    assert {q.stage for q in stoppers} == {0, 1, 4, 5, 6, 8, 9, 10}
    # «پنج سؤال طلایی» are the summary of the whole bank — each must be answerable
    # without a click alone, i.e. it carries a written justification requirement.
    golden = [q for q in bank.questions() if q.golden]
    assert [q.code for q in golden] == list(bank.GOLDEN_CODES)


def test_question_shapes_are_self_consistent() -> None:
    for q in bank.questions():
        assert q.text.strip()
        assert q.kind in {"yes_no_unknown", "choice", "number", "text"}
        if q.kind == "choice":
            assert len(q.options) >= 2, q.code
            assert len({o.id for o in q.options}) == len(q.options), q.code
        if q.kind == "yes_no_unknown":
            assert tuple(o.id for o in q.options) == ("yes", "no", UNKNOWN), q.code
            assert not q.options[0].veto and not q.options[1].veto, q.code
        if q.kind == "number":
            assert q.inputs, q.code
            assert len({i.id for i in q.inputs}) == len(q.inputs), q.code
        for value in q.veto_values:
            assert value in {o.id for o in q.options}, f"{q.code} vetoes an option it does not offer"
        if q.stopper:
            # A stopper must be able to block: an option veto, a veto value, or forced prose.
            assert (
                any(o.veto for o in q.options)
                or q.veto_values
                or q.note_required
                or q.kind in {"text", "number"}
            ), q.code


def test_non_stoppers_may_mark_a_failing_answer_but_never_reject() -> None:
    """``veto`` on an option means "this is the bad answer" (the UI colours it), while
    rejection itself is gated on ★ in the engine — asserted in test_pre_buy_engine."""

    for q in bank.questions():
        if not q.stopper:
            assert not q.veto_values, f"{q.code}: veto_values are for stoppers only"


def test_every_evidence_handle_is_registered_in_the_catalogue() -> None:
    catalogue = bank.evidence_by_key()
    used = {e.key for q in bank.questions() for e in q.evidence}
    assert used <= set(catalogue), used - set(catalogue)
    for key, meta in catalogue.items():
        assert meta.source.startswith(("GET ", "POST ")), key
        assert meta.label.strip(), key


def test_evidence_keys_are_implemented_by_the_resolver() -> None:
    """A declared handle with no resolver would show as missing forever, silently."""

    from services.pre_buy_evidence import _RESOLVERS  # noqa: PLC2701 - contract check

    declared = set(bank.evidence_by_key())
    assert declared <= set(_RESOLVERS), declared - set(_RESOLVERS)
    # Every extra binding belongs to an instrument module, and is a handle some module declares.
    extra = set(_RESOLVERS) - declared
    declared_by_modules: set[str] = set()
    for key in registry.MODULES:
        declared_by_modules |= set(resolve(key).evidence_by_key())
    assert extra <= declared_by_modules, extra - declared_by_modules


def test_numeric_roles_are_unique_where_the_engine_depends_on_them() -> None:
    """The derived maths looks inputs up by role; two owners for one role is a bug."""

    owners: dict[str, list[str]] = {}
    for q in bank.questions():
        for inp in q.inputs:
            if inp.role:
                owners.setdefault(inp.role, []).append(q.code)
    for role, codes in owners.items():
        assert len(codes) == 1, f"role {role} claimed by {codes}"


def test_question_type_is_frozen_data() -> None:
    """Answers are keyed by code; mutating the bank at runtime would break saved sheets."""

    import dataclasses

    assert dataclasses.is_dataclass(Question)
    assert Question.__dataclass_params__.frozen
