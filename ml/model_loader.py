"""ModelLoader — lazy-loads ML models from disk with an LRU cache.

Architecture
--------------
Instead of loading all 359 artifact directories into memory at startup,
ModelLoader keeps at most ``maxsize`` models in an LRU cache (via
``functools.lru_cache``) and loads from disk on demand.

Typical memory-saving behaviour
--------------------------------
- A watchlist of ~20 symbols keeps its models hot in cache.
- Symbols that are only scanned occasionally are loaded, used, and evicted.
- Retraining a model calls ``invalidate(symbol, algorithm)`` so the stale
  entry is evicted; subsequent calls load the fresh artifact.

Usage
------
.. code-block:: python

    loader = ModelLoader()

    # Lazy load — picks the best available algorithm for `symbol`.
    model = await loader.get_model(symbol="فولاد")

    # Or get a specific algorithm for a symbol.
    model = await loader.get_model(symbol="فولاد", algorithm="xgboost")

    # Evict when the model is retrained.
    loader.invalidate(symbol="فولاد", algorithm="xgboost")
"""

from __future__ import annotations

import functools
import logging
import pickle
import time
from pathlib import Path
from typing import Any

from core.paths import models_path

logger = logging.getLogger(__name__)

# ── Shared constants ────────────────────────────────────────────────────────

_DEFAULT_MAXSIZE = 20  # max 20 models in LRU cache at any time
_ALGORITHM_PREFIXES = [
    "xgboost",
    "lightgbm",
    "catboost",
    "random_forest",
    "stacking_ensemble",
    "extra_trees",
    "hist_gradient_boosting",
    "huber_regressor",
    "bayesian_ridge",
    "bayesian",
]


