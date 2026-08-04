import asyncio
import sys

sys.path.insert(0, '.')

async def check():
    from sqlalchemy import text

    from core.database import close_database, get_session, init_database
    await init_database()
    async for session in get_session():
        # Check codal tables
        print('Codal-related tables:')
        for t in ['codal_reports', 'brsapi_codal_announcements']:
            try:
                count_r = await session.execute(text(f'SELECT COUNT(*) FROM "{t}"'))
                count = count_r.scalar() or 0
                print(f'\n  {t}: {count} rows')
                if count > 0:
                    sample_r = await session.execute(text(f'SELECT * FROM "{t}" LIMIT 1'))
                    row = sample_r.mappings().first()
                    if row:
                        print(f'    Columns: {list(row.keys())}')
            except Exception as e:
                print(f'  {t}: ERROR - {e}')
        break
    await close_database()

asyncio.run(check())
