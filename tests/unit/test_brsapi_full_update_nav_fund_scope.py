"""NAV in ``scripts/brsapi_full_update.py`` must be fund-scoped.

``/Tsetmc/Nav.php`` is a fund/ETF-only endpoint: requesting it for the whole
symbol universe (stocks, rights issues, …) only produces HTTP 502 churn. These
tests pin the fund-only selection and the duplicate-name fold measured against
the live DB on 1405-06-23.

No network or real database — the session is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.brsapi_full_update import BrsApiFullUpdater, get_fund_symbols


def _make_session(rows: list[tuple[str]]) -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows
    session.execute = AsyncMock(return_value=result)
    return session


def _updater() -> BrsApiFullUpdater:
    return BrsApiFullUpdater(client=MagicMock(), dry_run=True)


# ── get_fund_symbols ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fund_symbols_folds_numeric_suffix_twins():
    """TSETMC duplicate-name twins (``ابتکار2``) fold onto the base symbol."""
    session = _make_session(
        [("آتش",), ("ابتکار",), ("ابتکار2",), ("ابتکار",), ("گنج",)]
    )

    symbols = await get_fund_symbols(session)

    assert symbols == ["آتش", "ابتکار", "گنج"]


@pytest.mark.asyncio
async def test_get_fund_symbols_keeps_symbol_without_plain_twin():
    """A suffixed symbol with no base row in the batch is kept as-is."""
    session = _make_session([("آتی1",), ("گنج",)])

    symbols = await get_fund_symbols(session)

    assert symbols == ["آتی1", "گنج"]


# ── run(): NAV never touches the full symbol universe ───────────────────────


@pytest.mark.asyncio
async def test_run_nav_uses_fund_symbols_only():
    """``run(tables={"nav"})`` requests NAV for funds, never for all symbols."""
    updater = _updater()
    universe = ["فولاد", "خودرو", "شپنا"]
    funds = ["آتش", "ابتکار"]
    captured: dict[str, list[str]] = {}

    async def _fake_sync_for_symbols(self, session, symbols, endpoint, *args, **kwargs):
        if endpoint is not None and getattr(endpoint, "path", "") == "/Tsetmc/Nav.php":
            captured["nav"] = list(symbols)
        return []

    with (
        patch(
            "scripts.brsapi_full_update.get_all_symbols",
            new=AsyncMock(return_value=universe),
        ),
        patch(
            "scripts.brsapi_full_update.get_fund_symbols",
            new=AsyncMock(return_value=funds),
        ),
        patch.object(
            BrsApiFullUpdater, "_sync_for_symbols", new=_fake_sync_for_symbols
        ),
    ):
        await updater.run(MagicMock(), tables={"nav"})

    assert captured["nav"] == funds
    for stock in universe:
        assert stock not in captured["nav"]
