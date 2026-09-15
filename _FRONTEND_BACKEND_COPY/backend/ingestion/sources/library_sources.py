from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.logging import get_logger
from ingestion.http_client import RateLimiter

from .base import DataSource, FetchResult, SourcePayload

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════
# DataSource: finpy-tse
# ═══════════════════════════════════════════════════════════


class FinpyTseSource(DataSource):
    """Wrapper for the finpy-tse library.

    Provides: price history, intraday trades, order book, market watch,
    real/legal (حقیقی-حقوقی) data, index values, symbol list, shareholders.

    Actual function names verified from finpy-tse v1.2.x:
      Build_Market_StockList, Get_Price_History, Get_IntradayTrades_History,
      Get_IntradayOB_History, Get_MarketWatch, Get_RI_History,
      Get_ACT50_History, Get_LCI30_History, Get_INDI_History,
      Get_EWI_History, Get_CWI_History, Get_CWPI_History,
      Get_FFI_History, Get_ShareHoldersInfo
    """

    def __init__(self, max_calls: int = 5, period: float = 2.0) -> None:
        self._rate_limiter = RateLimiter(max_calls=max_calls, period=period)

    @property
    def name(self) -> str:
        return "finpy_tse"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        import finpy_tse as fpy

        ctx = context or {}
        symbol: str | None = ctx.get("symbol")
        data_type: str = ctx.get("data_type", "market_watch")

        await self._rate_limiter.acquire()
        payloads: list[SourcePayload] = []
        now = datetime.now(UTC)

        try:
            if data_type == "symbol_list":
                df = await asyncio.to_thread(
                    fpy.Build_Market_StockList,
                    bourse=ctx.get("bourse", True),
                    farabourse=ctx.get("farabourse", True),
                    payeh=ctx.get("payeh", True),
                )
                payloads.append(self._df_payload("symbol_list", df, now))

            elif data_type == "price_history" and symbol:
                df = await asyncio.to_thread(
                    fpy.Get_Price_History,
                    stock=symbol,
                    adjust_price=ctx.get("adjust_price", True),
                )
                payloads.append(self._df_payload("price_history", df, now, symbol))

            elif data_type == "intraday_trades" and symbol:
                df = await asyncio.to_thread(
                    fpy.Get_IntradayTrades_History,
                    stock=symbol,
                    start_date=ctx.get("start_date", ""),
                    end_date=ctx.get("end_date", ""),
                )
                payloads.append(self._df_payload("intraday_trades", df, now, symbol))

            elif data_type == "order_book" and symbol:
                df = await asyncio.to_thread(fpy.Get_IntradayOB_History, stock=symbol)
                payloads.append(self._df_payload("order_book", df, now, symbol))

            elif data_type == "real_individual" and symbol:
                df = await asyncio.to_thread(
                    fpy.Get_RI_History,
                    stock=symbol,
                    start_date=ctx.get("start_date", ""),
                    end_date=ctx.get("end_date", ""),
                )
                payloads.append(self._df_payload("real_individual", df, now, symbol))

            elif data_type == "shareholders" and symbol:
                df = await asyncio.to_thread(fpy.Get_ShareHoldersInfo, stock=symbol)
                payloads.append(self._df_payload("shareholders", df, now, symbol))

            elif data_type == "index_act50":
                df = await asyncio.to_thread(fpy.Get_ACT50_History)
                payloads.append(self._df_payload("index_act50", df, now))

            elif data_type == "index_lci30":
                df = await asyncio.to_thread(fpy.Get_LCI30_History)
                payloads.append(self._df_payload("index_lci30", df, now))

            elif data_type == "index_industry":
                df = await asyncio.to_thread(fpy.Get_INDI_History)
                payloads.append(self._df_payload("index_industry", df, now))

            elif data_type == "index_equal_weight":
                df = await asyncio.to_thread(fpy.Get_EWI_History)
                payloads.append(self._df_payload("index_equal_weight", df, now))

            elif data_type == "index_free_float":
                df = await asyncio.to_thread(fpy.Get_FFI_History)
                payloads.append(self._df_payload("index_free_float", df, now))

            elif data_type == "index_cwi":
                df = await asyncio.to_thread(fpy.Get_CWI_History)
                payloads.append(self._df_payload("index_cwi", df, now))

            elif data_type == "index_cwpi":
                df = await asyncio.to_thread(fpy.Get_CWPI_History)
                payloads.append(self._df_payload("index_cwpi", df, now))

            elif data_type == "market_watch":
                df = await asyncio.to_thread(fpy.Get_MarketWatch, save_excel=False)
                payloads.append(self._df_payload("market_watch", df, now))

            else:
                if symbol:
                    df = await asyncio.to_thread(fpy.Get_Price_History, stock=symbol)
                    payloads.append(self._df_payload("price_history", df, now, symbol))
                else:
                    df = await asyncio.to_thread(fpy.Get_MarketWatch, save_excel=False)
                    payloads.append(self._df_payload("market_watch", df, now))

        except ImportError:
            logger.error("finpy-tse library is not installed. Run: pip install finpy-tse")
        except Exception:
            logger.exception("finpy-tse fetch failed (type=%s, symbol=%s)", data_type, symbol)

        return FetchResult(payloads=payloads)

    def _df_payload(self, data_type: str, df: Any, now: datetime, symbol: str = "") -> SourcePayload:
        """Convert a DataFrame (or None) to a SourcePayload with JSON bytes."""
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            data = {"data_type": data_type, "symbol": symbol, "records": []}
        elif isinstance(df, pd.DataFrame):
            data = {
                "data_type": data_type,
                "symbol": symbol,
                "records": json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso")),
                "columns": list(df.columns),
                "shape": list(df.shape),
            }
        else:
            data = {"data_type": data_type, "symbol": symbol, "raw": str(df)}

        raw_bytes = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        return SourcePayload(
            source=self.name,
            endpoint=f"/finpy/{data_type}/{symbol}" if symbol else f"/finpy/{data_type}",
            raw_data=raw_bytes,
            content_type="application/json",
            fetch_time=now,
            metadata={"data_type": data_type, "symbol": symbol},
        )

    async def health_check(self) -> bool:
        try:
            import finpy_tse  # noqa: F401

            return True
        except ImportError:
            return False


