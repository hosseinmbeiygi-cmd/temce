# قسمت ۱۰ — آپشن، طلا، کدال و اخبار

| | |
|---|---|
| **مبنای اندازهگیری** | `73a6c52d` — همان مبنای قسمتهای ۰۵ تا ۰۹؛ HEAD برای **ششمین** قسمت متوالی جابهجا نشد. |
| **وضعیت worktree** | **۱۲۴ فایل Dirty** (همان پایان قسمت ۰۹). فایلهای مرتبط با این قسمت فقط **جابهجایی اسناد/تستها** به `docs/`, `reports/`, `tests/` توسط فرایند همزماناند (`OPTIONS_DEEP_ANALYSIS_2026-11-13.md/.html`, `OPTIONS_MARKET_REPORT.md`, `PLAN_GOLD.md`, `test_options.py`). هسته `domain/options/`, `services/gold/`, `src/gold_desk/`, `services/codal_analysis/`, `core/news_read_canary.py` و چهار router endpoint **جزو فایلهای اصلاحشده نیستند**؛ شواهد `DOM-*` هم در HEAD و هم در worktree معتبراند. |
| **تعهد** | فقط فایلهای Markdown تحلیلی ساخته/ویرایش شدند. **هیچ فایل کد، پیکربندی، تست، compose، مهاجرت یا سندی تغییر نکرد.** |
| **یادداشت روش** | جستجوها مسیرمحدود و با مستثنا کردن `.freebuff/worktrees/` انجام شدند (پروتکل قسمت ۰۸). اعداد سند حسابرسی آپشن و پنجره parity اخبار **نقل شدند و بازشماری/اجرا نشدند**. |
| **پیشوند یافتهها** | `DOM-*` (Domains) — با `DB-*` قسمت ۰۴ و `EX-*` قسمت ۰۱ اشتباه نشود. |
| **زبان** | فارسی (هماهنگ با سری) |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقطخواندنی)

| درخت / فایل | تعداد | خط | یادداشت |
|---|---:|---:|---|
| `domain/options/` | **۱۹ فایل `.py`** | **۴٬۵۴۶** | هسته ریاضی رسمی؛ **`black76.py` وجود ندارد** (لایه ۱۰۶ گزارش اصلی آن را لیست کرده) |
| `services/gold/` | **۲۸** | **۹٬۰۵۲** | دومین پشته طلا |
| `src/gold_desk/` | **۵۸** | **۱۶٬۳۱۸** | سومین پشته، درون همان monolith (لایه ۱۰۸: «حدود ۵۰») |
| `services/codal_analysis/` | **۳۴** | — | ISA/IFRS/forensic؛ **۳۰ ماژول واقعاً وصلاند** |
| فایلهای codal-named | ۱۰۶ | ۱۶٬۹۹۴ | چهار router + سرویسها + repositories |
| فایلهای news-named | ۷۸ | ۸٬۹۰۰ | `core/news_read_canary.py` (۳۹۹), `services/news_ingestion.py` (۵۳۴) |
| فایلهای option-named | ۴۴ | ۱۰٬۳۴۹ | `services/options_service.py` (۱٬۱۶۴), `endpoints/options.py` (۷۳۶) |
| فایلهای gold-named | ۱۱۶ | ۲۹٬۰۱۹ | `src/gold_desk/api.py` (۲٬۰۳۷), `phase2.py` (۱٬۱۶۶) |
| تستهای مرتبط | **۱۷۶** | **۳۰٬۱۱۹** | بزرگترین پوشش تستی میان قسمتهای ۰۱–۱۰ |
| `services/news/` | — | — | **وجود ندارد**؛ `domain/gold/` هم وجود ندارد |

شمارش ایستا: **۴ پیادهسازی قیمتگذاری آپشن** (`src/gold_desk/black76.py`, `services/gold/black76_engine.py`, `domain/options/pricing.py`, `domain/options/commodity_pricing.py`) · **۳ تقسیمکنندهٔ day-count** (`/365`, `/250` TSE, `/240` IME) · **۳ kill switch مستقل** · **۴ router کدال** · **۱۵ یافتهٔ `OF*`** همگی کامیت اصلاح دارند · ۶+ ماژول `domain/options` با صفر مصرفکننده.

---

## ۲ — ردیابی جریان اجرا

### ۲‑الف — قیمتگذاری آپشن در API زنده (قلب یافتهٔ بحرانی)

```
apps/api/endpoints/options.py:632   from src.gold_desk.black76 import black76_greeks, black76_price
  └─ :648   t = max(float(days) / 365.0, 1e-6)                       ← DOM-01
       └─ src/gold_desk/black76.py:78      delta_days / 365.0
            └─ :129-135   theta = (...) / 365.0
       └─ :651-654  black76_price(...) / black76_greeks(...) → theoretical, delta
  └─ :685   return ApiResponse(success=True, model="black76", ...)

در مقابل، دامنهٔ رسمی بعد از ace9339f / 55a0533d (OF5):
  domain/options/pricing.py:9,144,150          → / _TDAYS = 250   (TSE)
  domain/options/commodity_pricing.py:22,279,440 → / _IDAYS = 240   (IME)
  domain/options/heston_model.py:150           → / _TDAYS
  services/gold/black76_engine.py:164          → theta / 365.0     ← لمس نشد
```

### ۲‑ب — kill-switch بحران طلا

```
GET /api/v1/gold/kill-switch   → apps/api/endpoints/gold.py:378
  └─ live = await service.get_live_prices()      ← فقط دو قیمت لحظهای
  └─ evaluate_kill_switch(                       :383-388
         current_oz_usd=..., current_usd_irr=...,
         oz_history=None,        ← هاردکد + TODO «از TimescaleDB (فاز بعدی)»
         usd_history=None,       ← هاردکد
         market_frozen=False)    ← هاردکد
       └─ services/gold/kill_switch.py:44  «اگر خالی باشد NORMAL برمیگردد»
            └─ قوانین ۱ (نوسان >۵٪ در کمتر از ۲ ساعت) و ۲ (شوک مارجین) **غیرقابلارزیابی**
       └─ :391  ApiResponse(success=True, status="NORMAL", ...)
```

