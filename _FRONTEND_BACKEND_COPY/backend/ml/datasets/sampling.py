from __future__ import annotations

import numpy as np
import pandas as pd

from ml.types import FeatureMatrix, TargetVector


class DataSampler:
    def balanced_sample(
        self, features: FeatureMatrix, targets: TargetVector, random_state: int = 42
    ) -> tuple[FeatureMatrix, TargetVector]:
        try:
            from imblearn.over_sampling import RandomOverSampler

            ros = RandomOverSampler(random_state=random_state)
            X_res, y_res = ros.fit_resample(features.data, targets.data)
            return FeatureMatrix(data=X_res, feature_names=features.feature_names), TargetVector(
                data=pd.Series(y_res, name=targets.name)
            )
        except ImportError:
            return features, targets

    def temporal_sample(
        self, features: FeatureMatrix, targets: TargetVector, max_samples: int = 10000
    ) -> tuple[FeatureMatrix, TargetVector]:
        n = features.shape[0]
        if n <= max_samples:
            return features, targets
        indices = np.linspace(0, n - 1, max_samples, dtype=int)
        return (
            FeatureMatrix(data=features.data.iloc[indices], feature_names=features.feature_names),
            TargetVector(data=targets.data.iloc[indices], name=targets.name),
        )
