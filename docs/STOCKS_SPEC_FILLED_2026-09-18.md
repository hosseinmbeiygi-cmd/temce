# مشخصات فنی کامل و نهایی — ماژول سهام بورس تهران (نسخه تکمیل‌شده از کدبیس)

> تاریخ تکمیل: ۱۸ سپتامبر ۲۰۲۶ · مبنای کاوش: `docs/CODEBASE_DISCOVERY_STOCKS_2026-09-18.md` (کامیت `1bd0f9e`)
> اصل حاکم حفظ شد: **فقط افزودن، هرگز حذف.** هر جای سند اصلی که `[پر کن]` داشت، با واقعیت کد فعلی پر شده و با نشان `📸 واقعیت کد` مشخص است.
> جای هر چیزی که در کد وجود ندارد، صریحاً «**یافت نشد**» نوشته شده (نه حذف سطر) — این خودش اطلاعات مهمی است.
> مواردی که تصمیم تیم می‌خواهند با نشان **🔴 تصمیم تیم** علامت خورده‌اند.

---

## فهرست مطالب
۰) اصل حاکم | ۱) نقشه تب‌ها | ۲) مدل داده | ۳) بک‌اند و سرویس‌ها | ۴) موتور اندیکاتور تکنیکال | ۵) موتور تعدیل قیمت (رویدادهای شرکتی) | ۶) بک‌تست | ۷) ML | ۸) Roadmap | ۹) سوالات باز *(پاسخ داده شد)* | ۱۰) Wireframe تب‌های کلیدی | ۱۱) اسکیمای API | ۱۲) نقش‌ها و پنل مدیریت | ۱۳) Backfill تاریخی | ۱۴) مانیتورینگ کیفیت داده | ۱۵) Edge Case ها | ۱۶) معماری کامپوننت | ۱۷) برنامه تست | ۱۸) واژه‌نامه | ۱۹) خط لوله خودکار دریافت داده | ۲۰) Rollout بدون اختلال | ۲۱) چک‌لیست نهایی | ۲۲) خلاصه اجرایی | 🔴 جمع‌بندی تصمیم‌های تیم

---

## بخش ۰. اصل حاکم

هیچ فیلد/جدول/داده موجود (دیده‌بان فعلی، واچ‌لیست‌های کاربر، تاریخچه قیمت ثبت‌شده) حذف یا بازنویسی نمی‌شود. تغییرات فقط افزودنی هستند؛ در صورت نیاز اجتناب‌ناپذیر به تغییر ساختار قدیمی، migration با قابلیت rollback و اعتبارسنجی قبل/بعد الزامی است.

📸 **واقعیت کد — فهرست دقیق چیزهایی که باید دست‌نخورده بمانند:**

| مورد | مسیر/جدول واقعی | وضعیت |
|---|---|---|
| دیده‌بان فعلی | `GET /api/v1/market-watch` (`apps/api/endpoints/market_watch.py`) + `GET /api/v1/market/*` (۱۱ route) | ✅ حفظ |
| صفحه فرانت دیده‌بان | `frontend/src/app/market-watch/page.tsx` | ✅ حفظ |
| واچ‌لیست کاربران | `/api/v1/watchlist/*` (`apps/api/endpoints/watchlist.py`) — ⚠️ جدولش **بدون migration** ساخته می‌شود (`services/watchlist_service.py:_ensure_table`) | ✅ داده حفظ، ⚠️ جدول باید به Alembic منتقل شود (🔴 تصمیم ۱۶) |
| تاریخچه قیمت ثبت‌شده | `daily_history` (hypertable, PK `(symbol_id, trade_date)`) · `candlesticks` (hypertable) · `brsapi_candlesticks` · `brsapi_historical_daily` | ✅ حفظ |
| هویت نماد | `symbols` + ستون‌های افزودنی migration `0052` (همه nullable) | ✅ حفظ |
| لایه Enterprise سهام | `stock_live_tape`, `stock_order_book_l2`, `stock_indicators_snapshot`, `stock_quant_signals`, `stock_news_sentiment`, `stock_monthly_sales_production`, `market_macro_indicators` (migration `0052`) | ✅ حفظ |
| API سهام فعلی | `GET /api/v1/stocks/v2/*` (۱۲ route) — docstring: «نسخه‌بندی مستقل زیر `/stocks/v2` — endpointهای فعلی دست‌نخورده» | ✅ حفظ |
| فرانت سهام فعلی | `frontend/src/components/StockIntelligencePanel.tsx` (۹ تب + کارت سیگنال) روی `/symbol/[symbol]` | ✅ حفظ |
| جدول‌های legacy | `orderbooks`, `orderbook_snapshots`, `candlesticks` (migration `0001`) — ⚠️ نویسنده فعال ندارند (`docs/OPTIONS_SPEC_FILLED_2026-09-16.md:22-23` همان الگو را برای آپشن تأیید کرده) | ✅ حفظ |

⚠️ **نکته هشدار:** `core/database.py:128-131` — در non-production علاوه بر Alembic، `Base.metadata.create_all` هم اجرا می‌شود (منبع schemaهای خارج از کنترل Alembic). طبق اصل حاکم، هر migration جدید این سند باید کاملاً افزودنی (`CREATE TABLE IF NOT EXISTS` یا `ADD COLUMN IF NOT EXISTS`) باشد.

---

## بخش ۱. نقشه کامل تب‌ها

### ۱.۱. سطح پلتفرم

```
سهام بورس تهران (منوی اصلی)
├── دیده‌بان بازار (Market Watch) — صفحه فعلی، حفظ و ارتقا
├── اسکرینر سهام (Stock Screener)
├── مقایسه نمادها
├── گروه‌بندی صنعتی نمادها
├── رصد صندوق‌های دارنده هر سهم (لینک مستقیم به ماژول صندوق‌ها)
└── [صفحه اختصاصی هر نماد]
```

📸 **واقعیت کد — هر آیتم این نقشه امروز کجاست:**

| آیتم سند | واقعیت کد | فرانت |
|---|---|---|
| دیده‌بان بازار (حفظ و ارتقا) | ✅ `GET /api/v1/market-watch` + `GET /api/v1/market/*` (۱۱ route: `overview`, `indices`, `gainers`, `losers`, `active`, `watch`, `bourse`, `heatmap`, `enriched-heatmap`, `treemap`, `energy-commodity`) | ✅ `/market-watch` (`frontend/src/app/market-watch/page.tsx`) · مکمل: `/heatmap`, `/tables`, `/markets/stocks` (با زیرصفحه‌های `bonds`, `closing`, `dividends`, `maskan`, `rights`, `suspended`, `tal`) |
| اسکرینر سهام | ✅ فراتر از سند: `/api/v1/screener/*` + `/screener/v2/*` (شامل `/compare`) + `/screener110/monitor` + `/scanner/*` · جداول `screener_profiles`, `screener_snapshots`, `screener_signals` (مدل ۱۱۰ ستونی CANSLIM) | ✅ `/screener`, `/screener110`, `/smart-screener` |
| مقایسه نمادها | ✅ جزئی: `GET /api/v1/screener/v2/compare` (`apps/api/endpoints/screener_v2.py:476`) + `GET /api/v1/fundamental/compare` | 🔴 **صفحه اختصاصی مقایسه در فرانت یافت نشد** — نزدیک‌ترین: `/correlations`, `/multi-asset` |
| گروه‌بندی صنعتی نمادها | ✅ داده: `symbols.industry`/`industry_id` + `symbols.industry_name` (افزودنی `0052`) + `brsapi_symbol_snapshots.sector`/`sector_id` · API: `/market/heatmap`, `/market/enriched-heatmap`, `/market/treemap`, `/market-insights/*` · فرانت: `frontend/src/lib/sectors.ts`, `hooks/useSectorCounts.ts`, `components/dashboard/MarketMap.tsx` | 🔴 **صفحه مستقل «گروه‌بندی صنعتی» یافت نشد** — قابلیت داخل heatmap/treemap است |
| رصد صندوق‌های دارنده هر سهم | 🔶 **داده هست، endpoint نیست:** `fund_holdings.instrument_symbol` + `instrument_isin` (`models/fund_enterprise.py:122-124`) · ✅ فقط `GET /api/v1/funds/v2/{fund_id}/holdings` (`funds_v2.py:206`) | 🔴 `GET /api/stocks/:symbol/fund-holders` **یافت نشد** — بدون کد تکراری: یک query جدید روی همان جدول (🔴 تصمیم ۱۷) |
| صفحه اختصاصی هر نماد | ✅ `frontend/src/app/symbol/[symbol]/page.tsx` + `frontend/src/app/symbol-details/page.tsx` + `/analysis/[symbol]` + `/instruments/[id]` | ✅ موجود |
---

### ۱.۲. صفحه اختصاصی هر نماد — ۹ تب

```
Tab 1: نمای کلی
Tab 2: نمودار قیمت و تحلیل تکنیکال
Tab 3: اطلاعات بنیادی
Tab 4: عمق بازار (صف خرید/فروش)
Tab 5: رویدادهای شرکتی (کدال) — افزایش سرمایه، مجمع، تعدیل EPS
Tab 6: صندوق‌های دارنده این سهم (خلاصه + لینک به تب کامل در ماژول صندوق‌ها)
Tab 7: اخبار مرتبط (خلاصه + لینک به ماژول اخبار با فیلتر همین نماد)
Tab 8: بک‌تست استراتژی معاملاتی
Tab 9: پیش‌بینی و ML
```

🔴 **تصمیم تیم #۱ — تعارض نقشه ۹ تب (مهم‌ترین ابهام این سند):**

📸 **۹ تب فعلی که در کد پیاده شده** (`frontend/src/components/StockIntelligencePanel.tsx:6` + `apps/api/endpoints/stocks_v2.py`):

