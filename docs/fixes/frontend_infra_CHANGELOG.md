# CHANGELOG — دستیار ۳: `fix/frontend-infra`

نقش: Senior Frontend Engineer (Next.js/TS) + DevOps
تاریخ: ۲۰۲۶-۱۰-۲۴
گام ۰ (تأیید یافته‌ها): `docs/fixes/frontend_findings_verified.md`

> ⚠️ **وضعیت commit**: طبق تصمیم صاحب کار، همهٔ تغییرات **در همان درخت اصلی اعمال
> شده ولی commit نشده‌اند** — چون هر سه دستیار روی یک working tree مشترک کار
> می‌کنند و HEAD در میانهٔ کار از `fix/engine` به `fix/backend` جابه‌جا شد (و یک
> commit موتور روی `fix/backend` افتاد). پیش از commit، تکلیف branch isolation
> باید روشن شود. جزئیات: «سؤالات باز» §۱.
> به همان دلیل **`git stash` اجرا نشد** (۲۳۲ فایل تغییر‌یافتهٔ دیگران در درخت
> است); قرمزی تست‌ها با اجرای آن‌ها روی کد قبل از اصلاح اثبات شد.

---

## ۱) جدول شناسه‌ها

| شناسه | وضعیت | فایل‌ها | تست |
|---|---|---|---|
| **F1** | `fixed` | `frontend/src/app/globals.css` (۳ بلوک `[data-theme]` با ۱۲ توکن `--gd-*`) | `GoldThemeTokens.test.tsx` (۴ تست) |
| **F2** (C3) | `fixed` (فرانت) — **نگه‌دارندهٔ هر دو شکل** | `frontend/src/lib/goldApi.ts` (`GoldAPIError`, `goldCall`, `unwrapGoldPayload`, `normalizeGoldError`), `LiveSignalBanner.tsx` | `GoldApiLayer.test.ts` (۳ تست snapshot) |
| **F3** (C1) | `fixed` (فرانت) / ⛔ **در production قابل رسیدن نیست** | `frontend/src/lib/gold-decision.ts` (جدید), `types/gold.ts`, `SummarySection.tsx`, `coins/page.tsx`, `analytics/page.tsx`, `ScoreGauge.tsx`, `portfolio/page.tsx`, `backtest/page.tsx` | `GoldNoData.test.tsx` (۸ تست) |
| **F4** (C4, C5) | `fixed` (فرانت) — **merge هم‌زمان لازم است** | `goldApi.ts` (`planDCA`, `testTelegram` بی‌تغییر), `DCACalculator.tsx`, `portfolio/page.tsx` | `GoldApiLayer.test.ts` (۲ تست DCA + current_score) |
| **F5** (C7, C6) | `partial` | `components/gold/ConfirmDialog.tsx` (جدید), `portfolio/page.tsx`, `macro/page.tsx`, `tokens/page.tsx` | `GoldFrontendSurfaces.test.tsx` (۴ تست) |
| **F6** (C10) | `partial` | `goldApi.ts` (WS manager: `hot`/`snapshot`/`signal` + timestamps + backoff), `hooks/useGoldWS.ts` (جدید), `app/gold/layout.tsx`, `app/gold/page.tsx`, `coins/page.tsx` | `GoldWebSocket.test.tsx` (۵) + `GoldSnapshotPolling.test.tsx` (۳) |
| **F7** | `partial` | `backtest/page.tsx` (هشدار برجسته + خطای query + caveat) | — (بخش warning در `GoldNoData`/`GoldApiLayer` پوشیده نیست؛ ببین «سؤالات باز» §۵) |
| **F8** | `fixed` (حذف فیزیکی انجام **نشد** — سیاست «حذف داده ممنوع») | `components/gold/CoinBubbleTable.tsx` → adapter, `ParityBadge.tsx`, `tokens/page.tsx`, `goldApi.ts` (توکن‌ها), `layout.tsx` (ناوبری), `globals.css` (`padding-bottom`) | `GoldFrontendSurfaces.test.tsx` (۳ تست) |
| **F9** | `fixed` | `frontend/public/golddesk-sw.js` (بازنویسی), `PWAProvider.tsx` | `GoldServiceWorker.test.ts` (۶ تست) |
| **F10** | `fixed` | ۷ فایل تست جدید | ۴۱ تست جدید؛ کل suite **۴۸ فایل / ۵۲۷ تست پاس** |
| **I1** | `fixed` | `nginx-golddesk.conf` (ماسک token با `$uri` در `log_format`، timeoutها، upgrade، `X-Forwarded-Proto`) | — (config) |
| **I2** | `partial` | `monitoring/golddesk-prometheus.yml` (`authorization.credentials_file`)، `Dockerfile.golddesk` (healthcheck) | — |
| **I3** | `fixed` | `docker-compose.yml` (`<REDACTED>` با `:?` روی backend+worker؛ حذف دو پیش‌فرض secret) | — |
| **I4** | `partial` — **بازگردانی واقعی اجرا نشده** | `scripts/backup_golddesk.sh` (جدید), `docs/golddesk_backup.md` (جدید) | `scripts/test_backup_golddesk.sh` (جدید؛ ۹ بررسی، همه پاس) |
| **I5** | `fixed` | `.github/workflows/ci.yml` (دو مرحلهٔ جدید: `vitest` در job lint، `pytest tests/gold_desk` در job test؛ گسترش `paths`) | — |
| **D1** | `fixed` | `PLAN_GOLD.md` (جدول «دقت اسناد» + اصلاح مسیرها/شمارش‌ها/کادنس WS/SLO/لایسنس/hit-rate) | — |
| **D2** | `fixed` | `docs/golddesk_single_user_limit.md` (جدید) | — |

