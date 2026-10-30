# دفتر قابلیت‌ها — فاز صفر

**مبنا:** routeهای مونت‌شده (`Router().setup()` و `app.routes`)، ۱۵۲ صفحه `page.tsx`، فایل‌های تست، و خواندن کد. تاریخ: 2026-10-26.
**تعریف وضعیت:**
- **تأییدشده** = پیاده‌سازی + تست خودکار مرتبط سبز در اجرای این ممیزی.
- **پیاده‌سازی‌شده/اعتبارسنجی محدود** = کد و تست وجود دارد اما انتهابه‌انتها با داده/سرویس واقعی تأیید نشد.
- **ناقص** = بخشی از مسیر یا داده موجود نیست.
- **دارای ایراد** = ایراد تأییدشده در رجیستری.
- **فقط مستند** = در docs/UI نام برده شده اما route/پیاده‌سازی ندارد.
- **خارج از دامنه** = عمداً ساخته نشده یا نباید فعال شود.
- **ناشناخته** = شاهد کافی نیست.

> «وجود endpoint» به‌تنهایی دلیل کارکرد نیست. ستون «شاهد» دقیقاً همان چیزی است که دیده شده.

---

## 1. جدول قابلیت‌ها

| ID | قابلیت | مسیرها / UI | شاهد تست/اجرا | وضعیت | ریسک | مالک |
|---|---|---|---|---|---|---|
| C-01 | احراز هویت JWT + refresh | `/auth/*` (۱۸ route)، `/auth/login`، `/auth/register` | `auth-context.test.tsx`، `silent-refresh.test.ts`، `middleware.test.ts` در ۵۸۳ تست فرانت | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۳ |
| C-02 | مجوزدهی نقش‌محور | `_require_user/_admin` در `router.py` | تست‌های auth API؛ بازبینی mount | پیاده‌سازی‌شده/اعتبارسنجی محدود | **بالا** (مسیر پول) | ۳ |
| C-03 | داده و اطلاعات نمادهای بورس تهران | `/stocks`, `/symbols`, `/symbol-search`, `/market-info` | ۷۷ فایل تست با ارجاع brsapi، `useMarketData.test.tsx` | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-04 | زنجیره اختیار معامله | `/options/live/chain/*`، صفحه `/options` (۶۳ خط + کامپوننت) | `LiveChainPanel.test.tsx`، ۱۶ فایل تست options | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-05 | قیمت‌گذاری Black-Scholes و Greeks | `domain/options/pricing.py`, `/options/*` | تست‌های `tests/unit/domain/test_black_scholes_pricing.py`؛ **بازتولید عددی مرجع در این ممیزی** | تأییدشده (به‌جز IV) | متوسط | ۱ |
| C-06 | نوسان ضمنی (IV) | `pricing.implied_volatility`, `/options/analytics` | تست round-trip؛ **ایراد T=0 بازتولید شد** | **دارای ایراد** (ISSUE-102) | بالا | ۱ |
| C-07 | مارجین اختیار (SEO/IME) | `/options/professional/margin`, `margin_engine.py` | تست‌های `test_margin_engine.py`؛ **ایراد covered call بازتولید شد** | **دارای ایراد** (ISSUE-101) | بالا | ۱ |
| C-08 | VaR/CVaR پرتفوی اختیار | `domain/options/var_calculator.py` | تست واحد موجود؛ **بدون مصرف‌کننده API** | پیاده‌سازی‌شده/اعتبارسنجی محدود + قرارداد مبهم | متوسط | ۱ |
| C-09 | بک‌تست استراتژی | `/backtests/*` (۳۳ route)، ۱۱ صفحه `/backtest/*` | ۳۳ فایل تست backtesting؛ اجرای unit سبز (به‌جز cutoff) | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-10 | هزینه‌های معاملات ایران | `backtesting/costs/iran_costs.py`, `engine/commission.py` | تست `test_cost_parity.py` در CI | تأییدشده (واحد) | متوسط | ۱ |
| C-11 | جلوگیری از lookahead در بک‌تست | `engine/simulator.py` (next_open)، `vectorized_engine._validate_no_lookahead` | بازبینی کد؛ تست‌های parity | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-12 | پیش‌بینی و ML | `/ml/*` (۱۲ route)، `/forecast*` | ۱۳ فایل تست ml؛ **اجرای کامل ml ممکن نشد** | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-13 | غربالگری و فیلتر | `/screener*`, `/scanner`, صفحههای screener | ۱۵ فایل تست با ارجاع | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۱ |
| C-14 | صندوق‌ها، NAV و انطباق | `/funds/*` (۸۴ route)، `/funds/*` UI | ۳۱ فایل تست funds | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-15 | کدال و صورت‌های مالی | `/codal*` (۶۳ route)، ۶ صفحه | ۲۰ فایل تست codal | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-16 | GoldDesk فاز ۰ (snapshot/score/bubble) | `/gold/snapshot`, `/gold/score`, ... | ۴۳۴ تست `tests/gold_desk` سبز | **تأییدشده** | متوسط | ۱ |
| C-17 | GoldDesk فاز ۱ (terminal/what-if) | `/gold/terminal`, `/gold/what-if`, UI `/gold/terminal` | ۷۰ تست phase1+2 سبز؛ mount guard | **تأییدشده** (fixture؛ DB واقعی محدود) | متوسط | ۱ |
| C-18 | GoldDesk فاز ۲ (پوشش بازار) | `/gold/tehran-board`, `/platforms`, `/returns-matrix`, `/fund-map` | ۲۹ تست phase2 | **تأییدشده با داده ناقص** (`NO_DATA` برای دو board) | متوسط | ۱ |
| C-19 | پورتفوی/معاملات طلا | `/gold/portfolio/*`, `/gold/trades` | تست‌های portfolio؛ **۲ تست fixture قرمز** (ISSUE-117) | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-20 | DCA و هشدار طلا | `/gold/dca/*`, `/gold/alerts/*` | تست‌های dca/alert | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۱ |
| C-21 | Black-76 و اختیار طلا | `/gold/options/*`, `services/gold/black76_engine.py` | تست `test_black76.py` | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-22 | GoldDesk SaaS (توکن scoped) | `/golddesk/*` (۳ route) | `test_golddesk_http.py` (۱۰ تست) | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۳ |
| C-23 | دریافت و همگام‌سازی BrsApi | `/brsapi/*` (۴۴ route)، `SyncService` | ۷۷ فایل تست با ارجاع؛ **۵ تست retry قرمز** | **دارای ایراد محیطی** (ISSUE-116/119) | **بالا** | ۱ |
| C-24 | jobها و پردازش پس‌زمینه | `/jobs/*`، `brsapi/jobs`, precompute | ۱۷ فایل تست jobs | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۱ |
| C-25 | هشدارها و سیگنال‌ها | `/alerts`, `/signals`, `/multi-market-signals` | ۱۶ فایل تست با ارجاع alerts | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۱ |
| C-26 | اخبار، تقویم اقتصادی، macro | `/news`, `/economic-calendar`, `/gold/macro` | ۵ فایل تست news | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۱ |
| C-27 | کریپتو، ارز، کالا | `/brsapi/crypto`, `/currency`, `/commodities`, UI مربوط | تست crypto و currency؛ ۱۵/۵ ارجاع | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۱ |
| C-28 | Decision Engine و paper trading | `/decision-engine` (۱۷)، `/paper-trading` (۷) | `test_paper_trading_*`, `test_p0_*` | پیاده‌سازی‌شده/اعتبارسنجی محدود | بالا | ۱ |
| C-29 | Tabdeal | `/tabdeal/*` (۲۰ route) | فقط `tests/test_all_pages.py` ارجاع دارد | **ناشناخته/کم‌تست** | متوسط | ۱ |
| C-30 | دستیار چت و گزارش‌های تحلیلی | `/chat`, `/assistant`, `/alpha`, `/anomalies` | `test_chat.py`، `AssistantRulesPanel.test.tsx` | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۱+۲ |
| C-31 | سلامت، متریک، مانیتورینگ | `/health`, `/monitoring`, `/metrics` | تست‌های health/monitoring | پیاده‌سازی‌شده/اعتبارسنجی محدود | متوسط | ۳ |
| C-32 | ادمین (jobs/tables/tests) | `/admin`, `/jobs`, `/tables`, `/tests` | `admin` تست محدود؛ mount با `_require_admin` | پیاده‌سازی‌شده/اعتبارسنجی محدود | **بالا** | ۳ |
| C-33 | اجرای خودکار معامله (auto-trade) | `src/gold_desk/auto_trade.py` | **هیچ مصرف‌کننده‌ای در `apps/api/src/services/jobs` ندارد** (`grep` بدون نتیجه)؛ فقط `tests/gold_desk/test_auto_trade.py` | **خارج از دامنه — فعال نیست** | **بالا در صورت اتصال** | ۳ |
| C-34 | ثبت سفارش/کیف پول/تحویل طلا | — | تست `test_phase2_routes_are_read_only_and_never_trade` | **خارج از دامنه** (عمداً ساخته نشده) | — | مالک محصول |

