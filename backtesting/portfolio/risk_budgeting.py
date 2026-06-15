from __future__ import annotations

import numpy as np


class RiskBudgeting:
    def __init__(self, target_risk: float = 0.15) -> None:
        self.target_risk = target_risk

    def compute_risk_parity_weights(self, cov_matrix: np.ndarray) -> np.ndarray:
        n = cov_matrix.shape[0]
        x0 = np.ones(n) / n
        from scipy.optimize import minimize

        def risk_contribution(w: np.ndarray) -> np.ndarray:
            portfolio_var = w @ cov_matrix @ w
            sigma = np.sqrt(portfolio_var)
            mrc = cov_matrix @ w
            rc = w * mrc / sigma
            return rc

        def objective(w: np.ndarray) -> float:
            w = np.abs(w)
            w = w / w.sum()
            rc = risk_contribution(w)
            target_rc = rc.sum() / n
            return np.sum((rc - target_rc) ** 2)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0, 1) for _ in range(n)]
        result = minimize(objective, x0, bounds=bounds, constraints=constraints, method="SLSQP")
        weights = np.abs(result.x)
        return weights / weights.sum() if weights.sum() > 0 else x0

    def budget_risk(self, weights: np.ndarray, cov_matrix: np.ndarray) -> dict[str, float]:
        portfolio_var = weights @ cov_matrix @ weights
        sigma = np.sqrt(portfolio_var)
        mrc = cov_matrix @ weights
        rc = weights * mrc / sigma if sigma > 0 else np.zeros_like(weights)
        return {"portfolio_risk": float(sigma), "risk_contributions": rc.tolist()}