دو kill switch دیگر، کاملاً جدا: `services/kill_switch.py` (singleton سیستمی، `POST /system/kill-switch/*` با تأیید دوگانه) و `apps/currency_service/domain/kill_switch.py` (`check_kill_switch` در overview ارز). هیچ پروتکل مشترکی میانشان نیست.

### ۲‑ج — کاناری خواندن اخبار (کاملترین مکانیسم، متوقف در `off`)

```
core/config/__init__.py:333   news_read_mode = "off"    ← هیچ compose/envای آن را ست نمیکند
  └─ repositories/news_repository.py:_route()  :41
       └─ core/news_read_canary.resolve_mode() → decide(mode, discriminator)
            off      → فقط legacy (`news_<24hex>`)
            shadow   → legacy + probe جدول news_items + شمارش parity در Redis
            canary   → برش هش قطعی (`NEWS_READ_CANARY_PERCENT=10`)
            full     → فقط news_items
       └─ writes: همیشه legacy + dual-write به news_items (مهاجرت 0054)
  └─ jobs/definitions/news_jobs.py:105  NewsReadPathHalterJob  → apps/scheduler/app.py:125 ✅ ثبت شده
  └─ apps/api/endpoints/news.py:547-573  halt_status / set_runtime_mode (admin)
  └─ apps/api/metrics.py:92             record_http_outcome
  └─ docs/NEWS_READ_CANARY_SHADOW_REPORT_2026-09-20.md
       parity_ok=1542/1700 (**۹۰٫۷۱٪**، آستانه ۹۹٪) · regression=0 · halted=false
       ۳۳۸ خطای PostgreSQL OOM روی COUNT DISTINCT مسیر legacy
```

---

## ۳ — سیاست شکست (گامبهگام)

| گام | رویداد شکست | سیاست | سطح لاگ | اثر |
|---|---|---|---|---|
| `GoldDesk` router import | هر استثناء | `logger.exception` + **fail-closed** در production/staging | `exception` | نقطه قوت؛ برعکس `CFG-01` قسمت ۰۳ |
| `GOLD_API_TOKEN_SALT` ناموجود | — | **fail-fast** در import (`RuntimeError`) | — | نقطه قوت؛ `${VAR:?}` در هر دو compose |
| `/golddesk/*` | توکن بدون scope | `api_key_auth("gold:read")` ⇒ ۴۰۳ | — | نقطه قوت |
| `_public_read` (چهار router کدال) | متد نوشتن بدون JWT | `get_current_user` ⇒ ۴۰۱ | — | نقطه قوت؛ GETها عمداً عمومیاند |
| `black76_price/greeks` در endpoint | استثناء | `logger.warning` + `theo=0.0, delta=0.0` | `warning` | **قیمت صفر ساکت** در میانهٔ زنجیره (`DOM-01`) |
| `evaluate_kill_switch` | history خالی / `market_frozen=False` | **NORMAL** | — | گیت بحران هرگز ACTIVE نمیشود (`DOM-02`) |
| `NewsRepository._route` | Redis در دسترس نباشد | degrade به شمارندهٔ درونفرایندی | — | مستند و قابلقبول، ولی تصمیم تکورکر میشود |
| canary `shadow` probe | خطای DB | safe-fail، شمارش نمیشود | — | نقطه قوت؛ ۳۳۸ OOM را divergence حساب نکرد |
| `evaluate_auto_halt` | parity < ۹۹٪ ولی `regression=0` | **عدم توقف** | — | درست (قصداً فقط رگرسیون را میگیرد)، ولی پیمانه همچنان `off` |
| startup news ingest | خطا | ۳ تلاش با backoff ۱۵/۳۰/۶۰ + قفل توزیعشده | `exception` | نقطه قوت؛ وابسته به `_track_background_task` |
| `OptionsNormalizeJob` | — | scheduler: ✅ ثبت شده | — | OF6 بسته شد |

---

## ۴ — جدول یافتهها (`DOM-01`…`DOM-16`)

