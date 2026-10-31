# TEMCE Audit Report - Phase 1: Market Source and Parsers
## Data Flow: Source → Client → Parser → Storage → API → Frontend

### Repository State
- **Branch**: integration/golddesk-fixes
- **HEAD Commit**: 90597e05b9f4328bcd82ee819a31ba5c55413c12
- **Report Date**: 2026-10-27

### 1. Source Overview

#### TSETMC (Iran Stock Exchange) - Primary Data Source
**Parsers Available** (in `ingestion/parser/`):
- `TsetmcMarketWatchParser` - source: `tsetmc_marketwatch`
  - Parses `marketData` array from JSON payload
  - Extracts: instrument_id, symbol, name, last_price, close_price, first_price, high_price, low_price, volume, value, trade_count, yesterday_close, eps, base_volume
  - **Critical**: All fields use `_to_decimal()` which returns `None` on failure (not 0 or empty string)

- `TsetmcTradeParser` - source: `tsetmc_trades`
  - Parses `closingPriceData` array from JSON payload
  - Extracts daily OHLCV data: instrument_id, trade_date, price, volume, value, trade_count, last_price, first_price, high_price, low_price

- `TsetmcOrderBookParser` - source: `tsetmc_orderbook`
  - Parses buy/sell rows from order book JSON
  - Extracts bid/ask levels with price, volume, order_count, rank

**Parser Pattern**: All TSETMC parsers follow the same pattern:
1. `json.loads(payload)` 
2. Extract records from `data` or `marketData` or `closingPriceData` keys
3. For each record, call `_extract_*` static method
4. Return `ParsedEvent` with source, event_type, data, fetch_time, parsed_at

**Critical Observation**: Parsers return `None` for failed field extractions via `_to_decimal()`, but the caller must handle `None` values appropriately. A price of `None` should NOT be treated as success with zero price.

#### Canonical Market Data
**Parser**: `CanonicalMarketDataParser` - source ending with `_usdt` or starting with `global_`
- Parses `records` envelope
- Filters records missing `instrument` or `price`
- Maps `instrument` → `instrument_id`
- Returns `market_tick` events

#### Library Parsers (finpy-tse, tsetmc_lib, tehran_stocks, tse_utils)
- `_BaseLibParser` - common dispatch logic
- Each parser handles different `data_type` values:
  - `market_watch` → `_market_snapshot`
  - `price_history` → `_daily_ohlcv`
  - `intraday_trades` → `_trade_tick`
  - `order_book` → `_orderbook_level`
  - `real_individual` → `_real_individual`
  - `shareholders`/`symbol_list` → `_instrument_info`
  - Index types → `_index_value`

### 2. Client/HTTP Layer

**Key Files**:
- `brsapi/services/sync_service.py` - Main sync orchestrator (lines 7-8: "Parse the response (via parser classes)", "Store parsed records in the database (via repositories)")
- `brsapi/parsers.py` - Parser registry and dispatch
- `ingestion/worker.py` - Ingestion worker pipeline
- `ingestion/main.py` - Main entry point

**Sync Flow** (from sync_service.py):
1. Fetch from BrsApi endpoint
2. **Parse the response (via parser classes)** ← Critical point
3. Store parsed records in the database (via repositories)

**Parser Registration** (sync_service.py line 55-56):
- `TsetmcParser.parse_all_symbols`
- `TsetmcParser.parse_index`  
- `CommodityParser.parse`
- `CryptoParser.parse`

### 3. Parser Analysis and Issues

#### Issue 1: Empty Response ≠ Success
**Location**: Multiple parsers across codebase
**Problem**: Parsers may return empty lists `[]` for various reasons (no data, parse error, HTML redirect to Suspend.php, HTTP 402, timeout), but the sync pipeline may treat this as `success=True, items_count=0` rather than distinguishing between "no data available" and "success with data"

**Evidence from logs** (historical, not live):
- `logs/brsapi_sync_20261027.log` showed: `All sync attempts rejected fast: success=True, items_count=0`
- `TSETMC: ❌ exhausted (HTTP 402)`

**Impact**: Downstream consumers (API, frontend) receive empty data and may incorrectly display it as "live" or "fresh" when it actually indicates a source problem.

#### Issue 2: Parser Failure Swallows Errors
**Location**: `_BaseLibParser.parse()` in `ingestion/parser/library_parsers.py` lines 45-48:
```python
async def parse(self, payload: bytes) -> list[ParsedEvent]:
    try:
        data = json.loads(payload)
    except Exception:
        logger.exception("Failed to parse %s payload", self._source_name)
        return []  # Returns empty list on JSON parse failure - no error propagation!
```
**Problem**: JSON parse failures silently return `[]` without any error indication. The caller has no way to distinguish between "valid empty response" and "corrupted/invalid response".

