# ممیزی مستقل مرحله ۵ — قرارداد پاکت API در فرانت‌اند

**مسیر این گزارش:** `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5.md`
**گزارش مرحله (مرجع اجرا):** `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_API_CONTRACT.md` — موجود، ۱۴٬۶۸۶ بایت
**گزارش مرحلهٔ قبل:** `QA_STAGE_4.md` (دست‌نخورده)
**تاریخ/زمان ممیزی:** 2026-10-28 — حدود ۱۳:۵۸ (UTC+03:30)
**شاخه:** `integration/golddesk-fixes`
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` (بدون commit جدید)

**نتیجهٔ نهایی: PARTIAL** — مکانیزم قرارداد در لایهٔ مشترک بسته شد و ۵۴۷ تست فرانت‌اند سبز است، اما «نمایش کهنگی» فقط در یک مسیر (نقشهٔ بازار) سیم‌کشی شده، ۷۰ مصرف‌کنندهٔ دیگر `extractArray` متادیتای `data_as_of` ندارند، و تأیید رفتاری با بک‌اند زنده BLOCKED است.

> این ممیزی بر پایهٔ بازخوانی کد فعلی، diff، Git و **اجرای مجدد** تست‌ها/تایپ‌چک/لینت نوشته شده است. هیچ ادعای گزارش مرحله بدون شاهد بازتولید نشده. خروجی‌های خام در بخش ۵ ثبت شده‌اند.

---

## ۱. مسیر گزارش‌ها و وجود فایل

| گزارش | مسیر | وضعیت |
|---|---|---|
| گزارش مرحله | `AUDIT_REPORTS/MODULAR_TEMCE/05_FRONTEND_API_CONTRACT.md` | ✅ موجود — ۱۴٬۶۸۶ بایت |
| گزارش ممیزی این اجرا | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_5.md` | ✅ همین فایل |
| گزارش‌های قبلی (`00`…`QA_STAGE_4`) | `AUDIT_REPORTS/MODULAR_TEMCE/` | ✅ بازنویسی نشدند (`grep`/`ls` تأیید) |

---

## ۲. وضعیت Git و حفظ تغییرات

| مورد | مقدار/شاهد |
|---|---|
| HEAD ابتدا/انتها | `90597e05…` → `90597e05…` |
| staged قبلی | ۱۳۸ فایل؛ `115998 insert / 1447 delete` — **بدون تغییر** |
| فایل حذف‌شده | ۰ (`git status --porcelain \| grep '^ D'` خالی) |
| عملیات ممنوع | هیچ: بدون commit، reset، clean، stash، checkout مخرب، force |
| تغییرات این مرحله | ۶ فایل ویرایش‌شده + ۳ فایل جدید، همه unstaged/untracked |

**فایل‌های این مرحله:**

```
 M frontend/src/lib/api.ts
 M frontend/src/lib/goldApi.ts
 M frontend/src/hooks/useMarketData.ts
 M frontend/src/components/dashboard/LiveDataBanner.tsx
 M frontend/src/app/heatmap/page.tsx
 M frontend/src/__tests__/useMarketData.test.tsx
?? frontend/src/lib/api-envelope.ts
?? frontend/src/__tests__/apiEnvelope.test.ts
?? frontend/src/__tests__/LiveDataBanner.test.tsx
```

---

## ۳. فایل‌های بررسی‌شده و بررسی‌نشده

### بررسی‌شده (کد فعلی، خط‌به‌خط)

| فایل | شاهد بررسی |
|---|---|
| `frontend/src/lib/api-envelope.ts` | ۲۱۵ خط کامل؛ نمادها در خطوط ۲۱، ۲۶، ۴۷، ۸۹، ۱۲۰، ۱۲۵، ۱۳۵، ۱۶۲، ۱۹۸ |
| `frontend/src/lib/api.ts` | کامل؛ `assertSuccessEnvelope` در خط ۲۴۷، parse در ۲۴۲ |
| `frontend/src/lib/goldApi.ts` | کامل؛ شاخهٔ جدید در خط ۱۳۷ (`error instanceof ApiEnvelopeError`) |
| `frontend/src/hooks/useMarketData.ts` | کامل؛ `HeatmapFeed` ۲۷۰، `isRowFresh` ۲۷۸، queryFn ۲۹۰-۳۱۰ |
| `frontend/src/components/dashboard/LiveDataBanner.tsx` | کامل؛ `isStale` ۳۵-۳۸، گارد `dataAsOf != null` ۳۷ |
| `frontend/src/app/heatmap/page.tsx` | کامل؛ هیچ `catch` باقی نمانده (تنها تطبیق، کامنت خط ۱۷۳ است)، mock فقط در ۲۰۹ |
| `frontend/src/__tests__/apiEnvelope.test.ts` | کامل (۱۶ تست) |
| `frontend/src/__tests__/LiveDataBanner.test.tsx` | کامل (۶ تست) |
| `frontend/src/__tests__/useMarketData.test.tsx` | کامل؛ assertions قبلی دست‌نخورده |
| `frontend/src/__tests__/GoldApiLayer.test.ts` | کامل (تست رگرسیون C3) |
| `schemas/common/responses.py` | کامل (تعریف `data_as_of`/`cache_hit`) |
| `frontend/vitest.config.ts`, `src/__tests__/setup.ts` | کامل |

