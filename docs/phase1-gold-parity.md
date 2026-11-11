# Phase 1 — GoldDesk Data Terminal Parity

**Status: IMPLEMENTED — 2026-10-26.**
**Scope:** Phase 1 only (entry-data terminal versus `rahavard365.com/gold`). No OMS, wallet, custody, delivery, or order button was added.
**Authority:** this document plus `docs/phase0-gold-foundation.md` for the Phase 0 engine and quality contract. Untracked `docs/data-sources-phase1.md` and `docs/phase1-*-api.md` were **not** used as implementation inputs.

---

## 1. Surface and routes

| Layer | Route | Purpose |
|---|---|---|
| FastAPI (assembled app) | `GET /api/v1/gold/terminal` | Ticker + physical + funds + certificates in one response |
| FastAPI (assembled app) | `POST /api/v1/gold/what-if` | Preview intrinsic/bubble/implied-USD under manual XAU/USD and USD/IRR |
| Next.js | `/gold/terminal` (tab «میز داده») | Phase 1 UI |

- The personal router is mounted behind `_require_user`; both routes are **read** endpoints.
- Both routes are also present in the gold router's `/docs/endpoints` inventory.
- `TerminalResponse.capabilities` and `WhatIfResponse.capabilities` are hard-coded:
  `orders=false`, `wallet=false`, `delivery=false`, `preview_only=true`.
- No `order`, `orders`, `buy`, `sell`, `wallet`, `delivery`, `custody`, `checkout` segment is mounted under the gold router; this is asserted in `tests/gold_desk/test_phase1_terminal.py`.
- Phase 0 `GET /gold/snapshot` was not modified.

### What-if request contract

```json
{ "xau_usd": 5000.0, "usd_irt_rial": 1500000.0 }
```

`xauUsd` and `usdIrr` are accepted aliases. Bounds: `0 < xau_usd ≤ 100,000` and
`0 < usd_irt_rial ≤ 1,000,000,000`. The value is **Rial**, not Toman.

---

## 2. Unit conventions (Rial vs Toman)

| Value | Source unit | Phase 1 handling |
|---|---|---|
| `XAU/USD` | USD per troy ounce | Kept as USD/oz; rounded to 2 decimals |
| Physical gold/coin quotes (`brsapi_gold_coin_prices`) | Toman in practice, despite legacy `unit="IRR"` metadata | **×10 → Rial** with `Decimal` `ROUND_HALF_UP` (`_toman_to_rial`) |
| USD free-market quote (`brsapi_currency_prices`) | Toman in practice | **×10 → Rial** |
| Physical change amount | Toman | **×10 → Rial** |
| IME fund price, NAV, turnover, market value | Rial | Used as Rial, rounded to integer Rial |
| IME certificate price | Rial | Used as Rial |
| Certificate `trade_value` with `trade_value_unit` | Rial, possibly scaled | Multiplied by 1,000 / 1,000,000 / 1,000,000,000 when the unit says هزار / میلیون / میلیارد; unknown empty unit → gap |
| Engine input `usd_irt` | Rial | `fair_value(..., unit="rial")`; coin mint cost (Toman table) is ×10 inside the engine |
| Phase 1 API response | — | **All monetary fields are Rial**; `usd_irt_toman` is derived as Rial ÷ 10 |

The UI shows both Rial and its Toman equivalent for the free-market USD reference only, to prevent a 10× reading error.

---

## 3. Symbols and sources

### 3.1 Ticker

| Key | Label | Source | Unit | Status |
|---|---|---|---|---|
| `XAUUSD` | اونس جهانی طلا (XAU/USD) | `brsapi_commodity_prices`, `symbol=XAUUSD`, `category=precious_metal` | USD/oz | price + change % + change amount + `as_of` + quality |
| `IR_GOLD_18K` | طلای ۱۸ عیار | `brsapi_gold_coin_prices` | Rial/gram | same |
| `USD` | دلار آزاد | `brsapi_currency_prices`, `symbol=USD` | Rial | same |
| `GOLD_FUND_INDEX` | شاخص صندوق‌های طلا | none | — | `status="under_construction"`, `quality="NO_DATA"`, no numeric price |

The ticker is rendered at the top of the data desk. The fund index is deliberately a label, not a synthetic number; the UI shows «در دست ساخت».

### 3.2 Physical table (8 fixed rows)

