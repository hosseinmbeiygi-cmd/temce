"""TDD tests for GoldNewsRSSProvider (multi-feed RSS news client)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ── sample RSS XML ────────────────────────────────────────────────────────────

_RSS_KITCO = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Kitco Gold News</title>
    <link>https://www.kitco.com</link>
    <item>
      <title>Gold rises as dollar weakens</title>
      <link>https://www.kitco.com/news/2026-11-10/gold-rises.html</link>
      <description>Gold climbed 0.8% on Tuesday as the dollar...</description>
      <pubDate>Mon, 10 Nov 2026 14:30:00 +0000</pubDate>
    </item>
    <item>
      <title>Fed signals pause on rate hikes</title>
      <link>https://www.kitco.com/news/2026-11-09/fed-pause.html</link>
      <description>The Federal Reserve indicated...</description>
      <pubDate>Sun, 09 Nov 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

_RSS_SANA = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>سنا - بورس کالا</title>
    <item>
      <title>قیمت سکه در بازار آزاد</title>
      <link>https://sana.ir/fa/news/123456</link>
      <description>سکه امروز در معاملات...</description>
      <pubDate>Mon, 10 Nov 2026 09:00:00 +0330</pubDate>
    </item>
  </channel>
</rss>"""


def _mock_client_map(feed_xml_map: dict[str, str]) -> MagicMock:
    """Return a mock client that returns different XML per URL."""
    async def _get(url: str, **kwargs):
        xml = feed_xml_map.get(url, "<rss version='2.0'><channel></channel></rss>")
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.text = xml
        return resp

    client = MagicMock()
    client.get = AsyncMock(side_effect=_get)
    client.aclose = AsyncMock()
    return client


def _mock_single(xml_text: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.text = xml_text
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_importable():
    from providers.macro_sources.news_rss import (  # noqa: F401
        GOLD_RSS_FEEDS,
        GoldNewsRSSProvider,
        NewsItem,
        RSSFeedConfig,
        RSSNewsClient,
    )


def test_feed_catalogue_contains_expected_sources():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS

    expected = {"kitco", "fxstreet_gold", "sana", "ibna", "tgju_news"}
    missing = expected - set(GOLD_RSS_FEEDS.keys())
    assert not missing, f"Missing feeds: {missing}"


def test_international_feeds_are_english():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS

    for name, cfg in GOLD_RSS_FEEDS.items():
        if cfg.category == "international":
            assert cfg.language == "en", f"{name} should be 'en'"


def test_domestic_feeds_are_persian():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS

    for name, cfg in GOLD_RSS_FEEDS.items():
        if cfg.category == "domestic":
            assert cfg.language == "fa", f"{name} should be 'fa'"


# ── 2. RSS parsing ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_feed_parses_items():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    client = RSSNewsClient(client=_mock_single(_RSS_KITCO))
    items = await client.fetch_feed(GOLD_RSS_FEEDS["kitco"])

    assert len(items) == 2
    assert items[0].title == "Gold rises as dollar weakens"
    assert items[0].source == "Kitco News"
    assert items[0].language == "en"
    assert items[0].category == "international"


@pytest.mark.asyncio
async def test_fetch_feed_parses_pubdate_to_iso():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    client = RSSNewsClient(client=_mock_single(_RSS_KITCO))
    items = await client.fetch_feed(GOLD_RSS_FEEDS["kitco"])

    # pubDate "Mon, 10 Nov 2026 14:30:00 +0000" should parse to ISO-8601
    assert "2026" in items[0].published_at
    assert "T" in items[0].published_at  # ISO format contains T


@pytest.mark.asyncio
async def test_fetch_feed_strips_html_from_description():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    html_xml = """<rss version="2.0"><channel>
      <item>
        <title>Test</title>
        <link>https://example.com</link>
        <description><p>Gold <strong>climbed</strong> 0.8%</p></description>
        <pubDate>Mon, 10 Nov 2026 14:30:00 +0000</pubDate>
      </item>
    </channel></rss>"""
    client = RSSNewsClient(client=_mock_single(html_xml))
    items = await client.fetch_feed(GOLD_RSS_FEEDS["kitco"])

    assert "<" not in items[0].summary
    assert "Gold" in items[0].summary


@pytest.mark.asyncio
async def test_fetch_feed_returns_empty_on_bad_xml():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    client = RSSNewsClient(client=_mock_single("not xml at all"))
    items = await client.fetch_feed(GOLD_RSS_FEEDS["kitco"])
    assert items == []


@pytest.mark.asyncio
async def test_fetch_feed_returns_empty_on_network_error():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("timeout"))
    bad.aclose = AsyncMock()

    client = RSSNewsClient(client=bad)
    items = await client.fetch_feed(GOLD_RSS_FEEDS["kitco"])
    assert items == []