| ID | شدت | خط دقیق | شاهد | اثر عملی | جهت اصلاح |
|---|---|---|---|---|---|
| **DOM-01** | 🔴 بحرانی | `apps/api/endpoints/options.py:632,648,651-654`; `src/gold_desk/black76.py:78,129-135`; `services/gold/black76_engine.py:164`; `domain/options/pricing.py:9,144,150`; `domain/options/commodity_pricing.py:22,279,440` | سند `OPTIONS_DEEP_ANALYSIS_2026-11-13.md:64` یافتهٔ **OF5** را «day-count ناسازگار: ۳۶۵ تقویمی vs ۲۵۲ معاملاتی (θ gap=۴۴٫۸٪)» ثبت کرده و کامیت `ace9339f` صریحاً «OF5 day-count» را بست. ولی `git show --stat ace9339f` فقط `core/trading_constants.py`, `domain/options/{heston_model,pricing}.py`, `services/options_backtest_service.py` را لمس کرده؛ `55a0533d` هم فقط `domain/options/*` و `jobs/definitions/options_normalize_job.py`. **هیچ مسیر GoldDesk / `services/gold` اصلاح نشد**، و endpoint زنده دقیقاً همان `/365` را صدا میزند — حتی `t` را خودش بر ۳۶۵ تقسیم میکند | **OF5 در مسیری که کاربر واقعاً صدا میزند همچنان باز است**: theta، زمان تا سررسید، و در نتیجه `_leg` قیمت تئوریک و دلتا هم با معیار ۳۶۵ حساب میشوند، در حالی که همان سامانه برای سهام ۲۵۰ و برای IME ۲۴۰ بهکار میبرد. اختلاف `t` حدود ۳۱٪ ⇒ قیمت/دلتای متفاوت، نه فقط θ. «رفع شد» فقط دربارهٔ دامنهای صادق است که endpoint آپشن کالا به آن وصل نیست | گسترش اصلاح OF5 به `src/gold_desk/black76.py`, `services/gold/black76_engine.py` و `endpoints/options.py:648`؛ یا انتقال endpoint به `domain/options.commodity_pricing`؛ تست پاریتی چهار پیادهسازی روی یک ورودی واحد |
| **DOM-02** | 🔴 بحرانی | `apps/api/endpoints/gold.py:382-395`; `services/gold/kill_switch.py:44,57-60`; `services/kill_switch.py`; `apps/currency_service/domain/kill_switch.py:14` | endpoint سه ورودی کلیدی را **هاردکد** میدهد: `oz_history=None`, `usd_history=None`, `market_frozen=False`، با TODO صریح «از TimescaleDB (در phase بعدی)». مستند `evaluate_kill_switch` میگوید history خالی ⇒ `NORMAL`؛ قوانین ۱ (نوسان >۵٪ در کمتر از ۲ ساعت) و ۲ (شوک وجه تضمین) اساساً بدون تاریخچه قابلارزیابی نیستند و قانون ۳ با `market_frozen=False` همیشه خاموش است | **گیت بحران بازار طلا در production همیشه `NORMAL` است** و با `success=True` سریال میشود؛ داشبورد/فرانتاند نمیتواند تشخیص دهد آشکارساز کار نکرده یا بازار سالم است. الگوی دقیق قسمت ۰۸ (`BT-04` حکم اعمال نمیشود) و ۰۹ (`MLD-01` عدد جعلی)، اینبار در لایه ایمنی مالی. افزون بر آن **سه kill switch مستقل** (طلا / سیستمی / ارز) بدون هیچ پروتکل مشترک وجود دارند | وصل کردن `oz_history`/`usd_history` به TimescaleDB و `market_frozen` به فید نمادها؛ پرچم `data_available: false` و `status: UNKNOWN` تا زمان وصل؛ یکی کردن سه پیادهسازی یا مستندسازی مرز حاکمیت |
| **DOM-03** | 🟠 بالا | `core/config/__init__.py:333`; `docker-compose*.yml` (صفر ارجاع); `repositories/news_repository.py:30-36`; `migrations/versions/0054_news_module_foundation.py`; `docs/NEWS_READ_CANARY_SHADOW_REPORT_2026-09-20.md` | `NEWS_READ_MODE` پیشفرض `off` است و در هیچ فایل compose/env مستقر ست نشده (فقط `docs/env-vars.md:250` و runbook مستندش کردهاند). مهاجرت `0054` اسکیمای `news_items` را ساخته و dual-write همیشه مینویسد، ولی با `off` هیچ خواندهای از آن صورت نمیگیرد. پنجره shadow واقعی (۲۰۲۶-۰۹-۲۰، حدود ۲ ماه پیش): `parity_ok 1542/1700 = ۹۰٫۷۱٪` (زیر آستانهٔ ۹۹٪)، `regression 0`، `halted=false`، و **۳۳۸ خطای PostgreSQL OOM** روی `COUNT DISTINCT` مسیر legacy | پیچیدهترین مکانیسم rollout سامانه (چهار حالت، shadow parity، auto-halt، dual-write، runbook، endpoint ادمین، halter job، metrics) **از سپتامبر در همان نقطه مانده است**: جدول جدید بیهزینهٔ نگهداری/دوبرابری نوشتن نگهداری میشود و مسیر legacyای که OOM داده همچنان تنها مسیر سرو است. مرز: حالت runtime در Redis قابلتغییر دستی از endpoint ادمین است و وضعیت Redis production در این تحلیل راستیآزمایی نشد | تصمیم صریح: یا تکمیل rollout (رفع `divergence_items_superset` و OOM)، یا توقف dual-write و بایگانی اسکیمای جدید؛ ثبت `NEWS_READ_MODE` در compose تا وضعیت مستقر قابلحسابرسی باشد |
| **DOM-04** | 🟠 بالا | `apps/api/endpoints/options.py:632`; `apps/api/router.py:328-329`; `src/gold_desk/black76.py`; `services/gold/black76_engine.py`; `domain/options/*` | چهار پیادهسازی Black-Scholes/Black-76 در سه لایهٔ معماری متفاوت همزیستاند. endpoint رسمی آپشن (`apps/api/endpoints/options.py`) برای قیمتگذاری کالا **به `src/gold_desk` (زیرپروژهٔ طلا) وابسته میشود**، نه به دامنهٔ `domain/options/`؛ همان endpoint در `:690` برای مارجین دوباره سراغ `domain.options.margin_engine` میرود. `services/gold/black76_engine.py` نیز توسط `options_chain`, `options_matrix`, `strategies` مصرف میشود | وابستگی معکوس `apps → src` در حالی که `domain/` لایهٔ رسمی است؛ هیچ گارد import-linter متناظر وجود ندارد (`phase0-ml-purity` فقط `ml/` را میبیند). تغییر یک فرمول در GoldDesk، خروجی API آپشن کالا را عوض میکند بدون اینکه تستهای `domain/options` متوجه شوند. لایه ۱۰۷ گزارش اصلی «چهار اسکیم آپشن» را دربارهٔ **جداول** گفته؛ این تکثر دربارهٔ **کد محاسبه** است و آنجا دیده نشد | تعیین `domain/options` بهعنوان تنها مرجع قیمتگذاری؛ تبدیل دو پیادهسازی دیگر به adapter یا حذف؛ گارد import-linter برای `apps → src` |
| **DOM-05** | 🟠 بالا | `domain/options/` (۱۹ فایل / ۴٬۵۴۶ خط); شمارش مصرفکنندگان | `commodity_pricing` (۵۷۹ خط), `greeks`, `higher_order_greeks`, `volatility`, `heston_model`, `monte_carlo`, `tree_pricing` **صفر مصرفکننده production** دارند؛ فقط `pricing` (۴), `strategy_engine` (۱), `margin_engine` (۱) وصلاند. هستهٔ ریاضی سند حسابرسی — Put-Call Parity خطای 2.27e-13، IV round-trip 3.23e-06، همگرایی binomial/MC — دقیقاً در ماژولهای وصلنشده است | دامنهای که ۴٬۵۴۶ خط محاسبهٔ تستشده دارد، در تصمیم مسیر زنده سهمی ندارد؛ تلاش تیم در `ace9339f`/`55a0533d`/`8831b574` اصلاح موتوری کرد که API از آن استفاده نمیکند. ریسک قسمت ۰۹ `MLD-11` (`ml/inference/` مرده) در لایه آپشن تکرار شد | یا وصل کردن `domain/options` به endpointها، یا اعلام صریح آن بهعنوان کتابخانهٔ مرجع و حذف مسیرهای محاسبهٔ موازی |
| **DOM-06** | 🟠 بالا | `services/gold/kill_switch.py`; `services/kill_switch.py`; `apps/currency_service/domain/kill_switch.py`; `apps/api/endpoints/system.py:48-104` | سه «kill switch» با سه قرارداد کاملاً متفاوت: (۱) `evaluate_kill_switch(...)` خروجی `NORMAL/WARNING/ACTIVE` برای بازار طلا، (۲) singleton سیستمی با `kill()/revive()` و تأیید دوگانهٔ نقشها، (۳) `check_kill_switch` بولی در سرویس ارز. هیچکدام دیگری را نمیخواند و هیچ وضعیت مشترکی در Redis/DB ندارند | فعال شدن بحران طلا (`DOM-02` اگر وصل شود) هیچ اثری بر توقف معاملات سیستمی یا ارز ندارد؛ برعکس، `kill_switch.kill()` سیستمی وضعیت `ACTIVE` طلا را تغییر نمیدهد. اپراتور با سه کلید همنام و معانی متفاوت روبهرو است | یکی کردن وضعیت در Redis/DB و تعریف صریح «کدام کلید حاکم است»؛ یا تغییر نام دو تای دیگر |
| **DOM-07** | 🟠 بالا | `services/options_service.py:42-52`; `backtesting/metrics/risk_free_rate.py`; `apps/api/endpoints/options.py:632,651` | `OptionsStrategyEngine` نرخ بدون ریسک را `RISK_FREE_RATE = 0.15` (۱۵٪) و `CONTRACT_SIZE = 1000` هاردکد میکند؛ قسمت ۰۸ (`BT-07`) نشان داد `RiskMetrics` و walk-forward از `get_risk_free_rate("moderate") = 0.25` (۲۵٪) استفاده میکنند؛ چهار pricer نرخ را بهعنوان **پارامتر ورودی** میگیرند و endpoint آن را از query میخواند. `26660f89` صرفاً `contract_size 1x→1000x` را در `dual_payoff_curve` اصلاح کرد | سه مقدار متفاوت نرخ بدون ریسک (۰٫۱۵ / ۰٫۲۵ / ورودی کاربر) و دو منبع `CONTRACT_SIZE` در یک زیرسیستم؛ اختلاف ۱۰ واحد درصد، قیمتگذاری، break-even و سود استراتژیها را جابهجا میکند. همان «چندمنبعی ثابت» قسمت ۰۸ `BT-07`، اینبار در دامنه آپشن | تکمنبع کردن نرخ و اندازه قرارداد در `core/trading_constants` / `acceptance.yaml`؛ تست پاریتی `OptionsStrategyEngine` در برابر `domain/options` |
| **DOM-08** | 🟡 متوسط | `docs/OPTIONS_DEEP_ANALYSIS_2026-11-13.md:8,57-66`; کامیتهای `ace9339f`…`5aaa2d12`; `apps/scheduler/app.py:392` | سند حسابرسی آپشن هنوز «**۳ باگ CRITICAL**» و «Max Pain اشتباه / Heston=0 / validators NO_OP / Vomma خطای ۹٬۸۷۸٪» را بهعنوان وضعیت جاری اعلام میکند، در حالی که OF1–OF15 همگی کامیت اصلاح دارند، `OptionsNormalizeJob` در scheduler ثبت شده و OF4 مانیتور کیفیت گرفته است | مستنداتی که تیم و عامل بعدی بهعنوان مرجع میخوانند، وضعیتی **دو هفته قدیمیتر** از کد را نشان میدهد؛ خطر صرف وقت دوباره روی یافتههای بستهشده،یا برعکس اعتماد به «همهچیز رفع شد» در حالی که `DOM-01` باز است. خوشه `K` قسمت ۰۴ در گستردهترین شکلش | افزودن جدول وضعیت `OF*` با شمارهٔ کامیت به بالای سند؛ ترجیحاً تستی در CI که ادعاهای CRITICAL سند را در برابر کد چک کند |
| **DOM-09** | 🟡 متوسط | `services/gold/` (۲۸ فایل); شمارش مصرفکنندگان | `kill_switch` (وصل ولی بیورودی), `feature_source` (۸۰۰ خط), `physical_market_service`, `feed_health`, `arbitrage`, `physical_arbitrage`, `risk_scenarios` صفر مصرفکننده در `apps/ jobs/ core/` دارند. `services/gold/__init__.py` نُه ماژول را export میکند بیآنکه مصرفکنندهای بیرون از پکیج داشته باشد | حدود نیمی از ۹٬۰۵۲ خط دومین پشته طلا بدهی نگهداری است؛ `feed_health` (سلامت فید) و `arbitrage` دقیقاً ابزارهاییاند که `DOM-02` برای تشخیص بحران کمشان است | حذف یا وصل کردن؛ دستکم `feed_health` را به kill-switch وصل کنید |
| **DOM-10** | 🟡 متوسط | `apps/api/router.py:237-240,425-443`; `apps/api/endpoints/codal_professional.py` (۲۹+ route); `services/codal_analysis/` (۳۴ ماژول); `apps/api/dependencies.py:334-343` | چهار router کدال (`/codal`, `/codal-accounting`, `/codal-audit`, `/codal-professional`) همگی با `dependencies=_public_read` mount شدهاند. `require_user_for_writes` فقط GET/HEAD/OPTIONS را آزاد میگذارد و docstring خودش هشدار میدهد «Read handlers that are user-scoped must not live on such a router». endpointهای حسابرسی حساس (`risk-assessment`, `materiality`, `forensic`, `audit-program`, `going-concern`) همگی **GET عمومی**اند. در همان پکیج، `amendment_tracker`, `lineage`, `point_in_time` صفر واردکننده دارند | نوشتنها درست محافظت میشوند، ولی محاسبات سنگین ISA/IFRS و گزارشهای کارشناسی بدون احراز هویت و بدون نرخگیری اختصاصی قابل فراخوانیاند (سوءاستفادهٔ محاسباتی). سرویس «point-in-time» — که دقیقاً برای جلوگیری از look-ahead در داده مالی لازم است — مرده است، در حالی که ۳۰ ماژول دیگر وصلاند | اسکوپ کردن router حرفهای به `_require_user` (یا دستکم rate-limit اختصاصی)؛ وصل/حذف سه ماژول مرده؛ بررسی `point_in_time` پیش از هر ادعای جلوگیری از نشت |
| **DOM-11** | 🟡 متوسط | `apps/api/router.py:305,323-348`; `src/gold_desk/api.py:99,111`; `apps/api/app.py:39`; `docker-compose.production.yml:25` | `src/gold_desk/` یک اپ ۵۸ فایله با router جداگانه، توکن scopeدار، WebSocket (`ws_hub`), بات تلگرام، بکتست و `antigravity/` است که **درون همان monolith FastAPI** mount میشود — هم بهصورت `/golddesk` (scoped token) و هم `/gold` (JWT شخصی). import داخل `try/except` است ولی برخلاف الگوی قسمت ۰۳، در production/staging `raise` میکند؛ `GOLD_API_TOKEN_SALT` با `${VAR:?}` در هر دو compose اجباری و `app.py:39` fail-fast اضافه کرده | نقطهٔ قوت امنیتی (سه لایه: salt، scope، fail-closed)، ولی دو سطح احراز هویت متفاوت برای دو مسیر روی یک کد مشترک، و یک مرز استقرار مبهم: `apps/currency_service/` شبیه آن استقرار مستقل دارد، `gold_desk` نه. لایه ۵۲ گزارش فقط salt را دیده است | مستندسازی صریح مرز «کدام اپ مستقل است / کدام داخل monolith»؛ یکی کردن سیاست احراز هویت دو router طلا |
| **DOM-12** | 🟡 متوسط | `docs/DEEP_ANALYSIS_160_LAYERS_2026-11-13.md:407-417`; شمارش این قسمت | لایه ۱۰۶ `domain/options/` را شامل `black76` میداند (**چنین فایلی وجود ندارد**)؛ لایه ۱۰۸ `src/gold_desk/` را «حدود ۵۰ فایل» (**۵۸**) و `services/codal_analysis/` را «۳۵ فایل» (**۳۴**) نوشته؛ لایه ۱۰۹ `services/news_*` را محل `read_canary` و `providers/news/` را محل RSS معرفی میکند، در حالی که واقعی `core/news_read_canary.py` و `providers/macro_sources/news_rss.py`اند | چهار خطا در شش لایهٔ متوالی — فشردهترین تمرکز کهنگی/جابهجایی مسیر در کل گزارش. جستجو برای `services/news_read_canary.py` (مسیر ذکرشده در shadow report) نیز بیمورد است | تصحیح موضعی لایهها؛ ترجیحاً تولید خودکار جدول ابعاد از شمارش مخزن |
| **DOM-13** | 🟡 متوسط | `tests/unit/services/test_black76_theta_derivative.py`; `services/gold/black76_engine.py:154-155`; ۱۷۶ فایل تست / ۳۰٬۱۱۹ خط | تنها گارد day-count یافتشده، فرمول θ را **فقط** برای `services/gold/black76_engine` در برابر `-dV/dT` قفل کرده است. تست پاریتی چهار پیادهسازی، یا تستی که `endpoints/options.py:648` را با `domain/options` مقایسه کند، پیدا نشد. سند حسابرسی هم «Day-Count: PARTIAL (θ gap=44.8%)» را ثبت کرده ولی تست معادل نساخته | ۱۷۶ فایل تست نتوانستند `DOM-01` را بگیرند چون هر پیادهسازی جداگانه و درستبهنظر تست میشود؛ مشکل در **مقایسهٔ بین پیادهسازیها** است. همان درس `BT-01` قسمت ۰۸ (پاریتی هزینه قفل شده، پاریتی پیکربندی نه) | یک تست جدولمحور با ورودی واحد (F, K, T, r, σ) که هر چهار pricer را صدا زده و `theta_daily`, `theoretical`, `delta` را با تلرانس مشخص مقایسه کند |
| **DOM-14** | 🟡 متوسط | `apps/api/app.py:737-788,993-994`; `jobs/definitions/news_jobs.py:105`; `core/news_read_canary.py:30-40`; `docs/RUNBOOK_NEWS_READ_CANARY.md:38` | startup خواندن RSS با قفل توزیعشده و backoff ۱۵/۳۰/۶۰ وظیفهای سالم است، ولی به `_track_background_task` و `get_session()` تکیه دارد و قسمت ۰۶ (`JOB-01`) نشان داد صف job در compose تولید خاموش است. افزون بر آن `news_read_parity_min_samples` در کد **۵۰** است (`core/config/__init__.py:338`) ولی runbook «پیشفرض 100» مینویسد | دو منبع آماری تصمیم auto-halt متفاوتاند؛ اپراتور با آستانهٔ ۱۰۰ برنامهریزی میکند در حالی که کد با ۵۰ نمونه قضاوت مینماید. وابستگی startup news ingest به سلامت background taskها نیز در شکست خاموش قسمت ۰۱ (`EX-09`) شریک است | یکی کردن عدد (کد یا runbook)؛ لاگ ساختاریافتهٔ نتیجهٔ startup ingest؛ بررسی رفتار هنگام خاموشی صف |
| **DOM-15** | 🟢 کم | `docs/NEWS_READ_CANARY_SHADOW_REPORT_2026-09-20.md:24-32`; `core/news_read_canary.py` | پنجره shadow پاریتی خام **۹۰٫۷۱٪** (زیر آستانهٔ ۹۹٪) گزارش کرده ولی `regression_parity_percent=100` و `halted=false` نتیجه گرفته؛ ۱۵۸ divergence همگی `items_superset` (مسیر جدید بیشتر برمیگرداند) بودهاند | رفتار auto-halt **درست** است (فقط رگرسیون واقعی را میگیرد)، ولی خوانندهٔ داشبورد که `parity_percent` را میبیند، عددی زیر آستانه میخواند بیآنکه توضیح «superset = بهبود عمدی» کنارش باشد؛ تصمیم به ادامهٔ rollout مبهم میماند | جدا کردن `raw_parity_percent` از `regression_parity_percent` در متریکها و مستندات |
| **DOM-16** | 🟢 کم | `docs/PLAN_GOLD.md`, `GOLD_SILVER_ASSISTANT_SPEC.md`, `acceptance.yaml`, `config/signal_policy.yaml`; `core/time/` (۴ تقویم، قسمت ۰۷ `SIG-04`) | برای حوزه طلا دستکم چهار سند حاکم و چهار تقویم معاملاتی متناقض (۱۲:۰۰–۱۸:۰۰ / ۰۹:۰۰–۱۲:۳۰ / ۰۸:۳۰–۱۲:۳۰ / ۰۸:۴۵–۱۲:۳۰) در کنار `src/gold_desk/dates.py` و `services/gold/constants.py` وجود دارد. `PLAN_GOLD.md` همین حین تحلیل از ریشه به `docs/` منتقل شد | تعیین «کدام سند/تقویم حاکم است» بدون خواندن تکتک فایلها ممکن نیست؛ قسمت ۰۷ نشان داد هیچکدام به گیت اجرا وصل نیستند و قسمت ۰۸ نشان داد آستانههای سند طلا به کل موتور بکتست تحمیل میشود (`BT-14`) | فهرست کردن تکمنبع حاکم در `README` حوزه طلا و حذف/بایگانی بقیه |

