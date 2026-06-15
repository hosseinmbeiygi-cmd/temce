from __future__ import annotations

from typing import Any


class ModelStabilityTest:
    def bootstrap_score(self, model: Any, X: Any, y: Any, n_bootstrap: int = 100) -> dict[str, float]:
        import numpy as np
        from sklearn.metrics import accuracy_score

        scores = []
        for _ in range(n_bootstrap):
            indices = np.random.choice(len(X), len(X), replace=True)
            X_boot, y_boot = X[indices], y[indices]
            model.fit(X_boot, y_boot)
            preds = model.predict(X)
            scores.append(accuracy_score(y, preds))
        return {"mean": float(np.mean(scores)), "std": float(np.std(scores))}
