"""Placeholder foreign-news providers must not report healthy.

Audit DS-04. All three providers ship with an ``api.example.com`` base URL and
returned ``{"healthy": True}``, so a deployment that never configured them
looked like it had three working news sources.
"""

from __future__ import annotations

import pytest

from providers.news.foreign.commodities_news_provider import CommoditiesNewsProvider
from providers.news.foreign.fx_news_provider import FXNewsProvider
from providers.news.foreign.global_market_news_provider import GlobalMarketNewsProvider

PROVIDERS = [CommoditiesNewsProvider, FXNewsProvider, GlobalMarketNewsProvider]


@pytest.mark.parametrize("provider_cls", PROVIDERS)
async def test_placeholder_provider_is_not_healthy(provider_cls) -> None:
    health = await provider_cls().health()

    assert health["healthy"] is False
    assert "placeholder" in health["message"]


@pytest.mark.parametrize("provider_cls", PROVIDERS)
async def test_placeholder_provider_does_not_pretend_to_fetch(provider_cls) -> None:
    result = await provider_cls().fetch_news(limit=5)

    assert result.success is False
    assert "provider_not_configured" in (result.error or "")
