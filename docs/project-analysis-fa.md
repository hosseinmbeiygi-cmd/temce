# گزارش تحلیل پروژهٔ temce

**تاریخ:** ۲۴ سپتامبر ۲۰۲۶  
**نسخهٔ بررسی‌شده:** `bc9fd2070a4003bbe4de8c888cd676563aa01046`  
**دامنه:** ساختار مخزن فعال، مسیرهای اصلی اجرا، وابستگی‌ها، استقرار، امنیت پایه و آزمون‌های قابل اجرای محلی. در کد مخزن تغییری داده نشده است. این بررسی، ممیزی خط‌به‌خط همهٔ فایل‌ها یا آزمون امنیت نفوذ نیست؛ شاخهٔ `_FRONTEND_BACKEND_COPY/` به‌عنوان کپی تاریخی برای نتیجه‌گیری دربارهٔ کد فعال کنار گذاشته شد.

## جمع‌بندی اجرایی

پلتفرم، سامانهٔ تحلیل دادهٔ بازار ایران با فرانت‌اند Next.js و بک‌اند FastAPI، موتورهای سیگنال/بک‌تست، دریافت‌کننده‌های داده، PostgreSQL/TimescaleDB و Redis است. فرانت‌اند مستقل در این محیط **build** و typecheck می‌شود و ۴۰۸ تست آن می‌گذرند. در مقابل، **API در همین commit به‌علت باقی‌ماندن نشانگرهای merge در روتر import نمی‌شود**؛ نصب وابستگی‌های رسمی Python و فایل‌های Compose پیش‌فرض نیز شکست می‌خورند. بنابراین هیچ ادعایی دربارهٔ سلامت استقرار کامل یا اجرای API نمی‌توان داشت.

## نقشهٔ معماری و جریان داده

1. **رابط:** `frontend/src/app/` شامل مسیرهای App Router، و `frontend/src/lib/api.ts` کلاینت درخواست و مدیریت نشست را پیاده می‌کند. `frontend/next.config.ts:17` درخواست‌های `/api/v1/*` را به بک‌اند proxy می‌کند. نسخهٔ فعلی `frontend/package.json:13` بر Next.js 16 و React 19 استوار است.
2. **API و هویت:** `main.py:7` و `apps/api/app.py:943` ورودی‌های FastAPI هستند. `apps/api/router.py:257` روترها را نصب می‌کند؛ `apps/api/dependencies.py:221` احراز هویت Bearer و کنترل نقش را پیاده می‌کند؛ `apps/api/middleware.py` لایه‌های CSRF، محدودسازی نرخ و امنیت درخواست را تعریف می‌کند.
3. **منطق کسب‌وکار:** `domain/` قراردادها و مدل‌های دامنه، `services/` سناریوهای تجاری، `backtesting/runner.py` نقطهٔ ورود بک‌تست و `ml/` قابلیت‌های یادگیری ماشین را نگه می‌دارند. `backtesting/costs/iran_costs.py` مرجع محاسبهٔ هزینهٔ معاملات است و محافظ‌های آزمون آن اجرا شدند.
4. **داده و عملیات:** `providers/`، `brsapi/` و `ingestion/` دادهٔ خارجی را دریافت می‌کنند؛ `repositories/` و `core/database.py` دسترسی به PostgreSQL را فراهم می‌کنند؛ `migrations/versions/` تاریخچهٔ Alembic است. `jobs/` و `apps/scheduler/` زمان‌بندی و صف/worker را مدیریت می‌کنند؛ Redis برای صف/کش/قفل استفاده می‌شود.
5. **سرویس‌های جانبی:** `apps/admin/`، `apps/currency_service/` و `apps/decision_engine/` سطوح اجرایی مستقل‌اند؛ `docker-compose*.yml`، Dockerfileهای ریشه و `.github/workflows/` مسیرهای استقرار و CI را تعریف می‌کنند. برای نقشهٔ عمومی از `README.md:123` و `docs/PROJECT_GUIDE.md` استفاده شود؛ `ARCHITECTURE.md:1` عمدتاً معماری زیرسامانهٔ پیش‌بینی BrsApi را شرح می‌دهد، نه کل مخزن.