### بررسی‌نشده (و بررسی‌شده محسوب نمی‌شوند)

| مورد | دلیل |
|---|---|
| ۷۰ فراخوانِ دیگر `extractArray` در `src/` | خارج از دامنهٔ اجرایی این مرحله؛ هیچ‌کدام به `data_as_of` وصل نشدند |
| `apps/api/endpoints/*` | در مرحله ۴ ممیزی شده؛ این مرحله فقط قرارداد مصرف را عوض کرد |
| `frontend/src/app/page.tsx` (داشبورد) | تغییر نکرد؛ فقط ۱۰ ویجتِ مصرف‌کنندهٔ `LiveDataBanner` به‌صورت غیرمستقیم تحت تأثیر قرار گرفتند و تست‌هایشان سبز است |
| رفتار واقعی مرورگر با بک‌اند زنده | BLOCKED (بخش ۶) |

---

## ۴. جدول الزام‌ها

| # | الزام | شاهد (path:line / خروجی) | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| ۱ | `success:false` نباید «خالی» خوانده شود | `api.ts:242-248` + تست `rejects when the backend answers HTTP 200 with success:false` | ✅ PASS | — |
| ۲ | `data_as_of` و `cache_hit` قابل خواندن باشند | `api-envelope.ts:89-126` + تست `readEnvelopeMeta` (۳ تست) | ✅ PASS | مصرف `cache_hit` در UI نیست |
| ۳ | کهنگی دادهٔ زنده اعلام شود | `LiveDataBanner.tsx:35-38` + تست «warns when live data is older…» | 🟡 PARTIAL | فقط `heatmap` پروپ `dataAsOf` می‌فرستد؛ ۱۰ ویجت دیگر بدون متادیتا هستند |
| ۴ | دادهٔ mock جای دادهٔ واقعی/خطا را نگیرد | `heatmap/page.tsx:205-209` (mock فقط پیش از اولین پاسخ) | ✅ PASS (offline) | تأیید بصری/مرورگری اجرا نشد |
| ۵ | زمان آینده «تازه» تلقی نشود | `api-envelope.ts:198-209` + تست «rejects future timestamps» | ✅ PASS | — |
| ۶ | خطای داخلی سرور در UI لو نرود | `api-envelope.ts:135-155` + تست `not.toMatch(/Traceback\|bubbler/)` + نگاشت C3 در `goldApi.ts:137-143` | ✅ PASS | — |
| ۷ | عدم رگرسیون در قرارداد gold (C3) | `GoldApiLayer.test.ts` — ۹ تست سبز پس از اصلاح | ✅ PASS | — |
| ۸ | حفظ staged/untracked و عدم commit | HEAD ثابت؛ ۱۳۸ staged؛ ۰ حذف | ✅ PASS | — |
| ۹ | تست واقعی، نه ادعا | ۵۴۷/۵۴۷ سبز، اجرای مجدد در همین ممیزی | ✅ PASS | — |
| ۱۰ | تأیید با بک‌اند/BrsApi زنده | — | ⛔ BLOCKED | PostgreSQL/Redis/BrsApi در دسترس نیستند؛ هیچ درخواست زنده‌ای ارسال نشد |
| ۱۱ | پوشش `next build` | — | ⛔ BLOCKED | ۲۱ خطای تایپ از پیش موجود در `Fund*` |

### جزئیات دو مورد که در گزارش مرحله کم‌رنگ بود

**الف) لینت اولیه شکست خورد و اصلاح شد (نه suppress).** اجرای اول `eslint` روی `useMarketData.ts` خطای
`react-hooks/purity — Cannot call impure function during render` روی `Date.now()` داد. این خطا از نسخهٔ
uncommitted قبلی همان تابع می‌آمد، ولی چون تابع بازنویسی شد، به‌جای افزودن `eslint-disable`، خواندن زمان به
`queryFn` منتقل شد (خط ۳۰۵). اجرای نهایی: **۰ error**.

