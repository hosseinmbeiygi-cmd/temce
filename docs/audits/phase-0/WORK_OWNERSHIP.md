# مالکیت کار و قواعد ضدتداخل — فاز صفر

**Baseline:** `90597e05` روی `integration/golddesk-fixes`.
**وضعیت working tree در زمان ممیزی:** ۱۰ فایل tracked تغییرکرده (۳۰۲ insert / ۱۴ delete)، ۳۳ مسیر untracked، و ساب‌ماژول `InkGist` dirty. این تغییرات **متعلق به کار جاری طلا (فاز ۰/۱/۲)** است و باید پیش از شروع شاخه‌های اصلاحی، توسط مالک خودش commit یا stash شود؛ هیچ دستیاری حق reset/checkout آن را ندارد.

---

## 1. دستیار اول — بک‌اند، داده و محاسبات

**دامنه مالکیت (مسیرهای واقعی):**

| مسیر | توضیح |
|---|---|
| `apps/api/endpoints/*.py` | همه endpointها به‌جز `router.py` (مالکیت مشترک با دستیار ۳) |
| `apps/api/pagination.py`, `apps/api/error_handlers.py` | لایه ارائه بک‌اند |
| `services/**` | `quant_signal_orchestrator.py`, `feature_engine.py`, `options_analytics.py`, `gold/*` |
| `domain/**` | `options/pricing.py`, `margin_engine.py`, `var_calculator.py`, `tree_pricing.py`, سایر دامنه‌ها |
| `core/indicators.py`, `core/database.py`, `core/cache*`, `core/time*` | محاسبات و لایه داده مشترک |
| `brsapi/**` | client، repositories، `sync_service.py`، jobs، models |
| `src/gold_desk/{pricer,phase1,phase2,phase1_schemas,phase2_schemas,api,constants}.py` | موتور و سطوح طلا |
| `migrations/versions/*.py` | **پیاده‌سازی** با بازبینی اجباری دستیار ۳ |
| `tests/unit/{domain,services,brsapi,options,ml}/**`، `tests/gold_desk/**` | تست‌های مالکیت خود |

**خارج از دامنه:** فایل‌های فرانت، `apps/api/router.py`، Docker/CI/nginx.

---

## 2. دستیار دوم — فرانت‌اند، جدول‌ها و عملکرد

**دامنه مالکیت:**

| مسیر | توضیح |
|---|---|
| `frontend/src/app/**` | همه صفحات و layoutها، شامل `app/gold/**` |
| `frontend/src/components/**` | جدول، نمودار، فرم، `DataTrustBadge` |
| `frontend/src/hooks/**` | `useMarketData.ts`, `useDebugLogs.ts`, … |
| `frontend/src/lib/api.ts` | کلاینت HTTP مرورگر (قرارداد با دستیار ۳) |
| `frontend/src/lib/goldApi.ts` | قرارداد مصرف طلا (قرارداد با دستیار ۱) |
| `frontend/src/types/**` | `gold.ts`, `phase1.ts`, `phase2.ts` (قرارداد با دستیار ۱) |
| `frontend/src/__tests__/**` | تست‌های Vitest/RTL |
| `frontend/next.config.ts`, `frontend/vitest.config.ts`, `frontend/eslint.config.mjs` | پیکربندی فرانت (هماهنگی با دستیار ۳ برای production) |
| `frontend/src/middleware.ts`, `frontend/src/lib/sound/**`, `frontend/public/**` | مالکیت فرانت |

**خارج از دامنه:** هر فایل Python، schema بک‌اند، Docker.

---

## 3. دستیار سوم — امنیت، معماری و یکپارچگی

**دامنه مالکیت:**

| مسیر | توضیح |
|---|---|
| `apps/api/router.py` | مونتاژ و گاردهای احراز هویت — **تک‌مالک** |
| `apps/api/app.py`, `apps/api/auth.py`, `apps/api/dependencies.py`, `apps/api/middleware.py` | احراز هویت، CORS، rate limit |
| `core/config/**` | تنظیمات و پیش‌فرض‌های امن |
| `docker-compose*.yml`, `Dockerfile*`, `.dockerignore` | استقرار |
| `k8s/**`, `nginx-golddesk.conf`, `monitoring/**`, `prometheus.yml` | عملیات |
| `.github/workflows/**`, `.gitleaks.toml`, `.pre-commit-config.yaml` | CI و اسکن |
| `docs/contracts/**`, `docs/data-sources-*.md` | قراردادهای مشترک |
| `tests/integration/**`, `tests/e2e/**`, `tests/unit/api/test_*security*`, `scripts/check_*.py` | یکپارچگی و امنیت |
| `migrations/**` (بازبینی، نه پیاده‌سازی) | سازگاری schema |
| `docs/audits/phase-0/**` | مالکیت این مجموعه مستندات در فاز ۰ |

