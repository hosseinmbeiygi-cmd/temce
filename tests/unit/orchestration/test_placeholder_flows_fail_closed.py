"""Placeholder orchestration flows must not report success.

Root cause locked down (audit run3, orchestration package):

``CodalFlow``, ``FundFlow`` and ``MarketFlow`` are stubs that do no work yet
returned ``Result.ok({"status": "completed"})``. If any future wiring ever called
them, the caller would believe a data flow ran to completion. ``NewsFlow`` was
already fixed to ``Result.fail("not_implemented: …")``; these three were missed.

The same "no fake success" rule from the master prompt applies to them.
"""

from __future__ import annotations

import pytest

_PLACEHOLDERS = (
    ("orchestration.codal_flow", "CodalFlow"),
    ("orchestration.fund_flow", "FundFlow"),
    ("orchestration.market_flow", "MarketFlow"),
)


@pytest.mark.parametrize(("module_name", "class_name"), _PLACEHOLDERS)
@pytest.mark.asyncio
async def test_placeholder_flow_fails_closed(module_name: str, class_name: str) -> None:
    import importlib

    flow_cls = getattr(importlib.import_module(module_name), class_name)
    result = await flow_cls().run(context=None)

    assert result.success is False, (
        f"{class_name} reported success for a flow that does no work — "
        "callers would treat a no-op as a completed data flow"
    )
    assert "not_implemented" in (result.error or "")
