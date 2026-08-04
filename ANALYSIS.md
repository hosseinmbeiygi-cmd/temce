# تحلیل جامع سیستم — Iran Market Data & Analytics Platform

> تحلیل ۱۰۰ لایه‌ای معماری، عملکرد، و پیشنهادات ارتقا
> هدف نهایی: **معرفی بهترین نمادها برای خرید در بازارهای مختلف مالی**

---

## فهرست مطالب

1. [نمای کلی سیستم](#۱-نمای-کلی-سیستم)
2. [تحلیل لایه ورودی و شروع برنامه](#۲-تحلیل-لایه-ورودی-و-شروع-برنامه)
3. [لایه API و مسیریابی](#۳-لایه-api-و-مسیریابی)
4. [لایه سرویس‌ها](#۴-لایه-سرویس‌ها)
5. [پایپ‌لاین سیگنال‌دهی (قلب سیستم)](#۵-پایپ‌لاین-سیگنال‌دهی)
6. [پایپ‌لاین یادگیری ماشین](#۶-پایپ‌لاین-یادگیری-ماشین)
7. [لایه داده و دیتابیس](#۷-لایه-داده-و-دیتابیس)
8. [منابع داده خارجی](#۸-منابع-داده-خارجی)
9. [برنامه‌ریزی و جاب‌ها](#۹-برنامه‌ریزی-و-جاب‌ها)
10. [فرانت‌اند](#۱۰-فرانت‌اند)
11. [زیرساخت و داکر](#۱۱-زیرساخت-و-داکر)
12. [امنیت](#۱۲-امنیت)
13. [مانیتورینگ](#۱۳-مانیتورینگ)
14. [بطری‌های گلو (Bottlenecks)](#۱۴-بطری‌های-گلو)
15. [تحلیل بازارها](#۱۵-تحلیل-بازارها)
16. [پیشنهادات ارتقا تا سطح هوش مصنوعی پیشرفته](#۱۶-پیشنهادات-ارتقا)
17. [نقشه راه توسعه](#۱۷-نقشه-راه-توسعه)
18. [مشکل بارگذاری صفحات](#۱۸-مشکل-بارگذاری-صفحات)

---

## ۱. نمای کلی سیستم

### معماری

```
┌─────────────────────────────────────────────────────────────────┐
│                     Iran Market Platform                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Frontend │  │  Backend │  │ Scheduler│  │ Ingestion│       │
│  │ Next.js  │  │ FastAPI  │  │ APSched. │  │ aiohttp  │       │
│  │ Port:3000│  │ Port:8000│  │          │  │          │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │              │             │
│       └──────────────┴──────────────┴──────────────┘             │
│                          │                                       │
│                   ┌──────┴──────┐                                │
│                   │  PostgreSQL │                                │
│                   │ TimescaleDB │                                │
│                   │  Port:5432  │                                │
│                   └─────────────┘                                │
│                          │                                       │
│                   ┌──────┴──────┐                                │
│                   │    Redis    │                                │
│                   │  Port:6379  │                                │
│                   └─────────────┘                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### آمار کلی

| مؤلفه | تعداد |
|-------|-------|
| صفحات فرانت‌اند | ۵۳ صفحه |
| کامپوننت‌های React | ۳۹ کامپوننت |
| API Endpointها | ۴۸+ مسیر |
| سرویس‌های بک‌اند | ۸۳ فایل |
| مدل‌های ML | ۱۵+ نوع الگوریتم |
| بازارهای تحت پوشش | ۷ بازار |
| جاب‌های زمان‌بندی‌شده | ۲۵+ جاب |
| اسکریپت‌ها | ۱۷۱ اسکریپت |
| تست‌ها | ۴۳+ فایل تست |
| جداول دیتابیس | ۳۰+ جدول |

---

## ۲. تحلیل لایه ورودی و شروع برنامه

### نقطه ورود: `main.py`

```python
uvicorn.run("apps.api.app:app", host=settings.server_host, port=settings.server_port)
```

### روند راه‌اندازی: `apps/api/app.py`

```
1. setup_logging()
2. settings.validate_production()
3. init_database()                    ← PostgreSQL اتصال
4. register_all_models()              ← ثبت مدل‌های ML
5. get_cache().initialize()           ← Redis اتصال
6. SchedulerApp().start()             ← شروع APScheduler
7. _brsapi_startup_sync()             ← همگام‌سازی اولیه BrsApi
8. _fetch_news_on_startup()           ← دریافت اخبار RSS
9. _orchestrator_hourly_cron()        ← حلقه ساعتی سیگنال‌دهی
```

### مشکلات شناسایی شده:

| مشکل | فایل | خط | شدت |
|------|------|-----|------|
| state متغیر در سطح ماژول | `app.py` | 42-51 | بحرانی |
| رقابت DB sessions در شروع | `app.py` | 268-293 | بالا |
| عدم تخلیه graceful shutdown | `app.py` | 416 | متوسط |

---

## ۳. لایه API و مسیریابی

### ۴۸+ مسیر API ثبت شده

| دسته | مسیرها | تعداد |
|------|--------|-------|
| **بازار** | `/market`, `/market-dashboard`, `/market-watch`, `/quotes`, `/trades`, `/orderbooks` | ۶ |
| **سیگنال** | `/signals`, `/multi-market-signals`, `/recommendations` | ۳ |
| **غربالگری** | `/screener`, `/smart-screener`, `/smart-money` | ۳ |
| **تحلیل** | `/analysis`, `/indicators`, `/fundamental`, `/macro` | ۴ |
| **بک‌تست** | `/backtests` | ۱ |
| **ML** | `/ml`, `/experiments` | ۲ |
| **داده** | `/codal`, `/news`, `/data-import`, `/instruments`, `/brsapi` | ۵ |
| **پرتفوی** | `/portfolios`, `/watchlist`, `/alerts` | ۳ |
| **ادمین** | `/dashboard`, `/jobs`, `/health`, `/tests` | ۴ |
| **سایر** | `/chat`, `/assistant`, `/stock-assistant`, `/reports`, `/anomalies` | ۵+ |

### Middleware Stack

```
Request → CORSMiddleware → TimingMiddleware → LoggingMiddleware → RateLimitMiddleware → Route Handler
```

### مشکلات:

| مشکل | توضیح |
|------|-------|
| CORS `["*"]` | اجازه هر origin در production |
| ۴۸ روتر روی یک اپ | بدون microservice separation |
| Dependency injection ساده | بدون lazy initialization واقعی |

---

## ۴. لایه سرویس‌ها

### نقشه وابستگی سرویس‌های سیگنال

```
QuantSignalOrchestrator (1200+ خط)
├── MultiMarketSignalEngine (1234 خط)     ← قوانین تکنیکال
│   ├── SQL queries → brsapi_* tables
│   ├── RSI, SMA, EMA, ATR computation
│   └── Entry/Exit zone calculation
├── MLSignalConnector (297 خط)            ← پیش‌بینی ML
│   ├── SignalFeaturePipeline (338 خط)    ← استخراج ویژگی
│   └── ModelRegistry → مدل‌های آموزش‌دیده
├── SignalVotingSystem (264 خط)           ← ترکیب آرا
├── ProbabilityCalibrator (668 خط)        ← کالیبراسیون احتمال
├── ConfidenceScorer (325 خط)             ← امتیاز اطمینان
├── SignalDecisionEngine (984 خط)         ← ۱۰ دروازه تصمیم‌گیری
├── CrossMarketCorrelator                 ← همبستگی بین‌بازاری
└── AutoRetrainPipeline (265 خط)          ← بازآموزی خودکار
```

### سرویس‌های بازار داده

| سرویس | مسئولیت |
|--------|---------|
| `MarketService` | نمای کلی بازار، شاخص‌ها |
| `QuoteService` | داده‌های تاریخچه قیمت |
| `TradeService` | تاریخچه معاملات |
| `OrderBookService` | snapshots عمق بازار |
| `InstrumentService` | متادیتای نمادها |
| `RealtimeQuoteService` | قیمت‌های لحظه‌ای WebSocket |

---

## ۵. پایپ‌لاین سیگنال‌دهی (قلب سیستم)

### مراحل کامل

```
مرحله ۰: جمع‌آوری داده (بک‌گراند)
    BrsApi → Rate Limiter → SyncService → PostgreSQL

مرحله ۱: تولید سیگنال قانونی (Rule-Based)
    MultiMarketSignalEngine.generate_all()
    ├── سهام: momentum + RSI + trend + volume + فاندامنتال
    ├── طلا: momentum + RSI + trend
    ├── ارز: change_pct threshold + ATR
    ├── رمزارز: momentum + RSI + trend + volume/cap
    ├── آپشن: Put/Call Ratio + Max Pain
    ├── کالا: change_pct + ATR
    └── بورس کالا: futures analysis

مرحله ۲: پیش‌بینی ML
    MLSignalConnector.predict()
    ├── استخراج ویژگی از تاریخچه
    ├── اجرای آن‌سومبل مدل‌ها
    └── میانگین وزنی buy/sell/hold

مرحله ۳: رأی‌گیری
    SignalVotingSystem.vote()
    ├── رأی قانونی (score / 100)
    ├── رأی ML (direction_scores × weights)
    └── استراتژی: weighted / unanimous / majority

مرحله ۳.۵: کالیبراسیون احتمال
    ProbabilityCalibrator.calibrate()
    ├── Bucket-based calibration
    ├── Platt scaling / Isotonic regression
    └── Brier score + ECE tracking

مرحله ۴: امتیاز اطمینان
    ConfidenceScorer.compute_confidence()
    ├── دقت تاریخی (۳۰٪)
    ├── توافق مدل (۲۰٪)
    ├── قدرت روند (۱۵٪)
    ├── رژیم نوسان (۱۰٪)
    ├── قدرت سیگنال (۱۵٪)
    └── عملکرد اخیر (۱۰٪)

مرحله ۴.۵: موتور تصمیم‌گیری (۱۰ دروازه)
    SignalDecisionEngine.evaluate()
    ├── دروازه ۱: کیفیت داده
    ├── دروازه ۲: سلامت مدل
    ├── دروازه ۳: احتمال کالیبره‌شده
    ├── دروازه ۴: رژیم بازار
    ├── دروازه ۵: اجماع آن‌سومبل
    ├── دروازه ۶: نقدینگی
    ├── دروازه ۷: نسبت ریسک/ریوارد
    ├── دروازه ۸: انتظار خالص
    ├── دروازه ۹: محدودیت پرتفوی
    └── دروازه ۱۰: شرایط اجرایی

مرحله ۵: همبستگی بین‌بازاری
    CrossMarketCorrelator.analyze()
    ├── Risk-Off: طلا صعودی + سهام نزولی
    ├── Risk-On: طلا نزولی + سهام صعودی
    ├── Inflation-Hedge: طلا + رمزارز صعودی
    ├── Import-Inflation: کالا صعودی + ارز نزولی
    └── Systemic-Risk: همه بازارها نزولی

مرحله ۶: فیلتر + ذخیره‌سازی
    فیلتر اطمینان ≥ min_confidence
    سهمیه هر بازار (تنوع)
    ذخیره در signal_accuracy

مرحله ۷: حلقه بازخورد
    ارزیابی سیگنال‌های گذشته
    بازآموزی خودکار اگر دقت < ۵۵٪
```

### دروازه‌های تصمیم‌گیری (جدول جزئی)

| دروازه | نام | آستانه BLOCK | آستانه WARN |
|--------|------|-------------|-------------|
| ۱ | کیفیت داده | score < 0.80 | missing_fields > 3 |
| ۲ | مدل | active_models < 1 | disagreement > 0.60 |
| ۳ | احتمال | prob < threshold | margin < 0.10 |
| ۴ | رژیم | CRISIS/UNKNOWN | HIGH_VOLATILITY |
| ۵ | اجماع | < min_agree models | < min_active models |
| ۶ | نقدینگی | score < 0.50 | fill_probability < 0.50 |
| ۷ | ریسک/ریوارد | rr < 0.5 | rr < 1.0 |
| ۸ | انتظار خالص | net_exp < 0 | net_exp < 0.05R |
| ۹ | پرتفوی | open_risk > 25% | correlated > 40% |
| ۱۰ | اجرا | — | spread > max_spread |

### رتبه‌بندی سیگنال‌ها

| رتبه | احتمال | نسبت R:R | انتظار خالص |
|------|--------|----------|------------|
| **A+** | ≥ 0.70 | ≥ 2.0 | ≥ 0.20R |
| **A** | ≥ 0.65 | ≥ 1.5 | ≥ 0.12R |
| **B** | ≥ 0.60 | ≥ 1.0 | ≥ 0.05R |
| **WATCHLIST** | بقیه | — | — |
| **REJECT** | هر BLOCK | — | — |

---

## ۶. پایپ‌لاین یادگیری ماشین

### الگوریتم‌های موجود

| دسته | مدل‌ها | تعداد |
|------|--------|-------|
| **خطی** | Linear, Ridge, Lasso, ElasticNet, Logistic | ۵ |
| **درختی** | RandomForest, ExtraTrees, XGBoost, LightGBM, CatBoost, HistGradientBoosting | ۶ |
| ** SVM ** | SVM, SVR | ۲ |
| ** Bayesian ** | BayesianRidge, ARDRegression | ۲ |
| ** KNN ** | KNN Classifier, KNN Regressor | ۲ |
| ** عمیق** | LSTM, GRU, CNN, Transformer, RNN, TCN, Autoencoder | ۷ |
| **آن‌سومبل** | Stacking, Voting, Weighted Average, Mixture of Experts | ۴ |

### ویژگی‌های ML (۱۷ ماژول)

| ماژول | ویژگی‌ها |
|-------|---------|
| PriceFeatures | بازده، مومنتوم، نوسان |
| TechnicalFeatures | RSI, MACD, Bollinger, ATR |
| CandlestickFeatures | الگوهای کندلی |
| VolumeFeatures | حجم، OBV, VWAP |
| TradeFeatures | تعداد معاملات |
| CrossSectionalFeatures | رتبه، z-score |
| FundamentalFeatures | P/E, P/B, ROE |
| MacroFeatures | نرخ بهره، تورم |
| MicrostructureFeatures | Spread, تأثیر بازار |
| NewsFeatures | تحلیل احساسات NLP |

### آن‌سومبل مدل‌ها به ازای هر بازار

| بازار | وزن‌ها |
|-------|--------|
| **سهام** | XGBoost(0.35) + LSTM(0.30) + RandomForest(0.20) + Transformer(0.15) |
| **طلا** | XGBoost(0.40) + LSTM(0.35) + GRU(0.25) |
| **ارز** | XGBoost(0.45) + LSTM(0.30) + Linear(0.25) |
| **رمزارز** | XGBoost(0.30) + LSTM(0.35) + Transformer(0.35) |

### حجم مدل‌های ذخیره‌شده

- ۳۵۹ پوشه مدل در `ml_artifacts/`
- بیشتر: BayesianRidge و ExtraTrees
- نمادها: ۱۰۰+ نماد ایرانی

---

## ۷. لایه داده و دیتابیس

### جداول اصلی

| جدول | ردیف | توضیح |
|------|------|-------|
| `brsapi_symbol_snapshots` | ~۵۰۰ | اسنپ‌شات لحظه‌ای نمادها |
| `brsapi_historical_daily` | ~۱۰۰K+ | تاریخچه روزانه |
| `brsapi_gold_coin_history` | ~۴۴K | تاریخچه طلا و سکه |
| `brsapi_gold_currency_pro_daily_history` | ~۱۶۰K | تاریخچه ارز و XAUUSD |
| `brsapi_crypto_daily_history` | ~۱۸K | تاریخچه رمزارز |
| `codal_reports` | ~۲۲۷K | اطلاعیه‌های کدال |
| `signal_accuracy` | متغیر | ردیابی دقت سیگنال‌ها |
| `instruments` | ~۵۰۰+ | اطلاعات نمادها |
| `daily_history` | ~۵۰۰K+ | OHLCV روزانه |
| `intraday_trades` | ~۱M+ | معاملات درون‌روزی |

### تنظیمات اتصال

```python
pool_size = 5          # ← بحرانی: خیلی کم برای production
max_overflow = 10
pool_pre_ping = True
pool_recycle = 3600    # ← بازیافت هر ساعت
```

### مشکلات:

| مشکل | شدت |
|------|------|
| `pool_size=5` خیلی کم | بحرانی |
| بدون TimescaleDB hypertable | بالا |
| بدون partitioning برای جداول بزرگ | بالا |
| بدون read replica | متوسط |

---

## ۸. منابع داده خارجی

### BrsApi.ir — منبع اصلی

| دسته | Endpoint | فاصله | محدودیت |
|------|----------|-------|---------|
| سهام | AllSymbols | ۲ دقیقه | ۳۰ req/min |
| شاخص | Index | ۲ دقیقه | — |
| آپشن | Options | ۵ دقیقه | — |
| بورس کالا | IME Futures/Options/Certificates | ۵ دقیقه | ۱۵ req/min |
| رمزارز | Cryptocurrency | ۵ دقیقه | — |
| طلا و ارز | GoldCurrency/Pro | ۵ دقیقه | — |
| کالا | Commodity | ۵ دقیقه | — |
| کدال | Announcement | ۱۵ دقیقه | ۲۰ req/min |

### محدودیت‌های نرخ

```
روزانه: ۱۰,۰۰۰ درخواست
۵ دقیقه: ۵۰۰ درخواست (sliding window)
به ازای هر دسته: Token bucket مجزا
```

---

## ۹. برنامه‌ریزی و جاب‌ها

### جدول زمان‌بندی کامل

| جاب | فاصله اجرا | اولویت |
|-----|-----------|--------|
| `SyncQuotesJob` | هر ۲ دقیقه | بالا |
| `SyncSnapshotsToQuotesJob` | هر ۲ دقیقه | بالا |
| `brsapi_all_symbols` | هر ۲ دقیقه | بالا |
| `brsapi_index` | هر ۲ دقیقه | بالا |
| `brsapi_options` | هر ۵ دقیقه | متوسط |
| `brsapi_ime_*` | هر ۵ دقیقه | متوسط |
| `brsapi_commodities` | هر ۵ دقیقه | متوسط |
| `brsapi_crypto` | هر ۵ دقیقه | متوسط |
| `brsapi_gold_currency` | هر ۵ دقیقه | متوسط |
| `brsapi_codal` | هر ۱۵ دقیقه | پایین |
| `NewsIngestionJob` | هر ۱۰ دقیقه | متوسط |
| `SyncCodalJob` | هر ۶ ساعت | پایین |
| `SyncInstrumentsJob` | هر ۲۴ ساعت | پایین |
| `Orchestrator Cron` | هر ۱ ساعت | بالا |
| `RiskMonitorCheck` | هر ۵ دقیقه | بالا |
| `BackfillHistoricalData` | روزانه ۲:۰۰ صبح | پایین |
| `Auto-Retrain` | هر ۷ روز | پایین |

### مشکل: دو سیستم زمان‌بندی مجزا

```
1. APScheduler (apps/scheduler/app.py) → جاب‌های BrsApi + Sync
2. asyncio.create_task (apps/api/app.py) → Orchestrator hourly cron
```

هر دو در حافظه نگهداری می‌شوند و در restart از بین می‌روند.

---

## ۱۰. فرانت‌اند

### صفحات اصلی (۵۳ صفحه)

| صفحه | پیچیدگی | توضیح |
|------|---------|-------|
| **Dashboard** | بالا | شاخص‌ها، ارز، طلا، رمزارز، اخبار، عرضه/تقاضا |
| **Multi-Market Signals** | بالا | سیگنال‌های چندبازاره با cron status |
| **Backtest** | خیلی بالا | موتور بک‌تست با مقایسه استراتژی‌ها |
| **Analysis** | بالا | تحلیل تکنیکال + فاندامنتال |
| **Heatmap** | بالا | نقشه حرارتی بازار |
| **Smart Screener** | متوسط-بالا | غربالگری پیشرفته |
| **Smart Money** | بالا | تحلیل جریان پول هوشمند |
| **Crypto** | متوسط | بازار رمزارز |
| **Watchlist** | متوسط-بالا | لیست مشاهده با sparkline |
| **Portfolio** | متوسط | مدیریت پرتفوی |
| **Signals** | پایین | جدول ساده سیگنال‌ها ← **نیاز به بازنویسی** |

### الگوهای عملکرد

| الگو | کجا استفاده شده |
|------|----------------|
| Dynamic imports | AreaChart, BarChart, PieChart, TradingView |
| `ssr: false` | تمام dynamic imports |
| `useMemo` | mock data generators |
| `useCallback` | removeSymbol, handleAdd |
| Skeleton loading | تمام صفحات |
| Query stale times | 10s-300s بسته به نوع داده |

### State Management

- **React Query** (`@tanstack/react-query`) → state سرور
- **useState** → state محلی UI
- **localStorage** → theme, auth token, debug logs
- **بدون Redux/Zustand/Context** → state management سراسری وجود ندارد

---

## ۱۱. زیرساخت و داکر

### سرویس‌های Docker

| سرویس | CPU | RAM | توضیح |
|-------|-----|-----|-------|
| `api` (×2) | 1 core | 512MB | FastAPI backend |
| `worker` (×2) | 2 cores | 1GB | Background worker |
| `scheduler` | 0.5 core | 256MB | APScheduler |
| `admin` | 0.5 core | 256MB | Admin panel |
| `postgres` | 1 core | 1GB | TimescaleDB |
| `redis` | 0.5 core | 256MB | Cache |
| `frontend` | — | — | Next.js |

### مشکلات زیرساخت

| مشکل | شدت |
|------|------|
| بدون nginx/reverse proxy | بالا |
| بدون Prometheus/Grafana | بالا |
| بدون MinIO/S3 service | متوسط |
| بدون log aggregation | متوسط |
| نسخه Python ناهمگون (3.11 vs 3.12) | پایین |

---

## ۱۲. امنیت

### وضعیت فعلی

| مؤلفه | وضعیت |
|-------|-------|
| احراز هویت JWT | ✅ فعال |
| رمزگذاری رمز عبور | ✅ PBKDF2-SHA256 |
| Rate Limiting | ✅ فعال |
| CORS | ⚠️ `["*"]` — خطرناک |
| TLS Verification | ❌ غیرفعال در BrsApi |
| CSRF Protection | ❌ وجود ندارد |
| Input Sanitization | ⚠️ وجود دارد ولی متصل نیست |
| JWT Revocation | ❌ وجود ندارد |
| MFA | ❌ وجود ندارد |
| API Versioning | ❌ وجود ندارد |

### مشکلات امنیتی بحرانی

```
⚠️ .env شامل رمزهای عبور hardcoded
⚠️ CORS همه origins را اجازه می‌دهد
⚠️ BrsApi TLS verification غیرفعال
⚠️ Production validation نادیده گرفته می‌شود
```

---

## ۱۳. مانیتورینگ

### اجزای فعلی

| مؤلفه | وضعیت | مشکل |
|-------|-------|------|
| Health Checks | ✅ DB + Redis | Queue check تکراری |
| Metrics (In-Memory) | ✅ | از بین می‌رود در restart |
| Alert Rules | ✅ ۴ قاعده | فقط logging، نه notification |
| Data Freshness | ✅ | In-memory only |
| Drift Detection | ✅ KS + PSI | In-memory only |
| Tracing | ⚠️ Custom | غیرسازگار با OTel |
| Prometheus | ⚠️ پیکربندی شده | Endpoint وجود ندارد |
| Log Aggregation | ❌ | وجود ندارد |

---

## ۱۴. بطری‌های گلو (Bottlenecks)

### رتبه‌بندی بر اساس شدت

| # | مشکل | مکان | شدت | تأثیر |
|---|-------|------|------|-------|
| ۱ | **pool_size=5** | `core/database.py:29` | بحرانی | تمام درخواست‌ها صف می‌کشند |
| ۲ | **پایپ‌لاین تک‌رشته** | `quant_signal_orchestrator.py` | بحرانی | سیگنال‌دهی کند برای ۷ بازار |
| ۳ | **sync startup** | `app.py:296-356` | بالا | رقابت DB در شروع |
| ۴ | **state در حافظه** | `app.py:42-61` | بالا | عدم سازگاری multi-worker |
| ۵ | **SQL خام در سرویس‌ها** | `multi_market_signal_engine.py` | بالا | دور زدن ORM + خطر SQL injection |
| ۶ | **duplicate cache** | `core/cache.py` vs `integrations/cache/` | متوسط | سردرگمی و ناسازگاری |
| ۷ | **بدون distributed lock** | `jobs/locking.py:13` | بالا | اجرای تکراری جاب‌ها |
| ۸ | ** ingestion تک‌رشته** | `ingestion/worker.py:49` | متوسط | کندی جمع‌آوری داده |
| ۹ | **بدون feature store** | ML pipeline | متوسط | محاسبه مجدد ویژگی‌ها |
| ۱۰ | **models in-memory** | `ml_signal_connector.py:70` | متوسط | از بین رفتن در restart |

---

## ۱۵. تحلیل بازارها

### بازارهای تحت پوشش فعلی

| بازار | کیفیت سیگنال | عمق داده | تاریخچه | ارزیابی |
|-------|-------------|---------|---------|---------|
| **سهام** | بالا | خیلی بالا | ۲۰۰+ روز | ⭐⭐⭐⭐⭐ |
| **طلا** | بالا | بالا | ۵۰۰+ رکورد | ⭐⭐⭐⭐ |
| **رمزارز** | متوسط | متوسط | ۱۰۰ روز | ⭐⭐⭐ |
| **آپشن** | متوسط | متوسط | Snapshot | ⭐⭐⭐ |
| **بورس کالا** | پایین | پایین | Snapshot | ⭐⭐ |
| **ارز** | پایین | خیلی پایین | فقط فعلی | ⭐ |
| **کالا (جهانی)** | پایین | خیلی پایین | فقط فعلی | ⭐ |

### بازارهای غیرcovered

| بازار | وضعیت |
|-------|-------|
| اوراق قرضه | ❌ وجود ندارد |
| ETF/صندوق‌ها | ❌ وجود ندارد |
| Forex Futures | ❌ وجود ندارد |
| شاخص‌های بین‌المللی | ❌ وجود ندارد |
| کالاهای کشاورزی | ❌ وجود ندارد |
| اوراق اسلامی (Sukuk) | ❌ وجود ندارد |

### مشکل اصلی: ارز و کالا

```
ارز: فقط change_pct threshold ساده → بدون تحلیل تکنیکال
کالا: فقط change_pct → بدون تاریخچه برای RSI/SMA/EMA
→ این دو بازار سیگنال‌های ضعیفی تولید می‌کنند
```

---

## ۱۶. پیشنهادات ارتقا

### سطح ۱: رفع مشکلات حیاتی (هفته ۱-۲)

#### ۱.۱. افزایش Connection Pool

```python
# core/config/database.py
pool_size: int = 20          # از 5 به 20
max_overflow: int = 30       # از 10 به 30
```

#### ۱.۲. تعمیر State Management

```python
# apps/api/app.py
# جایگزینی _cron_state و _alert_state با Redis-backed state
from core.cache import get_cache

async def get_cron_state():
    cache = get_cache()
    state = await cache.get("cron:state")
    return json.loads(state) if state else {}
```

#### ۱.۳. رفع CORS

```python
# core/config/__init__.py
cors_origins: list[str] = ["http://localhost:3000"]  # نه ["*"]
```

#### ۱.۴. فعال کردن TLS Verification

```python
# brsapi/client.py
async with httpx.AsyncClient(verify=True) as client:  # نه verify=False
```

#### ۱.۵. Distributed Locking با Redis

```python
# jobs/locking.py
import redis.asyncio as redis

class RedisJobLock:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def acquire(self, job_name: str, ttl: int = 300) -> bool:
        return await self.redis.set(f"lock:{job_name}", "1", nx=True, ex=ttl)

    async def release(self, job_name: str):
        await self.redis.delete(f"lock:{job_name}")
```

---

### سطح ۲: بهینه‌سازی عملکرد (هفته ۳-۴)

#### ۲.۱. پارالل‌سازی پایپ‌لاین سیگنال

```python
# services/quant_signal_orchestrator.py
import asyncio

async def generate_all_markets(self):
    tasks = [
        self._generate_for_market("stock"),
        self._generate_for_market("gold"),
        self._generate_for_market("currency"),
        self._generate_for_market("crypto"),
        self._generate_for_market("option"),
        self._generate_for_market("commodity"),
        self._generate_for_market("ime"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return self._merge_results(results)
```

#### ۲.۲. Feature Store

```python
# ml/feature_store.py (جدید)
class FeatureStore:
    """ذخیره ویژگی‌های محاسبه‌شده در Redis/DB"""

    async def get_features(self, symbol: str, market: str) -> Optional[MarketFeatures]:
        key = f"features:{market}:{symbol}"
        cached = await self.cache.get(key)
        return MarketFeatures.from_dict(cached) if cached else None

    async def set_features(self, features: MarketFeatures, ttl: int = 300):
        key = f"features:{features.market}:{features.symbol}"
        await self.cache.set(key, features.to_dict(), ttl)
```

#### ۲.۳. پایپ‌لاین جمع‌آوری داده موازی

```python
# ingestion/worker.py
async def ingest_all_parallel(self):
    tasks = [self.ingest_source(source) for source in self.sources]
    await asyncio.gather(*tasks, return_exceptions=True)
```

#### ۲.۴. TimescaleDB Hypertables

```sql
-- migrations/versions/0008_timescale_hypertables.sql
SELECT create_hypertable('daily_history', 'trade_date');
SELECT create_hypertable('intraday_trades', 'trade_date');
SELECT add_retention_policy('intraday_trades', INTERVAL '6 months');
SELECT add_compression_policy('daily_history', INTERVAL '30 days');
```

---

### سطح ۳: ارتقای هوش مصنوعی (هفته ۵-۸)

#### ۳.۱. اضافه کردن بازارهای جدید

```python
# services/multi_market_signal_engine.py

async def _signals_bonds(self) -> list[MarketSignal]:
    """سیگنال اوراق قرضه"""
    # تحلیل بر اساس: نرخ بهره، منحنی بازده، duration, credit spread
    pass

async def _signals_etf(self) -> list[MarketSignal]:
    """سیگنال ETF و صندوق‌ها"""
    # تحلیل بر اساس: NAV discount/premium, tracking error, volume
    pass

async def _signals_international(self) -> list[MarketSignal]:
    """سیگنال شاخص‌های بین‌المللی"""
    # تحلیل S&P500, NASDAQ, DAX, Nikkei
    pass
```

#### ۳.۲. بهبود تحلیل بین‌بازاری

```python
# services/cross_market_correlator.py (جدید)
class AdvancedCrossMarketCorrelator:
    """تحلیل همبستگی آماری واقعی"""

    async def compute_rolling_correlation(self, market_a: str, market_b: str, window: int = 30):
        """محاسبه همبستگی غلتکی ۳۰ روزه"""
        pass

    async def detect_regime(self) -> MarketRegime:
        """تشخیص رژیم بازار با HMM (Hidden Markov Model)"""
        pass

    async def granger_causality(self, cause: str, effect: str, max_lag: int = 5):
        """آزمون علیت گرنجر بین بازارها"""
        pass

    async def sector_rotation_signal(self) -> RotationSignal:
        """سیگنال چرخش بخشی"""
        pass
```

#### ۳.۳. مدل‌های عمیق واقعی

```python
# ml/models/deep/transformer_v2.py
class TransformerV2(BaseModel):
    """Transformer پیشرفته با attention چندگانه"""

    def __init__(self, d_model=128, nhead=8, num_layers=4, dropout=0.1):
        # Multi-head attention
        # Positional encoding
        # Layer normalization
        # Feed-forward network
        pass

# ml/models/deep/temporal_fusion_transformer.py
class TemporalFusionTransformer(BaseModel):
    """TFT برای پیش‌بینی سری زمانی"""
    pass
```

#### ۳.۴. سیستم A/B Testing

```python
# services/ab_testing.py
class ABTestingFramework:
    """مقایسه استراتژی‌های مختلف سیگنال‌دهی"""

    async def create_experiment(self, name: str, variants: list[SignalStrategy]):
        pass

    async def route_signal(self, experiment_id: str, signal: MarketSignal):
        pass

    async def compute_winner(self, experiment_id: str) -> str:
        """محاسبه برنده بر اساس ducose, Sharpe, win rate"""
        pass
```

#### ۳.۵. Paper Trading

```python
# services/paper_trading.py
class PaperTradingEngine:
    """شبیه‌سازی معاملات واقعی"""

    async def execute_virtual_trade(self, signal: Signal, capital: float):
        pass

    async def track_performance(self) -> PerformanceReport:
        pass

    async def compare_with_live(self) -> ComparisonReport:
        pass
```

#### ۳.۶. Sentiment Analysis پیشرفته

```python
# services/sentiment_engine.py
class SentimentEngine:
    """تحلیل احساسات چندمنظوره"""

    async def analyze_news_sentiment(self, text: str) -> SentimentResult:
        """Persian BERT + Financial domain adaptation"""
        pass

    async def analyze_social_sentiment(self, platform: str) -> SentimentResult:
        """تحلیل شبکه‌های اجتماعی"""
        pass

    async def analyze_institutional_flow(self, symbol: str) -> FlowSignal:
        """تحلیل جریان نهادی"""
        pass
```

#### ۳.۷. Explainable AI (XAI)

```python
# services/explainability.py
class SignalExplainer:
    """توضیح دقیق دلایل سیگنال"""

    async def explain_signal(self, signal: EnrichedSignal) -> ExplanationReport:
        return ExplanationReport(
            top_features=self._shap_values(signal),
            contribution_breakdown=self._feature_contributions(signal),
            counterfactual=self._what_if_analysis(signal),
            historical_analogues=self._find_similar_signals(signal),
            risk_factors=self._identify_risks(signal),
            confidence_decomposition=self._break_confidence(signal),
        )
```

---

### سطح ۴: زیرساخت حرفه‌ای (هفته ۹-۱۲)

#### ۴.۱. Message Queue

```
Redis Streams یا Apache Kafka
├── topic: raw_data
├── topic: signals
├── topic: predictions
├── topic: alerts
└── topic: audit
```

#### ۴.۲. Model Serving

```
MLflow یا BentoML
├── Model Registry
├── Model Serving (REST/gRPC)
├── Model Monitoring
├── A/B Testing
└── Canary Deployments
```

#### ۴.۳. Observability Stack

```
Prometheus + Grafana + Loki + Tempo
├── Metrics: API latency, error rates, signal accuracy
├── Logs: Centralized log aggregation
├── Traces: Distributed tracing with OpenTelemetry
└── Dashboards: Real-time system health
```

#### ۴.۴. CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
stages:
  - lint (ruff, mypy, eslint)
  - test (pytest, vitest)
  - security (bandit, safety)
  - build (docker build)
  - deploy (docker compose up)
  - monitor (health check)
```

---

## ۱۷. نقشه راه توسعه

### فاز ۱: تثبیت (هفته ۱-۴)
- [ ] افزایش DB pool_size به ۲۰
- [ ] رفع CORS vulnerability
- [ ] فعال کردن TLS verification
- [ ] Distributed locking با Redis
- [ ] رفع state management مشکلات
- [ ] پارالل‌سازی signal pipeline
- [ ] اضافه کردن TimescaleDB hypertables
- [ ] رفع duplicate cache implementations

### فاز ۲: بهبود سیگنال (هفته ۵-۸)
- [ ] اضافه کردن تاریخچه ارز برای تحلیل تکنیکال
- [ ] اضافه کردن تاریخچه کالا
- [ ] Feature store برای ML
- [ ] بهبود Cross-market correlator
- [ ] اضافه کردن بازار اوراق قرضه
- [ ] اضافه کردن بازار ETF
- [ ] Sentiment Analysis پیشرفته
- [ ] Explainable AI برای سیگنال‌ها

### فاز ۳: ارتقای ML (هفته ۹-۱۲)
- [ ] Temporal Fusion Transformer
- [ ] Transformer V2 با attention چندگانه
- [ ] A/B Testing framework
- [ ] Paper trading engine
- [ ] AutoML برای انتخاب بهترین مدل
- [ ] Online learning (آموزش مداوم)
- [ ] Model ensemble optimization

### فاز ۴: زیرساخت (هفته ۱۳-۱۶)
- [ ] Message queue (Redis Streams)
- [ ] Model serving (MLflow)
- [ ] Prometheus + Grafana
- [ ] OpenTelemetry tracing
- [ ] CI/CD pipeline
- [ ] Horizontal scaling
- [ ] Load balancing
- [ ] Backup automation

---

## ۱۸. مشکل بارگذاری صفحات

### سه بخش برنامه که بارگذاری نشدند

بر اساس تحلیل، این صفحات ممکن است مشکل بارگذاری داشته باشند:

| صفحه | دلیل احتمالی | راه حل |
|------|-------------|--------|
| **Multi-Market Signals** | API `/multi-market-signals` کند (پایپ‌لاین ۷ مرحله‌ای) | Cache کردن نتیجه + lazy loading |
| **Backtest** | بارگذاری حجم زیاد داده تاریخچه | Streaming + virtual scrolling |
| **Heatmap** | پردازش ۵۰۰+ نماد در فرانت‌اند | Web Worker + WebAssembly |

### راه حل‌های پیشنهادی

#### ۱. کش کردن سیگنال‌ها در سمت سرور

```python
# apps/api/endpoints/multi_market_signals.py
from core.cache import get_cache

@router.get("")
async def get_signals():
    cache = get_cache()
    cached = await cache.get("signals:latest")
    if cached:
        return cached

    # اجرای پایپ‌لاین
    result = await orchestrator.generate(...)
    await cache.set("signals:latest", result, ttl=300)  # ۵ دقیقه cache
    return result
```

#### ۲. استفاده از Streaming Response

```python
# apps/api/endpoints/multi_market_signals.py
from starlette.responses import StreamingResponse

@router.get("")
async def get_signals_stream():
    async def generate():
        async for batch in orchestrator.generate_streaming():
            yield json.dumps(batch) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

#### ۳. Web Worker برای Heatmap

```typescript
// frontend/src/workers/heatmap.worker.ts
self.onmessage = (e) => {
  const { symbols } = e.data;
  const processed = symbols.map(processSymbol);
  self.postMessage(processed);
};
```

---

## خلاصه

### نقاط قوت
- ✅ پایپ‌لاین سیگنال‌دهی بسیار پیشرفته (۷ مرحله + ۱۰ دروازه)
- ✅ پوشش ۷ بازار مختلف
- ✅ ۱۵+ الگوریتم ML
- ✅ ۵۳ صفحه فرانت‌اند
- ✅ مانیتورینگ جامع
- ✅ زیرساخت Docker حرفه‌ای

### نقاط ضعف اصلی
- ❌ DB pool_size بحرانی
- ❌ State management در حافظه
- ❌ ارز و کالا سیگنال ضعیف
- ❌ بدون feature store
- ❌ بدون distributed locking
- ❌ CORS vulnerability
- ❌ بدون message queue

### اولویت‌های فوری
1. **DB pool_size** → ۲۰ (بحرانی)
2. **Distributed locking** → Redis (بحرانی)
3. **State management** → Redis-backed (بالا)
4. **پارالل‌سازی pipeline** → asyncio.gather (بالا)
5. **CORS** → محدود کردن origins (بالا)
6. **TLS verification** → فعال کردن (بالا)

---

> **نویسنده تحلیل**: MiMoCode AI
> **تاریخ**: ۲۰۲۶-۰۷-۲۴
> **نسخه تحلیل**: 1.0
