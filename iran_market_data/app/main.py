from __future__ import annotations

from iran_market_data.app.utils.logger import setup_logger

logger = setup_logger(__name__)


def main() -> None:
    """Main entry point for iran_market_data."""
    logger.info("Iran Market Data Collector")
    logger.info("Use scripts/run_tsetmc.py, run_codal.py, or run_fipiran.py")


if __name__ == "__main__":
    main()
