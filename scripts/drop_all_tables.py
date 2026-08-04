"""Drop all tables in the database."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text


async def main():
    import core.database as db

    print("=" * 60)
    print("  DROPPING ALL TABLES")
    print("=" * 60)

    await db.init_database()

    if db.engine is None:
        print("ERROR: Engine is None")
        sys.exit(1)

    async with db.engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result.fetchall()]

    print(f"\nFound {len(tables)} tables:")
    for t in tables:
        print(f"  - {t}")

    if not tables:
        print("\nNo tables to drop.")
        await db.close_database()
        return

    async with db.engine.begin() as conn:
        print("\nDropping all tables...")
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO hossein"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        print("Done! Schema dropped and recreated.")

    async with db.engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        ))
        remaining = result.fetchall()

    print(f"\nTables remaining: {len(remaining)}")
    print("Database is now clean.")

    await db.close_database()


if __name__ == "__main__":
    asyncio.run(main())