# ── 3. Multi-feed fetch ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_feeds_merges_results():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    feed_map = {
        GOLD_RSS_FEEDS["kitco"].url: _RSS_KITCO,
        GOLD_RSS_FEEDS["sana"].url: _RSS_SANA,
    }
    client = RSSNewsClient(client=_mock_client_map(feed_map))
    items = await client.fetch_feeds(feed_names=["kitco", "sana"])

    assert len(items) == 3  # 2 kitco + 1 sana
    sources = {i.source for i in items}
    assert "Kitco News" in sources
    assert "سنا - بورس کالا" in sources


@pytest.mark.asyncio
async def test_fetch_feeds_category_filter():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    feed_map = {
        GOLD_RSS_FEEDS["kitco"].url: _RSS_KITCO,
        GOLD_RSS_FEEDS["sana"].url: _RSS_SANA,
    }
    client = RSSNewsClient(client=_mock_client_map(feed_map))
    items = await client.fetch_feeds(category="domestic")

    assert all(i.category == "domestic" for i in items)


@pytest.mark.asyncio
async def test_fetch_feeds_language_filter():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, RSSNewsClient

    feed_map = {
        GOLD_RSS_FEEDS["kitco"].url: _RSS_KITCO,
        GOLD_RSS_FEEDS["sana"].url: _RSS_SANA,
    }
    client = RSSNewsClient(client=_mock_client_map(feed_map))
    items = await client.fetch_feeds(feed_names=["kitco", "sana"], language="fa")

    assert all(i.language == "fa" for i in items)


# ── 4. GoldNewsRSSProvider ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_fetch_returns_result_ok():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, GoldNewsRSSProvider

    feed_map = {GOLD_RSS_FEEDS["kitco"].url: _RSS_KITCO}
    provider = GoldNewsRSSProvider(
        client=_mock_client_map(feed_map),
        feed_names=["kitco"],
    )
    result = await provider.fetch()

    assert result.success
    assert len(result.value) == 2
    assert result.value[0]["title"] == "Gold rises as dollar weakens"


@pytest.mark.asyncio
async def test_provider_fetch_sorts_newest_first():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, GoldNewsRSSProvider

    feed_map = {GOLD_RSS_FEEDS["kitco"].url: _RSS_KITCO}
    provider = GoldNewsRSSProvider(
        client=_mock_client_map(feed_map),
        feed_names=["kitco"],
    )
    result = await provider.fetch()

    dates = [item["published_at"] for item in result.value]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_provider_fetch_respects_limit():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, GoldNewsRSSProvider

    feed_map = {GOLD_RSS_FEEDS["kitco"].url: _RSS_KITCO}
    provider = GoldNewsRSSProvider(
        client=_mock_client_map(feed_map),
        feed_names=["kitco"],
    )
    result = await provider.fetch(limit=1)

    assert len(result.value) == 1


@pytest.mark.asyncio
async def test_provider_fetch_returns_fail_when_all_feeds_empty():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, GoldNewsRSSProvider

    empty_xml = "<rss version='2.0'><channel></channel></rss>"
    feed_map = {GOLD_RSS_FEEDS["kitco"].url: empty_xml}
    provider = GoldNewsRSSProvider(
        client=_mock_client_map(feed_map),
        feed_names=["kitco"],
    )
    result = await provider.fetch()
    assert not result.success


@pytest.mark.asyncio
async def test_provider_health_check():
    from providers.macro_sources.news_rss import GOLD_RSS_FEEDS, GoldNewsRSSProvider

    feed_map = {GOLD_RSS_FEEDS["kitco"].url: _RSS_KITCO}
    provider = GoldNewsRSSProvider(client=_mock_client_map(feed_map))
    h = await provider.health()
    assert h["healthy"] is True