# ═══════════════════════════════════════════════════════════
# DataSource: tsetmc (async library - pip install tsetmc)
# ═══════════════════════════════════════════════════════════


class TsetmcLibSource(DataSource):
    """Wrapper for the tsetmc async library.

    Uses Instrument-based request/response calls (not streaming MarketWatch)
    to fetch price history and instrument info for a given symbol.
    """

    @property
    def name(self) -> str:
        return "tsetmc_lib"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ctx = context or {}
        symbol: str | None = ctx.get("symbol")
        data_type: str = ctx.get("data_type", "instrument_info")

        payloads: list[SourcePayload] = []
        now = datetime.now(UTC)

        if not symbol:
            logger.warning("tsetmc_lib fetch requires a 'symbol' in context")
            return FetchResult(payloads=[])

        try:
            from tsetmc.instruments import Instrument

            inst = await Instrument.from_l18(symbol)

            if data_type in ("instrument_info", "all"):
                info = await inst.info()
                if info:
                    raw = json.dumps(
                        {"data_type": "instrument_info", "symbol": symbol, "info": info},
                        ensure_ascii=False,
                        default=str,
                    ).encode("utf-8")
                    payloads.append(
                        SourcePayload(
                            source=self.name,
                            endpoint=f"/tsetmc_lib/info/{symbol}",
                            raw_data=raw,
                            content_type="application/json",
                            fetch_time=now,
                            metadata={"symbol": symbol, "data_type": "instrument_info"},
                        )
                    )

            if data_type in ("price_history", "all"):
                df = await inst.price_history(adjusted=ctx.get("adjusted", True))
                if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                    records = json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))
                    raw = json.dumps(
                        {"data_type": "price_history", "symbol": symbol, "records": records},
                        ensure_ascii=False,
                        default=str,
                    ).encode("utf-8")
                    payloads.append(
                        SourcePayload(
                            source=self.name,
                            endpoint=f"/tsetmc_lib/history/{symbol}",
                            raw_data=raw,
                            content_type="application/json",
                            fetch_time=now,
                            metadata={"symbol": symbol, "data_type": "price_history"},
                        )
                    )

            if data_type in ("closing_price", "all"):
                df = await inst.daily_closing_price(n=ctx.get("days", 30))
                if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                    records = json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))
                    raw = json.dumps(
                        {"data_type": "closing_price", "symbol": symbol, "records": records},
                        ensure_ascii=False,
                        default=str,
                    ).encode("utf-8")
                    payloads.append(
                        SourcePayload(
                            source=self.name,
                            endpoint=f"/tsetmc_lib/closing/{symbol}",
                            raw_data=raw,
                            content_type="application/json",
                            fetch_time=now,
                            metadata={"symbol": symbol, "data_type": "closing_price"},
                        )
                    )

        except ImportError:
            logger.error("tsetmc library is not installed. Run: pip install tsetmc")
        except Exception:
            logger.exception("tsetmc_lib fetch failed (symbol=%s)", symbol)

        return FetchResult(payloads=payloads)

    async def health_check(self) -> bool:
        try:
            import tsetmc  # noqa: F401

            return True
        except ImportError:
            return False


