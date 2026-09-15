"""Bootstrap Calibration Models — pre-trained calibration curves for cold-start.

The feedback-loop problem:
  No initial signals → no outcomes → no signal_accuracy data
  No signal_accuracy → calibrator can't train → raw_score unchanged
  Raw scores unfiltered → bad signal quality → users lose trust

Solution: Domain-adapted pre-trained calibration curves.

Each market type has a theoretically-derived calibration curve based on
microstructure principles, market efficiency, and known behavioral biases
of the Iranian market. These serve as Bayesian priors that blend toward
real data as it accumulates.

Sources:
  - TSE (stock):  Low efficiency → moderate signal-to-noise ratio
  - Gold:         Global correlation → stronger trends
  - Crypto:       Very high noise → weak calibration slope
  - Currency:     Macro-driven → strongest trends (IRR has persistent bias)
  - Commodity:    Similar to stock, lower liquidity
  - Option:       Very low liquidity → near-random walk

Usage:
    from core.calibration_bootstrap import BOOTSTRAP_BUCKETS
    buckets = BOOTSTRAP_BUCKETS.get("stock", BOOTSTRAP_BUCKETS["default"])
"""

from __future__ import annotations

from typing import Any

# ── Bootstrap calibration curves ──────────────────────────────────────────────
# Each market has a list of (lo, hi, predicted_mean, actual_rate, confidence)
# The actual_rate is the prior win probability for a signal in that bucket.
#
# Design principles:
#   1. Low scores (< 0.55):  actual ≈ predicted − small penalty (conservative)
#   2. Mid scores (0.55-0.75): actual ≈ predicted (well-calibrated)
#   3. High scores (0.75-0.90): actual = predicted − noise_penalty (optimism bias)
#   4. Very high scores (> 0.90): actual capped at 0.88 (extreme caution)
#
# The "confidence" (0-100) represents how many synthetic signals back this bucket,
# used as a Bayesian prior weight when blending with real data.

BOOTSTRAP_BUCKETS: dict[str, list[dict[str, Any]]] = {
    # ── Stock (TSE / IFB) ────────────────────────────────────────────────
    # Iran market: moderate efficiency, some informational advantage possible
    "stock": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.48, "count": 500},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.52, "count": 200},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.57, "count": 200},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.62, "count": 200},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.66, "count": 150},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.70, "count": 100},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.73, "count": 80},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.75, "count": 50},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.78, "count": 30},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.80, "count": 20},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.82, "count": 15},
    ],
    # ── Gold / Coin ──────────────────────────────────────────────────────
    # Global correlation provides stronger trends, better calibration
    "gold": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.49, "count": 400},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.53, "count": 150},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.58, "count": 150},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.63, "count": 150},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.68, "count": 120},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.72, "count": 80},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.75, "count": 60},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.78, "count": 40},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.80, "count": 25},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.82, "count": 15},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.85, "count": 10},
    ],
    # ── Crypto ───────────────────────────────────────────────────────────
    # Very high noise → calibration is weak, strong regression to mean
    "crypto": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.48, "count": 600},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.50, "count": 250},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.54, "count": 250},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.58, "count": 200},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.61, "count": 150},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.64, "count": 100},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.66, "count": 70},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.68, "count": 40},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.70, "count": 25},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.72, "count": 15},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.74, "count": 10},
    ],
    # ── Currency (IRR/USD, IRR/EUR) ──────────────────────────────────────
    # Macro-driven: strong persistent trends → best calibration
    "currency": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.50, "count": 300},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.54, "count": 120},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.59, "count": 120},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.64, "count": 100},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.69, "count": 80},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.73, "count": 60},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.76, "count": 40},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.79, "count": 30},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.81, "count": 20},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.83, "count": 10},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.85, "count": 8},
    ],
    # ── Commodity (IME: metals, chemicals) ──────────────────────────────
    # Similar to stock, lower liquidity → slightly weaker
    "commodity": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.48, "count": 500},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.51, "count": 200},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.56, "count": 200},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.61, "count": 180},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.65, "count": 130},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.69, "count": 90},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.72, "count": 60},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.74, "count": 40},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.76, "count": 25},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.78, "count": 15},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.80, "count": 10},
    ],
    # ── IME (کالا و انرژی) ────────────────────────────────────────────
    # Similar to commodity, slightly lower liquidity
    "ime": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.48, "count": 500},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.51, "count": 200},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.56, "count": 200},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.60, "count": 180},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.64, "count": 130},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.68, "count": 90},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.71, "count": 60},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.73, "count": 40},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.75, "count": 25},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.77, "count": 15},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.79, "count": 10},
    ],
    # ── Option (very low liquidity) ──────────────────────────────────────
    # Near-random walk → very weak calibration
    "option": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.48, "count": 800},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.50, "count": 300},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.52, "count": 300},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.54, "count": 250},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.55, "count": 200},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.57, "count": 150},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.58, "count": 100},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.60, "count": 60},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.62, "count": 40},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.64, "count": 25},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.66, "count": 15},
    ],
    # ── Default fallback (any unknown market) ──────────────────────────
    "default": [
        {"lo": 0.00, "hi": 0.50, "predicted_mean": 0.50, "actual_rate": 0.48, "count": 600},
        {"lo": 0.50, "hi": 0.55, "predicted_mean": 0.53, "actual_rate": 0.51, "count": 250},
        {"lo": 0.55, "hi": 0.60, "predicted_mean": 0.58, "actual_rate": 0.55, "count": 250},
        {"lo": 0.60, "hi": 0.65, "predicted_mean": 0.62, "actual_rate": 0.60, "count": 200},
        {"lo": 0.65, "hi": 0.70, "predicted_mean": 0.67, "actual_rate": 0.64, "count": 150},
        {"lo": 0.70, "hi": 0.75, "predicted_mean": 0.72, "actual_rate": 0.67, "count": 100},
        {"lo": 0.75, "hi": 0.80, "predicted_mean": 0.77, "actual_rate": 0.70, "count": 70},
        {"lo": 0.80, "hi": 0.85, "predicted_mean": 0.82, "actual_rate": 0.72, "count": 45},
        {"lo": 0.85, "hi": 0.90, "predicted_mean": 0.87, "actual_rate": 0.74, "count": 30},
        {"lo": 0.90, "hi": 0.95, "predicted_mean": 0.92, "actual_rate": 0.76, "count": 18},
        {"lo": 0.95, "hi": 1.00, "predicted_mean": 0.97, "actual_rate": 0.78, "count": 12},
    ],
}