```
تب ۱ تابلو ۳۶۰       → GET /api/v1/stocks/v2/{symbol}/tape
تب ۲ تکنیکال         → GET /api/v1/stocks/v2/{symbol}/indicators
تب ۳ صنعت/هم‌گروه    → GET /api/v1/stocks/v2/{symbol}/peers
تب ۴ شناسنامه        → GET /api/v1/stocks/v2/{symbol}/dossier
تب ۵ کدال            → GET /api/v1/stocks/v2/{symbol}/codal
تب ۶ اخبار/سنتیمنت   → GET /api/v1/stocks/v2/{symbol}/news
تب ۷ تاریخچه         → GET /api/v1/stocks/v2/{symbol}/history  |  /history/export.csv
تب ۸ پروفایل حجم     → GET /api/v1/stocks/v2/{symbol}/volume-profile
تب ۹ نبض بازار       → GET /api/v1/stocks/v2/market-pulse
کارت سیگنال          → GET /api/v1/stocks/v2/{symbol}/signal
```

**نگاشت تب‌های سند به تب‌های موجود (کد):**

| تب سند | تب موجود معادل | وضعیت |
|---|---|---|
| Tab 1 — نمای کلی | تب ۱ (تابلو ۳۶۰) + کارت سیگنال | ✅ ~۷۰٪ پوشش (نیاز: «خلاصه ۳ صندوق برتر» — تب ۶) |
| Tab 2 — نمودار قیمت و تحلیل تکنیکال | تب ۲ (تکنیکال) + تب ۷ (تاریخچه) + تب ۸ (پروفایل حجم) | ✅ داده کامل؛ 🔴 نمودار Candlestick با تایم‌فریم/زوم/افزودن اندیکاتور تعاملی **یافت نشد** |
| Tab 3 — اطلاعات بنیادی | تب ۴ (شناسنامه) + `GET /api/v1/fundamental/ratios/{symbol}` | ✅ پوشش |
| Tab 4 — عمق بازار | ⚠️ فقط داخل تب ۱ (تابلو) به‌صورت ماتریس تابلوخوانی | 🔴 **تب مستقل عمق بازار یافت نشد** — اما `GET /api/v1/orderbooks/{symbol}` و `stock_order_book_l2` موجودند |
| Tab 5 — رویدادهای شرکتی | تب ۵ (کدال) | ⚠️ خام: فقط اعلامیهٔ متنی؛ **ساخت‌یافته نیست** (بدون `action_type`/`price_adjustment_factor`) |
| Tab 6 — صندوق‌های دارنده | ❌ **یافت نشد** | 🔴 داده هست، endpoint و تب نیست |
| Tab 7 — اخبار مرتبط | تب ۶ (اخبار/سنتیمنت) | ✅ پوشش |
| Tab 8 — بک‌تست | ❌ **یافت نشد** (در ۹ تب نماد) | 🔴 API موجود (`/backtests/*`) ولی فراست صفحه نماد وصل نیست |
| Tab 9 — پیش‌بینی و ML | ❌ **یافت نشد** (در ۹ تب نماد) | 🔴 کارت سیگنال تا حدی جای آن را می‌گیرد؛ اما «بازه اطمینان + دقت تاریخی مدل» **یافت نشد** |

**گزینه‌های تصمیم:**
- **(الف)** حفظ ۹ تب کد + به‌روزرسانی سند به نقشه واقعی (کم‌ریسک‌ترین، سازگار با اصل «فقط افزودن»)
- **(ب)** افزودن ۴ تب/بخش جدید **کنار** تب‌های فعلی: عمق بازار مستقل، رویدادهای شرکتی ساخت‌یافته، صندوق‌های دارنده، بک‌تست، ML
- **(ج)** بازطراحی کامل به نقشه سند (❌ ناقض اصل حاکم — از دامنه خارج است)

**پیشنهاد:** گزینه (ب) با حفظ کامل تب‌های فعلی.
#### Tab 1 — نمای کلی
**الزام سند:** قیمت پایانی/آخرین، درصد تغییر، حجم، ارزش معاملات، تعداد معاملات، وضعیت نماد (باز/متوقف/مسدود)، خلاصه اطلاعات بنیادی، خلاصه صندوق‌های دارنده (۳ صندوق برتر).

 **واقعیت کد — هر قلم از کجا می‌آید:**

| قلم | منبع واقعی |
|---|---|
| قیمت پایانی/آخرین | `stock_live_tape.{close_price,last_price}` (`models/stock_enterprise.py:40-41`) یا `brsapi_symbol_snapshots.{price_close,price_last}` |
| درصد تغییر | `stock_live_tape.{price_change_pct,close_change_pct}` |
| حجم معاملات | `stock_live_tape.trade_volume` (BIGINT) |
| ارزش معاملات | `stock_live_tape.trade_value` |
| تعداد معاملات | `stock_live_tape.trade_count` (BIGINT) |
| **وضعیت نماد (باز/متوقف/مسدود)** | ✅ ستون اختصاصی: `symbols.trading_state VARCHAR(30)` با مقادیر `allowed\|forbidden\|suspended\|auction` (افزودنی `0052:30`) |
| خلاصه اطلاعات بنیادی | `symbols.{eps,pe,total_shares,base_volume}` + `symbols.{free_float_pct,industry_name}` (`0052`) + `brsapi_symbol_snapshots.{market_value,eps,pe_ratio,sector,shares_count}` |
| خلاصه ۳ صندوق برتر |  **یافت نشد** — داده موجود (`fund_holdings.weight_pct`) ولی endpoint نیست |
| API فعلی | `GET /api/v1/stocks/v2/{symbol}/tape` (tape + matrix + freshness) · `GET /api/v1/stocks/v2/{symbol}/signal` |

#### Tab 2 — نمودار قیمت و تحلیل تکنیکال
**الزام سند:** Candlestick با تایم‌فریم روزانه/هفتگی/ماهانه، زوم/پن، اندیکاتورهای SMA/EMA/RSI/MACD/Bollinger، نمودار حجم هم‌راستا.

📸 **واقعیت کد:**

| قلم | وضعیت |
|---|---|
| داده Candlestick | ✅ `brsapi_candlesticks` — `open/high/low/close/volume/count` + `candle_type` + `gregorian_date` + `shamsi_date` · جایگزین: `brsapi_historical_daily` (سری روزانه) · legacy: `candlesticks` (hypertable) |
| API نمودار | ✅ `GET /api/v1/stocks/v2/{symbol}/history` و `/history/export.csv` (CSV) |
| کتابخانه فرانت کندل | ✅ **`lightweight-charts@^5.2.0`** نصب است (`frontend/package.json:17`) |
| تایم‌فریم روزانه/هفتگی/ماهانه | 🔴 **پارامتر تایم‌فریم در endpoint سند** (`?range=`) یافت نشد؛ تبدیل سمت کلاینت یا افزودنی لازم است |
| زوم/پن | ✅ **در lightweight-charts بومی است** (`lightweight-charts` زوم/پن داخلی دارد) — نیاز به کد اضافی نیست |
| SMA | ⚠️ تابع مستقل `SMA` ❓ یافت نشد — با `pandas.rolling` محلی محاسبه می‌شود؛ پارامتر پیش‌فرض `INDICATOR_SMA_SPAN=20` (`core/config/indicators.py:11`) |
| EMA | ✅ `ema_20/50/100/200` در `stock_indicators_snapshot` + `ema_cross` |
| RSI | ✅ `rsi_14` + `rsi_divergence` (`RD+\|RD-\|HD+\|HD-`) |
| MACD | ✅ `macd`, `macd_signal`, `macd_hist` |
| Bollinger Bands | ✅ `bb_upper`, `bb_middle`, `bb_lower`, `bb_squeeze` + `keltner_*` |
| اندیکاتورهای اضافه (خارج سند) | ✅ Ichimoku (`ichimoku_tenkan/kijun/senkou_a/senkou_b/state`), ATR-14, MFI-14, VWAP, Pivots ×۳, `trend_alignment_score` |
| API اندیکاتور | ✅ `GET /api/v1/stocks/v2/{symbol}/indicators` |
| «افزودن اندیکاتور» تعاملی (Dropdown چندانتخابی) | 🔴  یافت نشد — کامپوننت `IndicatorSelector` سند (§۱۶) وجود ندارد |
| **Toggle «تعدیل‌شده/خام»** | ⚠️ داده‌اش هست (`candle_type` ۲/۳) ولی toggle سند ❓ یافت نشد |
| نمودار حجم هم‌راستا | ✅ داده (`volume`/`trade_volume`) موجود؛ کامپوننت حجم هم‌راستا ❓ یافت نشد |

📸 **هشدار مهم برای این تب:** داده تعدیل‌شده **از سرویس داده هم می‌آید** — ستون `candle_type` با مقادیر `1=realtime, 2=unadjusted, 3=adjusted` (`brsapi/models/tsetmc.py:502-504`). یعنی موتور تعدیل سند (§۵) هم می‌تواند محلی باشد و هم از داده آمادهٔ منبع تغذیه شود (🔴 تصمیم ۴).

#### Tab 3 — اطلاعات بنیادی
**الزام سند:** EPS (تحقق‌یافته و پیش‌بینی‌شده)، P/E، سرمایه ثبت‌شده، درصد سهام شناور آزاد، گروه صنعت، تاریخ آخرین تعدیل EPS.

📸 **نگاشت دقیق:**

| قلم سند | نام واقعی در کد | محل |
|---|---|---|
| EPS تحقق‌یافته | `eps_current` | `screener_profiles.eps_current` (`models/screener.py:39`) |
| EPS سال قبل | `eps_prev_year` | `screener_profiles.eps_prev_year` (`:40`) |
| EPS (عمومی) | `eps` | `symbols.eps` (Numeric) · `brsapi_symbol_snapshots.eps` (Float) |
| **EPS پیش‌بینی‌شده** | ❓ **یافت نشد** — ستون `eps_forecast` موجود نیست | — |
| P/E | `pe` / `pe_ratio` / `live_pe` | `symbols.pe`, `brsapi_symbol_snapshots.pe_ratio`, `screener_signals.live_pe`, `screener_signals.pe_ratio` |
| P/E صنعت | `industry_pe` | `screener_profiles.industry_pe` (`:55`) |
| سرمایه ثبت‌شده | `registered_capital` | `screener_profiles.registered_capital` (`:45`, میلیارد) |
| **درصد سهام شناور آزاد** | ⚠️ نام سند (`free_float_percentage`) ❓ یافت نشد. نام‌های واقعی: `free_float_pct` (DOUBLE) در `symbols` (افزودنی `0052:33`) · `free_float_shares` (BIGINT) در `screener_profiles` (`:36`) |  تصمیم ۱۱ |
| گروه صنعت | `industry` / `industry_id` (symbols) · `industry_name` (افزودنی 0052) · `sector`/`sector_id` (brsapi) · `industry`/`sub_industry` (screener_profiles) | ⚠️ **۴ نام موازی** |
| **تاریخ آخرین تعدیل EPS** |  **یافت نشد** — هیچ ستون تاریخ تعدیل EPS وجود ندارد | — |
| API فعلی | ✅ `GET /api/v1/fundamental/ratios/{symbol}`, `/dcf/{symbol}`, `/score/{symbol}`, `/industry/{industry}`, `GET /api/v1/stocks/v2/{symbol}/dossier` | — |
#### Tab 4 — عمق بازار
**الزام سند:** ۵ سطح قیمتی صف خرید و فروش، بهروزرسانی لحظه‌ای/نزدیک‌به‌لحظه‌ای در صورت وجود داده.

