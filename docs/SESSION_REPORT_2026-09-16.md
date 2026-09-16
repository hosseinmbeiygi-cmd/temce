# گزارش جلسه — امنیت، حقوقی، پاکسازی و Observability

> تاریخ: ۱۶ سپتامبر ۲۰۲۶
> دامنه: **۲۰ کامیت** روی `main` (بعد از `1797019b`)
> حجم: ۸۰+ فایل تغییر یافته، خالص: کاهش چند هزار خطی از ریپو

---

## ۱️⃣ پاکسازی امنیتی (مشکلات #۱، #۲، #۴، #۱۰، #۱۳ گزارش ممیزی ساختاری)

**کامیت:** `51e9bebc` — ‎۴۶ فایل، ‎−۵,۱۰۰ خط

| اقدام | جزئیات |
|-------|--------|
| Untrack فایل‌های حساس | `.env.production` (با SECRET_KEY و DATABASE_URL واقعی)، `t.bin`، `checkpoint.json`، `.dmcode-memory.json` |
| حذف plans هوش مصنوعی | ۱۴ فایل `.zcode/plans/` و `.mimocode/plans/` (منطق داخلی کسب‌وکار و promptها) |
| حذف ۲۷ اسکریپت دیباگ | `_nav_*`، `_mig_*`، `_pc*` و بقیه پیشونددارهای روت |
| سخت‌سازی `.gitignore` | الگوهای جدید: `.env.*` (با استثنای `!.env.example`)، `*.bin`، `/checkpoint.json`، `/_*`، `.zcode/`، `.dmcode-memory.json` |

⚠️ **اقدام باز و حیاتی:** `.env.production` از initial commit در تاریخچه git است. تا زمان rotate کردن SECRET_KEY و پسورد DB و پاکسازی history با `git filter-repo`، این secretها باید لو-رفته فرض شوند.

---

## ۲️⃣ حقوقی (مشکل #۱۱)

| کامیت | محتوا |
|-------|-------|
| `e3e42971` | `LICENSE` (MIT، مالک Hossein Mbeiygi) + ارجاع `license = { file = "LICENSE" }` در `pyproject.toml` |
| `54849c92` | بازه کپی‌رایت `2024-2026` در LICENSE + تکمیل بخش «📄 مجوز» README |

---

## ۳️⃣ Data Layer (مشکل #۸ و بخشی از #۹)

### حذف چهار ماژول مرده — `7876f4f8` (‎−۱,۷۲۷ خط)

`database_handler.py`، `postgresql_client.py`، `data_repo.py`، `datenrepo.py` — چهار نسخه دستی psycopg2 که **هیچ import ای در کل کدبیس نداشتند** (تأیید با git grep). لایه واقعی: `core/database.py` (SQLAlchemy async) + پکیج `repositories/` + Alembic.

باگ‌های واقعی که با حذف‌شان از بین رفت:
- `postgresql_client.py`: interpolation خام شناسه‌های SQL (ریسک injection)
- `database_handler.py`: `ON CONFLICT (instrument_id)` غلط (UNIQUE واقعی `(instrument_id, date)` است) + `NameError` در `handle_scraping_error`
- `data_repo.py`/`datenrepo.py`: `fetchone()` بعد از INSERT بدون `RETURNING` → crash در runtime

### بازیابی value-added — `32b2603f` + `8a1ce3e3`

`export_all_to_csv` به `scripts/db_export.py` منتقل شد با:
- credentials از `core.settings` (قرارداد `scripts/_db.py`) به‌جای env هاردکد
- quote کردن نام جدول‌ها
- CLI کامل با `argparse` (`--help`، `-o`، `--batch-size`) — تست‌شده بدون اتصال به DB

### حذف create_tables.py — `1727dfec` (بقیه مشکل #۹)

مکانیزم دوم ساخت schema بدون هیچ ارجاعی؛ `database_auto_create_tables` در `core/database.py` + Alembic منبع واحد حقیقت ماندند.

