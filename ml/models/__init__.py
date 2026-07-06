from ml.models.base import BaseModel
from ml.models.checkpointer import ModelCheckpointer
from ml.models.ensembler import ModelEnsembler
from ml.models.explainer import Explainer
from ml.models.interpreter import ModelInterpreter
from ml.models.registry import ModelRegistry, model_registry
from ml.models.serializer import ModelSerializer
from ml.models.sweeper import HyperparamSweeper
from ml.models.versioning import ModelVersion


def register_all_models() -> None:
    # ── Shallow models ──
    from ml.models.shallow.linear_models import LinearRegressionModel, LogisticRegressionModel
    from ml.models.shallow.tree_models import RandomForestModel, XGBoostModel

    model_registry.register("linear_regression", LinearRegressionModel)
    model_registry.register("logistic_regression", LogisticRegressionModel)
    model_registry.register("random_forest", RandomForestModel)
    model_registry.register("xgboost", XGBoostModel)

    # ── Deep models ──
    from ml.models.deep.lstm import LSTMModel
    from ml.models.deep.gru import GRUModel
    from ml.models.deep.cnn import CNNModel
    from ml.models.deep.transformer import TransformerModel

    model_registry.register("lstm", LSTMModel)
    model_registry.register("gru", GRUModel)
    model_registry.register("cnn", CNNModel)
    model_registry.register("transformer", TransformerModel)

    # ── Also register into the global metadata registry so models appear in API endpoints ──
    from ml.global_registry import get_registry

    global_registry = get_registry()
    existing_frameworks = {m["framework"] for m in global_registry.list_models()}

    shallow_models = [
        ("linear_regression", "Linear Regression", "regression", ["baseline"]),
        ("logistic_regression", "Logistic Regression", "classification", ["classification"]),
        ("random_forest", "Random Forest", "regression", ["ensemble"]),
        ("xgboost", "XGBoost", "regression", ["gradient-boosting"]),
    ]
    deep_models = [
        ("lstm", "LSTM", "regression", ["deep-learning", "time-series"]),
        ("gru", "GRU", "regression", ["deep-learning", "time-series"]),
        ("cnn", "CNN", "regression", ["deep-learning"]),
        ("transformer", "Transformer", "regression", ["deep-learning", "attention"]),
    ]

    for framework, name, task, tags in shallow_models + deep_models:
        if framework not in existing_frameworks:
            global_registry.register(name, task, framework, tags=tags)


__all__ = [
    "BaseModel",
    "ModelRegistry",
    "model_registry",
    "ModelVersion",
    "ModelSerializer",
    "HyperparamSweeper",
    "ModelInterpreter",
    "Explainer",
    "ModelCheckpointer",
    "ModelEnsembler",
    "register_all_models",
]
