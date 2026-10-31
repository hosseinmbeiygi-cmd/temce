# تست دستی UI — موج ۴: ذخیره‌سازی (Portfolio / Alerts / Tokens)

- **تاریخ اجرا:** 2026-10-31، حدود 03:30 تا 04:15 (Asia/Tehran)
- **Branch:** `backup/db02-baseline-20261030` — **HEAD:** `54c6a6eb`
- **دامنه:** `/gold/portfolio` (افزودن holding، فروش، DCA create/execute/delete)، `/gold/alerts` (create/toggle/delete/seed/ack)، `/gold/tokens` (create/revoke/copy)
- **تغییرات کد محصول:** **هیچ.** فقط فایل‌های شاهد تست در `audit_out/_tmp/` و همین گزارش ایجاد شد.
- **کاربران تست:** `audit_ui_storage_20261031` (دو بار ساخته شد: `usr_c443b9d595154fa1adebc6b4` و `usr_4f65d5f2daa349a39fc0a9fd`) — هر دو پس از تأیید صفر بودن ردیف‌های وابسته حذف شدند.

---

## ۱) خلاصهٔ مدیریتی

- **Portfolio:** افزودن holding، ثبت فروش، ساخت/اجرای DCA و حذف DCA از UI کار می‌کنند و در UI/API/PostgreSQL یکسان‌اند و پس از refresh و خروج/ورود دوباره باقی می‌مانند.
- **Alerts:** ساخت، toggle، حذف، seed و ack از UI کار می‌کنند؛ ack در DB ثبت و پس از refresh/ورود دوباره پایدار است.
- **Tokens:** ساخت، کپی و revoke در لایهٔ ذخیره‌سازی (Redis) درست کار می‌کنند؛ token خام هرگز در Redis ذخیره نمی‌شود و پس از revoke هش حذف می‌شود.
- **اما سه نقص جدی تأیید شد:**
  1. **فروش، تعداد holding را کم نمی‌کند** (Critical, مالی): بعد از فروش ۱ از ۲، API/UI/DB همچنان ۲ نشان می‌دهند.
  2. **Tokenهای read/write/admin عملاً بی‌مصرف‌اند** (High): روی `/gold/snapshot` و `/golddesk/snapshot` و `/gold/metrics` همه ۴۰۱ می‌دهند؛ فقط scope `metrics` (که UI اصلاً ارائه نمی‌دهد) روی `/gold/metrics` کار می‌کند.
  3. **Service Worker طلا باعث حلقهٔ reload بی‌پایان در صفحات `/gold` می‌شود** (High): با SW فعال، reload صفحهٔ پورتفوی ۱۰۲ ناوبری در ۱۵ ثانیه و بدون hydration بود؛ با SW مسدود، دو ناوبری و hydration سالم.
- دو نقص متوسط دیگر: نمایش P&L به‌صورت «۰» وقتی هیچ دارایی قیمت‌دار نیست، و بی‌صدا no-op شدن «درج قوانین پیش‌فرض» وقتی کاربر حتی یک قانون دارد.

---

## ۲) وضعیت Git

- شروع/پایان: branch `backup/db02-baseline-20261030`، HEAD `54c6a6eb`.
- هیچ commit/stage/reset/stash/clean انجام نشد. فایل‌های کاربر دست نخوردند.
- فایل‌های جدید: `audit_out/_tmp/storage_wave4*.js|json`، `storage_wave4_followup*`، `storage_logout_test*`، `dca_delete_test*`، `gold_reload_diag.js`، `gold_sw_cache_diag.js`، و همین گزارش.

---

## ۳) محیط و روش

| مورد | مقدار |
|---|---|
| API | `scripts/ui_test_server.py` روی `127.0.0.1:8000` (بدون lifespan تولیدی) |
| DB | `tse_timescaledb` / `15432` / `tse_quant_verify` / Alembic `0120` |
| Redis | `tse_redis` / `16379` (رمز فقط از `docker inspect` خوانده و چاپ نشد) |
| Frontend | Next dev روی `127.0.0.1:3000` |
| مرورگر | Playwright 1.64.1 + Chromium 1248 محلی |
| کاربر | اولین کاربر DB → نقش `admin` (بوت‌استرپ) |
| جداسازی | `serviceWorkers: 'block'` + abort فراخوانی‌های بازار/خبر/ارز shell تا hydration صفحه‌های ذخیره‌سازی مختل نشود |
| داده | نام/نماد/یادداشت با پیشوند `AUD-UI-`؛ هیچ داده واقعی تغییر نکرد |

