# ماتریس پوشش به‌روزشدهٔ آزمون دستی UI

- تاریخ: 2026-10-31 03:49 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- این فایل جایگزین **وضعیت** ماتریس Baseline در `UI_MANUAL_TEST_PLAN_20261030_1406.md` است؛ خودِ فایل Baseline دست‌نخورده ماند.
- منبع: موج ۱ (Auth/Gold)، موج ۲ (Silver)، موج ۴ (Portfolio/Alerts/Tokens) + شاهدهای `audit_out/_tmp/*`.
- **هیچ فایل محصولی تغییر نکرد.**

> نکتهٔ روش‌شناسی: در ماتریس Baseline، ستون «کنترل‌های آزموده‌شده» عملاً شمارش **صفحه** بود (جمع ستون‌ها = ۱۵۲ صفحه). در این فایل، **صفحه** و **کنترل/اکشن** جدا شده‌اند تا «۵ صفحهٔ لمس‌شده» با «۷۶ اکشن اجراشده» اشتباه نشود.

---

## ۱) ماتریس سطح صفحه (گروه‌بندی قبلی)

| گروه | صفحه | آزموده‌شده (Partial) | PASS کامل | FAIL کامل | BLOCKED | اجرا نشد | ذخیره‌سازی تأییدشده |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gold | 22 | 3 | 0 | 0 | 0 | 19 | 3 |
| Markets/Silver | 22 | 1 | 0 | 0 | 0 | 21 | 0 |
| Backtest | 11 | 0 | 0 | 0 | 0 | 11 | 0 |
| Fundamental/Codal | 15 | 0 | 0 | 0 | 0 | 15 | 0 |
| Auth/Admin/Settings | 6 | 1 | 0 | 0 | 0 | 5 | 0 |
| بقیه | 76 | 0 | 0 | 0 | 0 | 76 | 0 |
| **کل** | **152** | **5** | **0** | **0** | **0** | **147** | **3** |

**صفحات Partial و شاهد آن‌ها:**

| صفحه | چه چیزی اجرا شد | یافته/محدودیت | شاهد |
|---|---|---|---|
| `/auth/login` | ورود صحیح، رمز اشتباه، logout (از `/`)، refresh پس از reload، redirect مسیر محافظت‌شده، logout→refresh 401 | رمز اشتباه پیام گمراه‌کننده (F1)؛ Register UI اجرا نشد | موج ۱ + `storage_logout_test.json` |
| `/gold/portfolio` | تب‌ها، افزودن holding، فروش، DCA create/execute/delete، جدول دارایی‌ها و تاریخچه، refresh و logout/login | فروش موجودی را کم نمی‌کند (W4-01)؛ P&L نامعلوم «۰» (W4-04)؛ دکمهٔ فروش گروه چندردیفی مخفی (W4-08) | موج ۱ + موج ۴ |
| `/gold/alerts` | create، toggle، delete، seed (دو حالت)، ack، تب رویدادها، refresh و login دوباره | seed با وجود یک قانون بی‌صدا صفر می‌شود (W4-05)؛ تحویل Telegram اجرا نشد | موج ۴ |
| `/gold/tokens` | create، copy، revoke، جدول، refresh و logout/login | توکن read/write/admin روی مسیر تبلیغ‌شده ۴۰۱ (W4-02)؛ ردیف revoked بدون وضعیت (W4-06) | موج ۴ |
| `/markets/silver` | ۷ تب، مبدل گرم/انس/ریال، فرم بک‌تست (بدون اجرا)، جستجوی ML، جدول‌ها/empty/error، refresh | forecast و اجرای بک‌تست به‌دلیل نبود داده/جدول مسدود؛ خطاهای schema در commodities/currency/futures | موج ۲ |

**۱۴۷ صفحهٔ اجرانشده** شامل ۱۹ صفحهٔ باقی‌ماندهٔ Gold، ۲۱ صفحهٔ Markets، ۱۱ صفحهٔ Backtest، ۱۵ صفحهٔ Fundamental/Codal، ۵ صفحهٔ Auth/Admin/Settings و ۷۶ صفحهٔ بقیه است. هیچ‌کدام «بررسی‌شده» علامت نمی‌خورند.

---

