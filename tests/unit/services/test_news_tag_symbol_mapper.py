"""Tests for the Persian news-tag → symbol/fund mapping layer.

Covers the ``news_tag_symbol_map`` join table (migration 0059) and the
``NewsTagSymbolMapper`` service:

* ``normalize_persian``: Arabic ي/ك folding, ZWNJ→space (نیم‌فاصله ≡
  فاصله), digit unification — the cases that broke naive comparisons
* ``_spelling_variants``: reverse-lookup variant set
* ``resolve``: exact / arabic_fallback / miss / persisted reuse /
  manual override (never auto-overridden)
* ``tag_values_for_symbol`` + ``NewsItemsReadRepo.get_by_symbol``:
  an item tagged with a *human* alias is found through the canonical
  symbol (the whole point of the mapping layer)
* ``auto_map_all`` idempotency on the real corpus

DB-backed tests run against real Postgres and are skipped without
``DATABASE_URL``. They only write ``news_tag_symbol_map`` rows tagged
with a unique marker plus their own ``news_items`` fixture rows.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

_MARK = "test_map"


def _engine():
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("DATABASE_URL not set")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        return create_async_engine(url)
    except Exception:
        pytest.skip("DB not reachable")


# ── pure unit: normalization ─────────────────────────────────────────────


class TestNormalizePersian:
    def test_arabic_yeh_kaf_fold(self):
        from services.news_tag_symbol_mapper import normalize_persian

        assert normalize_persian("وبانک") == normalize_persian("وبانك")
        assert normalize_persian("فملی") == normalize_persian("فملي")

    def test_zwnj_equals_space(self):
        from services.news_tag_symbol_mapper import normalize_persian

        # regression: ZWNJ was stripped entirely, making
        # سرمايه‌گذاري ≠ سرمایه گذاری forever
        assert normalize_persian("سرمايه‌گذاري") == normalize_persian("سرمایه گذاری")

    def test_whitespace_and_digits(self):
        from services.news_tag_symbol_mapper import normalize_persian

        assert normalize_persian("  فولاد  ") == "فولاد"
        assert normalize_persian("آسود2") == normalize_persian("اسود۲")

    def test_empty(self):
        from services.news_tag_symbol_mapper import normalize_persian

        assert normalize_persian("") == ""
        assert normalize_persian(None) == ""

    def test_spelling_variants(self):
        from services.news_tag_symbol_mapper import _spelling_variants

        v = _spelling_variants("وبانك")
        assert "وبانك" in v and "وبانک" in v
        assert _spelling_variants(None) == set()


# ── pure unit: a tag with no mapping must be recorded, never guessed ─────


class _StubResult:
    def __init__(self, row=None) -> None:
        self._row = row

    def first(self):
        return self._row

    def scalars(self):
        return self

    def all(self):
        return []


class _RecordingSession:
    """Minimal AsyncSession stand-in: every probe returns "no row"."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement, params=None):  # noqa: ANN001
        self.statements.append(str(statement))
        return _StubResult(None)


class TestUnmappedTagIsRecorded:
    @pytest.mark.asyncio
    async def test_unknown_tag_resolves_to_none_and_is_persisted_as_unmapped(self):
        """A tag matching neither ``funds`` nor ``symbols`` must NOT be attached
        to some other symbol — it resolves to None and the attempt is written
        to ``news_tag_symbol_map`` as ``unmapped`` so the removal reason is
        traceable and the auto-mapper stops retrying."""
        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        session = _RecordingSession()
        mapper = NewsTagSymbolMapper(session)

        assert await mapper.resolve("برچسب_بی‌صاحب", persist=True) is None

        joined = " ".join(session.statements)
        assert "news_tag_symbol_map" in joined
        assert "unmapped" in joined
        # The probe order is funds → symbols; both must have been tried before
        # giving up (a silent early exit would hide real mappings).
        assert "FROM funds" in joined
        assert "FROM symbols" in joined

    @pytest.mark.asyncio
    async def test_miss_without_persist_does_not_write(self):
        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        session = _RecordingSession()
        mapper = NewsTagSymbolMapper(session)

        assert await mapper.resolve("برچسب_بی‌صاحب", persist=False) is None
        # ``_get_persisted`` still SELECTs the map table; what must not happen
        # is an INSERT (no row is written when ``persist=False``).
        assert not any("INSERT INTO news_tag_symbol_map" in s for s in session.statements)


# ── pure unit: ambiguous probes are deterministic, never arbitrary ───────


class _Rows(list):
    """``.all()``/``.first()`` over scripted rows (probe path only)."""

    def all(self):
        return list(self)

    def first(self):
        return self[0] if self else None


class _DuplicateRowSession:
    """Probe session: the ``funds`` lookup returns two same-symbol rows."""

    def __init__(self, rows: list[tuple[str, str]]) -> None:
        self._rows = rows
        self.statements: list[str] = []

    async def execute(self, statement, params=None):  # noqa: ANN001
        sql = str(statement)
        self.statements.append(sql)
        if "FROM funds" in sql:
            return _Rows(self._rows)
        return _Rows([])