---

## 1.1. کارت جزئیات قابلیت‌های کلیدی

### C-03 — داده نمادهای بورس
- **هدف:** نمایش قیمت/حجم/تغییر و تاریخچه نمادها.
- **ورودی:** `brsapi_symbol_snapshots`, `brsapi_historical_daily`, `brsapi_candlesticks`.
- **خروجی:** قیمت، تغییر، حجم، ارزش، OHLC.
- **API:** `/api/v1/stocks/*`, `/api/v1/market/*`, `/api/v1/symbols/*`.
- **UI:** `/`, `/heatmap`, `/symbol/[symbol]`, `/symbol-details`.
- **تست:** ۳۸ فایل با ارجاع gold، ۱۴۸ با market، `useMarketData.test.tsx`.
- **معیار پذیرش:** داده قدیمی `DELAYED`؛ صفر/غایب `null`؛ بدون mock خاموش.

### C-04 — زنجیره اختیار
- **هدف:** نمایش call/put، IV، حجم/موقعیت باز.
- **ورودی:** `brsapi_option_snapshots`, `brsapi_ime_options`.
- **خروجی:** ردیف‌های زنجیره + liquidity.
- **API:** `/api/v1/options/live/chain/{underlying}`.
- **UI:** `/options` + `LiveChainPanel`.
- **تست:** `LiveChainPanel.test.tsx`, ۱۶ فایل options.
- **معیار پذیرش:** تغییر نماد سریع → پاسخ قدیمی داده جدید را بازنویسی نکند (تست‌شده با `signal`).

