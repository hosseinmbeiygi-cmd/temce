"""
Global commodity price parser.

Maps the ``/Market/Commodity.php`` JSON response to structured records
for precious metals, base metals, and energy products.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from logging import getLogger
from typing import Any

from brsapi.parsers.errors import BrsApiParseError, ensure_payload, is_no_data

logger = getLogger(__name__)

# Sections of the combined ``Gold_Currency`` / ``Gold_Currency_Pro`` payloads.
# A response that carries other sections but not the requested one is a valid
# empty answer; a response with none of them is an envelope we cannot read.
_GOLD_CURRENCY_SECTIONS = frozenset({"gold", "currency", "cryptocurrency"})


class CommodityParser:
    """
    Parses BrsApi commodity endpoint responses.

    The API returns an object with fields like:
    ``date``, ``time``, ``time_unix``, ``symbol``, ``name``,
    ``price``, ``change_value``, ``change_percent``, ``unit``.
    """

    PRECIOUS_METALS = {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"}
    BASE_METALS = {"COPPER", "ALUMINUM", "ZINC", "LEAD", "NICKEL"}
    ENERGY = {"BRENT", "WTI", "NGAS", "GASOLINE", "GASOIL"}

    @classmethod
    def classify(cls, symbol: str) -> str:
        """Return the commodity category for a given symbol."""
        if symbol.upper() in cls.PRECIOUS_METALS:
            return "precious_metal"
        if symbol.upper() in cls.BASE_METALS:
            return "base_metal"
        if symbol.upper() in cls.ENERGY:
            return "energy"
        return "other"

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        """
        Parse the commodity prices response.

        The API returns a dict with category keys:
        ``{"metal_precious": [...], "metal_base": [...], "energy": [...]}`
        Each category contains a list of price items.
        """
        ensure_payload(data, "Commodity")
        if is_no_data(data):
            return []

        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        # Category mapping from API keys to our classify values
        CATEGORY_MAP = {
            "metal_precious": "precious_metal",
            "metal_base": "base_metal",
            "energy": "energy",
        }

        if isinstance(data, dict):
            # Check if it's a nested structure with category keys
            has_lists = any(isinstance(v, list) for v in data.values())
            if has_lists:
                # Nested structure: {"metal_precious": [...], "metal_base": [...], ...}
                for category_key, items in data.items():
                    if not isinstance(items, list):
                        continue
                    category = CATEGORY_MAP.get(category_key, "other")
                    for entry in items:
                        if not isinstance(entry, dict):
                            continue
                        symbol = entry.get("symbol", "")
                        rec = {
                            "symbol": symbol,
                            "name": entry.get("name", ""),
                            "price": cls._float(entry.get("price", 0)),
                            "change_value": cls._float(entry.get("change_value", 0)),
                            "change_percent": cls._float(entry.get("change_percent", 0)),
                            "unit": entry.get("unit", "USD"),
                            "category": category,
                            "date": entry.get("date", ""),
                            "time": entry.get("time", ""),
                            "time_unix": cls._int(entry.get("time_unix", 0)),
                            "fetched_at": now,
                            "raw_json": json.dumps(entry, ensure_ascii=False),
                        }
                        records.append(rec)
            else:
                # Flat dict: {"XAUUSD": {...}, "XAGUSD": {...}, ...}
                if not any(isinstance(v, dict) for v in data.values()):
                    raise BrsApiParseError(
                        f"Commodity: unrecognised envelope keys {sorted(data)[:5]}",
                        code="unrecognised_envelope",
                    )
                for symbol, info in data.items():
                    if not isinstance(info, dict):
                        continue
                    rec = {
                        "symbol": symbol,
                        "name": info.get("name", ""),
                        "price": cls._float(info.get("price", 0)),
                        "change_value": cls._float(info.get("change_value", 0)),
                        "change_percent": cls._float(info.get("change_percent", 0)),
                        "unit": info.get("unit", "USD"),
                        "category": cls.classify(symbol),
                        "date": info.get("date", ""),
                        "time": info.get("time", ""),
                        "time_unix": cls._int(info.get("time_unix", 0)),
                        "fetched_at": now,
                        "raw_json": json.dumps(info, ensure_ascii=False),
                    }
                    records.append(rec)
        elif isinstance(data, list):
            # List of price items with 'symbol' key
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    symbol = entry.get("symbol", "")
                    rec = {
                        "symbol": symbol,
                        "name": entry.get("name", ""),
                        "price": cls._float(entry.get("price", 0)),
                        "change_value": cls._float(entry.get("change_value", 0)),
                        "change_percent": cls._float(entry.get("change_percent", 0)),
                        "unit": entry.get("unit", "USD"),
                        "category": cls.classify(symbol),
                        "date": entry.get("date", ""),
                        "time": entry.get("time", ""),
                        "time_unix": cls._int(entry.get("time_unix", 0)),
                        "fetched_at": now,
                        "raw_json": json.dumps(entry, ensure_ascii=False),
                    }
                    records.append(rec)
        else:
            raise BrsApiParseError(
                f"Commodity: unexpected data type {type(data).__name__}",
                code="unexpected_shape",
            )

        return records

    @staticmethod
    def _int(v: Any) -> int | None:
        from .numeric import parse_int

        return parse_int(v)

    @staticmethod
    def _float(v: Any) -> float | None:
        from .numeric import parse_float

        return parse_float(v)


class GoldCurrencyParser:
    """
    Parses the combined ``/Market/Gold_Currency.php`` response.

    The API returns ``{"gold": [...], "currency": [...], "cryptocurrency": [...]}``
    where each item has ``symbol``, ``name``, ``price``, ``change_value``,
    ``change_percent``, ``date``, ``time``, ``time_unix``.
    """

    @classmethod
    def parse_gold(cls, data: Any) -> list[dict[str, Any]]:
        """Extract gold & coin records from the combined response."""
        return cls._extract_section(data, "gold")

    @classmethod
    def parse_currency(cls, data: Any) -> list[dict[str, Any]]:
        """Extract currency records from the combined response."""
        return cls._extract_section(data, "currency")

    @classmethod
    def _extract_section(cls, data: Any, section: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        ensure_payload(data, f"Gold_Currency/{section}")
        if is_no_data(data):
            return []

        items: list[Any] = []
        if isinstance(data, dict):
            section_data = data.get(section)
            if isinstance(section_data, list):
                items = section_data
            elif not _GOLD_CURRENCY_SECTIONS.intersection(data):
                raise BrsApiParseError(
                    f"Gold_Currency: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
            # else: the provider answered without this section — a valid empty.
        elif isinstance(data, list):
            items = data
        else:
            raise BrsApiParseError(
                f"Gold_Currency: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for entry in items:
            if not isinstance(entry, dict):
                continue
            records.append({
                "symbol": entry.get("symbol", ""),
                "name": entry.get("name", entry.get("name_en", entry.get("symbol", ""))),
                "price": cls._float(entry.get("price", 0)),
                "change_value": cls._float(entry.get("change_value", 0)),
                "change_percent": cls._float(entry.get("change_percent", 0)),
                "unit": "IRR",
                "date": entry.get("date", ""),
                "time": entry.get("time", ""),
                "time_unix": cls._int(entry.get("time_unix", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(entry, ensure_ascii=False),
            })
        return records

    @classmethod
    def parse_crypto(cls, data: Any) -> list[dict[str, Any]]:
        """
        Extract cryptocurrency records from the combined Gold_Currency.php response.

        CryptoPriceModel uses ``price_usd`` / ``price_toman`` / ``price_irr`` / ``market_cap`` / ``volume_24h``
        fields, which differ from the gold/currency schema.
        """
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        ensure_payload(data, "Gold_Currency/cryptocurrency")
        if is_no_data(data):
            return []

        items: list[Any] = []
        if isinstance(data, dict):
            section_data = data.get("cryptocurrency")
            if isinstance(section_data, list):
                items = section_data
            elif not _GOLD_CURRENCY_SECTIONS.intersection(data):
                raise BrsApiParseError(
                    f"Gold_Currency: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
        elif isinstance(data, list):
            items = data
        else:
            raise BrsApiParseError(
                f"Gold_Currency: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for entry in items:
            if not isinstance(entry, dict):
                continue
            records.append({
                "name": entry.get("name", entry.get("symbol", "")),
                "symbol": entry.get("symbol", ""),
                "price_usd": cls._float(entry.get("price", entry.get("price_usd", 0))),
                "price_toman": cls._float(entry.get("price_toman", 0)),
                "price_irr": cls._float(entry.get("price_irr", entry.get("price_toman", 0))),
                "change_percent": cls._float(entry.get("change_percent", 0)),
                "market_cap": cls._float(entry.get("market_cap", 0)),
                "volume_24h": cls._float(entry.get("volume_24h", 0)),
                "icon_url": entry.get("link_icon", entry.get("icon_url", "")),
                "rank": cls._int(entry.get("rank", entry.get("cmc_rank", 0))),
                "date": entry.get("date", ""),
                "time": entry.get("time", ""),
                "time_unix": cls._int(entry.get("time_unix", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(entry, ensure_ascii=False),
            })
        return records

    @staticmethod
    def _int(v: Any) -> int | None:
        from .numeric import parse_int

        return parse_int(v)

    @staticmethod
    def _float(v: Any) -> float | None:
        from .numeric import parse_float

        return parse_float(v)


class GoldCoinParser:
    """
    Parses BrsApi gold/coin endpoint responses.

    Each item has fields like:
    ``symbol``, ``name``, ``price``, ``change_value``, ``change_percent``.
    """

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        ensure_payload(data, "GoldCoin")
        if is_no_data(data):
            return []

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            if not any(isinstance(v, dict) for v in data.values()):
                raise BrsApiParseError(
                    f"GoldCoin: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            raise BrsApiParseError(
                f"GoldCoin: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for symbol, info in items.items():
            if not isinstance(info, dict):
                continue
            records.append({
                "symbol": symbol,
                "name": info.get("name", ""),
                "price": cls._float(info.get("price", 0)),
                "change_value": cls._float(info.get("change_value", 0)),
                "change_percent": cls._float(info.get("change_percent", 0)),
                "unit": info.get("unit", "IRR"),
                "date": info.get("date", data.get("date", "")),
                "time": info.get("time", data.get("time", "")),
                "time_unix": cls._int(info.get("time_unix", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(info, ensure_ascii=False),
            })
        return records

    @classmethod
    def parse_history(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        ensure_payload(data, "History")
        if is_no_data(data):
            return []
        if not isinstance(data, list):
            raise BrsApiParseError(
                f"History: expected a list, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for item in data:
            if not isinstance(item, dict):
                continue
            records.append({
                "symbol": item.get("symbol", ""),
                "date": item.get("date", ""),
                "price_open": cls._float(item.get("open", 0)),
                "price_high": cls._float(item.get("high", 0)),
                "price_low": cls._float(item.get("low", 0)),
                "price_close": cls._float(item.get("close", item.get("price", 0))),
                "fetched_at": now,
            })
        return records

    @staticmethod
    def _int(v: Any) -> int | None:
        from .numeric import parse_int

        return parse_int(v)

    @staticmethod
    def _float(v: Any) -> float | None:
        from .numeric import parse_float

        return parse_float(v)


class CurrencyParser:
    """
    Parses BrsApi currency/forex endpoint responses.
    """

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        ensure_payload(data, "Currency")
        if is_no_data(data):
            return []

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            if not any(isinstance(v, dict) for v in data.values()):
                raise BrsApiParseError(
                    f"Currency: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            raise BrsApiParseError(
                f"Currency: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for symbol, info in items.items():
            if not isinstance(info, dict):
                continue
            records.append({
                "symbol": symbol,
                "name": info.get("name", info.get("symbol", symbol)),
                "price": cls._float(info.get("price", 0)),
                "change_value": cls._float(info.get("change_value", 0)),
                "change_percent": cls._float(info.get("change_percent", 0)),
                "unit": info.get("unit", "IRR"),
                "date": info.get("date", data.get("date", "")),
                "time": info.get("time", data.get("time", "")),
                "time_unix": cls._int(info.get("time_unix", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(info, ensure_ascii=False),
            })
        return records

    @classmethod
    def parse_24h(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        ensure_payload(data, "Currency24h")
        if is_no_data(data):
            return []

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            if not any(isinstance(v, dict) for v in data.values()):
                raise BrsApiParseError(
                    f"Currency24h: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            raise BrsApiParseError(
                f"Currency24h: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for symbol, info in items.items():
            if not isinstance(info, dict):
                continue
            records.append({
                "symbol": symbol,
                "name": info.get("name", info.get("symbol", symbol)),
                "price_now": cls._float(info.get("price_now", info.get("price", 0))),
                "price_24h_ago": cls._float(info.get("price_24h_ago", 0)),
                "change_value": cls._float(info.get("change_value", 0)),
                "change_percent": cls._float(info.get("change_percent", 0)),
                "high_24h": cls._float(info.get("high_24h", 0)),
                "low_24h": cls._float(info.get("low_24h", 0)),
                "date": info.get("date", data.get("date", "")),
                "time": info.get("time", data.get("time", "")),
                "fetched_at": now,
            })
        return records

    @classmethod
    def parse_history(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"
        ensure_payload(data, "History")
        if is_no_data(data):
            return []
        if not isinstance(data, list):
            raise BrsApiParseError(
                f"History: expected a list, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for item in data:
            if not isinstance(item, dict):
                continue
            records.append({
                "symbol": item.get("symbol", ""),
                "date": item.get("date", ""),
                "price": cls._float(item.get("price", 0)),
                "change_value": cls._float(item.get("change_value", 0)),
                "change_percent": cls._float(item.get("change_percent", 0)),
                "fetched_at": now,
            })
        return records

    @staticmethod
    def _int(v: Any) -> int | None:
        from .numeric import parse_int

        return parse_int(v)

    @staticmethod
    def _float(v: Any) -> float | None:
        from .numeric import parse_float

        return parse_float(v)


class GoldCurrencyProParser:
    """
    Parses the ``/Market/Gold_Currency_Pro.php`` endpoint responses.

    Supports three modes:
    1. ``section=gold|currency|cryptocurrency`` — real-time Pro prices with ``sign``, ``url_base_icon``, ``path_icon``
    2. ``history=1&symbol=XYZ`` — 24-hour tick history
    3. ``history=2&symbol=XYZ&date_start=...&date_end=...`` — daily OHLC history
    """

    @classmethod
    def parse_section(cls, data: Any, section_name: str) -> list[dict[str, Any]]:
        """
        Extract a section (gold, currency, cryptocurrency) from the Pro real-time response.

        The API response structure varies by section::

            **Currency / Crypto (flat list)::**
                {
                    "data": {
                        "currency": [{...}, ...],
                        "cryptocurrency": [{...}, ...]
                    }
                }

            **Gold (nested subcategories)::**
                {
                    "gold": {
                        "ounce":        [{...}, ...],   ← XAUUSD, XAGUSD
                        "type":         [{...}, ...],   ← IR_GOLD_18K, IR_GOLD_24K
                        "coin":         [{...}, ...],   ← IR_COIN_EMAMI, IR_COIN_FULL
                        "coin_parsian": [{...}, ...]    ← optional
                    }
                }

        Both formats are flattened into a single list of records with
        an optional ``subcategory`` field for the nested structure.
        """
        ensure_payload(data, f"Gold_Currency_Pro/{section_name}")
        if is_no_data(data):
            return []

        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        # Resolve top-level icon (shared across all items in the response)
        top_icon_base = cls._str(data.get("url_base_icon", "")) if isinstance(data, dict) else ""

        items: list[dict[str, Any]] = []
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, dict):
                if is_no_data(inner):
                    return []

                section_data = inner.get(section_name)

                if isinstance(section_data, list):
                    # Flat list: [{...}, ...]
                    items = [(None, entry) for entry in section_data if isinstance(entry, dict)]

                elif isinstance(section_data, dict):
                    # Nested subcategories: {"ounce": [{...}], "type": [{...}], ...}
                    for subcat, sub_items in section_data.items():
                        if isinstance(sub_items, list):
                            for entry in sub_items:
                                if isinstance(entry, dict):
                                    items.append((subcat, entry))

                elif not _GOLD_CURRENCY_SECTIONS.intersection(inner):
                    raise BrsApiParseError(
                        "Gold_Currency_Pro: unrecognised envelope keys "
                        f"{sorted(inner)[:5]}",
                        code="unrecognised_envelope",
                    )
                # else: the provider answered without this section.
            else:
                raise BrsApiParseError(
                    "Gold_Currency_Pro: 'data' must be an object or list, "
                    f"got {type(inner).__name__}",
                    code="unexpected_shape",
                )
        elif isinstance(data, list):
            items = [(None, entry) for entry in data if isinstance(entry, dict)]
        else:
            raise BrsApiParseError(
                "Gold_Currency_Pro: expected a list or object, got "
                f"{type(data).__name__}",
                code="unexpected_shape",
            )

        for _subcategory, entry in items:
            rec = {
                "section": section_name,
                "symbol": cls._str(entry.get("symbol", "")),
                "name_en": cls._str(entry.get("name_en", "")),
                "name": cls._str(entry.get("name", "")),
                "sign": cls._str(entry.get("sign", "")),
                "price": cls._float(entry.get("price", 0)),
                "change_value": cls._float(entry.get("change_value", 0)),
                "change_percent": cls._float(entry.get("change_percent", 0)),
                "unit": cls._str(entry.get("unit", "IRR")),
                "url_base_icon": cls._str(entry.get("url_base_icon", "") or top_icon_base),
                "path_icon": cls._str(entry.get("path_icon", "")),
                "date": cls._str(entry.get("date", "") or data.get("date", "")),
                "time": cls._str(entry.get("time", "") or data.get("time", "")),
                "time_unix": cls._int(entry.get("time_unix", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(entry, ensure_ascii=False),
            }
            records.append(rec)
        return records

    @classmethod
    def parse_gold(cls, data: Any) -> list[dict[str, Any]]:
        """Extract gold section from Pro real-time response."""
        return cls.parse_section(data, "gold")

    @classmethod
    def parse_currency(cls, data: Any) -> list[dict[str, Any]]:
        """Extract currency section from Pro real-time response."""
        return cls.parse_section(data, "currency")

    @classmethod
    def parse_crypto(cls, data: Any) -> list[dict[str, Any]]:
        """Extract cryptocurrency section from Pro real-time response."""
        return cls.parse_section(data, "cryptocurrency")

    @classmethod
    def parse_history_24h(cls, data: Any) -> list[dict[str, Any]]:
        """
        Parse 24-hour tick history from ``history=1`` mode.

        The API wraps items in ``data.history_24h`` or returns a list directly.
        Each item has: ``price``, ``time``, ``date``, ``time_unix``.
        """
        ensure_payload(data, "Gold_Currency_Pro/history_24h")
        if is_no_data(data):
            return []

        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        items: list[Any] = []
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, dict):
                history = inner.get("history_24h", inner.get("history"))
                if isinstance(history, list):
                    items = history
                elif is_no_data(inner):
                    return []
                else:
                    raise BrsApiParseError(
                        "Gold_Currency_Pro: neither 'history_24h' nor 'history' "
                        f"is a list (keys {sorted(inner)[:5]})",
                        code="unrecognised_envelope",
                    )
            elif isinstance(inner, list):
                items = inner
            else:
                raise BrsApiParseError(
                    "Gold_Currency_Pro: 'data' must be an object or list, "
                    f"got {type(inner).__name__}",
                    code="unexpected_shape",
                )
        elif isinstance(data, list):
            items = data
        else:
            raise BrsApiParseError(
                "Gold_Currency_Pro: expected a list or object, got "
                f"{type(data).__name__}",
                code="unexpected_shape",
            )

        symbol = ""
        if isinstance(data, dict):
            symbol = cls._str(data.get("symbol", ""))
        for entry in items:
            if not isinstance(entry, dict):
                continue
            records.append({
                "symbol": symbol or cls._str(entry.get("symbol", "")),
                "price": cls._float(entry.get("price", 0)),
                "time": cls._str(entry.get("time", "")),
                "date": cls._str(entry.get("date", "")),
                "time_unix": cls._int(entry.get("time_unix", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(entry, ensure_ascii=False),
            })
        return records

    @classmethod
    def parse_daily_history(cls, data: Any) -> list[dict[str, Any]]:
        """
        Parse daily OHLC history from ``history=2`` mode.

        The API wraps items in ``data.history_daily`` or returns a list directly.
        Each item has: ``symbol``, ``name``, ``sign``, ``unit``, ``url_base_icon``,
        ``path_icon``, ``date``, ``open``, ``high``, ``low``, ``close``.
        """
        ensure_payload(data, "Gold_Currency_Pro/history_daily")
        if is_no_data(data):
            return []

        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        items: list[Any] = []
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, dict):
                history = inner.get("history_daily", inner.get("history"))
                if isinstance(history, list):
                    items = history
                elif is_no_data(inner):
                    return []
                else:
                    raise BrsApiParseError(
                        "Gold_Currency_Pro: neither 'history_daily' nor 'history' "
                        f"is a list (keys {sorted(inner)[:5]})",
                        code="unrecognised_envelope",
                    )
            elif isinstance(inner, list):
                items = inner
            else:
                raise BrsApiParseError(
                    "Gold_Currency_Pro: 'data' must be an object or list, "
                    f"got {type(inner).__name__}",
                    code="unexpected_shape",
                )
        elif isinstance(data, list):
            items = data
        else:
            raise BrsApiParseError(
                "Gold_Currency_Pro: expected a list or object, got "
                f"{type(data).__name__}",
                code="unexpected_shape",
            )

        for entry in items:
            if not isinstance(entry, dict):
                continue
            records.append({
                "symbol": cls._str(entry.get("symbol", "")),
                "name": cls._str(entry.get("name", "")),
                "sign": cls._str(entry.get("sign", "")),
                "unit": cls._str(entry.get("unit", "IRR")),
                "url_base_icon": cls._str(entry.get("url_base_icon", "")),
                "path_icon": cls._str(entry.get("path_icon", "")),
                "date": cls._str(entry.get("date", "")),
                "price_open": cls._float(entry.get("open")),
                "price_high": cls._float(entry.get("high")),
                "price_low": cls._float(entry.get("low")),
                "price_close": cls._float(entry.get("close")),
                "fetched_at": now,
                "raw_json": json.dumps(entry, ensure_ascii=False),
            })
        return records

    @staticmethod
    def _str(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        try:
            return str(v)
        except (ValueError, TypeError):
            return ""

    @staticmethod
    def _int(v: Any) -> int | None:
        from .numeric import parse_int

        return parse_int(v)

    @staticmethod
    def _float(v: Any) -> float | None:
        from .numeric import parse_float

        return parse_float(v)


class Gold24hParser:
    """
    Parses 24-hour gold price change data.
    """

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        ensure_payload(data, "Gold24h")
        if is_no_data(data):
            return []

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            if not any(isinstance(v, dict) for v in data.values()):
                raise BrsApiParseError(
                    f"Gold24h: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            raise BrsApiParseError(
                f"Gold24h: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        for symbol, info in items.items():
            if not isinstance(info, dict):
                continue
            records.append({
                "symbol": symbol,
                "name": info.get("name", info.get("symbol", symbol)),
                "price_now": cls._float(info.get("price_now", info.get("price", 0))),
                "price_24h_ago": cls._float(info.get("price_24h_ago", 0)),
                "change_value": cls._float(info.get("change_value", 0)),
                "change_percent": cls._float(info.get("change_percent", 0)),
                "high_24h": cls._float(info.get("high_24h", 0)),
                "low_24h": cls._float(info.get("low_24h", 0)),
                "date": info.get("date", data.get("date", "")),
                "time": info.get("time", data.get("time", "")),
                "fetched_at": now,
            })
        return records

    @staticmethod
    def _int(v: Any) -> int | None:
        from .numeric import parse_int

        return parse_int(v)

    @staticmethod
    def _float(v: Any) -> float | None:
        from .numeric import parse_float

        return parse_float(v)