**توزیع شدت:** ۲ بحرانی · ۵ بالا · ۷ متوسط · ۲ کم = **۱۶ یافته**.

---

## ۵ — نقاط قوت تأییدشده

1. **سری `OF1–OF15` واقعاً و قابلردیابی بسته شد.** `ace9339f` (OF1/2/3/5), `d77d663e` (OF6), `8831b574` (OF7), `2d34beba` (OF8–12), `55a0533d` (theta/UTC), `26660f89` (OF13/15), `2ef8be2a` (OF4), `5aaa2d12` (OF14) — هر کدام شناسهٔ یافته را در عنوان کامیت نام میبرند. `OptionsNormalizeJob` در `apps/scheduler/app.py:392` ثبت شده و تستهای عددی سند (Put-Call Parity 2.27e-13، IV round-trip 3.23e-06، همگرایی binomial/MC) همچنان معتبراند. تنها استثنای مهم `OF5` در مسیر زنده است (`DOM-01`)، نه انکار کل تلاش.
2. **کاناری خواندن اخبار پیچیدهترین و سالمترین مکانیسم rollout سامانه است.** چهار حالت، مقایسهٔ shadow با **کلید طبیعی** (URL/title) بهجای id چون دو اسکیما id مشترک ندارند، شمارندههای Redis با TTL یکساعته، برش هش قطعی، auto-halt فقط روی رگرسیون، dual-write همیشه → بازگشت دادهامن، degrade مستند بدون Redis، endpoint ادمین، متریک Prometheus، `NewsReadPathHalterJob` ثبتشده، runbook و گزارش پنجرهٔ واقعی. قسمت ۰۶ نشان داد بسیاری jobها فقط تعریف شدهاند؛ این یکی وصل است.
3. **لایهٔ امنیتی GoldDesk سهگانه و fail-closed است.** `GOLD_API_TOKEN_SALT` بدون مقدار ⇒ `RuntimeError` در import (`api_token.py`), `${VAR:?}` در هر دو compose، `app.py:39` fail-fast صریح، `api_key_auth("gold:read"/"gold:analyze")` در تکتک مسیرهای `/golddesk`, و `router.py:344-348` که شکست mount را در production/staging **`raise`** میکند. دقیقاً برعکس الگوی `CFG-01` قسمت ۰۳ (یک کلید گمشده چهار لایه دفاعی را خلعسلاح کرد) — اینجا تیم همان درس را گرفته است.
4. **زیرسیستم حسابرسی کدال واقعاً وصل است (برخلاف حدس اولیه).** ۳۰ از ۳۴ ماژول `services/codal_analysis` توسط `service.py` وارد میشوند و به ۲۹+ endpoint حرفهای (`ISA 315/320/330/450/520/530/570`, `IFRS 15/16`, `IAS 12/36`, نمونهگیری PPS/MUS, تحلیل تقلب, دوپونت) سرو میدهند. `require_user_for_writes` تضمین میکند تمام متدهای نوشتن JWT میخواهند.
5. **`core/trading_constants` واقعاً تکمنبع است** (`GLOBAL 252`, `TSE 250`, `IME 240`, `CALENDAR 365`, `DEFAULT=TSE`) و `domain/options`, `src/gold_desk/backtest_runner`, `performance`, `cointegration`, `monte_carlo` و `heston_model` همگی از آن وارد میکنند. قسمت ۰۸ `BT-07` پراکندگی را در **مصرفکنندگان قدیمی** پیدا کرد، نه در تعریف ثابتها؛ مشکل `DOM-01` دقیقاً مصرفکنندهای است که از این تکمنبع جا مانده.
6. **startup خواندن اخبار defensively طراحی شده.** قفل توزیعشده `_with_startup_lock("news_ingest", ...)` جلوی تکثیر میان رپلیکاها را میگیرد، ۳ تلاش با backoff نمایی، لاگ ساختاریافتهٔ `fetched/saved`، و رها کردن قفل در نهایت — برخلاف `ING-03` قسمت ۰۵ که زمانبند دریافت نگهبان بازورود نداشت.
7. **پوشش آزمون این چهار دامنه چشمگیر است**: ۱۷۶ فایل تست / ۳۰٬۱۱۹ خط (بیش از کل `ml/` و نزدیک به `backtesting/`). مشکل `DOM-13` کمبود کمّی تست نیست، نبود **تست مقایسهای میان پیادهسازیها** است.

