# TEMCE Audit Report - Phase 3: Databases, Schema, Repositories and Storage Integrity
## Data Persistence: Schema → Writer → Query → Frontend

### Repository State
- **Branch**: integration/golddesk-fixes
- **HEAD Commit**: 90597e05b9f4328bcd82ee819a31ba5c55413c12
- **Report Date**: 2026-10-27

### 1. Core ORM Models Overview

#### `SymbolSnapshotModel` (`brsapi/models/tsetmc.py`)
**Table**: `brsapi_symbol_snapshots`  
**Unique Constraint**: `UniqueConstraint("symbol", "fetched_at", name="uq_snap_symbol_fetched")`  
**Purpose**: Core realtime price & volume data. One row per symbol per fetch cycle.

**Critical Schema Details**:
- `fetched_at: DateTime, index=True` - Indexed for "latest" queries
- `created_at: DateTime, server_default=func.now(), index=True` - Insertion time
- `ins_id: String(50), index=True` - TSETMC internal ID
- `symbol: String(50), index=True, nullable=False` - Trading symbol
- **Unique constraint on (symbol, fetched_at)** prevents duplicate snapshots

**Key Price Fields**:
- `price_last`, `price_close`, `price_first`, `price_min`, `price_max`
- `trade_count`, `trade_volume`, `trade_value`
- `buy_real_count`, `sell_legal_count`, etc. (real/legal breakdown)

**Index Layout**:
```sql
Index("idx_snap_ins_fetched", "ins_id", "fetched_at"),
Index("idx_snap_symbol_fetched", "symbol", "fetched_at"),
UniqueConstraint("symbol", "fetched_at", name="uq_snap_symbol_fetched"),
```

#### `SymbolDetailModel` (`brsapi/models/tsetmc.py`)
**Table**: `brsapi_symbol_details`  
**Primary Key**: `ins_id` (unique)  
**Purpose**: Enriched symbol detail (sector, market, fundamentals) - one row per symbol

**Key Fields**:
- `sector`, `sub_sector`, `market`, `board`
- `free_float_pct`, `eps`, `pe_ratio`, `group_pe_ratio`
- `price_lowest_allowed` (tmin), `price_highest_allowed` (tmax)

#### `IndexValueModel` (`brsapi/models/tsetmc.py`)
**Table**: `brsapi_index_values`  
**Dedup Strategy**: Windowed dedup (last 50,000 IDs) + GROUP BY fallback

**Key Query** (`get_latest_snapshots`):
1. Find `max_id = SELECT MAX(id) FROM SymbolSnapshotModel`
2. Windowed dedup: `SELECT symbol, MAX(id) FROM SymbolSnapshotModel WHERE id > max_id - 50000 GROUP BY symbol`
3. Join back to get full rows
4. Fallback to full `GROUP BY symbol` if window query fails

#### `NavRecordModel` (`brsapi/models/tsetmc.py`)
**Table**: `brsapi_nav_records`  
**Query**: `ORDER BY created_at DESC LIMIT 1` per symbol

#### `HistoricalDailyModel` (`brsapi/models/tsetmc.py`)
**Table**: `brsapi_historical_daily`  
**Partitioning**: By `date` (yearly, PK on (id, date))  
**Query**: `ORDER BY date DESC LIMIT limit` per symbol

#### `CandlestickModel` (`brsapi/models/tsetmc.py`)
**Table**: `brsapi_candlesticks`  
**Unique Constraint**: `UniqueConstraint("symbol", "date", "time", "candle_type", name="uq_candle_symbol_date_time_type")`  
**Dual Date**: `shamsi_date` (Jalali) + `gregorian_date` (derived)

---

### 2. Bulk Upsert Repository (`brsapi/repositories/base.py`)

#### `BulkUpsertRepository.bulk_insert()`
**Two modes**:

**Mode 1: `on_conflict_update=False` (default)** - `ON CONFLICT DO NOTHING`
```python
conflict_sql = "ON CONFLICT DO NOTHING"
```
- Silent skip on primary key collision
- Useful when you want to keep the first-inserted row
- **Risk**: Without unique constraint on (symbol, fetched_at), table grows unboundedly

