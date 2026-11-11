# پاس Regression بصری — Portfolio / Silver / Gold tabs (پس از W6-03)

- تاریخ: 2026-10-31 09:15 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- هدف: بررسی اینکه انتقال reset به `@layer base` (W6-03) چیدمان صفحات Portfolio، Silver و تب‌های Gold را نشکسته باشد.
- مرورگر: Playwright headless، viewport **1440×900**، SW مسدود، فراخوانی‌های کند shell (enriched-heatmap / market-dashboard / news) abort شدند. برای Silver، hydration با polling تا ۶۰s صبر شد.
- هیچ کد محصولی در این پاس تغییر نکرد.

---

## ۱) روش و معیار

برای هر صفحه/تب:
- `scrollWidth` در برابر `innerWidth` (بدون overflow افقی)
- موقعیت/عرض `main` و `padding` محاسبه‌شده (اعمال utilityهای Tailwind)
- وجود heading/محتوا، تغییر تب فعال و marker محتوای همان تب (Portfolio/Silver)
- خطاهای API/console (برای تفکیک خطای داده از خطای چیدمان)

---

## ۲) Portfolio (`/gold/portfolio`)

| view | main | padding | overflow | محتوا |
|---|---|---|---|---|
| overview | x=80, w=1280 | `32px 24px` | 1440/1440 | تب فعال «نمای کلی» |
| ثبت خرید | x=80, w=1280 | `32px 24px` | 1440/1440 | heading «ثبت خرید جدید» |
| پلن‌های DCA | x=80, w=1280 | `32px 24px` | 1440/1440 | heading «ساخت پلن DCA» |
| تاریخچه | x=80, w=1280 | `32px 24px` | 1440/1440 | تب معاملات |
| overview دوباره | x=80, w=1280 | `32px 24px` | 1440/1440 | بازگشت به overview |

- هیچ API خطا/overflow دیده نشد.
- **مشاهده (نه regression):** با DB خالی، زیر تب‌ها ناحیهٔ محتوا خالی است؛ empty-state متنی در viewport دیده نشد. این رفتار به داده/حالت خالی مربوط است، نه W6-03.

---

## ۳) Silver (`/markets/silver`) — ۷ تب

| تب | active | marker محتوا | padding | overflow |
|---|---|---|---|---|
| نمای کلی | نمای کلی | overview | `32px 20px 80px` | 1440/1440 |
| پیش‌بینی | پیش‌بینی | ✅ | `32px 20px 80px` | 1440/1440 |
| صندوق‌ها | صندوق‌ها | ✅ | `32px 20px 80px` | 1440/1440 |
| آتی (IME) | آتی (IME) | ✅ | `32px 20px 80px` | 1440/1440 |
| بک‌تست | بک‌تست | ✅ | `32px 20px 80px` | 1440/1440 |
| هوش مصنوعی | هوش مصنوعی | ✅ | `32px 20px 80px` | 1440/1440 |
| اخبار | اخبار | ✅ | `32px 20px 80px` | 1440/1440 |

- hydration در ~۴s انجام شد؛ همهٔ تب‌ها محتوای اختصاصی خود را نشان دادند.
- داده‌ها به‌دلیل DB خالی `—`/empty هستند (مورد انتظار)؛ هیچ overflow یا جابه‌جایی دیده نشد.

---

## ۴) Gold tabs — ۱۵ صفحه (از ۱۸)

| صفحه | main | padding | overflow | heading/وضعیت |
|---|---|---|---|---|
| `/gold/health` | x=80, w=1280 | `32px 24px` | 1440/1440 | loading/health cards؛ چند خطای داده |
| `/gold/settings` | x=80, w=1280 | `32px 24px` | 1440/1440 | «وضعیت سیستم» |
| `/gold/etf` | x=80, w=1280 | `32px 24px` | 1440/1440 | «صندوق‌های طلا (ETF)» |
| `/gold/alerts` | x=80, w=1280 | `32px 24px` | 1440/1440 | «قوانین موجود» |
| `/gold/tokens` | x=80, w=1280 | `32px 24px` | 1440/1440 | «ساخت Token جدید» |
| `/gold/backtest` | x=80, w=1280 | `32px 24px` | 1440/1440 | «پارامترها» |
| `/gold/coverage` | x=80, w=1280 | `32px 24px` | 1440/1440 | «پوشش بازار طلا» |
| `/gold/terminal` | x=80, w=1280 | `32px 24px` | 1440/1440 | «میز داده و برابری طلا» |
| `/gold/analytics` | x=80, w=1280 | `32px 24px` | 1440/1440 | «تحلیل تاریخی» |
| `/gold/macro` | x=80, w=1280 | `32px 24px` | 1440/1440 | «کلان طلا» |
| `/gold/funds` | x=80, w=1280 | `32px 24px` | 1440/1440 | «صندوق‌های طلا» |
| `/gold/physical` | x=80, w=1280 | `32px 24px` | 1440/1440 | «بازار فیزیکی و آربیتراژ» |
| `/gold/chat` | x=80, w=1280 | `32px 24px` | 1440/1440 | پوسته چت |
| `/gold/antigravity` | x=80, w=1280 | `32px 24px` | 1440/1440 | «Antigravity — ماژول طلا» |
| `/gold/futures` | x=80, w=1280 | `32px 24px` | 1440/1440 | «آتی سکه (IME)» + 503 snapshot |

