from __future__ import annotations

import json
from datetime import UTC, datetime

from . import ParsedEvent, Parser


class CanonicalMarketDataParser(Parser):
    """Parses normalized ``records`` envelopes emitted by new connectors."""

    def can_parse(self, source: str, endpoint: str, content_type: str) -> bool:
        return source.endswith("_usdt") or source.startswith("global_")

    def source_name(self) -> str:
        return "canonical_market_data"

    async def parse(self, payload: bytes) -> list[ParsedEvent]:
        envelope = json.loads(payload)
        records = envelope.get("records", []) if isinstance(envelope, dict) else []
        now = datetime.now(UTC).isoformat()
        events: list[ParsedEvent] = []
        for record in records:
            if not record.get("instrument") or record.get("price") in (None, ""):
                continue
            data = dict(record)
            data["instrument_id"] = data["instrument"]
            events.append(
                ParsedEvent(
                    source=str(envelope.get("source", "canonical_market_data")),
                    event_type="market_tick",
                    data=data,
                    raw_object_key="",
                    fetch_time=now,
                    parsed_at=now,
                )
            )
        return events
