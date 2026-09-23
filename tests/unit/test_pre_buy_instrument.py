"""🧮 Instrument classification — the rules that decide which bank judges a symbol.

These pin the *decision table*, not the SQL: ``_probe`` is replaced with a canned lookup so
every branch (priority order, the ``fund_type`` mapping, the refusal) is exercised without a
database. The real queries against the real tables are driven by
``scripts/_check_pre_buy_shadow.py``.

The most important tests here are the negative ones: the platform must not invent an
instrument class it cannot evidence, and must not answer an unknown symbol with the stock
questions.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.question_bank import registry
from core.question_bank.registry import MODULES, UnknownInstrument
from core.question_bank.schema import INSTRUMENT_LABELS, INSTRUMENT_TYPES
from services import pre_buy_instrument as pi
from services.pre_buy_service import PreBuySheetService, bank_unavailable, catalogue


def _stubs(**hits: Any) -> Any:
    """Replace ``_probe`` with a table-name → value lookup."""

    async def fake_probe(session: Any, stmt: Any, table: str) -> Any:
        return hits.get(table)

    return fake_probe


def _install(monkeypatch: pytest.MonkeyPatch, **hits: Any) -> None:
    monkeypatch.setattr(pi, "_probe", _stubs(**hits))


# ── the type space ────────────────────────────────────────────────────────────────────


def test_every_modelled_type_is_labelled_in_persian() -> None:
    assert set(INSTRUMENT_LABELS) == set(INSTRUMENT_TYPES)
    assert all(label.strip() for label in INSTRUMENT_LABELS.values())


def test_no_type_is_invented_without_a_source() -> None:
    """``gold_fund`` and ``reit`` are absent on purpose.

    ``funds.fund_type`` has no gold or property value, and ``gold_fund_nav``/``gold_snapshots``
    hold zero rows, so a category by those names would be a claim nothing can check. Adding
    one requires a table that evidences it first.
    """

    assert "gold_fund" not in INSTRUMENT_TYPES
    assert "reit" not in INSTRUMENT_TYPES


def test_check_instrument_type_rejects_an_unknown_name() -> None:
    with pytest.raises(pi.UnknownInstrumentType):
        pi.check_instrument_type("crypto_perpetual")
    assert pi.check_instrument_type(None) is None
    assert pi.check_instrument_type("option") == "option"


def test_choices_advertise_which_banks_exist() -> None:
    choices = {c["key"]: c["hasBank"] for c in pi.instrument_choices()}
    assert set(choices) == set(INSTRUMENT_TYPES)
    assert choices["equity"] is True
    assert choices["option"] is True
    assert choices["unknown"] is False
    assert sorted(k for k, v in choices.items() if v) == sorted(MODULES)


def test_a_missing_bank_always_states_why() -> None:
    """A refusal without a reason reads as a bug, not as a data gap."""

    missing = [c for c in pi.instrument_choices() if not c["hasBank"]]
    assert [c["key"] for c in missing] == ["unknown"]
    for choice in missing:
        assert choice["missingBecause"].strip(), f"{choice['key']} refuses without a reason"


def test_the_classes_without_any_table_are_declared_in_data_terms() -> None:
    """REIT and bond evidence does not exist, and the platform has to say which column.

    These are the two classes the user's document lists that the database cannot support at
    all; the sentence must name the missing thing so it reads as a data finding and not as a
    backlog item.
    """

    assert "هیچ جدول" in registry.GAP_REASONS["reit"]
    assert "املاک" in registry.GAP_REASONS["reit"]
    assert "اخزا" in registry.GAP_REASONS["fixed_income"]
    for reason in registry.GAP_REASONS.values():
        assert reason.strip()


# ── classification ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("hits", "expected"),
    [
        ({"options": "خودرو"}, "option"),
        ({"commodity_options": "CU"}, "option"),
        ({"brsapi_ime_options": "CU"}, "option"),
        ({"commodity_futures": "قرارداد آتی"}, "future"),
        ({"brsapi_ime_futures": "قرارداد آتی"}, "future"),
        ({"commodity_certificates": "پسته"}, "commodity_certificate"),
        ({"brsapi_ime_certificates": "سکه طلا"}, "commodity_certificate"),
        ({"funds": "اهرمی"}, "leveraged_fund"),
        ({"funds": "درآمد ثابت"}, "fixed_income"),
        ({"funds": "سهامی"}, "fund"),
        ({"funds": "مختلط"}, "fund"),
        ({"brsapi_ime_funds": "صندوق س.کالای آبان"}, "commodity_fund"),
        ({"symbols": "پارس"}, "etf"),
        ({"instruments": "فولاد"}, "equity"),
    ],
)
async def test_each_source_produces_its_class(
    monkeypatch: pytest.MonkeyPatch, hits: dict[str, Any], expected: str
) -> None:
    _install(monkeypatch, **hits)
    decided = await pi.classify(object(), "XYZ")
    assert decided.instrument_type == expected
    assert decided.evidenced is True
    # The basis must name where the claim came from, never just repeat the answer.
    assert next(iter(hits)) in decided.basis


async def test_an_unrecognised_symbol_is_refused_not_defaulted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch)
    decided = await pi.classify(object(), "NAMAD-NIST")
    assert decided.instrument_type == "unknown"
    assert decided.evidenced is False
    assert decided.has_bank is False


async def test_derivatives_outrank_everything_else(monkeypatch: pytest.MonkeyPatch) -> None:
    """An option code that also appears in the equity tables is still an option."""

    _install(monkeypatch, options="خودرو", funds="سهامی", symbols="خودرو", instruments="خودرو")
    decided = await pi.classify(object(), "ضخود1234")
    assert decided.instrument_type == "option"


async def test_a_registered_fund_type_outranks_the_commodity_board(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A leveraged fund on the IME board is judged as leveraged, and the clash is reported."""

    _install(monkeypatch, funds="اهرمی", brsapi_ime_funds="صندوق اهرمی کالا")
    decided = await pi.classify(object(), "اهرمX")
    assert decided.instrument_type == "leveraged_fund"
    assert "brsapi_ime_funds" in decided.basis


