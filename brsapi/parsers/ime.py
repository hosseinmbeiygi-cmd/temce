"""
IME (Iran Mercantile Exchange) parsers.

Covers:
- Futures contracts (``/IME/Futures.php``)
- Option contracts (``/IME/Option.php``)
- Certificate / depository receipts (``/IME/Certificate.php``)
- Commodity funds (``/IME/Fund.php``)
- Physical trades (``/IME/Physical.php``)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


class ImeParser:
    """
    Stable parsers for all IME (Iran Mercantile Exchange) endpoints.
    """

    # ── Futures ────────────────────────────────────

    @classmethod
    def parse_futures(cls, data: Any) -> list[dict[str, Any]]:
        """``/IME/Futures.php`` response."""
        items = cls._ensure_list(data)
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        for item in items:
            if not isinstance(item, dict):
                continue
            rec = {
                "contract_code": cls._str(item.get("contract_code", "")),
                "contract_description": cls._str(item.get("contract_description", "")),
                "contract_size": cls._int(item.get("contract_size", 0)),
                "contract_size_unit": cls._str(item.get("contract_size_unit", "")),
                "contract_currency": cls._str(item.get("contract_currency", "")),
                "date_end": cls._str(item.get("date_end", "")),
                "date_end_text": cls._str(item.get("date_end_text", "")),
                "days_remaining": cls._int(item.get("day_remain", 0)),
                "margin_initial": cls._float(item.get("margin_initial", 0)),
                "margin_maintenance": cls._float(item.get("margin_maintenance", 0)),
                "open_interest": cls._int(item.get("interest_open", 0)),
                "open_interest_change": cls._int(item.get("interest_openc", 0)),
                "open_interest_change_pct": cls._float(item.get("interest_openp", 0)),
                "price_yesterday": cls._float(item.get("py", 0)),
                "price_first": cls._float(item.get("pf", 0)),
                "price_first_change": cls._float(item.get("pfc", 0)),
                "price_first_change_pct": cls._float(item.get("pfp", 0)),
                "price_max": cls._float(item.get("pmax", 0)),
                "price_max_change": cls._float(item.get("pmaxc", 0)),
                "price_max_change_pct": cls._float(item.get("pmaxp", 0)),
                "price_min": cls._float(item.get("pmin", 0)),
                "price_min_change": cls._float(item.get("pminc", 0)),
                "price_min_change_pct": cls._float(item.get("pminp", 0)),
                "price_last": cls._float(item.get("pl", 0)),
                "price_last_change": cls._float(item.get("plc", 0)),
                "price_last_change_pct": cls._float(item.get("plp", 0)),
                "price_last_settlement": cls._float(item.get("pls", 0)),
                "trade_count": cls._int(item.get("tno", 0)),
                "trade_volume": cls._int(item.get("tvol", 0)),
                "trade_value": cls._float(item.get("tval", 0)),
                "trade_value_unit": cls._str(item.get("tval_unit", "")),
                "buy_real_count": cls._int(item.get("Buy_CountI", 0)),
                "buy_legal_count": cls._int(item.get("Buy_CountN", 0)),
                "sell_real_count": cls._int(item.get("Sell_CountI", 0)),
                "sell_legal_count": cls._int(item.get("Sell_CountN", 0)),
                "time": cls._str(item.get("time", "")),
                "date_update": cls._str(item.get("date_update", "")),
                "time_update": cls._str(item.get("time_update", "")),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            }

            # Orderbook
            for i in range(1, 4):
                rec[f"bid_volume_{i}"] = cls._int(item.get(f"qd{i}", 0))
                rec[f"bid_price_{i}"] = cls._float(item.get(f"pd{i}", 0))
                rec[f"ask_volume_{i}"] = cls._int(item.get(f"qo{i}", 0))
                rec[f"ask_price_{i}"] = cls._float(item.get(f"po{i}", 0))

            records.append(rec)

        return records

    # ── Options (IME) ──────────────────────────────

    @classmethod
    def parse_options(cls, data: Any) -> list[dict[str, Any]]:
        """``/IME/Option.php`` response."""
        items = cls._ensure_list(data)
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        for item in items:
            if not isinstance(item, dict):
                continue
            rec = {
                "contract_category": cls._str(item.get("contract_category", "")),
                "contract_category_sub": cls._str(item.get("contract_category_sub", "")),
                "contract_category_commodity": cls._str(item.get("contract_category_commodity", "")),
                "strike_price": cls._float(item.get("price_strike", 0)),
                "level_strike": cls._str(item.get("level_strike", "")),

                # Call side
                "call_contract_id": cls._int(item.get("call_contract_id", 0)),
                "call_contract_code": cls._str(item.get("call_contract_code", "")),
                "call_contract_description": cls._str(item.get("call_contract_description", "")),
                "call_contract_size": cls._int(item.get("call_contract_size", 0)),
                "call_contract_size_unit": cls._str(item.get("call_contract_size_unit", "")),
                "call_contract_currency": cls._str(item.get("call_contract_currency", "")),
                "call_date_end": cls._str(item.get("call_date_end", "")),
                "call_days_remaining": cls._int(item.get("call_day_remain", 0)),
                "call_margin_initial": cls._float(item.get("call_margin_initial", 0)),
                "call_margin_required": cls._float(item.get("call_margin_required", 0)),
                "call_open_interest": cls._int(item.get("call_interest_open", 0)),
                "call_open_interest_change": cls._int(item.get("call_interest_openc", 0)),
                "call_open_interest_change_pct": cls._float(item.get("call_interest_openp", 0)),
                "call_price_yesterday": cls._float(item.get("call_py", 0)),
                "call_price_first": cls._float(item.get("call_pf", 0)),
                "call_price_first_change": cls._float(item.get("call_pfc", 0)),
                "call_price_first_change_pct": cls._float(item.get("call_pfp", 0)),
                "call_price_max": cls._float(item.get("call_pmax", 0)),
                "call_price_max_change": cls._float(item.get("call_pmaxc", 0)),
                "call_price_max_change_pct": cls._float(item.get("call_pmaxp", 0)),
                "call_price_min": cls._float(item.get("call_pmin", 0)),
                "call_price_min_change": cls._float(item.get("call_pminc", 0)),
                "call_price_min_change_pct": cls._float(item.get("call_pminp", 0)),
                "call_price_last": cls._float(item.get("call_pl", 0)),
                "call_price_last_change": cls._float(item.get("call_plc", 0)),
                "call_price_last_change_pct": cls._float(item.get("call_plp", 0)),
                "call_trade_count": cls._int(item.get("call_tno", 0)),
                "call_trade_volume": cls._int(item.get("call_tvol", 0)),
                "call_trade_value": cls._float(item.get("call_tval", 0)),
                "call_trade_value_unit": cls._str(item.get("call_tval_unit", "")),

                # Put side
                "put_contract_id": cls._int(item.get("put_contract_id", 0)),
                "put_contract_code": cls._str(item.get("put_contract_code", "")),
                "put_contract_description": cls._str(item.get("put_contract_description", "")),
                "put_contract_size": cls._int(item.get("put_contract_size", 0)),
                "put_contract_size_unit": cls._str(item.get("put_contract_size_unit", "")),
                "put_contract_currency": cls._str(item.get("put_contract_currency", "")),
                "put_date_end": cls._str(item.get("put_date_end", "")),
                "put_days_remaining": cls._int(item.get("put_day_remain", 0)),
                "put_margin_initial": cls._float(item.get("put_margin_initial", 0)),
                "put_margin_required": cls._float(item.get("put_margin_required", 0)),
                "put_open_interest": cls._int(item.get("put_interest_open", 0)),
                "put_open_interest_change": cls._int(item.get("put_interest_openc", 0)),
                "put_open_interest_change_pct": cls._float(item.get("put_interest_openp", 0)),
                "put_price_yesterday": cls._float(item.get("put_py", 0)),
                "put_price_first": cls._float(item.get("put_pf", 0)),
                "put_price_first_change": cls._float(item.get("put_pfc", 0)),
                "put_price_first_change_pct": cls._float(item.get("put_pfp", 0)),
                "put_price_max": cls._float(item.get("put_pmax", 0)),
                "put_price_max_change": cls._float(item.get("put_pmaxc", 0)),
                "put_price_max_change_pct": cls._float(item.get("put_pmaxp", 0)),
                "put_price_min": cls._float(item.get("put_pmin", 0)),
                "put_price_min_change": cls._float(item.get("put_pminc", 0)),
                "put_price_min_change_pct": cls._float(item.get("put_pminp", 0)),
                "put_price_last": cls._float(item.get("put_pl", 0)),
                "put_price_last_change": cls._float(item.get("put_plc", 0)),
                "put_price_last_change_pct": cls._float(item.get("put_plp", 0)),
                "put_trade_count": cls._int(item.get("put_tno", 0)),
                "put_trade_volume": cls._int(item.get("put_tvol", 0)),
                "put_trade_value": cls._float(item.get("put_tval", 0)),
                "put_trade_value_unit": cls._str(item.get("put_tval_unit", "")),

                "time": cls._str(item.get("time", "")),
                "date_update": cls._str(item.get("date_update", "")),
                "time_update": cls._str(item.get("time_update", "")),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            }

            # Call orderbook
            for i in range(1, 4):
                rec[f"call_bid_volume_{i}"] = cls._int(item.get(f"call_qd{i}", 0))
                rec[f"call_bid_price_{i}"] = cls._float(item.get(f"call_pd{i}", 0))
                rec[f"call_ask_volume_{i}"] = cls._int(item.get(f"call_qo{i}", 0))
                rec[f"call_ask_price_{i}"] = cls._float(item.get(f"call_po{i}", 0))

            # Put orderbook
            for i in range(1, 4):
                rec[f"put_bid_volume_{i}"] = cls._int(item.get(f"put_qd{i}", 0))
                rec[f"put_bid_price_{i}"] = cls._float(item.get(f"put_pd{i}", 0))
                rec[f"put_ask_volume_{i}"] = cls._int(item.get(f"put_qo{i}", 0))
                rec[f"put_ask_price_{i}"] = cls._float(item.get(f"put_po{i}", 0))

            records.append(rec)

        return records

    # ── Certificates / Depository Receipts ────────

    @classmethod
    def parse_certificates(cls, data: Any) -> list[dict[str, Any]]:
        """``/IME/Certificate.php`` response."""
        items = cls._ensure_list(data)
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        for item in items:
            if not isinstance(item, dict):
                continue
            rec = {
                "commodity": cls._str(item.get("commodity", "")),
                "contract_code": cls._str(item.get("contract_code", "")),
                "contract_description": cls._str(item.get("contract_description", "")),
                "contract_size": cls._int(item.get("contract_size", 0)),
                "contract_size_unit": cls._str(item.get("contract_size_unit", "")),
                "contract_currency": cls._str(item.get("contract_currency", "")),
                "price_yesterday": cls._float(item.get("py", 0)),
                "price_first": cls._float(item.get("pf", 0)),
                "price_first_change": cls._float(item.get("pfc", 0)),
                "price_first_change_pct": cls._float(item.get("pfp", 0)),
                "price_max": cls._float(item.get("pmax", 0)),
                "price_max_change": cls._float(item.get("pmaxc", 0)),
                "price_max_change_pct": cls._float(item.get("pmaxp", 0)),
                "price_min": cls._float(item.get("pmin", 0)),
                "price_min_change": cls._float(item.get("pminc", 0)),
                "price_min_change_pct": cls._float(item.get("pminp", 0)),
                "price_last": cls._float(item.get("pl", 0)),
                "price_last_change": cls._float(item.get("plc", 0)),
                "price_last_change_pct": cls._float(item.get("plp", 0)),
                "trade_count": cls._int(item.get("tno", 0)),
                "trade_volume": cls._int(item.get("tvol", 0)),
                "trade_value": cls._float(item.get("tval", 0)),
                "trade_value_unit": cls._str(item.get("tval_unit", "")),
                "time": cls._str(item.get("time", "")),
                "date_update": cls._str(item.get("date_update", "")),
                "time_update": cls._str(item.get("time_update", "")),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            }

            # Orderbook
            for i in range(1, 4):
                rec[f"bid_volume_{i}"] = cls._int(item.get(f"qd{i}", 0))
                rec[f"bid_price_{i}"] = cls._float(item.get(f"pd{i}", 0))
                rec[f"ask_volume_{i}"] = cls._int(item.get(f"qo{i}", 0))
                rec[f"ask_price_{i}"] = cls._float(item.get(f"po{i}", 0))

            records.append(rec)

        return records

    # ── Commodity Funds ────────────────────────────

    @classmethod
    def parse_funds(cls, data: Any) -> list[dict[str, Any]]:
        """``/IME/Fund.php`` response."""
        items = cls._ensure_list(data)
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        for item in items:
            if not isinstance(item, dict):
                continue
            rec = {
                "symbol": cls._str(item.get("l18", "")),
                "name": cls._str(item.get("l30", "")),
                "isin": cls._str(item.get("isin", "")),
                "ins_id": cls._str(item.get("id", "")),
                "shares_count": cls._int(item.get("z", 0)),
                "base_volume": cls._int(item.get("bvol", 0)),
                "market_value": cls._float(item.get("mv", 0)),
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
                "time": cls._str(item.get("time", "")),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            }

            # Orderbook
            for i in range(1, 6):
                rec[f"bid_count_{i}"] = cls._int(item.get(f"zd{i}", 0))
                rec[f"bid_volume_{i}"] = cls._int(item.get(f"qd{i}", 0))
                rec[f"bid_price_{i}"] = cls._float(item.get(f"pd{i}", 0))
                rec[f"ask_count_{i}"] = cls._int(item.get(f"zo{i}", 0))
                rec[f"ask_volume_{i}"] = cls._int(item.get(f"qo{i}", 0))
                rec[f"ask_price_{i}"] = cls._float(item.get(f"po{i}", 0))

            records.append(rec)

        return records

    # ── Physical Trades ────────────────────────────

    @classmethod
    def parse_physical_trades(cls, data: Any) -> list[dict[str, Any]]:
        """``/IME/Physical.php`` response."""
        items = cls._ensure_list(data)
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        for item in items:
            if not isinstance(item, dict):
                continue
            records.append({
                "symbol": cls._str(item.get("l18", "")),
                "name": cls._str(item.get("l30", "")),
                "category_id": cls._str(item.get("id_category", "")),
                "offer_code": cls._str(item.get("code_offer", "")),
                "market_hall": cls._str(item.get("market_hall", "")),
                "producer": cls._str(item.get("producer", "")),
                "supplier": cls._str(item.get("supplier", "")),
                "broker": cls._str(item.get("broker", "")),
                "contract_type": cls._str(item.get("type_contract", "")),
                "settlement_type": cls._str(item.get("type_settlement", "")),
                "date_price_settlement": cls._str(item.get("date_price_settlement", "")),
                "date_delivery": cls._str(item.get("date_delivery", "")),
                "location_delivery": cls._str(item.get("location_delivery", "")),
                "unit": cls._str(item.get("unit", "")),
                "packaging_type": cls._str(item.get("type_packaging", "")),
                "currency": cls._str(item.get("currency", "")),
                "method_offer": cls._str(item.get("method_offer", "")),
                "method_purchase": cls._str(item.get("method_purchase", "")),
                "date_trade": cls._str(item.get("date_trade", "")),
                "price_base": cls._float(item.get("price_base_offer", 0)),
                "volume_contract": cls._float(item.get("volume_contract", 0)),
                "volume_offer": cls._float(item.get("volume_offer", 0)),
                "demand": cls._float(item.get("demand", 0)),
                "price_min": cls._float(item.get("pmin", 0)),
                "price_max": cls._float(item.get("pmax", 0)),
                "price_close": cls._float(item.get("pl", 0)),
                "price_weighted_avg": cls._float(item.get("pc", 0)),
                "trade_value": cls._float(item.get("tval", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(item, ensure_ascii=False),
            })

        return records

    # ── Helpers ────────────────────────────────────

    @classmethod
    def _ensure_list(cls, data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Some endpoints wrap data in a "data" or "items" key
            for key in ("data", "items", "records", "result"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        logger.warning("IME: unexpected data type %s", type(data).__name__)
        return []

    @staticmethod
    def _str(v: Any) -> str:
        """Safely convert a value to string, handling None and non-string types."""
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        try:
            return str(v)
        except (ValueError, TypeError):
            return ""

    @staticmethod
    def _int(v: Any) -> int:
        if v is None:
            return 0
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _float(v: Any) -> float:
        if v is None:
            return 0.0
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0
