# ممیزی عملکرد — فاز صفر

**اصل:** بدون اندازه‌گیری، «بهبود» اعلام نمی‌شود. اعداد زیر روی همین ماشین (Windows، Python 3.11.9، Node 24.16) و در تاریخ 2026-10-26 گرفته شده‌اند.

---

## 1. اندازه‌گیری‌های واقعی

| # | سنجه | نتیجه | روش |
|---|---|---|---|
| P-01 | import سرد اپ (۷۱۴ route) | **۶۰.۴s** | اولین `from apps.api.app import app` |
| P-02 | import گرم اپ | **۲۳.۶۴s / ۲۴.۸۷s** (دو اجرا) | پروسه جدید، کش دیسک گرم |
| P-03 | تعداد ماژول import‌شده | **۲۹۸۲** | `python -X importtime` |
| P-04 | build فرانت | **≈۵ دقیقه** (compile ۲.۱min + TS 90s + صفحات) | `npm run build`، EXIT=0 |
| P-05 | `tsc --noEmit` | **۹۰s** در build | خروجی Next |
| P-06 | Vitest | **۱۰۰.۸۸s** برای ۵۸۳ تست/۵۵ فایل | `npx vitest run` |
| P-07 | unit backend (بدون ml/performance) | **۷۲۱.۸۶s** برای ۶۳۹۷ تست | `pytest tests/unit` |
| P-08 | gold suite | **۱۱۰.۰۲s** برای ۴۳۵ تست | `pytest tests/gold_desk` |
| P-09 | RSI (۴۰۰ کندل) | **۳۸۹ µs/call** | ۲۰۰۰ تکرار |
| P-10 | ATR (۴۰۰ کندل) | **۲۶۵ µs/call** | ۲۰۰۰ تکرار |
| P-11 | MACD (۴۰۰ کندل) | **۲۳۴ µs/call** | ۲۰۰۰ تکرار |
| P-12 | Black-Scholes | **۴۱۸ µs/call** | ۲۰۰۰ تکرار |

**تفسیر:** محاسبات تک‌دارایی hotspot نیستند (زیر ۰.۵ms). گلوگاه قابل‌اثبات، **زمان startup** است (P-01/P-02) که با ۲۹۸۲ ماژول و import سنگین هم‌راستاست.

---

## 2. بک‌اند — نقاط پرهزینه (اندازه‌گیری‌نشده)

| مورد | شاهد | وضعیت |
|---|---|---|
| import همه endpointها در startup | `apps/api/router.py` importهای داخل تابع `setup()`؛ ۷۱۴ route | **تأییدشده** (P-01/P-02) |
| health/freshness | `freshness._probe` برای ۱۳ منبع، هر کدام **۲ query** (`MAX` + `COUNT`) → ۲۶ query در هر گزارش | **مشکوک** (S-07)؛ روی جدول بزرگ می‌تواند کند باشد |
| admin dashboard | توضیح `pyproject.toml:127-128`: اسکن ~**۵.۵ میلیون ردیف** | **تأییدشده در مستند پیکربندی**، زمان اندازه‌گیری نشد |
| connection pool | `pool_size=20`, `max_overflow=30` | پیکربندی معقول؛ مصرف واقعی اندازه‌گیری نشد |
| batch insert سینک | `batch_size` در `SyncService` | پیاده‌سازی موجود؛ throughput اندازه‌گیری نشد |
| N+1 query | بررسی سیستماتیک انجام نشد | **بررسی‌نشده** |
| endpoint latency | سرور اجرا نشد | **اندازه‌گیری نشد** |
| Redis hit rate | Redis تأیید نشد | **اندازه‌گیری نشد** |
| صف/job backlog | jobها اجرا نشدند | **اندازه‌گیری نشد** |

---

## 3. فرانت‌اند

| مورد | شاهد | وضعیت |
|---|---|---|
| ۱۵۲ صفحه، ۳۰۸ فایل با `"use client"` | شمارش | حجم زیاد؛ code-splitting توسط Next انجام می‌شود |
| virtualization | **۰** مورد | **ریسک** برای جدول‌های بزرگ (options/funds/codal) |
| bundle size | Turbopack اندازه چاپ نکرد | **اندازه‌گیری نشد** |
| refetch intervals | هوک‌های بازار ۱۵s–۱۲۰s | طراحی موجود؛ بار واقعی اندازه‌گیری نشد |
| تصاویر | ۱۱ `<img>` | ریسک LCP؛ اندازه‌گیری نشد |
| React Query Devtools | در `src` استفاده نشده | بدون هزینه production |

---

## 4. مقایسه با هدف (پیشنهادی، نه تعهد)

| سنجه | فعلی | هدف پیشنهادی فاز ۴ | شرط اندازه‌گیری |
|---|---|---|---|
| startup | ۲۳.۶–۶۰.۴s | < ۱۰s | همان سخت‌افزار، ۳ اجرا |
| p95 `/gold/snapshot` | نامعلوم | < 500ms | DB واقعی + داده warm |
| p95 `/options/live/chain` | نامعلوم | < 800ms | DB واقعی |
| freshness report | نامعلوم | < 300ms | جدول‌های واقعی |
| build فرانت | ≈۵min | بدون رگرسیون > ۲۰٪ | CI |

