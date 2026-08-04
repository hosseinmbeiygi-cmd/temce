from __future__ import annotations

from backtesting.reporting.excel_report import ExcelReport, ExcelReportConfig


class TestExcelReport:
    def test_generate_metrics_only(self):

        report = ExcelReport()
        sheets = report.generate(metrics={"total_return_pct": 25.5, "sharpe_ratio": 1.5})
        assert len(sheets) >= 1
        assert sheets[0].name == "Metrics"

    def test_generate_with_equity_curve(self):

        report = ExcelReport()
        curve = [
            {
                "date": "2024-01-01",
                "nav": 1_000_000_000,
                "cash": 500_000_000,
                "positions_value": 500_000_000,
                "return_pct": 0.0,
            }
        ]
        sheets = report.generate(metrics={"return": 10.0}, equity_curve=curve)
        assert any(s.name == "Equity Curve" for s in sheets)

    def test_generate_with_trades(self):

        report = ExcelReport()
        trades = [
            {
                "date": "2024-01-01",
                "instrument_id": "IRAN123",
                "side": "buy",
                "quantity": 1000,
                "price": 10000,
                "pnl": 0,
                "commission": 5000,
                "reason": "signal",
            }
        ]
        sheets = report.generate(metrics={"return": 10.0}, trades=trades)
        assert any(s.name == "Trades" for s in sheets)

    def test_generate_with_drawdown(self):

        report = ExcelReport()
        dd = [
            {
                "date": "2024-01-01",
                "drawdown_pct": 5.0,
                "peak": 1_000_000_000,
                "trough": 950_000_000,
                "duration": 10,
            }
        ]
        sheets = report.generate(metrics={"return": 10.0}, drawdown=dd)
        assert any(s.name == "Drawdown" for s in sheets)

    def test_generate_with_monthly_returns(self):

        report = ExcelReport()
        mr = [{"month": "2024-01", "return_pct": 2.5, "cumulative_pct": 2.5}]
        sheets = report.generate(metrics={"return": 10.0}, monthly_returns=mr)
        assert any(s.name == "Monthly Returns" for s in sheets)

    def test_generate_with_attribution(self):

        config = ExcelReportConfig(include_attribution=True)
        report = ExcelReport(config)
        sheets = report.generate(
            metrics={"return": 10.0},
            attribution={"factor_A": {"contribution_pct": 5.0, "exposure": 0.5}},
        )
        assert any(s.name == "Attribution" for s in sheets)

    def test_generate_with_sensitivity(self):

        config = ExcelReportConfig(include_sensitivity=True)
        report = ExcelReport(config)
        sheets = report.generate(
            metrics={"return": 10.0},
            sensitivity={
                "commission": {
                    "base_value": 0.0035,
                    "low_impact": 24.0,
                    "high_impact": 22.0,
                    "elasticity": 0.5,
                }
            },
        )
        assert any(s.name == "Sensitivity" for s in sheets)

    def test_custom_config(self):

        config = ExcelReportConfig(title="Custom Report", author="Tester", include_charts=False)
        report = ExcelReport(config)
        assert report.config.title == "Custom Report"
        assert report.config.author == "Tester"

    def test_disabled_sections(self):

        config = ExcelReportConfig(include_metrics=False, include_trades=False, include_equity_curve=False)
        report = ExcelReport(config)
        sheets = report.generate(metrics={"return": 10.0})
        assert len(sheets) == 0

    def test_metrics_with_various_types(self):

        report = ExcelReport()
        sheets = report.generate(
            metrics={
                "string_val": "test",
                "int_val": 42,
                "float_val": 3.14159,
                "none_val": None,
            }
        )
        sheet = sheets[0]
        assert len(sheet.rows) >= 3
