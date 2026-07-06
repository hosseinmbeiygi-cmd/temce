"""
Show structure and indexes of all 20 BrsApi tables in PostgreSQL.
"""

from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from sqlalchemy import create_engine, text
from core.config import settings


def main() -> None:
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)

    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name LIKE 'brsapi_%' "
                "ORDER BY table_name"
            )
        ).fetchall()

        for (tname,) in tables:
            sep = "=" * 70
            print(f"\n{sep}")
            print(f"  TABLE: {tname}")
            print(sep)

            # Columns
            cols = conn.execute(
                text(
                    "SELECT column_name, data_type, character_maximum_length, "
                    "is_nullable, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_name = :t ORDER BY ordinal_position"
                ),
                {"t": tname},
            ).fetchall()

            print(f"  {'Column':30s} {'Type':30s} {'Nullable':10s} Default")
            print(f"  {'-'*30} {'-'*30} {'-'*10} {'-'*30}")
            for c in cols:
                col_type = c.data_type
                if c.character_maximum_length:
                    col_type += f"({c.character_maximum_length})"
                default = str(c.column_default or "")[:30]
                print(f"  {c.column_name:30s} {col_type:30s} {c.is_nullable:10s} {default}")

            # Indexes
            idxs = conn.execute(
                text(
                    "SELECT i.indexname, i.indexdef "
                    "FROM pg_indexes i WHERE i.tablename = :t "
                    "ORDER BY i.indexname"
                ),
                {"t": tname},
            ).fetchall()

            if idxs:
                print(f"\n  Indexes:")
                for idx in idxs:
                    # Show the CREATE INDEX definition for clarity
                    print(f"    -> {idx.indexdef[:100]}...")
            else:
                print(f"\n  Indexes: (none)")

    engine.dispose()


if __name__ == "__main__":
    main()
