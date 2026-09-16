"""
Visual Analysis of 5000-Question Backtest Results
==================================================

This script:
1. Reads the JSON test report (backtest_test_report.json)
2. Generates bar charts, pie charts, and gauge charts
3. Outputs HTML report with embedded charts

Usage:
    python tests/visualize_backtest_results.py
    python tests/visualize_backtest_results.py --report path/to/report.json
    python tests/visualize_backtest_results.py --output-dir ./charts
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys

# ── Persian labels for categories ──────────────────────────
PERSIAN_LABELS: dict[str, str] = {
    "strategy_backtest": "Backtest Strategy",
    "strategy_compare": "Compare Strategies",
    "view_result": "View Results",
    "param_tuning": "Parameter Tuning",
    "capital_mgmt": "Capital Management",
    "risk_mgmt": "Risk Management",
    "optimization": "Optimization",
    "portfolio": "Portfolio",
    "symbol_select": "Symbol Selection",
    "period_analysis": "Period Analysis",
    "result_analysis": "Result Analysis",
    "strategy_gen": "Strategy Generation",
    "ml_backtest": "ML Backtest",
    "edge_cases": "Edge Cases",
    "multi_symbol": "Multi-Symbol",
    "scenario_whatif": "Scenario/What-If",
    "benchmark_compare": "Benchmark Compare",
    "data_prep": "Data Preparation",
    "custom_metrics": "Custom Metrics",
}

RESPONSE_TYPE_COLORS = {
    "recommendation": "#2ecc71",
    "screener": "#3498db",
    "comparison": "#9b59b6",
    "filter": "#1abc9c",
    "market": "#f39c12",
    "pattern": "#e74c3c",
    "portfolio": "#34495e",
    "alert": "#e67e22",
    "multi_timeframe": "#16a085",
    "volume_profile": "#2980b9",
    "correlation": "#8e44ad",
    "report": "#d35400",
    "greeting": "#f1c40f",
    "farewell": "#95a5a6",
    "help": "#27ae60",
    "refresh": "#e74c3c",
    "info": "#3498db",
    "error": "#c0392b",
    "unknown": "#7f8c8d",
}

CATEGORY_COLORS = [
    "#3498db",
    "#2ecc71",
    "#e74c3c",
    "#f39c12",
    "#9b59b6",
    "#1abc9c",
    "#e67e22",
    "#34495e",
    "#16a085",
    "#d35400",
    "#2980b9",
    "#8e44ad",
    "#27ae60",
    "#c0392b",
    "#7f8c8d",
    "#f1c40f",
    "#2c3e50",
    "#95a5a6",
    "#e91e63",
]

TYPE_PERSIAN = {
    "recommendation": "Recommendation",
    "screener": "Screener",
    "comparison": "Comparison",
    "filter": "Filter",
    "market": "Market",
    "pattern": "Pattern",
    "portfolio": "Portfolio",
    "alert": "Alert",
    "multi_timeframe": "Multi-TF",
    "volume_profile": "Volume Profile",
    "correlation": "Correlation",
    "report": "Report",
    "greeting": "Greeting",
    "farewell": "Farewell",
    "help": "Help",
    "refresh": "Refresh",
    "info": "Info",
    "error": "Error",
    "unknown": "Unknown",
}


# ── Safe printing helpers (handles Windows cp1252) ─────────


def _safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


def _log(msg: str):
    _safe_print(f"  [*] {msg}")


def _ok(msg: str):
    _safe_print(f"  [+] {msg}")


def _warn(msg: str):
    _safe_print(f"  [!] {msg}")


# ── Font utilities ─────────────────────────────────────────


def try_set_persian_font() -> str | None:
    """Try to find a Persian-capable font for matplotlib."""
    with contextlib.suppress(Exception):
        import matplotlib.font_manager as fm

        preferred = ["Tahoma", "Segoe UI", "Arial", "B Nazanin", "B Yekan", "IRANSans"]
        for font_name in preferred:
            try:
                font = fm.findfont(font_name, fallback_to_default=False)
                if font and "DejaVu" not in font:
                    return font_name
            except Exception:
                continue

        for font in fm.fontManager.ttflist:
            if any(
                kw in font.name.lower()
                for kw in [
                    "tahoma",
                    "segoe",
                    "b nazanin",
                    "b yekan",
                    "iran",
                    "persian",
                    "arabic",
                ]
            ):
                return font.name
    return None


def _setup_plot(font_name: str | None):
    """Configure matplotlib for Persian text."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if font_name:
        plt.rcParams["font.family"] = font_name
    plt.rcParams["axes.unicode_minus"] = False


