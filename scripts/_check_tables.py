#!/usr/bin/env python
"""Quick check: does generated_strategies table exist?"""
import asyncio
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from sqlalchemy import text

import core.database as _db


async def main():
    await _db.init_database()
    async with _db.async_session_factory() as sess:
        r = await sess.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'generated_strategies')"
        ))
        print("generated_strategies exists:", r.scalar())

        r2 = await sess.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE '%strateg%'"
        ))
        for row in r2.fetchall():
            print("  found table:", row[0])


asyncio.run(main())
