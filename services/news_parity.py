"""Read-only parity audit: legacy ``news_articles`` vs mirrored ``news_items``.

Dual-write keeps both schemas fed, and the shadow read-path canary compares
*served pages* while traffic flows. Neither answers the ops question “are the
two tables actually in sync right now?” — the audit (stage 9) left that as a
DB-only check with no tool. This module is that tool: SQL only, ``SELECT``
only, no mutation.

Identity: a mirror row is matched to its legacy row by ``legacy_article_id``
(written by the dual-writer since this stage). Rows mirrored before that link
existed fall back to ``source_url`` + case-folded title, which is also the key
``news_read_canary.compare_page`` uses.

A nonzero ``legacy_missing_mirror`` means the new schema is missing articles;
a nonzero ``mirror_missing_legacy`` means it holds rows the legacy table never
saw (or that were deleted there). ``parity_ok`` is true only when both are 0.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)

_COUNTS_SQL = """
WITH w AS (SELECT now() - make_interval(days => :days) AS cutoff)
SELECT
    (SELECT count(*) FROM news_articles) AS legacy_total,
    (SELECT count(*) FROM news_items) AS mirror_total,
    (SELECT count(*) FROM news_articles a, w
      WHERE COALESCE(a.published_at_ts, a.created_at) >= w.cutoff) AS legacy_recent,
    (SELECT count(*) FROM news_items m, w
      WHERE m.published_at >= w.cutoff) AS mirror_recent,
    (SELECT count(*) FROM news_articles a, w
      WHERE COALESCE(a.published_at_ts, a.created_at) >= w.cutoff
        AND NOT EXISTS (
            SELECT 1 FROM news_items m
            WHERE m.legacy_article_id = a.id
               OR (m.legacy_article_id IS NULL
                   AND m.source_url IS NOT DISTINCT FROM a.url
                   AND lower(btrim(m.title)) = lower(btrim(a.title)))
        )) AS legacy_missing_mirror,
    (SELECT count(*) FROM news_items m, w
      WHERE m.published_at >= w.cutoff
        AND NOT EXISTS (
            SELECT 1 FROM news_articles a
            WHERE a.id = m.legacy_article_id
               OR (m.legacy_article_id IS NULL
                   AND m.source_url IS NOT DISTINCT FROM a.url
                   AND lower(btrim(m.title)) = lower(btrim(a.title)))
        )) AS mirror_missing_legacy,
    (SELECT count(*) FROM news_items
      WHERE legacy_article_id IS NOT NULL) AS linked_rows,
    (SELECT count(*) FROM news_items m
      JOIN news_articles a ON a.id = m.legacy_article_id
      WHERE m.published_at IS NULL OR a.published_at_ts IS NULL) AS linked_missing_time
"""

_SAMPLES_SQL = """
WITH w AS (SELECT now() - make_interval(days => :days) AS cutoff)
SELECT a.id, a.title, a.url
FROM news_articles a, w
WHERE COALESCE(a.published_at_ts, a.created_at) >= w.cutoff
  AND NOT EXISTS (
      SELECT 1 FROM news_items m
      WHERE m.legacy_article_id = a.id
         OR (m.legacy_article_id IS NULL
             AND m.source_url IS NOT DISTINCT FROM a.url
             AND lower(btrim(m.title)) = lower(btrim(a.title)))
  )
ORDER BY COALESCE(a.published_at_ts, a.created_at) DESC
LIMIT :limit
"""


async def news_parity_report(
    session: AsyncSession,
    *,
    days: int = 7,
    sample_limit: int = 10,
) -> dict[str, Any]:
    """Compare the two news schemas over the last *days* (read-only).

    Returns counts plus ``parity_ok``; ``sample_missing`` lists up to
    *sample_limit* legacy rows the mirror lacks (titles only — enough to
    diagnose without dumping content).
    """
    days = max(1, min(int(days), 90))
    row = (
        await session.execute(text(_COUNTS_SQL), {"days": days})
    ).mappings().one()
    counts = {key: int(row[key] or 0) for key in row}

    samples: list[dict[str, Any]] = []
    if counts.get("legacy_missing_mirror", 0) and sample_limit > 0:
        rows = (
            await session.execute(
                text(_SAMPLES_SQL),
                {"days": days, "limit": max(1, min(int(sample_limit), 50))},
            )
        ).mappings().all()
        samples = [
            {"id": r["id"], "title": (r["title"] or "")[:120], "url": r["url"]}
            for r in rows
        ]

    report = {
        **counts,
        "window_days": days,
        "checked_at": datetime.now(UTC).isoformat(),
        "parity_ok": counts.get("legacy_missing_mirror", 0) == 0
        and counts.get("mirror_missing_legacy", 0) == 0,
        "sample_missing": samples,
    }
    if not report["parity_ok"]:
        logger.warning(
            "news parity: %d legacy row(s) missing from news_items, %d mirror row(s) "
            "missing from news_articles over %d day(s)",
            counts.get("legacy_missing_mirror", 0),
            counts.get("mirror_missing_legacy", 0),
            days,
        )
    return report


__all__ = ["news_parity_report"]