| Symbol | Label | Basis |
|---|---|---|
| `IR_GOLD_18K` | طلای ۱۸ عیار | gram |
| `IR_GOLD_24K` | طلای ۲۴ عیار | gram |
| `IR_GOLD_MELTED` | طلای آب‌شده (مثقالی) | mesghal |
| `IR_COIN_EMAMI` | سکه امامی | coin |
| `IR_COIN_BAHAR` | سکه بهار آزادی | coin |
| `IR_COIN_HALF` | نیم سکه | coin |
| `IR_COIN_QUARTER` | ربع سکه | coin |
| `IR_COIN_1G` | سکه یک گرمی | coin |

All rows come from `brsapi_gold_coin_prices`; the latest row per symbol is selected by `(fetched_at, time_unix, id)`.

### 3.3 Gold funds

Source: latest row per symbol from `brsapi_ime_funds`, joined to the latest row per symbol from `brsapi_nav_records`.

Universe filter (`is_gold_fund`) excludes:

- silver/platinum counterparts by symbol prefix or name term (`نقره`, `نقر`, `سیلو`, `سیگ`, `پلات`, `پلاتین`, `سیمین`);
- names ending with `1` (manager's silver counterpart);
- placeholder symbols ending with any digit (e.g. stale duplicates).

The filter is a naming heuristic, not a legal classification. On the 2026-10-26 dev database it returned **38 funds**. The largest by reported market value were `عیار`, `طلا`, `کهربا`, `گنج`, `مثقال`, and `گوهر` — real rows, not a hard-coded list. Coverage is re-derived from the feed on every request.

Other columns:

- price = `price_last`, fallback `price_close` (with a gap note);
- change % / amount = `price_last_change_pct` / `price_last_change`, fallback close fields;
- volume = `trade_volume`, turnover = `trade_value`, market value = `market_value`;
- trade time = `time`; **trade date is not present in the feed** → `last_trade_date` is `null` and a Persian gap explains it;
- NAV = `nav_issue`, fallback `nav_redemption`; both issue and redemption are exposed;
- NAV date/time are Jalali and converted from Tehran time (UTC+03:30) to UTC for `nav_as_of`. If conversion fails, `fetched_at` is used **only** as a visibly-flagged fallback;
- `intrinsic_price` (intrinsic backed value per unit) is present in the contract but `null` until composition exists.

### 3.4 Certificates

Source: latest row per `contract_code` from `brsapi_ime_certificates` where
`contract_code ∈ {GoldBar, GoldCoin}` **or** `commodity ∈ {شمش طلا, سکه طلا}`.

Current feed yields `GoldBar` (گواهی شمش طلا) and `GoldCoin` (گواهی سکه طلا). No verified
salam certificate row exists in the current data; no column is removed when it is absent.

**Certificate intrinsic is intentionally `null`.** `contract_size` in this feed is
«ضریب تبدیل نماد به گروه انبار» (warehouse conversion multiplier), not grams, and the feed
provides no purity/weight per contract. Intrinsic, bubble, and implied USD therefore stay
`—` with a Persian data-gap; inventing a gram weight was rejected.

---

## 4. Formulas as implemented

### 4.1 Phase 0 engine (unchanged)

`xau_usd` is USD/oz and `usd_irt` is Rial per USD. All engine results below are Rial.

```
base_24k_per_gram = xau_usd × usd_irt / 31.1034768
gold_18k_per_gram = base_24k_per_gram × (750 / 999.9)
gold_24k_per_gram = base_24k_per_gram
melted_per_mesghal = 4.6083 × gold_18k_per_gram
coin_fair = coin_weight × (900 / 999.9) × base_24k_per_gram + mint_cost_toman × 10
```

Coin weights (g): Emami 8.133, Bahar 8.133, Half 4.066, Quarter 2.033, 1g 1.010.
Rounding: integer Rial, `Decimal` `ROUND_HALF_UP` (`pricer.round_to_rial(..., "rial")`).

### 4.2 Physical row

```
intrinsic      = fair_value(symbol, xau_usd, usd_irt_rial, unit="rial")
bubble_amount  = market_price − intrinsic          (Rial)
bubble_pct     = (market_price − intrinsic) / intrinsic × 100   (2 decimals)
implied_usd    = (market_price − mint_rial) × 31.1034768 / (usd_irt_rial × grams_24k_equivalent)
```

`grams_24k_equivalent` is the asset's fine-gold content per quoted unit:

- 18k: `750/999.9`
- 24k: `1`
- melted: `4.6083 × 750/999.9`
- coins: `weight × 900/999.9`

For coins, `mint_rial` is subtracted before inverting the engine, so implied USD is the
gold-only implied ounce price. This is the inverse of the Phase 0 formula, not a second
fair-value implementation.

### 4.3 Gold fund bubbles

Let `NAV = nav_issue` if present, otherwise `nav_redemption`.

```
nominal_bubble_pct    = (market_price − NAV) / NAV × 100
nominal_bubble_amount = market_price − NAV
```

This is a **percentage premium/discount**, not the P/NAV ratio. Equivalently,
`price / NAV = 1 + nominal_bubble_pct / 100`.

- `intrinsic_price`: **not computed**; `null`, `composition_status="needs_composition"`.
- `bubble_intrinsic_pct` / `bubble_intrinsic_amount`: **not computed**; `null`, `composition_status="needs_composition"`.
- `bubble_real_pct`: **not computed**; `null`.
- `implied_usd` for funds: **not computed**; needs holdings composition and units outstanding.

No composition percentages (coin/bar/cash/other) exist in any connected source. The columns
remain in both API and UI and show `—` + «نیاز به ترکیب دارایی صندوق». They are never zero-filled.

### 4.4 What-if

`POST /gold/what-if` reads the same market rows, then recomputes only the **preview**:

- physical: `preview_intrinsic`, `preview_bubble_pct`, `preview_bubble_amount`, `preview_implied_usd`
  using the manual `xau_usd` and `usd_irt_rial` with the same engine functions;
- funds: `nominal_bubble_pct_before == nominal_bubble_pct_after` because NAV is not a function
  of XAU/USD; real bubble and implied USD stay `null` (composition missing);
- every physical preview row carries `preview_quality="SAMPLE"`; the UI labels the whole block
  with a solid `SAMPLE` badge and states that the numbers are not live and are not stored;
- the base/live rows are untouched, and the session is read-only: tests assert no `add`,
  `flush`, or `commit` call is made.

---

## 5. Quality, freshness, and fail-closed rules

| Quality | Rule |
|---|---|
| `LIVE` | Price present and source `fetched_at` age ≤ `PRICE_LIVE_TTL_SECONDS` (300 s), not in the future |
| `DELAYED` | Price present but older than 300 s, timestamp missing, or timestamp in the future |
| `NO_DATA` | Price missing, null, or ≤ 0; intrinsic/composition/weight unavailable |
| `SAMPLE` | What-if preview only |
| `EDUCATIONAL` | Reserved; not emitted by Phase 1 |

Additional rules:

- References quality is the **worst** of XAU/USD and USD; the same worst-of rule is available
  for mixed-quality sets (`NO_DATA` > `EDUCATIONAL` > `SAMPLE` > `DELAYED` > `LIVE`).
- `references.as_of` is the earlier of the two source timestamps and is `null` unless both
  references exist with timestamps.
- `intrinsic_quality` = references quality when intrinsic is computed, otherwise `NO_DATA`.
- `nav_quality` is computed from the converted NAV timestamp, not from the fund row's `fetched_at`.
- Every price cell in the UI shows source + `as_of`; every missing value shows `—` with a tooltip
  containing the Persian reason. Unknown quality strings in the UI fail closed to `DELAYED`.
- Legacy `quality_flag` is ignored; `quality_flag="clean"` does not make a value LIVE.

On the 2026-10-26 smoke run, every market/NAV row was `DELAYED` because the newest BrsApi fetch
was 2026-10-18 (eight days old). That is the intended behaviour, not a UI failure.

---

## 6. UI surface (`/gold/terminal`)

1. **Reference strip** — XAU/USD, USD free-market (Rial + Toman equivalent), reference time,
   source, quality, and data gaps.
2. **Ticker** — the four items from §3.1; the fund index is «در دست ساخت».
3. **What-if calculator** — two numeric inputs, submit button, SAMPLE-labelled preview;
   text: «فقط خواندن و محاسبه — هیچ سفارشی ثبت نمی‌شود.»
4. **Physical table** — price, change %/amount, intrinsic, bubble (% or Rial via
   «نمایش حباب به درصد» toggle), implied USD, source/quality. All eight symbols.
5. **Funds table** — price, change, volume, turnover, market cap, issue/redemption NAV,
   NAV date, intrinsic backed price, nominal/intrinsic/real bubble, coin/bar/cash/other
   composition columns, composition status chip, implied USD, quality.
6. **Certificates table** — price, change, volume, turnover, contract size/unit, intrinsic,
   bubble, implied USD (all `—` with explanation), source/quality.
7. **Capability note + disclaimer** — orders/wallet/delivery show «غیرفعال»; the canonical
   Phase 0 disclaimer is rendered inline; the header banner remains.

No order, cart, checkout, wallet, custody, delivery, or buy/sell control is present.
The only button is «محاسبه پیش‌نمایش».

---

## 7. Evidence (2026-10-26)

| Check | Result |
|---|---|
| `venv/Scripts/python.exe -m pytest tests/gold_desk tests/unit/api/test_golddesk_http.py -q` | **415 passed, 1 skipped** (107.53 s) |
| `venv/Scripts/python.exe -m pytest tests/gold_desk/test_phase1_terminal.py -q` | **41 passed** |
| `cd frontend && npx vitest run` | **574 passed, 54 files** (78.89 s) |
| `cd frontend && npx tsc --noEmit` | **exit 0** |
| Real dev-DB smoke via `build_terminal` | 8/8 physical rows, **38 funds**, 2 certificates, `capabilities` all false except `preview_only` |

Smoke values (illustrative, from the 2026-10-18 BrsApi rows — all `DELAYED`):

- references: XAU/USD `4165.18`, USD `2,628,000` Rial;
- 18k: market `259,372,000`, intrinsic `263,970,194`, bubble `−1.74٪`, implied USD `4092.63`;
- Emami: market `2,641,900,000`, intrinsic `2,577,043,510`, bubble `+2.52٪`;
- one fund (`عیار`): price `716,570`, NAV `720,227`, nominal bubble `−0.51٪`;
- certificates: `GoldBar` `34,552,090`; `GoldCoin` `2,626,111,900`; intrinsic/bubble `null`.

Backend tests cover: Toman→Rial conversion, engine equality, missing references, missing NAV
(never zero), Jalali→UTC NAV time, composition gaps, certificate weight gaps, ticker
under-construction, fund-universe filtering, two different what-if input pairs, read-only
session, forbidden route segments, and assembled-router mounting. Frontend tests cover: `—`
rendering, `NO_DATA` badges, bubble %/Rial toggle, nominal fund bubble, composition gap,
certificate gaps, SAMPLE preview, unchanged live values, and absence of order controls.

---

## 8. Limitations versus Rahavard365/Gold

| Area | GoldDesk Phase 1 | Rahavard-style expectation |
|---|---|---|
| Official fund index | No connected source; shown as «در دست ساخت» | A published index with history |
| Fund composition | No source for coin/bar/cash weights | Per-fund portfolio breakdown |
| Intrinsic fund bubble | Needs composition → `—` | NAV/intrinsic/real premium per fund |
| Real fund bubble / implied USD | Needs composition + units → `—` | Real-asset-backed valuation |
| Fund trade date | Feed provides time only; date `null` with a gap | Full trade timestamp |
| NAV freshness | Daily Jalali NAV; often `DELAYED` | Intraday/official NAV stream |
| Certificates | Price/volume only; no grams/purity → no intrinsic | Intrinsic/bubble for certificates |
| Salam / coin certificates | No verified source row in the current DB | Certificate/salam coverage |
| Order book / execution | None | Possibly order routing (out of scope here) |
| Data licensing | BrsApi + IME feed; no Rahavard data | Rahavard's own licensed feeds |
| Refresh | UI polls `/terminal` every 120 s; API reads latest DB rows | Real-time push/stream |

The goal is analytical parity of the **entry-data** surface, not identical numbers: different
sources, refresh rates, and fund-universe filters will produce different values.

---

## 9. No-order guarantee

- No order/wallet/delivery/custody/checkout/buy/sell route exists under the gold router;
  a test enumerates forbidden path segments.
- The API advertises `orders=false`, `wallet=false`, `delivery=false`, `preview_only=true`.
- The UI contains no purchase button; its only action is a read-only preview.
- What-if performs no writes and does not mutate live response rows.
- The canonical disclaimer is fixed: «این میز فقط ابزار تحلیلی، تصمیم‌یاری و آموزش است.
  سفارش اجرا نمی‌کند، دارایی نگهداری نمی‌کند، و توصیه قطعی خرید/فروش نیست. مسئولیت تصمیم با کاربر است.»

---

## 10. Residual work (not Phase 1)

1. Connect a licensed/source-backed gold-fund composition feed (coin/bar/cash weights and
   units outstanding) to enable intrinsic bubble, real bubble, and fund implied USD.
2. Obtain trade date (not just time) and NAV observation time directly from the IME feed.
3. Obtain certificate contract weight + purity to enable certificate intrinsic/bubble.
4. Add an official gold-fund index source, then replace «در دست ساخت» with real values.
5. Confirm the silver/platinum exclusion heuristic with fund-manager metadata (`fund_type` is
   not sufficient today: e.g. `گنج` is typed as `سهامی` but behaves as a gold commodity fund).
6. Any future formula change requires a unit/integration test and an update to this document;
   Phase 0 engine formulas must not be edited silently.
