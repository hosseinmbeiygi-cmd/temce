# ماتریس پوشش — به‌روزرسانی موج ۵

- تاریخ: 2026-10-31 04:32 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- این فایل **افزونه** بر `UI_COVERAGE_MATRIX_20261031_0349.md` است؛ آن فایل دست‌نخورده ماند.
- منبع جدید: `UI_WAVE5_BACKTEST_ADMIN_TDD_20261031_0430.md` و شاهدهای `audit_out/_tmp/wave5_*`, `admin_*`.

---

## ۱) تغییرات این موج

| صفحه | وضعیت جدید | چه چیزی اجرا شد | محدودیت |
|---|---|---|---|
| `/backtest` | **PARTIAL (بارگذاری)** | صفحه، ۱۰ دکمه، ۱۱ ورودی، ۳ select، ۶ نمودار | هیچ اجرای job/دکمهٔ اجرا |
| `/backtest/engine` | **PARTIAL (بارگذاری)** | صفحه، ۱۰ دکمه، ۴ ورودی | هیچ اجرای job |
| `/backtest/walk-forward` | **PARTIAL (بارگذاری)** | صفحه، ۱ دکمه، ۳ ورودی، ۱ select | یک `500 /auth/refresh` گذرا |
| `/admin` (admin) | **PARTIAL (بارگذاری)** | پنل با session ادمین | تب‌ها/عملیات اجرا نشد |
| `/admin` (user) | **PARTIAL — W5-01** | پوسته لود شد؛ `/dashboard` و `/jobs/scheduler` ۴۰۳، `/brsapi/sync-status` ۲۰۰ | gate نقش ندارد |
| `/admin/users` | **PARTIAL** | heading «مدیریت کاربران» | جدول/دکمه‌ای در snapshot نبود |
| `/data-import` | **PARTIAL (بارگذاری)** | heading، ۱ ورودی، ۴ دکمه | Import واقعی NOT RUN |
| `/sync-manager` | **PARTIAL** | heading، ۲۴ دکمه | عملیات sync اجرا نشد |

**۸ مسیر باقی‌ماندهٔ Backtest** (`adaptive`, `cascade`, `compose`, `decision`, `full-scan`, `generate`, `methods`, `monte-carlo`) همچنان **NOT RUN**.

---

## ۲) جمع‌بندی سطح صفحه

| وضعیت | قبل (0349) | جدید (0432) |
|---|---:|---:|
| PASS کامل | 0 | **0** |
| PARTIAL | 5 | **12** |
| FAIL کامل | 0 | 0 |
| BLOCKED | 0 | 0 |
| NOT RUN | 147 | **140** |
| کل | 152 | 152 |

**۱۲ صفحهٔ Partial:** ۵ صفحهٔ قبلی (Auth/Login، Portfolio، Alerts، Tokens، Silver) + ۷ صفحهٔ جدید (سه Backtest، Admin، Admin/Users، Data Import، Sync Manager).

---

## ۳) سطح کنترل

- در این موج **هیچ کنترل تعاملی جدیدی به‌طور کامل اجرا نشد**؛ فقط بارگذاری صفحه/هیدریت و ثبت شبکه انجام شد.
- تنها اقدام تعاملی جدید: **ورود ادمین و کاربر عادی** و **تلاش رمز اشتباه** (برای تأیید F1). این‌ها در شمارش قبلی Auth تکرار نمی‌شوند.
- شمارش اکشن قبلی (۷۶ اجراشده، ۷۳ موفق، ۳ ناموفق) بدون تغییر است؛ جزئیات در فایل 0349.
- ذخیره‌سازی جدیدی تأیید نشد (Data Import اجرا نشد؛ هیچ رکوردی نوشته نشد).

---

## ۴) یافتهٔ جدید مؤثر بر ماتریس

**W5-01:** کاربر عادی می‌تواند `/admin` را لود کند و `/brsapi/sync-status` با ۲۰۰ دادهٔ عملیاتی (۱۰ بخش شامل record_count/freshness) را می‌گیرد؛ `/dashboard` و `/jobs/scheduler` ۴۰۳ هستند. صفحهٔ ادمین gate نقش ندارد و endpoint sync-status بدون dependency نقش است. جزئیات در گزارش موج ۵.

---

## ۵) وضعیت پایانی

- **وضعیت سلامت:** `/health` و `/health/ready` هر دو PASS.
- **اصلاح TDD:** F1 (پیام رمز اشتباه) اصلاح و با ۱۳/۱۳ تست تأیید شد.
- **هیچ صفحه‌ای PASS کامل نیست.**
- **۱۴۰ صفحه** هنوز اجرا نشده‌اند؛ ۱۲ صفحه PARTIAL.

**گزارش تفصیلی:** `AUDIT_REPORTS/UI_WAVE5_BACKTEST_ADMIN_TDD_20261031_0430.md`.

---

## ۶) تلاش Gold در 04:35 (بدون تغییر در شمارش)

- ۲۲ مسیر Gold با SW مسدود تلاش شد؛ dev server هنگام کامپایل `/gold` با OOM کرش کرد
  (`Zone Allocation failed` در webpack؛ `memory allocation failed` در Turbopack) و
  صفحه با `ERR_CONNECTION_RESET` بارگذاری نشد.
- هیچ صفحهٔ Gold جدیدی به Partial اضافه نشد؛ همان ۳ صفحهٔ Portfolio/Alerts/Tokens باقی می‌ماند و
  **۱۹ صفحه همچنان NOT RUN** است.
- موانع: **W5-03** (OOM محیط dev) + **W4-03** (حلقهٔ reload سرویس‌ورکر).
- گزارش این دور: `AUDIT_REPORTS/UI_WAVE6_CONSOLIDATED_20261031_0439.md`.