def load_report(report_path: str) -> dict:
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


# ── Chart generation functions ─────────────────────────────


def plot_category_bar_chart(report: dict, output_dir: str, font_name: str | None):
    """Bar chart: questions per category with pass/fail breakdown."""
    _setup_plot(font_name)
    import matplotlib.pyplot as plt
    import numpy as np

    cats = report.get("categories", {})
    if not cats:
        _warn("No category data to plot")
        return

    sorted_cats = sorted(cats.items(), key=lambda x: -x[1]["total"])
    labels = [PERSIAN_LABELS.get(c, c) for c, _ in sorted_cats]
    totals = [d["total"] for _, d in sorted_cats]
    passed = [d["passed"] for _, d in sorted_cats]
    failed = [d["failed"] for _, d in sorted_cats]
    warnings = [d.get("warnings", 0) for _, d in sorted_cats]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 14), gridspec_kw={"height_ratios": [2, 1]})
    fig.suptitle("Backtest Results by Category", fontsize=20, fontweight="bold", y=0.98)

    x = np.arange(len(labels))
    width = 0.55

    ax1.bar(
        x,
        passed,
        width,
        label="Passed",
        color="#2ecc71",
        edgecolor="white",
        linewidth=0.5,
    )
    ax1.bar(
        x,
        failed,
        width,
        bottom=passed,
        label="Failed",
        color="#e74c3c",
        edgecolor="white",
        linewidth=0.5,
    )

    ax1.set_ylabel("Questions", fontsize=12)
    ax1.set_title("Question Distribution by Category", fontsize=16, fontweight="bold", pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=11)
    ax1.legend(loc="upper right", fontsize=12)
    ax1.grid(axis="y", alpha=0.3, linestyle="--")

    for i, (p, f) in enumerate(zip(passed, failed, strict=False)):
        total = p + f
        if total > 0:
            ax1.text(
                i,
                total + max(totals) * 0.01,
                str(total),
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color="#2c3e50",
            )

    colors_warn = [CATEGORY_COLORS[i % len(CATEGORY_COLORS)] for i in range(len(labels))]
    ax2.bar(x, warnings, width, color=colors_warn, edgecolor="white", linewidth=0.5)
    ax2.set_ylabel("Warnings", fontsize=12)
    ax2.set_title("Warnings by Category", fontsize=16, fontweight="bold", pad=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=11)
    ax2.grid(axis="y", alpha=0.3, linestyle="--")

    for i, w in enumerate(warnings):
        if w > 0:
            ax2.text(
                i,
                w + max(warnings) * 0.02 if max(warnings) > 0 else 1,
                str(w),
                ha="center",
                va="bottom",
                fontsize=9,
                color="#2c3e50",
            )

    plt.tight_layout()
    path = os.path.join(output_dir, "category_bar_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _ok(f"Category bar chart: {path}")


def plot_response_type_pie(report: dict, output_dir: str, font_name: str | None):
    """Donut chart: distribution of response types."""
    _setup_plot(font_name)
    import matplotlib.pyplot as plt

    type_dist = report.get("response_type_distribution", {})
    if not type_dist:
        _warn("No response type data to plot")
        return

    sorted_types = sorted(type_dist.items(), key=lambda x: -x[1])
    labels = [TYPE_PERSIAN.get(t, t) for t, _ in sorted_types]
    values = [v for _, v in sorted_types]
    colors = [RESPONSE_TYPE_COLORS.get(t, "#95a5a6") for t, _ in sorted_types]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle("Response Type Distribution", fontsize=18, fontweight="bold", y=0.98)

    wedges, texts, autotexts = ax1.pie(
        values,
        labels=None,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.85,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_fontweight("bold")

    centre_circle = plt.Circle((0, 0), 0.55, fc="white", linewidth=1.5, edgecolor="#ddd")
    ax1.add_artist(centre_circle)
    ax1.text(
        0,
        0,
        f"{sum(values):,}\nTotal",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )
    ax1.set_title("Response Ratio", fontsize=14, fontweight="bold", pad=15)

    legend_labels = [f"{idx} ({v:,})" for idx, v in zip(labels, values, strict=False)]
    ax2.axis("off")

    # Legend table
    table_data = []
    for i in range(0, len(legend_labels), 2):
        row = [
            legend_labels[i],
            legend_labels[i + 1] if i + 1 < len(legend_labels) else "",
        ]
        table_data.append(row)

    if table_data:
        table = ax2.table(cellText=table_data, colWidths=[0.45, 0.45], cellLoc="left", loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)

        for i in range(len(table_data)):
            idx = i * 2
            if idx < len(colors):
                table[(i, 0)].set_facecolor(colors[idx] + "40")
            if idx + 1 < len(colors):
                table[(i, 1)].set_facecolor(colors[idx + 1] + "40")

    plt.tight_layout()
    path = os.path.join(output_dir, "response_type_pie.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _ok(f"Response type pie chart: {path}")


def plot_warnings_bar(report: dict, output_dir: str, font_name: str | None):
    """Horizontal bar chart: top warnings."""
    _setup_plot(font_name)
    import matplotlib.pyplot as plt

    warnings = report.get("common_warnings", {})
    if not warnings:
        _warn("No warning data to plot")
        return

    top_warnings = sorted(warnings.items(), key=lambda x: -x[1])[:10]
    labels = [w[:70] + "..." if len(w) > 70 else w for w, _ in top_warnings]
    values = [v for _, v in top_warnings]

    fig, ax = plt.subplots(figsize=(14, 8))
    fig.suptitle("Top Warnings", fontsize=18, fontweight="bold", y=0.98)

    colors = plt.cm.RdYlGn_r([v / max(values) for v in values]) if max(values) > 0 else ["#3498db"] * len(values)
    bars = ax.barh(
        range(len(labels)),
        values,
        color=colors,
        edgecolor="white",
        linewidth=1.0,
        height=0.6,
    )

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Count", fontsize=12)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3, linestyle="--")

    for bar, v in zip(bars, values, strict=False):
        ax.text(
            v + max(values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    plt.tight_layout()
    path = os.path.join(output_dir, "warnings_bar_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _ok(f"Warnings bar chart: {path}")


def plot_errors_bar(report: dict, output_dir: str, font_name: str | None):
    """Horizontal bar chart: top errors."""
    _setup_plot(font_name)
    import matplotlib.pyplot as plt

    errors = report.get("common_errors", {})
    if not errors:
        _warn("No error data to plot")
        return

    top_errors = sorted(errors.items(), key=lambda x: -x[1])[:10]
    labels = [e[:70] + "..." if len(e) > 70 else e for e, _ in top_errors]
    values = [v for _, v in top_errors]

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.suptitle("Top Errors", fontsize=18, fontweight="bold", y=0.98)

    bars = ax.barh(
        range(len(labels)),
        values,
        color="#e74c3c",
        edgecolor="white",
        linewidth=1.0,
        height=0.5,
    )

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Count", fontsize=12)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3, linestyle="--")

    for bar, v in zip(bars, values, strict=False):
        ax.text(
            v + max(values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#c0392b",
        )

    plt.tight_layout()
    path = os.path.join(output_dir, "errors_bar_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _ok(f"Errors bar chart: {path}")


def plot_performance_gauge(report: dict, output_dir: str, font_name: str | None):
    """Gauge chart: overall performance metrics."""
    _setup_plot(font_name)
    import matplotlib.pyplot as plt
    import numpy as np

    summary = report.get("summary", {})
    if not summary:
        return

    fig, axes = plt.subplots(1, 4, figsize=(16, 5), subplot_kw={"projection": "polar"})
    fig.suptitle("Performance Gauges", fontsize=18, fontweight="bold", y=1.08)

    total_q = max(summary.get("total_questions", 1), 1)
    metrics = [
        ("Pass Rate", summary.get("pass_rate_pct", 0) / 100, "#2ecc71"),
        ("No API Error", 1 - summary.get("api_errors", 0) / total_q, "#3498db"),
        (
            "Speed (QPS)",
            min(summary.get("questions_per_second", 0) / 20, 1.0),
            "#f39c12",
        ),
        ("Quality", max(0, 1 - summary.get("total_warnings", 0) / total_q), "#9b59b6"),
    ]

    for ax, (label, value, color) in zip(axes, metrics, strict=False):
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 1)

        angles = np.linspace(0, np.pi, 50)
        ax.plot(angles, [value] * len(angles), color=color, linewidth=3)
        ax.fill_between(angles, 0, [value] * len(angles), alpha=0.3, color=color)
        ax.plot(angles, [1] * len(angles), color="#ddd", linewidth=2, alpha=0.5)

        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(label, fontsize=13, fontweight="bold", pad=20)
        ax.text(
            np.pi / 2,
            0.5,
            f"{value*100:.0f}%",
            ha="center",
            va="center",
            fontsize=22,
            fontweight="bold",
            color=color,
        )

    plt.tight_layout()
    path = os.path.join(output_dir, "performance_gauges.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _ok(f"Performance gauges: {path}")


def plot_response_time_scatter(output_dir: str, font_name: str | None, results_path: str | None = None):
    """Scatter plot of response times by category (requires results JSONL)."""
    if not results_path or not os.path.exists(results_path):
        _warn("No results JSONL found, skipping response time plot")
        return

    _setup_plot(font_name)
    import matplotlib.pyplot as plt
    import numpy as np

    categories = []
    durations = []

    with open(results_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                categories.append(r.get("category", "unknown"))
                durations.append(r.get("duration_ms", 0))
            except (json.JSONDecodeError, KeyError):
                continue

    if not durations:
        _warn("No duration data in results")
        return

    fig, ax = plt.subplots(figsize=(16, 8))
    fig.suptitle("Response Time by Category", fontsize=18, fontweight="bold", y=0.98)

    unique_cats = list(set(categories))
    cat_to_idx = {c: i for i, c in enumerate(unique_cats)}
    cat_colors = [CATEGORY_COLORS[cat_to_idx[c] % len(CATEGORY_COLORS)] for c in categories]

    x_positions = (-0.2, 0.2)

    ax.scatter(
        x_positions,
        durations,
        c=cat_colors,
        alpha=0.6,
        s=20,
        edgecolor="white",
        linewidth=0.3,
    )

    cat_data = {c: [] for c in unique_cats}
    for cat, dur in zip(categories, durations, strict=False):
        cat_data[cat].append(dur)

    cat_names = list(cat_data.keys())
    cat_vals = [cat_data[c] for c in cat_names]
    labels_persian = [PERSIAN_LABELS.get(c, c) for c in cat_names]

    bp = ax.boxplot(
        cat_vals,
        positions=range(len(cat_names)),
        widths=0.5,
        patch_artist=True,
        showfliers=False,
    )
    for patch, color in zip(
        bp["boxes"],
        [CATEGORY_COLORS[i % len(CATEGORY_COLORS)] for i in range(len(cat_names))],
        strict=False,
    ):
        patch.set_facecolor(color + "30")
        patch.set_edgecolor(color)
        patch.set_linewidth(1.5)

    ax.set_xticks(range(len(cat_names)))
    ax.set_xticklabels(labels_persian, rotation=45, ha="right", fontsize=10)
    ax.set_ylabel("Response Time (ms)", fontsize=12)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    avg_dur = np.mean(durations)
    ax.axhline(
        y=avg_dur,
        color="red",
        linestyle="--",
        linewidth=1.5,
        alpha=0.7,
        label=f"Avg: {avg_dur:.0f}ms",
    )
    ax.legend(fontsize=11)

    plt.tight_layout()
    path = os.path.join(output_dir, "response_time_scatter.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _ok(f"Response time scatter: {path}")


# ── HTML Report Generation ─────────────────────────────────


def generate_html_report(report: dict, output_dir: str):
    """Generate a standalone HTML report with all charts."""
    summary = report.get("summary", {})
    categories = report.get("categories", {})
    type_dist = report.get("response_type_distribution", {})
    common_warnings = report.get("common_warnings", {})

    # Check which chart files exist
    chart_names = [
        "performance_gauges",
        "category_bar_chart",
        "response_type_pie",
        "warnings_bar_chart",
        "errors_bar_chart",
        "response_time_scatter",
    ]
    existing = {name: os.path.exists(os.path.join(output_dir, f"{name}.png")) for name in chart_names}

    # Category table
    cat_rows = []
    sorted_cats = sorted(categories.items(), key=lambda x: -x[1]["total"])
    for cat, data in sorted_cats:
        name = PERSIAN_LABELS.get(cat, cat)
        rate = data["passed"] / data["total"] * 100
        cat_rows.append(
            f"""<tr><td>{name}</td><td>{data['total']:,
    }</td><td>{data['passed']:,
    }</td><td>{data['failed']:,
    }</td><td>{data.get('api_errors',
    0)}</td><td>{data.get('warnings',
    0)}</td><td>{rate:.1f}%</td></tr>"""
        )

    # Type distribution table
    type_rows = []
    for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
        type_rows.append(
            f"<tr><td>{TYPE_PERSIAN.get(t, t)}</td><td>{c:,}</td><td>{c/sum(type_dist.values())*100:.1f}%</td></tr>"
        )

    # Warning list
    warning_items = []
    for w, c in sorted(common_warnings.items(), key=lambda x: -x[1])[:10]:
        warning_items.append(f"<li><strong>{c}x</strong>: {w[:120]}</li>")

    # Build chart sections HTML
    chart_sections = ""
    if existing["performance_gauges"]:
        chart_sections += (
            '<h2>Performance</h2><div class="chart"><img src="performance_gauges.png" alt="Performance"></div>\n'
        )
    if existing["category_bar_chart"]:
        chart_sections += '<h2>Category Distribution</h2><div class="chart"><img src="category_bar_chart.png" alt="Categories"></div>\n'
    if existing["response_type_pie"]:
        chart_sections += (
            '<h2>Response Types</h2><div class="chart"><img src="response_type_pie.png" alt="Response Types"></div>\n'
        )
    if existing["warnings_bar_chart"]:
        chart_sections += (
            '<h2>Top Warnings</h2><div class="chart"><img src="warnings_bar_chart.png" alt="Warnings"></div>\n'
        )
    if existing["errors_bar_chart"]:
        chart_sections += '<h2>Top Errors</h2><div class="chart"><img src="errors_bar_chart.png" alt="Errors"></div>\n'
    if existing.get("response_time_scatter"):
        chart_sections += (
            '<h2>Response Time</h2><div class="chart"><img src="response_time_scatter.png" alt="Response Time"></div>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Backtest 5000-Question Test Report</title>
<style>
    * {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; box-sizing: border-box; }}
    body {{ background: #f5f7fa; color: #2c3e50; margin: 0; padding: 20px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ text-align: center; color: #2c3e50; margin-bottom: 30px; font-size: 28px; }}
    h2 {{ color: #34495e; border-bottom: 3px solid #3498db; padding-bottom: 8px; margin-top: 40px; }}
    .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0; }}
    .card {{ background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
    .card .value {{ font-size: 32px; font-weight: bold; color: #2c3e50; }}
    .card .label {{ font-size: 13px; color: #7f8c8d; margin-top: 5px; }}
    .card.green .value {{ color: #27ae60; }}
    .card.red .value {{ color: #e74c3c; }}
    .card.blue .value {{ color: #3498db; }}
    .card.orange .value {{ color: #f39c12; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin: 20px 0; }}
    th {{ background: #34495e; color: white; padding: 12px 15px; text-align: center; font-size: 13px; }}
    td {{ padding: 10px 15px; text-align: center; border-bottom: 1px solid #ecf0f1; font-size: 13px; }}
    tr:hover {{ background: #f8f9fa; }}
    .chart {{ text-align: center; margin: 30px 0; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
    .chart img {{ max-width: 100%; height: auto; border-radius: 8px; }}
    .warnings {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
    .warnings li {{ padding: 8px 0; border-bottom: 1px solid #ecf0f1; font-size: 13px; }}
    .footer {{ text-align: center; color: #95a5a6; font-size: 12px; margin-top: 50px; padding: 20px; }}
    @media (max-width: 768px) {{ .summary-cards {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<div class="container">
    <h1>Backtest 5000-Question Test Report</h1>

    <div class="summary-cards">
        <div class="card green"><div class="value">{summary.get('total_questions', 0):,}</div><div class="label">Total Questions</div></div>
        <div class="card green"><div class="value">{summary.get('pass_rate_pct', 0):.1f}%</div><div class="label">Pass Rate</div></div>
        <div class="card blue"><div class="value">{summary.get('avg_response_time_ms', 0):.0f}</div><div class="label">Avg Response (ms)</div></div>
        <div class="card orange"><div class="value">{summary.get('questions_per_second', 0):.1f}</div><div class="label">Questions/sec</div></div>
        <div class="card red"><div class="value">{summary.get('total_warnings', 0):,}</div><div class="label">Total Warnings</div></div>
        <div class="card green"><div class="value">{summary.get('total_duration_seconds', 0):.0f}</div><div class="label">Duration (sec)</div></div>
    </div>

    {chart_sections}

    <h2>Category Details</h2>
    <table>
        <thead><tr><th>Category</th><th>Total</th><th>Passed</th><th>Failed</th><th>API Err</th><th>Warnings</th><th>Rate</th></tr></thead>
        <tbody>{''.join(cat_rows)}</tbody>
    </table>

    <h2>Response Type Distribution</h2>
    <table>
        <thead><tr><th>Type</th><th>Count</th><th>Percent</th></tr></thead>
        <tbody>{''.join(type_rows)}</tbody>
    </table>

    <h2>Top Warnings</h2>
    <div class="warnings"><ol>{''.join(warning_items)}</ol></div>

    <div class = (
    ).strftime('%Y-%m-%d %H:%M'
)
</div>
</body>
</html>"""

    path = os.path.join(output_dir, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    _ok(f"HTML report: {path}")


# ── Console Summary ────────────────────────────────────────


def print_text_summary(report: dict):
    """Print a text summary to console."""
    summary = report.get("summary", {})
    categories = report.get("categories", {})
    type_dist = report.get("response_type_distribution", {})

    print()
    print("=" * 60)
    print("  Backtest Results Summary")
    print("=" * 60)
    s = summary
    print(f"  Total questions:     {s.get('total_questions', 0):,}")
    print(f"  Passed:              {s.get('passed', 0):,} ({s.get('pass_rate_pct', 0):.1f}%)")
    print(f"  Failed:              {s.get('failed', 0):,}")
    print(f"  API errors:          {s.get('api_errors', 0):,}")
    print(f"  Avg response:        {s.get('avg_response_time_ms', 0):.0f} ms")
    print(f"  QPS:                 {s.get('questions_per_second', 0):.1f}")
    print(f"  Duration:            {s.get('total_duration_seconds', 0):.0f} sec")
    print(f"  Total warnings:      {s.get('total_warnings', 0):,}")
    print()

    sorted_cats = sorted(categories.items(), key=lambda x: -x[1]["total"])[:5]
    print("  Top 5 categories:")
    max_total = max(d["total"] for _, d in sorted_cats) if sorted_cats else 1
    for cat, data in sorted_cats:
        name = PERSIAN_LABELS.get(cat, cat)
        rate = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
        bar = "#" * (data["total"] * 30 // max_total)
        print(f"  {name:25s}: {data['total']:5,} {bar} ({rate:.0f}%)")

    print()
    print("  Response type distribution:")
    total_resp = sum(type_dist.values()) or 1
    for t, c in sorted(type_dist.items(), key=lambda x: -x[1])[:8]:
        pct = c / total_resp * 100
        bar = "#" * int(pct / 3)
        print(f"  {TYPE_PERSIAN.get(t, t):20s}: {c:5,} ({pct:5.1f}%) {bar}")

    print()


# ── Main ───────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Visual Analysis of Backtest 5000-Question Results")
    parser.add_argument(
        "--report",
        default="backtest_test_report.json",
        help="Path to JSON report (default: backtest_test_report.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="charts",
        help="Output directory for charts (default: ./charts)",
    )
    parser.add_argument(
        "--results",
        default="backtest_test_results.jsonl",
        help="Path to results JSONL (default: backtest_test_results.jsonl)",
    )
    parser.add_argument("--skip-html", action="store_true", help="Skip HTML report generation")
    parser.add_argument(
        "--font",
        default=None,
        help="Custom font for Persian text (default: auto-detect)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.report):
        print(f"[ERROR] Report file not found: {args.report}")
        print("  Run the test first:")
        print("  python tests/test_backtest_5000_questions.py --sample 100")
        sys.exit(1)

    _log(f"Loading report: {args.report}")
    report = load_report(args.report)
    ensure_dir(args.output_dir)
    print()

    # Print text summary
    print_text_summary(report)

    # Try to set Persian font
    font_name = args.font or try_set_persian_font()
    if font_name:
        _log(f"Using font: {font_name}")
    else:
        _warn("No Persian font found; some characters may not render correctly")
    print()

    # Generate charts
    _log("Generating charts...")
    plot_performance_gauge(report, args.output_dir, font_name)
    plot_category_bar_chart(report, args.output_dir, font_name)
    plot_response_type_pie(report, args.output_dir, font_name)
    plot_warnings_bar(report, args.output_dir, font_name)
    plot_errors_bar(report, args.output_dir, font_name)
    plot_response_time_scatter(args.output_dir, font_name, args.results)

    # Generate HTML report
    if not args.skip_html:
        print()
        _log("Generating HTML report...")
        generate_html_report(report, args.output_dir)

    print()
    _ok(f"All outputs in: {os.path.abspath(args.output_dir)}")


if __name__ == "__main__":
    main()
