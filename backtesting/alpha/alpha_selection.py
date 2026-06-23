from __future__ import annotations

from typing import Any

import numpy as np


class AlphaSelection:
    """Selects the best alphas using clustering, stability, and capacity analysis."""

    def __init__(self, n_select: int = 20, max_correlation: float = 0.7) -> None:
        self.n_select = n_select
        self.max_correlation = max_correlation
        self._selected: list[str] = []

    def cluster(self, alpha_returns: dict[str, list[float]]) -> dict[str, list[str]]:
        """Cluster alphas by return correlation using hierarchical clustering.

        Args:
            alpha_returns: Dict of {alpha_id: return_series}

        Returns:
            Dict of {cluster_id: [alpha_ids]}
        """
        ids = list(alpha_returns.keys())
        if len(ids) < 2:
            return {"cluster_0": ids}

        returns_matrix = np.array([alpha_returns[a] for a in ids])
        corr = np.corrcoef(returns_matrix)

        # Simple clustering: group by correlation threshold
        clusters: dict[str, list[str]] = {}
        assigned = set()

        for i, aid in enumerate(ids):
            if aid in assigned:
                continue
            cluster_id = f"cluster_{len(clusters)}"
            clusters[cluster_id] = [aid]
            assigned.add(aid)

            for j, bid in enumerate(ids):
                if bid in assigned or i == j:
                    continue
                if abs(corr[i, j]) > self.max_correlation:
                    clusters[cluster_id].append(bid)
                    assigned.add(bid)

        # Assign remaining unassigned
        for aid in ids:
            if aid not in assigned:
                clusters[f"cluster_{len(clusters)}"] = [aid]

        return clusters

    def select_from_clusters(self, alpha_metrics: dict[str, Any], clusters: dict[str, list[str]]) -> list[str]:
        """Select the best alpha from each cluster.

        Args:
            alpha_metrics: Dict of {alpha_id: metric_value} (higher = better)
            clusters: Dict of {cluster_id: [alpha_ids]}

        Returns:
            List of selected alpha IDs
        """
        selected: list[str] = []
        for cluster_id, alpha_ids in clusters.items():
            if not alpha_ids:
                continue

            # Pick the best alpha in each cluster
            best = max(alpha_ids, key=lambda a: alpha_metrics.get(a, 0))
            selected.append(best)

            if len(selected) >= self.n_select:
                break

        return selected[:self.n_select]

    def select(self, alpha_metrics: dict[str, float], alpha_returns: dict[str, list[float]]) -> list[str]:
        """Full selection pipeline: cluster then select.

        Args:
            alpha_metrics: Dict of {alpha_id: metric_value}
            alpha_returns: Dict of {alpha_id: return_series}

        Returns:
            List of selected alpha IDs
        """
        clusters = self.cluster(alpha_returns)
        self._selected = self.select_from_clusters(alpha_metrics, clusters)
        return self._selected

    @staticmethod
    def stability_test(alpha_returns: dict[str, list[float]], window: int = 63) -> dict[str, float]:
        """Test alpha stability using rolling Sharpe ratio.

        Args:
            alpha_returns: Dict of {alpha_id: return_series}
            window: Rolling window size

        Returns:
            Dict of {alpha_id: stability_score} where higher = more stable
        """
        stability: dict[str, float] = {}
        for alpha_id, returns in alpha_returns.items():
            if len(returns) < window * 2:
                stability[alpha_id] = 0.0
                continue

            arr = np.array(returns)
            rolling_sharpes: list[float] = []
            for i in range(len(arr) - window):
                window_returns = arr[i:i + window]
                mean_r = np.mean(window_returns)
                std_r = np.std(window_returns)
                if std_r > 0:
                    rolling_sharpes.append(mean_r / std_r)

            if rolling_sharpes:
                std_sharpe = float(np.std(rolling_sharpes))
                stability[alpha_id] = 1.0 / (1.0 + std_sharpe)
            else:
                stability[alpha_id] = 0.0

        return stability

    @staticmethod
    def capacity_analysis(alpha_turnover: dict[str, float], adv: float, max_participation: float = 0.1) -> dict[str, float]:
        """Estimate alpha capacity (how much capital it can handle).
        
        Capacity ≈ ADV * participation / turnover
        """
        capacity: dict[str, float] = {}
        for alpha_id, turnover in alpha_turnover.items():
            if turnover > 0:
                capacity[alpha_id] = adv * max_participation / turnover
            else:
                capacity[alpha_id] = float("inf")
        return capacity

    @staticmethod
    def alpha_decay(alpha_id: str, signal: list[float], returns: list[float], max_lag: int = 20) -> dict[int, float]:
        """Calculate IC at various lags to see how fast the signal decays.

        Args:
            alpha_id: Alpha identifier
            signal: Alpha signal values
            returns: Forward returns
            max_lag: Maximum lag to test

        Returns:
            Dict of {lag: IC_value}
        """
        signal_arr = np.array(signal)
        returns_arr = np.array(returns)
        ics: dict[int, float] = {}

        for lag in range(1, min(max_lag + 1, len(signal_arr) - 1)):
            lagged = signal_arr[:-lag]
            forward = returns_arr[lag:]
            n = min(len(lagged), len(forward))
            if n < 10:
                continue

            lagged = lagged[:n]
            forward = forward[:n]

            if np.std(lagged) > 0 and np.std(forward) > 0:
                corr = np.corrcoef(lagged, forward)
                ics[lag] = float(corr[0, 1]) if corr.shape == (2, 2) else 0.0

        return ics

    @property
    def selected(self) -> list[str]:
        return list(self._selected)