**ب) یک رگرسیون واقعی در همان دور اول کشف و رفع شد.** پس از فعال‌کردن پرتاب در `api.ts`، تست
`GoldApiLayer.test.ts` («200 + success:false ⇒ unavailable») شکست خورد؛ چون `api.ts` پیش از `goldApi`
خطا می‌داد و کد C3 (`snapshot_unavailable`) از دست می‌رفت. شاخهٔ `instanceof ApiEnvelopeError` در
`goldApi.ts:137` اضافه شد تا نگاشت قبلی حفظ شود. **تست ضعیف یا حذف نشد.**

---

## ۵. فرمان‌های تست و نتیجهٔ واقعی

| فرمان | خروجی |
|---|---|
| `cd frontend && npx vitest run` | `Test Files 57 passed (57)` / `Tests 547 passed (547)` / `Duration 64.08s` / exit 0 |
| `npx vitest run src/__tests__/useMarketData.test.tsx src/__tests__/LiveDataBanner.test.tsx src/__tests__/apiEnvelope.test.ts src/__tests__/GoldApiLayer.test.ts` | `Test Files 4 passed (4)` / `Tests 41 passed (41)` / exit 0 |
| `npx vitest run` (مجموعهٔ ۵ فایلی با `silent-refresh`) | `57 passed (57)` / exit 0 |
| `npx tsc --noEmit` | ۲۱ خطا، همه در `FundAnalysisModal` (۶)، `FundCompareModal` (۱)، `FundDetailDrawer` (۸)، `FundScorecardPanel` (۶) — **۰ خطا در فایل‌های این مرحله** |
| `npx eslint` روی ۷ فایل تغییر‌یافته | `0 errors`؛ ۱ warning از پیش موجود (`useCallback` بی‌استفاده در `heatmap/page.tsx:3`) |
| `git rev-parse HEAD` | `90597e05…` (بدون تغییر) |

**اجرا نشده‌ها:** تست بک‌اند/Pytest در این مرحله لازم نبود و اجرا نشد؛ `next build` (به‌دلیل ۲۱ خطای قبلی)؛ هیچ تست e2e یا مرورگری.

---

## ۶. مسدودها

| مورد | دلیل | اثر بر نتیجه |
|---|---|---|
| BrsApi | cooldown ۳۰۲ در مراحل قبل؛ در این ممیزی هیچ درخواستی ارسال نشد | تأیید `data_as_of` واقعی ممکن نیست |
| PostgreSQL | خاموش (`localhost:5432`) | endpoint واقعی قابل اجرا نیست |
| Redis | نصب/فعال نیست | کش و invalidate بین‌پروسه‌ای تأیید نشد |
| مرورگر | بدون بک‌اند، صفحه دادهٔ واقعی ندارد | تأیید بصری انجام نشد |

هیچ‌کدام «موفق» ثبت نشده‌اند.

---

## ۷. چرا PARTIAL و نه PASS

۱. معیار «نمایش کهنگی» فقط در `heatmap` سیم‌کشی شد؛ بقیهٔ سطوح بازار متادیتا نمی‌فرستند.
۲. `cache_hit` خوانده می‌شود ولی هیچ UI آن را نمایش نمی‌دهد (تصمیم محصولی گرفته نشده).
۳. تأیید رفتاری با دادهٔ زنده و در مرورگر BLOCKED است.
۴. `next build` همچنان به‌دلیل خطاهای از پیش موجود `Fund*` شکست می‌خورد.

آنچه قطعی و تأییدشده است: بستن حالت «خطا = خالی» در لایهٔ مشترک، تفکیک سه‌گانهٔ داده/خالی/خطا در بنر، رد کردن `data_as_of` آینده و نامعتبر، حفظ قرارداد C3 گلد، و ۵۴۷ تست سبز.

---

## ۸. کارهای باقی‌مانده (دقیق)

1. `data_as_of` را به صفحات `markets/*`، `instruments`، `codal`، `data` وصل کنید (همان `LiveDataBanner`).
2. متن/آستانهٔ نمایش `cache_hit` را تعیین و پیاده‌سازی کنید.
3. شاخه‌های مردهٔ `!res.success` را در صفحه‌هایی که اکنون `apiRequest` پرتاب می‌کند حذف کنید.
4. ۲۱ خطای تایپ `Fund*` را رفع کنید تا `next build` قابل اجرا شود.
5. با PostgreSQL/Redis/BrsApi فعال، `data_as_of` واقعی و رفتار بنر کهنگی را در مرورگر تأیید کنید.
6. هنگام تأیید، یک آزمون قراردادی برای `/market/treemap` (که هنوز `success` را دستی نمی‌خواند) اضافه کنید.
