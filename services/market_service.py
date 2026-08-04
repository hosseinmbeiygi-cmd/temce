from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.result import Result
from domain.market_data.quote import Quote
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository

logger = get_logger(__name__)


class MarketService:
    def __init__(
        self,
        quote_repo: QuoteRepository | None = None,
        instrument_repo: InstrumentRepository | None = None,
        brsapi_query_service: Any | None = None,
        brsapi_client: Any = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.quote_repo = quote_repo or QuoteRepository(session=session)
        self.instrument_repo = instrument_repo or InstrumentRepository(session=session)
        self._brsapi = brsapi_query_service
        self._client = brsapi_client

    async def get_overview(self) -> Result[dict[str, Any]]:
        # Try BrsApi snapshots first (realtime data)
        if self._brsapi:
            try:
                snapshots = await self._brsapi.get_latest_snapshots(limit=500)
                if snapshots:
                    # Compute market stats from snapshots
                    total = len(snapshots)
                    gainers = sum(1 for s in snapshots if (s.get("price_last_change_pct") or 0) > 0)
                    losers = sum(1 for s in snapshots if (s.get("price_last_change_pct") or 0) < 0)
                    total_value = sum(s.get("trade_value") or 0 for s in snapshots)
                    total_volume = sum(s.get("trade_volume") or 0 for s in snapshots)
                    avg_change = sum(s.get("price_last_change_pct") or 0 for s in snapshots) / total if total else 0

                    return Result.ok({
                        "total_instruments": total,
                        "total_quotes": total,
                        "gainers": gainers,
                        "losers": losers,
                        "unchanged": total - gainers - losers,
                        "total_value": total_value,
                        "total_volume": total_volume,
                        "avg_change_pct": round(avg_change, 2),
                    })
            except Exception:
                logger.exception("Failed to get overview from BrsApi")

        # Fallback to quote repo
        return await self.quote_repo.get_market_summary()

    async def get_index_values(self) -> Result[list[dict[str, Any]]]:
        # Try local DB first
        if self._brsapi:
            try:
                indices = await self._brsapi.get_latest_indices()
                if indices:
                    return Result.ok(indices)
            except Exception:
                logger.exception("Failed to fetch index values from BrsApi")
        # Live fallback: fetch directly from BrsApi API
        if self._client:
            try:
                indices = await self._fetch_live_indices()
                if indices:
                    return Result.ok(indices)
            except Exception:
                logger.exception("Live fetch for indices failed")
        return Result.ok([])

    async def _fetch_live_indices(self) -> list[dict[str, Any]]:
        """Fetch indices directly from BrsApi API when DB is empty."""
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import TsetmcParser

        all_indices: list[dict[str, Any]] = []
        for idx_type in ("1", "2"):  # TSE, Farabours
            result = await self._client.fetch(
                BrsApiEndpoints.INDEX,
                params={"type": idx_type},
            )
            if result.success and result.value and result.value.data:
                parsed = TsetmcParser.parse_index(result.value.data)
                if isinstance(parsed, list):
                    all_indices.extend(parsed)
        return all_indices

    async def get_top_gainers(self, limit: int = 10) -> Result[list[Quote]]:
        return await self.quote_repo.get_top_gainers(limit)

    async def get_top_losers(self, limit: int = 10) -> Result[list[Quote]]:
        return await self.quote_repo.get_top_losers(limit)

    async def get_most_active(self, limit: int = 10) -> Result[list[Quote]]:
        return await self.quote_repo.get_most_active(limit)

    async def get_sector_summary(self) -> Result[list[dict[str, Any]]]:
        if self._brsapi:
            try:
                snapshots = await self._brsapi.get_latest_snapshots(limit=200)
                if snapshots:
                    return Result.ok(self._build_sectors(snapshots))
            except Exception:
                logger.exception("Failed to build sector summary")
        # Live fallback
        if self._client:
            try:
                snapshots = await self._fetch_live_snapshots()
                if snapshots:
                    return Result.ok(self._build_sectors(snapshots))
            except Exception:
                logger.exception("Live fetch for sector summary failed")
        return Result.ok([])

    @staticmethod
    def _build_sectors(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sectors: dict[str, dict[str, Any]] = {}
        for s in snapshots:
            sector = s.get("sector_name") or s.get("industry", "سایر")
            if sector not in sectors:
                sectors[sector] = {"name": sector, "count": 0, "total_value": 0, "avg_change": 0}
            sectors[sector]["count"] += 1
            sectors[sector]["total_value"] += s.get("trade_value", 0) or 0
        result = list(sectors.values())
        for sec in result:
            sec["avg_change"] = 0
        return result

    async def _fetch_live_snapshots(self) -> list[dict[str, Any]]:
        """Fetch all-symbol snapshots directly from BrsApi API."""
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import TsetmcParser

        result = await self._client.fetch(
            BrsApiEndpoints.ALL_SYMBOLS,
            params={"type": "1"},
        )
        if result.success and result.value and result.value.data:
            parsed = TsetmcParser.parse_all_symbols(result.value.data)
            if isinstance(parsed, list):
                return parsed
        return []

    async def _get_historical_from_quotes_table(
        self, symbol: str, start_date: str, end_date: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        """
        Fallback: read historical daily data from the core ``quotes`` table
        (QuoteModel / QuoteRepository) when BrsApi tables are empty.

        Resolves the symbol to an instrument_id first, then queries
        QuoteRepository for the matching date range.
        """
        try:
            # 1. Resolve symbol -> instrument_id
            inst_result = await self.instrument_repo.get_by_symbol(symbol)
            if not inst_result.success or not inst_result.value:
                logger.warning("Could not resolve symbol '%s' in instruments table", symbol)
                return []
            instrument_id = inst_result.value.id

            # 2. Query quotes from the core table
            from datetime import date as date_type
            start_dt = date_type.fromisoformat(start_date)
            end_dt = date_type.fromisoformat(end_date)

            quotes_result = await self.quote_repo.get_range(
                instrument_id, start_dt, end_dt, timeframe="1d"
            )
            if not quotes_result.success or not quotes_result.value:
                return []

            # 3. Convert domain Quote objects to plain dicts
            records = []
            for q in quotes_result.value:
                records.append({
                    "date": q.date or "",
                    "symbol": q.symbol or symbol,
                    "price_first": q.price_first or q.price_open or 0,
                    "price_last": q.price_last or q.price_close or 0,
                    "price_close": q.price_close or 0,
                    "price_max": q.price_high or q.price_max or 0,
                    "price_min": q.price_low or q.price_min or 0,
                    "price_yesterday": q.price_yesterday or 0,
                    "price_last_change": q.price_change or 0,
                    "price_last_change_pct": q.price_change_pct or 0,
                    "trade_volume": q.volume or 0,
                    "trade_value": q.value or 0,
                    "trade_count": q.trade_count or 0,
                })
            # Sort descending (newest first), consistent with BrsApiQueryService
            records.sort(key=lambda r: r["date"], reverse=True)
            return records[:limit]
        except Exception:
            logger.exception("Failed to fetch historical data from quotes table for %s", symbol)
            return []

    async def get_historical_quotes(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> Result[list[dict[str, Any]]]:
        # ── Step 1: Try BrsApiQueryService (BrsApi historical daily table) ──
        if self._brsapi:
            try:
                data = await self._brsapi.get_historical_daily(symbol, limit=500)
                filtered = [d for d in data if d.get("date", "") >= start_date and d.get("date", "") <= end_date]
                if filtered:
                    return Result.ok(filtered)
            except Exception:
                logger.exception("Failed to fetch historical quotes from BrsApi DB")
        # ── Step 2: Try core quotes table (QuoteModel) ──
        try:
            records = await self._get_historical_from_quotes_table(symbol, start_date, end_date, limit=500)
            if records:
                return Result.ok(records)
        except Exception:
            logger.exception("Failed to fetch historical quotes from quotes table")
        # ── Step 3: Live BrsApi API fallback with l18 resolution ──
        if self._client:
            try:
                live_data = await self._fetch_live_history(symbol, limit=500)
                if live_data:
                    filtered = [d for d in live_data if d.get("date", "") >= start_date and d.get("date", "") <= end_date]
                    if filtered:
                        return Result.ok(filtered)
            except Exception:
                logger.exception("Live fetch for historical quotes failed")
        return Result.ok([])

    async def get_ohlcv(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "1d",
    ) -> Result[list[dict[str, Any]]]:
        # ── Step 1: Try BrsApiQueryService (BrsApi historical daily table) ──
        if self._brsapi:
            try:
                raw = await self._brsapi.get_historical_daily(symbol, limit=500)
                filtered = [d for d in raw if d.get("date", "") >= start_date and d.get("date", "") <= end_date]
                ohlcv = [self._to_ohlcv(d) for d in filtered]
                if ohlcv:
                    return Result.ok(ohlcv)
            except Exception:
                logger.exception("Failed to fetch OHLCV data from BrsApi DB")
        # ── Step 2: Try core quotes table (QuoteModel) ──
        try:
            records = await self._get_historical_from_quotes_table(symbol, start_date, end_date, limit=500)
            if records:
                ohlcv = [self._to_ohlcv(r) for r in records]
                if ohlcv:
                    return Result.ok(ohlcv)
        except Exception:
            logger.exception("Failed to fetch OHLCV from quotes table")
        # ── Step 3: Live BrsApi API fallback with l18 resolution ──
        if self._client:
            try:
                live_data = await self._fetch_live_history(symbol, limit=500)
                if live_data:
                    filtered = [d for d in live_data if d.get("date", "") >= start_date and d.get("date", "") <= end_date]
                    ohlcv = [self._to_ohlcv(d) for d in filtered]
                    if ohlcv:
                        return Result.ok(ohlcv)
            except Exception:
                logger.exception("Live fetch for OHLCV failed")
        return Result.ok([])

    @staticmethod
    def _to_ohlcv(d: dict[str, Any]) -> dict[str, Any]:
        return {
            "date": d.get("date"),
            "open": d.get("price_first"),
            "high": d.get("price_max"),
            "low": d.get("price_min"),
            "close": d.get("price_last"),
            "volume": d.get("trade_volume"),
        }

    async def calculate_indicator(
        self,
        symbol: str,
        indicator: str,
        params: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any]]:
        """Compute a technical indicator for a symbol.

        Fetches historical data (DB-first, then live BrsApi API with l18 resolution),
        then computes the requested indicator (sma, ema, rsi, macd, bollinger).

        Returns a dict with ``dates`` and ``values`` where ``values`` is either a
        ``list[float]`` (sma/ema/rsi) or a ``dict[str, list[float]]`` with named
        sub-series (macd: macd/signal/histogram; bollinger: upper/middle/lower).
        """
        params = params or {}
        # ── Step 1: Fetch historical data ──
        raw: list[dict[str, Any]] = []
        if self._brsapi:
            try:
                raw = await self._brsapi.get_historical_daily(symbol, limit=500)
            except Exception:
                logger.exception("DB fetch for indicator failed")
        if not raw and self._client:
            try:
                raw = await self._fetch_live_history(symbol, limit=500)
            except Exception:
                logger.exception("Live fetch for indicator failed")
        if not raw:
            return Result.fail(f"No historical data for {symbol}")
        # ── Step 2: Extract OHLCV arrays (chronological order) ──
        sorted_data = sorted(raw, key=lambda d: d.get("date", ""))
        closes = [d.get("price_last", 0) or 0 for d in sorted_data]
        highs = [d.get("price_max", 0) or d.get("price_first", 0) or 0 for d in sorted_data]
        lows = [d.get("price_min", 0) or d.get("price_first", 0) or 0 for d in sorted_data]
        volumes = [d.get("trade_volume", 0) or 0 for d in sorted_data]
        dates = [d.get("date", "") for d in sorted_data]
        # ── Step 3: Compute indicator ──
        try:
            result = self._compute_indicator(indicator, closes, params, highs, lows, volumes)
            # Align dates: single-line uses list length, multi-line uses first sub-series
            if isinstance(result, list):
                data_len = len(result)
            else:
                first_series = next(iter(result.values()), []) if result else []
                data_len = len(first_series)
            return Result.ok({
                "symbol": symbol,
                "indicator": indicator,
                "params": params,
                "dates": dates[-data_len:] if data_len else dates,
                "values": result,
            })
        except ValueError as e:
            return Result.fail(str(e))

    @staticmethod
    def _compute_indicator(
        indicator: str,
        closes: list[float],
        params: dict[str, Any],
        highs: list[float] | None = None,
        lows: list[float] | None = None,
        volumes: list[float] | None = None,
    ) -> list[float] | dict[str, list[float]]:
        """Compute a technical indicator from price data.

        Returns a ``list[float]`` for single-line indicators or a
        ``dict[str, list[float]]`` for multi-line ones (macd, bollinger,
        stochastic, ichimoku).
        """
        period: int = int(params.get("period", 14))
        if indicator == "sma":
            return MarketService._sma(closes, period)
        if indicator == "ema":
            return MarketService._ema(closes, period)
        if indicator == "rsi":
            return MarketService._rsi(closes, period)
        if indicator == "macd":
            fast = int(params.get("fast", 12))
            slow = int(params.get("slow", 26))
            signal_p = int(params.get("signal", 9))
            macd_line, signal_line, histogram = MarketService._macd(closes, fast, slow, signal_p)
            return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
        if indicator == "bollinger":
            stddev = float(params.get("stddev", 2))
            upper, middle, lower = MarketService._bollinger(closes, period, stddev)
            return {"upper": upper, "middle": middle, "lower": lower}
        if indicator == "stochastic":
            k_smooth = int(params.get("k_smooth", 3))
            d_smooth = int(params.get("d_smooth", 3))
            k_line, d_line = MarketService._stochastic(highs or [], lows or [], closes, period, k_smooth, d_smooth)
            return {"k": k_line, "d": d_line}
        if indicator == "atr":
            return MarketService._atr(highs or [], lows or [], closes, period)
        if indicator == "obv":
            return MarketService._obv(closes, volumes or [])
        if indicator == "williams_r":
            return MarketService._williams_r(highs or [], lows or [], closes, period)
        if indicator == "ichimoku":
            tenkan_p = int(params.get("tenkan", 9))
            kijun_p = int(params.get("kijun", 26))
            senkou_b_p = int(params.get("senkou_b", 52))
            tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(
                highs or [], lows or [], closes, tenkan_p, kijun_p, senkou_b_p,
            )
            return {"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a, "senkou_b": senkou_b, "chikou": chikou}
        raise ValueError(f"Unknown indicator: {indicator}")

    # ── Indicator implementations ───────────────────

    @staticmethod
    def _sma(data: list[float], period: int) -> list[float]:
        if len(data) < period:
            return []
        result = []
        for i in range(period - 1, len(data)):
            result.append(sum(data[i - period + 1:i + 1]) / period)
        return result

    @staticmethod
    def _ema(data: list[float], period: int) -> list[float]:
        if len(data) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        for price in data[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema

    @staticmethod
    def _rsi(data: list[float], period: int) -> list[float]:
        if len(data) < period + 1:
            return []
        gains, losses = [], []
        for i in range(1, len(data)):
            delta = data[i] - data[i - 1]
            gains.append(delta if delta > 0 else 0)
            losses.append(-delta if delta < 0 else 0)
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        rsi_vals = [100 - (100 / (1 + avg_gain / avg_loss))] if avg_loss != 0 else [100]
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi_vals.append(100)
            else:
                rsi_vals.append(100 - (100 / (1 + avg_gain / avg_loss)))
        return rsi_vals

    @staticmethod
    def _macd(
        data: list[float], fast: int, slow: int, signal: int
    ) -> tuple[list[float], list[float], list[float]]:
        ema_fast = MarketService._ema(data, fast)
        ema_slow = MarketService._ema(data, slow)
        # Align: both start from the same point
        offset = slow - fast
        macd_line = [ema_fast[i + offset] - ema_slow[i] for i in range(len(ema_slow))]
        signal_line = MarketService._ema(macd_line, signal)
        # Align histogram with signal line
        hist = [macd_line[i] - signal_line[i] for i in range(min(len(macd_line), len(signal_line)))]
        return macd_line, signal_line, hist

    @staticmethod
    def _bollinger(
        data: list[float], period: int, stddev: float
    ) -> tuple[list[float], list[float], list[float]]:
        """Bollinger Bands — numpy vectorised (O(n) via E[X²]−E[X]²)."""
        n = len(data)
        if n < period:
            return [], [], []

        arr = np.asarray(data, dtype=np.float64)
        kernel = np.ones(period, dtype=np.float64) / period

        # Rolling mean (SMA) via convolution
        middle = np.convolve(arr, kernel, mode="valid")

        # Rolling variance: Var(X) = E[X²] − E[X]²
        arr_sq = arr * arr
        mean_sq = np.convolve(arr_sq, kernel, mode="valid")
        variance = mean_sq - middle * middle
        # Clip tiny negative values from floating-point error
        np.maximum(variance, 0.0, out=variance)
        stdev_arr = np.sqrt(variance)

        upper = middle + stddev * stdev_arr
        lower = middle - stddev * stdev_arr

        return upper.tolist(), middle.tolist(), lower.tolist()

    # ── Stochastic %K / %D ────────────────────────────

    @staticmethod
    def _stochastic(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
        k_smooth: int = 3,
        d_smooth: int = 3,
    ) -> tuple[list[float], list[float]]:
        """Stochastic Oscillator: returns (raw %K, %D)."""
        n = min(len(highs), len(lows), len(closes))
        if n < period:
            return [], []
        raw_k: list[float] = []
        for i in range(period - 1, n):
            window_high = max(highs[i - period + 1:i + 1])
            window_low = min(lows[i - period + 1:i + 1])
            if window_high == window_low:
                raw_k.append(50.0)
            else:
                raw_k.append(((closes[i] - window_low) / (window_high - window_low)) * 100.0)
        # Smooth %K (SMA of raw %K)
        k_line = MarketService._sma(raw_k, k_smooth)
        # %D = SMA of smoothed %K
        d_line = MarketService._sma(k_line, d_smooth)
        return k_line, d_line

    # ── ATR (Average True Range) ──────────────────────

    @staticmethod
    def _atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> list[float]:
        """Average True Range — volatility indicator."""
        n = min(len(highs), len(lows), len(closes))
        if n < period + 1:
            return []
        # Compute True Range for each bar
        true_ranges: list[float] = []
        for i in range(1, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)
        # First ATR = SMA of initial period
        atr = [sum(true_ranges[:period]) / period]
        # Wilder's smoothing for subsequent values
        for i in range(period, len(true_ranges)):
            atr.append((atr[-1] * (period - 1) + true_ranges[i]) / period)
        return atr

    # ── OBV (On-Balance Volume) ───────────────────────

    @staticmethod
    def _obv(closes: list[float], volumes: list[float]) -> list[float]:
        """On-Balance Volume — cumulative volume flow indicator."""
        n = min(len(closes), len(volumes))
        if n == 0:
            return []
        obv = [float(volumes[0])]
        for i in range(1, n):
            if closes[i] > closes[i - 1]:
                obv.append(obv[-1] + volumes[i])
            elif closes[i] < closes[i - 1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])
        return obv

    # ── Williams %R ───────────────────────────────────

    @staticmethod
    def _williams_r(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> list[float]:
        """Williams %R — momentum oscillator (inverse of Fast Stochastic)."""
        n = min(len(highs), len(lows), len(closes))
        if n < period:
            return []
        result: list[float] = []
        for i in range(period - 1, n):
            window_high = max(highs[i - period + 1:i + 1])
            window_low = min(lows[i - period + 1:i + 1])
            if window_high == window_low:
                result.append(-50.0)
            else:
                result.append(((window_high - closes[i]) / (window_high - window_low)) * -100.0)
        return result

    # ── Ichimoku Kinko Hyo ────────────────────────────

    @staticmethod
    def _ichimoku(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
    ) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
        """Ichimoku Kinko Hyo — returns (tenkan, kijun, senkou_a, senkou_b, chikou)."""
        n = min(len(highs), len(lows), len(closes))
        max_period = max(tenkan_period, kijun_period, senkou_b_period)
        if n < max_period:
            return [], [], [], [], []

        def _mid(period: int) -> list[float]:
            """Tenkan-sen / Kijun-sen style mid-line."""
            out: list[float] = []
            for i in range(period - 1, n):
                hh = max(highs[i - period + 1:i + 1])
                ll = min(lows[i - period + 1:i + 1])
                out.append((hh + ll) / 2.0)
            return out

        tenkan = _mid(tenkan_period)
        kijun = _mid(kijun_period)
        # Align tenkan and kijun to same length (kijun is shorter)
        offset = kijun_period - tenkan_period
        tenkan_aligned = tenkan[offset:]
        min_len = min(len(tenkan_aligned), len(kijun))
        # Senkou Span A = (Tenkan + Kijun) / 2, shifted forward 26 periods
        senkou_a = [(tenkan_aligned[i] + kijun[i]) / 2.0 for i in range(min_len)]
        # Senkou Span B = mid(senkou_b_period), shifted forward 26 periods
        senkou_b = _mid(senkou_b_period)
        # Chikou Span = close shifted backward 26 periods
        chikou = closes[kijun_period:] if n > kijun_period else []
        return tenkan, kijun, senkou_a, senkou_b, chikou

    # ── Live data fetching ────────────────────────────

    async def _fetch_live_history(self, symbol: str, limit: int = 500) -> list[dict[str, Any]]:
        """Fetch historical daily data directly from BrsApi API with l18 resolution."""
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import TsetmcParser

        # Resolve symbol to l18 code
        l18: str | None = None
        if self._brsapi:
            try:
                snap = await self._brsapi.get_symbol_snapshot(symbol)
                l18 = snap.get("l18") if snap else None
            except Exception:
                logger.warning("Could not resolve l18 via DB for %s", symbol)
        if not l18 and self._client:
            # Fallback: fetch all symbols to find l18
            try:
                result = await self._client.fetch(
                    BrsApiEndpoints.ALL_SYMBOLS,
                    params={"type": "1"},
                )
                if result.success and result.value and result.value.data:
                    all_sym = TsetmcParser.parse_all_symbols(result.value.data)
                    if isinstance(all_sym, list):
                        for s in all_sym:
                            if s.get("symbol") == symbol or s.get("name") == symbol:
                                l18 = s.get("l18")
                                break
            except Exception:
                logger.exception("Could not resolve l18 via ALL_SYMBOLS for %s", symbol)
        if not l18:
            logger.warning("No l18 code found for symbol %s — cannot fetch live history", symbol)
            return []
        # Fetch history from BrsApi
        try:
            result = await self._client.fetch(
                BrsApiEndpoints.HISTORY_PRICE,
                params={"l18": l18, "type": "0"},
            )
            if result.success and result.value and result.value.data:
                parsed = TsetmcParser.parse_history_price(result.value.data)
                if isinstance(parsed, list) and parsed:
                    # Save to DB for future reads
                    try:
                        await self._save_live_history(symbol, parsed)
                    except Exception:
                        logger.warning("Failed to persist live history for %s", symbol, exc_info=True)
                    return parsed[:limit]
        except Exception:
            logger.exception("Live history fetch failed for %s", symbol)
        return []

    async def _save_live_history(self, symbol: str, records: list[dict[str, Any]]) -> None:
        """Persist live-fetched historical records to DB."""
        from brsapi.models.tsetmc import HistoricalDailyModel
        from brsapi.repositories import BulkUpsertRepository
        from core.database import get_session

        async for session in get_session():
            repo = BulkUpsertRepository(session, HistoricalDailyModel)
            await repo.bulk_insert(records)
        # commit() fires after the async for loop completes naturally

    async def get_batch_sparklines(
        self, symbols: list[str], limit: int = 30
    ) -> Result[dict[str, list[float]]]:
        """
        Fetch last N close prices for multiple symbols in a single query.
        Returns {symbol: [close_price_1, close_price_2, ...]} chronological.
        """
        if not symbols:
            return Result.ok({})
        try:
            from sqlalchemy import text as sa_text

            from core.database import get_session

            result_map: dict[str, list[float]] = {}
            # Use raw SQL for an efficient batch query
            async for session in get_session():
                placeholders = ", ".join([f":sym{i}" for i in range(len(symbols))])
                params = {f"sym{i}": sym for i, sym in enumerate(symbols)}
                params["lim"] = limit
                sql = sa_text(f"""
                    SELECT q.symbol, q.price_close
                    FROM quotes q
                    WHERE q.symbol IN ({placeholders})
                      AND q.price_close IS NOT NULL
                    ORDER BY q.symbol, q.date DESC
                """)
                rows = await session.execute(sql, params)
                # Group by symbol, take first `limit` per symbol (most recent)
                for row in rows:
                    sym = str(row.symbol or "")
                    if not sym:
                        continue
                    if sym not in result_map:
                        result_map[sym] = []
                    if len(result_map[sym]) < limit:
                        result_map[sym].append(float(row.price_close or 0))
                # Reverse each list to chronological order
                for sym in result_map:
                    result_map[sym].reverse()
            return Result.ok(result_map)
        except Exception:
            logger.exception("Failed to fetch batch sparklines")
            return Result.ok({})

    async def get_market_summary(self) -> Result[dict[str, Any]]:
        return await self.quote_repo.get_market_summary()

    async def get_market_watch(self) -> Result[list[dict[str, Any]]]:
        quotes_result = await self.quote_repo.get_all()

        if not quotes_result.success:
            return quotes_result

        enriched_quotes: list[dict[str, Any]] = []

        for quote in quotes_result.value:
            inst_result = await self.instrument_repo.get_by_symbol(quote.symbol)

            market = "Unknown"

            if inst_result.success and inst_result.value:
                market_type = getattr(inst_result.value, "market_type", None)

                if market_type is not None:
                    market = getattr(market_type, "value", str(market_type))

            quote_dict = vars(quote).copy()
            quote_dict["market"] = market

            enriched_quotes.append(quote_dict)

        return Result.ok(enriched_quotes)

    async def get_instruments_by_market(self, market_type: str) -> Result[list[Any]]:
        return await self.instrument_repo.get_by_market(market_type)

    async def get_energy_commodity_summary(self) -> Result[dict[str, Any]]:
        if self._brsapi:
            try:
                commodities = await self._brsapi.get_commodity_prices()
                categories = await self._brsapi.get_commodity_categories()
                if commodities:
                    return Result.ok({
                        "summary": {"total_symbols": len(commodities)},
                        "sub_markets": [
                            {"name": cat["category"], "count": cat["count"], "instruments": []}
                            for cat in categories
                        ] if categories else [
                            {"name": "Commodity", "count": len(commodities), "instruments": commodities[:20]},
                            {"name": "Energy", "count": 0, "instruments": []},
                        ],
                    })
            except Exception:
                logger.exception("Failed to fetch commodity data")
        # Live fallback: fetch commodities from BrsApi API
        if self._client:
            try:
                commodities, categories = await self._fetch_live_commodities()
                return Result.ok({
                    "summary": {"total_symbols": len(commodities)},
                    "sub_markets": [
                        {"name": cat["category"], "count": cat["count"], "instruments": []}
                        for cat in categories
                    ] if categories else [
                        {"name": "Commodity", "count": len(commodities), "instruments": commodities[:20]},
                    ],
                })
            except Exception:
                logger.exception("Live fetch for commodities failed")
        return Result.ok({
            "summary": {"total_symbols": 0},
            "sub_markets": [
                {"name": "Commodity", "count": 0, "instruments": []},
                {"name": "Energy", "count": 0, "instruments": []},
            ],
        })

    async def _fetch_live_commodities(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Fetch commodities directly from BrsApi API."""
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import CommodityParser

        result = await self._client.fetch(BrsApiEndpoints.COMMODITY)
        if result.success and result.value and result.value.data:
            parsed = CommodityParser.parse(result.value.data)
            if isinstance(parsed, list):
                cats = [{"category": "Commodity", "count": len(parsed)}]
                return parsed, cats
        return [], []

    async def get_macro_data(
        self,
        indicator: str,
        country: str = "iran",
    ) -> Result[dict[str, Any]]:
        if self._brsapi and indicator in ("currency", "dollar", "eur", "gold"):
            try:
                if indicator == "gold":
                    data = await self._brsapi.get_gold_coin_prices()
                else:
                    data = await self._brsapi.get_currency_prices()
                if data:
                    return Result.ok({"indicator": indicator, "country": country, "data": data})
            except Exception:
                logger.exception("Failed to fetch macro data")
        # Live fallback: fetch gold/currency from BrsApi API
        if self._client and indicator in ("currency", "dollar", "eur", "gold"):
            try:
                data = await self._fetch_live_macro(indicator)
                if data:
                    return Result.ok({"indicator": indicator, "country": country, "data": data})
            except Exception:
                logger.exception("Live fetch for macro data failed")
        return Result.ok({"indicator": indicator, "country": country})

    async def _fetch_live_macro(self, indicator: str) -> list[dict[str, Any]]:
        """Fetch macro data directly from BrsApi API using the combined Gold_Currency endpoint.

        The old /Market/Coin.php and /Market/Currency.php endpoints are deprecated (HTTP 404).
        Uses /Market/Gold_Currency.php which returns gold, currency & crypto in one call.
        """
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import GoldCurrencyParser

        result = await self._client.fetch(BrsApiEndpoints.GOLD_CURRENCY)
        if not (result.success and result.value and result.value.data):
            return []

        data = result.value.data
        parsed = GoldCurrencyParser.parse_gold(data) if indicator == "gold" else GoldCurrencyParser.parse_currency(data)

        if isinstance(parsed, list):
            return parsed
        return []
