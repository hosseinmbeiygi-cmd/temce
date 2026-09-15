from __future__ import annotations

from typing import Any


class HyperparamSweeper:
    def grid_search(self, model_cls: type, param_grid: dict[str, list[Any]], X: Any, y: Any) -> dict[str, Any]:
        from sklearn.base import BaseEstimator
        from sklearn.model_selection import GridSearchCV

        estimator = model_cls() if isinstance(model_cls(), BaseEstimator) else model_cls
        search = GridSearchCV(estimator, param_grid, cv=5)
        search.fit(X, y)
        return {"best_params": search.best_params_, "best_score": search.best_score_}

    def random_search(
        self, model_cls: type, param_dist: dict[str, Any], X: Any, y: Any, n_iter: int = 20
    ) -> dict[str, Any]:
        from sklearn.base import BaseEstimator
        from sklearn.model_selection import RandomizedSearchCV

        estimator = model_cls() if isinstance(model_cls(), BaseEstimator) else model_cls
        search = RandomizedSearchCV(estimator, param_dist, n_iter=n_iter, cv=5)
        search.fit(X, y)
        return {"best_params": search.best_params_, "best_score": search.best_score_}
