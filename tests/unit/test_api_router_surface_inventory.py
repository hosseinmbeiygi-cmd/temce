"""API-05 guard: no endpoint router may be silently left unmounted.

`apps/api/router.py` mounts its routers via lazy ``from apps.api.endpoints.X
import router as y`` + ``router.include_router(y, ...)``. An endpoint module
that defines a ``router`` but is never imported/mounted is dead code: its
routes are unreachable through the public API even though they exist in the
tree.

The audit (API-05) found exactly seven such modules. This test does not try to
fix them (mount-vs-remove is a product decision); it only fails when a *new*
module accumulates a router without being mounted, so the dead surface cannot
grow unnoticed. The known set may shrink freely (mounting one is always fine).
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENDPOINTS_DIR = PROJECT_ROOT / "apps" / "api" / "endpoints"
ROUTER_FILE = PROJECT_ROOT / "apps" / "api" / "router.py"

# Modules known (audit API-05) to define a router but never be mounted.
# New entries must not appear without a deliberate decision.
KNOWN_UNMOUNTED = {
    "comprehensive_analysis",
    "ime",
    "monitoring",
    "proposals",
    "scanner",
    "sentiment",
    "symbol_alerts",
}


def _modules_defining_a_router() -> set[str]:
    found: set[str] = set()
    for path in ENDPOINTS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        # utf-8-sig: one module carries a UTF-8 BOM; import tolerates it, but
        # ast.parse on the raw text does not.
        tree = ast.parse(path.read_bytes().decode("utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "router" for t in node.targets
            ):
                found.add(path.stem)
                break
    return found


def _mounted_modules() -> set[str]:
    tree = ast.parse(ROUTER_FILE.read_bytes().decode("utf-8-sig"))
    alias_to_module: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("apps.api.endpoints")
        ):
            module = node.module.rsplit(".", 1)[-1]
            for alias in node.names:
                if alias.name == "router":
                    alias_to_module[alias.asname or "router"] = module

    mounted: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in alias_to_module:
                    mounted.add(alias_to_module[arg.id])
    return mounted


def test_no_endpoint_module_has_utf8_bom() -> None:
    """A BOM breaks tools that read source as plain UTF-8 text."""
    offenders = [
        p.name
        for p in ENDPOINTS_DIR.glob("*.py")
        if p.read_bytes().startswith(b"\xef\xbb\xbf")
    ]
    assert offenders == []


def test_new_unmounted_router_is_not_introduced() -> None:
    unmounted = _modules_defining_a_router() - _mounted_modules()
    assert unmounted <= KNOWN_UNMOUNTED, (
        "New unmounted endpoint router(s) detected (API-05): "
        f"{sorted(unmounted - KNOWN_UNMOUNTED)}"
    )
