"""Unit tests for macro drivers and resilient gold feed failover.

Covers:
  * AED dirham parity → Dubai implied USD → Tehran spread flag
  * Real-yield / DXY / trend macro posture (inverse TIPS model)
  * Provider failover on error, timeout and stale quotes (>120s)
"""

from __future__ import annotations

import time

import pytest

from services.gold.macro_indicators import (
    AED_PEG,
    GOLD_REPRICING_SPREAD_THRESHOLD,
    MAX_STALENESS_SECONDS,
    calculate_aed_implied_usd,
    evaluate_gold_macro_posture,
    fetch_resilient_gold_spot,
)

NOW = 1_700_000_000.0


def _provider(name: str, result):
    """Mock provider returning ``result`` or raising it when it's an exception."""

    def fetch():
        if isinstance(result, BaseException):
            raise result
        return result

    return {"name": name, "fetch": fetch}


def _quote(price: float, age_seconds: float = 10.0) -> dict:
    return {"price": price, "timestamp": NOW - age_seconds}


class TestAedImpliedUsd:
    def test_peg_constant(self):
        assert pytest.approx(3.6725) == AED_PEG
        assert pytest.approx(1.5) == GOLD_REPRICING_SPREAD_THRESHOLD

    def test_dubai_implied_usd_multiplication(self):
        # AED is quoted in rial; the peg converts it into an implied USD rate.
        result = calculate_aed_implied_usd(1_000_000.0, 3_800_000.0)
        assert result["dubai_implied_usd"] == pytest.approx(3_672_500.0)
        assert result["aed_peg"] == pytest.approx(AED_PEG)

    def test_spread_and_flag_when_tehran_premium_expands(self):
        aed_rate = 1_000_000.0
        dubai = aed_rate * AED_PEG
        tehran = dubai * 1.03472
        result = calculate_aed_implied_usd(aed_rate, tehran)
        assert result["spread_pct"] == pytest.approx(3.472, rel=1e-4)
        assert result["is_flagged"] is True
        assert result["signal"] == "TEHRAN_GOLD_REPRICING_RISK"

    def test_aligned_market_is_not_flagged(self):
        aed_rate = 1_000_000.0
        dubai = aed_rate * AED_PEG
        result = calculate_aed_implied_usd(aed_rate, dubai * 1.004)
        assert result["spread_pct"] == pytest.approx(0.4, rel=1e-9)
        assert result["is_flagged"] is False
        assert result["signal"] == "ALIGNED"

    def test_negative_spread_is_discount_not_reprising_risk(self):
        aed_rate = 1_000_000.0
        dubai = aed_rate * AED_PEG
        result = calculate_aed_implied_usd(aed_rate, dubai * 0.97)
        assert result["spread_pct"] == pytest.approx(-3.0, rel=1e-9)
        assert result["is_flagged"] is False
        assert result["signal"] == "TEHRAN_GOLD_DISCOUNT"

    def test_inputs_are_echoed(self):
        result = calculate_aed_implied_usd(950_000.0, 3_500_000.0)
        assert result["aed_rate"] == pytest.approx(950_000.0)
        assert result["tehran_usd_rate"] == pytest.approx(3_500_000.0)

    @pytest.mark.parametrize("bad_aed", [0.0, -1.0])
    def test_non_positive_aed_raises(self, bad_aed):
        with pytest.raises(ValueError):
            calculate_aed_implied_usd(bad_aed, 3_800_000.0)

    @pytest.mark.parametrize("bad_tehran", [0.0, -1.0])
    def test_non_positive_tehran_rate_raises(self, bad_tehran):
        with pytest.raises(ValueError):
            calculate_aed_implied_usd(1_000_000.0, bad_tehran)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_non_finite_inputs_raise(self, bad):
        with pytest.raises(ValueError):
            calculate_aed_implied_usd(bad, 3_800_000.0)


