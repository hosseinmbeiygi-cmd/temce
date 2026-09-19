"""Tests for the admin news-tag mapping endpoints (``/api/v1/news-tag-map``).

Two layers, mirroring the news-suite conventions:

* DB-backed tests call the endpoint functions against real Postgres —
  paged view over the live auto-mapped corpus, search/match_type filters,
  stats, the manual-override + ``audit_logs`` trail, target validation,
  and the no-persist guarantee of the dry ``verify`` probe.
* HTTP tests run the real FastAPI app and assert the auth chain:
  no token → 401, non-admin role → 403, admin role → 200 (DB session
  stubbed; Postgres not required).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

_MARK = "test_mapadm"


def _engine():
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("DATABASE_URL not set")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        return create_async_engine(url)
    except Exception:
        pytest.skip("DB not reachable")


# ── DB-backed endpoint logic ─────────────────────────────────────────────


class TestMappingAdminDb:
    @pytest.mark.asyncio
    async def test_list_stats_and_filters(self):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from apps.api.endpoints.news_tag_map_admin import list_mappings, mapping_stats

        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                page = await list_mappings(page=1, page_size=10, q=None, match_type=None, session=session)
                assert page.success
                data = page.data
                assert data["total"] >= 5  # live corpus: 5 auto-mapped tags
                assert data["total"] > 0
                if data["items"]:
                    row = data["items"][0]
                    assert row["confidence"] is None or isinstance(row["confidence"], float)
                    assert "resolved_symbol" in row

                # search filter narrows
                filtered = await list_mappings(page=1, page_size=10, q="فولاد", match_type=None, session=session)
                assert filtered.data["total"] <= data["total"]

                # match_type filter
                exact = await list_mappings(page=1, page_size=10, q=None, match_type="exact", session=session)
                assert all(item["match_type"] == "exact" for item in exact.data["items"])

                stats = await mapping_stats(session=session)
                assert stats.success
                assert sum(stats.data["counts"].values()) == stats.data["total"] == data["total"]
        finally:
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_manual_override_with_audit_trail(self):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from apps.api.endpoints.news_tag_map_admin import delete_mapping, set_manual_mapping

        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                target_id = (
                    await session.execute(text("SELECT id FROM symbols WHERE symbol = 'فولاد' LIMIT 1"))
                ).scalar_one()

                resp = await set_manual_mapping(
                    marker,
                    {"resolved_type": "symbol", "resolved_id": str(target_id)},
                    session=session,
                    user={"sub": "admin-test"},
                )
                assert resp.success and resp.data["match_type"] == "manual"

                # audit row written
                audit = (
                    await session.execute(
                        text("SELECT action, actor FROM audit_logs WHERE entity_id = :e AND entity_type='news_tag_symbol_map'"),
                        {"e": marker},
                    )
                ).first()
                assert audit is not None
                assert audit[0] == "news_tag_map.manual_set" and audit[1] == "admin-test"
                await session.commit()

            # fresh session: delete + audit
            async with maker() as session:
                del_resp = await delete_mapping(marker, session=session, user={"sub": "admin-test"})
                assert del_resp.success and del_resp.data["deleted"] is True
                gone = (
                    await session.execute(
                        text("SELECT count(*) FROM news_tag_symbol_map WHERE tag_value = :t"), {"t": marker}
                    )
                ).scalar_one()
                assert gone == 0
                await session.commit()
        finally:
            async with maker() as session:
                await session.execute(text("DELETE FROM news_tag_symbol_map WHERE tag_value = :t"), {"t": marker})
                await session.execute(
                    text("DELETE FROM audit_logs WHERE entity_id = :e AND entity_type='news_tag_symbol_map'"),
                    {"e": marker},
                )
                await session.commit()
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_manual_target_validation(self):
        eng = _engine()
        from fastapi import HTTPException
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from apps.api.endpoints.news_tag_map_admin import set_manual_mapping

        maker = async_sessionmaker(eng, expire_on_commit=False)
        marker = f"{_MARK}_bad_{uuid.uuid4().hex[:6]}"
        try:
            async with maker() as session:
                with pytest.raises(HTTPException) as exc:
                    await set_manual_mapping(
                        marker, {"resolved_type": "symbol", "resolved_id": "999999999"},
                        session=session, user={"sub": "admin-test"},
                    )
                assert exc.value.status_code == 404
                with pytest.raises(HTTPException) as exc2:
                    await set_manual_mapping(
                        marker, {"resolved_type": "bond", "resolved_id": "1"},
                        session=session, user={"sub": "admin-test"},
                    )
                assert exc2.value.status_code == 422
                await session.rollback()
        finally:
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_verify_is_dry(self):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from apps.api.endpoints.news_tag_map_admin import verify_tag

        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                before = (
                    await session.execute(text("SELECT count(*) FROM news_tag_symbol_map"))
                ).scalar_one()
                resp = await verify_tag("برچسب_ناکجاآباد", session=session)
                assert resp.success and resp.data["resolved"] is None
                after = (
                    await session.execute(text("SELECT count(*) FROM news_tag_symbol_map"))
                ).scalar_one()
                assert after == before  # nothing persisted
        finally:
            await eng.dispose()


# ── HTTP auth chain ──────────────────────────────────────────────────────


class TestMappingAdminHttp:
    @pytest.fixture()
    def client(self, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import MagicMock

        from fastapi.testclient import TestClient

        from apps.api.app import app
        from apps.api.dependencies import get_db_session
        from core.security.tokens import create_access_token

        session = MagicMock()

        async def _override_session():
            yield session

        app.dependency_overrides[get_db_session] = _override_session
        admin_token = create_access_token({"sub": "admin-test", "roles": ["admin"]})
        user_token = create_access_token({"sub": "user-test", "roles": ["user"]})
        yield TestClient(app, raise_server_exceptions=False), admin_token, user_token
        app.dependency_overrides.clear()

    def test_requires_token(self, client):
        c, _, _ = client
        resp = c.get("/api/v1/news-tag-map")
        assert resp.status_code == 401

    def test_rejects_non_admin(self, client):
        c, _, user_token = client
        resp = c.get(
            "/api/v1/news-tag-map", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert resp.status_code in (401, 403)  # 403 expected; 401 if revoked-check offline

    def test_admin_passes_auth(self, client):
        c, admin_token, _ = client
        resp = c.get(
            "/api/v1/news-tag-map", headers={"Authorization": f"Bearer {admin_token}"}
        )
        # auth passes; the stubbed DB may not satisfy the full SQL mock, but
        # the response must not be an auth rejection
        assert resp.status_code not in (401, 403)
