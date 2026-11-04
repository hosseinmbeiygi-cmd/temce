"""
TSETMC response parsers.

Maps the raw JSON arrays from BrsApi TSETMC endpoints into structured
dicts ready for ORM mapping.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from logging import getLogger
from typing import Any

import jdatetime

from brsapi.parsers.errors import BrsApiParseError, ensure_payload, is_no_data
from brsapi.quality import normalize_jalali_date
from core.time import today_jalali_tehran

logger = getLogger(__name__)

# Bounded ISO-ish string so fetched_at fits the varchar(30) columns used by most
# brsapi tables and stays identical across jobs running within the same second.
# The timestamptz columns (symbol_snapshots / index_values / symbol_details)
# instead get a second-truncated real datetime, which preserves the same
# deterministic dedup on the (symbol, fetched_at) unique constraint.
_FETCHED_AT_FORMAT = "%Y-%m-%d %H:%M:%S"

# Domain fields that identify a real payload for the single/ambiguous-shaped
# endpoints. A dict carrying none of them is an envelope we cannot read, not a
# record — otherwise an all-default row gets stored as if it were data.
_DETAIL_KEYS = frozenset(
    {"id", "l18", "l30", "l30_en", "isin", "code_12", "pl", "pc", "mv", "z"}
)
_INDEX_KEYS = frozenset(
    {
        "index",
        "name",
        "index_change",
        "index_change_percent",
        "index_equalWeight",
        "state",
        "mv",
    }
)
_NAV_KEYS = frozenset({"psubtran", "predtran"})

# Envelope keys the candlestick endpoint uses for its candle arrays.
_CANDLE_LIST_KEYS = (
    "candle_daily_adjusted",
    "candle_daily",
    "candle_intraday",
    "candle_realtime",
    "candles",
    "data",
)

# Keys a candlestick payload carries when the provider answered without any
# bars (``{"status": "no_data"}`` or a metadata-only header). Such a payload is
# a valid empty response, not an unreadable one.
_CANDLE_NO_DATA_KEYS = frozenset(
    {
        "l18",
        "type",
        "count",
        "status",
        "code_http",
        "successful",
        "message_error",
        "message",
    }
)


class TsetmcParser:
    """
    Stable parsers for every TSETMC BrsApi endpoint.

    Each ``parse_*`` classmethod accepts the ``data`` field of a
    ``BrsApiResponse`` (already JSON-decoded) and returns a list of
    flat dicts suitable for ORM insert / upsert.
    """

    # ── AllSymbols ──────────────────────────────────

    @classmethod
    def parse_all_symbols(cls, data: Any) -> list[dict[str, Any]]:
        """
        ``/Tsetmc/AllSymbols.php`` response.

        Returns a list of symbol-snapshot dicts keyed on ``ins_id``.
        """
        if not isinstance(data, list):
            raise BrsApiParseError(
                f"AllSymbols: expected a JSON list, got {type(data).__name__}",
                code="unexpected_shape",
            )

        records: list[dict[str, Any]] = []
        # SymbolSnapshotModel.fetched_at is timestamptz in the live DB (migration
        # 001) — emit a real datetime truncated to seconds so the (symbol,
        # fetched_at) upsert keeps its same-second dedup semantics.
        now = datetime.now(UTC).replace(microsecond=0, tzinfo=None)

        for item in data:
            if not isinstance(item, dict):
                continue
            rec = {
                "ins_id": str(item.get("id", "")),
                "symbol": str(item.get("l18", "")),
                "name": str(item.get("l30", "")),
                "isin": str(item.get("isin", "")),
                "sector": str(item.get("cs", "")),
                "sector_id": cls._int(item.get("cs_id", 0)),
                "shares_count": cls._int(item.get("z", 0)),
                "base_volume": cls._int(item.get("bvol", 0)),
                "market_value": cls._float(item.get("mv", 0)),
                "eps": cls._float(item.get("eps", 0)),
                "pe_ratio": cls._float(item.get("pe", 0)),
                "price_min": cls._float(item.get("pmin", 0)),
                "price_max": cls._float(item.get("pmax", 0)),
                "price_yesterday": cls._float(item.get("py", 0)),
                "price_first": cls._float(item.get("pf", 0)),
                "price_last": cls._float(item.get("pl", 0)),
                "price_last_change": cls._float(item.get("plc", 0)),
                "price_last_change_pct": cls._float(item.get("plp", 0)),
                "price_close": cls._float(item.get("pc", 0)),
                "price_close_change": cls._float(item.get("pcc", 0)),
                "price_close_change_pct": cls._float(item.get("pcp", 0)),
                "trade_count": cls._int(item.get("tno", 0)),
                "trade_volume": cls._int(item.get("tvol", 0)),
                "trade_value": cls._float(item.get("tval", 0)),
                "buy_real_count": cls._int(item.get("Buy_CountI", 0)),
                "buy_legal_count": cls._int(item.get("Buy_CountN", 0)),
                "sell_real_count": cls._int(item.get("Sell_CountI", 0)),
                "sell_legal_count": cls._int(item.get("Sell_CountN", 0)),
                "buy_real_volume": cls._int(item.get("Buy_I_Volume", 0)),
                "buy_legal_volume": cls._int(item.get("Buy_N_Volume", 0)),
                "sell_real_volume": cls._int(item.get("Sell_I_Volume", 0)),
                "sell_legal_volume": cls._int(item.get("Sell_N_Volume", 0)),
                "time": item.get("time", ""),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            }

            # Orderbook levels (bid)
            for i in range(1, 6):
                rec[f"bid_count_{i}"] = cls._int(item.get(f"zd{i}", 0))
                rec[f"bid_volume_{i}"] = cls._int(item.get(f"qd{i}", 0))
                rec[f"bid_price_{i}"] = cls._float(item.get(f"pd{i}", 0))

            # Orderbook levels (ask)
            for i in range(1, 6):
                rec[f"ask_count_{i}"] = cls._int(item.get(f"zo{i}", 0))
                rec[f"ask_volume_{i}"] = cls._int(item.get(f"qo{i}", 0))
                rec[f"ask_price_{i}"] = cls._float(item.get(f"po{i}", 0))

            records.append(rec)

        return records

    # ── Symbol Detail ───────────────────────────────

    @classmethod
    def parse_symbol_detail(cls, data: Any) -> dict[str, Any] | None:
        """
        ``/Tsetmc/Symbol.php`` response.

        Returns a single enriched detail dict, or ``None`` when the provider
        answered without a symbol (``{}`` / a metadata-only envelope).

        Raises ``BrsApiParseError`` for ``None``, a non-object payload, or a
        dict that carries none of the detail fields.
        """
        ensure_payload(data, "SymbolDetail")
        if not isinstance(data, dict):
            raise BrsApiParseError(
                f"SymbolDetail: expected an object, got {type(data).__name__}",
                code="unexpected_shape",
            )
        if is_no_data(data):
            return None
        if not _DETAIL_KEYS.intersection(data):
            raise BrsApiParseError(
                f"SymbolDetail: unrecognised envelope keys {sorted(data)[:5]}",
                code="unrecognised_envelope",
            )

        now = datetime.now(UTC).replace(tzinfo=None)
        rec = {
            "ins_id": str(data.get("id") or ""),
            "symbol": data.get("l18") or "",
            "name": data.get("l30") or "",
            "name_en": data.get("l30_en") or "",
            "isin": data.get("isin") or "",
            "code_12": data.get("code_12") or "",
            "code_5": data.get("code_5") or "",
            "code_4": data.get("code_4") or "",
            "market": data.get("m") or "",
            "board": data.get("m_board") or "",
            "board_id": str(data.get("m_board_id") or ""),
            "board_code": str(data.get("m_board_code") or ""),
            "sector": data.get("cs") or "",
            "sector_id": cls._int(data.get("cs_id", 0)),
            "sub_sector": data.get("cs_sub") or "",
            "sub_sector_id": cls._int(data.get("cs_sub_id", 0)),
            "shares_count": cls._int(data.get("z", 0)),
            "shares_issued": cls._int(data.get("z_issued", 0)),
            "base_volume": cls._int(data.get("bvol", 0)),
            "market_value": cls._float(data.get("mv", 0)),
            "free_float_pct": cls._float(data.get("ff", 0)),
            "eps": cls._float(data.get("eps", 0)),
            "pe_ratio": cls._float(data.get("pe", 0)),
            "group_pe_ratio": cls._float(data.get("g_pe", 0)),
            "ps_ratio": cls._float(data.get("ps", 0)),
            "price_lowest_allowed": cls._float(data.get("tmin", 0)),
            "price_highest_allowed": cls._float(data.get("tmax", 0)),
            "price_min_week": cls._float(data.get("pmin_1w", 0)),
            "price_max_week": cls._float(data.get("pmax_1w", 0)),
            "price_min_year": cls._float(data.get("pmin_1y", 0)),
            "price_max_year": cls._float(data.get("pmax_1y", 0)),
            "price_min": cls._float(data.get("pmin", 0)),
            "price_max": cls._float(data.get("pmax", 0)),
            "price_yesterday": cls._float(data.get("py", 0)),
            "price_first": cls._float(data.get("pf", 0)),
            "price_last": cls._float(data.get("pl", 0)),
            "price_last_change": cls._float(data.get("plc", 0)),
            "price_last_change_pct": cls._float(data.get("plp", 0)),
            "price_close": cls._float(data.get("pc", 0)),
            "price_close_change": cls._float(data.get("pcc", 0)),
            "price_close_change_pct": cls._float(data.get("pcp", 0)),
            "trade_count": cls._int(data.get("tno", 0)),
            "trade_volume": cls._int(data.get("tvol", 0)),
            "trade_volume_avg_month": cls._int(data.get("tvol_avg_1m", 0)),
            "trade_value": cls._float(data.get("tval", 0)),
            "buy_real_count": cls._int(data.get("Buy_CountI", 0)),
            "buy_legal_count": cls._int(data.get("Buy_CountN", 0)),
            "sell_real_count": cls._int(data.get("Sell_CountI", 0)),
            "sell_legal_count": cls._int(data.get("Sell_CountN", 0)),
            "buy_real_volume": cls._int(data.get("Buy_I_Volume", 0)),
            "buy_legal_volume": cls._int(data.get("Buy_N_Volume", 0)),
            "sell_real_volume": cls._int(data.get("Sell_I_Volume", 0)),
            "sell_legal_volume": cls._int(data.get("Sell_N_Volume", 0)),
            "state": data.get("state", ""),
            "date": data.get("date", ""),
            "date_update": data.get("date_update", ""),
            "time": data.get("time", ""),
            "fetched_at": now,
            "raw_json": json.dumps(data, ensure_ascii=False),
        }

        # Assembly info (list)
        assembly = data.get("assembly")
        if isinstance(assembly, list):
            rec["assembly"] = json.dumps(assembly, ensure_ascii=False)

        return rec

    # ── Index ──────────────────────────────────────

    @classmethod
    def parse_index(cls, data: Any) -> list[dict[str, Any]]:
        """
        ``/Tsetmc/Index.php`` response.

        Each item is an index snapshot (index_type determined by the
        ``type`` parameter passed to the API).
        """
        # API may return a single dict (type=1 or type=2) or a list (type=3)
        ensure_payload(data, "Index")
        if is_no_data(data):
            return []
        if isinstance(data, dict):
            # Any object is not an index: a provider envelope that slipped past
            # ``is_no_data`` must not become an all-default index row.
            if not _INDEX_KEYS.intersection(data):
                raise BrsApiParseError(
                    f"Index: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
            data = [data]
        elif not isinstance(data, list):
            raise BrsApiParseError(
                f"Index: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        records: list[dict[str, Any]] = []
        # brsapi_index_values.fetched_at is a DateTime column (migration 001) —
        # bind a real datetime (like parse_symbol_detail) or asyncpg rejects the
        # value with ``expected a datetime instance, got 'str'``.
        now = datetime.now(UTC).replace(tzinfo=None)

        for item in data:
            if not isinstance(item, dict):
                continue
            records.append({
                "name": item.get("name", ""),
                "state": item.get("state", ""),
                "index_value": cls._float(item.get("index", 0)),
                "index_change": cls._float(item.get("index_change", 0)),
                "index_change_pct": cls._float(item.get("index_change_percent", 0)),
                "index_equal_weight": cls._float(item.get("index_equalWeight", 0)),
                "index_equal_weight_change": cls._float(item.get("index_equalWeight_change", 0)),
                "market_value": cls._float(item.get("mv", 0)),
                "market_value_main": cls._float(item.get("mv_main", 0)),
                "market_value_base": cls._float(item.get("mv_base", 0)),
                "trade_count": cls._int(item.get("tno", 0)),
                "trade_volume": cls._int(item.get("tvol", 0)),
                "trade_value": cls._float(item.get("tval", 0)),
                "min": cls._float(item.get("min", 0)),
                "max": cls._float(item.get("max", 0)),
                "date": item.get("date", ""),
                "time": item.get("time", ""),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            })

        return records

    # ── NAV ────────────────────────────────────────

    @classmethod
    def parse_nav(cls, data: Any) -> dict[str, Any] | None:
        """
        ``/Tsetmc/Nav.php`` response.

        Returns a single NAV snapshot with issue and redemption prices, or
        ``None`` when the provider answered without one.
        """
        ensure_payload(data, "NAV")
        if not isinstance(data, dict):
            raise BrsApiParseError(
                f"NAV: expected an object, got {type(data).__name__}",
                code="unexpected_shape",
            )
        if is_no_data(data):
            return None
        if not _NAV_KEYS.intersection(data):
            raise BrsApiParseError(
                f"NAV: unrecognised envelope keys {sorted(data)[:5]}",
                code="unrecognised_envelope",
            )

        # Bounded ISO-ish string (matches the snapshots parser format) so it
        # fits String(30) and stays consistent across the codebase.
        now = datetime.now(UTC).strftime(_FETCHED_AT_FORMAT)
        return {
            "nav_issue": cls._float(data.get("psubtran", 0)),
            "nav_redemption": cls._float(data.get("predtran", 0)),
            "date": data.get("date", ""),
            "time": data.get("time", ""),
            "fetched_at": now,
            "raw_json": json.dumps(data, ensure_ascii=False),
        }

    # ── Option ─────────────────────────────────────

    @classmethod
    def parse_options(cls, data: Any) -> list[dict[str, Any]]:
        """
        ``/Tsetmc/Option.php`` response.

        Returns a list of option contract snapshots.
        """
        ensure_payload(data, "Option")
        if is_no_data(data):
            return []
        if not isinstance(data, list):
            raise BrsApiParseError(
                f"Option: expected a list, got {type(data).__name__}",
                code="unexpected_shape",
            )

        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime(_FETCHED_AT_FORMAT)

        for item in data:
            if not isinstance(item, dict):
                continue
            rec = {
                "symbol": item.get("l18", ""),
                "name": item.get("l30", ""),
                "isin": item.get("isin", ""),
                "underlying_symbol": item.get("base_l18", ""),
                "underlying_id": str(item.get("base_id", "")),
                "option_type": item.get("type", ""),          # "call" / "put"
                "contract_size": cls._int(item.get("size_contract", 0)),
                "strike_price": cls._float(item.get("price_strike", 0)),
                "open_interest": cls._int(item.get("interest_open", 0)),
                "date_begin": item.get("date_begin", ""),
                "date_end": item.get("date_end", ""),
                "days_remaining": cls._int(item.get("day_remain", 0)),
                "sector": item.get("cs", ""),
                "sector_id": str(item.get("cs_id", "")),
                "ins_id": str(item.get("id", "")),
                "underlying_price_yesterday": cls._float(item.get("base_py", 0)),
                "underlying_price_last": cls._float(item.get("base_pl", 0)),
                "underlying_price_last_change_pct": cls._float(item.get("base_plp", 0)),
                "underlying_price_close": cls._float(item.get("base_pc", 0)),
                "underlying_price_close_change_pct": cls._float(item.get("base_pcp", 0)),
                "price_min": cls._float(item.get("pmin", 0)),
                "price_max": cls._float(item.get("pmax", 0)),
                "price_yesterday": cls._float(item.get("py", 0)),
                "price_first": cls._float(item.get("pf", 0)),
                "price_last": cls._float(item.get("pl", 0)),
                "price_last_change": cls._float(item.get("plc", 0)),
                "price_last_change_pct": cls._float(item.get("plp", 0)),
                "price_close": cls._float(item.get("pc", 0)),
                "price_close_change": cls._float(item.get("pcc", 0)),
                "price_close_change_pct": cls._float(item.get("pcp", 0)),
                "trade_count": cls._int(item.get("tno", 0)),
                "trade_volume": cls._int(item.get("tvol", 0)),
                "trade_value": cls._float(item.get("tval", 0)),
                "notional_value": cls._float(item.get("nval", 0)),
                "buy_real_count": cls._int(item.get("Buy_CountI", 0)),
                "buy_legal_count": cls._int(item.get("Buy_CountN", 0)),
                "sell_real_count": cls._int(item.get("Sell_CountI", 0)),
                "sell_legal_count": cls._int(item.get("Sell_CountN", 0)),
                "buy_real_volume": cls._int(item.get("Buy_I_Volume", 0)),
                "buy_legal_volume": cls._int(item.get("Buy_N_Volume", 0)),
                "sell_real_volume": cls._int(item.get("Sell_I_Volume", 0)),
                "sell_legal_volume": cls._int(item.get("Sell_N_Volume", 0)),
                "time": item.get("time", ""),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            }

            # Orderbook levels
            for i in range(1, 6):
                rec[f"bid_count_{i}"] = cls._int(item.get(f"zd{i}", 0))
                rec[f"bid_volume_{i}"] = cls._int(item.get(f"qd{i}", 0))
                rec[f"bid_price_{i}"] = cls._float(item.get(f"pd{i}", 0))
                rec[f"ask_count_{i}"] = cls._int(item.get(f"zo{i}", 0))
                rec[f"ask_volume_{i}"] = cls._int(item.get(f"qo{i}", 0))
                rec[f"ask_price_{i}"] = cls._float(item.get(f"po{i}", 0))

            records.append(rec)

        return records

    # ── Transactions ───────────────────────────────

    @classmethod
    def parse_transactions(cls, data: Any) -> list[dict[str, Any]]:
        """
        ``/Tsetmc/Transaction.php`` response.

        Handles both raw flat lists and the BrsApi nested envelope:
        ``{"data": {"transaction": [...]}}``.

        Returns intraday trade ticks with fields: row, time, volume, price, canceled.
        """
        if data is None:
            raise BrsApiParseError(
                "Transaction: payload is None, not a JSON document",
                code="missing_payload",
            )

        # Unwrap BrsApi envelope: {"data": {"transaction": [...]}}
        if isinstance(data, dict):
            if not data:
                # Valid empty response: the provider answered, with no rows.
                return []
            inner = data.get("data")
            if isinstance(inner, dict):
                items = inner.get("transaction")
                if isinstance(items, list):
                    data = items
                elif not inner:
                    return []
                else:
                    raise BrsApiParseError(
                        "Transaction: 'data' envelope has no 'transaction' list",
                        code="unrecognised_envelope",
                    )
            elif isinstance(inner, list):
                data = inner
            elif isinstance(data.get("transaction"), list):
                data = data["transaction"]
            elif {"code_http", "successful", "status"} & set(data):
                # Provider envelope without rows (e.g. ``{"status": "no_data"}``).
                return []
            else:
                raise BrsApiParseError(
                    "Transaction: unrecognised envelope keys "
                    f"{sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )

        if not isinstance(data, list):
            raise BrsApiParseError(
                f"Transaction: expected a JSON list, got {type(data).__name__}",
                code="unexpected_shape",
            )

        records: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            # Handle both BrsApi field names (id, pTran, qTitTran, etc.) and simple names
            records.append({
                "id": cls._int(item.get("id", 0)),
                "row": cls._int(item.get("row", 0)),
                "time": item.get("time", "") or item.get("hEven", ""),
                "volume": cls._int(item.get("volume", 0) or item.get("qTitTran", 0)),
                "price": cls._float(item.get("price", 0) or item.get("pTran", 0)),
                "canceled": bool(item.get("canceled", False) or item.get("cCanceled", 0)),
            })
        return records

    # ── History (Price) ────────────────────────────

    @classmethod
    def parse_history_price(cls, data: Any) -> list[dict[str, Any]]:
        """``/Tsetmc/History.php?type=0`` – daily OHLCV summary."""
        ensure_payload(data, "HistoryPrice")
        if is_no_data(data):
            return []
        if not isinstance(data, list):
            raise BrsApiParseError(
                f"HistoryPrice: expected a list, got {type(data).__name__}",
                code="unexpected_shape",
            )
        return [cls._history_item(item) for item in data if isinstance(item, dict)]

    @classmethod
    def parse_history_real_legal(cls, data: Any) -> list[dict[str, Any]]:
        """``/Tsetmc/History.php?type=1`` – daily real/legal breakdown."""
        ensure_payload(data, "HistoryRealLegal")
        if is_no_data(data):
            return []
        if not isinstance(data, list):
            raise BrsApiParseError(
                f"HistoryRealLegal: expected a list, got {type(data).__name__}",
                code="unexpected_shape",
            )

        records: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            records.append({
                "date": item.get("date", ""),
                "buy_real_count": cls._int(item.get("Buy_CountI")),
                "buy_legal_count": cls._int(item.get("Buy_CountN")),
                "sell_real_count": cls._int(item.get("Sell_CountI")),
                "sell_legal_count": cls._int(item.get("Sell_CountN")),
                "buy_real_volume": cls._int(item.get("Buy_I_Volume")),
                "buy_legal_volume": cls._int(item.get("Buy_N_Volume")),
                "sell_real_volume": cls._int(item.get("Sell_I_Volume")),
                "sell_legal_volume": cls._int(item.get("Sell_N_Volume")),
                "buy_real_value": cls._float(item.get("Buy_I_Value")),
                "buy_legal_value": cls._float(item.get("Buy_N_Value")),
                "sell_real_value": cls._float(item.get("Sell_I_Value")),
                "sell_legal_value": cls._float(item.get("Sell_N_Value")),
            })
        return records

    @classmethod
    def _history_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        # Every numeric column is nullable: an absent field stays ``None`` so a
        # missing price is never published as a real-looking 0 (DS-05).
        return {
            "date": item.get("date", ""),
            "time": item.get("time", ""),
            "trade_count": cls._int(item.get("tno")),
            "trade_volume": cls._int(item.get("tvol")),
            "trade_value": cls._float(item.get("tval")),
            "price_min": cls._float(item.get("pmin")),
            "price_max": cls._float(item.get("pmax")),
            "price_yesterday": cls._float(item.get("py")),
            "price_first": cls._float(item.get("pf")),
            "price_last": cls._float(item.get("pl")),
            "price_last_change": cls._float(item.get("plc")),
            "price_last_change_pct": cls._float(item.get("plp")),
            "price_close": cls._float(item.get("pc")),
            "price_close_change": cls._float(item.get("pcc")),
            "price_close_change_pct": cls._float(item.get("pcp")),
        }

    # ── Candlestick ────────────────────────────────

    @classmethod
    def parse_candlesticks(cls, data: Any) -> list[dict[str, Any]]:
        """``/Tsetmc/Candlestick.php`` response.

        The API returns the ``date`` in Jalali format (e.g. ``1404-05-18``);
        each record is enriched with ``gregorian_date`` (DATE object) and
        ``shamsi_date`` (normalized ``YYYY-MM-DD``) so time-based sorting,
        queries and charts work without string hacks.

        Payload envelopes (per API ``type`` param):
          - type=1 realtime 2-min bars  → ``candle_intraday`` (no ``date``, only ``time``)
          - type=2 unadjusted daily     → ``candle_daily``
          - type=3 adjusted daily       → ``candle_daily_adjusted``

        Intraday bars carry no ``date`` — they are stamped with today's
        Jalali date (Tehran) so the chart has a full timestamp.

        Raises ``BrsApiParseError`` when the payload cannot be read:
        ``missing_payload`` for ``None``, ``unexpected_shape`` for a scalar
        payload or a non-list candle key, ``unrecognised_envelope`` for a
        dict that names neither a candle array, OHLC fields nor no-data
        metadata. A recognised empty response (``{"status": "no_data"}``)
        returns ``[]``.
        """
        if data is None:
            raise BrsApiParseError(
                "Candlestick: payload is None, not a JSON document",
                code="missing_payload",
            )
        if isinstance(data, list):
            # Some payloads are a bare array of candles.
            candles = data
        elif isinstance(data, dict):
            if not data:
                # Valid empty response: the provider answered, with no bars.
                return []
            candles = None
            for key in _CANDLE_LIST_KEYS:
                if key not in data:
                    continue
                value = data[key]
                if isinstance(value, list):
                    candles = value
                else:
                    raise BrsApiParseError(
                        f"Candlestick: '{key}' must be a list, got "
                        f"{type(value).__name__}",
                        code="unexpected_shape",
                    )
                break
            if candles is None:
                # Only treat a bare dict as a single candle when it actually
                # carries OHLC fields — metadata-only payloads (e.g. the
                # ``{"status": "no_data"}`` envelope) must not produce a
                # zero-valued row.
                has_ohlc = any(
                    k in data for k in ("open", "high", "low", "close", "date", "time")
                )
                if has_ohlc:
                    candles = [data]
                elif _CANDLE_NO_DATA_KEYS.intersection(data):
                    candles = []
                else:
                    raise BrsApiParseError(
                        "Candlestick: unrecognised envelope keys "
                        f"{sorted(data)[:5]}",
                        code="unrecognised_envelope",
                    )
        else:
            raise BrsApiParseError(
                "Candlestick: expected a JSON list or object, got "
                f"{type(data).__name__}",
                code="unexpected_shape",
            )

        # Intraday bars have no ``date`` field — stamp them with today's
        # Jalali date so gregorian/shamsi enrichment still works. The date is
        # Tehran's market day, not the host's: a UTC server's host-local day
        # is one behind between 20:30 UTC and midnight, which would date the
        # bars to the previous session.
        today_jalali = today_jalali_tehran()

        records: list[dict[str, Any]] = []
        for c in candles:
            if not isinstance(c, dict) or not c:
                continue
            raw_date = c.get("date") or ""
            gregorian_date, shamsi_date = cls._jalali_to_gregorian(raw_date or today_jalali)
            records.append({
                "date": raw_date or today_jalali,
                "time": c.get("time", ""),
                # Nullable columns: an absent field stays None instead of being
                # published as a real-looking 0 price/volume (DS-05).
                "open": cls._float(c.get("open")),
                "high": cls._float(c.get("high")),
                "low": cls._float(c.get("low")),
                "close": cls._float(c.get("close")),
                "volume": cls._int(c.get("volume")),
                "count": cls._int(c.get("count")),
                "gregorian_date": gregorian_date,
                "shamsi_date": shamsi_date,
            })
        return records

    @staticmethod
    def _jalali_to_gregorian(value: Any) -> tuple[Any, str | None]:
        """Convert a Jalali date (``1404/02/23`` or ``1404-02-23``) to
        ``(gregorian datetime.date, normalized shamsi ``YYYY-MM-DD``)``.

        Returns a **real ``datetime.date`` object** (not a string) because
        ``brsapi_candlesticks.gregorian_date`` is a DATE column and asyncpg
        rejects plain strings for date types (the same DataError class the
        codebase hit with ``fetched_at``). Values outside the Jalali domain
        (a Gregorian ``2026-…``, month 13, an impossible day) return
        ``(None, None)``: interpreting them as Jalali would silently move the
        bar centuries away, so the row keeps only its raw string.
        """
        from datetime import date

        # One Jalali parser for the whole codebase (Persian digits, ``/``/``.``
        # separators, year 1200..1599) — see ``brsapi.quality``.
        normalized = normalize_jalali_date(value)
        if normalized is None:
            return None, None
        try:
            jy, jm, jd = (int(part) for part in normalized.split("-"))
            g = jdatetime.date(jy, jm, jd).togregorian()
            return date(g.year, g.month, g.day), normalized
        except (TypeError, ValueError):
            return None, None

    # ── Shareholder ────────────────────────────────

    @classmethod
    def parse_shareholders(cls, data: Any) -> list[dict[str, Any]]:
        """``/Tsetmc/Shareholder.php`` response."""
        if data is None:
            raise BrsApiParseError(
                "Shareholder: payload is None, not a JSON document",
                code="missing_payload",
            )
        if isinstance(data, dict):
            if not data:
                return []
            inner = data.get("shareholders", data.get("data"))
            if isinstance(inner, list):
                data = inner
            elif {"code_http", "successful", "status"} & set(data):
                return []
            else:
                raise BrsApiParseError(
                    "Shareholder: unrecognised envelope keys "
                    f"{sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
        if not isinstance(data, list):
            raise BrsApiParseError(
                f"Shareholder: expected a JSON list, got {type(data).__name__}",
                code="unexpected_shape",
            )

        records: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            records.append({
                # TSETMC's internal shareholder id — previously discarded.
                "shareholder_id": cls._int(item.get("id", 0)),
                "shareholder_name": item.get("name", ""),
                "volume": cls._int(item.get("volume", 0)),
                "percent": cls._float(item.get("percent", 0)),
                # ``change`` arrives with a trailing minus for negatives
                # (e.g. ``"5000000-"``) — parse it sign-aware.
                "change": cls._signed_int(item.get("change", 0)),
            })
        return records

    # ── Helpers ────────────────────────────────────

    @staticmethod
    def _signed_int(v: Any) -> int:
        """Parse an int where a trailing ``-`` denotes a negative value.

        TSETMC returns signed amounts like ``"5000000-"`` for negative
        changes; ``float()`` (used by ``_int``) rejects that, so strip the
        trailing minus first. Falls back to 0 like ``_int``.
        """
        s = str(v).replace(",", "").strip()
        if s.endswith("-"):
            s = "-" + s[:-1]
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _int(v: Any) -> int | None:
        from .numeric import parse_int

        return parse_int(v)

    @staticmethod
    def _float(v: Any) -> float | None:
        from .numeric import parse_float

        return parse_float(v)
