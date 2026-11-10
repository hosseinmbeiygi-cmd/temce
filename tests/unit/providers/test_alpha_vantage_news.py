"""TDD tests for the Alpha Vantage News Sentiment provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


_SAMPLE_PAYLOAD = {
    "items": "2",
    "sentiment_score_definition": "...",
    "relevance_score_definition": "...",
    "feed": [
        {
            "title": "Gold prices rise amid Fed uncertainty",
            "url": "https://example.com/gold-news-1",
            "time_published": "20261110T143000",
            "summary": "Gold rose 0.8% on Tuesday...",
            "source": "Reuters",
            "overall_sentiment_score": 0.312,
            "overall_sentiment_label": "Somewhat-Bullish",
            "ticker_sentiment": [
                {"ticker": "COMMODITY:GOLD", "relevance_score": "0.85", "ticker_sentiment_score": "0.42"}
            ],
            "topics": [
                {"topic": "gold", "relevance_score": "0.90"},
                {"topic": "economy_macro", "relevance_score": "0.60"},
            ],
        },
        {
            "title": "CPI data weighs on gold outlook",
            "url": "https://example.com/gold-news-2",
            "time_published": "20261110T090000",
            "summary": "Higher-than-expected CPI...",
            "source": "Bloomberg",
            "overall_sentiment_score": -0.15,
            "overall_sentiment_label": "Somewhat-Bearish",
            "ticker_sentiment": [],
            "topics": [
                {"topic": "gold", "relevance_score": "0.70"},
            ],
        },
    ],
}


def _mock_client(payload: dict = _SAMPLE_PAYLOAD) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_importable():
    from providers.macro_sources.alpha_vantage import (  # noqa: F401
        AV_BASE_URL,
        AlphaVantageNewsClient,
        AlphaVantageNewsProvider,
        AVNewsItem,
    )


# ── 2. fetch_gold_news — happy path ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_news_items():
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsClient

    client = AlphaVantageNewsClient(api_key="test-key", client=_mock_client())
    items = await client.fetch_gold_news()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_item_fields_populated():
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsClient

    client = AlphaVantageNewsClient(api_key="test-key", client=_mock_client())
    items = await client.fetch_gold_news()
    item = items[0]

    assert "Gold" in item.title
    assert item.source == "Reuters"
    assert item.overall_sentiment_label == "Somewhat-Bullish"
    assert item.overall_sentiment_score == pytest.approx(0.312)
    assert item.relevance_score == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_relevance_falls_back_to_topic_score():
    """When no COMMODITY:GOLD ticker match, fall back to 'gold' topic score."""
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsClient

    client = AlphaVantageNewsClient(api_key="test-key", client=_mock_client())
    items = await client.fetch_gold_news()
    item = items[1]  # has no ticker_sentiment
    assert item.relevance_score == pytest.approx(0.70)


# ── 3. Error handling ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_api_key_raises():
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsClient
    from providers.macro_sources.base import MacroSourceError

    client = AlphaVantageNewsClient(api_key="", client=_mock_client())
    with pytest.raises(MacroSourceError, match="ALPHA_VANTAGE_API_KEY"):
        await client.fetch_gold_news()


@pytest.mark.asyncio
async def test_rate_limit_information_raises():
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsClient
    from providers.macro_sources.base import MacroSourceError

    rate_limited = {"Information": "Thank you for using Alpha Vantage! ...25 requests per day..."}
    client = AlphaVantageNewsClient(api_key="test-key", client=_mock_client(rate_limited))
    with pytest.raises(MacroSourceError, match="AlphaVantage"):
        await client.fetch_gold_news()


@pytest.mark.asyncio
async def test_network_error_returns_empty():
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsClient

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("timeout"))
    bad.aclose = AsyncMock()

    client = AlphaVantageNewsClient(api_key="test-key", client=bad)
    items = await client.fetch_gold_news()
    assert items == []


# ── 4. AlphaVantageNewsProvider ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_fetch_returns_result_ok():
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsProvider

    import providers.macro_sources.alpha_vantage as module
    orig = module._get_av_key
    module._get_av_key = lambda: "test-key"
    try:
        provider = AlphaVantageNewsProvider(client=_mock_client())
        result = await provider.fetch()
    finally:
        module._get_av_key = orig

    assert result.success
    assert len(result.value) == 2
    assert "sentiment_score" in result.value[0]
    assert "sentiment_label" in result.value[0]


@pytest.mark.asyncio
async def test_provider_returns_fail_on_missing_key():
    from providers.macro_sources.alpha_vantage import AlphaVantageNewsProvider

    import providers.macro_sources.alpha_vantage as module
    orig = module._get_av_key
    module._get_av_key = lambda: ""
    try:
        provider = AlphaVantageNewsProvider(client=_mock_client())
        result = await provider.fetch()
    finally:
        module._get_av_key = orig

    assert not result.success
    assert "ALPHA_VANTAGE_API_KEY" in result.error
