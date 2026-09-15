from __future__ import annotations

from typing import Any

from core.logging import get_logger

from .config import IngestionConfig
from .http_client import HttpClient
from .lake import RawDataLake
from .parser import ParserRegistry
from .parser.library_parsers import (
    FinpyTseParser,
    TehranStocksParser,
    TsetmcLibParser,
    TseUtilsParser,
)
from .parser.market_data import CanonicalMarketDataParser
from .parser.tsetmc_parsers import (
    TsetmcMarketWatchParser,
    TsetmcOrderBookParser,
    TsetmcTradeParser,
)
from .replay import ReplayEngine
from .scheduler import MarketScheduler
from .sources.codal import CodalSource
from .sources.crypto import NobitexSource, RamzinexSource, WallexSource
from .sources.derivatives import TsetmcFutureSource, TsetmcOptionSource
from .sources.energy import IMEEnergySource
from .sources.ifb import IFBSource
from .sources.library_sources import (
    FinpyTseSource,
    TehranStocksSource,
    TsetmcLibSource,
    TseUtilsSource,
)
from .sources.tsetmc import (
    TsetmcInstrumentSource,
    TsetmcMarketWatchSource,
    TsetmcOrderBookSource,
    TsetmcTradeSource,
)
from .storage import StorageLayer
from .storage.dedup import DeduplicationEngine
from .worker import IngestionWorker

logger = get_logger(__name__)


class IngestionEngine:
    def __init__(self, config: IngestionConfig | None = None, db: Any = None, redis: Any = None) -> None:
        self.config = config or IngestionConfig()
        self._db = db
        self._redis = redis
        self._http: HttpClient | None = None
        self._lake: RawDataLake | None = None
        self._scheduler: MarketScheduler | None = None
        self._worker: IngestionWorker | None = None
        self._parsers = ParserRegistry()

    async def start(self) -> None:
        logger.info("Starting IngestionEngine...")

        self._http = HttpClient(self.config)
        await self._http.start()

        self._lake = RawDataLake(self.config)
        await self._lake.start()

        self._parsers.register(TsetmcMarketWatchParser())
        self._parsers.register(TsetmcTradeParser())
        self._parsers.register(TsetmcOrderBookParser())
        self._parsers.register(FinpyTseParser())
        self._parsers.register(TsetmcLibParser())
        self._parsers.register(TehranStocksParser())
        self._parsers.register(TseUtilsParser())
        self._parsers.register(CanonicalMarketDataParser())

        dedup = DeduplicationEngine(self._redis, self.config.dedup_window_minutes) if self._redis else None
        storage = StorageLayer(self._db) if self._db else None

        from .identity import IdentityResolver

        identity = IdentityResolver(self._db) if self._db else None

        # Pre-create instrument source so it's shared between worker DI and source registration
        tsetmc_instruments = TsetmcInstrumentSource(self._http)

        self._worker = IngestionWorker(
            config=self.config,
            http=self._http,
            lake=self._lake,
            parsers=self._parsers,
            dedup=dedup,
            identity_resolver=identity,
            storage=storage,
            instrument_source=tsetmc_instruments,
        )

        self._register_sources(tsetmc_instruments=tsetmc_instruments)
        self._scheduler = MarketScheduler(self.config)
        self._scheduler.on_tick(self._worker.ingest_all)
        await self._scheduler.start()

        logger.info("IngestionEngine started")

    async def stop(self) -> None:
        logger.info("Stopping IngestionEngine...")
        if self._scheduler:
            await self._scheduler.stop()
        if self._http:
            await self._http.stop()
        logger.info("IngestionEngine stopped")

    def _register_sources(self, tsetmc_instruments: TsetmcInstrumentSource | None = None) -> None:
        assert self._http is not None
        assert self._worker is not None

        sources: dict[str, Any] = {
            "tsetmc_marketwatch": TsetmcMarketWatchSource(self._http),
            "tsetmc_trades": TsetmcTradeSource(self._http),
            "tsetmc_orderbook": TsetmcOrderBookSource(self._http),
            "ifb": IFBSource(self._http),
            "ime_energy": IMEEnergySource(self._http),
            "tsetmc_options": TsetmcOptionSource(self._http),
            "tsetmc_futures": TsetmcFutureSource(self._http),
            "codal": CodalSource(self._http),
            "finpy_tse": FinpyTseSource(),
            "tsetmc_lib": TsetmcLibSource(),
            "tehran_stocks": TehranStocksSource(),
            "tse_utils": TseUtilsSource(),
            "nobitex_usdt": NobitexSource(self._http),
            "wallex_usdt": WallexSource(self._http),
            "ramzinex_usdt": RamzinexSource(self._http),
        }
        # tsetmc_instruments is already passed as instrument_source to the worker,
        # so skip registering it as a regular source to avoid duplicate HTTP requests.
        for name in self.config.enabled_sources:
            if name.value in sources:
                self._worker.register_source(sources[name.value])
                logger.info("Registered source: %s", name.value)

    @property
    def replay(self) -> ReplayEngine:
        assert self._lake is not None
        return ReplayEngine(
            lake=self._lake,
            parser_registry=self._parsers,
            storage=StorageLayer(self._db) if self._db else None,
        )


async def run_ingestion() -> None:
    from ingestion.db.session import DatabaseSession

    config = IngestionConfig()
    db = DatabaseSession(config.db_dsn)
    await db.start(pool_size=config.db_pool_size, max_overflow=config.db_max_overflow)

    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(config.redis_url)

    engine = IngestionEngine(config=config, db=db, redis=redis_client)
    try:
        await engine.start()
        import asyncio

        forever = asyncio.get_event_loop().create_future()
        await forever
    finally:
        await engine.stop()
        await db.stop()
        await redis_client.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_ingestion())
