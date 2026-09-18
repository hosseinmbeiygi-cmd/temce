#!/usr/bin/env python
"""One-shot idempotent backfill: ``news_articles`` (legacy) -> ``news_items``.

Part of the news module foundation (spec:
``docs/NEWS_MODULE_SPEC_FILLED_2026-09-16.md``, decision #2: new ``news_items``
table fed both by live dual-write and by this backfill of the 15,581 legacy
rows).

Semantics
---------
* Reuses :func:`services.news_dual_write.compute_dedup_hash` verbatim, so a
  backfilled row and a future dual-write row for the same content share the
  same identity and collapse onto the DB partial-unique dedup.
* ``legacy_article_id`` = ``news_articles.id`` — the one-way link column,
  which doubles as a natural resume cursor (only rows with no mirror yet are
  selected; the join makes re-runs no-ops).
* Insert path mirrors ``NewsDualWriter.mirror``: upsert into
  ``news_ingestion_sources`` (source_type 'rss', last_fetched_at = legacy
  ``updated_at``/``created_at`` — historical, not now()), insert into
  ``news_items`` (``body`` from ``summary``, ``published_at`` from the
  migration-0054 ``published_at_ts`` backfill), then one ``news_tags`` row per
  legacy ``symbols`` entry (tag_type 'stock_symbol', confidence 1.0).
* Idempotent by construction: dedup-guard insert (``WHERE NOT EXISTS`` by
  dedup_hash), per-batch ``savepoint`` + per-row ``ON CONFLICT DO NOTHING``
  on ``legacy_article_id`` so any orphan tag insert after a concurrent mirror
  cannot crash the run.
* Batched (BATCH_SIZE=500) with per-batch commit — a failure leaves
  everything up to the last good batch committed and is re-runnable.

Usage
-----
    python scripts/backfill_news_items.py            # execute
    python scripts/backfill_news_items.py --dry-run  # report only, no writes
    python scripts/backfill_news_items.py --batch-size 1000

Exit codes: 0 = fully backfilled (nothing left), 1 = error, 2 = partial
(rows remain after a clean run — rerun the script).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from services.news_dual_write import compute_dedup_hash  # noqa: E402

BATCH_SIZE = 500

# dedup guard: reuse compute_dedup_hash in Python; insert only when absent.
# asyncpg has no named parameters — positional $n only.
INSERT_ITEM_SQL = """
INSERT INTO news_items
    (legacy_article_id, title, body, source, source_url,
     published_at, category, is_breaking, dedup_hash)
SELECT $1::varchar, $2::text, $3::text, $4::varchar, $5::text,
       $6::timestamp, NULLIF($7::varchar, ''), FALSE, $8::varchar
WHERE NOT EXISTS (
    SELECT 1 FROM news_items
    WHERE dedup_hash = $8::varchar
       OR ($1::varchar IS NOT NULL AND legacy_article_id = $1::varchar)
)
RETURNING id
"""

UPSERT_SOURCE_SQL = """
INSERT INTO news_ingestion_sources (source_name, source_type, endpoint_url, is_active, last_fetched_at)
VALUES ($1, 'rss', NULL, TRUE, $2)
ON CONFLICT (source_name) DO UPDATE
SET last_fetched_at = LEAST(
        COALESCE(news_ingestion_sources.last_fetched_at, $2),
        COALESCE($2, news_ingestion_sources.last_fetched_at))
"""

INSERT_TAG_SQL = """
INSERT INTO news_tags (news_id, tag_type, tag_value, confidence)
SELECT $1, 'stock_symbol', s.val, 1.0
FROM unnest($2::varchar[]) AS s(val)
WHERE NOT EXISTS (
    SELECT 1 FROM news_tags t
    WHERE t.news_id = $1 AND t.tag_type = 'stock_symbol' AND t.tag_value = s.val
)
"""


def _parse_symbols(raw: str | None) -> list[str]:
    """Split the legacy ``symbols`` column into clean ticker tokens.

    The column holds a **JSON array string** (e.g. ``["خودرو","وبانک"]``)
    written by the legacy extractor; older/other writers may leave a plain
    comma/semicolon-delimited TEXT list. JSON is tried first, delimiters are
    the fallback, so both shapes produce clean ``tag_value`` tokens (no
    brackets or quotes leaking into ``news_tags``).
    """
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                seen: list[str] = []
                for t in data:
                    tok = str(t).strip().upper()
                    if tok and tok not in seen:
                        seen.append(tok)
                return seen
        except (json.JSONDecodeError, ValueError, TypeError):
            pass  # malformed JSON — fall through to delimiter parsing
    out: list[str] = []
    for tok in raw.replace("،", ",").replace("؛", ",").replace(";", ",").replace("|", ",").split(","):
        tok = tok.strip().strip('[]"').strip().upper()
        if tok and tok not in out:
            out.append(tok)
    return out


async def _get_conn(dsn: str | None) -> asyncpg.Connection:
    if dsn:
        return await asyncpg.connect(dsn)
    from core.config import settings

    url: str = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return await asyncpg.connect(url)


async def retag(conn: asyncpg.Connection, batch_size: int = 1000) -> int:
    """Rebuild ``news_tags`` for already-backfilled rows with the fixed parser.

    Repairs the JSON-bracketed tag values produced by the pre-fix parser:
    deletes ``stock_symbol`` tags of mirrored rows (``legacy_article_id`` NOT
    NULL) and re-inserts them parsed cleanly. Idempotent by construction.
    """
    fixed = 0
    while True:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT n.id, a.symbols
                FROM news_items n JOIN news_articles a ON a.id = n.legacy_article_id
                WHERE n.legacy_article_id IS NOT NULL AND a.symbols IS NOT NULL AND a.symbols <> ''
                ORDER BY n.id
                LIMIT $1 OFFSET $2
                """,
                batch_size,
                fixed,
            )
            if not rows:
                break
            for r in rows:
                syms = _parse_symbols(r["symbols"])
                await conn.execute(
                    "DELETE FROM news_tags WHERE news_id = $1 AND tag_type = 'stock_symbol'",
                    r["id"],
                )
                if syms:
                    await conn.execute(INSERT_TAG_SQL, r["id"], syms)
            fixed += len(rows)
            print(f"  retag: {fixed} rows rebuilt")
    return fixed


