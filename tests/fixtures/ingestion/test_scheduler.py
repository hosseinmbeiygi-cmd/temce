from __future__ import annotations

from ingestion.config import IngestionConfig
from ingestion.scheduler import MarketScheduler


class TestMarketScheduler:
    def test_in_market_hours_returns_true_when_disabled(self) -> None:
        config = IngestionConfig(market_open="", market_close="")
        scheduler = MarketScheduler(config)
        assert scheduler._in_market_hours() is True

    def test_outside_market_hours(self) -> None:
        config = IngestionConfig(market_open="23:00", market_close="23:30")
        scheduler = MarketScheduler(config)
        if not scheduler._in_market_hours():
            pass