## ۲) ماتریس سطح کنترل/اکشن (فقط اجراشده‌ها)

واحد شمارش: یک کنترل یا اکشن کاربر (کلیک/تایپ/select/submit/تأیید دیالوگ). شمارش **یکتای** کنترل‌هاست؛ تکرار یک کنترل دو بار یک‌بار شمرده شده است.

| صفحه | اکشن اجراشده | موفق | ناموفق | کنترل‌های اجرانشده/مسدود (جدا) | ذخیره‌سازی |
|---|---:|---:|---:|---|---|
| `/auth/login` | 8 | 7 | 1 (پیام رمز اشتباه) | Register submit (۱) | session refresh تأیید شد |
| `/gold/portfolio` | 26 | 25 | 1 (فروش، W4-01) | حذف holding از UI (۲)، ثبت ارزش امروز (۱) | Postgres: holding/trade/DCA تأیید شد |
| `/gold/alerts` | 12 | 11 | 1 (seed با قانون موجود) | rule-type select (۱)، channel select (۱)، تحویل Telegram (۱) | Postgres: rule + ack(read_at) تأیید شد |
| `/gold/tokens` | 7 | 7 | 0 | — (چک‌های API خارجی جدا: ۳×۴۰۱، W4-02) | Redis: meta/hash/index تأیید شد |
| `/markets/silver` | 23 | 23 | 0 | اجرای بک‌تست (۱)، ۶ دکمهٔ افق غیرفعال + مسیر عددی forecast (۷) | — |
| **کل** | **76** | **73** | **3** | **۱۵ مورد اجرانشده/مسدود** | **۳ صفحه با ذخیره‌سازی تأییدشده** |

### تفکیک ۱۵ مورد اجرانشده/مسدود
- Auth: Register UI submit — **NOT RUN**.
- Portfolio: حذف holding از UI (دکمه+دیالوگ)، ثبت ارزش امروز — **NOT RUN**.
- Alerts: تغییر rule-type، تغییر channel، تحویل واقعی Telegram — **NOT RUN/BLOCKED** (ارسال بیرونی مجاز نیست).
- Silver: اجرای واقعی بک‌تست — **NOT RUN** (نماد دارای تاریخچه در DB تست نیست)؛ ۶ دکمهٔ افق پیش‌بینی + مسیر عددی — **BLOCKED** (داده نیست).

---

## ۳) وضعیت ذخیره‌سازی (فرم‌به‌فرم)

| فرم | ثبت UI | GET API | refresh | logout/login | مقایسه UI/API/DB | حکم |
|---|---|---|---|---|---|---|
| Add holding | ✅ | ✅ | ✅ | ✅ | qty=2، مبلغ 100M، fee=0.5%، note، user_id | PASS |
| Sell | ✅ | ✅ | ✅ | ✅ | trade 1@55M، PnL 5M؛ **holding qty=2 ماند** | FAIL (W4-01) |
| DCA create/execute | ✅ | ✅ | ✅ | ✅ | executed 0→1، DB=1 | PASS |
| DCA delete (UI) | ✅ | ✅ | — | — | API/UI/DB=0 | PASS |
| Alert create/toggle | ✅ | ✅ | ✅ | ✅ | enabled false→true، DB مطابق | PASS |
| Alert seed | ⚠️ | ✅ | — | — | ۰ با قانون موجود؛ ۸ بدون قانون | PARTIAL (W4-05) |
| Alert ack | ✅ | ✅ | ✅ | ✅ | read_at در API/DB | PASS |
| Alert delete | ✅ | ✅ | — | — | API/DB=0 | PASS |
| Token create/copy | ✅ | ✅ | ✅ | ✅ | raw فقط یک‌بار؛ کپی مطابق؛ raw در Redis نیست | PASS |
| Token revoke | ✅ | ✅ | ✅ | ✅ | hash حذف؛ enabled=false؛ ردیف در UI می‌ماند | PARTIAL (W4-06) |
| Token استفادهٔ خارجی | — | — | — | — | `/gold/snapshot` 401، `/golddesk/snapshot` 401 | FAIL (W4-02) |

---

## ۴) مغایرت با ماتریس Baseline

