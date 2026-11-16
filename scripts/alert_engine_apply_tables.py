"""Create the alert-engine tables on a database without running the Alembic chain.

``migrations/versions/0127_alert_engine.py`` is the migration of record. This helper
executes exactly its (idempotent, additive ``CREATE … IF NOT EXISTS``) statements, so a
dev database can get the tables while an earlier pending migration is still unapplied.
It does not touch ``alembic_version``; a later ``alembic upgrade head`` is a no-op for
these tables.

Usage:  python scripts/alert_engine_apply_tables.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _statements() -> list[str]:
    collected: list[str] = []
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = types.SimpleNamespace(execute=collected.append)  # type: ignore[attr-defined]
    real = sys.modules.get("alembic")
    sys.modules["alembic"] = fake_alembic
    try:
        spec = importlib.util.spec_from_file_location("m0127", ROOT / "migrations" / "versions" / "0127_alert_engine.py")
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        module.upgrade()
    finally:
        if real is not None:
            sys.modules["alembic"] = real
        else:
            del sys.modules["alembic"]
    return collected


async def main() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from core.config import settings

    engine = create_async_engine(settings.database_url_async)
    async with engine.begin() as conn:
        for sql in _statements():
            await conn.execute(text(sql))
    await engine.dispose()
    print("alert-engine tables ensured")


if __name__ == "__main__":
    asyncio.run(main())
