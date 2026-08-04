from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

from . import ParsedEvent, Parser

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════
# Shared field-mapping helpers
# ═══════════════════════════════════════════════════════════

def _safe_str(val: Any) -> str | None:
    if val is None:
        return None
    return str(val)


from core.db_utils import safe_float, safe_int


def _safe_float(val: Any) -> float | None:
    """Return None on failure (backward-compat)."""
    return safe_float(val, default=None)


def _safe_int(val: Any) -> int | None:
    """Return None on failure (backward-compat)."""
    return safe_int(val, default=None)


# TSETMC common field aliases used by all 4 libraries
_TSETMC_PRICE_FIELDS = {
    "symbol": ("symbol", "lVal18AFC", "name"),
    "name": ("name", "lVal30"),
    "ins_code": ("insCode", "instrument_code"),
    "last_price": ("pDrCotVal", "lastPrice", "last_price"),
    "close_price": ("pClosing", "closingPrice", "close"),
    "first_price": ("priceFirst", "firstPrice", "open", "first_price"),
    "high_price": ("priceMax", "highPrice", "high", "high_price"),
    "low_price": ("priceMin", "lowPrice", "low", "low_price"),
    "volume": ("qTotTran5J", "volume", "qTitTran"),
    "value": ("valTran", "value"),
    "trade_count": ("numberOfTrades", "tradeCount", "trade_count"),
    "yesterday_close": ("yesterdayPrice", "yesterdayClose", "yesterday_close"),
}


