from __future__ import annotations

from typing import Any


class NotificationTemplates:
    @staticmethod
    def signal_alert(symbol: str, signal_type: str, score: float, confidence: float, reason: str = "") -> str:
        lines = [
            f"Signal Alert: {symbol}",
            f"Type: {signal_type.upper()}",
            f"Score: {score:.2f}",
            f"Confidence: {confidence:.2%}",
        ]
        if reason:
            lines.append(f"Reason: {reason}")
        return "\n".join(lines)

    @staticmethod
    def recommendation_update(symbol: str, action: str, target_price: float | None, rationale: str) -> str:
        lines = [f"Recommendation Update: {symbol}", f"Action: {action.upper()}"]
        if target_price:
            lines.append(f"Target Price: {target_price:,.0f}")
        lines.append(f"Rationale: {rationale}")
        return "\n".join(lines)

    @staticmethod
    def market_summary(summary: dict[str, Any]) -> str:
        lines = ["Market Summary"]
        for key, value in summary.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def report_ready(report_name: str, report_type: str, summary: str = "") -> str:
        lines = [f"Report Ready: {report_name}", f"Type: {report_type}"]
        if summary:
            lines.append(f"Summary: {summary}")
        return "\n".join(lines)

    @staticmethod
    def error_alert(error_type: str, message: str, details: dict[str, Any] | None = None) -> str:
        lines = [f"Error Alert: {error_type}", f"Message: {message}"]
        if details:
            for k, v in details.items():
                lines.append(f"{k}: {v}")
        return "\n".join(lines)

    @staticmethod
    def job_status(job_name: str, status: str, started_at: str = "", duration: str = "") -> str:
        lines = [f"Job: {job_name}", f"Status: {status}"]
        if started_at:
            lines.append(f"Started: {started_at}")
        if duration:
            lines.append(f"Duration: {duration}")
        return "\n".join(lines)

    @staticmethod
    def html_wrap(body: str, title: str = "Notification") -> str:
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:sans-serif;padding:20px;max-width:600px;margin:auto">
<div style="border:1px solid #ddd;border-radius:8px;padding:20px">
{body}
</div></body></html>"""

    @staticmethod
    def signal_html_table(signals: list[dict[str, Any]]) -> str:
        rows = "".join(
            f"<tr><td>{s.get('symbol', '')}</td><td>{s.get('signal_type', '')}</td>"
            f"<td>{s.get('score', 0):.2f}</td><td>{s.get('confidence', 0):.2%}</td></tr>"
            for s in signals
        )
        return f"""<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
<thead><tr><th>Symbol</th><th>Type</th><th>Score</th><th>Confidence</th></tr></thead>
<tbody>{rows}</tbody></table>"""
