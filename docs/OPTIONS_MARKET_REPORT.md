# گزارش کامل بازار آپشن — Iran Market Platform

> مسیر اصلی: `/options` | عنوان: «📊 بازار اختیار معامله» | زیرعنوان: «تحلیل، استراتژی و ابزارهای حرفه‌ای اختیار معامله»
> آخرین به‌روزرسانی: ۱۴۰۴/۰۶/۰۴

---

## ۱. خلاصه اجرایی

بازار آپشن به‌صورت یک **ترمینال ۴ تب** (استراتژی‌ها / زنجیره / ابزار حرفه‌ای / آموزش) پیاده‌سازی شده است. فرانت با React Query به ۲۲ اندپوینت بک‌اند وصل می‌شود و موتور مالی ۳۰ استراتژی، قیمت‌گذاری بلک-شولز، مارجین، VaR و آربیتراژ را پوشش می‌دهد. داده زنده هر ۵ دقیقه از BrsApi (TSETMC + IME) در `brsapi_option_snapshots` / `brsapi_ime_options` به‌روز می‌شود.

- **فرانت:** `frontend/src/app/options/page.tsx` (۵۰۶ خط) + `error.tsx`
- **بک‌اند:** `apps/api/endpoints/options.py` (۴۳۹ خط، ۲۲ endpoint)
- **موتور:** `services/options_service.py` (۱۱۵۵ خط) + `domain/options/*` (۱۰ ماژول قیمت‌گذاری/ریسک)
- **دیتا:** ۶ جدول اصلی + ۲ جدول BrsApi زنده
- **وضعیت بیلد:** `next build` → ۱۱۳/۱۱۳ صفحه OK | `vitest` → ۲۸۵/۲۸۵ OK | `dev` → `0.0.0.0:3000 LISTENING`

---

## ۲. فرانت‌اند

### ۲.۱ ساختار کلی
```
AppLayout (title/subtitle)
 └─ TabBar [strategies | chain | professional | learn]
     ├─ Strategies  → Builder + PayoffDiagram + Recommendations
     ├─ Chain       → SymbolSelector + QuickBuy + Calls/Puts Tables
     ├─ Professional → CostCalculator + PositionSizing + IranRules
     └─ Learn       → Glossary / Mistakes / Formulas
```

State کلیدی: `tab`, `selectedStrategy=covered_call`, `marketCondition=neutral`, `riskTolerance=0.5`, `stockPrice/strike/callPremium/putPremium`, `selectedSymbol`, `chainData`.

Helperها: `riskColor` (کم=emerald، متوسط=amber، زیاد/خیلی‌زیاد=rose)، `riskLabel`، `fmt` با `fa-IR`.

### ۲.۲ تب استراتژی‌ها
- **شرایط بازار:** ۴ دکمه bullish/bearish/neutral/volatile (active `bg-primary-600`) + اسلایدر ریسک ۰–۱.
- **پیشنهاد خودکار:** گرید ۸ کارته از `POST /options/recommend` → کلیک = `setSelectedStrategy` + `analyze`.
- **Builder (ستون چپ):** `<select>` از ۳۰ استراتژی، ۴ input عددی، دکمه «تحلیل استراتژی» → `POST /options/analyze`.
- **نتیجه (ستون راست):** ۳ متریک (حداکثر سود emerald / حداکثر زیان rose / هزینه اولیه)، قرص‌های سر‌به‌سر amber، **PayoffDiagram SVG** (۶۰۰×۳۰۰، خط صفر چین‌دار `#475569`، polyline سبز `#10b981`، ناحیه سود/زیان، خطوط BE طلایی، برچسب‌های فارسی)، لیست لگ‌ها (خرید/فروش، Call/Put/Stock، strike/premium/qty)، باکس `best_for`.
- **همه استراتژی‌ها:** گرید ۵ستونه، انتخاب هایلایت `bg-primary-600/20`.

