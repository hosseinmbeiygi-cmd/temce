# What-If Calculations API (Phase 1)

## Endpoint: POST /api/v1/gold/what-if

### Request Body
```json
{
  "xauUsd": 2695.00,
  "usdIrr": 42500000
}
```

### Response
```json
{
  "items": [
    {
      "symbol": "XAU18",
      "preview_intrinsic": 25000000,
      "preview_bubblePct": 2.0,
      "preview_bubbleAmt": 500000,
      "preview_impliedUsd": 240.5,
      "effect_on_fund_nominal_bubblePct": 0.5,
      "effect_on_fund_real_bubblePct": null
    },
    {
      "symbol": "XAU24",
      "preview_intrinsic": 30000000,
      "preview_bubblePct": 1.5,
      "preview_bubbleAmt": 450000,
      "preview_impliedUsd": 239.8,
      "effect_on_fund_nominal_bubblePct": null,
      "effect_on_fund_real_bubblePct": null
    }
  ]
}
```

### Field Definitions

| Field | Description |
|-------|-------------|
| `symbol` | The physical symbol affected |
| `preview_intrinsic` | Intrinsic value preview based on input xauUsd/usdIrr |
| `preview_bubblePct` | Bubble percentage preview |
| `preview_bubbleAmt` | Bubble amount preview |
| `preview_impliedUsd` | Implied USD preview |
| `effect_on_fund_nominal_bubblePct` | If applicable, effect on fund's nominal bubblePct; `null` if fund NAV not applicable or computation not possible |
| `effect_on_fund_real_bubblePct` | If applicable, effect on fund's real bubblePct; `null` if not computable |

### Rules

1. **No LIVE data overwrite**: Pure preview only; does not modify any stored LIVE data or state.
2. **No persistent side-effect**: No storage, no database writes, no cache update that persists beyond the request.
3. **Input validation**: `xauUsd` and `usdIrr` must be positive numbers; if invalid → 400 error.
4. **Source-dependent**: Calculations use motor parallel formulas; if motor doesn't provide parallel formula → those fields may be `null`.
5. **Quality preservation**: Output includes or notes the quality assumptions used (e.g., "based on SAMPLE data").
6. **Optional fund effects**: If fund NAV is available and formula computable, show effect on fund's nominal/real bubblePct; otherwise `null`.

### What Must NOT Happen
- ❌ Overwrite LIVE or stored data
- ❌ Persistent side-effects (no storage, no cache mutation that survives)
- ❌ Price invention or LLM generation
- ❌ Order route activation
- ❌ Modification of fund NAV or attributes

### Prohibited
- ❌ Any data storage beyond the request scope
- ❌ Modification of motor state
- ❌ Price guessing