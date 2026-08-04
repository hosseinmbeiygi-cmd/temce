import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from core.database import async_session_factory


async def main():
    if not async_session_factory:
        print("Database not initialized")
        return
    async with async_session_factory() as sess:
        # List all tables
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
                rc = await sess.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                cnt = rc.scalar() or 0
                cc = await sess.execute(text(
                    f"SELECT COUNT(*) FROM information_schema.columns "
                    f"WHERE table_name='{tbl}'"
                ))
                col_cnt = cc.scalar() or 0
                print(f"  {tbl:<45s} {cnt:>12,} {col_cnt:>8}")
            except Exception as e:
                print(f"  {tbl:<45s} {'ERROR':>12s} {str(e)[:30]:>8}")


asyncio.run(main())