# ═══════════════════════════════════════════════════════════
# DataSource: tehran-stocks (offline SQLite-based)
# ═══════════════════════════════════════════════════════════


class TehranStocksSource(DataSource):
    """Wrapper for the tehran-stocks library.

    Provides: local SQLite-backed stock data (historical prices, symbol list).
    The database is auto-initialized on first fetch.
    """

    def __init__(self) -> None:
        self._initialized = False

    @property
    def name(self) -> str:
        return "tehran_stocks"

    async def _ensure_initialized(self) -> None:
        """Initialize the tehran-stocks SQLite database if not yet done."""
        if self._initialized:
            return
        try:
            await asyncio.to_thread(self._init_db)
            self._initialized = True
        except Exception:
            logger.exception("Failed to initialize tehran_stocks database")

    def _init_db(self) -> None:
        """Download and populate the SQLite database (synchronous)."""
        from tehran_stocks import get_all_price

        get_all_price()

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        await self._ensure_initialized()

        ctx = context or {}
        symbol: str | None = ctx.get("symbol")
        data_type: str = ctx.get("data_type", "all_stocks")

        payloads: list[SourcePayload] = []
        now = datetime.now(UTC)

        try:
            if data_type == "all_stocks":
                stocks = await asyncio.to_thread(self._get_all_stocks)
                raw = json.dumps(
                    {"data_type": "all_stocks", "stocks": stocks},
                    ensure_ascii=False,
                    default=str,
                ).encode("utf-8")
                payloads.append(
                    SourcePayload(
                        source=self.name,
                        endpoint="/tehran_stocks/all",
                        raw_data=raw,
                        content_type="application/json",
                        fetch_time=now,
                    )
                )

            elif data_type == "price_history" and symbol:
                df = await asyncio.to_thread(self._get_stock_data, symbol)
                if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                    records = json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))
                    raw = json.dumps(
                        {"data_type": "price_history", "symbol": symbol, "records": records},
                        ensure_ascii=False,
                        default=str,
                    ).encode("utf-8")
                    payloads.append(
                        SourcePayload(
                            source=self.name,
                            endpoint=f"/tehran_stocks/history/{symbol}",
                            raw_data=raw,
                            content_type="application/json",
                            fetch_time=now,
                            metadata={"symbol": symbol},
                        )
                    )

        except ImportError:
            logger.error("tehran-stocks library is not installed. Run: pip install tehran-stocks")
        except Exception:
            logger.exception("tehran_stocks fetch failed (type=%s, symbol=%s)", data_type, symbol)

        return FetchResult(payloads=payloads)

    def _get_all_stocks(self) -> list[dict[str, Any]]:
        from tehran_stocks import Stocks

        stocks = Stocks.query.all()
        return [
            {"id": s.id, "name": s.name, "symbol": s.symbol, "group": s.group_name, "market": s.market} for s in stocks
        ]

    def _get_stock_data(self, symbol: str) -> Any:
        from tehran_stocks import Stocks

        stock = Stocks.query.filter_by(name=symbol).first()
        if stock is None:
            stock = Stocks.query.filter_by(symbol=symbol).first()
        if stock is not None:
            return stock.df
        return None

    async def health_check(self) -> bool:
        try:
            import tehran_stocks  # noqa: F401

            return True
        except ImportError:
            return False


# ═══════════════════════════════════════════════════════════
# DataSource: tse-utils (async)
# ═══════════════════════════════════════════════════════════