class TestGoldMacroPosture:
    @staticmethod
    def _posture(tips, dxy, trend, **kwargs):
        """Classic DXY levels: only a *true* DXY series uses 95/105."""
        return evaluate_gold_macro_posture(
            tips, dxy, trend, dxy_series="DXY", **kwargs
        )

    def test_risk_on_bullish_stack(self):
        result = self._posture(0.8, 92.0, "up")
        assert result["real_yield_signal"] == "ACCOMMODATIVE"
        assert result["dxy_signal"] == "WEAK"
        assert result["dxy_threshold_mode"] == "classic"
        assert result["composite_score"] == pytest.approx(3)
        assert result["posture"] == "BULLISH"

    def test_risk_off_bearish_stack(self):
        result = self._posture(2.4, 108.0, "down")
        assert result["real_yield_signal"] == "RESTRICTIVE"
        assert result["dxy_signal"] == "STRONG"
        assert result["composite_score"] == pytest.approx(-3)
        assert result["posture"] == "BEARISH"

    def test_mixed_inputs_are_neutral(self):
        result = self._posture(1.5, 100.0, "sideways")
        assert result["real_yield_signal"] == "NEUTRAL"
        assert result["dxy_signal"] == "NEUTRAL"
        assert result["composite_score"] == pytest.approx(0)
        assert result["posture"] == "NEUTRAL"

    def test_tips_alone_can_drive_bullish_posture(self):
        result = self._posture(0.4, 100.0, "sideways")
        assert result["composite_score"] == pytest.approx(1)
        assert result["posture"] == "BULLISH"

    def test_strong_dollar_alone_can_drive_bearish_posture(self):
        result = self._posture(1.5, 107.0, "sideways")
        assert result["composite_score"] == pytest.approx(-1)
        assert result["posture"] == "BEARISH"

    def test_inverse_relationship_is_expected(self):
        result = self._posture(1.2, 99.0, "up")
        assert result["inverse_correlation_expected"] is True
        assert result["divergence"] is False

    def test_bearish_yields_with_rising_gold_is_divergent(self):
        result = self._posture(2.5, 100.0, "up")
        assert result["divergence"] is True

    def test_trend_is_case_insensitive(self):
        result = self._posture(0.8, 92.0, "UP")
        assert result["gold_trend"] == "up"
        assert result["composite_score"] == pytest.approx(3)

    def test_reasons_are_explained(self):
        result = self._posture(0.8, 92.0, "up")
        assert isinstance(result["reasons"], list)
        assert result["reasons"]

    def test_invalid_trend_raises(self):
        with pytest.raises(ValueError, match="gold_trend"):
            self._posture(1.0, 100.0, "moon")

    @pytest.mark.parametrize("bad_dxy", [0.0, -100.0])
    def test_non_positive_dxy_raises(self, bad_dxy):
        with pytest.raises(ValueError):
            self._posture(1.0, bad_dxy, "up")

    @pytest.mark.parametrize("bad_tips", [float("nan"), float("inf")])
    def test_non_finite_tips_raises(self, bad_tips):
        with pytest.raises(ValueError):
            self._posture(bad_tips, 100.0, "up")

    def test_negative_tips_yield_is_allowed(self):
        result = self._posture(-1.2, 100.0, "sideways")
        assert result["real_yield_signal"] == "ACCOMMODATIVE"

    # ── DTWEXBGS: historical-percentile thresholds (no fixed 95/105) ──────

    @staticmethod
    def _broad_history() -> list[float]:
        # 40 evenly spaced observations 90..129: p20=97.8, p80=121.2.
        return [90.0 + i for i in range(40)]

    def test_broad_dollar_uses_percentile_thresholds(self):
        history = self._broad_history()

        weak = evaluate_gold_macro_posture(
            1.5, 95.0, "sideways", dxy_history=history
        )
        strong = evaluate_gold_macro_posture(
            1.5, 125.0, "sideways", dxy_history=history
        )
        neutral = evaluate_gold_macro_posture(
            1.5, 110.0, "sideways", dxy_history=history
        )

        assert weak["dxy_threshold_mode"] == "percentile"
        assert weak["dxy_signal"] == "WEAK"
        assert weak["dxy_percentile_low"] == pytest.approx(97.8, abs=0.1)
        assert weak["dxy_percentile_high"] == pytest.approx(121.2, abs=0.1)
        assert strong["dxy_signal"] == "STRONG"
        assert neutral["dxy_signal"] == "NEUTRAL"
        # The classic 95/105 constants must not leak into broad-index mode:
        # 95 would be NEUTRAL under 95/105, but is WEAK at the p20 threshold.
        assert weak["dxy_signal"] != "NEUTRAL"

    def test_broad_dollar_without_enough_history_is_insufficient(self):
        result = evaluate_gold_macro_posture(
            1.5,
            108.0,
            "sideways",
            dxy_history=[100.0] * 29,
            min_samples=30,
        )

        assert result["dxy_signal"] == "INSUFFICIENT_HISTORY"
        assert result["posture"] == "insufficient_history"
        assert result["composite_score"] is None
        assert result["dxy_history_samples"] == 29

    def test_classic_dxy_ignores_history(self):
        result = evaluate_gold_macro_posture(
            1.5,
            92.0,
            "sideways",
            dxy_series="DXY",
            dxy_history=[200.0] * 100,
        )

        assert result["dxy_signal"] == "WEAK"
        assert result["dxy_threshold_mode"] == "classic"
        assert result["dxy_percentile_low"] is None
        assert result["dxy_percentile_high"] is None


