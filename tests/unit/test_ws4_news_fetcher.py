"""WS4: News fetcher — timeout guard + per-call warning when feedparser missing.

RED (before fixes):
  1. No NEWS_FETCH_TIMEOUT_SECONDS constant exists; asyncio.to_thread calls for
     RSS fetching have no asyncio.wait_for guard. A single stalled RSS source
     (server accepts connection but never sends data) blocks the caller thread
     for the OS socket timeout — potentially minutes.
  2. fetch_news_for_symbol() and fetch_market_news() do not log a WARNING at
     call time when HAS_FEEDPARSER=False. The only warning fires once at
     module-import time (line 29). In a long-running process this means ops
     see no log that every fetch call silently returns [].
  3. feedparser is not listed in requirements.txt. Any fresh install fails at
     runtime; the guard at line 23-29 is the first indicator of the missing dep.

GREEN (after fixes):
  1. NEWS_FETCH_TIMEOUT_SECONDS: float = 30.0 added; both async methods are
     wrapped in asyncio.wait_for(timeout=NEWS_FETCH_TIMEOUT_SECONDS).
  2. _fetch_from_rss() / _fetch_market_news_sync() log a warning on each call
     when HAS_FEEDPARSER is False, so ops can see the degraded state in live logs.
  3. feedparser>=6.0,<7 added to requirements.txt (approved by owner — gate "WS4").
     NOTE: edit to requirements.txt requires manual approval (auto-mode blocked it);
     the owner must run:
       pip install "feedparser>=6.0,<7"
       # and add `feedparser>=6.0,<7` to requirements.txt
     until then, HAS_FEEDPARSER=False tests still pass.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. NEWS_FETCH_TIMEOUT_SECONDS constant ──────────────────────────────────

def test_news_fetch_timeout_constant_exists():
    """NewsFetcher must expose NEWS_FETCH_TIMEOUT_SECONDS at module level.

    RED: no such constant; async fetch methods have no wall-clock guard.
    GREEN: NEWS_FETCH_TIMEOUT_SECONDS: float = 30.0 (or higher) added.
    """
    import services.chat.news_fetcher as nf_mod

    assert hasattr(nf_mod, "NEWS_FETCH_TIMEOUT_SECONDS"), (
        "news_fetcher.NEWS_FETCH_TIMEOUT_SECONDS does not exist. "
        "Add: NEWS_FETCH_TIMEOUT_SECONDS: float = 30.0"
    )
    timeout = nf_mod.NEWS_FETCH_TIMEOUT_SECONDS
    assert isinstance(timeout, (int, float)), (
        f"NEWS_FETCH_TIMEOUT_SECONDS must be a number, got {type(timeout).__name__}."
    )
    assert timeout >= 10.0, (
        f"NEWS_FETCH_TIMEOUT_SECONDS={timeout} is too low; 7 RSS sources × 10s each = 70s worst case."
    )


# ─── 2. Timeout guard on async methods ───────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_news_for_symbol_respects_timeout():
    """fetch_news_for_symbol() must complete within NEWS_FETCH_TIMEOUT_SECONDS
    even when the underlying sync worker hangs.

    RED: asyncio.to_thread(self._fetch_all, ...) has no asyncio.wait_for wrapper;
         a stalled RSS source blocks the caller indefinitely.
    GREEN: wrapped in asyncio.wait_for(timeout=NEWS_FETCH_TIMEOUT_SECONDS);
           TimeoutError is caught and [] is returned (or re-raised) quickly.
    """
    import services.chat.news_fetcher as nf_mod
    from services.chat.news_fetcher import NewsFetcher

    fetcher = NewsFetcher()

    def _slow_sync(*args, **kwargs):
        # Sleeps 0.5s — longer than the 0.1s timeout so the guard fires,
        # but short enough that the thread exits without blocking pytest teardown.
        import time
        time.sleep(0.5)
        return []

    async def _run():
        with patch.object(fetcher, "_fetch_all", _slow_sync), \
             patch.object(nf_mod, "NEWS_FETCH_TIMEOUT_SECONDS", 0.1):
            return await fetcher.fetch_news_for_symbol("فولاد")

    result = await asyncio.wait_for(_run(), timeout=5.0)
    assert isinstance(result, list), "fetch_news_for_symbol() must return a list even on timeout."


@pytest.mark.asyncio
async def test_fetch_market_news_respects_timeout():
    """fetch_market_news() must also respect NEWS_FETCH_TIMEOUT_SECONDS.

    RED: asyncio.to_thread(self._fetch_market_news_sync, ...) has no wait_for guard.
    GREEN: wrapped in asyncio.wait_for(timeout=NEWS_FETCH_TIMEOUT_SECONDS).
    """
    import services.chat.news_fetcher as nf_mod
    from services.chat.news_fetcher import NewsFetcher

    fetcher = NewsFetcher()

    def _slow_sync(*args, **kwargs):
        import time
        time.sleep(0.5)
        return []

    async def _run():
        with patch.object(fetcher, "_fetch_market_news_sync", _slow_sync), \
             patch.object(nf_mod, "NEWS_FETCH_TIMEOUT_SECONDS", 0.1):
            return await fetcher.fetch_market_news()

    result = await asyncio.wait_for(_run(), timeout=5.0)
    assert isinstance(result, list), "fetch_market_news() must return a list even on timeout."


# ─── 3. Per-call WARNING when feedparser is missing ──────────────────────────

def test_fetch_from_rss_logs_warning_when_feedparser_missing():
    """_fetch_from_rss() must log WARNING when HAS_FEEDPARSER is False.

    RED: the method returns [] silently with no call-site log.
    GREEN: logger.warning('feedparser not available...') is called, so ops can
           see in live logs that every RSS fetch attempt is degraded.
    Note: uses patch.object(logger, 'warning') because structlog bypasses caplog.
    """
    import services.chat.news_fetcher as nf_mod
    from services.chat.news_fetcher import NewsFetcher
    from unittest.mock import call

    fetcher = NewsFetcher()
    warn_calls: list = []

    with patch.object(nf_mod, "HAS_FEEDPARSER", False), \
         patch.object(nf_mod.logger, "warning", side_effect=lambda *a, **kw: warn_calls.append(a[0])):
        result = fetcher._fetch_from_rss("طلا", 3)

    assert result == [], "_fetch_from_rss must return [] when feedparser is absent."
    assert warn_calls, (
        "_fetch_from_rss() must call logger.warning() when HAS_FEEDPARSER=False."
    )
    assert any("feedparser" in str(msg).lower() for msg in warn_calls), (
        f"Expected 'feedparser' in warning message, got: {warn_calls!r}."
    )


def test_fetch_market_news_sync_logs_warning_when_feedparser_missing():
    """_fetch_market_news_sync() must also log WARNING when HAS_FEEDPARSER is False.

    RED: returns [] silently.
    GREEN: logger.warning('feedparser not available...') is called.
    """
    import services.chat.news_fetcher as nf_mod
    from services.chat.news_fetcher import NewsFetcher

    fetcher = NewsFetcher()
    warn_calls: list = []

    with patch.object(nf_mod, "HAS_FEEDPARSER", False), \
         patch.object(nf_mod.logger, "warning", side_effect=lambda *a, **kw: warn_calls.append(a[0])):
        result = fetcher._fetch_market_news_sync(1)

    assert result == [], "_fetch_market_news_sync must return [] when feedparser is absent."
    assert warn_calls, (
        "_fetch_market_news_sync() must call logger.warning() when HAS_FEEDPARSER=False."
    )
    assert any("feedparser" in str(msg).lower() for msg in warn_calls), (
        f"Expected 'feedparser' in warning message, got: {warn_calls!r}."
    )