---

## ۴️⃣ امنیت فرانت: CSP nonce-based — `fcde9e53`

مشکل تأییدشده گزارش دوم (#۱): CSP قبلی `script-src 'self' 'unsafe-inline'` داشت که حفاظت XSS را عملاً بی‌اثر می‌کرد.

**پیاده‌سازی:**
- تولید nonce یک‌بارمصرف base64 به‌ازای هر request در `middleware.ts`
- جایگزینی placeholder `{NONCE}` در هدر production + ارسال nonce با هدر `x-nonce`
- مصرف nonce در `layout.tsx` برای اسکریپت theme bootstrap
- `'strict-dynamic'` برای اجازه bootstrap Next.js از روی اسکریپت nonce دار
- هاردنینگ اضافه: `object-src 'none'`، `base-uri 'self'`، `frame-ancestors 'self'`
- CSP توسعه عمداً relaxed ماند (`unsafe-eval` برای source map و `ws://` برای وب‌سوکت بازار زنده) — مستند در کامنت کد

**اعتبارسنجی end-to-end:** build موفق (با heap 6GB) + سرور production واقعی با curl:
- ✅ nonce هدر == nonce اسکریپت theme در یک response (اجرا می‌شود)
- ✅ دو درخواست → دو nonce متفاوت
- ✅ redirect روت محافظت‌شده (`/admin → /auth/login`) هم CSP دارد
- ✅ تست‌های middleware: ۲۳/۲۳ (شامل تست جدید تازگی nonce در prod)

---

## ۵️⃣ Observability — Sentry دوطرفه (مشکل تأییدشده #۹ گزارش دوم)

| کامیت | سمت | جزئیات |
|-------|-----|--------|
| `1bc83bf7` | Backend | `sentry-sdk[fastapi]>=2.0` در requirements؛ `core/observability_sentry.py` با init محافظت‌شده (first در lifespan)، integrations: FastAPI/Asyncio/Redis/SQLAlchemy، `sentry_traces_sample_rate` جدید در settings، `before_send` که هدرهای Authorization/Cookie/X-API-Key را می‌شوید |
| `d23bd5c7` | Frontend | `@sentry/nextjs@10.74` + چهار touchpoint رسمی (`instrumentation.ts` lazy، `instrumentation-client.ts`، `sentry.edge.config.ts`، `withSentryConfig` روی next.config) + `captureException` در `error.tsx` و `global-error.tsx` |
| `5d1d2fc2` | ابزار | whitelist `frontend/.env.sentry.example` (قاعده `.env*` محلی فرانت override می‌کرد) |
| `0d8e4404` | استقرار | `SENTRY_DSN` + `SENTRY_TRACES_SAMPLE_RATE` در docker-compose (backend/worker/currency/frontend)، روی anchor `x-app-prod` فایل production، و در ConfigMap+Deployment ک8s decision-engine |

**اصل طراحی:** بدون DSN (پیش‌فرض) هیچ SDK ای import نمی‌شود و اپ کاملاً Sentry-free/offline-safe می‌ماند. DSN یک کلید ingest محدود write-only است → جای آن ConfigMap است نه Secret. آپلود sourcemap فقط در CI با `SENTRY_AUTH_TOKEN`.

---

## ۶️⃣ Rate Limit روی forecast (بستن آخرین مورد باز گزارش دوم)

### بررسی (`f171b3eb`)

روت‌های `/forecast` و `/forecast-engine` «باز» نبودند — با `_optional_auth` ثبت شده بودند، دقیقاً الگوی همه read-onlyهای عمومی؛ فرانت مهمان (صفحات markets/predictions) به آن‌ها وابسته است. ادعای گزارش سطح endpoint را دیده بود؛ dependency در سطح `include_router` بود.

حفره واقعی: هیچ entry در `endpoint_rate_limits` نداشتند → anonymous با queryهای DB/Redis-backed محدود نشده بود. **اصلاح:** هر دو prefix با سقف 30/min (middleware با longest-prefix، ساب‌پث‌ها را هم می‌گیرد).

### تست رگرسیون — `b07f7fb7`

`tests/unit/api/test_forecast_rate_limit.py` — ۱۱ تست در ۳ کلاس:
- **Config:** ثبت هر دو prefix + تمایز از fallback عمومی (جوهره باگ)
- **Path matching:** longest-prefix، ارث‌بری ساب‌پث، fallback برای مسیر نامرتبط
- **Dispatch واقعی:** ۳۰ موفق → ۴۲۹ با `Retry-After: 60` و `X-RateLimit-Limit`؛ bucket جداگانه per-IP

---

## ۷️⃣ اعتبارسنجی Build و اصلاح Heap — `975a77cf` + `09d94f3f`

### اعتبارسنجی end-to-end با build و SSR واقعی

پیاده‌سازی‌های CSP و Sentry فقط در سطح کد نماندند — با `next build` کامل و سرور `next start` واقعی اعتبارسنجی شدند:

| بررسی | نتیجه |
|-------|-------|
| تطابق nonce هدر CSP با اسکریپت theme در یک response (`/` و `/markets`) | ✅ MATCH |
| تازگی nonce بین requestها | ✅ |
| redirect روت محافظت‌شده (`/admin/users`) با CSP کامل | ✅ 307 |
| hook `onRouterTransitionStart` در باندل client | ✅ کامپایل شده |
| **نبود placeholder DSN در باندل‌ها** (بدون DSN، باندل Sentry-free) | ✅ |

### رفع هشدار build — `975a77cf`

export کردن `onRouterTransitionStart = Sentry.captureRouterTransitionStart` از `instrumentation-client.ts` — هشدار `ACTION REQUIRED` بیلد را رفع و navigation tracking فرانت را فعال کرد.

### wrapper دائمی heap — `09d94f3f`

`next build` در فاز TypeScript-check با heap پیش‌فرض OOM می‌شد (`Committing semi space failed`). راه‌حل `NODE_OPTIONS=... npm run build` در اسکریپت فقط POSIX است و روی cmd.exe/PowerShell شکست می‌خورد — این پروژه روی ویندوز بیلد می‌شود.

**راه‌حل:** `frontend/scripts/build-with-heap.js` (بدون dependency):

```json
"build": "node scripts/build-with-heap.js"
```

- اگر NODE_OPTIONS از قبل heap دارد → دست نمی‌زند (CI override)
- وگرنه `--max-old-space-size=6144` ست می‌کند (قابل تغییر با `FRONTEND_BUILD_HEAP_MB`)
- **اعتبارسنجی هر دو سناریو با build کامل:** بدون NODE_OPTIONS خارجی → موفق ۷۶s/۱۴۲ صفحه؛ با NODE_OPTIONS=4096 → موفق و محترم شمرده‌شده
- **مستندسازی:** `FRONTEND_BUILD_HEAP_MB` با توضیح پیش‌فرض/اولویت در `frontend/.env.sentry.example` ثبت شد (`ce2d6d2`)

### روش تکرارپذیر اعتبارسنجی (runbook)

برای بازتولید اعتبارسنجی در آینده (بعد از هر تغییر CSP/middleware/layout):

```bash
# 1) Build — wrapper خودش heap را تضمین می‌کند
cd frontend && npm run build

# 2) سرور production روی پورت موقت
npx next start -p 3199 &
sleep 8

# 3) nonce هدر CSP و اسکریپت theme باید در «یک» response برابر باشند
curl -s -D /tmp/h.txt http://localhost:3199/ -o /tmp/b.html
H=$(grep -i "content-security-policy" /tmp/h.txt | grep -oE "nonce-[A-Za-z0-9+/=]+" | head -1)
B=$(grep -oE '<script nonce="[A-Za-z0-9+/=]+"' /tmp/b.html | head -1 | grep -oE 'nonce="[^"]+' | cut -d'"' -f2)
[ "nonce-$B" = "$H" ] && echo MATCH || echo MISMATCH

# 4) تازگی nonce: دو درخواست → دو مقدار متفاوت
curl -sI http://localhost:3199/ | grep -ioE "nonce-[A-Za-z0-9+/=]+" | head -1
curl -sI http://localhost:3199/ | grep -ioE "nonce-[A-Za-z0-9+/=]+" | head -1

# 5) روت محافظت‌شده: 307 به login با CSP کامل
curl -sI http://localhost:3199/admin/users | grep -E "HTTP|location|content-security-policy"

# 6) بهداشت باندل Sentry (بدون DSN نباید هیچ اثری باشد)
grep -rl "sentry.io/project-id" .next/static/chunks/ && echo LEAK || echo CLEAN

# 7) خاموشی سرور موقت
ps aux | grep "next start" | grep -v grep | awk '{print $1}' | xargs -r kill
```

نتیجه اجرای این runbook در ۲۰۲۶-۰۹-۱۶: همه مراحل ✅ (جزئیات در جدول بالا).

**اسکریپت آماده:** این runbook حالا قابل اجراست — `frontend/scripts/validate-csp.sh` (کامیت `2d1b2a55`):

```bash
# بعد از npm run build — همه بررسی‌ها با یک دستور، exit code برای CI
bash frontend/scripts/validate-csp.sh [port]
```

## ۸️⃣ چرخش Secrets — `3c6103b1`

اجرای گام ۱ از اقدامات بعدی (جزئیات کامل: `docs/SECRETS_ROTATION_2026-09-16.md`):

- **`SECRET_KEY`:** ۶۴ کاراکتر hex تصادفی در `.env` (قبلی placeholder بود)
- **رمز Postgres محلی:** ۲۷ کاراکتر تصادفی — هم در `.env` (سازگار در `DATABASE_URL`/`DB_PASSWORD`/`PG_PASSWORD`) هم **روی خود سرور** با `ALTER USER`
- **docker-compose dev:** سه رمز هاردکد لو-رفته در history (`securepassword123`، `redissecure456`، `dev-shared-queue-token`) → `${DEV_*:-default}` قابل override

**راستی‌آزمایی واقعی:** اتصال DB با رمز قدیمی → ALTER → اتصال با رمز جدید ✅ · `init_database()` + `SELECT 1` ✅ · JWT با کلید جدید sign/verify ✅ · توکن امضاشده با کلید قدیمی → `InvalidSignatureError` (همه توکن‌های قبلی باطل شدند — اثر موردانتظار) ✅

**⚠️ اقدام دستی باقی‌مانده:** ترمینال/IDE متغیرهای process-level قدیمی تزریق می‌کند → ری‌استارت ترمینال لازم است؛ رمز production DB و `BRSAPI_API_KEY` فقط توسط مالک قابل چرخش‌اند.

## ۹️⃣ پایان جلسه

تمام ۲۰ کامیت روی `main` محلی‌اند (**push نشده**). همه تغییرات fund-related (سرویس‌های `fund_*`، `jobs/definitions/*`، `funds_v2.py`، کامپوننت‌ها و تست‌هایشان، `docs/funds/`) طبق تصمیم، برای جلسه بعد دست‌نخورده ماندند.

## 🔟 مستندسازی — `36df10ed` + `8b2bb614`

همین گزارش: `docs/SESSION_REPORT_2026-09-16.md` — جمع‌بندی تمام کارهای جلسه، سرنوشت ادعاهای دو ممیزی، و نقشه راه اقدامات بعدی.

---

## 📊 جمع‌بندی ممیزی‌ها

### گزارش اول (ساختاری) — ۱۳ ادعا
| وضعیت | موارد |
|-------|-------|
| ✅ حل شد در این جلسه | #۱ (env) · #۲ (t.bin) · #۴ (فایل‌های `_`) · #۸ (data layer) · #۹ (DDL هاردکد + create_tables) · #۱۰ (AI plans) · #۱۱ (LICENSE) · #۱۳ (checkpoint) |
| ⏳ باقی‌مانده | #۳ (`_FRONTEND_BACKEND_COPY` — ۲,۲۶۵ فایل، تصمیم معماری جدا) · #۵/#۶/#۷ (۹ Dockerfile + ۵ compose + k8s/Swarm/Compose همزمان) · #۱۲ (فعال‌سازی Security features گیت‌هاب) |

### گزارش دوم (فنی) — ۹ ادعا
| وضعیت | موارد |
|-------|-------|
| ✅ واقعی و پیاده شد | #۱ CSP (nonce، فراتر از پیشنهاد) · #۹ Sentry (دوطرفه) |
| ✅ حفره واقعی بسته شد | #۲ forecast (عمومی عمدی + rate limit جدید + تست رگرسیون) |
| ❌ از قبل موجود (ادعای غلط) | #۳ Redis cache · #۵ pool_size · #۶ Trivy/CodeQL در CI · #۸ Error Boundaries |
| ❌ رد شد (نامربوط) | #۴ Indexing (بدون شواهد) · #۷ Kafka/ES/AWS (jump زیرساختی ناسازگار) |

---

## 📜 لیست کامل کامیت‌ها

```
3c6103b1 chore(security): rotate leaked dev credentials — compose defaults + rotation doc
8b2bb614 docs: update session report — include report commit itself and fix commit count
09d94f3f build(frontend): guarantee next build heap via cross-platform wrapper
975a77cf feat(observability): add onRouterTransitionStart hook for App Router nav tracking
36df10ed docs: add Persian session report for 2026-09-16 (security, legal, cleanup, observability)
b07f7fb7 test(api): regression tests for forecast endpoint rate limiting
0d8e4404 feat(observability): plumb SENTRY_DSN through compose and k8s manifests
f171b3eb feat(api): rate-limit public forecast endpoints (30/min per IP)
5d1d2fc2 chore: whitelist frontend/.env.sentry.example in frontend/.gitignore
d23bd5c7 feat(observability): add @sentry/nextjs to the frontend (env-guarded)
1bc83bf7 feat(observability): wire optional Sentry into the API (sentry-sdk[fastapi])
fcde9e53 feat(security): switch CSP to per-request nonce + strict-dynamic (no unsafe-inline scripts)
8a1ce3e3 feat(scripts): add argparse CLI (--help, -o, --batch-size) to db_export.py
1727dfec chore(db): remove root create_tables.py — second schema mechanism (audit #9)
32b2603f feat(scripts): recover db_export.py from removed postgresql_client.py
7876f4f8 chore(db): remove four dead data-access modules from repo root
54849c92 docs(legal): set copyright year range and expand license section in README
e3e42971 chore(legal): add MIT LICENSE and reference it in pyproject metadata
51e9bebc chore(security): remove sensitive & temp files from tracking, harden .gitignore
```

---

## 🚀 اقدامات پیشنهادی بعدی

1. ~~**فوری:** rotate کردن `SECRET_KEY` و credentials دیتابیس~~ ✅ انجام شد — `3c6103b1` (باقی‌مانده دستی: رمز production DB، ری‌استارت ترمینال)
2. پاکسازی history با `git filter-repo` (destructive — بعد از rotate)
3. تصمیم معماری برای `_FRONTEND_BACKEND_COPY` (merge/حذف/archive)
4. کاهش ۹ Dockerfile و ۵ compose به ساختار واحد + انتخاب یک استراتژی deployment
5. فعال‌سازی Dependabot، Secret Scanning و CodeQL در تنظیمات گیت‌هاب (مشکل #۱۲)
6. ~~اصلاح heap build فرانت~~ ✅ انجام شد — `scripts/build-with-heap.js` (کامیت `09d94f3f`)
