"""Report row counts for every BrsApi-owned table (read-only)."""

import asyncio
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

import brsapi.models  # noqa: F401  (registers all models on the metadata)
from sqlalchemy import text

from brsapi.models.base import BrsApiBase
from core.database import get_session


async def main() -> None:
    models = list(BrsApiBase.__subclasses__())
    # Two-level walk (some models may subclass an intermediate base).
    seen = list(models)
    for m in list(models):
        seen.extend(m.__subclasses__())
    models = {getattr(m, "__tablename__", None): m for m in seen if getattr(m, "__tablename__", None)}
    # Fall back to the metadata registry (covers all mapped tables).
    for table in BrsApiBase.metadata.tables.values():
        models.setdefault(table.name, None)
    async for session in get_session():
        rows = []
        for table in sorted(models):
            try:
                count = (await session.execute(text(f'SELECT COUNT(*) FROM "{table}"'))).scalar()
            except Exception as exc:  # noqa: BLE001
                rows.append((table, f"ERR {type(exc).__name__}: {str(exc)[:60]}"))
                continue
            rows.append((table, count))
        rows.sort(key=lambda r: (isinstance(r[1], str), r[0]))
        print(f"{'table':48s} rows")
        print("-" * 60)
        for table, count in rows:
            print(f"{table:48s} {count}")


if __name__ == "__main__":
    asyncio.run(main())
