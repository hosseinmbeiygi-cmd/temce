# اصلاح overflow افقی داشبورد (W6-01) — با TDD

- تاریخ: 2026-10-31 08:47 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- دامنه: ریسک‌کم‌ترین اصلاح overflow افقی در پوستهٔ داشبورد، با تست رگرسیون.
- **فایل‌های تغییرکرده:** `frontend/src/app/globals.css` (M، +10/−1)، `frontend/src/__tests__/DashboardShellOverflow.test.ts` (جدید). هیچ فایل دیگری تغییر نکرد.

---

## ۱) ریشهٔ دقیق (با شاهد عددی)

1. `.dash-field::after` یک لایهٔ تزئینی aurora است:
   `position: fixed; inset: -18%; animation: auroraDrift 38s ...; will-change: transform;`
2. `.page-enter` (در `src/app/template.tsx`) انیمیشن `pageRise` با `fill-mode: both` دارد؛ پس **بعد از پایان انیمیشن هم `transform: translateY(0)` روی آن باقی می‌ماند**.
3. هر ancestor با `transform` غیر-none، برای descendants با `position: fixed` **containing block** می‌سازد. بنابراین aurora دیگر نسبت به viewport ثابت نیست؛ نسبت به `.page-enter` (عرض ۱۴۴۰/۱۹۲۰) positioning می‌شود و `inset: -18%` آن را **۱۸٪ پهن‌تر از viewport** می‌کند.
4. ۱۸٪ دقیقاً با شاهد هم‌خوان است:
   - ۱۴۴۰ × ۱.۱۸ ≈ ۱۶۹۹ → observed `scrollWidth=1705`
   - ۱۹۲۰ × ۱.۱۸ ≈ ۲۲۶۶ → observed `scrollWidth=2269`
5. علاوه بر این، `auroraDrift` تا `scale(1.05)` و `translate3d(-2.2%, 1.6%, 0)` می‌رسد؛ حتی با `inset: 0`، در فازهای انتهایی انیمیشن چند ده پیکسل overflow باقی می‌ماند (worst-case در ۱۹۲۰: `2010`).

**شاهد DOM:** `main` عرض ۱۶۰۰ دارد، `.page-enter` عرض ۱۹۲۰ و `scrollWidth≈2269`؛ هیچ فرزند عریضی در `main` نبود (`mainSW=1600`) — overflow از pseudo-element تزئینی پوسته بود، نه از جدول/نمودار.

---

## ۲) گزینه‌های آزموده‌شده (قبل از انتخاب)

| گزینه | نتیجه |
|---|---|
| `display:none` روی aurora | overflow صفر، ولی جلوهٔ aurora حذف می‌شود |
| `inset: 0` (بدون clip) | ۱۸٪ حذف شد، اما انیمیشن تا `~2010px` در ۱۹۲۰ سرریز می‌کند |
| `clip-path: inset(0)` روی aurora | در فازهای مختلف overflow را حذف نکرد (بدتر شد) |
| `animation: none` | overflow صفر، ولی حرکت aurora حذف می‌شود |
| `overflow: clip` روی `.dash-field` | کافی نبود (containing block همان `.page-enter` است) |
| **`overflow-x: clip` روی `.page-enter`** | **overflow سند صفر؛ انیمیشن حفظ می‌شود؛ scroll container نمی‌سازد** |

---

## ۳) اصلاح اعمال‌شده (کم‌ریسک)

```css
.dash-field::after {
  position: fixed;
  inset: 0;        /* قبلاً -18% */
  ...
}

.page-enter {
  animation: pageRise 0.34s cubic-bezier(0.22, 1, 0.36, 1) both;
  overflow-x: clip;
}
```

- `inset: 0` منبع ۱۸٪ overflow را حذف می‌کند و aurora را در viewport نگه می‌دارد.
- `overflow-x: clip` فقط overflow افقی پوستهٔ transformed را می‌بندد؛ `clip` (نه `hidden`) scroll container نمی‌سازد و sticky/fixed را تحت‌تأثیر قرار نمی‌دهد.
- انیمیشن aurora و page transition حفظ شده‌اند.

