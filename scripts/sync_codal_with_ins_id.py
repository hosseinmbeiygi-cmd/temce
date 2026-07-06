"""
Run Codal sync to populate ins_id and instrument_id for all announcements.
Uses the updated sync_service that batch-lookup ins_id from snapshots.
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

    async with async_session() as session:
        print("Initializing BrsApi client...")
        client = await get_client()

        service = BrsApiSyncService(client=client)

        print("Running Codal sync...")
        report = await service.sync_codal(session=session)

        print()
        print("=" * 60)
        print("  CODAL SYNC RESULT")
        print("=" * 60)
        print(f"  Endpoint:    {report.endpoint}")
        print(f"  Success:     {report.success}")
        print(f"  Items:       {report.items_count}")
        print(f"  Duration:    {report.duration_ms:.0f}ms")
        print(f"  Error:       {report.error or 'None'}")

        # Verify: check how many records now have ins_id
        from sqlalchemy import text
        r = await session.execute(text("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE ins_id IS NOT NULL) as has_ins,
                   COUNT(*) FILTER (WHERE instrument_id IS NOT NULL) as has_instr
            FROM brsapi_codal_announcements
        """))
        total, has_ins, has_instr = r.fetchone()
        print()
        print("  CODAL TABLE STATUS:")
        print(f"  Total records:     {total}")
        print(f"  With ins_id:       {has_ins}")
        print(f"  With instrument_id:{has_instr}")
        print()

    await engine.dispose()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
