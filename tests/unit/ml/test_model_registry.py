from __future__ import annotations


def test_model_registry_register():
    from ml.model_registry import ModelRegistry

    registry = ModelRegistry()
    model_id = registry.register(name="test_model", task="classification", framework="sklearn")
    assert model_id is not None


def test_model_registry_get():
    from ml.model_registry import ModelRegistry

    registry = ModelRegistry()
    model_id = registry.register(name="test_model", task="classification", framework="sklearn")
    model = registry.get(model_id)
    assert model is not None
    assert model["name"] == "test_model"


def test_model_registry_add_version():
    from ml.model_registry import ModelRegistry

    registry = ModelRegistry()
    model_id = registry.register(name="test_model", task="classification", framework="sklearn")
    version = registry.add_version(model_id, version="1.0.0", metrics={"accuracy": 0.85}, stage="production")
    assert version["version"] == "1.0.0"


def test_model_registry_get_version():
    from ml.model_registry import ModelRegistry

    registry = ModelRegistry()
    model_id = registry.register(name="test_model", task="classification", framework="sklearn")
    registry.add_version(model_id, version="1.0.0", metrics={"accuracy": 0.85})
    version = registry.get_version(model_id, "1.0.0")
    assert version is not None
    assert version["metrics"]["accuracy"] == 0.85


def test_model_registry_list():
    from ml.model_registry import ModelRegistry

    registry = ModelRegistry()
    registry.register(name="model_a", task="classification", framework="sklearn")
    registry.register(name="model_b", task="regression", framework="xgboost")
    models = registry.list_models()
    assert len(models) == 2