**Mode 2: `on_conflict_update=True`** - `ON CONFLICT DO UPDATE SET`
```python
conflict_sql = f"ON CONFLICT ({target_sql}) DO UPDATE SET {update_clause}"
```
- **Requires**: `conflict_target` parameter (e.g., `["symbol", "fetched_at"]`)
- Updates conflicting row with latest values
- **Critical**: Must match the UniqueConstraint columns

**`truncate()` Method**:
- Executes `TRUNCATE TABLE "table_name"` 
- **Warning**: "use with caution — for full-refresh endpoints only"
- No soft delete, no validation, immediate data loss

**`get_latest_by_symbol(symbol, limit=1, order_column="fetched_at")`**:
- Gets most recent rows for a given symbol
- Default order by `fetched_at` DESC
- Falls back to `created_at` if `order_column` not found

---

### 3. Storage Layer (`ingestion/storage/__init__.py` → `layered_pipeline.py`)

#### `StorageLayer.write_market_snapshot()`
**INSERT syntax**:
```sql
INSERT INTO market_snapshots (
    instrument_id, last_price, close_price, first_price,
    high_price, low_price, volume, value, trade_count,
    yesterday_close, eps, base_volume, fetched_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
```
- Uses `NOW()` for `fetched_at` (server time)
- All fields use `.get()` with defaults (0 or None)
- `instrument_id` is required

**`StorageLayer.write_daily_ohlcv()`**:
```sql
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
```
- **Upsert on (instrument_id, trade_date)** - updates existing day's data
- Fields with `or data.get("field", default)` patterns
- **Risk**: `data.get("first_price") or data.get("open")` - if `first_price` is 0 (falsy!), falls through to `open`

#### `StorageLayer.write_trade_tick()`:
```sql
INSERT INTO trade_ticks (instrument_id, trade_date, price, volume, value, trade_count, fetched_at)
VALUES ($1, $2, $3, $4, $5, $6, NOW())
ON CONFLICT DO NOTHING
```
- Simple insert with `ON CONFLICT DO NOTHING`
- No upsert logic

#### `StorageLayer.write_orderbook_level()`:
```sql
INSERT INTO orderbook_events (instrument_id, side, price, volume, order_count, rank, fetched_at)
VALUES ($1, $2, $3, $4, $5, $6, NOW())
```
- No conflict resolution

---

### 4. Dedup Mechanisms

#### Redis Dedup (`ingestion/storage/dedup.py`)
```python
class DeduplicationEngine:
    def __init__(self, redis_client, window_minutes=60):
        self._redis = redis_client
        self._window = timedelta(minutes=window_minutes)

    def _make_key(self, source, payload):
        content_hash = hashlib.sha256(payload).hexdigest()
        return f"dedup:{source}:{content_hash}"

    async def is_duplicate(self, source, payload):
        key = self._make_key(source, payload)
        return bool(await self._redis.exists(key))

    async def mark_seen(self, source, payload):
        key = self._make_key(source, payload)
        await self._redis.setex(key, int(self._window.total_seconds()), "1")
```
- **Key**: `dedup:{source}:{sha256_of_payload}`
- **TTL**: `window_minutes` (default 60 minutes)
- **Purpose**: In-memory/Redis dedup before DB insert

#### PostgreSQL Unique Constraint (`SymbolSnapshotModel`)
```python
UniqueConstraint("symbol", "fetched_at", name="uq_snap_symbol_fetched")
```
- **Database-level dedup**: Prevents insert if (symbol, fetched_at) already exists
- **Bulk insert**: `BulkUpsertRepository.bulk_insert(on_conflict_update=True, conflict_target=["symbol", "fetched_at"])`
- **Without this constraint**: Table grows unboundedly, every sync appends new row

#### Pipeline Dedup (`layered_pipeline.py`):
```python
def _dedup_key(symbol, fetched_at):
    minute = fetched_at[:16]  # 2026-09-13T01:23
    raw = f"{symbol}:{minute}"
    return f"armor:dedup:{hashlib.md5(raw.encode()).hexdigest()[:12]}"
```
- **Minute bucket**: Truncates `fetched_at` to minute precision
- **Redis SETNX**: `armor:dedup:{hash}` with TTL 3600s
- **Order**: Hot (Redis) first, then Warm (Postgres)