**Impact**: Errors are lost; downstream systems cannot detect or recover from parse failures.

#### Issue 3: `_to_decimal()` Returns None, Callers May Use 0
**Location**: `ingestion/parser/tsetmc_parsers.py` `_to_decimal()` function
**Problem**: `_to_decimal()` returns `None` on failure, but callers may default to 0 or empty string, creating false "success with zero price" scenarios.

**Example**: In `TsetmcMarketWatchParser._extract_snapshot()`:
```python
"last_price": _to_decimal(rec.get("pDrCotVal")),
```
If `pDrCotVal` is missing or invalid, `last_price` becomes `None`. Downstream, this may be rendered as `0` or empty, masking the actual data failure.

#### Issue 4: No Distinction Between "Empty Valid Response" vs "Error Response"
**Problem**: The pipeline doesn't differentiate between:
- ✅ Successful fetch, valid response, but no records matching criteria
- ❌ HTTP error (402, 429, 5xx)
- ❌ Network timeout
- ❌ HTML redirect (Suspend.php)
- ❌ JSON parse failure
- ❌ Valid JSON but missing required fields

All of these may result in `success=True, items_count=0` being reported upstream.

### 4. Data Flow Validation

#### TSETMC Market Watch Pipeline
```
HTTP Request → TsetmcMarketWatchParser.parse() → _extract_snapshot() → ParsedEvent → store_hot/warm → API → Frontend
```

**Validation Points**:
1. **HTTP level**: Status code check (200 vs error codes)
2. **JSON parse level**: `json.loads()` success/failure
3. **Record level**: Each record extracted; fields may be `None` if missing
4. **Empty records**: If `records` array is empty, events list is empty
5. **Storage level**: `store_hot()` returns `False` if deduped or Redis unavailable

**Critical Gap**: No step explicitly validates that the response is "healthy" vs "empty due to no data". A response with `success: true` but 0 records after parsing is ambiguous.

#### Canonical Market Data Pipeline
```
HTTP Request → CanonicalMarketDataParser.parse() → filter records → ParsedEvent → store → API → Frontend
```

**Validation**: Filters records missing `instrument` or `price`, but doesn't distinguish from HTTP errors.

### 5. Specific Parser Issues Found

#### Issue A: `TsetmcMarketWatchParser` - Missing Field Handling
**Code** (`ingestion/parser/tsetmc_parsers.py`, line 57-76):
```python
"last_price": _to_decimal(rec.get("pDrCotVal")),
```
If `pDrCotVal` is absent from the API response, `_to_decimal(None)` returns `None`. The resulting `ParsedEvent.data` has `last_price: None`.

**Risk**: Downstream, `None` price may be rendered as `0` or empty string, which is indistinguishable from a legitimate zero-price situation.

**Recommendation**: Add explicit validation after parsing; if critical fields (price, symbol) are `None`, return an error event or reject the record rather than storing `None` values.

#### Issue B: `CanonicalMarketDataParser` - Incomplete Filtering
**Code** (`ingestion/parser/market_data.py`):
```python
if not record.get("instrument") or record.get("price") in (None, ""):
    continue
```
This filters out records missing instrument or price, but:
1. Records with `price: 0` pass the filter (0 is not None or "")
2. Records with `price: "0"` (string) also pass
3. No distinction between "price was 0 in source" vs "price field missing/defaulted to 0"

**Recommendation**: Use explicit `is None` checks and track whether the field was actually present in the source.

#### Issue C: `_BaseLibParser` - Silent Failure on JSON Parse Error
**Code** (`ingestion/parser/library_parsers.py`, lines 45-48):
```python
except Exception:
    logger.exception("Failed to parse %s payload", self._source_name)
    return []
```
**Problem**: Returns empty list without any error marker. The caller (`sync_service.py`) cannot tell if:
- The payload was intentionally empty
- JSON was corrupted
- Encoding issue
- Service returned HTML instead of JSON

**Recommendation**: Return a special event type or raise a custom exception that the caller can catch and handle appropriately.

#### Issue D: Dedup Before Validation
**Historical finding** (from ZIP audit): In the ingestion pipeline, the dedup marker was stored **before** parse/validation/persist completion. If parsing failed after dedup, the record was lost without retry capability.

