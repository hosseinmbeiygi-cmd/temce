"""
Sync BrsApi live data to PostgreSQL for the live market widget.
Uses the proper BrsApi sync service with error handling.
"""
import asyncio
import io
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from brsapi.client import close_client, get_client
from brsapi.services.sync_service import BrsApiSyncService

DATABASE_URL = "postgresql+asyncpg://hossein:1343@localhost:5432/my_first_db"


async def sync_all():
    print("=" * 60)
    print("  Syncing BrsApi Live Data for Widget")
    print("=" * 60)

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    client = await get_client()
    await client.start()

    try:
        async with async_session() as session:
            svc = BrsApiSyncService(client=client, session=session)

            # ── Sync TSETMC symbols (type=1 for stocks) ──
            print("\n[1/6] Syncing TSETMC symbols...")
            try:
                report = await svc.sync_all_symbols(session, symbol_type="1")
                status = "OK" if report.success else "FAIL"
                print(f"   [{status}] {report.items_count} records in {report.duration_ms:.0f}ms")
                if report.error:
                    print(f"   Error: {report.error}")
            except Exception as e:
                print(f"   [FAIL] {e}")

            # ── Sync gold, currency & crypto (combined endpoint) ──
            print("\n[2/6] Syncing gold, currency & crypto (Gold_Currency.php)...")
            try:
                reports = await svc.sync_gold_currency(session)
                for r in reports:
                    status = "OK" if r.success else "FAIL"
                    print(f"   [{status}] {r.endpoint}: {r.items_count} records in {r.duration_ms:.0f}ms")
                    if r.error:
                        print(f"   Error: {r.error}")
            except Exception as e:
                print(f"   [FAIL] {e}")

            # ── Sync index values ──
            print("\n[3/6] Syncing index values...")
            try:
                report = await svc.sync_index(session, index_type="1")
                status = "OK" if report.success else "FAIL"
                print(f"   [{status}] {report.items_count} records in {report.duration_ms:.0f}ms")
                if report.error:
                    print(f"   Error: {report.error}")
            except Exception as e:
                print(f"   [FAIL] {e}")

            # ── Sync commodities (global) ──
            print("\n[4/6] Syncing global commodity prices...")
            try:
                report = await svc.sync_commodities(session)
                status = "OK" if report.success else "FAIL"
                print(f"   [{status}] {report.items_count} records in {report.duration_ms:.0f}ms")
                if report.error:
                    print(f"   Error: {report.error}")
            except Exception as e:
                print(f"   [FAIL] {e}")

        print("\n" + "=" * 60)
        print("  Sync complete!")
        print("=" * 60)

    finally:
        await close_client()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(sync_all())
