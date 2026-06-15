from __future__ import annotations

from backtesting.reporting.summary_report import SummaryReport
from backtesting.types import BacktestResult


class PDFReport:
    @staticmethod
    def generate(result: BacktestResult) -> bytes:
        try:
            import io

            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.pdfgen import canvas

            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            width, height = A4
            y = height - 2 * cm

            c.setFont("Helvetica-Bold", 16)
            c.drawString(2 * cm, y, f"Report: {result.strategy_name}")
            y -= 1 * cm

            summary = SummaryReport.generate(result)
            c.setFont("Helvetica", 12)
            for key, value in summary.items():
                c.drawString(2 * cm, y, f"{key}: {value}")
                y -= 0.5 * cm
                if y < 2 * cm:
                    c.showPage()
                    y = height - 2 * cm

            c.save()
            return buf.getvalue()
        except ImportError:
            return b"PDF generation requires reportlab: pip install reportlab"

    @staticmethod
    def save(result: BacktestResult, filepath: str) -> None:
        data = PDFReport.generate(result)
        with open(filepath, "wb") as f:
            f.write(data)
