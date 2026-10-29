"""A malformed feed body must not read as "the feed is empty".

Audit DS-03. ``RSSParser.parse`` swallowed ``ET.ParseError`` and returned ``[]``,
so a WAF/HTML page or truncated XML was counted as a healthy empty feed.
"""

from __future__ import annotations

import pytest

from core.result import Result
from providers.news.rss.rss_parser import RSSParseError, RSSParser
from providers.news.rss.rss_provider import RSSNewsProvider

VALID_EMPTY = '<rss version="2.0"><channel><title>x</title></channel></rss>'
# Truncated / unbalanced markup — what a WAF block page or a cut connection
# actually leaves behind (well-formed HTML would parse as XML).
MALFORMED = "<html><body>blocked<div></body></html>"


class _ClientStub:
    def __init__(self, body: str) -> None:
        self.body = body

    async def fetch_feed(self, url: str) -> Result[str]:
        return Result.ok(self.body)


def _provider(body: str) -> RSSNewsProvider:
    provider = RSSNewsProvider(name="rss_malformed")
    provider.client = _ClientStub(body)  # type: ignore[assignment]
    provider.feeds = {"a": "https://example.invalid/a"}
    return provider


def test_parser_raises_on_malformed_xml() -> None:
    with pytest.raises(RSSParseError):
        RSSParser().parse(MALFORMED)


def test_parser_keeps_a_valid_empty_feed_empty() -> None:
    assert RSSParser().parse(VALID_EMPTY) == []


async def test_fetch_feed_reports_a_parse_error() -> None:
    result = await _provider(MALFORMED).fetch_feed("https://example.invalid/a")

    assert result.success is False
    assert "parse_error" in (result.error or "")


async def test_all_malformed_feeds_fail_the_fetch() -> None:
    result = await _provider(MALFORMED).fetch_news(limit=5)

    assert result.success is False
    assert "a" in (result.error or "")


UNDATED_ITEM = (
    '<rss version="2.0"><channel><item>'
    "<title>undated</title><link>https://example.invalid/1</link>"
    "</item></channel></rss>"
)
DATED_ITEM = (
    '<rss version="2.0"><channel><item>'
    "<title>dated</title><link>https://example.invalid/2</link>"
    "<pubDate>Wed, 01 Oct 2025 10:00:00 GMT</pubDate>"
    "</item></channel></rss>"
)


def test_an_undated_item_keeps_published_at_empty() -> None:
    """Audit DS-06: ingestion time must not masquerade as the source date."""
    items = RSSParser().parse(UNDATED_ITEM)

    assert items[0]["published_at"] is None


def test_a_dated_item_keeps_the_source_date() -> None:
    items = RSSParser().parse(DATED_ITEM)

    assert items[0]["published_at"]
