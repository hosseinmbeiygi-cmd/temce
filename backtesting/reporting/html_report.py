from __future__ import annotations

from backtesting.reporting.equity_curve import EquityCurveReport
from backtesting.reporting.summary_report import SummaryReport
from backtesting.reporting.trade_log_report import TradeLogReport
from backtesting.types import BacktestResult
from core.paths import validate_safe_path


class HTMLReport:
    @staticmethod
    def generate(result: BacktestResult) -> str:
        summary = SummaryReport.generate(result)
        equity = EquityCurveReport.generate(result)
        trades = TradeLogReport.generate(result)

        [p.nav for p in result.equity_curve]
        str(equity).replace("'", '"')
        rows = "".join(
            f"<tr><td>{t['order_id']}</td><td>{t['instrument_id']}</td>"
            f"<td>{t['side']}</td><td>{t['quantity']}</td>"
            f"<td>{t['price']:,.0f}</td><td>{t['total_value']:,.0f}</td></tr>"
            for t in trades
        )

        html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="UTF-8"><title>{result.strategy_name} - گزارش</title>
<style>
body {{ font-family: Tahoma, Arial; margin: 20px; direction: rtl; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
th {{ background-color: #4CAF50; color: white; }}
h1 {{ color: #333; }}
</style></head>
<body>
<h1>گزارش بازدهی: {result.strategy_name}</h1>
<h2>خلاصه</h2>
<table>
<tr><th>شاخص</th><th>مقدار</th></tr>
<tr><td>سرمایه اولیه</td><td>{summary["initial_capital"]:,.0f}</td></tr>
<tr><td>سرمایه نهایی</td><td>{summary["final_capital"]:,.0f}</td></tr>
<tr><td>بازده کل</td><td>{summary["total_return_pct"]:.2f}%</td></tr>
<tr><td>تعداد معاملات</td><td>{summary["total_trades"]}</td></tr>
<tr><td>نسبت شارپ</td><td>{summary["sharpe_ratio"]:.4f}</td></tr>
<tr><td>حداکثر کاهش</td><td>{summary["max_drawdown"]:.2f}%</td></tr>
</table>
<h2>فهرست معاملات</h2>
<table><tr><th>کد</th><th>نماد</th><th>طرف</th><th>تعداد</th><th>قیمت</th><th>ارزش</th></tr>{rows}</table>
</body></html>"""
        return html

    @staticmethod
    def save(result: BacktestResult, filepath: str) -> None:
        safe = validate_safe_path(filepath)
        html = HTMLReport.generate(result)
        safe.write_text(html, encoding="utf-8")
