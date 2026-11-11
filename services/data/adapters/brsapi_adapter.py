"""BrsApi source adapter (Assistant 4 source layer).

Pure normalizer: it receives a raw BrsApi payload dict and returns a
:class:`MarketRecord`.  It never opens a network connection and never stores
credentials; any ``token``/``cookie``/``authorization`` keys are stripped.

Source contract (docs/data-sources-phase0.md / docs/phase0-gold-foundation.md):
    value, unit, asOf (ISO + TZ), source="brsapi",
    quality_flag ∈ {LIVE, DELAYED, SAMPLE, EDUCATIONAL}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import BaseAdapter, MarketRecord


class BrsApiAdapter(BaseAdapter):
    source = "brsapi"
    ttl_seconds = 300  # < 5 min LIVE window for BrsApi feeds

    def extract(self, raw: dict[str, Any]) -> dict[str, Any]:
        quality_flag = raw.get("quality_flag") or raw.get("quality")
        return {
            "symbol": raw.get("symbol"),
            "value": raw.get("value"),
            "unit": raw.get("unit"),
            "asOf": raw.get("asOf"),
            "source": raw.get("source"),
            "quality": quality_flag,
        }


def brsapi_normalize(raw: dict[str, Any], now: datetime | None = None) -> MarketRecord:
    return BrsApiAdapter().normalize(raw, now=now)
