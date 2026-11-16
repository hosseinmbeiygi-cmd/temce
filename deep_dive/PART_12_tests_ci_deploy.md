# قسمت ۱۲ — تست، CI، استقرار و پایش

| | |
|---|---|
| **مبنای اندازهگیری** | `105002d7` — **اولین بار از قسمت ۰۵ که HEAD جابهجا شد** (قسمت ۱۱ روی `73a6c52d` اندازهگیری شد، سپس دو کامیت همزمان `e8c83049` و `105002d7` وارد شد). تمام اعداد این قسمت روی `105002d7` و فایلهای روی دیسک اندازهگیری شدند. |
| **وضعیت worktree** | **۲۴ فایل Dirty**. تازهترین رانش: `frontend/src/lib/api.ts` **اصلاحشده** (M) — تنها تغییر آن اضافهشدن `_sessionRestore = null` در `clearAuth()` و `storeAuth()` (۳۹۳ → ۳۹۵ خط)، یک رفع اشکال race مربوط به بازیابی نشست است و **هیچیک از یافتههای `UIF-*` قسمت ۱۱ را تحت تأثیر قرار نمیدهد**. بقیه فایلها untrackedاند: alert engineجدید (`services/alert_engine/`, `models/alert_engine.py`, `migrations/versions/0127_alert_engine.py`, تستهای آن) و جابهجایی اسناد. |
| **تعهد** | فقط فایلهای Markdown تحلیلی ساخته/ویرایش شدند. **هیچ فایل کد، پیکربندی، تست، compose، مهاجرت یا سندی تغییر نکرد.** |
| **یادداشت روش** | جستجوها مسیرمحدود و با مستثنا کردن `.freebuff/worktrees/`, `node_modules`, `.next`, `.git`, `__pycache__`, `venv`, `.turbo`, `.pytest_cache`, `codal_env` انجام شدند. **هیچ تستی اجرا نشد، workflowای اجرا نشد، استقاری صورت نگرفت** — تمام نتایج ایستااند. |
| **پیشوند یافتهها** | `QLT-*` (Quality / Delivery) — چون `QA-*`, `DEP-*`, `CICD-*` در مخزن تداخل دارند (DEP مربوط به قسمت ۰۳ است). |
| **زبان** | فارسی (هماهنگ با سری) |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقطخواندنی)

| درخت / فایل | تعداد | خط | یادداشت |
|---|---:|---:|---|
| `tests/` | **۷۴۴ فایل** | **۱۳۹٬۳۴۱** | ۷۱۲ فایل `.py` |
| `tests/unit/` | **۵۲۲** | — | — |
| `tests/gold_desk/` | **۵۱** | — | توسط مرحلهٔ جداگانه در CI اجرا میشود |
| `tests/integration/` | **۱۹** | — | فقط ۱ فایل صریحاً در CI صدا زده میشود |
| `tests/e2e/` | **۱۱** | — | **هیچ workflowای آن را اجرا نمیکند** |
| `tests/performance/` | **۹** | — | **هیچ workflowای آن را اجرا نمیکند** |
| root `tests/test_*.py` | **۳۷** | — | اکثراً خارج از مسیرهای CI |
| `.github/workflows/` | **۶ workflow** | **۱٬۶۷۵** | `ci.yml` 474 · `ci-pr.yml` 253 · `decision-engine.yml` 397 · `fund-service.yml` 264 · `release.yml` 209 · `secrets-scan.yml` 27 |
| `monitoring/` | **۲۷ فایل** | **۲٬۰۹۷** | ۲۲ ماژول Python |
| `scripts/` | **۳۵۸** | **۵۷٬۹۷۴** | شامل `quality_ratchet.py` (186 خط) |
| `migrations/versions/` | **۱۱۲** | **۱۱٬۶۵۹** | شامل `0126` (ترacked) و `0127` (untracked) |
| `Dockerfile*` | **۹** | — | ۸ تای آنها `HEALTHCHECK` و `USER` غیر root دارند |
| `docker-compose*` | **۵** | — | `docker-compose.production.yml` 202 خط |

نکتهٔ شمارش: لاگ اصلی ۱۶۰ لایهای و گزارش قسمت ۱۰ اعداد متفاوتی DID (مثلاً «۶۶۴ تست» در README سری) — عدد دقیق روی دیسک **۷۴۴ فایل / ۱۳۹٬۳۴۱ خط** است.

