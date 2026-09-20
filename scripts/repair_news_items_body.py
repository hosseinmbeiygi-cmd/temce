"""Idempotent repair of ``news_items.body`` — full legacy content mirror.

Root cause of canary search parity divergence: the original backfill
copied ``news_articles.summary`` (VARCHAR 500) into ``news_items.body``,
while the legacy search path matches the full ``content`` column. Any
keyword past char 500 therefore went missing on the news_items read
path. Dual-write already writes the full text; only backfilled rows
need repair. Re-running is a no-op (matched rows have equal length).

Also deletes leftover test rows (``test_canary_*`` legacy articles that
shadow-routing tests insert without cleanup) so the one-hour parity
window is not polluted by three phantom rows.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg

# Legacy may hold DUPLICATE titles (re-ingested articles). The legacy
# read path's DISTINCT ON (title) picks the NEWEST row per title, so the
# mirror must carry that row's timestamp/content — not an arbitrary
# duplicate's. The subqueries below reproduce DISTINCT ON semantics
# (newest per title among source-filtered rows).
UPDATE_BODY_SQL = """
UPDATE news_items n
SET body = d.content
FROM (
    SELECT DISTINCT ON (title) title, content
    FROM news_articles
    WHERE source IS NOT NULL AND source <> ''
    ORDER BY title, COALESCE(published_at_ts, created_at) DESC NULLS LAST
) d
WHERE n.title = d.title
  AND d.content IS NOT NULL
  AND length(d.content) > length(COALESCE(n.body, ''))
"""

# Backfill copies published_at from the article; rows mirrored by the
# live dual-write got their published_at from the parsed RSS datetime.
# Where the two disagree (RSS said 09:30, article row was created 09:31
# with a backfilled ts from created_at), same-title joins still match
# but the two schemas ORDER differently. Re-stamp news_items rows from
# the newest legacy row per title (what DISTINCT ON serves).
RESTAMP_PUBLISHED_SQL = """
UPDATE news_items n
SET published_at = d.eff_ts
FROM (
    SELECT title, max(COALESCE(published_at_ts, created_at)) AS eff_ts
    FROM news_articles
    WHERE source IS NOT NULL AND source <> ''
    GROUP BY title
) d
WHERE n.title = d.title
  AND d.eff_ts IS NOT NULL
  AND n.published_at IS DISTINCT FROM d.eff_ts
"""

DELETE_TEST_ROWS_SQL = """
DELETE FROM news_tags t
USING news_articles a
WHERE t.news_id IN (SELECT id FROM news_items WHERE legacy_article_id = a.id)
  AND a.id LIKE 'news_test_canary_%'
"""

DELETE_TEST_ITEMS_SQL = """
DELETE FROM news_items
WHERE legacy_article_id IN (
    SELECT id FROM news_articles WHERE id LIKE 'news_test_canary_%'
)
"""

DELETE_TEST_ARTICLES_SQL = """
DELETE FROM news_articles WHERE id LIKE 'news_test_canary_%'
"""


async def main() -> int:
    from core.config import settings

    url: str = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(url)
    try:
        n_test = await conn.fetchval(DELETE_TEST_ITEMS_SQL)
        await conn.execute(DELETE_TEST_ARTICLES_SQL)
        print(f"deleted test-canary leftovers: {n_test or 0}")

        stamped = await conn.execute(RESTAMP_PUBLISHED_SQL)
        try:
            n_stamped = int(stamped.rsplit(" ", 1)[-1])
        except (ValueError, AttributeError):
            n_stamped = 0
        print(f"published_at re-stamped from legacy ts: {n_stamped} rows")

        total = 0
        while True:
            async with conn.transaction():
                cur = await conn.execute(UPDATE_BODY_SQL)
                fixed = int(cur.rsplit(" ", 1)[-1]) if cur and cur.rsplit(" ", 1)[-1].isdigit() else 0
            total += fixed
            if fixed == 0:
                break
        print(f"body repaired to full content: {total} rows")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
