# گزارش حسابرسی جامع — سامانه معاملات الگوریتمی TEMCE

| | |
|---|---|
| **تاریخ حسابرسی** | ۲۰۲۶-۱۱-۱۲ |
| **شاخه / آخرین کامیت** | `main` · `68f2c6c0 fix: resolve remaining test + mypy + lint errors` |
| **سطح** | Deep-Dive، مبتنی بر شواهد کد (نه صرفاً بازخوانی گزارش‌های قبلی) |
| **دامنه** | `services/`, `core/`, `domain/options/`, `brsapi/`, `backtesting/`, `apps/api/`, `src/gold_desk/`, CI/CD، استقرار |
| **جایگزین** | `AUDIT_REPORT.md` (۲۰۲۶-۰۸-۲۳، قدیمی) |
| **مکمل** | `DEEP_REVIEW_PART1.md`, `DEEP_REVIEW_PART2.md` |

---

## خلاصه اجرایی

ادعاهای مطرح‌شده در **پنج سند بازبینی موجود** در برابر کد واقعی فعلی راستی‌آزمایی شدند. نتیجهٔ اصلی:

> **پروژه به طور معنی‌داری سالم‌تر از آن چیزی است که گزارش‌های قدیمی نشان می‌دهند** — ۱۸ ادعای «اصلاح شد» حسابرسی اوت، ۱۲ ادعای آدیت ۱۰ نوامبر، و بخش عمدهٔ «خطاهای پنهان» همگی در کد فعلی **واقعاً رفع شده‌اند**. `ruff` صفر خطا، `compileall` تمیز، و هفت ماژول حیاتی بدون خطای نحوی.
>
> **اما سه یافتهٔ بحرانی/مهم همچنان زنده است** و مهم‌تر اینکه چند **ناسازگاری تازه** کشف شد که در هیچ گزارش قبلی نیامده بود — در رأس آن‌ها **چهار مقدار متفاوت برای تعداد روز معاملاتی سال** در یک سیستم.

### امتیاز کلی

| بُعد | امتیاز (از ۱۰) | وضعیت |
|---|---|---|
| ایمنی مالی / Fail-closed | ۹.۰ | 🟢 عالی |
| صحت محاسبات بک‌تست و اندیکاتورها | ۸.۵ | 🟢 خوب |
| امنیت / lint / پارس کد | ۸.۵ | 🟢 خوب |
| منطق مالی آپشن‌ها | ۸.۵ | 🟢 خوب |
| **صحت اندازهگیری دقت و افق** | **۳.۵** | 🔴 **بحرانی** |
| **یکپارچگی ثابت‌های بازار** | **۴.۰** | 🔴 **نیازمند اصلاح** |
| کیفیت داده / نقدینگی | ۶.۰ | 🟠 متوسط |
| DRY / معماری | ۶.۵ | 🟡 متوسط |
| تست و CI | ۶.۵ | 🟡 مشروط |
| **میانگین** | **۶.۸** | 🟡 **قابل استقرار، ولی نه قابل اتکا از نظر متریک عملکرد** |

---

## ۱. دامنه و روش

**منابع ادعا (پنج سند):**
1. `AUDIT_REPORT.md` — ۲۰۲۶-۰۸-۲۳، ۱۸ ادعای «اصلاح شد ✅»
2. `docs/signal-pipeline-deep-diagnosis-en.md` — ۲۰۲۶-۰۹-۲۴، ادعاهای P0/P1
3. `HIDDEN_ERRORS_REPORT.md` — ادعای ۲۳ خطای پنهان (۳ کرش بحرانی)
4. `AUDIT_REPORTS/FULL_ANALYSIS_20261110.md` — ۲۰۲۶-۱۱-۱۰، ادعای رفع ۱۲ ایراد
5. `AUDIT_REPORTS/MODULAR_TEMCE/` — ۳۶+ گزارش ماژولار (امنیت، داده، تست، استقرار)