## یافته‌های اولویت‌دار

### P0 — روتر اصلی به‌علت merge حل‌نشده قابل import نیست

در `apps/api/router.py:223` تا `apps/api/router.py:226` نشانگرهای `<<<<<<<`، `=======` و `>>>>>>>` داخل کد باقی مانده‌اند. `apps/api/__init__.py:1` همین فایل را import می‌کند؛ بنابراین import API، ممیزی auth و گردآوری تست‌های وابسته با `SyntaxError` متوقف می‌شوند. `py_compile` و `compileall` نیز خطا را تأیید کردند. **اقدام:** نشانگرها را حذف و import مربوط به `news_tag_map_admin_router` را حفظ کنید؛ سپس compile، ممیزی auth و suite بک‌اند را دوباره اجرا کنید.

### P0 — نصب رسمی backend از نظر dependency ناممکن است

`requirements.txt:7` به `sqlalchemy>=2.0` نیاز دارد، ولی `requirements.txt:33`، بستهٔ `tehran-stocks>=2.0` را اضافه می‌کند که نسخهٔ ۲٫۰٫۰ آن طبق خروجی resolver به `SQLAlchemy<2.0` نیاز دارد. `pip install -r requirements.txt` با `ResolutionImpossible` شکست خورد. نصب‌های CI در `.github/workflows/ci.yml:85` و build در `Dockerfile.api:6` و `Dockerfile:9` به همین فایل وابسته‌اند. نصب جداگانهٔ `pyproject.toml` تنها زیرمجموعه‌ای بدون این provider را فراهم می‌کند و راه‌حل استقرار نیست. **اقدام:** provider ناسازگار را به نسخهٔ سازگار ارتقا دهید یا آن را پشت adapter/محیط جدا از SQLAlchemy 2 قرار دهید؛ سپس یک lock/آزمون حل وابستگی ایجاد کنید.

### P0 — پیکربندی Docker Compose پیش‌فرض نامعتبر است

`docker-compose.yml:35` سرویس `backend` تعریف می‌کند، در حالی که override خودکار در `docker-compose.override.yml:6` سرویس تازهٔ `api` را **بدون image/build** و در `docker-compose.override.yml:47` سرویس تازهٔ `postgres` را تعریف می‌کند. اجرای `docker compose config --quiet` خطای «service api has neither an image nor a build context» داد. حتی پس از اصلاح نام‌ها، `docker-compose.yml:107` دنبال `frontend/Dockerfile` می‌گردد که وجود ندارد؛ و `docker-compose.yml:38` از `Dockerfile` ریشه استفاده می‌کند که در `Dockerfile:14` به‌جای ASGI، `ingestion.main` را اجرا می‌کند. `Dockerfile.api` و `Dockerfile.frontend` در ریشه وجود دارند ولی در Compose اصلی انتخاب نشده‌اند. **اقدام:** نام‌های مشترک سرویس، build context، Dockerfile و آدرس proxy را در base/override/production هماهنگ کنید؛ اول `docker compose config --quiet` و سپس build و healthcheck را بررسی کنید.

### P1 — دسترسی سرویس‌های توسعه روی تمام واسط‌های میزبان

`docker-compose.yml:12` و `docker-compose.yml:28` گذرواژه‌های پیش‌فرضِ ثابتِ توسعه دارند و `docker-compose.yml:13` و `docker-compose.yml:29` درگاه‌های PostgreSQL و Redis را به‌صورت پیش‌فرض روی میزبان منتشر می‌کنند. این **در صورت اجرا روی میزبان در دسترس شبکه** خطر دسترسی ناخواسته دارد؛ شواهدی از افشای واقعی یا استفادهٔ تولیدی از این Compose به‌دست نیامد. **اقدام:** در توسعه binding را به `127.0.0.1` محدود کنید و برای میزبان‌های مشترک/production مقادیر secret اجباری قرار دهید. تنظیم production جداگانه را نیز ارزیابی کنید.

### P1 — دروازه‌های کیفیت و تنظیمات frontend ناسازگارند

