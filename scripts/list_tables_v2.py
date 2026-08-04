"""List all database tables and row counts using direct psycopg2 connection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio

from sqlalchemy import text

import core.database as _db


async def main():
    await _db.init_database()
    if not _db.async_session_factory:
        print("Database not initialized")
        return

    async with _db.async_session_factory() as sess:
        r = await sess.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ))
        tables = [row[0] for row in r.fetchall()]

        print(f"\n{'='*70}")
        print(f"{'Table Name':<45s} {'Rows':>12s} {'Columns':>8s}")
        print(f"{'='*70}")

        for tbl in tables:
            try:
                rc = await sess.execute(text(f"SELECT COUNT(*) FROM \"{tbl}\""))
                cnt = rc.scalar() or 0
                cc = await sess.execute(text(
                    f"SELECT COUNT(*) FROM information_schema.columns "
                    f"WHERE table_name='{tbl}'"
                ))
                col_cnt = cc.scalar() or 0
                icon = "✅" if cnt > 0 else "○"
                print(f"  {icon} {tbl:<43s} {cnt:>12,} {col_cnt:>8}")
            except Exception as e:
                print(f"  ❌ {tbl:<43s} {'ERROR':>12s} {str(e)[:50]}")

asyncio.run(main())
