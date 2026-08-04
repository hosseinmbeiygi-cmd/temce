"""Unit tests for Finglish transliteration in ``InstrumentRepository.search``.

The in-memory fallback path (no PostgreSQL session) is fully testable in
CI — these tests seed instruments into the shared in-memory store and
verify that a Latin (Finglish) query like ``folad`` also finds the Persian
symbol ``فولاد``, with correct de-duplication against the plain substring
match.
"""

from __future__ import annotations

from domain.instruments.instrument import Instrument
from repositories.base_repository import InMemoryRepository
from repositories.instrument_repository import InstrumentRepository


def _make_instrument(id: str, symbol: str, name: str = "") -> Instrument:
    return Instrument(id=id, symbol=symbol, name=name)


async def _seed_store() -> None:
    """Reset the shared in-memory store and seed a few instruments."""
    InMemoryRepository._shared_store.clear()
    repo = InstrumentRepository()  # no session → in-memory fallback
    await repo.save(_make_instrument("1", "فولاد", "فولاد خوزستان"))
    await repo.save(_make_instrument("2", "فملی", "ملی صنایع مس ایران"))
    await repo.save(_make_instrument("3", "BTC", "بیت‌کوین"))


async def test_inmemory_search_finds_persian_symbol_via_finglish() -> None:
    """A Latin query must find the Persian symbol through transliteration."""
    await _seed_store()
    repo = InstrumentRepository()
    result = await repo.search("folad")
    assert result.success
    symbols = [inst.symbol for inst in result.value.items]
    assert "فولاد" in symbols, f"folad should find فولاد, got {symbols}"


async def test_inmemory_search_finds_persian_symbol_via_direct_match() -> None:
    """A Persian query keeps its plain substring behaviour."""
    await _seed_store()
    repo = InstrumentRepository()
    result = await repo.search("فولاد")
    assert result.success
    symbols = [inst.symbol for inst in result.value.items]
    assert "فولاد" in symbols


async def test_inmemory_search_persian_query_no_duplicates() -> None:
    """A Persian query returns each matching symbol exactly once.

    (Finglish candidates are Persian-only and a Latin query can never
    substring-match a Persian symbol, so the ``known``-set dedup in the
    in-memory path is a defensive guard — the plain path is sanity-checked
    here instead.)
    """
    await _seed_store()
    repo = InstrumentRepository()
    result = await repo.search("فولاد")
    assert result.success
    symbols = [inst.symbol for inst in result.value.items]
    assert symbols.count("فولاد") == 1, "no duplicate results expected"


async def test_inmemory_search_plain_latin_still_works() -> None:
    """Latin symbols are found via plain substring regardless of transliteration."""
    await _seed_store()
    repo = InstrumentRepository()
    result = await repo.search("btc")
    assert result.success
    symbols = [inst.symbol for inst in result.value.items]
    assert "BTC" in symbols


async def test_inmemory_search_no_match_returns_empty() -> None:
    """A nonsense query returns an empty page (not an error)."""
    await _seed_store()
    repo = InstrumentRepository()
    result = await repo.search("zzzqqq_nonsense_123")
    assert result.success
    assert result.value.items == []
    assert result.value.total == 0
