"""Trading Plane — v5.0 — NetEdge, Hard Blocks, Signal Score, Position Sizing."""

from __future__ import annotations

import math

from .models import RejectionReason


# ── Hard Blocks (سند §5.2) ──
def check_hard_blocks(
    is_stale: bool,
    delivery_risk: bool,
    liquidity_ok: bool,
    tick_ok: bool,
    net_edge: float,
    model_confidence: float,
) -> RejectionReason | None:
    if is_stale:
        return RejectionReason.DATA_STALE
    if delivery_risk:
        return RejectionReason.DELIVERY_RISK
    if not liquidity_ok:
        return RejectionReason.LOW_LIQUIDITY
    if not tick_ok:
        return RejectionReason.TICK_MISMATCH
    if net_edge <= 0:
        return RejectionReason.COST_NOT_COVERED
    if model_confidence < 0.5:
        return RejectionReason.MODEL_LOW_CONFIDENCE
    return None


# ── NetEdge (سند §5.3) — Almgren-Chriss simplified ──
def market_impact(Q: float, V: float, sigma: float, eta: float = 0.1, gamma: float = 0.05) -> float:
    """Impact = η σ √(Q/V) + γ (Q/V) — Q حجم سفارش، V حجم بازار."""
    if V <= 0 or Q <= 0:
        return 0.0
    ratio = Q / V
    return eta * sigma * math.sqrt(ratio) + gamma * ratio


def compute_net_edge(
    gross_edge: float,
    commission: float,
    slippage: float,
    Q: float,
    V: float,
    sigma: float,
    latency_buffer: float = 0.0,
) -> float:
    impact = market_impact(Q, V, sigma)
    return gross_edge - commission - slippage - impact - latency_buffer


# ── Signal Score (سند §5.5) ──
def signal_score(data_quality: float, liquidity: float, execution_ease: float, model_confidence: float) -> float:
    """Score = 0.30*DQ + 0.25*Liq + 0.25*Exec + 0.20*Model — 0.5 تا 1.0 قابل معامله."""
    return 0.30 * data_quality + 0.25 * liquidity + 0.25 * execution_ease + 0.20 * model_confidence


# ── Position Sizing — Fixed Fractional (سند §6.1) ──
def fixed_fractional_size(risk_budget: float, signal_score_val: float, stop_distance: float) -> int:
    """Size = (Risk_Budget * Tier) / Stop_Distance — Tier بر اساس Score."""
    if stop_distance <= 0:
        return 0
    tier = 0.5 if signal_score_val < 0.6 else 1.0 if signal_score_val < 0.8 else 1.5
    # ریسک 0.5% تا 2% بسته به Tier (نسبت به risk_budget)
    risk_pct = 0.005 * tier  # 0.5% * tier
    return max(0, int((risk_budget * risk_pct) / stop_distance))


# ── Half-Kelly (سند §6.2) — آزمایشی ──
def half_kelly_size(p: float, b: float, capital: float, half: float = 0.5) -> int:
    """f*=(pb-q)/b, Size=0.5*f*Capital — فقط با p معتبر 55-60%."""
    if not 0.55 <= p <= 0.70 or b <= 0:
        return 0
    q = 1 - p
    f_star = (p * b - q) / b
    if f_star <= 0:
        return 0
    return max(0, int(half * f_star * capital))


# ── Drawdown Control (سند §6.3) ──
def drawdown_action(drawdown_pct: float) -> str:
    """-5% احتیاط، -10% توقف، -15% کاهش 50%."""
    if drawdown_pct <= -0.15:
        return "HALVE_SIZE"
    if drawdown_pct <= -0.10:
        return "STOP_ALL"
    if drawdown_pct <= -0.05:
        return "CAUTION"
    return "NORMAL"