## ۲) چیزی که قرمزِ واقعی بود (قاعده ۳)

هر رفع با تستی شروع شد که روی کد فعلی می‌شکست؛ خروجی‌های کلیدی:

| تست | پیام قرمز (قبل از رفع) |
|---|---|
| `GoldThemeTokens` | `در تم dark تعریف نشده‌اند: --gd-text-2, --gd-bg-2, --gd-border, --gd-text, --gd-accent, --gd-bg-3, --gd-text-3, --gd-bg` |
| `GoldApiLayer` (DCA) | `expected undefined to match object { recommended_vehicle: 'etf' }` ← `/dca/plan` پاکت ندارد و `r.data` تهی بود |
| `GoldApiLayer` (snapshot) | `The instanceof assertion needs a constructor but undefined was given` (`GoldAPIError` وجود نداشت) |
| `GoldNoData` | `Failed to resolve import "@/lib/gold-decision"` |
| `GoldSnapshotPolling` | `expected "vi.fn()" to be called 1 times, but got 2 times` ← polling با سوکت وصل هم کار می‌کرد |
| `GoldServiceWorker` | `پاسخ کهنه نباید ok باشد: expected true to be false` ← SW پاسخ مالی ۸ دقیقه کهنه را سرو می‌کرد |

## ۳) جایی که گزارش با کد نخواند (قاعده ۶) — واقعیت ثبت‌شده