**دربارهٔ ابطال فراخوانی‌های shell:** فقط `/api/v1/market/**`، `/api/v1/market-dashboard`، `/api/v1/news**`، `/api/v1/economic-calendar**` و `/api/v1/brsapi/**` مسدود شدند؛ این‌ها به صفحه‌های Portfolio/Alerts/Tokens ربطی ندارند و در محیط تست کند/خراب بودند. خطاهای `net::ERR_FAILED` در کنسول از همین ابطال‌های عمدی است، نه خطای صفحه.

---

## ۴) ماتریس تست

| سناریو | UI | API | DB | refresh | خروج/ورود دوباره | حکم |
|---|---|---|---|---|---|---|
| افزودن holding | ردیف با نام/تعداد 2.00 | `GET /gold/portfolio` → qty 2 | `gold_holdings.id=7`، qty 2، مبلغ 100M، fee 0.5% | ✅ 2.00 | ✅ 2.00 | **PASS** |
| فروش ۱ از ۲ | trade در تاریخچه | trade id 5، qty 1، مبلغ 55M، PnL 5M | `gold_trades.id=5` مطابق | ✅ (اما qty 2.00) | ✅ qty 2.00 | **FAIL (W4-01)** |
| DCA create | کارت پلن | `plan_id=2` | `gold_dca_plans.id=2` | ✅ | ✅ 1/3 | **PASS** |
| DCA execute | «1/3» | executed=1 | executed_tranches=1 | ✅ | ✅ | **PASS** |
| DCA delete (UI) | کارت حذف شد | از API حذف شد | count=0 | — | — | **PASS** |
| Alert create | کارت قانون | `id=2` | `gold_alert_rules.id=2` | ✅ | ✅ | **PASS** |
| Alert toggle | فعال↔غیرفعال | enabled false→true | — | — | — | **PASS** |
| Alert seed (با ۱ قانون موجود) | هیچ تغییری | inserted=0 | تعداد بدون تغییر | — | — | **FAIL (W4-05)** |
| Alert seed (پس از حذف همه) | ۸ قانون | ۸ ردیف | ۸ ردیف (پاک شد) | — | — | **PASS** |
| Alert ack | «خواندم» ناپدید شد | read_at ست شد | `read_at=2026-10-31 00:05:56.445715` | ✅ | ✅ | **PASS** |
| Alert delete (UI) | کارت حذف شد | نام حذف شد | count=0 (event با cascade) | — | — | **PASS** |
| Token create | token یک‌بار نمایش | `token_id=a441b42ac03e0852` | Redis meta+hash | ✅ | — | **PASS** |
| Token copy | کلیپ‌بورد == token | — | — | — | — | **PASS** |
| Token استفادهٔ خارجی | راهنمای صفحه Bearer می‌گوید | `/gold/snapshot` 401، `/golddesk/snapshot` 401، `/gold/metrics` 401 | — | — | 401 | **FAIL (W4-02)** |
| Token revoke | ردیف باقی می‌ماند | enabled=false | hash حذف، meta enabled=false | ✅ | ✅ | **PARTIAL (W4-06)** |
| Logout واقعی | از `/` انجام شد → `/auth/login` | refresh بعد از logout 401 | — | — | ✅ داده‌ها ماندند | **PASS (از داشبورد؛ W4-07)** |
| Gold page reload | حلقهٔ ناوبری با SW | — | — | **FAIL (W4-03)** | — | **FAIL** |

---

## ۵) یافته‌ها

### W4-01 — فروش، تعداد holding را کاهش نمی‌دهد (Critical، مالی)

**شواهد:**
- holding ایجادشده: `id=7`، `quantity=2`، `buy_price=50,000,000`، `buy_amount_irt=100,000,000`.
- فروش ۱ واحد با قیمت 55,000,000: trade `id=5`، `quantity=1`، `amount_irt=55,000,000`، `pnl_irt=5,000,000` — هر سه UI/API/DB مطابق.
- **بلافاصله بعد از فروش:** `GET /gold/portfolio` → `quantity=2`؛ UI پس از refresh → `2.00`؛ ردیف DB holding همچنان `quantity=2.00000000`.
- کد: `src/gold_desk/portfolio.py:584-630` فقط ردیف trade را می‌نویسد و `GoldHoldingModel.quantity` را تغییر نمی‌دهد؛ `get_holdings_grouped` (`portfolio.py:447-503`) فقط `quantity` ردیف‌های holding را جمع می‌زند و فروش‌ها را کم نمی‌کند.
- محدودیت مضاعف: دکمهٔ «فروش» فقط وقتی نمایش داده می‌شود که گروه holding **یک** ردیف داشته باشد (`frontend/src/app/gold/portfolio/page.tsx:375-388`، شرط `ids.length === 1`)؛ در اجرای اول که دو ردیف خرید برای یک نماد وجود داشت، دکمهٔ فروش اصلاً رندر نشد.

