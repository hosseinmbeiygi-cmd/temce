# تحلیل جامع و عمیق ماژول غربالگری هوشمند (Smart Screening)

> تحلیل‌کننده: WorkBuddy AI | تاریخ: ۱۴۰۵/۰۸/۲۱ | زبان: فارسی
> هدف: بررسی عمیق، چندجانبه و انتقادی کل سیستم غربالگری هوشمند از معماری تا امنیت، عملکرد، تست و تجربه کاربر.

---

## ۱. خلاصه اجرایی (Executive Summary)

ماژول «غربالگری هوشمند» در این پروژه **سه سیستم غربالگری موازی و مستقل** دارد که هیچ‌کدام با هم یکپارچه نشده‌اند:

| نسخه | مسیر API | موتور اصلی | خروجی امتیاز | حالت کلیدی |
|------|----------|-----------|--------------|-----------|
| **V1** | `/screener` | `ScreenerService` → `ScreenerPipeline` → `ScoringEngine` (۹ لایه Smart Money) | SMC در `[۰,۱]` | ۵ فاز: نقدشوندگی/قدرت/ساختار/جریان‌سفارش/تریگر |
| **V2** | `/screener-v2` | `SmartScreenerV2` + `AdvancedAnalyticsEngine` | ترکیبی در `[-۱,۱]` | چندبازه‌ای (multi-timeframe)، ۱۵ اندیکاتور |
| **۱۱۰ ستونه** | `/screener110` | `screener110_service` (معماری ۳ لایه) | ۹ زیرامتیاز وزنی | الهام‌گرفته از CANSLIM، خروجی تصمیم‌محور |

**یافته‌های کلیدی:**
1. **تکرار کد گسترده** — کشِ TTL/LRU، محدودیت نرخ (rate-limit) و منطق فیلتر در سه ماژول endpoint تکرار شده است.
2. **لایه دامنه یتیم (Orphaned Domain Layer)** — `domain/screening/` ساخته شده اما **هیچ endpointی آن را import نمی‌کند**؛ فقط خودش و `rules.py` به خودش ارجاع می‌دهند.
3. **شِمای یتیم** — `schemas/api/screening.py` جایگزین شده توسط `screener_filter.py` و عملاً بلااستفاده است.
4. **فیلدهای اعلام‌شده اما سیم‌نشده** — در V2 پارامترهای `timeframe`، `risk_tolerance`، `signal_filter` در مدل Pydantic هستند اما به خط لوله وصل نیستند.
5. **وضعیت ماژول-سطح ناایمن** — سیستم ۱۱۰ ستونه از `_last_run` (دیکشنری در سطح ماژول) استفاده می‌کند که نه thread-safe است و نه در ری‌استارت باقی می‌ماند.
6. **صحت الگوریتمی متوسط** — RSI از میانگین ساده (نه Wilder)، MACD سیگنال ساده‌سازی‌شده، و تخمین open از close در تشخیص الگوها.
7. **پوشش تست ضعیف در سطح ریاضی** — اکثر تست‌ها integration با mock هستند؛ واحد تستی برای فرمول‌های امتیازدهی وجود ندارد.

---

## ۲. معماری کلان و نقشه سیستم

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (/smart-screener)                    │
│  React + TanStack Query | FloatingShortcuts | SmartScreenerFab        │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │                               │
        ┌───────▼────────┐              ┌────────▼─────────┐
        │  Chat / NLU    │              │  REST API Router │
        │ IntentClassifier│             │  (apps/api/router)│
        │ CompoundSplitter│             └───┬───┬────┬──────┘
        └───────┬────────┘                 │   │    │
                │                           │   │    │
   ┌────────────▼──────────┐   ┌────────────▼───▼────┐ ┌▼──────────────┐
   │   Dynamic Filter      │   │ /screener     │ /screener-v2 │ /screener110│
   │   (فیلتر RSI<30)      │   │  V1            │  V2           │  110-col    │
   └───────────┬───────────┘   └──────┬─────────┴────┬─────────┴─────┬──────┘
               │                     │              │               │
   ┌───────────▼─────────────────────▼──────────────▼───────────────▼──────┐
   │                 سرویس‌های غربالگری (۳ سیستم موازی)                    │
   │  ScreenerService │ SmartScreenerV2 │ screener110_service            │
   │  + ScoringEngine │ +AdvancedAnalytics│ +BatchLoader/Vector/BulkWriter│
   │  (۹ لایه SMC)    │                  │                              │
   └───────────┬─────────────────────┬──────────────┬───────────────┬──────┘
               │                     │              │               │
   ┌───────────▼─────────────────────▼──────────────▼───────────────▼──────┐
   │  market_watch_helper (تنها نقطه اشتراک!) │ Saved Filters CRUD       │
   │  fetch_market_watch / fetch_history_map   │ ScreenerAIReportService  │
   └───────────┬───────────────────────────────┬──────────────────────────┘
               │                               │
   ┌───────────▼───────────────────────────────▼──────────────────────────┐
   │  PostgreSQL: snapshots | daily_history | daily_real_legal |          │
   │  screener_profiles (۱۱۰ ستون) | screener_daily_scores | signals      │
   └─────────────────────────────────────────────────────────────────────┘

   ⚠️ لایه domain/screening/ در هیچ‌کدام از مسیرهای فوق حضور ندارد (یتیم).
