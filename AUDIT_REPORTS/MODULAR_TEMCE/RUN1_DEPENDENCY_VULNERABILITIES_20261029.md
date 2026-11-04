# آسیب‌پذیری‌های وابستگی — TEMCE — Run 1

- **تاریخ snapshot:** 2026-10-29T10:51Z (Iran: 14:21)
- **ریشه:** `C:/Users/Iran/Desktop/temce`
- **Branch:** `integration/golddesk-fixes` · **HEAD:** `be8b4ff4`
- **وضعیت کاری:** کثیف (کار موازی در همان tree)؛ این گزارش **هیچ فایلی را تغییر نداده است**
- **نتیجهٔ کلی:** `OPEN` — ۲۲ بستهٔ آسیب‌پذیر (۹۱ CVE یکتا)؛ ۱ مورد `BLOCKED` (starlette)، ۱ مورد بدون fix بالادست (xlsx).

> روش: `gh` روی این ماشین نصب نیست، بنابراین alert های GitHub خوانده نشد. به‌جای آن نسخه‌های قفل‌شدهٔ واقعی مخزن در برابر پایگاه عمومی **OSV** (`api.osv.dev`) ارزیابی شد: `requirements.lock` (۱۳۲ بسته، ecosystem PyPI) و `frontend/package-lock.json` (۶۸۹ بسته، ecosystem npm). هر advisory با شناسهٔ GHSA/PYSEC/CVE و severity رسمی (`database_specific.severity` در GHSA) ثبت شده است.
>
> اختلاف با عدد «۱۷ alert» گیت‌هاب طبیعی است: Dependabot فایل `requirements.lock` را نمی‌خواند، تعداد را بر اساس manifest می‌شمارد و GHSA/PYSEC تکراری را در چند alert جدا نشان می‌دهد. ملاک این گزارش، بستهٔ واقعاً قفل‌شده است.

---

## ۱) خلاصهٔ مدیریتی

۹۱ آسیب‌پذیری یکتا در ۲۲ بسته پیدا شد. سه مورد نیازمند تصمیم/تحقیق است و بقیه مسیر رفع مستقیم دارند:

1. **`next@16.2.9` — ۲۰ CVE (۵ Critical)** — بزرگ‌ترین سطح ریسک؛ رفع با یک پچ در همان minor (`16.2.11`).
2. **`starlette@0.52.1` — ۵ CVE (۲ High)** — `BLOCKED`: `fastapi==0.128.8` محدودیت `starlette<1.0.0` دارد و همهٔ رفع‌ها در ۱.x هستند؛ در محدودهٔ مجاز نسخهٔ امن وجود ندارد.
3. **`lxml@4.9.4` — XXE (High)** — رفع فقط با پرش major به `6.1.0`؛ سه کتابخانهٔ بازار ایران (`finpy-tse`، `tehran-stocks`، `tse-utils`) به آن وابسته‌اند و باید سازگاری‌شان آزموده شود.
4. **`xlsx@0.18.5` — ۲ CVE High، بدون fix** — بستهٔ npm آن رها شده است؛ در `frontend/src` هیچ import ای ندارد، پس حذف آن رایگان‌ترین رفع است.
5. **ناهم‌خوانی lock با محیط نصب‌شده** (DEPV-22): aiohttp 3.14.3 در lock در برابر 3.13.3 در venv، lxml 4.9.4 در برابر 5.4.0، و همین‌طور certifi/opentelemetry — یعنی dev و production دو نسخهٔ متفاوت اجرا می‌کنند.

---

## ۲) دامنه و محدودیت‌ها

| مورد | وضعیت |
|---|---|
| `requirements.lock` (uv compile، ۱۳۲ بسته) | اسکن شد |
| `frontend/package-lock.json` (۶۸۹ بسته) | اسکن شد |
| `requirements.txt` بدون lock | فقط از طریق lock پوشش داده شد |
| تصاویر Docker (`Dockerfile.*`) | **اسکن نشد** — نیاز به اسکنر image (Trivy/Grype) |
| GitHub Actions (`.github/workflows`) | **اسکن نشد** |
| بسته‌های سیستمی OS در runtime | **اسکن نشد** |
| `node_modules` نصب‌شده در برابر lock | مقایسه نشد؛ ملاک، lock است |

severity ها از فیلد رسمی GHSA گرفته شده‌اند؛ جایی که GHSA مقدار نداده `UNKNOWN` ثبت شده و در ستون شدت با `*` مشخص است.

---

## ۳) یافته‌ها

### ۳.۱ پایتون (production)

