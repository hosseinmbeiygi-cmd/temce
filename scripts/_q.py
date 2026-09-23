import asyncio, importlib.util, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
load_dotenv()
spec = importlib.util.spec_from_file_location(
    "m0065", "migrations/versions/0065_timescale_compression_policies.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

async def main():
    e = create_async_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
    async with e.connect() as c:
        await c.run_sync(lambda conn: print(
            "timescaledb present:", m._timescaledb_present(conn)))
        def check(conn):
            for t, seg, order in m._TARGETS:
                print(f"  {t:22s} hypertable={m._is_hypertable(conn,t)} "
                      f"cols_configured={m._has_compression_columns(conn,t)} "
                      f"policy_exists={m._has_compression_policy(conn,t)} "
                      f"segmentby={seg} orderby={order!r}")
        await c.run_sync(check)
    await e.dispose()
asyncio.run(main())