**روش:** جستجوی محتوایی مستقیم در کد (شماره خطReportها کهنه بودند)، تطبیق با `git log`، اجرای `ast.parse`، `python -m compileall -q` و `ruff check .`. عامل‌های تأیید کد به دلیل قطعی شبکه در میانهٔ کار از دسترس خارج شدند و تمام بررسی‌ها مستقیم با ابزار فایل/ترمینال تکمیل شد.

**محدودیت:** تست‌های کامل `pytest`، اتصال به پایگاه داده زنده، و اجرای سرور انجام نشد. نتایج «صحت کد» است، نه «صحت عملکرد معاملاتی زنده».

---

## ۲. ماتریس راستیآزمایی ادعاهای `AUDIT_REPORT.md` (۱۸ مورد)

| # | ادعا | شاهد کد | حکم |
|---|---|---|---|
| ۱ | Default Release → Fail-closed | `quant_signal_orchestrator.py:1300-1319` → `reject` / `REJECTED_ON_ERROR` | ✅ |
| ۲ | Data Quality هاردکد → محاسبه واقعی | `:1235-1239` → `compute_data_quality_score(...)` از `core/indicators.py:281` | ✅ |
| ۳ | Smart Money weights → config | `smart_money/layer1_price_volume.py:13-36` → `_load_pvs_weights()` از `config/smart_money.yaml:13-21` | ✅ |
| ۴ | تکرار RSI/ATR/Trend → ماژول واحد | `core/indicators.py` ایجاد شد؛ `feature_engine.py:1142` و `confidence_scorer.py:306` صرفاً wrapper اند | 🟠 جزئی ← §۵ |
| ۵ | هزینه معاملاتی در بک‌تست | `signal_backtest_engine.py:241-245,258` | ✅ |
| ۶ | Walk-Forward در آموزش ML | `ml_signal_connector.py:539-554,586` | ✅ |
| ۷ | MACD → EMA واقعی | `core/indicators.py:166-167,189` | ✅ |
| ۸ | Sharpe annualization | `signal_backtest_engine.py:383` → `252 ** 0.5` | ✅ (ام ← §۴.۵) |
| ۹ | Max Drawdown → cumprod | `signal_backtest_engine.py:389-391` | ✅ |
| ۱۰ | Buckets کالیبراتور متقارن | `probability_calibrator.py:91-92` → `0.0…1.0` | 🟠 جزئی ← §۵ |
| ۱۱ | حذف کف ۰.۰۰۱ Profit Factor | `trade_metrics.py:26` → `max(abs(sum(losing)), 1.0)` | ✅ |
| ۱۲ | Trend Strength یکپارچه | `confidence_scorer.py:306-308` → `return compute_trend_strength(closes, period)` | ✅ **تأیید شد در این پاس** |
| ۱۳ | Volatility یکپارچه | `confidence_scorer.py:311-313` → `compute_volatility_regime(...)`؛ `*20` حذف شد | ✅ **تأیید شد** |
| ۱۴ | `cost_r` با `abs()` | `signal_decision_engine.py:1125` → `costs_pct / abs(candidate.stop_loss_pct) if abs(...) > 0.001` | ✅ **تأیید شد** |
| ۱۵ | آستانههای Walk-Forward سختگیرانهتر | `walk_forward_validator.py:246-250` → `avg_overfitting < 0.10` **و** `avg_test_sharpe > 0.5` | ✅ **تأیید شد** |
| ۱۶ | Stop/Target از سیگنال | `paper_trading_service.py:161-169` (پارس اول، fallback هاردکد باقیست) | 🟠 جزئی |
| ۱۷ | Wilder's RSI | `core/indicators.py:87-90` | ✅ |
| ۱۸ | کد تکراری feature_engine | `feature_engine.py:1141-1160` → wrapperهای نازک delegation | ✅ **تأیید شد** |

