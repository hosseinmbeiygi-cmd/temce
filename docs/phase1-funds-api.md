# Funds API (Phase 1)

## Minimum Active Major Gold Funds

Based on live data (not stale list), the following fund symbols should be included:

| Symbol | Name | Description |
|--------|------|-------------|
| `عيار` | Eghlāf/Standard | Standard gold fund |
| `طلا` | Tolā | Gold fund |
| `خرابه` | Kherābā | Kherābā fund |
| `مثقال` | Miṭghāl | Mithghāl (specific unit) |
| `گنج` | Kanj | Kan (treasure) fund |
| `گوهر` | Gohār | Gohār (jewelry) fund |

### Response Fields per Fund

```json
{
  "symbol": "عيار",
  "name": "عيار",
  "price": 399800000,
  "changePct": 0.8,
  "changeAmt": 3200000,
  "lastTradeAt": "2026-10-25T14:30:00+03:30",
  "volume": 5000,
  "turnover": 2000000000,
  "marketCap": 150000000000,
  "nav": 400000000,
  "bubbleNominalPct": 0.5,
  "bubbleNominalAmt": 2000000,
  "bubbleIntrinsicPct": null,
  "bubbleRealPct": null,
  "weights": {
    "coin": 0.5,
    "bar": 0.3,
    "cash": 0.2
  },
  "impliedUsd": 239.7,
  "asOf": "2026-10-25T14:30:00+03:30",
  "source": "brsapi",
  "quality": "LIVE"
}
```

### Field Definitions

| Field | Description | Rules |
|-------|-------------|-------|
| `symbol` | Fund symbol code | Required |
| `name` | Fund name | Required |
| `price` | Current price | Required, from motor |
| `changePct` | % change | Required |
| `changeAmt` | Absolute change | Required |
| `lastTradeAt` | Last trade timestamp | Optional |
| `volume` | Daily trading volume | Optional |
| `turnover` | Daily turnover value | Optional |
| `marketCap` | Market capitalization | Optional; if source has no combo data → `weights=null` NOT zero |
| `nav` | Net Asset Value | Required for bubble calculation |
| `bubbleNominalPct` | Named bubble % = (price - nav) / nav * 100 | **Only when nav valid**; otherwise **null** (NOT zero) |
| `bubbleNominalAmt` | Named bubble amount | When bubbleNominalPct calculated |
| `bubbleIntrinsicPct` | Intrinsic bubble % | Only when motor formula computable |
| `bubbleRealPct` | Real bubble % | Only when motor formula computable |
| `weights` | { coin, bar, cash } weights | **Null if no combination source**; NOT zero (different from missing data) |
| `impliedUsd` | Implied USD value | Motor calculation |
| `asOf` | ISO 8601 with timezone | Required |
| `source` | Source tag | Required |
| `quality` | Quality flag | Required |

### Critical Rules

1. **Named bubble only with valid NAV**: `bubbleNominalPct = (price - nav) / nav * 100` — only when `nav` is present and valid. If NAV absent → `bubbleNominalPct = null` (absolutely not 0 or invented).

2. **Weights**: If the source doesn't provide a combination (coin/bar/cash), then `weights = null` — this is not the same as `weights = 0`. Zero would be misleading; null means "not available from this source."

3. **Intrinsic/Real bubble**: Only fill `bubbleIntrinsicPct` and `bubbleRealPct` when the motor explicitly provides these formulas. Do not reimplement or guess.

4. **Quality enforcement**: Same SAMPLE/EDUCATIONAL → LIVE prohibition as ticker API.

### Prohibited
- ❌ No invented NAV or price
- ❌ No `weights = 0` when source lacks combination data
- ❌ No bubble calculation when NAV invalid
- ❌ No order route
- ❌ No LLM-generated values