def _get_first(rec: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        val = rec.get(k)
        if val is not None:
            return val
    return None


def _map_price_fields(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": _safe_str(_get_first(rec, *_TSETMC_PRICE_FIELDS["symbol"])),
        "name": _safe_str(_get_first(rec, *_TSETMC_PRICE_FIELDS["name"])),
        "last_price": _safe_float(_get_first(rec, *_TSETMC_PRICE_FIELDS["last_price"])),
        "close_price": _safe_float(_get_first(rec, *_TSETMC_PRICE_FIELDS["close_price"])),
        "first_price": _safe_float(_get_first(rec, *_TSETMC_PRICE_FIELDS["first_price"])),
        "high_price": _safe_float(_get_first(rec, *_TSETMC_PRICE_FIELDS["high_price"])),
        "low_price": _safe_float(_get_first(rec, *_TSETMC_PRICE_FIELDS["low_price"])),
        "volume": _safe_int(_get_first(rec, *_TSETMC_PRICE_FIELDS["volume"])),
        "value": _safe_float(_get_first(rec, *_TSETMC_PRICE_FIELDS["value"])),
        "trade_count": _safe_int(_get_first(rec, *_TSETMC_PRICE_FIELDS["trade_count"])),
        "yesterday_close": _safe_float(_get_first(rec, *_TSETMC_PRICE_FIELDS["yesterday_close"])),
    }


# ═══════════════════════════════════════════════════════════
# Base Library Parser (common logic)
# ═══════════════════════════════════════════════════════════

class _BaseLibParser(Parser):
    """Base parser with common dispatch logic for library-sourced data."""

    _source_name: str = ""

    def source_name(self) -> str:
        return self._source_name

    def can_parse(self, source: str, endpoint: str, content_type: str) -> bool:
        return source == self._source_name

    async def parse(self, payload: bytes) -> list[ParsedEvent]:
        try:
            data = json.loads(payload)
        except Exception:
            logger.exception("Failed to parse %s payload", self._source_name)
            return []
        return self._dispatch(data)

    def _dispatch(self, data: dict[str, Any]) -> list[ParsedEvent]:
        """Override in subclass to dispatch by data_type."""
        return []

    # ── Event builders ──

    def _market_snapshot(self, rec: dict[str, Any], now: str) -> ParsedEvent:
        return ParsedEvent(
            source=self._source_name,
            event_type="market_snapshot",
            data=_map_price_fields(rec),
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )

    def _daily_ohlcv(self, rec: dict[str, Any], symbol: str, now: str) -> ParsedEvent:
        return ParsedEvent(
            source=self._source_name,
            event_type="daily_ohlcv",
            data={
                "symbol": symbol or _safe_str(_get_first(rec, "symbol", "lVal18AFC")),
                "date": _safe_str(_get_first(rec, "date", "dEven")),
                "open": _safe_float(_get_first(rec, "priceFirst", "open", "firstPrice")),
                "high": _safe_float(_get_first(rec, "priceMax", "high", "highPrice")),
                "low": _safe_float(_get_first(rec, "priceMin", "low", "lowPrice")),
                "close": _safe_float(_get_first(rec, "pClosing", "close", "closingPrice")),
                "volume": _safe_int(_get_first(rec, "qTotTran5J", "volume")),
                "value": _safe_float(_get_first(rec, "valTran", "value")),
            },
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )

    def _trade_tick(self, rec: dict[str, Any], symbol: str, now: str) -> ParsedEvent:
        return ParsedEvent(
            source=self._source_name,
            event_type="trade_tick",
            data={
                "symbol": symbol or _safe_str(_get_first(rec, "symbol", "lVal18AFC")),
                "time": _safe_str(_get_first(rec, "time", "hEven")),
                "price": _safe_float(_get_first(rec, "pTran", "price")),
                "volume": _safe_int(_get_first(rec, "qTitTran", "volume")),
            },
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )

    def _orderbook_level(self, rec: dict[str, Any], symbol: str, now: str) -> ParsedEvent:
        side = "bid" if _safe_str(_get_first(rec, "side")) in ("buy", "bid", "B") else "ask"
        return ParsedEvent(
            source=self._source_name,
            event_type="orderbook_level",
            data={
                "symbol": symbol or _safe_str(_get_first(rec, "symbol", "lVal18AFC")),
                "side": side,
                "price": _safe_float(_get_first(rec, "pPrice", "price")),
                "volume": _safe_int(_get_first(rec, "qTit", "volume")),
                "order_count": _safe_int(_get_first(rec, "zOrder", "count", "order_count")),
                "rank": _safe_int(_get_first(rec, "rank")),
            },
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )

    def _real_individual(self, rec: dict[str, Any], symbol: str, now: str) -> ParsedEvent:
        return ParsedEvent(
            source=self._source_name,
            event_type="real_individual",
            data={
                "symbol": symbol,
                "date": _safe_str(_get_first(rec, "date", "dEven")),
                "buy_count_real": _safe_int(_get_first(rec, "buyCountReal", "buyCountI")),
                "buy_volume_real": _safe_float(_get_first(rec, "buyVolumeReal", "buyVolumeI")),
                "sell_count_real": _safe_int(_get_first(rec, "sellCountReal", "sellCountI")),
                "sell_volume_real": _safe_float(_get_first(rec, "sellVolumeReal", "sellVolumeI")),
                "buy_count_legal": _safe_int(_get_first(rec, "buyCountLegal", "buyCountL")),
                "buy_volume_legal": _safe_float(_get_first(rec, "buyVolumeLegal", "buyVolumeL")),
                "sell_count_legal": _safe_int(_get_first(rec, "sellCountLegal", "sellCountL")),
                "sell_volume_legal": _safe_float(_get_first(rec, "sellVolumeLegal", "sellVolumeL")),
            },
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )

    def _index_value(self, rec: dict[str, Any], index_type: str, now: str) -> ParsedEvent:
        return ParsedEvent(
            source=self._source_name,
            event_type="index_value",
            data={
                "index_type": index_type,
                "date": _safe_str(_get_first(rec, "date", "dEven")),
                "value": _safe_float(_get_first(rec, "value", "indexValue", "xNivInu130")),
                "change": _safe_float(_get_first(rec, "change", "indexChange", "xNivInu132")),
            },
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )

    def _instrument_info(self, rec: dict[str, Any], now: str) -> ParsedEvent:
        return ParsedEvent(
            source=self._source_name,
            event_type="instrument_info",
            data={
                "symbol": _safe_str(_get_first(rec, "symbol", "lVal18AFC", "name")),
                "name": _safe_str(_get_first(rec, "name", "lVal30")),
                "ins_code": _safe_str(_get_first(rec, "insCode", "instrument_code")),
                "market": _safe_str(_get_first(rec, "market")),
                "group": _safe_str(_get_first(rec, "group", "group_name")),
            },
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )

    def _price_adjustment(self, rec: dict[str, Any], code: str, now: str) -> ParsedEvent:
        return ParsedEvent(
            source=self._source_name,
            event_type="price_adjustment",
            data={
                "tsetmc_code": code,
                "date": _safe_str(_get_first(rec, "date", "dEven")),
                "adjusted_price": _safe_float(_get_first(rec, "adjustedPrice", "pClosing")),
            },
            raw_object_key="",
            fetch_time=now,
            parsed_at=now,
        )


# ═══════════════════════════════════════════════════════════
# Parser: finpy-tse
# ═══════════════════════════════════════════════════════════

class FinpyTseParser(_BaseLibParser):
    _source_name = "finpy_tse"

    def _dispatch(self, data: dict[str, Any]) -> list[ParsedEvent]:
        data_type = data.get("data_type", "unknown")
        records = data.get("records", [])
        symbol = data.get("symbol", "")
        now = datetime.now(UTC).isoformat()
        events: list[ParsedEvent] = []

        if data_type == "market_watch":
            for rec in records:
                events.append(self._market_snapshot(rec, now))

        elif data_type == "price_history":
            for rec in records:
                events.append(self._daily_ohlcv(rec, symbol, now))

        elif data_type == "intraday_trades":
            for rec in records:
                events.append(self._trade_tick(rec, symbol, now))

        elif data_type == "order_book":
            for rec in records:
                events.append(self._orderbook_level(rec, symbol, now))

        elif data_type == "real_individual":
            for rec in records:
                events.append(self._real_individual(rec, symbol, now))

        elif data_type == "shareholders":
            for rec in records:
                events.append(self._instrument_info(rec, now))

        elif data_type in ("index_act50", "index_lci30", "index_industry",
                           "index_equal_weight", "index_free_float",
                           "index_cwi", "index_cwpi"):
            for rec in records:
                events.append(self._index_value(rec, data_type, now))

        elif data_type == "symbol_list":
            for rec in records:
                events.append(self._instrument_info(rec, now))

        return events


# ═══════════════════════════════════════════════════════════
# Parser: tsetmc (async library)
# ═══════════════════════════════════════════════════════════

class TsetmcLibParser(_BaseLibParser):
    _source_name = "tsetmc_lib"

    def _dispatch(self, data: dict[str, Any]) -> list[ParsedEvent]:
        data_type = data.get("data_type", "unknown")
        records = data.get("records", [])
        symbol = data.get("symbol", "")
        now = datetime.now(UTC).isoformat()
        events: list[ParsedEvent] = []

        if data_type == "market_watch":
            for rec in records:
                events.append(self._market_snapshot(rec, now))

        elif data_type == "price_history" or data_type == "closing_price":
            for rec in records:
                events.append(self._daily_ohlcv(rec, symbol, now))

        elif data_type == "instrument_info":
            info = data.get("info", {})
            events.append(ParsedEvent(
                source=self._source_name,
                event_type="instrument_info",
                data={
                    "symbol": symbol,
                    "name": _safe_str(_get_first(info, "name", "lVal30")),
                    "ins_code": _safe_str(_get_first(info, "insCode")),
                    "market": _safe_str(_get_first(info, "market")),
                    "group": _safe_str(_get_first(info, "group")),
                    "eps": _safe_float(_get_first(info, "eps")),
                    "pe_ratio": _safe_float(_get_first(info, "pe")),
                    "base_volume": _safe_int(_get_first(info, "baseVol")),
                },
                raw_object_key="",
                fetch_time=now,
                parsed_at=now,
            ))

        elif data_type == "indexes":
            stats = data.get("stats", {})
            events.append(ParsedEvent(
                source=self._source_name,
                event_type="index_value",
                data={
                    "index_type": "market_summary",
                    "total_index": _safe_float(_get_first(stats, "totalIndex")),
                    "equal_weight": _safe_float(_get_first(stats, "equalWeightIndex")),
                    "market_value": _safe_float(_get_first(stats, "marketValue")),
                },
                raw_object_key="",
                fetch_time=now,
                parsed_at=now,
            ))

        return events


# ═══════════════════════════════════════════════════════════
# Parser: tehran-stocks
# ═══════════════════════════════════════════════════════════

class TehranStocksParser(_BaseLibParser):
    _source_name = "tehran_stocks"

    def _dispatch(self, data: dict[str, Any]) -> list[ParsedEvent]:
        data_type = data.get("data_type", "unknown")
        symbol = data.get("symbol", "")
        now = datetime.now(UTC).isoformat()
        events: list[ParsedEvent] = []

        if data_type == "all_stocks":
            for s in data.get("stocks", []):
                events.append(self._instrument_info(s, now))

        elif data_type == "price_history":
            for rec in data.get("records", []):
                events.append(self._daily_ohlcv(rec, symbol, now))

        return events


# ═══════════════════════════════════════════════════════════
# Parser: tse-utils
# ═══════════════════════════════════════════════════════════

class TseUtilsParser(_BaseLibParser):
    _source_name = "tse_utils"

    def _dispatch(self, data: dict[str, Any]) -> list[ParsedEvent]:
        data_type = data.get("data_type", "unknown")
        tsetmc_code = data.get("tsetmc_code", "")
        raw_records = data.get("data", [])
        records = raw_records if isinstance(raw_records, list) else [raw_records] if isinstance(raw_records, dict) else []
        now = datetime.now(UTC).isoformat()
        events: list[ParsedEvent] = []

        if data_type == "order_book":
            for level in records:
                events.append(self._orderbook_level(level, tsetmc_code, now))

        elif data_type == "trade_history":
            for rec in records:
                events.append(self._trade_tick(rec, tsetmc_code, now))

        elif data_type == "price_adjustments":
            for rec in records:
                events.append(self._price_adjustment(rec, tsetmc_code, now))

        elif data_type == "client_type":
            for rec in records:
                events.append(self._real_individual(rec, tsetmc_code, now))

        elif data_type == "market_overview":
            for inst in records:
                events.append(self._instrument_info(inst, now))

        return events