**نتیجه:** ۱۵ ✅ / ۳ 🟠. **هیچ مورد «هنوز خراب» در مسیرهای اصلی باقی نمانده است.**

---

## ۳. راستیآزمایی سایر اسناد

### ۳.۱ `HIDDEN_ERRORS_REPORT.md` — عمدتاً رفع شده

| ادعا | کد فعلی | حکم |
|---|---|---|
| 🔴 `_stage_time` NameError (۱۵ نقطه، کرش ۵۰۰) | **صفر رخداد** در `quant_signal_orchestrator.py` | 🚫 رد شد |
| 🔴 `compute_trend_strength` پارامتر `period` نادیده میگیرد | `core/indicators.py:232` → `for i in range(1, period + 1)` دقیقاً رعایت میکند | 🚫 رد شد |
| 🟠 `float_turnover_pct` ۱۰۰× / `net_inst_ratio` مخرج غلط | `feature_engine.py:377-379` → `int(shares_count * free_float_pct / 100)`؛ `:539-543` و `:591-594` clamp + مخرج `float_shares_count` | ✅ رفع شد |
| 🟠 `gamma = inf` | `domain/options/pricing.py:38-46,73-76` → `_vol_sqrt_t()` guard | ✅ رفع شد |
| 🟠 `cvar = nan` | `var_calculator.py:124-129` → `tail.size > 0` + `isfinite` | ✅ رفع شد |
| 🟠 covered_call / `contract_size` | `margin_engine.py:138-144` → ISSUE-101 رفع، `short_call_shares` محاسبه میشود | ✅ رفع شد |
| 🟠 عبارات مرده tree_pricing | `tree_pricing.py:91` → `nu = (r - q - 0.5*sigma*sigma) * dt` انتساب یافته | ✅ رفع شد |
| 🟠 bulk_insert تعداد دروغین | `brsapi/repositories/base.py:57-105` → هشدار + `attempted` به عنوان تقریب | ✅ رفع شد |
| 🟠 dedup هرگز چک نمیشود | `sync_service.py:423-424` → `if dedup_seconds > 0: needs_sync(..., params=params)` | ✅ رفع شد |

### ۳.۲ `FULL_ANALYSIS_20261110.md` (۱۲ ایراد)

- `brsapi/client.py:404` → `result.error_code not in _CB_IGNORE_CODES` ✅
- `brsapi/models/commodity.py:258` → `UniqueConstraint("symbol","date", name="uq_pro_daily_sym_date")` ✅ (گزارش نام `currency_pair` / `uq_gold_currency_pro_daily` ذکر کرده بود → **جزئی نادرست در نامگذاری**)
- `src/gold_desk/backtest_runner.py:47` و `performance.py:16` → `250` ✅
- کامیتهای ادعاشده (`86e60589`, `76200c1f`, `213e5192`, `4c07cc52`) همگی در `git log` موجودند ✅

### ۳.۳ `signal-pipeline-deep-diagnosis-en.md` (P0/P1)

| ادعا | حکم |
|---|---|
| P0#1 آموزش خودکار غیرقابلدسترس (`LIMIT 20`) | 🚫 رد شد — `LIMIT 100`، آموزش در `:242` قابل دسترس |
| P0#2 نشت هدف via `closes[-1]` | 🚫 رد شد — هدف از `closes[-2]`، کامنت صریح ضد lookahead |
| P0#5 marker ادغام در `router.py` | 🚫 رد شد — فایل تمیز، ۷۶۱ خط |
| **P0#3 افق اشتباه ارزیابی** | ❌ **زنده — بحرانی** |
| **P0#4 دقت last-source-wins** | ❌ **زنده — بالا** |
| P1b نقدینگی proxy | ❌ **زنده — متوسط** |
| P1c تأیید پورتفولیو unconditional | ⚠️ قدیمی — validator واقعی اضافه شده |

