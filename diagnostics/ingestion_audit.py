"""Diagnostic audit of ingestion health."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from sqlalchemy import text

from core.database import get_session


async def db_stats() -> dict:
    stats: dict[str, Any] = {}
    async for session in get_session():
        # Table row counts
        tables = [
            "brsapi_symbol_snapshots",
            "brsapi_index_values",
            "brsapi_codal_announcements",
            "brsapi_commodity_prices",
            "brsapi_crypto_prices",
            "brsapi_gold_coin_prices",
            "brsapi_currency_prices",
            "brsapi_intraday_trades",
            "brsapi_historical_daily",
            "brsapi_historical_real_legal",
            "brsapi_candlesticks",
            "brsapi_shareholder_records",
            "brsapi_ime_futures",
            "brsapi_ime_options",
            "brsapi_ime_certificates",
            "brsapi_ime_funds",
            "brsapi_ime_physical_trades",
            "brsapi_nav_records",
            "brsapi_option_snapshots",
            "quotes",
            "news_articles",
            "codal_reports",
        ]
        for tbl in tables:
            try:
                result = await session.execute(text(f"SELECT count(*) FROM {tbl}"))
                stats[tbl] = result.scalar()
            except Exception as exc:
                stats[tbl] = f"ERR: {exc}"[:60]

        # Sync logs last 24h
        try:
            result = await session.execute(
                text(
                    "SELECT endpoint, status, count(*) "
                    "FROM brsapi_sync_log "
                    "WHERE started_at >= CURRENT_DATE "
                    "GROUP BY endpoint, status ORDER BY endpoint"
                )
            )
            stats["sync_logs_today"] = [tuple(r) for r in result.fetchall()]
        except Exception as exc:
            stats["sync_logs_today"] = f"ERR: {exc}"[:60]

        # Latest sync log per endpoint
        try:
            result = await session.execute(
                text(
                    "SELECT DISTINCT ON (endpoint) endpoint, status, items_count, error_message, started_at "
                    "FROM brsapi_sync_log ORDER BY endpoint, started_at DESC"
                )
            )
            stats["latest_sync_logs"] = [tuple(r) for r in result.fetchall()]
        except Exception as exc:
            stats["latest_sync_logs"] = f"ERR: {exc}"[:60]

        # Latest snapshot timestamp
        try:
            result = await session.execute(
                text("SELECT max(fetched_at) FROM brsapi_symbol_snapshots")
            )
            stats["latest_snapshot_time"] = str(result.scalar())
        except Exception as exc:
            stats["latest_snapshot_time"] = f"ERR: {exc}"[:60]
        break
    return stats


async def brsapi_health() -> dict:
    from brsapi.client import BrsApiClient
    client = BrsApiClient(api_key=os.getenv("BRSAPI_API_KEY", "FreeSV0E1LSgB9RDjuf0QorSLViX8pPG"))
    await client.start()
    try:
        result = await client.health()
        return result
    finally:
        await client.stop()


async def main() -> None:
    output_path = "diagnostics/ingestion_audit_result.json"
    result: dict[str, Any] = {}

    print("=== DB Stats ===")
    result["db_stats"] = await db_stats()
    print(json.dumps(result["db_stats"], indent=2, default=str, ensure_ascii=True))

    print("\n=== BrsApi Health ===")
    try:
        result["brsapi_health"] = await asyncio.wait_for(brsapi_health(), timeout=30)
        print(json.dumps(result["brsapi_health"], indent=2, default=str, ensure_ascii=True))
    except Exception as exc:
        result["brsapi_health"] = {"error": str(exc)}
        print(f"BrsApi health failed: {exc}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str, ensure_ascii=False)
    print(f"\nFull report written to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
