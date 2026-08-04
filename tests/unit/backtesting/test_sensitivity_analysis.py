from __future__ import annotations

from backtesting.analytics.sensitivity_analysis import (
    DefaultSensitivityParameters,
    SensitivityAnalysis,
    SensitivityParameter,
)


class TestSensitivityAnalysis:
    def test_analyze_parameter(self):
        sa = SensitivityAnalysis()
        param = SensitivityParameter("commission_pct", 0.0035, 0.001, 0.01, steps=5)
        result = sa.analyze_parameter(param, lambda x: {"total_return_pct": 25.0 - x * 100})
        assert result.parameter_name == "commission_pct"
        assert len(result.values) == 5
        assert len(result.metric_values) == 5

    def test_elasticity_calculation(self):

        sa = SensitivityAnalysis()
        param = SensitivityParameter("slippage_bps", 10, 0, 50, steps=6)

        def metric(x):
            return {"total_return_pct": 30.0 - x * 0.5}

        result = sa.analyze_parameter(param, metric)
        assert result.elasticity != 0

    def test_impact_pct(self):

        sa = SensitivityAnalysis()
        param = SensitivityParameter("test_param", 5, 0, 10, steps=3)

        def metric(x):
            return {"total_return_pct": 10.0 + x}

        result = sa.analyze_parameter(param, metric)
        assert result.impact_pct >= 0

    def test_linearity_check(self):

        sa = SensitivityAnalysis()
        param = SensitivityParameter("test_param", 5, 0, 10, steps=3)

        def metric(x):
            return {"total_return_pct": float(x)}

        result = sa.analyze_parameter(param, metric)
        assert result.is_linear

    def test_analyze_multiple(self):

        sa = SensitivityAnalysis()
        params = [
            SensitivityParameter("commission", 0.0035, 0.001, 0.01, steps=3),
            SensitivityParameter("slippage", 10, 0, 50, steps=3),
        ]

        def metric(params_dict):
            return {
                "total_return_pct": 25.0 - params_dict.get("commission", 0) * 100 - params_dict.get("slippage", 0) * 0.5
            }

        report = sa.analyze_multiple(params, metric)
        assert len(report.parameters) == 2
        assert len(report.tornado_data) == 2

    def test_tornado_data(self):

        sa = SensitivityAnalysis()
        param = SensitivityParameter("test", 5, 0, 10, steps=3)
        sa.analyze_parameter(param, lambda x: {"value": float(x)})
        tornado = sa.get_tornado_data()
        assert "test" in tornado

    def test_most_sensitive(self):

        sa = SensitivityAnalysis()
        p1 = SensitivityParameter("high_impact", 5, 0, 10, steps=3)
        p2 = SensitivityParameter("low_impact", 5, 4.5, 5.5, steps=3)
        sa.analyze_parameter(p1, lambda x: {"ret": float(x * 10)})
        sa.analyze_parameter(p2, lambda x: {"ret": float(x)})
        top = sa.get_most_sensitive(1)
        assert top[0] == "high_impact"

    def test_default_parameters(self):

        params = DefaultSensitivityParameters.get_defaults()
        assert len(params) == 5
        names = [p.name for p in params]
        assert "commission_pct" in names
        assert "slippage_bps" in names

    def test_clear(self):

        sa = SensitivityAnalysis()
        param = SensitivityParameter("test", 5, 0, 10, steps=3)
        sa.analyze_parameter(param, lambda x: {"ret": float(x)})
        sa.clear()
        assert len(sa.get_most_sensitive()) == 0