---

## ۴. حسابرسی ابعاد (یافتههای مستقل)

### ۴.۱ امنیت — 🟢 خوب
- **bandit:** `[tool.bandit]` در `pyproject.toml:182` با `skips = ["B608","B613","B104"]` همراه **توجیه فنی مکتوب** (identifierها pre-validate میشوند، مقادیر کاربر bind parameter، bidi به خاطر متن فارسی، `0.0.0.0` پشت reverse proxy).
- **SHA1:** تنها ۳ مورد، همگی `usedforsecurity=False` (غیرامنیتی، صرفاً digest) ✅
- **SQL injection:** f-stringهای `brsapi/quality.py` فقط identifier با **allowlist**؛ مطابق توجیه bandit ✅
- **Auth:** ۸۴ فایل endpoint؛ الگوی `Depends` / `get_current_user` تقریباً در همه دیده میشود
- **CORS:** `apps/api/app.py:1075` → `settings.cors_origins` (config-driven، نه `*`) ✅
- **اسرار:** تنها `core/enums/provider.py:29 API_KEY = "api_key"` (نام enum، بیضرر)؛ `.env` در `.gitignore`

### ۴.۲ داده / DB / Ingestion — 🟡 متوسط
- `ON CONFLICT DO UPDATE` در `base.py:89-93` پشتیبانی میشود ✅، ولی `sync_service.py:1092` همچنان به حذف خاموش رکوردها با `DO NOTHING` اشاره دارد → **بررسی دقیقتر لازم است**
- بررسی تازگی داده: `freshness_adapter.py`, `point_in_time.py`, `data_layer.py` وجود دارند ✅ (اما گیت تصمیمگیرندهٔ سیگنال همچنان proxy است ← P1a)

### ۴.۳ تست / CI — 🟡 مشروط
| چک | نتیجه |
|---|---|
| `ast.parse` روی ۷ ماژول حیاتی | ✅ همگی OK |
| `python -m compileall -q services core apps/api domain brsapi` | ✅ exit 0 |
| `ruff check .` | ✅ **All checks passed!** |
| تعداد تستها | ۴۴۴۰ فایل `test_*.py` / ۵۰ `conftest.py` |
| پیکربندی pytest | `pyproject.toml:155` → `-m "not needs_db"` ⚠️ |

**یافتههای CI:**
- 🟠 `addopts = ["-m", "not needs_db"]` → **تستهای وابسته به DB به طور پیشفرض اجرا نمیشوند**
- 🟠 Job `needs-db` در `ci.yml:328-331` و `Secret scan` در `:199-200` هر دو `continue-on-error: true`
- 🟠 `ESLint` در `ci-pr.yml:208` و `benchmark` در `:175` نیز advisory هستند
- ۶ workflow موجود؛ پوشش اسمی خوب است، ولی **چند گیت کلیدی واقعاً مسدودکننده نیستند**

### ۴.۴ استقرار
- `docker-compose.yml` سرویس با نام `api` **ندارد** (شامل: `timescaledb`, `redis`, `backend`, `ingestion`, `worker`, `currency`, `frontend`) → `docker compose up api` روی فایل پیشفرض شکست میخورد
- `docker-compose.production.yml:36-39` سرویس `api` را با `image: ghcr.io/.../api:latest` تعریف کرده ✅
- **توصیه:** یا نام `backend` → `api` یکسانسازی شود، یا مستندات استقرار صریحاً از production compose استفاده کند

### ۴.۵ 🔴 یافتهٔ جدید: ناسازگاری تعداد روز معاملاتی (در هیچ گزارشی نبود)

