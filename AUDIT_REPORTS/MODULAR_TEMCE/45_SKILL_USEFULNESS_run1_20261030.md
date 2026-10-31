# ۴۵ — ارزیابی سودمندی Skillها برای ارتقای temce — ۳۰ اکتبر ۲۰۲۶

**نتیجهٔ کلی:** از ۳۹۲ skill یکتا، حدود **۴۵ مورد Tier A** (مفید و قابل استفاده برای
ارتقا)، حدود **۲۵ مورد Tier B** (مفید اما نیازمند کلید/نصب/ورودی) و بقیه (شامل ۶۸ مورد
دامنهٔ دیگر) برای این پروژه کم‌ارزش یا بی‌ربط‌اند.
ضمیمهٔ کامل: `evidence/SKILL_INVENTORY_20261030.md`.

---

## ۰) روش و محدودیت (صادقانه)

«اجرای واقعی همهٔ ۳۹۲ skill» ممکن نیست: بسیاری به حساب/کلید/ورودی (PRD، Figma،
collection پستمن) وابسته‌اند. بنابراین سه لایه سنجش انجام شد:

1. **اعتبارسنجی بسته برای همه:** parse کردن frontmatter همهٔ `SKILL.md`ها.
2. **ارزیابی ایستا برای همه:** تطبیق نام/توضیح با شواهد واقعی ریپو
   (FastAPI، Next 16، Postgres/TimescaleDB، Redis، ML forecasting، TSE).
3. **Smoke واقعی برای نمونهٔ قابل‌اجرا:** context7، Chrome DevTools، toolchain و
   موارد مسدود.

محدودیت: skillهای `code-review` و `security-audit` به‌صورت Skill فراخوانی نشدند؛
متدولوژی‌شان دستی (ruff/mypy/tsc/eslint/secret-scan/review) اعمال شد.

## ۱) اعتبارسنجی بسته

| شاخص | مقدار |
|---|---|
| فایل `SKILL.md` روی دیسک | **۴۱۴** (۳۶۳ user + ۵۱ repo) |
| نام یکتا | **۳۹۲** |
| نام تکراری/نسخه‌دار | **۲۲** |
| بدون description | **۱** (`references`) |

تکرارها عمدتاً plugin در برابر standalone هستند: `frontend-design`، `query`،
`the-news`، `vercel-*`، `design`، `health`، `init-pipeline` و… .
**توصیه:** نسخهٔ plugin را مبنا بگیر؛ کپی‌های تکراری فقط نویز context هستند.

## ۲) توزیع دامنه (خودکار)

| دامنه | تعداد |
|---|---|
| کد و تست | ۹۹ |
| فرانت و UX | ۸۴ |
| دامنهٔ دیگر | ۶۸ |
| بک‌اند و API | ۳۲ |
| ML و AI | ۲۷ |
| دیتابیس و داده | ۲۰ |
| دانش و حافظه | ۱۹ |
| معماری | ۱۶ |
| مالی و بازار | ۱۳ |
| محصول و PM | ۹ |
| پلتفرم Qoder | ۵ |

> این جدول خودکار over-inclusive است (مثلاً Alibaba/Apollo هم در دامنه‌های مرتبط
> افتاده‌اند)؛ Tierهای زیر نسخهٔ اصلاح‌شدهٔ دستی‌اند.

## ۳) Tier A — مفید و قابل استفاده (curated)

### کیفیت کد و تست
`code-review`، `requesting-code-review`، `security-audit`، `test-driven-development`،
`verification-before-completion`، `verify-and-stop`،
`andrej-karpathy-skills:karpathy-guidelines`، `prefer-unknown-over-any`،
`create-technical-spike`، `finishing-a-development-branch`،
`gstack:review/health/investigate/qa/qa-only/benchmark`،
ایجنت‌های `feature-dev:code-reviewer` و `code-simplifier`.

### معماری
`architecture-visualization`: `system-modeler`، `risk-quality-reviewer`،
`dependency-impact-analyzer`، `architecture-health`، `flow-visualizer`،
`evolution-planner`، `legacy-system-visualizer`، `c4model`، `graphviz`، `drawio`،
`architecture-communicator`؛ `arch-guard`، `analyze-project`، `explore-code`،
`codebase-knowledge`، `project-knowledge`، `project-knowledge-architect`.
(گارد چرخهٔ AST هم در `tests/unit/test_no_import_cycles.py` اضافه شد.)

### دیتابیس و داده
`supabase-postgres-best-practices` (برای Postgres، نه فقط Supabase)،
`redis-development`، `realtime-data-engineer:data-quality-monitoring`،
`data-lineage-impact-analysis`، `duckdb-skills:*` (پس از نصب).

### بک‌اند و API
`context7` (**تست زنده: PASS**)، `postman:agent-ready-apis` (پس از collection)،
`sentry-cli` (پس از نصب/token)، `sourcegraph` (پس از MCP).

### فرانت و UX
`design-review`: `accessibility-review`، `responsive-design`، `design-debt-review`،
`component-library-alignment`، `visual-regression-review`، `design-qa`،
`design-system-capture`؛ `web-design-guidelines`، `frontend-design`، `impeccable`،
`product-design:chart/check/access/qa/edge`،
`chrome-devtools-mcp:a11y-debugging/debug-optimize-lcp/memory-leak-debugging`،
`webapp-testing`.

### مالی (متدولوژی، نه فید TSE)
`stock-market-pro`، `trading-analysis`، `equity-research`، `portfolio-concentration`،
`news-stock-impact`، `the-news`، `news-aggregator-skill`. این‌ها دادهٔ US/KR/global
دارند؛ برای بورس تهران فقط چارچوب/فرمول‌ها مفیدند.

