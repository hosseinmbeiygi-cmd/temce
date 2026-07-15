"""
Cryptocurrency price parser.

Maps the ``/Market/Cryptocurrency.php`` JSON response to structured records
for cryptocurrencies with price in USD and IRR/TOMAN.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


class CryptoParser:
    """
    Parses BrsApi cryptocurrency endpoint responses.

    Each item has fields like:
    ``name``, ``price``, ``price_toman``, ``change_percent``,
    ``market_cap``, ``link_icon``, ``date``, ``time``, ``time_unix``.
    """

    @classmethod
    def parse(cls, data: Any) -> list[dict[str, Any]]:
        """
        Parse the cryptocurrency prices response.

        The API may return:
        - A dict of ``{ "Bitcoin": {...}, "Ethereum": {...}, ... }``
        - A list of dicts each with a ``name`` key
        """
        records: list[dict[str, Any]] = []
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"

        items: dict[str, Any] = {}

        if isinstance(data, dict):
            items = data
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "name" in entry:
                    items[entry["name"]] = entry
        else:
            logger.warning("Crypto: unexpected data type %s", type(data).__name__)
            return []

        common_date = data.get("date", "") if isinstance(data, dict) else ""
        common_time = data.get("time", "") if isinstance(data, dict) else ""

        for name, info in items.items():
            if not isinstance(info, dict):
                continue
            rec = {
                "name": name[:100],
                "symbol": info.get("symbol") or info.get("name_en", info.get("name", name))[:20],
                "price_usd": cls._float(info.get("price", info.get("price_usd", 0))),
                "price_toman": cls._float(info.get("price_toman", 0)),
                "price_irr": cls._float(info.get("price_irr", info.get("price_toman", 0))),
                "change_percent": cls._float(info.get("change_percent", 0)),
                "market_cap": cls._float(info.get("market_cap", 0)),
                "volume_24h": cls._float(info.get("volume_24h", 0)),
                "icon_url": (info.get("link_icon") or info.get("icon_url", ""))[:500],
                "rank": cls._int(info.get("rank", info.get("cmc_rank", 0))),
                "date": (info.get("date") or common_date)[:20],
                "time": (info.get("time") or common_time)[:20],
                "time_unix": cls._int(info.get("time_unix", 0)),
                "fetched_at": now,
                "raw_json": json.dumps(info, ensure_ascii=False),
            }
            records.append(rec)

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