**اثر:** موقعیت و ارزش پورتفو بیش از واقع نشان داده می‌شود؛ P&L و گزارش مالیاتی با تعداد واقعی نمی‌خواند؛ پس از چند خرید، فروش از UI ممکن نیست. این یک خطای صحت دادهٔ مالی است، نه فقط UI.

**اصلاح پیشنهادی (اجرا نشد):** در `record_trade` برای `sell`، مقدار holding هدف (یا لات‌های FIFO) را کاهش/تخصیص دهید و در یک تراکنش با trade ثبت کنید؛ برای گروه چندردیفی، فروش را با FIFO روی `holding_ids` توزیع کنید و دکمهٔ فروش را برای گروه هم فعال کنید. تست لازم: فروش جزئی/کامل، فروش بیش از موجودی (باید ۴۰۰/۴۰۹)، و تطابق `fifo_realized` با trade.

---

### W4-02 — Tokenهای read/write/admin هیچ مصرف‌کننده‌ای ندارند (High)

**شواهد:**
- token ساخته‌شده با scope `read` (طول ۴۳) روی این مسیرها:
  - `GET /api/v1/gold/snapshot` با `Authorization: Bearer <token>` → **401**
  - `GET /api/v1/gold/metrics` با همان Bearer → **401** (scope `metrics` لازم است)
  - `GET /api/v1/golddesk/snapshot` با `X-API-Key: <token>` → **401** (این سطح از توکن HMAC جداگانه استفاده می‌کند)
- فقط توکن با scope `metrics` (ساخته‌شده مستقیم با API، نه UI) روی `/gold/metrics` → **200** و بعد از revoke → **401**.
- کد: `apps/api/dependencies.py:259-284` فقط JWT را می‌پذیرد؛ `verify_token` از `api_token.py` تنها در `src/gold_desk/api.py:1709-1733` برای `/gold/metrics` صدا زده می‌شود؛ سطح SaaS در `core/security/saas.py:275-314` از `X-API-Key` HMAC استفاده می‌کند، نه توکن‌های Redis.
- UI دقیقاً می‌گوید: `curl -H "Authorization: Bearer YOUR_TOKEN" <HOST>/api/v1/gold/snapshot` (`frontend/src/app/gold/tokens/page.tsx:180-183`) — که کار نمی‌کند.

**اثر:** هدف اصلی صفحهٔ Token (اتصال Google Sheets/ربات تلگرام/اپ موبایل) محقق نمی‌شود. کاربر توکن می‌سازد، کپی می‌کند و همه‌جا ۴۰۱ می‌گیرد. (ساخت/کپی/revoke خودشان درست‌اند.)

**اصلاح پیشنهادی:** یا مسیر `/gold/*` یک dependency ترکیبی JWT-or-API-token با بررسی scope بگیرد، یا صفحهٔ Token فقط توکن‌های `metrics` را با مسیر درست (`/gold/metrics`) تبلیغ کند، یا به سطح `/golddesk` با فرمت HMAC مهاجرت کند. تصمیم محصولی/امنیتی لازم است.

---

### W4-03 — Service Worker طلا: حلقهٔ reload بی‌پایان در صفحات `/gold` (High)

**شواهد (بازتولیدپذیر):**
- با SW فعال: login → `/gold/portfolio` → `reload` → **۱۰۲ ناوبری** به همان URL در ۱۵ ثانیه، `hydrated=false`، کلیک روی تب DCA هیچ ورودی‌ای نشان نداد. کش `golddesk-static-v2` برای `/gold/portfolio` یک پاسخ ۲۰۰ HTML معتبر داشت؛ کنترل‌کننده: `/golddesk-sw.js`.
- با `serviceWorkers: 'block'`: همان مسیر → **۲ ناوبری**، `hydrated=true`، ورودی DCA موجود.
- کد: `frontend/public/golddesk-sw.js:90-93` برای همهٔ مسیرهای `/gold` از `cacheFirst` استفاده می‌کند (HTML احرازشده را کش می‌کند)؛ ثبت در `frontend/src/components/gold/PWAProvider.tsx:35-37`.

