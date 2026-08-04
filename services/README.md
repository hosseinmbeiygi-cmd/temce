# 🧠 خدمات (services/) — قلب برنامه بازار سرمایه ایران

این پوشه **قلب منطق تجاری** پلتفرم است. همه دادهها (از `brsapi/`, `providers/`, `repositories/`) از طریق لایه سرویس به API، جابها و داشبورد تبدیل میشوند.

> وضعیت: **بررسی و بهینهسازی فاز ۳** — اشکالات رفع شده و README بهروز شده است.

---

## 📑 فهرست محتوا

1. [معماری لایهها](#-معماری-لایهها)
2. [موتورهای سیگنال (Signal Engines)](#-موتورهای-سیگنال-signal-engines)
3. [Smart Money Engine](#-smart-money-engine)
4. [سرویس صندوقها (Fund Service)](#-سرویس-صندوقها-fund-service)
5. [سرویسهای بازار و داده](#-سرویسهای-بازار-و-داده)
6. [سرویسهای تحلیلی](#-سرویسهای-تحلیلی)
7. [سرویسهای کاربری](#-سرویسهای-کاربری)
8. [دستیار گفتگو (Assistant)](#-دستیار-گفتگو-assistant)
9. [سرویسهای Codal و اخبار](#-سرویسهای-codal-و-اخبار)
10. [زیرساخت مشترک (data_mesh, chat, codal_analysis, quantitative)](#-زیرساخت-مشترک)
11. [خط لوله کامل سیگنال](#-خط-لوله-کامل-سیگنال)
12. [اشکالات رفعشده در فاز ۳](#-اشکالات-رفعشده-در-فاز-۳)
13. [تستها](#-تستها)
14. [راهنمای توسعه](#-راهنمای-توسعه)

---

## 🏗 معماری لایهها

```
apps/api (endpoints)
   │  Dependency Injection (apps/api/dependencies.py)
   ▼
services/  ← شما اینجا هستید
   │
   ├── Signal Engines      → multi_market_signal_engine, quant_signal_orchestrator, ...
   ├── Smart Money         → smart_money_service, smart_money/
   ├── Fund Service        → fund_service, fund_sync_service
   ├── Market & Data       → market_service, quote_service, orderbook_service, ...
   ├── Analytics           → screener, recommendation, signal_accuracy_tracker, ...
   ├── User Services       → user_service, portfolio_service, watchlist_service, ...
   ├── Assistant           → stock_assistant_service, unified_assistant_service
   ├── Codal & News        → codal_*, news_*
   └── Shared Subpackages  → data_mesh/, chat/, codal_analysis/, quantitative/
   │
   ▼
repositories/ → domain/ → models/ → core/ (database, cache, logging)
```

**قانون طلایی:** سرویسها فقط از طریق `repositories/` یا `core.database` به DB وصل میشوند و خروجی خود را بهصورت `Result[T]` برمیگردانند (هرگز دیکشنری خام یا exception عمومی).

---

## 🔔 موتورهای سیگنال (Signal Engines)

قلب سیستمی که سیگنالهای خرید/فروش را در ۷ بازار تولید میکند.

### `multi_market_signal_engine.py` — موتور سیگنال چندبازاری

- **پوشش بازارها:** stock, gold, currency, crypto, option, commodity, ime
- **ساختار خروجی:** `MarketSignal` با **۶ فیلد الزامی** + **۵ فیلد حرفهای**:
  1. `symbol` (نماد)
  2. `direction` (buy/sell/hold/wait)
  3. `timeframe` (daily/2day/3day/weekly/monthly/quarterly)
  4. `entry_zone` (نقطه ورود)
  5. `stop_loss` (حد ضرر)
  6. `targets` (اهداف سود)
  7. `position_sizing` (حجم پیشنهادی)
  8. `confirmation_condition` (شرط تأیید)
  9. `reason` (علت و منطق)
  10. `invalidation` (شرایط فسخ)
  11. `trailing_stop` (مدیریت پس از ورود)
- **آمار فنی:** RSI، SMA/EMA، ATR، مومنتوم، روند، حجم، حمایت/مقاومت + فاکتور بنیادی از `codal_audit_summary`
- **تنوع بازار:** کووتای per-market تا یک بازار کل لیست را نگیرد

### `quant_signal_orchestrator.py` — ارکستراتور سیگنال کوانت

خط لوله کامل ۷ مرحلهای:

```
1. MultiMarketSignalEngine  → سیگنالهای قانونمبنا
2. MLSignalConnector        → پیشبینی ML برای هر سیگنال
3. SignalVotingSystem       → ترکیب رأی قانون + ML (+ Smart Money)
4. ProbabilityCalibrator    → احتمال برد کالیبرهشده (باکت/پلات/ایزوتونیک)
5. ConfidenceScorer         → اطمینان چندعاملی
6. SignalDecisionEngine     → ۱۰ گیت تصمیم (release/watchlist/reject)
7. CrossMarketCorrelator    → رژیم بازار از قیمتهای واقعی
```

خروجی `EnrichedSignal` با `calibrated_probability`, `decision_verdict`, `net_expectancy_r` و...

**حلقه بازخورد:** سیگنالها در `signal_accuracy` ذخیره میشوند؛ دفعه بعد `_record_outcomes_and_retrain()` نتیجه را میسنجد و در صورت افت دقت (<55٪) بازآموزی خودکار را صدا میزند.

### `signal_decision_engine.py` — موتور تصمیم ۱۰ گیتی

هر سیگنال باید از ۱۰ گیت بگذرد:

| # | گیت | معیار |
|---|------|--------|
| 1 | داده | کیفیت داده ≥ 0.80 |
| 2 | مدل | مدلهای فعال/اختلافنظر |
| 3 | احتمال | احتمال کالیبره ≥ آستانه پویا |
| 4 | رژیم | رژیم بازار از قیمت واقعی |
| 5 | اجماع | توافق مدلهای ensemble |
| 6 | نقدشوندگی | نمره ≥ 0.50 |
| 7 | ریسک/پاداش | RR ≥ 1.0 |
| 8 | امید ریاضی | EV خالص > 0.05R |
| 9 | پرتفوی | ریسک باز ≤ 25٪ |
| 10 | اجرا | اسپرد و شرایط بازار |

گرید نهایی: **A+ / A / B / WATCHLIST / REJECT** — همه آستانهها از `config/signal_policy.yaml` با override بازار خوانده میشوند (`get_gate_config(gate, market)`).

### سایر موتورها

| فایل | نقش |
|------|-----|
| `signal_voting_system.py` | رأیگیری weighted/unanimous/ml_override + رأی Smart Money |
| `confidence_scorer.py` | اطمینان از تاریخچه + توافق مدل + روند + نوسان |
| `probability_calibrator.py` | کالیبراسیون سلسلهمراتبی (market+tf+regime → market → global → bootstrap) |
| `multi_timeframe_confirmer.py` | تأیید چندبازهای — آستانهها از `required_agreement` |
| `risk_adjusted_filter.py` | فیلتر ریسکی |
| `walk_forward_validator.py` | اعتبارسنجی walk-forward |
| `signal_backtest_engine.py` | بکتست سیگنال |
| `signal_accuracy_tracker.py` | ردیابی دقت |
| `signal_performance_tracker.py` | ردیابی عملکرد |
| `signal_feature_pipeline.py` | استخراج feature برای ML |
| `ensemble_engine.py` / `adaptive_engine.py` / `cascade_engine.py` | مدلهای ترکیبی |
| `ensemble_optimizer.py` | بهینهسازی وزن ensemble |

---

## 💰 Smart Money Engine

### `smart_money_service.py` — سرویس اصلی

```python
result = await SmartMoneyService(session=session).analyze("فولاد")
# result.value = {
#   "smart_money_score": 0.63, "phase": "accumulation",
#   "scores": {"accumulation": .., "absorption": .., "float_lock": ..,
#              "breakout_readiness": .., "buyer_power": .., "microstructure": ..},
#   "penalties": {"distribution_risk": .., "fake_breakout_risk": .., "dead_compression": ..},
#   "meta": {"engine_version", "analysis_mode", "data_quality_score", "confidence", ...}
# }
```

**داده واقعی، نه Mock:** اگر نماد در `brsapi_symbol_snapshots` نباشد → `Result.fail` (نه امتیاز ساختگی).

### `smart_money/` — موتور ۹ لایهای

| لایه | فایل | نقش |
|------|------|-----|
| 1 | `layer1_price_volume.py` | قیمت/حجم |
| 2 | `layer2_absorption.py` | جذب سفارش |
| 3 | `layer3_ownership.py` | مالکیت حقیقی/حقوقی |
| 4 | `layer4_compression.py` | فشردگی (compression) |
| 5 | `layer5_relative_strength.py` | قدرت نسبی |
| 6 | `layer6_breakout.py` | شکست |
| 7 | `layer7_buyer_power.py` | قدرت خریدار |
| 8 | `layer8_microstructure.py` | ریزساختار |
| 9 | `layer9_breakout_quality.py` | کیفیت شکست |

**ارکستراسیون:**
- `scoring_engine.py` — گیت کیفیت داده → محاسبه لایهها → Feature Store → نمرات composite (acc/abs/fl/br/smc) → جریمهها → فاز → اطمینان
- `parallel_engine.py` — پردازش موازی با semaphore + retry + timeout برای غربالگری انبوه
- `feature_store.py` — کش ویژگیها با TTL
- `data_quality.py` — گیت کیفیت داده (نحوه رد داده ضعیف)
- `config_loader.py` — وزنها و آستانهها از YAML
- `confidence.py` — تخمین عدمقطعیت
- `phase_alerts.py` — هشدار تغییر فاز
- `advanced_analytics.py` — تحلیلها

---

## 🏦 سرویس صندوقها (Fund Service)

### `fund_service.py`

- **دو حالت:** InMemory (توسعه/تست) و PostgreSQL (تولید)
- **مسئولیتها:**
  - CRUD صندوق + جستجو بر اساس `symbol`/`name`/`ISIN` + فیلتر نوع
  - تاریخچه NAV (`FundNavRepository`) و ترکیب پرتفوی (`FundHoldingRepository`)
  - `update_from_brsapi(symbol, brsapi)` — دریافت لحظهای و ذخیره (قیمت، حجم، NAV، حقیقی/حقوقی)
  - `ensure_seeded()` — seed خودکار داده نمونه در DB خالی
- **نمونه داده:** ۷۵+ صندوق واقعی ایرانی با نام فارسی

### `fund_sync_service.py`

همگامسازی صندوقها از BrsApi.

---

## 📊 سرویسهای بازار و داده

| سرویس | نقش |
|--------|-----|
| `market_service.py` | نمای کلی بازار، بیشترین/کمترین رشد |
| `quote_service.py` | قیمت لحظهای |
| `orderbook_service.py` | دفتر سفارش |
| `trade_service.py` | معاملات |
| `market_watch_helper.py` | دریافت بازارنما |
| `market_health_index.py` | شاخص سلامت بازار |
| `historical_data_service.py` / `history_backfill_service.py` | داده تاریخی/بازپرکنی |
| `instrument_service.py` / `symbol_service.py` / `symbol_catalog.py` | نمادها و کاتالوگ |
| `symbol_detail_service.py` | جزئیات کامل نماد |
| `realtime_service.py` / `realtime_quote_service.py` | قیمت زنده |
| `tsetmc_client.py` | کلاینت TSETMC CDN (سهم مستقیم) |
| `macro_service.py` | طلا/ارز/شاخصهای کلان |
| `block_trade_detector.py` | معاملات بلوکی |
| `queue_analysis.py` / `queue_analysis_service.py` | تحلیل صف خرید/فروش |

---

## 📈 سرویسهای تحلیلی

| سرویس | نقش |
|--------|-----|
| `screener_service.py` / `screener110_service.py` / `smart_screener_v2.py` | غربالگری |
| `recommendation_service.py` | پیشنهاد سهم |
| `feature_engine.py` | موتور ویژگیها |
| `analytics_service.py` | تحلیل |
| `fundamental_service.py` | بنیادی |
| `mass_scanner_service.py` | اسکن انبوه |
| `hidden_accumulation.py` | انباشت پنهان |
| `fake_queue_detector.py` | تشخیص صف جعلی |
| `manipulation_detector.py` | تشخیص دستکاری |
| `iran_fear_greed_index.py` | شاخص ترس/طمع |
| `gap_prediction.py` | پیشبینی گپ |
| `historical_level_analyzer.py` | سطوح تاریخی |
| `real_return_calculator.py` | بازده واقعی |
| `live_risk_monitor.py` | پایش ریسک زنده |
| `options_analytics.py` / `options_reference.py` / `options_service.py` | آپشنها |
| `backtest_framework.py` / `backtest_service.py` / `event_backtest.py` | بکتست |
| `strategy_generator.py` / `compose_service.py` | ساخت/ترکیب استراتژی |
| `training_service.py` / `global_training_service.py` / `auto_retrain_pipeline.py` | آموزش ML |
| `inference_service.py` / `ml_signal_connector.py` | استنتاج ML |
| `ensemble_optimizer.py` | بهینهسازی |

---

## 👤 سرویسهای کاربری

| سرویس | نقش |
|--------|-----|
| `user_service.py` | کاربران و احراز هویت |
| `portfolio_service.py` | پرتفوی |
| `watchlist_service.py` | دیدهبان |
| `alert_service.py` | **هشدار قیمت/حجم/RSI** — با همنرمالسازی فیلد (`price` ↔ `price_last`)، cooldown ضداسپم، و کانالهای telegram/console/email/sound |
| `saved_filters.py` | فیلترهای ذخیرهشده |
| `report_service.py` | گزارشها |
| `job_service.py` | مدیریت جابها |
| `monitoring_service.py` | پایش |
| `query_logger.py` | لاگ پرسوجوها |
| `diagnostics_runner.py` | عیبیابی |
| `sync_master_service.py` | همگامسازی سراسری |

---

## 🤖 دستیار گفتگو (Assistant)

### `stock_assistant_service.py`

- تحلیل گفتگومحور فارسی با ۱۰+ اندیکاتور (SMA/EMA/RSI/MACD/BB/Stochastic/ATR/VWAP/Ichimoku/Fib/MFI)
- تشخیص الگوهای کندل، پرتفوی، هشدار، چندبازهای، حجم-در-قیمت، همبستگی، بکتست

### `unified_assistant_service.py`

- تشخیص intent برای **همه** امکانات برنامه: بازار، تحلیل، مقایسه، دیدهبان، هشدار، پرتفوی، بکتست، غربالگری، ML، کدال، اخبار، ماکرو، نقشه حرارتی، ریسک، گزارش، ناهنجاری، سیگنال، کریپتو، کامودیتی
- نگاشت مترادفهای محاورهای فارسی به فیلترهای ساختاریافته (`_SCREENER_SYNONYMS`)

---

## 📰 سرویسهای Codal و اخبار

| سرویس | نقش |
|--------|-----|
| `codal_service.py` | اطلاعیههای کدال |
| `codal_accounting_service.py` | حسابداری |
| `codal_attachment_service.py` | پیوستها (S3 خواندن هنوز NotImplemented — ردیابی شده) |
| `codal_download_service.py` / `codal_import_service.py` / `codal_financial_import_service.py` | دانلود/ایمپورت |
| `codal_financial_service.py` | مالی |
| `news_ingestion.py` / `news_service.py` / `news_dedup.py` / `news_filter.py` | اخبار RSS با dedup و فیلتر |
| `persian_sentiment_service.py` | احساسات فارسی |

---

## 🧩 زیرساخت مشترک

| پوشه | نقش |
|------|-----|
| `data_mesh/` | یکپارچهسازی داده بین سرویسها |
| `chat/` | موتور چت (intent, entity, sentiment, learning, personalizer, suggestion) |
| `codal_analysis/` | تحلیل عمیق کدال (IFRS, حسابرسی، تقلب، رویداد) |
| `quantitative/` | ابزارهای کمی (`normalizer.py`) |

---

## 🔄 خط لوله کامل سیگنال

```
مثال: POST /api/v1/signals/generate

1. MultiMarketSignalEngine.generate_all()
   └── هر بازار: Snapshot + History + Codal → MarketSignal (۱۱ فیلد)
2. (اختیاری ML) QuantSignalOrchestrator._get_ml_predictions()
3. SignalVotingSystem.vote()  → رأی نهایی + استراتژی
4. ProbabilityCalibrator.calibrate() → احتمال برد کالیبره
5. ConfidenceScorer.compute_confidence() → اطمینان + عوامل
6. SignalDecisionEngine.evaluate() → ۱۰ گیت + گرید
7. CrossMarketCorrelator.analyze() → رژیم بازار
8. فیلتر نهایی confidence + کووتای بازار → EnrichedSignal[]
9. _persist_pending_signals() → ذخیره برای حلقه بازخورد
```

---

## 🐛 اشکالات رفعشده در فاز ۳

| # | فایل | اشکال | اصلاح |
|---|------|-------|-------|
| 1 | `multi_market_signal_engine.py` | **۷ نقطه حروف چینی در متن فارسی UI** (به فرانتاند کاراکتر خراب میفرستاد) | جایگزینی با فارسی صحیح |
| 2 | `multi_market_signal_engine.py` | **کد مرده:** `closes[-tf_days-1:]`, `(volume - volume*0.5)`, `put_oi/max(call_oi,1)`, `min(all_strikes,...)` — هیچ اثری نداشتند | حذف کامل |
| 3 | `multi_market_signal_engine.py` | **امتیاز خارج از بازه:** `score=50 + change_pct*5` در `_minimal_stock_signal` میتوانست منفی یا >100 شود | clamp به `[0,100]` |
| 4 | `multi_market_signal_engine.py` | **نشان دادن «محدوده: - - -»** در سیگنال ارز — `high_24h/low_24h` همیشه None بود ولی در متن reason چاپ میشد | حذف از متن ارز؛ طلا فقط وقتی داده واقعی هست |
| 5 | `quant_signal_orchestrator.py` | **نام ستون اشتباه طلا:** `_HISTORY_PRICE_COL["gold"]="price"` در حالی که اسکیمای `GoldCoinHistoryModel` ستون `price_close` دارد (کوئری حین اجرا خطا میداد) | اصلاح به `price_close` |
| 6 | `multi_timeframe_confirmer.py` | **پارامتر `required_agreement` نادیده گرفته میشد** — آستانهها hardcode بود | آستانهها از `required_agreement` مشتق میشوند (پیشفرض 0.5 دقیقاً رفتار قبلی را حفظ میکند) |
| 7 | `multi_timeframe_confirmer.py` | کد مرده `num_agreeing / total_votes` | حذف |
| 8 | `probability_calibrator.py` | کد مرده `min(...)` و شاخه `if row is None` غیرقابلدسترس | حذف |
| 9 | `unified_assistant_service.py` | حروف چینی `移动`/`主力` در الگوهای regex | حذف |
| 10 | `tsetmc_client.py`, `stock_assistant_service.py`, `stock_assistant.py` | حروف چینی در docstring/متن | اصلاح |

---

## 🧪 تستها

پوشه تست: `tests/unit/services/` (۳۳+ فایل)

```bash
# تستهای کلیدی فاز ۳ (۱۰۶۵ تست پاس)
python -m pytest tests/unit/services/test_signal_decision_engine.py \
  tests/unit/services/test_probability_calibrator.py \
  tests/unit/services/test_quant_signal_orchestrator.py \
  tests/unit/services/test_orchestrator_signal_integration.py \
  tests/unit/services/test_signal_generation_service.py \
  tests/unit/services/test_signal_service.py \
  tests/unit/services/test_alert_service.py \
  tests/unit/services/test_fund_service.py \
  tests/unit/services/test_fund_service_update_brsapi.py \
  tests/unit/services/test_screener_nlu.py \
  tests/unit/services/test_screener_filters.py -q

# همه تستها
python -m pytest tests/unit/services -q

# Lint
python -m ruff check services/ --output-format=concise
```

---

## 🛠 راهنمای توسعه

### ساخت سرویس جدید

1. کلاس خود را در `services/xxx_service.py` بنویسید
2. خروجیها را `Result[T]` برگردانید (نه raise عمومی)
3. اگر به DB نیاز دارید: `session: AsyncSession` را از سازنده بگیرید
4. در `apps/api/dependencies.py` یک `get_xxx_service()` اضافه کنید
5. در `apps/api/router.py` به endpoint وصل شوید

### نکات مهم

- **هرگز** به فرانتاند متن با حروف غیرفارسی/Unicode نشتشده بفرستید (بزرگترین باگ فاز ۳)
- اعداد فارسی/انگلیسی را نرمالسازی کنید (در orchestrator: `_normalize_digits`)
- برای کوئریهای سنگین از `asyncio.gather` + `Semaphore` استفاده کنید (مثل `_fetch_smart_money_analyses`)
- فاکتورهای اعتمادسنج (`ConfidenceScorer.WEIGHTS`) جمعشان باید 1.0 باشد
- جدولهای `signal_accuracy` و `calibration_models` باید قبل از استفاده وجود داشته باشند (`_ensure_db_tables`)
