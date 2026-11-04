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

import contextlib
import functools
import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Shared constants ────────────────────────────────────────────────────────

_DEFAULT_MAXSIZE = 20  # max 20 models in LRU cache at any time

# ML-007: a pickled model is executable code. Loading an artifact whose bytes
# do not match the hash recorded at save time means the file changed after it
# was produced — corruption at best, tampering at worst — so it is refused.
# ``ML_ALLOW_UNVERIFIED_MODELS=1`` is the explicit escape hatch for legacy
# artifacts written before hashing existed.
_ALLOW_UNVERIFIED_ENV = "ML_ALLOW_UNVERIFIED_MODELS"
_TRUTHY = {"1", "true", "yes", "on"}
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
        # Same root resolution as ArtifactManager (audit F-01): the configured
        # ML_MODEL_DIR may be empty while the artifacts live in ml_artifacts/.
        from ml.artifacts import resolve_artifact_root

        self._base_dir = resolve_artifact_root(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
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
            model_key = f"{algo}_{symbol}"
            # ML-006: key the cache on the artifact *version*, not just the
            # name. Retraining writes a new version next to the old one; a
            # name-only key would keep serving the previous model until the
            # process restarted.
            version = self._artifact_version(model_key)
            cache_key = f"{model_key}@{version}" if version else model_key
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
            prefix = f"{algorithm}_{symbol}"
            keys = [
                k for k in self._loaded
                if k == prefix or k.startswith(f"{prefix}@")
            ]
        else:
            keys = [
                k for k, entry in self._loaded.items()
                if entry.symbol == symbol
            ]

        for key in keys:
            self._loaded.pop(key, None)
            with contextlib.suppress(AttributeError):
                self._load_cached.cache_clear()

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

    def _artifact_version(self, model_key: str) -> str | None:
        """Version string that identifies the artifact currently on disk.

        Prefers the version folder written by the training pipeline, then the
        ``artifact_hash`` recorded in ``metadata.json``, and finally
        ``mtime-size`` for flat-layout artifacts that carry no metadata. Each
        of these changes when the model is retrained, which is what makes the
        LRU entry stale-proof (ML-006).
        """
        from ml.artifacts import MODEL_FILE_CANDIDATES, latest_version

        artifact_dir = self._base_dir / model_key
        if not artifact_dir.is_dir():
            return None

        version = latest_version(artifact_dir)
        if version:
            return version

        for name in MODEL_FILE_CANDIDATES:
            model_file = artifact_dir / name
            if not model_file.is_file():
                continue
            meta_file = artifact_dir / "metadata.json"
            with contextlib.suppress(OSError, ValueError, AttributeError):
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                digests = self._recorded_digests(meta) if isinstance(meta, dict) else []
                if digests:
                    return digests[0][1][:16]
            try:
                stat = model_file.stat()
            except OSError:
                return None
            return f"m{int(stat.st_mtime)}-{stat.st_size}"
        return None

    @staticmethod
    def _recorded_digests(meta: dict[str, Any]) -> list[tuple[str, str]]:
        """``(algorithm, hexdigest)`` pairs declared by an artifact's metadata.

        Two producers write these files: :meth:`ArtifactManager.save_model`
        records a sha256 in ``artifact_hash``, while the external training
        toolchain records an md5 in ``checksum``. Both are file digests, so
        both are honoured.
        """
        pairs: list[tuple[str, str]] = []
        sha = str(meta.get("artifact_hash") or "")
        if len(sha) == 64:
            pairs.append(("sha256", sha.lower()))
        md5 = str(meta.get("checksum") or "")
        if len(md5) == 32:
            pairs.append(("md5", md5.lower()))
        return pairs

    def _assert_integrity(self, model_file: Path) -> None:
        """Refuse to unpickle an artifact that fails its recorded hash (ML-007)."""
        meta_file = model_file.parent / "metadata.json"
        recorded: list[tuple[str, str]] = []
        if meta_file.is_file():
            with contextlib.suppress(OSError, ValueError, AttributeError):
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if isinstance(meta, dict):
                    recorded = self._recorded_digests(meta)

        if recorded:
            raw = model_file.read_bytes()
            for algorithm, expected in recorded:
                digest = hashlib.new(algorithm, raw).hexdigest()
                if not hmac.compare_digest(digest, expected):
                    raise ValueError(
                        f"Model integrity check FAILED for {model_file}: recorded "
                        f"{algorithm} {expected[:12]}… does not match the file on disk "
                        f"({digest[:12]}…). Re-train or re-export the artifact instead "
                        f"of loading it."
                    )
            return

        if os.environ.get(_ALLOW_UNVERIFIED_ENV, "").strip().lower() in _TRUTHY:
            logger.warning(
                "Loading unverified model artifact %s (%s=1)", model_file, _ALLOW_UNVERIFIED_ENV
            )
            return

        raise ValueError(
            f"ML-007: refusing to unpickle {model_file} — metadata.json records no "
            f"artifact_hash/checksum for it, so its integrity cannot be proven. "
            f"Set {_ALLOW_UNVERIFIED_ENV}=1 to load legacy artifacts at your own risk."
        )

    def _load_from_disk(self, cache_key: str) -> Any:
        """Load a pickled model from the artifact directory.

        Two layouts are supported: the flat one (``<model>/model_pipeline.pkl``)
        and the versioned one the training pipeline produces
        (``<model>/<version>/model_pipeline.pkl`` + ``latest_path.txt``).

        Raises ``FileNotFoundError`` when no artifact exists for *cache_key*.
        """
        from ml.artifacts import MODEL_FILE_CANDIDATES, latest_version, load_artifact_file

        # ``algorithm_symbol@version`` pins an exact version folder; without the
        # suffix the newest one is used (``latest_path.txt`` aware).
        model_key, _, pinned = cache_key.partition("@")
        artifact_dir = self._base_dir / model_key
        if not artifact_dir.is_dir():
            raise FileNotFoundError(f"No artifact directory: {artifact_dir}")

        version = pinned or latest_version(artifact_dir)
        search_dirs = [artifact_dir]
        if version:
            search_dirs.append(artifact_dir / version)

        tried: list[str] = []
        for directory in search_dirs:
            for name in MODEL_FILE_CANDIDATES:
                model_file = directory / name
                tried.append(str(model_file))
                if model_file.exists():
                    self._assert_integrity(model_file)
                    obj = load_artifact_file(model_file)
                    logger.debug("Loaded model from %s", model_file)
                    return obj

        raise FileNotFoundError(
            f"No model file found in {artifact_dir} (tried: {tried})"
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
