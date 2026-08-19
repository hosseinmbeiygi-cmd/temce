"""Tests for ``ml/model_loader.py`` — ModelLoader with LRU cache.

Uses a temporary directory with pickled model stubs to avoid touching
the real ``ml_artifacts/`` directory.
"""

from __future__ import annotations

import os
import pickle
import tempfile
from pathlib import Path

import pytest

from ml.model_loader import ModelLoader


class _DummyModel:
    """Minimal model stub — picklable, has is_fitted."""
    is_fitted = True

    def predict(self, X):
        return [0.5]


@pytest.fixture
def artifact_dir():
    """Create a temporary artifact directory with a few fake models.

    Directory layout::

        {tmp}/
            xgboost_فولاد/
                model.pkl
            lightgbm_فولاد/
                model.pkl
            random_forest_فولاد/
                model_pipeline.pkl
            xgboost_خودرو/
                model.pkl
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        models = [
            ("xgboost_فولاد", "model.pkl"),
            ("lightgbm_فولاد", "model.pkl"),
            ("random_forest_فولاد", "model_pipeline.pkl"),
            ("xgboost_خودرو", "model.pkl"),
        ]

        for dir_name, file_name in models:
            d = base / dir_name
            d.mkdir(parents=True, exist_ok=True)
            with open(d / file_name, "wb") as f:
                pickle.dump(_DummyModel(), f)

        yield str(base)


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_model_returns_model(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    model = await loader.get_model(symbol="فولاد", algorithm="xgboost")
    assert model is not None
    assert model.is_fitted


@pytest.mark.asyncio
async def test_get_model_returns_none_when_missing(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    model = await loader.get_model(symbol="ناموجود", algorithm="xgboost")
    assert model is None


@pytest.mark.asyncio
async def test_get_model_auto_picks_algorithm(artifact_dir):
    """When no algorithm is specified, pick the first available by priority."""
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    model = await loader.get_model(symbol="فولاد")
    assert model is not None  # xgboost_فولاد should be found first


@pytest.mark.asyncio
async def test_get_model_new_format(artifact_dir):
    """model_pipeline.pkl (new format) is preferred over model.pkl."""
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    model = await loader.get_model(symbol="فولاد", algorithm="random_forest")
    assert model is not None
    assert model.is_fitted


@pytest.mark.asyncio
async def test_invalidate_evicts_specific_algorithm(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    # Load once to populate cache.
    m1 = await loader.get_model(symbol="فولاد", algorithm="xgboost")
    assert m1 is not None
    assert "xgboost_فولاد" in loader._loaded

    # Invalidate just xgboost for فولاد.
    loader.invalidate(symbol="فولاد", algorithm="xgboost")
    assert "xgboost_فولاد" not in loader._loaded

    # lightgbm for the same symbol should still be cached (if loaded).
    # xgboost_خودرو should still be cached (different symbol).
    await loader.get_model(symbol="خودرو", algorithm="xgboost")
    assert "xgboost_خودرو" in loader._loaded

    loader.invalidate(symbol="خودرو", algorithm="xgboost")
    assert "xgboost_خودرو" not in loader._loaded


@pytest.mark.asyncio
async def test_invalidate_all_clears_symbol(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    await loader.get_model(symbol="فولاد", algorithm="xgboost")
    await loader.get_model(symbol="فولاد", algorithm="lightgbm")

    assert "xgboost_فولاد" in loader._loaded
    assert "lightgbm_فولاد" in loader._loaded

    loader.invalidate(symbol="فولاد")  # no algorithm → all for symbol
    assert "xgboost_فولاد" not in loader._loaded
    assert "lightgbm_فولاد" not in loader._loaded


@pytest.mark.asyncio
async def test_cache_size_bounded(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=2)

    await loader.get_model(symbol="فولاد", algorithm="xgboost")
    await loader.get_model(symbol="خودرو", algorithm="xgboost")

    info = loader.cache_info()
    assert info["currsize"] <= 2
    assert info["hits"] == 0
    assert info["misses"] == 2

    # Hit on cached.
    await loader.get_model(symbol="فولاد", algorithm="xgboost")
    info = loader.cache_info()
    assert info["hits"] == 1


@pytest.mark.asyncio
async def test_clear_evicts_everything(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    await loader.get_model(symbol="فولاد", algorithm="xgboost")
    await loader.get_model(symbol="خودرو", algorithm="xgboost")
    assert len(loader._loaded) == 2

    loader.clear()
    assert len(loader._loaded) == 0
    assert loader.cache_info()["currsize"] == 0


def test_list_cached_symbols(artifact_dir):
    import asyncio
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    async def _load():
        await loader.get_model(symbol="فولاد", algorithm="xgboost")
        return loader.list_cached_symbols()

    syms = asyncio.run(_load())
    assert "فولاد" in syms


@pytest.mark.asyncio
async def test_get_model_no_algorithm_returns_first_available(artifact_dir):
    """When symbol exists with multiple algorithms but algorithm=None."""
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    model = await loader.get_model(symbol="فولاد")
    assert model is not None


@pytest.mark.asyncio
async def test_get_model_no_artifact_dir_returns_none(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)
    model = await loader.get_model(symbol="غیرموجود")
    assert model is None


# ── Preload (watchlist / screener-aware warm-up) ─────────────────────────────


@pytest.mark.asyncio
async def test_preload_loads_only_existing_symbols(artifact_dir):
    """Only symbols with artifacts get loaded; others are reported missing."""
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    report = await loader.preload(symbols=["فولاد", "ناموجود", "خودرو"])

    assert report["loaded"] == 2
    assert "ناموجود" in report["missing"]
    assert "xgboost_فولاد" in loader._loaded
    assert "xgboost_خودرو" in loader._loaded
    assert "ناموجود" not in loader.list_cached_symbols()


@pytest.mark.asyncio
async def test_preload_respects_algorithm_whitelist(artifact_dir):
    """When algorithms are restricted, only those are considered."""
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    # Only lightgbm exists for فولاد; restrict to algorithms that don't exist.
    report = await loader.preload(symbols=["فولاد"], algorithms=["huber_regressor"])
    assert report["loaded"] == 0
    assert "فولاد" in report["missing"]

    # Restricting to lightgbm finds the artifact.
    report2 = await loader.preload(symbols=["فولاد"], algorithms=["lightgbm"])
    assert report2["loaded"] == 1
    assert "lightgbm_فولاد" in loader._loaded


@pytest.mark.asyncio
async def test_preload_empty_symbols_is_noop(artifact_dir):
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)
    report = await loader.preload(symbols=[])
    assert report == {"loaded": 0, "missing": [], "symbols": []}


@pytest.mark.asyncio
async def test_preload_populates_cache_so_get_model_hits(artifact_dir):
    """After preload, get_model should hit the cache (misses unchanged)."""
    loader = ModelLoader(base_dir=artifact_dir, maxsize=5)

    await loader.preload(symbols=["فولاد"])
    info_before = loader.cache_info()

    model = await loader.get_model(symbol="فولاد", algorithm="xgboost")
    assert model is not None
    info_after = loader.cache_info()
    assert info_after["hits"] > info_before["hits"]