---

## ۲ — ردیابی جریان اجرا

### ۲‑الف — مسیر CI

```
push/PR → ci.yml (path-filtered)
  ├─ lint: ruff → import-linter ratchet → mypy ratchet → mypy strict(security)
  │        → prod-check gate → hadolint ×5 → npm ci → tsc → vitest → secret scan ×2
  ├─ docs: mermaid syntax
  ├─ test: postgres16 + redis7
  │        ├─ cost parity + engine runner D1 (two key files)
  │        ├─ pytest tests/unit  (addopts: -m "not needs_db")
  │        ├─ pytest tests/gold_desk
  │        └─ celery chain integration (one file)
  ├─ needs-db: timescaledb + redis
  │        ├─ alembic upgrade head
  │        ├─ alembic downgrade -1 → upgrade head    ← DB-06 finally exercised
  │        └─ pytest -m needs_db tests/unit tests/gold_desk tests/test_db.py
  └─ build (main push only, needs [lint, test]): 5 images + trivy SARIF

tag v*.*.* → release.yml
  ├─ validate: semver parse + CHANGELOG warning
  ├─ build (needs [validate]): 6 images incl. `ingestion`
  ├─ release (needs [validate, build]): GitHub release
  └─ deploy (needs [build, release]): ssh + docker compose up -d   ← NO test job in chain
```

### ۲‑ب — مسیر پایش

```
apps/api/middleware.py:34 MetricsMiddleware
  → integrations/observability/prometheus_exporter.py (singleton)
       ├─ inc("http_requests_total", labels method+route)
       ├─ observe("http_request_duration_seconds")
       ├─ inc("http_responses_total", labels status)
       └─ export_text()   ← legacy renderer, unquoted labels
apps/api/endpoints/monitoring.py:26 GET /metrics → exporter.export_text()
apps/api/endpoints/monitoring.py:33 GET /data-quality
       └─ exporter.gauge(...) / exporter.counter(...)  ← READS THAT CREATE ZERO SERIES
monitoring/ (27 files)
       └─ only monitoring.health has an external consumer
          (services/monitoring_service.py:8)
docker-compose.production.yml
       └─ healthcheck: api, postgres, nginx only
          worker / scheduler / admin / redis / frontend: NONE
```

---

## ۳ — یافتهها

**توزیع شدت:** ۲ بحرانی · ۶ بالا · ۶ متوسط · ۲ کم = **۱۶ یافته**.

| شناسه | شدت | خلاصه |
|---|---|---|
| `QLT-01` | 🔴 بحرانی | `release.yml` deploy را به تست گره نزده است؛ کامیت تگشده بدون CI سبز مستقر میشود |
| `QLT-02` | 🔴 بحرانی | `/data-quality` ورودیهای خود را میسازد: `counter()` یک سری صفر ایجاد میکند → `all_checks_passed` همیشه true |
| `QLT-03` | 🟠 بالا | export_text() قالب معتبر Prometheus نیست ولی `/metrics` دقیقاً همان را برمیگرداند |
| `QLT-04` | 🟠 بالا | ۲۱ از ۲۲ ماژول `monitoring/` بدون مصرفکنندهٔ خارجی |
| `QLT-05` | 🟠 بالا | auto-skip `needs_db`_ci سبز را با صفر تست اجراشده ممکن میسازد |
| `QLT-06` | 🟠 بالا | مسیر timezone thread در CI، برخلاف توصیهٔ صریح کد |
| `QLT-07` | 🟠 بالا | دایرکتوریهای `e2e/`, `performance/` و ۳۷ تست ریشه در هیچ workflowای اجرا نمیشوند |
| `QLT-08` | 🟠 بالا | production compose فقط ۳ سرویس از ۸ سرویس healthcheck دارد |
| `QLT-09` | 🟡 متوسط | ماتریس تصاویر CI و release متفاوت است (currency/golddesk/decision-engine بیرون ماتریس اصلی) |
| `QLT-10` | 🟡 متوسط | ratchet baseline عملاً خالی است (`mypy: {}`) |
| `QLT-11` | 🟡 متوسط | اسرار و certهای production در مخزن وجود ندارند (انتظار میرود، ولی استقرار را وابسته میکند) |
| `QLT-12` | 🟡 متوسط | production compose فاقد سرویس `currency` است در حالی که frontend به آن rewrite میکند |
| `QLT-13` | 🟡 متوسط | alert engineجدید untracked است و path-filter CI شامل آن modelها نمیشود |
| `QLT-14` | 🟡 متوسط | ۴۹ فراخوانی `pytest.skip(` در ۷۱۲ فایل تست |
| `QLT-15` | 🟢 کم | `mypy strict` فقط دو ماژول را پوشش میدهد (security + gold ratchet) |
| `QLT-16` | 🟢 کم | deploy_url placeholder `https://your-domain.com` باقی مانده است |

