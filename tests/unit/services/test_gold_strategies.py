"""Hand-computed tests for the gold option strategy builder.

All payoffs are per one unit of the underlying unless a quantity is given.
Long legs are positive, short legs are negative.
"""

from __future__ import annotations

import pytest

from services.gold.black76_engine import black76_price
from services.gold.strategies import (
    analyze_strategy,
    build_covered_call,
    build_iron_condor,
    build_straddle,
    build_strangle,
    build_vertical_spread,
)


class TestStraddle:
    def test_long_straddle_payoff_breakevens_and_extrema(self):
        result = build_straddle(100.0, 5.0, 4.0, expiry_price=100.0)

        assert result["net_debit"] == pytest.approx(9.0)
        assert result["expiry_payoff"] == pytest.approx(0.0)
        assert result["expiry_pnl"] == pytest.approx(-9.0)
        assert result["breakevens"] == pytest.approx([91.0, 109.0])
        assert result["max_loss"] == pytest.approx(9.0)
        assert result["max_profit"] is None
        assert result["max_profit_unbounded"] is True
        assert result["max_loss_unbounded"] is False

    def test_long_straddle_payoff_above_and_below_strike(self):
        below = build_straddle(100.0, 5.0, 4.0, expiry_price=80.0)
        above = build_straddle(100.0, 5.0, 4.0, expiry_price=120.0)

        assert below["expiry_payoff"] == pytest.approx(20.0)
        assert below["expiry_pnl"] == pytest.approx(11.0)
        assert above["expiry_payoff"] == pytest.approx(20.0)
        assert above["expiry_pnl"] == pytest.approx(11.0)

    def test_straddle_at_expiry_is_discounted_intrinsic(self):
        result = build_straddle(
            100.0,
            5.0,
            4.0,
            expiry_price=110.0,
            forward_price=100.0,
            risk_free_rate=0.03,
            days_to_expiry=30,
        )
        assert result["expiry_pnl"] == pytest.approx(1.0)


class TestStrangle:
    def test_long_strangle_hand_computed(self):
        result = build_strangle(90.0, 110.0, 3.0, 2.0, expiry_price=100.0)

        assert result["net_debit"] == pytest.approx(5.0)
        assert result["expiry_pnl"] == pytest.approx(-5.0)
        assert result["breakevens"] == pytest.approx([85.0, 115.0])
        assert result["max_loss"] == pytest.approx(5.0)
        assert result["max_profit"] is None
        assert result["max_profit_unbounded"] is True

    def test_long_strangle_upper_payoff(self):
        result = build_strangle(90.0, 110.0, 3.0, 2.0, expiry_price=120.0)
        assert result["expiry_payoff"] == pytest.approx(10.0)
        assert result["expiry_pnl"] == pytest.approx(5.0)


class TestVerticalSpreads:
    def test_long_call_vertical_hand_computed(self):
        result = build_vertical_spread(
            "call", 100.0, 110.0, 5.0, 2.0, expiry_price=105.0
        )

        assert result["net_debit"] == pytest.approx(3.0)
        assert result["expiry_payoff"] == pytest.approx(5.0)
        assert result["expiry_pnl"] == pytest.approx(2.0)
        assert result["breakevens"] == pytest.approx([103.0])
        assert result["max_profit"] == pytest.approx(7.0)
        assert result["max_loss"] == pytest.approx(3.0)
        assert result["max_profit_unbounded"] is False
        assert result["max_loss_unbounded"] is False

    @pytest.mark.parametrize(
        ("price", "expected_pnl"),
        [(90.0, -3.0), (100.0, -3.0), (110.0, 7.0), (130.0, 7.0)],
    )
    def test_long_call_vertical_boundaries(self, price, expected_pnl):
        result = build_vertical_spread(
            "call", 100.0, 110.0, 5.0, 2.0, expiry_price=price
        )
        assert result["expiry_pnl"] == pytest.approx(expected_pnl)

    def test_long_put_vertical_hand_computed(self):
        result = build_vertical_spread(
            "put", 100.0, 90.0, 5.0, 2.0, expiry_price=80.0
        )

        assert result["net_debit"] == pytest.approx(3.0)
        assert result["expiry_payoff"] == pytest.approx(10.0)
        assert result["expiry_pnl"] == pytest.approx(7.0)
        assert result["breakevens"] == pytest.approx([97.0])
        assert result["max_profit"] == pytest.approx(7.0)
        assert result["max_loss"] == pytest.approx(3.0)


