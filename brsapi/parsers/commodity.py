"""
Global commodity price parser.

Maps the ``/Market/Commodity.php`` JSON response to structured records
for precious metals, base metals, and energy products.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


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
        records: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()[:30]

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
            logger.warning("Commodity: unexpected data type %s", type(data).__name__)
            return []

        return records

    @staticmethod
    def _int(v: Any) -> int:
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _float(v: Any) -> float:
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0


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
    def parse_crypto(cls, data: Any) -> list[dict[str, Any]]:
        """Extract cryptocurrency records from the combined response."""
        return cls._extract_section(data, "cryptocurrency")

    @classmethod
    def _extract_section(cls, data: Any, section: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()[:30]

        items: list[Any] = []
        if isinstance(data, dict):
            section_data = data.get(section, [])
            if isinstance(section_data, list):
                items = section_data
        elif isinstance(data, list):
            items = data

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
        now = datetime.now(timezone.utc).isoformat()[:30]

        items: list[Any] = []
        if isinstance(data, dict):
            section_data = data.get("cryptocurrency", [])
            if isinstance(section_data, list):
                items = section_data
        elif isinstance(data, list):
            items = data

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
    def _int(v: Any) -> int:
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _float(v: Any) -> float:
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0


class GoldCoinParser:
    """
    Parses BrsApi gold/coin endpoint responses.

    Each item has fields like:
    ``symbol``, ``name``, ``price``, ``change_value``, ``change_percent``.
    """

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()[:30]

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            logger.warning("GoldCoin: unexpected data type %s", type(data).__name__)
            return []

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
        now = datetime.now(timezone.utc).isoformat()[:30]

        items: list[Any] = data if isinstance(data, list) else []
        for item in items:
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
    def _int(v: Any) -> int:
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _float(v: Any) -> float:
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0


class CurrencyParser:
    """
    Parses BrsApi currency/forex endpoint responses.
    """

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()[:30]

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            logger.warning("Currency: unexpected data type %s", type(data).__name__)
            return []

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
        now = datetime.now(timezone.utc).isoformat()[:30]

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            logger.warning("Currency24h: unexpected data type %s", type(data).__name__)
            return []

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
        now = datetime.now(timezone.utc).isoformat()[:30]
        items: list[Any] = data if isinstance(data, list) else []
        for item in items:
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
    def _int(v: Any) -> int:
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _float(v: Any) -> float:
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0


class Gold24hParser:
    """
    Parses 24-hour gold price change data.
    """

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()[:30]

        items: dict[str, Any] = {}
        if isinstance(data, dict):
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "symbol" in entry:
                    items[entry["symbol"]] = entry
        else:
            logger.warning("Gold24h: unexpected data type %s", type(data).__name__)
            return []

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
    def _int(v: Any) -> int:
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _float(v: Any) -> float:
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0