### 🔴 `QLT-01` — deploy به هیچ تستی گره نخورده است

```yaml
# release.yml:21-22
validate:  # فقط semver + warning for CHANGELOG
# :69-72
build: needs: [validate]
# :138-141
release: needs: [validate, build]
# :183-190
deploy:
  needs: [build, release]
  if: needs.validate.outputs.prerelease == 'false'
  # ssh ... docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

**تحلیل:** release workflow **هیچ job تستی ندارد** و `ci.yml` را workflow_call نمیکند. کامیتی که مستقیم تگ `v1.2.3` میخورد — حتی اگر وارد CI نرفته باشد (مثلاً فقط فایلهایی خارج از path-filter ci.yml تغییر کرده باشد) — تصویر میسازد، product release میکند و **خودکار production را آپدیت میکند**. تنها Gateها semver و prereleaseاند. بهعبارت OTHER: «quality gate» یک convention است، نه الزام ساختاری. نقطهٔ مقابل: `ci.yml:406` `needs: [lint, test]` دارد، یعنی تیم میداند چگونه گره بزند — فقط release.yml این کار را نکرده است.

**اثر:** possibility of deploying untested commit; دور زدن تمام ratchet/test gates با یک tag.

---

### 🔴 `QLT-02` — `/data-quality` ورودیهایش را خودش میسازد

```python
# integrations/observability/prometheus_exporter.py:35-46
def counter(self, name, labels=None) -> float:
    key = self._metric_key(name, labels)
    self._counters.setdefault(key, 0.0)   # ← SIDE EFFECT: create zero series
    return self._counters[key]
def gauge(self, name, labels=None) -> float:
    return self._gauges.get(key, 0.0)     # ← absent gauge reads as 0
```
```python
# apps/api/endpoints/monitoring.py:38-49
staleness = exporter.gauge("data_staleness_seconds")           # کسی set نمیکند → 0
requests_5xx = exporter.counter("http_responses_total", labels={"status": "5xx"})
                                                              # middleware آن را با labels
                                                              # method+route+status مینویسد،
                                                              # نه فقط status → سری جداست → 0
checks = {
    "null_check": staleness < 300,          # 0 < 300 → True
    "checksum": exporter.gauge("data_checksum_valid") > 0,   # 0 > 0 → False
    "staleness": staleness < 300,           # True
    "price_limit": exporter.gauge("price_limit_breaches") == 0,  # True
}
# :62  "all_checks_passed": all(checks.values())
```

صرفنظر از عدم تطابق labelها، self-created seriesها باعث میشوند endpoint **هم منبع داده را تولید کند و هم حکم دهد** — الگوی دقیق `BT-02` / `MLD-02` / `DOM-02` در لایهٔ پایش. نتیجه: `all_checks_passed` اساساً تابعی از مقادیر پیشفرض است، نه وضعیت واقعی.

---

### 🟠 `QLT-03` — `/metrics` قالب ناسازگار برمیگرداند

```python
# integrations/observability/prometheus_exporter.py:96-101
def export_text(self) -> str:
    """Legacy renderer (unquoted labels) kept for compatibility/parity tests.
    Use :meth:`export_prometheus` for anything a Prometheus server will
    scrape: this legacy output is not valid exposition format once labels
    are present."""
```
```python
# apps/api/endpoints/monitoring.py:26-30
@router.get("/metrics", ...)
async def metrics_endpoint():
    exporter = get_prometheus_exporter()
    return PlainTextResponse(exporter.export_text())   # ← دقیقاً همان متد منسوخ
