import asyncio
from core.database import init_database, engine
from sqlalchemy import text

async def main():
    await init_database()
    from core.database import engine as eng2
    e = eng2 if eng2 is not None else engine
    async with e.begin() as conn:
        try:
            v = (await conn.execute(text('SELECT version_num FROM alembic_version'))).scalar()
            print('alembic_version:', v)
        except Exception as ex:
            print('alembic_version error:', str(ex)[:150])
        tables = (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'fund_%' OR tablename LIKE 'stock_%')"))).fetchall()
        print('existing new tables:', sorted(t[0] for t in tables))

asyncio.run(main())
