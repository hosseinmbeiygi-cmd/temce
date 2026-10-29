"""One-shot batch editor, DP cluster (run once, then deletable).

Anchors are matched against LF-normalized text; files are written back CRLF.
"""
from __future__ import annotations

LF = chr(10)
CRLF = chr(13) + chr(10)


def edit(path: str, pairs: list[tuple[str, str]]) -> None:
    with open(path, "rb") as fh:
        raw = fh.read().decode("utf-8")
    b = raw.replace(CRLF, LF)
    for old, new in pairs:
        old_lf = old.replace(CRLF, LF)
        new_lf = new.replace(CRLF, LF)
        assert old_lf in b, f"{path}: ANCHOR NOT FOUND: {old_lf[:80]!r}"
        b = b.replace(old_lf, new_lf, 1)
    b = b.replace(LF, CRLF)
    with open(path, "wb") as fh:
        fh.write(b.encode("utf-8"))
    print("OK", path)


# -- DP-021 docstring: HistoricalDailyModel is UNADJUSTED ------------------
edit("brsapi/models/tsetmc.py", [
(
"class HistoricalDailyModel(InstrumentRefMixin, BrsApiBase):\n    \"\"\"\n    Daily historical price data from ``History.php?type=0``.\n\n    Partitioned by ``date`` (yearly). One row per symbol per day.\n    \"\"\"",
"class HistoricalDailyModel(InstrumentRefMixin, BrsApiBase):\n    \"\"\"\n    Daily historical price data from ``History.php?type=0``.\n\n    Partitioned by ``date`` (yearly). One row per symbol per day.\n\n    Audit DP-021: the TSETMC ``History.php?type=0`` feed stores **raw,\n    unadjusted** prices - they do NOT reflect capital increases, bonus\n    issues or cash dividends. For the adjusted series use\n    ``CandlestickModel`` rows with ``candle_type='3'`` (the adjusted daily\n    feed), or apply ``daily_adjust_factors`` (migration 0061, materialized\n    by ``services/corporate_action_service.py``) to these raw prices.\n    Consumers MUST NOT mix rows from the two series.\n    \"\"\"",
),
])

# -- DP-007: source_timestamp on ingestion storage writes ------------------
edit("ingestion/storage/__init__.py", [
(
"from __future__ import annotations\n\nfrom typing import Any\n\nfrom core.logging import get_logger",
"from __future__ import annotations\n\nfrom datetime import UTC, datetime\nfrom typing import Any\n\nfrom core.logging import get_logger",
),
(
"    async def write_trade_tick(self, instrument_id: str, data: dict[str, Any]) -> None:\n        await self._db.execute(\n            \"\"\"\n            INSERT INTO trade_ticks (instrument_id, trade_date, price, volume, value, trade_count, fetched_at)\n            VALUES ($1, $2, $3, $4, $5, $6, NOW())\n            ON CONFLICT DO NOTHING\n            \"\"\",\n            instrument_id,\n            data.get(\"trade_date\"),\n            data.get(\"price\"),\n            data.get(\"volume\", 0),\n            data.get(\"value\"),\n            data.get(\"trade_count\", 0),\n        )",
"    @staticmethod\n    def _source_time(data: dict[str, Any]) -> datetime:\n        \"\"\"Exchange-side timestamp of the event, when the source provides one.\n\n        Audit DP-007: every write used to be stamped only with NOW() (our\n        fetch time), so a delayed poll looked identical to a live tick and\n        late backfills silently overwrote fresher rows. Parsers that set\n        ``source_time`` / ``observed_at`` / ``timestamp`` / ``trade_date``\n        preserve the exchange's own clock; ``fetched_at`` keeps recording\n        the receive time alongside it.\n        \"\"\"\n        for key in (\"source_time\", \"observed_at\", \"timestamp\", \"trade_date\"):\n            value = data.get(key)\n            if isinstance(value, datetime):\n                return value if value.tzinfo else value.replace(tzinfo=UTC)\n            if isinstance(value, str) and value:\n                try:\n                    parsed = datetime.fromisoformat(value.replace(\"Z\", \"+00:00\"))\n                except ValueError:\n                    continue\n                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)\n        return datetime.now(UTC)\n\n    async def write_trade_tick(self, instrument_id: str, data: dict[str, Any]) -> None:\n        await self._db.execute(\n            \"\"\"\n            INSERT INTO trade_ticks (instrument_id, trade_date, price, volume, value, trade_count, source_timestamp, fetched_at)\n            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())\n            ON CONFLICT DO NOTHING\n            \"\"\",\n            instrument_id,\n            data.get(\"trade_date\"),\n            data.get(\"price\"),\n            data.get(\"volume\", 0),\n            data.get(\"value\"),\n            data.get(\"trade_count\", 0),\n            self._source_time(data),\n        )",
),
(
"            INSERT INTO market_snapshots (\n                instrument_id, last_price, close_price, first_price,\n                high_price, low_price, volume, value, trade_count,\n                yesterday_close, eps, base_volume, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())",
"            INSERT INTO market_snapshots (\n                instrument_id, last_price, close_price, first_price,\n                high_price, low_price, volume, value, trade_count,\n                yesterday_close, eps, base_volume, source_timestamp, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())",
),
(
"            data.get(\"base_volume\"),\n        )",
"            data.get(\"base_volume\"),\n            self._source_time(data),\n        )",
),
(
"            INSERT INTO daily_ohlcv (\n                instrument_id, trade_date, open, high, low, close,\n                volume, value, trade_count, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())",
"            INSERT INTO daily_ohlcv (\n                instrument_id, trade_date, open, high, low, close,\n                volume, value, trade_count, source_timestamp, fetched_at\n            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())",
),
])

# append the source_timestamp param for daily_ohlcv (last param before closing paren)
with open("ingestion/storage/__init__.py", "rb") as fh:
    b = fh.read().decode("utf-8")
old = '            data.get("trade_count", 0),\r\n        )\r\n'
assert old in b, "daily_ohlcv params anchor missing"
b = b.replace(old, '            data.get("trade_count", 0),\r\n            StorageLayer._source_time(data),\r\n        )\r\n', 1)
with open("ingestion/storage/__init__.py", "wb") as fh:
    fh.write(b.encode("utf-8"))
print("OK daily_ohlcv param")

# -- DP-022: corporate-action events reach the storage layer ---------------
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
print("DP BATCH DONE")
