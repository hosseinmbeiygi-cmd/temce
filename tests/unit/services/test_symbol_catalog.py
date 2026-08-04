"""Unit tests for the DB-free static symbol catalog + search endpoint.

``services.symbol_catalog`` is intentionally dependency-free (no PostgreSQL)
so the frontend can search symbols even when the database is unreachable.
"""

from __future__ import annotations

import httpx

from services import symbol_catalog

# ── Catalog helpers ────────────────────────────────────────────

def test_catalog_is_nonempty() -> None:
    catalog = symbol_catalog.all_symbols()
    assert isinstance(catalog, list)
    assert len(catalog) > 0, "curated symbol lists must produce a non-empty catalog"
    # Every entry has at least a symbol.
    for entry in catalog:
        assert entry["symbol"].strip(), "catalog entries must have a non-empty symbol"


def test_catalog_contains_default_watchlist_symbols() -> None:
    catalog_symbols = {entry["symbol"] for entry in symbol_catalog.all_symbols()}
    for expected in ("فولاد", "فملی", "خودرو", "شپنا"):
        assert expected in catalog_symbols, f"expected {expected!r} in static catalog"


def test_catalog_contains_gold_coin_symbols() -> None:
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    for expected in ("IR_GOLD_18K", "IR_GOLD_24K", "IR_COIN_EMAMI", "IR_COIN_BAHAR"):
        assert expected in catalog_symbols, f"expected gold/coin {expected!r} in static catalog"
    gold = [e for e in catalog if e["symbol"] == "IR_GOLD_18K"]
    assert gold and gold[0]["sector"] == "طلا و سکه"


def test_catalog_contains_currency_symbols() -> None:
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    for expected in ("USD", "EUR", "AED"):
        assert expected in catalog_symbols, f"expected currency {expected!r} in static catalog"
    usd = [e for e in catalog if e["symbol"] == "USD"]
    assert usd and usd[0]["sector"] == "ارز"


def test_catalog_contains_crypto_symbols() -> None:
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    for expected in ("BTC", "ETH", "USDT", "SOL"):
        assert expected in catalog_symbols, f"expected crypto {expected!r} in static catalog"
    btc = [e for e in catalog if e["symbol"] == "BTC"]
    assert btc and btc[0]["sector"] == "رمزارز"


def test_catalog_contains_commodity_symbols() -> None:
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    for expected in ("XAUUSD", "BRENT", "WTI", "COPPER"):
        assert expected in catalog_symbols, f"expected commodity {expected!r} in static catalog"
    xau = [e for e in catalog if e["symbol"] == "XAUUSD"]
    assert xau and xau[0]["sector"] == "کامودیتی"


def test_search_finds_english_symbols() -> None:
    results = symbol_catalog.search("usd")
    assert any(r["symbol"].lower() == "usd" for r in results)
    btc = symbol_catalog.search("btc")
    assert any(r["symbol"].lower() == "btc" for r in btc)


def test_catalog_contains_ime_symbols() -> None:
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    for expected in ("IME_FUTURE_ZAFARAN", "IME_CERT_ZAFARAN", "IME_FUND_GOLD", "IME_OPTION_PISTACHIO"):
        assert expected in catalog_symbols, f"expected IME symbol {expected!r} in static catalog"
    ime_entry = [e for e in catalog if e["symbol"] == "IME_FUTURE_ZAFARAN"]
    assert ime_entry and ime_entry[0]["sector"] == "بورس کالا", "IME symbol sector should be 'بورس کالا'"


def test_catalog_contains_ime_futures_and_certs() -> None:
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    for expected in ("IME_FUTURE_CEMENT", "IME_CERT_STEEL", "IME_FUND_OIL", "IME_OPTION_GOLD_BULLION"):
        assert expected in catalog_symbols, f"expected IME symbol {expected!r} in static catalog"


def test_search_finds_ime_persian() -> None:
    results = symbol_catalog.search("زعفران")
    assert len(results) >= 1
    assert any("زعفران" in r["name"] for r in results)
    # Also search by English prefix
    ime_results = symbol_catalog.search("IME_FUTURE")
    assert len(ime_results) >= 3


def test_catalog_contains_tabdeal_symbols() -> None:
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    for expected in ("BTCIRT", "ETHIRT", "USDTIRT", "BTCUSDT"):
        assert expected in catalog_symbols, f"expected Tabdeal symbol {expected!r} in static catalog"
    tabdeal_entry = [e for e in catalog if e["symbol"] == "BTCIRT"]
    assert tabdeal_entry and tabdeal_entry[0]["sector"] == "رمزارز", "Tabdeal symbol sector should be 'رمزارز'"