📸 **واقعیت کد — داده کامل موجود است، در ۴ مسیر موازی:**

| مسیر | شکل داده | نکته |
|---|---|---|
| `brsapi_symbol_snapshots` | **۴۵ ستون صریح**: `bid_count_1..5`, `bid_volume_1..5`, `bid_price_1..5` + `ask_count_1..5`, `ask_volume_1..5`, `ask_price_1..5` (`brsapi/models/tsetmc.py:90-122`) | ✅ **تنها منبعی که از سرویس واقعی پر می‌شود** — از `AllSymbols.php` |
| `stock_live_tape.buy_orders_json` / `.sell_orders_json` | `TEXT` (JSON) — snapshot زنده per symbol (PK `symbol`) | ✅ خواندنی سریع |
| `stock_order_book_l2` | `bids_json`/`asks_json` TEXT + `obi_5` + `bid_queue_value` + `ask_queue_value` · UQ `(symbol, captured_at)` | ✅ ساخت‌یافته‌ترین + شاخص OBI |
| legacy `orderbooks` / `orderbook_snapshots` | migration `0001` | ️ نویسنده فعال یافت نشد |
| **API** | ✅ `GET /api/v1/orderbooks/{symbol}` + `GET /api/v1/orderbooks/{symbol}/history` · سرویس: `services/orderbook_service.py` — docstring: «**No mock/hardcoded orderbook.** The 5-level bid/ask data comes directly from the AllSymbols snapshot» | ✅ |
| **به‌روزرسانی لحظه‌ای** | ⚠️ `SyncQuotesJob` هر **۲ دقیقه** (`apps/scheduler/app.py:74`) · `PROVIDER_TSETMC_WS_URL = None` (`core/config/providers.py:20`) · WS موجود: `/api/v1/ws/market` | 🔴 دانه‌بندی واقعی ≈ ۲ دقیقه (🔴 تصمیم ۹) |
| **تب مستقل در فرانت** |  **یافت نشد** — عمق بازار فعلاً داخل تب ۱ (تابلو) است | نیاز به تب جدید افزودنی |
| **کامپوننت `OrderBookDepthView`** (سند §۱۶) | 🔴 **یافت نشد** | باید ساخته شود |
| ⚠️ fixture تست | `tests/fixtures/sample_orderbooks.py` فقط **۳ سطح** دارد (نه ۵) | تست ۵ سطح باید نوشته شود |

#### Tab 5 — رویدادهای شرکتی (کدال)
**الزام سند:** جدول زمانی افزایش سرمایه (نوع: سود انباشته/آورده نقدی/سلب حق تقدم)، برگزاری مجمع (نوع و تاریخ)، تعدیل EPS (جدید vs قبلی). این رویدادها منبع اصلی موتور تعدیل قیمت (§۵).

📸 **واقعیت کد — خام موجود، ساخت‌یافته نه:**

| قلم | وضعیت |
|---|---|
| منبع داده | ✅ `brsapi_codal_announcements` (`brsapi/models/codal.py:17-53`) — `symbol`, `company_name`, `title`, `code`, `date_title`, `date_send`, `time_send`, `date_publish` (VARCHAR(20)), `time_publish`, `link`, `link_pdf`, `link_excel`, `link_attachment`, `audit_status`, `content_hash` (UQ) |
| منبع دوم | ✅ CODAL مستقیم (`PROVIDER_CODAL_BASE_URL`) — `providers/reference/codal/*` (parser, statement_parser, attachment_extractor) |
| **`action_type`** (`capital_increase` / `general_assembly` / `eps_adjustment`) |  **یافت نشد** — استخراج ساخت‌یافته از عنوان اعلامیه لازم است |
| **نوع افزایش سرمایه** (سود انباشته/آورده نقدی/سلب حق تقدم) |  **یافت نشد** — اما `screener_profiles.capital_increase_type` (`models/screener.py:50`) و `capital_increase_pct` (`:51`) وجود دارند (⚠️ خاستگاه پر‌کردنشان تأیید نشد) |
| **`price_adjustment_factor`** | ❓ **یافت نشد** در هیچ ستونی |
| **جدول `stock_corporate_actions`** |  **یافت نشد** — باید ساخته شود |
| `stock_codal_filings` |  **یافت نشد** (ادعاشده در `docs/stock-enterprise-architecture.md:11`) |
| API | ⚠️ `GET /api/v1/stocks/v2/{symbol}/codal` + `GET /api/v1/codal/*` (شامل `major_holders`) |
| ❓ `GET /api/stocks/:symbol/corporate-actions` |  یافت نشد |
| تب فرانت | 🔶 تب ۵ (کدال) موجود است — ولی نمایش **اعلامیه متنی**، نه جدول زمانی رویداد ساخت‌یافته |

### ✅ خبر مهم (تأییدکننده نکته کلیدی سند)
منطق تعدیل قیمت **از قبل در کدبیس هست**، فقط وصل نیست:
- `backtesting/corporate_actions.py` → `class CorporateActionAdjuster` با `adjust_prices(prices, actions)` و `adjust_volume(volume, action)`
- `domain/market_data/corporate_action.py` → entity `CorporateAction` با `ActionType`, `ratio`, `adjustment_factor`, `date`
- `backtesting/engine/replay_engine.py:183-187` → از `p.get("adjustment_factor", 1.0)` استفاده می‌کند
❓ **تست واحد برای آن وجود ندارد** (سند §۱۷ می‌خواهد ≥۳ سناریو) — باید از صفر نوشته شود.
#### Tab 6 — صندوق‌های دارنده این سهم
**الزام سند:** این تب **کد را از تب «رصد سهام در صندوق‌ها» در ماژول صندوقها بازاستفاده می‌کند** (endpoint `GET /api/stocks/:symbol/fund-holders` که در سند صندوق‌ها تعریف شد) — بدون بازنویسی منطق تکراری. فقط یک نمای فشرده + لینک «مشاهده کامل».

📸 **واقعیت کد — داده هست، endpoint/تب نیست:**

| قلم | وضعیت |
|---|---|
| جدول داده | ✅ `fund_holdings` — `instrument_symbol VARCHAR(50)`, `instrument_name VARCHAR(200)`, `instrument_isin VARCHAR(20)`, `holding_type VARCHAR(30)`, `quantity`, `book_value`, `market_value`, **`weight_pct`**, `period_end_date` (`models/fund_enterprise.py:105-130`) · UQ `(fund_id, period_end_date, holding_type, instrument_symbol)` |
| تغییرات وزنی (ورود/خروج پول) | ✅ `fund_portfolio_diffs.instrument_symbol` (`models/fund_enterprise.py:133-`) |
| هویت صندوق | ✅ `fund_symbol_aliases` (`fund_id`, `symbol`, `isin`, `national_id`) — کلید کانونی ISIN/national_id |
| `GET /api/stocks/:symbol/fund-holders` |  **یافت نشد** — فقط جهت معکوس موجود: `GET /api/v1/funds/v2/{fund_id}/holdings` (`apps/api/endpoints/funds_v2.py:206`) |
| API «نمای فشرده» |  **یافت نشد** |
| فرانت |  **یافت نشد** (نه تب، نه wrapper) |

✅ **موارد لازم برای ساخت (بدون کد تکراری):** یک query جدید `WHERE instrument_symbol = :symbol OR instrument_isin = :isin ORDER BY weight_pct DESC` روی جدول موجود + یک کامپوننت wrapper. **جدول جدید لازم نیست.** (🔴 تصمیم ۱۷)

#### Tab 7 — اخبار مرتبط
**الزام سند:** فراخوانی endpoint اخبار با فیلتر تگ نماد (طبق سند ماژول اخبار). نمایش ۵ خبر اخیر + لینک «همه اخبار این نماد».

 **واقعیت کد — کاملاً آماده و بازاستفاده‌شدنی:**

| قلم | واقعیت |
|---|---|
| endpoint فیلتر تگ نماد | ✅ `GET /api/v1/news/symbol/{symbol}` (`apps/api/endpoints/news.py`) — **دقیقاً همان چیزی که سند می‌خواهد** |
| endpoint دوم | ✅ `GET /api/v1/stocks/v2/{symbol}/news` (`stocks_v2.py`) |
| جدول نمادمحور با ایندکس زمانی | ✅ `stock_news_sentiment` با Index `ix_news_symbol_pub (symbol, published_at)` (`models/stock_enterprise.py:172-174`) — شامل `sentiment`, `sentiment_score`, `impact_tag` |
| جدول موازی | `news_articles` — تگ‌ها در ستون `symbols` به‌صورت CSV (`TEXT`)؛ `published_at` آن **`String(40)`** است (⚠️ نه TIMESTAMP — `docs/NEWS_MODULE_SPEC_FILLED_2026-09-16.md:57`) |
| فرانت | ✅ تب ۶ فعلی (`StockIntelligencePanel.tsx`) + صفحه `/news` · 🔴 صفحه اختصاصی خبر یافت نشد |
| لینک «همه اخبار این نماد» | 🔴 یافت نشد — صفحه `/news` فیلتر نماد ندارد |

