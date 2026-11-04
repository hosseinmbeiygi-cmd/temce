# اصلاح W6-02 — وسط‌چین شدن پوستهٔ داشبورد (با TDD)

- تاریخ: 2026-10-31 08:57 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- دامنه: رفع نوار سفید ۳۲۰px و نچسبیدن `main`/هدر به لبهٔ راست در ۱۹۲۰، با کم‌ریسک‌ترین اصلاح.
- فایل‌ها: `frontend/src/app/globals.css` (در ادامهٔ اصلاح W6-01)، `frontend/src/__tests__/DashboardShellOverflow.test.ts` (تست جدید، اکنون ۳ تست).

---

## ۱) ریشهٔ دقیق

`frontend/src/app/globals.css:201`:

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
```

این reset **unlayered** است، در حالی که Tailwind v4 utilities داخل `@layer utilities` هستند. طبق cascade، استایل unlayered بر layered اولویت دارد (مستقل از specificity). بنابراین:

- `.mx-auto { margin-inline: auto; }` در CSS تولیدشده **match می‌شود** (CDP نشان داد)، اما `* { margin:0 }` آن را خنثی می‌کند.
- در RTL، بلوک ۱۶۰۰px بدون margin خودکار به **لبهٔ inline-start (راست)** می‌چسبد:
  - ۱۹۲۰: `main.x=320`، `right=1920` (نوار سفید ۳۲۰px در چپ)
  - ۱۴۴۰: عرض ۱۴۴۰ ≤ max-width، پس x=0 و مشکل دیده نمی‌شود
- همین اتفاق برای کانتینر داخلی هدر (`mx-auto max-w-[1600px]`) هم رخ می‌داد: `x=320`.
- این reset همچنین **همهٔ** utilityهای `px/py/p/m` را خنثی می‌کند؛ به همین دلیل `main` با کلاس‌های `px-3 pt-8 pb-20` در محاسبه `padding=0px` داشت. (این بخش جداگانه است: W6-03.)

**شاهد CDP:** `.mx-auto` با `margin-inline:auto` در matched rules دیده شد، ولی `main` rect = `x=320,width=1600,right=1920` و parent width=1920؛ هیچ element یا border/padding والد پهنای ۳۲۰ نداشت.

---

## ۲) اصلاح (هدفمند و کم‌ریسک)

بعد از reset، یک قاعدهٔ **unlayered** اضافه شد:

```css
/* reset بالا unlayered است و utilityهای mx-auto را خنثی می‌کند. */
.mx-auto {
  margin-inline: auto;
}
```

- فقط `mx-auto` را برمی‌گرداند؛ reset سراسری جابه‌جا/حذف نشد.
- جابه‌جایی کل reset به `@layer base` (اصلاح ریشه‌ای‌تر) blast radius بزرگ دارد (همهٔ spacing utilityها فعال می‌شوند) و به regression بصری جدا نیاز دارد؛ انجام نشد.

---

## ۳) TDD

به `DashboardShellOverflow.test.ts` تست سوم اضافه شد:

- «keeps mx-auto containers centered despite the universal reset»
- assert می‌کند یک قاعدهٔ `.mx-auto { margin-inline: auto; }` **بعد از** reset سراسری وجود دارد.

**قرمز:** قبل از افزودن قاعده → **۱ failed / ۲ passed**.
**سبز:** بعد از افزودن → **۳ passed / ۰ failed**؛ `eslint` روی تست → exit 0.

---

## ۴) تأیید مرورگر

| عرض | قبل | بعد |
|---:|---|---|
| ۱۹۲۰ | `main.x=320`، `main.right=1920`، `headerInner.x=320` | **`main.x=160`، `main.right=1760`، `headerInner.x=160`** |
| ۱۴۴۰ | `main.x=0` | `main.x=0` |
| overflow | `scrollWidth=1920` | `scrollWidth=1920` (بدون تغییر؛ W6-01 حفظ شد) |

اسکرین‌شات بعد از اصلاح: `audit_out/_tmp/show_dashboard_w602_fixed_1920.png`
(محتوای shell اکنون ۱۶۰px حاشیه در هر طرف دارد؛ نوار سفید ۳۲۰px حذف شد.)

---

## ۵) باقی‌ماندهٔ مهم — W6-03 (اصلاح نشد)

همان reset unlayered، **همهٔ** margin/padding utilityها را خنثی می‌کند؛ مثلاً `main` با `px-3/pt-8/pb-20` همچنان `padding=0px` دارد و کارت‌ها/محتوا به لبه می‌چسبند. اصلاح درست:

1. انتقال reset به `@layer base` (یا حذف `margin/padding` از `*` و اتکا به preflight تیلویند)،
2. regression بصری روی صفحات کلیدی (داشبورد، portfolio، silver، backtest، admin)،
3. سپس حذف workaround `.gold-main` در صورت نیاز.

این تغییر به‌دلیل blast radius بالا در این دامنه انجام نشد.

---

## ۶) وضعیت و پاک‌سازی

- Frontend `:3000` = 200، API `/health/ready` = 200، DB/Redis بالا.
- کاربر تستی `audit_ui_w602_20261031` حذف شد؛ `users=0`.
- هیچ داده‌ای نوشته/حذف نشد؛ هیچ commit/stage انجام نشد.
- تغییرات این دو اصلاح: `globals.css` (+۱۹/−۱ مجموع W6-01+W6-02) و تست جدید `DashboardShellOverflow.test.ts` (۳ تست).

**جمع‌بندی:** W6-02 ناشی از combination «reset unlayered + Tailwind layered utility» بود؛ با یک قاعدهٔ unlayered `.mx-auto` وسط‌چینی در ۱۴۴۰/۱۹۲۰ برگشت، بدون دست‌زدن به reset سراسری. W6-03 (خنثی‌شدن padding/spacing) باقی است و نیازمند اصلاح لایه‌ای + regression جداگانه است.
