"""Stamp alembic at revision 0021 then run upgrade to 0022.

The database already has all tables from 0001-0021 (created by
core.database.init_database -> Base.metadata.create_all), but the
alembic_version table is missing. This script stamps the current
state at 0021, then applies revision 0022.
"""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from core.config import settings


def main():
    # Create sync database URL
    sync_url = settings.database_url
    if "+asyncpg" in sync_url:
        sync_url = sync_url.replace("+asyncpg", "+psycopg2")

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    # Check if alembic_version table exists
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.tables "
                "  WHERE table_schema = 'public' AND table_name = 'alembic_version'"
                ")"
            )
        )
        version_exists = result.scalar()

        if not version_exists:
            print("alembic_version table not found. Stamping at revision 0021...")
            # Stamp at the last existing revision
            command.stamp(alembic_cfg, "0021")
            print("Stamped at 0021.")
        else:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()
            print(f"Current alembic version: {current}")

    engine.dispose()

    # Now run upgrade to head (which should be 0022)
    print("\nRunning alembic upgrade head...")
    command.upgrade(alembic_cfg, "head")
    print("Migration 0022 (BrsApi tables) completed successfully!")


if __name__ == "__main__":
    main()
