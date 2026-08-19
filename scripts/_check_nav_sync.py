import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings


async def main() -> None:
    eng = create_async_engine(settings.database_url_async or settings.database_url)
    async with eng.connect() as c:
        r = await c.execute(
            text(
                "SELECT created_at, status, items_count, error_message "
                "FROM brsapi_sync_log WHERE endpoint = '/Tsetmc/Nav.php' "
                "ORDER BY created_at DESC LIMIT 6"
            )
        )
        print("=== NAV sync_log (last 6) ===")
        for x in r.fetchall():
            print("  ", x)

        r = await c.execute(
            text(
                "SELECT COUNT(DISTINCT symbol) FROM brsapi_symbol_snapshots "
                "WHERE sector LIKE '%صندوق%'"
            )
        )
        print("fund symbols (sector like %صندوق%):", r.fetchone()[0])

        r = await c.execute(
            text(
                "SELECT date, COUNT(*) FROM brsapi_nav_records "
                "GROUP BY date ORDER BY date DESC LIMIT 6"
            )
        )
        print("=== nav_records per date (latest 6) ===")
        for x in r.fetchall():
            print("  ", x)

        r = await c.execute(
            text("SELECT MAX(date), COUNT(DISTINCT symbol) FROM brsapi_nav_records")
        )
        print("max date / distinct symbols:", r.fetchone())
    await eng.dispose()


asyncio.run(main())