### ۲.۳ تب زنجیره
- **انتخاب نماد:** گرید ۲–۵ ستونه از `GET /options/live/symbols` (نماد، تعداد قرارداد، حجم به میلیون، قیمت) — کلیک = `loadChain`.
- **QuickBuyPanel:** قیمت سهم پایه، input اعمال و تعداد، دو دکمه خرید Call (emerald) / Put (rose) → فعلاً `alert` (mock).
- **تحلیل زنجیره:** `atm_strike`, `put_call_ratio`, `max_pain`, `pcr_interpretation`.
- **جداول Calls/Puts:** ۷ ستون (اعمال، قیمت، Bid، Ask، حجم، OI، وضعیت ITM/OTM/ATM رنگی) — کلیک سطر مقدار strike/premium را پر کرده و به تب استراتژی می‌برد. منطق ITM: Call اگر `strike < underlying`، Put اگر `strike > underlying`.

### ۲.۴ تب ابزار حرفه‌ای
- **محاسبه هزینه واقعی:** ورودی ورود/خروج/تعداد → `POST /professional/costs` → سود ناخالص، کارمزد، سود خالص و ٪، سر‌به‌سر.
- **سایز پوزیشن:** سرمایه/٪ریسک/زیان هر قرارداد → `POST /professional/position-sizing` → حداکثر قرارداد، هزینه کل، ٪ سرمایه.
- **قوانین ایران (۸ کارت):** کارمزد خرید ۰.۱۲۵٪ / فروش ۰.۶۲۵٪ (با مالیات)، تسویه T+2، هر قرارداد ۱۰۰۰ سهم، دامنه ±۱۹٪، اروپایی، فروش استقراضی ممنوع، حداقل ۵۰م.

### ۲.۵ تب آموزش
- **واژه‌نامه:** ۲۵ واژه (فارسی/انگلیسی/توضیح) در کارت‌های شیشه‌ای.
- **خطاهای رایج:** ۱۰ مورد با ❌ و راه‌حل ✅.
- **فرمول‌ها:** گرید کد تک‌رنگ `dir=ltr` (BS call/put, d1/d2, Greeks).

### ۲.۶ ناوبری
- `Sidebar.tsx:18` → `{ href:"/options", label:"آپشن", icon:"🎯"}`
- `nav-config.tsx`: داشبورد → «اختیار معامله»، بازارها → «اختیار»، `SEARCH_SHORTCUTS` → «آپشن»
- `SyncStatus.tsx` → `SECTION_ID_MAP.options="option"` و `TABLE_LABELS` order 9، دکمه Sync Now به `POST /brsapi/manage/sync/option`

---

## ۳. بک‌اند API

### ۳.۱ روتر `apps/api/endpoints/options.py` (پیشوند `/options`)

| دسته | متد | مسیر | ورودی | خروجی |
|------|-----|------|-------|-------|
| استراتژی | `GET` | `/strategies` | — | `list[StrategyInfo]` (۳۰ مورد: id/name/name_fa/category/market/risk/legs) |
| | `POST` | `/analyze` | `strategy, stock_price, strike, call_premium, put_premium, ...` | `StrategyResult` (max_profit/loss, break_even, legs, profit_at_expiry) |
| | `POST` | `/recommend` | `market_condition, risk_tolerance` | لیست مرتب با `score` |
| قیمت‌گذاری | `GET` | `/greeks?S,K,T,r,sigma,type` | query | `price, delta, gamma, theta, vega, rho, intrinsic, time_value` |
| | `GET` | `/pricing?S,K,T,r,sigma` | query | `call_price, put_price` |
| دانشنامه | `GET` | `/reference/{selection-guide,mistakes,glossary,references,examples,syllabus,iran-rules,stats,formulas}` | — | ثابت‌های `options_reference.py` |
| تحلیل | `GET` | `/analytics/arbitrage/parity` | `call,put,S,K,T` | بررسی `C+Ke^-rT = P+S` |
| | `POST` | `/analytics/arbitrage/scan` | chain | نقض parity + box spread |
| | `POST` | `/analytics/volatility` | chain | IV surface vs HV، smile |
| | `POST` | `/analytics/portfolio` | positions | جمع Greeks |
| حرفه‌ای | `POST` | `/professional/{costs,position-sizing,iv-rank,chain-analysis,checklist}` | قیمت/سرمایه/chain | هزینه واقعی، سایز، IV Rank، PCR/max_pain، چک‌لیست ۱۲موردی |
| | `GET` | `/professional/iran-costs` | — | مثال ۵۰۰→۸۰۰ |
| زنده | `GET` | `/live/chain/{underlying}?limit=50` | underlying | calls/puts مرتب + `analyze_options_chain` |
| | `GET` | `/live/symbols` | — | `underlying, count, volume, price` |