**خارج از دامنه:** اصلاح منطق مالی یا UI؛ فقط بازبینی و ثبت ایراد.

---

## 4. فایل‌های مشترک (Coordination files)

| فایل | مالک اصلی | هم‌مالک/بازبین | قاعده |
|---|---|---|---|
| `apps/api/router.py` | دستیار ۳ | دستیار ۱ | هر تغییر mount/auth نیازمند ثبت در `API_CONTRACTS.md` و تست mount |
| `src/gold_desk/api.py` | دستیار ۱ | دستیار ۳ | تغییر route جدید = به‌روزرسانی `test_phase0_mount.py` + قرارداد |
| `frontend/src/lib/api.ts` | دستیار ۲ | دستیار ۳ | تغییر رفتار خطا/۴۰۱ نیازمند تست Vitest و تأیید قرارداد |
| `frontend/src/lib/goldApi.ts` + `types/gold.ts` | دستیار ۲ | دستیار ۱ | تغییر فیلد = هماهنگی با schema بک‌اند |
| `frontend/src/types/phase1.ts` / `phase2.ts` | دستیار ۲ | دستیار ۱ | آینه schema؛ تغییر هم‌زمان |
| `docs/contracts/*.json` | دستیار ۳ | دستیار ۱ و ۲ | منبع قرارداد؛ تغییر نیازمند PR مجزا |
| `migrations/versions/*` | دستیار ۱ | دستیار ۳ | بازبینی اجباری؛ rollback مستند |
| `docker-compose*.yml` + `.env.example` | دستیار ۳ | دستیار ۱ | هر متغیر جدید در `.env.example` مستند شود |
| `tests/gold_desk/test_phase0_mount.py` | دستیار ۱ | دستیار ۳ | منبع truth مسیرهای gold |
| `pyproject.toml` / `requirements*.txt` | دستیار ۳ | دستیار ۱ | وابستگی جدید فقط با تأیید |

---

## 5. قواعد هماهنگی (غیرقابل‌مذاکره)

1. هر فایل یک مالک اصلی دارد؛ مالک در جدول بالا مشخص است.
2. تغییر فایل مشترک فقط با ثبت تصمیم در `DECISIONS_AND_BLOCKERS.md` و اعلان در گزارش فاز.
3. تغییر API یا schema ابتدا در `API_CONTRACTS.md` پیشنهاد، سپس پیاده‌سازی.
4. دستیار ۳ در اصلاحات عادی بک‌اند/فرانت دخالت نمی‌کند؛ فقط بازبینی و ابزار.
5. هیچ دستیاری فایل دیگری را «بازنویسی کامل» نمی‌کند؛ فقط patch محدود.
6. اگر ایرادی چند ماژول را درگیر کند، مالک اصلی طبق جدول ISSUE_REGISTRY تعیین می‌شود و بقیه زیرکار می‌گیرند.
7. هر دستیار گزارش خودش را در `docs/audits/phase-N/` می‌نویسد؛ گزارش دیگری را ویرایش نمی‌کند.
8. `git reset --hard`, `checkout --`, حذف گسترده و بازنویسی تاریخچه ممنوع است.
9. تا زمان تأیید مالک محصول، merge/push/release انجام نمی‌شود.
10. هیچ ادعای «تست پاس شد» بدون خروجی فرمان در گزارش ثبت نمی‌شود.

---

## 6. روش جلوگیری از تداخل عملی

- قبل از هر تسک: `git status --short` و تأیید اینکه فایل هدف در دامنه مالک است.
- هر تسک یک شاخه جدا با نام `fix/...` یا `audit/...` (بخش RUNBOOK).
- تفکیک commit بر اساس دامنه: commitهای بک‌اند، فرانت و infra قاطی نشوند.
- تغییرات schema/قرارداد در commit مستقل با پیام `contract:`.
- پیش از merge: `git diff --name-only main...HEAD` باید فقط زیرمجموعه دامنه باشد.
- تعارض در فایل مشترک: تصمیم با مالک اصلی + تست پس از حل؛ ثبت در DECISIONS.