| مورد | Baseline | به‌روزشده |
|---|---|---|
| صفحات آزموده‌شده | ۰ | ۵ (همه Partial) |
| صفحات PASS کامل | ۰ | ۰ |
| صفحات اجرانشده | ۱۵۲ | ۱۴۷ |
| کنترل/اکشن اجراشده | ۰ | ۷۶ (۷۳ موفق، ۳ ناموفق) |
| ذخیره‌سازی تأییدشده | ۰ | ۳ صفحه (Portfolio/Alerts/Tokens) |
| یافته‌های بحرانی جدید | — | فروش موجودی را کم نمی‌کند؛ توکن‌ها بی‌مصرف؛ SW طلا reload را حلقه می‌کند |

---

## ۵) چرا هنوز هیچ صفحه‌ای PASS نیست؟

1. **پوشش کنترل‌به‌کنترل ناقص است:** حتی در ۵ صفحهٔ لمس‌شده، کنترل‌هایی مثل حذف holding، snapshot، rule-type/channel، اجرای بک‌تست و تحویل Telegram اجرا نشده‌اند.
2. **وضعیت‌های Cross-cutting تست نشده‌اند:** loading/disabled/double-click، قطع API، 500، offline، mobile 390×844، desktop 1440×900 و keyboard navigation در هیچ صفحه‌ای کامل آزموده نشده‌اند.
3. **Gold reload با SW فعال شکسته است (W4-03):** تا رفع حلقهٔ Service Worker، تست پایدار ۱۹ صفحهٔ باقی‌ماندهٔ Gold و reload آن‌ها ممکن نیست.
4. **نبود داده در DB تست:** forecast/بک‌تست/NAV/قیمت‌ها مسدود می‌مانند تا fixture کنترل‌شده بارگذاری شود.
5. **دو صفحه فقط از طریق API/curl بررسی شده‌اند، نه UI:** register و برخی APIهای token؛ این‌ها به‌عنوان UI تست‌شده شمرده نشده‌اند.

---

## ۶) پیشنهاد موج بعدی (به ترتیب)

1. **رفع W4-03 (SW reload loop)** و سپس ادامهٔ ۱۹ صفحهٔ Gold با SW فعال؛ بدون این، reload/refresh قابل اتکا نیست.
2. **Backtest (۱۱ صفحه):** run/poll/result، ورودی‌های مرزی، خطا و لغو؛ با نماد fixture.
3. **Fundamental/Codal (۱۵ صفحه):** خواندن/فیلتر/جزئیات؛ فقط با داده fixture.
4. **Auth/Register و Admin/Settings (۵ صفحهٔ باقی‌مانده):** register UI، نقش‌ها، settings، logout در Gold.
5. **Cross-cutting:** loading/empty/error/offline/double-click/mobile/keyboard روی ۵ صفحهٔ Partial.
6. **اصلاح W4-01/W4-02/W4-04/W4-05/W4-06** با TDD و سپس تست دوبارهٔ همان کنترل‌ها.

---

## ۷) شاهدها

- `AUDIT_REPORTS/UI_MANUAL_WAVE1_AUTH_GOLD_20261031_0203.md`
- `AUDIT_REPORTS/UI_MANUAL_WAVE2_SILVER_20261031_0259.md`
- `AUDIT_REPORTS/UI_MANUAL_WAVE4_STORAGE_20261031_0343.md`
- `audit_out/_tmp/storage_wave4f.json`، `storage_wave4_followup2.json`، `storage_logout_test.json`، `dca_delete_test.json`، `silver_tabs_content.json`، `silver_converter_synthetic.json`
- `audit_out/ui_static_inventory.json` (۱۵۲ مسیر؛ مبنای شمارش گروه‌ها)

**جمع‌بندی:** ماتریس Baseline «۰ آزموده» بود؛ پس از موج‌های ۱/۲/۴، **۵ صفحه Partial**، **۷۶ اکشن اجراشده** و **۳ صفحه با ذخیره‌سازی تأییدشده** داریم. هیچ صفحه‌ای هنوز PASS کامل نیست و ۱۴۷ صفحه اجرا نشده‌اند؛ این عدد باید تا تکمیل کنترل‌ها و حالت‌های Cross-cutting همین‌طور صادقانه باقی بماند.
