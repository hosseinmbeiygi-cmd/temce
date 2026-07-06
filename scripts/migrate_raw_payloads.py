#!/usr/bin/env python
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


async def migrate_payloads(source_dir: str, target_dir: str) -> int:
    src = Path(source_dir)
    tgt = Path(target_dir)
    tgt.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in src.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["_migrated_at"] = datetime.now(UTC).isoformat()
                data["_migration_version"] = "1.0"
            target_file = tgt / f.name
            target_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            count += 1
            logger.debug("Migrated: %s", f.name)
        except Exception as e:
            logger.error("Failed to migrate %s: %s", f.name, e)
    return count


async def main() -> None:
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else str(settings.data_path / "raw" / "legacy")
    target = sys.argv[2] if len(sys.argv) > 2 else str(settings.data_path / "raw" / "migrated")
    count = await migrate_payloads(source, target)
    logger.info("Migration complete: %d files migrated", count)


if __name__ == "__main__":
    asyncio.run(main())
