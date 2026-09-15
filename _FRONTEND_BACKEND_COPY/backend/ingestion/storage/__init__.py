from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class StorageLayer:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def write_trade_tick(self, instrument_id: str, data: dict[str, Any]) -> None:
        await self._db.execute(
            """
            INSERT INTO trade_ticks (instrument_id, trade_date, price, volume, value, trade_count, fetched_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT DO NOTHING
            """,
            instrument_id,
            data.get("trade_date"),
            data.get("price"),
            data.get("volume", 0),
            data.get("value"),
            data.get("trade_count", 0),
        )

    async def write_market_snapshot(self, instrument_id: str, data: dict[str, Any]) -> None:
        await self._db.execute(
            """
            INSERT INTO market_snapshots (
                instrument_id, last_price, close_price, first_price,
                high_price, low_price, volume, value, trade_count,
                yesterday_close, eps, base_volume, fetched_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
            """,
            instrument_id,
            data.get("last_price"),
            data.get("close_price"),
            data.get("first_price"),
            data.get("high_price"),
            data.get("low_price"),
            data.get("volume", 0),
            data.get("value"),
            data.get("trade_count", 0),
            data.get("yesterday_close"),
            data.get("eps"),
            data.get("base_volume", 0),
        )

    async def write_orderbook_level(self, instrument_id: str, data: dict[str, Any]) -> None:
        await self._db.execute(
            """
            INSERT INTO orderbook_events (
                instrument_id, side, price, volume, order_count, rank, fetched_at
            ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """,
            instrument_id,
            data.get("side"),
            data.get("price"),
            data.get("volume", 0),
            data.get("order_count", 0),
            data.get("rank", 0),
        )

    async def write_daily_ohlcv(self, instrument_id: str, data: dict[str, Any]) -> None:
        await self._db.execute(
            """
            INSERT INTO daily_ohlcv (
                instrument_id, trade_date, open, high, low, close,
                volume, value, trade_count, fetched_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            ON CONFLICT (instrument_id, trade_date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                value = EXCLUDED.value,
                trade_count = EXCLUDED.trade_count
            """,
            instrument_id,
            data.get("trade_date"),
            data.get("first_price") or data.get("open"),
            data.get("high_price") or data.get("high"),
            data.get("low_price") or data.get("low"),
            data.get("close_price") or data.get("close"),
            data.get("volume", 0),
            data.get("value"),
            data.get("trade_count", 0),
        )

    async def write_market_tick(self, instrument_id: str, data: dict[str, Any], source: str) -> None:
        await self._db.execute(
            """
            INSERT INTO market_ticks (
                source, instrument, asset_class, observed_at, received_at,
                price, bid, ask, open, high, low, close, volume, value,
                currency, decision_basis, quality_flag, quality_reasons, raw_object_key, raw_sha256, metadata
            ) VALUES (
                $1, $2, $3, COALESCE($4::timestamptz, NOW()), NOW(),
                $5, $6, $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17::jsonb, $18, $19, $20::jsonb
            )
            ON CONFLICT (source, instrument, observed_at) DO UPDATE SET
                price = EXCLUDED.price,
                bid = EXCLUDED.bid,
                ask = EXCLUDED.ask,
                quality_flag = EXCLUDED.quality_flag,
                decision_basis = EXCLUDED.decision_basis,
                quality_reasons = EXCLUDED.quality_reasons,
                received_at = EXCLUDED.received_at,
                metadata = EXCLUDED.metadata
            """,
            source,
            instrument_id,
            data.get("asset_class", "unknown"),
            data.get("observed_at"),
            data.get("price"),
            data.get("bid"),
            data.get("ask"),
            data.get("open"),
            data.get("high"),
            data.get("low"),
            data.get("close"),
            data.get("volume"),
            data.get("value"),
            data.get("currency", "IRR"),
            data.get("decision_basis", "dual"),
            data.get("quality", "clean"),
            json.dumps(data.get("quality_reasons", []), ensure_ascii=False),
            data.get("raw_object_key"),
            data.get("raw_sha256"),
            json.dumps(data.get("metadata", {}), ensure_ascii=False, default=str),
        )
