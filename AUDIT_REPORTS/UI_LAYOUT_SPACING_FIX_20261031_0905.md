# اصلاح W6-03 — بازگرداندن utilityهای فاصله‌گذاری Tailwind (با TDD)

- تاریخ: 2026-10-31 09:05 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- دامنه: رفع ریشه‌ای خنثی‌شدن `mx-*` / `px-*` / `py-*` / `p-*` توسط reset سراسری unlayered.
- فایل‌ها: `frontend/src/app/globals.css`، `frontend/src/__tests__/DashboardShellOverflow.test.ts` (۳ تست). هیچ فایل دیگری تغییر نکرد.

---

## ۱) ریشه

`globals.css:201` یک reset **unlayered** داشت:

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
```

در Tailwind v4 همهٔ utilityها داخل `@layer utilities` هستند. CSS unlayered بر layered اولویت دارد، بنابراین این reset **همهٔ** utilityهای فاصله‌گذاری را خنثی می‌کرد:

- `.mx-auto` → margin خودکار از بین می‌رفت (W6-02).
- `px-*` / `py-*` / `p-*` / `m-*` → مقدار محاسبه‌شده ۰ می‌شد؛ حتی `main` با `px-3 pt-8 pb-20` در ۱۹۲۰ `padding=0px` داشت.
- در نتیجه محتوا به لبه‌ها می‌چسبید و shell در RTL به لبهٔ راست می‌رفت.

---

## ۲) اصلاح (ریشه‌ای، کم‌ریسک با تست)

1. reset به لایهٔ base منتقل شد:

```css
@layer base {
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
}
```

utilityهای Tailwind در لایهٔ utilities (بعد از base) دوباره برنده می‌شوند.

2. workaround موقت `.mx-auto { margin-inline: auto; }` (اصلاح W6-02) **حذف شد**؛ چون ریشه رفع شده و utility اصلی دوباره کار می‌کند.

3. کامنت `.gold-main` به‌روزرسانی شد (دیگر reset، utilityها را خنثی نمی‌کند). خود `.gold-main` به‌عنوان padding صریح پوستهٔ Gold باقی ماند.

---

## ۳) TDD

تست سوم `DashboardShellOverflow.test.ts` بازنویسی شد:

- assert می‌کند reset داخل `@layer base` است؛
- assert می‌کند یک reset سراسری unlayered باقی نمانده است.

**قرمز:** قبل از تغییر CSS → **۱ failed / ۲ passed**.
**سبز:** بعد از تغییر → **۳ passed / ۰ failed**؛ ESLint روی تست → exit 0.

---

## ۴) تأیید مرورگر (قبل/بعد W6-03)

| متریک | قبل (W6-02) | بعد (W6-03) |
|---|---|---|
| `main.padding` در ۱۹۲۰ | `0px` | **`32px 20px 80px`** (`pt-8`, `px-5`, `pb-20`) |
| `main.x` در ۱۹۲۰ | 160 (با workaround) | **160** (با utility اصلی) |
| `header inner padding` | 0 | **`0 20px`** |
| `main.x` در ۱۴۴۰ | 0 | **0** |
| `scrollWidth / innerWidth` | 1920/1920 | **1920/1920** |

صفحات بررسی‌شده: `/`، `/backtest`، `/admin` — هر سه با padding صحیح، `main.x=160` در ۱۹۲۰ و بدون overflow.
اسکرین‌شات: `audit_out/_tmp/show_dashboard_w603_fixed_1920.png` (چیدمان وسط‌چین با فاصله‌های کارت‌ها).

---

## ۵) ریسک باقی‌مانده / regression

- فعال‌شدن همهٔ utilityهای margin/padding می‌تواند فاصله‌گذاری صفحات دیگر را تغییر دهد. در این دور فقط `/`، `/backtest` و `/admin` بصری بررسی شدند؛ **۱۴۹ صفحهٔ دیگر regression بصری نشده‌اند**.
- `.gold-main` به‌عنوان padding صریح باقی مانده؛ اگر همهٔ صفحات Gold از utility استفاده کنند، می‌توان در آینده حذفش کرد.
- W6-01 (overflow) و W6-02 (centering) با این تغییر حفظ شده‌اند.

---

## ۶) وضعیت اجرا و پاک‌سازی

- **در حین تأیید:** Frontend `:3000` = 200 و API `/health/ready` = 200 بودند و شاهدهای بالا ثبت شد.
- **بعد از تأیید:** dev server (webpack، heap 1536MB) با OOM کرش کرد و API تستی هم خاموش شد؛ Docker (DB/Redis) سالم است و حافظهٔ آزاد ~۰.۵GB. این به کد W6-03 مربوط نیست (محدودیت محیط).
- کاربر تستی `audit_ui_w603_20261031` حذف شد؛ `users=0`.
- هیچ داده‌ای نوشته/حذف نشد؛ هیچ commit/stage انجام نشد.
- مجموع diff فعلی: `globals.css` (+۱۹/−۹ شامل W6-01/W6-02/W6-03) و تست جدید `DashboardShellOverflow.test.ts` (۳ تست).

**جمع‌بندی:** W6-03 با انتقال reset به `@layer base` رفع شد؛ utilityهای Tailwind دوباره اعمال می‌شوند، workaround W6-02 حذف شد و تست‌ها ۳/۳ سبزند. ریسک باقی‌مانده، regression بصری صفحاتی است که در این دور بررسی نشدند.
