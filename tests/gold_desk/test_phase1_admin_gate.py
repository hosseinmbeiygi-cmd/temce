"""Phase 1 — admin gate tests.

Three token endpoints (/gold/tokens POST, GET, DELETE) must gate on a
dependency that carries ``__auth_guard__ = True`` (the same marker that
``require_roles()`` sets).  Using an ad-hoc function that calls
``get_current_user`` internally still passes the route-audit gate, but
the name ``_require_admin_user`` is not in AUTH_NAMES and cannot be
audited at the source-text level — a silent gap.

Red criterion: at least one of the three token routes lacks a dependency
with ``__auth_guard__ = True`` in its direct dependency list.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.auth_policy import AUTH_DEP_ATTR  # noqa: E402


def _has_auth_guard(route) -> bool:
    """Return True if any *direct* dependency on the route carries AUTH_DEP_ATTR."""
    for dep in getattr(route, "dependencies", None) or []:
        call = getattr(dep, "dependency", None) or getattr(dep, "call", None)
        if getattr(call, AUTH_DEP_ATTR, False):
            return True
        # Also check endpoint parameters
        import inspect
        endpoint = getattr(route, "endpoint", None)
        if endpoint:
            for param in inspect.signature(endpoint).parameters.values():
                default = param.default
                if hasattr(default, "dependency"):
                    dep_call = getattr(default.dependency, "dependency", None) or default.dependency
                    if getattr(dep_call, AUTH_DEP_ATTR, False):
                        return True
    return False


def test_gold_token_endpoints_use_auth_guard():
    """POST/GET/DELETE /gold/tokens must each have a dependency with __auth_guard__."""
    from tests.gold_desk._route_utils import iter_routes
    from apps.api.router import Router

    token_routes = {
        ("POST", "/gold/tokens"),
        ("GET", "/gold/tokens"),
        ("DELETE", "/gold/tokens/{token_id}"),
    }
    found_guarded: set[tuple[str, str]] = set()

    for path, route in iter_routes(Router().setup().routes):
        methods = frozenset(getattr(route, "methods", None) or ())
        for method in methods:
            key = (method, path)
            if key in token_routes and _has_auth_guard(route):
                found_guarded.add(key)

    missing = sorted(token_routes - found_guarded)
    assert not missing, (
        f"Token endpoints lack a dependency with {AUTH_DEP_ATTR}=True: {missing}. "
        "Replace _require_admin_user with Depends(require_roles('admin'))."
    )
