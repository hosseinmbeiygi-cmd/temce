"""Check whether version-2/3 fund symbols (ابتکار2, اتکاسا3, ...) are real funds in snapshots."""
import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from brsapi.models import SymbolSnapshotModel
from core.database import get_session

SAMPLES = ["ابتکار2", "اتکاسا3", "اتوآگاه2", "آتی1", "آتیه ملت4", "ابتکار", "اتکاسا"]


async def main() -> None:
    async for session in get_session():
        for s in SAMPLES:
            r = await session.execute(
                select(
                    SymbolSnapshotModel.symbol,
                    SymbolSnapshotModel.name,
                    SymbolSnapshotModel.sector,
                    SymbolSnapshotModel.ins_id,
                    SymbolSnapshotModel.fetched_at,
                )
                .where(SymbolSnapshotModel.symbol == s)
                .order_by(SymbolSnapshotModel.fetched_at.desc())
                .limit(1)
            )
            row = r.one_or_none()
            if row:
                print(f"{s:12s} name={row.name!r:24s} sector={row.sector!r:28s} ins_id={row.ins_id}")
            else:
                print(f"{s:12s} NOT IN SNAPSHOTS")


asyncio.run(main())
