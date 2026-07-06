"""
Create all database tables in PostgreSQL via SQLAlchemy metadata.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from core.config import settings
from models.base import Base


async def create_all_tables():
    print("=" * 60)
    print("  Creating all database tables in PostgreSQL")
    print("=" * 60)
    print(f"\nDB URL: {settings.database_url}")
    
    import core.database as db
    
    try:
        print("\nConnecting to PostgreSQL...")
        await db.init_database()
        
        if db.engine is None:
            print("ERROR: Engine is None after init_database!")
            sys.exit(1)
        print("Connected!")
        
        print("\nLoading models...")
        import models  # noqa: F401
        
        all_tables = sorted(Base.metadata.tables.keys())
        print(f"Registered tables: {len(all_tables)}")
        for t in all_tables:
            print(f"  - {t}")
        
        print("\nCreating tables...")
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("All tables created successfully!")
        
        print("\nVerifying tables in PostgreSQL...")
        async with db.engine.begin() as conn:
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
            )
            tables = [row[0] for row in result]
            print(f"Tables in PostgreSQL: {len(tables)}")
            for t in tables:
                print(f"  + {t}")
        
        print("\n" + "=" * 60)
        print("  SUCCESS! All tables created")
        print("=" * 60)
        
    except Exception as e:
        import traceback
        print(f"\nERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        await db.close_database()


if __name__ == "__main__":
    asyncio.run(create_all_tables())