سایر فایل‌های مرتبط: `brsapi.py` (نگاشت `option` و `ime-options`).

### ۳.۲ اسکیما `schemas/api/options.py`
`OptionRequest/Response/ListResponse` — نسخه minimal؛ اندپوینت اصلی از تایپ‌های داخلی `AnalyzeRequest/RecommendRequest` استفاده می‌کند.

---

## ۴. موتور مالی

### ۴.۱ `services/options_service.py`
`OptionsStrategyEngine` — ثابت‌های ایران: `CONTRACT_SIZE=1000`, `RISK_FREE=15%`, `COMMISSION_BUY 0.125%`, `SELL 0.625%`, `SETTLEMENT T+2`, `PRICE_LIMIT 5%`, `OPTION_LIMIT 19%`, `MIN_CAPITAL 50M`.

۳۰ متد `analyze_*`: `covered_call`, `married_put`, `collar`, `long/short_straddle/strangle`, `bull/bear_call/put_spread`, `butterfly/iron_butterfly/iron_condor/condor`, `strip/strap/gut`, `calendar/ratio/back_spread`, `conversion/synthetic_long/short`, `diagonal` — هرکدام break-even و `profit_at_expiry` در ۵ نقطه (۰.۷/۰.۸۵/۱/۱.۱/۱.۳×).

ابزارها: `calculate_realistic_costs`, `calculate_position_size`, `calculate_iv_rank` (۵ سطح)، `analyze_options_chain` (ATM/PCR/max_pain)، `generate_trade_checklist` (۱۲ + اختصاصی).

### ۴.۲ `services/options_reference.py` (۳۸۵ خط)
`STRATEGY_SELECTION_GUIDE`، `COMMON_MISTAKES` (۱۰)، `GLOSSARY` (۲۵)، `REFERENCES` (Hull, Natenberg…)، `IRANIAN_EXAMPLES` (۱۰ کیس واقعی ذوب/فارس…)، `COURSE_SYLLABUS` (۷ فصل)، `IRAN_MARKET_RULES`، `IRAN_OPTIONS_STATS` (رشد ۳.۲× در ۱۴۰۳، ۷۵٪ خرید ساده)، `KEY_FORMULAS`.

### ۴.۳ `services/options_analytics.py`
`ArbitrageDetector`، `VolatilityAnalyzer` (Newton IV)، `OptionsPortfolioAnalyzer` (جمع Greeks + پیشنهاد hedge).

### ۴.۴ `domain/options/*`

| فایل | نقش |
|------|-----|
| `pricing.py` | Black-Scholes + `implied_volatility` (Newton ۱۰۰ تکرار) |
| `greeks.py` / `higher_order_greeks.py` | Delta/Gamma/... + Speed/Charm/Vanna/Vomma/Color/Ultima |
| `tree_pricing.py` | Binomial/Trinomial (CRR/Boyle) با اعمال زودهنگام آمریکایی |
| `heston_model.py` | نوسان تصادفی (Fourier + Monte Carlo QE) |
| `commodity_pricing.py` | طلا/زعفران/پسته (carry, Black76) |
| `margin_engine.py` | مارجین covered/spread/condor/straddle |
| `var_calculator.py` | VaR تاریخی/پارامتری/مونت‌کارلو + CVaR |
| `probability.py` | احتمال touch/ITM، expected move، max pain |
| `entities.py` / `volatility.py` / `rules.py` | موجودیت‌ها و اعتبارسنجی |

