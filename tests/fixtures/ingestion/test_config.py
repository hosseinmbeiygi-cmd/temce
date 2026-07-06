from __future__ import annotations

from ingestion.config import IngestionConfig, SourceType


class TestIngestionConfig:
    def test_default_config_has_all_sources(self) -> None:
        config = IngestionConfig()
        assert SourceType.TSETMC_MARKETWATCH in config.enabled_sources
        assert SourceType.TSETMC_TRADES in config.enabled_sources
        assert SourceType.IFB in config.enabled_sources
        assert SourceType.CODAL in config.enabled_sources

    def test_market_hours_disabled_when_empty(self) -> None:
        config = IngestionConfig(market_open="", market_close="")
        assert config.market_hours_enabled is False

    def test_market_hours_enabled_by_default(self) -> None:
        config = IngestionConfig()
        assert config.market_hours_enabled is True

    def test_worker_count_bounds(self) -> None:
        config = IngestionConfig(worker_count=1)
        assert config.worker_count == 1
        config = IngestionConfig(worker_count=32)
        assert config.worker_count == 32

    def test_dedup_window_default(self) -> None:
        config = IngestionConfig()
        assert config.dedup_window_minutes == 60

