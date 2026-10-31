"""Live mirror must link each ``news_items`` row to its legacy article.

``news_items.legacy_article_id`` is a UNIQUE column created for exactly this
link, and the one-shot backfill already fills it — but the live dual-writer
never did, so new mirror rows could only be matched to legacy by fuzzy
title+URL. The parity audit (``services.news_parity.py``) joins on the id
first; without this link every new row falls back to the fuzzy path.

Offline: a recording fake session replays the query shapes.
"""

from __future__ import annotations

from typing import Any

from services.news_dual_write import NewsDualWriter


class _Result:
    def __init__(self, *, one: Any = None, scalar: Any = None) -> None:
        self._one = one
        self._scalar = scalar

    def scalar_one_or_none(self) -> Any:
        return self._one

    def scalar_one(self) -> Any:
        return self._scalar


class _Session:
    def __init__(self, existing_id: Any = None, new_id: int = 42) -> None:
        self.existing_id = existing_id
        self.new_id = new_id
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        sql = " ".join(str(statement).split())
        self.calls.append((sql, params or {}))
        if sql.startswith("SELECT id FROM news_items"):
            return _Result(one=self.existing_id)
        if "INSERT INTO news_items" in sql:
            return _Result(scalar=self.new_id)
        return _Result()

    @property
    def item_inserts(self) -> list[dict[str, Any]]:
        return [p for sql, p in self.calls if "INSERT INTO news_items" in sql]


async def _mirror(session: _Session, legacy_id: str | None) -> int | None:
    return await NewsDualWriter(session=session).mirror(
        session,  # type: ignore[arg-type]
        title="عنوان آزمون",
        body="body",
        source="mehr",
        url="https://example.invalid/a",
        published_at=None,
        category="بازار",
        is_breaking=False,
        symbols=["فولاد"],
        dedup_hash="hash-1",
        legacy_article_id=legacy_id,
    )


async def test_mirror_writes_the_legacy_link() -> None:
    session = _Session()

    news_id = await _mirror(session, "news_abc123")

    assert news_id == 42
    (params,) = session.item_inserts
    assert params["legacy_id"] == "news_abc123"
    insert_sql = next(sql for sql, _p in session.calls if "INSERT INTO news_items" in sql)
    assert "legacy_article_id" in insert_sql


async def test_dedup_check_also_matches_the_legacy_link() -> None:
    session = _Session()

    await _mirror(session, "news_abc123")

    select_sql, select_params = session.calls[0]
    assert "legacy_article_id" in select_sql
    assert select_params["legacy_id"] == "news_abc123"


async def test_already_linked_row_is_not_mirrored_twice() -> None:
    session = _Session(existing_id=7)

    result = await _mirror(session, "news_abc123")

    assert result is None
    assert session.item_inserts == []


async def test_missing_legacy_id_is_allowed() -> None:
    """Backfill/repair callers may mirror without a legacy row; the link is NULL."""
    session = _Session()

    await _mirror(session, None)

    (params,) = session.item_inserts
    assert params["legacy_id"] is None
