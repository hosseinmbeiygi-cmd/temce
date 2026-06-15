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
    from ml.models.shallow.linear_models import LinearRegressionModel, LogisticRegressionModel
    from ml.models.shallow.tree_models import RandomForestModel, XGBoostModel

    model_registry.register("linear_regression", LinearRegressionModel)
    model_registry.register("logistic_regression", LogisticRegressionModel)
    model_registry.register("random_forest", RandomForestModel)
    model_registry.register("xgboost", XGBoostModel)


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