### ML و دانش
`ai-research-explore`، `analyze-project`، `explore-code`،
`qoder-repowiki:knowledge-plan/edit`، `knowledge-validator`، `knowledge-sync`،
`gstack:document-generate`، `Presentations:pptx`، `gstack:make-pdf/diagram`.

## ۴) Tier B — مفید اما مسدود/نیازمند ورودی

| skill | دلیل |
|---|---|
| `openmemory:*` | `HOLOGRES_OPEN_MEMORY_API_KEY` ست نشده |
| `qoder-qmind:qmind` | workspace/منبع معرفی نشده |
| `qoder-cloud-agents`, `sites:*` | احراز هویت Qoder لازم |
| `graphos-tools`, `apollo-*` | پروژه GraphQL نیست و حساب Apollo ندارد |
| `postman:*` | collection/حساب Postman لازم |
| `sentry-cli` | نصب نیست؛ token ندارد |
| `project-explorer`, `sourcegraph` | MCP server پیکربندی نشده |
| `duckdb-skills:*` | ماژول duckdb نصب نیست (`pip install duckdb`) |
| `vercel:*` | پروژه روی Vercel نیست |
| `alibabacloud:*`, `PolarDB` | زیرساخت Alibaba استفاده نمی‌شود |
| `supabase`, `neon-postgres`, `turso-db`, `convex`, `firebase`, `clerk` | در استک نیستند |
| `product-design:*`, `product-management:*`, `ui-ux-pro-max:*` | PRD/Figma/design system نداریم |
| `toss-investment`, `xtb-portfolio-review`, `warren-buffett`, `merger-model` | بازار/بروکر دیگر |

## ۵) Tier C — کم‌ارزش/بی‌ربط برای temce

`hik-isc-plugin` (۲۴)، `dingtalk` (۱۴)، `cangjie-skills` (۶)، `moonbit-skills` (۹)،
`superun-creation` (۵)، `meoo`، `petdex`، `knot-theory-educator`،
`alipay-rental-knowledge-base`، `marketing-psychology`، `influence-psychology`،
`gws-gmail-forward`، `recipe-create-expense-tracker`، `anti-detect-browser`،
`modeling-glb`، `remotion-markup`، `hyperframes-registry`، `banner-design`،
`poster`، `avatar`، `internal-comms`، `mobile-use`، `ios-*`، `flutter-*`.

**توصیه:** غیرفعال/نادیده گرفتن این‌ها نویز انتخاب skill را کم می‌کند.

## ۶) Smoke testهای واقعی

| مورد | نتیجه |
|---|---|
| `context7` (FastAPI HTTPBearer docs) | **PASS** — resolve + query زنده |
| Chrome DevTools MCP (S5) | **PASS** — console/network + Lighthouse 90/96/91/60 |
| toolchain: ruff / mypy / tsc / eslint / vitest / pytest / alembic | **PASS/PARTIAL** (مستند در گزارش‌های ۳۲–۴۴) |
| `duckdb` | **BLOCKED** — module نصب نیست |
| `sentry-cli` | **BLOCKED** — نصب/token ندارد |
| `openmemory` | **BLOCKED** — API key ندارد |
| `project-explorer` / `openmemory` MCP | **BLOCKED** — server در دسترس نیست |
| `postman` analyzer | **BLOCKED** — نیازمند collection/حساب |
| `code-review` / `security-audit` به‌صورت Skill | اجرا نشد؛ معادل دستی اجرا شد |

## ۷) شکاف‌های واقعی (چیزی که نداری)

1. **TSE/بورس تهران**: هیچ skill بومی BrsApi/کدال/TSETMC نیست؛ skillهای مالی همه
   US/KR/global هستند.
2. **فارسی/RTL**: skill اختصاصی a11y/RTL فارسی وجود ندارد.
3. **MLOps**: MLflow/W&B/experiment tracking پوشش داده نمی‌شود.
4. **TimescaleDB**: skill اختصاصی hypertable/compression نیست.
5. **Migration linter**: فقط drift test و cycle guard ساختیم؛ linter رسمی Alembic نیست.
6. **OpenAPI contract linter**: postman بخشی را پوشش می‌دهد اما نیازمند حساب است.

## ۸) توصیهٔ عملی برای ارتقا

1. **Workflow هسته:** `context7` + `code-review` + `security-audit` +
   `verification-before-completion` + `design-review:accessibility-review` +
   `architecture-visualization:risk-quality-reviewer`.
2. **فعال‌سازی:** `pip install duckdb`، نصب `sentry-cli` + token، پیکربندی
   `project-explorer` MCP، و در صورت نیاز کلید `openmemory`.
3. **حذف نویز:** ۶۸ skill دامنهٔ دیگر + ۲۲ کپی تکراری.
4. **گام بعدی پیشنهادی:** اجرای واقعی `code-review` و `security-audit` روی یک diff
   کوچک (نه کل درخت) و `accessibility-review` با dev server بالا.

## ۹) وضعیت

| مورد | وضعیت |
|---|---|
| اعتبارسنجی همهٔ ۴۱۴ فایل | **PASS** |
| ارزیابی ایستای ۳۹۲ نام یکتا | **PASS** |
| Smoke واقعی نمونه | **PARTIAL** (۴ PASS، ۴+ BLOCKED) |
| Tierبندی کاربردی | **PASS** (۴۵ A / ~۲۵ B / بقیه C) |
| تغییر کد | ندارد (فقط گزارش/ضمیمه) |