---

## ۶ — تصحیح گزارش ۱۶۰ لایهای و حدسهای ردشده

### ۶‑الف — تصحیحات (۴ مورد)

| لایه | ادعای گزارش | واقعیت در `73a6c52d` |
|---|---|---|
| **۱۰۶ / ۴۰۷** | «`domain/options/`: … `commodity_pricing`, … `black76`» | پوشه ۱۹ فایل دارد و **`black76.py` در آن وجود ندارد**؛ Black-76 در `src/gold_desk/black76.py`, `services/gold/black76_engine.py` و توابع `black76_call/put` داخل `commodity_pricing.py` است. همچنین «Vomma خطای ۹٬۸۷۸٪ و Heston=0» دیگر وضعیت جاری نیستند (`8831b574`, `ace9339f`). |
| **۱۰۷ / ۴۱۰** | «شکاف طراحی اسکیم / writer **در حال بسته شدن** است» + فصل خلاصه «چهار اسکیم آپشن» | `OptionsNormalizeJob` **بسته شده** و در scheduler ثبت است؛ دربارهٔ جداول درست است. ولی تکثر تازهای در لایهٔ **کد محاسبه** دیده نشد: چهار pricer و وابستگی `apps → src.gold_desk` (`DOM-04`)، و مهمتر اینکه اصلاح OF5 فقط `domain/options` را گرفته و مسیر API زنده همچنان ۳۶۵ است (`DOM-01`). |
| **۱۰۸ / ۴۱۱** | «`src/gold_desk/` حدود **۵۰** فایل»؛ «`services/gold/` ۲۸ فایل»؛ لایه ۱۰۹ «`services/codal_analysis/` **۳۵** فایل»، «`services/news_*` … `read_canary`»، «`providers/news/`» | شمارش مجدد: `src/gold_desk` **۵۸** فایل / ۱۶٬۳۱۸ خط؛ `services/gold` ۲۸ / ۹٬۰۵۲ (درست)؛ `codal_analysis` **۳۴** ماژول؛ canary در **`core/news_read_canary.py`** است نه `services/news_*`؛ RSS در **`providers/macro_sources/news_rss.py`** است نه `providers/news/`. نتیجهٔ لایه («گستردهترین حوزه با بیشترین تکرار») همچنان درست و حتی تشدید شد. |
| **۱۰۹ / ۴۱۷** | «کاناری خواندن اخبار، پیچیدهترین مکانیسم rollout سامانه است» | دربارهٔ **طراحی** کاملاً درست و این قسمت آن را تأیید کرد؛ ولی نتیجه باید تکمیل شود: `NEWS_READ_MODE` در هیچ compose/env مستقر ست نشده (پیشفرض `off`)، پنجره shadow سپتامبر ۲۰۲۶ با پاریتی خام ۹۰٫۷۱٪ و ۳۳۸ OOM متوقف مانده، و اسکیمای `news_items` نوشته میشود ولی خوانده نمیشود (`DOM-03`). «پیچیدهترین» بله؛ «فعال» خیر. |

