from __future__ import annotations

from typing import Any


class FeatureSelector:
    def select_k_best(self, features: Any, targets: Any, k: int = 10):
        from sklearn.feature_selection import SelectKBest, f_classif

        selector = SelectKBest(score_func=f_classif, k=k)
        return selector.fit_transform(features, targets), selector

    def variance_threshold(self, features: Any, threshold: float = 0.0):
        from sklearn.feature_selection import VarianceThreshold

        selector = VarianceThreshold(threshold=threshold)
        return selector.fit_transform(features), selector
