"""Tests for :mod:`core.scenario_bank` — the gold/silver assistant's answer contract.

The load-bearing test is :func:`test_model_answers_pass_the_checker`: every scenario's own
``expected`` must satisfy the contract it declares, otherwise the bank documents a rule it
itself violates. The rest pin the bank's shape and prove each rule actually fires.
"""

from __future__ import annotations

import pytest

from core.scenario_bank import bank, engine
from core.scenario_bank.schema import CATEGORIES, SECTION_IDS

SCENARIOS = bank.scenarios()


def test_bank_shape_and_unique_codes() -> None:
    codes = bank.scenario_codes()
    assert len(codes) == len(set(codes)), "scenario codes must be unique"
    assert len(SCENARIOS) >= 14
    assert all(code.startswith("PM-") for code in codes)
    assert all(s.category in CATEGORIES for s in SCENARIOS)
    assert all(s.mode in ("advise", "inform", "refuse") for s in SCENARIOS)
    assert all(s.expected.strip() for s in SCENARIOS)
    assert bank.scenario("PM-001") is not None
    assert bank.scenario("PM-999") is None


def test_every_category_is_covered() -> None:
    covered = {s.category for s in SCENARIOS}
    assert covered == set(CATEGORIES)


def test_requirement_catalogue_covers_every_key() -> None:
    catalogue = bank.evidence_by_key()
    used = {key for s in SCENARIOS for key in s.requirement_keys()}
    assert used <= set(catalogue), used - set(catalogue)
    assert all(r.source.strip() for r in catalogue.values())


def test_unresolved_keys_are_declared_requirements() -> None:
    for scenario in SCENARIOS:
        assert set(scenario.unresolved) <= set(scenario.requirement_keys()), scenario.code


def test_model_answers_pass_the_checker() -> None:
    failures = []
    for scenario in SCENARIOS:
        result = engine.check(scenario, scenario.expected)
        if not result.passed:
            failures.append((scenario.code, result.reasons))
    assert not failures, failures


def test_refusal_scenarios_are_gated_out_of_scope() -> None:
    for code in bank.REFUSAL_CODES:
        scenario = bank.scenario(code)
        assert scenario is not None
        gated = engine.gate(scenario.question)
        assert not gated.in_scope, code
        assert gated.mode == "refuse", code


def test_in_scope_scenarios_are_not_refused_and_get_a_view_when_advising() -> None:
    for scenario in SCENARIOS:
        if scenario.mode == "refuse":
            continue
        gated = engine.gate(scenario.question)
        assert gated.in_scope, scenario.code
        if scenario.mode == "advise":
            assert gated.mode == "advise", scenario.code


def test_forbidden_phrase_is_caught() -> None:
    scenario = bank.scenario("PM-001")
    assert scenario is not None
    result = engine.check(scenario, scenario.expected + "\nو سود تضمینی است.")
    assert not result.passed
    assert any(v.rule == "forbidden_phrase" for v in result.violations)


def test_missing_four_part_section_is_caught() -> None:
    scenario = bank.scenario("PM-003")
    assert scenario is not None
    only_summary = "جمع‌بندی: بفروش.\nدلایل: حباب بالا (ساعت ۱۰:۰۰، منبع: snapshot)."
    result = engine.check(scenario, only_summary)
    assert not result.passed
    assert result.missing_sections
    assert any(v.rule == "four_part_contract" for v in result.violations)


def test_missing_data_must_be_declared_not_decided_on() -> None:
    scenario = bank.scenario("PM-018")
    assert scenario is not None

    silent = "پریمیوم تاریخی این صندوق تقریباً ۲۰٪ بوده و خرید منطقی است."
    result = engine.check(scenario, silent)
    assert not result.passed
    assert any(v.rule == "undeclared_missing_data" for v in result.violations)

    declared = (
        "جمع‌بندی: این عدد نامشخص است.\n"
        "دلایل: سابقهٔ پریمیوم ذخیره نمی‌شود.\n"
        "ریسک: تصمیم بر پایهٔ یک رکورد روزانه گمراه‌کننده است.\n"
        "گام اجرایی: بدون اقدام."
    )
    assert engine.check(scenario, declared).passed


def test_definite_language_on_missing_data_is_caught() -> None:
    scenario = bank.scenario("PM-010")
    assert scenario is not None
    result = engine.check(scenario, "مالیات قطعاً صفر است.")
    assert not result.passed
    assert any(
        v.rule in ("definite_on_missing_data", "undeclared_missing_data")
        for v in result.violations
    )


def test_source_and_time_required_when_citing_live_data() -> None:
    scenario = bank.scenario("PM-001")
    assert scenario is not None
    raw = (
        "جمع‌بندی: ورود پله‌ای.\n"
        "دلایل: پریمیوم بالاست.\n"
        "ریسک: همگرایی پریمیوم تحلیل را باطل می‌کند.\n"
        "گام اجرایی: ۳۰٪ حجم، سفارش محدود."
    )
    result = engine.check(scenario, raw)
    assert not result.passed
    assert any(v.rule == "source_and_time" for v in result.violations)


@pytest.mark.parametrize(
    ("question", "reason_key"),
    [
        ("یک کیلو شمش طلا چطور بخرم و تحویل بگیرم؟", "physical"),
        ("مطمئنی سود می‌کنم؟ تضمین می‌کنی؟", "guarantee"),
        ("تمام سرمایه‌ام را طلا بخرم؟", "all_in"),
        ("بیت‌کوین بخرم؟", "other_market"),
        ("قیمت طلا فردا دقیقاً چقدر می‌شود؟", "prediction"),
    ],
)
def test_gate_detects_out_of_scope(question: str, reason_key: str) -> None:
    result = engine.gate(question)
    assert not result.in_scope
    assert result.mode == "refuse"
    assert result.reason


def test_gate_routes_in_scope_questions() -> None:
    assert engine.gate("الان صندوق طلا بخرم؟").mode == "advise"
    assert engine.gate("حباب طلا و سکه چیست؟").mode == "inform"
    assert engine.gate("روند هفتگی طلا چطور است؟").in_scope
    assert engine.gate("").category == "analyze"


def test_section_ids_match_markers() -> None:
    assert set(SECTION_IDS) == set(engine.SECTION_MARKERS)