### C-07 — مارجین اختیار
- **هدف:** مارجین اولیه/نگهداری طبق ضرایب.
- **ورودی:** legs (نوع، جهت، strike، premium، contract_size، quantity).
- **خروجی:** `strategy_type`, initial/maintenance, net premium.
- **API:** `POST /api/v1/options/professional/margin`.
- **تست:** `test_margin_engine.py`؛ **ایراد covered call بازتولید شد**.
- **معیار پذیرش:** سهام ۱٬۰۰۰ + ۱۰ short call → مارجین > 0؛ ۱۰٬۰۰۰ سهم → 0.

### C-09 — بک‌تست
- **هدف:** ارزیابی استراتژی با هزینه، slippage و اجرای t+1.
- **ورودی:** OHLCV، سفارش، پیکربندی.
- **خروجی:** equity curve، معیارها، گزارش.
- **API:** `/api/v1/backtests/*` (۳۳ route)؛ UI ۱۱ صفحه.
- **تست:** ۳۳ فایل backtesting؛ parity هزینه در CI.
- **معیار پذیرش:** بدون lookahead، هزینه کامل، گزارش قابل بازتولید.

### C-14 — صندوق‌ها و NAV
- **هدف:** NAV، حباب اسمی، انطباق، دفتر.
- **ورودی:** `brsapi_nav_records`, `brsapi_ime_funds`.
- **خروجی:** NAV، premium، compliance.
- **API:** `/api/v1/funds/*` (۸۴ bucket)؛ UI `/funds/*`.
- **تست:** ۳۱ فایل.
- **معیار پذیرش:** NAV غایب → `null`، نه صفر؛ تاریخ جلالی درست.

