# Data Sources — Phase 1

## Stable Feed for Tickers

| Ticker | Source | Fields | Update Frequency | Note |
|--------|--------|--------|-----------------|------|
| `XAU_USD` | brsapi/internal | price, asOf, source, quality | < 5 min | Primary gold-USD feed |
| `USD_IRR` | brsapi/internal | price, asOf, source, quality | < 5 min | Dollar rate |
| `XAU18` | brsapi/internal | price, asOf, source, quality | < 5 min | 18k gold specific |

## Physical Feed

| Symbol | Description | Fields | Source |
|--------|-------------|--------|--------|
| `18` | 18 کارت | price (toman/gram), purity, asOf | brsapi |
| `24` | 24 کارت | price (toman/gram), purity, asOf | brsapi |
| `melted` | آبشده | price (toman/gram), gold% , asOf | brsapi |
| `forward` | آ flottوان | price, dayHigh, dayLow, asOf | brsapi |
| `spring` | بهاری | price, change_pct, asOf | brsapi |
| `half` | نیم | price, asOf | brsapi |
| `quarter` | ربع | price, asOf | brsapi |
| `carati` | گرمی (specific) | price, purity, asOf | brsapi |

## Fund Feed

| Field | Description | Source | Note |
|-------|-------------|--------|------|
| `price` |unit price per share | brsapi | required |
| `nav` | Net Asset Value | brsapi | **abort if absent** → mark quality=SAMPLE |
| `volume` | daily trading volume | brsapi | optional |
| `turnover` | daily turnover value | brsapi | optional |
| `marketCap` | market capitalization | brsapi | optional; if absent → weights=null |

## Coin & Silver Certification

| Item | Fields | Source |
|------|--------|--------|
| `soghdeh` (coin) | price, mintage, purity, asOf | mint/issuer |
| `siv` (silver) | price (toman/gram), weight, purity | brsapi/tgju |

## Output Compliance — Phase 1 Contract

Every output record must satisfy Assistant 1's Phase 1 schema:
- `value` (number) — price equivalent
- `unit` (string) — "USD" | "IRR" | "toman/ounce"
- `asOf` (ISO 8601 with timezone)
- `source` (string) — one of: brsapi, tgju, cis, coin_supply, dashboard
- `quality` ∈ {LIVE, DELAYED, SAMPLE, EDUCATIONAL, UNAVAILABLE}
- **SAMPLE/EDUCATIONAL must never be promoted to LIVE** upstream

## Testing: Fixed Snapshot (CI Without Network)

> **fixture**: `tests/fixtures/phase1-snapshot.json`
> - Recorded single snapshot from brsapi mock at known time
> - No network required for CI
> - Validates: schema compliance, quality enforcement, asOf format
> - Example:
> ```json
> {
>   "symbol": "XAU_USD",
>   "value": 399800000,
>   "unit": "IRR",
>   "asOf": "2026-10-25T14:30:00+03:30",
>   "source": "brsapi",
>   "quality": "SAMPLE"
> }
> ```

## What Must NOT Appear
- ❌ price guessed or LLM-invented
- ❌ bubble/Score calculated here (Assistant 1 owns formulas)
- ❌ order/buy/sell recommendation
- ❌ user balance or custody data
- ❌ secrets (cookies, tokens) in any output