# 🇮🇷 سکوی داده و تحلیل بازار سرمایه ایران

**Iran Market Data & Analytics Platform**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

یک پلتفرم جامع، ماژولار و مقیاس‌پذیر برای **جمع‌آوری، پردازش، ذخیره‌سازی، تحلیل و بک‌تست** داده‌های بازار سرمایه ایران (بورس تهران، فرابورس، کالا، انرژی، طلا، ارز، رمزارز، اوراق و مشتقه). این سیستم شامل موتور بک‌تست چندبازاری با مدل هزینه واقعی ایران، زنجیره کامل تولید سیگنال با بازخورد خودکار (دقت‌سنجی + بازآموزی)، غربالگری ۱۱۰ ستونه، تحلیل پول هوشمند (Smart Money)، و زیرساخت اجرایی Queue-محور با قفل توزیع‌شده است.

---

## 📊 آمار کلی پروژه (بررسی مستقیم کد)

| بخش | تعداد |
|------|------|
| فایل‌های endpoint API | ۶۰ |
| route تعریف‌شده (`@router.*`) | ~۴۳۸ |
| صفحه فرانت‌اند (Next.js `page.tsx`) | ۸۸ |
| فایل سرویس تجاری (`services/`) | ۱۰۳ |
| ماژول موتور بک‌تست (`backtesting/`) | ۲۷۵ |
| ماژول ML (`ml/`) | ۱۱۸ |
| تعریف job زمان‌بندی‌شده | ۱۹ |
| مهاجرت Alembic (head: `0039`) | ۳۹ |
| جدول دیتابیس | ~۱۲۲ |
| فایل تست | ۲۵۰ |

---

## 📚 مستندات کامل

> 📖 **راهنمای جامع پروژه:** [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) — معماری، استک، ساختار، ماژول‌های API، jobها، ML، بک‌تست و فرانت‌اند.

| مستند | موضوع |
|-------|-------|
| [مستندات BrsApi.ir](docs/brsapi-data-sources.md) | کاتالوگ endpoint ها، نرخ مجاز، بودجه‌بان و راهنمای دریافت داده |
| [گزارش وضعیت Sync](docs/brsapi-sync-status-report.md) | تازگی جداول و وضعیت هماهنگ‌سازی داده‌ها |
| [ارزیابی موتور سیگنال کوانت](docs/quant-signal-goal-assessment.md) | فاصله پروژه تا هدف «بهترین سیگنال» با اعداد واقعی |
| [معماری Job Queue](docs/job-queue.md) | قفل توزیع‌شده Redis، Publisher/Consumer و dead-letter |
| [Model Loader](docs/ml-model-loader.md) | بارگذاری Lazy + LRU کش مدل‌های ML |
| [API موتور تصمیم‌گیری](docs/decision-engine-api.md) | مستندات API موتور تصمیم |
| [متغیرهای محیطی (.env)](docs/env-vars.md) | مرجع کامل همه متغیرها، پیش‌فرض‌ها و نکات امنیتی |
| [ممیزی معماری](docs/ARCHITECTURE_AUDIT.md) | یافته‌های ممیزی عمیق و وضعیت رفع هرکدام |
| [گزارش ممیزی مجدد](docs/re-audit-status.md) | وضعیت تأییدشده همه یافته‌های بحرانی/بالا با سوت‌های تست |

---

## 📑 فهرست مطالب

