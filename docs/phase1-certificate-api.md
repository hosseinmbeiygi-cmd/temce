# Certificate of Deposit API (Phase 1)

## Minimum Gold/Silver-Linked Certificates

Minimum symbols linked to gold/silver data (soghdeh/silver related):

### Response Schema
```json
{
  "symbol": "soghdeh_gold",
  "name": "شمش طلایی",
  "price": 25500000,
  "changePct": 1.2,
  "volume": 1000,
  "turnover": 25500000000,
  "intrinsic": 25000000,
  "bubblePct": 2.0,
  "impliedUsd": 240.5,
  "asOf": "2026-10-25T14:30:00+03:30",
  "source": "brsapi",
  "quality": "LIVE"
}
```

### Field Definitions

| Field | Description | Rules |
|-------|-------------|-------|
| `symbol` | Certificate symbol code | Required |
| `name` | Certificate name | Required |
| `price` | Current price | Required, from motor |
| `changePct` | % change | Required |
| `volume` | Trading volume | Optional |
| `turnover` | Turnover value | Optional |
| `intrinsic` | Intrinsic gold/silver value | Motor calculation required |
| `bubblePct` | Bubble percentage | Motor parallel calculation |
| `impliedUsd` | Implied USD value | Conversion from IRR/TOM |
| `asOf` | ISO 8601 with timezone | Required |
| `source` | Source tag | Required |
| `quality` | Quality flag | Required |

### Quality Rules
- Same as other Phase 1 APIs
- SAMPLE/EDUCATIONAL never → LIVE
- If intrinsic unavailable from source → appropriate quality flag

### Prohibited
- ❌ No price invention
- ❌ No order route
- ❌ No treasury data beyond intrinsic/bubble
- ❌ LLM-generated values