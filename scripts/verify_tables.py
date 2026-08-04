import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text


async def main():
    import core.database as db
    await db.init_database()

    async with db.engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ))
        tables = [row[0] for row in result.fetchall()]
        print(f"Total tables: {len(tables)}")
        for t in tables:
            print(f"  - {t}")

    await db.close_database()


if __name__ == "__main__":
    asyncio.run(main())
