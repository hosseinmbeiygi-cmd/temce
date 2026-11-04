"""Freshness / staleness marker (Assistant 4 source layer, phase 3).

Standalone adapter wrapping :meth:`BaseAdapter.freshness_mark` so any record
carrying ``asOf`` can be turned into the gate dict consumed by Assistant 1's
``data_stale`` gate:

    {"ageSeconds": <int|null>, "freshness": "fresh"|"stale"|"unknown", "staleFlag": <bool>}

Rule (docs/phase3-decision-assistant.md): ageSeconds > TTL (default 900 s for
LIVE) ⇒ quality DELAYED/SAMPLE and ``staleFlag=True``.  Stale data is never
promoted to LIVE.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import BaseAdapter, MarketRecord


class FreshnessAdapter(BaseAdapter):
    source = "freshness_marker"

    def extract(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {}

    def mark(self, record: MarketRecord, now: datetime | None = None) -> dict[str, Any]:
        return self.freshness_mark(record, now=now)


def freshness_mark(record: MarketRecord, now: datetime | None = None) -> dict[str, Any]:
    return FreshnessAdapter().mark(record, now=now)