### ۶‑ج — حدسهایی که حین راستیآزمایی **رد شدند** (۸ مورد)

1. «`services/codal_analysis/` بدهی مردهٔ ۳۴ فایلی است» → **رد**: ۳۰ ماژول مستقیماً توسط `service.py` وارد و به ۲۹+ endpoint وصلاند. تنها ۳ ماژول (`amendment_tracker`, `lineage`, `point_in_time`) مردهاند (`DOM-10`).
2. «`/golddesk` چون در `include_router` هیچ `dependencies` ندارد، بدون احراز هویت است» → **رد**: `apps/api/endpoints/golddesk.py` روی تکتک مسیرها `Depends(api_key_auth("gold:read"/"gold:analyze"))` دارد و `SCOPES` را چک میکند.
3. «mount کردن GoldDesk داخل `try/except` یک fail-open دیگر است (الگوی قسمت ۰۳)» → **رد**: `router.py:344-348` در `production`/`staging` صریحاً `raise` میکند و `logger.exception` لاگ کامل میدهد. نقطهٔ قوت ثبت شد (`DOM-11`).
4. «`services/gold/kill_switch.py` صفر مصرفکننده و کاملاً مرده است» → **رد**: `apps/api/endpoints/gold.py:58,383` آن را صدا میزند. مسئله **وصل نبودن** نیست، **ورودی هاردکد** است (`DOM-02`) — تمایزی که نتیجه را از «کد مرده» به «گیت جعلی» ارتقا داد.
5. «`OptionsNormalizeJob` (OF6) مثل خیلی jobهای قسمت ۰۶ فقط تعریف شده» → **رد**: `apps/scheduler/app.py:392` واقعاً `add_job` کرده است.
6. «`GOLD_API_TOKEN_SALT` فقط مستند شده و در compose تولید اختیاری است» → **رد**: `docker-compose.production.yml:25` و `docker-compose.yml:66,128` همگی `${VAR:?...}` دارند و import ماژول بدون آن `RuntimeError` میدهد. لایه ۵۲ گزارش تأیید شد.
7. «`NEWS_READ_PARITY_MIN_SAMPLES` در کد و runbook یکی است» → **رد**: کد `۵۰`، runbook `۱۰۰` (تبدیل به `DOM-14`).
8. «`services/news/` و `domain/gold/` وجود دارند و چهارمین/پنجمین پشتهاند» → **رد**: هر دو پوشه **موجود نیستند**؛ کد در `services/news_*.py`, `core/news_*.py`, `repositories/news_*`, `providers/macro_sources/news_rss.py` و `services/gold/` + `src/gold_desk/` پراکنده است.

