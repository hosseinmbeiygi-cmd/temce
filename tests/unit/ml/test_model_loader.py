"""Unit tests for the ModelLoader (lazy-loading ML model cache).

Covers:
  - ``get_model`` with an explicit algorithm / auto-priority / missing artifact
  - new (``model_pipeline.pkl``) and legacy (``model.pkl``) artifact formats
  - ``preload`` loaded / missing reporting
  - ``invalidate`` (single algorithm and whole symbol)
  - ``clear`` / ``cache_info`` / ``list_cached_symbols``

Artifacts are pickled into ``tmp_path`` — no real ML models needed.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import pytest

from ml.model_loader import ModelLoader

# ── Helpers ───────────────────────────────────────────────────────────────


def _write_artifact(base: Path, cache_key: str, filename: str = "model_pipeline.pkl", payload: Any = None) -> Path:
    """Create an artifact dir ``base/<cache_key>/<filename>`` with a pickled payload."""
    artifact_dir = base / cache_key
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_file = artifact_dir / filename
    with open(model_file, "wb") as f:
        pickle.dump(payload if payload is not None else {"name": cache_key}, f)
    return model_file


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def loader(base_dir: Path) -> ModelLoader:
    return ModelLoader(base_dir=str(base_dir), maxsize=5)


# ── get_model ─────────────────────────────────────────────────────────────


class TestGetModel:
    @pytest.mark.asyncio
    async def test_returns_model_for_explicit_algorithm(self, loader: ModelLoader, base_dir: Path) -> None:
        payload = {"algo": "xgboost", "symbol": "فولاد"}
        _write_artifact(base_dir, "xgboost_فولاد", payload=payload)

        model = await loader.get_model(symbol="فولاد", algorithm="xgboost")

        assert model == payload

    @pytest.mark.asyncio
    async def test_picks_first_available_algorithm_by_priority(self, loader: ModelLoader, base_dir: Path) -> None:
        """Without an algorithm, priority order decides — random_forest > bayesian."""
        rf_payload = {"algo": "random_forest"}
        _write_artifact(base_dir, "random_forest_خودرو", payload=rf_payload)
        _write_artifact(base_dir, "bayesian_خودرو", payload={"algo": "bayesian"})

        model = await loader.get_model(symbol="خودرو")

        assert model == rf_payload

    @pytest.mark.asyncio
    async def test_returns_none_when_no_artifact(self, loader: ModelLoader, base_dir: Path) -> None:
        model = await loader.get_model(symbol="غایب")
        assert model is None

    @pytest.mark.asyncio
    async def test_loads_legacy_model_pkl_format(self, loader: ModelLoader, base_dir: Path) -> None:
        payload = {"legacy": True}
        _write_artifact(base_dir, "lightgbm_شستا", filename="model.pkl", payload=payload)

        model = await loader.get_model(symbol="شستا", algorithm="lightgbm")

        assert model == payload

    @pytest.mark.asyncio
    async def test_prefers_new_format_over_legacy(self, loader: ModelLoader, base_dir: Path) -> None:
        _write_artifact(base_dir, "catboost_فولاد", filename="model_pipeline.pkl", payload={"new": True})
        _write_artifact(base_dir, "catboost_فولاد", filename="model.pkl", payload={"legacy": True})

        model = await loader.get_model(symbol="فولاد", algorithm="catboost")

        assert model == {"new": True}


# ── preload ───────────────────────────────────────────────────────────────


class TestPreload:
    @pytest.mark.asyncio
    async def test_reports_loaded_and_missing(self, loader: ModelLoader, base_dir: Path) -> None:
        _write_artifact(base_dir, "xgboost_فولاد", payload={"a": 1})

        report = await loader.preload(symbols=["فولاد", "خودرو", "وبملت"])

        assert report["loaded"] == 1
        assert report["missing"] == ["خودرو", "وبملت"]
        assert report["symbols"] == ["فولاد", "خودرو", "وبملت"]
        # Loaded symbol is now hot in cache.
        assert "فولاد" in loader.list_cached_symbols()

    @pytest.mark.asyncio
    async def test_respects_algorithm_whitelist(self, loader: ModelLoader, base_dir: Path) -> None:
        _write_artifact(base_dir, "lightgbm_فولاد", payload={"algo": "lightgbm"})

        report = await loader.preload(symbols=["فولاد"], algorithms=["catboost", "lightgbm"])

        assert report["loaded"] == 1
        assert report["missing"] == []


# ── invalidate ────────────────────────────────────────────────────────────


class TestInvalidate:
    @pytest.mark.asyncio
    async def test_invalidate_single_algorithm(self, loader: ModelLoader, base_dir: Path) -> None:
        _write_artifact(base_dir, "xgboost_فولاد", payload={"a": 1})
        await loader.get_model(symbol="فولاد", algorithm="xgboost")
        assert "فولاد" in loader.list_cached_symbols()

        loader.invalidate(symbol="فولاد", algorithm="xgboost")

        assert "فولاد" not in loader.list_cached_symbols()

    @pytest.mark.asyncio
    async def test_invalidate_all_algorithms_for_symbol(self, loader: ModelLoader, base_dir: Path) -> None:
        _write_artifact(base_dir, "xgboost_فولاد", payload={"a": 1})
        _write_artifact(base_dir, "catboost_فولاد", payload={"b": 2})
        _write_artifact(base_dir, "xgboost_خودرو", payload={"c": 3})
        await loader.preload(symbols=["فولاد", "خودرو"])
        assert set(loader.list_cached_symbols()) == {"فولاد", "خودرو"}

        loader.invalidate(symbol="فولاد")

        assert "فولاد" not in loader.list_cached_symbols()
        assert "خودرو" in loader.list_cached_symbols()


# ── cache lifecycle ───────────────────────────────────────────────────────


class TestCacheLifecycle:
    @pytest.mark.asyncio
    async def test_lru_evicts_least_recently_used(self, base_dir: Path) -> None:
        small = ModelLoader(base_dir=str(base_dir), maxsize=2)
        for sym in ["فولاد", "خودرو", "وبملت", "شستا"]:
            _write_artifact(base_dir, f"xgboost_{sym}", payload={"s": sym})
            await small.get_model(symbol=sym, algorithm="xgboost")

        # The LRU cache itself is bounded by maxsize=2 — 4 loads, 4 misses.
        info = small.cache_info()
        assert info["maxsize"] == 2
        assert info["currsize"] == 2
        assert info["misses"] == 4

        # Reloading an evicted symbol bumps the miss counter (disk reload);
        # a hit on a resident symbol does not.
        await small.get_model(symbol="فولاد", algorithm="xgboost")  # evicted → miss
        await small.get_model(symbol="شستا", algorithm="xgboost")   # resident → hit
        info = small.cache_info()
        assert info["misses"] == 5
        assert info["hits"] == 1

    @pytest.mark.asyncio
    async def test_clear_empties_cache(self, loader: ModelLoader, base_dir: Path) -> None:
        _write_artifact(base_dir, "xgboost_فولاد", payload={"a": 1})
        await loader.get_model(symbol="فولاد", algorithm="xgboost")

        loader.clear()

        assert loader.list_cached_symbols() == []
        assert loader.cache_info()["currsize"] == 0

    @pytest.mark.asyncio
    async def test_cache_info_tracks_hits_and_misses(self, loader: ModelLoader, base_dir: Path) -> None:
        _write_artifact(base_dir, "xgboost_فولاد", payload={"a": 1})

        await loader.get_model(symbol="فولاد", algorithm="xgboost")
        await loader.get_model(symbol="فولاد", algorithm="xgboost")  # cache hit
        await loader.get_model(symbol="غایب")  # miss

        info = loader.cache_info()
        assert info["maxsize"] == 5
        assert info["currsize"] >= 1
        assert info["hits"] >= 1
        assert info["misses"] >= 2
        assert "فولاد" in info["cached_symbols"]