| منبع | مقدار | کاربرد |
|---|---|---|
| `src/gold_desk/backtest_runner.py:47` | **۲۵۰** | Sharpe/Sortino طلا (TSE) |
| `src/gold_desk/performance.py:16` | **۲۵۰** | متریکهای عملکرد |
| `acceptance.yaml:11` (`global_xau`) | **۲۵۲** |Production Gate — XAU |
| `acceptance.yaml:17,23` (`domestic_ime/etf`) | **۲۴۰** | Production Gate — داخلی |
| `services/signal_backtest_engine.py:383` | **۲۵۲** | Sharpe بکست سیگنال |
| `services/options_backtest_service.py:19` | **۲۵۲** | Sharpe آپشنها |
| `backtesting/composer/phase_runner.py:230,261` | **۲۵۲** | Sharpe/Sortino composer |

**اثر:** annualization بسته به مسیر تا ~۵٪ تفاوت میکند؛ یک استراتژی واحد بسته به اینکه از کدام موتور ارزیابی شود، Sharpe متفاوتی میگیرد و ممکن است در برابر `acceptance.yaml` (آستانهٔ `min_oos_sharpe: 1.00`) تصمیم متفاوتی بگیرد. **این نقض «منبع واحد حقیقت» است که خود `acceptance.yaml` ادعایش را دارد.**

---

## ۵. یافتههای زنده (جدول نهایی بر اساس شدت)

| # | یافته | فایل | شدت |
|---|---|---|---|
| ۱ | ارزیابی خروجی سیگنال در افق اشتباه (فیلتر ۵-۳۰ روز تقویمی، بدون `timeframe`، قیمت آخرین snapshot) | `quant_signal_orchestrator.py:1841-1905` | 🔴 بحرانی |
| ۲ | چهار مقدار متفاوت `trading_days_per_year` (۲۴۰/۲۵۰/۲۵۲) در موتورهای مختلف | §۴.۵ | 🔴 بحرانی |
| ۳ | دقت بازار last-source-wins (`GROUP BY market,source` ولی مصرفکننده فقط کلید `market`) | `signal_accuracy_tracker.py:208` + `quant_signal_orchestrator.py:1975` | 🟠 بالا |
| ۴ |liquidity/fill تابع خالص `abs(change_pct)` بدون حجم/عمق order-book | `quant_signal_orchestrator.py:1242-1244` | 🟠 بالا |
| ۵ | گیتهای CI مسدودکننده نیستند (`needs-db`, secret-scan, ESLint) + `-m "not needs_db"` | `ci.yml`, `ci-pr.yml`, `pyproject.toml:155` | 🟠 بالا |
| ۶ | DRY ناقص: RSI/ATR مستقل و متفاوت در `multi_market_signal_engine.py:119`, `adaptive_engine.py:370`, `screener110_service.py:218` | سه سرویس | 🟡 متوسط |
| ۷ | `DEFAULT_BUCKETS` متقارن شد ولی کوئری ثانویه همچنان از ۰.۵۰ شروع میکند | `probability_calibrator.py:635-639` | 🟡 متوسط |
| ۸ | fallback هاردکد ۵٪/۸٪ در پرتفوی آزمایشی | `paper_trading_service.py:163,167,169` | 🟡 متوسط |
| ۹ | proxy تعداد نقاط قیمتی از voting coverage در نبود تاریخچه | `quant_signal_orchestrator.py:1222-1234` | 🟡 متوسط |
| ۱۰ | ناسازگاری lifecycle (یک سینگلتون در برابر سه سرویس per-call) | `signal_decision_engine.py:1177` و همتایان | 🟡 متوسط |
| ۱۱ | سرویس `api` در compose پیشفرض تعریف نشده | `docker-compose.yml` | 🟡 متوسط |
| ۱۲ | نام `UniqueConstraint` در گزارش ۱۰ نوامبر با کد فعلی مطابق نیست | `FULL_ANALYSIS_20261110.md` | 🟢 پایین (مستندات) |

---

## ۶. ماتریس ریسک