**Pipeline store flow** (`pipeline_store`):
1. For each row: try `store_hot(sym, r, r["fetched_at"])`
2. If hot stored → append to warm_batch
3. If hot deduped → skip (but still may go to warm if Redis unavailable)
4. `warm_stored = await store_warm(warm_batch)` - bulk upsert

**Critical gap**: If Redis is unavailable, `store_hot` returns False, and the code does:
```python
with contextlib.suppress(Exception):
    from core.cache import get_cache
    if not get_cache().is_connected:
        warm_batch.append(r)
        hot_stored += 1  # Counts as hot-missed but warm will get it
```
- **Problem**: When Redis down, counts `hot_stored += 1` even though hot wasn't actually stored. Metrics become inaccurate.

---

### 5. Timestamp Semantics Analysis

#### Column Definitions Across Models

| Model | Column | Type | Default | Purpose |
|-------|--------|------|---------|---------|
| `SymbolSnapshotModel` | `fetched_at` | DateTime | None | **Market timestamp** - when the data was fetched from source |
| `SymbolSnapshotModel` | `created_at` | DateTime | `func.now()` | **Insertion time** - when row was inserted into DB |
| `RawPayloadModel` | `fetched_at` | DateTime | `datetime.now` | Client receive time (naive UTC) |
| `RawPayloadModel` | `market_time` | DateTime | None | Market timestamp inside the payload |
| `SyncLogModel` | `started_at` | DateTime | `datetime.now` | Sync operation start |
| `SyncLogModel` | `completed_at` | DateTime | None | Sync operation completion |
| `IndexValueModel` | `fetched_at` | DateTime | None | Fetch timestamp |
| `IndexValueModel` | `created_at` | DateTime | `func.now()` | Insertion timestamp |
| `NavRecordModel` | `fetched_at` | String(30) | None | Stored as string, not DateTime |
| `HistoricalDailyModel` | `created_at` | DateTime | `func.now()` | Insertion time |
| `CandlestickModel` | `created_at` | DateTime | `func.now()` | Insertion time |
| `BrsApiDailyUsageModel` | `updated_at` | DateTime | `func.now()` onupdate | Last update timestamp |

#### Key Semantic Issues

**Issue 1: `fetched_at` = Server Time vs Source Time**
- `StorageLayer.write_market_snapshot()` uses `NOW()` (server time)
- But parsers set `event.parsed_at = datetime.now(UTC).isoformat()` (also server time)
- **Question**: Should `fetched_at` reflect when the API responded, or when the market data was generated?
- **Risk**: If `NOW()` is used consistently, all snapshots from same sync cycle have identical `fetched_at`, which combined with the UniqueConstraint on (symbol, fetched_at) means only ONE row per sync cycle survives (the `ON CONFLICT DO NOTHING` keeps the first).

**Issue 2: `created_at` vs `fetched_at` for "Latest" Queries**
- `get_latest_snapshots()` uses `MAX(SymbolSnapshotModel.id)` in a window, NOT `MAX(fetched_at)`
- `get_symbol_snapshot()` orders by `SymbolSnapshotModel.created_at.desc().limit(1)`
- **Inconsistency**: Some queries use `id` (insertion order), some use `created_at`, some use `fetched_at`

