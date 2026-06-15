from __future__ import annotations

from typing import Any


class Explainer:
    def shap_values(self, model: Any, X: Any) -> Any:
        try:
            import shap

            explainer = shap.Explainer(model, X)
            return explainer(X)
        except ImportError:
            return None

    def lime_explain(self, model: Any, X: Any, instance: Any) -> dict[str, float] | None:
        try:
            from lime.lime_tabular import LimeTabularExplainer

            explainer = LimeTabularExplainer(X, mode="classification")
            exp = explainer.explain_instance(instance, model.predict_proba)
            return dict(exp.as_list())
        except ImportError:
            return None
