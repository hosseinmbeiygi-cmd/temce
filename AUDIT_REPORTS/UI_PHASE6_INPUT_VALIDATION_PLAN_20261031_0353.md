# فاز ۶ — ورودی/اعتبارسنجی، کنترل‌ها و مرز امنیتی: برنامهٔ آزمون

- تاریخ: 2026-10-31 03:53 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- وضعیت: **هیچ ورودی‌ای در این فاز اجرا نشد؛ موارد زیر فرضیه‌های آزمون‌اند، نه یافته.**
- تنها موردی که در همین فاز **تأیید** شد، شکاف middleware است (بخش ۳) و آن هم فقط با درخواست بدون کوکی؛ هیچ داده‌ای نوشته/تغییر نشد.
- هیچ فایل محصولی تغییر نکرد.

---

## ۱) آنچه پیش از فاز ۶ واقعاً اجرا شده (برای تفکیک از فرضیه)

فاز ۶ از صفر شروع می‌شود، اما موج‌های ۱/۲/۴ زیرمجموعه‌ای از ورودی‌ها را اجرا کرده‌اند؛ این‌ها **یافته‌های تأییدشدهٔ قبلی** هستند و نباید دوباره «فرضیه» نامیده شوند:

| ورودی/جریان | نتیجهٔ تأییدشده | شاهد |
|---|---|---|
| `/auth/login` رمز اشتباه | پیام «Login failed: missing access token» به‌جای پیام اعتبارنامه | موج ۱ — F1 |
| `/markets/silver` مبدل با `abc`/خالی | خروجی `0.00 $ / ۰ ریال` به‌جای `—` یا خطا | موج ۲ — SIL-05 |
| `/markets/silver` بک‌تست JSON نامعتبر | پیام محلی «پارامترهای JSON نامعتبر است» بدون فراخوانی API | موج ۲ |
| `/gold/portfolio` فرم افزودن | ۹ کنترل (نماد/نام/نوع/تعداد/قیمت/مبلغ/کارمزد/یادداشت/ثبت) با موفقیت | موج ۱/۴ |
| `/gold/portfolio` فروش | فقط مقادیر مثبت تست شد؛ کاهش موجودی انجام نشد (W4-01) | موج ۴ |
| `/gold/alerts` فرم ساخت قانون | نام/نماد/آستانه/cooldown/submit تست شد؛ rule-type و channel تغییر نکردند | موج ۴ |
| `/gold/tokens` ساخت | نام/scope/submit تست شد؛ scope=admin و تیک تأیید تست نشد | موج ۴ |

**فرضیه‌های باقی‌مانده (NOT RUN):** ناهمگونی اعتبارسنجی UI/Backend، double-submit/idempotency، رفتار دیالوگ‌ها، واحد پول/دقت/زمان در جدول‌ها و نمودارها، و اکثریت ۲۲۳ ورودی.

---

## ۲) هشدار دربارهٔ اعداد ایستا

| عدد | منبع | تفسیر درست |
|---:|---|---|
| ۲۲۳ ورودی | `ui_static_inventory.json` | تعداد ** occurrence در JSX**، نه کنترل یکتای رندرشده |
| ۱۰ فرم | همان | فرم‌های صریح `<form>`؛ بسیاری از فرم‌ها div-based هستند و در این عدد نیستند (مثلاً فرم پورتفوی/توکن) |
| ۱۱۷ write API / ۴۹ mutation | همان | الگوهای فراخوانی در کد؛ برای فهرست سطح حمله خوب است، برای «تعداد تست» نه |
| ۸۸ دیالوگ / ۱۰۴ جدول / ۳۰ نمودار | همان | occurrence؛ ممکن است یک کامپوننت مشترک چند بار شمرده شود |

بنابراین برنامهٔ فاز ۶ باید بر **مسیرها و کنترل‌های واقعی هر صفحه** بنا شود، نه بر جمع این اعداد.

---

## ۳) یافتهٔ تأییدشده — middleware فقط ۱۲ مسیر را می‌بندد (P0)

**کد:** `frontend/src/middleware.ts:68-109` و `:126-144`
- `PROTECTED_ROUTES` فقط شامل `/admin`, `/settings/security`, `/profile`, `/watchlist`, `/portfolio`, `/pre-buy`, `/signals/register`, `/paper-trading`, `/sync`, `/sync-manager`, `/data-import`, `/personal` است.
- `/gold/*`، `/backtest`، `/options`، `/settings`، `/alerts` در این فهرست نیستند.
- متغیر `isPublic` محاسبه می‌شود ولی در شرط ریدایرکت **استفاده نمی‌شود**؛ برخلاف کامنت «everything else is protected by default»، رفتار واقعی allowlist معکوس نیست و فقط فهرست صریح را می‌بندد.

**شاهد (بدون کوکی، curl):**