| ID | بسته | نصب‌شده | CVE یکتا | بدترین شدت | رفع در | مسیر وابستگی | وضعیت |
|---|---|---|---|---|---|---|---|
| DEPV-01 | `aiohttp` | 3.14.3 | ۸ | High (۳ High / ۴ Moderate / ۱ Low) | **3.14.4** | مستقیم (`requirements.txt`) | OPEN |
| DEPV-02 | `starlette` | 0.52.1 | ۵ | High (۲ High / ۲ Moderate / ۱ Low) | 1.3.1 | از `fastapi==0.128.8` | **BLOCKED** |
| DEPV-03 | `lxml` | 4.9.4 | ۱ | High (XXE، خواندن فایل محلی) | **6.1.0** | `finpy-tse`، `tehran-stocks`، `tse-utils` | OPEN (major) |
| DEPV-04 | `certifi` | 2026.7.22 | ۲ | Critical (CA های emSign با کلید میانی compromised) | 2026.10.19 | `httpx` / `aiohttp` / `curl-cffi` | OPEN |
| DEPV-05 | `brotli` | 1.2.0 | ۱ | Critical (OOB write در دیکودر) | 1.2.1 | از `aiohttp` | OPEN |
| DEPV-06 | `opentelemetry-api` | 1.45.0 | ۱ | Moderate (parsing نامحدود tracestate) | 1.45.1 | مستقیم | OPEN |

### ۳.۲ npm (production / bundle)

| ID | بسته | نصب‌شده | CVE یکتا | بدترین شدت | رفع در | مسیر وابستگی | وضعیت |
|---|---|---|---|---|---|---|---|
| DEPV-07 | `next` | 16.2.9 | ۲۰ | **Critical (۵ Critical / ۶ High / ۸ Moderate / ۱ Low)** | **16.2.11** | مستقیم (پین دقیق) | OPEN |
| DEPV-08 | `sharp` | 0.34.5 | ۳ | High | 0.35.5 | از `next` | OPEN |
| DEPV-09 | `postcss` | 8.5.15 | ۲ | High | 8.5.23 | از `next` / `@tailwindcss/postcss` / `vite` | OPEN |
| DEPV-10 | `@sentry/nextjs` | 10.74.0 | ۱ | Critical | 10.75.2 | مستقیم | OPEN |
| DEPV-11 | `xlsx` | 0.18.5 | ۲ | High | **بدون fix در npm** | مستقیم، **در کد import نمی‌شود** | OPEN (حذف) |

### ۳.۳ npm (dev / build-only — سطح حملهٔ production ندارند)

| ID | بسته | نصب‌شده | CVE یکتا | بدترین شدت | رفع در | مسیر وابستگی |
|---|---|---|---|---|---|---|
| DEPV-12 | `undici` | 7.28.0 | ۲۳ | High (۷ High / ۱۳ Moderate / ۳ Low) | 7.30.1 | `jsdom` (dev) |
| DEPV-13 | `vite` | 8.1.0 | ۵ | High | 8.3.3 | `vitest` / `@vitejs/plugin-react` (dev) |
| DEPV-14 | `vitest` + `@vitest/mocker` | 4.1.9 | ۳ | Moderate | 4.1.12 | dev |
| DEPV-15 | `js-yaml` | 4.2.0 | ۳ | High | 4.3.2 | `@eslint/eslintrc` (dev) |
| DEPV-16 | `fast-uri` | 3.1.8 | ۴ | Moderate | 3.1.9 | `ajv` (dev/build) |
| DEPV-17 | `nanoid` | 3.3.15 | ۲ | High | 3.3.18 | `postcss` |
| DEPV-18 | `browserslist` | 4.28.4 | ۲ | High | 4.28.7 | build |
| DEPV-19 | `zod` | 4.4.3 | ۱ | High | 4.6.6 | `eslint-plugin-react-hooks` (dev) |
| DEPV-20 | `source-map-js` | 1.2.1 | ۱ | High | 1.2.2 | build |
| DEPV-21 | `baseline-browser-mapping` | 2.10.40 | ۱ | Moderate | 2.11.0 | build |

### ۳.۴ یافتهٔ فرایندی

| ID | یافته | شاهد | وضعیت |
|---|---|---|---|
| DEPV-22 | lock و محیط نصب‌شده ناهم‌خوان‌اند | lock: `aiohttp==3.14.3`, `lxml==4.9.4`, `certifi==2026.7.22`, `opentelemetry-api==1.45.0` · venv: `3.13.3`, `5.4.0`, `2026.6.17`, `1.42.1` | OPEN |

پیامد: بررسی امنیتی روی lock انجام می‌شود ولی runtime فعلی نسخهٔ دیگری دارد؛ تا وقتی lock منبع حقیقتِ استقرار نشود، این گزارش برای production قطعی نیست.