این اهداف پیشنهادی‌اند و در فاز صفر تأیید نشده‌اند.

---

## 5. پیشنهادهای مبتنی بر شاهد (بدون تغییر کد در این فاز)

1. **startup:** پروفایل import با `-X importtime` (۲۹۸۲ ماژول)؛ انتقال importهای سنگین endpointها به lazy؛ اندازه‌گیری مجدد با ۳ اجرا. (مالک ۳)
2. **freshness:** کاهش ۲۶ query به یک query تجمیعی یا cache کوتاه؛ اندازه‌گیری روی جدول واقعی. (مالک ۱)
3. **جدول‌های بزرگ:** افزودن pagination سمت سرور یا virtualization فقط پس از اندازه‌گیری. (مالک ۲)
4. **تصاویر:** ارزیابی `next/image` برای crypto. (مالک ۲)
5. **endpoint latency:** افزودن middleware زمان‌بندی موجود (لاگ `... -> 200 (0.06s)`) برای جمع‌آوری p50/p95. (مالک ۳)

---

## 6. پروفایل startup و کاهش import (T15 — اجرا شد)

### 6.1. روش اندازه‌گیری

```bash
GOLD_API_TOKEN_SALT=... venv/Scripts/python.exe -X importtime -c "import apps.api.app"
GOLD_API_TOKEN_SALT=... venv/Scripts/python.exe -c "import time; s=time.perf_counter(); import apps.api.app; print(time.perf_counter()-s)"
```

خروجی خام: `_audit_tmp/importtime_before.txt` و `importtime_after.txt` (خارج از درخت مستندات).

### 6.2. یافته‌ها (قبل از تغییر)

| مورد | مقدار |
|---|---|
| کل import سرد `apps.api.app` | **۴۰.۸۶s** / ۲۹۸۲ ماژول (یک اندازه‌گیری) |
| `integrations` (زنجیره eager) | **۱.۶۴s** — با وارد کردن `apps/api/metrics` همه آداپترها (OTel/gRPC، S3، queue، search، notifications) لود می‌شدند |
| `ml.models` | ۲.۳۲s |
| `backtesting.engine` | ۰.۹۰s (از طریق endpointهای bکتست) |
| `scipy` (optimize+stats) | ۱.۹۱s |
| `pandas` | ۱.۸۵s |
| `bs4` + `html5lib` | ۰.۷۰s |
| پروفایل `cProfile` | ۱۳.۶s در `builtins.eval` (ارزیابی annotationهای pydantic/typing) + ۸.۰s خواندن/کامپایل کد |

### 6.3. تغییر اعمال‌شده (کم‌ریسک، قابل برگشت)

`integrations/__init__.py` و `integrations/observability/__init__.py` از importهای eager به export تنبل (PEP 562، `__getattr__`) تغییر کردند. نام‌های عمومی دقیقاً همان ۲۶ نام قبلی هستند و `from integrations import X` بدون تغییر کار می‌کند.

**قبل/بعد اندازه‌گیری‌شده:**

| معیار | قبل | بعد |
|---|---|---|
| `import integrations` | ۱.۶۴s | **۰.۰۲۶s** |
| `integrations.observability.otel_exporter` پس از import کامل اپ | لود می‌شد | لود نمی‌شود (تا اولین استفاده از `OTelExporter`) |

صرفه‌جویی قطعی: **~۱.۶s** در هر بوت (برای هر مصرف‌کننده `integrations`).

### 6.4. آنچه عمداً تغییر نکرد

- `ml.models` همچنان از طریق `services.inference_service` / `training_service` که endpointها import می‌کنند لود می‌شود؛ انتقال آن به lifespan فقط ظاهری بود و صرفه واقعی نداشت، پس تغییر `apps/api/app.py` برگشت داده شد.
- `backtesting/scipy/pandas/bs4` از ماژول‌های endpointها می‌آیند که در `Router.setup()` وارد می‌شوند. تنبل‌کردن آن‌ها یعنی بازطراحی نحوه mount کردن routeها (خارج از دامنه فاز ۰).
- هیچ endpoint یا رفتاری تغییر نکرد؛ ۸۲ تست هدفمند (observability، cache، alert، news health) **passed** شد.

### 6.5. آنچه ادعا نمی‌شود

- هیچ عدد bundle size، p95 endpoint یا query time ثبت نشد.
- مجموع زمان کل import پس از تغییر بین **۲۴.۱s تا ۳۷.۳s** در سه اجرا نوسان داشت؛ این نوسان از اثر تغییر (۱.۶s) بزرگ‌تر است، پس **کاهش کل زمان بوت ادعا نمی‌شود** — فقط کاهش مؤلفه `integrations` که مستقیم اندازه‌گیری شد.
- هزینه ساختاری باقی‌مانده (۲۹۸۲ → ۲۶۹۹ ماژول، ۷۱۴ route، ~۱۴s ارزیابی annotation) با lazy import حل نمی‌شود و نیازمند بازطراحی route/pydantic در فازهای بعد است.