class ModelLoader:
    """Lazy-load ML models for specific symbols, keeping a bounded LRU cache.

    Parameters
    ----------
    base_dir : str | None
        Override the artifact base directory (defaults to ``settings.ml_model_dir``).
    maxsize : int
        Maximum number of models kept in the LRU cache (default 20).
    """

    def __init__(
        self,
        base_dir: str | None = None,
        maxsize: int = _DEFAULT_MAXSIZE,
    ) -> None:
        self._base_dir = Path(base_dir or models_path()).resolve()
        self._maxsize = maxsize

        # LRU-cached loader — one per process, thread-safe via functools.
        self._load_cached = functools.lru_cache(maxsize=maxsize)(
            self._load_from_disk
        )

        # Model → (timestamp, model_obj, symbol, algorithm)  for invalidation.
        self._loaded: dict[str, _CacheEntry] = {}

    # ── Public API ─────────────────────────────────────────────────────────

    async def get_model(
        self,
        symbol: str,
        algorithm: str | None = None,
    ) -> Any | None:
        """Return a trained model for *symbol*, optionally picking *algorithm*.

        When *algorithm* is ``None`` the first available algorithm (by priority
        in ``_ALGORITHM_PREFIXES``) is returned.  Returns ``None`` when no
        artifact exists for the given (symbol, algorithm) pair.
        """
        algorithms = [algorithm] if algorithm else _ALGORITHM_PREFIXES

        for algo in algorithms:
            cache_key = f"{algo}_{symbol}"
            try:
                model = self._load_cached(cache_key)
                self._loaded[cache_key] = _CacheEntry(
                    timestamp=time.time(),
                    model=model,
                    symbol=symbol,
                    algorithm=algo,
                )
                return model
            except FileNotFoundError:
                continue

        logger.debug("No trained model found for %s / %s", symbol, algorithm or "any")
        return None

    async def preload(
        self,
        symbols: list[str],
        algorithms: list[str] | None = None,
    ) -> dict[str, Any]:
        """Warm the cache for a set of *active* symbols.

        Callers (e.g. the signal pipeline) pass the symbols that are actually
        needed right now — typically the union of the active Watchlist and
        Smart Screener symbols — and only those models are loaded into the
        LRU cache.  Symbols without an artifact on disk are skipped silently
        (no exception).  This keeps startup light while ensuring the hot
        symbols' models stay resident.

        Usage::

            loader = get_model_loader()
            report = await loader.preload(
                symbols=["فولاد", "وبملت", "خودرو"],
            )
            logger.info("Preloaded %d models: %s", report["loaded"], report["missing"])

        Parameters
        ----------
        symbols : list[str]
            Symbols whose models should be cached (watchlist / screener).
        algorithms : list[str] | None
            Optional algorithm whitelist (defaults to the priority order in
            ``_ALGORITHM_PREFIXES``).

        Returns
        -------
        dict
            ``{"loaded": int, "missing": list[str], "symbols": list[str]}``
        """
        algo_list = list(algorithms) if algorithms else None
        loaded = 0
        missing: list[str] = []

        for sym in symbols:
            if algo_list is None or len(algo_list) == 1:
                # Default priority order (or a single whitelisted algorithm).
                model = await self.get_model(
                    symbol=sym,
                    algorithm=algo_list[0] if algo_list else None,
                )
            else:
                # Multi-algorithm whitelist — try each in order.
                model = None
                for algo in algo_list:
                    model = await self.get_model(symbol=sym, algorithm=algo)
                    if model is not None:
                        break

            if model is not None:
                loaded += 1
            else:
                missing.append(sym)

        logger.info(
            "ModelLoader.preload: %d loaded, %d missing of %d symbols",
            loaded, len(missing), len(symbols),
        )
        return {"loaded": loaded, "missing": missing, "symbols": list(symbols)}

    def invalidate(self, symbol: str, algorithm: str | None = None) -> None:
        """Evict cached model(s) for *symbol*.

        When *algorithm* is ``None`` all cached entries for *symbol* are
        evicted (e.g. after full retrain).  Otherwise only the specific
        algorithm is evicted.
        """
        if algorithm:
            keys = [f"{algorithm}_{symbol}"]
        else:
            keys = [
                k for k, entry in self._loaded.items()
                if entry.symbol == symbol
            ]

        for key in keys:
            self._loaded.pop(key, None)
            try:
                self._load_cached.cache_clear()
            except AttributeError:
                pass

        # Rebuild cache from remaining entries.
        remaining = dict(self._loaded)
        self._load_cached = functools.lru_cache(maxsize=self._maxsize)(
            self._load_from_disk
        )
        # Warm the new LRU with the survivors (oldest-first so LRU is fresh).
        for key, entry in sorted(remaining.items(), key=lambda kv: kv[1].timestamp):
            self._load_cached(key)  # side-effect: populates LRU
            self._loaded[key] = entry

        logger.info("Invalidated model cache for %s (%s)", symbol, algorithm or "all")

    def list_cached_symbols(self) -> list[str]:
        """Return symbols whose models are currently hot in cache."""
        return sorted({e.symbol for e in self._loaded.values()})

    def cache_info(self) -> dict[str, Any]:
        """Diagnostic info about the LRU cache."""
        info = self._load_cached.cache_info()
        return {
            "maxsize": self._maxsize,
            "currsize": info.currsize,
            "hits": info.hits,
            "misses": info.misses,
            "cached_symbols": self.list_cached_symbols(),
        }

    def clear(self) -> None:
        """Evict all cached models (e.g. before a full reload)."""
        self._loaded.clear()
        self._load_cached.cache_clear()
        logger.info("ModelLoader cache cleared")

    # ── Internal ───────────────────────────────────────────────────────────

    def _load_from_disk(self, cache_key: str) -> Any:
        """Load a pickled model from the artifact directory.

        Raises ``FileNotFoundError`` when no artifact exists for *cache_key*.
        """
        artifact_dir = self._base_dir / cache_key
        if not artifact_dir.is_dir():
            raise FileNotFoundError(f"No artifact directory: {artifact_dir}")

        # Try the new format (model_pipeline.pkl) first, then legacy (model.pkl).
        candidates = [
            artifact_dir / "model_pipeline.pkl",
            artifact_dir / "model.pkl",
        ]
        for model_file in candidates:
            if model_file.exists():
                with open(model_file, "rb") as f:
                    obj = pickle.load(f)
                logger.debug("Loaded model from %s", model_file)
                return obj

        raise FileNotFoundError(
            f"No model file found in {artifact_dir} "
            f"(tried: {[p.name for p in candidates]})"
        )


# ── Internal data structure ─────────────────────────────────────────────────


class _CacheEntry:
    """Minimal entry for the in-memory model cache."""

    __slots__ = ("timestamp", "model", "symbol", "algorithm")

    def __init__(
        self,
        timestamp: float,
        model: Any,
        symbol: str,
        algorithm: str,
    ) -> None:
        self.timestamp = timestamp
        self.model = model
        self.symbol = symbol
        self.algorithm = algorithm


# ── Global singleton ────────────────────────────────────────────────────────

_model_loader: ModelLoader | None = None


def get_model_loader(
    base_dir: str | None = None,
    maxsize: int = _DEFAULT_MAXSIZE,
) -> ModelLoader:
    """Get or create the global ModelLoader singleton."""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader(base_dir=base_dir, maxsize=maxsize)
    return _model_loader
