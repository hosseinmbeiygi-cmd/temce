# Physical Table API (Phase 1)

## Required Symbols and Fields

For each of the following symbols, the API returns price, changePct, changeAmt, intrinsic, bubblePct, bubbleAmt, impliedUsd, asOf, source, quality:

| Symbol | Description |
|--------|-------------|
| `XAU18` | طلا گرم ۱۸ |
| `XAU24` | طلا گرم ۲۴ |
| `melted` | نقدی آبشده |
| `amir` | سکه امامی |
| `azadi` | سکه بهار آزادی |
| `nim` | نیم سکه |
| `roqe` | ربع سکه |
| `ghorbi` | سکه ۱ گرمی |

### Response Schema (per symbol)
```json
{
  "symbol": "XAU18",
  "price": 25500000,
  "changePct": 1.2,
  "changeAmt": 300000,
  "intrinsic": 25000000,
  "bubblePct": 2.0,
  "bubbleAmt": 500000,
  "impliedUsd": 240.5,
  "asOf": "2026-10-25T14:30:00+03:30",
  "source": "brsapi",
  "quality": "LIVE"
}
```

### Field Definitions

| Field | Description | Note |
|-------|-------------|------|
| `price` | Current price from motor | Required |
| `changePct` | % change from previous close | Required |
| `changeAmt` | Absolute change amount | Required |
| `intrinsic` | Intrinsic value (gold content value) | Motor calculation |
| `bubblePct` | Bubble as percentage of intrinsic | Motor parallel calculation |
| `bubbleAmt` | Bubble amount = price - intrinsic | Motor parallel calculation |
| `impliedUsd` | Implied USD value | Convert from IRR/TOM to USD |
| `asOf` | ISO 8601 with timezone | Required |
| `source` | Source tag | Required |
| `quality` | LIVE/DELAYED/SAMPLE/EDUCATIONAL/UNAVAILABLE | Required |

### Quality Rules
- If source data stale → downgrade quality
- SAMPLE/EDUCATIONAL never → LIVE upstream
- If intrinsic/unavailable → bubblePct/bubbleAmt may be null

### Prohibited
- ❌ No CTA/buy button
- ❌ No price guessing (if source absent → null)
- ❌ No treasury/wallet data
- ❌ No order execution