**اثر:** reload صفحات طلا با SW نصب‌شده می‌تواند به حلقه/صفحهٔ کهنه تبدیل شود؛ همین رفتار توضیح‌دهندهٔ «هنگ» مرورگر روی reload صفحات طلا در موج‌های قبلی است. در محیط dev قطعی است؛ برای production به‌دلیل نبود HMR شدت کمتر، اما cache-first برای HTML احرازشده پس از deploy می‌تواند chunkهای کهنه/۴۰۴ بدهد.

**اصلاح پیشنهادی:** برای navigationها network-first (یا stale-while-revalidate با revalidation اجباری) به‌جای cache-first؛ کش HTML احرازشده را نسخه‌دار/پاک‌شدنی کنید؛ آزمون E2E: نصب SW → reload → بدون حلقه و با hydration.

---

### W4-04 — نمایش P&L «۰» وقتی هیچ دارایی قیمت‌دار نیست (Medium)

**شواهد:** API پورتفو با یک holding بدون قیمت: `total_pnl=0`، `total_pnl_pct=0`، `priced_cost=0`. UI: `P&L +۰ریال +0.00٪ · روی هزینهٔ ۰ قیمت‌دار`، در حالی که همان صفحه بنر می‌دهد «۱ دارایی قیمت فعلی ندارد؛ P&L آن‌ها — است». کد: `frontend/src/app/gold/portfolio/page.tsx:302-313` فقط `priced_cost === null` را «—» می‌کند و `0` را عدد واقعی می‌پندارد؛ `portfolio.py:506-510` نیز صفر برمی‌گرداند.

**اثر:** کاربر «سود صفر» را با «سود نامعلوم» اشتباه می‌گیرد؛ این خلاف قاعدهٔ «نبود داده ⇒ —» است.

**اصلاح پیشنهادی:** وقتی `priced_cost == 0` (یا هیچ holding قیمت‌دار نیست) `total_pnl`/`total_pnl_pct` را `null` کنید و UI «—» نشان دهد؛ یا در UI همین شرط را اضافه کنید.

---

### W4-05 — «درج قوانین پیش‌فرض» بی‌صدا هیچ کاری نمی‌کند (Medium)

**شواهد:** با یک قانون سفارشی موجود، کلیک روی «درج قوانین پیش‌فرض» → API `inserted=0`، لیست بدون تغییر، UI هیچ پیامی نداد. پس از حذف همهٔ قوانین، همان کلیک ۸ قانون پیش‌فرض ساخت (نام‌ها: حباب سکه بالا/پایین، NAV صندوق عیار، شکاف درهم، امتیاز سبز، تمرکز پرتفوی، انحراف ری‌بالانس، افت سرمایه). کد: `src/gold_desk/alert_engine.py:303-307` اگر مالک **هر** قانونی داشته باشد ۰ برمی‌گرداند؛ `frontend/src/app/gold/alerts/page.tsx:28-36` نتیجه را نمایش نمی‌دهد.

**اثر:** کاربر فکر می‌کند پیش‌فرض‌ها اضافه شده‌اند؛ در عمل هیچ. راه‌حل: پیام «قوانین پیش‌فرض فقط برای مالک بدون قانون درج می‌شود» یا درج idempotent تک‌تک بر اساس نام.

---

### W4-06 — Tokenهای revoked در جدول «فعال» با دکمهٔ لغو و بدون وضعیت می‌مانند (Medium)

**شواهد:** بعد از revoke، `GET /gold/tokens` ردیف را با `enabled=false` برمی‌گرداند؛ UI همهٔ ردیف‌ها را رندر می‌کند، هدر «Tokenهای فعال (0)» است اما ردیف با دکمهٔ «لغو» باقی می‌ماند و ستون enabled/وضعیت ندارد. پس از reload و خروج/ورود دوباره هم همین‌طور است. کد: `src/gold_desk/api_token.py:175-196` (لیست شامل غیرفعال‌ها)، `frontend/src/app/gold/tokens/page.tsx:135,148-171`.

**اثر:** کاربر وضعیت توکن را نمی‌بیند و دکمهٔ لغو برای توکن لغوشده بی‌اثر است؛ خطر اشتباه در مدیریت دسترسی.

**اصلاح پیشنهادی:** ستون وضعیت + مخفی/کم‌رنگ‌کردن ردیف غیرفعال و حذف دکمهٔ لغو برای آن.