```

---

## ۳. سه سیستم غربالگری موازی

### ۳.۱ نسخه ۱ (V1) — لوله ۵ مرحله‌ای Smart Money
**فایل‌ها:** `services/screener_service.py` (۱۱۸۳ خط)، `services/smart_money/scoring_engine.py` (۲۶۰ خط) + ۹ لایه.
**جریان:** `ScreenerService.screen()` → برای هر سهم `ScreenerPipeline.run()` → `ScoringEngine.analyze()`.

`ScoringEngine` شامل ۹ لایه است:
- L1 قیمت/حجم، L2 جذب (Absorption)، L3 مالکیت، L4 فشردگی، L5 قدرت نسبی،
- L6 آمادگی شکست، L7 قدرت خریدار، L8 ریزساختار، L9 کیفیت شکست.

ویژگی‌های مثبت V1:
- **دروازه کیفیت داده (Data Quality Gate)** — نمادهای با کیفیت پایین رد می‌شوند.
- **تخمین اطمینان (Confidence)** — سطح عدم‌قطعیت را گزارش می‌دهد.
- **پیکربندی YAML-محور** — وزن‌ها و آستانه‌ها از کانفیگ خوانده می‌شوند (hot-reload).
- **حالت جزئی (Partial Mode)** — وقتی تاریخچه کم است لایه‌های سنگین را رد می‌زند.

امتیاز نهایی V1: `smc_final ∈ [0,1]` با ۳ جریمه (ریسک توزیع، شکست کاذب، فشردگی مرده).

### ۳.۲ نسخه ۲ (V2) — موتور ترکیبی چندبازه‌ای
**فایل‌ها:** `services/smart_screener_v2.py` (۷۲۱ خط)، `services/smart_money/advanced_analytics.py` (۶۵۳ خط).
**وزن‌های ترکیبی:** `smart_money=0.4, technical=0.3, fundamental=0.2, momentum=0.1`.

نقاط قوت:
- **تشخیص صریح None در مقابل ۰.۰** — RSI=۰ یعنی اشباع فروش واقعی؛ عدم‌اندازه‌گیری (None/NOT_MEASURED) نباید نماد را «خرید» رتبه‌بندی کند. این یک تصمیم طراحی بسیار خوب است (دیدگاه در `advanced_analytics.py` خط ۱۸-۳۲ مستند شده).
- **۱۵ اندیکاتور فنی** — RSI/MACD/BB/ADX/Stochastic/CCI/MFI/Williams%R/OBV/VWAP/ATR + تشخیص الگوهای شمعی + سطوح حمایت/مقاومت + پروفایل حجم + چرخش بخشی.
- **بازنرمال‌سازی وزن** — وقتی یک «پا» (leg) None باشد وزن‌ها تقسیم بر مجموع می‌شوند.

نقاط ضعف V2:
- فیلدهای `timeframe`, `risk_tolerance`, `signal_filter` در `ScreenerV2Request` **اعلام شده اما سیم نشده‌اند**.
- منطق فیلتر در `_apply_client_filters` (سرویس) **و** در endpoint (خط ۳۵۶-۴۴۰) **تکرار شده** — دو منبع حقیقت.

### ۳.۳ سیستم ۱۱۰ ستونه (Screener110) — معماری ۳ لایه
**فایل:** `services/screener110_service.py` (۷۹۶ خط).
**معماری:**
1. `BatchLoader` — ۵ کوئری SQL متوالی (نه موازی، به‌دلیل محدودیت AsyncSession).
2. `VectorCalculator` — stateless، از `__slots__` برای بهینگی.
3. `BulkWriter` — upsert تکه‌ای با `ON CONFLICT DO NOTHING`.

- ۹ زیرامتیاز وزنی که جمعاً ۱.۰ می‌شوند.
- ۱۰ ستون پرچم ریسک (`RISK_FILTER_COLUMNS`).
- منطق تصمیم: `rule_pass = adj ≥ 70 and risk and neg_cnt < 3` → خروجی: خرید/نخرید/رد_ریسک/رد_نمره.
- حد ضرر: `max(price - 2*ATR, price*0.93)`؛ اندازه موقعیت از ۱٪ سرمایه / (price - SL).

**نقطه ضعف حیاتی:** وضعیت `_last_run` (دیکشنری ماژول-سطح) در `screener110.py` نه thread-safe است و نه پس از ری‌استارت باقی می‌ماند.

---

## ۴. جریان داده (Data Flow)

۱. **منبع:** `brsapi_symbol_snapshots` (quote لحظه‌ای)، `brsapi_historical_daily` (OHLCV)، `brsapi_historical_real_legal` (حقیقی/حقوقی).
۲. **تبدیل:** `market_watch_helper.build_market_watch_from_snapshots` و `candles_from_daily_rows` (تنها نقطه اشتراک واقعی بین V1 و سایرین).
۳. **تحلیل:** هر سیستم داده را به فرمت خود مصرف می‌کند.
۴. **خروجی:** `ScreenerProfile` (۱۱۰+ ستون در ۶ بخش)، `ScreenerSnapshot` (سری‌زمانی)، `ScreenerSignal` (ردیابی خروجی: entry/exit/pnl/outcome_correct).
۵. **جدول رتبه‌بندی روزانه:** `scripts/build_screener_scores.py` جدول `screener_daily_scores` را با `rank_in_market`, `rank_in_industry`, `percentile_score` می‌سازد.
۶. **گزارش‌دهی:** `ScreenerAIReportService` گزارش‌های تحلیل‌گر فارسی تولید می‌کند.
۷. **زمان‌بندی:** `Screener110RunCycleJob` هر ۲ دقیقه کل چرخه را اجرا می‌کند.

**نکته مهم در `candles_from_daily_rows` (خط ۱۳۱-۱۵۷):** قبلاً ناهماهنگی بین کلیدهای `price_open`/`price_high` و `price_first`/`price_max` باعث می‌شد تمام high/low/volume صفر شود و اندیکاتورها «برعکس در زمان» محاسبه شوند — این با reverse کردن لیست اصلاح شده است.

---

## ۵. صحت الگوریتم‌ها (Algorithm Correctness)

| بخش | وضعیت | توضیح |
|-----|-------|-------|
| **RSI** | ⚠️ | از میانگین ساده (sum/period) استفاده می‌کند، نه هموارسازی Wilder. در بازارهای واقعی RSI استاندارد Wilder است. خطای کوچک اما سیستماتیک. |
| **MACD** | ⚠️ | وقتی طول < ۳۵، سیگنال = `macd_line * 0.8` (ساده‌سازی). همچنین در حلقه `for i` برای هر i دوباره EMA را از اول محاسبه می‌کند → O(n²). |
| **Bollinger** | ⚠️ | وقتی `len < period`، مقدار `sma*1.02/sma/sma*0.98` برمی‌گرداند (داوری دلبخواه). |
| **ADX/CCI/MFI/Williams** | ✅ | فرمول‌ها تقریباً استاندارد هستند. |
| **تشخیص الگو** | ⚠️ | از `close` به‌عنوان `open` استفاده می‌کند (`o = closes[i-1]`) — داده واقعی open را نادیده می‌گیرد. |
| **VWAP** | ✅ | فرمول (H+L+C)/3 × V صحیح است. |
| **تفکیک None/۰** | ✅✅ | طراحی عالی در V2/AdvancedAnalytics. |
| **وزن‌دهی ترکیبی V1** | ✅ | با clamp به [۰,۱] و جریمه‌ها منطقی است. |

**نتیجه:** الگوریتم‌های هسته «کار می‌کنند» اما در جزئیات با استانداردهای صنعتی فاصله دارند (مخصوصاً RSI و MACD). برای سیگنال‌دهی مالی این تفاوت‌ها می‌توانند رتبه‌بندی را جابجا کنند.

---

## ۶. لایه دامنه یتیم (Orphaned Domain Layer)

`domain/screening/` شامل:
- `filters.py` — `FilterOperator`, `FilterCriterion`, `ScreeningFilter`
- `ranking.py` — `ScreeningResult`
- `presets.py` — `ScreeningPreset`
- `rules.py` — اعتبارسنج‌ها (validators)

**تأیید شده با grep:** تنها مصرف‌کنندگان این ماژول، خودِ `__init__.py` و `rules.py` هستند. **هیچ endpoint یا سرویسی** آن را import نمی‌کند. endpointها منطق فیلتر خود را به‌صورت inline تعریف کرده‌اند.

**پیامد:** این یک لایه DDD کامل است که ساخته شده اما هرگز «سیم» نشده — نگهداری آن هزینه بدون سود است و هرگونه تغییر در آن بی‌اثر خواهد بود.

همین وضعیت برای `schemas/api/screening.py` (`ScreeningRequest`, `ScreeningResult`, `ScreeningListResponse`) صادق است که توسط `schemas/api/screener_filter.py` جایگزین شده.

---

## ۷. تکرار کد و انتشار نسخه‌ها (Duplication & Version Sprawl)

۱. **کش TTL/LRU** — `_CacheManager` در `screener_service.py` تعریف شده، اما نمونه‌های جداگانه در سه endpoint (`screener.py`, `screener_v2.py`, `screener110.py`) نگهداری می‌شوند → ۳ پیاده‌سازی/تنظیم موازی.
۲. **Rate-limit** — از `core.rate_limit` اشتراکی استفاده می‌شود (خوب) اما هر endpoint جداگانه آن را فراخوانی می‌کند.
۳. **منطق فیلتر** — بین `SmartScreenerV2._apply_client_filters` و endpoint V2 (خط ۳۵۶-۴۴۰) دوبار نوشته شده.
۴. **تبدیل snapshot→candle** — `market_watch_helper` نقطه اشتراک خوبی است اما V1 هنوز `build_real_quote_from_snapshot`/`build_real_history_from_rows` خودش را دارد.
۵. **سه سیستم موازی** با هدف مشابه (انتخاب سهم برتر) بدون یک «ورودی واحد» (facade) — انتخاب برای کاربر و توسعه‌دهنده گیج‌کننده است.

---

## ۸. امنیت (Security)

| موضوع | وضعیت | جزئیات |
|-------|-------|--------|
| **احراز هویت** | ✅ | `saved_filters.py` از `get_current_user` استفاده می‌کند. |
| **RBAC** | ✅ | تست `test_funds_api.py` نشان می‌دهد screener نیازمند نقش analyst/admin است. |
| **محدودیت نرخ** | ✅ | per-IP sliding window در `core.rate_limit`. |
| **جلوگیری از تزریق** | ✅ | ستون مرتب‌سازی (sort column) از whitelist عبور می‌کند. |
| **فیلتر سمت کلاینت** | ⚠️ | عملگرهای gte/lte/gt/lt/eq/neq/between/in/not_in/contains اعمال می‌شوند؛ ورودی‌های رشته‌ای در `_parse_numeric` پاک‌سازی می‌شوند. |
| **ذخیره فیلتر** | ⚠️ | `filters_json` به‌صورت رشته JSON ذخیره می‌شود (خطر eval/parse نادرست اگر اعتبارسنجی ضعیف شود). |

**نقطه قوت:** جداسازی خواندنی‌ها با `get_replica_session` (کاهش بار روی primary).
**نقطه ضعف:** هیچ اعتبارسنجی ساختاری مرکزی روی فیلترهای پیچیده (AND/OR nested) دیده نشد.

---

## ۹. عملکرد و کش (Performance & Caching)

- **کش درون‌حافظه‌ای TTL ۶۰ ثانیه** با LRU — خوب برای کاهش بار DB، اما:
  - در `ScoringEngine.reload_config` کش `ScreenerPipeline._score_cache` پاک می‌شود، اما V2 کش خودش را دارد → **عدم هماهنگی**.
  - کش‌ها در سطح ماژول هستند → در محیط multi-worker (چندین process) **هر worker کش جداگانه** دارد (اثربخشی کم).
- **BatchLoader ۱۱۰ ستونه موازی نیست** (۵ کوئری متوالی) به‌دلیل محدودیت AsyncSession — فرصت بهینه‌سازی با `asyncio.gather`.
- **MACD O(n²)** — بازنویسی EMA در هر ایندکس.
- **۹ لایه SMC** هرکدام `compute` جداگانه — برای ۵۰۰+ نماد در لحظه ممکن است سنگین شود.

---

## ۱۰. پوشش تست (Test Coverage)

یافته‌ها از grep روی `tests/`:
- `tests/integration/test_screener_endpoint.py` — تست integration که تأیید می‌کند endpoint از `fetch_market_watch` shared استفاده می‌کند (خوب).
- `tests/test_screener_flow.py` — تست end-to-end جریان داده.
- `tests/test_screener_api.py`, `tests/legacy/...` — تست‌های legacy با mock.
- `tests/test_funds_api.py` — تست RBAC برای screener.

**شکاف‌های تست:**
- ❌ هیچ **واحد تست (unit test)** برای فرمول‌های امتیازدهی (RSI/MACD/وزن‌دهی ترکیبی) دیده نشد.
- ❌ تستی برای منطق فیلتر (`_apply_client_filters`)، تفکیک None/۰، و تصمیم‌گیری ۱۱۰ ستونه وجود ندارد.
- ❌ هیچ تستی روی `domain/screening/` (منطقی، چون یتیم است).
- ❌ در `AUDIT_REPORTS/` هیچ گزارش ممیزی‌ای به screener اشاره نمی‌کند.

---

## ۱۱. رابط کاربری و تجربه کاربر (Frontend)

- **صفحه:** `/smart-screener` (۱۲۶۷ خط، React/Next.js + TanStack Query).
- **مؤلفه‌های شناور:** `SmartScreenerFab` (قرص شناور) و `FloatingShortcuts` (ناوبری کناری).
- **تعریف فیلدها:** ۱۳ فیلد آماده (`FILTER_FIELDS`) با برچسب فارسی و محدوده min/max.
- **عملگرها:** gte/lte/gt/lt/eq/between با رابط فارسی.
- **نمایش نتایج:** جدول با `ScreenedItem` (smc_score, phase, rank, reason, امتیازهای ۵گانه).

**نقطه قوت:** رابط کاربر فارسی کامل و مرتبط با خروجی V1 است.
**نقطه ضعف:** frontend عمدتاً به V1 متصل است؛ خروجی‌های متمایز V2 و ۱۱۰ ستونه (تصمیم خرید/حد ضرر/اندازه موقعیت) در UI فعلی بازنمایی نشده‌اند.

---

## ۱۲. ادغام با چت و NLU

- **`IntentClassifier`** (۶۰۰ خط): ML (TF-IDF + LogisticRegression) با fallback رجکس. شامل intentهای `screener` و `dynamic_filter`.
  - الگوهای `screener`: `(غربال|screener|screen)`, `(پول هوشمند|smart money|smc)`, `(حجم بالا|تجمع|توزیع)`, `(شکست مقاومت|breakout)`.
  - `dynamic_filter` برای پرسش‌هایی مثل «فیلتر RSI<30».
- **`CompoundSplitter`** (۱۵۹ خط): پرسش‌های مرکب فارسی («تحلیل فولاد و مقایسه با شپنا») را تقسیم می‌کند.
- **`ScreenerAIReportService`**: ترکیب مدل ۱۱۰ ستونه + پروفایل + تاریخچه سیگنال + جریان قانونی + تاریخچه روزانه برای تولید گزارش فارسی.

این لایه نویدبخش است اما به‌خوبی به V2/110 وصل نشده (فقط V1 و dynamic_filter را پوشش می‌دهد).

---

## ۱۳. فهرست باگ‌ها و نقاط ضعف (Consolidated Issues)

| # | شدت | مشکل | محل |
|---|------|------|-----|
| ۱ | 🔴 | `_last_run` ماژول-سطح → ناایمن در ری‌استارت/چندنخی | `screener110.py` |
| ۲ | 🔴 | لایه دامنه `domain/screening/` یتیم | `domain/screening/*` |
| ۳ | 🟠 | فیلدهای V2 (`timeframe` و غیره) سیم‌نشده | `screener_v2.py` |
| ۴ | 🟠 | تکرار منطق فیلتر (سرویس + endpoint) | `screener_v2.py` ۳۵۶-۴۴۰ |
| ۵ | 🟠 | MACD O(n²) و سیگنال ساده‌سازی‌شده | `advanced_analytics.py` ۲۳۳-۲۴۷ |
| ۶ | 🟠 | RSI از میانگین ساده (نه Wilder) | `advanced_analytics.py` ۲۰۲-۲۱۵ |
| ۷ | 🟡 | کش‌های موازی در سه endpoint بی‌هماهنگ | `screener*.py` |
| ۸ | 🟡 | `reload_config` فقط کش V1 را پاک می‌کند | `scoring_engine.py` ۶۲-۷۱ |
| ۹ | 🟡 | تشخیص الگو از close به‌عنوان open | `advanced_analytics.py` ۳۷۱ |
| ۱۰ | 🟡 | فقدان واحد تست برای فرمول‌های ریاضی | `tests/` |
| ۱۱ | 🟡 | BatchLoader موازی نیست | `screener110_service.py` |
| ۱۲ | 🟢 | `schemas/api/screening.py` یتیم | `schemas/api/screening.py` |

---

## ۱۴. توصیه‌ها و نقشه راه بهبود (Recommendations)

### الف) کوتاه‌مدت (Low-risk، High-value)
1. **یکپارچه‌سازی کش:** کش را به سرویس اشتراکی (مثلاً `core.cache`) منتقل کنید تا همه endpointها یک نمونه داشته باشند و `reload_config` همه را پاک کند.
2. **رفع وضعیت `_last_run`:** آن را به Redis/DB یا حداقل lock با `threading.Lock` + persist منتقل کنید.
3. **سیم کردن فیلدهای V2:** `timeframe` را به AdvancedAnalytics و `risk_tolerance` را به وزن‌دهی ترکیبی وصل کنید، یا از مدل حذفشان کنید.
4. **حذف تکرار فیلتر:** منطق فیلتر را در یک تابع shared قرار دهید و هر دو endpoint و سرویس از آن استفاده کنند.

### ب) میان‌مدت
5. **انتخاب یک «موتور پیش‌فرض»:** V1 (SMC) را به‌عنوان هسته نگه دارید و V2 را یا در آن ادغام کنید یا به‌عنوان «حالت پیشرفته» زیر یک facade واحد (`/screener`) قرار دهید. سیستم ۱۱۰ ستونه را به‌عنوان «لایه تصمیم» (فقط خروجی خرید/ریسک) نگه دارید.
6. **وصل کردن یا حذف لایه دامنه:** `domain/screening/` را یا به endpointها متصل کنید یا مستندسازی کنید که deprecated است و حذفش کنید.
7. **اصلاح RSI/MACD:** به هموارسازی Wilder و MACD سیگنال استاندارد (EMA-9 روی خط MACD) ارتقا دهید؛ MACD را به O(n) برسانید.
8. **واحد تست‌ها:** حداقل برای `_compute_composite`، وزن‌دهی V1، تفکیک None/۰ و منطق تصمیم ۱۱۰ ستونه تست بنویسید.

### ج) بلندمدت
9. **Facade واحد:** یک `/screener` با پارامتر `mode=v1|v2|full` طراحی کنید تا سه سیستم موازی به یک ورودی تبدیل شوند.
10. **مقایسه بازگشت (Backtest):** خروجی‌های سه سیستم را روی داده تاریخی مقایسه کنید تا مشخص شود کدام دقت سیگنال بالاتری دارد — این پروژه قبلاً ماژول backtesting دارد (`BACKTESTING_README.md`).

---

## ۱۵. نتیجه‌گیری

ماژول غربالگری هوشمند **پوشش تحلیلی بسیار غنی** دارد — از ۹ لایه Smart Money تا ۱۵ اندیکاتور فنی و یک سیستم ۱۱۰ ستونه الهام‌گرفته از CANSLIM، همراه با گزارش‌دهی AI فارسی و ادغام NLU. طراحی جزئیات خوبی دارد (مخصوصاً تفکیک None/۰ و دروازه کیفیت داده).

با این حال، **بزرگ‌ترین ضعف آن «انتشار نسخه و تکرار» است**: سه سیستم موازی، یک لایه دامنه یتیم، کش‌های تکراری، و فیلدهای اعلام‌شده‌اما-سیم‌نشده. این‌ها هزینه نگهداری را بدون سود متناسب بالا می‌برند. اولویت اول باید **یکپارچه‌سازی و حذف تکرار** باشد، نه افزودن قابلیت جدید.

صحت الگوریتمی در سطح «قابل استفاده» است اما برای سیگنال‌دهی مالی جدی، اصلاح RSI/MACD و افزودن واحد تست‌های ریاضی ضروری است.

---
*گزارش توسط تحلیل عمیق کد (۲۵+ فایل) شامل سرویس‌ها، endpointها، لایه دامنه، شِما، فرانت‌اند، NLU و تست‌ها تهیه شده است.*