- [ویژگی‌ها](#ویژگی‌ها)
- [معماری](#معماری)
- [بازارهای پشتیبانی‌شده](#بازارهای-پشتیبانی‌شده)
- [تکنولوژی‌ها](#تکنولوژی‌ها)
- [ساختار پروژه](#ساختار-پروژه)
- [راه‌اندازی سریع](#راه-اندازی-سریع)
- [استفاده با Docker](#استفاده-با-docker)
- [API Reference](#api-reference)
- [موتور بک‌تست](#موتور-بک-تست)
- [سیستم سیگنال کوانت](#سیستم-سیگنال-کوانت)
- [Smart Money](#smart-money)
- [غربالگری](#غربالگری)
- [موتور تصمیم‌گیری](#موتور-تصمیم-گیری)
- [Machine Learning Pipeline](#machine-learning-pipeline)
- [یکپارچه‌سازی BrsApi](#یکپارچه-سازی-brsapi)
- [زیرساخت Job Queue](#زیرساخت-job-queue)
- [صندوق‌های سرمایه‌گذاری](#صندوق-های-سرمایه-گذاری)
- [اخبار و کدال](#اخبار-و-کدال)
- [فرانت‌اند Next.js](#فرانت-اند-nextjs)
- [مانیتورینگ و متریک‌ها](#مانیتورینگ-و-متریک-ها)
- [تست‌ها](#تست-ها)
- [CI/CD و استقرار](#cicd-و-استقرار)
- [عیب‌یابی](#عیب-یابی)
- [توسعه و مشارکت](#توسعه-و-مشارکت)

---

## ✨ ویژگی‌ها

### 🏛️ موتور بک‌تست چندبازاری
- **دیسپچر یکتای موتورها** (`backtesting/runner.py::BacktestRunner`): ۶ موتور (Simulator کانونیکال + Replay + Hybrid + Portfolio + دو legacy منسوخ) با نرمال‌سازی نتیجه یکسان — هر مسیر بک‌تست همان PnL را می‌دهد (گارد پاریتی در CI).
- **مدل هزینه واقعی ایران** (`backtesting/costs/iran_costs.py`): کارمزد ۰٫۴٪ + کارمزد تسویه + مالیات ۰٫۵٪ فقط در سمت فروش — تک‌منبع برای همه مسیرها.
- **لغزش مبتنی بر ADV واقعی هر نماد** (`backtesting/engine/adv.py::AdvResolver`): واکشی خودکار میانگین حجم روزانه از دیتابیس + کش؛ بدون پیش‌فرض صامت ۱ میلیونی.
- **FIFO cost-basis PnL**: کارمزد خرید در سود/زیان گردش معامله لحاظ می‌شود (AnalyticsEngine + TradeMetrics با `deque`).
- **Replay Engine**: بازپخش رویدادمحور با خط زمانی یکپارچه (۱۰۰+ میلیون رویداد).
- **Microstructure Engine**: صف، ایمپکت قیمت (قانون جذر)، حراج، نقدینگی پنهان، مدل تأخیر.
- **Agent-Based Modeling**: بازارگردان، Noise Trader، Trend Follower، Mean Reversion.
- **Portfolio Simulator**: چند نماد هم‌زمان با allocation و rebalancing.
- **Experiments**: Grid Search، Walk-Forward (با purged/embargo)، Monte Carlo، بهینه‌سازی ژنتیک.
- **قوانین بازار** (`backtesting/market/`): دامنه نوسان، اندازه تیک، سشن، حراج برای TSE/IFB/پایه/ETF/بدهی/مشتقه/IME/انرژی.

### 🤖 سیستم سیگنال کوانت (بازخورد خودکار)
- **Quant Signal Orchestrator**: تولید سیگنال دوره‌ای، پایش دقت، بازآموزی خودکار هنگام افت دقت زیر آستانه.
- **Signal Voting System**: رأی‌گیری چند مدل برای افزایش دقت.
- **Confidence Calibration / Probability Calibrator**: کالیبراسیون اطمینان سیگنال‌ها.
- **Outcome Tracking بدون شکست صامت** (`services/signal_accuracy_tracker.py` + `services/accuracy_outcome_queue.py`): outcomeها در صف داخلی بچ می‌شوند، هنگام شکست DB requeue می‌شوند و هر drop در Prometheus شمارش می‌شود (`accuracy_tracking_dropped_total`).
- **Multi-Market Signal Engine + Multi-Timeframe Confirmer + Ensemble Engine**.
- **Decision Engine (۱۰ دروازه)** با Rule-Based Override وابسته به رژیم بازار.

### 📊 Smart Money Analysis (۹ لایه)
1. Price-Volume Analysis — 2. Absorption Detection — 3. Ownership Analysis (حقیقی/حقوقی) — 4. Compression — 5. Relative Strength — 6. Breakout — 7. Buyer Power — 8. Microstructure — 9. Breakout Quality

### 🔬 غربالگری
- **Smart Screener**: ۴۰۰+ فیلتر با منطق OR/AND و ذخیره فیلترها.
- **Screener 110 (CANSLIM)**: غربالگری ۱۱۰ ستونه.
- **سرویس‌های غربالگری جداگانه** (screener، screener-v2، saved-filters).

### 🧠 موتور تصمیم‌گیری (Decision Engine)
- داده‌های معماری سازمانی + Auto-Seeding از JSON + API اختصاصی (`/decision-engine`).

### 🗄️ جمع‌آوری داده
- **TSETMC** (بورس/فرابورس)، **CODAL** (اطلاعیه + دانلود پیوست)، **BrsApi.ir** (کامودیتی، رمزارز، طلا، ارز، بدهی)، اخبار، ماکرو، WebSocket لحظه‌ای.

### 📈 ML Pipeline
- **ModelLoader** (`ml/model_loader.py`): lazy loading + LRU کش (حداکثر ۲۰ مدل در حافظه) + `invalidate()` برای بازآموزی.
- **Weight Validator** (`ml/weight_validator.py`): R² برش OOS با purged walk-forward (بدون R² درون‌نمونه).
- Feature Store، Model Registry، Drift Detection، Auto-Retrain.

---

## 🏗️ معماری

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 16)                        │
│              port 3000 — Rewrite Proxy → API                     │
│   ۸۸ صفحه │ RTL │ Dark Mode │ Responsive │ Recharts             │
└────────────────────────────┬────────────────────────────────────┘
                             │ /api/v1/*
┌────────────────────────────▼────────────────────────────────────┐
│                   API Gateway (FastAPI)                          │
│              port 8000 — ۶۰ ماژول / ~۴۳۸ route                   │
│  CORS │ CSRF │ Rate Limit │ Input Sanitization │ Timing │ Metrics│
└────┬──────────────┬───────────────┬────────────┬────────────────┘
     │              │               │            │
┌────▼────┐  ┌──────▼──────┐  ┌─────▼─────┐  ┌───▼────────────┐
│ Services │  │   Jobs       │  │ ML Worker  │  │ Job Queue      │
│ ۱۰۳+ svc │  │ APScheduler  │  │ Train/Inf  │  │ Redis Streams  │
│          │  │ + JobQueue   │  │            │  │ + Dead-Letter  │
└────┬─────┘  └──────┬──────┘  └─────┬─────┘  └───┬────────────┘
     │              │               │            │
┌────▼──────────────▼───────────────▼────────────▼───────────────┐
│                      Infrastructure                              │
│  PostgreSQL 16 + TimescaleDB │ Redis 7 │ MinIO │ Prometheus     │
│  OpenTelemetry │ Telegram Bot │ BrsApi.ir / TSETMC / CODAL      │
└────────────────────────────────────────────────────────────────┘
```

---

## 🌍 بازارهای پشتیبانی‌شده

| بازار | شناسه | دامنه نوسان | سشن | حراج | سفارش بازار |
|-------|-------|------------|------|------|------------|
| بورس تهران (TSE) | `tse` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| فرابورس (IFB) | `ifb` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| بازار پایه | `base_market` | ۳-۱٪ پلکانی | ۰۸:۴۵-۱۲:۳۰ | دوره‌ای | ❌ |
| ETF / صندوق | `etf` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| اوراق بدهی | `bonds` | ±۱٪ | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| مشتقه | `derivatives` | متغیر | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| بورس کالا (IME) | `ime` | ±۵٪ | ۱۱:۴۵-۱۸:۰۰ | ✅ | ✅ |
| بورس انرژی | `energy` | ±۵٪ | ۱۱:۴۵-۱۸:۰۰ | دوره‌ای | ❌ |
| رمزارز | `crypto` | بدون محدودیت | ۲۴/۷ | ❌ | ✅ |
| طلا و سکه | `gold` | متغیر | متغیر | ❌ | ✅ |
| ارز | `fx` | متغیر | متغیر | ❌ | ✅ |

---

## 🛠️ تکنولوژی‌ها

### Backend
| تکنولوژی | نسخه | کاربرد |
|-----------|-------|---------|
| Python | 3.11+ | زبان اصلی |
| FastAPI / Uvicorn | 0.109+ | REST API |
| SQLAlchemy 2.0 (async) | 2.0+ | ORM + AsyncPG |
| Alembic | 1.13+ | مهاجرت دیتابیس |
| Pydantic v2 | 2.5+ | اعتبارسنجی داده |
| APScheduler | 3.10+ | زمان‌بندی وظایف |
| Redis (redis.asyncio) | 5.0+ | کش، صف، قفل توزیع‌شده |
| Pandas / NumPy | — | پردازش داده |
| OpenTelemetry | 1.22+ | ردیابی توزیع‌شده |
| Prometheus | — | متریک‌ها (`/metrics`) |
| httpx / aiohttp | — | HTTP client ناهمزمان |

### ML (اختیاری)
| تکنولوژی | کاربرد |
|-----------|---------|
| scikit-learn | مدل‌های پایه (Ridge، RandomForest، ...) |
| XGBoost / LightGBM / CatBoost | Gradient Boosting |
| PyTorch | یادگیری عمیق (LSTM, GRU, Transformer) |
| pandas_ta | محاسبه اندیکاتورها |

### Frontend
| تکنولوژی | نسخه | کاربرد |
|-----------|-------|---------|
| Next.js | 16.x | فریمورک React (App Router) |
| React | 19.x | UI Library |
| TypeScript | 5.x | Type Safety |
| Tailwind CSS | 4.x | استایل‌دهی |
| Recharts | 3.8+ | نمودارها |
| TanStack Query | 5.x | مدیریت state سرور |
| Lightweight Charts | 5.2+ | نمودار کندلاستیک |
| Vitest | 4.x | تست واحد |

### Database / Infra
| سرویس | نسخه | کاربرد |
|-------|-------|---------|
| PostgreSQL | 16 | دیتابیس اصلی |
| TimescaleDB | latest | هایپرتیبل داده زمانی |
| Redis | 7 | کش + صف + قفل |
| MinIO | — | ذخیره‌سازی آبجکت (S3) |
| Prometheus / Grafana | — | مانیتورینگ |

---

## 📁 ساختار پروژه

```
iran-market-platform/
├── apps/                          # لایه اپلیکیشن
│   ├── api/                       # FastAPI اصلی
│   │   ├── app.py                 # ساخت اپ + lifespan + /metrics
│   │   ├── router.py              # مسیریابی ~۴۳۸ route
│   │   ├── metrics.py             # PrometheusExporter + MetricsMiddleware
│   │   ├── middleware.py          # CSRF، Input Sanitization، Rate Limit، Timing
│   │   └── endpoints/             # ۶۰ ماژول endpoint
│   ├── admin/                     # پنل مدیریت (port 8001)
│   ├── scheduler/                 # زمان‌بندی وظایف
│   ├── worker/                    # worker پس‌زمینه
│   ├── decision_engine/           # موتور تصمیم‌گیری
│   └── cli/                       # رابط خط فرمان
│
├── backtesting/                   # 🎯 موتور بک‌تست (۲۷۵ ماژول)
│   ├── runner.py                  # BacktestRunner — دیسپچر یکتای موتورها
│   ├── costs/iran_costs.py        # مدل هزینه واقعی ایران (تک‌منبع)
│   ├── engine/                    # Simulator، Broker، Replay، adv.py (ADV)
│   ├── analytics/engine.py        # AnalyticsEngine (cost-basis PnL)
│   ├── metrics/                   # TradeMetrics، RiskMetrics، ...
│   ├── abm/  alpha/  calibration/  execution/  experiment/
│   ├── market/  microstructure/  multi_market/  optimization/
│   ├── portfolio/  regime/  reporting/  risk/  scenarios/  signals/
│   ├── strategies/                # rule_based / factor_based / ml_based / options / portfolios
│   └── visualization/
│
├── brsapi/                        # یکپارچه‌سازی BrsApi.ir
│   ├── budget.py                  # BrsApiBudgetGovernor — بودجه‌بان روزانه/۵دقیقه/۳۰۲
│   ├── usage_recorder.py          # ثبت مصرف روزانه در brsapi_daily_usage
│   ├── readiness.py               # بررسی آمادگی کلید
│   ├── rate_limiter.py            # محدودیت نرخ درون‌فرایندی
│   ├── client.py                  # HTTP client با retry/circuit-breaker
│   ├── parsers/  repositories/  services/  models/  migrations/
│   └── jobs/registry.py           # رجیستری jobهای برس‌آپی
│
├── core/                          # هسته سیستم
│   ├── config/                    # settings + validate_production
│   ├── database.py                # async_session_factory
│   ├── cache.py                   # کش مشترک Redis
│   ├── cache_manager.py           # CacheManager سه‌لایه (L1/L2/L3)
│   ├── security/                  # JWT + blacklist + MFA/TOTP + secrets
│   ├── resilience/  retry/  rate_limit/  concurrency/
│   ├── json/  constants/  exceptions/  health/  time/  ids/
│   └── typing/result.py           # Result/PaginatedResult
│
├── services/                      # ۱۰۳+ سرویس تجاری
│   ├── accuracy_outcome_queue.py  # صف outcomeها (بدون شکست صامت)
│   ├── signal_accuracy_tracker.py # دقت‌سنجی سیگنال‌ها
│   ├── quant_signal_orchestrator.py # هماهنگ‌کننده سیگنال کوانت
│   ├── multi_market_signal_engine.py  signal_voting_system.py
│   ├── confidence_scorer.py  probability_calibrator.py
│   ├── decision_gate.py  dynamic_weighting.py  ml_signal_connector.py
│   ├── smart_money/               # تحلیل ۹ لایه‌ای
│   ├── screener_service.py  smart_screener_v2.py  screener110_service.py
│   ├── backtest_service.py  backtest_framework.py  strategy_generator.py
│   ├── fund_service.py  fund_sync_service.py
│   ├── news_service.py  codal_service.py  codal_attachment_service.py
│   ├── market_service.py  market_watch_helper.py  monitoring_service.py
│   ├── chat/  stock_assistant_service.py  unified_assistant_service.py
│   └── ... (بقیه)
│
├── models/  schemas/              # مدل‌های دیتابیس + Pydantic schemaها
├── ingestion/  pipelines/  providers/  repositories/
├── jobs/                          # سیستم job
│   ├── locking.py                 # RedisJobLock (قفل توزیع‌شده)
│   ├── queue_publisher.py         # ارسال job به Redis Stream
│   ├── queue_consumer.py          # اجرای job در Worker + dead-letter
│   └── definitions/               # ۱۹ تعریف job
├── ml/                            # ML Pipeline (۱۱۸ ماژول)
│   ├── model_loader.py            # lazy + LRU کش
│   ├── weight_validator.py        # R² برش OOS (purged WF)
│   ├── train_weight_optimizer.py  # بهینه‌ساز وزن رژیم‌ها
│   ├── artifacts.py  models/  feature_store.py  types.py
│   └── ml_artifacts/              # مدل‌های ذخیره‌شده
├── migrations/versions/           # ۳۹ مهاجرت Alembic
├── scripts/                       # اسکریپت‌های عملیاتی
│   ├── run_backlog_sync.py        # sync بودجه‌آگاه برس‌آپی
│   ├── replay_dead_letter.py      # بازگرداندن پیام‌های dead-letter
│   ├── dead_letter_report.py      # گزارش توزیع خطاها
│   ├── build_feature_store.py  clean_historical_data.py
│   └── ...
├── monitoring/  integrations/     # OpenTelemetry، Prometheus، RedisLogHandler
├── tests/                         # ۲۵۰ فایل تست
├── frontend/                      # 🟢 فرانت‌اند Next.js (۸۸ صفحه)
│   └── src/{app,components,hooks,lib,__tests__}
├── docker-compose.yml             # timescaledb + redis + backend + worker + frontend
├── .env.example                   # نمونه متغیرهای محیطی
├── Makefile                       # دستورات کاربردی
├── pyproject.toml                 # پیکربندی پروژه (ruff, pytest, deps)
└── README.md                      # این فایل
```

---

## 🚀 راه‌اندازی سریع

### پیش‌نیازها
- **Python 3.11+**، **Node.js 18+**، **PostgreSQL 16**، **Redis 7** (یا Docker)

### ۱. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
pip install -e ".[dev]"      # اختیاری: ابزارهای توسعه
pip install -e ".[ml]"       # اختیاری: وابستگی‌های ML
```

### ۲. پیکربندی محیط

```bash
cp .env.example .env
# مقادیر را مطابق محیط خود ویرایش کنید
```

متغیرهای اصلی (مرجع کامل: [docs/env-vars.md](docs/env-vars.md)):

```env
# دیتابیس
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/market

# Redis (کش، صف، قفل)
REDIS_URL=redis://localhost:6379/0

# امنیت
SECRET_KEY=your-secret-key-here
CORS_ORIGINS=["http://localhost:3000"]

# داده برس‌آپی (برای دریافت داده واقعی)
BRSAPI_API_KEY=your-brsapi-key
BRSAPI_ENABLED=true
BRSAPI_GLOBAL_DAILY_LIMIT=4000   # بودجه روزانه — مهم برای جلوگیری از مسدود شدن کلید

# Telegram (اختیاری)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### ۳. مهاجرت دیتابیس

```bash
alembic upgrade head
# یا
make migrate
```

### ۴. اجرای سرور

```bash
# بک‌اند (Python 3.11+)
python main.py
# یا
uvicorn apps.api.app:app --reload --host 0.0.0.0 --port 8000

# فرانت‌اند (ترمینال جداگانه)
cd frontend
npm install --no-audit --no-fund
npm run dev
```

### ۵. دسترسی

| سرویس | آدرس | توضیح |
|-------|------|-------|
| API | http://localhost:8000 | FastAPI اصلی |
| Swagger | http://localhost:8000/docs | مستندات تعاملی API |
| ReDoc | http://localhost:8000/redoc | مستندات زیبا |
| Prometheus | http://localhost:8000/metrics | متریک‌های Prometheus |
| Frontend | http://localhost:3000 | فرانت‌اند Next.js |
| Admin | http://localhost:8001 | پنل مدیریت |

---

## 🐳 استفاده با Docker

```bash
# ساخت و اجرای همه سرویس‌ها
docker compose up --build -d

# مشاهده لاگ‌ها
docker compose logs -f

# توقف و حذف
docker compose down -v
```

### سرویس‌های docker-compose

| سرویس | پورت | توضیح |
|-------|------|-------|
| `backend` (FastAPI) | 8000 | سرویس اصلی REST API |
| `worker` | — | اجرای jobها از صف |
| `frontend` (Next.js) | 3000 | واسط کاربری |
| `timescaledb` | 5432 | دیتابیس اصلی |
| `redis` | 6379 | کش + صف + قفل |

### دستورات Makefile

```bash
make install        # نصب وابستگی‌ها
make dev            # اجرای توسعه‌ای backend
make dev-all        # backend + admin + worker
make migrate        # alembic upgrade head
make lint           # ruff
make typecheck      # mypy
make test           # تست‌ها
make docker-up      # ساخت و اجرای Docker
make backup         # پشتیبان‌گیری دیتابیس
make prod-check     # بررسی تنظیمات production
```

---

## 📡 API Reference

همه مسیرها زیر پیشوند `/api/v1` هستند. ساختار کلی:

```
GET  /api/v1/{resource}
POST /api/v1/{resource}
GET  /api/v1/{resource}/{id}
```

### گروه‌های اصلی (۶۰ ماژول / ~۴۳۸ route)

| گروه | مسیر | توضیح |
|------|------|-------|
| Health | `/api/v1/health` | سلامت سیستم (live/ready/full) |
| Auth + MFA | `/api/v1/auth` | ورود، توکن، MFA/TOTP، باطل‌سازی توکن |
| Market | `/api/v1/market` | نمای کلی، رشدها، هیت‌مپ |
| Instruments | `/api/v1/instruments` | نمادها و جستجو |
| Quotes / Trades | `/api/v1/quotes`, `/api/v1/trades` | قیمت‌ها و معاملات |
| Signals | `/api/v1/signals` | سیگنال‌های معاملاتی |
| Signal Insights | `/api/v1/signal-insights` | دقت، walk-forward، بازآموزی |
| Screener | `/api/v1/screener`, `/screener-v2`, `/screener110` | غربالگری (۴۰۰+ فیلتر، ۱۱۰ ستونه) |
| Saved Filters | `/api/v1/saved-filters` | فیلترهای ذخیره‌شده |
| Smart Money | `/api/v1/smart-money` | تحلیل پول هوشمند ۹ لایه |
| Backtests | `/api/v1/backtests` | اجرا و مدیریت بک‌تست |
| Compose | `/api/v1/compose` | ترکیب استراتژی |
| ML | `/api/v1/ml` | آموزش، مدل‌ها، ModelLoader cache-info |
| News | `/api/v1/news` | اخبار (با dedup) |
| Codal | `/api/v1/codal` | اطلاعیه‌ها + دانلود پیوست |
| Funds | `/api/v1/funds` | صندوق‌های سرمایه‌گذاری (+ `POST /funds/{symbol}/update`) |
| Macro | `/api/v1/macro` | اقتصاد کلان |
| Economic Calendar | `/api/v1/economic-calendar` | تقویم اقتصادی |
| Chat | `/api/v1/chat` | مکالمه هوشمند |
| Stock Assistant | `/api/v1/stock-assistant` | دستیار سهام |
| Assistant | `/api/v1/assistant` | دستیار یکپارچه |
| BrsApi | `/api/v1/brsapi` | کامودیتی، رمزارز، طلا، ارز + مدیریت مصرف |
| Market Dashboard | `/api/v1/market-dashboard` | داشبورد بازار |
| Market Watch | `/api/v1/market-watch` | دیده‌بان بازار |
| Decision Engine | `/api/v1/decision-engine` | موتور تصمیم‌گیری |
| Queue Analysis | `/api/v1/queue-analysis` | تحلیل صف سفارشات |
| Jobs | `/api/v1/jobs` | مدیریت jobها + `POST /jobs/queue/replay` + گزارش dead-letter |
| Anomalies | `/api/v1/anomalies` | ناهنجاری‌ها |
| WebSocket | `/api/v1/ws` | داده لحظه‌ای |

### نمونه درخواست

```bash
# نمای کلی بازار
curl http://localhost:8000/api/v1/market/overview

# سیگنال‌ها
curl http://localhost:8000/api/v1/signals

# غربالگری
curl -X POST http://localhost:8000/api/v1/screener/scan \
  -H "Content-Type: application/json" \
  -d '{"filters": [{"field": "volume", "op": ">", "value": 1000000}]}'

# اجرای بک‌تست
curl -X POST http://localhost:8000/api/v1/backtests/run \
  -H "Content-Type: application/json" \
  -d '{"strategy": "momentum", "symbol": "فولاد", "start_date": "2024-01-01"}'

# به‌روزرسانی داده روزانه یک صندوق
curl -X POST http://localhost:8000/api/v1/funds/صندوق-آفتاب/update

# گزارش مصرف روزانه BrsApi
curl http://localhost:8000/api/v1/brsapi/manage/usage?days=30

# وضعیت صف job و گزارش dead-letter
curl http://localhost:8000/api/v1/jobs/queue/summary
```

---

## 🎯 موتور بک‌تست

### دیسپچر یکتا — `BacktestRunner`

```python
from backtesting.runner import BacktestRunner

runner = BacktestRunner()
result = runner.run("simulator", strategy, initial_capital=1_000_000_000, data=data)
```

| موتور | شناسه | وضعیت |
|-------|-------|--------|
| `BacktestSimulator` | `simulator` | ✅ کانونیکال (همه سرویس‌ها) |
| `ReplayEngine` | `replay` | پشتیبانی (ingestion/research) |
| `HybridMarketSimulator` | `hybrid` | پشتیبانی (ABM/microstructure) |
| `PortfolioBacktestSimulator` | `portfolio` | پشتیبانی (چند-نماده) |
| `SimulationEngine` | `simulation` | 🔶 legacy منسوخ |
| `BacktestEngine` | `backtest_engine` | 🔶 legacy منسوخ |

همه موتورها به یک **کانترکت نتیجه یکسان** نرمالیزه می‌شوند و پاریتی در تست CI (`test_cost_parity.py`) fail-fast قفل شده است.

### مدل هزینه واقعی ایران (F1/F2/F3)

| جزء | نرخ | اعمال‌شده در |
|-----|-----|------------|
| کارمزد کارگزار | ۰٫۴٪ هر سمت | خرید + فروش |
| کارمزد تسویه (CSD) | ۰٫۰۸۵٪ | هر سمت |
| مالیات | ۰٫۵٪ | **فقط فروش** |

### استراتژی‌های پیش‌فرض

| گروه | استراتژی‌ها |
|------|------------|
| Rule-Based | `MovingAverageCross`, `MomentumStrategy`, `MeanReversionStrategy`, `RSIReversion`, `BreakoutStrategy`, `SupportResistanceStrategy`, `HalfTrendStrategy`, `SqueezeMomentumStrategy`, `VolatilityBreakout`, `PhaseStrategy` |
| Factor-Based | `MomentumFactorStrategy`, `ValueFactorStrategy`, `QualityFactorStrategy`, `LowVolatilityStrategy`, `MultiFactorStrategy` |
| ML-Based | `ClassificationSignalStrategy`, `ForecastSignalStrategy`, ... |

### اجرای مستقیم

```bash
python scripts/run_backtest.py --symbol فولاد --strategy ma_cross
python scripts/ultimate_walk_forward.py
```

---

## 🤖 سیستم سیگنال کوانت

مسیر تولید سیگنال تا بازخورد:

```
MultiMarketSignalEngine → Ensemble Engine → Confidence Scoring
        ↓                                        ↓
  Decision Engine (۱۰ دروازه)          Probability Calibration
        ↓                                        ↓
   انتشار سیگنال ───────────────────────► SignalAccuracyTracker
        ↓                                        ↓
   Auto-Retrain (افت دقت) ◄────────── AccuracyOutcomeQueue (صف + متریک)
```

- **Outcome Tracking بدون شکست صامت**: outcomeها در `AccuracyOutcomeQueue` بچ می‌شوند و به `signal_accuracy` فلاش می‌شوند؛ شکست DB → requeue؛ سرریز → متریک `accuracy_tracking_dropped_total`. خارج از production نبود DB = خطای صریح.
- **بازآموزی خودکار**: وقتی دقت بازار زیر ۵۵٪ افت کند، `AutoRetrainPipeline` مدل‌های آن بازار را بازآموزی می‌کند و `ModelLoader.invalidate()` کش را تازه می‌کند.
- **Decision Gates**: ۱۰ دروازه پیکربندی‌پذیر + Rule-Based Override بر اساس رژیم بازار (رکود/حجم بالا) — `services/decision_gate.py`.

---

## 💰 Smart Money

سرویس `services/smart_money/` تحلیل ۹ لایه‌ای پول هوشمند را ارائه می‌دهد و از طریق `/api/v1/smart-money` در دسترس است. فیلترهای مبتنی بر آن در Smart Screener نیز قابل استفاده هستند.

---

## 🔬 غربالگری

| سرویس | مسیر | توضیح |
|-------|------|-------|
| `screener_service` | `/api/v1/screener` | غربالگری پایه با فیلترهای ترکیبی |
| `smart_screener_v2` | `/api/v1/screener-v2` | ۴۰۰+ فیلتر، منطق OR/AND خودکار |
| `screener110_service` | `/api/v1/screener110` | غربالگری ۱۱۰ ستونه CANSLIM |

```bash
curl http://localhost:8000/api/v1/screener110?market=stock
```

---

## 🧠 موتور تصمیم‌گیری

- ذخیره‌سازی داده‌های معماری سازمانی + **Auto-Seeding** خودکار از فایل‌های JSON هنگام startup.
- API اختصاصی در `/api/v1/decision-engine` — مستندات: [docs/decision-engine-api.md](docs/decision-engine-api.md).

---

## 📈 Machine Learning Pipeline

### ModelLoader — lazy + LRU

`ml/model_loader.py` فقط مدل‌های موردنیاز را بارگذاری می‌کند (حداکثر ۲۰ مدل در کش) — حل مشکل ۳۵۹ مدل و حافظه.

```python
from ml.model_loader import get_model_loader

loader = get_model_loader()
model = await loader.get_model(symbol="فولاد", algorithm="xgboost")  # lazy load
loader.invalidate("فولاد", "xgboost")  # بعد از بازآموزی
await loader.preload(symbols=["فولاد", "شپنا"])  # پیش‌بارگذاری در startup
```

- `GET /api/v1/ml/model-loader/cache-info` — وضعیت کش برای مانیتورینگ runtime.
- مدل‌های جدید بدون ری‌استارت: بازآموزی → `invalidate(symbol, algorithm)` → دفعه بعد lazy-load با نسخه جدید.

### ارزیابی صادقانه (F6)

`ml/weight_validator.py::PurgedWeightValidator` — R² برش **OOS** با purged walk-forward (پنجره train/test بدون نشت + embargo). مدل‌های آموزشی که اسنپ‌شات‌شان آلوده است با پرچم `provisional` مشخص می‌شوند.

### قرارداد برچسب (F8)

`SignalFeaturePipeline.prepare_training_data(feature_sequence, closes=..., targets=..., ...)` — برچسب `y_{t+1}` از `closes` در داخل محاسبه می‌شود و هم‌ترازی assert می‌شود؛ هیچ آرایه برچسب جابه‌جایی بی‌صدا نمی‌پذیرد.

```bash
# آموزش مدل‌ها برای همه نمادها
python scripts/run_train_all_symbols.py

# آموزش رژیم‌یاب
python ml/train_regime_classifier.py

# بهینه‌ساز وزن رژیم‌ها با اعتبارسنجی OOS
python -m ml.train_weight_optimizer --market stock --no-walk-forward
```

---

## 🌐 یکپارچه‌سازی BrsApi

### بودجه‌بان — `BrsApiBudgetGovernor`

برای جلوگیری از مسدود شدن کلید (خطای ۳۰۲ → فایل حجیم) یک **بودجه‌بان مرکزی** پیاده‌سازی شده است:

- **شمارنده روزانه پایدار**: Redis `INCRBY` (کلید بر اساس تاریخ شمسی + TTL) با fallback فایل/حافظه — ری‌استارت/چند-worker بودجه تازه نمی‌گیرند.
- **پنجره ۵دقیقه‌ای مشترک**: Redis sorted set با پیش‌پردازش کشویی؛ fail-fast یا صبر تا انقضای قدیمی‌ترین.
- **حالت مسدودی ۳۰۲**: `report_302()` → cooldown (پیش‌فرض ۹۰۰ ثانیه)؛ `report_ok()` بعد از انقضا پاک می‌کند.
- **ثبت مصرف روزانه**: `brsapi_daily_usage` + `POST /brsapi/manage/usage/flush` + گزارش از پنل ادمین.
- محدودیت‌ها: `BRSAPI_GLOBAL_DAILY_LIMIT` (پیش‌فرض ۴۰۰۰)، `BRSAPI_GLOBAL_5MIN_LIMIT`، `BRSAPI_ENABLED`.

### دریافت داده

```bash
# دریافت کامل اطلاعات همه نمادها
python scripts/sync_live_data.py

# sync بودجه‌آگاه (پس از مسدود شدن/بازگشت بودجه)
python scripts/run_backlog_sync.py

# آمادگی کلید (۱ درخواست ارزان)
python scripts/brsapi_ready_check.py
```

- `BRSAPI_ENABLED=false` در `.env` تمام تماس‌های زنده را متوقف می‌کند (حالت امن هنگام مسدودی).

---

## 🔧 زیرساخت Job Queue

### معماری Queue-محور (Redis Streams)

```
APScheduler ──► JobQueuePublisher (job:queue) ──► Worker (Consumer)
                                                    │
                                                    ├─ موفق → اجرا
                                                    └─ خطا (۳ بار) → job:dead (dead-letter)
```

| فایل | مسئولیت |
|------|---------|
| `jobs/locking.py` | `RedisJobLock` — قفل توزیع‌شده (SET NX PX + Lua برای release/extend اتمیک، فقط owner) |
| `jobs/queue_publisher.py` | ارسال job به Redis Stream + احراز هویت توکن |
| `jobs/queue_consumer.py` | مصرف از صف، قفل، اجرا، retry و dead-letter + `stats()` |
| `scripts/replay_dead_letter.py` | بازگرداندن پیام‌های dead-letter به صف اصلی (با `--list`/`--dry-run`/`--summary`) |
| `scripts/dead_letter_report.py` | گزارش توزیع خطاها و job_nameها |

### مدیریت از پنل/API

```bash
# وضعیت صف + گزارش dead-letter
curl http://localhost:8000/api/v1/jobs/queue/summary

# بازپخش پیام‌های dead-letter
curl -X POST http://localhost:8000/api/v1/jobs/queue/replay
```

> در محیط تک-worker (توسعه)، `JOB_QUEUE_ENABLED=false` جاب‌ها را همان‌جا اجرا می‌کند (fallback درون‌فرایندی).

---

## 💼 صندوق‌های سرمایه‌گذاری

- **FundService + FundRepository** با PostgreSQL (جدول `funds`).
- **به‌روزرسانی روزانه**: `POST /api/v1/funds/{symbol}/update` + auto-refresh job از BrsApi.
- **seed اولیه**: `scripts/seed_funds.py`.
- صفحه فرانت‌اند `/funds` با دکمه به‌روزرسانی هر صندوق.

---

## 📰 اخبار و کدال

- **اخبار**: سرویس خبر با dedup و تنوع منبع (`news_dedup.py`, `news_filter.py`) + جمع‌آوری خودکار.
- **کدال**: `codal_service`, `codal_attachment_service` (دانلود پیوست از S3/MinIO با fallback محلی), `codal_download_service`, `codal_financial_service`.

---

## 🖥️ فرانت‌اند Next.js

۸۸ صفحه، RTL کامل، Dark Mode، واکنش‌گرا. همه درخواست‌ها از Rewrite Proxy عبور می‌کنند (`API_URL` فقط سمت سرور).

### صفحات اصلی

| مسیر | صفحه |
|------|------|
| `/` | داشبورد (شاخص، حجم، ترکیب صنایع) |
| `/markets` | وضعیت لحظه‌ای بازار |
| `/analysis` | تحلیل تکنیکال و بنیادی |
| `/smart-screener`, `/screener`, `/screener110` | غربالگری |
| `/signals`, `/signals/all` | سیگنال‌ها |
| `/smart-money` | پول هوشمند |
| `/backtest` | بک‌تست |
| `/portfolio` | پرتفوی |
| `/funds` | صندوق‌ها |
| `/news`, `/codal` | اخبار و اطلاعیه‌ها |
| `/brsapi`, `/brsapi/history/[symbol]` | داده‌های برس‌آپی |
| `/commodities`, `/crypto`, `/macro`, `/economic-calendar` | بازارهای جهانی و کلان |
| `/decision-engine` | موتور تصمیم |
| `/watchlist`, `/alerts`, `/recommendations` | دیده‌بان و هشدار |
| `/chat` | مکالمه هوشمند |
| `/admin`, `/jobs`, `/ml`, `/tables`, `/health` | مدیریت و مانیتورینگ |

### کامپوننت‌های نمودار

`AreaChartCard`, `BarChartCard`, `PieChartCard`, `CandleChartCard`, `TradingViewChart`, `SentimentChart`, `EquityCurveChart`

---

## 📊 مانیتورینگ و متریک‌ها

| سطح | ابزار | جزئیات |
|-----|-------|--------|
| متریک | Prometheus `/metrics` | `http_requests_total`, `http_request_errors_total`, `http_request_duration_seconds`, `accuracy_tracking_dropped_total`, `accuracy_tracking_flush_failed_total`, `accuracy_tracking_read_unavailable_total` |
| تریس | OpenTelemetry (`integrations/observability/otel_exporter.py`) | ردیابی توزیع‌شده |
| لاگ | `RedisLogHandler` → Redis Stream (`log-aggregator:stream`) | تجمیع لاگ برای Loki/ELK |
| سلامت | `/api/v1/health`, `/health/ready`, `/health/live`, `/health/full` | لایو/آمادگی/کامل |

---

## 🧪 تست‌ها

```bash
# تست‌های واحد
pytest tests/unit -v

# تست‌های integration
pytest tests/integration -v

# تست‌های e2e
pytest tests/e2e -v

# با coverage
pytest --cov=. --cov-report=html

# فرانت‌اند
cd frontend
npm test
npx tsc --noEmit
npm run lint
```

> گاردهای CI کلیدی: **Backtest integrity guard** (پاریتی هزینه + دیسپچر موتورها — `test_cost_parity.py` + `test_engine_runner.py`) و **چک سینتکس Mermaid مستندات** (`scripts/check_mermaid_blocks.py`).

---

## 🚀 CI/CD و استقرار

### GitHub Actions (`.github/workflows/ci.yml`)

- Lint & Typecheck (ruff, mypy)
- Backend Tests (pytest)
- Docker Build & Push
- Frontend Build & Test
- گاردهای یکپارچگی (پاریتی بک‌تست، مستندات Mermaid)

### Docker Swarm (تولید)

```bash
docker swarm init
docker stack deploy -c docker-compose.yml -c docker-compose.production.yml market
```

- Reverse proxy nginx با TLS-ready: `deploy/nginx/nginx.conf`.
- بررسی تنظیمات production پیش از استقرار: `make prod-check` (رد `SECRET_KEY` پیش‌فرض، `CORS=*` و...).

---

## 🔧 عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| خطای اتصال دیتابیس | `pg_isready` را چک کنید؛ `DATABASE_URL` را در `.env` اصلاح کنید |
| Redis در دسترس نیست | `redis-cli ping`؛ `REDIS_URL` را اصلاح کنید |
| کلید BrsApi مسدود شد (۳۰۲) | `BRSAPI_ENABLED=false` بگذارید، صبر کنید تا شمارنده ریست شود، سپس `python scripts/run_backlog_sync.py` با بودجه‌آگاه اجرا کنید |
| خطای Rate Limit | صبر کنید یا `BRSAPI_GLOBAL_*_LIMIT` را در `.env` تنظیم کنید |
| CERTIFICATE_VERIFY_FAILED در BrsApi | `BRSAPI_VERIFY_SSL=false` |
| پیام‌های `job:dead` زیاد | `python scripts/dead_letter_report.py` (گزارش توزیع) سپس `python scripts/replay_dead_letter.py` بعد از رفع مشکل |
| دقت ML پایین | `POST /api/v1/signal-insights/retrain?market=stock&force=true` یا صبر تا بازآموزی خودکار |
| مهاجرت اجرا نمی‌شود | `alembic upgrade head` و بررسی زنجیره `0039` |
| فرانت‌اند build نمی‌شود | `cd frontend && rm -rf node_modules .next && npm install && npm run build` |
| `value too long for type character varying(30)` در `news_articles` | ✅ رفع‌شده — `published_at` به `VARCHAR(40)` ارتقا یافت (migration `0021`) و ریپازیتوری میکروثانیه‌ها را نرمال می‌کند؛ ستون‌های title/summary/content/url از قبل TEXT بودند |
| `PendingRollbackError` بعد از خطای ذخیره خبر | ✅ رفع‌شده — `NewsIngestionService.ingest()` بعد از هر خطای ذخیره، سشن را rollback می‌کند تا مقاله‌های بعدی ادامه یابند (بجای مسموم شدن سشن) |
| `DataError: expected a datetime.date ... got 'str'` در جاب‌ها | ✅ رفع‌شده — `SyncSnapshotsToQuotesJob`، `EvaluateAlertsJob` و `IranFearGreedIndex` حالا برای `fetched_at >= :today` آبجکت `datetime` (نیمه‌شب UTC) می‌فرستند نه رشته |
| `InvalidRequestError: provisioning a new connection` در سینک صندوق‌ها | ✅ رفع‌شده — `FundSyncService.sync_all_funds()` حالا نمادها را ترتیبی سینک می‌کند (بدون `asyncio.gather` روی سشن مشترک) |

---

## 🛣️ وضعیت ممیزی معماری

گزارش کامل: [docs/ARCHITECTURE_AUDIT.md](docs/ARCHITECTURE_AUDIT.md)

**همه یافته‌های بحرانی/بالا (ردیف P0/P1) رفع شده‌اند:**

| شناسه | موضوع | وضعیت |
|-------|-------|--------|
| F1/F2/F3 | مدل هزینه یکپارچه ایران + پاریتی + مالیات فقط-فروش | ✅ |
| S1 | بودجه‌بان مرکزی BrsApi (جلوگیری از مسدودی) | ✅ |
| F6 | R² برش OOS + purged walk-forward | ✅ |
| F8 | قرارداد صریح برچسب در `prepare_training_data` | ✅ |
| D1 | تجمیع موتورهای بک‌تست روی `BacktestRunner` | ✅ |
| F4 | cost-basis PnL + deque | ✅ |
| F5 | ADV واقعی هر نماد (اجباری/خودکار) | ✅ |
| S2 | شکست‌های صامت → متریک + صف | ✅ |

باقی‌مانده‌ها (غیربحرانی — ردیف P2): سیاست چرخه حیات `ml_artifacts` (M2)، متادیتا+هش مدل‌ها (M1)، تک‌منبع‌سازی منطق صندوق (D6)، پکیج screener یکپارچه (D7)، EvaluationSuite مشترک (M3)، حذف `.bak` (D3)، قطع وابستگی چرخه‌ای (D4).

---

## 🤝 توسعه و مشارکت

1. **fork** و **branch** بسازید
2. تغییرات را اعمال و **تست** کنید
3. **PR** بفرستید

### استانداردها

- Linting: `ruff`
- Type Checking: `mypy`
- Testing: `pytest` (+ Vitest برای فرانت‌اند)
- Formatting: `ruff format`

### ساختار commits

```
feat: افزودن ویژگی جدید
fix: رفع باگ
docs: به‌روزرسانی مستندات
test: افزودن تست
refactor: بازآرایی کد
chore: وظایف نگهداری
```

---## 🗄️ ساختار دیتابیس

سکوی داده روی **PostgreSQL 16 + TimescaleDB** اجرا می‌شود و در حال حاضر **128 جدول** دارد
(تخمین کل ردیف‌ها: **~42,474,311**). جدول‌های بزرگ سری‌زمانی با TimescaleDB به هایپرتیبل تبدیل شده‌اند.

### نمودار ارتباط جدول‌ها

نمودار زیر روابط **Foreign Key** و اتصال معنایی `symbol`/`ins_id` به جدول مرجع `symbols` را برای
جدول‌های اصلی نشان می‌دهد (فقط جدول‌هایی که رابطه دارند در نمودار می‌آیند؛ لیست کامل در جدول زیر است):

```mermaid
erDiagram
    %% --- نمودار ارتباط جدول‌های اصلی (خوشه‌بندی‌شده بر اساس دامنه) ---
    brsapi_candlesticks {}
    brsapi_commodity_prices {}
    brsapi_crypto_daily_history {}
    brsapi_crypto_prices {}
    brsapi_currency_24h {}
    brsapi_currency_prices {}
    brsapi_gold_24h {}
    brsapi_gold_coin_history {}
    brsapi_gold_coin_prices {}
    brsapi_gold_currency_pro_daily_history {}
    brsapi_gold_currency_pro_history_24h {}
    brsapi_gold_currency_pro_prices {}
    brsapi_historical_daily {}
    brsapi_historical_real_legal {}
    brsapi_ime_certificates {}
    brsapi_ime_funds {}
    brsapi_ime_futures {}
    brsapi_ime_options {}
    brsapi_ime_physical_trades {}
    brsapi_index_values {}
    brsapi_intraday_trades {}
    brsapi_option_snapshots {}
    brsapi_shareholder_records {}
    brsapi_symbol_details {}
    brsapi_symbol_snapshots {}
    ml_engineered_features {}
    ml_models {}
    ml_predictions {}
    ml_symbol_results {}
    tabdeal_markets {}
    tabdeal_orders {}
    tabdeal_quotes {}
    tabdeal_trades {}
    open_interest_history {}
    option_contracts {}
    option_snapshots {}
    option_trades {}
    options {}
    brsapi_nav_records {}
    daily_history {}
    daily_real_legal {}
    etf_nav {}
    funds {}
    indicators {}
    intraday_trades {}
    orderbook_snapshots {}
    orderbooks {}
    quotes {}
    shareholders {}
    trades {}
    backtest_runs {}
    backtest_trades {}
    compare_results {}
    generated_strategies {}
    queue_analysis_results {}
    screener_daily_scores {}
    screener_profiles {}
    screener_signals {}
    screener_snapshots {}
    signal_accuracy {}
    signals {}
    decision_results {}
    job_runs {}
    alerts {}
    candlesticks_deprecated {}
    commodity_certificates {}
    commodity_funds {}
    commodity_futures {}
    commodity_options {}
    commodity_prices {}
    commodity_trades {}
    daily_history_deprecated {}
    gold_currency_prices {}
    instruments {}
    intraday_trades_deprecated {}
    paper_signal_snapshots {}
    paper_trades {}
    symbol_snapshots_deprecated {}
    portfolio_positions {}
    recommendations {}
    saved_filters {}
    symbols {}
    users {}
    account_mappings {}
    analysis_reports {}
    brsapi_codal_announcements {}
    brsapi_codal_attachments {}
    codal_announcements_deprecated {}
    codal_audit_summary {}
    codal_financial_statements {}
    codal_reports {}
    corporate_actions {}
    data_lineage {}
    dim_account {}
    dim_company {}
    dim_date {}
    dim_document {}
    dim_report_type {}
    fact_financials {}
    fact_growth {}
    fact_quality_signals {}
    fact_ratios {}
    fact_text_analytics {}
    import_audit_log {}
    import_document_files {}
    import_document_tables {}
    macro_indicators {}
    news_articles {}
    account_mappings ||--o{ dim_account : "دارای رابطه"
    alerts ||--o{ symbols : "دارای رابطه"
    analysis_reports ||--o{ dim_company : "دارای رابطه"
    analysis_reports ||--o{ symbols : "دارای رابطه"
    backtest_trades ||--o{ symbols : "دارای رابطه"
    brsapi_candlesticks ||--o{ symbols : "دارای رابطه"
    brsapi_codal_announcements ||--o{ symbols : "دارای رابطه"
    brsapi_codal_attachments ||--o{ symbols : "دارای رابطه"
    brsapi_commodity_prices ||--o{ symbols : "دارای رابطه"
    brsapi_crypto_daily_history ||--o{ symbols : "دارای رابطه"
    brsapi_crypto_prices ||--o{ symbols : "دارای رابطه"
    brsapi_currency_24h ||--o{ symbols : "دارای رابطه"
    brsapi_currency_prices ||--o{ symbols : "دارای رابطه"
    brsapi_gold_24h ||--o{ symbols : "دارای رابطه"
    brsapi_gold_coin_history ||--o{ symbols : "دارای رابطه"
    brsapi_gold_coin_prices ||--o{ symbols : "دارای رابطه"
    brsapi_gold_currency_pro_daily_history ||--o{ symbols : "دارای رابطه"
    brsapi_gold_currency_pro_history_24h ||--o{ symbols : "دارای رابطه"
    brsapi_gold_currency_pro_prices ||--o{ symbols : "دارای رابطه"
    brsapi_historical_daily ||--o{ symbols : "دارای رابطه"
    brsapi_historical_real_legal ||--o{ symbols : "دارای رابطه"
    brsapi_ime_certificates ||--o{ symbols : "دارای رابطه"
    brsapi_ime_funds ||--o{ symbols : "دارای رابطه"
    brsapi_ime_futures ||--o{ symbols : "دارای رابطه"
    brsapi_ime_options ||--o{ symbols : "دارای رابطه"
    brsapi_ime_physical_trades ||--o{ symbols : "دارای رابطه"
    brsapi_index_values ||--o{ symbols : "دارای رابطه"
    brsapi_intraday_trades ||--o{ symbols : "دارای رابطه"
    brsapi_nav_records ||--o{ symbols : "دارای رابطه"
    brsapi_option_snapshots ||--o{ symbols : "دارای رابطه"
    brsapi_shareholder_records ||--o{ symbols : "دارای رابطه"
    brsapi_symbol_details ||--o{ symbols : "دارای رابطه"
    brsapi_symbol_snapshots ||--o{ symbols : "دارای رابطه"
    candlesticks_deprecated ||--o{ symbols : "دارای رابطه"
    codal_announcements_deprecated ||--o{ symbols : "دارای رابطه"
    codal_audit_summary ||--o{ symbols : "دارای رابطه"
    codal_financial_statements ||--o{ symbols : "دارای رابطه"
    codal_reports ||--o{ symbols : "دارای رابطه"
    commodity_certificates ||--o{ symbols : "دارای رابطه"
    commodity_funds ||--o{ symbols : "دارای رابطه"
    commodity_futures ||--o{ symbols : "دارای رابطه"
    commodity_options ||--o{ symbols : "دارای رابطه"
    commodity_prices ||--o{ symbols : "دارای رابطه"
    commodity_trades ||--o{ symbols : "دارای رابطه"
    compare_results ||--o{ symbols : "دارای رابطه"
    corporate_actions ||--o{ symbols : "دارای رابطه"
    daily_history_deprecated ||--o{ symbols : "دارای رابطه"
    daily_real_legal ||--o{ symbols : "دارای رابطه"
    data_lineage ||--o{ dim_document : "دارای رابطه"
    data_lineage ||--o{ fact_financials : "دارای رابطه"
    decision_results ||--o{ symbols : "دارای رابطه"
    dim_account ||--o{ dim_account : "دارای رابطه"
    dim_company ||--o{ symbols : "دارای رابطه"
    dim_document ||--o{ dim_company : "دارای رابطه"
    dim_document ||--o{ dim_report_type : "دارای رابطه"
    etf_nav ||--o{ symbols : "دارای رابطه"
    fact_financials ||--o{ dim_account : "دارای رابطه"
    fact_financials ||--o{ dim_company : "دارای رابطه"
    fact_financials ||--o{ dim_date : "دارای رابطه"
    fact_financials ||--o{ dim_document : "دارای رابطه"
    fact_financials ||--o{ dim_report_type : "دارای رابطه"
    fact_growth ||--o{ dim_company : "دارای رابطه"
    fact_growth ||--o{ dim_date : "دارای رابطه"
    fact_quality_signals ||--o{ dim_company : "دارای رابطه"
    fact_quality_signals ||--o{ dim_date : "دارای رابطه"
    fact_ratios ||--o{ dim_company : "دارای رابطه"
    fact_ratios ||--o{ dim_date : "دارای رابطه"
    fact_text_analytics ||--o{ dim_company : "دارای رابطه"
    fact_text_analytics ||--o{ dim_document : "دارای رابطه"
    funds ||--o{ symbols : "دارای رابطه"
    generated_strategies ||--o{ symbols : "دارای رابطه"
    gold_currency_prices ||--o{ symbols : "دارای رابطه"
    import_audit_log ||--o{ import_document_files : "دارای رابطه"
    import_document_tables ||--o{ import_document_files : "دارای رابطه"
    indicators ||--o{ symbols : "دارای رابطه"
    instruments ||--o{ symbols : "دارای رابطه"
    intraday_trades_deprecated ||--o{ symbols : "دارای رابطه"
    ml_engineered_features ||--o{ symbols : "دارای رابطه"
    ml_predictions ||--o{ symbols : "دارای رابطه"
    ml_symbol_results ||--o{ symbols : "دارای رابطه"
    open_interest_history ||--o{ option_contracts : "دارای رابطه"
    option_contracts ||--o{ symbols : "دارای رابطه"
    option_snapshots ||--o{ option_contracts : "دارای رابطه"
    option_trades ||--o{ option_contracts : "دارای رابطه"
    options ||--o{ symbols : "دارای رابطه"
    orderbook_snapshots ||--o{ symbols : "دارای رابطه"
    orderbooks ||--o{ symbols : "دارای رابطه"
    paper_signal_snapshots ||--o{ symbols : "دارای رابطه"
    paper_trades ||--o{ symbols : "دارای رابطه"
    portfolio_positions ||--o{ symbols : "دارای رابطه"
    queue_analysis_results ||--o{ symbols : "دارای رابطه"
    quotes ||--o{ symbols : "دارای رابطه"
    recommendations ||--o{ symbols : "دارای رابطه"
    saved_filters ||--o{ users : "دارای رابطه"
    screener_daily_scores ||--o{ symbols : "دارای رابطه"
    screener_profiles ||--o{ symbols : "دارای رابطه"
    screener_signals ||--o{ symbols : "دارای رابطه"
    screener_snapshots ||--o{ symbols : "دارای رابطه"
    shareholders ||--o{ symbols : "دارای رابطه"
    signal_accuracy ||--o{ symbols : "دارای رابطه"
    signals ||--o{ symbols : "دارای رابطه"
    symbol_snapshots_deprecated ||--o{ symbols : "دارای رابطه"
    tabdeal_markets ||--o{ symbols : "دارای رابطه"
    tabdeal_orders ||--o{ symbols : "دارای رابطه"
    tabdeal_trades ||--o{ symbols : "دارای رابطه"
    trades ||--o{ symbols : "دارای رابطه"
```

### آمار کامل جدول‌ها

ستون‌ها: تعداد ستون هر جدول. ردیف: تخمین PostgreSQL (دقیق نیست؛ `>0` یعنی داده دارد ولی آمار جمع نشده).
رابطه: Foreign Keyهای واقعی و اتصال معنایی به `symbols`.

| جدول | ستون‌ها | ردیف (~) | منبع تاریخ دوتایی | رابطه با جدول‌های دیگر |
|------|--------:|---------:|-------------------|------------------------|
| `brsapi_candlesticks` | 17 | ~2,166,522 | date | symbol→symbols |
| `brsapi_commodity_prices` | 19 | ~13,440 | fetched_at | symbol→symbols |
| `brsapi_crypto_daily_history` | 12 | ~18,609 | created_at | symbol→symbols |
| `brsapi_crypto_prices` | 22 | ~567 | fetched_at | symbol→symbols |
| `brsapi_currency_24h` | 18 | ~0 | fetched_at | symbol→symbols |
| `brsapi_currency_prices` | 18 | ~28 | fetched_at | symbol→symbols |
| `brsapi_daily_usage` | 8 | ~0 | — | — |
| `brsapi_gold_24h` | 18 | ~0 | fetched_at | symbol→symbols |
| `brsapi_gold_coin_history` | 14 | ~44,207 | created_at | symbol→symbols |
| `brsapi_gold_coin_prices` | 18 | ~9 | fetched_at | symbol→symbols |
| `brsapi_gold_currency_pro_daily_history` | 20 | ~160,567 | created_at | symbol→symbols |
| `brsapi_gold_currency_pro_history_24h` | 14 | ~0 | fetched_at | symbol→symbols |
| `brsapi_gold_currency_pro_prices` | 23 | ~19 | fetched_at | symbol→symbols |
| `brsapi_historical_daily` | 23 | ~5,652,876 | created_at | symbol→symbols |
| `brsapi_historical_real_legal` | 21 | ~909,896 | created_at | symbol→symbols |
| `brsapi_ime_certificates` | 48 | ~4,259 | fetched_at | symbol→symbols |
| `brsapi_ime_funds` | 67 | ~24,441 | fetched_at | symbol→symbols |
| `brsapi_ime_futures` | 59 | ~8,379 | date_end | symbol→symbols |
| `brsapi_ime_options` | 101 | ~58,294 | fetched_at | symbol→symbols |
| `brsapi_ime_physical_trades` | 37 | ~935 | date_trade | symbol→symbols |
| `brsapi_index_values` | 26 | ~3,437 | fetched_at | symbol→symbols |
| `brsapi_intraday_trades` | 14 | ~1,637,033 | trade_date | symbol→symbols |
| `brsapi_option_snapshots` | 81 | ~499,922 | date_end | symbol→symbols |
| `brsapi_raw_payloads` | 11 | ~0 | fetched_at | — |
| `brsapi_shareholder_records` | 14 | ~768,334 | created_at | symbol→symbols |
| `brsapi_symbol_details` | 65 | ~3,923 | fetched_at | symbol→symbols |
| `brsapi_symbol_snapshots` | 71 | ~1,194,116 | fetched_at | symbol→symbols |
| `brsapi_sync_log` | 13 | ~50 | created_at | — |
| `ml_engineered_features` | 50 | ~3 | — | symbol→symbols |
| `ml_model_versions` | 13 | ~638 | created_at | — |
| `ml_models` | 11 | ~359 | created_at | — |
| `ml_predictions` | 22 | ~20,674 | created_at | symbol→symbols |
| `ml_symbol_results` | 22 | ~5,506 | start_date | symbol→symbols |
| `ml_training_runs` | 17 | ~6,078 | created_at | — |
| `tabdeal_accounts` | 15 | ~0 | created_at | — |
| `tabdeal_balances` | 10 | ~0 | created_at | — |
| `tabdeal_listen_keys` | 9 | ~0 | created_at | — |
| `tabdeal_markets` | 21 | ~0 | created_at | symbol→symbols |
| `tabdeal_orders` | 25 | ~0 | created_at | symbol→symbols |
| `tabdeal_trades` | 19 | ~0 | created_at | symbol→symbols |
| `open_interest_history` | 8 | ~0 | date | FK→option_contracts |
| `option_contracts` | 18 | ~0 | created_at | symbol→symbols |
| `option_snapshots` | 27 | ~0 | created_at | FK→option_contracts |
| `option_trades` | 13 | ~0 | created_at | FK→option_contracts |
| `options` | 13 | ~3,225 | expiry_date | symbol→symbols |
| `volatility_surface` | 11 | ~0 | date | — |
| `brsapi_nav_records` | 14 | ~245 | fetched_at | symbol→symbols |
| `daily_real_legal` | 16 | ~387,701 | trade_date | FK→symbols |
| `etf_nav` | 7 | ~12 | time | FK→symbols |
| `funds` | 31 | ~27 | snapshot_date | symbol→symbols |
| `indicators` | 13 | ~0 | created_at | symbol→symbols |
| `orderbook_snapshots` | 34 | ~0 | time | FK→symbols |
| `orderbooks` | 12 | ~0 | created_at | symbol→symbols |
| `quotes` | 29 | ~3,366,996 | created_at | symbol→symbols |
| `shareholders` | 8 | ~2,390 | record_date | FK→symbols |
| `trades` | 14 | ~14,884,365 | created_at | symbol→symbols |
| `backtest_runs` | 22 | ~1,579 | start_date | — |
| `backtest_trades` | 18 | ~0 | created_at | symbol→symbols |
| `calibration_models` | 15 | ~0 | last_trained_at | — |
| `compare_results` | 20 | ~0 | start_date | symbol→symbols |
| `generated_strategies` | 38 | ~0 | created_at | symbol→symbols |
| `generation_batches` | 14 | ~0 | created_at | — |
| `queue_analysis_results` | 30 | ~500 | created_at | symbol→symbols |
| `screener_daily_scores` | 14 | ~1,515 | — | symbol→symbols |
| `screener_profiles` | 62 | ~1,562 | created_at | symbol→symbols |
| `screener_signals` | 37 | ~511 | created_at | symbol→symbols |
| `screener_snapshots` | 20 | ~511 | created_at | symbol→symbols |
| `signal_accuracy` | 28 | ~3,693 | created_at | symbol→symbols |
| `signals` | 17 | ~4 | created_at | symbol→symbols |
| `audit_logs` | 12 | ~0 | timestamp | — |
| `audit_trail` | 10 | ~0 | timestamp | — |
| `decision_architectures` | 9 | ~1 | created_at | — |
| `decision_results` | 25 | ~0 | created_at | symbol→symbols |
| `job_runs` | 15 | ~0 | created_at | — |
| `provider_health` | 14 | ~0 | created_at | — |
| `provider_health_history` | 8 | ~0 | checked_at | — |
| `alert_history` | 8 | ~1,536 | triggered_at | — |
| `alerts` | 14 | ~2 | created_at | symbol→symbols |
| `candlesticks_deprecated` | 10 | ~0 | — | FK→symbols |
| `commodity_certificates` | 8 | ~125,256 | time | symbol→symbols |
| `commodity_funds` | 8 | ~186 | time | symbol→symbols |
| `commodity_futures` | 11 | ~60 | expiry_date | symbol→symbols |
| `commodity_options` | 11 | ~476 | expiry_date | symbol→symbols |
| `commodity_prices` | 9 | ~42 | time | symbol→symbols |
| `commodity_trades` | 12 | ~320,005 | created_at | symbol→symbols |
| `daily_history_deprecated` | 17 | ~88,961 | — | FK→symbols |
| `dual_date_columns` | 4 | ~117 | — | — |
| `gold_currency_prices` | 12 | ~74,463 | time | symbol→symbols |
| `indices` | 8 | ~4 | time | — |
| `instruments` | 26 | ~499 | created_at | symbol→symbols |
| `intraday_trades_deprecated` | 9 | ~9,135,020 | — | FK→symbols |
| `paper_equity_history` | 9 | ~3 | — | — |
| `paper_signal_snapshots` | 25 | ~3,025 | — | symbol→symbols |
| `paper_trades` | 26 | ~3,025 | — | symbol→symbols |
| `symbol_relations` | 13 | ~0 | created_at | — |
| `symbol_snapshots_deprecated` | 28 | ~0 | — | FK→symbols |
| `markets` | 14 | ~0 | created_at | — |
| `portfolio_positions` | 14 | ~0 | created_at | symbol→symbols |
| `portfolios` | 11 | ~0 | created_at | — |
| `recommendations` | 18 | ~0 | created_at | symbol→symbols |
| `saved_filters` | 17 | ~0 | created_at | FK→users |
| `symbols` | 19 | ~511 | created_at | — |
| `users` | 21 | ~>0 | created_at | — |
| `account_mappings` | 14 | ~0 | — | FK→dim_account |
| `analysis_reports` | 22 | ~0 | report_date | FK→dim_company، symbol→symbols |
| `brsapi_codal_announcements` | 24 | ~5,053 | date_publish | symbol→symbols |
| `brsapi_codal_attachments` | 18 | ~10,336 | created_at | symbol→symbols |
| `codal_announcements_deprecated` | 17 | ~0 | — | symbol→symbols |
| `codal_audit_summary` | 33 | ~451 | analyzed_at | symbol→symbols |
| `codal_financial_statements` | 16 | ~451 | imported_at | symbol→symbols |
| `codal_reports` | 17 | ~226,818 | publish_date | symbol→symbols |
| `corporate_actions` | 11 | ~0 | ex_date | symbol→symbols |
| `data_lineage` | 13 | ~0 | created_at | FK→dim_document، FK→fact_financials |
| `dim_account` | 10 | ~0 | — | FK→dim_account |
| `dim_company` | 12 | ~0 | listing_date | symbol→symbols |
| `dim_date` | 10 | ~0 | jalali_date | — |
| `dim_document` | 15 | ~0 | publish_date | FK→dim_company، FK→dim_report_type |
| `dim_report_type` | 7 | ~0 | — | — |
| `fact_financials` | 16 | ~0 | — | FK→dim_account، FK→dim_company، FK→dim_date، FK→dim_document، FK→dim_report_type |
| `fact_growth` | 11 | ~0 | created_at | FK→dim_company، FK→dim_date |
| `fact_quality_signals` | 11 | ~0 | created_at | FK→dim_company، FK→dim_date |
| `fact_ratios` | 14 | ~0 | created_at | FK→dim_company، FK→dim_date |
| `fact_text_analytics` | 13 | ~0 | created_at | FK→dim_company، FK→dim_document |
| `import_audit_log` | 9 | ~0 | timestamp | FK→import_document_files |
| `import_document_files` | 18 | ~95,418 | created_at | — |
| `import_document_tables` | 13 | ~524,564 | created_at | FK→import_document_files |
| `macro_indicators` | 15 | ~0 | created_at | — |
| `news_articles` | 16 | ~71 | created_at | — |

### خلاصه مشکلات جدول‌ها

تعداد جدول‌هایی که هر نوع مشکل را دارند (هر جدول می‌تواند چند مشکل داشته باشد):

| مشکل | تعداد جدول |
|------|-----------:|
| جدول خالی است | 55 |
| مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست | 40 |
| بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود | 11 |
| لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود | 10 |
| ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟ | 6 |
| هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو | 6 |
| نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است | 3 |
| نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` است | 2 |
| ستون منبع تاریخ `expiry_date` در نمونه NULL دارد | 2 |
| ستون منبع تاریخ `start_date` در نمونه NULL دارد | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_option_snapshots` جایگزین آن است | 1 |
| ۱۲ ردیف یتیم بدون مصرف‌کننده — نسخه‌های زنده `brsapi_nav_records` و `funds` جایگزین‌اند | 1 |
| رکوردزنی جاب‌ها در `services/job_service.py` پیاده‌سازی نشده — جدول در عمل خالی می‌ماند | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_commodity_prices` جایگزین آن است | 1 |
| هیچ SQL فعالی ندارد — مراجع کد صرفاً از نام ماژول/پکیج هستند | 1 |
| آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید | 1 |

### تحلیل عمیق — مشکلات پیدا و ناپیدا

این گزارش با `python scripts/analyze_db_issues.py` تولید می‌شود — مجموع **218 یافته**: 🔴 0 بحرانی، 🟠 2 بالا، 🟡 116 متوسط، 🔵/⚪ 100 کم/اطلاعاتی.

<details>
<summary>نمایش همه 218 یافته (کلیک کنید)</summary>

| شدت | تعداد |
|------|------:|
| 🔴 بحرانی | 0 |
| 🟠 بالا | 2 |
| 🟡 متوسط | 116 |
| 🔵 کم / ⚪ اطلاعاتی | 100 |

**data:**

- 🔵 کم `symbols`: 12 نماد با isin خالی دارند
- ⚪ اطلاعاتی `symbols`: نماد تکراری ندارد — constraint یکتا سالم است

**dates:**

- 🟡 متوسط `analysis_reports`: ستون تاریخ `report_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `backtest_runs`: ستون تاریخ `end_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `backtest_runs`: ستون تاریخ `start_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `backtest_trades`: ستون تاریخ `entry_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `backtest_trades`: ستون تاریخ `exit_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_candlesticks`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_codal_announcements`: ستون تاریخ `date_publish` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_codal_announcements`: ستون تاریخ `date_send` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_codal_announcements`: ستون تاریخ `date_title` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_codal_announcements`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_codal_announcements`: ستون تاریخ `time_publish` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_codal_announcements`: ستون تاریخ `time_send` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_commodity_prices`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_commodity_prices`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_crypto_daily_history`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_crypto_daily_history`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_crypto_prices`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_crypto_prices`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_currency_24h`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_currency_24h`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_currency_prices`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_currency_prices`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_daily_usage`: ستون تاریخ `usage_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_24h`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_24h`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_coin_history`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_coin_history`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_coin_prices`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_coin_prices`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_currency_pro_daily_history`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_currency_pro_daily_history`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_currency_pro_history_24h`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_currency_pro_history_24h`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_currency_pro_prices`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_gold_currency_pro_prices`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_historical_daily`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_historical_real_legal`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_certificates`: ستون تاریخ `date_update` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_certificates`: ستون تاریخ `date_y` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_certificates`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_certificates`: ستون تاریخ `time_update` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_funds`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_futures`: ستون تاریخ `date_end` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_futures`: ستون تاریخ `date_end_text` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_futures`: ستون تاریخ `date_update` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_futures`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_futures`: ستون تاریخ `time_update` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_options`: ستون تاریخ `call_date_end` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_options`: ستون تاریخ `date_update` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_options`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_options`: ستون تاریخ `put_date_end` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_options`: ستون تاریخ `time_update` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_physical_trades`: ستون تاریخ `date_delivery` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_physical_trades`: ستون تاریخ `date_price_settlement` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_physical_trades`: ستون تاریخ `date_trade` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_physical_trades`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_ime_physical_trades`: ستون تاریخ `location_delivery` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_index_values`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_intraday_trades`: ستون تاریخ `trade_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_nav_records`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_nav_records`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_option_snapshots`: ستون تاریخ `date_begin` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_option_snapshots`: ستون تاریخ `date_end` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_option_snapshots`: ستون تاریخ `fetched_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_shareholder_records`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_symbol_details`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `brsapi_symbol_details`: ستون تاریخ `date_update` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `codal_announcements`: ستون تاریخ `date_publish` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `codal_announcements`: ستون تاریخ `date_send` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `codal_announcements`: ستون تاریخ `date_title` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `codal_audit_summary`: ستون تاریخ `report_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `codal_financial_statements`: ستون تاریخ `report_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `codal_reports`: ستون تاریخ `publish_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `compare_results`: ستون تاریخ `end_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `compare_results`: ستون تاریخ `start_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `data_lineage`: ستون تاریخ `created_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `dim_company`: ستون تاریخ `fiscal_year_end` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `dim_company`: ستون تاریخ `listing_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `dim_document`: ستون تاریخ `fiscal_period_end` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `dim_document`: ستون تاریخ `publish_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `funds`: ستون تاریخ `snapshot_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `indicators`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `intraday_trades`: ستون تاریخ `trade_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `macro_indicators`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `markets`: ستون تاریخ `close_time` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `markets`: ستون تاریخ `open_time` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `ml_symbol_results`: ستون تاریخ `end_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `ml_symbol_results`: ستون تاریخ `start_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `news_articles`: ستون تاریخ `published_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `orderbooks`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `paper_equity_history`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `quotes`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `trades`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*

**freshness:**

- 🟡 متوسط `codal_reports`: آخرین داده 40 روز پیش است (2026-07-12) → *اجرای جاب سینک مربوطه*
- 🟡 متوسط `daily_real_legal`: آخرین داده 38 روز پیش است (2026-07-14) → *اجرای جاب سینک مربوطه*
- 🟡 متوسط `shareholders`: آخرین داده 44 روز پیش است (2026-07-08) → *اجرای جاب سینک مربوطه*
- 🔵 کم `brsapi_historical_daily`: محاسبه max تاریخ به‌دلیل نبود ایندکس/وقفه انجام نشد
- 🔵 کم `trades`: محاسبه max تاریخ به‌دلیل نبود ایندکس/وقفه انجام نشد
- ⚪ اطلاعاتی `orderbooks`: جدول سری زمانی خالی است

**infra:**

- 🟡 متوسط `-`: 5 هایپرتیبل بدون فشرده‌سازی: candlesticks_deprecated، commodity_prices، daily_history_deprecated، intraday_trades_deprecated، symbol_snapshots_deprecated → *فعال‌سازی compression + retention policy*
- ⚪ اطلاعاتی `-`: 10 هایپرتیبل TimescaleDB: candlesticks_deprecated، commodity_prices، daily_history_deprecated، daily_real_legal، etf_nav، gold_currency_prices، intraday_trades_deprecated، orderbook_snapshots، shareholders، symbol_snapshots_deprecated

**legacy:**

- 🟠 بالا `commodity_prices`: نسخه قدیمی/تکراری است — `brsapi_commodity_prices` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*
- 🟠 بالا `option_snapshots`: نسخه قدیمی/تکراری است — `brsapi_option_snapshots` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*

**orphan:**

- 🟡 متوسط `alerts`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `candlesticks`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `codal_announcements`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `codal_audit_summary`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `codal_financial_statements`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `codal_reports`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `daily_history`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `intraday_trades`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `ml_symbol_results`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `options`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `paper_signal_snapshots`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `paper_trades`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `queue_analysis_results`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `screener_profiles`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `signal_accuracy`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `symbol_snapshots`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_codal_announcements`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_codal_attachments`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_commodity_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_crypto_daily_history`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_crypto_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_currency_prices`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_gold_24h`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_gold_coin_history`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_gold_coin_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_gold_currency_pro_daily_history`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_gold_currency_pro_prices`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_certificates`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_funds`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_ime_futures`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_options`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_physical_trades`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_index_values`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_nav_records`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_option_snapshots`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_symbol_details`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_certificates`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_funds`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_futures`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_options`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_trades`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `funds`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `gold_currency_prices`: بررسی یتیم‌های `symbol` به‌دلیل حجم/وقفه انجام نشد
- 🔵 کم `vw_clean_daily_history`: بررسی یتیم‌های `symbol` به‌دلیل حجم/وقفه انجام نشد

**schema:**

- 🟡 متوسط `brsapi_historical_daily`: constraint یکتا روی `symbol,date` ندارد (upsert با ON CONFLICT پرخطر است) → *ایندکس یکتا اضافه کنید*
- 🟡 متوسط `brsapi_intraday_trades`: constraint یکتا روی `symbol,date,time` ندارد (upsert با ON CONFLICT پرخطر است) → *ایندکس یکتا اضافه کنید*
- 🟡 متوسط `codal_reports`: constraint یکتا روی `ins_id,report_type` ندارد (upsert با ON CONFLICT پرخطر است) → *ایندکس یکتا اضافه کنید*
- 🔵 کم `account_mappings`: 2 ایندکس با ستون اول یکسان `source_label` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_candlesticks`: 4 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_codal_announcements`: 2 ایندکس با ستون اول یکسان `date_publish` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_codal_announcements`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_codal_attachments`: 2 ایندکس با ستون اول یکسان `announcement_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_codal_attachments`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_commodity_prices`: 2 ایندکس با ستون اول یکسان `category` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_commodity_prices`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_crypto_daily_history`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_crypto_prices`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_currency_24h`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_currency_prices`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_gold_24h`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_gold_coin_history`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_gold_coin_prices`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_gold_currency_pro_daily_history`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_gold_currency_pro_history_24h`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_gold_currency_pro_prices`: 2 ایندکس با ستون اول یکسان `section` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_daily`: 2 ایندکس با ستون اول یکسان `gregorian_date` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_daily`: 2 ایندکس با ستون اول یکسان `ins_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_daily`: 2 ایندکس با ستون اول یکسان `instrument_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_daily`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_real_legal`: 2 ایندکس با ستون اول یکسان `ins_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_real_legal`: 2 ایندکس با ستون اول یکسان `instrument_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_real_legal`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_funds`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_futures`: 2 ایندکس با ستون اول یکسان `contract_code` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_options`: 2 ایندکس با ستون اول یکسان `call_contract_code` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_options`: 2 ایندکس با ستون اول یکسان `put_contract_code` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_physical_trades`: 2 ایندکس با ستون اول یکسان `date_trade` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_intraday_trades`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_nav_records`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_option_snapshots`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_option_snapshots`: 2 ایندکس با ستون اول یکسان `underlying_symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_shareholder_records`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_symbol_snapshots`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `codal_audit_summary`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `codal_financial_statements`: 2 ایندکس با ستون اول یکسان `import_batch` → *ادغام ایندکس‌ها*
- 🔵 کم `codal_financial_statements`: 2 ایندکس با ستون اول یکسان `report_date` → *ادغام ایندکس‌ها*
- 🔵 کم `codal_financial_statements`: 2 ایندکس با ستون اول یکسان `report_type` → *ادغام ایندکس‌ها*
- 🔵 کم `codal_financial_statements`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `dim_account`: 2 ایندکس با ستون اول یکسان `canonical_code` → *ادغام ایندکس‌ها*
- 🔵 کم `dim_company`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `fact_financials`: 2 ایندکس با ستون اول یکسان `company_id` → *ادغام ایندکس‌ها*
- 🔵 کم `fact_growth`: 2 ایندکس با ستون اول یکسان `company_id` → *ادغام ایندکس‌ها*
- 🔵 کم `fact_ratios`: 2 ایندکس با ستون اول یکسان `company_id` → *ادغام ایندکس‌ها*
- 🔵 کم `import_document_files`: 2 ایندکس با ستون اول یکسان `file_status` → *ادغام ایندکس‌ها*
- 🔵 کم `import_document_tables`: 2 ایندکس با ستون اول یکسان `document_file_id` → *ادغام ایندکس‌ها*
- 🔵 کم `ml_engineered_features`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `ml_symbol_results`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `open_interest_history`: 2 ایندکس با ستون اول یکسان `contract_id` → *ادغام ایندکس‌ها*
- 🔵 کم `option_contracts`: 2 ایندکس با ستون اول یکسان `underlying_symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `option_snapshots`: 2 ایندکس با ستون اول یکسان `contract_id` → *ادغام ایندکس‌ها*
- 🔵 کم `option_snapshots`: 2 ایندکس با ستون اول یکسان `date` → *ادغام ایندکس‌ها*
- 🔵 کم `quotes`: 3 ایندکس با ستون اول یکسان `instrument_id` → *ادغام ایندکس‌ها*
- 🔵 کم `quotes`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `screener_profiles`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `screener_signals`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `screener_snapshots`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `signal_accuracy`: 2 ایندکس با ستون اول یکسان `market` → *ادغام ایندکس‌ها*
- 🔵 کم `signal_accuracy`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `tabdeal_orders`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `tabdeal_trades`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `trades`: 2 ایندکس با ستون اول یکسان `instrument_id` → *ادغام ایندکس‌ها*
- 🔵 کم `volatility_surface`: 2 ایندکس با ستون اول یکسان `underlying_symbol` → *ادغام ایندکس‌ها*

### جزئیات هر جدول (مشکلات + مراجع کد + نمونه داده)

برای هر جدول: مشکلات شناسایی‌شده، مدل ORM و فایل‌های کدی که از آن استفاده می‌کنند، و ۲ ردیف نمونه
(با `LIMIT 2` و بدون `ORDER BY`؛ برای جدول‌های پهن حداکثر ۱۲ ستون اول). مراجع کد بر اساس شمارش
نام جدول در فایل‌های پایتون (به‌جز migrations و همین اسکریپت) محاسبه شده است.

<details>
<summary><code>brsapi_candlesticks</code> — ~2,166,522 ردیف، 17 ستون (نمایش 12 ستون از 17) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `CandlestickModel`
- سرویس: `services/history_backfill_service.py` (2)، `services/market_service.py` (2)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/backfill_dates.py` (1)، `scripts/backfill_ins_id.py` (1)، `scripts/run_brsapi_sync.py` (1)
- تست: `tests/unit/test_brsapi_candlestick_daily_job.py` (3)، `tests/test_instrument_relations.py` (1)، `tests/unit/test_brsapi_candlesticks.py` (1)، `tests/unit/test_brsapi_candlestick_manual.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (5)، `brsapi/parsers/tsetmc.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | date | time | open | high | low | close | volume | count | candle_type | created_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 820 | پاسارگاد |  |  | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 367 | 3 | 2026-08-10 01:19:37.671675 | … |
| 821 | پاسارگاد |  |  | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 367 | 2 | 2026-08-10 01:19:45.800784 | … |

</details>

<details>
<summary><code>brsapi_commodity_prices</code> — ~13,440 ردیف، 19 ستون (نمایش 12 ستون از 19)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `CommodityPriceModel`
- سرویس: `services/gap_prediction.py` (2)، `services/quant_signal_orchestrator.py` (1)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | name | price | change_value | change_percent | unit | category | date | time | time_unix | fetched_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 7516 | XAUUSD | انس طلا | 4247.97 | 1.95 | 0.05 | دلار | precious_metal | 1405/05/15 | 21:57 | 1786040846 | 2026-08-06T18:30:57.494Z | … |
| 7519 | XAGUSD | انس نقره | 61.53 | -0.44 | -0.71 | دلار | precious_metal | 1405/05/15 | 21:57 | 1786040846 | 2026-08-06T18:30:57.494Z | … |

</details>

<details>
<summary><code>brsapi_crypto_daily_history</code> — ~18,609 ردیف، 12 ستون</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/crypto.py` → `CryptoDailyHistoryModel`
- API: `apps/api/endpoints/brsapi.py` (2)
- اسکریپت: `scripts/import_history_data.py` (3)
- سایر: `brsapi/services/history_fetch_service.py` (1)

**نمونه داده:**

| id | symbol | date | price_open | price_high | price_low | price_close | volume | fetched_at | created_at | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 55219 | ADA | 1405-05-14 | 0.1935 | 0.1946 | 0.1913 | 0.1924 | 7.5335952e+16 | NULL | 2026-08-05 06:14:01.344936 | 2026-08-05 | 1405-05-14 |
| 55220 | ADA | 1405-05-13 | 0.1944 | 0.1995 | 0.1909 | 0.1935 | 1.20626628e+18 | NULL | 2026-08-05 06:14:01.344936 | 2026-08-05 | 1405-05-14 |

</details>

<details>
<summary><code>brsapi_crypto_prices</code> — ~567 ردیف، 22 ستون (نمایش 12 ستون از 22)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/crypto.py` → `CryptoPriceModel`
- سرویس: `services/quant_signal_orchestrator.py` (3)، `services/confidence_scorer.py` (1)
- اسکریپت: `scripts/check_tables.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | name | symbol | price_usd | price_toman | price_irr | change_percent | market_cap | volume_24h | icon_url | rank | date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1147008 | بیت‌کوین | BTC | 65123.0 | 0.0 | 0.0 | 0.25 | 1304896276390.0 | 0.0 |  | 0 | 1405/05/19 | … |
| 1147009 | اتریوم | ETH | 1920.0 | 0.0 | 0.0 | 0.06 | 231343331366.0 | 0.0 |  | 0 | 1405/05/19 | … |

</details>

<details>
<summary><code>brsapi_currency_24h</code> — جدول خالی است (18 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `Currency24hModel`
- اسکریپت: `scripts/populate_24h_tables.py` (3)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)

</details>

<details>
<summary><code>brsapi_currency_prices</code> — ~28 ردیف، 18 ستون (نمایش 12 ستون از 18)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `CurrencyPriceModel`
- سرویس: `services/quant_signal_orchestrator.py` (3)، `services/auto_retrain_pipeline.py` (2)، `services/populate_profiles_service.py` (2)، `services/confidence_scorer.py` (1)
- اسکریپت: `scripts/full_populate_profiles.py` (6)، `scripts/populate_24h_tables.py` (2)، `scripts/check_tables.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | name | price | change_value | change_percent | unit | date | time | time_unix | fetched_at | raw_json | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 28257 | USDT_IRT | دلار تتر | 185701.0 | -428.0 | -0.23 | IRR | 1405/05/19 | 15:27:03 | 1786363023 | 2026-08-10T11:57:53.514Z | {"date": "1405/05/19", "time":… | … |
| 28258 | USD | دلار | 185800.0 | -100.0 | -0.05 | IRR | 1405/05/19 | 15:08 | 1786361917 | 2026-08-10T11:57:53.514Z | {"date": "1405/05/19", "time":… | … |

</details>

<details>
<summary><code>brsapi_daily_usage</code> — جدول خالی است (8 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `brsapi/models/base.py` → `BrsApiDailyUsageModel`
- API: `apps/api/endpoints/brsapi.py` (3)
- تست: `tests/unit/test_brsapi_usage_recorder.py` (1)
- سایر: `brsapi/usage_recorder.py` (3)، `brsapi/budget.py` (1)

</details>

<details>
<summary><code>brsapi_gold_24h</code> — جدول خالی است (18 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `Gold24hModel`
- اسکریپت: `scripts/populate_24h_tables.py` (3)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)

</details>

<details>
<summary><code>brsapi_gold_coin_history</code> — ~44,207 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `GoldCoinHistoryModel`
- سرویس: `services/auto_retrain_pipeline.py` (2)، `services/quant_signal_orchestrator.py` (2)، `services/multi_timeframe_confirmer.py` (1)، `services/risk_adjusted_filter.py` (1)
- API: `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/signal_insights.py` (1)
- اسکریپت: `scripts/import_gold_currency_history.py` (4)، `scripts/import_history_data.py` (2)، `scripts/add_constraints.py` (1)، `scripts/check_columns.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/services/history_fetch_service.py` (1)

**نمونه داده:**

| id | symbol | date | price_open | price_high | price_low | price_close | fetched_at | created_at | ins_id | instrument_id | updated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 41174 | IR_PCOIN_700MG | 1405-02-23 | 14250000.0 | 14250000.0 | 14250000.0 | 14250000.0 | NULL | 2026-07-23 20:15:33.396299 | NULL | NULL | NULL | … |
| 41175 | IR_PCOIN_700MG | 1405-02-22 | 14570000.0 | 14570000.0 | 14570000.0 | 14570000.0 | NULL | 2026-07-23 20:15:33.396299 | NULL | NULL | NULL | … |

</details>

<details>
<summary><code>brsapi_gold_coin_prices</code> — ~9 ردیف، 18 ستون (نمایش 12 ستون از 18)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `GoldCoinPriceModel`
- سرویس: `services/quant_signal_orchestrator.py` (3)، `services/confidence_scorer.py` (1)
- اسکریپت: `scripts/populate_24h_tables.py` (2)، `scripts/check_tables.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | name | price | change_value | change_percent | unit | date | time | time_unix | fetched_at | raw_json | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 9154 | IR_GOLD_18K | طلای 18 عیار | 18825400.0 | 10800.0 | 0.06 | IRR | 1405/05/19 | 15:26 | 1786363000 | 2026-08-10T11:57:53.431Z | {"date": "1405/05/19", "time":… | … |
| 9155 | IR_GOLD_24K | طلای 24 عیار | 25100300.0 | 14500.0 | 0.06 | IRR | 1405/05/19 | 15:26 | 1786363000 | 2026-08-10T11:57:53.431Z | {"date": "1405/05/19", "time":… | … |

</details>

<details>
<summary><code>brsapi_gold_currency_pro_daily_history</code> — ~160,567 ردیف، 20 ستون (نمایش 12 ستون از 20)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `GoldCurrencyProDailyHistoryModel`
- سرویس: `services/paper_trading_service.py` (4)، `services/quant_signal_orchestrator.py` (4)، `services/auto_retrain_pipeline.py` (3)، `services/multi_timeframe_confirmer.py` (1)
- API: `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/signal_insights.py` (1)
- اسکریپت: `scripts/import_history_data.py` (2)، `scripts/add_constraints.py` (1)، `scripts/check_columns.py` (1)، `scripts/check_tables.py` (1)
- تست: `tests/test_brsapi_job_registry.py` (5)
- سایر: `brsapi/jobs/registry.py` (2)، `brsapi/services/history_fetch_service.py` (1)

**نمونه داده:**

| id | symbol | name | sign | unit | url_base_icon | path_icon | date | price_open | price_high | price_low | price_close | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 396948 | NIMA_SEK | NULL | NULL | NULL | NULL | NULL | 1405-05-03 | 154723.0 | 154723.0 | 154723.0 | 154723.0 | … |
| 76190 | NIMA_SEK | NULL | NULL | NULL | NULL | NULL | 1405-05-01 | 154845.0 | 154845.0 | 154845.0 | 154845.0 | … |

</details>

<details>
<summary><code>brsapi_gold_currency_pro_history_24h</code> — جدول خالی است (14 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `GoldCurrencyProHistory24hModel`
- تست: `tests/test_brsapi_job_registry.py` (5)
- سایر: `brsapi/jobs/registry.py` (2)

</details>

<details>
<summary><code>brsapi_gold_currency_pro_prices</code> — ~19 ردیف، 23 ستون (نمایش 12 ستون از 23)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `GoldCurrencyProPriceModel`
- سرویس: `services/real_return_calculator.py` (4)، `services/gap_prediction.py` (3)، `services/quant_signal_orchestrator.py` (2)
- اسکریپت: `scripts/full_populate_profiles.py` (2)

**نمونه داده:**

| id | section | symbol | name_en | name | sign | price | change_value | change_percent | unit | url_base_icon | path_icon | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 65073 | cryptocurrency | BTC | Bitcoin | بیت‌کوین |  | 65050.0 | 0.0 | 0.13 | دلار | https://s1.BrsApi.ir/Api/Marke… | BTC.png | … |
| 65074 | cryptocurrency | ETH | Ethereum | اتریوم |  | 1919.0 | 0.0 | -0.08 | دلار | https://s1.BrsApi.ir/Api/Marke… | ETH.png | … |

</details>

<details>
<summary><code>brsapi_historical_daily</code> — ~5,652,876 ردیف، 23 ستون (نمایش 12 ستون از 23)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `HistoricalDailyModel`
- سرویس: `services/backtest_service.py` (7)، `services/auto_retrain_pipeline.py` (6)، `services/iran_fear_greed_index.py` (6)، `services/hidden_accumulation.py` (4)
- API: `apps/api/endpoints/backtests.py` (3)، `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/funds.py` (2)، `apps/api/endpoints/signal_insights.py` (2)
- اسکریپت: `scripts/clean_historical_data.py` (9)، `scripts/dedup_and_constrain.py` (9)، `scripts/dedup_batched.py` (9)، `scripts/check_partitions.py` (8)
- تست: `tests/test_instrument_relations.py` (4)، `tests/unit/test_brsapi_history_backfill_manual.py` (2)، `tests/unit/services/test_paper_trading_service.py` (1)
- سایر: `ml/train_weight_optimizer.py` (5)، `brsapi/migrations/001_create_brsapi_tables.py` (3)، `backtesting/engine/adv.py` (2)، `backtesting/types.py` (1)

**نمونه داده:**

| id | symbol | date | time | trade_count | trade_volume | trade_value | price_min | price_max | price_yesterday | price_first | price_last | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 3675676 | بالاس | 1400-06-29 | 12:29:08 | 398 | 695492 | 26266759988.0 | 36000.0 | 38152.0 | 36336.0 | 36000.0 | 38152.0 | … |
| 3675677 | بالاس | 1400-06-28 | 14:13:48 | 688 | 1121250 | 40742063095.0 | 35858.0 | 38990.0 | 37745.0 | 38001.0 | 36710.0 | … |

</details>

<details>
<summary><code>brsapi_historical_real_legal</code> — ~909,896 ردیف، 21 ستون (نمایش 12 ستون از 21)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `HistoricalRealLegalModel`
- سرویس: `services/screener_service.py` (3)، `services/hidden_accumulation.py` (1)، `services/smart_money_service.py` (1)
- API: `apps/api/endpoints/funds.py` (2)، `apps/admin/dashboard.py` (1)
- اسکریپت: `scripts/import_real_legal.py` (4)، `scripts/check_partitions.py` (3)، `scripts/analyze_patterns.py` (1)، `scripts/backfill_ins_id.py` (1)
- تست: `tests/unit/test_brsapi_history_backfill_manual.py` (2)، `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/services/query_service.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | date | buy_real_count | buy_legal_count | sell_real_count | sell_legal_count | buy_real_volume | buy_legal_volume | sell_real_volume | sell_legal_volume | buy_real_value | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | آ س پ | 1405-04-24 | 80 | 1 | 155 | 0 | 6551386 | 574916 | 7126302 | 0 | 95535407920.0 | … |
| 2 | آ س پ | 1405-04-23 | 178 | 1 | 226 | 0 | 16176269 | 2390509 | 18566778 | 0 | 229129476110.0 | … |

</details>

<details>
<summary><code>brsapi_ime_certificates</code> — ~4,259 ردیف، 48 ستون (نمایش 12 ستون از 48)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeCertificateModel`
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/simulate_brsapi_usage.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (2)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | commodity | contract_code | contract_description | contract_size | contract_size_unit | contract_currency | price_yesterday | price_first | price_first_change | price_first_change_pct | price_max | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 3847 | شمش نقره | SilverBar | گواهی سپرده پیوسته شمش نقره 99… | 1 | ضریب تبدیل نماد به گروه انبار | ریال | 3980122.0 | 4087200.0 | 107078.0 | 2.69 | 4087200.0 | … |
| 3848 | شمش طلا | GoldBar | گواهی سپرده پیوسته شمش طلای +9… | 10 | ضریب تبدیل نماد به گروه انبار | ریال | 24560013.0 | 24400000.0 | -160013.0 | -0.65 | 24470000.0 | … |

</details>

<details>
<summary><code>brsapi_ime_funds</code> — ~24,441 ردیف، 67 ستون (نمایش 12 ستون از 67)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeFundModel`
- API: `apps/api/endpoints/funds.py` (5)، `apps/api/endpoints/market_info.py` (1)
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/audit_data_access.py` (1)، `scripts/simulate_brsapi_usage.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | ins_id | symbol | name | isin | shares_count | base_volume | market_value | price_min | price_max | price_yesterday | price_first | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 21035 | 34144395039913458 | عیار | صندوق طلای عیار مفید | IRTKMOFD0001 | 4810000000 | 1 | 2425110610000000.0 | 501998.0 | 508142.0 | 508624.0 | 508139.0 | … |
| 21036 | 32469128621155736 | مثقال | صندوق س.کالای آگاه | IRTKZARA0001 | 3000000000 | 1 | 439005000000000.0 | 145713.0 | 147864.0 | 147482.0 | 147864.0 | … |

</details>

<details>
<summary><code>brsapi_ime_futures</code> — ~8,379 ردیف، 59 ستون (نمایش 12 ستون از 59) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeFutureModel`
- سرویس: `services/quant_signal_orchestrator.py` (1)
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/fix_dual_date_remaining.py` (1)، `scripts/simulate_brsapi_usage.py` (1)، `scripts/start_scheduler.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | contract_code | contract_description | contract_size | contract_size_unit | contract_currency | date_end | date_end_text | days_remaining | margin_initial | margin_maintenance | open_interest | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | SILKH05 | قرارداد آتی گواهی سپرده نقره ت… | 10 | گرم | ریال | 0000-00-00 |  | 0 | 26900000.0 | 18830000.0 | 0 | … |
| 2 | GB19MO05 | قرارداد آتی شمش طلای خام 995 ت… | 1 | گرم | ریال | 0000-00-00 |  | 0 | 66000000.0 | 46200000.0 | 0 | … |

</details>

<details>
<summary><code>brsapi_ime_options</code> — ~58,294 ردیف، 101 ستون (نمایش 12 ستون از 101)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeOptionModel`
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/simulate_brsapi_usage.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | contract_category | contract_category_sub | contract_category_commodity | strike_price | level_strike | call_contract_id | call_contract_code | call_contract_description | call_contract_size | call_contract_size_unit | call_contract_currency | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 48304 | DY05   تاریخ سررسید: 1405/10/2… | LG ETCDY05 | LG ETC | 700000.0 | -3 | 1002143 | TLDY05C70 | قرارداد اختیار معامله خرید واح… | 1 | واحد | ریال | … |
| 48305 | AZ05   تاریخ سررسید: 1405/09/2… | SilverBarAZ05 | SilverBar | 2400000.0 | -6 | 1002144 | SLAZ05C240 | قرارداد اختیار معامله خرید شمش… | 1 | SilverBar | ریال | … |

</details>

<details>
<summary><code>brsapi_ime_physical_trades</code> — ~935 ردیف، 37 ستون (نمایش 12 ستون از 37)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImePhysicalTradeModel`
- سرویس: `services/paper_trading_service.py` (1)
- اسکریپت: `scripts/fix_dual_date_remaining.py` (2)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | name | category_id | offer_code | market_hall | producer | supplier | broker | contract_type | settlement_type | date_price_settlement | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 688 | CHMI-BSO004X-00 | شمش بلوم (150*150)4SP | 1-1-1 | 1289806 | تالار صنعتی | شرکت معدنی وصنعتی چادرملو | معدنی و صنعتی چادر ملو | بانک سپه | سلف | نقدی / اعتباری | 2026/08/01 | … |
| 690 | AISC-BSD414X-00 | شمش بلوم (150*150) SWRY | 1-1-1 | 1291316 | تالار صنعتی | آهن و فولاد ارفع | آهن و فولاد ارفع | سی ولکس | سلف | نقدی / اعتباری | 2026/08/01 | … |

</details>

<details>
<summary><code>brsapi_index_values</code> — ~3,437 ردیف، 26 ستون (نمایش 12 ستون از 26)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `IndexValueModel`
- سرویس: `services/decision_gate.py` (3)، `services/quant_signal_orchestrator.py` (3)، `services/signal_decision_engine.py` (3)، `services/dynamic_weighting.py` (2)
- اسکریپت: `scripts/sync_all_tables.py` (1)، `scripts/sync_delta_report.py` (1)
- تست: `tests/unit/test_brsapi_sync_fixes.py` (2)، `tests/test_instrument_relations.py` (1)، `tests/unit/test_decision_gate.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `ml/train_weight_optimizer.py` (3)، `brsapi/parsers/tsetmc.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | name | state | index_value | index_change | index_change_pct | index_equal_weight | index_equal_weight_change | market_value | market_value_main | market_value_base | trade_count | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 3640 |  | بسته | 43871.09 | 1113.13 | 0.0 | 0.0 | 0.0 | 0.0 | 2.3105426381064972e+16 | 5101184554778607.0 | 332184 | … |
| 3643 |  | بسته | 5407901.78 | 130549.16 | 0.0 | 1534561.27 | 36742.34 | 1.550961153907927e+17 | 0.0 | 0.0 | 441737 | … |

</details>

<details>
<summary><code>brsapi_intraday_trades</code> — ~1,637,033 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `IntradayTradeModel`
- سرویس: `services/backtest_service.py` (3)
- اسکریپت: `scripts/dedup_and_constrain.py` (7)، `scripts/dedup_batched.py` (7)، `scripts/import_transactions.py` (6)، `scripts/analyze_db_issues.py` (2)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | row | time | volume | price | canceled | trade_date | created_at | ins_id | instrument_id | updated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1541428 | دعبید3 | 579 | 12:49:44 | 1701 | 18720.0 | False | 1405-05-12 | 2026-08-05 06:53:04.353461 | 51293756044181812 | NULL | NULL | … |
| 1541429 | دعبید3 | 580 | 12:49:44 | 98299 | 18720.0 | False | 1405-05-12 | 2026-08-05 06:53:04.353461 | 51293756044181812 | NULL | NULL | … |

</details>

<details>
<summary><code>brsapi_option_snapshots</code> — ~499,922 ردیف، 81 ستون (نمایش 12 ستون از 81)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `OptionSnapshotModel`
- API: `apps/api/endpoints/options.py` (3)، `apps/admin/dashboard.py` (1)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/audit_data_access.py` (1)، `scripts/sync_all_tables.py` (1)، `scripts/sync_delta_report.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | ins_id | symbol | name | isin | underlying_symbol | underlying_id | option_type | contract_size | strike_price | open_interest | date_begin | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 378000 | 18021230509502207 | ضستا5049 | اختیارخ شستا-2400-1405/05/14 | IRO9TAMN0J61 | شستا | 2400322364771558 | call | 1000 | 2400.0 | 0 | 1405-03-12 | … |
| 378001 | 30082561993947191 | ضملت5033 | اختیارخ وبملت-1354-1405/05/20 | IRO9BMLT0K41 | وبملت | 778253364357513 | call | 1000 | 1354.0 | 5194167 | 1405-03-12 | … |

</details>

<details>
<summary><code>brsapi_raw_payloads</code> — جدول خالی است (11 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `brsapi/models/base.py` → `RawPayloadModel`
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (2)

</details>

<details>
<summary><code>brsapi_shareholder_records</code> — ~768,334 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `ShareholderRecordModel`
- سرویس: `services/history_backfill_service.py` (2)
- اسکریپت: `scripts/import_shareholders.py` (11)، `scripts/analyze_shareholders.py` (9)، `scripts/backfill_shareholder_dates.py` (7)، `scripts/update_free_float.py` (4)
- تست: `tests/test_instrument_relations.py` (1)، `tests/unit/test_brsapi_shareholder_manual.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | shareholder_name | volume | percent | change | date | created_at | ins_id | instrument_id | updated_at | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1897589 | شتران | بانک صادرات ایران | 39119744887 | 5.995 | 0 | 2026-08-10 | 2026-08-10 02:56:15.492427 | 51617145873056483 | NULL | NULL | 2026-08-10 | … |
| 1897590 | شتران | شرکت سرمایه گذاری ایرانیان -سه… | 31074623449 | 4.762 | 0 | 2026-08-10 | 2026-08-10 02:56:15.492427 | 51617145873056483 | NULL | NULL | 2026-08-10 | … |

</details>

<details>
<summary><code>brsapi_symbol_details</code> — ~3,923 ردیف، 65 ستون (نمایش 12 ستون از 65)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `SymbolDetailModel`
- سرویس: `services/populate_profiles_service.py` (3)، `services/watchlist_service.py` (3)، `services/fundamental_service.py` (1)
- API: `apps/api/endpoints/brsapi.py` (4)، `apps/admin/dashboard.py` (1)
- اسکریپت: `scripts/fetch_all_symbols_full.py` (6)، `scripts/full_populate_profiles.py` (5)، `scripts/check_market_field.py` (4)، `scripts/fix_eps.py` (4)
- تست: `tests/unit/test_brsapi_symbol_details_daily_job.py` (3)، `tests/test_instrument_relations.py` (1)، `tests/test_sync_2.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (2)

**نمونه داده:**

| id | ins_id | instrument_id | symbol | name | name_en | isin | code_12 | code_5 | code_4 | market | board | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1286 | 25855824481936305 | NULL | آ س پ3 | آ.س.پ | A.S.P CO | IRO3ASPZ0003 | IRO3ASPZ0008 | ASPZ3 | ASPZ | فرابورس | -' | … |
| 1287 | 17758788623651072 | NULL | آتی1 | ص.س.ج. یکم آرمان آتی | Arman Ati 1 VCF-VR | IRT3VC020001 | IRT3VC020008 | VC021 | VC02 | فرابورس | -' | … |

</details>

<details>
<summary><code>brsapi_symbol_snapshots</code> — ~1,194,116 ردیف، 71 ستون (نمایش 12 ستون از 71)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `SymbolSnapshotModel`
- سرویس: `services/watchlist_service.py` (8)، `services/market_health_index.py` (5)، `services/iran_fear_greed_index.py` (4)، `services/populate_profiles_service.py` (4)
- API: `apps/api/endpoints/funds.py` (4)، `apps/api/endpoints/analysis.py` (3)، `apps/api/endpoints/ml.py` (2)، `apps/api/endpoints/news.py` (2)
- جاب: `jobs/definitions/sync_jobs.py` (3)، `jobs/definitions/alert_jobs.py` (1)، `jobs/definitions/fund_jobs.py` (1)
- اسکریپت: `scripts/full_populate_profiles.py` (7)، `scripts/merge_year_tables.py` (7)، `scripts/_check_symbols_state.py` (7)، `scripts/fetch_all_symbols_full.py` (6)
- تست: `tests/unit/test_brsapi_sync_fixes.py` (2)، `tests/test_instrument_relations.py` (1)، `tests/unit/services/test_paper_trading_service.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (5)، `brsapi/tests/test_tsetmc_symbols_integration.py` (2)، `diagnostics/ingestion_audit.py` (2)، `brsapi/jobs/registry.py` (1)

**نمونه داده:**

| id | ins_id | symbol | name | isin | sector | sector_id | shares_count | base_volume | market_value | eps | pe_ratio | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 6935329 | 26547785441834730 | زشریف | کشت وصنعت شریف آباد | IRO3SAAZ0001 | زراعت و خدمات وابسته | 1 | 2404787000 | 1 | 40833283260000.0 | 2402.0 | 7.1 | … |
| 6935330 | 48287767791629523 | رشد | صندوق س.رشد پایدار آبان-د | IRT3RSHF0001 | صندوق سرمایه‌گذاری قابل معامله | 68 | 4500000000 | 1 | 95418000000000.0 | 0.0 | 0.0 | … |

</details>

<details>
<summary><code>brsapi_sync_log</code> — ~50 ردیف، 13 ستون (نمایش 12 ستون از 13)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/base.py` → `SyncLogModel`
- API: `apps/api/endpoints/brsapi.py` (2)
- اسکریپت: `scripts/build_feature_store.py` (3)، `scripts/build_screener_scores.py` (2)، `scripts/clean_historical_data.py` (2)، `scripts/_check_nav_sync.py` (1)
- تست: `tests/unit/repositories/conftest.py` (3)، `tests/unit/test_brsapi_sync_status.py` (2)، `tests/unit/scripts/test_build_screener_scores.py` (2)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (2)

**نمونه داده:**

| id | endpoint | category | status | items_count | error_message | duration_ms | params_snapshot | started_at | completed_at | created_at | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 37620 | /Tsetmc/AllSymbols.php | tsetmc | error | 0 | RequestError: [Errno 11001] ge… | 9297.00000002049 | {"type": "1"} | 2026-08-06 21:00:24.227862 | 2026-08-06 21:00:24.202862 | 2026-08-06 21:00:24.228353 | 2026-08-06 | … |
| 37622 | /Tsetmc/Index.php | tsetmc | error | 0 | RequestError: [Errno 11001] ge… | 20703.999999997905 | {"type": "2"} | 2026-08-06 21:00:57.008610 | 2026-08-06 21:00:57.006613 | 2026-08-06 21:00:57.009027 | 2026-08-06 | … |

</details>

<details>
<summary><code>ml_engineered_features</code> — ~3 ردیف، 50 ستون (نمایش 12 ستون از 50) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود

**مراجع کد:**
- مدل: _بدون مدل ORM_
- API: `apps/scheduler/app.py` (1)
- جاب: `jobs/definitions/feature_store_jobs.py` (1)
- اسکریپت: `scripts/build_feature_store.py` (6)، `scripts/sync_delta_report.py` (1)

**نمونه داده:**

| symbol | trade_date | price_close | price_open | price_high | price_low | volume | trade_value | trade_count | rsi_14 | macd_histogram | macd_signal | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| فولاد | 2026-07-16 | 2354.0 | NULL | NULL | NULL | 5343075284 | 12463417315198.0 | 42892 | 100.0 | NULL | -1.0 | … |
| خودرو | 2026-07-18 | 602.0 | NULL | NULL | NULL | 7659535055 | 4569697218208.0 | 16159 | 9.4 | NULL | -1.0 | … |

</details>

<details>
<summary><code>ml_model_versions</code> — ~638 ردیف، 13 ستون (نمایش 12 ستون از 13)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/ml.py` → `MlModelVersionModel`
- سرویس: `services/inference_service.py` (3)
- API: `apps/api/endpoints/ml.py` (1)، `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/register_ml_artifacts.py` (2)

**نمونه داده:**

| id | model_id | version | stage | metrics | parameters | artifact_path | dataset_snapshot | training_run_id | created_at | updated_at | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| bayesian_ridge_آپ::v1-827f543e | bayesian_ridge_آپ | v1-827f543e | development | {"mean_mse": 0.001434, "std_ms… | {"feature_groups": ["price", "… | C:\Users\Iran\Desktop\temce\ml… | NULL | 827f543e6bc0 | 2026-08-02 08:53:54.313177 | NULL | 2026-08-02 | … |
| bayesian_ridge_آپ::v1-98a8f41d | bayesian_ridge_آپ | v1-98a8f41d | production | {"mean_mse": 0.001434, "std_ms… | {"feature_groups": ["price", "… | C:\Users\Iran\Desktop\temce\ml… | NULL | 98a8f41d3740 | 2026-08-02 08:53:54.313177 | NULL | 2026-08-02 | … |

</details>

<details>
<summary><code>ml_models</code> — ~359 ردیف، 11 ستون</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/ml.py` → `MlModelModel`
- سرویس: `services/diagnostics_runner.py` (1)، `services/inference_service.py` (1)
- API: `apps/admin/dashboard.py` (5)، `apps/api/endpoints/ml.py` (1)، `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/batch_backtest_ml.py` (4)، `scripts/batch_final.py` (4)، `scripts/register_ml_artifacts.py` (2)

**نمونه داده:**

| id | name | task | framework | latest_version | description | tags | updated_at | created_at | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|
| bayesian_ridge_آبادا | bayesian_ridge_آبادا | regression | bayesian_ridge | v1-042f4bc2 | مدل bayesian_ridge آموزش‌دیده … | ["آبادا", "bayesian_ridge", "b… | 2026-07-18 01:26:42.044000 | 2026-08-02 08:53:54.313177 | 2026-08-02 | 1405-05-11 |
| bayesian_ridge_آپ | bayesian_ridge_آپ | regression | bayesian_ridge | v1-98a8f41d | مدل bayesian_ridge آموزش‌دیده … | ["آپ", "bayesian_ridge", "baye… | 2026-07-18 01:26:42.350939 | 2026-08-02 08:53:54.313177 | 2026-08-02 | 1405-05-11 |

</details>

<details>
<summary><code>ml_predictions</code> — ~20,674 ردیف، 22 ستون (نمایش 12 ستون از 22)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/ml.py` → `MlPredictionModel`
- سرویس: `services/quant_signal_orchestrator.py` (6)، `services/diagnostics_runner.py` (1)

**نمونه داده:**

| id | batch_id | symbol | model_type | prediction | accuracy | confidence | f1_score | mse | samples | duration_seconds | predicted_change_pct | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| mlpred_93f9ad38bf6a4da594bc0aa… | 2cb3168bc8cc | خودرو | xgboost | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.02 | NULL | … |
| mlpred_7c67858be2e94a4abb4d7d3… | 2cb3168bc8cc | آبادا | xgboost | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.02 | NULL | … |

</details>

<details>
<summary><code>ml_symbol_results</code> — ~5,506 ردیف، 22 ستون (نمایش 12 ستون از 22) ⚠️ 4 مشکل</summary>

**مشکلات (4):**
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون منبع تاریخ `start_date` در نمونه NULL دارد
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: _بدون مدل ORM_
- اسکریپت: `scripts/run_ml_dual.py` (6)، `scripts/train.py` (5)، `scripts/test_train_single.py` (4)، `scripts/train_all_symbols.py` (4)

**نمونه داده:**

| id | symbol | data_type | model_type | status | metrics | fold_metrics | feature_importance | train_samples | val_samples | feature_count | feature_groups | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 56cf3beecafd | آكنتور | daily |  | failed | NULL | NULL | NULL | 0 | 0 | 0 | NULL | … |
| 24d441229ae2 | آسيا | daily |  | failed | NULL | NULL | NULL | 0 | 0 | 0 | NULL | … |

</details>

<details>
<summary><code>ml_training_runs</code> — ~6,078 ردیف، 17 ستون (نمایش 12 ستون از 17)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/ml.py` → `MlTrainingRunModel`
- سرویس: `services/diagnostics_runner.py` (1)
- API: `apps/api/endpoints/ml.py` (1)، `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/import_train_results_to_runs.py` (4)، `scripts/register_ml_artifacts.py` (2)

**نمونه داده:**

| id | experiment_name | run_name | status | model_type | config | metrics | best_params | progress_pct | started_at | finished_at | duration_seconds | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| tam_01d9e33bc81b | train_all_models | hist_gradient_boosting-آ س پ | completed | hist_gradient_boosting | {"symbol": "آ س پ", "data_type… | {"r2": 0.0159, "mae": 0.000569… | {} | 100.0 | 2026-08-02 21:55:18.553135 | 2026-08-02 21:55:18.553135 | 3.4 | … |
| 00658db0abb3 | bayesian_ridge-آبادا-20260718 | bayesian_ridge-آبادا | completed | bayesian_ridge | {"symbol": "آبادا", "feature_g… | {"mean_mse": 0.000292, "std_ms… | {} | 100.0 | 2026-07-18 01:17:29.013199 | 2026-07-18 01:17:29.013199 | NULL | … |

</details>

<details>
<summary><code>tabdeal_accounts</code> — جدول خالی است (15 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `tabdeal/models.py` → `TabdealAccountModel`

</details>

<details>
<summary><code>tabdeal_balances</code> — جدول خالی است (10 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `tabdeal/models.py` → `TabdealBalanceModel`

</details>

<details>
<summary><code>tabdeal_listen_keys</code> — جدول خالی است (9 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `tabdeal/models.py` → `TabdealListenKeyModel`

</details>

<details>
<summary><code>tabdeal_markets</code> — جدول خالی است (21 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `tabdeal/models.py` → `TabdealMarketInfoModel`
- API: `apps/api/endpoints/tabdeal.py` (1)

</details>

<details>
<summary><code>tabdeal_orders</code> — جدول خالی است (25 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `tabdeal/models.py` → `TabdealOrderModel`

</details>

<details>
<summary><code>tabdeal_trades</code> — جدول خالی است (19 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `tabdeal/models.py` → `TabdealTradeModel`

</details>

<details>
<summary><code>open_interest_history</code> — جدول خالی است (8 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` است

**مراجع کد:**
- مدل: `models/option.py` → `OpenInterestHistoryModel`
- اسکریپت: `scripts/fix_schema_gap.py` (1)

</details>

<details>
<summary><code>option_contracts</code> — جدول خالی است (18 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است

**مراجع کد:**
- مدل: `models/option.py` → `OptionContractModel`
- اسکریپت: `scripts/fix_schema_gap.py` (1)

</details>

<details>
<summary><code>option_snapshots</code> — جدول خالی است (27 ستون) ⚠️ 4 مشکل</summary>

**مشکلات (4):**
- جدول خالی است
- نسخه قدیمی است — جدول زنده `brsapi_option_snapshots` جایگزین آن است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است

**مراجع کد:**
- مدل: `models/option.py` → `OptionSnapshotModel`
- اسکریپت: `scripts/fix_schema_gap.py` (1)
- سایر: `brsapi/services/query_service.py` (1)

</details>

<details>
<summary><code>option_trades</code> — جدول خالی است (13 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است

**مراجع کد:**
- مدل: `models/option.py` → `OptionTradeModel`
- اسکریپت: `scripts/fix_schema_gap.py` (1)

</details>

<details>
<summary><code>options</code> — ~3,225 ردیف، 13 ستون (نمایش 12 ستون از 13) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- ستون منبع تاریخ `expiry_date` در نمونه NULL دارد
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/market_data.py` → `StockOptionModel`
- سرویس: `services/options_service.py` (13)، `services/multi_market_signal_engine.py` (4)، `services/options_analytics.py` (4)، `services/symbol_catalog.py` (2)
- API: `apps/api/endpoints/options.py` (13)، `apps/api/endpoints/brsapi.py` (4)، `apps/api/endpoints/screener_v2.py` (1)
- جاب: `jobs/replay.py` (1)، `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/brsapi_full_update.py` (5)، `scripts/run_full_backtest.py` (5)، `scripts/_tmp_api_test2.py` (4)، `scripts/_tmp_api_test4.py` (3)
- تست: `tests/unit/domain/test_black_scholes_pricing.py` (38)، `tests/unit/options/test_options_comprehensive.py` (13)، `tests/test_all_pages.py` (2)، `tests/unit/test_backend_api_edge_cases.py` (2)
- سایر: `domain/options/margin_engine.py` (13)، `domain/options/commodity_pricing.py` (9)، `test_options.py` (7)، `domain/options/tree_pricing.py` (7)

**نمونه داده:**

| id | symbol | underlying_symbol | strike_price | expiry_date | option_type | price_last | price_close | trade_count | trade_volume | time | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | ضملت4021 |  | NULL | NULL | call | 2.0 | 3.0 | 18485 | 8930627 | 2026-07-14 14:58:07.656964+00:… | NULL | … |
| 2 | ضملت4020 |  | NULL | NULL | call | 30.0 | 33.0 | 17210 | 7457580 | 2026-07-14 14:58:07.665000+00:… | NULL | … |

</details>

<details>
<summary><code>volatility_surface</code> — جدول خالی است (11 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` است

**مراجع کد:**
- مدل: `models/option.py` → `VolatilitySurfaceModel`
- اسکریپت: `scripts/fix_schema_gap.py` (1)

</details>

<details>
<summary><code>brsapi_nav_records</code> — ~245 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `NavRecordModel`
- API: `apps/api/endpoints/funds.py` (4)، `apps/api/endpoints/brsapi.py` (2)، `apps/admin/dashboard.py` (1)
- جاب: `jobs/definitions/sync_jobs.py` (1)
- اسکریپت: `scripts/_check_nav_sync.py` (2)، `scripts/analyze_db_issues.py` (1)، `scripts/backfill_ins_id.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | nav_issue | nav_redemption | date | time | fetched_at | raw_json | created_at | ins_id | instrument_id | updated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 140 | ابتکار | 20919.0 | 20711.0 | 1405-05-17 | 08:59:30 | 2026-08-08 05:30:19 | {"date": "1405-05-17", "time":… | 2026-08-08 09:00:00.016267 | 65473703162196532 | NULL | NULL | … |
| 141 | آبنوس | 25906.0 | 25649.0 | 1405-05-17 | 15:57:15 | 2026-08-08 12:27:52 | {"date": "1405-05-17", "time":… | 2026-08-08 15:57:51.099023 | 40912525017440979 | NULL | NULL | … |

</details>

<details>
<summary><code>daily_real_legal</code> — ~387,701 ردیف، 16 ستون (نمایش 12 ستون از 16)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/market_data.py` → `DailyRealLegalModel`
- سرویس: `services/populate_profiles_service.py` (2)، `services/screener110_service.py` (2)، `services/screener_ai_report_service.py` (2)، `services/screener_service.py` (2)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/full_populate_profiles.py` (1)، `scripts/populate_profiles.py` (1)
- سایر: `ml/features/trade_features.py` (2)

**نمونه داده:**

| symbol_id | trade_date | real_buy_count | real_sell_count | legal_buy_count | legal_sell_count | real_buy_volume | real_sell_volume | legal_buy_volume | legal_sell_volume | real_buy_value | real_sell_value | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1234567890123456 | 2026-07-13 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | … |
| 1234567890123456 | 2026-07-12 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | … |

</details>

<details>
<summary><code>etf_nav</code> — ~12 ردیف، 7 ستون ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ۱۲ ردیف یتیم بدون مصرف‌کننده — نسخه‌های زنده `brsapi_nav_records` و `funds` جایگزین‌اند

**مراجع کد:**
- مدل: `models/market_data.py` → `EtfNavModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| symbol_id | time | nav | price | discount_premium | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|
| 57534567890123457 | 2026-07-07 12:28:05+00:00 | 28362.5 | NULL | NULL | 2026-07-07 | 1405-04-16 |
| 57534567890123458 | 2026-07-07 11:33:48+00:00 | 50452.0 | NULL | NULL | 2026-07-07 | 1405-04-16 |

</details>

<details>
<summary><code>funds</code> — ~27 ردیف، 31 ستون (نمایش 12 ستون از 31)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `iran_market_data/app/storage/models.py` → `FundInfo`
- مدل: `models/fund.py` → `FundModel`
- سرویس: `services/fund_service.py` (13)، `services/symbol_catalog.py` (4)، `services/unified_assistant_service.py` (2)، `services/chat/chat_engine.py` (1)
- API: `apps/api/endpoints/funds.py` (46)، `apps/api/endpoints/market_info.py` (6)، `apps/api/router.py` (5)، `apps/api/endpoints/brsapi.py` (3)
- جاب: `jobs/definitions/fund_jobs.py` (4)، `jobs/definitions/brsapi_jobs.py` (1)
- ریپازیتوری: `repositories/fund_repository.py` (5)
- اسکریپت: `scripts/_tmp_api_test2.py` (8)، `scripts/fix_schema_gap.py` (5)، `scripts/_tmp_api_test.py` (2)، `scripts/_tmp_api_test3.py` (2)
- تست: `tests/unit/test_funds_api.py` (51)، `tests/unit/jobs/test_job_context_result.py` (4)، `tests/unit/services/test_fund_service.py` (4)، `tests/unit/test_backend_api.py` (3)
- سایر: `brsapi/services/sync_service.py` (6)، `iran_market_data/app/collectors/fipiran.py` (6)، `domain/funds/__init__.py` (3)، `providers/funds/provider.py` (3)

**نمونه داده:**

| id | symbol | name | isin | fund_type | nav | nav_change | nav_change_pct | price_last | price_close | price_yesterday | price_max | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| fund_cc7433533b8548e482f5d848 | آگاس | صندوق س.هستی بخش آگاه-س | IRT3SAGF0001 | سهامی | 384689.0 | 11204.0 | 3.0 | 384689.0 | 384689.0 | 373485.0 | 384689.0 | … |
| fund_3ac466660f554121a99237de | اطلس | صندوق س.توسعه اطلس مفید-س | IRT3SATF0001 | سهامی | 130919.0 | 3813.0 | 3.0 | 130919.0 | 130865.0 | 127106.0 | 130919.0 | … |

</details>

<details>
<summary><code>indicators</code> — جدول خالی است (13 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/indicator.py` → `IndicatorModel`
- سرویس: `services/smart_screener_v2.py` (9)، `services/codal_analysis/audit_workflow.py` (9)، `services/smart_money/advanced_analytics.py` (9)، `services/macro_service.py` (5)
- API: `apps/api/endpoints/backtests.py` (7)، `apps/api/router.py` (4)، `apps/api/endpoints/stock_assistant.py` (4)، `apps/api/endpoints/compose.py` (2)
- جاب: `jobs/definitions/macro_jobs.py` (4)، `jobs/definitions/analytics_jobs.py` (3)
- ریپازیتوری: `repositories/indicator_repository.py` (2)
- اسکریپت: `scripts/backtest_all_symbols.py` (3)، `scripts/run_full_backtest.py` (3)، `scripts/audit_data_access.py` (2)، `scripts/rebuild_indicators.py` (2)
- تست: `tests/unit/services/test_audit_modules.py` (7)، `tests/test_compose.py` (5)، `tests/unit/pipelines/test_indicator_pipeline.py` (5)، `tests/fixtures/sample_macro.py` (3)
- سایر: `backtesting/composer/indicator_registry.py` (26)، `domain/indicators/registry/__init__.py` (11)، `backtesting/strategies/incremental_indicators.py` (6)، `domain/indicators/__init__.py` (6)

</details>

<details>
<summary><code>orderbook_snapshots</code> — جدول خالی است (34 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو

**مراجع کد:**
- مدل: _بدون مدل ORM_
- مرجع کد فعال: _هیچ_

</details>

<details>
<summary><code>orderbooks</code> — جدول خالی است (12 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/orderbook.py` → `OrderbookModel`
- API: `apps/api/router.py` (3)، `apps/admin/dashboard.py` (2)، `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/_tmp_api_test4.py` (3)، `scripts/_tmp_api_test2.py` (2)، `scripts/analyze_db_issues.py` (1)
- تست: `tests/comprehensive/test_all.py` (2)
- سایر: `core/constants/paths.py` (1)

</details>

<details>
<summary><code>quotes</code> — ~3,366,996 ردیف، 29 ستون (نمایش 12 ستون از 29)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/quote.py` → `QuoteModel`
- سرویس: `services/backtest_service.py` (11)، `services/market_service.py` (11)، `services/unified_assistant_service.py` (3)، `services/inference_service.py` (2)
- API: `apps/api/endpoints/alpha.py` (6)، `apps/api/router.py` (4)، `apps/api/endpoints/backtests.py` (4)، `apps/api/endpoints/brsapi.py` (4)
- جاب: `jobs/definitions/sync_jobs.py` (9)، `jobs/market_data_jobs.py` (1)، `jobs/definitions/alert_jobs.py` (1)، `jobs/definitions/housekeeping_jobs.py` (1)
- ریپازیتوری: `repositories/quote_repository.py` (10)
- اسکریپت: `scripts/create_symbol_kpi_view.py` (9)، `scripts/import_backtest_data.py` (8)، `scripts/test_alpha_direct.py` (6)، `scripts/debug_db_check2.py` (5)
- تست: `tests/comprehensive/test_all.py` (5)، `tests/unit/domain/test_quote_rules.py` (5)، `tests/unit/pipelines/test_quote_normalizer.py` (5)، `tests/unit/pipelines/test_quote_validator.py` (5)
- سایر: `backtesting/microstructure/calibration.py` (18)، `backtesting/calibration/nightly_calibration.py` (10)، `backtesting/calibration/impact_calibration.py` (7)، `backtesting/calibration/liquidity_depth_model.py` (6)

**نمونه داده:**

| id | instrument_id | symbol | price_close | price_open | price_high | price_low | price_last | price_change | price_change_pct | volume | value | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 436dd31e379673edb2fd327ce56ea8… | بکام3 | بکام3 | 1513.0 | 0.0 | 0.0 | 0.0 | 1513.0 | 12.0 | 0.8 | 0 | 0.0 | … |
| 6c6b31f3b14ac87484bda9f8823c54… | بکام3 | بکام3 | 1501.0 | 0.0 | 0.0 | 0.0 | 1501.0 | 0.0 | 0.0 | 0 | 0.0 | … |

</details>

<details>
<summary><code>shareholders</code> — ~2,390 ردیف، 8 ستون</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/market_data.py` → `ShareholderModel`
- سرویس: `services/symbol_detail_service.py` (15)، `services/sync_master_service.py` (1)
- API: `apps/api/endpoints/brsapi.py` (6)
- اسکریپت: `scripts/import_shareholders.py` (3)، `scripts/analyze_db_issues.py` (1)، `scripts/analyze_shareholders.py` (1)، `scripts/simulate_brsapi_usage.py` (1)
- تست: `tests/unit/test_brsapi_history_backfill_manual.py` (1)
- سایر: `ingestion/sources/library_sources.py` (3)، `brsapi/jobs/registry.py` (1)، `brsapi/migrations/001_create_brsapi_tables.py` (1)، `brsapi/services/query_service.py` (1)

**نمونه داده:**

| symbol_id | record_date | holder_name | volume | percent | change | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 28534567890123456 | 2026-07-08 | شخص حقیقی | 49530000 | 2.008 | 0.0 | 2026-07-08 | 1405-04-17 |
| 35134567890123456 | 2026-07-08 | شخص حقیقی | 45883823 | 1.941 | 0.0 | 2026-07-08 | 1405-04-17 |

</details>

<details>
<summary><code>trades</code> — ~14,884,365 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/trade.py` → `TradeModel`
- سرویس: `services/block_trade_detector.py` (19)، `services/ensemble_engine.py` (10)، `services/trade_service.py` (10)، `services/mass_scanner_service.py` (9)
- API: `apps/api/endpoints/tabdeal.py` (14)، `apps/api/endpoints/alpha.py` (9)، `apps/api/endpoints/paper_trading.py` (8)، `apps/api/endpoints/backtests.py` (5)
- جاب: `jobs/definitions/paper_trading_job.py` (4)، `jobs/definitions/brsapi_jobs.py` (1)، `jobs/definitions/housekeeping_jobs.py` (1)
- ریپازیتوری: `repositories/backtest_repository.py` (1)
- اسکریپت: `scripts/backtest_all_symbols.py` (12)، `scripts/test_alpha_direct.py` (9)، `scripts/run_full_backtest.py` (6)، `scripts/test_single_symbol.py` (6)
- تست: `tests/unit/test_paper_trading_api.py` (18)، `tests/unit/backtesting/test_analytics_cost_basis.py` (18)، `tests/unit/test_trades_e2e.py` (17)، `tests/unit/services/test_trade_service.py` (10)
- سایر: `backtesting/microstructure/calibration.py` (20)، `backtesting/optimization/walk_forward.py` (20)، `backtesting/calibration/nightly_calibration.py` (16)، `backtesting/abm/matching_engine.py` (10)

**نمونه داده:**

| id | instrument_id | symbol | price | volume | value | side | time | date | data_source | created_at | updated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| e9efe6bd7320406fc8be5c92557bb8… | سخاش | سخاش | 11690.0 | 7979 | 93274510.0 | NULL | 09:55:38 | 1405-03-18 | tsetmc | 2026-07-12 12:08:26.530015 | NULL | … |
| 55280438b0860564df67194bb1ef0f… | سخاش | سخاش | 11690.0 | 52481 | 613502890.0 | NULL | 09:55:38 | 1405-03-18 | tsetmc | 2026-07-12 12:08:26.530015 | NULL | … |

</details>

<details>
<summary><code>backtest_runs</code> — ~1,579 ردیف، 22 ستون (نمایش 12 ستون از 22)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/backtest.py` → `BacktestRunModel`
- سرویس: `services/diagnostics_runner.py` (2)
- API: `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/debug_db_check.py` (3)، `scripts/debug_db_check2.py` (3)، `scripts/backtest_all_symbols.py` (2)
- تست: `tests/unit/test_ws_origin_and_table_guard.py` (1)
- سایر: `postgresql_client.py` (5)

**نمونه داده:**

| id | name | strategy_type | symbols | status | start_date | end_date | initial_capital | current_value | total_return_pct | commission_pct | slippage_bps | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| bt_9acbb4afda27405ca19890af | Test Backtest | moving_average_cross | ["فولاد"] | completed | 2024-01-01 | 2024-12-31 | 1000000000.0 | 999998821.3673556 | -0.0001 | 0.0035 | 10.0 | … |
| bt_299c9f000309408d8d2deca5 | T1 | moving_average_cross | ["فولاد"] | completed | 2025-01-01 | 2025-06-01 | 1000000000.0 | 999999537.6762643 | NULL | 0.0035 | 10.0 | … |

</details>

<details>
<summary><code>backtest_trades</code> — جدول خالی است (18 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/backtest.py` → `BacktestTradeModel`
- API: `apps/api/endpoints/tables.py` (1)
- سایر: `postgresql_client.py` (2)

</details>

<details>
<summary><code>calibration_models</code> — جدول خالی است (15 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود

**مراجع کد:**
- مدل: _بدون مدل ORM_
- سرویس: `services/probability_calibrator.py` (7)، `services/quant_signal_orchestrator.py` (5)
- تست: `tests/unit/services/test_probability_calibrator.py` (1)

</details>

<details>
<summary><code>compare_results</code> — جدول خالی است (20 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/compare.py` → `CompareResultModel`

</details>

<details>
<summary><code>generated_strategies</code> — جدول خالی است (38 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/generated_strategy.py` → `GeneratedStrategyModel`
- سرویس: `services/mass_scanner_service.py` (3)
- API: `apps/api/endpoints/backtests.py` (1)
- اسکریپت: `scripts/_create_generated_strategies.py` (11)، `scripts/backtest_all_symbols.py` (6)، `scripts/run_full_backtest.py` (3)، `scripts/_check_tables.py` (3)

</details>

<details>
<summary><code>generation_batches</code> — جدول خالی است (14 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/generated_strategy.py` → `GenerationBatchModel`
- اسکریپت: `scripts/_create_generated_strategies.py` (4)

</details>

<details>
<summary><code>queue_analysis_results</code> — ~500 ردیف، 30 ستون (نمایش 12 ستون از 30)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/queue_analysis.py` → `QueueAnalysisResult`
- سرویس: `services/queue_analysis_service.py` (2)
- API: `apps/api/endpoints/queue_analysis.py` (1)
- اسکریپت: `scripts/fix_schema_gap.py` (1)

**نمونه داده:**

| id | symbol | run_id | market_type | queue_status | queue_volume_ratio | queue_days_streak | queue_type_change | distance_to_limit | last_price | limit_up | limit_down | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | وپاسار2 | queue-auto-20260807-104110-83f… | bours | NONE | 0.0 | 0 | QUEUE_BROKEN | 0.0 | 9940.0 | 10143.0 | 9177.0 | … |
| 2 | عیار | queue-auto-20260807-104110-83f… | bours | NONE | 0.0 | 0 | NO_CHANGE | 0.0 | 502700.0 | 534055.0 | 483193.0 | … |

</details>

<details>
<summary><code>screener_daily_scores</code> — ~1,515 ردیف، 14 ستون (نمایش 12 ستون از 14) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود

**مراجع کد:**
- مدل: _بدون مدل ORM_
- جاب: `jobs/definitions/feature_store_jobs.py` (1)
- اسکریپت: `scripts/build_screener_scores.py` (5)، `scripts/sync_delta_report.py` (1)
- تست: `tests/unit/scripts/test_build_screener_scores.py` (2)
- سایر: `ml/train_weight_optimizer.py` (4)

**نمونه داده:**

| symbol | trade_date | score_total | score_momentum | score_value | score_growth | score_quality | score_liquidity | score_sentiment | rank_in_market | rank_in_industry | percentile_score | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| آبادا | 2026-08-11 | 2.200000047683716 | 0.0 | 0.0 | 7.5 | 0.0 | 5.0 | 5.0 | 461 | 5 | 9.800000190734863 | … |
| آپ | 2026-08-11 | 2.200000047683716 | 0.0 | 0.0 | 7.5 | 0.0 | 5.0 | 5.0 | 462 | 8 | 9.600000381469727 | … |

</details>

<details>
<summary><code>screener_profiles</code> — ~1,562 ردیف، 62 ستون (نمایش 12 ستون از 62)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/screener.py` → `ScreenerProfile`
- سرویس: `services/populate_profiles_service.py` (3)، `services/screener_ai_report_service.py` (3)، `services/screener110_service.py` (2)، `services/sync_master_service.py` (1)
- API: `apps/api/endpoints/screener110.py` (5)
- اسکریپت: `scripts/full_populate_profiles.py` (14)، `scripts/fix_eps.py` (8)، `scripts/update_free_float.py` (6)، `scripts/import_codal_to_profiles.py` (3)

**نمونه داده:**

| symbol | industry | sub_industry | free_float_shares | eps_current | eps_prev_year | exchange_rate_base | inflation_rate | net_operating_profit | accumulated_loss | registered_capital | legal_reserve | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| وپایا | سرمایه‌گذاری‌ها |  | 0 | 235.0 | 199.75 | 28500.0 | 35.0 | NULL | 0.0 | 13000.0 | NULL | … |
| وپترو3 | محصولات شیمیایی |  | 0 | 6913.0 | 5876.05 | 28500.0 | 35.0 | NULL | 0.0 | 1820.0 | NULL | … |

</details>

<details>
<summary><code>screener_signals</code> — ~511 ردیف، 37 ستون (نمایش 12 ستون از 37)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/screener.py` → `ScreenerSignal`
- سرویس: `services/screener_ai_report_service.py` (9)، `services/screener110_service.py` (1)
- API: `apps/api/endpoints/screener110.py` (5)
- جاب: `jobs/definitions/screener_jobs.py` (1)
- اسکریپت: `scripts/build_screener_scores.py` (1)

**نمونه داده:**

| id | symbol | generated_at | current_price | live_pe | pe_ratio | institutional_ratio | volume_spike | liquidity_pct | nima_free_spread | score_fundamental | score_valuation | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | آبادا | 2026-08-09 15:06:44.146146 | 9040.0 | 8.3 | 1.31 | 0.0 | 1.0 | 10698939170.0 | 6.523 | 7.5 | 10.0 | … |
| 2 | آپ | 2026-08-09 15:06:44.146146 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 6.523 | 7.5 | 20.0 | … |

</details>

<details>
<summary><code>screener_snapshots</code> — ~511 ردیف، 20 ستون (نمایش 12 ستون از 20)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/screener.py` → `ScreenerSnapshot`
- سرویس: `services/screener110_service.py` (4)، `services/screener_ai_report_service.py` (1)
- جاب: `jobs/definitions/screener_jobs.py` (1)

**نمونه داده:**

| symbol | timestamp | open | high | low | close | volume | current_price | price_change_pct | today_volume | avg_daily_value | institutional_buy | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| آبادا | 2026-08-09 15:06:44.146146 | NULL | NULL | NULL | NULL | NULL | 9040.0 | NULL | 1197640 | NULL | NULL | … |
| آپ | 2026-08-09 15:06:44.146146 | NULL | NULL | NULL | NULL | NULL | 0.0 | NULL | 0 | NULL | NULL | … |

</details>

<details>
<summary><code>signal_accuracy</code> — ~3,693 ردیف، 28 ستون (نمایش 12 ستون از 28)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/signal_accuracy.py` → `SignalAccuracyModel`
- سرویس: `services/quant_signal_orchestrator.py` (12)، `services/signal_performance_tracker.py` (7)، `services/diagnostics_runner.py` (3)، `services/probability_calibrator.py` (3)
- اسکریپت: `scripts/_check_signal_health.py` (17)، `scripts/cleanup_signal_accuracy.py` (9)
- تست: `tests/e2e/test_orchestrator_pipeline.py` (4)، `tests/unit/test_ws_origin_and_table_guard.py` (1)
- سایر: `core/calibration_bootstrap.py` (2)

**نمونه داده:**

| id | signal_id | symbol | market | source | direction | timeframe | actual_return_pct | direction_correct | max_profit_pct | max_loss_pct | hit_target1 | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| sacc_219f97292b0f4fd1a8308618 | sig_7de42aba222c4e16a11273ee | کاسپین | stock | voting_weighted | buy | daily | 2.472703917790623 | True | 0.0 | 0.0 | False | … |
| sacc_3686a67eec9b4a3b8efce964 | sig_3c6c60b2b649475abc188b59 | AMD | currency | voting_weighted | buy | daily | -3.787878787878788 | False | 0.0 | 0.0 | False | … |

</details>

<details>
<summary><code>signals</code> — ~4 ردیف، 17 ستون (نمایش 12 ستون از 17)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/signal.py` → `SignalModel`
- سرویس: `services/quant_signal_orchestrator.py` (67)، `services/multi_market_signal_engine.py` (41)، `services/ensemble_engine.py` (12)، `services/unified_assistant_service.py` (11)
- API: `apps/api/app.py` (21)، `apps/api/endpoints/multi_market_signals.py` (12)، `apps/api/endpoints/signal_insights.py` (9)، `apps/api/endpoints/screener110.py` (6)
- جاب: `jobs/definitions/paper_trading_job.py` (5)، `jobs/definitions/screener_jobs.py` (2)، `jobs/signal_generation.py` (1)
- ریپازیتوری: `repositories/signal_repository.py` (8)
- اسکریپت: `scripts/run_full_backtest.py` (15)، `scripts/debug_signal_gates.py` (4)، `scripts/dump_signal_code.py` (4)، `scripts/_check_signal_health.py` (4)
- تست: `tests/unit/services/test_quant_signal_orchestrator.py` (83)، `tests/benchmark_signal_quality.py` (51)، `tests/unit/test_rate_limit_middleware.py` (50)، `tests/e2e/test_orchestrator_pipeline.py` (22)
- سایر: `backtesting/research/alpha_evaluation_engine.py` (36)، `backtesting/engine/vectorized_engine.py` (12)، `backtesting/signals/signal_conflict_resolver.py` (12)، `backtesting/alpha/fast_evaluator.py` (8)

**نمونه داده:**

| id | instrument_id | symbol | signal_type | strength | direction | source | indicators | message | timeframe | data_source | generated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| sig_f9ddc27d231a486ab9b39ec2 | فولاد |  | bullish | 0.75 | NULL | NULL | NULL | NULL | 1d | system | 2026-07-18 02:52:29.325664 | … |
| sig_1ccd148cdf2a469e8e1a9e18 | فولاد |  | bullish | 0.75 | NULL | NULL | NULL | NULL | 1d | system | 2026-07-28 00:45:50.908871 | … |

</details>

<details>
<summary><code>audit_logs</code> — جدول خالی است (12 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/audit_log.py` → `AuditLogModel`
- API: `apps/api/endpoints/tables.py` (1)
- سایر: `database_handler.py` (2)، `data_repo.py` (1)، `datenrepo.py` (1)

</details>

<details>
<summary><code>audit_trail</code> — جدول خالی است (10 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `AuditTrail`

</details>

<details>
<summary><code>decision_architectures</code> — ~1 ردیف، 9 ستون</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/decision_engine.py` → `DecisionArchitecture`
- API: `apps/api/endpoints/decision_engine.py` (2)، `apps/api/app.py` (1)
- اسکریپت: `scripts/seed_architecture.py` (3)
- تست: `tests/unit/services/test_decision_engine_auto_seed.py` (1)

**نمونه داده:**

| id | version | title | data | is_active | created_at | updated_at | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|
| 1 | Enterprise-Final-1.0 | سامانه تصمیم‌یار بورس تهران | {'api': {'meta': {'version': '… | True | 2026-07-27 23:34:58.535204 | NULL | 2026-07-27 | 1405-05-05 |

</details>

<details>
<summary><code>decision_results</code> — جدول خالی است (25 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/decision_engine.py` → `DecisionResult`
- API: `apps/api/endpoints/decision_engine.py` (2)
- اسکریپت: `scripts/seed_architecture.py` (1)

</details>

<details>
<summary><code>job_runs</code> — جدول خالی است (15 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- رکوردزنی جاب‌ها در `services/job_service.py` پیاده‌سازی نشده — جدول در عمل خالی می‌ماند

**مراجع کد:**
- مدل: `models/job_run.py` → `JobRunModel`
- API: `apps/admin/dashboard.py` (4)، `apps/api/endpoints/jobs.py` (4)، `apps/api/endpoints/data_import.py` (2)، `apps/api/endpoints/tables.py` (1)
- سایر: `monitoring/job_monitor.py` (1)

</details>

<details>
<summary><code>provider_health</code> — جدول خالی است (14 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/provider_health.py` → `ProviderHealthModel`
- API: `apps/api/endpoints/tables.py` (1)
- سایر: `schemas/admin/__init__.py` (1)

</details>

<details>
<summary><code>provider_health_history</code> — جدول خالی است (8 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/provider_health.py` → `ProviderHealthHistoryModel`
- API: `apps/api/endpoints/tables.py` (1)

</details>

<details>
<summary><code>alert_history</code> — ~1,536 ردیف، 8 ستون</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/alert.py` → `AlertHistoryModel`
- API: `apps/api/endpoints/tables.py` (1)
- جاب: `jobs/definitions/alert_jobs.py` (1)

**نمونه داده:**

| id | alert_id | triggered_at | trigger_value | message | delivered | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| alh_72e7418ad5044cbd80bc297b | alr_035b5d82ba7143759a9a776c | 2026-08-07 07:05:19.276106 | 28242.0 | کاج price reached 28242.0 (thr… | True | 2026-08-07 | 1405-05-16 |
| alh_0f1ca10f2e564d09872ab078 | alr_035b5d82ba7143759a9a776c | 2026-08-07 07:07:19.422440 | 28242.0 | کاج price reached 28242.0 (thr… | True | 2026-08-07 | 1405-05-16 |

</details>

<details>
<summary><code>alerts</code> — ~2 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/alert.py` → `AlertModel`
- سرویس: `services/stock_assistant_service.py` (16)، `services/unified_assistant_service.py` (12)، `services/monitoring_service.py` (10)، `services/alert_service.py` (8)
- API: `apps/api/app.py` (5)، `apps/api/router.py` (4)، `apps/api/endpoints/assistant.py` (2)، `apps/scheduler/app.py` (2)
- جاب: `jobs/definitions/alert_jobs.py` (9)، `jobs/definitions/sync_jobs.py` (1)
- ریپازیتوری: `repositories/alert_repository.py` (1)
- اسکریپت: `scripts/_tmp_api_test4.py` (3)، `scripts/audit_data_access.py` (2)، `scripts/_tmp_api_test3.py` (2)، `scripts/import_shareholders.py` (1)
- تست: `tests/unit/test_rate_limit_middleware.py` (7)، `tests/unit/services/test_alert_service.py` (7)، `tests/unit/test_security_middleware.py` (6)، `tests/unit/test_cron_alerts_real.py` (5)
- سایر: `domain/alerts/__init__.py` (3)، `core/config/__init__.py` (1)، `domain/alerts/rules.py` (1)، `monitoring/__init__.py` (1)

**نمونه داده:**

| id | instrument_id | symbol | alert_type | condition | channels | enabled | triggered_count | last_triggered | description | updated_at | created_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| alr_035b5d82ba7143759a9a776c | کاج | کاج | price_above | {"threshold": 1000, "operator"… | ["email", "console"] | True | 1594 | 2026-08-10 18:39:21.978324 |  | NULL | 2026-07-28 13:32:22.564870 | … |
| alr_e85cb1af402e48f889221758 |  | ????? | price_above | {"threshold": 5000, "operator"… | ["console"] | True | 0 | NULL | test | NULL | 2026-08-09 20:55:57.948030 | … |

</details>

<details>
<summary><code>candlesticks_deprecated</code> — جدول خالی است (10 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو

**مراجع کد:**
- مدل: _بدون مدل ORM_
- مرجع کد فعال: _هیچ_

</details>

<details>
<summary><code>commodity_certificates</code> — ~125,256 ردیف، 8 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityCertificateModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/dedup_and_constrain.py` (1)، `scripts/dedup_batched.py` (1)

**نمونه داده:**

| id | symbol | name | price | volume | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 4959 | PACR-BI6070B-00 | قیر 6070 | 5200.0 | 424 | 2026-07-13 02:46:52.449560+00:… | 2026-07-13 | 1405-04-22 |
| 5690 | JRC-BI85100B-00 | قیر 85100 | 5750.0 | 320 | 2026-07-13 02:46:52.449560+00:… | 2026-07-13 | 1405-04-22 |

</details>

<details>
<summary><code>commodity_funds</code> — ~186 ردیف، 8 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityFundModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| id | symbol | name | nav | price | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 1 | عیار | صندوق طلای عیار مفید | NULL | 501990.0 | 2026-07-14 14:58:08.847483+00:… | 2026-07-14 | 1405-04-23 |
| 2 | نقران | صندوق س.کالای کهربا1 | NULL | 10555.0 | 2026-07-14 14:58:08.851409+00:… | 2026-07-14 | 1405-04-23 |

</details>

<details>
<summary><code>commodity_futures</code> — ~60 ردیف، 11 ستون ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون منبع تاریخ `expiry_date` در نمونه NULL دارد
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityFuturesModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| id | symbol | name | expiry_date | price_last | price_close | trade_count | trade_volume | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SILKH05 | قرارداد آتی گواهی سپرده نقره ت… | NULL | 6681103.0 | 6681103.0 | 484 | 11170 | 2026-07-13 00:00:57.287864+00:… | NULL | NULL |
| 2 | GB19MO05 | قرارداد آتی شمش طلای خام 995 ت… | NULL | 346295354.0 | 346295354.0 | 456 | 3958 | 2026-07-13 00:00:57.287864+00:… | NULL | NULL |

</details>

<details>
<summary><code>commodity_options</code> — ~476 ردیف، 11 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityOptionModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| id | symbol | name | underlying | strike_price | expiry_date | option_type | price_last | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TLDY05C90 | قرارداد اختیار معامله خرید واح… | LG ETC | 900000.0 | 2027-01-17 | call | 583001.0 | 2026-07-14 15:10:37.650343+00:… | 2027-01-17 | 1405-10-27 |
| 2 | TLDY05P90 | قرارداد اختیار معامله فروش واح… | LG ETC | 900000.0 | 2027-01-17 | put | NULL | 2026-07-14 15:10:37.703492+00:… | 2027-01-17 | 1405-10-27 |

</details>

<details>
<summary><code>commodity_prices</code> — ~42 ردیف، 9 ستون ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- نسخه قدیمی است — جدول زنده `brsapi_commodity_prices` جایگزین آن است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityGlobalPriceModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)
- سایر: `brsapi/services/query_service.py` (1)

**نمونه داده:**

| symbol | time | name | price | change_value | change_pct | unit | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|
| XAUUSD | 2026-07-14 14:58:08.449514+00:… | انس طلا | 4083.67 | 84.27 | NULL | دلار | 2026-07-14 | 1405-04-23 |
| XAGUSD | 2026-07-14 14:58:08.487040+00:… | انس نقره | 59.32 | 1.74 | NULL | دلار | 2026-07-14 | 1405-04-23 |

</details>

<details>
<summary><code>commodity_trades</code> — ~320,005 ردیف، 12 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityTradeModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/dedup_and_constrain.py` (1)، `scripts/dedup_batched.py` (1)

**نمونه داده:**

| id | symbol | name | trade_date | price | volume | value | counter_party | created_at | updated_at | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20791 | PACB-BIPG6422B-00 | قیر PG6422 | NULL | 9600.0 | 1850 | 17760000.0 | نفت پاسارگاد\|باهنر | 2026-07-13 02:45:23.796153+00:… | NULL | 2026-07-13 | 1405-04-22 |
| 21479 | PACA-BIMC250B-00 | قیر MC250 | NULL | 12222.0 | 242 | 2957724.0 | نفت پاسارگاد\|باهنر | 2026-07-13 02:45:23.796153+00:… | NULL | 2026-07-13 | 1405-04-22 |

</details>

<details>
<summary><code>daily_history_deprecated</code> — ~88,961 ردیف، 17 ستون (نمایش 12 ستون از 17) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو

**مراجع کد:**
- مدل: _بدون مدل ORM_
- مرجع کد فعال: _هیچ_

**نمونه داده:**

| symbol_id | trade_date | trade_count | trade_volume | trade_value | price_min | price_max | price_yesterday | price_first | price_last | price_last_change | price_last_change_pct | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 48934567890123456 | 2023-04-16 | 0 | 0 | 0.0 | 0.0 | 0.0 | 7370.0 | 0.0 | 7380.0 | 0.0 | 0.0 | … |
| 2234567890123456 | 2023-03-25 | 2137 | 3222331 | 37290951110.0 | 11360.0 | 11800.0 | 11370.0 | 11600.0 | 11520.0 | 150.0 | 1.32 | … |

</details>

<details>
<summary><code>dual_date_columns</code> — ~117 ردیف، 4 ستون ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: _بدون مدل ORM_
- اسکریپت: `scripts/install_dual_dates.py` (6)، `scripts/fix_dual_date_gaps.py` (4)، `scripts/backfill_dual_dates.py` (2)، `scripts/analyze_db_issues.py` (1)
- تست: `tests/unit/test_dual_dates.py` (4)

**نمونه داده:**

| table_name | source_column | gregorian_date | shamsi_date |
|---|---|---|---|
| alerts | created_at | NULL | NULL |
| analysis_reports | report_date | NULL | NULL |

</details>

<details>
<summary><code>gold_currency_prices</code> — ~74,463 ردیف، 12 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/market_data.py` → `GoldCurrencyPriceModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/backfill_dual_dates_direct.py` (1)، `scripts/fix_dual_date_remaining.py` (1)، `scripts/populate_profiles.py` (1)

**نمونه داده:**

| symbol | time | name | name_en | sign | price | change_value | change_pct | unit | section | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AED | 2018-04-16 19:30:00+00:00 | AED | NULL | NULL | 14770.0 | -330.0 | -2.185430463576159 | unit | currency | 2018-04-17 | 1397-01-28 |
| AMD | 2018-04-16 19:30:00+00:00 | AMD | NULL | NULL | 140.0 | -950.0 | -87.1559633027523 | unit | currency | 2018-04-17 | 1397-01-28 |

</details>

<details>
<summary><code>indices</code> — ~4 ردیف، 8 ستون</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/market_data.py` → `IndexModel`
- سرویس: `services/market_service.py` (8)
- API: `apps/api/endpoints/market_watch.py` (5)، `apps/api/endpoints/market.py` (3)، `apps/api/endpoints/market_dashboard.py` (3)، `apps/api/router.py` (1)
- جاب: `jobs/definitions/sync_jobs.py` (2)، `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/_tmp_api_test.py` (2)، `scripts/_tmp_api_test2.py` (2)، `scripts/audit_data_access.py` (1)، `scripts/fix_dual_date_remaining.py` (1)
- سایر: `domain/indices/__init__.py` (3)، `ml/datasets/sampling.py` (3)، `ml/evaluation/stability.py` (3)، `ml/models/ensemble/blending.py` (3)

**نمونه داده:**

| id | name | value | change_value | change_pct | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 1 | شاخص کل | 4924683.63 | -42077.13 | NULL | 2026-07-14 14:41:36.860251+00:… | 2026-07-14 | 1405-04-23 |
| 2 | شاخص کل | 4924683.63 | -42077.13 | NULL | 2026-07-14 14:58:05.546302+00:… | 2026-07-14 | 1405-04-23 |

</details>

<details>
<summary><code>instruments</code> — ~499 ردیف، 26 ستون (نمایش 12 ستون از 26)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `iran_market_data/app/storage/models.py` → `Instrument`
- مدل: `models/instrument.py` → `InstrumentModel`
- سرویس: `services/screener_service.py` (14)، `services/market_service.py` (8)، `services/market_watch_helper.py` (8)، `services/unified_assistant_service.py` (7)
- API: `apps/api/endpoints/screener.py` (12)، `apps/api/endpoints/screener_v2.py` (10)، `apps/admin/dashboard.py` (4)، `apps/api/endpoints/backtests.py` (4)
- جاب: `jobs/definitions/housekeeping_jobs.py` (1)، `jobs/definitions/reference_jobs.py` (1)، `jobs/definitions/sync_jobs.py` (1)
- ریپازیتوری: `repositories/instrument_repository.py` (1)
- اسکریپت: `scripts/check_backfill_query.py` (10)، `scripts/check_symbol_match.py` (6)، `scripts/sync_symbol_details_all.py` (6)، `scripts/check_codal.py` (4)
- تست: `tests/unit/test_backend_api_edge_cases.py` (15)، `tests/unit/services/test_market_watch_helper.py` (15)، `tests/test_instrument_relations.py` (13)، `tests/unit/test_symbols_page_size.py` (9)
- سایر: `backtesting/universe/filters.py` (18)، `backtesting/engine/portfolio_simulator.py` (13)، `orchestration/signal_flow.py` (10)، `providers/reference/instrument_master/provider.py` (9)

**نمونه داده:**

| id | symbol | name | isin | market_type | asset_class | status | sector_code | group_code | sub_group_code | tick_size | lot_size | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1234567890123456 | خودرو | اوراق مشاركت ايران خودرو | IRB5IKCO8751 | stock | equity | active | خودرو و ساخت قطعات | 34 | 34 | 1.0 | 1 | … |
| 2234567890123456 | آبادا | توليد نيروي برق آبادان | IRO1NBAB0001 | stock | equity | active | عرضه برق، گاز، بخارو | 40 | 40 | 1.0 | 1 | … |

</details>

<details>
<summary><code>intraday_trades_deprecated</code> — ~9,135,020 ردیف، 9 ستون ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو

**مراجع کد:**
- مدل: _بدون مدل ORM_
- مرجع کد فعال: _هیچ_

**نمونه داده:**

| symbol_id | trade_date | seq_no | time | volume | price | is_canceled | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|
| 7234567890123456 | 2026-06-09 | 23887 | 10:33:36 | 35 | 146630.0 | False | 2026-06-09 | 1405-03-19 |
| 7234567890123456 | 2026-06-09 | 23888 | 10:34:10 | 70 | 146630.0 | False | 2026-06-09 | 1405-03-19 |

</details>

<details>
<summary><code>paper_equity_history</code> — ~3 ردیف، 9 ستون</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/paper_trading.py` → `PaperEquityModel`
- سرویس: `services/paper_trading_service.py` (1)
- جاب: `jobs/definitions/paper_trading_job.py` (1)

**نمونه داده:**

| id | date | equity | cash | open_value | realized_pnl | open_positions | total_closed | created_at |
|---|---|---|---|---|---|---|---|---|
| peq_356b13fddc714a279d351bbd | 2026-08-08 | 847461872.0 | 847461872.0 | 0.0 | -152538128.0 | 0 | 3027 | 2026-08-08 08:01:35.798715 |
| peq_898e38c7439641b8bbc24cbf | 2026-08-09 | 847475349.0 | 847461872.0 | 13477.0 | -152538128.0 | 1 | 3027 | 2026-08-09 21:00:49.570150 |

</details>

<details>
<summary><code>paper_signal_snapshots</code> — ~3,025 ردیف، 25 ستون (نمایش 12 ستون از 25)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/paper_trading.py` → `PaperSignalSnapshotModel`
- سرویس: `services/paper_trading_service.py` (1)
- جاب: `jobs/definitions/paper_trading_job.py` (1)
- اسکریپت: `scripts/_check_signal_health.py` (2)

**نمونه داده:**

| id | batch_id | generated_at | symbol | name | market | direction | timeframe | source | entry_zone | stop_loss | targets | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| psnap_5f513f26f43447cdab935e44 | backfill | 2026-07-22 02:38:56.927338 | ونفت | NULL | stock | buy | daily | snapshot_analysis | NULL | NULL | NULL | … |
| psnap_b4788f2d8e4f4d8a939febc8 | backfill | 2026-07-22 02:38:56.941351 | شاراک | NULL | stock | buy | daily | snapshot_analysis | NULL | NULL | NULL | … |

</details>

<details>
<summary><code>paper_trades</code> — ~3,025 ردیف، 26 ستون (نمایش 12 ستون از 26)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/paper_trading.py` → `PaperTradeModel`
- سرویس: `services/paper_trading_service.py` (1)
- جاب: `jobs/definitions/paper_trading_job.py` (1)

**نمونه داده:**

| id | signal_snapshot_id | symbol | name | market | timeframe | source | confidence | score | entry_price | stop_loss_price | target1_price | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| ptrade_a66d355fa13c4780bbd7547… | psnap_5f513f26f43447cdab935e44 | ونفت | NULL | stock | daily | snapshot_analysis | 0.3 | NULL | 9290.0 | NULL | NULL | … |
| ptrade_3e3b3845f4e54b0fbf7f547… | psnap_b4788f2d8e4f4d8a939febc8 | شاراک | NULL | stock | daily | snapshot_analysis | 0.3 | NULL | 17610.0 | NULL | NULL | … |

</details>

<details>
<summary><code>symbol_relations</code> — جدول خالی است (13 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/symbol_relation.py` → `SymbolRelationModel`
- سرویس: `services/mass_scanner_service.py` (1)
- سایر: `backtesting/relations/symbol_graph.py` (1)

</details>

<details>
<summary><code>symbol_snapshots_deprecated</code> — جدول خالی است (28 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو

**مراجع کد:**
- مدل: _بدون مدل ORM_
- مرجع کد فعال: _هیچ_

</details>

<details>
<summary><code>markets</code> — جدول خالی است (14 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- هیچ SQL فعالی ندارد — مراجع کد صرفاً از نام ماژول/پکیج هستند

**مراجع کد:**
- مدل: `models/market.py` → `MarketModel`
- سرویس: `services/quant_signal_orchestrator.py` (9)، `services/multi_market_signal_engine.py` (6)، `services/unified_assistant_service.py` (5)، `services/auto_retrain_pipeline.py` (3)
- API: `apps/api/endpoints/multi_market_signals.py` (8)، `apps/api/endpoints/tabdeal.py` (6)، `apps/api/endpoints/signal_insights.py` (2)، `apps/api/app.py` (1)
- اسکریپت: `scripts/audit_data_access.py` (1)
- تست: `tests/benchmark_signal_quality.py` (16)، `tests/unit/services/test_quant_signal_orchestrator.py` (15)، `tests/e2e/test_orchestrator_pipeline.py` (3)، `tests/test_all_pages.py` (2)
- سایر: `backtesting/engine/replay_engine.py` (5)، `backtesting/engine/simulation_engine.py` (4)، `backtesting/relations/market_graph.py` (4)، `backtesting/hybrid/hybrid_simulator.py` (3)

</details>

<details>
<summary><code>portfolio_positions</code> — جدول خالی است (14 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/portfolio.py` → `PortfolioPositionModel`
- سرویس: `services/ensemble_engine.py` (2)
- API: `apps/api/endpoints/tables.py` (1)

</details>

<details>
<summary><code>portfolios</code> — جدول خالی است (11 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/portfolio.py` → `PortfolioModel`
- سرویس: `services/live_risk_monitor.py` (4)، `services/unified_assistant_service.py` (3)، `services/portfolio_service.py` (1)
- API: `apps/api/router.py` (3)، `apps/api/endpoints/portfolios.py` (2)، `apps/admin/dashboard.py` (1)، `apps/api/middleware.py` (1)
- ریپازیتوری: `repositories/portfolio_repository.py` (1)
- اسکریپت: `scripts/_tmp_api_test4.py` (2)
- تست: `tests/unit/test_security_middleware.py` (7)، `tests/unit/services/test_portfolio_service.py` (4)
- سایر: `backtesting/strategies/registry.py` (8)، `backtesting/strategies/portfolios/__init__.py` (5)، `backtesting/analytics/attribution.py` (2)، `domain/options/var_calculator.py` (2)

</details>

<details>
<summary><code>recommendations</code> — جدول خالی است (18 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/recommendation.py` → `RecommendationModel`
- سرویس: `services/market_health_index.py` (8)، `services/codal_analysis/audit_control_testing.py` (4)، `services/chat/learning_engine.py` (1)، `services/chat/suggestion_engine.py` (1)
- API: `apps/api/endpoints/analysis.py` (6)، `apps/api/router.py` (4)، `apps/api/endpoints/recommendations.py` (4)، `apps/admin/dashboard.py` (2)
- اسکریپت: `scripts/audit_data_access.py` (2)، `scripts/_tmp_api_test.py` (2)، `scripts/_tmp_api_test2.py` (2)، `scripts/_tmp_api_test3.py` (2)
- تست: `tests/comprehensive/test_all.py` (6)، `tests/unit/domain/test_recommendation_rules.py` (5)، `tests/debug_api.py` (2)، `tests/test_all_pages.py` (2)
- سایر: `domain/recommendations/__init__.py` (4)، `core/security/permissions.py` (2)، `reports/builders/recommendation_report_builder.py` (2)، `backtesting/optimization/walk_forward.py` (1)

</details>

<details>
<summary><code>saved_filters</code> — جدول خالی است (17 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/saved_filter.py` → `SavedFilter`
- API: `apps/api/router.py` (1)

</details>

<details>
<summary><code>symbols</code> — ~511 ردیف، 19 ستون (نمایش 12 ستون از 19)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/market_data.py` → `SymbolModel`
- سرویس: `services/chat/chat_engine.py` (41)، `services/mass_scanner_service.py` (31)، `services/chat/comparison_engine.py` (30)، `services/realtime_service.py` (29)
- API: `apps/api/endpoints/brsapi.py` (65)، `apps/api/endpoints/backtests.py` (60)، `apps/api/endpoints/ml.py` (31)، `apps/api/endpoints/funds.py` (23)
- جاب: `jobs/market_data_jobs.py` (15)، `jobs/definitions/market_data_jobs.py` (11)، `jobs/definitions/sync_jobs.py` (6)، `jobs/definitions/feature_store_jobs.py` (5)
- ریپازیتوری: `repositories/news_repository.py` (13)، `repositories/backtest_repository.py` (8)، `repositories/generated_strategy_repository.py` (2)
- اسکریپت: `scripts/brsapi_full_update.py` (29)، `scripts/build_feature_store.py` (28)، `scripts/sync_all_tables.py` (27)، `scripts/sync_symbol_details_all.py` (27)
- تست: `tests/unit/test_ml_model_preload.py` (35)، `tests/comprehensive/test_all.py` (29)، `tests/unit/scripts/test_build_screener_scores.py` (23)، `tests/unit/services/test_symbol_catalog.py` (20)
- سایر: `brsapi/jobs/registry.py` (99)، `brsapi/services/sync_service.py` (40)، `brsapi/services/history_fetch_service.py` (22)، `ml/model_loader.py` (16)

**نمونه داده:**

| id | symbol | name | isin | market_type | asset_class | industry | industry_id | total_shares | base_volume | eps | pe | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1234567890123456 | خودرو | اوراق مشاركت ايران خودرو | IRB5IKCO8751 | stock | equity | خودرو و ساخت قطعات | NULL | 0 | 1 | NULL | NULL | … |
| 2234567890123456 | آبادا | توليد نيروي برق آبادان | IRO1NBAB0001 | stock | equity | عرضه برق، گاز، بخاروآب گرم | NULL | 0 | 1 | NULL | NULL | … |

</details>

<details>
<summary><code>users</code> — ~>0 ردیف، 21 ستون (نمایش 12 ستون از 21) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید

**مراجع کد:**
- مدل: `models/user.py` → `UserModel`
- سرویس: `services/user_service.py` (3)، `services/chat/suggestion_engine.py` (2)، `services/codal_analysis/audit_fraud.py` (1)، `services/smart_money/confidence.py` (1)
- API: `apps/api/endpoints/auth.py` (3)، `apps/admin/dashboard.py` (2)، `apps/api/endpoints/symbols.py` (2)، `apps/api/endpoints/tables.py` (2)
- تست: `tests/unit/test_rbac.py` (5)، `tests/unit/test_mfa_integration.py` (3)، `tests/unit/test_confirmed_runtime_fixes.py` (1)، `tests/unit/test_deep_confirmed_fixes.py` (1)
- سایر: `postgresql_client.py` (3)، `core/security/permissions.py` (2)، `brsapi/rate_limiter.py` (1)، `brsapi/jobs/registry.py` (1)

**نمونه داده:**

| id | username | email | hashed_password | full_name | phone | roles | is_active | is_verified | last_login | refresh_token | metadata | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| usr_87358d25da2344ad9a1fa156 | admin_test_1786376238 | admin_test_1786376238@example.… | 100000$423189da84c2d91bcd64bca… | Admin Test |  | admin | True | False | 2026-08-10 15:43:25.592089 | eyJhbGciOiJIUzI1NiIsInR5cCI6Ik… | NULL | … |
| usr_dee9fdd42ac8420e862f9aea | testadmin | testadmin@test.com | 100000$1b8f8c5bbc1a96781c0b722… | Test Admin |  | admin | True | True | 2026-08-06 18:15:04.807321 | eyJhbGciOiJIUzI1NiIsInR5cCI6Ik… | NULL | … |

</details>

<details>
<summary><code>account_mappings</code> — جدول خالی است (14 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `AccountMapping`

</details>

<details>
<summary><code>analysis_reports</code> — جدول خالی است (22 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `AnalysisReport`

</details>

<details>
<summary><code>brsapi_codal_announcements</code> — ~5,053 ردیف، 24 ستون (نمایش 12 ستون از 24)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/codal.py` → `CodalAnnouncementModel`
- سرویس: `services/codal_attachment_service.py` (2)
- API: `apps/api/endpoints/brsapi.py` (3)، `apps/api/endpoints/codal.py` (1)
- جاب: `jobs/definitions/sync_jobs.py` (1)
- اسکریپت: `scripts/fix_schema_gap.py` (6)، `scripts/backfill_dates.py` (1)، `scripts/backfill_ins_id.py` (1)، `scripts/batch_codal_sync.py` (1)
- تست: `tests/test_codal_sync_3x.py` (1)، `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | company_name | title | code | date_title | date_send | time_send | date_publish | time_publish | link | link_pdf | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 7524 | لبن | صنایع دامپروری و لبنی رضوی | آگهی دعوت به مجمع عمومی عادی ب… | ن-۵۴ | NULL | ۱۴۰۵/۰۵/۱۶ | ۰۵:۰۳:۱۶ | ۱۴۰۵/۰۵/۱۶ | ۰۵:۰۳:۱۶ | https://codal.ir/Reports/Decis… | https://codal.ir/DownloadFile.… | … |
| 7525 | داسوه | داروسازی اسوه | اطلاعات و صورت‌های مالی میاندو… | ن-۱۰ | ۱۴۰۵/۰۳/۳۱ | ۱۴۰۵/۰۵/۱۵ | ۲۲:۴۸:۳۷ | ۱۴۰۵/۰۵/۱۵ | ۲۲:۴۸:۳۷ | https://codal.ir/Reports/Decis… | https://codal.ir/DownloadFile.… | … |

</details>

<details>
<summary><code>brsapi_codal_attachments</code> — ~10,336 ردیف، 18 ستون (نمایش 12 ستون از 18)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/codal.py` → `CodalAttachmentModel`
- سرویس: `services/codal_attachment_service.py` (6)
- اسکریپت: `scripts/fix_schema_gap.py` (1)

**نمونه داده:**

| id | announcement_id | symbol | code | attachment_type | source_url | storage_type | storage_path | file_size | mime_type | status | error_message | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 6 | 2 | فیروزا |  | html | https://codal.ir/Reports/Decis… | local | NULL | NULL | NULL | downloading |  | … |
| 4 | 2 | فیروزا |  | pdf | https://codal.ir/DownloadFile.… | local | NULL | NULL | NULL | downloading |  | … |

</details>

<details>
<summary><code>codal_announcements_deprecated</code> — جدول خالی است (17 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو

**مراجع کد:**
- مدل: _بدون مدل ORM_
- مرجع کد فعال: _هیچ_

</details>

<details>
<summary><code>codal_audit_summary</code> — ~451 ردیف، 33 ستون (نمایش 12 ستون از 33)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/codal.py` → `CodalAuditSummaryModel`
- API: `apps/api/endpoints/codal_audit.py` (7)، `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/codal.py` (1)
- اسکریپت: `scripts/batch_audit_all_symbols.py` (9)، `scripts/codal_deep.py` (4)، `scripts/extract_codal_financials.py` (4)، `scripts/codal_audit.py` (3)

**نمونه داده:**

| id | symbol | company_name | report_type | report_date | revenue | net_profit | total_assets | total_equity | eps | roe | roa | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 6 | رمپنا | NULL | ن-۱۰ | ۱۴۰۵ | 15099257000.0 | NULL | NULL | 8561.0 | NULL | 0.0 | NULL | … |
| 7 | خساپا | NULL | ن-۱۰ | ۱۴۰۵ | 4893360.0 | NULL | NULL | 110.0 | NULL | 0.0 | NULL | … |

</details>

<details>
<summary><code>codal_financial_statements</code> — ~451 ردیف، 16 ستون (نمایش 12 ستون از 16)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/codal_financial.py` → `CodalFinancialStatementModel`
- سرویس: `services/codal_download_service.py` (2)
- API: `apps/api/endpoints/brsapi.py` (1)، `apps/api/endpoints/codal.py` (1)
- اسکریپت: `scripts/import_codal_excel.py` (8)، `scripts/codal_deep.py` (4)، `scripts/batch_audit_all_symbols.py` (3)، `scripts/codal_audit.py` (3)

**نمونه داده:**

| id | symbol | report_type | report_date | filename | file_path | title | parsed_data | table_count | row_count | import_batch | imported_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| cfs_c820bbccb8d81814 | وبملت | ن-۱۰ | ۱۴۰۵ | NULL | NULL | Batch audit - وبملت | {'dupont': {'roe': 0.0, 'roe_d… | 14 | 0 | batch_1784534137 | 2026-07-20 11:25:37.132687 | … |
| cfs_28d023770e385f6a | وبانک | ن-۱۰ | ۱۴۰۵ | NULL | NULL | Batch audit - وبانک | {'dupont': {'roe': 0.0799, 'ro… | 11 | 0 | batch_1784534138 | 2026-07-20 11:25:38.021954 | … |

</details>

<details>
<summary><code>codal_reports</code> — ~226,818 ردیف، 17 ستون (نمایش 12 ستون از 17)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/codal.py` → `CodalReportModel`
- API: `apps/admin/dashboard.py` (2)، `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/codal.py` (2)، `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/check_codal.py` (8)، `scripts/check_codal_data.py` (7)، `scripts/check_symbol_match.py` (6)، `scripts/codal_audit.py` (5)
- سایر: `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | instrument_id | symbol | company_name | isin | report_type | fiscal_year | period | audit_status | publish_date | attachment_url | summary | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| c2d331b0846832611944a6eb510d4b… | البرز | البرز | بیمه البرز | NULL | ن-۶۷ | NULL | NULL | NULL | ۱۳۹۴/۱۲/۰۵ | https://codal.ir/Reports/Attac… | آگهی ثبت افزایش سرمایه | … |
| 256ba5524a435f143adcd8064d8f01… | انرژی | انرژی | بورس انرژی | NULL |  | NULL | NULL | NULL | ۱۳۹۴/۰۵/۲۶ | https://codal.ir/Reports/Attac… | آگهی ثبت تغیرات (به پیوست) | … |

</details>

<details>
<summary><code>corporate_actions</code> — جدول خالی است (11 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/option.py` → `CorporateActionModel`
- API: `apps/api/endpoints/codal.py` (1)
- اسکریپت: `scripts/fix_schema_gap.py` (1)
- سایر: `providers/capabilities/matrix.py` (1)

</details>

<details>
<summary><code>data_lineage</code> — جدول خالی است (13 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `DataLineage`

</details>

<details>
<summary><code>dim_account</code> — جدول خالی است (10 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `DimAccount`
- سرویس: `services/codal_analysis/point_in_time.py` (1)

</details>

<details>
<summary><code>dim_company</code> — جدول خالی است (12 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `DimCompany`

</details>

<details>
<summary><code>dim_date</code> — جدول خالی است (10 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `DimDate`
- سرویس: `services/codal_analysis/point_in_time.py` (1)

</details>

<details>
<summary><code>dim_document</code> — جدول خالی است (15 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `DimDocument`

</details>

<details>
<summary><code>dim_report_type</code> — جدول خالی است (7 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `DimReportType`

</details>

<details>
<summary><code>fact_financials</code> — جدول خالی است (16 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `FactFinancials`
- سرویس: `services/codal_analysis/point_in_time.py` (1)

</details>

<details>
<summary><code>fact_growth</code> — جدول خالی است (11 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `FactGrowth`

</details>

<details>
<summary><code>fact_quality_signals</code> — جدول خالی است (11 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `FactQualitySignals`

</details>

<details>
<summary><code>fact_ratios</code> — جدول خالی است (14 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `FactRatios`

</details>

<details>
<summary><code>fact_text_analytics</code> — جدول خالی است (13 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود

**مراجع کد:**
- مدل: `models/codal_analysis.py` → `FactTextAnalytics`

</details>

<details>
<summary><code>import_audit_log</code> — جدول خالی است (9 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `bulk_importer/models.py` → `ImportAuditLog`
- سایر: `bulk_importer/models.py` (1)

</details>

<details>
<summary><code>import_document_files</code> — ~95,418 ردیف، 18 ستون (نمایش 12 ستون از 18) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `bulk_importer/models.py` → `DocumentFile`
- سایر: `bulk_importer/persistence.py` (4)، `bulk_importer/models.py` (3)

**نمونه داده:**

| id | issuer_symbol | report_type | report_date_jalali | file_name | file_path | file_size_bytes | sha256 | detected_format | file_status | error_message | parsed_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 23644 | خکاوه | n30 | 1403-11-06 | خکاوه_ن-۳۰_۱۴۰۳_۱۱_۰۶.xlsx | C:\Users\Iran\Desktop\temce\da… | 80770 | fast:C:\Users\Iran\Desktop\tem… | html | saved | NULL | 2026-07-20 03:20:21.493608 | … |
| 27042 | دماوند | n30 | 1401-09-07 | دماوند_ن-۳۰_۱۴۰۱_۰۹_۰۷.xlsx | C:\Users\Iran\Desktop\temce\da… | 61188 | fast:C:\Users\Iran\Desktop\tem… | html | saved | NULL | 2026-07-20 03:20:43.105116 | … |

</details>

<details>
<summary><code>import_document_tables</code> — ~524,564 ردیف، 13 ستون (نمایش 12 ستون از 13) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `bulk_importer/models.py` → `DocumentTable`
- سایر: `bulk_importer/models.py` (1)، `bulk_importer/persistence.py` (1)

**نمونه داده:**

| id | document_file_id | table_name | table_index | logical_section | extraction_status | row_count | column_count | raw_json | created_at | updated_at | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 3925 | 634 | NULL | 4 | NULL | success | 53 | 5 | {'rows': [['حسابرسی نشده', 'حس… | 2026-07-20 03:17:47.760571 | NULL | 2026-07-20 | … |
| 7297 | 1061 | NULL | 2 | balance_sheet | success | 30 | 8 | {'rows': [['دارایی\u200cها', N… | 2026-07-20 03:18:02.889345 | NULL | 2026-07-20 | … |

</details>

<details>
<summary><code>macro_indicators</code> — جدول خالی است (15 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/macro.py` → `MacroIndicatorModel`
- سرویس: `services/real_return_calculator.py` (3)
- API: `apps/admin/dashboard.py` (1)، `apps/api/endpoints/tables.py` (1)

</details>

<details>
<summary><code>news_articles</code> — ~71 ردیف، 16 ستون (نمایش 12 ستون از 16)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/news.py` → `NewsArticleModel`
- سرویس: `services/iran_fear_greed_index.py` (2)، `services/gap_prediction.py` (1)
- API: `apps/admin/dashboard.py` (2)، `apps/api/endpoints/news.py` (1)، `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/fix_remaining_categories.py` (5)، `scripts/fix_schema_gap.py` (5)، `scripts/fix_news_categories.py` (4)، `scripts/fix_categories.py` (3)
- تست: `tests/unit/test_critical_runtime_fixes.py` (1)
- سایر: `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | title | summary | content | source | url | category | symbols | published_at | sentiment | sentiment_score | data_source | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| news_45e4a48fdb32482096582336 | مأموریت تصمیم‌ساز در حکمرانی ا… | چهره‌ها با مهدی طحانی | چهره‌ها با مهدی طحانی | fardaye_latest | https://www.fardayeeghtesad.co… | economic | NULL | 2026-08-06T14:14:27+00:00 | neutral | 0.0 | rss | … |
| news_731061a1a1fb41858d91a5dc | جشن هرمز؛ شکست مرزها در ۷ بازا… | بازارنگر چهارشنبه ۱۴ مرداد ۱۴۰… | بازارنگر چهارشنبه ۱۴ مرداد ۱۴۰… | fardaye_latest | https://www.fardayeeghtesad.co… | market | NULL | 2026-08-05T10:12:48+00:00 | neutral | 0.0 | rss | … |

</details>

### لیست نمادها

همه **511 نماد** جدول مرجع `symbols` (مرجع `symbol`/`ins_id` برای کل سکو).
توزیع بر اساس نوع بازار: stock 499، ETF 12.

<details>
<summary>نمایش لیست کامل (511 نماد)</summary>

| symbol | name | market_type | asset_class | industry | isin |
|---|---|---|---|---|---|
| آبادا | توليد نيروي برق آبادان | stock | equity | عرضه برق، گاز، بخاروآب گرم | IRO1NBAB0001 |
| آپ | آسان پرداخت پرشين | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1APPE0001 |
| اپال | فرآوري معدني اپال كاني پارس | stock | equity | استخراج کانه هاي فلزي | IRO1OPAL0001 |
| اتكام | بيمه اتكايي امين | stock | equity | بيمه وصندوق بازنشستگي به جزتام… | IRO1ETKA0001 |
| اخابر | مخابرات ايران | stock | equity | مخابرات | IRO1MKBT0001 |
| اردستان | سيمان اردستان | stock | equity | سيمان، آهك و گچ | IRO1ARDS0001 |
| اروند | پتروشيمي اروند | stock | equity | محصولات شيميايي | IRO1RVND0001 |
| آسيا | بيمه آسيا | stock | equity | بيمه وصندوق بازنشستگي به جزتام… | IRO1ASIA0001 |
| اسياتك | انتقال داده هاي آسياتك | stock | equity | اطلاعات و ارتباطات | IRO1ASTC0001 |
| افران | صندوق افران | ETF | commodity | NULL | NULL |
| افق | فروشگاههاي زنجيره اي افق كوروش | stock | equity | خرده فروشي،باستثناي وسايل نقلي… | IRO1OFOG0001 |
| اكالا | كارگزاران بورس كالاي ايران | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1BKLA0001 |
| اكتيو | پديده شيمي قرن | stock | equity | محصولات شيميايي | IRO1ACTV0001 |
| آكنتور | كنتورسازي‌ايران‌ | stock | equity | ابزارپزشکي، اپتيکي و اندازه‌گي… | IRO1CONT0001 |
| البرز | بيمه البرز | stock | equity | بيمه وصندوق بازنشستگي به جزتام… | IRO1BALB0001 |
| آلومينا | آلوميناي ايران | stock | equity | فلزات اساسي | IRO1ALMN0001 |
| اميد | تامين سرمايه اميد | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1OMID0001 |
| امين | تامين سرمايه امين | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1TSAN0001 |
| انرژي1 | نهادهاي مالي بورس انرژي | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1BENA0001 |
| انرژي2 | فعالان بورس انرژي | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1BENB0001 |
| انرژي3 | سايراشخاص بورس انرژي | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1BENC0001 |
| اهرم | صندوق اهرم | ETF | commodity | NULL | NULL |
| آوند | صندوق آوند | ETF | commodity | NULL | NULL |
| باختر | كابل‌ باختر | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1BAKH0001 |
| بالبر | كابل‌ البرز | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1KALZ0001 |
| بايكا | كابلسازي‌ايران‌ | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1KBLI0001 |
| بترانس | ايران‌ ترانسفو | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1TRNS0001 |
| بتك | كابلسازي‌ تك‌ | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1KTAK0001 |
| بجهرم | توسعه مولد نيروگاهي جهرم | stock | equity | عرضه برق، گاز، بخاروآب گرم | IRO1JHRM0001 |
| برانسفو | ترانسفورماتور توزيع زنگان | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1TTZC0001 |
| بركت | گروه دارويي بركت | stock | equity | مواد و محصولات دارويي | IRO1BRKT0001 |
| بسويچ | پارس‌سويچ‌ | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1SWIC0001 |
| بشهاب | لامپ‌ پارس‌ شهاب‌ | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1LAPS0001 |
| بفجر | فجر انرژي خليج فارس | stock | equity | عرضه برق، گاز، بخاروآب گرم | IRO1BFJR0001 |
| بكاب | صنايع‌جوشكاب‌يزد | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1JOSH0001 |
| بكام | كارخانجات توليدي شهيد قندي | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1KGND0001 |
| بموتو | موتوژن‌ | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1MOTJ0001 |
| بنيرو | نيروترانس‌ | stock | equity | ماشين آلات و دستگاه‌هاي برقي | IRO1NIRO0001 |
| بورس | بورس اوراق بهادار تهران | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1BORS0001 |
| بوعلي | پتروشيمي بوعلي سينا | stock | equity | محصولات شيميايي | IRO1BONA0001 |
| پارتا | مجتمع‌صنعتي‌آرتاويل‌تاير | stock | equity | لاستيك و پلاستيك | IRO1ARTA0001 |
| پارس | پتروشيمي پارس | stock | equity | محصولات شيميايي | IRO1PARS0001 |
| پارسان | گسترش نفت و گاز پارسيان | stock | equity | محصولات شيميايي | IRO1PASN0001 |
| پارسيان | بيمه پارسيان | stock | equity | بيمه وصندوق بازنشستگي به جزتام… | IRO1IPAR0001 |
| پاسا | ايران‌ياساتايرورابر | stock | equity | لاستيك و پلاستيك | IRO1YASA0001 |
| پاكشو | گروه صنعتي پاكشو | stock | equity | محصولات شيميايي | IRO1PASH0001 |
| پتاير | ايران‌ تاير | stock | equity | لاستيك و پلاستيك | IRO1TAIR0001 |
| پترول | گ.س.وت.ص.پتروشيمي خليج فارس | stock | equity | محصولات شيميايي | IRO1IPTR0001 |
| پخش اول | گلپخش اول | stock | equity | خرده فروشي،باستثناي وسايل نقلي… | IRO1GOLP0001 |
| پدرخش | درخشان‌ تهران‌ | stock | equity | لاستيك و پلاستيك | IRO1DRKH0001 |
| پدنا | توليدي‌لاستيك‌دنا | stock | equity | لاستيك و پلاستيك | IRO1DENA0001 |
| پرداخت | به پرداخت ملت | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1PRKT0001 |
| پرديس | سرمايه گذاري پرديس | stock | equity | سرمايه گذاريها | IRO1AYEG0001 |
| پرشيا | توسعه صنعت نفت و گاز پرشيا | stock | equity | استخراج نفت گاز و خدمات جنبي ج… | IRO1PERS0001 |
| پسهند | صنايع‌ لاستيكي‌ سهند | stock | equity | لاستيك و پلاستيك | IRO1SHND0001 |
| پشاهن | پلاستيك‌ شاهين‌ | stock | equity | لاستيك و پلاستيك | IRO1SHIN0001 |
| پكرمان | گروه‌ صنعتي‌ بارز | stock | equity | لاستيك و پلاستيك | IRO1BARZ0001 |
| پكوير | كوير تاير | stock | equity | لاستيك و پلاستيك | IRO1KVRZ0001 |
| پلاست | پلاستيران‌ | stock | equity | لاستيك و پلاستيك | IRO1PLST0001 |
| پلاسك | پلاسكوكار | stock | equity | لاستيك و پلاستيك | IRO1PLKK0001 |
| پلوله | گازلوله‌ | stock | equity | لاستيك و پلاستيك | IRO1GAZL0001 |
| پيزد | مجتمع‌صنايع‌لاستيك‌يزد | stock | equity | ماشين آلات و تجهيزات | IRO1LYZD0001 |
| تاپيكو | س. نفت و گاز و پتروشيمي تأمين | stock | equity | محصولات شيميايي | IRO1PTAP0001 |
| تاصيكو | سرمايه گذاري صدرتامين | stock | equity | استخراج کانه هاي فلزي | IRO1SADR0001 |
| تايرا | تراكتورسازي‌ايران‌ | stock | equity | ماشين آلات و تجهيزات | IRO1TRIR0001 |
| تپكو | توليدتجهيزات‌سنگين‌هپكو | stock | equity | ماشين آلات و تجهيزات | IRO1HPKO0001 |
| تپمپي | پمپ‌ سازي‌ ايران‌ | stock | equity | ماشين آلات و تجهيزات | IRO1PIRN0001 |
| تدبير | گروه سرمايه گذاري تدبير | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1TDBR0001 |
| تراك | ماشين‌آلات صنعتي تراكتورسازي‌ | stock | equity | ماشين آلات و تجهيزات | IRO1MOZI0001 |
| تفيرو | فيروزا | stock | equity | ماشين آلات و تجهيزات | IRO1FROZ0001 |
| تكشا | گسترش‌صنايع‌وخدمات‌كشاورزي‌ | stock | equity | ماشين آلات و تجهيزات | IRO1GSKE0001 |
| تكمبا | كمباين‌ سازي‌ ايران‌ | stock | equity | ماشين آلات و تجهيزات | IRO1COMB0001 |
| تكنو | تكنوتار | stock | equity | ماشين آلات و تجهيزات | IRO1TKNO0001 |
| تمحركه | ماشين‌سازي‌نيرومحركه‌ | stock | equity | ماشين آلات و تجهيزات | IRO1MNMH0001 |
| تمدن | تامين سرمايه تمدن | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1TMDN0001 |
| تملت | تامين سرمايه بانك ملت | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1TMLT0001 |
| تنوين | تامين سرمايه نوين | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1TNOV0001 |
| تيپيكو | سرمايه گذاري دارويي تامين | stock | equity | مواد و محصولات دارويي | IRO1DTIP0001 |
| ثاباد | توريستي ورفاهي آبادگران ايران | stock | equity | انبوه سازي، املاك و مستغلات | IRO1ABAD0001 |
| ثاخت | بين‌المللي‌توسعه‌ساختمان | stock | equity | انبوه سازي، املاك و مستغلات | IRO1BSTE0001 |
| ثاژن | سخت‌ آژند | stock | equity | انبوه سازي، املاك و مستغلات | IRO1SAJN0001 |
| ثاصفا | ساختمان‌ اصفهان‌ | stock | equity | انبوه سازي، املاك و مستغلات | IRO1SESF0001 |
| ثامان | سامان‌ گستراصفهان‌ | stock | equity | انبوه سازي، املاك و مستغلات | IRO1SGOS0001 |
| ثاميد | توسعه و عمران اميد | stock | equity | انبوه سازي، املاك و مستغلات | IRO1TOOM0001 |
| ثبهساز | بهساز كاشانه تهران | stock | equity | انبوه سازي، املاك و مستغلات | IRO1BEKA0001 |
| ثشاهد | سرمايه‌ گذاري‌ شاهد | stock | equity | انبوه سازي، املاك و مستغلات | IRO1SAHD0001 |
| ثشرق | سرمايه گذاري مسكن شمال شرق | stock | equity | انبوه سازي، املاك و مستغلات | IRO1PMSZ0001 |
| ثفارس | عمران‌وتوسعه‌فارس‌ | stock | equity | انبوه سازي، املاك و مستغلات | IRO1OFRS0001 |
| ثمسكن | سرمايه‌گذاري‌ مسكن‌ | stock | equity | انبوه سازي، املاك و مستغلات | IRO1MSKN0001 |
| ثملي | بين المللي ساختمان و صنعت ملي | stock | equity | انبوه سازي، املاك و مستغلات | IRO1BMLI0001 |
| ثنوسا | نوسازي‌وساختمان‌تهران‌ | stock | equity | انبوه سازي، املاك و مستغلات | IRO1NSTH0001 |
| جم | پتروشيمي جم | stock | equity | محصولات شيميايي | IRO1PJMZ0001 |
| جم پيلن | پلي پروپيلن جم - جم پيلن | stock | equity | محصولات شيميايي | IRO1JPPC0001 |
| چافست | افست‌ | stock | equity | انتشار، چاپ و تکثير | IRO1OFST0001 |
| چبسپا | بسته‌ بندي‌ پارس‌ | stock | equity | محصولات كاغذي | IRO1BPRS0001 |
| چدن | توليدي چدن سازان | stock | equity | ساخت محصولات فلزي | IRO1CHDN0001 |
| چفيبر | فيبر ايران‌ | stock | equity | محصولات چوبي | IRO1FIBR0001 |
| چكاپا | گروه صنايع كاغذ پارس | stock | equity | محصولات كاغذي | IRO1KAPA0011 |
| چكارم | كارتن‌ مشهد | stock | equity | محصولات كاغذي | IRO1KMSH0001 |
| چكارن | كارتن‌ ايران‌ | stock | equity | محصولات كاغذي | IRO1KRTI0001 |
| چكاوه | صنايع‌كاغذسازي‌كاوه‌ | stock | equity | محصولات كاغذي | IRO1KSKA0001 |
| چنوپا | نيوپان‌ 22 بهمن‌ | stock | equity | محصولات چوبي | IRO1NEOP0001 |
| حپترو | حمل و نقل پتروشيمي( سهامي عام | stock | equity | حمل ونقل، انبارداري و ارتباطات | IRO1HJPT0001 |
| حتايد | تايدواترخاورميانه | stock | equity | حمل ونقل، انبارداري و ارتباطات | IRO1TAYD0001 |
| حتوكا | حمل‌ونقل‌توكا | stock | equity | حمل ونقل، انبارداري و ارتباطات | IRO1HTOK0001 |
| حفارس | حمل و نقل بين المللي خليج فارس | stock | equity | حمل ونقل، انبارداري و ارتباطات | IRO1HFRS0001 |
| حفاري | حفاري شمال | stock | equity | استخراج نفت گاز و خدمات جنبي ج… | IRO1HSHM0001 |
| حفجر | كشتيراني والفجر | stock | equity | حمل و نقل آبي | IRO1KFJR0001 |
| حكشتي | كشتيراني جمهوري اسلامي ايران | stock | equity | حمل ونقل، انبارداري و ارتباطات | IRO1KSHJ0001 |
| خاذين | سايپاآذين‌ | stock | equity | خودرو و ساخت قطعات | IRO1AZIN0001 |
| خاهن | آهنگري‌ تراكتورسازي‌ ايران‌ | stock | equity | خودرو و ساخت قطعات | IRO1ATIR0001 |
| خاور | ايران‌ خودروديزل‌ | stock | equity | خودرو و ساخت قطعات | IRO1KAVR0001 |
| خبهمن | گروه‌بهمن‌ | stock | equity | خودرو و ساخت قطعات | IRO1BHMN0001 |
| خپارس | پارس‌ خودرو | stock | equity | خودرو و ساخت قطعات | IRO1PKOD0001 |
| خپويش | سازه‌ پويش‌ | stock | equity | خودرو و ساخت قطعات | IRO1SZPO0001 |
| ختراك | ريخته‌گري‌ تراكتورسازي‌ ايران‌ | stock | equity | خودرو و ساخت قطعات | IRO1RTIR0001 |
| ختور | رادياتور ايران‌ | stock | equity | خودرو و ساخت قطعات | IRO1RADI0001 |
| ختوقا | قطعات‌ اتومبيل‌ ايران‌ | stock | equity | خودرو و ساخت قطعات | IRO1GHAT0001 |
| خچرخش | چرخشگر | stock | equity | خودرو و ساخت قطعات | IRO1CHAR0001 |
| خراسان | پتروشيمي خراسان | stock | equity | محصولات شيميايي | IRO1KRSN0001 |
| خريخت | صنايع‌ريخته‌گري‌ايران‌ | stock | equity | خودرو و ساخت قطعات | IRO1RIIR0001 |
| خرينگ | رينگ‌سازي‌مشهد | stock | equity | خودرو و ساخت قطعات | IRO1RINM0001 |
| خزاميا | زامياد | stock | equity | خودرو و ساخت قطعات | IRO1ZMYD0001 |
| خزر | فنرسازي‌زر | stock | equity | خودرو و ساخت قطعات | IRO1FNAR0001 |
| خساپا | سايپا | stock | equity | خودرو و ساخت قطعات | IRO1SIPA0001 |
| خشرق | الكتريك‌ خودرو شرق‌ | stock | equity | خودرو و ساخت قطعات | IRO1KHSH0001 |
| خصدرا | حذف-صنعتي‌ دريايي‌ ايران‌ | stock | equity | پيمانكاري صنعتي | IRO1SDRA0001 |
| خفنر | فنرسازي‌خاور | stock | equity | خودرو و ساخت قطعات | IRO1KFAN0001 |
| خكار | ايركا پارت صنعت | stock | equity | خودرو و ساخت قطعات | IRO1KRIR0001 |
| خكاوه | سايپا ديزل‌ | stock | equity | خودرو و ساخت قطعات | IRO1SPDZ0001 |
| خكمك | كمك‌فنرايندامين‌ | stock | equity | خودرو و ساخت قطعات | IRO1INDM0001 |
| خگستر | گسترش‌سرمايه‌گذاري‌ايران‌خودرو | stock | equity | خودرو و ساخت قطعات | IRO1GOST0001 |
| خلنت | لنت‌ ترمزايران‌ | stock | equity | خودرو و ساخت قطعات | IRO1LENT0001 |
| خمحركه | نيرو محركه‌ | stock | equity | خودرو و ساخت قطعات | IRO1NMOH0001 |
| خمحور | توليدمحورخودرو | stock | equity | خودرو و ساخت قطعات | IRO1TMKH0001 |
| خمهر | مهركام‌پارس‌ | stock | equity | خودرو و ساخت قطعات | IRO1MHKM0001 |
| خموتور | موتورسازان‌تراكتورسازي‌ايران‌ | stock | equity | خودرو و ساخت قطعات | IRO1MSTI0001 |
| خنصير | مهندسي‌نصيرماشين‌ | stock | equity | خودرو و ساخت قطعات | IRO1MNSR0001 |
| خودرو | اوراق مشاركت ايران خودرو | stock | equity | خودرو و ساخت قطعات | IRB5IKCO8751 |
| خوساز | محورسازان‌ايران‌خودرو | stock | equity | خودرو و ساخت قطعات | IRO1MESI0001 |
| دابور | داروسازي‌ ابوريحان‌ | stock | equity | مواد و محصولات دارويي | IRO1DABO0001 |
| دارا یکم | صندوق دارا یکم | ETF | commodity | NULL | NULL |
| دارو | كارخانجات‌داروپخش‌ | stock | equity | مواد و محصولات دارويي | IRO1DPAK0001 |
| داسوه | داروسازي‌ اسوه‌ | stock | equity | مواد و محصولات دارويي | IRO1DOSE0001 |
| دالبر | البرزدارو | stock | equity | مواد و محصولات دارويي | IRO1DALZ0001 |
| دامين | داروسازي‌ امين‌ | stock | equity | مواد و محصولات دارويي | IRO1AMIN0001 |
| دانا | بيمه دانا | stock | equity | بيمه وصندوق بازنشستگي به جزتام… | IRO1BDAN0001 |
| دپارس | پارس‌ دارو | stock | equity | مواد و محصولات دارويي | IRO1PDRO0001 |
| دتماد | توليدمواداوليه‌داروپخش‌ | stock | equity | مواد و محصولات دارويي | IRO1TMVD0001 |
| دتهران | داروسازي‌ تهران‌ دارو | stock | equity | مواد و محصولات دارويي | IRO1THDR0001 |
| دجابر | داروسازي‌ جابرابن‌حيان‌ | stock | equity | مواد و محصولات دارويي | IRO1DJBR0001 |
| ددام | داروسازي زاگرس فارمد پارس | stock | equity | مواد و محصولات دارويي | IRO1DAML0001 |
| درازك | دارويي‌ رازك‌ | stock | equity | مواد و محصولات دارويي | IRO1DRZK0001 |
| دروز | داروسازي‌ روزدارو | stock | equity | مواد و محصولات دارويي | IRO1ROZD0001 |
| دزهراوي | داروسازي‌زهراوي‌ | stock | equity | مواد و محصولات دارويي | IRO1DZAH0001 |
| دسبحا | گروه دارويي سبحان | stock | equity | مواد و محصولات دارويي | IRO1DSOB0001 |
| دسبحان | سبحان دارو | stock | equity | مواد و محصولات دارويي | IRO1DSBH0001 |
| دسينا | داروسازي‌ سينا | stock | equity | مواد و محصولات دارويي | IRO1DSIN0001 |
| دشيمي | شيمي‌ داروئي‌ داروپخش‌ | stock | equity | مواد و محصولات دارويي | IRO1DDPK0001 |
| دعبيد | لابراتوارداروسازي‌ دكترعبيدي‌ | stock | equity | مواد و محصولات دارويي | IRO1ABDI0001 |
| دفارا | داروسازي‌ فارابي‌ | stock | equity | مواد و محصولات دارويي | IRO1DFRB0001 |
| دفرا | فرآورده‌هاي‌ تزريقي‌ ايران‌ | stock | equity | مواد و محصولات دارويي | IRO1FTIR0001 |
| دكوثر | داروسازي‌ كوثر | stock | equity | مواد و محصولات دارويي | IRO1DKSR0001 |
| دكيمي | كيميدارو | stock | equity | مواد و محصولات دارويي | IRO1KIMI0001 |
| دلر | داروسازي‌ اكسير | stock | equity | مواد و محصولات دارويي | IRO1EXIR0001 |
| دلقما | دارويي‌ لقمان‌ | stock | equity | مواد و محصولات دارويي | IRO1DLGM0001 |
| ديران | ايران‌دارو | stock | equity | مواد و محصولات دارويي | IRO1IRDR0001 |
| ذوب | ذوب آهن اصفهان | stock | equity | فلزات اساسي | IRO1ZOBI0001 |
| رانفور | خدمات‌انفورماتيك‌ | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1INFO0001 |
| رتاپ | تجارت الكترونيك پارسيان | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1EPRS0001 |
| رتكو | كنترل‌خوردگي‌تكين‌كو | stock | equity | خدمات فني و مهندسي | IRO1TKIN0001 |
| ركيش | كارت اعتباري ايران كيش | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1RKSH0001 |
| رمپنا | گروه مپنا (سهامي عام) | stock | equity | خدمات فني و مهندسي | IRO1MAPN0001 |
| زپارس | ملي كشت و صنعت و دامپروري پارس | stock | equity | زراعت و خدمات وابسته | IRO1ZPRS0001 |
| زرنام | گروه ص. پژوهشي فرهيختگان زرنام | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1ZRNM0001 |
| زكوثر | سرمايه گذاري كشاورزي كوثر | stock | equity | زراعت و خدمات وابسته | IRO1KOSR0001 |
| زمگسا | كشاورزي‌ ودامپروي‌ مگسال‌ | stock | equity | زراعت و خدمات وابسته | IRO1MAGS0001 |
| سآبيك | سيمان آبيك | stock | equity | سيمان، آهك و گچ | IRO1ABIK0001 |
| ساذري | آذريت‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1AZRT0001 |
| ساراب | سيمان‌ داراب‌ | stock | equity | سيمان، آهك و گچ | IRO1SDAB0001 |
| ساربيل | سيمان آرتا اردبيل | stock | equity | سيمان، آهك و گچ | IRO1SADB0001 |
| ساروم | سيمان‌اروميه‌ | stock | equity | سيمان، آهك و گچ | IRO1SURO0001 |
| ساوه | سيمان‌سفيدساوه‌ | stock | equity | سيمان، آهك و گچ | IRO1SAVE0001 |
| سايرا | ايرانيت‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1IRNT0001 |
| سبجنو | سيمان‌ بجنورد | stock | equity | سيمان، آهك و گچ | IRO1SBOJ0001 |
| سبهان | سيمان‌ بهبهان‌ | stock | equity | سيمان، آهك و گچ | IRO1SBHN0001 |
| سپ | پرداخت الكترونيك سامان كيش | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1SEPK0001 |
| سپاها | سيمان‌سپاهان‌ | stock | equity | سيمان، آهك و گچ | IRO1SSEP0001 |
| سپرمي | پرميت | stock | equity | ساير محصولات كاني غيرفلزي | IRO1PRMT0001 |
| سپيد | سپيد ماكيان | stock | equity | زراعت و خدمات وابسته | IRO1SPID0001 |
| ستران | سيمان‌ تهران‌ | stock | equity | سيمان، آهك و گچ | IRO1STEH0001 |
| سخاش | سيمان‌خاش‌ | stock | equity | سيمان، آهك و گچ | IRO1SKHS0001 |
| سخزر | سيمان‌ خزر | stock | equity | سيمان، آهك و گچ | IRO1SKAZ0001 |
| سخوز | سيمان خوزستان | stock | equity | سيمان، آهك و گچ | IRO1KHOC0001 |
| سدشت | صنايع سيمان دشتستان | stock | equity | سيمان، آهك و گچ | IRO1SDST0001 |
| سدور | سيمان‌ دورود | stock | equity | سيمان، آهك و گچ | IRO1SDOR0001 |
| سرود | سيمان‌شاهرود | stock | equity | سيمان، آهك و گچ | IRO1SROD0001 |
| سشرق | سيمان‌ شرق‌ | stock | equity | سيمان، آهك و گچ | IRO1SSHR0001 |
| سشمال | سيمان‌ شمال‌ | stock | equity | سيمان، آهك و گچ | IRO1SIMS0001 |
| سصفها | سيمان‌اصفهان‌ | stock | equity | سيمان، آهك و گچ | IRO1SEFH0001 |
| سصوفي | سيمان‌ صوفيان‌ | stock | equity | سيمان، آهك و گچ | IRO1SSOF0001 |
| سغدير | توسعه سرمايه و صنعت غدير | stock | equity | سيمان، آهك و گچ | IRO1GDRS0001 |
| سغرب | سيمان‌غرب‌ | stock | equity | سيمان، آهك و گچ | IRO1SGRB0001 |
| سفار | سيمان‌فارس‌ | stock | equity | سيمان، آهك و گچ | IRO1SFRS0001 |
| سفارس | سيمان فارس و خوزستان | stock | equity | سيمان، آهك و گچ | IRO1SFKZ0001 |
| سفارود | كارخانه‌فارسيت‌درود | stock | equity | ساير محصولات كاني غيرفلزي | IRO1FRDO0001 |
| سفاسيت | فارسيت‌ اهواز | stock | equity | ساير محصولات كاني غيرفلزي | IRO1SFAS0001 |
| سفانو | سيمان فارس نو | stock | equity | سيمان، آهك و گچ | IRO1SFNO0001 |
| سقاين | سيمان‌ قائن‌ | stock | equity | سيمان، آهك و گچ | IRO1SGEN0001 |
| سكارون | سيمان‌ كارون‌ | stock | equity | سيمان، آهك و گچ | IRO1SKRN0001 |
| سكرد | سيمان كردستان | stock | equity | سيمان، آهك و گچ | IRO1SKOR0001 |
| سكرما | سيمان‌ كرمان‌ | stock | equity | سيمان، آهك و گچ | IRO1SKER0001 |
| سمازن | سيمان‌مازندران‌ | stock | equity | سيمان، آهك و گچ | IRO1SMAZ0001 |
| سنير | سيمان‌ سفيد ني‌ريز | stock | equity | سيمان، آهك و گچ | IRO1SSNR0001 |
| سهرمز | سيمان‌هرمزگان‌ | stock | equity | سيمان، آهك و گچ | IRO1SHZG0001 |
| سهگمت | سيمان‌هگمتان‌ | stock | equity | سيمان، آهك و گچ | IRO1SHGN0001 |
| سيتا | سرمايه گذاري سيمان تامين | stock | equity | سيمان، آهك و گچ | IRO1SITA0001 |
| سيدكو | سرمايه گذاري توسعه صنايع سيمان | stock | equity | سيمان، آهك و گچ | IRO1CIDC0001 |
| سيستم | همكاران سيستم | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1SYSM0001 |
| سيلام | سيمان‌ ايلام‌ | stock | equity | سيمان، آهك و گچ | IRO1SEIL0001 |
| سیلور | صندوق سیلور | ETF | commodity | NULL | NULL |
| سيمرغ | سيمرغ | stock | equity | زراعت و خدمات وابسته | IRO1SMRG0001 |
| سينا | مالي و سرمايه گذاري سينا | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1FSIN0001 |
| شاراك | پتروشيمي شازند | stock | equity | محصولات شيميايي | IRO1PARK0001 |
| شاملا | معدني‌ املاح‌ ايران‌ | stock | equity | محصولات شيميايي | IRO1AMLH0001 |
| شبريز | پالايش نفت تبريز | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1PNTB0001 |
| شبندر | پالايش نفت بندرعباس | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1PNBA0001 |
| شبهرن | نفت‌ بهران‌ | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1NBEH0001 |
| شپارس | بين‌ المللي‌ محصولات‌ پارس‌ | stock | equity | محصولات شيميايي | IRO1BMPS0001 |
| شپاكسا | پاكسان‌ | stock | equity | محصولات شيميايي | IRO1PAKS0001 |
| شپترو | پتروشيمي‌ آبادان‌ | stock | equity | محصولات شيميايي | IRO1PABD0001 |
| شپديس | پتروشيمي پرديس | stock | equity | محصولات شيميايي | IRO1PRDZ0001 |
| شپلي | پلي‌اكريل‌ | stock | equity | محصولات شيميايي | IRO1PLAK0001 |
| شپمچا | پارس‌ پامچال‌ | stock | equity | محصولات شيميايي | IRO1PPAM0001 |
| شپنا | پالايش نفت اصفهان | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1PNES0001 |
| شتران | پالايش نفت تهران | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1PTEH0001 |
| شتهران | تهران‌ شيمي‌ | stock | equity | مواد و محصولات دارويي | IRO1THSH0001 |
| شتولي | تولي‌پرس‌ | stock | equity | محصولات شيميايي | IRO1TOPI0001 |
| شجي | شركت نفت جي | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1NJEY0001 |
| شخارك | پتروشيمي‌ خارك‌ | stock | equity | محصولات شيميايي | IRO1PKHA0001 |
| شدوص | دوده‌ صنعتي‌ پارس‌ | stock | equity | محصولات شيميايي | IRO1DODE0001 |
| شرنگي | صنعتي‌ رنگين‌ | stock | equity | محصولات شيميايي | IRO1SHRG0001 |
| شزنگ | تجهيزنيروي‌زنگان‌ | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1ZNGN0001 |
| شسپا | نفت سپاهان | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1SEPP0001 |
| شستا | سرمايه گذاري تامين اجتماعي | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1TAMN0001 |
| شسم | توليد سموم‌ علف‌ كش | stock | equity | محصولات شيميايي | IRO1TSAL0001 |
| شسينا | صنايع‌شيميايي‌سينا | stock | equity | محصولات شيميايي | IRO1SHSI0001 |
| شصفها | پتروشيمي‌ اصفهان‌ | stock | equity | محصولات شيميايي | IRO1PESF0001 |
| شغدير | پتروشيمي غدير | stock | equity | محصولات شيميايي | IRO1PGDR0001 |
| شفا | سرمايه گذاري شفادارو | stock | equity | مواد و محصولات دارويي | IRO1SHFA0001 |
| شفارا | پتروشيمي‌فارابي‌ | stock | equity | محصولات شيميايي | IRO1PFRB0001 |
| شفارس | صنايع‌ شيميايي‌ فارس‌ | stock | equity | محصولات شيميايي | IRO1SHFS0001 |
| شفن | پتروشيمي فناوران | stock | equity | محصولات شيميايي | IRO1PFAN0001 |
| شكربن | كربن‌ ايران‌ | stock | equity | محصولات شيميايي | IRO1CRBN0001 |
| شكف | كف‌ | stock | equity | محصولات شيميايي | IRO1KAFF0001 |
| شكلر | نيروكلر | stock | equity | محصولات شيميايي | IRO1NKOL0001 |
| شگل | گلتاش‌ | stock | equity | محصولات شيميايي | IRO1GTSH0001 |
| شلعاب | لعابيران‌ | stock | equity | محصولات شيميايي | IRO1LEAB0001 |
| شلوان | رنگ پارس الوان | stock | equity | محصولات شيميايي | IRO1SLVN0001 |
| شمواد | توليدمواداوليه الياف‌مصنوعي‌ | stock | equity | محصولات شيميايي | IRO1MAVA0001 |
| شنفت | نفت‌ پارس‌ | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1NPRS0001 |
| شوش | هنكل‌ پاك‌ وش‌ | stock | equity | محصولات شيميايي | IRO1VASH0001 |
| شوينده | مديريت صنعت شوينده ت.ص.بهشهر | stock | equity | محصولات شيميايي | IRO1SHOY0001 |
| شيراز | پتروشيمي‌شيراز | stock | equity | محصولات شيميايي | IRO1PSHZ0001 |
| شيران | س. صنايع‌شيميايي‌ايران | stock | equity | محصولات شيميايي | IRO1SSIN0001 |
| طلا | صندوق طلا | ETF | commodity | NULL | NULL |
| عیار | صندوق عیار | ETF | commodity | NULL | NULL |
| غاذر | كشت‌وصنعت‌پياذر | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1PIAZ0001 |
| غالبر | لبنيات‌ كالبر | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1KLBR0001 |
| غبشهر | صنعتي‌ بهشهر | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1SBEH0001 |
| غبهپاك | بهپاك‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1BEPP0001 |
| غبهنوش | بهنوش‌ ايران‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1BENN0001 |
| غپاك | لبنيات‌ پاك‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1LPAK0001 |
| غپينو | پارس‌ مينو | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1MINO0001 |
| غچين | كشت‌ و صنعت‌ چين‌ چين | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1CHCH0001 |
| غدام | خوراك‌ دام‌ پارس‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1KDPS0001 |
| غدشت | دشت‌ مرغاب‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1DMOR0001 |
| غزر | صنعتي زر ماكارون | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1ZARM0001 |
| غساسا | ساسان‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1SASN0001 |
| غسالم | سالمين‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1SLMN0001 |
| غشاذر | پگاه‌آذربايجان‌غربي‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1SHPZ0001 |
| غشان | شيرپاستوريزه‌پگاه‌خراسان‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1SPKH0001 |
| غشصفا | شيرپاستوريزه‌پگاه‌اصفهان‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1SPPE0001 |
| غشهد | شهد ايران ‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1SHAD0001 |
| غكورش | صنعت غذايي كورش | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1KRSH0001 |
| غگرجي | بيسكويت‌ گرجي‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1GORJ0001 |
| غگل | گلوكوزان‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1GCOZ0001 |
| غمارگ | مارگارين‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1MRGN0001 |
| غمهرا | توليدي‌مهرام‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1MRAM0001 |
| غناب | روغن‌ نباتي‌ ناب‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1RNAB0001 |
| غنوش | نوش‌ مازندران‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1NOSH0001 |
| غيوان | كيوان‌ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1KIVN0001 |
| فاذر | صنايع‌ آذرآب‌ | stock | equity | ساخت محصولات فلزي | IRO1AZAB0001 |
| فاراك | ماشين‌ سازي‌ اراك‌ | stock | equity | ساخت محصولات فلزي | IRO1MARK0001 |
| فارس | صنايع پتروشيمي خليج فارس | stock | equity | محصولات شيميايي | IRO1PKLJ0001 |
| فاسمين | كالسيمين‌ | stock | equity | فلزات اساسي | IRO1KSIM0001 |
| فالوم | آلومتك‌ | stock | equity | فلزات اساسي | IRO1ALTK0001 |
| فاما | صنعتي‌ آما | stock | equity | ساخت محصولات فلزي | IRO1SAMA0001 |
| فاهواز | نوردولوله‌ اهواز | stock | equity | فلزات اساسي | IRO1NLAH0001 |
| فايرا | آلومينيوم‌ايران‌ | stock | equity | فلزات اساسي | IRO1ALIR0001 |
| فباهنر | مس‌ شهيدباهنر | stock | equity | فلزات اساسي | IRO1BAHN0001 |
| فبستم | صنايع‌بسته‌بندي‌ مشهد | stock | equity | ساخت محصولات فلزي | IRO1BMAS0001 |
| فبيرا | بسته‌ بندي‌ ايران‌ | stock | equity | ساخت محصولات فلزي | IRO1BIRI0001 |
| فپارس | آلومينيم‌ پارس‌ | stock | equity | فلزات اساسي | IRO1ALPS0001 |
| فپنتا | سپنتا | stock | equity | فلزات اساسي | IRO1SPTA0001 |
| فجام | جام‌دارو | stock | equity | ساخت محصولات فلزي | IRO1JAMD0001 |
| فجر | فولاد اميركبيركاشان | stock | equity | فلزات اساسي | IRO1FAJR0001 |
| فجوش | جوش‌ و اكسيژن‌ ايران‌ | stock | equity | ساخت محصولات فلزي | IRO1JSHO0001 |
| فخاس | فولاد خراسان | stock | equity | فلزات اساسي | IRO1FKAS0001 |
| فخوز | فولاد خوزستان | stock | equity | فلزات اساسي | IRO1FKHZ0001 |
| فرآور | فرآوري‌موادمعدني‌ايران‌ | stock | equity | فلزات اساسي | IRO1FRVR0001 |
| فروس | فروسيليس‌ ايران‌ | stock | equity | فلزات اساسي | IRO1FRIS0001 |
| فروم | توليدفروموليبدن‌كرمان‌ | stock | equity | فلزات اساسي | IRO1TFKR0001 |
| فساز | لوله‌سازي‌اهواز | stock | equity | فلزات اساسي | IRO1LSAH0001 |
| فسازان | غلتك سازان سپاهان | stock | equity | فلزات اساسي | IRO1FSAZ0001 |
| فسبزوار | پارس فولاد سبزوار | stock | equity | فلزات اساسي | IRO1FSBZ0001 |
| فسپا | گروه‌صنعتي‌سپاهان‌ | stock | equity | فلزات اساسي | IRO1SEPA0001 |
| فسديد | لوله و تجهيزات سديد | stock | equity | فلزات اساسي | IRO1LSDD0001 |
| فسرب | ملي‌ سرب‌وروي‌ ايران‌ | stock | equity | فلزات اساسي | IRO1SORB0001 |
| فسلير | سوليران‌ | stock | equity | ساخت محصولات فلزي | IRO1SOLI0001 |
| فلامي | لاميران‌ | stock | equity | ساخت محصولات فلزي | IRO1LAMI0001 |
| فلوله | لوله‌وماشين‌سازي‌ايران‌ | stock | equity | فلزات اساسي | IRO1LMIR0001 |
| فمتال | پارس‌ متال‌ | stock | equity | فلزات اساسي | IRO1PMET0001 |
| فمراد | آلومراد | stock | equity | فلزات اساسي | IRO1ALMR0001 |
| فملي | ملي‌ صنايع‌ مس‌ ايران‌ | stock | equity | فلزات اساسي | IRO1MSMI0001 |
| فنرژي | گسترش‌صنايع‌انرژي‌آذرآب‌ | stock | equity | ساخت محصولات فلزي | IRO1ENAZ0001 |
| فنوال | نورد آلومينيوم‌ | stock | equity | فلزات اساسي | IRO1NALM0001 |
| فنورد | نوردوقطعات‌ فولادي‌ | stock | equity | فلزات اساسي | IRO1NGFO0001 |
| فوكا | فولادكاويان‌ | stock | equity | فلزات اساسي | IRO1FVAN0001 |
| فولاد | فولاد مباركه اصفهان | stock | equity | فلزات اساسي | IRO1FOLD0001 |
| فولاژ | فولاد آلياژي ايران | stock | equity | فلزات اساسي | IRO1FAIR0001 |
| قپارس | قندپارس‌ | stock | equity | قند و شكر | IRO1GPRS0001 |
| قپيرا | فرآورده‌هاي‌غدايي‌وقندپيرانشهر | stock | equity | قند و شكر | IRO1GPSH0001 |
| قثابت | قند ثابت‌ خراسان‌ | stock | equity | قند و شكر | IRO1GSBE0001 |
| قجام | فرآوردههاي غذايي وقندتربت‌جام‌ | stock | equity | قند و شكر | IRO1GTOR0001 |
| قرن | پديده شيمي قرن | stock | equity | محصولات شيميايي | IRO1GARN0001 |
| قزوين | كارخانجات‌ قند قزوين‌ | stock | equity | قند و شكر | IRO1GGAZ0001 |
| قستان | قند قهستان‌ | stock | equity | قند و شكر | IRO1GGOH0001 |
| قستون | قند بيستون‌ | stock | equity | قند و شكر | IRO1GBIS0001 |
| قشرين | قند شيرين‌ خراسان‌ | stock | equity | قند و شكر | IRO1GSHI0001 |
| قشكر | شكرشاهرود | stock | equity | قند و شكر | IRO1SHKR0001 |
| قشهد | شهد | stock | equity | قند و شكر | IRO1GHND0001 |
| قشير | قندشيروان‌ ،قوچان‌ وبجنورد | stock | equity | قند و شكر | IRO1GBJN0001 |
| قصفها | قنداصفهان‌ | stock | equity | قند و شكر | IRO1GESF0001 |
| قلرست | قند لرستان‌ | stock | equity | قند و شكر | IRO1GLOR0001 |
| قمرو | قند مرودشت‌ | stock | equity | قند و شكر | IRO1GMRO0001 |
| قنقش | قندنقش‌جهان‌ | stock | equity | قند و شكر | IRO1GNJN0001 |
| قنيشا | قند نيشابور | stock | equity | قند و شكر | IRO1GNBO0001 |
| قهكمت | قندهكمتان‌ | stock | equity | قند و شكر | IRO1GHEG0001 |
| كابگن | آبگينه‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1ABGN0001 |
| كاذر | فرآورده‌هاي‌نسوزآذر | stock | equity | ساير محصولات كاني غيرفلزي | IRO1NSAZ0001 |
| كاصفا | كاشي‌ اصفهان‌ | stock | equity | كاشي و سراميك | IRO1KESF0001 |
| كالا | بورس كالاي ايران | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1KALA0001 |
| كاما | باما | stock | equity | استخراج کانه هاي فلزي | IRO1BAMA0001 |
| كاوه | فولاد كاوه جنوب كيش | stock | equity | فلزات اساسي | IRO1KVEH0001 |
| كايتا | ايتالران‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1ITAL0001 |
| كايگچ | ايران‌ گچ‌ | stock | equity | سيمان، آهك و گچ | IRO1IRGC0001 |
| كبافق | معادن‌ بافق‌ | stock | equity | استخراج کانه هاي فلزي | IRO1BAFG0001 |
| كبورس | كارگزاران بورس اوراق بهادار | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1KBRS0001 |
| كپارس | كاشي‌ پارس‌ | stock | equity | كاشي و سراميك | IRO1KPRS0001 |
| كپشير | پشم‌شيشه‌ايران‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1PSIR0001 |
| كترام | توليدي‌ كاشي‌ تكسرام‌ | stock | equity | كاشي و سراميك | IRO1TKSM0001 |
| كچاد | معدني‌وصنعتي‌چادرملو | stock | equity | استخراج کانه هاي فلزي | IRO1CHML0001 |
| كچيني | چيني‌ ايران | stock | equity | كاشي و سراميك | IRO1CHIR0001 |
| كحافظ | كاشي‌ وسراميك‌ حافظ‌ | stock | equity | كاشي و سراميك | IRO1KHFZ0001 |
| كخاك | صنايع‌خاك‌چيني‌ايران‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1KCHI0001 |
| كدما | معدني‌ دماوند | stock | equity | استخراج کانه هاي فلزي | IRO1DMVN0001 |
| كرازي | كارخانجات‌توليدي‌شيشه‌رازي‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1TSRZ0001 |
| كرماشا | صنايع پتروشيمي كرمانشاه | stock | equity | محصولات شيميايي | IRO1PKER0001 |
| كروي | توسعه‌ معادن‌ روي‌ ايران‌ | stock | equity | استخراج کانه هاي فلزي | IRO1ROOI0001 |
| كساپا | سايپاشيشه‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1SISH0001 |
| كساوه | صنايع‌ كاشي‌ و سراميك‌ سينا | stock | equity | كاشي و سراميك | IRO1SINA0001 |
| كسرا | سراميك‌هاي‌صنعتي‌اردكان‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1ARDK0001 |
| كسرام | پارس‌ سرام‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1PSER0001 |
| كسعدي | كاشي‌ سعدي‌ | stock | equity | كاشي و سراميك | IRO1KSAD0001 |
| كطبس | ذغال‌سنگ‌ نگين‌ ط‌بس‌ | stock | equity | استخراج زغال سنگ | IRO1TBAS0001 |
| كفپارس | فرآورده‌هاي‌ نسوز پارس‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1NSPS0001 |
| كفرا | فراورده‌ هاي‌ نسوزايران‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1NASI0001 |
| كقزوي | شيشه‌ قزوين‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1SHQZ0001 |
| كگاز | شيشه‌ و گاز | stock | equity | ساير محصولات كاني غيرفلزي | IRO1SGAZ0001 |
| كگل | معدني و صنعتي گل گهر | stock | equity | استخراج کانه هاي فلزي | IRO1GOLG0001 |
| كلوند | كاشي‌ الوند | stock | equity | كاشي و سراميك | IRO1ALVN0001 |
| كماسه | تامين‌ ماسه‌ ريخته‌گري‌ | stock | equity | استخراج ساير معادن | IRO1TAMI0001 |
| كمنگنز | معادن‌منگنزايران‌ | stock | equity | استخراج کانه هاي فلزي | IRO1MNGZ0001 |
| كنور | توسعه معدني و صنعتي صبانور | stock | equity | استخراج کانه هاي فلزي | IRO1KNRZ0001 |
| كنيلو | كاشي‌ نيلو | stock | equity | كاشي و سراميك | IRO1NILO0001 |
| كهرام | توليدي‌گرانيت‌بهسرام‌ | stock | equity | كاشي و سراميك | IRO1BHSM0001 |
| كهمدا | شيشه‌ همدان‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1SHMD0001 |
| كورز | ورزيران‌ | stock | equity | ساير محصولات كاني غيرفلزي | IRO1VARZ0001 |
| كوير | توليدي فولاد سپيد فراب كوير | stock | equity | فلزات اساسي | IRO1KVIR0001 |
| كيانا | گروه مالي كيان | stock | equity | سرمايه گذاريها | IRO1KYAN0001 |
| کهربا | صندوق کهربا | ETF | commodity | NULL | NULL |
| لابسا | آبسال‌ | stock | equity | ماشين آلات و تجهيزات | IRO1ASAL0001 |
| لازما | آزمايش‌ | stock | equity | ماشين آلات و تجهيزات | IRO1AZMA0001 |
| لبهمن | توليدي‌ بهمن‌ | stock | equity | ماشين آلات و تجهيزات | IRO1TBHM0001 |
| لبوتان | گروه‌صنعتي‌بوتان‌ | stock | equity | ماشين آلات و تجهيزات | IRO1BOTA0001 |
| لپارس | پارس‌ الكتريك‌ | stock | equity | ساخت دستگاه‌ها و وسايل ارتباطي | IRO1PELC0001 |
| لپويا | ايران‌ پويا | stock | equity | ماشين آلات و تجهيزات | IRO1IRPO0001 |
| لپيام | كارخانجات‌ صنعتي‌ پيام‌ | stock | equity | ساخت دستگاه‌ها و وسايل ارتباطي | IRO1PYAM0001 |
| لجام | توليدي‌ جام‌ جهان‌ نما | stock | equity | ساخت دستگاه‌ها و وسايل ارتباطي | IRO1JJNM0001 |
| لخانه | لوازم‌ خانگي‌ پارس‌ | stock | equity | ماشين آلات و تجهيزات | IRO1LKPS0001 |
| لخزر | پارس‌ خزر | stock | equity | ماشين آلات و تجهيزات | IRO1KHAZ0001 |
| لسرما | سرما آفرين‌ | stock | equity | ماشين آلات و تجهيزات | IRO1SRMA0001 |
| لكما | كارخانجات‌مخابراتي‌ايران‌ | stock | equity | ساخت دستگاه‌ها و وسايل ارتباطي | IRO1KMOA0001 |
| لمخابر | صنايع‌مخابراتي‌راه‌دورايران‌ | stock | equity | ساخت دستگاه‌ها و وسايل ارتباطي | IRO1SMRI0001 |
| لوتوس | تامين سرمايه لوتوس پارسيان | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1LTOS0001 |
| ما | بيمه ما | stock | equity | بيمه وصندوق بازنشستگي به جزتام… | IRO1BVMA0001 |
| مبين | مبين انرژي خليج فارس | stock | equity | عرضه برق، گاز، بخاروآب گرم | IRO1MOBN0001 |
| مثقال | صندوق مثقال | ETF | commodity | NULL | NULL |
| مدار | س. مديريت سرمايه مدار | stock | equity | سرمايه گذاريها | IRO1MDAR0001 |
| مداران | داده‌پردازي‌ايران‌ | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1DADE0001 |
| مرقام | ايران‌ارقام‌ | stock | equity | رايانه و فعاليت‌هاي وابسته به … | IRO1IAGM0001 |
| ملت | بيمه ملت | stock | equity | بيمه وصندوق بازنشستگي به جزتام… | IRO1BMEL0001 |
| موج | صندوق موج | ETF | commodity | NULL | NULL |
| ميدكو | توسعه معادن وص.معدني خاورميانه | stock | equity | فلزات اساسي | IRO1MDKO0001 |
| نارنج اهرم | صندوق نارنج اهرم | ETF | commodity | NULL | NULL |
| نبروج | نساجي‌ بروجرد | stock | equity | منسوجات | IRO1BROJ0001 |
| نبورس | نهادهاي مالي بورس اوراق بهادار | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1NBRS0001 |
| نتوس | پشم‌ بافي‌ توس‌ | stock | equity | منسوجات | IRO1PTOS0001 |
| نكالا | نهادهاي مالي بورس كالاي ايران | stock | equity | فعاليتهاي كمكي به نهادهاي مالي… | IRO1NKLA0001 |
| نمرينو | ايران‌ مرينوس‌ | stock | equity | منسوجات | IRO1MRIN0001 |
| نوري | پتروشيمي نوري | stock | equity | محصولات شيميايي | IRO1NORI0001 |
| هاي وب | داده گسترعصرنوين-هاي وب | stock | equity | اطلاعات و ارتباطات | IRO1HWEB0001 |
| همراه | شركت ارتباطات سيار ايران | stock | equity | مخابرات | IRO1HMRZ0001 |
| واتي | سرمايه‌ گذاري‌ آتيه‌ دماوند | stock | equity | سرمايه گذاريها | IRO1ATDM0001 |
| وآذر | سرمايه‌گذاري‌توسعه‌آذربايجان‌ | stock | equity | انبوه سازي، املاك و مستغلات | IRO1TAZB0001 |
| وآردل | سرمايه‌گذاري‌كارآفرين‌(هلدينگ‌ | stock | equity | ماشين آلات و تجهيزات | IRO1KARA0001 |
| واعتبار | سرمايه گذاري اعتبار ايران | stock | equity | سرمايه گذاريها | IRO1IDOC0001 |
| والبر | سرمايه‌ گذاري‌ البرز(هلدينگ‌ | stock | equity | مواد و محصولات دارويي | IRO1ALBZ0001 |
| واميد | گروه مديريت سرمايه گذاري اميد | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1OIMC0001 |
| وانصار | بانك انصار | stock | equity | بانكها و موسسات اعتباري | IRO1BANS0001 |
| وايران | ليزينگ ايرانيان | stock | equity | ساير واسطه گريهاي مالي | IRO1LIRZ0001 |
| وبانك | سرمايه گذاري گروه توسعه ملي | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1BANK0001 |
| وبشهر | توسعه‌ صنايع‌ بهشهر(هلدينگ | stock | equity | محصولات غذايي و آشاميدني به جز… | IRO1TSBE0001 |
| وبصادر | بانك صادرات ايران | stock | equity | بانكها و موسسات اعتباري | IRO1BSDR0001 |
| وبملت | بانك ملت | stock | equity | بانكها و موسسات اعتباري | IRO1BMLT0001 |
| وبهمن | سرمايه‌گذاري‌بهمن‌ | stock | equity | سرمايه گذاريها | IRO1SBAH0001 |
| وبوعلي | سرمايه‌گذاري‌بوعلي‌ | stock | equity | سرمايه گذاريها | IRO1BALI0001 |
| وبيمه | سرمايه‌ گذاري‌ صنعت‌ بيمه‌ | stock | equity | سرمايه گذاريها | IRO1BIME0001 |
| وپارس | بانك‌پارسيان‌ | stock | equity | بانكها و موسسات اعتباري | IRO1BPAR0001 |
| وپاسار | بانك پاسارگاد | stock | equity | بانكها و موسسات اعتباري | IRO1BPAS0001 |
| وپترو | سرمايه‌گذاري صنايع پتروشيمي‌ | stock | equity | محصولات شيميايي | IRO1PETR0001 |
| وپخش | داروپخش‌ (هلدينگ‌ | stock | equity | مواد و محصولات دارويي | IRO1DARO0001 |
| وپست | پست بانك ايران | stock | equity | بانكها و موسسات اعتباري | IRO1BPST0001 |
| وتجارت | بانك تجارت | stock | equity | بانكها و موسسات اعتباري | IRO1BTEJ0001 |
| وتوس | توسعه‌شهري‌توس‌گستر | stock | equity | انبوه سازي، املاك و مستغلات | IRO1TGOS0001 |
| وتوسم | سرمايه‌گذاري‌توسعه‌ملي‌ | stock | equity | سرمايه گذاريها | IRO1TMEL0001 |
| وتوشه | سرمايه‌ گذاري‌ پارس‌ توشه‌ | stock | equity | ماشين آلات و تجهيزات | IRO1TSHE0001 |
| وتوصا | گروه س توسعه صنعتي ايران | stock | equity | سرمايه گذاريها | IRO1TOSA0001 |
| وتوكا | سرمايه‌گذاري‌توكافولاد(هلدينگ | stock | equity | فلزات اساسي | IRO1TOKA0001 |
| وخارزم | سرمايه گذاري خوارزمي | stock | equity | سرمايه گذاريها | IRO1IKHR0001 |
| وخاور | بانك خاورميانه | stock | equity | بانكها و موسسات اعتباري | IRO1BKHZ0001 |
| ورنا | سرمايه‌گذاري‌ رنا(هلدينگ‌ | stock | equity | خودرو و ساخت قطعات | IRO1RENA0001 |
| وساپا | سرمايه‌گذاري‌ سايپا | stock | equity | سرمايه گذاريها | IRO1SSAP0001 |
| وساخت | سرمايه‌ گذاري‌ ساختمان‌ايران‌ | stock | equity | انبوه سازي، املاك و مستغلات | IRO1SAKH0001 |
| وساربيل | شركت س استان اردبيل | stock | equity | سرمايه گذاريها | IRO1OS030001 |
| وساشرقي | شركت س استان آذربايجان شرقي | stock | equity | سرمايه گذاريها | IRO1OS010001 |
| وساغربي | شركت س استان آذربايجان غربي | stock | equity | سرمايه گذاريها | IRO1OS020001 |
| وسبوشهر | شركت س استان بوشهر | stock | equity | سرمايه گذاريها | IRO1OS060001 |
| وسپه | سرمايه‌گذاري‌ سپه‌ | stock | equity | سرمايه گذاريها | IRO1SPAH0001 |
| وسخراج | شركت س استان خراسان جنوبي | stock | equity | سرمايه گذاريها | IRO1OS090001 |
| وسخراش | شركت س استان خراسان شمالي | stock | equity | سرمايه گذاريها | IRO1OS110001 |
| وسخوز | شركت س استان خوزستان | stock | equity | سرمايه گذاريها | IRO1OS120001 |
| وسديد | گروه‌صنعتي‌سديد(هلدينگ‌ | stock | equity | فلزات اساسي | IRO1SDID0001 |
| وسرضوي | س.سهام عدالت استان خراسان رضوي | stock | equity | سرمايه گذاريها | IRO1OS100001 |
| وسزنجان | شركت س استان زنجان | stock | equity | سرمايه گذاريها | IRO1OS130001 |
| وسصفا | شركت س استان اصفهان | stock | equity | سرمايه گذاريها | IRO1OS040001 |
| وسفارس | شركت س استان فارس | stock | equity | سرمايه گذاريها | IRO1OS160001 |
| وسقزوين | سرمايه گذاري عدالت استان قزوين | stock | equity | سرمايه گذاريها | IRO1OS170001 |
| وسقم | شركت س استان قم | stock | equity | سرمايه گذاريها | IRO1OS180001 |
| وسكاب | س.ص.بازنشستگي كاركنان بانكها | stock | equity | سرمايه گذاريها | IRO1SKBV0001 |
| وسكرد | شركت س استان كردستان | stock | equity | سرمايه گذاريها | IRO1OS190001 |
| وسكرشا | س.سهام عدالت استان كرمانشاه | stock | equity | سرمايه گذاريها | IRO1OS210001 |
| وسكرمان | س.سهام عدالت استان كرمان | stock | equity | سرمايه گذاريها | IRO1OS200001 |
| وسكهبو | س.عدالت ا. كهگيلويه وبويراحمد | stock | equity | سرمايه گذاريها | IRO1OS220001 |
| وسگلستا | شركت س استان گلستان | stock | equity | سرمايه گذاريها | IRO1OS230001 |
| وسگيلا | شركت س استان گيلان | stock | equity | سرمايه گذاريها | IRO1OS240001 |
| وسلرستا | شركت س استان لرستان | stock | equity | سرمايه گذاريها | IRO1OS250001 |
| وسمازن | س.سهام عدالت استان مازندران | stock | equity | سرمايه گذاريها | IRO1OS260001 |
| وسمحال | شركت س.استان چهارمحال وبختياري | stock | equity | سرمايه گذاريها | IRO1OS080001 |
| وسمركز | شركت س استان مركزي | stock | equity | سرمايه گذاريها | IRO1OS270001 |
| وسهرمز | شركت س استان هرمزگان | stock | equity | سرمايه گذاريها | IRO1OS280001 |
| وسهمدا | شركت س استان همدان | stock | equity | سرمايه گذاريها | IRO1OS290001 |
| وسيزد | شركت س استان يزد | stock | equity | سرمايه گذاريها | IRO1OS300001 |
| وسيستا | شركت س استان سيستان وبلوچستان | stock | equity | سرمايه گذاريها | IRO1OS150001 |
| وسيلام | شركت س استان ايلام | stock | equity | سرمايه گذاريها | IRO1OS050001 |
| وسينا | بانك سينا | stock | equity | بانكها و موسسات اعتباري | IRO1VSIN0001 |
| وصنا | گروه‌صنايع‌بهشهرايران‌ | stock | equity | سرمايه گذاريها | IRO1GBEH0001 |
| وصندوق | سرمايه‌گذاري‌صندوق‌بازنشستگي‌ | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1SAND0001 |
| وصنعت | سرمايه گذاري توسعه صنعت وتجارت | stock | equity | سرمايه گذاريها | IRO1SNMA0001 |
| وغدير | سرمايه‌گذاري‌غدير(هلدينگ‌ | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1GDIR0001 |
| وكار | بانك‌ كارآفرين‌ | stock | equity | بانكها و موسسات اعتباري | IRO1KRAF0001 |
| وكغدير | بين المللي توسعه ص. معادن غدير | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1TMGD0001 |
| ولپارس | ليزينگ پارسيان | stock | equity | ساير واسطه گريهاي مالي | IRO1LPRS0001 |
| ولساپا | ليزينگ رايان‌ سايپا | stock | equity | ساير واسطه گريهاي مالي | IRO1RSAP0001 |
| ولصنم | ليزينگ‌صنعت‌ومعدن‌ | stock | equity | ساير واسطه گريهاي مالي | IRO1LSMD0001 |
| ولغدر | ليزينگ‌خودروغدير | stock | equity | ساير واسطه گريهاي مالي | IRO1LKGH0001 |
| ولكار | ليزينگ كارآفرين | stock | equity | ساير واسطه گريهاي مالي | IRO1LKAR0001 |
| ولملت | واسپاري ملت | stock | equity | ساير واسطه گريهاي مالي | IRO1VLMT0001 |
| ولنوين | ليزينگ اقتصاد نوين | stock | equity | ساير واسطه گريهاي مالي | IRO1VALE0001 |
| وليز | ليزينگ‌ايران‌ | stock | equity | ساير واسطه گريهاي مالي | IRO1LZIN0001 |
| ومدير | گ.مديريت ارزش سرمايه ص ب كشوري | stock | equity | سرمايه گذاريها | IRO1VMDR0001 |
| ومعادن | توسعه‌معادن‌وفلزات‌ | stock | equity | استخراج کانه هاي فلزي | IRO1MADN0001 |
| ومعين | سرمايه گذاري توسعه معين ملت | stock | equity | واسطه‌گري‌هاي مالي و پولي | IRO1MOIN0001 |
| وملت | سرمايه‌گذاري‌ملت‌ | stock | equity | سرمايه گذاريها | IRO1MELT0001 |
| وملي | گروه‌ صنعتي‌ ملي‌ (هلدينگ‌ | stock | equity | دباغي، پرداخت چرم و ساخت انواع… | IRO1GMEL0001 |
| ونفت | سرمايه‌گذاري‌ صنعت‌ نفت‌ | stock | equity | فراورده هاي نفتي، كك و سوخت هس… | IRO1NAFT0001 |
| ونوين | بانك‌اقتصادنوين‌ | stock | equity | بانكها و موسسات اعتباري | IRO1NOVN0001 |
| ونيرو | سرمايه‌گذاري‌نيرو | stock | equity | عرضه برق، گاز، بخاروآب گرم | IRO1SNRO0001 |
| ونيكي | سرمايه‌گذاري‌ ملي‌ايران‌ | stock | equity | شرکتهاي چند رشته اي صنعتي | IRO1NIKI0001 |
| یاقوت | صندوق یاقوت | ETF | commodity | NULL | NULL |

</details>

> **نکته مهم — ستون‌های تاریخ دوتایی:** هر جدول ستون‌های `gregorian_date date` و `shamsi_date varchar(10)` دارد.
> منبع استخراج (مثلاً `trade_date`، `created_at` یا `fetched_at`) در جدول «منبع تاریخ دوتایی» آمده و مقدار آن
> به‌صورت خودکار توسط trigger دیتابیس (`sync_dual_dates_fn`) در هر INSERT/UPDATE محاسبه می‌شود.
> برای backfill داده‌های موجود: `python scripts/backfill_dual_dates.py`

### جمع‌بندی جامع و نقشه راه اصلاحات

سکوی داده شامل **128 جدول** و حدود **~42,474,311 ردیف** است. از این میان **55 جدول خالی**، **2 جدول نسخه قدیمی** با جایگزین زنده `brsapi_*`، **11 جدول بدون مدل ORM** و **6 جدول بدون هیچ مرجع کد فعال** وجود دارد (برای **1 جدول** آمار PostgreSQL جمع نشده و برآورد ردیف دقیق نیست).

**نقشه راه اصلاحات (اولویت‌بندی‌شده):**

| اولویت | اقدام | هدف |
|--------|-------|-----|
| **P0** | افزودن constraint یکتا برای upsert امن | `brsapi_historical_daily(symbol,date)`، `news_articles(url)`، `brsapi_intraday_trades(symbol,date,time)`، `codal_reports(ins_id,report_type)` |
| **P0** | رفع باگ دانلود ضمائم کدال | `codal_announcements` خالی است؛ `codal_download_service.py` باید از `brsapi_codal_announcements` بخواند |
| **P1** | مهاجرت ستون‌های تاریخ VARCHAR به نوع زمانی | حدود ۱۰۰ ستون در جدول‌های BrsApi و legacy (فهرست کامل در بخش «تحلیل عمیق») |
| **P1** | تکمیل backfill تاریخ دوتایی + اجرای ANALYZE | `python scripts/backfill_dual_dates.py` سپس `ANALYZE` روی جدول‌های بدون آمار |
| **P2** | ایندکس‌های مفقود و فشرده‌سازی هایپرتیبل‌ها | جدول‌های >۱۰۰K ردیف با ۱ ایندکس؛ فعال‌سازی compression روی هایپرتیبل‌ها |
| **P2** | پاکسازی ردیف‌های یتیم نماد | جدول‌های TSE که به نمادهای ناموجود ارجاع می‌دهند |
| **P3** | حذف جدول‌های قدیمی بعد از تأیید | `candlesticks`، `symbol_snapshots`، `option_*`، `intraday_trades` و… |
| **P3** | حذف جدول‌های بدون مصرف‌کننده | جدول‌های بدون مرجع کد فعال (بخش «جزئیات هر جدول») |

> برای به‌روزرسانی این گزارش: `python scripts/analyze_db_issues.py && python scripts/generate_db_readme.py`

---

## 📄 مجوز

MIT License — مشاهده [LICENSE](LICENSE) برای جزئیات.

---

## 🙏 قدردانی

- **FastAPI** — فریمورک API
- **Next.js** — فریمورک React
- **PostgreSQL / TimescaleDB** — دیتابیس
- **Redis** — کش، صف و قفل
- **Recharts / TanStack Query** — فرانت‌اند
- **BrsApi.ir** — ارائه‌دهنده داده بازار ایران

---

<p align="center">ساخته شده با ❤️ برای بازار سرمایه ایران</p>