---

## ۴) تحلیل موارد مسدود / نیازمند تصمیم

### ۴.۱ `starlette` (DEPV-02) — BLOCKED

- `importlib.metadata.requires("fastapi")` → `starlette<1.0.0,>=0.40.0`
- رفع‌های OSV: `1.0.1` (Host header / path poisoning)، `1.1.0` (StaticFiles روی Windows + dispatch متد دلخواه)، `1.3.0/1.3.1` (path poisoning + DoS در `request.form()`).
- هیچ نسخهٔ امنی در `<1.0.0` وجود ندارد ⇒ گزینه‌ها: (الف) ارتقای `fastapi` به نسخه‌ای که starlette 1.x را می‌پذیرد، (ب) پذیرش ریسک با کنترل‌های جبرانی (اعتبارسنجی Host، محدودیت حجم body در nginx، عدم استفاده از `StaticFiles` روی Windows).
- تصمیم لازم است؛ بدون آن هر ارتقای starlette نصب را می‌شکند.

### ۴.۲ `lxml` (DEPV-03) — major bump

- XXE: پیکربندی پیش‌فرض `iterparse()` / `ETCompatXMLParser()` اجازهٔ خواندن فایل محلی را می‌دهد (CVSS 3.1: `C:H`).
- سه کتابخانهٔ `finpy-tse`، `tehran-stocks`، `tse-utils` نسخهٔ `4.9.4` را قفل کرده‌اند؛ ارتقا به `6.1.0` نیاز به آزمون پارسرهای Codal/BrsApi دارد.
- گزینهٔ جبرانی موقت: هر جا XML از منبع بیرونی پارس می‌شود، `resolve_entities=False` و `no_network=True`.

### ۴.۳ `xlsx` (DEPV-11) — بدون fix

- دو advisory High بدون نسخهٔ وصله در registry؛ پروژهٔ SheetJS نسخه‌های وصله‌شده را خارج از npm منتشر می‌کند.
- `rg "xlsx"` در `frontend/src` فقط پسوند فایل (`.xlsx` در `accept` و متن UI) را نشان می‌دهد و هیچ `import/require` ای از کتابخانه وجود ندارد ⇒ وابستگی مرده است.
- رفع پیشنهادی: حذف از `frontend/package.json` (بدون جایگزین).

---

## ۵) برنامهٔ رفع پیشنهادی (اجرا نشده)

**فاز ۱ — پچ‌های بدون تغییر رفتار (production):**
```
# frontend
npm i next@16.2.11 @sentry/nextjs@10.75.2 postcss@8.5.23
# python (بازتولید lock با uv، سپس نصب از lock)
#   aiohttp>=3.14.4, brotli>=1.2.1, certifi>=2026.10.19, opentelemetry-api>=1.45.1
uv pip compile requirements.txt -o requirements.lock --python-version 3.11 \
  --override requirements-overrides.txt
```
سپس `npm run build`، `npm test` (تست‌های dates.ts طبق قرارداد پروژه قرمز می‌مانند) و `pytest tests/gold_desk tests/unit`.

**فاز ۲ — پاک‌سازی dev-only:** `npm i -D vite@8.3.3 vitest@4.1.12 js-yaml@4.3.2 browserslist@4.28.7` و هم‌راستاسازی `undici/fast-uri/nanoid/zod/source-map-js/baseline-browser-mapping` از طریق `npm audit fix`.

**فاز ۳ — حذف `xlsx`** از `frontend/package.json` (DEPV-11) و اطمینان از سبز ماندن build.

**فاز ۴ — نیازمند تصمیم:** `lxml 6.1.0` (DEPV-03) و زنجیرهٔ `fastapi/starlette` (DEPV-02).

**فاز ۵ — بستن DEPV-22:** `requirements.lock` تنها منبع نصب در CI و Docker شود و اختلاف venv محلی با آن با نصب مجدد از lock رفع شود.

---

## ۶) راستی‌آزمایی

- بازاجرای همین اسکن پس از هر فاز: OSV روی lock ها؛ انتظار: نبود DEPV-01/04/05/06/07/09/10.
- `pytest tests/gold_desk tests/unit -q` و `npm run build && npm test` باید سبز بمانند (به‌جز ۲ شکست پذیرفته‌شدهٔ `dates.test.ts`).
- برای DEPV-02 تا زمانی که BLOCKED است، کنترل جبرانی: اعتبارسنجی `Host` در nginx و سقف حجم body.

---

## ۷) تغییرات اعمال‌شده

هیچ. این run فقط ممیزی و برنامهٔ رفع تولید کرده است؛ هیچ وابستگی، lock، `package.json`، Dockerfile یا کد تغییر نکرد.