---

### W4-07 — در صفحات `/gold` هیچ دکمهٔ خروجی وجود ندارد (Medium/Low)

**شواهد:** در `/gold/portfolio` فقط سه دکمهٔ aria-label دیده شد: «منو» (مخفی موبایل)، «ثبت فروش برای …»، «حذف دارایی …». دکمهٔ `aria-label="خروج"` وجود ندارد. `frontend/src/app/gold/layout.tsx` هدر اختصاصی GoldDesk دارد و از TopNavbar اشتراکی (که خروج در آن است) استفاده نمی‌کند.

**اثر:** کاربر برای خروج باید ابتدا از بخش طلا خارج شود؛ در PWA/موبایل این کار سخت‌تر است.

**تست خروج:** از داشبورد `/` انجام شد: کلیک خروج → `/auth/login`، `POST /auth/refresh` بعد از خروج **401**، رفتن به `/gold/portfolio` در حالت خروج → `/auth/login?redirect=%2Fgold%2Fportfolio`؛ سپس ورود دوباره و تأیید ماندگاری (holding 2.00، DCA 1/3، token revoked در لیست).

---

### W4-08 — فروش گروه چندردیفی از UI ممکن نیست (Medium)

**شواهد:** در اجرای اول (دو ردیف خرید برای یک نماد) دکمهٔ فروش رندر نشد؛ شرط `ids.length === 1` در `page.tsx:379`. فروش برای یک ردیف تنها کار کرد.

**اثر:** هر خرید جداگانه یک ردیف می‌سازد؛ بعد از دو خرید، کاربر نمی‌تواند بفروشد (مگر API). این با W4-01 هم‌راستاست.

---

### W4-09 — P&L فروش بر پایهٔ یک ردیف holding است، نه FIFO (احتمالی/نیازمند تصمیم — Low)

`record_trade` برای `sell` مقدار `pnl = (price - holding.buy_price) * qty` را از **همان holding_id** می‌گیرد (`portfolio.py:612-613`)، در حالی که گزارش مالیاتی از FIFO لات‌ها استفاده می‌کند (`fifo_realized`). در تست تک‌لات، PnL=۵٬۰۰۰٬۰۰۰ درست بود؛ برای فروش چندلاتی (فقط از API ممكن) PnL ممکن است با FIFO اختلاف داشته باشد. تصمیم محصولی لازم است.

---

## ۶) شاهدهای محاسباتی

| محاسبه | ورودی | نتیجهٔ برنامه | مرجع مستقل | حکم |
|---|---|---|---|---|
| PnL فروش تک‌لات | (55M − 50M) × 1 | 5,000,000 | 5,000,000 | ✅ |
| مبلغ فروش | 1 × 55M | 55,000,000 | 55,000,000 | ✅ |
| P&L holding بدون قیمت | قیمت فعلی null | UI: ۰ (نمایش)، بنر: نامعلوم | باید «—» | ❌ W4-04 |
| DCA پلهٔ اول | سرمایه 100M، balanced | executed 0→1؛ next 30% = 29,955,067.3989 | ۳۰٪ اسمی 30M منهای هزینهٔ برآوردی | ✅ ثبت/اجرا (فرمول DCA در این موج بازبینی نشد) |
| N/A | — | — | — | — |

---

## ۷) مقایسهٔ UI/API/DB (نمونه‌های کلیدی)

- **holding:** UI «2.00» ↔ API `quantity=2` ↔ DB `quantity=2.00000000` (پس از فروش هم هر سه ۲ → W4-01).
- **trade:** API `id=5, sell, 1@55M, pnl=5M` ↔ DB `5|sell|1|55000000|55000000|5000000|...`.
- **DCA:** API `plan_id=2, executed=1` ↔ DB `2|AUD-UI-DCA-20261031|1|100000000`.
- **alert:** API/DB `id=2, bubble_above, AUD-UI-SYM, threshold=20, enabled=t`؛ toggle false→true.
- **ack:** API/DB `read_at=2026-10-31 00:05:56.445715`.
- **token:** Redis meta (`name`, `scopes=["read"]`, `enabled=true`, `token_hash` موجود)؛ token خام در meta **نیست**؛ پس از revoke `enabled=false` و hash حذف شد.

---

## ۸) شاهد حلقهٔ SW

