# Data Sources — Phase 2

## Tehran Banking Feed + Hand-Down

| Field | Source | Notes |
|-------|--------|-------|
| `price` | Tehran official bank rate | Published daily by CBI; fallback to brsapi if unavailable |
| `dayLow` | Lowest price day | Bank publish time 15:30 |
| `dayHigh` | Highest price day | Bank publish time 15:30 |
| `asOf` | ISO timestamp | Bank publish date only; time 15:30 + TTL |
| `source` | "cis" | Central Bank of Iran |
| `quality` | LIVE/DELAYED/SAMPLE | If bank data missing → SAMPLE |

**Contract**: Same as Assistant 1's Phase 2 data contract — price, dayLow, dayHigh, asOf, source, quality.

## Platform Comparison Feed (Public Only)

| Field | Constraint |
|-------|------------|
| `buy_price` | Public buy price only; NO user session price |
| `sell_price` | Public sell price only |
| `dayLow` | Public daily low |
| `dayHigh` | Public daily high |
| `asOf` | Must include source tag, e.g. "tgju@2026-10-25T10:00:00+03:30" |
| `source` | Platform name (e.g. "platform_A"); NO user-specific data |
| `quality` | DELAYED (platforms typically 15+ min behind) |

**Prohibited**: 
- ❌ User session data
- ❌ Login-required prices
- ❌ CTA or buy button data
- ❌ Personalized pricing

**Yield Matrix / Time Series** (point-to-point, no look-ahead):

| Period | Data Type | Guard |
|--------|-----------|-------|
| `1m` | Monthly change Pct | min 2 data points required |
| `3m` | Quarterly change | zero-division guard: if no data → null → "—" |
| `6m` | 6-month change | same |
| `9m` | 9-month change | same |
| `1y` | Yearly change | same |

**Turnover / marketCap / changePctDaily** (for treemap):
- `turnover` | daily volume | guard: `if turnover === 0 → null → "—"`
- `marketCap` | total market value | guard: `if marketCap === 0 → null → "—"`
- `changePctDaily` | % change today | guard: compute from yesterday/ today; if missing → null → "—"

## docs/data-sources-phase2.md — Legal Constraints & Update Frequency

```md
# Data Sources — Phase 2

## Legal Constraints: Platform Names
- Platform comparison shows ONLY public buy/sell/dayLow/dayHigh
- NO mention of user accounts, sessions, or personalized data
- Platform names may appear as labels ONLY if ToS permits
- No scraping behind login; only public endpoints

## Update Frequency
- brsapi: < 5 min (configurable per environment)
- tgju: 15-30 min (respect ToS; add cache layer)
- cis: daily 15:30 exact; no intraday
- Platform comparison: per platform ToS (typically 1-5 min)
- Yield matrix: point-to-point; recompute on each API request from stored snapshots

## What Must NOT Appear
- ❌ User balance or position data
- ❌ Order book or trade flow
- ❌ CTA / buy-sell recommendations
- ❌ Platform names without ToS confirmation
- ❌ Secrets, cookies, user tokens in any output
```

## Adapter Requirements (Phase 2)

| Adapter | Input | Output Guarantees |
|---------|-------|-------------------|
| `tehran_bank` | CBI official publish | price, dayLow, dayHigh, asOf, source="cis", quality∈{LIVE,DELAYED,SAMPLE} |
| `platform_cmp` | Public REST per platform | buy/sell/dayLow/dayHigh, asOf, source=<platform>, quality=DELAYED |
| `yield_ts` | Stored snapshots (1m/3m/6m/9m/1y) | point-to-point change%; null→"—" if insufficient data |
| `turnover_guard` | daily volume/marketCap | divide-by-zero guard; 0→null→"—" |