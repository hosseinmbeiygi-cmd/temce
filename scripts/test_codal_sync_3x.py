"""
Run codal sync 3 times with 5-second intervals to test API response.
"""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from brsapi.client import get_client
from brsapi.services.sync_service import BrsApiSyncService
from core.config import settings


async def main():
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print("Connecting to database...")
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    client = await get_client()
    service = BrsApiSyncService(client=client)

    for attempt in range(1, 4):
        print(f"\n{'='*50}")
        print(f"  Attempt {attempt}/3")
        print(f"{'='*50}")

        async with async_session() as session:
            report = await service.sync_codal(session=session)
            print(f"  Success:   {report.success}")
            print(f"  Items:     {report.items_count}")
            print(f"  Duration:  {report.duration_ms:.0f}ms")
            print(f"  Error:     {report.error or 'None'}")
            print(f"  Skipped:   {report.skipped}")

        if attempt < 3:
            print(f"\n  Waiting 5 seconds...")
            await asyncio.sleep(5)

    # Final check
    print(f"\n{'='*50}")
    print("  FINAL DATABASE CHECK")
    print(f"{'='*50}")
    async with async_session() as session:
        from sqlalchemy import text
        r = await session.execute(text("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE ins_id IS NOT NULL) as has_ins,
                   COUNT(*) FILTER (WHERE instrument_id IS NOT NULL) as has_instr
            FROM brsapi_codal_announcements
        """))
        total, has_ins, has_instr = r.fetchone()
        print(f"  Total records:     {total}")
        print(f"  With ins_id:       {has_ins}")
        print(f"  With instrument_id: {has_instr}")

    await engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
