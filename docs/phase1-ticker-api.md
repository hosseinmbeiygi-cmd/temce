# Ticker API (Phase 1)

## Endpoint: GET /api/v1/gold/ticker

### Query Parameters
| Parameter | Required | Description |
|-----------|----------|-------------|
| `symbol` | yes | Symbol code: `XAU_USD`, `XAU18`, `USD_IRR` |
| `index` | no | Optional fund/index average; only if real source available; otherwise `status=unavailable` |

### Responses

**200 OK**
```json
{
  "symbol": "XAU18",
  "price": 25500000,
  "changePct": 1.2,
  "changeAmt": 300000,
  "unit": "IRR",
  "asOf": "2026-10-25T14:30:00+03:30",
  "source": "brsapi",
  "quality": "LIVE"
}
```

**404 Not Found** (unsupported symbol)
```json
{ "error": "unsupported_symbol" }
```

### Optional Index/Average
- Only returned if `index` query param provided AND real source available
- Otherwise `status` field: `"unavailable"` and no index data

### Prohibited
- ❌ No order route
- ❌ No price invention (if source absent → null + quality=SAMPLE/UNAVAILABLE)
- ❌ LLM-generated prices