"""DP batch, part 2: corrected anchors (run once, then deletable)."""
from __future__ import annotations

LF = chr(10)
CRLF = chr(13) + chr(10)


def edit(path: str, pairs: list[tuple[str, str]]) -> None:
    raw = open(path, "rb").read().decode("utf-8")
    b = raw.replace(CRLF, LF)
    for old, new in pairs:
        old_lf = old.replace(CRLF, LF)
        new_lf = new.replace(CRLF, LF)
        assert old_lf in b, f"{path}: ANCHOR NOT FOUND: {old_lf[:80]!r}"
        b = b.replace(old_lf, new_lf, 1)
    b = b.replace(LF, CRLF)
    open(path, "wb").write(b.encode("utf-8"))
    print("OK", path)


# finish DP-007 edits on storage (corrected anchors)
edit("ingestion/storage/__init__.py", [
(
"            INSERT INTO market_snapshots (\n                instrument_id, last_price, close_price, first_price,\n                high_price, low_price, volume, value, trade_count,\n                yesterday_close, eps, base_volume, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())",
"            INSERT INTO market_snapshots (\n                instrument_id, last_price, close_price, first_price,\n                high_price, low_price, volume, value, trade_count,\n                yesterday_close, eps, base_volume, source_timestamp, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())",
),
(
"            data.get(\"base_volume\", 0),\n        )",
"            data.get(\"base_volume\", 0),\n            self._source_time(data),\n        )",
),
(
"            INSERT INTO daily_ohlcv (\n                instrument_id, trade_date, open, high, low, close,\n                volume, value, trade_count, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())",
"            INSERT INTO daily_ohlcv (\n                instrument_id, trade_date, open, high, low, close,\n                volume, value, trade_count, source_timestamp, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())",
),
(
"            data.get(\"close_price\") or data.get(\"close\"),\n            data.get(\"volume\", 0),\n            data.get(\"value\"),\n            data.get(\"trade_count\", 0),\n        )",
"            data.get(\"close_price\") or data.get(\"close\"),\n            data.get(\"volume\", 0),\n            data.get(\"value\"),\n            data.get(\"trade_count\", 0),\n            self._source_time(data),\n        )",
),
])

# DP-022: worker route + storage writer
edit("ingestion/worker.py", [
(
'            elif event_type == "daily_ohlcv":\n                await self._storage.write_daily_ohlcv(instrument_id, event.data)',
'            elif event_type == "daily_ohlcv":\n                await self._storage.write_daily_ohlcv(instrument_id, event.data)\n            elif event_type == "price_adjustment":\n                # Audit DP-022: corporate-action events were parsed but had\n                # no storage path - they evaporated between the source and\n                # the warehouse, leaving the adjust-factor materializer with\n                # nothing to consume.\n                await self._storage.write_corporate_action(instrument_id, event.data)',
),
])

edit("ingestion/storage/__init__.py", [
(
"    async def write_daily_ohlcv(self, instrument_id: str, data: dict[str, Any]) -> None:",
"    async def write_corporate_action(self, instrument_id: str, data: dict[str, Any]) -> None:\n        \"\"\"Persist a corporate-action event (audit DP-022).\n\n        The ``price_adjustment`` events emitted by the tse_utils source land\n        in ``corporate_action_events`` (migration 0061) so\n        ``services/corporate_action_service.py`` can materialize adjust\n        factors from them. Unknown symbols are skipped (the FK on symbol_id\n        would otherwise reject the row).\n        \"\"\"\n        code = str(data.get(\"tsetmc_code\") or instrument_id or \"\")\n        if not code:\n            return\n        symbol_id: int | None = None\n        if code.isdigit():\n            symbol_id = int(code)\n        else:\n            try:\n                row = await self._db.execute(\n                    \"SELECT id FROM symbols WHERE symbol = $1 LIMIT 1\",\n                    code,\n                )\n                symbol_id = int(row[0][0]) if row else None\n            except Exception:\n                logger.debug(\"corporate action: symbol lookup failed for %s\", code, exc_info=True)\n                return\n        if symbol_id is None:\n            logger.debug(\"corporate action: unknown symbol %s - skipped\", code)\n            return\n        await self._db.execute(\n            \"\"\"\n            INSERT INTO corporate_action_events (symbol_id, ex_date, action_type, ratio, dps, source)\n            VALUES ($1, COALESCE($2::date, CURRENT_DATE), $3, $4, 0, 'import')\n            ON CONFLICT (symbol_id, ex_date, action_type) DO UPDATE SET\n                ratio = EXCLUDED.ratio\n            \"\"\",\n            symbol_id,\n            data.get(\"date\"),\n            \"capital_increase\",\n            data.get(\"adjusted_price\") or 0,\n        )\n\n    async def write_daily_ohlcv(self, instrument_id: str, data: dict[str, Any]) -> None:",
),
])
print("DP BATCH 2 DONE")