| مسیر | پاسخ | نتیجه |
|---|---|---|
| `/admin` | 307 → `/auth/login?redirect=%2Fadmin` | محافظت middleware |
| `/gold` | 200 | بدون ریدایرکت |
| `/gold/portfolio` | 200 | بدون ریدایرکت |
| `/backtest` | 200 | بدون ریدایرکت |
| `/options` | 200 | بدون ریدایرکت |
| `/settings` | 200 | بدون ریدایرکت |
| `/alerts` | 200 | بدون ریدایرکت |
| `/gold/analytics` | 200 | عمومی by design (ماشین‌حساب) |

**لایهٔ API (بدون احراز هویت):**

| API | پاسخ |
|---|---|
| `/api/v1/gold/portfolio` | 401 |
| `/api/v1/gold/tokens` | 401 |
| `/api/v1/gold/alerts/rules` | 401 |
| `/api/v1/backtests/strategies` | 401 |
| `/api/v1/market/indices` | 200 (دادهٔ بازار عمومی) |

**ارزیابی دقیق:**
- **نشت دادهٔ مستقیم تأیید نشد:** HTML بدون کوکی فقط پوستهٔ صفحه است؛ نشانه‌ای از دادهٔ کاربر در SSR دیده نشد و APIهای شخصی ۴۰۱ می‌دهند. مرز امنیتی واقعی API است و در تست‌ها برقرار بود.
- **اما شکاف defense-in-depth/UX واقعی است:** کاربر بدون session صفحهٔ ۲۰۰ می‌گیرد و فقط با اجرای JS و ۴۰۱ بعدی به login هدایت می‌شود؛ با JS کند/غیرفعال، SW کش‌کننده یا اسکرین‌شات خودکار، پوستهٔ صفحهٔ شخصی سرو می‌شود. این با نیت کامنت و «default-deny» نمی‌خواند.
- **اصلاح پیشنهادی (اجرا نشد):** `if (!isPublicPath(pathname) && !request.cookies.has(AUTH_COOKIE_NAME)) redirect` یا گسترش صریح `PROTECTED_ROUTES`؛ افزودن تست E2E برای هر مسیر شخصی؛ حفظ ۴۰۱ سمت API به‌عنوان مرز نهایی.

---

## ۴) ماتریس آزمون فاز ۶ (همه NOT RUN تا اجرا)

### P0 — مرز امنیتی/احراز هویت (اولویت اول؛ خواندنی)
| مورد | مسیر/کنترل | انتظار | وضعیت |
|---|---|---|---|
| middleware برای همهٔ مسیرهای شخصی | `/gold/*`, `/backtest*`, `/options*`, `/settings*`, `/alerts`, `/portfolio*` | بدون کوکی → 307 login | **FAIL تأییدشده برای `/gold/*`,`/backtest`,`/options`,`/settings`,`/alerts`** |
| API بدون توکن | gold portfolio/alerts/tokens/DCA/backtest | 401 | PASS (تأیید شد برای ۴ endpoint) |
| نقش‌ها | admin vs user روی `/gold/tokens`, `/admin`, `/gold/alerts` | 403 برای غیرمجاز | NOT RUN |
| IDOR | holding/alert/DCA/event/token با id کاربر دیگر | 404/403، نه 200 | NOT RUN |
| scope توکن | read/write/admin/metrics روی endpointهای واقعی | مطابق scope | **FAIL تأییدشده (W4-02)** |
| CORS/CSRF | originهای غیرمجاز، cookie refresh | رد/عدم افشا | NOT RUN |
| کش/سرویس‌ورکر | کش HTML احرازشده | عدم سرو پوستهٔ شخصی به کاربر دیگر | NOT RUN (مرتبط با W4-03) |

### P1 — اعتبارسنجی ورودی (نیازمند کاربر تست، بدون داده واقعی)
| گروه | ورودی‌ها | مرزهای لازم | وضعیت |
|---|---|---|---|
| Auth | username/password/email/phone/register | خالی، طول، unicode، تزریق، رمز ضعیف | NOT RUN (فقط login) |
| Portfolio | symbol/name/vehicle/quantity/buy_price/amount/fee/note | 0، منفی، NaN، اعشار، مبلغ > قیمت×تعداد، طول note، نماد تکراری | PARTIAL (مقادیر مثبت) |
| Sell | quantity/price | 0/منفی/بیش از موجودی/اعشار | PARTIAL (فقط مثبت) |
| DCA | name/capital/risk | 0/منفی/بزرگ/نام تکراری | PARTIAL (مقادیر پیش‌فرض) |
| Alerts | name/rule_type/symbol/threshold/cooldown/channel/chat_id | آستانه منفی/بزرگ، cooldown 0/منفی، chat_id نامعتبر، نام تکراری | PARTIAL |
| Tokens | name/scopes/admin ack | نام خالی/طول، scope نامعتبر، admin بدون تیک | PARTIAL |
| Silver converter | grams | خالی/`abc`/منفی/خیلی بزرگ/اعشار فارسی | **FAIL تأییدشده (SIL-05)** برای `abc`/خالی |
| Backtest | symbol/strategy/dates/capital/commission/slippage/JSON | تاریخ معکوس، کارمزد >100، سرمایه 0، JSON نامعتبر | PARTIAL (JSON تأیید شد) |

