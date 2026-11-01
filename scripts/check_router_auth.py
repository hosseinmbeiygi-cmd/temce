#!/usr/bin/env python
"""CI gate: every HTTP operation on the API must be authenticated or exempt.

Unlike a source-text scan, this resolves the real FastAPI dependency graph so a
route that only *looks* guarded at mount time is still caught, and so per-route
dependencies are counted. It also covers routes declared directly on the app in
apps/api/app.py, which never pass through apps/api/router.py.

Policy (single source: scripts/auth_policy.py):
  - Fully public:      /health, /auth, the API root, and the OpenAPI/metrics docs.
  - WebSocket:         authenticated in the handler by verify_websocket_token().
  - Public *read*:     reference market data; GET/HEAD anonymous, writes enforced.
  - Everything else:   must resolve to a real auth dependency.

Exit 0 = clean, 1 = violation, 2 = the audit itself could not run.
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.auth_policy import (  # noqa: E402 — sys.path is set above
    APP_LEVEL_PUBLIC_PATHS,
    AUTH_DEP_ATTR,
    AUTH_NAMES,
    AUTH_SOURCE_TOKENS,
    MIN_OPERATIONS,
    PUBLIC_EXACT_PATHS,
    PUBLIC_PREFIXES,
    PUBLIC_READ_PREFIXES,
    WRITE_ONLY_AUTH_NAMES,
    WS_PUBLIC_ALLOWLIST,
)

# A Windows console defaults to cp1252 and crashes on the Persian route
# summaries; the gate must behave the same on every OS.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP_FILE = ROOT / "apps" / "api" / "app.py"


def _dep_name(dep: Any) -> str:
    call = getattr(dep, "dependency", None) or getattr(dep, "call", None)
    return getattr(call, "__name__", "") or ""


def _collect(dep: Any, names: set[str], depth: int = 0) -> None:
    """Walk a route's whole sub-dependency graph, including endpoint parameters."""
    if depth > 20:
        return
    for sub in getattr(dep, "dependencies", None) or []:
        call = getattr(sub, "dependency", None) or getattr(sub, "call", None)
        if getattr(call, AUTH_DEP_ATTR, False):
            names.add(AUTH_DEP_ATTR)
        names.add(_dep_name(sub))
        _collect(sub, names, depth + 1)


def _top_prefix(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if not parts:
        return ""
    if parts[0] == "funds" and len(parts) > 1 and parts[1] == "v2":
        return "/funds/v2"
    if parts[0] == "api" and len(parts) > 1 and parts[1] == "options":
        # The options-frontend router is mounted at ``/api/options`` and its
        # routes are declared relative to that mount.
        return "/api/options"
    return "/" + parts[0]


def _iter_operations(routes: Any, prefix: str = "", inherited: frozenset[str] = frozenset()) -> Any:
    """Yield (path, route, inherited_auth) for every real operation.

    FastAPI 0.128 collapses include_router() into an ``_IncludedRouter`` whose
    sub-routes are NOT present in ``app.routes``. Mount-level ``dependencies=``
    live on the wrapper's ``include_context``, not on the inner route's
    dependant, so they must be carried down the recursion — dropping them made
    every ``_require_user`` mount look unauthenticated.
    """
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


def audit_router() -> tuple[list[str], int]:
    from fastapi import FastAPI

    from apps.api.router import Router
    from core.config import settings

    app = FastAPI()
    router = Router().setup()
    app.include_router(router, prefix=settings.api_prefix)

    errors: list[str] = []
    checked = 0
    for rel_path, route, inherited in _iter_operations(app.routes):
        methods = sorted(getattr(route, "methods", None) or [])
        is_ws = not methods
        rel_path = rel_path.removeprefix(settings.api_prefix) or "/"
        prefix = _top_prefix(rel_path)
        names: set[str] = set(inherited)
        _collect(getattr(route, "dependant", None), names)
        enforced = bool(names & AUTH_NAMES) or AUTH_DEP_ATTR in names
        write_only = bool(names & WRITE_ONLY_AUTH_NAMES)

        if is_ws:
            checked += 1
            if rel_path in WS_PUBLIC_ALLOWLIST:
                continue
            try:
                handler_src = inspect.getsource(route.endpoint)
            except (OSError, TypeError):
                handler_src = ""
            if "verify_websocket_token" not in handler_src:
                errors.append(f"WS {rel_path}: handler does not verify a ws ticket")
            continue

        for method in methods:
            checked += 1
            where = f"{method} {rel_path}"
            if prefix in PUBLIC_PREFIXES or rel_path in PUBLIC_EXACT_PATHS:
                continue
            if enforced:
                continue
            if prefix in PUBLIC_READ_PREFIXES:
                if write_only:
                    continue
                errors.append(
                    f"{where}: public-read prefix {prefix} but no "
                    f"require_user_for_writes guard (anonymous writes allowed)"
                )
                continue
            errors.append(f"{where}: no authentication dependency resolved")
    return errors, checked


def audit_app_file() -> tuple[list[str], int]:
    """Cover @app.<method>() routes declared straight on the FastAPI instance."""
    from core.config import settings

    src = APP_FILE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    errors: list[str] = []
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "app":
                continue
            method = dec.func.attr
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            checked += 1
            path = _app_route_path(dec, settings.metrics_path)
            seg = ast.get_source_segment(src, node) or ""
            kw = next((k for k in dec.keywords if k.arg == "dependencies"), None)
            if kw is not None:
                seg += ast.get_source_segment(src, kw.value) or ""
            if path in APP_LEVEL_PUBLIC_PATHS:
                continue
            if not any(name in seg for name in AUTH_SOURCE_TOKENS | WRITE_ONLY_AUTH_NAMES):
                errors.append(f"app.py:{node.lineno}: {method.upper()} {path} has no auth dependency")
    return errors, checked


def _app_route_path(dec: ast.Call, metrics_path: str) -> str:
    """Resolve the decorator's path literal, including settings.metrics_path."""
    if not dec.args:
        return "?"
    arg = dec.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.Attribute) and arg.attr == "metrics_path":
        return metrics_path
    return "?"


def main() -> int:
    all_errors: list[str] = []
    try:
        router_errors, router_count = audit_router()
        app_errors, app_count = audit_app_file()
    except Exception as exc:  # a broken audit must not read as a pass
        print(f"Router auth audit could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    all_errors += router_errors + app_errors
    print(f"Audited {router_count} router operations and {app_count} app-level routes.")
    if router_count < MIN_OPERATIONS:
        print(
            f"Router auth audit saw only {router_count} operations "
            f"(< {MIN_OPERATIONS}) — router expansion is broken",
            file=sys.stderr,
        )
        return 2
    if all_errors:
        print("Router auth audit FAILED:", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    print("Router auth audit OK — every operation is authenticated or on the documented allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
