#!/usr/bin/env python
"""CI gate: every HTTP operation on the API must be authenticated or exempt.

Unlike a source-text scan, this resolves the real FastAPI dependency graph so a
route that only *looks* guarded at mount time is still caught, and so per-route
dependencies are counted. It also covers routes declared directly on the app in
apps/api/app.py, which never pass through apps/api/router.py.

Policy:
  - Fully public:      /health, /auth, the API root, and the OpenAPI/metrics docs.
  - WebSocket:         /ws/* is exempt by protocol (no bearer handshake wired up).
  - Public *read*:     reference market data; GET/HEAD anonymous, writes enforced.
  - Everything else:   must resolve to a real auth dependency.

Exit 0 = clean, 1 = violation, 2 = the audit itself could not run.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP_FILE = ROOT / "apps" / "api" / "app.py"

PUBLIC_PREFIXES = {"", "/health", "/auth"}
WS_PREFIXES = {"/ws"}

# Swagger/ReDoc are public documentation by policy.
PUBLIC_EXACT_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}

# Mounts that let anonymous visitors read reference market data.
PUBLIC_READ_PREFIXES = {
    "/market",
    "/market-dashboard",
    "/market-watch",
    "/market-info",
    "/instruments",
    "/symbols",
    "/quotes",
    "/orderbooks",
    "/trades",
    "/indicators",
    "/macro",
    "/news",
    "/codal",
    "/codal-accounting",
    "/codal-audit",
    "/codal-professional",
    "/options",
    "/funds",
}

# Dependencies that actually reject an anonymous request.
AUTH_NAMES = {
    "get_current_user",
    "get_current_active_user",
    "require_role",
    "require_roles",
    "require_any_role",
    "_check",
}
# Enforces auth on mutating methods only; legal only under PUBLIC_READ_PREFIXES.
WRITE_ONLY_AUTH_NAMES = {"require_user_for_writes"}

APP_LEVEL_PUBLIC = {("/health", "get"), ("/metrics", "get"), ("/", "get")}


def _dep_name(dep: Any) -> str:
    call = getattr(dep, "dependency", None) or getattr(dep, "call", None)
    return getattr(call, "__name__", "") or ""


def _collect(dep: Any, names: set[str], depth: int = 0) -> None:
    """Walk a route's whole sub-dependency graph, including endpoint parameters."""
    if depth > 20:
        return
    for sub in getattr(dep, "dependencies", None) or []:
        names.add(_dep_name(sub))
        _collect(sub, names, depth + 1)


def _top_prefix(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if not parts:
        return ""
    if parts[0] == "funds" and len(parts) > 1 and parts[1] == "v2":
        return "/funds/v2"
    return "/" + parts[0]


def audit_router() -> tuple[list[str], int]:
    from fastapi import FastAPI

    from apps.api.router import Router
    from core.config import settings

    app = FastAPI()
    router = Router().setup()
    app.include_router(router, prefix=settings.api_prefix)

    errors: list[str] = []
    checked = 0
    for route in app.routes:
        methods = sorted(getattr(route, "methods", None) or [])
        is_ws = not methods
        rel_path = route.path.removeprefix(settings.api_prefix)
        prefix = _top_prefix(rel_path)
        names: set[str] = set()
        _collect(getattr(route, "dependant", None), names)
        enforced = bool(names & AUTH_NAMES)
        write_only = bool(names & WRITE_ONLY_AUTH_NAMES)

        for method in methods or ["WS"]:
            checked += 1
            where = f"{method} {rel_path}"
            if prefix in PUBLIC_PREFIXES or rel_path in PUBLIC_EXACT_PATHS:
                continue
            if is_ws or prefix in WS_PREFIXES:
                if not is_ws:
                    errors.append(f"{where}: non-WebSocket route mounted under /ws")
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
    tree = ast.parse(APP_FILE.read_text(encoding="utf-8"))
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
            path = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else "?"
            body = ast.get_source_segment(APP_FILE.read_text(encoding="utf-8"), node) or ""
            # also inspect the decorator's own dependencies= kwarg
            kw = next((k for k in dec.keywords if k.arg == "dependencies"), None)
            if kw is not None:
                body += ast.get_source_segment(APP_FILE.read_text(encoding="utf-8"), kw.value) or ""
            if (method, path) in APP_LEVEL_PUBLIC:
                continue
            if not any(name in body for name in AUTH_NAMES | WRITE_ONLY_AUTH_NAMES):
                errors.append(f"app.py:{node.lineno}: {method.upper()} {path} has no auth dependency")
    return errors, checked


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
    if all_errors:
        print("Router auth audit FAILED:", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    print("Router auth audit OK — every operation is authenticated or on the documented allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
