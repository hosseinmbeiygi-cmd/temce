"""Run Codal Excel bulk import in background with file-based logging."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("import_run.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("codal_import")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting Codal Excel Bulk Import")
    logger.info("=" * 60)

    from bulk_importer.orchestrator import Orchestrator
    from bulk_importer.persistence import Persistence

    persistence = Persistence()
    orchestrator = Orchestrator(
        persistence=persistence,
        max_workers=3,
        batch_size=500,
    )

    stats = orchestrator.run(
        scan_root=Path(r"C:\Users\Iran\Desktop\temce\data brsapi\codal_excel_files"),
        resume=True,
        dry_run=False,
    )

    logger.info("=" * 60)
    logger.info("IMPORT COMPLETE")
    logger.info("=" * 60)
    summary = stats.summary()
    for key, val in summary.items():
        logger.info("  %-25s: %s", key, val)
