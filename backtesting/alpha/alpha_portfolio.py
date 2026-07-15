from __future__ import annotations

import numpy as np


class AlphaPortfolio:
    """Constructs and manages a portfolio of selected alphas.

    Supports multiple weighting schemes:
    - mean_variance: Markowitz mean-variance optimization
    - equal_weight: Simple equal weighting
    - equal_risk_contribution: Risk parity
    """

    def __init__(self, weighting_scheme: str = "equal_weight") -> None:
        if weighting_scheme not in ("mean_variance", "equal_weight", "equal_risk_contribution"):
            msg = f"Unknown weighting scheme: {weighting_scheme}"
            raise ValueError(msg)
        self.weighting_scheme = weighting_scheme
        self._selected_alphas: list[str] = []
        self._weights: dict[str, float] = {}
        self._cov_matrix: np.ndarray | None = None
        self._mean_returns: np.ndarray | None = None

    def set_alphas(self, alpha_ids: list[str]) -> None:
        self._selected_alphas = alpha_ids

    def compute_weights(self, alpha_returns: dict[str, list[float]]) -> dict[str, float]:
        """Compute optimal weights for selected alphas."""
        if not self._selected_alphas:
            return {}

        returns_matrix = np.array([alpha_returns[a] for a in self._selected_alphas])
        self._mean_returns = np.mean(returns_matrix, axis=1)
        self._cov_matrix = np.cov(returns_matrix)

        if self.weighting_scheme == "equal_weight":
            n = len(self._selected_alphas)
            self._weights = dict.fromkeys(self._selected_alphas, 1.0 / n if n > 0 else 0.0)

        elif self.weighting_scheme == "mean_variance":
            self._weights = self._mean_variance_weights()

        elif self.weighting_scheme == "equal_risk_contribution":
            self._weights = self._risk_parity_weights()

        return dict(self._weights)

    def _mean_variance_weights(self) -> dict[str, float]:
        """Compute mean-variance optimal weights (max Sharpe)."""
        n = len(self._selected_alphas)
        if n == 0 or self._cov_matrix is None or self._mean_returns is None:
            return dict.fromkeys(self._selected_alphas, 1.0 / n) if n > 0 else {}

        try:
            inv_cov = np.linalg.inv(self._cov_matrix + np.eye(n) * 1e-6)
            raw_weights = inv_cov @ self._mean_returns
            total = np.sum(raw_weights)
            if total > 0:
                weights = raw_weights / total
            else:
                weights = np.ones(n) / n if n > 0 else np.array([])
        except np.linalg.LinAlgError:
            weights = np.ones(n) / n if n > 0 else np.array([])

        return {aid: float(w) for aid, w in zip(self._selected_alphas, weights, strict=False)}

    def _risk_parity_weights(self) -> dict[str, float]:
        """Compute equal risk contribution weights using simple iterative approach."""
        n = len(self._selected_alphas)
        if n == 0 or self._cov_matrix is None:
            return {}

        weights = np.ones(n) / n if n > 0 else np.array([])
        for _ in range(100):
            portfolio_var = weights @ self._cov_matrix @ weights
            if portfolio_var <= 0:
                break
            marginal_risk = self._cov_matrix @ weights / np.sqrt(portfolio_var)
            risk_contrib = weights * marginal_risk
            target_rc = np.mean(risk_contrib)
            weights = weights * (target_rc / (risk_contrib + 1e-10))
            weights = np.clip(weights, 0, 1)
            weights = weights / np.sum(weights) if np.sum(weights) > 0 else weights


        return {aid: float(w) for aid, w in zip(self._selected_alphas, weights, strict=False)}

    def portfolio_signal(self, alpha_values: dict[str, float]) -> float:
        """Compute the combined portfolio signal from individual alpha values.

        Args:
            alpha_values: Dict of {alpha_id: current_value}

        Returns:
            Combined portfolio signal (long/short)
        """
        if not self._weights:
            return 0.0

        signal = 0.0
        for alpha_id, weight in self._weights.items():
            value = alpha_values.get(alpha_id, 0)
            signal += weight * value
        return signal

    def get_weights(self) -> dict[str, float]:
        return dict(self._weights)

    @property
    def n_alphas(self) -> int:
        return len(self._selected_alphas)

    def reset(self) -> None:
        self._selected_alphas.clear()
        self._weights.clear()
        self._cov_matrix = None
        self._mean_returns = None
