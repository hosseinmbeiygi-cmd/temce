from __future__ import annotations

from typing import Any


class Regularization:
    @staticmethod
    def l1_penalty(weights: Any, lambda_val: float = 0.01) -> float:
        import numpy as np

        return float(lambda_val * np.sum(np.abs(weights)))

    @staticmethod
    def l2_penalty(weights: Any, lambda_val: float = 0.01) -> float:
        import numpy as np

        return float(lambda_val * np.sum(weights**2))

    @staticmethod
    def elastic_net(weights: Any, l1_ratio: float = 0.5, lambda_val: float = 0.01) -> float:
        l1 = Regularization.l1_penalty(weights, lambda_val)
        l2 = Regularization.l2_penalty(weights, lambda_val)
        return l1_ratio * l1 + (1 - l1_ratio) * l2