### P2 — Double-submit / Idempotency
| مورد | سناریو | وضعیت |
|---|---|---|
| ۴۹ mutation / ۱۱۷ write | دوبار کلیک سریع، retry شبکه، POST تکراری، دو تب همزمان | NOT RUN |
| holding/trade/DCA execute | دو ثبت همزمان؛ آیا رکورد تکراری/موجودی منفی می‌شود؟ | NOT RUN |
| alert create/toggle/seed/ack | دو بار seed، دو ack، toggle همزمان | NOT RUN |
| token create/revoke | دو create همنام، revoke دوباره | NOT RUN |
| backup/import/sync | هر write حجیم | BLOCKED (خارج از دامنه/نیاز به تأیید) |

### P3 — دیالوگ‌ها (۸۸ دیالوگ)
| مورد | انتظار | وضعیت |
|---|---|---|
| Escape / کلیک بیرون / دکمهٔ بستن | بستن بدون اجرای عمل مخرب | NOT RUN |
| ConfirmDialog حذف/فروش/لغو token | خارج از دیالوگ = انصراف؛ فوکوس روی تأیید؛ Enter | NOT RUN |
| تغییر تب/رفرش با دیالوگ باز | از بین رفتن state یا هشدار | NOT RUN |
| Gold pages | به‌دلیل W4-03 (SW reload loop) تا رفع، BLOCKED | BLOCKED |

### P4 — جدول‌ها/نمودارها (۱۰۴ جدول، ۳۰ نمودار)
| مورد | انتظار | وضعیت |
|---|---|---|
| empty/null/partial/stale | «—» یا پیام صریح، نه 0 | PARTIAL (Silver funds/futures/news، portfolio P&L) |
| واحد پول | ریال/تومان/دلار/گرم/انس صریح | PARTIAL (Silver/Porfolio) |
| precision/rounding | گِرد فقط در نمایش؛ جمع اقلام = جمع کل | PARTIAL (مبدل Silver دقیق) |
| زمان/تقویم | شمسی/میلادی، timezone، data_as_of | NOT RUN |
| مرتب‌سازی/صفحه‌بندی/فیلتر | داده تکراری/دیررس/خارج از ترتیب | NOT RUN |
| نمودار بدون داده | empty state، بدون کندل ساختگی | PARTIAL (Silver chart) |

---

## ۵) ترتیب اجرا و پیش‌نیازها

1. **P0 (اکنون قابل اجراست):** مرز middleware/API، نقش‌ها، IDOR، scope؛ فقط خواندنی/بدون نوشتن. نیاز به کاربر admin و یک کاربر عادی تستی (ساخت در DB تستی).
2. **P1:** با کاربر تست و fixtureهای ساختگی؛ بدون داده واقعی. ابتدا ۵ صفحهٔ Partial، سپس بقیه.
3. **P2:** نیازمند کاربر/DB تستی و پاک‌سازی `AUD-UI-*`؛ برای هر mutation باید شناسهٔ رکورد و مالکیت قبل از حذف تأیید شود.
4. **P3:** دیالوگ‌های غیر-Gold اکنون؛ دیالوگ‌های Gold پس از رفع W4-03.
5. **P4:** نیازمند fixture داده (قیمت/NAV/خبر/بک‌تست)؛ بدون آن فقط empty/error قابل تست است.

**موانع شناخته‌شده:** W4-03 (SW reload loop در Gold)، نبود fixture داده، ممنوعیت ارسال بیرونی Telegram، نبود محیط load test، و نیاز به تأیید برای migration/تغییر schema.

---

## ۶) معیار پذیرش

- هر مورد فقط وقتی «موفق/ناموفق» می‌شود که **واقعاً اجرا** شده و شاهد (UI + API + DB/Redis) دارد.
- برای هر فرم: ثبت، GET، refresh، خروج/ورود دوباره، مقایسهٔ UI/API/DB.
- برای هر write: یک بار عادی + یک بار double-submit/retry؛ بررسی رکورد تکراری/موجودی منفی.
- برای هر دیالوگ: Escape + کلیک بیرون + بستن + تأیید.
- برای هر جدول/نمودار: empty/null/stale/partial + واحد + precision.
- هیچ صفحه‌ای PASS نمی‌شود مگر همهٔ کنترل‌ها و حالت‌های Cross-cutting آن اجرا شده باشند.

---

## ۷) جمع‌بندی

- فاز ۶ هنوز **۰ ورودی اجراشده** دارد؛ فرضیه‌ها به‌عنوان یافته ثبت نمی‌شوند.
- تنها یافتهٔ تأییدشدهٔ این فاز: **شکاف middleware** (P0)؛ دادهٔ شخصی مستقیماً نشت نکرد چون API ۴۰۱ می‌دهد، اما لایهٔ محافظت صفحه ناقص و برخلاف نیت کد است.
- پیشنهاد: شروع **P0** به‌صورت خواندنی (middleware/API/نقش/IDOR/scope) و سپس P1 روی ۵ صفحهٔ Partial.

**فایل مرتبط:** `AUDIT_REPORTS/UI_COVERAGE_MATRIX_20261031_0349.md` (وضعیت پوشش) و گزارش‌های موج ۱/۲/۴.
