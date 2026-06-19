from __future__ import annotations

from typing import Any


def estimate_regime_transition_matrix(
    regime_sequence: list[str],
    all_regimes: list[str] | None = None,
) -> dict[str, dict[str, float]]:
    """Estimate a regime transition matrix from a sequence of detected regimes.

    P[i][j] = P(regime_j | regime_i)

    Args:
        regime_sequence: List of regime labels in chronological order
        all_regimes: Optional list of all possible regime labels

    Returns:
        Transition probability matrix as nested dict
    """
    if len(regime_sequence) < 2:
        return {}

    unique = all_regimes or list(set(regime_sequence))
    transitions: dict[str, dict[str, int]] = {r: dict.fromkeys(unique, 0) for r in unique}

    for i in range(1, len(regime_sequence)):
        from_r = regime_sequence[i - 1]
        to_r = regime_sequence[i]
        if from_r in transitions and to_r in transitions[from_r]:
            transitions[from_r][to_r] += 1

    matrix: dict[str, dict[str, float]] = {}
    for from_r, targets in transitions.items():
        total = sum(targets.values())
        if total > 0:
            matrix[from_r] = {t: c / total for t, c in targets.items()}
        else:
            matrix[from_r] = {t: 1.0 / len(unique) for t in unique}

    return matrix


def estimate_transition_from_features(
    features_list: list[dict[str, float]],
    detector: Any,
    window: int = 50,
) -> dict[str, dict[str, float]]:
    """Estimate transition matrix by running detector over historical features."""
    regimes: list[str] = []
    for features in features_list:
        detector._last_features = features
        regime = detector._detect_rule_based(features)
        regimes.append(regime)

    return estimate_regime_transition_matrix(regimes)


def default_transition_matrix() -> dict[str, dict[str, float]]:
    """Get a default transition matrix based on typical market behavior."""
    return {
        "normal": {"normal": 0.85, "trend": 0.10, "panic": 0.02, "low_liquidity": 0.02, "queue_lock": 0.01, "mean_reverting": 0.00},
        "trend": {"normal": 0.20, "trend": 0.70, "panic": 0.05, "low_liquidity": 0.03, "queue_lock": 0.01, "mean_reverting": 0.01},
        "panic": {"normal": 0.30, "trend": 0.10, "panic": 0.50, "low_liquidity": 0.05, "queue_lock": 0.03, "mean_reverting": 0.02},
        "low_liquidity": {"normal": 0.40, "trend": 0.10, "panic": 0.10, "low_liquidity": 0.35, "queue_lock": 0.03, "mean_reverting": 0.02},
        "queue_lock": {"normal": 0.20, "trend": 0.05, "panic": 0.10, "low_liquidity": 0.05, "queue_lock": 0.60, "mean_reverting": 0.00},
        "mean_reverting": {"normal": 0.50, "trend": 0.10, "panic": 0.05, "low_liquidity": 0.05, "queue_lock": 0.00, "mean_reverting": 0.30},
    }