| مورد | ادعای گزارش/پرامت | واقعیت کد |
|---|---|---|
| C3 | `/snapshot` و `/score` ۵۰۳ می‌دهند | **HTTP 200** با `{success:false,data:null,error:{message:<داخلی>}}` (`api.py:95-103,109-116`)؛ متن داخلی روی سیم |
| C1 | «ScoreResult فیلدهای جدید می‌گیرد» | موتور **انجامش داده** (`scorer.py:66-68,225-226`, `constants.py:151`) ولی `schemas.py:74-76` هیچ‌کدام را ندارد و `decision: Literal["GREEN","YELLOW","RED"]` مقدار `NO_DATA` را **reject** می‌کند (با اجرا تأیید شد: `ValidationError`). نتیجه: با پوشش < ۶۰ **کل `/snapshot` می‌شکند**. → `handoff_frontend_to_backend.md §۰` |
| C5 | `/dca/plan` باید پاکت بگیرد | `response_model=DCAResponse` → پاسخ برهنه؛ فرانت `r.data` می‌خواند ⇒ همیشه undefined |
| C5 | `/telegram/test` chat_id را از body بپذیرد | امضا `chat_id: str \| None = None` ⇒ FastAPI آن را **query** می‌خواند؛ body فرانت نادیده گرفته می‌شود |
| C4 | حذف ارسال `current_score` | `schemas.py:116` آن را **Required** کرده؛ حذف یک‌طرفه = 422. merge هم‌زمان الزامی است |
| C7 | «حذف دارایی باید soft-delete شود» | بک‌اند **از قبل** پیاده کرده (`api.py:963-989` + `models.py:154` + migration `0043`)؛ ولی `HoldingPnL` فیلد `id` ندارد ⇒ دکمهٔ حذف از UI قابل صدا زدن نبود. `priced_cost` هم در پاسخ نیست (متغیر محلی `portfolio.py:414`) |
| F5 | «حذف دارایی با دیالوگ تأیید» | در فرانت **هیچ** حذف دارایی‌ای وجود نداشت (جدول read-only); تنها `apiDelete` برای **پلن DCA** بود با `confirm("حذف شود؟")` |
| C10 | WS «هر ۵ ثانیه snapshot» | `ws_hub.py:71-87` **هیچ حلقهٔ push ندارد**؛ فقط یک snapshot کش‌شده در register و فریم‌های `signal` |
| F6 | «crypto/FX با `dataAvailable=false` حالت ناموجود» | در کل `frontend/src` **نه** `dataAvailable` هست نه هیچ مصرف‌کنندهٔ `/crypto` یا `/fx` — چیزی برای اصلاح وجود ندارد |
| F7 | «متریک out-of-sample کنار کل دوره» | `backtest_runner.py:77-81` آن را دارد، `/backtest/real` در پاسخ **نمی‌گذارد** |
| F8 | «۱۳ تب» | **۱۵** تب؛ و ۵ route اصلاً در ناوبری نیست (`/gold/coins`, `dashboard`, `dca`, `funds`, `technical`) |
| F9 | «skipWaiting/clients.claim لازم است» | از قبل بودند؛ مشکل اصلی **نبود TTL** و کشیدن بی‌قید `/api/` بود |
| I1 | «لاگ /ws توکن را ماسک کند» | فراتر از آن: مسیرهای فایل `/api/gold/*` بود که با base واقعی `/api/v1/gold` **هیچ‌وقت مچ نمی‌شد** |
| I2 | «healthcheck به /health» | `Dockerfile.golddesk` هم مسیر غلط داشت هم روی کانتینر **بدون پورت HTTP** probe می‌زد ⇒ همیشه unhealthy |
| I3 | فقط `<REDACTED>` | دو secret دیگر هم به‌صورت پیش‌فرض commit شده بودند: یک رمز Redis و یک توکن صف job (مقدارها طبق قاعدهٔ ۵ در این سند تکرار نمی‌شوند) |
| I4 | «۹ جدول» | ۹ تا درست است (راست‌آزمایی از `models.py`)؛ ولی `02_backend_infra.md §۲.۱` ۸ تا می‌شمارد و `gold_portfolio_values` جا افتاده |
| D1 | «117 passed in 2.45s» | **۲۵۸ passed, 1 deselected** در ~۳۵ ثانیه (اجرای واقعی) |
| I5 | «CI لازم است» | `ci.yml` وجود داشت ولی **هیچ‌وقت vitest اجرا نمی‌کرد** و `tests/gold_desk` را هم پوشش نمی‌داد |

## ۴) تغییرات رفتاری که باید بدانید

1. **breaking (هماهنگ)**: `planDCA` دیگر `current_score` نمی‌فرستد و در صورت
   ارسال‌شدن آن را **strip** می‌کند. تا قبل از `schemas.py` change، `/dca/plan`
   422 می‌دهد.
2. **breaking (بهترشونده)**: `POST /gold/portfolio/dca` از query-string به JSON body
   تغییر کرد. قبلاً فیلدها در query بودند درحالی‌که route بدنه می‌خواهد
   (`api.py:991-999`) ⇒ «ساخت پلن» امروز با 422 می‌ایستد؛ این رفع آن را درست می‌کند.
3. **compose fail-closed**: بدون `<REDACTED>` و `<REDACTED>`
   دیگر `docker compose up` بالا نمی‌آید (توضیح + راه‌حل در
   `docs/golddesk_backup.md §۵` و `handoff_frontend_to_ops_env.md`).
4. **PWA**: پاسخ مالی کهنه‌تر از ۵ دقیقه **سرو نمی‌شود** (۵۰۴ `offline_stale`) و
   بنر آفلاین حالا همین را صریح می‌گوید.
5. **ناوبری موبایل**: نوار پایین ۵ مقصد شد؛ `padding-bottom` از ۱۳۰px به ۸۴px.
6. **دکمهٔ حذف دارایی** فقط وقتی ظاهر می‌شود که پاسخ `/portfolio` فیلد `id` را
   بدهد (همین الان نمی‌دهد ⇒ عملاً مخفی است تا رفع §۴ handoff).

## ۵) سؤالات باز

