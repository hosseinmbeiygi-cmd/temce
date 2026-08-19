"""Ad-hoc: list tables without dual-date columns and their date-ish columns."""
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    e = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with e.connect() as c:
            rows = (
                await c.execute(
                    text(
                        "SELECT c.table_name, string_agg(c.column_name || ':' || c.data_type, ', ' ORDER BY c.ordinal_position) "
                        "FROM information_schema.columns c "
                        "WHERE c.table_schema = 'public' "
                        "  AND c.table_name NOT IN (SELECT table_name FROM dual_date_columns) "
                        "  AND c.table_name NOT LIKE 'alembic_%' "
                        "GROUP BY c.table_name ORDER BY c.table_name"
                    )
                )
            ).fetchall()
        for table, cols in rows:
            dateish = [x for x in cols.split(", ") if any(k in x for k in ("date", "time", "at ", "_at"))]
            print(f"{table}: {cols[:160]}")
            print(f"    date-ish: {dateish}")
    finally:
        await e.dispose()


asyncio.run(main())
