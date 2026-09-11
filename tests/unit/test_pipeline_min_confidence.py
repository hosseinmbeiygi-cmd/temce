"""Tests for the pipeline-wide confidence floor.

The pipeline is built as a FULL SUPERSET with ``_PIPELINE_MIN_CONFIDENCE``
= 0.0 (no floor at build time). This is deliberate: the multi_market_signals
endpoint caches ONE superset build (stale-while-revalidate, 90s TTL) and
applies every request's ``min_confidence`` filter server-side AFTER the cache
hit. Filtering at build time would either bake one threshold into the shared
cache (breaking other filter combinations) or force a fresh tens-of-seconds
pipeline run per requested threshold.

Override via ``SIGNAL_PIPELINE_MIN_CONFIDENCE`` is no longer read at import
time; the floor is a module constant on purpose.
"""

from __future__ import annotations

import importlib

import pytest


def _reload_module(monkeypatch: pytest.MonkeyPatch, env_value: str | None) -> object:
    """Reload the endpoint module, optionally setting the legacy env var.

    The env var is historical: the module no longer reads it, but we set/clear
    it anyway to prove the constant is independent of the environment.
    """
    if env_value is None:
        monkeypatch.delenv("SIGNAL_PIPELINE_MIN_CONFIDENCE", raising=False)
    else:
        monkeypatch.setenv("SIGNAL_PIPELINE_MIN_CONFIDENCE", env_value)
    # Drop any cached import so re-import picks up a fresh module object.
    import sys

    mod_name = "apps.api.endpoints.multi_market_signals"
    sys.modules.pop(mod_name, None)
    return importlib.import_module(mod_name)


def test_default_min_confidence_is_zero_superset(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no env override, the pipeline floor is 0.0 (full superset).

    Rationale: the single cached build must serve every requested
    min_confidence (0.0–1.0). Building with any floor > 0 would make low
    thresholds silently return fewer signals than requested.
    """
    mod = _reload_module(monkeypatch, env_value=None)
    assert mod._PIPELINE_MIN_CONFIDENCE == 0.0


def test_env_var_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """The legacy SIGNAL_PIPELINE_MIN_CONFIDENCE env var no longer applies.

    The floor is a module constant; documents that environment changes
    must NOT alter the superset build (cache-correctness invariant).
    """
    mod = _reload_module(monkeypatch, env_value="0.50")
    assert mod._PIPELINE_MIN_CONFIDENCE == 0.0


def test_env_zero_matches_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """0.0 in the environment matches the built-in superset default."""
    mod = _reload_module(monkeypatch, env_value="0.0")
    assert mod._PIPELINE_MIN_CONFIDENCE == 0.0


def test_invalid_env_does_not_affect_module_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-numeric env value must NOT crash the import path.

    The constant is not coerced from the environment anymore, so garbage
    in the (legacy, unread) variable is simply ignored.
    """
    mod = _reload_module(monkeypatch, env_value="not-a-number")
    assert mod._PIPELINE_MIN_CONFIDENCE == 0.0


def test_pipeline_build_uses_superset_floor() -> None:
    """The orchestrator build calls must pass the 0.0 floor, not a hardcoded value.

    Guards against someone re-introducing a build-time threshold that would
    break the derive-any-threshold-from-one-cache contract.
    """
    import inspect
    import sys

    mod = sys.modules.get("apps.api.endpoints.multi_market_signals")
    if mod is None:
        mod = importlib.import_module("apps.api.endpoints.multi_market_signals")
    src = inspect.getsource(mod)
    assert "min_confidence=_PIPELINE_MIN_CONFIDENCE" in src
    # The constant itself must stay 0.0 (full superset).
    assert mod._PIPELINE_MIN_CONFIDENCE == 0.0


def test_request_level_min_confidence_default_is_040() -> None:
    """The REQUEST-level default filter stays 0.40 (docs/accuracy-investigation-2026-08.md).

    The superset build is unfiltered, but the API query default applied
    server-side after the cache hit remains the accuracy sweet spot 0.40
    (47% acc, 32% coverage).
    """
    import inspect
    import sys

    mod = sys.modules.get("apps.api.endpoints.multi_market_signals")
    if mod is None:
        mod = importlib.import_module("apps.api.endpoints.multi_market_signals")
    src = inspect.getsource(mod)
    assert 'min_confidence: float = Query(0.40' in src