def test_search_finds_tabdeal_irt_pairs() -> None:
    results = symbol_catalog.search("IRT", limit=200)
    # IRT suffix should match all IRT pairs with limit=200 (all 35)
    assert len(results) >= 30, f"expected at least 30 IRT pairs, got {len(results)}"
    assert any("BTCIRT" in r["symbol"] for r in results)
    assert any("USDTIRT" in r["symbol"] for r in results)


def test_search_finds_tabdeal_persian_names() -> None:
    results = symbol_catalog.search("تومان")
    assert len(results) >= 5, f"expected at least 5 results for 'تومان', got {len(results)}"


def test_ime_symbols_do_not_collide_with_stock_symbols() -> None:
    """Ensure IME-prefixed symbols are distinct from stock symbols like فولاد."""
    catalog = symbol_catalog.all_symbols()
    catalog_symbols = {entry["symbol"] for entry in catalog}
    # "فولاد" should still be a stock (no sector or empty sector), not "بورس کالا"
    folad = [e for e in catalog if e["symbol"] == "فولاد"]
    assert len(folad) == 1, "فولاد should exist exactly once in the catalog"
    assert folad[0]["sector"] != "بورس کالا", "stock symbol 'فولاد' should NOT inherit IME sector"
    # IME version has a distinct symbol code
    assert "IME_FUTURE_STEEL" in catalog_symbols
    assert "IME_CERT_STEEL" in catalog_symbols


def test_catalog_is_deduplicated() -> None:
    symbols = [entry["symbol"] for entry in symbol_catalog.all_symbols()]
    assert len(symbols) == len(set(symbols)), "catalog must not contain duplicate symbols"


def test_catalog_sorted_by_symbol() -> None:
    symbols = [entry["symbol"] for entry in symbol_catalog.all_symbols()]
    assert symbols == sorted(symbols)


# ── search() ───────────────────────────────────────────────────

def test_search_finds_symbol_substring() -> None:
    results = symbol_catalog.search("فولاد")
    assert len(results) >= 1
    assert any("فولاد" in r["symbol"] or "فولاد" in r["name"] for r in results)


# ── Finglish transliteration ───────────────────────────────────

def test_search_finds_finglish_transliteration() -> None:
    """Searching the Latin spelling of a Persian symbol must find it."""
    results = symbol_catalog.search("folad")
    assert len(results) >= 1
    assert any("فولاد" in r["symbol"] or "فولاد" in r["name"] for r in results)


def test_search_finds_finglish_with_vowel_variants() -> None:
    """و→o/u/w/v variants and double-vowel misspellings must all match."""
    for query in ("folad", "foolad", "fulad"):
        results = symbol_catalog.search(query)
        assert any("فولاد" in r["symbol"] or "فولاد" in r["name"] for r in results), query


def test_search_finds_finglish_coin_names() -> None:
    """Finglish search works for gold/coin names (طلای ۱۸ عیار)."""
    results = symbol_catalog.search("tala")
    assert any("طلا" in r["name"] or "طلا" in r["symbol"] or "طلای" in r["name"] for r in results)


def test_search_finds_finglish_ime_names() -> None:
    """Finglish search works for IME (بورس کالا) contract names."""
    results = symbol_catalog.search("zafaran")
    assert any("زعفران" in r["name"] for r in results)


def test_finglish_empty_match_regression() -> None:
    """The ع empty-candidate bug must not match every word to every query.

    Regression guard: ``عیار`` (in ``طلای ۱۸ عیار``) used to produce a regex
    matching the empty string, so *any* Latin query matched the gold entry.
    After the fix a nonsense Latin query must not return IR_GOLD_18K.
    """
    results = symbol_catalog.search("qzzxwvut")
    assert not any(r["symbol"] == "IR_GOLD_18K" for r in results)
    # Pure-Persian search still works (non-ASCII path untouched).
    assert len(symbol_catalog.search("فولاد")) >= 1


# ── Finglish candidates for DB-backed search ───────────────────

def test_finglish_symbol_candidates_finds_persian_symbols() -> None:
    """A Latin query must yield the matching Persian symbols (e.g. folad→فولاد)."""
    candidates = symbol_catalog.finglish_symbol_candidates("folad")
    assert isinstance(candidates, list)
    assert "فولاد" in candidates
    assert all(not sym.isascii() for sym in candidates), "only Persian symbols are returned"


def test_finglish_symbol_candidates_empty_for_persian_query() -> None:
    """Persian or empty queries return [] so DB search keeps its plain path."""
    assert symbol_catalog.finglish_symbol_candidates("") == []
    assert symbol_catalog.finglish_symbol_candidates("فولاد") == []


def test_finglish_symbol_candidates_latin_symbols_excluded() -> None:
    """Latin symbols (BTC, USD, ...) are NOT candidates — ILIKE handles them."""
    candidates = symbol_catalog.finglish_symbol_candidates("btc")
    assert "BTC" not in candidates
    assert "USD" not in candidates


