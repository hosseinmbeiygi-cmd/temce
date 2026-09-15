from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.market_data.quote import Quote
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.tsetmc_client import TsetmcClient

logger = get_logger(__name__)


class QuoteService:
    def __init__(
        self,
        quote_repo: QuoteRepository | None = None,
        instrument_repo: InstrumentRepository | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.quote_repo = quote_repo or QuoteRepository(session=session)
        self.instrument_repo = instrument_repo or InstrumentRepository(session=session)
        self.tsetmc = TsetmcClient()

    # =============================
    # REALTIME INGESTION
    # =============================

    async def ingest_realtime(self, symbol: str, source: str = "tsetmc") -> Result[Quote]:
        """
        Fetch realtime data from TSETMC and save it.
        """

        inst_result = await self.instrument_repo.get_by_symbol(symbol)
        if not inst_result.success:
            return Result.fail(f"Instrument {symbol} not found")

        instrument = inst_result.value

        if not instrument.ins_code:
            return Result.fail(f"Instrument {symbol} has no ins_code")

        api_result = await self.tsetmc.get_closing_price_info(instrument.ins_code)
        if not api_result.success:
            return api_result

        data = api_result.value

        try:
            quote = Quote(
                id=new_id("quote"),
                instrument_id=instrument.id,
                symbol=symbol,
                price_close=float(data.get("pClosing", 0)),
                price_last=float(data.get("pDrCotVal", 0)),
                price_open=float(data.get("pOpen", 0)),
                price_high=float(data.get("pHigh", 0)),
                price_low=float(data.get("pLow", 0)),
                price_change=float(data.get("priceChange", 0)),
                price_change_pct=float(data.get("priceChangePercent", 0)),
                volume=int(data.get("zTotTran", 0)),
                value=float(data.get("qTotTran5J", 0)),
                trade_count=int(data.get("zTotTran", 0)),
                price_yesterday=float(data.get("priceYesterday", 0)),
                date=str(data.get("dEven", "")),
                time=str(data.get("hEven", "")),
                timeframe="1d",
                data_source=source,
            )

            save_result = await self.quote_repo.save(quote)
            return save_result

        except Exception as e:
            logger.exception("Failed to map TSETMC data")
            return Result.fail(str(e))

    # =============================
    # HISTORICAL PLACEHOLDER
    # =============================

    async def ingest_historical(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> Result[int]:
        """
        Historical ingestion not implemented yet.
        """
        return Result.fail("Historical ingestion not implemented yet")

    # =============================
    # READ METHODS
    # =============================

    async def get_latest(self, instrument_id: str) -> Result[Quote]:
        return await self.quote_repo.get_latest(instrument_id)

    async def get_history(
        self,
        instrument_id: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
    ) -> Result[list[Quote]]:
        return await self.quote_repo.get_range(
            instrument_id,
            start_date,
            end_date,
            timeframe,
        )

    async def save_quote(self, quote: Quote) -> Result[Quote]:
        return await self.quote_repo.save(quote)

    async def save_quotes(self, quotes: list[Quote]) -> Result[int]:
        count = 0
        for quote in quotes:
            result = await self.quote_repo.save(quote)
            if result.success:
                count += 1
        return Result.ok(count)

    async def get_market_summary(self) -> Result[dict[str, Any]]:
        return await self.quote_repo.get_market_summary()
