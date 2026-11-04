"""Flatten FastAPI route tables into concrete operations.

FastAPI 0.128+ wraps every ``include_router()`` in a private ``_IncludedRouter``
whose child routes are not present in ``app.routes``. Route-introspection tests
must walk the wrappers and accumulate their include prefixes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def iter_routes(routes: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Yield ``(full_path, route)`` for every real route, descending wrappers."""

    for route in routes:
        context = getattr(route, "include_context", None)
        original = getattr(route, "original_router", None)
        if context is not None and original is not None:
            yield from iter_routes(
                original.routes,
                prefix + (getattr(context, "prefix", "") or ""),
            )
            continue
        path = getattr(route, "path", None)
        if path is not None:
            yield prefix + path, route
