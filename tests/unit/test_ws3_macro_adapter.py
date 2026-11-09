"""WS3: Macro adapter — provider swappable + timeout guard.

RED (before fixes):
  1. macro_news.py has duplicate module-level definitions at lines 44-49:
     ``import logging``, ``logger``, ``REDIS_KEY_MACRO``, and
     ``REDIS_KEY_MACRO_CACHE_DAYS`` are each defined twice. This is a
     copy-paste error; a future change to one block won't update the other.
  2. No SCRAPE_TIMEOUT_SECONDS constant and no asyncio.wait_for wrapper in
     refresh_macro_events_cache() — a stall in scrape_cbi_news() (slow HTML
     parse, partial HTTP body) would block the caller indefinitely.
  3. fetch_macro_events() and scrape_cbi_news() are disconnected. There is no
     refresh_macro_events_cache(scraper) function; the cache can never be
     populated through this module. The scraper is also not injectable, so
     tests must patch httpx instead of passing a mock callable.

GREEN (after fixes):
  1. Duplicate block removed from macro_news.py; each name appears exactly once.
  2. SCRAPE_TIMEOUT_SECONDS: float = 20.0 added; refresh_macro_events_cache()
     wraps the scraper in asyncio.wait_for(timeout=SCRAPE_TIMEOUT_SECONDS).
  3. refresh_macro_events_cache(scraper=scrape_cbi_news, cache=None) added;
     it calls the scraper, deduplicates, and writes to Redis cache.
"""
from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. No duplicate module-level definitions ────────────────────────────────

def test_no_duplicate_redis_key_definition():
    """REDIS_KEY_MACRO must appear exactly once in macro_news.py source.

    RED: 'REDIS_KEY_MACRO = ' appears on lines 36 and 48 — copy-paste bug.
    GREEN: second block removed; exactly one definition remains.
    """
    import src.gold_desk.macro_news as macro_mod

    source = inspect.getsource(macro_mod)
    occurrences = source.count("REDIS_KEY_MACRO =")
    assert occurrences == 1, (
        f"REDIS_KEY_MACRO is defined {occurrences} times in macro_news.py. "
        "Remove the duplicate block (lines ~44–49). "
        "One definition is enough."
    )


def test_no_duplicate_logger_definition():
    """logger = getLogger(__name__) must appear exactly once.

    RED: logger is assigned on lines 34 and 46 — copy-paste bug.
    GREEN: duplicate assignment removed.
    """
    import src.gold_desk.macro_news as macro_mod

    source = inspect.getsource(macro_mod)
    occurrences = source.count('logger = logging.getLogger(__name__)')
    assert occurrences == 1, (
        f"logger is assigned {occurrences} times in macro_news.py. "
        "Remove the duplicate 'logger = logging.getLogger(__name__)' statement."
    )


# ─── 2. SCRAPE_TIMEOUT_SECONDS constant ──────────────────────────────────────

def test_scrape_timeout_constant_exists():
    """macro_news.SCRAPE_TIMEOUT_SECONDS must exist and be ≥ 10s.

    RED: no such constant exists; scraper has no wall-clock guard.
    GREEN: SCRAPE_TIMEOUT_SECONDS: float = 20.0 (or higher) is added.
    """
    import src.gold_desk.macro_news as macro_mod

    assert hasattr(macro_mod, "SCRAPE_TIMEOUT_SECONDS"), (
        "macro_news.SCRAPE_TIMEOUT_SECONDS does not exist. "
        "Add: SCRAPE_TIMEOUT_SECONDS: float = 20.0"
    )
    timeout = macro_mod.SCRAPE_TIMEOUT_SECONDS
    assert isinstance(timeout, (int, float)), (
        f"SCRAPE_TIMEOUT_SECONDS must be a number, got {type(timeout).__name__}."
    )
    assert timeout >= 10.0, (
        f"SCRAPE_TIMEOUT_SECONDS={timeout} is too short; CBI may return large pages."
    )


# ─── 3. Injectable provider / refresh_macro_events_cache ─────────────────────

def test_refresh_macro_events_cache_function_exists():
    """macro_news.refresh_macro_events_cache must exist as a callable.

    RED: no such function exists; scraper and cache are disconnected.
    GREEN: refresh_macro_events_cache(scraper=scrape_cbi_news, cache=None) added.
    """
    import src.gold_desk.macro_news as macro_mod

    assert hasattr(macro_mod, "refresh_macro_events_cache"), (
        "macro_news.refresh_macro_events_cache does not exist. "
        "Add: async def refresh_macro_events_cache(scraper=scrape_cbi_news, cache=None)"
    )
    assert callable(macro_mod.refresh_macro_events_cache), (
        "refresh_macro_events_cache must be callable."
    )


@pytest.mark.asyncio
async def test_refresh_macro_events_cache_calls_scraper_and_writes_cache():
    """refresh_macro_events_cache(scraper) calls scraper and writes to cache.

    RED: function does not exist.
    GREEN: scraper() is called and resulting events are JSON-serialized into
           cache under REDIS_KEY_MACRO.
    """
    from datetime import datetime

    import src.gold_desk.macro_news as macro_mod
    from src.gold_desk.macro_news import MacroEvent, REDIS_KEY_MACRO

    scraper_called = {"n": 0}
    cache_written: dict[str, str] = {}

    fake_event = MacroEvent(
        title="نرخ بهره ثابت ماند",
        source="cbi",
        category="rate",
        impact_score=0,
        confidence=0.5,
        explanation="تست",
        published_at=datetime(2026, 11, 9, 12, 0, 0),
    )

    async def _mock_scraper():
        scraper_called["n"] += 1
        return [fake_event]

    class _MockCache:
        async def get(self, key: str):
            return None

        async def set(self, key: str, value, ttl: int | None = None) -> None:
            cache_written[key] = value

    with patch("core.cache.get_cache", return_value=_MockCache()):
        await macro_mod.refresh_macro_events_cache(scraper=_mock_scraper)

    assert scraper_called["n"] == 1, (
        "refresh_macro_events_cache() did not call the injected scraper."
    )
    assert REDIS_KEY_MACRO in cache_written, (
        f"refresh_macro_events_cache() did not write to cache[{REDIS_KEY_MACRO!r}]."
    )


@pytest.mark.asyncio
async def test_refresh_macro_events_cache_does_not_hang_on_slow_scraper():
    """refresh_macro_events_cache() must respect SCRAPE_TIMEOUT_SECONDS.

    RED: no timeout guard; a stalled scraper stalls the caller.
    GREEN: scraper is wrapped in asyncio.wait_for(SCRAPE_TIMEOUT_SECONDS);
           TimeoutError is caught and an empty list is returned (or re-raised
           as RuntimeError) rather than hanging forever.
    """
    import src.gold_desk.macro_news as macro_mod

    async def _hang_forever():
        await asyncio.sleep(9999)
        return []

    class _MockCache:
        async def get(self, key: str):
            return None
        async def set(self, key: str, value, ttl: int | None = None) -> None:
            pass

    async def _run():
        with patch("core.cache.get_cache", return_value=_MockCache()):
            with patch.object(macro_mod, "SCRAPE_TIMEOUT_SECONDS", 0.1):
                await macro_mod.refresh_macro_events_cache(scraper=_hang_forever)

    # Must complete in under 5 s even though the scraper hangs
    await asyncio.wait_for(_run(), timeout=5.0)