---

## ۷ — مرز روش

- **هیچ چیز اجرا نشد**: نه pytest، نه بوت سرور، نه اتصال به DB/Redis زنده، نه محاسبهٔ قیمت یا گریک، نه خواندن RSS. همه یافتهها ایستا و مبتنی بر خواندن فایل، `git status/diff/show --stat` و جستجوی محدودشدهاند.
- `DOM-01` (اختلاف day-count در API زنده) **استنتاج از مسیر کد و `git show --stat`** است؛ اندازهگیری عددی gap روی ورودی واقعی انجام نشد. عدد ۴۴٫۸٪ از سند حسابرسی آپشن نقل شد. همچنین endpoint فقط `theoretical`/`delta` را برمیگرداند نه `theta` را — اثر بر `t` و `price`/`delta` استنتاج شد، `theta` مستقیماً به کلاینت نمیرسد.
- `DOM-03` دربارهٔ «off ماندن rollout» بر **نبود `NEWS_READ_MODE` در فایلهای compose/env مخزن** استوار است؛ `resolve_mode()` میتواند حالت را از **Redis runtime** یا `NEWS_READ_FROM_ITEMS` بگیرد و اپراتور از endpoint ادمین تغییرش دهد. وضعیت Redis production در این تحلیل **راستیآزمایی نشد**؛ نتیجه «در پیکربندی مستقر ثبت نشده» است، نه «قطعاً off است».
- اعداد پنجره parity (1700/1542/۹۰٫۷۱٪/۳۳۸ OOM)، ۴۶٬۹۰۶ پیشبینی و جدولهای آپشن (۱٬۲۸۱٬۶۷۸ ردیف و …) از اسناد `docs/` نقل و **بازشماری نشدند**. پنجره مربوط به **سرور dev با Redis خاموش و بار مصنوعی** بوده، نه production.
- جستجوی «صفر مصرفکننده» در `apps/ services/ jobs/ core/ src/ domain/ brsapi/ backtesting/ scripts/ tests/` و با مستثنا کردن `.freebuff/worktrees/` انجام شد. مصرفکنندگان غیرپایتونی (فرانتاند، cron خارجی، فراخوانی دینامیک `importlib`) پوشش داده نشدند.
- محتوای ۱۷۶ فایل تست **اجرا یا خطبهخط تحلیل نشد**؛ `DOM-13` بر جستجوی نام/محتوای تستهای day-count استوار است و وجود تست پاریتی دیگری را بهطور مطلق نفی نمیکند.

