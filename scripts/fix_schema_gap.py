"""
Fix the schema gap between the live database and the ORM models.

The alembic chain was broken (0021 referenced ``"0020"`` while the real
revision is ``"0020_brsapi_snapshots_unique"``) so migrations 0009→0021
never ran on this database. This script applies **only the missing
objects** idempotently:

  Tables created (if missing):
    - brsapi_codal_attachments      (migration 0019 — CodalAttachmentDownloadJob)
    - queue_analysis_results        (migration 0014)
    - option_contracts / option_snapshots / option_trades
    - open_interest_history / volatility_surface / corporate_actions
      (models/option.py)

  Columns / constraints:
    - brsapi_codal_announcements.content_hash VARCHAR(64) + unique (0018)
    - news_articles.published_at widened VARCHAR(30) → VARCHAR(40) (0021)

Afterwards the DB matches Alembic head — run ``alembic stamp head``.

Usage:
    python scripts/fix_schema_gap.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

# Import models so their Table objects register on the metadata
from brsapi.models.base import BrsApiBase  # noqa: F401,E402
from brsapi.models.codal import CodalAttachmentModel  # noqa: F401,E402
from core.config import settings  # noqa: E402
from models.base import Base  # noqa: F401,E402
from models.option import (  # noqa: F401,E402
    CorporateActionModel,
    OpenInterestHistoryModel,
    OptionContractModel,
    OptionSnapshotModel,
    OptionTradeModel,
    VolatilitySurfaceModel,
)
from models.queue_analysis import QueueAnalysisResult  # noqa: F401,E402

TABLES = [
    QueueAnalysisResult.__table__,
    OptionContractModel.__table__,
    OptionSnapshotModel.__table__,
    OptionTradeModel.__table__,
    OpenInterestHistoryModel.__table__,
    VolatilitySurfaceModel.__table__,
    CorporateActionModel.__table__,
    CodalAttachmentModel.__table__,
]


def main() -> int:
    url = settings.database_url_async.replace("+asyncpg", "+psycopg2")
    engine = create_engine(url)
    errors: list[str] = []

    with engine.begin() as conn:
        inspector = inspect(conn)
        print("── Tables ───────────────────────────────")
        for table in TABLES:
            if inspector.has_table(table.name):
                print(f"  ✔ {table.name} — already exists")
                continue
            try:
                table.create(conn)
                print(f"  + {table.name} — created")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{table.name}: {exc}")
                print(f"  ✖ {table.name} — FAILED: {exc}")

        print("── brsapi_codal_announcements.content_hash ─")
        has_col = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='brsapi_codal_announcements' AND column_name='content_hash'"
            )
        ).scalar()
        if not has_col:
            conn.execute(
                text("ALTER TABLE brsapi_codal_announcements ADD COLUMN content_hash VARCHAR(64)")
            )
            print("  + content_hash column — added")
        else:
            print("  ✔ content_hash column — exists")

        has_uniq = conn.execute(
            text(
                "SELECT 1 FROM pg_constraint WHERE conname='uq_codal_content_hash' "
                "AND conrelid='brsapi_codal_announcements'::regclass"
            )
        ).scalar()
        if not has_uniq:
            conn.execute(
                text(
                    "ALTER TABLE brsapi_codal_announcements "
                    "ADD CONSTRAINT uq_codal_content_hash UNIQUE (content_hash)"
                )
            )
            print("  + uq_codal_content_hash — added")
        else:
            print("  ✔ uq_codal_content_hash — exists")

        print("── news_articles.published_at width ─────")
        width = conn.execute(
            text(
                "SELECT character_maximum_length FROM information_schema.columns "
                "WHERE table_name='news_articles' AND column_name='published_at'"
            )
        ).scalar()
        if width is None:
            errors.append("news_articles.published_at: column not found")
        elif width < 40:
            conn.execute(
                text("ALTER TABLE news_articles ALTER COLUMN published_at TYPE VARCHAR(40)")
            )
            print(f"  + published_at widened {width} → 40")
        else:
            print(f"  ✔ published_at already {width} chars")

        print("── funds.updated_at ─────────────────────")
        has_funds_updated = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='funds' AND column_name='updated_at'"
            )
        ).scalar()
        if not has_funds_updated:
            conn.execute(text("ALTER TABLE funds ADD COLUMN updated_at TIMESTAMP"))
            print("  + funds.updated_at column — added")
        else:
            print("  ✔ funds.updated_at column — exists")

    engine.dispose()

    if errors:
        print("\n── ERRORS ───────────────────────────────")
        for err in errors:
            print("  ✖", err)
        return 1

    print("\n✅ Schema gap closed. Next: alembic stamp head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
