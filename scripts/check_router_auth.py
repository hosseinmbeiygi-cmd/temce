#!/usr/bin/env python
"""Audit script: ensure every include_router in apps/api/router.py has an
explicit ``dependencies=`` argument, except for the documented exemptions
(/health, /auth, /ws, /api/v1/system).

Run as a CI gate to catch accidentally-unprotected endpoints.
Exit code 0 = clean, 1 = at least one unprotected include_router.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROUTER_FILE = Path(__file__).resolve().parent.parent / "apps" / "api" / "router.py"

# include_router calls without dependencies= are allowed only for these
# prefix values. Anything else is treated as a hardening regression.
ALLOWED_UNGUARDED_PREFIXES = {
    "/health",
    "/auth",
    "/ws",
    "",  # system_router self-prefixes to /api/v1/system
}


def _kw(call: ast.Call, name: str) -> ast.keyword | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def main() -> int:
    if not ROUTER_FILE.exists():
        print(f"router.py not found at {ROUTER_FILE}", file=sys.stderr)
        return 2

    tree = ast.parse(ROUTER_FILE.read_text(encoding="utf-8"))
    findings: list[tuple[str, str]] = []  # (line, message)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "include_router"):
            continue

        prefix_node = _kw(node, "prefix")
        prefix = _literal_str(prefix_node.value) if prefix_node else None
        deps_node = _kw(node, "dependencies")

        if deps_node is not None:
            continue  # explicitly guarded

        # No dependencies=. Check whether prefix is in the allow-list.
        if prefix in ALLOWED_UNGUARDED_PREFIXES:
            continue

        line = node.lineno
        prefix_repr = repr(prefix) if prefix is not None else "<unknown>"
        findings.append((str(line), f"include_router prefix={prefix_repr} has no dependencies= kwarg"))

    if findings:
        print("Router auth audit FAILED:", file=sys.stderr)
        for line, msg in findings:
            print(f"  router.py:{line}: {msg}", file=sys.stderr)
        print(
            "\nFix: add dependencies=_optional_auth (or _require_user/_require_admin)\n"
            "to every unprotected include_router call. /health, /auth, /ws, and the\n"
            "self-prefixed /api/v1/system router are the only documented exemptions.",
            file=sys.stderr,
        )
        return 1

    print("Router auth audit OK — every include_router is explicitly guarded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
