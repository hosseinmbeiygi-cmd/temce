from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from iran_market_data.app.collectors.tsetmc import TsetmcCollector
from iran_market_data.app.utils.logger import setup_logger

logger = setup_logger("run_tsetmc")


def main() -> None:
    """Run TSETMC data collection."""
    collector = TsetmcCollector()
    result = collector.collect_market_watch()

    logger.info("Collection complete!")
    logger.info("Raw file saved at: %s", result["raw_path"])


if __name__ == "__main__":
    main()
