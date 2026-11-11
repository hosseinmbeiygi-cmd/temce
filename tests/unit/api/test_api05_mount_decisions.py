"""API-05 decision record: the seven unmounted routers stay unmounted.

The router surface inventory test (``tests/unit/test_api_router_surface_inventory.py``)
already fails when a *new* router appears unmounted. This file records the
opposite half of the decision for the seven modules the audit found: each was
classified as either dead code or a route surface without a consumer, so none
is mounted today.

Mounted is not free: every one of these paths would become reachable with the
platform's default dependencies. ``monitoring`` exposes internal counters and
DB diagnostics, ``scanner`` starts expensive scans, ``symbol_alerts`` /
``proposals`` / ``sentiment`` have no ownership or role model of their own.
Mounting any of them is a product decision that must also update the record in
``apps/api/router.py`` — this test forces that conversation instead of letting
the surface drift back.

Revisit condition (per module):
  * monitoring          — a Prometheus scrape target exists AND requests are
                          authenticated/role-scoped.
  * scanner             — a UI or job consumer needs the HTTP surface, with an
                          admin role on the POST routes.
  * ime                 — a consumer for the routes not covered by ``/gold/ime``.
  * comprehensive_analysis — a consumer that ``/analysis/overview`` cannot serve.
  * symbol_alerts       — only if the owner decides to revive it with ownership.
  * proposals, sentiment — only if the owner decides to revive the subsystem.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENDPOINTS_DIR = PROJECT_ROOT / "apps" / "api" / "endpoints"
ROUTER_FILE = PROJECT_ROOT / "apps" / "api" / "router.py"

# module name -> why it stays unmounted (kept next to the assertion so a future
# mount has to argue with the recorded reason).
DECISIONS: dict[str, str] = {
    "monitoring": "no scrape target; /metrics + /data-quality would be unauthenticated",
    "scanner": "POST /scan is costly and has no consumer; service used via backtests",
    "ime": "read-only duplicate of the mounted /gold/ime futures surface",
    "comprehensive_analysis": "overlaps the mounted /analysis/overview",
    "symbol_alerts": "subsystem reachable only via this router; /alerts is the live equivalent",
    "proposals": "subsystem reachable only via this router (dead code)",
    "sentiment": "subsystem reachable only via this router (dead code)",
}


def _mounted_aliases() -> set[str]:
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


@pytest.mark.parametrize(("module", "reason"), sorted(DECISIONS.items()))
def test_router_module_still_exists(module: str, reason: str) -> None:
    path = ENDPOINTS_DIR / f"{module}.py"
    assert path.exists(), (
        f"{module}: the module is gone — if it was removed, drop it from the "
        f"decision record (reason was: {reason})"
    )


def test_no_decided_router_is_mounted() -> None:
    mounted = _mounted_aliases() & set(DECISIONS)
    assert mounted == set(), (
        "API-05: these routers were mounted without updating the decision "
        f"record (apps/api/router.py + this file): {sorted(mounted)}. "
        "Mounting them requires a consumer and auth/role scoping; update the "
        "record with the evidence if the decision changed."
    )


def test_decision_record_is_referenced_in_router_source() -> None:
    """The person mounting one of them must find the record from the code."""
    source = ROUTER_FILE.read_text(encoding="utf-8")
    assert "API-05 decision" in source
    assert "tests/unit/api/test_api05_mount_decisions.py" in source
