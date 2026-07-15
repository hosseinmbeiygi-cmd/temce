<div dir="rtl">

# سکوی داده و تحلیل بازار سرمایه ایران 🇮🇷📈

**Iran Market Data & Analytics Platform** — یک پلتفرم جامع، ماژولار و مقیاس‌پذیر برای جمع‌آوری، پردازش، ذخیره‌سازی، تحلیل و بک‌تست داده‌های بازار سرمایه ایران.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![CI](https://github.com/your-username/iran-market-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/iran-market-platform/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## فهرست مطالب

- [ویژگی‌ها](#ویژگی‌ها)
- [معماری](#معماری)
- [بازارهای پشتیبانی‌شده](#بازارهای-پشتیبانی‌شده)
- [تکنولوژی‌ها](#تکنولوژی‌ها)
- [ساختار پروژه](#ساختار-پروژه)
- [راه‌اندازی سریع](#راه‌اندازی-سریع)
- [استفاده با Docker](#استفاده-با-docker)
- [فرانت‌اند Next.js](#فرانت‌اند-nextjs)
- [CI/CD Pipeline](#cicd-pipeline)
- [سیستم بک‌تست](#سیستم-بک‌تست)
- [Agent-Based Modeling (ABM)](#agent-based-modeling-abm)
- [ریزساختار بازار](#ریزساختار-بازار)
- [موتور تحلیل](#موتور-تحلیل)
- [موتور آزمایش](#موتور-آزمایش)
- [یکپارچه‌سازی BrsApi.ir](#یکپارچه‌سازی-brsapiir-)
- [موتور Smart Money (۹ لایه)](#موتور-smart-money-۹-لایه-)
- [موتور مکالمه ۲۰ سطحی (Chat Engine)](#موتور-مکالمه-۲۰-سطحی-chat-engine-)
- [API](#api)
- [ML Pipeline](#ml-pipeline)
- [مانیتورینگ](#مانیتورینگ)
- [اپراتورهای داده](#اپراتورهای-داده)
- [پیکربندی](#پیکربندی)
- [توسعه و مشارکت](#توسعه-و-مشارکت)
- [اسکریپت‌های کاربردی](#اسکریپت‌های-کاربردی)

---

## ویژگی‌ها

### 🏛️ سیستم بک‌تست چندبازاری
- **Replay Engine**: موتور بازپخش رویدادمحور با قابلیت پشتیبانی از ۱۰۰ میلیون رویداد
- **Unified Timeline**: خط زمانی یکپارچه با مرتب‌سازی بر اساس `(timestamp, priority)`
- **Market Rule Engine**: موتور قوانین مجزا برای هر بازار
- **Multi-Market**: پشتیبانی هم‌زمان از چند بازار با قوانین متفاوت
- **Event-Driven**: معماری رویدادمحور با انواع رویدادهای استاندارد

### 🤖 Agent-Based Modeling
- **Market Maker**: بازارگردان هوشمند با مدیریت موجودی
- **Noise Trader**: معامله‌گر نویز تصادفی
- **Trend Follower**: دنبال‌کننده روند
- **Mean Reversion Agent**: معامله‌گر بازگشت به میانگین

### 🔬 ریزساختار بازار (Microstructure)
- **مدل صف**: شبیه‌سازی صف سفارشات با قابلیت کنسل و تغییر
- **مدل ایمپکت قیمت**: قانون جذر (`sqrt law`) برای تخمین تأثیر معاملات
- **مدل نقدینگی پنهان**: برآورد عمق واقعی سفارشات
- **موتور حراج**: شبیه‌سازی حراج بازگشایی، پایانی و نوسان
- **مدل تأخیر**: شبیه‌سازی Latency شبکه
- **کالیبراسیون**: تخمین پارامترها از داده‌های واقعی

### 📊 تحلیل عملکرد
- **معیارهای سنتی**: Sharpe, Sortino, CAGR, Calmar, MDD
- **معیارهای معاملاتی**: Win Rate, Profit Factor, Turnover
- **منحنی سرمایه**: ردیابی روزانه NAV

### 🧪 آزمایش و بهینه‌سازی
- **Grid Search**: جستجوی ترکیبی پارامترها
- **Walk-Forward**: آزمایش پنجره‌های متوالی
- **Monte Carlo**: شبیه‌سازی تصادفی پارامترها

### 🗄️ جمع‌آوری داده
- **TSETMC**: داده‌های بورس تهران
- **CODAL**: سامانه کدال (اطلاعات شرکت‌ها)
- **اخبار و ماکرو**: داده‌های بنیادی و کلان

### 📈 ML Pipeline
- **Feature Store**: ذخیره و مدیریت ویژگی‌ها
- **Model Registry**: ثبت و نسخه‌گذاری مدل‌ها
- **Hyperparameter Tuning**: بهینه‌سازی فراپارامترها
- **Batch Inference**: پیش‌بینی دسته‌ای
- **Drift Detection**: تشخیص تغییر توزیع داده

---

## معماری

```
                ┌──────────────────────────────┐
                │      Historical Data Lake     │
                │  (Parquet / Arrow / InMemory) │
                └──────────┬───────────────────┘
                           │
                ┌──────────▼───────────────────┐
                │      Data Normalization       │
                └──────────┬───────────────────┘
                           │
                ┌──────────▼───────────────────┐
                │         Event Builder         │
                │   (Trade / Quote / Auction)   │
                └──────────┬───────────────────┘
                           │
                ┌──────────▼───────────────────┐
                │    Unified Event Timeline     │
                │   (sorted by timestamp + 🎯)  │
                └──────────┬───────────────────┘
                           │
                ┌──────────▼───────────────────┐
                │        Replay Engine          │
                │   ┌──────────┬──────────┐     │
                │   │ Market   │Strategy  │     │
                │   │ Engine   │ Engine   │     │
                │   ├──────────┼──────────┤     │
                │   │ Risk     │ Micro-   │     │
                │   │ Engine   │structure │     │
                │   └────┬─────┴────┬─────┘     │
                │        │          │           │
                │   ┌────▼──────────▼─────┐     │
                │   │  Execution Simulator│     │
                │   │   + Fill Simulator  │     │
                │   └──────────┬──────────┘     │
                │              │               │
                │   ┌──────────▼──────────┐     │
                │   │   Portfolio Engine   │     │
                │   └──────────┬──────────┘     │
                │              │               │
                │   ┌──────────▼──────────┐     │
                │   │  Analytics Engine    │     │
                │   └─────────────────────┘     │
                └──────────────────────────────┘
```

### اجزای اصلی

| لایه | وظیفه |
|------|--------|
| **Data Lake** | ذخیره و بارگذاری داده‌های تاریخی با فرمت Parquet/Arrow |
| **Event Builder** | تبدیل داده‌های خام به رویدادهای استاندارد بازار |
| **Unified Timeline** | خط زمانی مرتب‌شده از تمام رویدادها |
| **Replay Engine** | هسته شبیه‌سازی — مدیریت clock و dispatch رویدادها |
| **Market Engine** | نگهداری state بازار برای هر نماد |
| **Rule Engine** | اعمال قوانین هر بازار (دامنه نوسان، سشن، اندازه تیک) |
| **Microstructure Engine** | شبیه‌سازی ریزساختار (صف، ایمپکت، حراج، نقدینگی پنهان) |
| **Execution Simulator** | شبیه‌سازی اجرای سفارش با مدل صف |
| **Portfolio Engine** | مدیریت دارایی، margin، PnL |
| **Risk Engine** | کنترل ریسک (حداکثر موقعیت، drawdown، volatility) |
| **Analytics Engine** | محاسبه معیارهای عملکرد |
| **Experiment Engine** | مدیریت grid search, walk-forward, monte carlo |

---

## بازارهای پشتیبانی‌شده

| بازار | شناسه | نوسان قیمت | سشن | حراج | سفارش بازار |
|-------|-------|-----------|------|------|------------|
| **بورس تهران (TSE)** | `tse` | ۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **فرابورس (IFB)** | `ifb` | ۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **بازار پایه** | `base_market` | ۳-۱٪ پلکانی | ۰۸:۴۵-۱۲:۳۰ | دوره‌ای | ❌ |
| **ETF** | `etf` | ۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **اوراق بدهی** | `bonds` | ۱٪ | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| **مشتقه** | `derivatives` | متغیر | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| **بورس کالا (IME)** | `ime` | ۵٪ | ۱۱:۴۵-۱۸:۰۰ | ✅ | ✅ |
| **بورس انرژی** | `energy` | ۵٪ | ۱۱:۴۵-۱۸:۰۰ | دوره‌ای | ❌ |

---

## تکنولوژی‌ها

### Backend
| تکنولوژی | کاربرد |
|-----------|---------|
| **Python 3.11+** | زبان اصلی |
| **FastAPI** | REST API |
| **SQLAlchemy 2.0** | ORM |
| **Alembic** | مهاجرت دیتابیس |
| **Pydantic v2** | اعتبارسنجی داده |
| **httpx / aiohttp** | HTTP clientهای ناهمزمان |
| **APScheduler** | زمان‌بندی وظایف |
| **Redis** | کش و صف |
| **Pandas / NumPy** | پردازش داده |
| **OpenTelemetry** | ردیابی توزیع‌شده |
| **Prometheus** | متریک |

### ML (اختیاری)
| تکنولوژی | کاربرد |
|-----------|---------|
| **scikit-learn** | مدل‌های پایه |
| **XGBoost / LightGBM / CatBoost** | Gradient Boosting |
| **PyTorch** | یادگیری عمیق |
| **SHAP** | تفسیرپذیری مدل |

### Database
| سرویس | کاربرد |
|-------|---------|
| **PostgreSQL 16** | دیتابیس اصلی |
| **TimescaleDB** | داده‌های زمانی |
| **MinIO** | ذخیره‌سازی آبجکت (S3-compatible) |
| **Redis 7** | کش |

### Frontend
| تکنولوژی | کاربرد |
|-----------|---------|
| **Next.js 16** | فریمورک React |
| **Tailwind CSS v4** | استایل‌دهی |

---

### معماری Docker

```mermaid
flowchart LR
    subgraph External["🌍 بیرون از Docker"]
        USER["👤 کاربر\nمرورگر"]
        DEV["💻 توسعه\ncurl / httpie"]
    end

    subgraph DockerNet["🐳 Docker Network\n(overlay: internal)"]
        subgraph Public["📡 Public Services\n(ports exposed)"]
            FRONTEND["🟢 Frontend\nNext.js 16\nport 3000\nRewrite Proxy:\n/api/v1/* → api:8000"]
            API["🔵 API (FastAPI)\nuvicorn\nport 8000\n2 replicas (prod)\n• Swagger: /docs\n• ReDoc: /redoc"]
            ADMIN["🟣 Admin Panel\nport 8001\nمدیریت و مانیتورینگ"]
        end

        subgraph Background["⚙️ Background Services"]
            WORKER["⏳ Worker\n2 replicas\nپردازش پس‌زمینه\n• BrsApi sync\n• News fetch\n• Codal import"]
            SCHED["📅 Scheduler\nAPScheduler\nزمان‌بندی وظایف\n• هر ۵ دقیقه\n• هر ۱۵ دقیقه\n• روزانه"]
            INGEST["📥 Ingestion\nجمع‌آوری داده\nTSETMC · CODAL"]
        end

        subgraph Data["💾 Data Stores"]
            PG["🐘 PostgreSQL 16\n+ TimescaleDB\nport 5432\nhealthcheck: pg_isready"]
            REDIS["🔄 Redis 7\nCache + Queue\nport 6379\nappendonly: yes\nrequirepass"]
            MINIO["📦 MinIO\nS3-compatible\nport 9000 (API)\nport 9001 (Console)\nذخیره‌سازی آبجکت"]
        end

        subgraph Monitoring["📊 Observability"]
            PROM["📈 Prometheus\nport 9090\nمتریک‌های سیستم"]
            GRAF["📉 Grafana\nport 3001\nداشبوردهای مانیتورینگ"]
        end
    end

    subgraph ProdExtra["🏭 Production Only\n(Docker Swarm)"]
        TRAEFIK["🔒 Traefik / Reverse Proxy\nTLS termination\n127.0.0.1 binding"]
        SECRETS["🔐 Docker Secrets\npostgres_password\nsecret_key\napi_key"]
        LOGGING["📝 Logging\ndriver: json-file\nmax-size: 10m\nmax-file: 5"]
    end

    USER -->|"http://localhost:3000"| FRONTEND
    DEV -->|"http://localhost:8000\n/docs · /redoc"| API
    USER -.->|"http://localhost:8001"| ADMIN

    FRONTEND -->|"http://api:8000/api/v1/*\n(Next.js Rewrite)"| API
    API -->|"postgresql://user:pass\n@timescaledb:5432/tse_quant"| PG
    API -->|"redis://:pass\n@redis:6379/0"| REDIS
    API -->|"S3 API"| MINIO

    SCHED -->|"Trigger sync jobs"| WORKER
    WORKER -->|"Read/Write"| PG
    WORKER -->|"Queue"| REDIS
    INGEST -->|"Insert data"| PG

    PROM -->|"Scrape metrics"| API
    PROM -->|"Scrape"| WORKER
    GRAF -->|"Query"| PROM

    TRAEFIK -.->|"Production only"| API
    SECRETS -.->|"Mounted at\n/run/secrets/"| API
    SECRETS -.->|"Mounted"| WORKER
    LOGGING -.->|"All services"| API

    linkStyle 0,1,2,3 stroke-width:2px
    linkStyle 4,5,6 stroke-width:2px,stroke:#2e7d32
    linkStyle 7,8 stroke-width:2px,stroke:#e65100
    linkStyle 9,10 stroke-width:2px,stroke:#1565c0
    linkStyle 11,12 stroke-width:1px,stroke-dasharray:3 3
    linkStyle 13,14,15,16,17 stroke-width:1px,stroke-dasharray:5 5,stroke:#9e9e9e

    style External fill:#e8f5e9,stroke:#2e7d32
    style DockerNet fill:#e3f2fd,stroke:#1565c0
    style Public fill:#e8eaf6,stroke:#3f51b5
    style Background fill:#f3e5f5,stroke:#7b1fa2
    style Data fill:#fff3e0,stroke:#e65100
    style Monitoring fill:#e0f7fa,stroke:#0097a7
    style ProdExtra fill:#fce4ec,stroke:#c62828
```

در این معماری:
- **مرورگر** ← `http://localhost:3000` ← **Frontend (Next.js)**
- **درخواست‌های API** از طریق Next.js Rewrite Proxy به Backend هدایت می‌شوند
- **Frontend** داخل Docker network می‌تواند `api:8000` را resolve کند
- **Backend** از PostgreSQL, TimescaleDB, Redis, MinIO استفاده می‌کند
- **Worker** و **Scheduler** وظایف پس‌زمینه را مدیریت می‌کنند

---

## ساختار پروژه

```
📦 iran-market-platform
├── 📁 backtesting/          # 🎯 موتور بک‌تست
│   ├── 📁 abm/              # Agent-Based Modeling
│   ├── 📁 analytics/        # موتور تحلیل
│   ├── 📁 engine/           # موتور شبیه‌سازی اصلی
│   ├── 📁 execution/        # شبیه‌ساز اجرا
│   ├── 📁 experiment/       # موتور آزمایش
│   ├── 📁 market/           # موتور بازار و قوانین
│   ├── 📁 microstructure/   # ریزساختار بازار
│   └── 📄 ARCHITECTURE.md   # معماری سیستم (فارسی)
│
├── 📁 config/               # پیکربندی
├── 📁 core/                 # ابزارهای هسته
├── 📁 domain/               # دامنه و enumها
├── 📁 frontend/             # فرانت‌اند Next.js
├── 📁 ingestion/            # جمع‌آوری داده
├── 📁 integrations/         # سرویس‌های یکپارچه
├── 📁 iran_market_data/     # داده‌های بازار ایران
├── 📁 jobs/                 # وظایف زمان‌بندی‌شده
├── 📁 ml/                   # ML Pipeline
├── 📁 models/               # مدل‌های دیتابیس
├── 📁 monitoring/           # مانیتورینگ
├── 📁 migrations/           # مهاجرت دیتابیس
├── 📁 orchestration/        # هماهنگ‌سازی جریان‌ها
├── 📁 pipelines/            # پایپ‌لاین‌های داده
├── 📁 providers/            # تأمین‌کنندگان داده
├── 📁 reports/              # گزارش‌سازی
├── 📁 repositories/         # لایه دسترسی به داده
├── 📁 schemas/              # Pydantic schemaها
├── 📁 scripts/              # اسکریپت‌های کاربردی
├── 📁 services/
│   ├── 📁 chat/              # موتور مکالمه ۲۰ سطحی
│   ├── 📁 smart_money/       # موتور ۹ لایه‌ای Smart Money Scoring
│   ├── 📄 chat_engine.py     # هماهنگ‌کننده مکالمه هوشمند
│   ├── 📄 stock_assistant_service.py # دستیار سهام
│   ├── 📄 unified_assistant_service.py # دستیار یکپارچه
│   ├── 📄 screener_service.py         # غربال‌گر ۵ فاز
│   ├── 📄 smart_money_service.py      # سرویس پول هوشمند
│   ├── 📄 news_service.py             # سرویس اخبار
│   └── 📄 ... (۴۰+ سرویس دیگر)
├── 📁 services/
│   ├── 📁 chat/              # موتور مکالمه ۲۰ سطحی
│   ├── 📁 smart_money/       # موتور ۹ لایه‌ای Smart Money
│   ├── 📄 stock_assistant_service.py # دستیار سهام
│   ├── 📄 unified_assistant_service.py # دستیار یکپارچه
│   ├── 📄 screener_service.py         # غربال‌گر ۵ فاز
│   ├── 📄 smart_money_service.py      # سرویس پول هوشمند
│   └── 📄 ... (۴۰+ سرویس دیگر)
├── 📁 brsapi/               # یکپارچه‌سازی BrsApi.ir
├── 📁 storage/              # مدیریت فایل
├── 📁 tests/                # تست‌ها
│
├── 📄 main.py               # نقطه ورود API
├── 📄 docker-compose.yml    # سرویس‌های Docker
├── 📄 pyproject.toml        # پیکربندی پروژه
├── 📄 Makefile              # دستورات کاربردی
└── 📄 README.md             # این فایل
```

---

## راه‌اندازی سریع

### پیش‌نیازها
- **Python 3.11+**
- **PostgreSQL 16** (یا Docker)
- **Redis 7** (یا Docker)
- **MinIO** (یا Docker)

### ۱. نصب وابستگی‌ها

```bash
# نصب وابستگی‌های اصلی
pip install -r requirements.txt

# (اختیاری) نصب وابستگی‌های توسعه
pip install -r requirements-dev.txt

# (اختیاری) نصب ML dependencies
pip install -e ".[ml]"
```

### ۲. تنظیم محیط

```bash
cp .env.example .env
# .env را با مقادیر مناسب ویرایش کنید
```

### ۳. اجرای مهاجرت دیتابیس

```bash
alembic upgrade head
```

### ۴. اجرای سرور توسعه

```bash
# API اصلی
python main.py

# یا مستقیم با uvicorn
uvicorn apps.api.app:app --reload --host 0.0.0.0 --port 8000

# یا با Makefile
make dev
```

---

## استفاده با Docker

### اجرای سریع

```bash
# ساخت و اجرای همه سرویس‌ها
docker compose up --build -d

# مشاهده لاگ‌ها
docker compose logs -f
```

### سرویس‌های Docker

| سرویس | پورت | توضیح |
|-------|------|-------|
| **API (FastAPI)** | `8000` | سرویس اصلی REST API |
| **Admin Panel** | `8001` | پنل مدیریت |
| **Frontend (Next.js)** | `3000` | واسط کاربری تحت وب |
| **PostgreSQL** | `5432` | دیتابیس اصلی |
| **TimescaleDB** | `5433` | داده‌های زمانی |
| **MinIO** | `9000` (API) / `9001` (Console) | ذخیره‌سازی آبجکت |
| **Redis** | `6379` | کش و صف پیام |
| **Worker** | — | پردازش پس‌زمینه |
| **Scheduler** | — | زمان‌بندی وظایف |
| **Ingestion** | — | جمع‌آوری خودکار داده |
| **Prometheus** | `9090` | متریک |
| **Grafana** | `3001` | داشبورد مانیتورینگ |

### دستورات کاربردی Docker

```bash
make docker-up      # ساخت و اجرا
make docker-build   # ساخت imageها
make docker-down    # توقف و حذف volumeها
make docker-logs    # مشاهده لاگ‌ها
```

---

## فرانت‌اند Next.js

### نمای کلی

فرانت‌اند با **Next.js 16**, **React 19**, **Tailwind CSS v4** و **Recharts** ساخته شده است.
همه درخواست‌های API از طریق Next.js Rewrite Proxy عبور می‌کنند (هرگز مستقیم به Backend).

### ویژگی‌ها

- **۲۵ صفحه** شامل داشبورد، تحلیل، بک‌تست، پرتفوی، اخبار، کدال، تنظیمات
- **نمودارهای Recharts**: Area, Bar, Pie (Donut), Candle (سفارشی)
- **نمودار کندلاستیک** با Custom Shape و نوار حجم
- **تحلیل تکنیکال** با RSI, MACD, MA, Bollinger Bands
- **حالت تاریک** (Dark Mode)
- **واکنش‌گرا** (Responsive)
- **RTL کامل** برای زبان فارسی
- **داده‌های Mock** برای نمایش آفلاین

### کامپوننت‌های نمودار

| کامپوننت | توضیح |
|----------|---------|
| `AreaChartCard` | نمودار مساحت با گرادیان رنگی و Tooltip فارسی |
| `BarChartCard` | نمودار میله‌ای با رنگ‌بندی مثبت/منفی |
| `PieChartCard` | نمودار دوناتی با Legend سفارشی |
| `CandleChartCard` | کندلاستیک با Custom Shape, نوار حجم, اندیکاتورها |

### صفحات داشبورد

| مسیر | صفحه | توضیح |
|------|-------|---------|
| `/` | **داشبورد** | شاخص کل، حجم معاملات، ترکیب صنایع، احساسات |
| `/markets` | **بازارها** | وضعیت لحظه‌ای بازار |
| `/analysis` | **تحلیل** | تحلیل تکنیکال، بنیادی، احساسات، امواج الیوت |
| `/news` | **اخبار** | اخبار و اطلاعیه‌ها |
| `/portfolio` | **پرتفوی** | مدیریت سبد سهام |
| `/backtest` | **بک‌تست** | اجرای استراتژی‌های معاملاتی |
| `/alerts` | **هشدارها** | هشدارهای قیمتی |
| `/signals` | **سیگنال‌ها** | سیگنال‌های معاملاتی |
| `/settings` | **تنظیمات** | پیکربندی حساب |

### راه‌اندازی فرانت‌اند

```bash
# نصب وابستگی‌ها
cd frontend
npm install --no-audit --no-fund

# توسعه با hot-reload
npm run dev

# بیلد تولید
npm run build

# اجرای بیلد شده
npm start
```

### معماری Proxy (API Gateway)

```mermaid
flowchart LR
    subgraph Client_Side["🌐 سمت کلاینت (مرورگر)"]
        BROWSER["مرورگر کاربر\nReact + TanStack Query\nfetch('/api/v1/health')\n• API_URL مخفی از مرورگر\n• فقط path نسبی دیده می‌شود\n• کوکی‌ها خودکار ارسال می‌شوند"]
    end

    subgraph NextJS["⚡ Next.js Server (Frontend)\nport 3000"]
        REWRITE["Rewrite Proxy\nnext.config.ts\nasync rewrites()\nsource: /api/v1/:path*\ndestination: {API_URL}/api/v1/:path*"]
        SSR["SSR Pages\nServer Components"]
        STATIC["Static Assets\nCSS, JS, Images"]
        ENV_NOTE["API_URL:\n• Docker: http://backend:8000\n• Dev: http://localhost:8000\n(مخفی از مرورگر)"]
    end

    subgraph Middleware["🛡️ API Middleware Chain\nport 8000"]
        CORS["CORS Middleware\nمنشأهای مجاز: settings.cors_origins"]
        TIMING["TimingMiddleware\nزمان پاسخ → X-Response-Time-Ms"]
        LOGGING["LoggingMiddleware\nMethod, Path, Status Code"]
        RATE_LIMIT["RateLimitMiddleware\nمحدودیت: {max_calls}/min\nبر اساس IP + مسیر"]
    end

    subgraph Backend["🔌 FastAPI Backend"]
        ROUTER["Router\n/api/v1/*"]
        ERROR_HANDLER["Error Handler\nUnified Error Responses"]
        LIFESPAN["Lifespan Events\n• Startup: DB, Cache, ML, Scheduler\n• Shutdown: Cleanup"]
        BRAPI_SYNC["Startup Tasks:\n• BrsApi Full Sync\n• News Fetch\n• Scheduler Start"]
    end

    subgraph Services["📦 Backend Services"]
        HEALTH["/health· /health/ready\n/health/live · /health/full"]
        MARKET["/market/overview\n/market/gainers\n/market/heatmap"]
        SYMBOLS["/instruments\n/instruments/search"]
        QUOTES["/quotes\n/trades\n/orderbooks"]
        ANALYSIS["/analysis\n/signals\n/indicators"]
        SCREENER["/screener\n/smart-money\n/recommendations"]
        CHAT["/chat\n/chat/feedback\n/chat/stats"]
        CODAL["/codal\n/news\n/fundamental"]
        BACKTEST["/backtests\n/ml\n/compose"]
        BRSAPI["/brsapi/commodities\n/brsapi/crypto\n/brsapi/gold-coin"]
        MORE["... 15+ more routers\n  (total 35+ groups)"]
    end

    subgraph Infrastructure["🏗️ زیرساخت"]
        PG[("🐘 PostgreSQL\n+ TimescaleDB")]
        REDIS["🔄 Redis\nCache + Queue"]
        MINIO["📦 MinIO\nS3 Storage"]
    end

    BROWSER -->|"fetch('/api/v1/*')"| REWRITE
    REWRITE -->|"Proxy to backend"| CORS
    REWRITE --> STATIC
    REWRITE --> SSR
    CORS --> TIMING
    TIMING --> LOGGING
    LOGGING --> RATE_LIMIT
    RATE_LIMIT --> ROUTER
    ROUTER --> ERROR_HANDLER
    ROUTER --> LIFESPAN
    LIFESPAN --> BRAPI_SYNC
    ROUTER --> Services
    Services --> PG & REDIS & MINIO

    BROWSER -.->|"Swagger/ReDoc\n(مستقیم)"| CORS

    style Client_Side fill:#e3f2fd,stroke:#1565c0
    style NextJS fill:#e8f5e9,stroke:#2e7d32
    style Middleware fill:#fce4ec,stroke:#c62828
    style Backend fill:#f3e5f5,stroke:#7b1fa2
    style Services fill:#fff3e0,stroke:#e65100
    style Infrastructure fill:#e0f7fa,stroke:#0097a7
```

**جریان درخواست:**

```text
🔹 Development (محلی):
   مرورگر → fetch("/api/v1/health") → Next.js (3000)
       → Rewrite: http://localhost:8000/api/v1/health
       → FastAPI (8000) → PostgreSQL/Redis

🔹 Docker (تولید):
   مرورگر → fetch("/api/v1/health") → Next.js (3000)
       → Rewrite: http://backend:8000/api/v1/health
       → FastAPI (backend:8000) → PostgreSQL/Redis

🔹 Swagger/ReDoc (مستقیم):
   مرورگر → http://localhost:8000/docs → FastAPI (مستقیم)
```

**نکات امنیتی:**

- **API_URL** یک متغیر `NEXT_PUBLIC_*` نیست — فقط سمت سرور Next.js در دسترس است
- کوکی‌ها به صورت خودکار از طریق Proxy عبور می‌کنند
- همه درخواست‌های API از یک origin واحد می‌آیند (بدون CORS در Production)
- در Docker، `backend:8000` از طریق Docker DNS resolve می‌شود
- مستندات Swagger/ReDoc به صورت مستقیم (بدون Proxy) در دسترس هستند

---

## CI/CD Pipeline

### GitHub Actions

| Workflow | ماشه (Trigger) | کارها |
|----------|---------------|--------|
| **CI** | Push/PR به `main`, `develop` | Lint, Test, Build & Push Docker Images |
| **Release** | Push تگ `v*.*.*` | Build & Push با Semver Tags, GitHub Release, Deploy |

### CI (ci.yml)

اجرای خودکار روی هر push یا pull request:

```yaml
# ── 1. Lint & Typecheck ────────
- ruff (Python linter)
- mypy (Python type checker)
- hadolint (Dockerfile lint)

# ── 2. Backend Tests ───────────
- pytest با PostgreSQL و Redis service containers
- Code coverage → Codecov

# ── 3. Docker Build & Push ─────
- 4 imageها: api, frontend, worker, admin
- Cache: GitHub Actions Cache (type=gha)
- Security: Trivy vulnerability scan
- Registry: ghcr.io (GitHub Container Registry)
```

آدرس تصاویر Docker (هر commit به `main`):

```
ghcr.io/OWNER/REPO/api:{sha,latest}
ghcr.io/OWNER/REPO/frontend:{sha,latest}
ghcr.io/OWNER/REPO/worker:{sha,latest}
ghcr.io/OWNER/REPO/admin:{sha,latest}
```

### Release (release.yml)

اجرا با Push تگ Semantic Version:

```bash
git tag v1.2.3
git push origin v1.2.3
```

- **Validate**: بررسی Semver Tag
- **Build**: ۵ image با تگ‌های `{version}`, `{major.minor}`, `{major}`
- **Release**: GitHub Release با Auto-Changelog
- **Deploy**: (دستی) استقرار روی Production از طریق SSH

### GitHub Secrets مورد نیاز

| Secret | توضیح |
|--------|---------|
| `GITHUB_TOKEN` | خودکار (Push به ghcr.io) |
| `DEPLOY_SSH_KEY` | کلید SSH برای Production |
| `DEPLOY_HOST_KEY` | Host Key سرور |
| `DEPLOY_USER` | نام کاربری SSH |
| `DEPLOY_HOST` | IP/دامنه سرور |

---

## سیستم بک‌تست

```mermaid
flowchart TB
    subgraph DataLayer["📂 Data Layer"]
        LAKE["DataLake (ABC)\nload_chunk() · get_instruments()\nget_available_markets()"]
        INMEM["InMemoryDataLake\nadd_records() · chunk_size\n→ Parquet / Arrow / InMemory"]
        CHUNK["DataChunk\nmarket_id · instrument_ids\nrecords · start/end_time"]
    end

    subgraph EventPipeline["🔨 Event Pipeline"]
        BUILDER["EventBuilder\nfrom_raw() → MarketEvent\nbuild_trade() · build_quote()\nbuild_auction() · build_session()\nbuild_corporate_action()"]
        EVENTS["MarketEvent Types:\n• TRADE · QUOTE · AUCTION\n• SESSION_START/END\n• STATUS_CHANGE\n• CORPORATE_ACTION\n• ORDERBOOK_SNAPSHOT"]
        TIMELINE["UnifiedTimeline\nSorted by (timestamp, priority)\nadd_event() · stream(batch)\nfilter_by_instrument/market/type\nget_stats() → TimelineStats"]
    end

    subgraph ReplayCore["🎯 Replay Engine (هسته اصلی)"]
        CLOCK["Clock\njump_to(event.timestamp)\nnow() · tick()\nlisteners"]
        R_ENGINE["ReplayEngine\nrun() → BacktestResult\n• مدیریت event loop\n• chunk loading از data lake\n• dispatch به sub-engines\n• پشتیبانی 100M+ رویداد"]
        EVENT_BUS["EventBus (Pub/Sub)\nsubscribe(event_type, handler)\npublish(event) · clear()\nmax_history=1000"]
    end

    subgraph MarketState["📊 Market & State Management"]
        M_ENGINE["MarketEngine\nInstrumentState per symbol:\nbest_bid/ask · last_trade\nvolume · open/high/low/close\nsession_state · price_limits\nqueue_state"]
        M_STATE["MarketState (Read-only)\nof(instrument_id) → MarketSnapshot\nall() · instrument_ids()\n\nایمن برای استراتژی‌ها"]
        RULES["MarketRuleEngine\nMarketRuleSet per market:\n• SessionRules (open/close)\n• PriceLimitRules (±5%, 3-1% tiered)\n• TickSizeRules\n• AuctionRules\n• OrderValidationRules\n\n8 بازار: TSE · IFB · Base\nETF · Bonds · Derivatives\nIME · Energy"]
    end

    subgraph Microstructure["🔬 Microstructure Engine"]
        QUEUE["QueueState\nbid/ask queue volumes\norder position tracking\nP(fill) = 1 - e^(-λV)"]
        IMPACT["ImpactModel\nη × (Q/ADV)^α\nقانون جذر"]
        CANCEL["CancelModel\nتخمین نرخ کنسل"]
        ARRIVAL["OrderArrivalModel\nورود سفارشات جدید"]
        LATENCY["LatencyModel\nتأخیر شبکه"]
        AUCTION["AuctionEngine\nحراج بازگشایی/پایانی/نوسان"]
        HIDDEN["HiddenLiquidityModel\nنقدینگی پنهان"]
        MS_ENGINE["MicrostructureEngine\nprocess_event()"]
    end

    subgraph Execution["⚡ Execution & Fill"]
        FILL_SIM["FillSimulator\nmarket order → match immediately\nlimit order → add to queue\npartial fill support"]
        LVL3_BOOK["Level3OrderBook\nqueue position tracking\nexecute_market_order()\nprocess_limit_order()"]
        EXEC_SIM["ExecutionSimulator\nslippage · commission\n→ FillEvent"]
        BROKER["Broker\nsubmit_order()\ncommission · slippage · tax"]
    end

    subgraph Strategy["🧠 Strategy Engine"]
        ST_BASE["BaseStrategy\non_start() · on_bar(bar)\non_event(event) → Order[]\non_fill(fill) · on_end()"]
        ST_ENGINE["StrategyEngine\nadd_strategy(IStrategy)\nmulti-strategy support\ncontext + lifecycle hooks"]
        ST_CTX["StrategyContext\nmarket_engine · portfolio\norder_api · clock"]
    end

    subgraph Risk["🛡️ Risk Controls"]
        SL["StopLoss\nحد ضرر"]
        TP["TakeProfit\nحد سود"]
        DD["DrawdownControl\nکنترل افت سرمایه"]
    end

    subgraph Portfolio["💼 Portfolio Management"]
        PM["PortfolioManager\ncash · positions · NAV\nupdate_fill()\nmark_to_market()\nget_nav()"]
        PORT_SIM["PortfolioBacktestSimulator\nچند نماد هم‌زمان\nallocation · rebalancing"]
    end

    subgraph ABM["🤖 Agent-Based Modeling"]
        MM["MarketMaker\n• قیمت دوطرفه\n• مدیریت موجودی\n• اسپرد پویا"]
        NT["NoiseTrader\n• سفارش تصادفی\n• خرید/فروش تصادفی\n• حجم تصادفی"]
        TF["TrendFollower\n• دنبال‌کننده روند\n• lookback analysis"]
        MR["MeanReversionAgent\n• Z-score\n• بازگشت به میانگین"]
        SIM["Simulation (ABM)\nrun(n_steps)\n→ Agent PnLs · Final Price"]
    end

    subgraph Analytics["📈 Analytics & Experiments"]
        ANALYTICS["AnalyticsEngine\ncompute(result)\n→ CAGR · Sharpe · Sortino\n→ MaxDD · WinRate · ProfitFactor"]
        GRID["GridSearch\nجستجوی ترکیبی"]
        WF["WalkForward\nپنجره متوالی"]
        MC["MonteCarlo\nشبیه‌سازی تصادفی"]
    end

    subgraph Output["📤 Backtest Result"]
        RESULT["BacktestResult\nstrategy_name · total_return\nsharpe_ratio · win_rate\nmax_drawdown · total_trades\nequity_curve · fills\nmetadata"]
    end

    INMEM -.-> LAKE
    LAKE --> CHUNK
    CHUNK --> BUILDER
    BUILDER --> EVENTS
    EVENTS --> TIMELINE
    TIMELINE --> R_ENGINE
    R_ENGINE --> CLOCK
    R_ENGINE --> EVENT_BUS
    R_ENGINE --> M_ENGINE
    R_ENGINE --> FILL_SIM
    R_ENGINE --> PM
    R_ENGINE --> SL & TP & DD

    M_ENGINE --> M_STATE
    M_ENGINE --> RULES
    M_ENGINE --> MS_ENGINE

    MS_ENGINE --> QUEUE & IMPACT & CANCEL & ARRIVAL & LATENCY & AUCTION & HIDDEN

    EVENT_BUS --> ST_ENGINE
    ST_ENGINE --> ST_BASE
    ST_ENGINE --> ST_CTX
    ST_BASE --> LVL3_BOOK
    LVL3_BOOK --> FILL_SIM
    FILL_SIM --> EXEC_SIM
    EXEC_SIM --> BROKER
    BROKER --> PM

    PM --> PORT_SIM
    SL & TP & DD --> PM

    SIM --> MM & NT & TF & MR

    PM --> ANALYTICS
    ANALYTICS --> GRID & WF & MC

    ANALYTICS --> RESULT
    PM --> RESULT

    style DataLayer fill:#e3f2fd,stroke:#1565c0
    style EventPipeline fill:#e8eaf6,stroke:#3f51b5
    style ReplayCore fill:#f3e5f5,stroke:#7b1fa2
    style MarketState fill:#e0f7fa,stroke:#0097a7
    style Microstructure fill:#fce4ec,stroke:#c62828
    style Execution fill:#e8f5e9,stroke:#2e7d32
    style Strategy fill:#fff3e0,stroke:#e65100
    style Risk fill:#f5f5f5,stroke:#616161
    style Portfolio fill:#e0f7fa,stroke:#00695c
    style ABM fill:#f3e5f5,stroke:#4a148c
    style Analytics fill:#e8eaf6,stroke:#283593
    style Output fill:#e8f5e9,stroke:#1b5e20
```

### BacktestSimulator (نسخه کلاسیک)

موتور بک‌تست مبتنی بر `ohlcv` بار:

```python
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def on_bar(self, bar: dict) -> list[OrderEvent]:
        if bar["close"] > bar["sma_20"]:
            return [OrderEvent(instrument_id="IRAN123", ...)]
        return []

async def run():
    simulator = BacktestSimulator()
    result = await simulator.run(
        strategy=MyStrategy(),
        initial_capital=1_000_000_000,
        data=historical_bars,
    )
    print(f"Return: {result.data.total_return_pct:.2f}%")
```

### ReplayEngine (نسخه پیشرفته)

موتور بازپخش رویدادمحور با پشتیبانی از ریزساختار:

```python
from datetime import datetime
from backtesting.engine.replay_engine import ReplayEngine
from backtesting.engine.data_layer import InMemoryDataLake

# بارگذاری داده
data_lake = InMemoryDataLake()
data_lake.add_records("tse", historical_events)

# ساخت موتور
engine = ReplayEngine(data_lake=data_lake)

# اجرا
result = await engine.run(
    strategy=MyStrategy(),
    initial_capital=1_000_000_000,
    market_ids=["tse"],
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 12, 31),
)
```

### خروجی بک‌تست

```python
@dataclass
class BacktestResult:
    strategy_name: str
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    total_trades: int
    equity_curve: list[EquityPoint]
    trades: list[FillEvent]
    metadata: dict
```

---

## Agent-Based Modeling (ABM)

شبیه‌سازی عامل‌محور برای مدل‌سازی رفتار معامله‌گران در بازار.

### عامل‌ها

#### MarketMaker
بازارگردان با مدیریت موجودی:
- قیمت‌گذاری دوطرفه با اسپرد پویا
- تنظیم قیمت بر اساس موجودی (inventory adjustment)
- ارائه نقدینگی در هر دو سمت بازار

#### NoiseTrader
معامله‌گر تصادفی:
- سفارشات تصادفی خرید/فروش
- ترکیبی از سفارشات محدود و بازار
- حجم تصادفی

#### TrendFollower
دنبال‌کننده روند:
- تحلیل روند با lookback
- خرید در روند صعودی، فروش در روند نزولی
- آستانه ورود قابل تنظیم

#### MeanReversionAgent
بازگشت به میانگین:
- محاسبه Z-score
- فروش در گرانی، خرید در ارزانی
- انحراف معیار قابل تنظیم

### اجرای شبیه‌سازی

```python
from backtesting.abm import Simulation, MarketMaker, NoiseTrader
from backtesting.abm.environment import MarketEnvironment

sim = Simulation(random_seed=42)
sim.add_agent(MarketMaker(agent_id="mm1"))
sim.add_agent(NoiseTrader(agent_id="nt1"))
sim.add_agents([
    TrendFollower(agent_id="tf1"),
    MeanReversionAgent(agent_id="mr1"),
])

result = sim.run(n_steps=10000)
print(f"Final price: {result.final_mid}")
print(f"Total trades: {result.total_trades}")
print(f"Agent PnLs: {result.agent_pnls}")
```

---

## ریزساختار بازار

### اجزا

| مؤلفه | توضیح |
|--------|---------|
| **QueueState** | شبیه‌سازی صف سفارشات با حجم و موقعیت |
| **ImpactModel** | مدل ایمپکت قیمت (قانون جذر: `η × (Q/ADV)^α`) |
| **CancelModel** | تخمین نرخ کنسل شدن سفارشات |
| **OrderArrivalModel** | شبیه‌سازی ورود سفارشات جدید |
| **LatencyModel** | شبیه‌سازی تأخیر شبکه |
| **AuctionEngine** | محاسبه قیمت تسویه حراج (بازگشایی، پایانی، نوسان) |
| **HiddenLiquidityModel** | برآورد نقدینگی پنهان |

### کالیبراسیون

```python
from backtesting.microstructure import MicrostructureCalibrator

calibrator = MicrostructureCalibrator()
params = calibrator.calibrate_from_events(
    symbol="فولاد",
    quotes=historical_quotes,
    trades=historical_trades,
)
print(f"Trade rate: {params.trade_rate:.2f}/min")
print(f"Impact η: {params.impact_eta:.4f}")
print(f"Impact α: {params.impact_alpha:.4f}")
print(f"Avg queue: {params.avg_queue:,}")
```

### Queue Simulation

```python
from backtesting.execution.queue_simulation import QueueSimulation

qs = QueueSimulation(base_cancel_rate=0.05, base_trade_rate=0.3)

# اضافه کردن سفارش به صف
order = qs.add_order("IRAN123", is_buy=True, price=15000, quantity=10000)

# شبیه‌سازی یک گام
fills = qs.simulate_step("IRAN123", trade_volume=5000, trade_price=15000)

buy_depth, sell_depth = qs.get_queue_depth("IRAN123")
```

---

## موتور تحلیل

محاسبه معیارهای عملکرد از نتیجه بک‌تست:

```python
from backtesting.analytics import AnalyticsEngine

analytics = AnalyticsEngine()
ar = analytics.compute(result, trading_days=252)

print(f"CAGR: {ar.cagr:.2f}%")
print(f"Sharpe: {ar.sharpe_ratio:.2f}")
print(f"Sortino: {ar.sortino_ratio:.2f}")
print(f"Max DD: {ar.max_drawdown_pct:.2f}%")
print(f"Win Rate: {ar.win_rate:.1f}%")
print(f"Profit Factor: {ar.profit_factor:.2f}")
```

---

## موتور آزمایش

### Grid Search

```python
from backtesting.experiment import ExperimentEngine, GridSearch

exp_engine = ExperimentEngine()
grid = GridSearch(exp_engine)

runs = grid.generate(
    strategy_name="SmaCross",
    param_grid={
        "fast_period": [5, 10, 20],
        "slow_period": [50, 100, 200],
    },
)
```

### Walk-Forward

```python
from backtesting.experiment import WalkForward

wf = WalkForward(exp_engine, n_windows=5, train_pct=0.7)
runs = wf.generate(
    strategy_name="MyStrategy",
    base_params={"lookback": 20},
)
```

### Monte Carlo

```python
from backtesting.experiment import MonteCarlo

mc = MonteCarlo(exp_engine, n_simulations=1000)
runs = mc.generate(
    strategy_name="MyStrategy",
    param_distributions={
        "threshold": (0.001, 0.05),
        "lookback": (10, 100),
    },
)
```

---

## یکپارچه‌سازی BrsApi.ir 🗄️

لایه یکپارچه‌سازی سرویس BrsApi.ir برای دریافت داده‌های بورس تهران (TSETMC)،
کدال (CODAL)، بورس کالا (IME)، بازارهای جهانی، طلا و ارز، رمزارزها.

```mermaid
flowchart TB
    subgraph External["🌐 External API"]
        BRSAPI["BrsApi.ir\nREST API Provider"]
    end

    subgraph Client["📡 Client Layer"]
        CLIENT["BrsApiClient\n(httpx AsyncClient)"]
        RL["RateLimiter\n• 10,000/day global\n• 500/5min sliding\n• Per-category token bucket"]
        CB["CircuitBreaker\n• 5 failure threshold\n• 30s recovery timeout"]
        RETRY["Retry with Backoff\n• Exponential backoff\n• 502/503 retry\n• Timeout handling"]
    end

    subgraph Parsers["🧩 Parsers (6 classes)"]
        TP["TsetmcParser\nSymbols, Index, NAV,\nTrades, History, Shareholders"]
        CP["CodalParser\nAnnouncements\n& Disclosures"]
        IP["ImeParser\nFutures, Options,\nFunds, Certificates"]
        GP["GoldCurrencyProParser\nGold, Currency, Crypto,\n24h History, Daily OHLC"]
        COMP["CommodityParser\nPrecious Metals,\nBase Metals, Energy"]
        CRYPTO["CryptoParser\nCryptocurrencies\nUSD/IRR prices"]
    end

    subgraph Sync["🔄 Sync Orchestrator"]
        SYNC["BrsApiSyncService\nFetch → Parse → Store → Log"]
        DEDUP["Dedup Engine\nSkip if recently synced"]
    end

    subgraph Storage["💾 Storage Layer"]
        REPOS["Repositories\nBulkUpsertRepository\nSyncLogRepository\nRawPayloadRepository"]
        MODELS["26+ SQLAlchemy Models\n(brsapi_* tables)"]
        DB[("🗄️ PostgreSQL\n+ TimescaleDB")]
    end

    subgraph Scheduling["⏰ APScheduler Jobs"]
        J1["brsapi_all_symbols · 5m"]
        J2["brsapi_index · 5m"]
        J3["brsapi_gold_currency_pro · 5m"]
        J4["brsapi_codal · 15m"]
        J5["brsapi_commodities · 5m"]
        J6["brsapi_crypto · 5m"]
        J7["brsapi_ime_futures · 5m"]
        J8["... 11 more jobs"]
        TRIG["▶️ Execute"]
        J1 & J2 & J3 & J4 & J5 & J6 & J7 & J8 --> TRIG
    end

    subgraph API["🔌 FastAPI Endpoints"]
        API_MANAGE["/brsapi/manage/*\nSync, Download, Status"]
        API_DATA["/brsapi/commodities\n/brsapi/crypto\n/brsapi/gold-coin\n/brsapi/currency\n/brsapi/history/*"]
        API_HEALTH["/brsapi/health"]
    end

    BRSAPI -.->|"HTTPS"| CLIENT
    CLIENT --> RL & CB & RETRY
    RL & CB & RETRY --> SYNC
    SYNC --> DEDUP
    DEDUP -->|"Parse"| Parsers
    Parsers -->|"Store"| REPOS
    REPOS --> MODELS
    MODELS --> DB
    TRIG -->|"Run"| SYNC
    API_MANAGE -->|"Trigger"| SYNC
    API_DATA -->|"Query"| DB
    API_HEALTH -->|"Check"| CLIENT

    style BRSAPI fill:#e1f5fe,stroke:#0288d1
    style CLIENT fill:#e3f2fd,stroke:#1565c0
    style DB fill:#fff3e0,stroke:#e65100
    style Scheduling fill:#f3e5f5,stroke:#7b1fa2
    style API fill:#e8f5e9,stroke:#2e7d32
    style Sync fill:#fce4ec,stroke:#c62828
```

### Endpointهای پشتیبانی‌شده (۲۶+)

| دسته | Endpoint | توضیح |
|------|----------|-------|
| **TSETMC** | `AllSymbols.php` | لیست همه نمادها |
| | `Symbol.php` | جزئیات نماد |
| | `Candlestick.php` | داده‌های کندلاستیک |
| | `History.php` (type=0) | تاریخچه قیمت روزانه |
| | `History.php` (type=1) | تاریخچه حقیقی/حقوقی |
| | `Transaction.php` | معاملات درون‌روز |
| | `Shareholder.php` | ترکیب سهامداران |
| | `Index.php` | شاخص‌های بازار |
| | `Option.php` | قراردادهای آپشن |
| | `Nav.php` | ارزش خالص دارایی صندوق‌ها |
| **CODAL** | `Announcement.php` | اطلاعیه‌های کدال |
| **IME** | `Physical.php` | معاملات فیزیکی |
| | `Fund.php` | صندوق‌های کالایی |
| | `Certificate.php` | گواهی‌های سپرده |
| | `Option.php` | آپشن‌های کالایی |
| | `Futures.php` | قراردادهای آتی |
| **Market** | `Gold_Currency.php` | طلا و ارز (رایگان) |
| | `Gold_Currency_Pro.php` | طلا و ارز حرفه‌ای (Pro) |
| | `Cryptocurrency.php` | رمزارزها |
| | `Commodity.php` | کالاهای جهانی |

### معماری

```text
📦 brsapi/
├── 📄 client.py             # کلاینت HTTP ناهمزمان (httpx) با circuit breaker
├── 📄 config.py             # تعریف endpointها، نرخ محدودیت، تنظیمات
├── 📄 rate_limiter.py       # محدودکننده نرخ (token bucket)
├── 📁 models/               # ۲۶ مدل ORM (SQLAlchemy)
│   ├── 📄 base.py           # Base, RawPayloadModel, SyncLogModel
│   ├── 📄 tsetmc.py         # نمادها، شاخص، NAV، معاملات، تاریخچه
│   ├── 📄 codal.py          # اطلاعیه‌های کدال
│   ├── 📄 ime.py            # داده‌های بورس کالا
│   ├── 📄 commodity.py      # طلا، ارز، کامودیتی (شامل Gold_Currency_Pro)
│   └── 📄 crypto.py         # رمزارزها
├── 📁 parsers/              # تجزیه‌گر پاسخ JSON
│   ├── 📄 tsetmc.py
│   ├── 📄 codal.py
│   ├── 📄 commodity.py      # شامل GoldCurrencyParser و GoldCurrencyProParser
│   ├── 📄 crypto.py
│   └── 📄 ime.py
├── 📁 services/
│   ├── 📄 sync_service.py   # همگام‌سازی داده با دیتابیس
│   └── 📄 query_service.py  # جستجوی داده‌های ذخیره‌شده
├── 📁 jobs/
│   └── 📄 registry.py       # وظایف زمان‌بندی APScheduler
├── 📁 repositories/
│   ├── 📄 base.py           # BulkUpsertRepository, SyncLogRepository
│   └── 📄 __init__.py
└── 📁 migrations/           # مهاجرت دیتابیس
```

### کلاینت (client.py)

```python
from brsapi.client import BrsApiClient, get_client

# دریافت کلاینت singleton
client = await get_client()

# واکشی همه نمادها
result = await client.fetch(BrsApiEndpoints.ALL_SYMBOLS)
if result.success:
    data = result.value.data  # داده JSON解析شده

# واکشی جزئیات نماد
result = await client.fetch(
    BrsApiEndpoints.SYMBOL_DETAIL,
    params={"l18": "فولاد"},
)

await client.stop()
```

ویژگی‌های کلاینت:
- **محدودیت نرخ (Rate Limiting)**: token bucket برای هر دسته (TSETMC: ۳۰ rpm, CODAL: ۲۰ rpm)
- **Circuit Breaker**: محافظت در برابر خطاهای متوالی
- **Retry with Backoff**: تلاش مجدد با تأخیر تصاعدی
- **Raw Payload Audit**: ذخیره payload خام برای بازبینی

### سرویس همگام‌سازی (sync_service.py)

```python
from brsapi.services.sync_service import BrsApiSyncService

svc = BrsApiSyncService(client)

# همگام‌سازی همه نمادها
report = await svc.sync_all_symbols(session)
print(f"{report.items_count} records synced")

# همگام‌سازی Gold & Currency Pro
reports = await svc.sync_gold_currency_pro(session, sections="gold,currency")

# همگام‌سازی یک نماد خاص
report = await svc.sync_history_price(session, "فولاد")
```

### Gold & Currency Pro (Gold_Currency_Pro.php) 🥇

Endpoint حرفه‌ای طلا، ارز و رمزارز با سه حالت (mode) مختلف:

- **Mode 1 — قیمت‌های لحظه‌ای Pro**: `section=gold|currency|cryptocurrency`
- **Mode 2 — تاریخچه ۲۴ ساعته**: `history=1&symbol=XYZ` (تیک‌های درون‌روز)
- **Mode 3 — تاریخچه روزانه OHLC**: `history=2&symbol=XYZ&date_start=...&date_end=...`

#### ویژگی‌های Pro نسبت به نسخه رایگان

| ویژگی | Gold_Currency (رایگان) | Gold_Currency_Pro (حرفه‌ای) |
|--------|----------------------|---------------------------|
| **فیلدهای اضافی** | قیمت، تغییر | `sign`, `url_base_icon`, `path_icon`, `name_en` |
| **تاریخچه ۲۴ساعته** | ❌ | ✅ تیک‌های درون‌روز |
| **تاریخچه روزانه** | ❌ | ✅ OHLC با تاریخ شمسی |
| **نرخ محدودیت** | ۱ req/min | ۶ req/min |
| **آیکون نمادها** | ❌ | ✅ آدرس آیکون اختصاصی |
| **پشتیبانی رمزارز** | محدود | کامل با rank, market cap, volume 24h |

#### پارامترهای endpoint

| پارامتر | اجباری | مقادیر معتبر | توضیح |
|---------|--------|-------------|-------|
| `key` | ✅ | — | API key |
| `section` | ❌ | `gold`, `currency`, `cryptocurrency` | دسته‌بندی (تکی یا comma-separated) |
| `history` | ❌ | `1` (۲۴ساعته), `2` (روزانه) | فعال‌سازی حالت تاریخچه |
| `symbol` | ❌ | — | نماد (برای تاریخچه اجباری) |
| `date_start` | ❌ | YYYY-MM-DD (شمسی) | شروع بازه تاریخچه |
| `date_end` | ❌ | YYYY-MM-DD (شمسی) | پایان بازه تاریخچه |

#### مدل‌های دیتابیس

سه جدول برای ذخیره‌سازی داده‌های Pro:

| جدول | توضیح | فیلدهای اصلی |
|------|-------|-------------|
| `brsapi_gold_currency_pro_prices` | قیمت‌های لحظه‌ای | `section`, `symbol`, `name_en`, `name`, `sign`, `price`, `change_value`, `change_percent`, `url_base_icon`, `path_icon` |
| `brsapi_gold_currency_pro_history_24h` | تیک‌های ۲۴ساعته | `symbol`, `price`, `time`, `date`, `time_unix` |
| `brsapi_gold_currency_pro_daily_history` | OHLC روزانه | `symbol`, `date`, `price_open`, `price_high`, `price_low`, `price_close`, `sign`, `unit`, `url_base_icon` |

#### نمونه پاسخ API (Mode 1 — قیمت طلا)

```json
{
  "successful": true,
  "data": {
    "gold": [
      {
        "symbol": "gold18",
        "name": "طلا ۱۸ عیار",
        "name_en": "Gold 18 Karat",
        "sign": "﷼",
        "price": 4987500,
        "change_value": 12500,
        "change_percent": 0.25,
        "unit": "IRR",
        "date": "1404-04-20",
        "time": "12:30:00",
        "time_unix": 1719563400,
        "url_base_icon": "https://api.brsapi.ir/icon/",
        "path_icon": "gold18.png"
      }
    ],
    "currency": [
      {
        "symbol": "USD",
        "name": "دلار آمریکا",
        "name_en": "US Dollar",
        "sign": "$",
        "price": 585000,
        "change_value": -1500,
        "change_percent": -0.26,
        "unit": "IRR",
        "url_base_icon": "https://api.brsapi.ir/icon/",
        "path_icon": "usd.png"
      }
    ],
    "cryptocurrency": [
      {
        "symbol": "BTC",
        "name": "Bitcoin",
        "sign": "₿",
        "price": 61250.5,
        "price_toman": 3581240000,
        "change_percent": 1.2,
        "market_cap": 1200000000000,
        "volume_24h": 45000000000,
        "rank": 1,
        "url_base_icon": "https://api.brsapi.ir/icon/",
        "path_icon": "btc.png"
      }
    ]
  }
}
```

#### نمونه پاسخ API (Mode 2 — تاریخچه ۲۴ساعته)

```json
{
  "successful": true,
  "data": {
    "symbol": "gold18",
    "history_24h": [
      {"price": 4975000, "time": "09:00:00", "date": "1404-04-20", "time_unix": 1719545400},
      {"price": 4980000, "time": "09:15:00", "date": "1404-04-20", "time_unix": 1719546300},
      {"price": 4987500, "time": "12:30:00", "date": "1404-04-20", "time_unix": 1719563400}
    ]
  }
}
```

#### نمونه پاسخ API (Mode 3 — تاریخچه روزانه OHLC)

```json
{
  "successful": true,
  "data": {
    "symbol": "gold18",
    "history_daily": [
      {
        "date": "1404-04-20",
        "open": 4950000,
        "high": 4990000,
        "low": 4945000,
        "close": 4987500,
        "sign": "﷼",
        "unit": "IRR"
      }
    ]
  }
}
```

#### کلاس Parser (GoldCurrencyProParser)

در `brsapi/parsers/commodity.py`:

| متد | توضیح |
|------|--------|
| `parse_gold(data)` | استخراج داده‌های طلا از پاسخ Pro |
| `parse_currency(data)` | استخراج داده‌های ارز از پاسخ Pro |
| `parse_crypto(data)` | استخراج داده‌های رمزارز از پاسخ Pro |
| `parse_history_24h(data)` | پارس تاریخچه ۲۴ساعته (`history=1`) |
| `parse_daily_history(data)` | پارس تاریخچه روزانه OHLC (`history=2`) |

#### سرویس همگام‌سازی (sync_service.py)

سه متد در `BrsApiSyncService` برای Pro:

```python
# 1. قیمت‌های لحظه‌ای (سه بخش طلا، ارز، رمزارز)
reports = await svc.sync_gold_currency_pro(
    session,
    sections="gold,currency,cryptocurrency"  # یا ترکیب دلخواه
)

# 2. تاریخچه ۲۴ساعته یک نماد
report = await svc.sync_gold_currency_pro_history_24h(
    session,
    symbol="gold18"
)

# 3. تاریخچه روزانه OHLC یک نماد
report = await svc.sync_gold_currency_pro_daily_history(
    session,
    symbol="gold18",
    date_start="1404-01-01",
    date_end="1404-04-20"
)
```

#### استفاده مستقیم با کلاینت

```python
from brsapi.client import get_client
from brsapi.config import BrsApiEndpoints

client = await get_client()

# Mode 1: قیمت لحظه‌ای طلا
result = await client.fetch(
    BrsApiEndpoints.GOLD_CURRENCY_PRO,
    params={"section": "gold"}
)
if result.success:
    gold_price = result.value.data["data"]["gold"]
    for item in gold_price:
        print(f"{item['name']}: {item['price']:,} IRR")

# Mode 2: تاریخچه ۲۴ساعته
result = await client.fetch(
    BrsApiEndpoints.GOLD_CURRENCY_PRO,
    params={"history": "1", "symbol": "USD"}
)

# Mode 3: تاریخچه روزانه
result = await client.fetch(
    BrsApiEndpoints.GOLD_CURRENCY_PRO,
    params={"history": "2", "symbol": "gold18",
            "date_start": "1404-01-01", "date_end": "1404-04-20"}
)

await client.stop()
```

#### نمادهای پشتیبانی‌شده

| بخش | نمادهای اصلی | واحد |
|------|-------------|------|
| **gold** | `gold18` (طلای ۱۸), `gold24` (طلای ۲۴), `gerami` (گرمی), `mesghal` (مثقال), `ons` (انس جهانی), `coin_emami` (سکه امامی), `coin_bahar` (سکه بهار), `coin_1g` (سکه ۱ گرمی), `coin_2g`, `rub` (روبل) | IRR, USD |
| **currency** | `USD`, `EUR`, `GBP`, `AED`, `TRY`, `CNY`, `JPY`, `KRW`, `AUD`, `CAD`, `CHF`, `SEK`, `NOK`, `DKK`, `RUB`, `MYR`, `THB`, `SGD`, `HKD`, `OMR`, `QAR`, `KWD`, `BHD`, `SAR`, `IQD`, `AZN` | IRR |
| **cryptocurrency** | `BTC` (بیت‌کوین), `ETH` (اتریوم), `USDT` (تتر), `BNB`, `XRP`, `ADA`, `SOL`, `DOT`, `DOGE`, `TRX`, `MATIC`, `SHIB`, `DAI`, `LTC`, `BCH`, `ATOM`, `XLM`, `FIL`, `AVAX`, `UNI`, `VET`, `FTM`, `SAND`, `MANA`, `NEAR`, `ALGO`, `FTT`, `ICP`, `EGLD`, `AXS`, `KSM`, `ONE`, `XEC`, `CHZ`, `FLOW`, `MINA`, `ELF`, `KAVA` | USD, IRR |

#### Job زمان‌بندی

در `brsapi/jobs/registry.py` یک job با نام `brsapi_gold_currency_pro`
با بازه `۵ دقیقه` تعریف شده که هر سه بخش (طلا، ارز، رمزارز) را
به‌صورت خودکار همگام‌سازی می‌کند.

### اسکریپت بروزرسانی جامع (brsapi_full_update.py)

اسکریپت `scripts/brsapi_full_update.py` با:
- **محدودیت دوگانه**: ۱۰,۰۰۰ درخواست/روز + ۵۰۰ درخواست/۵دقیقه
- **Auto-create tables**: ایجاد خودکار جدول‌های گمشده
- **خطایابی ۵۰۲**: تلاش مجدد با backoff ۲s, ۴s, ۸s
- **Error Report جامع**: گروه‌بندی خطاها بر اساس نوع و endpoint

```bash
python scripts/brsapi_full_update.py                     # اجرای کامل
python scripts/brsapi_full_update.py --tables symbols     # فقط نمادها
python scripts/brsapi_full_update.py --dry-run --symbols 10
python scripts/brsapi_full_update.py --daily-limit 5000
```

---

## موتور Smart Money (۹ لایه) 🧠

موتور امتیازدهی پول هوشمند (SMC) با ۹ لایه تحلیل و معماری config-driven.

```mermaid
flowchart TB
    subgraph Input["📥 Data Inputs"]
        QUOTE["Quote\nprice, volume, value\navg_buy/sell, real_buy/sell"]
        HIST["History\n30+ days OHLCV"]
        TRADES["Trades\nReal/Legal breakdown\n(optional)"]
        INDEX["Index History\nTSE Index values\n(optional)"]
    end

    subgraph Step0["Step 0: Data Quality Gate 🛡️"]
        DQG["DataQualityGate\n• Required fields check\n• History length ≥ 5 days\n• Staleness < 5 days\n• Price outliers (z > 3.5)\n• Volume anomalies\n• OHLC consistency"]
        DQ_OUT["Decision:\nscore > 0.7 → Full Analysis\nscore 0.3-0.7 → Partial\nscore < 0.3 → ❌ Reject"]
    end

    QUOTE & HIST & TRADES & INDEX --> DQG
    DQG --> DQ_OUT

    subgraph Step1["Step 1: 9-Layer Computation 🧮"]
        L1["📊 Layer 1: PriceVolume\npvs · rvol_n · vtr_n\nclv_n · rec_n · lf_n"]
        L2["📉 Layer 2: Absorption\nabs · dps_n · lss_n\nrmr_n (vs index)"]
        L3["📋 Layer 3: Ownership\nfls · bp_n · nrmf_n\nbc_n · se_n · fd"]
        L4["📐 Layer 4: Compression\ness · rc · atrc · vvd"]
        L5["📈 Layer 5: RelativeStrength\nrrs · rsi3/5/10_n\nrss_n · rds_n"]
        L6["🚀 Layer 6: Breakout\nbrs · rp_n · btf_n\npt · bcp"]
        L7["💪 Layer 7: BuyerPower\nbps · rbp_n · z_rbp_n\nz_vr_n · z_pc_n"]
        L8["🔬 Layer 8: Microstructure\nmcs · vpin_n · abs_n\ndpsv_n · dry_n · sa_n"]
        L9["🎯 Layer 9: BreakoutQuality\nbqs · z_vol_n · clv_n\neff_n · accept_n"]
    end

    DQ_OUT -->|"Full or Partial"| L1 & L2 & L3 & L4 & L5 & L7 & L8
    L1 & L2 & L3 & L4 & L5 & L7 & L8 --> FEAT_POOL["Feature Pool\n(all layers)"]
    FEAT_POOL --> L6 & L9
    FEAT_POOL --> ALL_FEAT["All 9 Layer Features\n60+ normalized features"]
    L6 & L9 --> ALL_FEAT

    subgraph Step2["Step 2: Feature Store 💾"]
        FS["FeatureStore\nCache per symbol\nFeatureVector"]
    end

    ALL_FEAT --> FS

    subgraph Step3_4["Steps 3-4: Composite Scores + Penalties ⚖️"]
        ACC["ACC · Accumulation\nw₁×pvs + w₂×abs + w₃×fls\n+ w₄×bp_n + w₅×ess"]
        ABS["ABS · Absorption (final)\nw₁×abs + w₂×rmr_n\n+ w₃×dps_n + w₄×lss_n"]
        FL["FL · Float Lock\nw₁×ahm_n + w₂×dps_n\n+ w₃×nrmf_n + w₄×fls"]
        BR["BR · Breakout Readiness\nw₁×brs + w₂×rp_n\n+ w₃×bqs + w₄×bcp"]
        SMC_RAW["SMC = w_acc * ACC\n+ w_abs * ABS\n+ w_fl * FL\n+ w_br * BR"]
        PENALTIES["Penalties:\nDR · Distribution Risk\nFBR · Fake Breakout Risk\nDC · Dead Compression"]
        SMC_ADJ["SMC_adj = SMC\n- w_dr*DR - w_fbr*FBR - w_dc*DC\n→ Clamp [0, 1]"]
    end        ALL_FEAT --> ACC & ABS & FL & BR
    ACC & ABS & FL & BR --> SMC_RAW
    ALL_FEAT --> PENALTIES
    SMC_RAW & PENALTIES --> SMC_ADJ

    subgraph Step5["Step 5: Phase Classification 🏷️"]
        PHASE["PhaseEngine\nConfig-driven thresholds\n→ early_accumulation\n→ active_absorption\n→ float_lock\n→ breakout_ready\n→ confirmed_smart_money\n→ neutral"]
    end

    SMC_ADJ --> PHASE

    subgraph Step6["Step 6: Confidence Estimation 📏"]
        CONF["ConfidenceEstimator\nBased on:\n• History days\n• Data quality score\n• Feature variance\n→ confidence (0-1)\n→ level: low/medium/high"]
    end

    DQ_OUT --> CONF
    ALL_FEAT --> CONF

    subgraph Output["📤 Final Output"]
        RESULT["{smc_score, phase, scores, penalties,\n features (60+), meta info}"]
    end

    SMC_ADJ & PHASE & CONF --> RESULT

    style Input fill:#e3f2fd,stroke:#1565c0
    style Step0 fill:#fce4ec,stroke:#c62828
    style Step1 fill:#f3e5f5,stroke:#7b1fa2
    style Step2 fill:#e8f5e9,stroke:#2e7d32
    style Step3_4 fill:#fff3e0,stroke:#e65100
    style Step5 fill:#e0f7fa,stroke:#0097a7
    style Step6 fill:#f5f5f5,stroke:#616161
    style Output fill:#e8eaf6,stroke:#3f51b5
```

### لایه‌های تحلیل

| لایه | ماژول | وظیفه |
|------|--------|--------|
| **۱. قیمت و حجم** | `PriceVolumeLayer` | تحلیل RVOL، موقعیت قیمت، فشار حجم |
| **۲. جذب** | `AbsorptionLayer` | تشخیص جذب عرضه در سطوح کلیدی |
| **۳. مالکیت** | `OwnershipLayer` | قدرت خریدار، جریان پول حقیقی |
| **۴. فشار** | `CompressionLayer` | شناسایی فازهای فشردگی قیمت |
| **۵. قدرت نسبی** | `RelativeStrengthLayer` | مقایسه با شاخص و صنعت |
| **۶. شکست** | `BreakoutLayer` | تشخیص شکست مقاومت/حمایت |
| **۷. قدرت خریدار** | `BuyerPowerLayer` | قدرت خریداران در برابر فروشندگان |
| **۸. ریزساختار** | `MicrostructureLayer` | تحلیل عمق بازار و نقدینگی پنهان |
| **۹. کیفیت شکست** | `BreakoutQualityLayer` | اعتبار سیگنال شکست |

### امتیاز ترکیبی SMC

```
SMC = w_acc × ACC + w_abs × ABS + w_fl × FL + w_br × BR
```

| مؤلفه | توضیح |
|-------|--------|
| **ACC** | Accumulation — انباشت پول هوشمند |
| **ABS** | Absorption — جذب عرضه |
| **FL** | Float Lock — قفل شناوری |
| **BR** | Breakout Readiness — آمادگی شکست |

### فازهای بازار

| فاز | توضیح |
|-----|--------|
| `early_accumulation` | تجمع اولیه |
| `active_absorption` | جذب عرضه فعال |
| `float_lock` | قفل شناوری |
| `breakout_ready` | آماده شکست |
| `confirmed_smart_money` | پول هوشمند تأیید شده |
| `neutral` | خنثی |

### Data Quality Gate

ورودی‌ها قبل از تحلیل از فیلتر کیفیت عبور می‌کنند:
```
quality_score > 0.7 → تحلیل کامل
quality_score 0.3-0.7 → تحلیل ناقص
quality_score < 0.3 → رد و بازگشت نتیجه حداقلی
```

### استفاده

```python
from services.smart_money.scoring_engine import ScoringEngine

engine = ScoringEngine()
result = engine.analyze(
    quote=quote_dict,        # آخرین داده لحظه‌ای
    history=history_list,    # تاریخچه ۳۰ روزه
    index_history=index_px,  # (اختیاری) تاریخچه شاخص
)

smc_score = result["smart_money_score"]      # ۰ تا ۱
phase = result["phase"]                       # فاز فعلی
scores = result["scores"]                     # امتیاز هر لایه
confidence = result["meta"]["confidence"]     # اطمینان
```

---

## موتور مکالمه ۲۰ سطحی (Chat Engine) 🤖

سیستم مکالمه هوشمند با قابلیت تشخیص intent، استخراج موجودیت، مدیریت دیالوگ، تحلیل احساسات، شخصی‌سازی و یادگیری.

```mermaid
flowchart TD
    USER["👤 User\nMessage + user_id"] --> L14

    subgraph L14["Level 14: Sentiment Analysis"]
        SA["SentimentAnalyzer\nPositive / Negative / Neutral"]
    end

    L14 --> L7

    subgraph L7["Level 7: Slot Filling"]
        IC["IntentClassifier\n(50+ Intents, NaiveBayes)"]
        EE["EntityExtractor\nSymbols · Prices\nConditions · Alerts"]
    end

    L7 --> L8

    subgraph L8["Level 8: Context Management"]
        DM["DialogManager\nConversation History\nCross-turn Symbol Resolution"]
    end

    L8 --> L15

    subgraph L15["Level 15: Personalization"]
        PER["Personalizer + ProfileStore\nFavorite Symbols\nPersonalized Suggestions"]
    end

    L15 --> L19

    subgraph L19["Level 19: Learning"]
        LE["LearningEngine\nSuccess Tracking\nFeedback Recording"]
    end

    L19 --> L9

    subgraph L9_20["Level 9-20: Routing & Handlers"]
        CS["CompoundSplitter\nSingle vs Multi-Intent"]
        CS -->|"Single"| ROUTE
        CS -->|"Compound"| MIXED["Level 20:\nMixed Query Handler"]
        ROUTE["Route to Handler"] & MIXED --> HANDLERS

        subgraph HANDLERS["🎯 30+ Intent Handlers"]
            H1["📊 Market\nOverview · Gainers/Losers"]
            H2["📈 Analysis\nSymbol · Analyze All · Find Best"]
            H3["⚖️ Compare\nMulti-Symbol · Ranking"]
            H4["🔍 Screener\nSmart Filter · Dynamic Filter"]
            H5["📰 News\nSymbol · Market · Codal"]
            H6["⭐ Watchlist\nAdd · Remove · List"]
            H7["🔔 Alerts\nPrice · Technical · List"]
            H8["💰 Portfolio\nAdd · Remove · Summary"]
            H9["🏅 Macro\nGold · Currency · Crypto"]
            H10["🧠 ML\nPredict · Train · List"]
            H11["🧪 Backtest\nRun · List · Results"]
            H12["🗺️ Others\nHeatmap · Risk · Signals · Navigation"]
        end
    end

    HANDLERS --> L18

    subgraph L18["Level 18: Suggestions"]
        SG["SuggestionEngine\nContext-aware Follow-ups\n(Max 4 suggestions)"]
    end

    L18 --> RESP

    RESP["📤 Structured Response\ntext + type + data\n+ suggestions + sentiment"]

    style USER fill:#e3f2fd,stroke:#1565c0
    style L14 fill:#e8eaf6,stroke:#3f51b5
    style L7 fill:#f3e5f5,stroke:#7b1fa2
    style L8 fill:#e8f5e9,stroke:#2e7d32
    style L15 fill:#fff3e0,stroke:#e65100
    style L19 fill:#fce4ec,stroke:#c62828
    style L9_20 fill:#f5f5f5,stroke:#616161
    style L18 fill:#e0f7fa,stroke:#0097a7
    style RESP fill:#e8f5e9,stroke:#1b5e20
```

### معماری ۲۰ سطحی

| سطح | مؤلفه | فایل |
|-----|-------|------|
| ۱-۵ | پایه NLP | یکپارچه در ChatEngine |
| ۶ | BERT (اختیاری) | — |
| ۷ | **Slot Filling** | `intent_classifier.py`, `entity_extractor.py` |
| ۸ | **مدیریت متن** (Context) | `dialog_manager.py` |
| ۹ | **تقسیم درخواست مرکب** | `compound_splitter.py` |
| ۱۰ | **فیلتر پویا** | یکپارچه در ChatEngine |
| ۱۱ | **توضیحات** (Explanation) | Explainer (در `ml/models`) |
| ۱۲ | **نمودار** | `chart_generator.py` |
| ۱۳ | **ورودی صوتی** | سمت کلاینت |
| ۱۴ | **تحلیل احساسات** | `sentiment_analyzer.py` |
| ۱۵ | **شخصی‌سازی** | `personalizer.py`, `ProfileStore` |
| ۱۶ | **یکپارچه‌سازی اخبار** | `news_fetcher.py`, `news_analyzer.py`, `news_integration.py` |
| ۱۷ | **مقایسه پیشرفته** | `comparison_engine.py` |
| ۱۸ | **پیشنهادات فعال** | `suggestion_engine.py` |
| ۱۹ | **یادگیری** | `learning_engine.py` |
| ۲۰ | **درخواست‌های مرکب** | `chat_engine.py` + `compound_splitter` |

### Intentهای پشتیبانی‌شده (۵۰+)

```text
greeting, farewell, help,
analyze_symbol, analyze_all, compare_symbols,
market_overview, top_gainers, top_losers,
find_best, find_cheap, find_undervalued,
screener, dynamic_filter,
get_news, get_codal,
macro_data, gold_currency, crypto_prices,
add_watchlist, remove_watchlist, list_watchlist,
add_alert, list_alerts, remove_alert,
portfolio_add, portfolio_remove, portfolio_summary,
run_backtest, list_backtests,
ml_predict, ml_train, ml_list_models,
get_chart, heatmap, risk_overview,
signals, anomalies, navigate,
speech_input, personalize, recommendation,
complex_mixed,
...
```

### استفاده از ChatEngine

```python
from services.chat.chat_engine import ChatEngine

engine = ChatEngine(
    stock_assistant=stock_asst,
    market_service=market_svc,
    brsapi_service=brsapi_svc,
)

result = await engine.process(
    user_id="user_123",
    message="فولاد رو تحلیل کن و اخبارش رو بده",
)

print(result["text"])        # متن پاسخ
print(result["type"])        # نوع پاسخ (analysis, news, comparison, ...)
print(result["suggestions"]) # پیشنهادات دنباله
print(result["sentiment"])   # احساسات شناسایی‌شده
```

### API Endpoint

```
POST /api/chat
{
  "message": "فولاد رو تحلیل کن",
  "user_id": "user_123"
}

→
{
  "text": "📊 تحلیل کامل فولاد...",
  "type": "analysis",
  "suggestions": ["مقایسه فولاد و خودرو", "اخبار فولاد", ...],
  "link": "/symbol/فولاد",
  "sentiment": {"sentiment": "neutral", "score": 0.0}
}
```

### Personalization & Learning

شخصی‌سازی بر اساس `user_id`:
- ذخیره نمادهای محبوب
- پیشنهاد فیلترهای تکراری
- برجسته‌سازی نتایج بر اساس علاقه‌مندی‌ها

یادگیری از بازخورد کاربران:
```
POST /api/chat/feedback
{
  "query": "تحلیل فولاد",
  "response_text": "...",
  "rating": 4,  // ۱ تا ۵
  "feedback_text": "دقیق بود"
}

GET /api/chat/stats  → آمار یادگیری
```

---

## API

### مستندات خودکار
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

تمام endpointها تحت پیشوند `/api/v1` در دسترس هستند.
پاسخ همه endpointها با wrapper یکسان برمی‌گردد: `ApiResponse<T>`.

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### فهرست گروه‌های API

| گروه | پیشوند | توضیح |
|------|--------|-------|
| [Health](#health-) | `/health` | بررسی سلامت سرویس‌ها |
| [Auth](#auth-) | `/auth` | احراز هویت کاربران |
| [Market](#market-) | `/market` | وضعیت بازار، شاخص‌ها، هیت‌مپ |
| [Symbols](#symbols-) | `/instruments` | نمادها و جزئیات |
| [Quotes](#quotes-) | `/quotes` | قیمت‌های لحظه‌ای و تاریخی |
| [Trades](#trades-) | `/trades` | معاملات درون‌روز |
| [Orderbooks](#orderbooks-) | `/orderbooks` | صف سفارشات |
| [Indicators](#indicators-) | `/indicators` | اندیکاتورهای تکنیکال |
| [Analysis](#analysis-) | `/analysis` | تحلیل تکنیکال و بنیادی |
| [Signals](#signals-) | `/signals` | سیگنال‌های معاملاتی |
| [Recommendations](#recommendations-) | `/recommendations` | توصیه‌های خرید/فروش |
| [Smart Money](#smart-money-) | `/smart-money` | تحلیل پول هوشمند ۹ لایه‌ای |
| [Screener](#screener-) | `/screener` | غربال‌گر ۵ فاز SMC |
| [News](#news-) | `/news` | اخبار بازار |
| [Codal](#codal-) | `/codal` | اطلاعیه‌های کدال |
| [Fundamental](#fundamental-) | `/fundamental` | تحلیل بنیادی |
| [Macro](#macro-) | `/macro` | داده‌های کلان اقتصادی |
| [Backtests](#backtests-) | `/backtests` | بک‌تست استراتژی‌ها |
| [ML](#ml-) | `/ml` | مدل‌های یادگیری ماشین |
| [Portfolios](#portfolios-) | `/portfolios` | مدیریت پرتفوی |
| [Watchlist](#watchlist-) | `/watchlist` | لیست پیگیری |
| [Alerts](#alerts-) | `/alerts` | هشدارهای قیمتی |
| [Chat](#chat-) | `/chat` | دستیار مکالمه‌ای هوشمند |
| [BrsApi](#brsapi-) | `/brsapi` | کامودیتی، طلا، ارز، رمزارز |
| [Reports](#reports-) | `/reports` | گزارش‌های تحلیلی |
| [Risk](#risk-) | `/risk` | مدیریت ریسک |
| [Tabdeal](#tabdeal-) | `/tabdeal` | یکپارچه‌سازی صرافی Tabdeal |
| [Economic Calendar](#economic-calendar-) | `/economic-calendar` | رویدادهای اقتصادی |
| [Strategy Composition](#strategy-composition-) | `/compose` | ترکیب استراتژی‌ها |
| [Stock Assistant](#stock-assistant-) | `/stock-assistant` | دستیار هوشمند سهام |
| [Data Import](#data-import-) | `/data-import` | ورود داده CSV/XLSX |
| [Tables](#tables-) | `/tables` | مرورگر دیتابیس |
| [Rate Limits](#rate-limits-) | `/rate-limits` | وضعیت محدودیت نرخ |

---

### Health 🔵

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/health` | بررسی پایه — وضعیت، تایم‌استمپ |
| `GET` | `/health/ready` | آمادگی سرویس (Readiness Probe) |
| `GET` | `/health/live` | زنده بودن سرویس (Liveness Probe) |
| `GET` | `/health/full` | بررسی کامل: دیتابیس + Redis + BrsApi |

**نمونه پاسخ `/health`:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "timestamp": "2026-07-11T12:00:00+00:00",
    "service": "iran-market-platform"
  }
}
```

**نمونه پاسخ `/health/full`:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "checks": {
      "database": { "status": "ok", "latency_ms": 3.45 },
      "redis": { "status": "ok", "latency_ms": 1.2, "detail": "Redis connected" },
      "brsapi": { "status": "ok", "latency_ms": 120, "detail": "BrsApi.ir reachable" }
    }
  }
}
```

---

### Auth 🔐

| روش | مسیر | بدنه درخواست | توضیح |
|-----|------|-------------|-------|
| `POST` | `/auth/register` | `{ username, password, email }` | ثبت‌نام کاربر جدید |
| `POST` | `/auth/login` | `{ username, password }` | ورود و دریافت token |
| `POST` | `/auth/refresh` | `{ refresh_token }` | تمدید token |
| `GET` | `/auth/me` | — | اطلاعات کاربر جاری |
| `PUT` | `/auth/profile` | `{ name, email }` | ویرایش پروفایل |
| `POST` | `/auth/change-password` | `{ old_password, new_password }` | تغییر رمز |
| `POST` | `/auth/logout` | — | خروج |

---

### Market 📈

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/market/overview` | — | خلاصه بازار: شاخص‌ها، ارزش معاملات، تعداد نمادها |
| `GET` | `/market/indices` | — | مقادیر شاخص‌ها (TSE, IFB, etc) |
| `GET` | `/market/gainers` | `limit=10` | پربازده‌ترین نمادها |
| `GET` | `/market/losers` | `limit=10` | کم‌بازده‌ترین نمادها |
| `GET` | `/market/active` | `limit=10` | نمادهای با بیشترین حجم معاملات |
| `GET` | `/market/watch` | — | لیست نظارت بازار (تابلوی زنده) |
| `GET` | `/market/bourse` | — | نمادهای بازار بورس |
| `GET` | `/market/heatmap` | — | داده‌های هیت‌مپ قیمتی |
| `GET` | `/market/enriched-heatmap` | — | هیت‌مپ با P/E، free float، محدوده قیمت |
| `GET` | `/market/treemap` | `limit=500` | درخت سلسله‌مراتبی بر اساس صنعت |
| `GET` | `/market/indicator/{symbol}` | `indicator`, `period` | محاسبه اندیکاتور تکنیکال |
| `GET` | `/market/history/{symbol}` | `limit=200` | داده‌های OHLCV برای نمودار کندل |
| `GET` | `/market/sparklines` | `symbols=فولاد,فملی`, `limit=30` | قیمت پایانی چند نماد برای مینی‌چارت |
| `GET` | `/market/energy-commodity` | — | انرژی و کالاهای بورس انرژی |

**نمونه `/market/overview`:**
```json
{
  "success": true,
  "data": {
    "total_trade_value": 125000000000000,
    "total_trade_volume": 8500000000,
    "symbols_count": 650,
    "gainers_count": 280,
    "losers_count": 120,
    "indices": [
      { "name": "شاخص کل", "value": 2540000, "change_pct": 0.85 }
    ]
  }
}
```

**نمونه `/market/gainers?limit=3`:**
```json
{
  "success": true,
  "data": [
    { "symbol": "فولاد", "change": 4.95, "price": 45200, "volume": 85000000 },
    { "symbol": "فملی", "change": 3.82, "price": 28750, "volume": 62000000 },
    { "symbol": "وبملت", "change": 2.75, "price": 18650, "volume": 45000000 }
  ]
}
```

---

### Symbols 📋

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/instruments` | `page`, `page_size`, `market` | لیست همه نمادها با صفحه‌بندی |
| `GET` | `/instruments/search` | `q=فولاد`, `page=1` | جستجوی نماد بر اساس نام یا کد |
| `POST` | `/instruments` | `{ symbol, name, ... }` | ایجاد نماد جدید |
| `GET` | `/instruments/{symbol}` | — | دریافت یک نماد |
| `GET` | `/instruments/{symbol}/detail` | — | جزئیات کامل نماد |
| `POST` | `/instruments/import` | `file=` (CSV/XLSX) | ورود دسته‌ای نمادها (ده‌ها هزارتا) |
| `GET` | `/instruments/sample` | — | دانلود نمونه CSV برای ورود |

**نمونه `/instruments/search?q=فولاد`:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "symbol": "فولاد",
        "name": "فولاد مبارکه اصفهان",
        "isin": "IRO1FOLD0001",
        "market": "bours",
        "sector": "فلزات اساسی"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50
  }
}
```

---

### Quotes 💰

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `POST` | `/quotes/{instrument_id}` | `{ price_close, ... }` | ثبت کوئوت جدید |
| `GET` | `/quotes/{instrument_id}/latest` | — | آخرین قیمت یک نماد |
| `GET` | `/quotes/{instrument_id}/history` | `start`, `end`, `timeframe` | تاریخچه قیمت با بازه زمانی |
| `POST` | `/quotes/import-bulk` | `files=` (CSV) | ورود دسته‌ای CSV قیمت‌های روزانه |

---

### Trades 💹

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/trades/{symbol}` | `page`, `page_size` | معاملات یک نماد با صفحه‌بندی |
| `GET` | `/trades/{symbol}/recent` | — | آخرین معاملات یک نماد |

---

### Orderbooks 📊

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/orderbooks/{symbol}` | صف سفارشات فعلی یک نماد |
| `GET` | `/orderbooks/{symbol}/history` | تاریخچه صف سفارشات |

---

### Indicators 📉

| روش | مسیر | بدنه/پارامترها | توضیح |
|-----|------|---------------|-------|
| `POST` | `/indicators/{instrument_id}/{name}` | `{ params }` | ایجاد اندیکاتور تکنیکال |
| `GET` | `/indicators/{instrument_id}/{name}` | `timeframe=1d` | دریافت مقدار اندیکاتور |

اندیکاتورهای پشتیبانی‌شده: `sma`, `ema`, `rsi`, `macd`, `bollinger`, `stochastic`, `atr`, `obv`, `williams_r`, `ichimoku`

---

### Analysis 🔬

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/analysis/overview` | نمای کلی بازار: احساسات، روند صنایع، توصیه‌ها |
| `GET` | `/analysis/trends` | روند صنایع مختلف با نمادهای برتر |
| `GET` | `/analysis/liquidity` | جریان نقدینگی: ورود/خروج پول حقیقی و حقوقی |
| `GET` | `/analysis/elliot-waves/{symbol}` | تحلیل روند ساده برای یک نماد |

**نمونه `/analysis/liquidity`:**
```json
{
  "success": true,
  "data": {
    "total_trade_value": 125000000000000,
    "money_flow_index": 62.5,
    "total_inflow": 58000000000000,
    "total_outflow": 42000000000000,
    "net_flow": 16000000000000,
    "top_inflow_sectors": [
      { "sector": "فلزات اساسی", "inflow": 12000000000000 }
    ]
  }
}
```

---

### Signals 🚦

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/signals` | `page`, `page_size` | لیست همه سیگنال‌ها |
| `POST` | `/signals/{instrument_id}` | `{ signal_type, ... }` | ایجاد سیگنال جدید |
| `GET` | `/signals/{instrument_id}/latest` | — | آخرین سیگنال یک نماد |
| `GET` | `/signals/{instrument_id}` | `page`, `page_size` | سیگنال‌های یک نماد خاص |

---

### Recommendations 📝

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/recommendations` | `page`, `page_size` | لیست همه توصیه‌ها |
| `POST` | `/recommendations` | `{ instrument_id, action, ... }` | ایجاد توصیه جدید |
| `GET` | `/recommendations/{instrument_id}` | `page`, `page_size` | توصیه‌های فعال برای یک نماد |

---

### Smart Money 🧠

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/smart-money/{symbol}` | تحلیل پول هوشمند ۹ لایه‌ای برای یک نماد |

**نمونه پاسخ:**
```json
{
  "success": true,
  "data": {
    "symbol": "فولاد",
    "smc_score": 0.78,
    "phase": "accumulation",
    "confidence": 0.85,
    "scores": {
      "price_volume": 0.82,
      "absorption": 0.65,
      "ownership": 0.75,
      "compression": 0.70,
      "relative_strength": 0.80,
      "breakout": 0.72,
      "buyer_power": 0.78,
      "microstructure": 0.68,
      "breakout_quality": 0.73
    }
  }
}
```

---

### Screener 🔍

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/screener` | `sort_by`, `limit`, `min_score`, `market` | غربال‌گر ۵ فاز SMC با صفحه‌بندی |
| `POST` | `/screener/filter` | `{ filters: [...], logic, sort_by, ... }` | فیلتر پویا با معیارهای دلخواه |

فیلدهای قابل فیلتر: `rsi`, `pe_ratio`, `volume`, `price`, `change_pct`, `smc_score`, `market_value`, `eps`, `trade_count`

اپراتورها: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between`, `in`, `contains`

**نمونه `POST /screener/filter`:**
```json
{
  "filters": [
    { "field": "rsi", "operator": "gte", "value": 50 },
    { "field": "pe_ratio", "operator": "between", "value": 3, "value_to": 8 },
    { "field": "volume", "operator": "gt", "value": 5000000 }
  ],
  "sort_by": "smc_score",
  "sort_order": "desc",
  "limit": 20
}
```

---

### News 📰

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/news` | `page`, `page_size`, `category` | لیست اخبار با صفحه‌بندی |
| `POST` | `/news` | `{ title, summary, source, ... }` | ایجاد خبر جدید |
| `GET` | `/news/search` | `q=فولاد`, `page=1` | جستجوی اخبار |
| `GET` | `/news/symbol/{symbol}` | `page=1` | اخبار مرتبط با یک نماد |
| `GET` | `/news/category/{category}` | `page=1` | اخبار یک دسته: `market`, `company`, `economic`, `political`, `international` |
| `GET` | `/news/trending` | `limit=10` | اخبار داغ و پرطرفدار |
| `POST` | `/news/refresh` | — | بروزرسانی اخبار از RSS feeds |
| `GET` | `/news/refresh/status` | — | وضعیت بروزرسانی پس‌زمینه |

**نمونه `/news`:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "news_001",
        "title": "افزایش قیمت جهانی فولاد",
        "summary": "قیمت فولاد در بازارهای جهانی با رشد ۲.۵٪ همراه شد",
        "source": "تسنیم",
        "category": "market",
        "symbols": ["فولاد"],
        "published_at": "1404-04-20T12:00:00",
        "sentiment": "positive",
        "sentiment_score": 0.75
      }
    ],
    "total": 150,
    "page": 1,
    "page_size": 50
  }
}
```

---

### Codal 🏢

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/codal` | `symbol`, `page`, `page_size` | اطلاعیه‌های کدال با فیلتر |
| `POST` | `/codal/{instrument_id}` | `{ title, report_type, ... }` | ثبت اطلاعیه جدید |
| `GET` | `/codal/{instrument_id}` | `page`, `page_size` | اطلاعیه‌های یک نماد |
| `GET` | `/codal/brsapi-search` | `symbol`, `category`, `date_start`, `date_end` | جستجوی لحظه‌ای از BrsApi |
| `GET` | `/codal/announcements` | `symbol`, `date_start`, `date_end` | اطلاعیه‌های ذخیره‌شده در دیتابیس |
| `GET` | `/codal/{code}/profile` | — | پروفایل شرکت (EPS, P/E, market cap, سهامداران) |
| `GET` | `/codal/{code}/financials` | — | صورت‌های مالی فصلی |
| `GET` | `/codal/{code}/dividends` | — | تاریخچه سود نقدی |
| `GET` | `/codal/{code}/holders` | — | سهامداران عمده |
| `GET` | `/codal/{code}/insider` | — | معاملات مدیران و سهامداران اصلی |
| `POST` | `/codal/import-bulk` | `files=` (Excel/CSV) | ورود دسته‌ای داده‌های کدال |

---

### Fundamental 📐

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/fundamental/ratios/{symbol}` | نسبت‌های بنیادی (P/E, P/B, P/S, EPS, DPS, ROE, ROA) |
| `GET` | `/fundamental/dcf/{symbol}` | ارزش‌گذاری با مدل DCF |
| `GET` | `/fundamental/score/{symbol}` | امتیاز بنیادی ترکیبی |
| `GET` | `/fundamental/compare` | `symbols=فولاد,فملی,شپنا` | مقایسه بنیادی چند نماد |
| `GET` | `/fundamental/industry/{industry}` | تحلیل صنعت و مقایسه نمادهای هم‌صنعت |

---

### Macro 📊

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/macro/` | لیست همه اندیکاتورهای کلان اقتصادی |
| `GET` | `/macro/{indicator}` | مقدار فعلی یک اندیکاتور |
| `GET` | `/macro/{indicator}/history` | تاریخچه مقادیر یک اندیکاتور |

---

### Backtests 🎯

| روش | مسیر | توضیح |
|-----|------|-------|
| `POST` | `/backtests/run` | اجرای بک‌تست روی یک یا چند نماد |
| `GET` | `/backtests/runs` | لیست اجراهای بک‌تست |
| `GET` | `/backtests/runs/{run_id}` | جزئیات یک اجرا |
| `GET` | `/backtests/runs/{run_id}/result` | نتیجه یک اجرا |
| `GET` | `/backtests/strategies` | لیست استراتژی‌های موجود |
| `POST` | `/backtests/run-all` | اجرای استراتژی روی همه نمادها |
| `POST` | `/backtests/compare` | مقایسه همه استراتژی‌ها روی یک نماد |
| `POST` | `/backtests/compare/save` | ذخیره نتیجه مقایسه |
| `GET` | `/backtests/compare/history` | تاریخچه مقایسه‌ها |
| `POST` | `/backtests/generate` | تولید و فیلتر خودکار استراتژی‌ها |
| `POST` | `/backtests/walk-forward` | بهینه‌سازی walk-forward |
| `POST` | `/backtests/monte-carlo` | شبیه‌سازی مونت کارلو |
| `POST` | `/backtests/portfolio-run` | بک‌تست سطح پرتفوی |
| `POST` | `/backtests/cascade/run` | موتور فیلتر cascade |
| `POST` | `/backtests/adaptive/init` | راه‌اندازی سیستم تطبیقی |
| `GET` | `/backtests/adaptive/regime` | رژیم فعلی بازار |

**نمونه بدنه `POST /backtests/run`:**
```json
{
  "name": "MA Cross Test",
  "symbols": ["فولاد"],
  "strategy_type": "moving_average_cross",
  "strategy_params": { "fast_period": 10, "slow_period": 50 },
  "start_date": "2025-01-01",
  "end_date": "2026-07-01",
  "initial_capital": 1000000000
}
```

**نمونه پاسخ:**
```json
{
  "success": true,
  "data": {
    "id": "bt_abc123",
    "status": "completed",
    "metrics": {
      "total_return_pct": 45.2,
      "sharpe_ratio": 1.85,
      "win_rate": 62.5,
      "max_drawdown_pct": -12.3,
      "total_trades": 48
    }
  }
}
```

---

### ML 🤖

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/ml/models` | لیست مدل‌های ثبت‌شده |
| `GET` | `/ml/runs` | تاریخچه آموزش‌ها |
| `GET` | `/ml/runs/{run_id}` | جزئیات یک آموزش |
| `POST` | `/ml/predict/{model_id}` | پیش‌بینی با مدل |
| `POST` | `/ml/train` | آموزش مدل جدید |
| `POST` | `/ml/feature-importance/{model_id}` | اهمیت ویژگی‌ها (SHAP) |

---

### Portfolios 💼

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/portfolios/` | لیست پرتفوی‌ها |
| `POST` | `/portfolios/` | ایجاد پرتفوی جدید |
| `GET` | `/portfolios/{id}` | جزئیات پرتفوی |

---

### Watchlist ⭐

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/watchlist/` | لیست پیگیری با قیمت‌های لحظه‌ای |
| `POST` | `/watchlist/` | افزودن نماد به لیست پیگیری |
| `DELETE` | `/watchlist/{symbol}` | حذف نماد از لیست پیگیری |

---

### Alerts 🔔

| روش | مسیر | بدنه/پارامترها | توضیح |
|-----|------|---------------|-------|
| `GET` | `/alerts/` | `page`, `page_size` | لیست هشدارها |
| `POST` | `/alerts/` | `{ instrument_id, symbol, alert_type, condition, channels }` | ایجاد هشدار جدید |
| `PUT` | `/alerts/{id}` | `{ condition, enabled, ... }` | ویرایش هشدار |
| `DELETE` | `/alerts/{id}` | — | حذف هشدار |
| `GET` | `/alerts/{id}/history` | `page`, `page_size` | تاریخچه فعال‌شدن هشدار |

انواع هشدار: `price_above`, `price_below`, `volume_spike`, `change_pct`, `rsi_oversold`, `rsi_overbought`, `technical`

---

### Chat 💬

| روش | مسیر | بدنه | توضیح |
|-----|------|------|-------|
| `POST` | `/chat` | `{ message, user_id }` | دستیار هوشمند ۲۰ سطحی |
| `POST` | `/chat/feedback` | `{ query, response_text, rating }` | ثبت بازخورد برای یادگیری |
| `GET` | `/chat/stats` | — | آمار یادگیری موتور مکالمه |

**نمونه `POST /chat`:**
```json
// Request
{ "message": "فولاد رو تحلیل کن", "user_id": "user_123" }

// Response
{
  "success": true,
  "data": {
    "text": "📊 تحلیل کامل فولاد...\n\nقیمت آخر: ۴۵٬۲۰۰ ریال\nتغییر: ۴.۹۵٪\nسیگنال SMC: خرید (امتیاز ۰.۷۸)",
    "type": "analysis",
    "suggestions": ["مقایسه فولاد و فملی", "اخبار فولاد", "نمودار فولاد"],
    "link": "/symbol/فولاد",
    "link_label": "🔗 صفحه نماد فولاد",
    "sentiment": { "sentiment": "neutral", "score": 0.0 }
  }
}
```

---

### BrsApi 🌍

| روش | مسیر | پارامترها | توضیح |
|-----|------|----------|-------|
| `GET` | `/brsapi/health` | — | سلامت سرویس BrsApi |
| `GET` | `/brsapi/commodities` | `category=precious_metal` | قیمت کامودیتی‌های جهانی |
| `GET` | `/brsapi/commodities/categories` | — | دسته‌بندی کامودیتی‌ها |
| `GET` | `/brsapi/crypto` | `limit=50`, `sort_by=rank` | قیمت رمزارزها (USD/IRR) |
| `GET` | `/brsapi/crypto/top` | — | ۱۰ رمزارز برتر |
| `GET` | `/brsapi/gold-coin` | — | قیمت طلا و سکه |
| `GET` | `/brsapi/currency` | — | نرخ ارزها (USD, EUR, GBP, AED, ...) |
| `GET` | `/brsapi/history/{symbol}` | `limit=365`, `date_start`, `date_end` | قیمت‌های تاریخی روزانه |
| `GET` | `/brsapi/codal-announcements` | `symbol`, `date_start`, `date_end` | اطلاعیه‌های کدال (ذخیره‌شده) |
| `GET` | `/brsapi/codal-announcements/lazy/{symbol}` | `page=1` | دریافت لحظه‌ای کدال برای یک نماد |
| `GET` | `/brsapi/manage/sections` | — | لیست همه بخش‌ها با وضعیت sync |
| `POST` | `/brsapi/manage/sync/{section_id}` | `symbol`, `date_start` | همگام‌سازی یک بخش |
| `GET` | `/brsapi/manage/download/{section_id}` | `format=json|csv`, `live=true` | دانلود داده یک بخش |
| `POST` | `/brsapi/manage/sync-nav-all` | `max_symbols` | همگام‌سازی NAV همه صندوق‌ها |
| `POST` | `/brsapi/manage/sync-top-symbols` | `limit=10` | همگام‌سازی جزئیات N نماد برتر |
| `POST` | `/brsapi/manage/sync-all-history` | `limit` | همگام‌سازی تاریخچه همه نمادها |
| `GET` | `/brsapi/manage/last-update/{section_id}` | — | آخرین زمان بروزرسانی یک بخش |

---

### Reports 📄

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/reports/market` | گزارش جامع بازار |
| `GET` | `/reports/symbol/{symbol}` | گزارش تفصیلی یک نماد |
| `GET` | `/reports/backtest/{backtest_id}` | گزارش بک‌تست |

---

### Risk ⚠️

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/risk/` | اندیکاتورهای مدیریت ریسک |

---

### Tabdeal 💱

یکپارچه‌سازی صرافی Tabdeal (ارز دیجیتال). نیاز به API key جداگانه.

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/tabdeal/ping` | بررسی اتصال |
| `GET` | `/tabdeal/time` | زمان سرور Tabdeal |
| `GET` | `/tabdeal/markets` | اطلاعات بازارهای Tabdeal |
| `GET` | `/tabdeal/depth/{symbol}` | عمق بازار (orderbook) |
| `GET` | `/tabdeal/trades/{symbol}` | معاملات عمومی |
| `GET` | `/tabdeal/orders` | سفارشات از دیتابیس |
| `GET` | `/tabdeal/trades` | معاملات از دیتابیس |
| `GET` | `/tabdeal/account` | حساب از دیتابیس |
| `GET` | `/tabdeal/balances` | موجودی‌ها از دیتابیس |
| `POST` | `/tabdeal/sync/markets` | همگام‌سازی بازارها |
| `POST` | `/tabdeal/sync/orders` | همگام‌سازی سفارشات |
| `POST` | `/tabdeal/sync/trades` | همگام‌سازی معاملات |
| `POST` | `/tabdeal/sync/account` | همگام‌سازی حساب |
| `GET` | `/tabdeal/live/account` | حساب زنده (passthrough) |
| `GET` | `/tabdeal/live/open-orders` | سفارشات باز زنده |
| `GET` | `/tabdeal/live/fapi/positions` | پوزیشن‌های فیوچرز |

---

### Economic Calendar 📅

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/economic-calendar/` | رویدادهای اقتصادی پیش‌رو |
| `POST` | `/economic-calendar/subscribe` | اشتراک برای اطلاع‌رسانی رویدادها |
| `GET` | `/economic-calendar/subscriptions` | لیست اشتراک‌ها |
| `DELETE` | `/economic-calendar/subscriptions/{id}` | لغو اشتراک |

---

### Strategy Composition 🧩

| روش | مسیر | توضیح |
|-----|------|-------|
| `POST` | `/compose/start` | شروع ترکیب استراتژی |
| `GET` | `/compose/status` | وضعیت ترکیب |
| `GET` | `/compose/results` | نتایج ترکیب |
| `GET` | `/compose/top/{n}` | N استراتژی برتر |
| `POST` | `/compose/stop` | توقف ترکیب |
| `GET` | `/compose/export` | خروجی CSV |
| `GET` | `/compose/stats` | آمار اندیکاتورها |
| `GET` | `/compose/indicators` | لیست اندیکاتورهای موجود |

---

### Data Import 📥

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/data-import/history` | تاریخچه ورود داده‌ها |
| `GET` | `/data-import/templates` | قالب‌های ستون‌بندی برای هر نوع ورود |

---

### Tables 🗃️

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/tables` | لیست جداول با تعداد رکوردها |
| `GET` | `/tables/{name}` | داده‌های یک جدول با صفحه‌بندی |

---

### Tests 🧪

| روش | مسیر | توضیح |
|-----|------|-------|
| `POST` | `/tests/run` | اجرای تست‌های واحد از طریق API |

---

### Rate Limits ⏱️

| روش | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/api/v1/rate-limits` | وضعیت محدودیت نرخ (daily, 5min, per-endpoint) |

**نمونه پاسخ:**
```json
{
  "success": true,
  "data": {
    "global": {
      "daily_count": 3842,
      "daily_limit": 10000,
      "daily_used_pct": 38.42,
      "5min_count": 42,
      "5min_limit": 500,
      "5min_used_pct": 8.4
    },
    "endpoints": {
      "TSETMC.AllSymbols": { "count": 5, "limit": 1 },
      "TSETMC.SymbolDetail": { "count": 120, "limit": 18 },
      "Market.GoldCurrencyPro": { "count": 8, "limit": 6 }
    }
  }
}
```

---

### سرویس‌های اصلی

| سرویس | توضیح |
|--------|---------|
| **Instrument Service** | مدیریت نمادها |
| **Quote Service** | داده‌های لحظه‌ای قیمت |
| **Signal Service** | تولید سیگنال‌های معاملاتی |
| **Backtest Service** | اجرای بک‌تست |
| **Trade Service** | مدیریت معاملات |
| **Portfolio Service** | مدیریت پرتفوی |
| **ML Service** | آموزش و پیش‌بینی |
| **Monitoring Service** | مانیتورینگ سلامت |
| **Screener Service** | غربالگری نمادها (۵ فاز: نقدشوندگی، قدرت، ساختار، جریان سفارش، تریگر) |
| **Smart Money Service** | تحلیل هوشمند ۹ لایه‌ای (SMC Score) |
| **Stock Assistant Service** | دستیار مکالمه‌ای سهام (تحلیل، مقایسه، فیلتر، پرتفوی، هشدار) |
| **Unified Assistant Service** | دستیار یکپارچه متصل به همه سرویس‌ها |
| **Chat Engine (20-Level)** | موتور مکالمه ۲۰ سطحی با intent detection, sentiment, personalization |

---

### نکات مهم

- **فرمت پیش‌فرض پاسخ**: همه endpointها با `ApiResponse<T>` wrapper برمی‌گردند:
  ```json
  { "success": true, "data": ..., "error": null }
  ```
- **احراز هویت**: بیشتر endpointها از `get_optional_user` استفاده می‌کنند — اگر token ارائه شود، کاربر شناسایی می‌شود، در غیر این صورت درخواست به‌عنوان ناشناس پردازش می‌شود.
- **صفحه‌بندی**: از `PaginatedResult` استفاده می‌شود: `{ items: [...], total, page, page_size, total_pages }`
- **Rate Limiting**: محدودیت سراسری ۱۰,۰۰۰ req/day + ۵۰۰ req/5min (برای BrsApi)
- **کش**: پاسخ‌های Screener تا ۶۰ ثانیه کش می‌شوند
- **Fallback**: بسیاری از endpointها در صورت خالی بودن دیتابیس، داده‌های mock یا سنتز شده برمی‌گردانند

---

## ML Pipeline

```mermaid
flowchart TB
    subgraph DataSrc["📥 Data Sources"]
        QUOTE["Quotes & History\nOHLCV · Volume · Trades"]
        FUND["Fundamental Data\nP/E · EPS · DPS · ROE · ROA"]
        MACROE["Macro & Economic\nInflation · Index · News"]
    end

    subgraph FeatEng["🔧 Feature Engineering"]
        BUILDER["DatasetBuilder\ncreate_sequences · normalize\ntrain_test_split · validate"]
        FEAT_COMP["FeatureBuilder (ABC)\ncompute() · get_feature_names()\n→ Price · Volume · Technical\n→ Fundamental · Macro · Cross"]
        FEAT_MAT["FeatureMatrix\nshape · values · to_df()\nfeature_names"]
    end

    QUOTE & FUND & MACROE --> BUILDER
    BUILDER --> FEAT_COMP
    FEAT_COMP --> FEAT_MAT

    subgraph FeatStore["💾 Feature Store"]
        FS_MEM["FeatureStore (In-Memory)\nregister_feature · get_features\nlist_groups · remove_feature"]
        FS_FILE["FeatureStore (File-based)\nsave(key, json) · load(key)\n→ ./data/features/*.json"]
    end

    FEAT_MAT -.-> FS_MEM
    FEAT_MAT --> FS_FILE

    subgraph Training["🎓 Training Pipeline"]
        EXP["ExperimentTracker\nstart_run · log_metric\nend_run · get_runs"]
        TUNER["HyperparameterTuner\nGrid Search · Optuna\nWalk-Forward Validation"]
        TRAINER["Trainer\ntrain(model, X_train, y_train)\n→ MetricsCalculator\nMSE · RMSE · MAE · R² · DirAcc"]
        MODEL["BaseModel (ABC)\nfit() · predict()\n+ ModelRegistry (Builder)\n→ SklearnModel · XGBModel\n→ LSTMModel · Ensemble"]
    end

    FEAT_MAT --> EXP
    FEAT_MAT --> TUNER
    TUNER --> TRAINER
    TRAINER -.->|create| MODEL
    MODEL --> TRAINER

    subgraph Registry["📋 Model Registry"]
        REG_VERS["ModelRegistry\nregister(model_id, version)\nget(model_id, version)\nlist_models · list_versions\nadd_version(metrics, params)"]
        REG_STAGE["Staging & Promotion\nget_production(model_id)\npromote(version, stage)\n→ development → staging → production"]
        MODELS_ART["ModelArtifactMeta\nmodel_id · version · metrics\nparams · stage · created_at"]
    end

    TRAINER --> REG_VERS
    REG_VERS --> REG_STAGE
    REG_VERS -.-> MODELS_ART

    subgraph Storage["🗄️ Artifact Storage"]
        ARTIFACT["ArtifactManager\nsave_model(model.pkl + metadata.json)\nload_model(model_id, version)\n→ ./models/{model_id}/{version}/\n→ model.pkl + metadata.json"]
    end

    REG_STAGE --> ARTIFACT

    subgraph Inference["🚀 Batch Inference"]
        PREDICT["BatchPredictor\npredict(model, X, batch_size=64)\n→ numpy concatenation"]
        DRIFT["DriftDetector\ndetect_drift(new_data)\n→ drift_score + drifted flag\nthreshold = 0.1"]
        RESULT_PRED["PredictionResult\npredictions · probabilities\nmodel_id · timestamp"]
    end

    ARTIFACT --> PREDICT
    FEAT_MAT --> PREDICT
    FEAT_MAT --> DRIFT
    PREDICT --> RESULT_PRED

    subgraph Policies["⚖️ Policies"]
        PROMOTE["ModelPromotionPolicy\nshould_promote(metrics, current_best)\nmin_metric_threshold = 0.6"]
        ROLLBACK["RollbackPolicy\nshould_rollback(drift, error_rate)\ndrift > 0.3 → rollback\nerror > 0.1 → rollback"]
    end

    DRIFT --> ROLLBACK
    ROLLBACK --> REG_STAGE
    PROMOTE --> REG_STAGE

    subgraph ML_API["🔌 ML API Endpoints"]
        API_LIST["GET /ml/models\n→ لیست مدل‌های ثبت‌شده"]
        API_RUNS["GET /ml/runs\n→ تاریخچه آموزش"]
        API_TRAIN["POST /ml/train\n→ آموزش مدل جدید"]
        API_PREDICT["POST /ml/predict/{id}\n→ پیش‌بینی با مدل"]
        API_FEAT["POST /ml/feature-importance/{id}\n→ اهمیت ویژگی‌ها (SHAP)"]
    end

    REG_VERS --> API_LIST
    EXP --> API_RUNS
    TRAINER --> API_TRAIN
    PREDICT --> API_PREDICT

    style DataSrc fill:#e3f2fd,stroke:#1565c0
    style FeatEng fill:#e8eaf6,stroke:#3f51b5
    style FeatStore fill:#e0f7fa,stroke:#0097a7
    style Training fill:#f3e5f5,stroke:#7b1fa2
    style Registry fill:#fff3e0,stroke:#e65100
    style Storage fill:#fce4ec,stroke:#c62828
    style Inference fill:#e8f5e9,stroke:#2e7d32
    style Policies fill:#f5f5f5,stroke:#616161
    style ML_API fill:#ffebee,stroke:#b71c1c
```

### Feature Store
- **Price Features**: بازده، نوسان، شاخص‌های تکنیکال
- **Volume Features**: حجم، ارزش، نسبت‌ها
- **Technical Features**: RSI, MACD, Bollinger, Ichimoku
- **Fundamental Features**: نسبت‌های بنیادی
- **Macro Features**: شاخص‌های کلان اقتصادی
- **Cross-Sectional Features**: ویژگی‌های بین‌نمادی
- **News Features**: تحلیل اخبار

### Training Pipeline
```python
from ml.training.trainer import Trainer
from ml.training.hyperparameter_tuning import HyperparameterTuner
from ml.models.registry import ModelRegistry

trainer = Trainer()
tuner = HyperparameterTuner()
registry = ModelRegistry()

# آموزش با بهینه‌سازی فراپارامترها
best_params = tuner.tune(X_train, y_train)
model = trainer.train(X_train, y_train, **best_params)
registry.register("my_model_v1", model, metrics)
```

### Batch Inference
```python
from ml.inference.batch_predictor import BatchPredictor

predictor = BatchPredictor()
predictions = predictor.predict(model, X_latest)
```

---

## مانیتورینگ

### متریک‌های Prometheus
- تعداد درخواست‌ها و تأخیر
- وضعیت دیتابیس و کش
- سلامت سرویس‌ها
- تازگی داده‌ها (Data Freshness)

### Grafana Dashboards
- **Overview**: نمای کلی سیستم
- **Data Quality**: کیفیت داده‌های دریافتی

### Alerting
- هشدارهای SLA
- تشخیص ناهنجاری
- هشدار سلامت سرویس

---

## اپراتورهای داده

### Ingestion Pipeline
```python
# اجرای جمع‌آوری داده
python -m ingestion.main

# یا با Docker (به طور خودکار اجرا می‌شود)
```

### اپراتورهای موجود

| اپراتور | منبع | توضیح |
|----------|--------|---------|
| **TSETMC** | tsetmc.com | داده‌های لحظه‌ای و تاریخی بورس |
| **CODAL** | codal.ir | اطلاعات شرکت‌ها |
| **Manual** | — | ورود دستی داده |
| **Web Scraping** | — | استخراج از وبسایت‌ها |

---

## پیکربندی

### متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|--------|---------|---------|
| `SERVER_HOST` | `0.0.0.0` | هاست سرور |
| `SERVER_PORT` | `8000` | پورت سرور |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/marketdb` | آدرس دیتابیس |
| `REDIS_URL` | `redis://localhost:6379/0` | آدرس Redis |
| `MINIO_ENDPOINT` | `localhost:9000` | آدرس MinIO |
| `LOG_LEVEL` | `INFO` | سطح لاگ |
| `ENVIRONMENT` | `development` | محیط اجرا |

---

## توسعه و مشارکت

### دستورات کاربردی (Makefile)

```bash
make install      # نصب وابستگی‌ها
make lint         # اجرای linter (ruff)
make typecheck    # بررسی نوع (mypy)
make test         # اجرای تست‌های واحد
make test-all     # اجرای همه تست‌ها
make dev          # اجرای سرور توسعه
make clean        # پاکسازی کش
```

همه اسکریپت‌های `scripts/` هم بدون `PYTHONPATH` قابل اجرا هستند:
```bash
python scripts/fetch_news.py --limit 10
python scripts/seed_news.py
python scripts/backfill_historical_data.py
```

### تست

```bash
# تست‌های واحد
pytest tests/unit -v --tb=short

# تست‌های یکپارچگی
pytest tests/integration -v --tb=short

# تست‌های عملکرد
pytest tests/performance -v --tb=short

# پوشش تست
pytest --cov=backtesting tests/unit -v
```

### Linting & Type Checking

```bash
# بررسی کد با ruff
ruff check . --fix

# بررسی نوع با mypy
mypy apps core domain services --ignore-missing-imports
```

---

## اسکریپت‌های کاربردی

> **نکته:** تمام اسکریپت‌های پوشه `scripts/` به‌صورت خودکار `PYTHONPATH` را تشخیص می‌دهند و بدون نیاز به تنظیم دستی اجرا می‌شوند:
> ```bash
> python scripts/fetch_news.py --limit 10     # بدون PYTHONPATH=.
> python scripts/seed_news.py                 # بدون PYTHONPATH=.
> python scripts/backfill_historical_data.py  # بدون PYTHONPATH=.
> ```

| اسکریپت | توضیح |
|----------|---------|
| `fetch_news.py` | دریافت و ذخیره اخبار اقتصادی از RSS |
| `seed_news.py` | مقداردهی اولیه اخبار |
| `bootstrap_env.py` | راه‌اندازی اولیه محیط |
| `run_sample_backtest.py` | اجرای بک‌تست نمونه |
| `train_baseline_models.py` | آموزش مدل‌های پایه |
| `backfill_historical_data.py` | تکمیل داده‌های تاریخی |
| `seed_reference_data.py` | مقداردهی داده‌های مرجع |
| `rebuild_indicators.py` | بازسازی اندیکاتورها |
| `rebuild_features.py` | بازسازی ویژگی‌های ML |
| `backup_postgres.py` | پشتیبان‌گیری دیتابیس |
| `fetch_news_daily.ps1` | اسکریپت PowerShell برای Task Scheduler (اجرای روزانه) |
| `brsapi_full_update.py` | **بروزرسانی جامع BrsApi** (۱۰,۰۰۰ req/day, auto-create tables, error report) |
| `sync_all_brsapi.py` | همگام‌سازی همه داده‌های BrsApi |
| `sync_all_tables.py` | همگام‌سازی جداول |
| `sync_codal_with_ins_id.py` | همگام‌سازی کدال با شناسه نمادها |
| `sync_commodities_test.py` | تست همگام‌سازی کامودیتی‌ها |
| `sync_historical_batch.py` | همگام‌سازی دسته‌ای داده‌های تاریخی |
| `sync_live_data.py` | همگام‌سازی داده‌های لحظه‌ای |

---

## پروژه‌های مرتبط

- [tsetmc-scraper](https://github.com/mohsentaleb/tsetmc-scraper) — ابزار جمع‌آوری داده از TSETMC
- [codal-scraper](https://github.com/mohsentaleb/codal-scraper) — ابزار جمع‌آوری داده از CODAL

---

## مجوز

این پروژه تحت مجوز MIT منتشر شده است.

---

## حمایت

اگر این پروژه برایتان مفید است، می‌توانید با ستاره ⭐ دادن به مخزن از آن حمایت کنید.

</div>

---

# Iran Market Data & Analytics Platform 🇮🇷📈

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

A comprehensive, modular, and scalable platform for collecting, processing, storing, analyzing, and backtesting Iran capital market data.

> **Note:** The full Persian documentation above is the primary reference. This English section provides a quick overview.

## Quick Start

```bash
d frontend# Backend dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Frontend dependencies
c && npm install

# Run database migrations
alembic upgrade head

# Start development servers (no PYTHONPATH needed)
python main.py              # Backend API on :8000
# In another terminal:
cd frontend && npm run dev  # Frontend on :3000
.\redis-server.exe
# Run scripts (auto-PYTHONPATH)
python scripts/fetch_news.py --limit 10
```

## Docker

```bash
docker compose up --build -d
# Frontend: http://localhost:3000
# API Docs:  http://localhost:8000/docs
# Grafana:   http://localhost:3001
```

## Key Features

- **Multi-Market Backtesting** — ReplayEngine, Unified Timeline, Market Rule Engine
- **Agent-Based Modeling** — MarketMaker, NoiseTrader, TrendFollower, MeanReversion
- **Market Microstructure** — Queue Simulation, Impact Model, Auction Engine, Hidden Liquidity
- **Analytics** — Sharpe, Sortino, CAGR, Max Drawdown, Win Rate, Profit Factor
- **Experiments** — Grid Search, Walk-Forward, Monte Carlo
- **Iran Market Support** — TSE, IFB, Base Market, ETF, Bonds, Derivatives, IME, Energy
- **ML Pipeline** — Feature Store, Model Registry, Hyperparameter Tuning, Batch Inference
- **Modern Frontend** — Next.js 16, React 19, Recharts, Tailwind CSS v4, Dark Mode, RTL
- **CI/CD** — GitHub Actions, automated Docker builds, vulnerability scanning
- **Monitoring** — Prometheus metrics, Grafana dashboards, SLA alerting
- **Data Ingestion** — TSETMC, CODAL, manual, web scraping

## Supported Markets

| Market | ID | Price Limit | Session | Auction | Market Order |
|--------|----|-------------|---------|---------|-------------|
| TSE | `tse` | ±5% | 08:45-12:30 | ✅ | ✅ |
| IFB | `ifb` | ±5% | 08:45-12:30 | ✅ | ✅ |
| Base Market | `base_market` | 3-1% tiered | 08:45-12:30 | Periodic | ❌ |
| ETF | `etf` | ±5% | 08:45-12:30 | ✅ | ✅ |
| Bonds | `bonds` | ±1% | 08:45-12:30 | ❌ | ✅ |
| Derivatives | `derivatives` | Variable | 08:45-12:30 | ❌ | ✅ |
| IME | `ime` | ±5% | 11:45-18:00 | ✅ | ✅ |
| Energy | `energy` | ±5% | 11:45-18:00 | Periodic | ❌ |

## Tech Stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, APScheduler, Redis, Pandas, NumPy, httpx/aiohttp  
**Frontend:** Next.js 16, React 19, TypeScript 5, Recharts 3, Tailwind CSS v4, TanStack React Query  
**Database:** PostgreSQL 16, TimescaleDB (time-series), MinIO (S3-compatible), Redis 7  
**ML (optional):** scikit-learn, XGBoost, LightGBM, CatBoost, PyTorch, SHAP  
**Monitoring:** Prometheus, Grafana, OpenTelemetry, Trivy (container scanning)  
**CI/CD:** GitHub Actions, Docker Buildx, GitHub Container Registry (ghcr.io)

## Architecture Overview

```
Browser (port 3000)
  │
  ▼ (fetch /api/v1/*)
Next.js Server (Rewrite Proxy)
  │  resolves api:8000 inside Docker network
  ▼
FastAPI Backend (port 8000)
  ├── PostgreSQL 16 (main DB)
  ├── TimescaleDB (time-series data)
  ├── Redis 7 (cache & queuing)
  ├── MinIO (object storage)
  ├── Worker (background processing)
  └── Scheduler (cron jobs)
```

**Backtesting Engine (standalone):**

```
Data Lake → Event Builder → Unified Timeline → Replay Engine
                                                 ├── Market Engine + Rule Engine
                                                 ├── Strategy Engine
                                                 ├── Risk Engine
                                                 ├── Microstructure Engine
                                                 ├── Execution Simulator
                                                 └── Portfolio Engine → Analytics Engine
```

## API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Via Frontend Proxy**: `http://localhost:3000/api/v1/docs`

## Development

```bash
# Backend
python main.py                   # Start API dev server (auto-PYTHONPATH)
make dev                         # Or via Makefile

# Frontend
cd frontend && npm run dev       # Start frontend dev server

# Scripts (no PYTHONPATH needed)
python scripts/fetch_news.py --limit 10
python scripts/seed_news.py

# Code quality
make lint          # Run ruff linter
make typecheck     # Run mypy type checker
make test          # Run unit tests
make test-all      # Run all tests
make clean         # Clean cache files
```
## License

MIT
