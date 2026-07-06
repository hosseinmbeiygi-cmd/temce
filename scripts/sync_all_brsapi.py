"""
Run full BrsApi sync for all sections.
Uses BrsApiSyncService.sync_all() to sync all data in sequence.
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

        print("\nStarting full BrsApi sync...")
        print("=" * 60)

        reports = await service.sync_all(session=session)

        print("=" * 60)
        print(f"\n  COMPLETE - {len(reports)} sync operations")
        print("=" * 60)

        success = 0
        failed = 0
        total_items = 0
        total_time = 0.0

        for report in reports:
            icon = "[OK]" if report.success else "[FAIL]"
            skip_tag = " (skipped)" if report.skipped else ""
            print(f"  {icon} {report.endpoint:<40s} {report.items_count:>5} items  {report.duration_ms:>8.0f}ms{skip_tag}")
            if report.success:
                success += 1
                total_items += report.items_count
            else:
                failed += 1
            total_time += report.duration_ms

        print("=" * 60)
        print(f"  Success: {success} | Failed: {failed} | Total items: {total_items}")
        print(f"  Total time: {total_time/1000:.1f}s")
        print("=" * 60)

    await engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
