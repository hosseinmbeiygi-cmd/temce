from __future__ import annotations

import pytest


def test_feature_store_get_features():
    from ml.feature_store import FeatureStore

    store = FeatureStore()
    store.register_feature("close", "quote", "float64")
    store.register_feature("volume", "quote", "int64")
    features = store.get_features()
    assert "close" in features
    assert "volume" in features


def test_feature_store_get_by_group():
    from ml.feature_store import FeatureStore

    store = FeatureStore()
    store.register_feature("sma_20", "technical", "float64")
    store.register_feature("rsi", "technical", "float64")
    store.register_feature("eps", "fundamental", "float64")
    technical = store.get_features_by_group("technical")
    fundamental = store.get_features_by_group("fundamental")
    assert len(technical) == 2
    assert len(fundamental) == 1


def test_feature_store_duplicate_registration():
    from ml.feature_store import FeatureStore

    store = FeatureStore()
    store.register_feature("close", "quote", "float64")
    with pytest.raises(ValueError):
        store.register_feature("close", "quote", "float64")


def test_feature_store_list_groups():
    from ml.feature_store import FeatureStore

    store = FeatureStore()
    store.register_feature("close", "price", "float64")
    store.register_feature("eps", "fundamental", "float64")
    groups = store.list_groups()
    assert "price" in groups
    assert "fundamental" in groups


def test_feature_store_remove():
    from ml.feature_store import FeatureStore

    store = FeatureStore()
    store.register_feature("close", "price", "float64")
    store.remove_feature("close")
    assert "close" not in store.get_features()