# ── Market accuracy prior (for ConfidenceScorer) ──────────────────────────
# Base accuracy expectation per market when no historical data exists
MARKET_ACCURACY_PRIOR: dict[str, float] = {
    "stock": 0.62,
    "gold": 0.65,
    "crypto": 0.55,
    "currency": 0.68,
    "commodity": 0.60,
    "option": 0.52,
    "ime": 0.58,
    "default": 0.58,
}

# ── Constants ────────────────────────────────────────────────────────────────

# Equivalent sample size for bootstrap prior when blending with real data.
# Higher = slower adaptation to real data, lower = faster but more noisy.
BOOTSTRAP_PRIOR_WEIGHT: int = 100


# ── Utility functions ─────────────────────────────────────────────────────────


def get_bootstrap_buckets(market: str) -> list[dict[str, Any]]:
    """Get bootstrap calibration buckets for a market type.

    Falls back to 'default' if the market is not found.
    """
    return BOOTSTRAP_BUCKETS.get(market, BOOTSTRAP_BUCKETS["default"])


def get_accuracy_prior(market: str) -> float:
    """Get base accuracy expectation for a market type (0-1)."""
    return MARKET_ACCURACY_PRIOR.get(market, MARKET_ACCURACY_PRIOR["default"])


def find_bucket_for_score(
    buckets: list[dict[str, Any]],
    score: float,
) -> dict[str, Any] | None:
    """Find the bucket that contains *score* in its [lo, hi) range."""
    for bk in buckets:
        if bk["lo"] <= score < bk["hi"]:
            return bk
    return None


def blend_bootstrap_with_real(
    bootstrap_bucket: dict[str, Any] | None,
    real_actual_rate: float | None,
    real_count: int,
    bootstrap_weight: int = 100,
) -> float:
    """Bayesian blend of bootstrap prior with real data.

    Args:
        bootstrap_bucket: The matching bootstrap bucket (or None).
        real_actual_rate: The actual win rate from real data (or None).
        real_count: Number of real signals in this bucket.
        bootstrap_weight: Equivalent sample size for the bootstrap prior.

    Returns:
        Blended actual rate (weighted average).
    """
    if bootstrap_bucket is None and real_actual_rate is None:
        return 0.50
    if bootstrap_bucket is None:
        return float(real_actual_rate) if real_actual_rate is not None else 0.50
    if real_actual_rate is None:
        return float(bootstrap_bucket["actual_rate"])

    prior_rate = float(bootstrap_bucket["actual_rate"])
    total_weight = bootstrap_weight + real_count
    blended = (prior_rate * bootstrap_weight + real_actual_rate * real_count) / total_weight
    return round(blended, 4)
