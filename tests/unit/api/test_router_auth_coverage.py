"""Every operation must be authenticated or explicitly allowlisted.

The allowlist comes from scripts/auth_policy.py (one source of truth with the
CI gate); route expansion is implemented independently here on purpose, so a
bug in the gate cannot hide a route from the test.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import settings  # noqa: E402
from scripts.auth_policy import (  # noqa: E402
    APP_LEVEL_PUBLIC_PATHS,
    AUTH_DEP_ATTR,
    AUTH_NAMES,
    MIN_OPERATIONS,
    PUBLIC_EXACT_PATHS,
    PUBLIC_PREFIXES,
    PUBLIC_READ_PREFIXES,
    WRITE_ONLY_AUTH_NAMES,
    WS_PUBLIC_ALLOWLIST,
)


def _iter_operations(routes, prefix="", inherited=frozenset()):
    for route in routes:
        context = getattr(route, "include_context", None)
        original = getattr(route, "original_router", None)
        if context is not None and original is not None:
            inherited_here = inherited
            for dep in getattr(context, "dependencies", None) or []:
                call = getattr(dep, "dependency", None) or getattr(dep, "call", None)
                if getattr(call, AUTH_DEP_ATTR, False):
                    inherited_here |= {AUTH_DEP_ATTR}
                name = getattr(call, "__name__", "") or ""
                if name:
                    inherited_here |= {name}
            yield from _iter_operations(
                original.routes,
                prefix + (getattr(context, "prefix", "") or ""),
                inherited_here,
            )
            continue
        path = getattr(route, "path", None)
        if path is not None:
            yield prefix + path, route, inherited


def _dependency_sets(dep, depth=0):
    names: set[str] = set()
    if dep is None or depth > 20:
        return names
    for sub in getattr(dep, "dependencies", None) or []:
        call = getattr(sub, "dependency", None) or getattr(sub, "call", None)
        if getattr(call, AUTH_DEP_ATTR, False):
            names.add(AUTH_DEP_ATTR)
        names.add(getattr(call, "__name__", "") or "")
        names |= _dependency_sets(sub, depth + 1)
    return names


def _operations(app):
    prefix = settings.api_prefix
    return [
        (path.removeprefix(prefix) or "/", route, inherited)
        for path, route, inherited in _iter_operations(app.routes)
    ]


def test_audit_sees_the_whole_surface(app) -> None:
    operations = _operations(app)
    assert len(operations) >= MIN_OPERATIONS, (
        f"only {len(operations)} operations found — FastAPI include_router() "
        "expansion is broken and the auth audit would be blind"
    )


def test_every_http_operation_is_guarded_or_allowlisted(app) -> None:
    violations: list[str] = []
    for path, route, inherited in _operations(app):
        methods = sorted(getattr(route, "methods", None) or [])
        if not methods:
            continue
        names = set(inherited) | _dependency_sets(getattr(route, "dependant", None))
        for method in methods:
            if path in APP_LEVEL_PUBLIC_PATHS or path in PUBLIC_EXACT_PATHS:
                continue
            if any(
                path == prefix or path.startswith(prefix + "/")
                for prefix in PUBLIC_PREFIXES
                if prefix
            ):
                continue
            if names & AUTH_NAMES or AUTH_DEP_ATTR in names:
                continue
            if any(
                path == prefix or path.startswith(prefix + "/")
                for prefix in PUBLIC_READ_PREFIXES
            ) and (names & WRITE_ONLY_AUTH_NAMES):
                continue
            violations.append(f"{method} {path}")
    assert not violations, "unauthenticated operations: " + ", ".join(sorted(violations))


def test_every_websocket_is_guarded_or_allowlisted(app) -> None:
    violations: list[str] = []
    for path, route, _inherited in _operations(app):
        if getattr(route, "methods", None):
            continue
        if path in WS_PUBLIC_ALLOWLIST:
            continue
        try:
            source = inspect.getsource(route.endpoint)
        except (OSError, TypeError):
            source = ""
        if "verify_websocket_token" not in source:
            violations.append(path)
    assert not violations, f"WebSockets without a handshake check: {violations}"


def test_gold_surface_is_actually_mounted(app) -> None:
    """A silent ImportError in Router.setup() must not hide 60+ operations."""
    paths = {path for path, _route, _inherited in _operations(app)}
    assert "/gold/health" in paths
    assert any(path.startswith("/gold/portfolio") for path in paths)


def test_precompute_websocket_refuses_a_tokenless_handshake(app) -> None:
    """P1-03: /ws/precompute used to accept any client that skipped the Origin check."""
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as denied,
        client.websocket_connect("/api/v1/ws/precompute"),
    ):
        pass

    assert denied.value.code == 1008