---

## ۵. دیتابیس

| مدل | جدول | کلید |
|-----|------|------|
| `OptionContractModel` | `option_contracts` | `symbol PK`, ایندکس `(underlying,expiry)` |
| `OptionSnapshotModel` | `option_snapshots` | `contract_id+date` |
| `OptionTradeModel` | `option_trades` | `contract_id,date,time` |
| `OpenInterestHistoryModel` | `open_interest_history` | `contract_id,date` |
| `VolatilitySurfaceModel` | `volatility_surface` | `underlying+strike+expiry` |
| `CorporateActionModel` | `corporate_actions` | `symbol, ex_date` |
| `OptionSnapshotModel` (BrsApi) | `brsapi_option_snapshots` | ۸۰+ ستون، bid/ask ۵ سطح، underlying_price |
| `ImeOptionModel` | `brsapi_ime_options` | جفتی call/put در هر strike، ۳ سطح bid/ask |

---

## ۶. Ingestion

```
BrsApi /Tsetmc/Option.php (18/min) ─┐
                                    ├─► TsetmcParser/ImeParser ─► SyncService (هر ۵دقیقه، فقط ساعات بازار)
BrsApi /IME/Option.php (12/min) ────┘                              ├─► brsapi_option_snapshots
                                                                   └─► brsapi_ime_options
                                                                            │
                                           QueryService.get_options_by_underlying ─► /live/chain
```

`brsapi/config.py` (OPTION/IME_OPTION)، `brsapi/jobs/registry.py` (`brsapi_options` و `brsapi_ime_options` با `market_hours_only=True`)، `sync-settings.ts` (`maxAge=30min`).

---

## ۷. بک‌تست

`backtesting/strategies/options/` شامل `CoveredCall, ProtectivePut, Straddle, Strangle, BullCallSpread, BearPutSpread` (هرکدام `on_bar → OrderEvent`) + `multi_market/market_adapter.py` با `OPTIONS="options"`.

---

## ۸. تست و کیفیت

- `tests/unit/options/test_options_comprehensive.py` (۵۱۵ خط): BS parity/Greeks، کالای طلا، درخت، مارجین، VaR، احتمال.
- `test_options.py` (۳۷۷ خط): تست ۴ پرووایدر (algotik/pytsetmc/BrsApi/direct).

---

## ۹. وضعیت و پیشنهادات

**وضعیت فعلی:** بیلد و فرانت سالم، زنجیره زنده وابسته به BrsApi (در صورت فیلتر/اختلال، جدول خالی ولی صفحه سفید نمی‌شود).

**پیشنهاد بهبود:**
1. اتصال `QuickBuyPanel` از `alert` به سفارش واقعی کارگزاری.
2. افزودن WebSocket قیمت لحظه‌ای به‌جای poll ۶۰ثانیه.
3. تمیز کردن هشدارهای `eslint` (`Date.now` در رندر، `setState` در effect) در `TickerBar`/`useMarketData`.
4. پوشش تست برای `margin_engine` و `var_calculator` در CI.

---

*مسیرهای مطلق کلیدی:*
`apps/api/endpoints/options.py`, `services/options_service.py`, `services/options_reference.py`, `services/options_analytics.py`, `domain/options/*`, `models/option.py`, `brsapi/models/tsetmc.py`, `brsapi/models/ime.py`, `frontend/src/app/options/page.tsx`, `frontend/src/app/options/error.tsx`, `frontend/src/lib/sync-settings.ts`
