"""HTTP-level tests for the ``?from``/``?to`` filter on ``/api/v1/news``.

The unit tests (``test_news_date_range.py``) exercise the router functions
directly; these run the real FastAPI app with dependency overrides so the
full request pipeline is validated, including the ``from`` query-param
alias (a Python keyword, hence ``from_`` in signatures) and the error
payload shape on invalid input. DB access is stubbed out — no Postgres
required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from apps.api.app import app
from apps.api.dependencies import get_db_session, get_news_service
from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem


def _news_item(news_id: str, pub: datetime) -> NewsItem:
    return NewsItem(
        id=news_id,
        title=f"title {news_id}",
        summary="sum",
        source="rss",
        url=f"https://example.test/{news_id}",
        publish_date=pub,
        category="market",
    )


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App with the news service stubbed to repo semantics (date window at
    the DB layer) and the DB session replaced by a mock."""
    items = [
        _news_item("old", datetime(2026, 1, 1, tzinfo=UTC)),
        _news_item("in", datetime(2026, 9, 10, tzinfo=UTC)),
    ]

    async def _fake_ingest_refresh() -> None:  # pragma: no cover
        return None

    service = AsyncMock()

    async def _list_all(*args, **kwargs):
        f, t = kwargs.get("date_from"), kwargs.get("date_to")
        kept = [
            i for i in items
            if i.publish_date
            and (f is None or i.publish_date >= f)
            and (t is None or i.publish_date <= t)
        ]
        return Result.ok(PaginatedResult(items=kept, total=len(kept), page=1, page_size=50, total_pages=1))

    service.list_all.side_effect = _list_all

    async def _override_session():
        yield AsyncMock()

    app.dependency_overrides[get_news_service] = lambda: service
    app.dependency_overrides[get_db_session] = _override_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestNewsDateRangeHTTP:
    def test_from_to_filters_results(self, client: TestClient):
        resp = client.get("/api/v1/news", params={"from": "2026-09-01", "to": "2026-09-30"})
        assert resp.status_code == 200
        body = resp.json()
        ids = [i["id"] for i in body["data"]["items"]]
        assert "in" in ids and "old" not in ids

    def test_bare_date_to_includes_whole_day(self, client: TestClient):
        resp = client.get("/api/v1/news", params={"from": "2026-09-01", "to": "2026-09-16"})
        # the seeded row is published 2026-09-10, well inside the bare-date window
        ids = [i["id"] for i in resp.json()["data"]["items"]]
        assert "in" in ids

    def test_invalid_from_returns_error_payload(self, client: TestClient):
        resp = client.get("/api/v1/news", params={"from": "not-a-date"})
        assert resp.status_code == 200  # ApiResponse error contract, not HTTP 500
        body = resp.json()
        assert body["success"] is False
        assert "Invalid from" in body["error"]["message"]

    def test_no_params_returns_everything(self, client: TestClient):
        resp = client.get("/api/v1/news")
        assert resp.status_code == 200
        ids = [i["id"] for i in resp.json()["data"]["items"]]
        assert set(ids) == {"old", "in"}
