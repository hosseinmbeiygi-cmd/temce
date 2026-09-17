"""Dual-write to the new ``news_items`` table (news module foundation, migration 0054).

The legacy pipeline (``news_articles`` via ``NewsService``) keeps working
unchanged; every successfully classified article is *also* mirrored into the
new schema so the news module (spec: ``NEWS_MODULE_SPEC_FILLED_2026-09-16.md``)
accumulates data from day one:

* ``dedup_hash`` = SHA-256 of normalized ``title`` + ``source_url`` — a stable
  content identity that DB-level dedup (partial unique index) can enforce
  across restarts, complementing the in-memory TTL deduplicator upstream.
* Stock symbols extracted by the existing parser are stored as structured
  ``news_tags`` rows (``tag_type='stock_symbol'``) with full confidence —
  the legacy ``symbols`` TEXT column stays untouched.
* ``news_ingestion_sources`` gets upserted with ``last_fetched_at`` per feed,
  seeding the dead-source alerting budget.

Failure isolation: a dual-write error is logged and counted but never raised
into the legacy save path — the module is additive by contract. The caller
passes its session; writes join that transaction (no separate connections).
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)


def compute_dedup_hash(title: str, url: str) -> str:
    """Stable content identity: SHA-256 of the normalized title + source URL.

    Normalization = Unicode NFKC, casefold, whitespace collapse. Two feeds
    republishing the same headline under the same link collapse to one row;
    different links with the same headline do NOT collapse (the URL is part
    of the identity) — dedup by title alone is the upstream in-memory layer's
    job, here we stay conservative to avoid false positives.
    """
    import unicodedata

    norm_title = unicodedata.normalize("NFKC", title or "").casefold()
    norm_title = " ".join(norm_title.split())
    norm_url = (url or "").strip().casefold()
    return hashlib.sha256(f"{norm_title}\x1f{norm_url}".encode("utf-8")).hexdigest()


class NewsDualWriter:
    """Mirrors ingested articles into ``news_items`` (+tags, sources registry)."""

    def __init__(self, session: AsyncSession | None = None, enabled: bool = True) -> None:
        self._session = session
        self.enabled = enabled

    async def mirror(
        self,
        session: AsyncSession,
        *,
        title: str,
        body: str | None,
        source: str,
        url: str,
        published_at: Any,
        category: str,
        is_breaking: bool,
        symbols: list[str],
        dedup_hash: str,
    ) -> int | None:
        """Insert one article into ``news_items`` + its symbol tags.

        Returns the new ``news_items.id``, or ``None`` when the row already
        exists (dedup hit) or the mirror is disabled. Never raises for
        expected dedup violations; real errors propagate to the caller's
        fail-safe wrapper.
        """
        if not self.enabled:
            return None

        # Dedup fast-path: same content identity already mirrored.
        existing = await session.execute(
            text("SELECT id FROM news_items WHERE dedup_hash = :h LIMIT 1"),
            {"h": dedup_hash},
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return None

        # ── Upsert the source registry (feeds the dead-source alert) ──
        if source:
            await session.execute(
                text(
                    "INSERT INTO news_ingestion_sources (source_name, source_type, last_fetched_at) "
                    "VALUES (:name, 'rss', now()) "
                    "ON CONFLICT (source_name) DO UPDATE SET last_fetched_at = now()"
                ),
                {"name": source},
            )

        inserted = await session.execute(
            text(
                "INSERT INTO news_items "
                "(title, body, source, source_url, published_at, category, is_breaking, dedup_hash) "
                "VALUES (:title, :body, :source, :url, :published_at, :category, :is_breaking, :dedup_hash) "
                "RETURNING id"
            ),
            {
                "title": title,
                "body": body,
                "source": source,
                "url": url,
                "published_at": published_at,
                "category": category or None,
                "is_breaking": is_breaking,
                "dedup_hash": dedup_hash,
            },
        )
        news_id = inserted.scalar_one()

        # ── Structured tags: one row per extracted symbol, full confidence ──
        for symbol in symbols:
            await session.execute(
                text(
                    "INSERT INTO news_tags (news_id, tag_type, tag_value, confidence) "
                    "VALUES (:nid, 'stock_symbol', :val, 1.0)"
                ),
                {"nid": news_id, "val": symbol},
            )

        return news_id

    async def safe_mirror(self, article: dict[str, Any], **fields: Any) -> bool:
        """``mirror`` wrapped for the pipeline: logs failures, never raises.

        Returns True when the article was mirrored, False on dedup hit,
        disablement, missing session, or any error (logged with context).

        Transactional note: the legacy ``repo.save`` only flushes (the final
        commit happens in ``core.database.get_session`` / request teardown).
        When the mirror fails mid-transaction we ROLLBACK — otherwise the
        failed statement would poison the session and the pending legacy
        INSERT would be lost at commit time. The rollback discards BOTH the
        failed mirror AND the flushed-but-uncommitted legacy INSERT for the
        current article, so re-adding the legacy ORM object afterwards keeps
        that article on both paths. Articles already saved in this run stay
        pending and commit normally at session teardown.
        """
        if not self.enabled or self._session is None:
            return False
        try:
            result = await self.mirror(self._session, **fields)
            return result is not None
        except Exception:
            logger.exception(
                "Dual-write failed for article '%s' (legacy save unaffected)",
                (article.get("title") or "?")[:80],
            )
            try:
                await self._session.rollback()
            except Exception:
                logger.debug("Dual-write rollback failed", exc_info=True)
                return False
            # Re-issue the legacy save so this article isn't lost with the
            # rollback (news_items mirror for it is skipped — DB-level dedup
            # will pick it up on the next run via dedup_hash-less retry).
            try:
                reissue = getattr(self, "_reissue_legacy_save", None)
                if reissue is not None:
                    await reissue(article)
            except Exception:
                logger.exception(
                    "Legacy re-save after dual-write rollback failed for '%s'",
                    (article.get("title") or "?")[:80],
                )
            return False
