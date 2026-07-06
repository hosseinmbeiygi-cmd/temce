"""Fix codal table: add missing audit_status column."""
# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import init_database

async def main():
    await init_database()
    from core.database import engine
    async with engine.begin() as conn:
        await conn.execute(text('ALTER TABLE brsapi_codal_announcements ADD COLUMN IF NOT EXISTS audit_status VARCHAR'))
        print("audit_status column added")
    await engine.dispose()

asyncio.run(main())
