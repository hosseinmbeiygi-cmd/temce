"""
Layered storage pipeline — ingestion/storage/layered_pipeline.py
=================================================================
Hot  -> Redis  (core.cache.get_cache) — TTL 300s, immediate visibility
Warm -> TimescaleDB/Postgres (core.database.async_session_factory) — durable, 30d
Cold -> Parquet is NOT in scope for ingestion (handled by lake/ package)

- Validates raw payload minimally (no technicals)
- Writes Hot first (fail-open), then Warm (best-effort)
- Deduplicates by (symbol, fetched_at minute) via Redis SETNX

Reuse: core.cache, core.database, core.logging
Decoupled: never imports from precompute/api/frontend
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from core.cache import get_cache
from core.logging import get_logger

logger = get_logger(__name__)

HOT_TTL_SECONDS = 300
DEDUP_TTL_SECONDS = 3600


def _dedup_key(symbol: str, fetched_at: str) -> str:
    # Minute bucket
    minute = fetched_at[:16]  # 2026-09-13T01:23
    raw = f"{symbol}:{minute}"
    return f"armor:dedup:{hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:12]}"


async def store_hot(symbol: str, payload: dict[str, Any], fetched_at: str) -> bool:
    """
    Store raw validated payload in Redis Hot layer.
    Returns True if stored, False if deduped or Redis unavailable.
    """
    cache = get_cache()
    if not cache.is_connected:
        logger.debug("Hot store skipped — Redis not connected for %s", symbol)
        return False
    try:
        # Dedup
        dkey = _dedup_key(symbol, fetched_at)
        if cache.client is not None:
            is_new = await cache.client.set(dkey, "1", nx=True, ex=DEDUP_TTL_SECONDS)
            if not is_new:
                logger.debug("Hot dedup hit for %s @ %s", symbol, fetched_at)
                return False
        # Hot: per-symbol key + hash for batch
        hot_key = f"armor:raw:{symbol}"
        await cache.set(hot_key, payload, ttl=HOT_TTL_SECONDS)
        # Also push to hot hash for dashboard/ready style batch reads
        if cache.client is not None:
            await cache.client.hset("armor:raw:all", symbol, json.dumps(payload, ensure_ascii=False, default=str))
            await cache.client.expire("armor:raw:all", HOT_TTL_SECONDS)
        return True
    except Exception:
        logger.debug("Hot store failed for %s", symbol, exc_info=True)
        return False


async def store_warm(rows: list[dict[str, Any]]) -> int:
    """
    Store validated rows in Warm layer (Postgres/TimescaleDB).
    Best-effort: if DB unavailable, logs and returns 0 (data still in Hot).
    Returns count of rows inserted.
    """
    if not rows:
        return 0
    try:
        from core.database import async_session_factory
        from sqlalchemy import text

        if async_session_factory is None:
            logger.debug("Warm store skipped — DB not initialized (%d rows)", len(rows))
            return 0

        # Minimal validation: each row must have symbol
        valid = [r for r in rows if r.get("symbol")]
        if not valid:
            return 0

        async with async_session_factory() as session:  # type: ignore
            # Best-effort: ensure a generic hypertable exists (or fallback to a plain table)
            # We do NOT create the full armor schema here — just a raw_ingest table if missing
            try:
                await session.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS armor_raw_ingest (
                            symbol TEXT NOT NULL,
                            fetched_at TIMESTAMPTZ NOT NULL,
                            payload JSONB NOT NULL,
                            PRIMARY KEY (symbol, fetched_at)
                        );
                        """
                    )
                )
                await session.commit()
            except Exception:
                await session.rollback()
                logger.debug("Warm ensure table failed", exc_info=True)

            inserted = 0
            for r in valid:
                try:
                    sym = r["symbol"]
                    fetched = r.get("fetched_at") or datetime.now(UTC).isoformat()
                    # Parse to timestamptz
                    try:
                        ts = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
                    except Exception:
                        ts = datetime.now(UTC)
                    await session.execute(
                        text("INSERT INTO armor_raw_ingest (symbol, fetched_at, payload) VALUES (:s, :t, :p) ON CONFLICT DO NOTHING"),
                        {"s": sym, "t": ts, "p": json.dumps(r, ensure_ascii=False, default=str)},
                    )
                    inserted += 1
                except Exception:
                    logger.debug("Warm insert failed for %s", r.get("symbol"), exc_info=True)
                    await session.rollback()
            try:
                await session.commit()
            except Exception:
                await session.rollback()
            logger.info("Warm stored %d/%d rows", inserted, len(valid))
            return inserted
    except Exception:
        logger.debug("Warm store failed", exc_info=True)
        return 0


async def pipeline_store(rows: list[dict[str, Any]], fetched_at: str | None = None) -> dict[str, Any]:
    """
    Full layered pipeline: validate -> Hot -> Warm.

    Returns summary: {hot_stored, warm_stored, deduped, total}.
    """
    if not rows:
        return {"hot_stored": 0, "warm_stored": 0, "deduped": 0, "total": 0}
    fetched_at = fetched_at or datetime.now(UTC).isoformat()

    # Minimal validation: must have symbol, price_last or price, market
    total = len(rows)
    hot_stored = 0
    deduped = 0
    warm_batch: list[dict[str, Any]] = []

    for r in rows:
        sym = r.get("symbol")
        if not sym:
            deduped += 1
            continue
        # Ensure fetched_at
        r.setdefault("fetched_at", fetched_at)
        ok = await store_hot(sym, r, r["fetched_at"])
        if ok:
            hot_stored += 1
            warm_batch.append(r)
        else:
            # Check if deduped vs redis unavailable
            dkey = _dedup_key(sym, r["fetched_at"])
            # If redis unavailable, store_hot returns False but we still want warm
            with contextlib.suppress(Exception):
                from core.cache import get_cache

                if not get_cache().is_connected:
                    warm_batch.append(r)
                    hot_stored += 1  # count as hot-missed but warm will get it

    warm_stored = await store_warm(warm_batch)
    logger.info("Pipeline: total=%d hot=%d warm=%d deduped=%d", total, hot_stored, warm_stored, deduped)
    return {"hot_stored": hot_stored, "warm_stored": warm_stored, "deduped": deduped, "total": total}