- همهٔ صفحات از پوستهٔ Gold با `max-w-7xl` (۱۲۸۰px) و padding صحیح استفاده می‌کنند؛ هیچ overflow افقی دیده نشد.
- خطاهای داده (503 snapshot، loading health، موارد coverage) متعلق به نبود داده/سرویس در محیط تست‌اند، نه regression چیدمان.
- **BLOCKED:** `/gold/options` و `/gold` (root) هنگام کامپایل، dev server را با OOM از کار انداختند؛ اسکرین‌شات/اندازه‌گیری ندارند. `/gold/portfolio` در بخش Portfolio بالا پوشش داده شد.

---

## ۵) نتیجه

- **PASS (چیدمان)** برای ۵ view پورتفوی + ۷ تب Silver + ۱۵ صفحه Gold: `scrollWidth == innerWidth`، `main` centered در layout خودش، paddingهای Tailwind اعمال شده، بدون نوار سفید/بریدگی.
- W6-03 هیچ regression چیدمانی در این ۲۷ view ایجاد نکرد.
- **PARTIAL** به‌دلیل `/gold/options` و `/gold` (OOM) و بررسی‌نشدن ۱۹۲۰px برای Gold/Silver (پاس ۱۴۴۰ انجام شد؛ داشبورد ۱۹۲۰ قبلاً تأیید شده بود).
- مشاهده‌های داده‌ای: پورتفوی خالی بدون empty-state متنی در viewport، و خطاهای 503/loading در چند صفحهٔ Gold — خارج از دامنهٔ W6-03.

---

## ۶) شاهدها و پاک‌سازی

- ۲۷ اسکرین‌شات: `audit_out/_tmp/regression/*.png`
- نتایج JSONL: `audit_out/_tmp/regression/pf_sv.jsonl`، `silver_hydrated.jsonl`، `gold.jsonl`
- کاربر تستی `audit_ui_regress_20261031` حذف شد؛ `users=0`؛ هیچ داده‌ای نوشته/حذف نشد.
- Frontend/API در پایان = 200؛ هیچ commit/stage انجام نشد.

---

## ۷) تصحیح مهم (2026-10-31 10:50) — 503/500ها misattribution بودند

بررسی fresh-context نشان داد:
- `/gold/futures` خودش هیچ درخواست `/gold/snapshot` نمی‌زند؛ 503 ثبت‌شده از **`/gold/antigravity`** (route قبلی در پاس ترتیبی) بود که پس از navigation کامل شد.
- `/gold/health` خودش 200 است و در بارگذاری تازه هیچ‌کدام از `brsapi/commodities|crypto|gold-coin|indices` را صدا نمی‌زند؛ 500های ثبت‌شده از route قبلی/in-flight بودند. (صفحه health در آن اجرا hydrate نشد؛ hyd=-1.)
- 503 واقعی فقط `/gold/snapshot` است: `snapshot_unavailable` چون «no complete price source available (BrsApi + TGJU both incomplete)»؛ TGJU 404 و DB خالی.
- 500های دیگر ریشه در schema drift دارند: دو جدول `brsapi_gold_currency_pro_prices` و `brsapi_gold_currency_pro_daily_history` وجود ندارند؛ ستون‌های `ins_id` در commodity/currency/gold_coin/crypto و `bid_volume_1` در ime_futures غایب‌اند.

جزئیات: `AUDIT_REPORTS/UI_503_FORENSICS_20261031_1050.md`.