1. **branch isolation (مهم‌ترین)**: سه دستیار روی **یک** working tree کار می‌کنند.
   می‌خواهید (الف) من یک worktree مستقل بسازم و آنجا commit کنم، (ب) با HEAD فعلی
   روی یک branch مشترک commit شوند، یا (ج) changes بدون commit بماند تا خودتان
   دسته‌بندی کنید؟ هیچ commitی نزدم.
2. **لایسنس**: `LICENSE` = MIT و README هم MIT؛ `PLAN_GOLD.md` «استفادهٔ داخلی»
   می‌گفت. من متن را با `LICENSE` (MIT) هم‌راستا کردم، ولی این یک تصمیم **حقوقی**
   است نه متنی: اگر قصد واقعی «فقط داخلی» است باید خودِ `LICENSE` عوض شود.
3. **do not delete**: `components/gold/CoinBubbleTable.tsx` و ۹ کامپوننت بی‌import
   دیگر (`ScoreBreakdown`, `FundNAVTable`, `BubbleGauge`, `GoldKPICard`,
   `TimeSeriesChart`, `RSIIndicator`, `ParityBadge`, `DCACalculator`,
   `HealthRatioGauge` + `KillSwitchBanner`/`SpecRulesCard` را هم چک کنید) را
   به adapter/بی‌کد تبدیل کردم ولی **حذف نکردم** (سیاست repo). فهرست حذف امن را
   می‌خواهید؟
4. **دو Service Worker**: `public/sw.js` (scope `/`) و `public/golddesk-sw.js`
   (scope `/gold`) هم‌زمان register می‌شوند (`src/app/providers.tsx:14` و
   `PWAProvider.tsx`). تا وقتی روشن نشد کدام client را کنترل می‌کند، سیاست TTL من
   ممکن است دور زده شود. `sw.js` هم `/api/` را cache-first می‌کند (خط ۴۴) که برای
   دادهٔ مالی خطرناک‌تر است — ولی خارج از محدودهٔ gold است و دست نزدم.
5. **F7 تست**: برای «هشدار برجستهٔ بک‌تست» تست render اضافه نکردم چون صفحه
   `/gold/backtest` دو query مستقل دارد و پوشش درستش نیاز به fixture دوم داشت؛
   اگر می‌خواهید، اضافه می‌کنم.
6. **`.env.example`** در محدودهٔ هیچ‌یک از سه دستیار نیست؛ دو کلید جدید آنجا
   نیست (`handoff_frontend_to_ops_env.md`). تا افزودنشان، `docker compose up`
   روی محیط تازه خطا می‌دهد.
7. **`/gold/ws` token در query**: ماسک لاگ را حل کردم، ولی ریشه‌اش این است که
   handshake هدر نمی‌تواند برد. راه‌حل استاندارد `Sec-WebSocket-Protocol` است؛
   تغییر قرارداد دو طرفه است. می‌خواهید؟

## ۶) راستی‌آزمایی نهایی (خروجی واقعی)

```
$ cd frontend && npx tsc --noEmit
TSC=0

$ cd frontend && npx vitest run
 Test Files  48 passed (48)
      Tests  527 passed (527)

$ ./venv/Scripts/python.exe -m pytest tests/gold_desk -q
258 passed, 1 deselected in 34.78s        # اجراشده توسط من، بدون تغییر کد Python

$ bash scripts/test_backup_golddesk.sh
همهٔ بررسی‌ها پاس شد.                       # ۹ بررسی: نسخه، چک‌سام، retention،
                                            # scope نامعتبر، pg_dump خراب

$ bash -n scripts/backup_golddesk.sh        # SYNTAX OK
$ python -c "yaml.safe_load(ci.yml)"        # YAML OK؛ jobs: lint, docs, test, build
```

محدودهٔ تغییر (هیچ فایل Python یا migrationی دست نخورد — فقط خوانده شدند):

```
25 files changed, 1390 insertions(+), 412 deletions(-)   # فایل‌های track‌شدهٔ من
+ 19 فایل جدید (untracked): ۷ تست، ۳ ماژول فرانت، ۲ اسکریپت، ۴ سند docs/fixes، 2 docs، 1 ConfirmDialog
```

فهرست کامل فایل‌ها در `git status --short` با فیلتر محدودهٔ مالکیت قابل استخراج است
و آیتم‌های دیگر در درخت (`src/**.py`, `migrations/**`, `docs/analysis/**`,
`.agents/**`) کار دو دستیار دیگرند.