class TseUtilsSource(DataSource):
    """Wrapper for the tse-utils library (pip install tse-utils).

    Uses TsetmcScraper (the actual async API from the library) to fetch:
    order book, trade history, price adjustments, client type data,
    instrument list, and market overview.
    """

    @property
    def name(self) -> str:
        return "tse_utils"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ctx = context or {}
        symbol: str | None = ctx.get("symbol")
        tsetmc_code: str | None = ctx.get("tsetmc_code")
        data_type: str = ctx.get("data_type", "market_overview")

        payloads: list[SourcePayload] = []
        now = datetime.now(UTC)

        try:
            from tse_utils.tsetmc import TsetmcScraper

            async with TsetmcScraper() as scraper:
                if data_type == "market_overview":
                    instruments = await scraper.get_instruments_list()
                    if instruments:
                        raw = json.dumps(
                            {"data_type": "market_overview", "instruments": instruments},
                            ensure_ascii=False,
                            default=str,
                        ).encode("utf-8")
                        payloads.append(
                            SourcePayload(
                                source=self.name,
                                endpoint="/tse_utils/market_overview",
                                raw_data=raw,
                                content_type="application/json",
                                fetch_time=now,
                            )
                        )
                    return FetchResult(payloads=payloads)

                # Resolve tsetmc_code from symbol if needed
                code = tsetmc_code
                if not code and symbol:
                    results = await scraper.get_instrument_search(search_value=symbol)
                    if results and len(results) > 0:
                        code = str(results[0].get("insCode", ""))

                if not code:
                    return FetchResult(payloads=[])

                if data_type in ("order_book", "all"):
                    ob = await scraper.get_best_limits(tsetmc_code=code)
                    if ob:
                        raw = json.dumps(
                            {"data_type": "order_book", "tsetmc_code": code, "data": ob},
                            ensure_ascii=False,
                            default=str,
                        ).encode("utf-8")
                        payloads.append(
                            SourcePayload(
                                source=self.name,
                                endpoint=f"/tse_utils/orderbook/{code}",
                                raw_data=raw,
                                content_type="application/json",
                                fetch_time=now,
                                metadata={"tsetmc_code": code},
                            )
                        )

                if data_type in ("trade_history", "all"):
                    trades = await scraper.get_trade_intraday_list(tsetmc_code=code)
                    if trades:
                        raw = json.dumps(
                            {"data_type": "trade_history", "tsetmc_code": code, "data": trades},
                            ensure_ascii=False,
                            default=str,
                        ).encode("utf-8")
                        payloads.append(
                            SourcePayload(
                                source=self.name,
                                endpoint=f"/tse_utils/trades/{code}",
                                raw_data=raw,
                                content_type="application/json",
                                fetch_time=now,
                                metadata={"tsetmc_code": code},
                            )
                        )

                if data_type in ("price_adjustments", "all"):
                    adjustments = await scraper.get_price_adjustment_list(tsetmc_code=code)
                    if adjustments:
                        raw = json.dumps(
                            {"data_type": "price_adjustments", "tsetmc_code": code, "data": adjustments},
                            ensure_ascii=False,
                            default=str,
                        ).encode("utf-8")
                        payloads.append(
                            SourcePayload(
                                source=self.name,
                                endpoint=f"/tse_utils/adjustments/{code}",
                                raw_data=raw,
                                content_type="application/json",
                                fetch_time=now,
                                metadata={"tsetmc_code": code},
                            )
                        )

                if data_type in ("client_type", "all"):
                    ct = await scraper.get_client_type(tsetmc_code=code)
                    if ct:
                        raw = json.dumps(
                            {"data_type": "client_type", "tsetmc_code": code, "data": ct},
                            ensure_ascii=False,
                            default=str,
                        ).encode("utf-8")
                        payloads.append(
                            SourcePayload(
                                source=self.name,
                                endpoint=f"/tse_utils/client_type/{code}",
                                raw_data=raw,
                                content_type="application/json",
                                fetch_time=now,
                                metadata={"tsetmc_code": code},
                            )
                        )

        except ImportError:
            logger.error("tse-utils library is not installed. Run: pip install tse-utils")
        except Exception:
            logger.exception("tse_utils fetch failed (type=%s, symbol=%s)", data_type, symbol)

        return FetchResult(payloads=payloads)

    async def health_check(self) -> bool:
        try:
            import tse_utils  # noqa: F401

            return True
        except ImportError:
            return False
