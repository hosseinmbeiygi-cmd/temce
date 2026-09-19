"""HTTP-level tests for the ``SymbolMatchMeta`` on ``/api/v1/news/symbol/{symbol}``.

The mapping-layer unit tests (``test_news_tag_symbol_mapper.py``) exercise
the service on real Postgres; these run the real FastAPI app with the news
service stubbed so the full request pipeline is validated:

* ``message`` carries the ``SymbolMatchMeta`` JSON when items matched
* ``message`` stays ``null`` on an empty result (no noise for clients)
* meta is best-effort: an exploding mapper must not break the endpoint
DB access is stubbed out — no Postgres required.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.api.app import app
from apps.api.dependencies import get_db_session, get_news_service
from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem


def _news_item(news_id: str) -> NewsItem:
    return NewsItem(
        id=news_id,
        title=f"title {news_id}",
        summary="sum",
        source="rss",
        url=f"https://example.test/{news_id}",
        publish_date=datetime(2026, 9, 10, tzinfo=UTC),
        category="market",
        symbols=["وبانک"],
    )


def _db_session() -> AsyncMock:
    """Async session whose ``execute`` resolves to a result object with
    ``.mappings().all()`` — the shape ``explain_symbol`` consumes."""
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = [
        {
            "tag_value": "وبانک",
            "resolved_symbol": "وبانك",
            "match_type": "arabic_fallback",
            "confidence": 0.8,
        }
    ]
    session.execute.return_value = result
    return session


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App with the news service stubbed to return one وبانک-tagged item
    for any symbol lookup, and the DB session replaced by a mock."""
    items = [_news_item("ni_1"), _news_item("ni_2")]

    service = AsyncMock()

    async def _by_symbol(*args, **kwargs):
        return Result.ok(PaginatedResult(items=list(items), total=len(items), page=1, page_size=50, total_pages=1))

    service.get_by_symbol.side_effect = _by_symbol

    async def _override_session():
        yield _db_session()

    app.dependency_overrides[get_news_service] = lambda: service
    app.dependency_overrides[get_db_session] = _override_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestSymbolMatchMetaHTTP:
    def test_message_carries_match_meta(self, client: TestClient):
        resp = client.get("/api/v1/news/symbol/وبانك")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 2

        # every returned item is tagged وبانک — meta must say so
        assert body["message"] is not None
        meta = json.loads(body["message"])
        assert meta["symbol"] == "وبانك"
        assert "وبانک" in meta["matched"]
        assert meta["maps"][0]["match_type"] == "arabic_fallback"
        assert meta["maps"][0]["confidence"] == 0.8

    def test_empty_result_has_no_meta(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        # empty result branch: no items → no matched → no meta
        service = AsyncMock()

        async def _empty(*args, **kwargs):
            return Result.ok(PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1))

        service.get_by_symbol.side_effect = _empty

        async def _override_session():
            yield AsyncMock()

        app.dependency_overrides[get_news_service] = lambda: service
        app.dependency_overrides[get_db_session] = _override_session
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/api/v1/news/symbol/وبانك")
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 0
        assert body["message"] is None

    def test_meta_failure_never_breaks_endpoint(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        """The mapper is best-effort: even if ``explain_symbol`` raises, the
        endpoint must return the items with ``message: null``."""
        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        async def _boom(self, symbol):  # noqa: ANN001
            raise RuntimeError("mapping table gone")

        monkeypatch.setattr(NewsTagSymbolMapper, "explain_symbol", _boom)
        resp = client.get("/api/v1/news/symbol/وبانك")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 2
        assert body["message"] is None
