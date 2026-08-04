from __future__ import annotations

from datetime import datetime

from backtesting.risk.stress_testing import (
    HistoricalScenario,
    StressScenario,
    StressTesting,
)


class TestStressTesting:
    def test_add_scenario(self):
        st = StressTesting()
        st.add_scenario(StressScenario(name="test", market_drop_pct=10.0, volatility_shock_pct=20.0))
        assert len(st.scenarios) == 1

    def test_run_scenarios(self):
        st = StressTesting()
        st.add_scenario(StressScenario(name="crash", market_drop_pct=10.0, volatility_shock_pct=20.0))
        results = st.run(portfolio_value=1_000_000_000)
        assert len(results) == 1
        assert results[0]["portfolio_before"] == 1_000_000_000
        assert results[0]["portfolio_after"] < 1_000_000_000
        assert results[0]["impact"] > 0

    def test_run_multiple_scenarios(self):
        st = StressTesting()
        st.add_scenario(StressScenario(name="mild", market_drop_pct=5.0, volatility_shock_pct=10.0))
        st.add_scenario(StressScenario(name="severe", market_drop_pct=20.0, volatility_shock_pct=50.0))
        results = st.run(portfolio_value=1_000_000_000)
        assert len(results) == 2
        assert results[1]["impact"] > results[0]["impact"]

    def test_default_iran_scenarios(self):
        st = StressTesting()
        st.add_default_iran_scenarios()
        assert len(st.scenarios) == 7

    def test_historical_scenario(self):
        st = StressTesting()
        hs = HistoricalScenario(
            name="test_historical",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 3, 1),
            market_drop_pct=15.0,
            volatility_shock_pct=40.0,
        )
        result = st.run_historical_scenario(portfolio_value=1_000_000_000, scenario=hs)
        assert result["portfolio_after"] < 1_000_000_000
        assert "start_date" in result["details"]

    def test_add_historical_scenario(self):
        st = StressTesting()
        st.add_historical_scenario(
            HistoricalScenario(
                name="test",
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 3, 1),
                market_drop_pct=10.0,
                volatility_shock_pct=20.0,
            )
        )
        assert len(st.historical_scenarios) == 1

    def test_default_historical_scenarios(self):
        st = StressTesting()
        st.add_default_historical_scenarios()
        assert len(st.historical_scenarios) == 3

    def test_run_all_historical(self):
        st = StressTesting()
        st.add_default_historical_scenarios()
        results = st.run_all_historical(portfolio_value=1_000_000_000)
        assert len(results) == 3

    def test_monte_carlo(self):
        st = StressTesting()
        result = st.run_monte_carlo(portfolio_value=1_000_000_000, n_simulations=1000, seed=42)
        assert "mean" in result
        assert "var_95" in result
        assert "var_99" in result
        assert "cvar_95" in result
        assert result["mean"] > 0

    def test_worst_case(self):
        st = StressTesting()
        st.add_scenario(StressScenario(name="mild", market_drop_pct=5.0, volatility_shock_pct=10.0))
        st.add_scenario(StressScenario(name="severe", market_drop_pct=20.0, volatility_shock_pct=50.0))
        worst = st.run_worst_case(portfolio_value=1_000_000_000)
        assert worst["impact_pct"] > 0

    def test_survival_check(self):
        st = StressTesting()
        st.add_scenario(StressScenario(name="extreme", market_drop_pct=60.0, volatility_shock_pct=100.0))
        results = st.run(portfolio_value=1_000_000_000)
        assert not results[0]["survived"]

    def test_clear(self):
        st = StressTesting()
        st.add_scenario(StressScenario(name="test", market_drop_pct=10.0, volatility_shock_pct=20.0))
        st.add_default_historical_scenarios()
        st.clear()
        assert len(st.scenarios) == 0
        assert len(st.historical_scenarios) == 0