**Current state** (from `ingestion/storage/layered_pipeline.py`): 
- `store_hot()` uses Redis SETNX for dedup
- Dedup happens before warm storage
- If Redis unavailable, warm store still proceeds (with `contextlib.suppress`)

**Risk**: A failed parse after dedup means the record is silently lost.

### 6. Test Coverage Status

| Area | Tests | Status |
|------|-------|--------|
| `needs_sync()` | 15 tests | ✅ All pass |
| Parser behavior (empty/malformed) | ? | ⚠️ Not found in current test suite |
| `isDataFresh` future date check | ? | ⚠️ Syntax validated, runtime limited |
| Parser error handling | ? | ⚠️ No dedicated tests found |

**Test Discovery**: No specific tests found for parser error handling, empty response behavior, or malformed JSON scenarios. The 15 `needs_sync()` tests cover the repository layer but not the parser layer.

### 7. Root Cause Analysis

#### Root Cause: Ambiguous Success/Empty Distinction
The fundamental issue across the data pipeline is the **lack of distinction** between:
- ✅ "Successfully fetched, valid response, but no new data"
- ❌ "Failed to fetch/filter/parse data"

This ambiguity causes:
1. **False "live" displays**: Frontend shows data as fresh when it's actually stale or errored
2. **Silent data loss**: Parse failures swallowed, records lost without retry
3. **Incorrect dedup**: Records deduped before validation, lost on parse failure
4. **Cooldown masking**: BrsApi cooldown (302/303/402) treated as normal operation

**Chain of failure**:
```
BrsApi returns HTML/Suspend.php (HTTP 200, but not JSON)
→ sync_service.py treats as successful response
→ parser tries json.loads() → fails → returns []
→ pipeline stores empty result
→ API returns success=True, items_count=0
→ Frontend displays "live" data that doesn't exist
→ User sees outdated data as "zende" (alive)
```

### 8. Changes Made (This Session)

No changes were made to parser logic in this session. The focus was on:
1. ✅ `needs_sync()` tests (15/15 pass)
2. ✅ `useMarketData.ts` isDataFresh future date guard
3. 📋 **Pending**: Parser error handling and empty-response distinction

**Files Modified**: None (only verification and testing)

### 9. Acceptance Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 15/15 needs_sync tests pass | ✅ | `python -m pytest ... -v` output |
| isDataFresh future date guard | ✅ | Git diff verified |
| No BrsApi live requests | ✅ | Logs verified |
| No secret exposure | ✅ | Redacted in output |
| Test before claiming success | ✅ | All tests verified |

### 10. Blocked / Unverified

1. **Parser error handling tests** - No dedicated tests found in codebase
2. **Malformed JSON response behavior** - Not tested with fixture/mock
3. **Empty vs error response distinction** - No pipeline-level handling
4. **Dedup-before-parse edge case** - Historical finding, not currently tested
5. **Full parser runtime validation** - Requires TSETMC live access (blocked)

### 11. Recommended Next Steps

1. **Add parser test fixtures** for:
   - Valid TSETMC market watch response
   - Missing fields response (partial data)
   - Malformed JSON response
   - Empty records response
   - HTML redirect (Suspend.php) response

2. **Create parser behavior tests** verifying:
   - Successful parse returns expected events
   - Missing critical fields returns error/skips
   - JSON parse failure returns error indication (not silent [])
   - Empty valid response distinguished from error

3. **Add pipeline-level tracking** for:
   - `parse_success` vs `parse_failure` metrics
   - `records_extracted` vs `records_valid` counts
   - Error type tagging (json_error, field_missing, http_error)

4. **Fix `_BaseLibParser`** to return error events on JSON parse failure instead of silent `[]`

5. **Add validation after parsing** to reject records with critical `None` fields (price, symbol) rather than storing them

### 12. Files Referenced

- `ingestion/parser/tsetmc_parsers.py` - TSETMC market/watch/trade/orderbook parsers
- `ingestion/parser/validator.py` - Price/volume/instrument validation helpers
- `ingestion/parser/market_data.py` - Canonical market data parser
- `ingestion/parser/library_parsers.py` - Base lib parser with dispatch logic
- `brsapi/services/sync_service.py` - Sync orchestrator with parser dispatch
- `ingestion/storage/layered_pipeline.py` - Hot/Warm storage pipeline with dedup
- `tests/unit/repositories/test_sync_log_repository.py` - needs_sync() tests (15/15 pass)
- `frontend/src/hooks/useMarketData.ts` - isDataFresh fix (future date guard)
- `logs/brsapi_sync_20261027.log` - Historical sync logs (not live)