- فایل: `audit_out/_tmp/gold_reload_diag.js` (اجرا شد).
- با SW: `navCountAfterReload=102`، `hydrated=false`، `dcaInput=0`.
- بدون SW: `navCountAfterReload=2`، `hydrated=true`، `dcaInput=1`.
- کش: `golddesk-static-v2` شامل `/gold/portfolio` با status 200، `text/html`، `redirected=false`.
- کنترل‌کننده: `http://127.0.0.1:3000/golddesk-sw.js` (scope `/gold`).

---

## ۹) پاک‌سازی

- همهٔ ردیف‌های `AUD-UI-*` حذف شدند: holdings/trades/dca/alert rules/events/portfolio values = 0.
- ۸ قانون seed که خود تست ساخت (بدون پیشوند AUD-UI) با API حذف شدند؛ count=0.
- tokenها: meta/hash حذف، index به `[]` رسید (یک ورودی کهنهٔ index که meta آن از قبل نبود هم پاک شد).
- هر دو کاربر تست حذف شدند؛ `users=0`.
- هیچ ردیف/user دیگری حذف یا تغییر نکرد.

---

## ۱۰) محدودیت‌ها / اجرا نشد

| مورد | وضعیت | دلیل |
|---|---|---|
| رفتار SW در production | **اجرا نشد** | فقط dev؛ توصیه به تست staging |
| تحویل واقعی Telegram | **BLOCKED** | ارسال بیرونی/اعتبارنامه واقعی مجاز نیست |
| حذف holding از UI | اجرا نشد | در دامنهٔ درخواست نبود؛ حذف سخت در cleanup با API انجام شد |
| snapshot/ارزش روز پورتفو | اجرا نشد | نیاز به قیمت واقعی؛ در DB تست موجود نیست |
| export CSV / گزارش مالیاتی | اجرا نشد | خارج از دامنهٔ موج |
| فروش چندلاتی از UI | **BLOCKED** | دکمه رندر نمی‌شود (W4-08) |
| تست بار/همزمانی | اجرا نشد | نیاز به محیط و ابزار load |

---

## ۱۱) اقدامات بعدی اولویت‌دار

1. **W4-01 (فوری):** کاهش holding/لات در فروش + پشتیبانی فروش گروه چندردیفی؛ تست واحد/یکپارچه روی فروش جزئی/کامل و تطابق FIFO.
2. **W4-02 (فوری):** اتصال توکن‌های read/write/admin به مسیرهای واقعی (یا اصلاح متن/گزینه‌های UI)؛ تست ۲۰۰/۴۰۱ برای هر scope.
3. **W4-03 (فوری):** تغییر استراتژی کش SW برای HTML به network-first و افزودن تست reload با SW نصب‌شده.
4. **W4-04 (کوتاه‌مدت):** `null` کردن P&L وقتی `priced_cost=0`.
5. **W4-05 (کوتاه‌مدت):** بازخورد صریح seed (inserted/دلیل ۰) یا درج تک‌تک idempotent.
6. **W4-06/07 (کوتاه‌مدت):** ستون وضعیت توکن + حذف دکمهٔ لغو برای غیرفعال؛ افزودن خروج به هدر GoldDesk.
7. **W4-09 (تصمیم):** تعیین مرجع PnL فروش (هزینهٔ همان ردیف یا FIFO) و یکسان‌سازی با گزارش مالیاتی.

---

## ۱۲) پیوست فایل‌ها

- `audit_out/_tmp/storage_wave4f.json` — اجرای کامل UI/API/DB (موفق)
- `audit_out/_tmp/storage_wave4_followup2.json` — logout/seed/metrics-token/P&L
- `audit_out/_tmp/storage_logout_test.json` — خروج واقعی از داشبورد + ورود دوباره
- `audit_out/_tmp/dca_delete_test.json` — ساخت/حذف DCA از UI
- `audit_out/_tmp/gold_reload_diag.js` — شاهد حلقهٔ SW
- `audit_out/_tmp/gold_sw_cache_diag.js` — محتوای کش SW
- اسکرین‌شات‌ها: `w4_portfolio.png`، `w4_alerts.png`، `w4_tokens.png`، `w4_followup_portfolio.png`

**جمع‌بندی:** لایهٔ ذخیره‌سازی (Postgres + Redis) و فرم‌ها از نظر ثبت/خواندن/ماندگاری سالم‌اند؛ اما فروش موجودی را کم نمی‌کند، توکن‌ها به مسیر مصرف‌کننده وصل نیستند و SW صفحه‌های طلا را در reload می‌شکند. هیچ اصلاحی اعمال نشد.
