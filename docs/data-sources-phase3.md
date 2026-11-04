# Data Sources — Phase 3

## Silver Feed (Domestic / International per Source)

| Field | Domestic Source | International Source | Notes |
|-------|----------------|----------------------|-------|
| `price` | brsapi (toman/gram) | Spot (USD/oz, convert to toman/gram) | Domestic price primary; USD spot as fallback |
| `asOf` | ISO ++ timezone | ISO + timezone | Must match source |
| `source` | "brsapi" | "London_Bullion_Market" | Tag source explicitly |
| `quality` | LIVE/DELAYED/SAMPLE | LIVE/DELAYED | Based on feed freshness |
| `bubble` | null if unavailable → "—" | null if uncalculable → "—" | Assistant 1 owns bubble formula |

**Rule**: If only domestic source available → mark quality based on domestic feed age; international bubble = null unless Assistant 1 explicitly shares parallel formula.

## Derivative (Future/Option) — Read-Only

| Field | Description | Forbidden |
|-------|-------------|-----------|
| `price` | Mark price from engine/model | — |
| `settlement` | Settlement price (daily) | — |
| `distance_from_spot_pct` | `(price - spot) / spot` as % | if spot not definable → null → "—" |
| `expiry` | Expiry date string | — |
| `risks_simple` | `["liquidity-low", "assignment-risk"]` (fixed set) | — |

**Prohibited**:
- ❌ `place_order`, `cancel`, `position entry`
- ❌ ML/prediction of future price
- ❌ Real-time user position

**Note**: This layer only forwards read-only fields from the motor; no price calculation or transformation.

## News Regime Input → Output

**Input**: Free text or feed item (raw string from any source)

**Output Payload**:
```json
{
  "labels": ["dollar", "monetary_policy"],  // from fixed set ONLY
  "note": "short non‑price analysis; no target price"
}
```

**Fixed Label Set** (do NOT invent new labels):
- `dollar`
- `geopolitical`
- `monetary_policy`
- `coin_supply`
- `other`

**Rules**:
1. **Never invent political/monetary labels** — if text doesn't clearly match, use `"other"`.
2. **Note must be non‑price** — no target price, no "buy X".
3. **Source text cleaned** — remove irrelevant filler, keep only market-relevant signal.
4. **If module belongs to Assistant 1/3** — use their label module; this layer only normalizes & forwards text/metadata.

## Data Freshness: Stale Marker for Assistant 1's `data_stale` Gate

**Provide per-record**:
- `ageSeconds`: `currentTime - record.asOf` (in seconds)
- `freshness`: enum `"fresh"|"stale"|"unknown"` based on config TTL

**Gate integration**: If `ageSeconds > N` (configurable, e.g. 15 min for LIVE) → adapter marks `quality=DELAYED` or `quality=SAMPLE` AND sets `staleFlag=true` in metadata.

**Output addition** (pass-through to Assistant 1 gate):
```json
{
  "ageSeconds": 85,
  "freshness": "fresh",
  "staleFlag": false
}
```

**Never**:
- ❌ Hide `ageSeconds` or fabricate freshness
- ❌ Promote stale data as LIVE
- ❌ Modify `ageSeconds` after gateway check

## What Must NOT Appear (Phase 3)
- ❌ `place_order`, `cancel`, any OMS call
- ❌ User position or balance storage
- ❌ Fabricated prices or bubbles (Assistant 1 owns formulas)
- ❌ ML price prediction
- ❌ Secrets, cookies, user tokens
- ❌ Target price in news regime note

## Adapter Requirements (Phase 3)

| Adapter | Input | Output Guarantees |
|---------|-------|-------------------|
| `silver_feed` | Domestic + international sources | price, asOf, source, quality; bubble=null→"—" if not computable |
| `derivative_readonly` | Future/option motor data | price, settlement, distance_from_spot_pct, expiry, risks_simple (fixed set) |
| `news_normalize` | Raw text/feed string | labels[] from fixed set, note (non-price, no target) |
| `freshness_marker` | Any record with asOf | ageSeconds, freshness enum, staleFlag bool for gate |