### C-15 — کدال
- **هدف:** اطلاعیه، صورت مالی، تحلیل.
- **ورودی:** `brsapi_codal_announcements`, `brsapi_codal_attachments`.
- **API:** `/api/v1/codal*` (۶۳+ route در bucketهای codal/codal-professional)؛ UI ۶ صفحه.
- **تست:** ۲۰ فایل.
- **معیار پذیرش:** نگاشت فیلد و تاریخ سازگار؛ خطای منبع پنهان نشود.

### C-17/C-18 — Gold terminal و coverage
- **هدف:** میز داده طلا و پوشش بازار بدون سطح معامله.
- **ورودی:** BrsApi gold/currency/IME/NAV + `brsapi_gold_currency_pro_daily_history`.
- **خروجی:** `TerminalResponse`, `MarketCoverage` با `data_gaps` و `NO_DATA`.
- **API:** `/gold/terminal`, `/gold/what-if`, `/gold/tehran-board`, `/gold/platforms`, `/gold/returns-matrix`, `/gold/fund-map`.
- **UI:** `/gold/terminal`, `/gold/coverage`.
- **تست:** ۷۰ تست اختصاصی + ۴۳۴ تست کل gold.
- **معیار پذیرش:** ریال/تومان/دلار صریح؛ `orders/wallet/delivery=false`؛ هیچ `NaN/Infinity`.

### C-19 — پورتفوی طلا
- **هدف:** P&L، ارزش، DCA، معاملات.
- **ورودی:** `gold_holdings`, `gold_trades`, `gold_dca_plans`, `gold_portfolio_values`.
- **API:** `/gold/portfolio/*`, `/gold/trades`.
- **تست:** ۳۸ فایل با ارجاع portfolio؛ ۲ تست fixture قرمز (ISSUE-117).
- **معیار پذیرش:** قیمت غایب → `null` و `unpriced_holdings`؛ P&L فقط با قیمت معتبر.

### C-23 — همگام‌سازی BrsApi
- **هدف:** دریافت، dedup، upsert و ثبت وضعیت.
- **ورودی:** endpointهای BrsApi با rate limit.
- **خروجی:** ردیف در جدول‌های `brsapi_*` + `SyncReport`.
- **تست:** ۷۷ فایل با ارجاع؛ ۵ تست retry قرمز به‌دلیل cooldown.
- **معیار پذیرش:** بدون تماس شبکه در unit؛ dedup با params؛ upsert بدون تکرار.

---

## 2. قابلیت‌های ادعاشده که تأیید نشدند

| ادعا | واقعیت | وضعیت |
|---|---|---|
| `/gold/ticker` (docs/phase1-ticker-api.md) | ۰ route با ticker در ۱۰۳ مسیر gold | **فقط مستند** (ISSUE-104) |
| «۲۸+ عملیات GoldDesk» در سند قدیمی | کد ۱۰۳ مسیر gold دارد؛ سند به‌روزرسانی شده است | تأییدشده در PLAN_GOLD |
| «۱۵ صفحه طلا» | ۲۲ صفحه `page.tsx` زیر `app/gold` | شمارش واقعی |
| «همه قابلیت‌ها سالم» | ۹ تست قرمز baseline + ۲۰ ایراد | **رد می‌شود** |

---

## 3. قابلیت‌های ناشناخته (نیازمند بررسی فاز ۱/۵)

- Tabdeal (C-29): ۲۰ route و یک صفحه، بدون تست واحد اختصاصی.
- تحلیل‌های `alpha`/`anomalies`/`sentiment`: route و UI دارند، تست کم.
- کالا/IME: route و مدل دارند؛ کیفیت داده و اعتبار فرمول بررسی نشد.
- گزارش‌های `reports/`: خروجی تولید می‌شود اما صحت آن در این فاز سنجیده نشد.

---

## 4. جمع‌بندی

- **تأییدشده با تست سبز:** GoldDesk فاز ۰/۱/۲، Black-Scholes پایه، RSI/ATR/MACD، هزینه معاملات.
- **دارای ایراد تأییدشده:** IV، مارجین covered call، گیت اسرار، تست‌های BrsApi/portfolio.
- **ناقص/وابسته به داده:** دو board فاز ۲، بخشی از ML، Tabdeal.
- **خارج از دامنه:** auto-trade (غیرمتصل)، سفارش/کیف پول/تحویل طلا.
