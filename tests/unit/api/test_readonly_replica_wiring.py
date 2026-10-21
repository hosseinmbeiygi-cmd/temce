"""Regression tests for audit CFG-05 — read endpoints are replica-wired.

The read replica was configured but never injected anywhere, so the feature was
dead code. These tests pin the routing rule to the FastAPI dependency graph:

* every handler in the read-only modules (``analysis``, plus the GET side of
  ``screener`` / ``indicators``) resolves ``get_replica_session``;
* every write handler in those same modules still resolves ``get_db_session``,
  so a mutating request can never land on the replica.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

_READONLY_MODULES = (
    "apps.api.endpoints.analysis",
    "apps.api.endpoints.screener",
    "apps.api.endpoints.indicators",
)


def _dependency_names(dependant: Any) -> set[str]:
    """Flatten a FastAPI ``Dependant`` tree into the set of dependency names."""
    names: set[str] = set()
    stack = [dependant]
    while stack:
        current = stack.pop()
        if current.call is not None:
            names.add(getattr(current.call, "__name__", ""))
        stack.extend(current.dependencies)
    return names


def _routes(app: FastAPI):
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        if getattr(endpoint, "__module__", "") in _READONLY_MODULES:
            yield route, endpoint


def test_read_handlers_use_the_replica(app: FastAPI) -> None:
    checked = 0
    for route, _endpoint in _routes(app):
        if "GET" not in route.methods:
            continue
        names = _dependency_names(route.dependant)
        assert "get_replica_session" in names, f"{route.path} GET must read from the replica"
        assert "get_db_session" not in names, f"{route.path} GET must not fall back to the primary implicitly"
        checked += 1
    assert checked >= 7, f"expected the read-only routers to expose >=7 GET handlers, saw {checked}"


def test_write_handlers_stay_on_the_primary(app: FastAPI) -> None:
    checked = 0
    for route, _endpoint in _routes(app):
        if "GET" in route.methods:
            continue
        names = _dependency_names(route.dependant)
        assert "get_replica_session" not in names, f"{route.path} writes and must not use the replica"
        checked += 1
    assert checked >= 2, f"expected >=2 write handlers in the audited modules, saw {checked}"


def test_replica_and_primary_are_distinct_dependencies() -> None:
    """Guards against an accidental alias collapsing the two routes together."""
    from apps.api.dependencies import get_db_session, get_replica_session

    assert get_db_session is not get_replica_session
