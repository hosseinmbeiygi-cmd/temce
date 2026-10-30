# Baseline — وضعیت تحویل‌گرفته‌شده پروژه

**تاریخ ثبت:** 2026-10-26، پیش از هر تغییر در کد.
**مخزن:** `https://github.com/hosseinmbeiygi-cmd/temce.git` (remote `origin`).
**مسیر محلی:** `C:\Users\Iran\Desktop\temce` (bash: `/c/Users/Iran/Desktop/temce`).
**شاخه:** `integration/golddesk-fixes`.
**HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` — 2026-10-26 09:48:51 +0330.

این فایل فقط «وضعیت لحظه تحویل» را ثبت می‌کند؛ تحلیل در اسناد دیگر است.

---

## 1. وضعیت Git

| مورد | مقدار |
|---|---|
| tracked تغییرکرده | ۱۰ فایل (`git diff --stat`: 302 insert / 14 delete) |
| untracked | ۳۳ مسیر |
| `InkGist` | ` m` (dirty) — در `git submodule status` ثبت نشده؛ مخزن تودرتو/جدا است |
| stash | ۳ مورد (`stash@{0..2}`) — دست نخورد |
| branchهای محلی | ۳۰+ شاخه، شامل `fix/backend`, `fix/engine`, `feature/gold-platform` |
| commit/merge/push در این ممیزی | **انجام نشد** |

فهرست کامل تغییرات در `MASTER_READINESS_REPORT.md` §9 آمده است. هیچ `reset --hard`, `checkout --`, `clean` یا حذف فایل کاربر اجرا نشد.

---

## 2. محیط اجرا

| ابزار | نسخه | وضعیت |
|---|---|---|
| OS | Windows 11 (Git Bash) | — |
| Python (قابل استفاده) | **3.11.9** در `venv/Scripts/python.exe` | وابستگی‌ها نصب |
| Python (`.venv`) | 3.14.6 | **ناقص**: `fastapi` و `pytest` ندارد |
| Node.js | 24.16.0 | — |
| npm | 11.13.0 | — |
| FastAPI | 0.128.8 | نصب‌شده |
| Pydantic | 2.12.5 | نصب‌شده |
| SQLAlchemy | 2.0.51 | نصب‌شده |
| pandas / numpy / scipy | 2.3.3 / 1.26.4 / 1.15.3 | نصب‌شده |
| pytest / ruff / mypy | 9.1.1 / 0.15.17 / 2.1.0 | نصب‌شده |
| xgboost | 3.2.0 | نصب‌شده (روی Windows در تست timeout می‌دهد) |

نسخه‌های بالا از `importlib.metadata` خوانده شده‌اند، نه از فایل requirements.

---

## 3. ساختار و مقیاس (شمارش واقعی)

| مورد | عدد | روش |
|---|---|---|
| API route مونت‌شده | **714** | `app.routes` |
| ماژول endpoint | **85** | `ls apps/api/endpoints/*.py` |
| صفحه فرانت (`page.tsx`) | **152** | `find frontend/src/app -name page.tsx` |
| صفحه gold | **22** | همان، زیر `app/gold` |
| فایل Python/TS/TSX | `apps` 179، `src` 73، `core` 168، `services` 269، `domain` 219، `brsapi` 75، `frontend/src` 472 | walk |
| فایل تست | ۵۶۲ در `tests`، ۵۳ در `frontend/src/__tests__` | walk |
| migration | **86** | `ls migrations/versions` |
| قبولی تست collect | ۷۴۷۸ از ۷۵۲۷ | `pytest --collect-only` |

---

## 4. وابستگی‌ها و پیکربندی

| فایل | نقش |
|---|---|
| `pyproject.toml` | packaging، ruff، mypy، pytest config (`testpaths=tests`, `-m "not needs_db"`, `asyncio_mode=auto`) |
| `requirements.txt` | وابستگی‌های runtime بدون pin دقیق (`>=`) |
| `requirements.lock` | قفل ۸.۹KB (میزان پوشش آن بررسی نشد) |
| `requirements-dev.txt`, `requirements-overrides.txt` | dev/override |
| `frontend/package.json` + `package-lock.json` | Next 16.2.9، React 19.2.4، Vitest 4، TS 5 |
| `.env.example` | **۹۳ کلید** شامل `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `AUTH_DISABLED`, `GOLD_API_TOKEN_SALT` |
| `.env` | موجود اما **track نشده** (`.gitignore:19`) |
| `alembic.ini`, `migrations/` | migration |
| `docker-compose.yml` + `.production/.override/.decision-engine/.sandooghyar` | استقرار |
| `Dockerfile`, `Dockerfile.api/worker/frontend/golddesk/...` | ایمیج‌ها |
| `nginx-golddesk.conf` | reverse proxy |
| `k8s/`, `monitoring/`, `prometheus.yml` | عملیات |

---

## 5. سرویس‌های موردنیاز و دسترسی در زمان ممیزی

| سرویس | نیاز | وضعیت واقعی |
|---|---|---|
| PostgreSQL/TimescaleDB | اصلی | **در دسترس** روی `localhost:5432/my_first_db` (لاگ تست gold) |
| Redis | cache/state | **تأیید نشد**؛ کد در نبود آن `null cache` می‌سازد و در لاگ تست دیده شد |
| BrsApi | داده بازار | **در cooldown** (`Suspend.php`, «usage above plan threshold») |
| Codal / IME / TGJU | داده تکمیلی | تست نشد؛ نیاز به شبکه/کلید |
| Telegram | هشدار | تنظیمات موجود؛ ارسال واقعی انجام نشد |
| Sentry | پایش فرانت | بدون `SENTRY_AUTH_TOKEN` غیرفعال |
| حساب کاربری QA | تست authenticated | **در دسترس نبود** |

---

## 6. فرمان‌های اجرا (ثبت‌شده، نه حدس)

```bash
# backend (dev)
venv/Scripts/python.exe main.py            # uvicorn apps.api.app:app

# backend (نیازمند salt)
GOLD_API_TOKEN_SALT=... venv/Scripts/python.exe -m pytest tests/unit ...

# frontend
cd frontend && npm run dev
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
cd frontend && npx eslint src
cd frontend && npm run build

# lint/type backend
venv/Scripts/python.exe -m ruff check .
# mypy: پیکربندی موجود، اجرا نشد
```

**نتیجه واقعی این فرمان‌ها** در `TEST_STRATEGY.md` ثبت شده است. `npm run build` موفق (EXIT=0) و `pytest` بک‌اند با ۹ شکست همراه بود.

---

## 7. CI/CD

| Workflow | کار |
|---|---|
| `.github/workflows/ci.yml` | ruff، unit (Linux + Postgres/Redis)، gold_desk، integration celery، tsc، vitest، build/push ایمیج در main |
| `ci-pr.yml` | بررسی PR |
| `secrets-scan.yml` | gitleaks |
| `decision-engine.yml`, `fund-service.yml`, `release.yml` | سرویس‌های مجزا |

وضعیت آخرین اجرای CI در دسترس نبود؛ فقط پیکربندی خوانده شد. `ruff check .` با ۹۲ خطای زیرمجموعه محلی، احتمالاً قرمز است.

---

## 8. مسائل از پیش موجود (قبل از هر اصلاح)

1. ۹ تست قرمز baseline (۵ BrsApi cooldown، ۲ fixture portfolio، ۱ secret gate، ۱ tick cutoff).
2. رمز هاردکدشده در `tests/e2e/test_gold_session_reload.py:37`.
3. `ruff` ۹۲ خطا شامل ۲ F821.
4. startup ۲۳.۶–۶۰.۴ ثانیه برای ۷۱۴ route.
5. کلید BrsApi در cooldown.
6. `.venv` ناقص با Python 3.14.

این‌ها **قبل از ممیزی** وجود داشتند و در `ISSUE_REGISTRY.md` ردیابی می‌شوند.

---

## 9. اجراهای تکمیلی T13–T15 (پس از baseline اولیه)

| اجرا | فرمان | نتیجه | شاهد |
|---|---|---|---|
| T13 integration (ایزوله) | `_audit_tmp/run_pytest_env.py tests/integration -q -m "not performance"` | **۴۴ passed، ۶ failed، ۴۹.۸s** | `evidence/integration-suite.txt` |
| T13 E2E (ایزوله) | `... tests/e2e -q -m "not performance"` | **۳۵ passed، ۶ failed، ۱ skipped، ۱۹۶.۵s** | `evidence/e2e-suite.txt` |
| T13 celery (پس از رفع نام میزبان) | `... tests/integration/test_celery_chain_broker.py` | **۴ passed، ۱۲.۱۸s** | `evidence/isolated-itest-run.md` |
| T14 پروفایل داده | اسکریپت‌های فقط-خواندنی روی `my_first_db` | NAV=قیمت در ۳۲/۳۲؛ `gregorian_date` = تاریخ اجرا | `DATA_QUALITY_AUDIT.md` بخش ۶ |
| T15 پروفایل startup | `-X importtime` + ۳ اجرای زمان‌بندی‌شده | ۲۶۹۹ ماژول؛ `integrations` ۱.۶۴s → ۰.۰۲۶s | `PERFORMANCE_AUDIT.md` بخش ۶ |

محیط ایزوله: دیتابیس `phase0_it_20261026` (schema-only، ۲۴۰ جدول) + Redis DB 13. **هیچ داده‌ای در دیتابیس اپ تغییر نکرد** (فقط SELECT).

تنها فایل‌های کد تغییرکرده در این مراحل: `integrations/__init__.py` و `integrations/observability/__init__.py` (export تنبل). هیچ تستی برای سبز شدن حذف یا بی‌اثر نشد.

### آنچه هنوز در baseline ثبت نشده

- مقدار secretها (عمداً خوانده/چاپ نشد).
- وضعیت واقعی Redis در production.
- آخرین اجرای CI و نتیجه آن.
- پوشش کامل `requirements.lock` نسبت به محیط.
- اجرای `tests/performance` و `tests/load`.
- تست contract JSON (وجود ندارد — ISSUE-113).