---

## ۴) TDD

**تست جدید:** `frontend/src/__tests__/DashboardShellOverflow.test.ts`

- تست ۱: `.dash-field::after` باید `position: fixed`، `animation: auroraDrift` و `inset: 0` داشته باشد و `inset` منفی نداشته باشد.
- تست ۲: `.page-enter` باید `animation: pageRise` و `overflow-x: clip` داشته باشد.

**قرمز (قبل از اصلاح):**
- تست ۱ با `inset: -18%` شکست خورد؛
- پس از افزودن `overflow-x` تست ۲ هم قبل از CSS شکست خورد.

**سبز (بعد از اصلاح):**
- `vitest run src/__tests__/DashboardShellOverflow.test.ts` → **۲ passed / ۰ failed**
- `eslint src/__tests__/DashboardShellOverflow.test.ts` → exit 0

---

## ۵) تأیید مرورگر (Playwright، پس از HMR)

اندازه‌گیری `document.documentElement.scrollWidth` در برابر `innerWidth`:

| عرض | قبل | بعد (چند فاز انیمیشن) | بدترین فاز (`scale 1.05`) |
|---:|---|---|---|
| ۱۴۴۰ | ۱۷۰۵ | **۱۴۴۰ = ۱۴۴۰** | **۱۴۴۰ = ۱۴۴۰** |
| ۱۹۲۰ | ۲۲۶۹ | **۱۹۲۰ = ۱۹۲۰** | **۱۹۲۰ = ۱۹۲۰** |

`peSW` داخلی هنوز ۱۵۰۸/۲۰۱۰ است، اما با `overflow-x: clip` از سند بیرون نمی‌زند و اسکرول افقی ندارد. اسکرین‌شات بعد از اصلاح: `audit_out/_tmp/show_dashboard_fixed3_1920.png`.

---

## ۶) باقی‌ماندهٔ جدا (W6-02 — خارج از دامنهٔ overflow)

در ۱۹۲۰، `main` با عرض ۱۶۰۰ از `x=320` شروع می‌شود (به‌جای مرکز ۱۶۰) و یک نوار سفید ۳۲۰px در سمت چپ می‌ماند؛ در ۱۴۴۰، `main` از `x=0` است. این **overflow نیست** (`scrollWidth == innerWidth`)، بلکه یک مسئلهٔ positioning/چیدمان (احتمالاً ریل سایدبار خالی یا margin/RTL) است و در این اصلاح دست نخورد. نیازمند بررسی جداگانه است.

---

## ۷) وضعیت محیط و پاک‌سازی

- Frontend `:3000` = 200، API `:8000/api/v1/health/ready` = 200، DB/Redis بالا.
- کاربران تستی این بررسی (`audit_ui_layout_20261031`, `..._layout2...`, `..._layout3...`) حذف شدند؛ `users=0`.
- هیچ دادهٔ دیگری نوشته/حذف نشد؛ هیچ commit/stage انجام نشد.
- فایل‌های دارای تغییر کاربر (portfolio/alerts/tokens/layout/silver) دست نخوردند؛ `globals.css` و تست جدید فقط تغییر ما هستند.

---

## ۸) شاهدها

- `audit_out/_tmp/overflow_fix_experiment.json` — گزینه‌های اولیه
- `audit_out/_tmp/overflow_fix_experiment2.json` — فازهای انیمیشن
- `audit_out/_tmp/worstcase_overflow.json` — بدترین فاز transform
- `audit_out/_tmp/final_overflow_verify3.js` — تأیید نهایی ۱۴۴۰/۱۹۲۰
- `audit_out/_tmp/show_dashboard_fixed3_1920.png` — تصویر بعد از اصلاح

**جمع‌بندی:** ریشه `.dash-field::after{inset:-18%}` در containing block ساخته‌شده توسط transform `.page-enter` بود. اصلاح دو خط CSS + تست رگرسیون، overflow افقی را در همهٔ فازهای انیمیشن صفر کرد.
