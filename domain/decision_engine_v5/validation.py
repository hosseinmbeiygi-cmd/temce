"""Validation — v5.0 — Statistical Acceptance Gate + Drift Observability."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateResult:
    passed: bool
    reasons: list[str]


def acceptance_gate(
    win_rate: float,
    sharpe: float,
    out_of_sample_pnl: float,
    max_drawdown: float,
    profit_factor: float,
    expected_value: float,
) -> GateResult:
    """6 شرط سند §8.2 — همه باید پاس شود."""
    reasons: list[str] = []
    if win_rate < 0.55:
        reasons.append(f"Win Rate {win_rate:.1%} <55%")
    if sharpe < 1.5:
        reasons.append(f"Sharpe {sharpe:.2f} <1.5")
    if out_of_sample_pnl <= 0:
        reasons.append(f"OOS PnL {out_of_sample_pnl} <=0")
    if max_drawdown < -0.15:
        reasons.append(f"MaxDD {max_drawdown:.1%} < -15%")
    if profit_factor < 1.2:
        reasons.append(f"ProfitFactor {profit_factor:.2f} <1.2")
    if expected_value <= 0:
        reasons.append(f"EV {expected_value} <=0")
    return GateResult(passed=not reasons, reasons=reasons)


# ── Drift Observability (سند §9) — Grafana metrics ──
DRIFT_METRICS = [
    "data_freshness_seconds",
    "rejected_low_liquidity_rate",
    "iv_convergence_failure_rate",
    "slippage_vs_expected_bps",
    "tier1_vs_tier2_pnl_diff",
]