📸 **همگرایی با ماژول اخبار:** `docs/NEWS_MODULE_SPEC_FILLED_2026-09-16.md:43` تأیید می‌کند «لینک تگ نماد می‌تواند به روت موجود `/symbol/{symbol}` یا `/stocks/v2/{symbol}/dossier` وصل شود» — پس این اتصال دوطرفه **طراحی‌شده و تأییدشده** است.
#### Tab 8 — بک‌تست استراتژی معاملاتی
**الزام سند:** مشابه بک‌تست صندوق‌ها اما روی قیمت سهم: DCA، Buy & Hold، خرید در RSI زیر X / فروش در RSI بالای Y. خروجی: نمودار رشد سرمایه، CAGR، Max Drawdown. هشدار «داده گذشته» همیشه‌نمایان.

 **واقعیت کد — زیرساخت کامل و فراوان، فقط به تب نماد وصل نیست:**

| قلم | واقعیت |
|---|---|
| موتور بک‌تست | ✅ `backtesting/` — `engine/{vectorized_engine, simulator, replay_engine, event_builder, run_manifest}`, `composer/indicator_registry`, `costs/apply_costs`, `optimization/monte_carlo`, `metrics/{trade_metrics, risk_metrics}`, `market/rule_versioning`, `reporting/{summary_report, html_report}` |
| سرویس | ✅ `services/backtest_service.py` (شامل `strategy_type == "ml_signal"` در `:164`), `backtest_framework.py`, `signal_backtest_engine.py`, `event_backtest.py` |
| API | ✅ `POST /api/v1/backtests/run` + **۳۰ route دیگر** (runs, strategies, compare, generate, scan-indicators, walk-forward, monte-carlo, portfolio-run, cascade/*, adaptive/*) |
| جدول | ✅ `backtest_runs` (`models/backtest.py`) — شامل `strategy_type`, `parameters`, `start_date`, `end_date`, `result_summary`, `created_by` |
| **استراتژی DCA** | ❓ در این کاوش تأیید نشد (نیاز به بررسی دستی `backtesting/composer/`) — نمونه فرانت موجود: `/gold/dca` |
| **Buy & Hold** | ❓ در این کاوش تأیید نشد |
| **RSI<X / RSI>Y** | ✅ زیرساخت آماده (`stock_indicators_snapshot.rsi_14` + `backtesting/composer/indicator_registry.py`) |
| Max Drawdown | ✅ `backtesting/metrics/risk_metrics.py` · `build_symbol_reports.py:486-488` (`peak`/`dd`) |
| CAGR | ⚠️ نام دقیق در کد: `annualized_return_pct` (`frontend/src/app/backtest/page.tsx:38`, `schemas/backtest/metrics.py`) — «CAGR» ❓ یافت نشد |
| هشدار «داده گذشته» همیشه‌نمایان | ✅ مفهوم موجود: `docs/BACKTESTING_README.md` + «داده سینتتیک» در `services/backtest_service.py:167` («always False since we fail if no real data found») |
| **فرانت: تب بک‌تست داخل صفحه نماد** | 🔴 **یافت نشد** — صفحه `/backtest` مستقل موجود است (با `/backtest/monte-carlo`), ولی داخل ۹ تب نماد نیست |
| **`<CandlestickChart />` reusable** (سند §۱۶) | 🔴 یافت نشد به‌عنوان کامپوننت مشترک |

#### Tab 9 — پیش‌بینی و ML
**الزام سند:** پیش‌بینی روند کوتاه‌مدت قیمت با **بازه اطمینان** + **دقت تاریخی مدل**؛ هرگز توصیه قطعی معاملاتی framing نشود.

📸 **واقعیت کد:**

| قلم | وضعیت |
|---|---|
| جدول‌های ML | ✅ `models/ml.py` → `ml_predictions` (ستون `prediction_date` تأیید شد) · `ml_models` (۳۵۹ ردیف) · `ml_model_versions` (۶۳۸) · `ml_training_runs` (۶٬۰۷۸) · `ml_symbol_results` · `ml_engineered_features` (طبق `docs/DATABASE_README.md:150-151`) |
| پکیج ML | ✅ `ml/` (`models/`, `datasets/loaders.py`, registry) + `ml_artifacts/` + `train_all_models_results.json` |
| API | ✅ `GET /api/v1/ml/models`, `/ml/runs`, `/ml/runs/{run_id}`, `POST /ml/predict/{model_id}`, `POST /ml/train` |
| موتور پیش‌بینی/آموزش | ✅ `services/{training_service, inference_service, ml_lifecycle_service, auto_retrain_pipeline, global_training_service, walk_forward_validator}.py` + `endpoints/forecast.py`, `forecast_engine.py` + `src/forecast_engine/`, `src/forecasting/` |
| **جدول `stock_ml_predictions`** |  **یافت نشد** |
| **`confidence_interval_low` / `confidence_interval_high`** | ❓ **یافت نشد** در هیچ جدول ML (فقط `backtesting/optimization/monte_carlo.py` `confidence_levels` دارد — سطح Monte Carlo، نه ستون ذخیره‌شده) |
| **`actual_close` برای سنجش دقت** |  **یافت نشد** در هیچ جدول |
| **`model_version`** | ✅ موجود: `ml_model_versions`, `decision_engine` (`run_id`, `model_version`) |
| **دقت تاریخی مدل** | ✅ فرآیند موجود: `services/{signal_accuracy_tracker, signal_performance_tracker, evaluation_suite}.py`, جدول `signal_accuracy`, `docs/accuracy-investigation-2026-08.md` |
| **تب ML در صفحه نماد** | 🔴 **یافت نشد** — صفحه `/predictions` و `/ml` مستقل موجود است |
| **«هرگز توصیه قطعی»** | ✅ الگوی موجود: `services/probability_calibrator.py` (احتمال کالیبره) + `decision_gate.py` + `signal_decision_engine.py` + `services/stock_read_through.py:estimate_fund_score_safe` |
| ❓ `GET /api/stocks/:symbol/ml-prediction` |  یافت نشد (🔴 تصمیم ۸) |

### ۱.۳. اسکرینر سهام (Stock Screener)
**الزام سند:** فیلتر ترکیبی روی P/E، بازده اخیر، حجم نسبت به میانگین، گروه صنعت، ارزش بازار، وضعیت نماد. نتیجه در جدول قابل مرتب‌سازی و export.

📸 **واقعیت کد — از سند جلوتر است:**

| فیلتر سند | ستون واقعی | محل |
|---|---|---|
| P/E | `live_pe`, `pe_ratio`, `industry_pe` | `models/screener.py:172-173`, `:55` |
| بازده اخیر | `current_price` + تاریخچه `daily_history` (`price_close_change_pct`, `price_last_change_pct`) | `models/screener.py:54`, `models/market_data.py:60-64` |
| حجم نسبت به میانگین | `volume_spike` (`models/screener.py:177`) · `avg_volume_50d` (migration `0031`) | ✅ |
| گروه صنعت | `industry`, `sub_industry` | `models/screener.py:34-35` |
| ارزش بازار | `market_value` در `brsapi_symbol_snapshots` · `total_shares × price` | — |
| وضعیت نماد | `symbols.trading_state` (`allowed\|forbidden\|suspended\|auction`) | افزودنی `0052:30` |
| مرتب‌سازی | ✅ `final_score`, `adjusted_score`, `raw_score`, ۹ نمره جزئی | `models/screener.py:182-190` |
| **Export** | ✅ نمونه موجود: `GET /api/v1/stocks/v2/{symbol}/history/export.csv` (`StreamingResponse` + `csv`) · کتابخانه `xlsx@^0.18.5` در فرانت | ✅ الگو موجود |
| مزیت اضافه | ✅ **مدل ۱۱۰ ستونی CANSLIM** (`screener_profiles`) + `screener_signals` با `stop_loss_price`, `position_size`, `decision`, `rule_50_30`, `outcome_correct` | — |
| API | ✅ `GET/POST /api/v1/screener/*` · `/screener/v2/*` · `/screener110/monitor` · `/scanner/*` · `/saved-filters/*` | — |
| فرانت | ✅ `/screener`, `/screener110`, `/smart-screener` | — |

🔴 `GET /api/v1/stocks/screener?peMax=&sector=&...` (شکل سند): **یافت نشد** — معادل واقعی `/api/v1/screener*`. (🔴 تصمیم ۷)
---

## بخش ۲. مدل داده بک‌اند

```sql
-- افزودنی؛ جداول موجود دست‌نخورده
```
📸 **وضعیت واقعی هر جدول پیشنهادی سند (کاوش کامیت `1bd0f9e`):**

| جدول سند | وضعیت در کدبیس | نزدیک‌ترین معادل موجود |
|---|---|---|
| `stock_ohlcv_daily` |  **یافت نشد** | `brsapi_candlesticks` (دارای `candle_type` 2=unadjusted/3=adjusted + `gregorian_date`) · `daily_history` (hypertable، **بدون `open`**) · `brsapi_historical_daily` · `candlesticks` (hypertable legacy) |
| `stock_fundamentals` |  **یافت نشد** | `symbols.{eps,pe,total_shares,free_float_pct,industry_name}` + `brsapi_symbol_snapshots.{shares_count,market_value,eps,pe_ratio,sector}` + `screener_profiles` (۱۱۰ ستون) |
| `stock_corporate_actions` |  **یافت نشد** | `brsapi_codal_announcements` (غیرساخت‌یافته) + `backtesting/corporate_actions.py` (فقط منطق، بدون ذخیره) |
| `order_book_snapshots` | ❓ **با این نام یافت نشد** | `stock_order_book_l2` (UQ `(symbol, captured_at)` + `obi_5`) · `stock_live_tape.{buy,sell}_orders_json` · `brsapi_symbol_snapshots` (۴۵ ستون صریح ۵ سطح) |
| `stock_ml_predictions` |  **یافت نشد** | `ml_predictions`/`ml_models`/`ml_model_versions`/`ml_symbol_results` (عمومی) |
| `stock_backtest_runs` |  **یافت نشد** | `backtest_runs` (`models/backtest.py`) — عمومی، با `strategy_type`/`parameters`/`result_summary` |
| `ingestion_quarantine_stocks` |  **یافت نشد** | `fund_ingestion_quarantine` (فقط صندوق‌ها — `models/fund_enterprise.py:211-224`) |
| `ingestion_run_logs` (سند §۱۹) |  **یافت نشد** | ✅ `job_runs` (`models/job_run.py`) — `job_type`, `status`, `progress_pct`, `started_at`, `completed_at`, `duration_seconds`, `error_message`, `result` |

🔴 **تصمیم ۲ — جدول `stock_ohlcv_daily`:** گزینه‌ها:
- **(الف)** ساخت جدول جدید مطابق سند + sync یک‌طرفه از `brsapi_candlesticks`/`daily_history` (سازگارترین با سند؛ هزینه: مسیر همگام‌سازی جدید)
- **(ب)** استفاده مستقیم از `brsapi_candlesticks` + افزودن فقط `adjusted_close` (کمترین کار — `candle_type` و `gregorian_date` را از قبل دارد)
- **(ج)** ساخت یک `VIEW` یکپارچه‌ساز روی منابع موجود (بدون جدول جدید، بدون داده تکراری)

🔴 **تصمیم ۳ — منبع واحد عمق بازار:** `stock_order_book_l2` (ساخت‌یافته‌ترین، `obi_5`) / `stock_live_tape` JSON / `brsapi_symbol_snapshots` (تنها منبعی که از سرویس واقعی پر می‌شود) / legacy
→ **پیشنهاد:** `stock_order_book_l2` مقصد (T2) و `brsapi_symbol_snapshots` منبع (T1).

### 📸 لایه Enterprise سهامی که **از قبل ساخته شده** (migration `0052`)

| جدول | کلید یگانه | نکته سند |
|---|---|---|
| `stock_live_tape` | PK `symbol VARCHAR(50)` (upsert) | اسنپ‌شات زنده + ۵ مظنه JSON |
| `stock_order_book_l2` | UQ `(symbol, captured_at)` | دفتر سفارشات L2 + OBI |
| `stock_indicators_snapshot` | PK `(symbol, trade_date)` | اندیکاتورهای پیش‌محاسبه شبانه |
| `stock_quant_signals` | UQ `(symbol, signal_date)` | تاریخچه سیگنال ۵لایه + مدیریت ریسک |
| `stock_news_sentiment` | Index `(symbol, published_at)` | اخبار + سنتیمنت NLP |
| `stock_monthly_sales_production` | UQ `(symbol, jalali_year, jalali_month, product_name)` | فروش ماهانه کدال MoM/YoY |
| `market_macro_indicators` | UQ `indicator_date` | دلار نیما/آزاد، اخزا، رژیم بازار |

➕ **ستون‌های افزودنی `0052` روی `symbols` (همه nullable):** `isin VARCHAR(20)`, `market_segment VARCHAR(30)`, `trading_state VARCHAR(30)`, `industry_name VARCHAR(100)`, `base_volume BIGINT`, `free_float_pct DOUBLE PRECISION`, `price_range_pct DOUBLE PRECISION`

### ⚠️ سه تناقض اسکیمایی که در کاوش تأیید شد

| # | تناقض | شواهد |
|---|---|---|
| ۱ | `symbols.symbol` → migration `VARCHAR(20)` ولی ORM `String(50)`؛ `symbols.industry` → migration `VARCHAR(200)` ولی ORM `String(100)` | `0001_initial_schema.py:23,28` vs `models/market_data.py:26,31` |
| ۲ | `ADD COLUMN isin` در `0052` تکراری است (`isin` در `0001:25` با `VARCHAR(50)` بود) | `0052_tse_stocks_enterprise.py:28` |
| ۳ | `stock_indicators_snapshot` هم PK دارد هم UQ روی همان دو ستون | `models/stock_enterprise.py:95,99-100` |

→ پیش از هر migration جدید در این ماژول، 🔴 تصمیم ۱۸: رفع این تناقض‌ها یا ثبت به‌عنوان بدهی پذیرفته‌شده.
---

## بخش ۳. بک‌اند — سرویس‌ها و اتصالات

### ۳.۱. منبع داده

**الزام سند:** `[پر کن — API رسمی TSETMC، ارائه‌دهنده واسط، یا وب‌سرویس فعلی پروژه]`. برای رویدادهای شرکتی، منبع کدال.

📸 **پاسخ قطعی از کد:**

| مورد | مقدار واقعی |
|---|---|
| **منبع اصلی قیمت/معاملات** | **BrsApi** — `BRSAPI_BASE_URL` (پیش‌فرض `https://Api.BrsApi.ir`) · کلاینت `brsapi/client.py` · تعریف endpointها `brsapi/config.py:50+` |
| Endpoint قیمت لحظه‌ای | `GET /Tsetmc/AllSymbols.php` (`brsapi/config.py:74-84`) · کامنت کد: `2 req / 100s` |
| Endpoint کندل | `GET /Tsetmc/Candlestick.php` (`:159-170`) · `2 req / 10s` |
| Endpoint تاریخچه | `GET /Tsetmc/History.php?type=0` (قیمت) و `?type=1` (حقیقی/حقوقی) (`:136-158`) · `4 req / 10s` |
| **TSETMC مستقیم** | ✅ موجود ولی محدود: `PROVIDER_TSETMC_BASE_URL` (پیش‌فرض `https://tsetmc.com`) · مصرف واقعی: `services/tsetmc_client.py:132` → `/Shareholder/GetInstrumentShareHolderLast/{ins_code}` |
| **رویدادهای شرکتی** | ✅ دو مسیر: (۱) BrsApi `GET /Codal/Announcement.php` (`:183-198`) (۲) CODAL مستقیم — `PROVIDER_CODAL_BASE_URL` (پیش‌فرض `https://codal.ir`) + `providers/reference/codal/*` |
| **سهمیه واقعی** | `brsapi/rate_limiter.py:42-43` → `DEFAULT_GLOBAL_DAILY_LIMIT = 4_000` · `DEFAULT_GLOBAL_5MIN_LIMIT = 1_000` · کامنت: «keeps a safety margin below the real-world plan cap (~5,000/day, above which the key gets blocked)» |
| **حالت اضطرار** | `brsapi/readiness.py` → «DB-only mode» وقتی کلید بلاک شود + `BrsApiReadyCheckJob` (هر ۱ ساعت) برای کشف بازگشت سرویس |
| محدودیت نرخ per-category | `BRSAPI_RATE_LIMIT_TSETMC/CODAL/IME/COMMODITY/CRYPTO` · کامنت `.env.example:157`: TSETMC ۳۰/min، CODAL ۲۰، IME ۱۵، Commodity ۱۵، Crypto ۱۵ |
| ⚠️ نقض سیاست | `ml/datasets/loaders.py:37` مستقیماً به `cdn.tsetmc.com/api/Instrument/GetInstrumentSearch` می‌زند — **خارج از کلاینت مرکزی و rate-limiter** (خطر بلاک شدن کلید) |

🔴 **تصمیم ۹/۱۵:** سهمیه ۴٬۰۰۰/روز برای backfill ۲-۳ ساله روی چند هزار نماد کافی نیست — نیاز به عدد واقعی پلن و اولویت‌بندی نمادها.

### ۳.۲. Real-time vs Snapshot

**الزام سند:** اگر داده لحظه‌ای (WebSocket) در دسترس است، معماری باید throttle داشته باشد (حداکثر هر ۲۵۰-۵۰۰ms رندر) تا مرورگر سنگین نشود؛ داده خام اما گم نشود.

📸 **واقعیت کد:**

| مورد | وضعیت |
|---|---|
| WebSocket API | ✅ `WS /api/v1/ws/market` (`apps/api/endpoints/websocket.py` — `@router.websocket("/market")`) + `WS /api/v1/ws/precompute` (`precompute_ws.py`) |
| زیرساخت WS | ✅ `providers/realtime/websocket/{base_ws_client, connection_manager, reconnect, subscriptions, parser, health}.py` — شامل reconnect و subscription management |
| جریان داده WS | ⚠️ **از BrsApi polling ۲ دقیقه‌ای تغذیه می‌شود** — `SyncQuotesJob` هر ۲ دقیقه (`apps/scheduler/app.py:74`) |
| WS TSETMC |  پیکربندی نشده: `PROVIDER_TSETMC_WS_URL = None` (`core/config/providers.py:20`) |
| فرانت WS | ✅ `frontend/src/hooks/useWebSocket.ts` موجود |
| throttle ۲۵۰-۵۰۰ms | 🔴 **یافت نشد** — و با دانه‌بندی ۲ دقیقه‌ای داده لازم هم نیست |
| **معماری فعلی جایگزین** | ✅ کش سه‌لایه در `services/stock_read_through.py`: L1 in-memory (TTL ۲-۵ ثانیه) → L2 Redis `stocks:tape:{symbol}` (SETEX) → DB `stock_live_tape` · Mutex توزیع‌شده SETNX+Lua روی `stock:{isin}:lock` · «برنده JIT از BrsApi، بازنده انتظار ≤۸s → خواندن DB» · TTL داینامیک (خارج بازار ۸ ساعت) — `docs/stock-enterprise-architecture.md:31-34,31-34` |
| فرانت refetch | ✅ تب ۱ با `refetchInterval: 5s` (`docs/stock-enterprise-architecture.md:91`) |
| **اصل «داده خام گم نشود»** | ✅ تأمین‌شده: `brsapi_symbol_snapshots.raw_json TEXT` + جدول `brsapi_raw_payloads` · متغیر `BRSAPI_RAW_PAYLOAD_SINK_ENABLED` |

🔴 **تصمیم ۹:** با سهمیه ۴٬۰۰۰/روز، polling زیر ۲ دقیقه عملاً غیرممکن است. گزینه‌ها: (الف) پذیرش ۲ دقیقه · (ب) پلن بالاتر BrsApi · (ج) منبع WS جدید (مثلاً `PROVIDER_TSETMC_WS_URL` اگر موجود باشد).
---

## بخش ۴. موتور اندیکاتور تکنیکال
```
توابع خالص و تست‌شده، مستقل از UI: SMA, EMA, RSI(14), MACD(12,26,9), Bollinger(20,2).
اگر کتابخانه استاندارد موجود است، از بازنویسی پرهیز شود؛ فقط wrapper تست‌شده.
```

📸 **واقعیت کد — نه یک موتور، بلکه ۷ پیاده‌سازی موازی (D4):**

| موتور | فایل | شکل |
|---|---|---|
| ۱. موتور تکنیکال سهام | `services/stock_technical_engine.py` | `rsi(closes, period=14)` + `sma`/`ema` محلی (تغذیه `stock_indicators_snapshot`) |
| ۲. سرویس اندیکاتور عمومی | `services/market_service.py` (`compute_indicator`) + `core/indicators.py` (`compute_rsi` — «Wilder's smoothing (industry standard)») | تست‌شده: `tests/unit/services/test_all_services.py:99` (`TestMarketServiceIndicators`), `test_market_service.py:225` |
| ۳. کلاس TechnicalIndicators | `services/stock_assistant_service.py:26` | `@staticmethod rsi/prices...` (پیاده‌سازی سوم) |
| ۴. Pipeline اندیکاتور BrsApi | `brsapi/pipelines/indicators.py:6` (`IndicatorPipeline.rsi` — `period=14`) | پیاده‌سازی چهارم |
| ۵. رجیستری بک‌تست | `backtesting/composer/indicator_registry.py` + `backtesting/engine/vectorized_engine.py:206` (`rsi_reversion_strategy`) | پنجم |
| ۶. Precompute شبانه | `services/indicator_precompute_service.py` + `jobs/definitions/enterprise_jobs.py` (`IndicatorPrecomputeJob`) → upsert به `stock_indicators_snapshot` | ⚠️ کندل را از `daily_history` می‌خواند که **ستون `open` ندارد** (🔴 تصمیم ۲) |
| ۷. محاسبات محلی پراکنده | `build_symbol_reports.py:356` (`series.ewm(span=n)`), `new_reports/analytics.py:23` (`rsi_wilder`), `services/market_data_service.py` (pandas rolling) | ششم/هفتم |

### 📸 نگاشت الزامات سند

| الزام سند | وضعیت واقعی |
|---|---|
| SMA | ✅ `core/config/indicators.py:11` → `sma_span: int = 20` · ستون‌های snapshot: `sma_20_50_200` (سه بازه) · ❓ تابع مستقل `SMA(period)` عمومی یافت نشد — با `pandas.rolling` محلی |
| EMA | ✅ `ema_span: 12` (`:10`) · snapshot: `ema_20/50/100/200` + `ema_cross` |
| RSI(14) | ✅ `rsi_period: 14` (`:14`) — دقیقاً مطابق سند · snapshot: `rsi_14` + `rsi_divergence` (`RD+|RD-|HD+|HD-`) · ۳ پیاده‌سازی موازی (Wilder در `core/indicators.py`) |
| MACD(12,26,9) | ✅ `macd_fast: 12, macd_slow: 26, macd_signal: 9` (`:15-17`) — دقیقاً مطابق سند · snapshot: `macd`, `macd_signal`, `macd_hist` |
---

## بخش ۵. موتور تعدیل قیمت (Price Adjustment Engine)
```
مسئله: افزایش سرمایه/تقسیم سود → افت مصنوعی قیمت در نمودار.
راه‌حل: price_adjustment_factor در stock_corporate_actions؛ تابع خالص adjustHistoricalPrices؛
adjusted_close + close خام هر دو ذخیره؛ تست با ۳+ سناریوی واقعی.
```

📸 **واقعیت کد — منطق موجود است، داده و ذخیره‌سازی نه:**

| قلم سند | وضعیت واقعی |
|---|---|
| «تابع خالص adjustHistoricalPrices» | ✅ **وجود دارد**: `backtesting/corporate_actions.py` → `class CorporateActionAdjuster` با `adjust_prices(prices, actions)` و `adjust_volume(volume, action)` · Entity: `domain/market_data/corporate_action.py` → `CorporateAction` با `ActionType`, `ratio`, `adjustment_factor`, `date` · مصرف در `backtesting/engine/replay_engine.py:183-187` (`p.get("adjustment_factor", 1.0)`) |
| «جدول stock_corporate_actions» |  **یافت نشد** — باید ساخته شود (مطابق SQL بخش ۲ سند) |
| «price_adjustment_factor» |  **یافت نشد** در هیچ جدول · ⚠️ داده آمادهٔ منبع هست: `brsapi_candlesticks.candle_type` (`1=realtime, 2=unadjusted, 3=adjusted` — `brsapi/models/tsetmc.py:502-504`) |
| «ذخیره adjusted_close + close خام» | ⚠️ دو مسیر: (۱) سرویس داده BrsApi از قبل هر دو نوع را می‌فرستد (candle_type 2/3) — فقط در دو ردیف جدا؛ (۲) ذخیره هم‌ردیفی (`adjusted_close` کنار `close`) فقط در طرح `stock_ohlcv_daily` سند است |
| «تست ۳+ سناریو» | ❌ **تست واحد برای CorporateActionAdjuster یافت نشد** — باید نوشته شود (`tests/unit/` جای مناسب است؛ ۳۵۸ تست بک‌اند موجود) |
| اجرای محاسبه | 🔶 الگوی موجود: محاسبات شبانه در `IndicatorPrecomputeJob` — افزودن مرحله تعدیل به همین job کم‌ریسک‌ترین مسیر است |
| سنتز رویداد از کدال | 🔴 ساخت‌یافته نه — `brsapi_codal_announcements` فقط `title`/`link_pdf` دارد؛ استخراج `action_type`/درصد/تاریخ لازم است · `screener_profiles.capital_increase_type|capital_increase_pct` (`models/screener.py:50-51`) الگوی ستون‌ها را نشان می‌دهد |

🔴 **تصمیم ۴ (منبع تعدیل):** (الف) محاسبه محلی با موتور موجود از روی `stock_corporate_actions` (سازگار با سند) · (ب) مصرف مستقیم candle_type=3 از BrsApi (سریع‌تر، وابسته به منبع) · (ج) هر دو + مقایسه انحراف به‌عنوان QA داده (پیشنهاد — با بخش ۱۴ هم‌راستاست).

📸 **نکته اجرایی مهم:** فرمول‌های ضریب باید از منطق `CorporateActionAdjuster` فعلی برداشت شوند تا دو تعریف موازی از «تعدیل» شکل نگیرد (بدهی D4 تکرار نشود).

---

## بخش ۶. جزئیات بک‌تست
```
مشابه الگوی بک‌تست ماژول صندوق‌ها + استراتژی‌های اندیکاتوری (مثل RSI<30 خرید / RSI>70 فروش).
هشدار «داده گذشته» همیشه‌نمایان الزامی است.
```

📸 **واقعیت کد — زیرساخت بسیار قوی‌تر از سند؛ فقط اتصال به تب نماد ندارد:**

| قلم | واقعیت |
|---|---|
| موتور | ✅ `backtesting/engine/{vectorized_engine, simulator, replay_engine, event_builder, run_manifest}` + `costs/apply_costs` + `optimization/monte_carlo` + `metrics/{trade_metrics, risk_metrics}` + `market/rule_versioning` + `reporting/{summary_report, html_report}` |
| استراتژی اندیکاتوری RSI | ✅ `backtesting/engine/vectorized_engine.py:206` → `rsi_reversion_strategy(data, period=14, ...)` — دقیقاً همان «خرید RSI پایین/فروش RSI بالا» |
| سرویس‌ها | ✅ `backtest_service.py` (فرانت‌فیسing؛ `strategy_type == "ml_signal"` در `:164`), `backtest_framework.py`, `signal_backtest_engine.py`, `event_backtest.py`, `global_backtest_service.py` |
| API | ✅ `POST /api/v1/backtests/run` + ۳۰ route (compare, walk-forward, monte-carlo, portfolio-run, cascade/*, adaptive/*, scan-indicators) |
| جدول | ✅ `backtest_runs` (`models/backtest.py`) — `strategy_type`, `parameters`, `start/end_date`, `result_summary`, `created_by` (❓ جدول `stock_backtest_runs` جدید لازم نیست — 🔴 تصمیم ۶) |
| فرانت | ✅ `/backtest` + `/backtest/monte-carlo` (`annualized_return_pct` = معادل CAGR, `max_drawdown_pct`) |
| DCA / Buy&Hold | ❓ در این کاوش تأیید نشد — نمونه فرانت `/gold/dca` موجود؛ نیاز به بررسی `backtesting/composer/` |
| هشدار «داده گذشته» | ✅ سابقه: `docs/BACKTESTING_README.md` + سرویس «داده سینتتیک ندارد» (`backtest_service.py:167`) |
| **شکاف اصلی** | 🔴 تب بک‌تست داخل صفحه نماد (۱.۲-Tab8) و `<CandlestickChart/>` reusable یافت نشد |
| Bollinger(20,2) | ✅ `bollinger_period: 20, bollinger_std: 2.0` (`:12-13`) — دقیقاً مطابق سند · snapshot: `bb_upper/middle/lower` + `bb_squeeze` |
| مازاد بر سند | ✅ ATR(14), MFI(14), VWAP, Keltner, Pivots×۳, Ichimoku(۵ مؤلفه), `trend_alignment_score` |
| کتابخانه npm (technicalindicators) |  **نصب نیست** (`frontend/package.json` فقط `lightweight-charts`, `recharts`, `framer-motion`...) — محاسبه سمت بک‌اند است؛ 🔴 افزودن کتابخانه JS لازم نیست مگر محاسبه کلاینتی خواسته شود |
| «توابع خالص و تست‌شده» | ✅ تا حدی: تست‌های موجود `test_market_service.py` (SMA/Unknown raises), `test_monthly_sales_and_indicators.py:122` (`TestIndicatorSnapshotNoLookAhead` — «مقدار در روز T فقط به داده ≤T وابسته») — 🔴 تست مرجع (golden values) برای EMA/BB/MACD یافت نشد |

🔴 **تصمیم ۴ (کاوش):** موتور مرجع واحد انتخاب شود (پیشنهاد: `core/indicators.py` + `IndicatorSettings` به‌عنوان پیکربندی مرکزی؛ بقیه به آن delegate شوند) — بدون حذف پیاده‌سازی‌های فعلی (اصل افزودن).
---

## بخش ۷. جزئیات ML
```
مشابه الگوی ماژول صندوق‌ها (فاز۱ baseline → فاز۲ سری زمانی → فاز۳ پیشرفته) با ورودی‌های اضافه:
حجم معاملات، اخبار (sentiment)، تغییرات وزن صندوق‌ها. ذخیره model_version و actual_close الزامی.
```

📸 **واقعیت کد — زیرساخت ML از سند جلوتر است؛ ستون‌های حیاتی سند نداریم:**

| الزام سند | وضعیت واقعی |
|---|---|
| الگوی فازبندی | ✅ موجود و فراتر: `ml/` (registry, `datasets/loaders.py`, `models/`), `ml_artifacts/`, `train_all_models_results.json` · سرویس‌ها: `training_service`, `inference_service`, `ml_lifecycle_service`, `auto_retrain_pipeline`, `global_training_service`, `walk_forward_validator`, `feature_engineering_service`, `model_evaluation_service` |
| ورودی: حجم معاملات | ✅ `stock_live_tape.trade_volume`, `daily_history.volume`, `stock_indicators_snapshot.volume_*` |
| ورودی: اخبار/sentiment | ✅ `stock_news_sentiment` (`sentiment`, `sentiment_score`, `impact_tag`) — دقیقاً برای این طراحی شده |
| ورودی: تغییرات وزن صندوق‌ها | ✅ `fund_portfolio_diffs.instrument_symbol` (`models/fund_enterprise.py:133-`) — «استفاده متقابل ماژول‌ها» که سند خواسته، داده‌اش از قبل هست |
| **ذخیره model_version** | ✅ `ml_model_versions` + `decision_engine(run_id, model_version)` |
| **ذخیره actual_close (سنجش دقت)** |  **یافت نشد** — `ml_predictions` ستون `actual_close` ندارد (🔴 تصمیم ۸) |
| **بازه اطمینان (CI low/high)** |  **یافت نشد** (فقط Monte Carlo در بک‌تست `confidence_levels` دارد) |
| جدول `stock_ml_predictions` |  **یافت نشد** — گزینه‌ها: (الف) `ALTER TABLE ml_predictions ADD COLUMN symbol/symbol_scope/actual_close/confidence_*` (افزودنی، سازگار با اصل حاکم) · (ب) جدول جدا مطابق سند (🔴 تصمیم ۵) |
| API | ✅ `GET /api/v1/ml/models`, `/ml/runs[/{run_id}]`, `POST /ml/predict/{model_id}`, `POST /ml/train` + `forecast.py`, `forecast_engine.py` |
| سنجش دقت تاریخی | ✅ `signal_accuracy` جدول + `signal_accuracy_tracker.py`, `signal_performance_tracker.py`, `evaluation_suite.py`, `probability_calibrator.py`, `decision_gate.py` |
| endpoint نمادمحور | ❓ `GET /api/stocks/:symbol/ml-prediction` **یافت نشد** — لازم: یک route جدید که از `ml_predictions`/`stock_quant_signals` می‌خواند |

🔴 **تصمیم ۵:** جدول پیش‌بینی نمادمحور: افزودن ستون به `ml_predictions` (الف) یا جدول جدید `stock_ml_predictions` (ب). → پیشنهاد (الف) + view نمادمحور؛ هیچ جدول فعلی تغییر breaking نمی‌کند.

🔴 **تصمیم ۸:** نمایش ML در صفحه نماد: کارت سیگنال فعلی (`/stocks/v2/{symbol}/signal`) گسترش یابد یا تب ۹ جدید ساخته شود.

📸 **نکته خط‌لوله (بدهی D-ML):** `ml/datasets/loaders.py:37` مستقیماً به `cdn.tsetmc.com` می‌زند — خارج از rate-limiter BrsApi؛ قبل از backfill بزرگ باید به مسیر مرکزی منتقل شود (افزودنی: wrapper روی `brsapi/client.py`).

---

## بخش ۸. Roadmap پیشنهادی
**متن سند:** ۱) مدل داده OHLCV + اتصال منبع  ۲) موتور تعدیل  ۳) Tab نمودار + اندیکاتور  ۴) بنیادی + رویدادهای شرکتی  ۵) عمق بازار  ۶) اسکرینر  ۷) اتصال صندوق‌ها/اخبار  ۸) بک‌تست  ۹) ML

📸 **هم‌راستاسازی با واقعیت کد (چیزهایی که «فاز ۱» سند هستند، عملاً ساخته شده‌اند):**

| مرحله سند | وضعیت کد | باقی‌مانده واقعی |
|---|---|---|
| ۱. مدل داده OHLCV + اتصال منبع | ✅ ۴ فروشگاه OHLCV + BrsApi + scheduler فعال | 🔴 یکسان‌سازی منبع (تصمیم ۲) + رفع باگ‌های B1/B2 |
| ۲. موتور تعدیل | 🔶 منطق موجود (`CorporateActionAdjuster`)، داده نه | جدول `stock_corporate_actions` + سنتز از کدال + تست ۳ سناریو |
| ۳. Tab نمودار + اندیکاتور | ✅ ۹ تب + `lightweight-charts` + اندیکاتورها | تایم‌فریم/افزودن اندیکاتور تعاملی + toggle تعدیل (UI) |
| ۴. بنیادی + رویدادها | ✅ dossier + کدال + monthly_sales | ساخت‌یافته‌کردن رویدادها (Tab 5) |
| ۵. عمق بازار | ✅ داده ۵ سطح + L2 + OBI | تب مستقل + `OrderBookDepthView` |
| ۶. اسکرینر | ✅ **کامل** (CANSLIM ۱۱۰ ستونی + NLU + save فیلتر) | فقط نگاشت فیلترهای سند به `/screener/*` (تصمیم ۷) |
| ۷. اتصال صندوق‌ها/اخبار | ✅ اخبار کامل · 🔶 صندوق‌ها: داده هست، endpoint/تب نه | `GET /api/v1/stocks/v2/{symbol}/fund-holders` + wrapper فرانت |
| ۸. بک‌تست | ✅ موتور کامل + ۳۰ route | تب ۸ + استراتژی‌های DCA/Buy&Hold (تأیید/افزودن) |
| ۹. ML | ✅ خط‌لوله کامل + دقت‌سنجی | ستون‌های `actual_close`/CI + تب ۹ |

📸 **پیشنهاد ترتیب اجرا (کم‌ریسک به ریسک‌دار، همه افزودنی):**
1. رفع باگ‌های B1/B2 (`stocks_v2.py:466,478`) — مستقل از همه تصمیم‌ها
2. یکسان‌سازی منبع OHLCV (تصمیم ۲) + migration افزودنی اسکیمای mismatch (تصمیم ۱۸)
3. `stock_corporate_actions` + تعدیل (تصمیم ۴) + تست ۳ سناریو
4. `fund-holders` endpoint (کم‌هزینه‌ترین فیچر جدید — داده آماده)
5. تب عمق بازار + تب بک‌تست + تب ML (فرانت)
6. backfill تدریجی (تصمیم ۹) + مانیتورینگ کیفیت (بخش ۱۴)

---

## بخش ۹. سوالات باز — پاسخ داده‌شده با کاوش

| سوال سند | ✅ پاسخ از کد |
|---|---|
| منبع رسمی/مجاز داده لحظه‌ای چیست؟ محدودیت نرخ؟ | **BrsApi** (`https://Api.BrsApi.ir`) — سهمیه جهانی ۴٬۰۰۰/روز (حاشیه امن زیر سقف واقعی ~۵٬۰۰۰؛ `rate_limiter.py:42`)، ۵min: ۱٬۰۰۰، per-endpoint: AllSymbols ۲/۱۰۰s، Candlestick ۲/۱۰s، History ۴/۱۰s · fallback: DB-only mode (`brsapi/readiness.py`) + `BrsApiReadyCheckJob` هر ۱h · 🔴 سهمیه پلن واقعی باید از تیم تأیید شود (تصمیم ۹) |
| آیا داده عمق بازار در API فعلی هست؟ | ✅ **بله** — `AllSymbols.php` هر ۵ مظنه را در `brsapi_symbol_snapshots` می‌دهد (۴۵ ستون bid/ask با count/volume/price)؛ + `stock_order_book_l2` و `stock_live_tape.buy/sell_orders_json` · سرویس: `services/orderbook_service.py` («No mock/hardcoded orderbook») |
| backfill برای همه نمادها یا پرمعامله‌ها؟ | 🔴 تصمیم باز — محاسبه کاوش: AllSymbols ۲req/۱۰۰s ≈ ۷۲req/h ≈ ۱٬۰۰۰/روز فقط برای snapshot لحظه‌ای؛ Candlestick ۲req/10s برای ۲-۳ سال × چند هزار نماد در سهمیه ۴٬۰۰۰/روز جا نمی‌شود → **پرمعامله‌ها فاز ۱ + صف اولویت** (`job_runs` برای audit) عملی است؛ عدد نمادهای فاز ۱ از تیم (تصمیم ۱۵) |
---

## بخش ۱۰. Wireframe تب‌های کلیدی

### Tab 2 — نمودار و تحلیل تکنیکال
```
[هدر] نام نماد | آخرین قیمت | درصد تغییر | [دکمه افزودن به واچ‌لیست]
[نوار ابزار] تایم‌فریم | افزودن اندیکاتور (Dropdown چندانتخابی) | تعدیل‌شده/خام (toggle)
[نمودار Candlestick + اندیکاتورهای انتخابی]
[نمودار حجم زیر نمودار قیمت]
```

📸 **نگاشت wireframe به کد:**

| قلم wireframe | وضعیت |
|---|---|
| دکمه «افزودن به واچ‌لیست» | ✅ جدول `watchlist` + `GET/POST/DELETE /api/v1/watchlists/*` و `watchlist_items` · ⚠️ جدول خارج از Alembic ساخته می‌شود (`_ensure_table` — بدهی D12) |
| انتخاب تایم‌فریم | 🔴 پارامتر تایم‌فریم یافت نشد — با `lightweight-charts` تبدیل D/W/M سمت کلاینت ممکن است یا افزودن `?tf=` به `/history` (endpoint فعلی: `limit 1..2500` + `adjusted`) |
| Dropdown چندانتخابی اندیکاتور | 🔴 کامپوننت یافت نشد — فهرست اندیکاتورها آماده است (`IndicatorSettings` + ۲۵+ ستون snapshot) |
| toggle تعدیل‌شده/خام | ⚠️ **پارامتر هست، عمل نیست**: `GET /{symbol}/history` پارامتر `adjusted: bool = Query(default=False)` را می‌گیرد ولی فقط در پاسخ echo می‌شود؛ `svc._load_daily_candles(symbol, limit)` را بدون فیلتر صدا می‌زند (`apps/api/endpoints/stocks_v2.py:366-375`) → وابسته به تصمیم ۴ (بعد از موتور تعدیل وصل شود) |
| نمودار حجم هم‌راستا | ✅ داده موجود؛ کامپوننت ❓ یافت نشد — با `lightweight-charts` histogram سریع ساخته می‌شود |

### Tab 4 — عمق بازار
```
[دو ستون کنار هم] خرید: ۵ ردیف (تعداد|حجم|قیمت) از بالاترین · فروش: ۵ ردیف (قیمت|حجم|تعداد) از پایین‌ترین
[نوار میانی] آخرین قیمت + جهت (خرید/فروش) با رنگ
```

📸 **نگاشت به کد:** ستون‌ها عیناً موجودند — `bid_count_1..5/bid_volume_1..5/bid_price_1..5` و `ask_*` در `brsapi_symbol_snapshots` (`brsapi/models/tsetmc.py:90-122`) · نوار میانی: `price_last/price_change_pct` همان جدول · نوسان لحظه‌ای: refetch ۵s + `/api/v1/ws/market` · شاخص آماده: `stock_order_book_l2.obi_5` (نمایش «فشار خرید/فروش» پیشنهاد افزودنی) · ⚠️ fixture تست فقط ۳ سطح دارد (`tests/fixtures/sample_orderbooks.py`) — برای E2E تب باید ۵ سطح شود.

---

## بخش ۱۱. اسکیمای API (نمونه‌های کلیدی)

📸 **نگاشت ۱۰ route سند به واقعیت (نسخه‌بندی: همه زیر `/api/v1/...`):**

| سند | واقعیت کد | وضعیت |
|---|---|---|
| `GET /api/stocks/:symbol` | `GET /api/v1/stocks/v2/{symbol}/tape` (+`/dossier`) | 🔶 معادل عملی؛ شکل سند یافت نشد (تصمیم ۷) |
| `GET /api/stocks/:symbol/ohlcv?range=&adjusted=` | `GET /api/v1/stocks/v2/{symbol}/history` + `/history/export.csv` | 🔶 بدون `?range=`/`?adjusted=` (تصمیم ۲/۴) |
| `GET /api/stocks/:symbol/fundamentals` | `GET /api/v1/fundamental/ratios/{symbol}`, `/dcf/{symbol}`, `/score/{symbol}` | ✅ معادل |
| `GET /api/stocks/:symbol/corporate-actions` | ❌ **یافت نشد** | 🔴 پس از جدول `stock_corporate_actions` ساخته شود |
| `GET /api/stocks/:symbol/order-book` | `GET /api/v1/orderbooks/{symbol}` + `/history` | ✅ معادل |
| `GET /api/stocks/:symbol/fund-holders` | ❌ **یافت نشد** (فقط جهت معکوس: `/api/v1/funds/v2/{fund_id}/holdings`) | 🔴 ساده‌ترین افزودنی |
| `GET /api/stocks/:symbol/news` | ✅ `GET /api/v1/news/symbol/{symbol}` + `GET /api/v1/stocks/v2/{symbol}/news` | ✅ دقیقاً موجود |
| `POST /api/stocks/:symbol/backtest` | `POST /api/v1/backtests/run` (بدون scope نماد در URL — `symbol` در body) | ✅ معادل |
| `GET /api/stocks/:symbol/ml-prediction` | ❌ **یافت نشد** | 🔴 (تصمیم ۵/۸) |
| `GET /api/stocks/screener?peMax=&sector=` | `GET/POST /api/v1/screener/*`, `/screener/v2/*`, `/screener110/monitor` | ✅ قوی‌تر از سند |

📸 **JSON نمونه corporate-actions سند** → پیشنهاد پاسخ واقعی پس از ساخت جدول:
```json
{
  "stockSymbol": "فولاد",
  "actions": [{
    "type": "capital_increase",
    "date": "2024-05-01",
    "details": { "source": "retained_earnings", "percentage": 40 },
    "priceAdjustmentFactor": 0.714,
    "sourceUrl": "codal.ir/..." 
  }]
}
```
📈 ستون‌های پیشنهادی جدول دقیقاً با طرح سند (بخش ۲) سازگار است؛ تنها منبع پر‌کردن: پارس ساخت‌یافته از `brsapi_codal_announcements` (+ CODAL مستقیم).

---

## بخش ۱۲. نقش‌ها و پنل مدیریت

**سند:** همان الگوی صندوق‌ها (Viewer / Analyst / Admin / **ML Engineer**). پنل: مدیریت نمادهای پیگیری، وضعیت sync کدال + Re-sync، ویرایش دستی ضریب تعدیل با Audit Log.

📸 **واقعیت RBAC کد:**

| نقش سند | موجود در کد؟ |
|---|---|
| Viewer | ✅ `Role.VIEWER` |
| Analyst | ✅ `Role.ANALYST` |
| Admin | ✅ `Role.ADMIN` |
| **ML Engineer** | ❌ **یافت نشد** — نزدیک‌ترین: `Role.OPERATOR`, `Role.EDITOR` (🔴 تصمیم ۱۰: افزودن نقش جدید یا نگاشت به ADMIN/OPERATOR) |

📸 **اجزای پنل — نگاشت به کد:**

| قلم سند | واقعیت |
|---|---|
| مدیریت نمادهای پیگیری اولویت‌دار | 🔶 داده‌اش هست: `symbols.trading_state/market_segment` + `screener_profiles`؛ UI پنل اختصاصی یافت نشد |
| وضعیت آخرین sync کدال + Re-sync دستی | ✅ زیرساخت کامل: `SyncCodalJob` (هر ۶h — `apps/scheduler/app.py:75`) + `job_runs` (`job_type`, `status`, `progress_pct`, `error_message`) + الگوی job-run UI (`/job-runs`, `scripts/migration_report.py`) + `POST /api/v1/jobs/{job}/run` (اجرای دستی job از قبل ممکن است) |
| ویرایش دستی ضریب تعدیل + Audit Log | ⚠️ جدول ضریب وجود ندارد (پس UI هم نه)؛ الگوی Audit: `brsapi_raw_payloads`, `audit_logs`, `fund_ingestion_quarantine.reviewed` |

📸 **نکته فرانت:** هدر پنل ادمین از قبل «استفاده از RBAC» را نمایش می‌دهد (`frontend/src/app/admin/page.tsx`) — افزودن گزینه‌های این ماژول به همان صفحه، افزودنی است.
---

## بخش ۱۳. Backfill تاریخی
**سند:** حداقل ۲-۳ سال OHLCV روزانه برای نمادهای اولویت‌دار (برای SMA200 و بک‌تست معنادار). اجرای pilot روی ۵-۱۰ نماد قبل از اجرای کامل.

📸 **واقعیت کد — backfill از قبل وجود دارد و فعال است:**

| قلم | واقعیت |
|---|---|
| **Job بک‌فیل** | ✅ `BackfillHistoricalDataJob` — `trigger="cron", hour=2` (هر روز ۲ بامداد، `max_instances=1`) — `apps/scheduler/app.py:143-150` · کامنت کد: «Backfill historical data (daily, off-peak hours)» |
| سرویس‌های بک‌فیل | ✅ `BackfillJob` + `services/backfill_service.py` + `backfill_real_legal.py` · جدول‌های مقصد: `brsapi_historical_daily`, `brsapi_historical_real_legal`, `brsapi_candlesticks`, `brsapi_intraday_trades` |
| API بک‌فیل | ✅ `POST /api/v1/backfill/run` |
| Audit | ✅ `job_runs` + `jobs/` dispatcher |
| داده موجود (حجم فعلی) | 📊 طبق discovery: `brsapi_candlesticks` پرشده از Candlestick.php (۲req/10s) · `daily_history` hypertable · عمق واقعی تاریخ‌ها در DB چک شود (`SELECT symbol, MIN(date), MAX(date), COUNT(*) FROM brsapi_candlesticks GROUP BY symbol`) |
| **اسکریپت خارجی** | 📁 `z.py` (root) — backfiller مستقل با `DAILY_LIMIT = 10000` و API key هارد‌کد (`z.py:17`) · 🔴 **هشدار امنیتی/سیاستی**: کلید در کد commit شده + سقف ۱۰٬۰۰۰ با `rate_limiter.py` (۴٬۰۰۰) ناسازگار است → باید حذف/بازنویسی شود (تصمیم ۱۳) |

📸 **محاسبه سهمیه (کاوش، برای تصمیم ۹/۱۵):**

| کار | درخواست/روز برآورد |
|---|---|
| `SyncQuotesJob` (AllSymbols، ۲req/۱۰۰s، بازار ~۴.۵h) | ~۲۵۰-۳۰۰ |
| Candlestick.php برای ۱۰۰ نماد اولویت (۲req/10s) | ~۱۰۰ نماد × ~۸۶ req/day ≈ ۸٬۶۰۰ ❌ (باید batch/تناوب کمتر شود) |
| History.php برای بک‌فیل اولیه ۵-۱۰ نماد pilot | یک‌بار‌ه، شدنی |

→ **جمع‌بندی:** backfill تاریخیِ همه نمادها با پلن ۴-۵ هزار/روز شدنی نیست؛ سند درست می‌گوید: pilot ۵-۱۰ نماد + صف اولویت‌بندی + گسترش تدریجی.

🔴 **تصمیم ۱۵:** فهرست نمادهای اولویت فاز ۱ (سند پیشنهاد: ۵-۱۰ pilot؛ معیار پیشنهادی: بالاترین `market_value` در `brsapi_symbol_snapshots` + عضویت در `watchlist` کاربران).

🔴 **تصمیم ۱۳:** تکلیف `z.py` (کلید هاردکد + سقف ۱۰٬۰۰۰ ناسازگار): حذف، انتقال به `scripts/` با env-var، یا ادغام در `BackfillJob`.