class TestAmbiguousProbeIsDeterministic:
    @pytest.mark.asyncio
    async def test_duplicate_rows_resolve_to_the_lowest_id_and_are_logged(self, monkeypatch):
        """Two ``funds`` rows sharing a symbol must not be picked arbitrarily:
        the query orders by ``id`` and the ambiguity is logged."""
        from services import news_tag_symbol_mapper as mod

        warnings: list[str] = []
        monkeypatch.setattr(
            mod.logger,
            "warning",
            lambda msg, *args, **kwargs: warnings.append(msg % args if args else msg),
        )

        session = _DuplicateRowSession([("f_1", "آگاس"), ("f_2", "آگاس")])
        mapper = mod.NewsTagSymbolMapper(session)

        hit = await mapper._probe_tables("آگاس")

        assert hit == ("fund", "f_1", "آگاس")
        joined = " ".join(session.statements)
        assert "ORDER BY id" in joined
        # the ambiguity must be visible in the logs, not silent
        assert warnings and "mbiguous" in warnings[0]

    def test_probe_sql_is_ordered_and_bounded(self):
        from services.news_tag_symbol_mapper import _probe_sql

        for table in ("funds", "symbols"):
            sql = _probe_sql(table)
            assert f"FROM {table}" in sql
            assert "ORDER BY id" in sql
            assert "LIMIT" in sql


# ── DB-backed: resolve + read path ───────────────────────────────────────


class TestMapperOnDb:
    @pytest.mark.asyncio
    async def test_resolve_real_corpus(self):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                mapper = NewsTagSymbolMapper(session)
                # the tagger writes وبانک; the symbols table spells وبانك
                m = await mapper.resolve("وبانک", persist=False)
                assert m is not None
                assert m["resolved_type"] == "symbol"
                assert m["match_type"] == "arabic_fallback"
                assert m["resolved_symbol"] == "وبانك"

                # exact case
                exact = await mapper.resolve("فولاد", persist=False)
                assert exact["match_type"] == "exact"

                # hopeless tag → None, nothing persisted
                assert await mapper.resolve("برچسب_ناکجا", persist=False) is None
        finally:
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_manual_override_survives_auto(self):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                mapper = NewsTagSymbolMapper(session)
                target_id = (
                    await session.execute(
                        text("SELECT id FROM symbols WHERE symbol = 'وبانك' LIMIT 1")
                    )
                ).scalar_one()

                manual = await mapper.set_manual(marker, "symbol", str(target_id))
                assert manual["match_type"] == "manual"

                # resolve must return the manual mapping…
                m = await mapper.resolve(marker, persist=True)
                assert m["match_type"] == "manual"
                assert m["resolved_symbol"] == "وبانك"

                # …and an auto re-map must never override it
                assert await mapper._probe_tables(marker) is None
        finally:
            async with maker() as session:
                await session.execute(
                    text("DELETE FROM news_tag_symbol_map WHERE tag_value = :t"),
                    {"t": marker},
                )
                await session.commit()
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_alias_tag_found_via_canonical_symbol(self):
        """End-to-end: item tagged with a *human* alias is returned by
        ``get_by_symbol`` on the canonical (Arabic-spelled) symbol."""
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from repositories.news_items_read_repo import NewsItemsReadRepo
        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        marker = f"{_MARK}_{uuid.uuid4().hex[:8]}"
        alias = f"علیاس_{marker}"
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                # seed one news_items row tagged with the alias
                res = await session.execute(
                    text(
                        "INSERT INTO news_items (title, body, source, source_url, published_at, category, dedup_hash) "
                        "VALUES (:t, :b, :s, :u, now(), 'market', :h) RETURNING id"
                    ),
                    {"t": f"{marker} title", "b": f"{marker} body", "s": f"{marker}src",
                         "u": f"https://x.test/{marker}", "h": f"hash_{marker}"},
                )
                item_id = res.scalar_one()
                await session.execute(
                    text("INSERT INTO news_tags (news_id, tag_type, tag_value, confidence) "
                         "VALUES (:n, 'stock_symbol', :v, 1.0)"),
                    {"n": item_id, "v": alias},
                )
                # persist manual alias → canonical وبانك
                target_id = (
                    await session.execute(
                        text("SELECT id FROM symbols WHERE symbol = 'وبانك' LIMIT 1")
                    )
                ).scalar_one()
                await NewsTagSymbolMapper(session).set_manual(alias, "symbol", str(target_id))
                await session.commit()

                repo = NewsItemsReadRepo(session)
                found = await repo.get_by_symbol("وبانك", page=1, page_size=50)
                assert found.success
                ids = [i.id for i in found.value.items]
                assert f"ni_{item_id}" in ids  # alias resolved through the map

                # Persian spelling must also find the alias item
                # (subset: persisted aliases may legitimately widen the
                # canonical-spelling result)
                fa = await repo.get_by_symbol("وبانک", page=1, page_size=50)
                assert f"ni_{item_id}" in {i.id for i in fa.value.items}
        finally:
            async with maker() as session:
                await session.execute(
                    text("DELETE FROM news_tag_symbol_map WHERE tag_value = :t"),
                    {"t": alias},
                )
                await session.execute(
                    text("DELETE FROM news_tags WHERE news_id = :n"), {"n": item_id}
                )
                await session.execute(
                    text("DELETE FROM news_items WHERE id = :n"), {"n": item_id}
                )
                await session.commit()
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_auto_map_all_idempotent(self):
        eng = _engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from services.news_tag_symbol_mapper import NewsTagSymbolMapper

        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as session:
                mapper = NewsTagSymbolMapper(session)
                first = await mapper.auto_map_all()
                second = await mapper.auto_map_all()
                assert first["mapped"] == second["mapped"]
                assert second["unmapped"] == 0
        finally:
            await eng.dispose()
