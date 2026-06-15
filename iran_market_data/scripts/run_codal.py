from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from iran_market_data.app.collectors.codal import CodalCollector
from iran_market_data.app.utils.logger import setup_logger

logger = setup_logger("run_codal")


def main() -> None:
    """Run Codal data collection."""
    collector = CodalCollector()
    result = collector.search_announcements(
        search_url="PUT_CODAL_SEARCH_URL_HERE",
    )

    logger.info("Collection complete!")
    logger.info("Found %d announcements", len(result["announcements"]))
    logger.info("Raw file saved at: %s", result["raw_path"])


if __name__ == "__main__":
    main()
