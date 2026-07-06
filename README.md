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

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Browser     │────→│  Frontend    │────→│  API (FastAPI)   │
│  3000        │     │  Next.js 16  │     │  port 8000       │
│              │     │  (Proxy)     │     └────────┬─────────┘
└─────────────┘     └──────────────┘              │
                                           ┌──────┴──────┐
                                           │  PostgreSQL  │
                                           │  TimescaleDB │
                                           │  Redis       │
                                           │  MinIO       │
                                           └─────────────┘
                                                  │
                                           ┌──────┴──────┐
                                           │  Worker     │
                                           │  Scheduler  │
                                           │  Ingestion  │
                                           └─────────────┘
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
├── 📁 services/             # لایه سرویس
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

### معماری Proxy

```
مرورگر: fetch("/api/v1/health")
    │
    ▼
Next.js Server: Rewrite Proxy
    │  source: /api/v1/:path*
    │  destination: http://api:8000/api/v1/:path*
    │  (API_URL = http://api:8000, فقط سمت سرور)
    ▼
Backend API (FastAPI) on port 8000
```

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

## API

### مستندات خودکار
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### نقطه ورود

```python
# main.py
uvicorn.run(
    "apps.api.app:app",
    host=settings.server_host,
    port=settings.server_port,
    reload=settings.is_development,
)
```

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
| **Screener Service** | غربالگری نمادها |
| **Smart Money Service** | تحلیل هوشمند ۹ لایه‌ای |

---

## ML Pipeline

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
# Backend dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Frontend dependencies
cd frontend && npm install

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
