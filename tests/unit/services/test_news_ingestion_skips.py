"""Ingestion outcome accounting: a skipped duplicate is NOT a save.

``NewsIngestionService._save_article`` returns early when
``repo.exists_by_url_or_title`` reports the article already exists (the
cross-run dedup guard). The pipeline used to count every early return as a
successful save, so ``stats["saved"]`` reported rows that were never written
and the removal reason was invisible everywhere (job result, ``/news/refresh``
status, CLI summary).

These tests pin the honest accounting using only in-memory fakes — no
PostgreSQL, no live feed.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.result import Result


class _FakeRSSProvider:
    """Stands in for ``RSSDomesticProvider`` (no network)."""

    def __init__(self) -> None:
        self.feeds = {"fake_feed": "https://example.invalid/rss"}

    async def fetch_news(self, limit: int = 50, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.ok(
            [
                {
                    "title": "dup article",
                    "description": "d" * 120,
                    "link": "https://example.invalid/dup",
                },
                {
                    "title": "fresh article",
                    "description": "f" * 120,
                    "link": "https://example.invalid/fresh",
                },
            ]
        )


class _FakeNewsService:
    """Minimal ``NewsService`` stand-in (repo + save)."""

    def __init__(
        self,
        existing_titles: set[str] | None = None,
        fail_titles: set[str] | None = None,
        reject_titles: set[str] | None = None,
    ) -> None:
        self.repo = self
        self.existing_titles = existing_titles or set()
        self.fail_titles = fail_titles or set()
        # ``reject_titles`` fail without raising — a ``Result.fail`` from save.
        self.reject_titles = reject_titles or set()
        self.saved_titles: list[str] = []

    async def exists_by_url_or_title(self, url: str, title: str) -> bool:
        return title in self.existing_titles

    async def save(self, item: Any) -> Result[Any]:
        if item.title in self.fail_titles:
            raise RuntimeError(f"boom for {item.title}")
        self.saved_titles.append(item.title)
        if item.title in self.reject_titles:
            return Result.fail(f"repository rejected {item.title}")
        return Result.ok(item)


def _service(monkeypatch: pytest.MonkeyPatch, fake: _FakeNewsService) -> Any:
    from services import news_ingestion as mod

    monkeypatch.setattr(mod, "RSSDomesticProvider", _FakeRSSProvider)
    # session=None + dual_write disabled ⇒ the mirror is a no-op, so the test
    # needs no database at all.
    return mod.NewsIngestionService(news_service=fake, session=None, dual_write_enabled=False)


@pytest.mark.asyncio
async def test_existing_article_is_reported_as_skipped_not_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeNewsService(existing_titles={"dup article"})
    service = _service(monkeypatch, fake)

    stats = await service.ingest(save=True, verbose=False)

    assert fake.saved_titles == ["fresh article"]
    assert stats["saved"] == 1, "only the row actually written may be counted as saved"
    assert stats["skipped_existing"] == 1


@pytest.mark.asyncio
async def test_all_duplicates_reports_zero_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fully-duplicate batch must not look like a successful ingest."""
    fake = _FakeNewsService(existing_titles={"dup article", "fresh article"})
    service = _service(monkeypatch, fake)

    stats = await service.ingest(save=True, verbose=False)

    assert fake.saved_titles == []
    assert stats["saved"] == 0
    assert stats["skipped_existing"] == 2


@pytest.mark.asyncio
async def test_save_failure_is_counted_and_does_not_abort_the_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One poisoned row must be traceable (error count) without losing the rest."""
    fake = _FakeNewsService(fail_titles={"dup article"})
    service = _service(monkeypatch, fake)

    stats = await service.ingest(save=True, verbose=False)

    assert stats["errors"] == 1
    assert stats["saved"] == 1
    assert fake.saved_titles == ["fresh article"]


@pytest.mark.asyncio
async def test_legacy_save_result_failure_is_not_counted_as_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Result.fail`` from the legacy save must surface as an error, not a save."""
    fake = _FakeNewsService(reject_titles={"dup article"})
    service = _service(monkeypatch, fake)

    stats = await service.ingest(save=True, verbose=False)

    assert stats["saved"] == 1
    assert stats["errors"] == 1


@pytest.mark.asyncio
async def test_per_source_outcome_reaches_the_ingest_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial feed outage must be visible per source, not folded into one count."""
    from services import news_ingestion as mod

    class _PartialProvider(_FakeRSSProvider):
        last_feed_report = {
            "ok": ["fake_feed"],
            "empty": ["empty_feed"],
            "failed": {"dead_feed": "Timeout after 20s"},
        }

    monkeypatch.setattr(mod, "RSSDomesticProvider", _PartialProvider)
    fake = _FakeNewsService()
    service = mod.NewsIngestionService(
        news_service=fake, session=None, dual_write_enabled=False
    )

    stats = await service.ingest(save=False, verbose=False)

    assert stats["source_report"] == {
        "ok": ["fake_feed"],
        "empty": ["empty_feed"],
        "failed": {"dead_feed": "Timeout after 20s"},
    }


@pytest.mark.asyncio
async def test_fetch_failure_is_recorded_instead_of_a_silent_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider failure must leave a trace (error count + reason).

    Previously the ingest logged a warning and returned zeroed stats, so the
    job result and ``/news/refresh`` reported a clean run with 0 records.
    """
    from core.result import Result
    from services import news_ingestion as mod

    class _FailingProvider:
        feeds = {"a": "https://example.invalid/a"}

        async def fetch_news(self, **kwargs: Any) -> Result[list[dict[str, Any]]]:
            return Result.fail("no_feeds_configured:rss_domestic")

    monkeypatch.setattr(mod, "RSSDomesticProvider", _FailingProvider)
    fake = _FakeNewsService()
    service = mod.NewsIngestionService(news_service=fake, session=None, dual_write_enabled=False)

    stats = await service.ingest(save=True, verbose=False)

    assert stats["saved"] == 0
    assert stats["errors"] == 1
    assert "no_feeds_configured" in stats["fetch_error"]


@pytest.mark.asyncio
async def test_sentiment_failure_is_counted_and_does_not_fail_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A classifier outage degrades one field, it must not look like "neutral news".

    Every article keeps the neutral display default, but the number of failed
    classifications is reported in ``sentiment_errors`` so the outage is
    visible without failing an otherwise successful ingest.
    """
    from services import news_ingestion as mod

    class _FailingClassifier:
        def classify(self, text: str) -> dict[str, Any]:
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(mod, "RSSDomesticProvider", _FakeRSSProvider)
    fake = _FakeNewsService()
    service = mod.NewsIngestionService(
        news_service=fake,
        session=None,
        dual_write_enabled=False,
        sentiment_classifier=_FailingClassifier(),
    )

    stats = await service.ingest(save=True, verbose=False)

    assert stats["saved"] == 2
    assert stats["sentiment_errors"] == 2
    assert stats["errors"] == 0, "the ingest itself succeeded"
    assert {a["sentiment_label"] for a in stats["articles"]} == {"neutral"}
    assert {a["sentiment_score"] for a in stats["articles"]} == {0.0}
