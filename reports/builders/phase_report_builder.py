"""Phase Report Builder — generates reports for Smart Money phase analysis.

Creates PDF/Excel reports showing phase distribution, transitions,
and performance metrics for monitored symbols.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Phase labels in Persian
PHASE_LABELS: dict[str, str] = {
    "confirmed_smart_money": "پول هوشمند",
    "breakout_ready": "آماده شکست",
    "float_lock": "قفل شناور",
    "active_absorption": "جذب فعال",
    "early_accumulation": "تجمع اولیه",
    "neutral": "خنثی",
}

PHASE_COLORS: dict[str, str] = {
    "confirmed_smart_money": "#22c55e",
    "breakout_ready": "#06b6d4",
    "float_lock": "#8b5cf6",
    "active_absorption": "#f59e0b",
    "early_accumulation": "#3b82f6",
    "neutral": "#64748b",
}


class PhaseReportBuilder:
    """Builds phase analysis reports."""

    def __init__(self) -> None:
        self._data: list[dict[str, Any]] = []
        self._transitions: list[dict[str, Any]] = []

    def add_symbol_data(
        self,
        symbol: str,
        phase: str,
        smc_score: float,
        scores: dict[str, float],
        timestamp: float = 0,
    ) -> None:
        """Add symbol phase data to the report."""
        self._data.append({
            "symbol": symbol,
            "phase": phase,
            "phase_label": PHASE_LABELS.get(phase, phase),
            "smc_score": smc_score,
            "smc_pct": round(smc_score * 100, 1),
            "scores": scores,
            "timestamp": timestamp or datetime.now().timestamp(),
        })

    def add_transition(
        self,
        symbol: str,
        old_phase: str,
        new_phase: str,
        smc_score: float,
        timestamp: float,
    ) -> None:
        """Add a phase transition to the report."""
        self._transitions.append({
            "symbol": symbol,
            "old_phase": old_phase,
            "old_label": PHASE_LABELS.get(old_phase, old_phase),
            "new_phase": new_phase,
            "new_label": PHASE_LABELS.get(new_phase, new_phase),
            "smc_score": smc_score,
            "timestamp": timestamp,
        })

    def build_summary(self) -> dict[str, Any]:
        """Build summary statistics."""
        if not self._data:
            return {"total": 0, "phases": {}, "avg_smc": 0}

        # Phase distribution
        phase_counts: dict[str, int] = {}
        for item in self._data:
            phase = item["phase"]
            phase_counts[phase] = phase_counts.get(phase, 0) + 1

        # Average SMC
        avg_smc = sum(d["smc_score"] for d in self._data) / len(self._data)

        # Bullish vs bearish
        bullish_phases = {"confirmed_smart_money", "breakout_ready", "float_lock", "active_absorption"}
        bullish_count = sum(1 for d in self._data if d["phase"] in bullish_phases)

        return {
            "total": len(self._data),
            "phases": phase_counts,
            "avg_smc": round(avg_smc, 4),
            "avg_smc_pct": round(avg_smc * 100, 1),
            "bullish_count": bullish_count,
            "bearish_count": len(self._data) - bullish_count,
            "bullish_ratio": round(bullish_count / len(self._data) * 100, 1) if self._data else 0,
            "transitions_count": len(self._transitions),
        }

    def build_excel_data(self) -> list[dict[str, Any]]:
        """Build data for Excel export."""
        rows = []
        for item in sorted(self._data, key=lambda x: x["smc_score"], reverse=True):
            rows.append({
                "نماد": item["symbol"],
                "فاز": item["phase_label"],
                "امتیاز SMC": item["smc_pct"],
                "تجمع": round(item["scores"].get("accumulation", 0) * 100, 1),
                "جذب": round(item["scores"].get("absorption", 0) * 100, 1),
                "قفل شناور": round(item["scores"].get("float_lock", 0) * 100, 1),
                "شکست": round(item["scores"].get("breakout_readiness", 0) * 100, 1),
            })
        return rows

    def build_html(self) -> str:
        """Build HTML report."""
        summary = self.build_summary()

        html = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <title>گزارش فازهای پول هوشمند</title>
    <style>
        body {{ font-family: Tahoma, Arial; margin: 20px; background: #1a1a2e; color: #e0e0e0; }}
        h1 {{ color: #06b6d4; text-align: center; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: #16213e; padding: 15px; border-radius: 10px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #22c55e; }}
        .stat-label {{ font-size: 12px; color: #888; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 10px; text-align: right; border-bottom: 1px solid #333; }}
        th {{ background: #16213e; color: #06b6d4; }}
        .phase-badge {{ padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>گزارش فازهای پول هوشمند</h1>
    <p style="text-align: center; color: #888;">تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

    <div class="summary">
        <div class="stat-card">
            <div class="stat-value">{summary['total']}</div>
            <div class="stat-label">تعداد نمادها</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{summary['avg_smc_pct']}%</div>
            <div class="stat-label">میانگین SMC</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{summary['bullish_count']}</div>
            <div class="stat-label">فاز صعودی</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{summary['bullish_ratio']}%</div>
            <div class="stat-label">نسبة صعودی</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>نماد</th>
                <th>فاز</th>
                <th>SMC</th>
                <th>تجمع</th>
                <th>جذب</th>
                <th>قفل شناور</th>
                <th>شکست</th>
            </tr>
        </thead>
        <tbody>
"""

        for item in sorted(self._data, key=lambda x: x["smc_score"], reverse=True):
            phase_color = PHASE_COLORS.get(item["phase"], "#64748b")
            html += f"""
            <tr>
                <td><strong>{item['symbol']}</strong></td>
                <td><span class="phase-badge" style="background: {phase_color}20; color: {phase_color};">{item['phase_label']}</span></td>
                <td>{item['smc_pct']}%</td>
                <td>{round(item['scores'].get('accumulation', 0) * 100, 1)}%</td>
                <td>{round(item['scores'].get('absorption', 0) * 100, 1)}%</td>
                <td>{round(item['scores'].get('float_lock', 0) * 100, 1)}%</td>
                <td>{round(item['scores'].get('breakout_readiness', 0) * 100, 1)}%</td>
            </tr>
"""

        html += """
        </tbody>
    </table>
</body>
</html>
"""
        return html

    def clear(self) -> None:
        """Clear all data."""
        self._data.clear()
        self._transitions.clear()