```

کد **خودش** هشدار داده است که خروجی معتبر نیست؛ با وجود این endpoint زنده از آن استفاده میکند. `:135` متد `export_prometheus` وجود دارد ولی توسط endpoint صدا زده نمیشود. nginx `/metrics` را مستقیم به backend هدایت میکند (`deploy/nginx/nginx.conf:66`)، پس Scrape واقعی همین خروجی ناسازگار را میگیرد.

---

### 🟠 `QLT-04` — پایش نوشتهشده وصلنشده

از ۲۲ ماژول Python در `monitoring/`:
```
22 ماژول  →  ۱ مورد مصرف خارجی: monitoring.health در services/monitoring_service.py:8
```
ماژولهای **بدون مصرفکننده** شامل: `drift.py` (192 خط)، `fx_monitor.py` (279)، `gold_monitor.py` (242)، `incidents.py` (135)، `job_monitor.py` (87)، `data_freshness.py` (108)، `model_performance.py` (38)، `sla.py` (42)، `tracer.py` (117)، `alerts/manager.py` (58)، `alerts/rules.py` (123)، `dashboards/*` (217)، `metrics/collector.py` + `service.py` (123).

همچنین `apps/api/router.py:209` صریحاً مینویسد:
```
# * monitoring — no Prometheus scrape is configured, and mounting
```
روتر `/metrics` در `apps/api/endpoints/monitoring.py` تعریف شده، ولی include آن در router دیده نمیشود — مسیر `/metrics` از middleware استثنا شده (`middleware.py:608`) و nginx آن را مستقیم میپذیرد، بنابراین route ممکن است عملاً male دسترسباشد. **مرز:** اجرای زنده انجام نشد؛ این استنتاج ایستا از نبود include و کامنت صریح است.

---

### 🟠 `QLT-05` — `needs_db`_ci سبز با صفر تست

```python
# tests/conftest.py:169-194
def pytest_collection_modifyitems(config, items):
    if _DB_AVAILABLE is None: _DB_AVAILABLE = _is_postgres_reachable()
    if _DB_AVAILABLE: return
    for item in items:
        if item.get_closest_marker("needs_db"):
            item.add_marker(pytest.mark.skip(reason="PostgreSQL is not reachable ..."))
```
```yaml
# ci.yml:328-400  needs-db job with real timescaledb service
- name: Run needs_db tests
  run: pytest -m needs_db tests/unit tests/gold_desk tests/test_db.py --timeout=300 -v
```

اگر service دیتابیس بالا نیاید ولی steps بعدی ادامه پیدا کنند (timeout/اتصال)، تمام موارد `needs_db` علامت skip میخورند و pytest **بدون line stimulus** exit 0 میدهد. چون `--strict-markers`/`--strict-config` و `--fail-on-skipped` تنظیم نشدهاند، job بهصورت سبز علامت میخورد. hypertableها و تستهای ۵٫۵ میلیون ردیف (دلیل وجود marker) دقیقاً همانهایاند که قرار بود اجرا شوند.

---

### 🟠 `QLT-06` — timeout method برخلاف توصیهٔ کد

```toml
# pyproject.toml:156-165
# * run the long suite on Linux (CI or WSL) with ``--timeout-method=signal``
#   so only the offending test dies;
timeout_method = "thread"
```
```yaml
# ci.yml:279-284
pytest tests/unit --cov=. --timeout=60 -x -v        # signal override نشده
# ci.yml:296-298
pytest tests/gold_desk --timeout=120 -v             # signal override نشده
# ci.yml:392-394
pytest -m needs_db ... --timeout=300 -v             # signal override نشده
```

CI اوبونتو است (Linux، SIGALRM موجود)، ولی هیچ مرحلهای `--timeout-method=signal` نمیزند. بنابراین رفتار pre-posted همان thread method است که کد آن را «کشتن کل فرایند هنگام گیر کردن یک تست» توصیف میکند. توصیه نوشتهشده وصل نشده است — نمونهٔ کلاسیک سری.

---

### 🟠 `QLT-07` — تستهایی که هیچ workflowای اجرا نمیکند

```
tests/e2e/            ۱۱ فایل    → بدون pytest e2e در هیچ workflow
tests/performance/     ۹ فایل    → بدون pytest performance در هیچ workflow
root tests/test_*.py  ۳۷ فایل    → pytest tests/unit و pytest -m needs_db آنها را پوشش نمیدهند
```
مراحل موجود: `tests/unit`, `tests/gold_desk`, `tests/integration/test_celery_chain_broker.py`, `tests/test_db.py` (با marker) و دو فایل parity. مارکرهای `e2e` و `performance` در `pyproject.toml:175-176` تعریفاند ولی -m مربوطه وجود ندارد. علاوهبراین `pyproject.toml:155` `addopts = ["--capture=no", "-m", "not needs_db"]` است، بنابراین حتی `pytest tests/` معمولی ۳۸ فایل needs_db را حذف میکند. **پوشش واقعی CI «زیرمجموعهای از درخت تست» است، نه کل درخت.**

---

### 🟠 `QLT-08` — healthcheck فقط ۳ سرویس از ۸

`docker-compose.production.yml` healthcheck دارد: `api`, `postgres`, `nginx`. **ندارد:** `admin`, `worker`, `scheduler`, `redis`, `frontend`.

نتیجه: orchestrator نمیداند worker/scheduler مردهاند یا نه — در حالی که قسمت ۰۶ نشان داد تمامJobها فقط توسط scheduler اجرا میشوند (`JOB-01`, `EX-13`). مرگ scheduler با `status: ok` کلی دیده میشود. علاوهبراین `/health/full` (قسمت ۰۱) حتی با Redis و BrsApi مرده `status: ok` میدهد، بنابراین همان healthcheck موجود api هم سیگنال ضعیفی است.

---

### 🟡 `QLT-09` — ماتریس تصاویر ناسازگار

| سرویس | `ci.yml` build | `release.yml` build | Dockerfile وجود دارد |
|---|---|---|---|
| api / frontend / worker / admin / scheduler | ✅ | ✅ | ✅ |
| ingestion | ❌ | ✅ (`Dockerfile`) | ✅ |
| currency | ❌ | ❌ | ✅ |
| golddesk | ❌ | ❌ | ✅ |
| decision-engine | ❌ | ❌ | ✅ (workflow جداگانه) |

trece تقویم: `Dockerfile.frontend` فاقد build arg است (`UIF-01`) و حتی در ci.yml فقط hadolint میشود، نه با متغیرهای production بیلد میشود — یعنی **هیچ مرحلهای قرارداد بیلدزمان فرانتاند را راستیآزمایی نمیکند**.

---

### 🟡 `QLT-10` — ratchetها روی baseline خالی

```json
// ci/quality_baseline.json
{ "imports": {... 2 keys ...}, "mypy": {}, "mypy-strict-gold": {} }
```

CI مینویسد:
```
# src/gold_desk strict starts at 221 errors; the ratchet blocks new ones.
python scripts/quality_ratchet.py check --tool mypy-strict-gold
```
اما baseline مربوطه `{}` است. بسته به نحوهٔ مقایسه در `scripts/quality_ratchet.py`، یا تمام ۴۶ خطای فعلی «جدید» محسوب میشوند (پس CI باید قرمز باشد) یا منطق ratchet اجازهٔ عبور میدهد. **مرز:** رفتار دقیق بدون اجرا نمیتوان قطعی کرد؛ تنها واقعیت قابل تأیید ناسازگاری بین کامنت (221 خطای آغازین) و baseline خالی است. همان الگوی «عدد در سند با عدد در تنظیمات فرق میکند».

---

### 🟡 `QLT-11` — وابستگی استقرار به فایلهای خارج از مخزن

```
deploy/nginx/certs/            MISSING  (ولی compose آن را mount میکند)
secrets/postgres_password.txt  MISSING  (docker secret)
secrets/secret_key.txt         MISSING  (docker secret)
secrets/api_key.txt            MISSING  (docker secret)
.env.production                EXISTS   (غیر track شده انتظار میرود)
```

اینها برای production طبیعیاند (اسرار نباید commit شوند)، ولی دو نکتهٔ مشخص: (۱) release deploy **هیچ مرحلهای برای ایجاد/اعتبار سنجی این فایلها ندارد** — صرفاً ssh میزند و `docker compose up`؛ (۲) `deploy/nginx/nginx.conf:36` هدر HSTS را حتی روی HTTP plaintext تنظیم میکند (کامنت میگوید browsersignore میکنند).

---

### 🟡 `QLT-12` — سرویس currency در production غیروجود، router آن زنده

ادامهٔ `UIF-01`: `next.config.ts:23` fallback production به `http://currency:8002` میرود، ولی `docker-compose.production.yml` **سرویسی با نام currency نداند** ( serviceها: api, admin, worker, scheduler, redis, postgres, nginx, frontend). در مقابل `Dockerfile.currency` (62 خط، healthcheck + USER) و سرویس `currency` در `docker-compose.yml` توسعه وجود دارد. یعنی image ساخته شده، ولی استقرار production آن را شامل نمیشود — دومین مثال «ابزار ساختهشده وصلنشده» در استقرار.

---

### 🟡 `QLT-13` — alert engineجدیدOutside CI path-filter

فایلهای untracked توسط فرایند همزمان:
```
services/alert_engine/          10 فایل / ۲٬۵۰۲ خط
models/alert_engine.py          migration 0127
tests/unit/alert_engine/        ۲ فایل / ۴۴۴ خط
tests/integration/test_alert_engine_lifecycle.py
frontend/src/components/alerts/ ۱ فایل / ۵۰۸ خط
```
روتر وصل است (`router.py:227,352-354`) ولی جستجو در `ci.yml` و `ci-pr.yml` کلمهٔ `alert` را **صفر بار** مییابد. مارکر `tests/**` عموماً در path-filterها وجود دارد (`**/*.py`)، پس بعد از کامیت شدن CI اجرا میشود — ولی تا آن موقع کدی که ۲٬۵۰۲ خط production logs دارد خارج از هر gate ریسک است. **مرز:** untracked به معنای «توسط من تغییریافته» نیست؛ من فقط وضعیت را مستند میکنم.

---

### 🟡 `QLT-14` — پراکندگی skip در تستها

در ۷۱۲ فایل تست:
```
pytest.skip(         ۴۹ occurrence
skipif                ۳
pytest.mark.skip      ۱
xfail                 ۱
```
تعدادی مربوط به دسترسپذیری DBاند (قابل توجیه)، ولی برخی تستها عملاً «نوشتهشده ولی اجرانشده»اند. همان الگوی تکراری سری در لایهٔ تست.

---

### 🟢 `QLT-15` — پوشش strict محدود

CI تنها `mypy core/security --strict` (blocking) و `mypy-strict-gold` (ratchet) دارد. بقیهٔ ۱۲۰۹ فایل تحلیلشده توسط import-linter و راتچ mypy معمولی پوشش میگیرند. نکتهٔ مثبت: وجود ratchet بهجای freezing کامل — بدهی قدیمی مسدودکننده نیست، ولی رشد جدید بسته میشود.

---

### 🟢 `QLT-16` — placeholder در تنظیمات استقرار

```yaml
# release.yml:187-189
environment:
  name: production
  url: https://your-domain.com
```
GitHub Environment وجود یک gate دستی فراهم میکند (خوب)، ولی URL یک placeholder است — لینک deploy در release page به الگوی pre-fixture reference میدهد، نه آدرس واقعی.

---

## ۴ — حدسهای ردشده

| حدس | نتیجه | شاهد |
|---|---|---|
| «CI فاقد تست فرانتاند است» | **رد** — `vitest run` در `ci.yml:170` و `tsc --noEmit` در :165 وجود دارد | بند ۲‑الف |
| «ratchet importها صفر است» | **رد** — baseline imports دو کلید شامل «Analyzed 1209 files, 6467 dependencies» | `ci/quality_baseline.json` |
| «هیچ migration round-trip تست نمیشود» | **رد** — `ci.yml:381-385` صریحاً downgrade -1 سپس upgrade head | بند ۲‑الف |
| «cache_hit /Legal disclaimerاز Part 11 تحت تأثیر api.tsجدید قرار گرفتند» | **رد** — diff تنها `_sessionRestore = null` را به `clearAuth`/`storeAuth` اضافه کرده | بند ۰ (worktree) |
| «CI requirements.lock را path-filter نکرده» | **رد** — `requirements.lock` در فهرست مسیرها وجود دارد | `ci.yml` path list |
| «تمام درخت monitoring بدون مصرف است» | **رد** — `monitoring.health` توسط `services/monitoring_service.py:8` مصرف میشود | بند ۲‑ب |
| «healthcheck وجود ندارد» | **رد** — ۳ سرویس healthcheck واقعی دارند | `QLT-08` |
| «gold_desk تست در CI اجرا نمیشود» | **رد** — مرحلهٔ جداگانه `pytest tests/gold_desk` در :296 | `ci.yml` |

---

## ۵ — نقاط قوت تأییدشده

1. **CI گسترده و طبقهای است:** ruff + import ratchet + mypy ratchet + strict security + prod-check gate + ۵ hadolint + tsc + vitest + دو مرحله secret scan (blocking/advisory) + Mermaid syntax + چهار مرحله تست بکاند + migration round-trip + trivy SARIF.
2. **DB-06 بالاخره بسته شد:** `ci.yml:381-385` مسیر downgrade را بهصورت real اجرا میکند — نقطهٔ مقابل قسمت ۰۴ «هیچ جای مخزن downgrade صدا زده نمیشد».
3. **I5 بسته شد:** vitest و GoldDesk تستها به CI اضافه شدند (کامنتهای صریح :167 و :290).
4. **S3 secret scan:** blocking(scope-owned) + advisory(full-tree) با توضیح دقیق بدهی تاریخی — طراحی بالغ.
5. **Quality ratchet بهجای prohibition:** بدهی قدیمی مسدود نمیشود، ولی تخلفات تازه_fail_ میکنند.
6. **8 از 9 Dockerfile دارای non-root USER و healthcheckاند.**
7. **release SBOM/provenance + semver tag + GitHub environment gate (دستی) وجود دارد.**
8. **تست هوشمند:** `needs_db` auto-skip با بررسی واقعی اتصال و کپی session-level — حتی اگر گیت ضعیف باشد، پیادهسازی تمیز است.

---

## ۶ — خوشههای ریسک تازه

| خوشه | یافتهها | شدت | اثر مرکب |
|---|---|---|---|
| **AM — استقرار بدون گیت کیفیت** | `QLT-01`, `QLT-09`, `QLT-11`, `QLT-16` | 🔴 بحرانی | tag → build → release → deploy بدون تست؛ ماتریس تصاویر ناسازگار؛ اسرار خارج از مخزن بدون validation |
| **AN — پایش self-referential** | `QLT-02`, `QLT-03`, `QLT-04`, `QLT-08` | 🔴 بحرانی | endpoint حکم را از ورودیهایی میگیرد که خودش ساخت؛ exporter قالب ناسازگار؛ ۲۱ ماژول مرده؛ ۵ سرویس without healthcheck |
| **AO — پوشش تست توهمی** | `QLT-05`, `QLT-06`, `QLT-07`, `QLT-10`, `QLT-13`, `QLT-14` | 🟠 بالا | skip خاموش، timeout thread، ۲۰ فایل خارج از CI، baseline خالی، alert engine untracked |

**پیوند با سری:** `AM` ادامهٔ `AI` (قرارداد بیلدزمان) است — اکنون نشان میدهد حتی کامیت تستشده هم لزوماً همان کامیت مستقرشده نیست. `AN` همان `AK` (ابزار ساختهشده بدون خواننده) + `DOM-02` (گیت بیورودی) را در لایهٔ پایش تکرار میکند. `AO` همان الگوی «عدد/حکم بیاعتبار» را در لایهٔ تست بازتولید میکند.

---

## ۷ — اعتبارسنجی و محدوده

- تمام اعداد با اسکن Python مسیرمحدود روی دیسک بازشماری شدند؛ `.freebuff/worktrees/` استثنا شد.
- **هیچ تستی اجرا نشد** — هیچ ادعای زماناجرایی (مثلاً «CI قرمز است») مطرح نشده؛ فقط ساختارگری ایستا.
- توزیع شدت از ۱۶ ردیف جدول بازشماری شد: ۲ + ۶ + ۶ + ۲ = ۱۶.
- مبنای اندازهگیری `105002d7` است (برخلاف قسمتهای ۰۵–۱۱). تغییر `api.ts` حین کار ثبت شد ولی یافتههای قبل را باطل نمیکند.
- `git diff --name-only -- deep_dive .workbuddy-ai/memory` = **۰** تغییر trackشده؛ تنها فایل Markdown جدید ساخته شد.
- **ین قسمت، آخرین نقشهٔ ۱۲ قسمت است** — ماتریس تجمیعی اکنون ۱۲ قسمت / ۱۹۲ یافته را پوشش میدهد.