`Makefile:12` و `.github/workflows/ci.yml:96` نتیجهٔ mypy را با `|| true` نادیده می‌گیرند؛ `Makefile:9` lint را با `--fix` روی کد اجرا می‌کند. CI اصلی typecheck فرانت‌اند را اجرا می‌کند اما کل Vitest را اجرا نمی‌کند (`.github/workflows/ci.yml:137`)، در حالی که در بررسی محلی ۴۰۸ آزمون پاس شدند. همچنین `docker-compose.yml:118` متغیر `NEXT_PUBLIC_API_URL` را به `http://backend:8000` تنظیم می‌کند: این آدرس داخلی برای browser معتبر نیست **اگر هنگام build در باندل تزریق شود** و تنظیم runtime به‌تنهایی متغیر عمومی Next.js را در باندل موجود عوض نمی‌کند؛ مسیر `/api/v1` نسبی و `API_URL` سمت سرور را یکپارچه نگه دارید (`frontend/src/lib/api.ts:1`، `frontend/next.config.ts:19`).

### P2 — فرمان‌ها و مستندات از وضعیت کنونی عقب مانده‌اند

`Makefile:31` دستور `python -m jobs.worker` می‌دهد، در حالی که فایل/ماژول وجود ندارد؛ ورودی worker موجود `apps/worker/__main__.py:1` است. آمار معرفی در `README.md:16` (۸۸ صفحه، ۳۹ migration و ۲۵۰ فایل تست) با شمارش فایل‌های trackشدهٔ این checkout (۱۴۶ فایل `page.tsx`، ۶۷ migration، دست‌کم ۳۶۹ فایل `test_*.py` زیر `tests/`) یکسان نیست. ۲۲۶۵ فایل در `_FRONTEND_BACKEND_COPY/` نگهداری می‌شود؛ مرز نسخهٔ فعال و کپی نیاز به شفاف‌سازی دارد. این موارد به‌تنهایی مانع اصلی اجرا نیستند ولی هزینهٔ نگهداری را افزایش می‌دهند.

## نتایج اعتبارسنجی

| بررسی | نتیجه |
|---|---|
| `frontend/`: `npm test -- --run` | **گذشت**؛ ۳۲ فایل و ۴۰۸ آزمون |
| `frontend/`: `npx tsc --noEmit` | **گذشت** |
| `frontend/`: `FRONTEND_BUILD_HEAP_MB=4096 npm run build` | **گذشت**؛ هشدارهای deprecation برای middleware و Sentry |
| بک‌تست: دو تست‌ماژول `test_cost_parity` و `test_engine_runner` | **گذشت**؛ ۳۰ آزمون با Python 3.11.16 و نصب محدود `pyproject.toml` |
| `python -m compileall` روی پکیج‌های اصلی | **شکست**؛ تنها خطای نحوی گزارش‌شده در روتر API |
| `python scripts/check_router_auth.py` و `pytest tests/unit` | **مسدود** در import روتر؛ کل suite و احراز هویت runtime تأیید نشده‌اند |
| `docker compose config --quiet` | **شکست**؛ سرویس `api` ناقص |
| `pip install -r requirements.txt` | **شکست**؛ تعارض حل‌نشدنی SQLAlchemy/provider |

آزمون end-to-end با PostgreSQL/Redis، smoke test سرویس‌های زنده و build واقعی Docker اجرا نشد: قبل از آن باید dependency و Compose و خطای نحوی برطرف شوند. موفقیت build مستقل فرانت‌اند به معنی اتصال آن به API نیست.

## برنامهٔ پیشنهادی

1. **ابتدا:** تعارض merge در روتر را برطرف و compile/auth-audit/test collection را سبز کنید.
2. **سپس:** ناسازگاری dependency را در نصب رسمی رفع و مسیر CI/backend Docker را دوباره بررسی کنید.
3. **بعد:** base/override/production Compose را به سرویس‌های واحد و Dockerfileهای درست متصل کرده و healthcheckها را به کار اندازید.
4. **در ادامه:** دسترسی درگاه‌های توسعه و متغیرهای عمومی فرانت‌اند را ایمن و یکدست کنید؛ mypy و Vitest را به دروازهٔ قابل اتکای CI تبدیل کنید.
5. **پس از تثبیت:** Makefile، آمار README و وضعیت کپی تاریخی را به‌روزرسانی کنید.
