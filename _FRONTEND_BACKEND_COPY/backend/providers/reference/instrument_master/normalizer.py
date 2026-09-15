from __future__ import annotations

import re
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


PERSIAN_TO_ENGLISH = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)


class InstrumentNormalizer:
    def normalize_symbol(self, symbol: str) -> str:
        s = symbol.strip().translate(PERSIAN_TO_ENGLISH)
        s = re.sub(r"[^آ-ی\w]", "", s)
        return s.upper()

    def normalize_name(self, name: str) -> str:
        return re.sub(r"\s+", " ", name.strip())

    def normalize_instrument(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        if "symbol" in normalized:
            normalized["symbol"] = self.normalize_symbol(normalized["symbol"])
        if "name" in normalized:
            normalized["name"] = self.normalize_name(normalized["name"])
        if "market" in normalized:
            normalized["market"] = normalized["market"].strip().lower()
        return normalized

    def normalize_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.normalize_instrument(row) for row in data]