**Issue 3: `NavRecordModel.fetched_at` is String, not DateTime**
```python
fetched_at: Mapped[str | None] = mapped_column(String(30))
```
- Stored as string, making date-based queries harder
- No index (unlike other models' DateTime `fetched_at`)

**Issue 4: Naive vs Aware UTC**
- `RawPayloadModel.purge_older_than()` comment: "`fetched_at` is stored as a naive `utc_now_naive()`"
- Mixing aware/naive UTC in cutoffs would "silently miss or over-delete rows"
- **Risk**: If DB stores aware UTC but cutoff uses naive, or vice versa, deletion behavior is unpredictable

**Issue 5: `price_first` or `data.get("open")` Falsy Problem**
```python
data.get("first_price") or data.get("open")
```
- If `first_price` is `0`, `0 or open` evaluates to `open` (wrong!)
- Should use: `data.get("first_price") if data.get("first_price") is not None else data.get("open")`

---

### 6. Repository: `needs_sync()` Verification

#### `SyncLogRepository.needs_sync()` (`brsapi/repositories/base.py`)
```python
async def needs_sync(self, endpoint, interval_seconds=60):
    last = await self.last_sync(endpoint)
    if last is None:
        return True
    if last.completed_at is None:
        return True
    elapsed = (utc_now_naive() - last.completed_at).total_seconds()
    return elapsed >= interval_seconds
```

**Test Coverage** (15/15 pass):
- ✅ `test_needs_sync_no_previous_sync` - No sync record → True
- ✅ `test_needs_sync_no_completed_at` - completed_at is None → True
- ✅ `test_needs_sync_within_interval` - 10s elapsed < 60s interval → False
- ✅ `test_needs_sync_custom_interval` - 30s < 50s custom → False
- ✅ `test_needs_sync_expired_interval` - 70s > 60s → True
- ✅ `test_needs_sync_exact_interval_boundary` - 60s == 60s → True (boundary case)
- ✅ `test_needs_sync_zero_interval` - 0s interval → always True
- ✅ `test_needs_sync_large_interval` - 30s < 86400s (1 day) → False
- ✅ `test_needs_sync_multiple_syncs_decreasing_interval` - Most recent used
- ✅ `test_needs_sync_recent_multiple_syncs` - Most recent (not first) used

**Logic Summary**:
1. No sync record → always needs sync (True)
2. Sync exists but no completed_at → needs sync (True)  
3. Elapsed < interval → skip sync (False)
4. Elapsed >= interval → needs sync (True)
5. Elapsed == interval → needs sync True (boundary inclusive)
6. Zero interval → always sync (True)
7. Large interval (1 day) → skip if recently synced (False)
8. Multiple syncs → uses MOST RECENT completed_at (not first)

---

### 7. Writer/Query Consistency Issues

#### Issue A: `fetched_at` Determines "Latest" but Server Time is Used
**Problem**: Multiple sync cycles within the same second produce identical `fetched_at` (server `NOW()`).  
**With UniqueConstraint("(symbol, fetched_at)")**: Only one row per (symbol, second) survives.  
**Result**: Data from later in the same second is silently dropped (`ON CONFLICT DO NOTHING`).

**Evidence**: The unique constraint comment says: "Without this the table grows unboundedly and the latest-wins DISTINCT ON (symbol) query in the alert/quote jobs keeps seeing stale rows."

**Fix Option**: Use `created_at` as tie-breaker, or include microsecond precision, or use a sequence number.

#### Issue B: `get_latest_by_symbol()` Order Ambiguity
```python
async def get_latest_by_symbol(self, symbol, limit=1, order_column="fetched_at"):
    col = getattr(self.model_class, order_column, None)
    if col is None:
        col = self.model_class.created_at  # Fallback!
    stmt = select(self.model_class).where(self.model_class.symbol == symbol).order_by(col.desc()).limit(limit)
```
- If `order_column` is invalid (not a model attribute), falls back to `created_at`
- But `order_column="fetched_at"` IS a valid column on `SymbolSnapshotModel`
- **Risk**: Caller might pass arbitrary string, falls back silently to `created_at`

#### Issue C: `StorageLayer.write_daily_ohlcv()` Falsy Default
```python
data.get("first_price") or data.get("open")
```
- If `first_price=0`: `0 or open` → `open` (wrong! should be 0)
- If `first_price=None`: `None or open` → `open` (correct)
- If `first_price=5.0`: `5.0 or open` → `5.0` (correct)
- **Fix**: Use `if data.get("first_price") is not None else data.get("open")`

#### Issue D: `NavRecordModel.fetched_at` as String
- Stored as `String(30)`, not `DateTime`
- Queries like `order_by(NavRecordModel.created_at.desc())` work, but date-based filtering is harder
- **Risk**: Inconsistent querying, potential format mismatches

---

### 8. Changes Made (This Session)

No changes were made to database schema, repository logic, or storage layer in this session. The focus was on:
1. ✅ `needs_sync()` tests (15/15 pass - Phase 1)
2. ✅ `useMarketData.ts` isDataFresh future date guard (Phase 1)
3. 📋 **Pending**: Market source/parser analysis (Phase 1)
4. 📋 **Pending**: Scheduler/worker/queue analysis (Phase 2)

**Files Modified**: None (only verification and testing)

---

### 9. Acceptance Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 15/15 needs_sync tests pass | ✅ | `python -m pytest ... -v` output |
| isDataFresh future date guard | ✅ | Git diff verified |
| No BrsApi live requests | ✅ | Logs verified |
| No secret exposure | ✅ | Redacted in output |
| Test before claiming success | ✅ | All tests verified |

---

### 10. Blocked / Unverified

1. **Full database schema verification** - Requires PostgreSQL environment (not locally available)
2. **Live data pipeline execution** - Requires BrsApi access (blocked)
3. **Dedup edge cases** - (symbol, fetched_at) uniqueness with microsecond precision
4. **Falsy value handling** - `0 or x` pattern in StorageLayer
5. **NavRecordModel string timestamp** - Format and query behavior
6. **Full pipeline end-to-end** - Source → parser → lake → DB → query → frontend

---

### 11. Recommended Next Steps

1. **Fix StorageLayer falsy patterns**:
   ```python
   # Before (buggy):
   data.get("first_price") or data.get("open")
   
   # After (safe):
   data.get("first_price") if data.get("first_price") is not None else data.get("open")
   ```

2. **Standardize timestamp semantics**:
   - Decide: `fetched_at` = source fetch time vs server receive time
   - If source time: parse and store `market_time` from API response
   - If server time: consistent use of `NOW()` or `utc_now_naive()`
   - Document the convention and enforce it

3. **Add DB-level dedup tests**:
   - Insert duplicate (symbol, fetched_at) rows
   - Verify UniqueConstraint raises or ON CONFLICT works
   - Test `bulk_insert(on_conflict_update=True, conflict_target=["symbol", "fetched_at"])`

4. **Fix `NavRecordModel.fetched_at`**:
   - Change to `DateTime` type if possible
   - Or add conversion layer for string-to-datetime queries
   - Or document the string format and enforce it

5. **Verify `get_latest_by_symbol()` behavior**:
   - Test with various `order_column` values
   - Test fallback to `created_at`
   - Ensure consistent "latest" semantics across all query methods

6. **Add integration tests for pipeline dedup**:
   - Test Redis dedup + PostgreSQL unique constraint combined
   - Test behavior when Redis is down (pipeline falls back correctly)
   - Verify metrics accuracy when Redis unavailable

7. **Review `get_latest_snapshots()` window logic**:
   - Verify `_SNAPSHOT_SCAN_WINDOW = 50000` is appropriate
   - Test windowed dedup vs full GROUP BY equivalence
   - Add fallback test when window query fails

### 12. Files Referenced

- `brsapi/models/tsetmc.py` - Core ORM models (SymbolSnapshot, SymbolDetail, IndexValue, etc.)
- `brsapi/models/base.py` - Base model class, SyncLogModel, RawPayloadModel
- `brsapi/repositories/base.py` - BulkUpsertRepository, SyncLogRepository
- `ingestion/storage/__init__.py` - StorageLayer (write_market_snapshot, write_daily_ohlcv, etc.)
- `ingestion/storage/layered_pipeline.py` - Hot/Warm pipeline with Redis dedup
- `ingestion/storage/dedup.py` - DeduplicationEngine (Redis SETNX based)
- `tests/unit/repositories/test_sync_log_repository.py` - needs_sync() tests (15/15 pass)
- `frontend/src/hooks/useMarketData.ts` - isDataFresh fix (future date guard)
- `brsapi/services/query_service.py` - BrsApiQueryService (enriched snapshots, latest, etc.)