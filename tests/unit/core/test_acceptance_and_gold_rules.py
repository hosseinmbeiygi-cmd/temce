"""Behavioral tests for the Gold Engine acceptance gate (spec v1.0, 2026-10-13).

Covers:
  * Step 1 — ``acceptance.yaml`` loads with all three gold instruments.
  * Step 3 — ``get_gold_market_rules`` returns the per-instrument currency,
    risk-free rate and annualisation factor (USD/0.045/252d vs IRR/0.300/240d).
  * Step 3 — ``evaluate_acceptance`` gates a strategy as PASS/REJECT.
  * Step 2 (TD-01) — ``deflated_sharpe_ratio`` survives ``n_trials == 1``.
  * Step 3 — a malformed ``acceptance.yaml`` fails validation loudly.

All tests are behavioral: they call the public helpers and assert on returned
values — no source inspection or regex matching.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from core.config.acceptance_loader import (
    FEE_INSTRUMENTS,
    evaluate_acceptance,
    get_acceptance_config,
    get_assistant_rules,
    get_fee_schedule,
    get_fee_terms,
    get_gold_market_rules,
    get_market_hours,
    get_signal_filter,
    required_gross_move_pct,
)

# ── Step 1: acceptance.yaml loads ────────────────────────────────────────────

GOLD_INSTRUMENTS = ("global_xau", "domestic_ime", "domestic_etf")


def test_acceptance_yaml_loads_all_gold_instruments():
    config = get_acceptance_config()

    assert config["version"] == "1.0"
    assert config["asset_class"] == "gold"

    gold = config["market_rules"]["gold"]
    assert set(gold.keys()) == set(GOLD_INSTRUMENTS)
    for instrument in GOLD_INSTRUMENTS:
        rules = gold[instrument]
        assert set(rules.keys()) == {
            "currency",
            "risk_free_rate",
            "trading_days_per_year",
            "spread_model",
        }


def test_acceptance_yaml_thresholds_present():
    thresholds = get_acceptance_config()["thresholds"]

    assert thresholds["walk_forward"]["min_wfe"] == pytest.approx(0.50)
    assert thresholds["walk_forward"]["min_dsr"] == pytest.approx(0.95)
    assert thresholds["walk_forward"]["min_oos_sharpe"] == pytest.approx(1.00)
    assert thresholds["risk_management"]["max_drawdown"] == pytest.approx(0.20)
    assert thresholds["risk_management"]["min_profit_factor"] == pytest.approx(1.30)
    assert thresholds["risk_management"]["min_trade_count"] == 50


# ── Step 3: per-instrument market rules ─────────────────────────────────────


def test_get_gold_market_rules_global_xau():
    rules = get_gold_market_rules("global_xau")

    assert rules["currency"] == "USD"
    assert rules["risk_free_rate"] == pytest.approx(0.045)
    assert rules["trading_days_per_year"] == 252
    assert rules["annualization_factor"] == pytest.approx(math.sqrt(252))
    assert rules["spread_model"] == "floating_points"


@pytest.mark.parametrize("instrument", ["domestic_ime", "domestic_etf"])
def test_get_gold_market_rules_domestic(instrument):
    rules = get_gold_market_rules(instrument)

    assert rules["currency"] == "IRR"
    assert rules["risk_free_rate"] == pytest.approx(0.300)
    assert rules["trading_days_per_year"] == 240
    assert rules["annualization_factor"] == pytest.approx(math.sqrt(240))


def test_get_gold_market_rules_unknown_instrument_raises():
    with pytest.raises(KeyError):
        get_gold_market_rules("not_an_instrument")


# ── Step 3: the acceptance gate ─────────────────────────────────────────────


def _passing_metrics() -> dict:
    return {
        "walk_forward_efficiency": 0.80,
        "deflated_sharpe": 0.97,
        "avg_oos_sharpe": 1.50,
        "max_drawdown": 0.10,
        "profit_factor": 1.80,
        "trade_count": 120,
    }


def test_evaluate_acceptance_passes_qualifying_strategy():
    verdict = evaluate_acceptance(_passing_metrics())

    assert verdict["status"] == "PASS"
    assert verdict["reasons"] == []


def test_evaluate_acceptance_rejects_each_breached_criterion():
    metrics = {
        "walk_forward_efficiency": 0.30,  # < min_wfe 0.50
        "deflated_sharpe": 0.90,          # < min_dsr 0.95
        "avg_oos_sharpe": 0.40,           # < min_oos_sharpe 1.00
        "max_drawdown": 0.45,             # > max_drawdown 0.20
        "profit_factor": 1.10,            # < min_profit_factor 1.30
        "trade_count": 10,                # < min_trade_count 50
    }
    verdict = evaluate_acceptance(metrics)

    assert verdict["status"] == "REJECT"
    assert len(verdict["reasons"]) == 6
    joined = " ".join(verdict["reasons"]).lower()
    for token in ("wfe", "dsr", "sharpe", "drawdown", "profit", "trade"):
        assert token in joined


def test_evaluate_acceptance_boundary_values_pass():
    """Exactly-at-threshold must PASS (>= / <= semantics)."""
    metrics = {
        "walk_forward_efficiency": 0.50,
        "deflated_sharpe": 0.95,
        "avg_oos_sharpe": 1.00,
        "max_drawdown": 0.20,
        "profit_factor": 1.30,
        "trade_count": 50,
    }
    assert evaluate_acceptance(metrics)["status"] == "PASS"


def test_evaluate_acceptance_missing_metric_is_rejected():
    metrics = _passing_metrics()
    del metrics["profit_factor"]

    verdict = evaluate_acceptance(metrics)

    assert verdict["status"] == "REJECT"
    assert any("profit_factor" in r and "missing" in r.lower() for r in verdict["reasons"])


def test_evaluate_acceptance_normalizes_percent_drawdown():
    """Risk metrics reported as 0-100 percentages are normalized to fractions."""
    metrics = _passing_metrics()
    metrics["max_drawdown"] = 10.0  # 10% expressed on the 0-100 scale

    assert evaluate_acceptance(metrics)["status"] == "PASS"

    metrics["max_drawdown"] = 45.0  # 45% → above the 20% limit
    assert evaluate_acceptance(metrics)["status"] == "REJECT"


# ── Step 2 (TD-01): degenerate DSR guard ────────────────────────────────────


def test_deflated_sharpe_single_trial_does_not_raise():
    from backtesting.metrics.deflated_sharpe import deflated_sharpe_ratio

    result = deflated_sharpe_ratio(
        sharpe_observed=1.5,
        n_trials=1,
        n_observations=250,
    )

    assert result["n_trials"] == 1
    assert 0.0 <= result["deflated_sharpe"] <= 1.0
    assert 0.0 <= result["p_value"] <= 1.0
    assert math.isfinite(result["deflated_sharpe"])


# ── Malformed configuration fails loudly ────────────────────────────────────


def _valid_fee_schedule() -> dict:
    """§۲۷.۱ — every instrument must declare its own terms; ``None`` ≠ zero."""
    instruments: dict = {}
    for name in ("commodity_fund", "coin_certificate", "bullion_certificate"):
        instruments[name] = {
            "label_fa": name,
            "fee_per_side": 0.0012,
            "fee_cap_irr": None,
            "tax_exempt": True,
            "provenance": "spec",
        }
    for name in ("futures", "option"):
        instruments[name] = {
            "label_fa": name,
            "fee_per_side": None,
            "fee_cap_irr": None,
            "tax_exempt": False,
            "provenance": "unavailable",
        }
    return {"version": "1.0", "last_updated": "1405-07-22", "instruments": instruments}


def _valid_signal_filter() -> dict:
    return {
        "min_net_profit_pct": 2.0,
        "min_risk_reward": 2.0,
        "require_positive_ev": True,
        "provenance": {"min_net_profit_pct": "spec", "min_risk_reward": "assumption"},
    }


def _valid_market_hours() -> dict:
    return {
        "sat_to_wed": {"pre_open": "11:45", "open": "12:00", "close": "18:00"},
        "thursday": {"pre_open": "11:45", "open": "12:00", "close": "15:00"},
        "friday_closed": True,
        "price_band_pct": 10.0,
        "emergency_band_pcts": [1, 2, 5],
        "settlement_days": 1,
        "provenance": "assumption",
    }


def _valid_document() -> dict:
    """A minimal document that satisfies every ``_validate`` requirement."""
    return {
        "version": "1.0",
        "asset_class": "gold",
        "market_rules": {
            "gold": {
                "global_xau": {
                    "currency": "USD",
                    "risk_free_rate": 0.045,
                    "trading_days_per_year": 252,
                    "spread_model": "floating_points",
                }
            }
        },
        "thresholds": {
            "walk_forward": {"min_wfe": 0.50, "min_dsr": 0.95, "min_oos_sharpe": 1.00},
            "risk_management": {
                "max_drawdown": 0.20,
                "min_profit_factor": 1.30,
                "min_trade_count": 50,
            },
        },
        "fee_schedule": _valid_fee_schedule(),
        "signal_filter": _valid_signal_filter(),
        "market_hours": _valid_market_hours(),
    }


def _write_config(tmp_path: Path, document: dict) -> Path:
    import yaml  # local import: PyYAML is an optional runtime dependency

    path = tmp_path / "acceptance.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return path


def test_the_baseline_document_used_by_the_mutation_cases_is_valid(tmp_path):
    """Control: the fixture itself loads, so the cases below fail for their own reason."""
    config = get_acceptance_config(_write_config(tmp_path, _valid_document()))

    assert config["version"] == "1.0"
    assert config["thresholds"]["risk_management"]["min_trade_count"] == 50


def _drop_top_level(key: str):
    def mutate(document: dict) -> None:
        del document[key]

    return mutate


def _drop_threshold_section(section: str):
    def mutate(document: dict) -> None:
        del document["thresholds"][section]

    return mutate


def _drop_instrument_key(instrument: str, key: str):
    def mutate(document: dict) -> None:
        del document["market_rules"]["gold"][instrument][key]

    return mutate


def _empty_gold_universe():
    def mutate(document: dict) -> None:
        document["market_rules"]["gold"] = {}

    return mutate


def _drop_fee_instrument(instrument: str):
    def mutate(document: dict) -> None:
        del document["fee_schedule"]["instruments"][instrument]

    return mutate


def _zero_fee(instrument: str):
    """صفر یک نرخ جعلی است؛ عدد ناموجود باید ``None`` بماند (‏§۲۷.۱)."""

    def mutate(document: dict) -> None:
        document["fee_schedule"]["instruments"][instrument]["fee_per_side"] = 0

    return mutate


def _bad_provenance():
    def mutate(document: dict) -> None:
        document["signal_filter"]["provenance"]["min_risk_reward"] = "vibes"

    return mutate


def _non_positive_filter_threshold():
    def mutate(document: dict) -> None:
        document["signal_filter"]["min_risk_reward"] = 0

    return mutate


def _bad_clock_format():
    def mutate(document: dict) -> None:
        document["market_hours"]["thursday"]["close"] = "3pm"

    return mutate


def _out_of_range_clock():
    def mutate(document: dict) -> None:
        document["market_hours"]["thursday"]["close"] = "25:99"

    return mutate


def _drop_session_key():
    def mutate(document: dict) -> None:
        del document["market_hours"]["thursday"]["close"]

    return mutate


def _empty_emergency_bands():
    def mutate(document: dict) -> None:
        document["market_hours"]["emergency_band_pcts"] = []

    return mutate


@pytest.mark.parametrize(
    "mutate, expected_fragment",
    [
        (_drop_top_level("version"), "version"),
        (_drop_top_level("thresholds"), "thresholds"),
        (_empty_gold_universe(), "market_rules.gold"),
        (_drop_threshold_section("walk_forward"), "thresholds.walk_forward"),
        (_drop_threshold_section("risk_management"), "thresholds.risk_management"),
        (_drop_instrument_key("global_xau", "spread_model"), "spread_model"),
        (
            _drop_instrument_key("global_xau", "trading_days_per_year"),
            "trading_days_per_year",
        ),
        # §۲۷.۱ — تعرفه
        (_drop_top_level("fee_schedule"), "fee_schedule"),
        (_drop_top_level("signal_filter"), "signal_filter"),
        (_drop_top_level("market_hours"), "market_hours"),
        (_drop_fee_instrument("futures"), "fee_schedule.instruments"),
        (_zero_fee("commodity_fund"), "fee_per_side"),
        # §۲۶ — فیلتر ارزش معامله
        (_bad_provenance(), "provenance"),
        (_non_positive_filter_threshold(), "min_risk_reward"),
        # §۲۷.۳ — ساعت بازار
        (_bad_clock_format(), "HH:MM"),
        (_out_of_range_clock(), "market_hours.thursday.close"),
        (_drop_session_key(), "market_hours.thursday"),
        (_empty_emergency_bands(), "emergency_band_pcts"),
    ],
)
def test_incomplete_acceptance_config_is_rejected(tmp_path, mutate, expected_fragment):
    """A structurally incomplete config raises ``ValueError`` naming the offender.

    The failure must be loud and actionable — an accepted malformed config would
    silently gate strategies on thresholds that were never defined.
    """
    document = _valid_document()
    mutate(document)
    path = _write_config(tmp_path, document)

    with pytest.raises(ValueError) as excinfo:
        get_acceptance_config(path)

    message = str(excinfo.value)
    assert expected_fragment in message, message
    assert "acceptance" in message.lower(), message


def test_unparseable_acceptance_yaml_raises(tmp_path):
    import yaml

    path = tmp_path / "acceptance.yaml"
    path.write_text("thresholds: [unclosed\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        get_acceptance_config(path)


def test_non_mapping_acceptance_yaml_raises(tmp_path):
    path = tmp_path / "acceptance.yaml"
    path.write_text("- version\n- 1.0\n", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        get_acceptance_config(path)

    assert "mapping" in str(excinfo.value)


def test_empty_acceptance_yaml_raises(tmp_path):
    path = tmp_path / "acceptance.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        get_acceptance_config(path)

    assert "version" in str(excinfo.value)


def test_missing_acceptance_yaml_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError) as excinfo:
        get_acceptance_config(tmp_path / "absent.yaml")

    assert "not found" in str(excinfo.value)


def test_malformed_config_does_not_poison_the_real_config():
    """A rejected load leaves the shipped ``acceptance.yaml`` working."""
    config = get_acceptance_config()

    assert config["version"] == "1.0"
    assert get_gold_market_rules("global_xau")["trading_days_per_year"] == 252


# ── سند دستیار طلا و نقره: §۲۰، §۲۶، §۲۷.۱، §۲۷.۳ ────────────────────
#
# این تست‌ها قفل می‌کنند که اعداد سند در ``acceptance.yaml`` (منبع واحد) هستند،
# نه هاردکد در گیت سیگنال یا کامپوننت فرانت‌اند.


def test_fee_schedule_is_versioned_and_lists_every_instrument():
    schedule = get_fee_schedule()

    assert schedule["version"] == "1.0"
    assert schedule["last_updated"] == "1405-07-22"
    assert set(schedule["instruments"]) == set(FEE_INSTRUMENTS)


def test_commodity_fund_costs_012_percent_each_side():
    """§۲۷.۱ — تعرفهٔ صندوق کالایی؛ و منشأ آن «فرض» است تا تأیید کارگزار (§۲۸.۲)."""
    terms = get_fee_terms("commodity_fund")

    assert terms["fee_per_side"] == pytest.approx(0.0012)
    assert terms["round_trip_fee_per_side"] == pytest.approx(0.0024)
    assert terms["fee_cap_irr"] is None
    assert terms["provenance"] == "assumption"


def test_certificate_fees_and_caps_match_section_27_1():
    coin = get_fee_terms("coin_certificate")
    bullion = get_fee_terms("bullion_certificate")

    assert coin["fee_per_side"] == pytest.approx(0.00125)
    assert coin["fee_cap_irr"] == 300_000_000
    assert bullion["fee_per_side"] == pytest.approx(0.0024)
    assert bullion["fee_cap_irr"] == 450_000_000


def test_unavailable_instruments_stay_null_not_zero():
    """آتی و اختیار عدد قابل‌اتکا ندارند؛ صفر گذاشتن یک هزینهٔ جعلی می‌سازد."""
    for instrument in ("futures", "option"):
        terms = get_fee_terms(instrument)
        assert terms["fee_per_side"] is None
        assert terms["round_trip_fee_per_side"] is None
        assert terms["provenance"] == "unavailable"


def test_get_fee_terms_unknown_instrument_raises():
    with pytest.raises(KeyError):
        get_fee_terms("not_an_instrument")


def test_signal_filter_holds_the_section_26_thresholds():
    flt = get_signal_filter()

    assert flt["min_net_profit_pct"] == pytest.approx(2.0)
    assert flt["min_risk_reward"] == pytest.approx(2.0)
    assert flt["require_positive_ev"] is True
    # ۲٪ خواستهٔ مالک است؛ ۲ به ۱ پیشنهاد نویسندهٔ سند (§۲۸.۲).
    assert flt["provenance"]["min_net_profit_pct"] == "spec"
    assert flt["provenance"]["min_risk_reward"] == "assumption"


def test_market_hours_match_section_27_3():
    hours = get_market_hours()

    assert hours["sat_to_wed"] == {"pre_open": "11:45", "open": "12:00", "close": "18:00"}
    assert hours["thursday"]["close"] == "15:00"
    assert hours["friday_closed"] is True
    assert hours["price_band_pct"] == pytest.approx(10.0)
    assert hours["emergency_band_pcts"] == [1, 2, 5]
    assert hours["settlement_days"] == 1


def test_section_27_1_required_gross_move_for_the_fund():
    """§۲۰/§۲۷.۱ — هدف ۲٪ + کارمزد ۰٫۲۴٪ رفت‌وبرگشت = ۲٫۲۴٪ پیش از اسپرد و لغزش."""
    schedule = get_fee_schedule()
    trip_pct = schedule["instruments"]["commodity_fund"]["round_trip_fee_per_side"] * 100
    flt = get_signal_filter()

    gross = required_gross_move_pct(
        flt["min_net_profit_pct"],
        buy_fee_pct=trip_pct / 2,
        sell_fee_pct=trip_pct / 2,
    )
    assert gross == pytest.approx(2.24)


def test_required_gross_move_adds_spread_slippage_and_other():
    gross = required_gross_move_pct(
        2.0, 0.12, 0.12, spread_pct=0.3, slippage_pct=0.1, other_pct=0.05
    )
    assert gross == pytest.approx(2.69)


def test_assistant_rules_bundle_is_the_frontend_contract():
    """همین بسته را API به صفحه‌های طلا و نقره می‌دهد."""
    rules = get_assistant_rules()

    assert set(rules) == {"version", "fee_schedule", "signal_filter", "market_hours"}
    assert rules["signal_filter"]["min_risk_reward"] == pytest.approx(2.0)
    assert rules["market_hours"]["sat_to_wed"]["close"] == "18:00"
    assert rules["fee_schedule"]["instruments"]["commodity_fund"]["fee_per_side"] == pytest.approx(0.0012)
