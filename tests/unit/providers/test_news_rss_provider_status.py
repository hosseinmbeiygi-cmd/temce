"""RSS provider status: a silent zero must be distinguishable from a failure.

``RSSNewsProvider.fetch_news`` used to return ``Result.ok([])`` both when no
feeds were configured and when every feed errored, so the ingest path logged
"No articles fetched" and reported success with zero records. The contract
pinned here (offline, no network — ``parse_feed`` is stubbed):

* no feeds configured  → failure (configuration gap, not an empty result);
* every feed failed    → failure carrying the per-source reasons;
* some feeds failed    → the healthy articles are still returned;
* every feed returned zero items → a legitimate ``ok([])``.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.result import Result
from providers.news.rss.rss_provider import RSSNewsProvider


class _FeedStub(RSSNewsProvider):
    """Provider whose feeds/parse results are scripted per URL."""

    def __init__(self, outcomes: dict[str, Any]) -> None:
        super().__init__(name="rss_stub")
        self.feeds = {name: f"https://example.invalid/{name}" for name in outcomes}
        self._outcomes = outcomes

    async def parse_feed(self, url: str, limit: int = 50) -> Result[list[dict[str, Any]]]:
        name = url.rsplit("/", 1)[-1]
        outcome = self._outcomes[name]
        if isinstance(outcome, str):
            return Result.fail(outcome)
        return Result.ok(outcome)


@pytest.mark.asyncio
async def test_no_feeds_configured_is_a_failure_not_an_empty_success() -> None:
    provider = RSSNewsProvider(name="rss_empty")

    result = await provider.fetch_news(limit=10)

    assert result.success is False
    assert "no_feeds_configured" in (result.error or "")


@pytest.mark.asyncio
async def test_all_feeds_failing_reports_a_failure_with_per_source_detail() -> None:
    provider = _FeedStub({"a": "timeout", "b": "http 503"})

    result = await provider.fetch_news(limit=10)

    assert result.success is False
    assert "a" in (result.error or "") and "b" in (result.error or "")
    assert "timeout" in (result.error or "")


@pytest.mark.asyncio
async def test_partial_failure_still_returns_the_healthy_articles() -> None:
    article = {"title": "t", "link": "https://example.invalid/1"}
    provider = _FeedStub({"good": [article], "bad": "http 500"})

    result = await provider.fetch_news(limit=10)

    assert result.success is True
    assert [a["title"] for a in (result.value or [])] == ["t"]
    # the source key must be attached so the failure stays traceable downstream
    assert (result.value or [{}])[0]["_source_feed"] == "good"


@pytest.mark.asyncio
async def test_feeds_that_are_reachable_but_empty_are_an_ok_empty_result() -> None:
    provider = _FeedStub({"a": [], "b": []})

    result = await provider.fetch_news(limit=10)

    assert result.success is True
    assert result.value == []


@pytest.mark.asyncio
async def test_per_source_report_is_exposed_for_the_ingest_stats() -> None:
    """Stage 9: each feed's outcome (ok/empty/failed+reason) must be readable."""
    provider = _FeedStub({"good": [{"title": "t"}], "blank": [], "dead": "http 503"})

    await provider.fetch_news(limit=10)

    report = provider.last_feed_report
    assert report["ok"] == ["good"]
    assert report["empty"] == ["blank"]
    assert report["failed"] == {"dead": "http 503"}


@pytest.mark.asyncio
async def test_report_is_reset_between_runs() -> None:
    provider = _FeedStub({"a": "timeout"})
    await provider.fetch_news(limit=10)

    provider._outcomes = {"a": []}
    await provider.fetch_news(limit=10)

    assert provider.last_feed_report == {"ok": [], "empty": ["a"], "failed": {}}