| | احتمال کم | احتمال متوسط | احتمال بالا |
|---|---|---|---|
| **اثر بحرانی** | — | ۲ (ثابتهای بازار) | **۱ (افق ارزیابی)** |
| **اثر بالا** | — | ۴, ۵ | ۳ |
| **اثر متوسط** | ۱۲ | ۶, ۷, ۸, ۹, ۱۰, ۱۱ | — |

**جمع بندی ریسک:** مهمترین خطر «خراب بودن کد» نیست — کد از این نظر سالم است. خطر اصلی **«اعتماد به اعدادی است که سیستم دربارهٔ عملکرد خودش گزارش میدهد»**: تا وقتی افق ارزیابی (۱) و تجمیع دقت (۳) درست نشوند، هر عدد accuracy، هر تریگر retrain و هر گزارش Sharpe قابل اتکا نیست.

---

## ۷. نقشه اصلاح (اولویتبندی شده)

**فاز ۰ — مسدود کردن ادعاهای عملکردی (قبل از هر تصمیم معاملاتی)**
1. `due_at` برای هر سیگنال؛ برچسبگذاری فقط پس از تعداد **جلسات معاملاتی** متناظر با `timeframe`؛ قیمت خروج as-of؛ نگهداشت ردیفهای عقبافتاده در backlog.
2. تجمیع `correct/total` یکبار به ازای هر بازار + نگهداشت breakdown منبع؛ آستانهٔ حداقل نمونه برای alert/retrain.
3. یکسانسازی `trading_days_per_year` به **یک منبع واحد** (`acceptance.yaml` یا `config/market_calendar.py`) و حذف ۲۵۲/۲۵۰/۲۴۰ پراکنده.

**فاز ۱ — واقعگرایی اجرا و گیتها**
4. liquidity/fill از حجم و عمق واقعی؛ نبود داده = حالت degraded صریح، نه امتیاز مصنوعی.
5. تبدیل `needs-db` و secret-scan و ESLint به گیتهای مسدودکننده (یا حداقل گزارش شکست به عنوان failure).
6. تعریف سرویس `api` در compose پیشفرض یا اصلاح مستندات استقرار.

**فاز ۲ — بدهی فنی**
7. حذف RSI/ATR تکراری در سه سرویس → ارجاع به `core/indicators.py`.
8. اصلاح buckets ثانویهٔ کالیبراتور و fallback پرتفوی آزمایشی.
9. یکسانسازی lifecycle (DI) و تبدیل lazy importها به مرزهای صریح.

**فاز ۳ — بهروزرسانی اسناد**
10. بایگانی `AUDIT_REPORT.md`، `HIDDEN_ERRORS_REPORT.md` و `signal-pipeline-deep-diagnosis-en.md` به عنوان **اسناد تاریخی**؛ این报告 به عنوان مرجع وضعیت فعلی.

---

## پیوست: دستورات اجراشده و نتایج

```
git log --oneline -12            → 12 کامیت، عمدتاً fix/security/audit
grep "_stage_time" orchestrator  → 0 رخداد (ادعای کرش بحرانی رد شد)
ast.parse (7 ماژول حیاتی)         → همگی OK
python -m compileall -q ...      → exit 0
ruff check .                     → All checks passed!
find test_*.py / conftest.py     → 4440 / 50
```

**شفافیت:** تست کامل `pytest`، پایگاه داده زنده، و اجرای سرور انجام نشد؛ عاملهای تأیید کد به دلیل خطای شبکه (`ENOTFOUND www.workbuddy.ai`) در دسترس نبودند و کلیه بررسیها مستقیم با ابزار فایل و ترمینال انجام شد. نتیجهٔ «اجراپذیر» به معنای صحت نحوی و lint است، نه سلامت ران تایم انتها به انتها.

---

*این گزارش صرفاً بر اساس کد موجود در checkout فعلی تهیه شده و هیچ فایل منبعی را تغییر نداده است (بهجز ایجاد فایلهای گزارش).*
