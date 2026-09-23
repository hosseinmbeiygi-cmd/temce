"""🔁 Pre-buy service serialisation — answers, evidence and the audit hash.

Nothing here touches Postgres: these are the pure encode/decode edges of the service,
which is exactly where a saved sheet can silently lose fidelity (a ``numbers`` dict
flattened to strings, an ``answeredAt`` key renamed between camel and snake case, a hash
that changes on every save).
"""

from __future__ import annotations

from core.question_bank import bank
from core.question_bank.engine import evaluate
from core.question_bank.schema import BANK_VERSION, UNKNOWN, Answer, EvidenceValue
from services.pre_buy_service import (
    answers_to_json,
    catalogue,
    evaluation_to_json,
    evidence_from_json,
    evidence_to_json,
    parse_answers,
)


def test_answers_roundtrip_preserves_numbers_and_notes() -> None:
    original = {
        "PB-084": Answer(code="PB-084", numbers={"entry": 12345.0, "stop": 11000.0}, note="ورود و ابطال"),
        "PB-003": Answer(code="PB-003", value=UNKNOWN),
        "PB-111": Answer(code="PB-111", value="دو جمله دلیل"),
    }
    restored = parse_answers(answers_to_json(original))

    assert restored["PB-084"].numbers == {"entry": 12345.0, "stop": 11000.0}
    assert restored["PB-084"].note == "ورود و ابطال"
    assert restored["PB-003"].is_unknown
    assert restored["PB-111"].value == "دو جمله دلیل"


def test_parse_answers_survives_junk() -> None:
    parsed = parse_answers({
        "PB-001": "not-a-dict",
        "PB-002": {"value": None, "numbers": {"horizon_months": "12", }},
        "PB-003": {"value": "yes", "numbers": {"stray": "not-a-number"}},
    })
    assert "PB-001" not in parsed
    assert parsed["PB-003"].value == "yes"
    assert parsed["PB-003"].numbers == {}, "non-numeric entries must not leak into the map"


def test_evidence_roundtrip_marks_only_available_as_available() -> None:
    values = {
        "detail.eps": EvidenceValue(key="detail.eps", label="EPS", source="GET /x", value=497.0,
                                    status="available", as_of="1405-06-04"),
        "fin.roe": EvidenceValue(key="fin.roe", label="ROE", source="GET /y", status="missing",
                                 note="یافت نشد"),
        # The app's own gap must survive the round trip: a saved sheet whose declared handle
        # came back as an ordinary miss would blame the user for a column that never existed.
        "holders.institutional_pct": EvidenceValue(
            key="holders.institutional_pct", label="سهم حقوقی", source="GET /z", status="missing",
            note="نوع سهامدار ذخیره نمی‌شود.", declared=True,
        ),
    }
    restored = evidence_from_json(evidence_to_json(values))
    assert restored["detail.eps"].status == "available"
    assert restored["detail.eps"].value == 497.0
    assert restored["detail.eps"].as_of == "1405-06-04"
    assert restored["fin.roe"].status == "missing"
    assert restored["fin.roe"].note == "یافت نشد"
    assert restored["fin.roe"].declared is False
    assert restored["holders.institutional_pct"].declared is True


def test_input_hash_is_stable_and_content_sensitive() -> None:
    from services.pre_buy_service import _input_hash

    a = {"PB-003": Answer(code="PB-003", value="yes")}
    ev = {"detail.eps": EvidenceValue(key="detail.eps", label="EPS", source="s", value=1.0)}
    assert _input_hash("equity", a, ev) == _input_hash("equity", dict(a), dict(ev))
    assert _input_hash("equity", a, ev) != _input_hash("equity", a, {"detail.eps": EvidenceValue(
        key="detail.eps", label="EPS", source="s", value=2.0)})
    assert _input_hash("equity", a, ev) != _input_hash(
        "equity", {"PB-003": Answer(code="PB-003", value="no")}, ev)
    assert _input_hash("equity", a, ev) != _input_hash("etf", a, ev), (
        "the same answers under two banks are two different claims"
    )
    assert len(_input_hash("equity", {}, {})) == 64


def test_next_review_follows_the_recorded_interval() -> None:
    from datetime import datetime

    from services.pre_buy_service import _next_review_at

    now = datetime(2026, 9, 21, 8, 0, 0)
    answers = {"PB-105": Answer(code="PB-105", numbers={"review_days": 30.0})}
    assert _next_review_at(answers, now) == datetime(2026, 10, 21, 8, 0, 0)
    assert _next_review_at({}, now) is None


def test_catalogue_shape_matches_the_bank() -> None:
    cat = catalogue()
    assert cat["total"] == 115
    assert len(cat["stages"]) == 11
    assert len(cat["questions"]) == 115
    assert cat["stopperCodes"] == list(bank.STOPPER_CODES)
    assert cat["goldenCodes"] == list(bank.GOLDEN_CODES)

    by_code = {q["code"]: q for q in cat["questions"]}
    star = by_code["PB-016"]
    assert star["stopper"] is True
    assert by_code["PB-084"]["inputs"][0]["role"] == "entry_price"
    assert by_code["PB-013"]["evidence"], "star questions must surface their evidence handle"
    assert all({"id", "label", "veto"} <= set(o) for o in by_code["PB-015"]["options"])


def test_evaluation_serialises_everything_the_ui_needs() -> None:
    payload = evaluation_to_json(evaluate({}))
    assert payload["verdict"] == "not_started"
    assert payload["canBuy"] is False
    assert len(payload["stages"]) == 11
    assert len(payload["derived"]) == 10
    assert {"key", "label", "value", "formula", "available", "note"} <= set(payload["derived"][0])
    assert set(payload["stages"][0]) >= {"id", "locked", "status", "progressPct", "missing"}


async def test_save_stamps_answers_without_mutating_frozen_records() -> None:
    """Regression: `Answer` is frozen, so the merge loop has to build a new record.

    The first version assigned `answered_at` in place, which raised `FrozenInstanceError`
    on the very first save the UI made — the one path no pure serialisation test hit.
    """

    from unittest.mock import AsyncMock

    from models.pre_buy import PreBuySheet
    from services.pre_buy_service import PreBuySheetService

    sheet = PreBuySheet(
        user_id="u-1", symbol="فولاد", bank_version=BANK_VERSION,
        status="DRAFT", answers={}, evidence={},
    )
    svc = PreBuySheetService(session=AsyncMock())

    row, evaluation, _ = await svc.save(
        sheet,
        {"PB-001": {"value": "yes"}, "PB-013": {"value": UNKNOWN}, "NOT-A-CODE": {"value": "yes"}},
        refresh_evidence=False,
    )

    assert row.answers["PB-001"]["answeredAt"], "the server clock must stamp the answer"
    assert "NOT-A-CODE" not in row.answers, "codes outside the bank are dropped on save"
    assert evaluation.answered == 2
    assert evaluation.unlocked_stage == 0, "one «نمی‌دانم» keeps the next stage closed"


async def test_save_refuses_to_rewrite_an_archived_sheet() -> None:
    """The service is the only writer of a sheet, so the read-only rule lives here too."""

    from unittest.mock import AsyncMock

    import pytest

    from models.pre_buy import PreBuySheet
    from services.pre_buy_service import PreBuySheetService

    sheet = PreBuySheet(
        user_id="u-1", symbol="فولاد", bank_version=BANK_VERSION,
        status="SUBMITTED", answers={}, evidence={},
    )
    with pytest.raises(ValueError, match="read-only"):
        await PreBuySheetService(session=AsyncMock()).save(
            sheet, {"PB-001": {"value": "no"}}, refresh_evidence=False
        )