class TestIronCondor:
    def test_iron_condor_hand_computed(self):
        result = build_iron_condor(
            90.0,
            95.0,
            105.0,
            110.0,
            2.0,
            4.0,
            4.0,
            2.0,
            expiry_price=100.0,
        )

        assert result["net_debit"] == pytest.approx(-4.0)
        assert result["net_credit"] == pytest.approx(4.0)
        assert result["expiry_pnl"] == pytest.approx(4.0)
        assert result["breakevens"] == pytest.approx([91.0, 109.0])
        assert result["max_profit"] == pytest.approx(4.0)
        assert result["max_loss"] == pytest.approx(1.0)
        assert result["max_profit_unbounded"] is False
        assert result["max_loss_unbounded"] is False

    @pytest.mark.parametrize(
        ("price", "expected_pnl"),
        [(0.0, -1.0), (90.0, -1.0), (95.0, 4.0), (105.0, 4.0), (110.0, -1.0)],
    )
    def test_iron_condor_boundaries(self, price, expected_pnl):
        result = build_iron_condor(
            90.0,
            95.0,
            105.0,
            110.0,
            2.0,
            4.0,
            4.0,
            2.0,
            expiry_price=price,
        )
        assert result["expiry_pnl"] == pytest.approx(expected_pnl)


class TestCoveredCall:
    def test_covered_call_hand_computed(self):
        result = build_covered_call(
            100.0, 110.0, 5.0, expiry_price=120.0
        )

        assert result["net_debit"] == pytest.approx(95.0)
        assert result["expiry_payoff"] == pytest.approx(110.0)
        assert result["expiry_pnl"] == pytest.approx(15.0)
        assert result["breakevens"] == pytest.approx([95.0])
        assert result["max_profit"] == pytest.approx(15.0)
        assert result["max_loss"] == pytest.approx(95.0)
        assert result["max_profit_unbounded"] is False
        assert result["max_loss_unbounded"] is False

    @pytest.mark.parametrize(
        ("price", "expected_pnl"),
        [(0.0, -95.0), (95.0, 0.0), (100.0, 5.0), (110.0, 15.0), (150.0, 15.0)],
    )
    def test_covered_call_boundaries(self, price, expected_pnl):
        result = build_covered_call(100.0, 110.0, 5.0, expiry_price=price)
        assert result["expiry_pnl"] == pytest.approx(expected_pnl)


class TestPreExpiryAndValidation:
    def test_pre_expiry_value_uses_black76_legs(self):
        call_iv = 0.25
        put_iv = 0.30
        remaining_days = 15
        pre_forward = 105.0
        result = build_straddle(
            100.0,
            5.0,
            4.0,
            expiry_price=105.0,
            forward_price=100.0,
            risk_free_rate=0.03,
            days_to_expiry=30,
            pre_expiry_days=remaining_days,
            pre_expiry_forward=pre_forward,
            call_iv=call_iv,
            put_iv=put_iv,
        )

        T = remaining_days / 365.0
        expected_value = black76_price(
            pre_forward, 100.0, T, 0.03, call_iv, "call"
        ) + black76_price(pre_forward, 100.0, T, 0.03, put_iv, "put")
        assert result["pre_expiry_value"] == pytest.approx(expected_value)
        assert result["pre_expiry_pnl"] == pytest.approx(expected_value - 9.0)

    def test_pre_expiry_requires_iv(self):
        result = build_straddle(
            100.0,
            5.0,
            4.0,
            expiry_price=100.0,
            pre_expiry_days=15,
            pre_expiry_forward=105.0,
        )
        assert result["pre_expiry_value"] is None
        assert "iv" in result["pre_expiry_error"]

    def test_analyze_strategy_rejects_unknown_option_type(self):
        with pytest.raises(ValueError, match="option_type"):
            analyze_strategy(
                [
                    {
                        "option_type": "straddle",
                        "strike": 100.0,
                        "quantity": 1.0,
                        "premium": 5.0,
                    }
                ],
                expiry_price=100.0,
            )

    def test_analyze_strategy_rejects_negative_premium(self):
        with pytest.raises(ValueError, match="premium"):
            analyze_strategy(
                [
                    {
                        "option_type": "call",
                        "strike": 100.0,
                        "quantity": 1.0,
                        "premium": -1.0,
                    }
                ],
                expiry_price=100.0,
            )

    def test_vertical_requires_matching_option_type(self):
        with pytest.raises(ValueError, match="option_type"):
            build_vertical_spread(
                "future", 100.0, 110.0, 5.0, 2.0, expiry_price=105.0
            )
