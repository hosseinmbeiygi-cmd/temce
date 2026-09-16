"""Unit tests for Fund Discovery & Coverage engine (A1/A3/A6).

تست‌های Pure بدون DB اجرا می‌شوند؛ تست یکپارچگی Discovery با مارکر
``needs_db`` و در نبود PostgreSQL به‌صورت خودکار Skip می‌شود.
"""

from __future__ import annotations

import pytest

from services.fund_discovery import (
    MIN_NAV_COVERAGE_PCT,
    STALE_QUOTE_MINUTES,
    coverage_score,
    coverage_status,
    detect_capabilities,
    merge_capabilities,
)


def test_detect_capabilities_tse_etf():
    caps = detect_capabilities(
        fund_id="tse:آلتون",
        symbol="آلتون",
        market="tse",
        nav_symbols={"آلتون"},
        nav_funds=set(),
        quote_symbols={"آلتون"},
        quote_funds=set(),
        codal_symbols=set(),
        portfolio_funds=set(),
        holding_funds=set(),
    )
    assert caps == {
        "has_nav": True,
        "has_market_quotes": True,
        "has_codal_reports": False,
        "has_portfolio": False,
        "is_etf": True,
    }


def test_detect_capabilities_ime_is_not_etf():
    caps = detect_capabilities(
        fund_id="ime:گلدیس",
        symbol="گلدیس",
        market="ime",
        nav_symbols=set(),
        nav_funds={"ime:گلدیس"},
        quote_symbols={"گلدیس"},
        quote_funds=set(),
        codal_symbols=set(),
        portfolio_funds={"ime:گلدیس"},
        holding_funds=set(),
    )
    assert caps["is_etf"] is False
    assert caps["has_nav"] is True
    assert caps["has_portfolio"] is True
    assert caps["has_market_quotes"] is False


def test_merge_capabilities_is_monotonic():
    existing = {"has_nav": True, "has_portfolio": False, "is_etf": True,
                "has_market_quotes": True, "has_codal_reports": False}
    detected = {"has_nav": False, "has_portfolio": True, "is_etf": True,
                "has_market_quotes": False, "has_codal_reports": True}
    merged = merge_capabilities(existing, detected)
    assert merged == {
        "has_nav": True,
        "has_portfolio": True,
        "is_etf": True,
        "has_market_quotes": True,
        "has_codal_reports": True,
    }


def test_coverage_status_thresholds():
    assert coverage_status(MIN_NAV_COVERAGE_PCT + 10, True, STALE_QUOTE_MINUTES - 1) == "ok"
    assert coverage_status(MIN_NAV_COVERAGE_PCT + 10, True, STALE_QUOTE_MINUTES + 1) == "stale"
    assert coverage_status(MIN_NAV_COVERAGE_PCT - 10, True, None) == "partial"
    assert coverage_status(0, False, None) == "missing"


def test_coverage_score_bounds():
    lo = coverage_score(0, False, None, 0)
    hi = coverage_score(100, True, 1, 3)
    assert 0 <= lo < hi <= 100
    assert hi == 100.0


@pytest.mark.needs_db
async def test_discovery_integration_with_fake_adapter():
    """Discovery باید Idempotent باشد و Alias/Universe را درست بسازد."""
    from core.database import close_database, get_session, init_database
    from services.fund_discovery import FundDiscoveryService
    from services.fund_identity import normalize_symbol

    class FakeAdapter:
        def __init__(self, rows):
            self.rows = rows

        async def fetch_universe(self):
            return [dict(r) for r in self.rows]

    sym = normalize_symbol("تست‌واحدصندوق")
    await init_database()
    try:
        async for session in get_session():
            rows = [
                {
                    "fund_id": "ignored",
                    "symbol": sym,
                    "name": "صندوق تست واحد",
                    "isin": "IRUNITTEST01",
                    "market": "tse",
                    "sector": "صندوق سرمایه گذاری قابل معامله",
                    "fund_type_hint": "سهامی",
                }
            ]
            from sqlalchemy import text

            await session.execute(
                text("DELETE FROM fund_symbol_aliases WHERE symbol = :s"), {"s": sym}
            )
            await session.execute(text("DELETE FROM funds WHERE symbol = :s"), {"s": sym})
            await session.commit()

            svc = FundDiscoveryService(session, FakeAdapter(rows))
            await svc.discover()
            stats1 = svc.last_stats
            assert stats1 is not None
            assert stats1.created == 1

            svc2 = FundDiscoveryService(session, FakeAdapter(rows))
            await svc2.discover()
            stats2 = svc2.last_stats
            assert stats2 is not None
            assert stats2.created == 0  # Idempotency

            alias = (
                await session.execute(
                    text("SELECT fund_id FROM fund_symbol_aliases WHERE symbol = :s"),
                    {"s": sym},
                )
            ).scalar()
            assert alias

            cov = await svc2.compute_coverage(limit=500)
            assert any(c["symbol"] == sym for c in cov)
    finally:
        await close_database()