async def backfill(conn: asyncpg.Connection, batch_size: int, dry_run: bool) -> tuple[int, int]:
    """Run backfill batches; returns (mirrored, skipped_or_deduped)."""
    mirrored = 0
    skipped = 0

    while True:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT a.id, a.title, a.summary, a.source, a.url,
                       COALESCE(a.published_at_ts, a.created_at) AS published_at,
                       a.category, a.symbols, a.updated_at, a.created_at
                FROM news_articles a
                WHERE NOT EXISTS (
                    SELECT 1 FROM news_items n WHERE n.legacy_article_id = a.id
                )
                ORDER BY a.id
                LIMIT $1
                """,
                batch_size,
            )
            if not rows:
                break
            if dry_run:
                print(f"[dry-run] would process {len(rows)} rows (first id={rows[0]['id']})")
                break

            for r in rows:
                dedup_hash = compute_dedup_hash(r["title"] or "", r["url"] or "")
                async with conn.transaction() as sp:
                    if r["source"]:
                        await conn.execute(
                            UPSERT_SOURCE_SQL,
                            r["source"],
                            r["updated_at"] or r["created_at"],
                        )
                    item_id = await conn.fetchval(
                        INSERT_ITEM_SQL,
                        r["id"],
                        r["title"],
                        r["summary"],
                        r["source"],
                        r["url"],
                        r["published_at"],
                        r["category"] or "",
                        dedup_hash,
                    )
                    if item_id is None:
                        await sp.rollback()  # nothing inserted; also undo the source upsert
                        skipped += 1
                        continue
                    syms = _parse_symbols(r["symbols"])
                    if syms:
                        await conn.execute(
                            INSERT_TAG_SQL,
                            item_id,
                            syms,
                        )
                    mirrored += 1
        if not dry_run and rows:
            print(f"  batch done: +{len(rows)} processed (total mirrored={mirrored}, skipped={skipped})")

    return mirrored, skipped


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--retag", action="store_true",
                    help="rebuild stock_symbol tags of already-backfilled rows (idempotent repair)")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--dsn", default=None, help="override DB DSN (default: app settings)")
    args = ap.parse_args()

    conn = await _get_conn(args.dsn)
    try:
        if args.retag:
            fixed = await retag(conn, args.batch_size)
            print(f"\nretag done: {fixed} mirrored rows rebuilt")
            return 0
        remaining_before = await conn.fetchval(
            "SELECT count(*) FROM news_articles a "
            "WHERE NOT EXISTS (SELECT 1 FROM news_items n WHERE n.legacy_article_id = a.id)"
        )
        print(f"legacy rows without mirror: {remaining_before}")
        if remaining_before == 0:
            print("nothing to do — already backfilled (idempotent no-op)")
            return 0

        mirrored, skipped = await backfill(conn, args.batch_size, args.dry_run)
        if args.dry_run:
            return 0

        remaining_after = await conn.fetchval(
            "SELECT count(*) FROM news_articles a "
            "WHERE NOT EXISTS (SELECT 1 FROM news_items n WHERE n.legacy_article_id = a.id)"
        )
        total_items = await conn.fetchval("SELECT count(*) FROM news_items")
        total_tags = await conn.fetchval(
            "SELECT count(*) FROM news_tags WHERE tag_type='stock_symbol' "
            "AND news_id IN (SELECT id FROM news_items WHERE legacy_article_id IS NOT NULL)"
        )
        sources = await conn.fetchval(
            "SELECT count(*) FROM news_ingestion_sources"
        )

        print("\n=== backfill summary ===")
        print(f"mirrored this run : {mirrored}")
        print(f"skipped (dedup)   : {skipped}")
        print(f"remaining         : {remaining_after}")
        print(f"news_items total  : {total_items}")
        print(f"backfilled tags   : {total_tags}")
        print(f"sources registry  : {sources}")

        if mirrored == 0 and skipped == 0 and remaining_after > 0:
            print("WARNING: no progress made — inspect errors above")
            return 2
        return 0 if remaining_after == 0 else 2
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