---

## ۸ — خوشههای تازه برای ماتریس تجمیعی

| خوشه | یافتهها | شدت مؤثر | پیوند با قسمتهای قبل |
|---|---|---|---|
| **AE — تکثر قیمتگذاری و day-count رفعنشده** | `DOM-01`, `DOM-04`, `DOM-05`, `DOM-07`, `DOM-13` | 🔴 بحرانی | OF5 فقط در `domain/options` بسته شد؛ API زنده `/365` در برابر ۲۵۰/۲۴۰؛ چهار pricer، وابستگی `apps→src`، دامنهٔ ۴٬۵۴۶ خطی وصلنشده. مستقیم به `BT-07` (قسمت ۰۸) و `SIG-03` (قسمت ۰۷) |
| **AF — گیتهای ایمنی بیورودی** | `DOM-02`, `DOM-06`, `DOM-09` | 🔴 بحرانی | kill-switch طلا همیشه `NORMAL`؛ سه پیادهسازی بیارتباط؛ `feed_health`/`arbitrage` مرده در همان پکیج. همان `BT-04`/`MLD-01`، اینبار در لایهٔ توقف معاملات |
| **AG — rollout ناتمام و نوشتن بدون خواندن** | `DOM-03`, `DOM-14`, `DOM-15` | 🟠 بالا | `news_items` نوشته میشود، خوانده نمیشود؛ shadow سپتامبر متوقف؛ آستانهٔ پاریتی کد/رونبوک متفاوت. مستقیم به `MLD-10` (قسمت ۰۹: جدول feature بلااستفاده) و `JOB-01` (قسمت ۰۶) |
| **AH — تکثر دامنهای و مستندات کهنه** | `DOM-08`, `DOM-10`, `DOM-11`, `DOM-12`, `DOM-16` | 🟡 متوسط | چهار لایهٔ متوالی گزارش (۱۰۶–۱۰۹) نیاز به تصحیح دارند؛ سه پشته طلا، چهار router کدال، چهار سند حاکم و چهار تقویم. گسترش خوشه `K` و `O` |

**ترتیب بستن پیشنهادی** (بدون تغییر کد، صرفاً اولویت): `AF → AE → AB → AC → AA → AG → X → W → S → T → Y → P → V → U → N → Q → H → B → AH → AD → Z → …`.

**عبارت خلاصه قسمت ۱۰:** نه قسمت قبل الگوی «ابزار ساخته میشود، وصل نمیشود، یا حکمش اعمال نمیشود، یا عددش ساختگی است» را لایهبهلایه دنبال کردند؛ قسمت ۱۰ نشان میدهد **همان الگو حتی پس از اصلاح رسمی هم زنده میماند**. سری `OF1–OF15` با هشت کامیت و شناسهگذاری دقیق بسته شد، ولی `OF5` فقط دامنهای را گرفت که API آپشن کالا به آن وصل نیست — endpoint زنده همچنان `/365` محاسبه میکند (`DOM-01`). و در لایهٔ ایمنی، آشکارساز بحران طلا با سه قانون مکتوب، سه ورودی هاردکد `None/None/False` میگیرد و همیشه `NORMAL` برمیگرداند (`DOM-02`). در برابرش، این قسمت **سالمترین نقاط سامانه** را هم پیدا کرد: کاناری چهارحالتهٔ اخبار با shadow parity و auto-halt، امنیت سهگانهٔ GoldDesk که برعکس `CFG-01` در production **fail-closed** است، و ۳۰ ماژول حسابرسی ISA/IFRS که واقعاً به ۲۹ endpoint وصلاند. تمایز نهایی دیگر «زیرساخت خوب / نتیجه بد» نیست، بلکه **«همان فایل میتواند هم الگوی درست و هم الگوی شکست را داشته باشد»**: `core/trading_constants` تکمنبع درستی است که `domain/options` از آن استفاده میکند و `src/gold_desk` نه؛ `services/gold` هم `kill_switch` را درست وصل کرده و هم `feed_health`ای را که باید تغذیهاش کند رها کرده است.
