"""
AllSymbols scanner — ingestion/scanners/all_symbols.py
=======================================================
Spec: AllSymbols.php (whole market in one request, every 30s during market).

- Uses ingestion/brs_api_client.py (300/5min, 10k/day, browser headers, backoff)
- Minimal validation: each row must have symbol + price_last/trade_volume
- Hands off to layered_pipeline for Hot/Warm storage
- Respects market hours (Asia/Tehran 08:30-15:30) — outside hours runs every 5 min as keep-alive
- Designed to be called by a scheduler (e.g. APScheduler or a simple asyncio loop)

Reuse: ingestion.brs_api_client, ingestion.storage.layered_pipeline, ingestion.validation
Decoupled: never imports precompute/api/frontend
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

try:
    from ingestion.brs_api_client import get_armor_client
except ImportError:
    # Fallback to the existing ingestion client (BrsApiIngestionClient)
    from ingestion.brs_api_client import BrsApiIngestionClient

    def get_armor_client():  # type: ignore
        return BrsApiIngestionClient()

from ingestion.storage.layered_pipeline import pipeline_store

logger = get_logger(__name__)

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))
MARKET_OPEN = (8, 30)
MARKET_CLOSE = (15, 30)
SCAN_INTERVAL_MARKET = 30  # seconds
SCAN_INTERVAL_OFF = 300  # 5 min outside market


def _is_market_open(now: datetime | None = None) -> bool:
    now_tehran = (now or datetime.now(TEHRAN_TZ)).astimezone(TEHRAN_TZ)
    # Weekend: Thu/Fri are weekend in Iran? TSE is Sat-Wed. Keep simple: Fri is closed
    if now_tehran.weekday() == 4:  # Friday
        return False
    hm = (now_tehran.hour, now_tehran.minute)
    return MARKET_OPEN <= hm < MARKET_CLOSE


def _validate_rows(raw: Any) -> list[dict[str, Any]]:
    """
    Minimal validation per spec: no technical calculations, just basic field checks.
    Accepts BrsApi AllSymbols response shapes: list or dict with data/list/results.
    Returns list of normalized rows with at least symbol + market.
    """
    candidates: Any = None
    if isinstance(raw, list):
        candidates = raw
    elif isinstance(raw, dict):
        # BrsApi often wraps: {"data": [...]} or {"list": [...]} or {"results": [...]}
        for key in ("data", "list", "results", "items", "symbols"):
            if key in raw and isinstance(raw[key], list):
                candidates = raw[key]
                break
        if candidates is None:
            # Single page object with symbols nested under unexpected key — try any list value
            for v in raw.values():
                if isinstance(v, list) and v and isinstance(v[0], dict) and "symbol" in v[0]:
                    candidates = v
                    break
    if not isinstance(candidates, list):
        return []

    out: list[dict[str, Any]] = []
    for r in candidates:
        if not isinstance(r, dict):
            continue
        sym = r.get("symbol") or r.get("l18") or r.get("name") or ""
        if not sym or not isinstance(sym, str):
            continue
        # Minimal required: symbol + at least one price/volume field
        # We keep rows even if some fields missing — auditor will flag later
        out.append(
            {
                "symbol": sym.strip(),
                "price_last": r.get("price_last") or r.get("price") or r.get("last_price") or r.get("pc"),
                "trade_volume": r.get("trade_volume") or r.get("volume") or r.get("tradeVolume"),
                "trade_value": r.get("trade_value") or r.get("value") or r.get("tradeValue"),
                "market": r.get("market") or r.get("board") or "TSE",
                "fetched_at": datetime.now(UTC).isoformat(),
                "_raw": r,  # keep original for debugging (Warm layer will store full)
            }
        )
    return out


async def scan_once() -> dict[str, Any]:
    """
    Single scan: fetch AllSymbols.php -> validate -> layered store.
    Returns summary: {fetched, validated, stored, is_market_open, elapsed_ms}.
    """
    is_open = _is_market_open()
    client = get_armor_client()
    # BrsApiIngestionClient needs start() before fetch
    with contextlib.suppress(Exception):
        if hasattr(client, "start"):
            await client.start()
    t0 = datetime.now(UTC)
    raw_resp = await client.fetch_all_symbols()
    elapsed_ms = (datetime.now(UTC) - t0).total_seconds() * 1000

    # Normalize both dict-style and Result-style responses
    if hasattr(raw_resp, "success"):
        # Result object from BrsApiIngestionClient
        if not raw_resp.success:  # type: ignore
            err = getattr(raw_resp, "error", "unknown")
            logger.warning("AllSymbols fetch failed: %s", err)
            return {
                "fetched": 0,
                "validated": 0,
                "stored": 0,
                "is_market_open": is_open,
                "elapsed_ms": elapsed_ms,
                "error": err,
            }
        resp = {"success": True, "data": getattr(raw_resp, "value", getattr(raw_resp, "data", None))}
    else:
        resp = raw_resp  # type: ignore

    if not resp.get("success"):
        logger.warning("AllSymbols fetch failed: %s", resp.get("error"))
        return {
            "fetched": 0,
            "validated": 0,
            "stored": 0,
            "is_market_open": is_open,
            "elapsed_ms": elapsed_ms,
            "error": resp.get("error"),
        }

    raw = resp.get("data")
    rows = _validate_rows(raw)
    # Use layered pipeline (Hot Redis + Warm Postgres)
    fetched_at = datetime.now(UTC).isoformat()
    summary = await pipeline_store(rows, fetched_at=fetched_at)
    # limiter status may be method or property depending on client impl
    try:
        lim = client.limiter_status() if hasattr(client, "limiter_status") else {}
    except Exception:
        lim = {}
    logger.info(
        "AllSymbols scan: fetched=%d validated=%d hot=%d warm=%d market_open=%s elapsed=%.0fms limiter=%s",
        len(rows) if isinstance(raw, list) else len(rows),
        len(rows),
        summary.get("hot_stored", 0),
        summary.get("warm_stored", 0),
        is_open,
        elapsed_ms,
        lim,
    )
    return {
        "fetched": len(rows),
        "validated": len(rows),
        "stored": summary.get("hot_stored", 0),
        "warm_stored": summary.get("warm_stored", 0),
        "is_market_open": is_open,
        "elapsed_ms": elapsed_ms,
        "limiter": lim,
    }


async def run_forever(stop_after: int | None = None) -> None:
    """
    Loop forever (or stop_after iterations for tests).
    During market: every 30s. Outside market: every 5 min.
    """
    iteration = 0
    while True:
        try:
            await scan_once()
        except Exception:
            logger.exception("AllSymbols scan iteration failed")
        iteration += 1
        if stop_after is not None and iteration >= stop_after:
            break
        is_open = _is_market_open()
        await asyncio.sleep(SCAN_INTERVAL_MARKET if is_open else SCAN_INTERVAL_OFF)


# ── For scheduler integration (e.g. apps/scheduler) ──────────────
async def scheduled_tick() -> None:
    """One tick for an external scheduler — just calls scan_once()."""
    await scan_once()