async def test_a_blank_symbol_is_not_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, symbols="فولاد")
    decided = await pi.classify(object(), "   ")
    assert decided.instrument_type == "unknown"


def test_the_refusal_names_every_table_it_checked() -> None:
    message = str(pi.InstrumentUndetermined("XYZ"))
    assert all(table in message for table in pi.InstrumentUndetermined.CHECKED)


# ── the sheet side ────────────────────────────────────────────────────────────────────


def test_catalogue_is_per_instrument_and_never_falls_back() -> None:
    equity = catalogue("equity")
    option = catalogue("option")

    assert equity["total"] == 115 and equity["instrumentLabel"] == "سهام"
    assert option["total"] == 48 and option["instrumentLabel"] == "اختیار معامله"
    assert {q["code"] for q in option["questions"]} != {q["code"] for q in equity["questions"]}
    # The document's class D: recognised as a category, but no table backs it.
    with pytest.raises(UnknownInstrument):
        catalogue("reit")


def test_an_unauthored_bank_says_so_in_persian() -> None:
    message = bank_unavailable("option")
    assert "اختیار معامله" in message
    assert "نوشته نشده" in message


async def test_bank_for_an_unflushed_sheet_is_equity() -> None:
    from models.pre_buy import PreBuySheet

    rb = PreBuySheetService.bank_for(PreBuySheet(user_id="u", symbol="فولاد", bank_version="1.0.0"))
    assert rb.instrument_type == "equity"
    assert len(rb.questions()) == 115


def test_the_column_check_matches_the_modelled_types() -> None:
    """Migration 0062 is the same list as the type space, or a valid sheet is rejected by Postgres."""

    import importlib.util
    import os

    path = os.path.join("migrations", "versions", "0062_pre_buy_instrument_axis.py")
    spec = importlib.util.spec_from_file_location("m0062", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert tuple(mod._TYPES) == tuple(INSTRUMENT_TYPES)