def test_search_is_case_insensitive_latin() -> None:
    catalog_symbols = {entry["symbol"] for entry in symbol_catalog.all_symbols()}
    # Only meaningful if a Latin symbol exists in the catalog.
    latin = [s for s in catalog_symbols if s.isascii()]
    if not latin:
        return
    probe = latin[0]
    lower = probe.lower()
    upper = probe.upper()
    assert len(symbol_catalog.search(lower)) == len(symbol_catalog.search(upper))


def test_search_empty_query_returns_empty() -> None:
    assert symbol_catalog.search("") == []
    assert symbol_catalog.search("   ") == []


def test_search_unknown_query_returns_empty() -> None:
    assert symbol_catalog.search("نمادناموجود_xyz_123") == []


def test_search_limit_is_respected() -> None:
    # "ف" matches many Persian symbols; ensure we never exceed limit.
    results = symbol_catalog.search("ف", limit=5)
    assert len(results) <= 5


def test_search_limit_clamped() -> None:
    assert len(symbol_catalog.search("ف", limit=9999)) <= 200
    # limit=0 clamps to 1 — a single result max.
    assert len(symbol_catalog.search("ف", limit=0)) <= 1


# ── HTTP endpoint (uses the shared session-scoped app) ─────────

async def test_symbols_search_endpoint(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/symbols/search", params={"q": "فولاد"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    data = payload["data"]
    assert isinstance(data, list) and len(data) >= 1
    assert any("فولاد" in item["symbol"] or "فولاد" in item["name"] for item in data)


async def test_symbols_search_endpoint_finglish(client: httpx.AsyncClient) -> None:
    """GET /symbols/search?q=folad must return the Persian symbol فولاد."""
    resp = await client.get("/api/v1/symbols/search", params={"q": "folad"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    data = payload["data"]
    assert isinstance(data, list) and len(data) >= 1
    assert any(
        "فولاد" in item["symbol"] or "فولاد" in item["name"] for item in data
    ), "q=folad should find فولاد via Finglish transliteration"


async def test_symbols_search_endpoint_missing_q_is_422(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/symbols/search")
    assert resp.status_code == 422


async def test_symbols_list_endpoint(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/symbols", params={"limit": 10})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert len(payload["data"]) <= 10


# ── Sector summary ─────────────────────────────────────────────

EXPECTED_SECTORS = {"سهام", "طلا و سکه", "ارز", "رمزارز", "کامودیتی", "بورس کالا", "صندوق"}


def test_fund_symbols_have_sandogh_sector() -> None:
    """A known fund/ETF symbol must carry sector="صندوق" (not be folded into سهام)."""
    catalog = symbol_catalog.all_symbols()
    by_symbol = {entry["symbol"]: entry for entry in catalog}
    fund_candidates: list[str] = []
    try:
        from services.fund_sync_service import KNOWN_FUND_SYMBOLS

        fund_candidates.extend(list(KNOWN_FUND_SYMBOLS)[:5])
    except Exception:  # noqa: BLE001
        pass
    if not fund_candidates:
        try:
            from brsapi.constants import BRSAPI_ETF_SYMBOLS

            fund_candidates.extend(list(BRSAPI_ETF_SYMBOLS)[:5])
        except Exception:  # noqa: BLE001
            pass
    assert fund_candidates, "expected at least one fund/ETF symbol source to be importable"
    for sym in fund_candidates:
        entry = by_symbol.get(sym)
        assert entry is not None, f"fund symbol {sym} missing from the catalog"
        assert entry["sector"] == "صندوق", f"{sym} must have sector='صندوق', got {entry['sector']!r}"


def test_sector_summary_contains_expected_sectors() -> None:
    summary = symbol_catalog.sector_summary()
    sectors = {row["sector"]: row["count"] for row in summary}
    assert set(sectors) == EXPECTED_SECTORS, f"expected exactly {EXPECTED_SECTORS}, got {set(sectors)}"
    for sector, count in sectors.items():
        assert count >= 1, f"sector {sector!r} must have a positive count"
    # Counts must add up to the full catalog size.
    assert sum(sectors.values()) == len(symbol_catalog.all_symbols())


def test_sector_summary_ordered_by_count_desc() -> None:
    summary = symbol_catalog.sector_summary()
    counts = [row["count"] for row in summary]
    assert counts == sorted(counts, reverse=True), "sectors must be ordered by count descending"


async def test_symbols_sectors_endpoint(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/symbols/sectors")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    data = payload["data"]
    assert isinstance(data, list)
    sectors = {row["sector"] for row in data}
    assert sectors == EXPECTED_SECTORS, f"expected exactly {EXPECTED_SECTORS}, got {sectors}"
    total = sum(row["count"] for row in data)
    assert total == len(symbol_catalog.all_symbols())
