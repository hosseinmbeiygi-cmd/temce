import asyncio
import contextlib
import json
import sys
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.needs_db

from brsapi.client import get_client
from brsapi.config import BrsApiEndpoints
from brsapi.models.tsetmc import SymbolDetailModel
from brsapi.parsers.tsetmc import TsetmcParser
from core.config import settings

#!/usr/bin/env python
"""Test: sync via ORM objects."""

sys.path.insert(0, str(Path(__file__).resolve().parent))


load_dotenv()


async def test():
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        client = await get_client()

        for sym in ["فولاد", "شپنا", "خودرو"]:
            t0 = time.time()

            # Fetch from API
            result = await client.fetch(
                BrsApiEndpoints.SYMBOL_DETAIL,
                params={"l18": sym},
            )
            if not result.success:
                print(f"  {sym}: API error: {result.error}")
                continue

            resp = result.value
            if resp.is_empty:
                print(f"  {sym}: Empty response")
                continue

            # Parse
            parsed = TsetmcParser.parse_symbol_detail(resp.data)
            if not parsed:
                print(f"  {sym}: Parse error")
                continue

            # Fix types for ORM
            if "raw_json" in parsed and isinstance(parsed["raw_json"], str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    parsed["raw_json"] = json.loads(parsed["raw_json"])
            if "assembly" in parsed and isinstance(parsed["assembly"], str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    parsed["assembly"] = json.loads(parsed["assembly"])

            # Use ORM merge (upsert)
            try:
                await session.merge(SymbolDetailModel(**parsed))
                await session.flush()
                print(f"  {sym}: OK ({time.time()-t0:.1f}s)")
            except Exception as e:
                print(f"  {sym}: ORM error: {type(e).__name__}: {e}")

            await asyncio.sleep(2)

        try:
            await session.commit()
            print("\nCommitted!")
        except Exception as e:
            print(f"\nCommit failed: {e}")
            await session.rollback()

        result = await session.execute(text("SELECT COUNT(*) FROM brsapi_symbol_details"))
        print(f"Total symbol_details in DB: {result.scalar()}")

    await engine.dispose()


asyncio.run(test())
