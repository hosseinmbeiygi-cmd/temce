# Data Sources — Phase 0

## Candidate Sources List

| Source | Access Method | Typical Delay | Cutoff Risk | Trustworthy Fields |
|--------|--------------|---------------|-------------|---------------------|
| `brsapi` | Official internal API | < 5 min | Low | price, asOf, source, quality_flag |
| `tgju` | Public REST | 15-30 min | Medium | price, change_pct, asOf |
| `cis` | Central Bank | Daily 15:30 | High (weekends) | official price, volume, asOf |
| `coin_supply` | Mint/issuer | Per mint | Low | coin price, mintage, asOf |
| `dashboard` | Internal UI | Variable | Medium | last_price, date, source |

## Source Details

### brsapi
- **Endpoint**: `/api/gold/snapshot` (mock: returns fixed quality_flag=SAMPLE)
- **Fields**: value, unit, asOf (ISO+TTL), source="brsapi", quality_flag ∈ {LIVE,DELAYED,SAMPLE,EDUCATIONAL}
- **Delay**: Real-time to 5min depending on feed
- **Risk**: Feed cutoff → default to quality=SAMPLE with asOf="—not set—"

### tgju
- **Method**: Public website tgju.org gold prices
- **Fields**: price (IRR), change_pct, asOf (Persian "N دقیقه قبل")
- **Delay**: 15-30 min typically
- **Risk**: Site changes HTML → adapter break; add version tag in source field

### cis
- **Method**: Central Bank of Iran official publish (daily at 15:30)
- **Fields**: official_price, daily_volume, asOf (date only)
- **Delay**: Fixed daily; no intraday
- **Risk**: Weekend/holiday → no data; mark quality=SAMPLE

### coin_supply
- **Method**: Iranian mint/issuer data for coins (soghd, golshan, etc.)
- **Fields**: coin_price, mintage, purity, asOf
- **Delay**: Per mint policy
- **Risk**: Limited data; often only ceremonial price

## Normalization & Quality Rules (Absolute)
1. **SAMPLE/EDUCATIONAL → never promote to LIVE** upstream. Keep badge visible in UI.
2. **If delay > TTL** (configurable, e.g. 15 min for LIVE) → downgrade to DELAYED or SAMPLE.
3. **If source missing entirely** → quality="UNAVAILABLE", asOf="—not set—", source="unknown".
4. **Log no secrets** — remove any `token`, `cookie`, `password` from raw before processing; strip in adapter before normalize.
5. **Rate limit respect** — each adapter must honour source ToS; add `retry-after` or back-off.
6. **Never implement proprietary bubble/Score formula** — Assistant 1 owns all formulas. This layer only normalizes and transmits.

## Output Contract (Every Record Must Have)
- `value` (number|null) — price equivalent; `null` displays as `"—"` in UI
- `unit` (string) — e.g. "USD", "IRR", "toman/ounce"
- `asOf` (ISO string with timezone) — e.g. `"2026-10-25T14:30:00+03:30"`; `"—not set—"` if absent
- `source` (string) — one of the listed sources or `"unknown"`
- `quality` (enum) — `"LIVE"|"DELAYED"|"SAMPLE"|"EDUCATIONAL"|"UNAVAILABLE"`
- **Prohibition**: `quality` must NEVER be `"LIVE"` if the raw source is `"SAMPLE"` or `"EDUCATIONAL"`