class TestResilientGoldSpot:
    def test_primary_provider_wins(self):
        providers = [
            _provider("brsapi", _quote(2_400.0)),
            _provider("yahoo", _quote(2_401.0)),
        ]
        result = fetch_resilient_gold_spot(providers, now=NOW)
        assert result["price"] == pytest.approx(2_400.0)
        assert result["provider"] == "brsapi"
        assert result["fallback_used"] is False
        assert result["sources_tried"] == 1
        assert result["attempts"][0]["status"] == "ok"
        assert result["attempts"][0]["latency_ms"] >= 0

    def test_http_error_switches_to_fallback(self):
        providers = [
            _provider("brsapi", RuntimeError("HTTP 502 Bad Gateway")),
            _provider("yahoo", _quote(2_401.0)),
        ]
        result = fetch_resilient_gold_spot(providers, now=NOW)
        assert result["provider"] == "yahoo"
        assert result["price"] == pytest.approx(2_401.0)
        assert result["fallback_used"] is True
        assert result["attempts"][0]["status"] == "error"
        assert "HTTP 502" in result["attempts"][0]["error"]

    def test_stale_quote_switches_to_fallback(self):
        providers = [
            _provider("brsapi", _quote(2_400.0, age_seconds=300.0)),
            _provider("alpha", _quote(2_402.0, age_seconds=5.0)),
        ]
        result = fetch_resilient_gold_spot(providers, now=NOW)
        assert result["provider"] == "alpha"
        assert result["attempts"][0]["status"] == "stale"
        assert result["fallback_used"] is True

    def test_staleness_boundary_is_120_seconds(self):
        fresh = fetch_resilient_gold_spot(
            [_provider("brsapi", _quote(2_400.0, age_seconds=MAX_STALENESS_SECONDS))],
            now=NOW,
        )
        assert fresh["provider"] == "brsapi"
        assert fresh["age_seconds"] == pytest.approx(MAX_STALENESS_SECONDS)

        stale = fetch_resilient_gold_spot(
            [
                _provider("brsapi", _quote(2_400.0, age_seconds=MAX_STALENESS_SECONDS + 1)),
                _provider("yahoo", _quote(2_401.0, age_seconds=1.0)),
            ],
            now=NOW,
        )
        assert stale["provider"] == "yahoo"

    def test_timeout_switches_to_fallback_without_blocking(self):
        def slow():
            time.sleep(0.3)
            return _quote(2_400.0)

        providers = [
            {"name": "brsapi", "fetch": slow},
            _provider("yahoo", _quote(2_401.0)),
        ]
        started = time.monotonic()
        result = fetch_resilient_gold_spot(providers, timeout_seconds=0.05, now=NOW)
        elapsed = time.monotonic() - started
        assert result["provider"] == "yahoo"
        assert result["attempts"][0]["status"] == "timeout"
        assert elapsed < 1.0

    def test_all_providers_failing_raises_with_attempts(self):
        providers = [
            _provider("brsapi", RuntimeError("HTTP 500")),
            _provider("yahoo", _quote(2_400.0, age_seconds=500.0)),
        ]
        with pytest.raises(RuntimeError, match="All gold price providers failed") as info:
            fetch_resilient_gold_spot(providers, now=NOW)
        assert [attempt["status"] for attempt in info.value.attempts] == [
            "error",
            "stale",
        ]
        assert all(attempt["latency_ms"] >= 0 for attempt in info.value.attempts)

    def test_non_positive_price_is_treated_as_failure(self):
        providers = [
            _provider("brsapi", {"price": 0.0, "timestamp": NOW}),
            _provider("yahoo", _quote(2_401.0)),
        ]
        result = fetch_resilient_gold_spot(providers, now=NOW)
        assert result["provider"] == "yahoo"
        assert result["attempts"][0]["status"] == "error"

    def test_missing_timestamp_is_treated_as_failure(self):
        providers = [
            _provider("brsapi", {"price": 2_400.0}),
            _provider("yahoo", _quote(2_401.0)),
        ]
        result = fetch_resilient_gold_spot(providers, now=NOW)
        assert result["provider"] == "yahoo"
        assert result["attempts"][0]["status"] == "error"

    def test_object_provider_interface(self):
        class Provider:
            name = "brsapi"

            def fetch(self):
                return {"price": 2_399.5, "timestamp": NOW - 2}

        result = fetch_resilient_gold_spot([Provider()], now=NOW)
        assert result["provider"] == "brsapi"
        assert result["price"] == pytest.approx(2_399.5)
        assert result["age_seconds"] == pytest.approx(2.0)

    def test_empty_provider_list_raises(self):
        with pytest.raises(ValueError, match="providers"):
            fetch_resilient_gold_spot([])

    def test_invalid_timeout_raises(self):
        with pytest.raises(ValueError):
            fetch_resilient_gold_spot([_provider("brsapi", _quote(2_400.0))], timeout_seconds=0)

    def test_provider_executor_is_bounded(self):
        from services.gold.macro_indicators import (
            MAX_PROVIDER_WORKERS,
            _get_provider_executor,
        )

        assert MAX_PROVIDER_WORKERS >= 2
        assert _get_provider_executor()._max_workers == MAX_PROVIDER_WORKERS
