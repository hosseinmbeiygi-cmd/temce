# 🇮🇷 سکوی داده و تحلیل بازار سرمایه ایران

**Iran Market Data & Analytics Platform**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

یک پلتفرم جامع، ماژولار و مقیاس‌پذیر برای جمع‌آوری، پردازش، ذخیره‌سازی، تحلیل و بک‌تست داده‌های بازار سرمایه ایران. این سیستم شامل بیش از **۴۵ API endpoint**، **۵۰+ صفحه فرانت‌اند**، **موتور بک‌تست چندبازاری**، **سیستم سیگنال هوشمند با بازخورد خودکار** و **موتور تصمیم‌گیری** است.

---

## 📑 فهرست مطالب

- [ویژگی‌ها](#ویژگی‌ها)
- [معماری](#معماری)
- [بازارهای پشتیبانی‌شده](#بازارهای-پشتیبانی‌شده)
- [تکنولوژی‌ها](#تکنولوژی‌ها)
- [ساختار پروژه](#ساختار-پروژه)
- [راه‌اندازی سریع](#راه‌اندازی-سریع)
- [استفاده با Docker](#استفاده-با-docker)
- [فرانت‌اند Next.js](#فرانت‌اند-nextjs)
- [API Reference](#api-reference)
- [موتور بک‌تست](#موتور-بک‌تست)
- [موتور سیگنال هوشمند](#موتور-سیگنال-هوشمند)
- [موتور Smart Money](#موتور-smart-money)
- [غربالگری هوشمند](#غربالگری-هوشمند)
- [موتور مکالمه](#موتور-مکالمه)
- [موتور تصمیم‌گیری](#موتور-تصمیم‌گیری)
- [Machine Learning Pipeline](#machine-learning-pipeline)
- [یکپارچه‌سازی BrsApi.ir](#یکپارچه‌سازی-brsapiir)
- [سیستم شغل‌ها](#سیستم-شغل‌ها)
- [مانیتورینگ](#مانیتورینگ)
- [پیکربندی](#پیکربندی)
- [دستورات کاربردی](#دستورات-کاربردی)
- [ساختار دیتابیس](#ساختار-دیتابیس)
- [عیب‌یابی](#عیب‌یابی)
- [توسعه و مشارکت](#توسعه-و-مشارکت)

---

## ✨ ویژگی‌ها

### 🏛️ موتور بک‌تست چندبازاری
- **Replay Engine**: موتور بازپخش رویدادمحور با قابلیت پشتیبانی از ۱۰۰+ میلیون رویداد
- **Unified Timeline**: خط زمانی یکپارچه با مرتب‌سازی بر اساس `(timestamp, priority)`
- **Market Rule Engine**: موتور قوانین مجزا برای هر بازار (دامنه نوسان، سشن، اندازه تیک)
- **Agent-Based Modeling (ABM)**: شبیه‌سازی Market Maker، Noise Trader، Trend Follower، Mean Reversion
- **Microstructure Engine**: مدل صف، ایمپکت قیمت (قانون جذر)، حراج، نقدینگی پنهان
- **Portfolio Simulator**: مدیریت چند نماد هم‌زمان با allocation و rebalancing
- **Experiments**: Grid Search، Walk-Forward، Monte Carlo، Bayesian Optimization

### 🤖 سیستم سیگنال هوشمند با بازخورد خودکار
- **Quant Signal Orchestrator**: تولید سیگنال هر ساعت به صورت خودکار
- **Signal Voting System**: رأی‌گیری چند مدل برای افزایش دقت
- **Confidence Calibration**: کالیبراسیون اطمینان سیگنال‌ها
- **Outcome Tracking**: ثبت نتیجه سیگنال‌ها و محاسبه دقت
- **Auto-Retrain**: بازآموزی خودکار مدل‌ها هنگام افت دقت زیر ۵۰٪
- **Alert System**: هشدار تلگرام برای ۳ شکست متوالی یا افت دقت

### 📊 Smart Money Analysis (۹ لایه)
1. **Price-Volume Analysis**: تحلیل حجم و قیمت
2. **Absorption Detection**: تشخیص جذب سفارشات
3. **Ownership Analysis**: تحلیل مالکیت حقیقی/حقوقی
4. **Compression Detection**: تشخیص فشردگی قیمت
5. **Relative Strength**: قدرت نسبی نماد
6. **Breakout Analysis**: تحلیل شکست
7. **Buyer Power**: قدرت خریدار
8. **Microstructure Analysis**: تحلیل ریزساختار
9. **Breakout Quality**: کیفیت شکست

### 🔬 غربالگری هوشمند (Smart Screener)
- **۴۰۰+ فیلتر**: فیلترهای پیشرفته بر اساس قیمت، حجم، اندیکاتورها، تکنیکال و بنیادی
- **فیلترهای Smart Money**: فیلترهای مبتنی بر تحلیل پول هوشمند
- **پشتیبانی از OR/AND**: منطق ترکیبی فیلترها با تشخیص خودکار
- **ذخیره فیلترها**: ذخیره و بازیابی فیلترهای کاربر
- **۱۱۰ ستون CANSLIM**: غربالگری جامع با ۱۱۰ معیار

### 🧠 موتور تصمیم‌گیری (Decision Engine)
- **Enterprise Architecture Data**: ذخیره و مدیریت داده‌های معماری سازمانی
- **Auto-Seeding**: پر کردن خودکار داده‌ها از فایل‌های JSON
- **Decision Support**: پشتیبانی تصمیم‌گیری بر اساس داده‌های واقعی

### 💬 موتور مکالمه ۲۰ سطحی (Chat Engine)
- **Intent Classification**: تشخیص قصد کاربر
- **Entity Extraction**: استخراج موجودیت‌ها
- **Dialog Management**: مدیریت مکالمه چندمرحله‌ای
- **Chart Generation**: تولید خودکار نمودار
- **Sentiment Analysis**: تحلیل احساسات
- **News Integration**: یکپارچه‌سازی اخبار

### 📈 تحلیل تکنیکال و بنیادی
- **اندیکاتورها**: RSI, MACD, Bollinger Bands, Moving Averages, Stochastic, and more
- **تحلیل بنیادی**: EPS, P/E, P/B, ROE, ROA, and financial ratios
- **تحلیل احساسات**: Persian sentiment analysis for news
- **امواج الیوت**: Elliott Wave analysis
- **سیگنال‌های چندبازاری**: Cross-market signal analysis

### 🗄️ جمع‌آوری داده
- **TSETMC**: داده‌های بورس تهران و فرابورس
- **CODAL**: اطلاعیه‌های شرکت‌ها با دانلود پیوست‌ها
- **BrsApi.ir**: کامودیتی، رمزارز، طلا، ارز، اوراق بدهی
- **اخبار و ماکرو**: داده‌های بنیادی و کلان
- **WebSocket**: داده‌های لحظه‌ای

### 📊 ML Pipeline
- **Feature Store**: ذخیره و مدیریت ویژگی‌ها
- **Model Registry**: ثبت و نسخه‌گذاری مدل‌ها
- **Hyperparameter Tuning**: بهینه‌سازی فراپارامترها
- **Batch Inference**: پیش‌بینی دسته‌ای
- **Drift Detection**: تشخیص تغییر توزیع داده
- **Auto-Retrain**: بازآموزی خودکار هنگام افت دقت

---

## 🏗️ معماری

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 16)                   │
│              port 3000 — Rewrite Proxy → API                │
│   ۵۰+ صفحه │ RTL │ Dark Mode │ Responsive │ Charts        │
└──────────────────────────┬──────────────────────────────────┘
                           │ /api/v1/*
┌──────────────────────────▼──────────────────────────────────┐
│                   API Gateway (FastAPI)                      │
│              port 8000 — ۴۵+ endpoint                       │
│   CORS │ Rate Limit │ Logging │ Timing │ Auth (optional)    │
└────┬──────────────┬───────────────┬─────────────────────────┘
     │              │               │
┌────▼────┐  ┌──────▼──────┐  ┌────▼────────────────┐
│ Services │  │   Jobs      │  │   ML Worker          │
│ 40+ svc  │  │ Scheduler   │  │ Training/Inference   │
└────┬─────┘  └──────┬──────┘  └────┬────────────────┘
     │              │               │
┌────▼──────────────▼───────────────▼─────────────────────────┐
│                    Infrastructure                            │
│  PostgreSQL 16 + TimescaleDB │ Redis 7 │ MinIO │ Telegram  │
└─────────────────────────────────────────────────────────────┘
```

### اجزای اصلی

| لایه | وظیفه | فناوری |
|------|--------|--------|
| **Frontend** | واسط کاربری تحت وب | Next.js 16, React 19, Tailwind CSS v4, Recharts |
| **API Gateway** | REST API اصلی | FastAPI, Uvicorn, Pydantic v2 |
| **Services** | منطق تجاری | Python 3.11+, ۴۰+ سرویس |
| **Backtesting** | موتور بک‌تست | Event-driven replay, ABM, Microstructure |
| **ML Pipeline** | یادگیری ماشین | scikit-learn, XGBoost, LightGBM, PyTorch |
| **Jobs** | وظایف زمان‌بندی‌شده | APScheduler, Background Tasks |
| **Database** | ذخیره‌سازی داده | PostgreSQL 16 + TimescaleDB |
| **Cache** | کش و صف | Redis 7 |
| **Storage** | ذخیره‌سازی فایل | MinIO (S3-compatible) |
| **Monitoring** | مانیتورینگ | OpenTelemetry, Prometheus |
| **Notifications** | هشدارها | Telegram Bot |

---

## 🌍 بازارهای پشتیبانی‌شده

| بازار | شناسه | دامنه نوسان | سشن | حراج | سفارش بازار |
|-------|-------|------------|------|------|------------|
| **بورس تهران (TSE)** | `tse` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **فرابورس (IFB)** | `ifb` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **بازار پایه** | `base_market` | ۳-۱٪ پلکانی | ۰۸:۴۵-۱۲:۳۰ | دوره‌ای | ❌ |
| **ETF** | `etf` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **اوراق بدهی** | `bonds` | ±۱٪ | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| **مشتقه** | `derivatives` | متغیر | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| **بورس کالا (IME)** | `ime` | ±۵٪ | ۱۱:۴۵-۱۸:۰۰ | ✅ | ✅ |
| **بورس انرژی** | `energy` | ±۵٪ | ۱۱:۴۵-۱۸:۰۰ | دوره‌ای | ❌ |
| **رمزارز** | `crypto` | بدون محدودیت | ۲۴/۷ | ❌ | ✅ |
| **طلا و سکه** | `gold` | متغیر | متغیر | ❌ | ✅ |
| **ارز** | `fx` | متغیر | متغیر | ❌ | ✅ |

---

## 🛠️ تکنولوژی‌ها

### Backend

| تکنولوژی | نسخه | کاربرد |
|-----------|-------|---------|
| **Python** | 3.11+ | زبان اصلی |
| **FastAPI** | 0.109+ | REST API |
| **SQLAlchemy** | 2.0+ | ORM |
| **Alembic** | 1.13+ | مهاجرت دیتابیس |
| **Pydantic** | 2.5+ | اعتبارسنجی داده |
| **httpx / aiohttp** | — | HTTP client ناهمزمان |
| **APScheduler** | 3.10+ | زمان‌بندی وظایف |
| **Redis** | 5.0+ | کش و صف |
| **Pandas / NumPy** | — | پردازش داده |
| **OpenTelemetry** | 1.22+ | ردیابی توزیع‌شده |
| **Prometheus** | 0.19+ | متریک |
| **MinIO** | 7.2+ | ذخیره‌سازی آبجکت |

### ML (اختیاری)

| تکنولوژی | کاربرد |
|-----------|---------|
| **scikit-learn** | مدل‌های پایه |
| **XGBoost** | Gradient Boosting |
| **LightGBM** | Gradient Boosting سریع |
| **CatBoost** | Gradient Boosting با categorical |
| **PyTorch** | یادگیری عمیق |
| **SHAP** | تفسیرپذیری مدل |

### Frontend

| تکنولوژی | نسخه | کاربرد |
|-----------|-------|---------|
| **Next.js** | 16.2.9 | فریمورک React |
| **React** | 19.2.4 | UI Library |
| **TypeScript** | 5.x | Type Safety |
| **Tailwind CSS** | 4.x | استایل‌دهی |
| **Recharts** | 3.8+ | نمودارها |
| **TanStack Query** | 5.x | مدیریت state سرور |
| **Lightweight Charts** | 5.2+ | نمودار کندلاستیک |
| **Vitest** | 4.1+ | تست واحد |

### Database

| سرویس | نسخه | کاربرد |
|-------|-------|---------|
| **PostgreSQL** | 16 | دیتابیس اصلی |
| **TimescaleDB** | latest | داده‌های زمانی |
| **Redis** | 7.0 | کش و صف |
| **MinIO** | — | ذخیره‌سازی آبجکت |

---

## 📁 ساختار پروژه

```
iran-market-platform/
├── apps/                          # لایه اپلیکیشن
│   ├── api/                       # FastAPI اصلی
│   │   ├── app.py                 # ساخت و پیکربندی FastAPI
│   │   ├── router.py              # مسیریابی API
│   │   ├── endpoints/             # ۴۵+ endpoint
│   │   ├── middleware.py          # Logging, Rate Limit, Timing
│   │   └── error_handlers.py     # مدیریت خطا
│   ├── admin/                     # پنل مدیریت (port 8001)
│   ├── scheduler/                 # زمان‌بندی وظایف
│   ├── worker/                    # worker پس‌زمینه
│   └── cli/                       # رابط خط فرمان
│
├── backtesting/                   # 🎯 موتور بک‌تست
│   ├── abm/                       # Agent-Based Modeling
│   ├── alpha/                     # تولید و ارزیابی آلفا
│   ├── analytics/                 # تحلیل عملکرد
│   ├── calibration/               # کالیبراسیون پارامترها
│   ├── engine/                    # هسته شبیه‌سازی
│   ├── execution/                 # شبیه‌ساز اجرا
│   ├── experiment/                # موتور آزمایش
│   ├── market/                    # موتور بازار و قوانین
│   ├── microstructure/            # ریزساختار بازار
│   ├── metrics/                   # معیارهای عملکرد
│   ├── multi_market/              # چندبازاری
│   ├── optimization/              # بهینه‌سازی پارامترها
│   ├── portfolio/                 # مدیریت پرتفوی
│   ├── regime/                    # تشخیص رژیم بازار
│   ├── reporting/                 # تولید گزارش
│   ├── risk/                      # مدیریت ریسک
│   ├── scenarios/                 # سناریوهای بازار
│   ├── signals/                   # سیگنال‌ها
│   ├── strategies/                # استراتژی‌های معاملاتی
│   │   ├── rule_based/            # استراتژی‌های قاعده‌محور
│   │   ├── factor_based/          # استراتژی‌های فاکتورمحور
│   │   ├── ml_based/              # استراتژی‌های ML
│   │   ├── options/               # استراتژی‌های مشتقه
│   │   └── portfolios/            # استراتژی‌های پرتفوی
│   └── visualization/             # مصورسازی
│
├── brsapi/                        # یکپارچه‌سازی BrsApi.ir
│   ├── client.py                  # HTTP client
│   ├── config.py                  # پیکربندی
│   ├── parsers/                   # پارسرهای داده
│   ├── repositories/              # لایه دسترسی به داده
│   └── services/                  # سرویس‌های هماهنگ‌سازی
│
├── core/                          # هسته سیستم
│   ├── config/                    # پیکربندی سراسری
│   ├── cache.py                   # مدیریت کش
│   ├── concurrency/               # ابزارهای همزمانی
│   ├── constants/                 # ثابت‌ها
│   ├── database.py                # اتصال دیتابیس
│   ├── dependency_injection/      # DI container
│   ├── enums/                     # enumها
│   ├── exceptions/                # خطاهای سفارشی
│   ├── health/                    # سلامت سیستم
│   ├── json/                      # ابزارهای JSON
│   ├── logging/                   # لاگینگ
│   ├── rate_limit/                # محدودیت نرخ
│   ├── resilience/                # مقاومت خطا
│   ├── retry/                     # تلاش مجدد
│   ├── security/                  # امنیت
│   └── time/                      # ابزارهای زمانی
│
├── services/                      # سرویس‌های تجاری
│   ├── chat/                      # موتور مکالمه
│   ├── smart_money/               # Smart Money (۹ لایه)
│   ├── codal_analysis/            # تحلیل کدال
│   ├── stock_assistant_service.py # دستیار سهام
│   ├── unified_assistant_service.py # دستیار یکپارچه
│   ├── screener_service.py        # غربالگر
│   ├── smart_screener_v2.py       # غربالگر پیشرفته
│   ├── strategy_generator.py      # تولید خودکار استراتژی
│   ├── backtest_framework.py      # فریمورک بک‌تست
│   ├── quant_signal_orchestrator.py # هماهنگ‌کننده سیگنال
│   └── ... (۶۰+ سرویس دیگر)
│
├── models/                        # مدل‌های دیتابیس
├── schemas/                       # Pydantic schemaها
├── ingestion/                     # جمع‌آوری داده
├── pipelines/                     # پایپ‌لاین‌های پردازش
├── providers/                     # تأمین‌کنندگان داده
├── jobs/                          # وظایف زمان‌بندی‌شده
├── ml/                            # ML Pipeline
├── migrations/                    # مهاجرت دیتابیس
├── scripts/                       # اسکریپت‌های کاربردی
├── tests/                         # تست‌ها
├── monitoring/                    # مانیتورینگ
├── frontend/                      # 🟢 فرانت‌اند Next.js
│   ├── src/
│   │   ├── app/                   # ۵۰+ صفحه
│   │   ├── components/            # کامپوننت‌ها
│   │   ├── hooks/                 # هوک‌ها
│   │   └── lib/                   # ابزارها
│   └── package.json
│
├── docker-compose.yml             # سرویس‌های Docker
├── Makefile                       # دستورات کاربردی
├── pyproject.toml                 # پیکربندی پروژه
└── README.md                      # این فایل
```

---

## 🚀 راه‌اندازی سریع

### پیش‌نیازها

- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL 16** (یا Docker)
- **Redis 7** (یا Docker)

### ۱. کلون و نصب

```bash
# کلون پروژه
git clone https://github.com/your-username/iran-market-platform.git
cd iran-market-platform

# نصب وابستگی‌های بک‌اند
pip install -r requirements.txt

# (اختیاری) نصب وابستگی‌های ML
pip install -e ".[ml]"

# (اختیاری) نصب وابستگی‌های توسعه
pip install -e ".[dev]"
```

### ۲. پیکربندی محیط

```bash
# ایجاد فایل .env
# (فایل .env.example در ریپازیتوری موجود نیست — مقادیر زیر را دستی ایجاد کنید)
touch .env
```

یا فایل `.env` را با محتوای زیر بسازید:

متغیرهای محیطی اصلی:

```env
# دیتابیس
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/market

# Redis
REDIS_URL=redis://localhost:6379/0

# امنیت
SECRET_KEY=your-secret-key-here
CORS_ORIGINS=["http://localhost:3000"]

# API Keys (اختیاری)
BRSAPI_API_KEY=your-brsapi-key
CODAL_API_KEY=your-codal-key

# Telegram (اختیاری)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### ۳. مهاجرت دیتابیس

```bash
alembic upgrade head
```

### ۴. اجرای سرور

```bash
# اجرای بک‌اند
python main.py
# یا
uvicorn apps.api.app:app --reload --host 0.0.0.0 --port 8000

# اجرای فرانت‌اند (ترمینال جداگانه)
cd frontend
npm install --no-audit --no-fund
npm run dev
```

### ۵. دسترسی

| سرویس | آدرس | توضیح |
|-------|------|-------|
| **API** | http://localhost:8000 | FastAPI اصلی |
| **Swagger** | http://localhost:8000/docs | مستندات API |
| **ReDoc** | http://localhost:8000/redoc | مستندات زیبا |
| **Frontend** | http://localhost:3000 | فرانت‌اند Next.js |
| **Admin** | http://localhost:8001 | پنل مدیریت |

---

## 🐳 استفاده با Docker

### اجرای سریع

```bash
# ساخت و اجرای همه سرویس‌ها
docker compose up --build -d

# مشاهده لاگ‌ها
docker compose logs -f

# توقف و حذف
docker compose down -v
```

### سرویس‌های Docker

| سرویس | پورت | توضیح |
|-------|------|-------|
| **Backend (FastAPI)** | `8000` | سرویس اصلی REST API |
| **Frontend (Next.js)** | `3000` | واسط کاربری |
| **Admin Panel** | `8001` | پنل مدیریت |
| **PostgreSQL + TimescaleDB** | `5432` | دیتابیس اصلی |
| **Redis** | `6379` | کش و صف |

### Dockerfile‌ها

```
├── Dockerfile                    # بک‌اند اصلی
├── Dockerfile.admin              # پنل مدیریت
├── Dockerfile.worker             # worker پس‌زمینه
├── Dockerfile.decision-engine    # موتور تصمیم‌گیری
└── frontend/Dockerfile.dev       # فرانت‌اند توسعه
```

---

## 🖥️ فرانت‌اند Next.js

### نمای کلی

فرانت‌اند با **Next.js 16**, **React 19**, **TypeScript 5**, **Tailwind CSS v4** و **Recharts** ساخته شده است. همه درخواست‌های API از طریق Next.js Rewrite Proxy عبور می‌کنند.

### صفحات اصلی

| مسیر | صفحه | توضیح |
|------|-------|---------|
| `/` | **داشبورد** | شاخص کل، حجم معاملات، ترکیب صنایع |
| `/markets` | **بازارها** | وضعیت لحظه‌ای بازار |
| `/analysis` | **تحلیل** | تحلیل تکنیکال و بنیادی |
| `/smart-screener` | **غربالگر هوشمند** | غربالگری با ۴۰۰+ فیلتر |
| `/screener` | **غربالگر** | غربالگری ساده |
| `/screener110` | **غربالگر ۱۱۰** | غربالگری CANSLIM |
| `/signals` | **سیگنال‌ها** | سیگنال‌های معاملاتی |
| `/signals/all` | **همه سیگنال‌ها** | سیگنال‌های همه بازارها |
| `/smart-money` | **Smart Money** | تحلیل پول هوشمند |
| `/backtest` | **بک‌تست** | اجرای استراتژی‌های معاملاتی |
| `/portfolio` | **پرتفوی** | مدیریت سبد سهام |
| `/news` | **اخبار** | اخبار و اطلاعیه‌ها |
| `/codal` | **کدال** | اطلاعیه‌های شرکت‌ها |
| `/brsapi` | **BrsApi** | کامودیتی، رمزارز، طلا، ارز |
| `/brsapi/history/[symbol]` | **تاریخچه** | تاریخچه نماد خاص |
| `/indicators` | **اندیکاتورها** | نمودار اندیکاتورها |
| `/heatmap` | **هیت‌مپ** | هیت‌مپ بازار |
| `/commodities` | **کامودیتی** | قیمت جهانی |
| `/crypto` | **رمزارز** | قیمت ارزهای دیجیتال |
| `/funds` | **صندوق‌ها** | صندوق‌های سرمایه‌گذاری |
| `/macro` | **اقتصاد کلان** | داده‌های کلان |
| `/economic-calendar` | **تقویم اقتصادی** | رویدادهای اقتصادی |
| `/decision-engine` | **موتور تصمیم** | معماری سازمانی |
| `/recommendations` | **پیشنهادات** | پیشنهادات خرید/فروش |
| `/alerts` | **هشدارها** | هشدارهای قیمتی |
| `/watchlist` | **دیده‌بان** | نمادهای تحت نظر |
| `/chat` | **چت** | مکالمه با هوش مصنوعی |
| `/settings` | **تنظیمات** | پیکربندی حساب |
| `/admin` | **ادمین** | پنل مدیریت |
| `/jobs` | **شغل‌ها** | مدیریت وظایف |
| `/ml` | **ML** | مدل‌های یادگیری ماشین |
| `/reports` | **گزارش‌ها** | گزارش‌های تولید شده |
| `/tables` | **جداول** | مرور جداول دیتابیس |
| `/health` | **سلامت** | وضعیت سیستم |

### کامپوننت‌های نمودار

| کامپوننت | توضیح |
|----------|---------|
| `AreaChartCard` | نمودار مساحت با گرادیان رنگی |
| `BarChartCard` | نمودار میله‌ای با رنگ‌بندی مثبت/منفی |
| `PieChartCard` | نمودار دوناتی با Legend سفارشی |
| `CandleChartCard` | کندلاستیک با Custom Shape و نوار حجم |
| `TradingViewChart` | نمودار TradingView (lightweight-charts) |
| `SentimentChart` | نمودار احساسات |
| `EquityCurveChart` | نمودار منحنی سرمایه |

---

## 📡 API Reference

### ساختار URL

```
GET  /api/v1/{resource}
POST /api/v1/{resource}
GET  /api/v1/{resource}/{id}
```

### گروه‌های اصلی API

| گروه | مسیر | توضیح |
|------|------|-------|
| **Health** | `/api/v1/health` | بررسی سلامت |
| **Auth** | `/api/v1/auth` | ورود، ثبت‌نام، توکن |
| **Market** | `/api/v1/market` | نمای کلی بازار |
| **Instruments** | `/api/v1/instruments` | نمادها و ابزارها |
| **Quotes** | `/api/v1/quotes` | قیمت‌ها |
| **Trades** | `/api/v1/trades` | معاملات |
| **Signals** | `/api/v1/signals` | سیگنال‌ها |
| **Screener** | `/api/v1/screener` | غربالگری |
| **Screener V2** | `/api/v1/screener-v2` | غربالگر پیشرفته |
| **Screener110** | `/api/v1/screener110` | غربالگر CANSLIM |
| **Saved Filters** | `/api/v1/saved-filters` | فیلترهای ذخیره شده |
| **Smart Money** | `/api/v1/smart-money` | تحلیل پول هوشمند |
| **Backtests** | `/api/v1/backtests` | بک‌تست |
| **Compose** | `/api/v1/compose` | ترکیب استراتژی |
| **ML** | `/api/v1/ml` | یادگیری ماشین |
| **News** | `/api/v1/news` | اخبار |
| **Codal** | `/api/v1/codal` | اطلاعیه‌ها |
| **Macro** | `/api/v1/macro` | اقتصاد کلان |
| **Chat** | `/api/v1/chat` | مکالمه |
| **Stock Assistant** | `/api/v1/stock-assistant` | دستیار سهام |
| **Assistant** | `/api/v1/assistant` | دستیار یکپارچه |
| **BrsApi** | `/api/v1/brsapi` | کامودیتی، رمزارز |
| **Tabdeal** | `/api/v1/tabdeal` | صرافی تبادل |
| **Decision Engine** | `/api/v1/decision-engine` | موتور تصمیم |
| **Market Dashboard** | `/api/v1/market-dashboard` | داشبورد بازار |
| **Market Watch** | `/api/v1/market-watch` | دیده‌بان بازار |
| **Market Insights** | `/api/v1/market-insights` | بینش بازار |
| **Signal Insights** | `/api/v1/signal-insights` | بینش سیگنال |
| **Queue Analysis** | `/api/v1/queue-analysis` | تحلیل صف |
| **WebSocket** | `/api/v1/ws` | داده لحظه‌ای |

### نمونه درخواست

```bash
# دریافت نمای کلی بازار
curl http://localhost:8000/api/v1/market/overview

# دریافت سیگنال‌ها
curl http://localhost:8000/api/v1/signals

# اجرای غربالگری
curl -X POST http://localhost:8000/api/v1/screener/scan \
  -H "Content-Type: application/json" \
  -d '{"filters": [{"field": "volume", "op": ">", "value": 1000000}]}'

# دریافت قیمت رمزارز
curl http://localhost:8000/api/v1/brsapi/crypto

# دریافت اطلاعیه‌های کدال
curl http://localhost:8000/api/v1/codal

# اجرای بک‌تست
curl -X POST http://localhost:8000/api/v1/backtests/run \
  -H "Content-Type: application/json" \
  -d '{"strategy": "momentum", "symbol": "فولاد", "start_date": "2024-01-01"}'
```

---

## 🎯 موتور بک‌تست

### معماری

```
Data Lake → Event Builder → Unified Timeline → Replay Engine
                                                      ↓
                                               Market Engine
                                                      ↓
                                           Execution Simulator
                                                      ↓
                                            Portfolio Manager
                                                      ↓
                                            Analytics Engine
```

### استراتژی‌های پیش‌فرض

#### Rule-Based
| استراتژی | توضیح |
|----------|---------|
| `MomentumStrategy` | دنبال‌کننده روند |
| `MeanReversionStrategy` | بازگشت به میانگین |
| `MovingAverageCross` | تقاطع میانگین متحرک |
| `RSIReversion` | بازگشت RSI |
| `BreakoutStrategy` | شکست مقاومت |
| `SupportResistanceStrategy` | حمایت و مقاومت |
| `HalfTrendStrategy` | نیم‌روند |
| `SqueezeMomentumStrategy` | فشردگی مومنتوم |
| `VolatilityBreakout` | شکست نوسان |
| `PhaseStrategy` | فاز بازار |

#### Factor-Based
| استراتژی | توضیح |
|----------|---------|
| `MomentumFactorStrategy` | فاکتور مومنتوم |
| `ValueFactorStrategy` | فاکتور ارزش |
| `QualityFactorStrategy` | فاکتور کیفیت |
| `LowVolatilityStrategy` | فاکتور نوسان کم |
| `MultiFactorStrategy` | ترکیب چند فاکتور |

#### ML-Based
| استراتژی | توضیح |
|----------|---------|
| `ClassificationSignalStrategy` | سیگنال طبقه‌بندی |
| `ForecastSignalStrategy` | پیش‌بینی قیمت |
| `RankingSignalStrategy` | رتبه‌بندی نمادها |
| `RegimeAwareStrategy` | آگاه از رژیم بازار |

#### Options
| استراتژی | توضیح |
|----------|---------|
| `CoveredCallStrategy` | کالا پوششی |
| `ProtectivePutStrategy` | پوت حفاظتی |
| `BullCallSpreadStrategy` | اسپرد کال صعودی |
| `BearPutSpreadStrategy` | اسپرد پوت نزولی |
| `StraddleStrategy` | Straddle |
| `StrangleStrategy` | Strangle |

#### Portfolio
| استراتژی | توضیح |
|----------|---------|
| `EqualWeightStrategy` | وزن مساوی |
| `MaxSharpeStrategy` | حداکثر شارپ |
| `MinimumVarianceStrategy` | حداقل واریانس |
| `RiskParityStrategy` | برابری ریسک |
| `TacticalAllocationStrategy` | تخصیص تاکتیکی |

### معیارهای عملکرد

| معیار | توضیح |
|-------|---------|
| **CAGR** | نرخ بازده سالانه مرکب |
| **Sharpe Ratio** | نسبت بازده به ریسک |
| **Sortino Ratio** | نسبت بازده به ریسک منفی |
| **Max Drawdown** | حداکثر افت سرمایه |
| **Win Rate** | نرخ برد |
| **Profit Factor** | فاکتور سود |
| **Total Trades** | تعداد کل معاملات |
| **Calmar Ratio** | نسبت کالمر |
| **Deflated Sharpe** | شارپ تعدیل‌شده |

---

## 🤖 موتور سیگنال هوشمند

### چرخه بازخورد خودکار

```
تولید سیگنال (هر ساعت)
       ↓
ثبت سیگنال در دیتابیس
       ↓
پیگیری نتیجه (Outcome Tracking)
       ↓
محاسبه دقت (Accuracy)
       ↓
اگر دقت < 50% → بازآموزی خودکار
       ↓
اگر ۳ شکست متوالی → هشدار تلگرام
```

### مولفه‌ها

| مولفه | توضیح |
|-------|---------|
| **QuantSignalOrchestrator** | هماهنگ‌کننده اصلی |
| **SignalVotingSystem** | رأی‌گیری چند مدل |
| **ConfidenceCalibrator** | کالیبراسیون اطمینان |
| **SignalAccuracyTracker** | ردیابی دقت |
| **SignalPerformanceTracker** | ردیابی عملکرد |
| **AutoRetrainPipeline** | بازآموزی خودکار |
| **SignalDecisionEngine** | موتور تصمیم‌گیری |

---

## 💰 موتور Smart Money (۹ لایه)

| لایه | نام | توضیح |
|------|------|---------|
| ۱ | **Price-Volume Analysis** | تحلیل حجم و قیمت |
| ۲ | **Absorption Detection** | تشخیص جذب سفارشات بزرگ |
| ۳ | **Ownership Analysis** | تحلیل مالکیت حقیقی/حقوقی |
| ۴ | **Compression Detection** | تشخیص فشردگی قیمت |
| ۵ | **Relative Strength** | قدرت نسبی نماد |
| ۶ | **Breakout Analysis** | تحلیل شکست سطوح |
| ۷ | **Buyer Power** | قدرت خریدار |
| ۸ | **Microstructure Analysis** | تحلیل ریزساختار بازار |
| ۹ | **Breakout Quality** | کیفیت شکست |

---

## 🔍 غربالگری هوشمند

### فیلترها

- **فیلترهای قیمتی**: قیمت، تغییر قیمت، نسبت قیمت به حداکثر/حداقل
- **فیلترهای حجمی**: حجم معاملات، نسبت حجم به میانگین
- **فیلترهای اندیکاتوری**: RSI, MACD, Bollinger Bands, Moving Averages
- **فیلترهای بنیادی**: EPS, P/E, P/B, ROE, ROA
- **فیلترهای Smart Money**: امتیاز پول هوشمند، فاز بازار
- **فیلترهای تکنیکال**: الگوهای کندلی، حمایت/مقاومت
- **فیلترهای بازار**: بازار، صنعت، نوع نماد

### پشتیبانی از منطق OR/AND

```
"حجم بالای ۱ میلیون و RSI زیر ۳۰" → AND
"حجم بالا یا RSI زیر ۳۰" → OR
```

تشخیص خودکار با کلمات کلیدی فارسی (`یا`) و انگلیسی (`or`).

---

## 💬 موتور مکالمه

### ۲۰ سطح هوشمندی

1. **Intent Classification**: تشخیص قصد کاربر
2. **Entity Extraction**: استخراج نماد، تاریخ، عدد
3. **Dialog Management**: مدیریت مکالمه چندمرحله‌ای
4. **Context Tracking**: ردیابی زمینه مکالمه
5. **Chart Generation**: تولید خودکار نمودار
6. **Sentiment Analysis**: تحلیل احساسات
7. **News Integration**: یکپارچه‌سازی اخبار
8. **Comparison Engine**: مقایسه نمادها
9. **Personalizer**: شخصی‌سازی پاسخ‌ها
10. **Suggestion Engine**: پیشنهادات هوشمند

---

## 🧠 موتور تصمیم‌گیری

موتور تصمیم‌گیری بر اساس داده‌های معماری سازمانی عمل می‌کند:

- **Auto-Seeding**: پر کردن خودکار از فایل‌های JSON
- **Decision Support**: پشتیبانی تصمیم‌گیری
- **Enterprise Architecture**: مدیریت داده‌های معماری

---

## 🤖 Machine Learning Pipeline

### مدل‌ها

| مدل | کاربرد |
|-----|---------|
| **XGBoost** | طبقه‌بندی سیگنال |
| **LightGBM** | طبقه‌بندی سریع |
| **CatBoost** | طبقه‌بندی با categorical |
| **Random Forest** | مجموعه درخت تصمیم |
| **Neural Network** | یادگیری عمیق |

### Pipeline

```
جمع‌آوری داده → پیش‌پردازش → ویژگی‌سازی → آموزش → ارزیابی → استقرار
                                                        ↓
                                                   بازآموزی خودکار
```

---

## 🔗 یکپارچه‌سازی BrsApi.ir

### داده‌های دریافتی

| نوع | توضیح |
|-----|---------|
| **Commodity** | کامودیتی‌های جهانی |
| **Crypto** | ارزهای دیجیتال |
| **Gold Coin** | سکه و طلا |
| **Currency** | ارز |
| **Codal** | اطلاعیه‌های شرکت‌ها |
| **History** | تاریخچه قیمت |

### Rate Limiting

- **Daily Limit**: ۱۰,۰۰۰ درخواست
- **5-min Limit**: ۵۰۰ درخواست
- **Concurrency**: ۵ درخواست هم‌زمان
- **Retry**: تلاش مجدد با backoff

---

## ⏰ سیستم شغل‌ها

### شغل‌های خودکار

| شغل | زمان‌بندی | توضیح |
|-----|----------|---------|
| **Orchestrator Cron** | هر ساعت | تولید سیگنال + بازخورد |
| **Fund Sync** | هر ۱۵ دقیقه | به‌روزرسانی صندوق‌ها |
| **News Fetch** | هر روز | دریافت اخبار |
| **BrsApi Sync** | هر روز | هماهنگ‌سازی BrsApi |
| **Codal Sync** | هر روز | هماهنگ‌سازی کدال |
| **Model Retrain** | هنگام افت دقت | بازآموزی مدل‌ها |

### مدیریت شغل‌ها

```bash
# مشاهده شغل‌ها
GET /api/v1/jobs

# اجرای دستی شغل
POST /api/v1/jobs/{job_id}/run

# متوقف کردن شغل
POST /api/v1/jobs/{job_id}/stop
```

---

## 📊 مانیتورینگ

### OpenTelemetry

- **Tracing**: ردیابی توزیع‌شده درخواست‌ها
- **Metrics**: متریک‌های سیستم
- **Logs**: لاگینگ یکپارچه

### Prometheus

```bash
# متریک‌ها
GET /metrics
```

### Health Checks

```bash
# بررسی سلامت
GET /api/v1/health
GET /api/v1/health/ready
GET /api/v1/health/live
GET /api/v1/health/full
```

### Telegram Alerts

#### راه‌اندازی ربات تلگرام:

1. با `@BotFather` در تلگرام ربات بسازید
2. توکن ربات را کپی کنید
3. ربات را در گروه/چت خصوصی اضافه کنید
4. `TELEGRAM_BOT_TOKEN` و `TELEGRAM_CHAT_ID` را در `.env` تنظیم کنید

#### انواع هشدار:

- **۳ شکست متوالی**: هشدار فوری
- **افت دقت زیر ۵۰٪**: هشدار بازآموزی
- **بازیابی**: اطلاع‌رسانی بازگشت به حالت عادی

---

## ⚙️ پیکربندی

### متغیرهای محیطی اصلی

| متغیر | پیش‌فرض | توضیح |
|-------|---------|---------|
| `DATABASE_URL` | — | URL اتصال دیتابیس |
| `REDIS_URL` | — | URL اتصال Redis |
| `SECRET_KEY` | — | کلید امنیتی |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | منشأهای مجاز |
| `ENV` | `development` | محیط اجرا |
| `API_PREFIX` | `/api/v1` | پیشوند API |
| `LOG_LEVEL` | `INFO` | سطح لاگ |
| `BRSAPI_API_KEY` | — | کلید BrsApi |
| `CODAL_API_KEY` | — | کلید کدال |
| `TELEGRAM_BOT_TOKEN` | — | توکن ربات تلگرام |
| `TELEGRAM_CHAT_ID` | — | شناسه چت تلگرام |

### پیکربندی تولید

```python
# core/config/__init__.py
class Settings(BaseSettings):
    environment: str = "production"
    cors_origins: list[str] = ["https://yourdomain.com"]
    secret_key: str = "your-secure-secret-key"
    database_url: str = "postgresql+asyncpg://..."
```

---

## 📋 دستورات کاربردی

### Makefile

```bash
# نصب وابستگی‌ها
make install

# بررسی کیفیت
make lint              # ruff linter
make typecheck         # mypy type checker
make test              # تست‌های unit
make test-all          # تمام تست‌ها

# اجرای محلی
make dev               # API با hot-reload
make api               # API بدون hot-reload
make admin             # پنل مدیریت (port 8001)
make worker            # worker پس‌زمینه

# توجه: make dev-all از PowerShell استفاده می‌کند (فقط ویندوز)
# در لینوکس/مک، هر سرویس را در ترمینال جداگانه اجرا کنید

# Docker
make docker-up         # ساخت و اجرا
make docker-build      # ساخت imageها
make docker-down       # توقف و حذف
make docker-logs       # مشاهده لاگ‌ها

# دیتابیس
make backup            # بک‌آپ PostgreSQL
make migrate           # اجرای مهاجرت
make migrate-new       # ساخت مهاجرت جدید

# تولید
make prod-check        # بررسی پیکربندی تولید
make clean             # پاکسازی
```

---

## 🗄️ ساختار دیتابیس

سکوی داده روی **PostgreSQL 16 + TimescaleDB** اجرا می‌شود و در حال حاضر **122 جدول** دارد
(تخمین کل ردیف‌ها: **~32,896,752**). جدول‌های بزرگ سری‌زمانی با TimescaleDB به هایپرتیبل تبدیل شده‌اند.

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
    candlesticks {}
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
    symbol_snapshots {}
    trades {}
    backtest_runs {}
    backtest_trades {}
    compare_results {}
    generated_strategies {}
    queue_analysis_results {}
    screener_profiles {}
    screener_signals {}
    screener_snapshots {}
    signal_accuracy {}
    signals {}
    decision_results {}
    job_runs {}
    alerts {}
    commodity_certificates {}
    commodity_funds {}
    commodity_futures {}
    commodity_options {}
    commodity_prices {}
    commodity_trades {}
    gold_currency_prices {}
    instruments {}
    portfolio_positions {}
    recommendations {}
    saved_filters {}
    symbols {}
    users {}
    account_mappings {}
    analysis_reports {}
    brsapi_codal_announcements {}
    brsapi_codal_attachments {}
    codal_announcements {}
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
    candlesticks ||--o{ symbols : "دارای رابطه"
    codal_announcements ||--o{ symbols : "دارای رابطه"
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
    daily_history ||--o{ symbols : "دارای رابطه"
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
    intraday_trades ||--o{ symbols : "دارای رابطه"
    ml_predictions ||--o{ symbols : "دارای رابطه"
    ml_symbol_results ||--o{ symbols : "دارای رابطه"
    open_interest_history ||--o{ option_contracts : "دارای رابطه"
    option_contracts ||--o{ symbols : "دارای رابطه"
    option_snapshots ||--o{ option_contracts : "دارای رابطه"
    option_trades ||--o{ option_contracts : "دارای رابطه"
    options ||--o{ symbols : "دارای رابطه"
    orderbook_snapshots ||--o{ symbols : "دارای رابطه"
    orderbooks ||--o{ symbols : "دارای رابطه"
    portfolio_positions ||--o{ symbols : "دارای رابطه"
    queue_analysis_results ||--o{ symbols : "دارای رابطه"
    quotes ||--o{ symbols : "دارای رابطه"
    recommendations ||--o{ symbols : "دارای رابطه"
    saved_filters ||--o{ users : "دارای رابطه"
    screener_profiles ||--o{ symbols : "دارای رابطه"
    screener_signals ||--o{ symbols : "دارای رابطه"
    screener_snapshots ||--o{ symbols : "دارای رابطه"
    shareholders ||--o{ symbols : "دارای رابطه"
    signal_accuracy ||--o{ symbols : "دارای رابطه"
    signals ||--o{ symbols : "دارای رابطه"
    symbol_snapshots ||--o{ symbols : "دارای رابطه"
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
| `brsapi_candlesticks` | 17 | ~819 | created_at | symbol→symbols |
| `brsapi_commodity_prices` | 19 | ~7,462 | fetched_at | symbol→symbols |
| `brsapi_crypto_daily_history` | 12 | ~18,609 | created_at | symbol→symbols |
| `brsapi_crypto_prices` | 22 | ~19 | fetched_at | symbol→symbols |
| `brsapi_currency_24h` | 18 | ~0 | fetched_at | symbol→symbols |
| `brsapi_currency_prices` | 18 | ~28 | fetched_at | symbol→symbols |
| `brsapi_gold_24h` | 18 | ~0 | fetched_at | symbol→symbols |
| `brsapi_gold_coin_history` | 14 | ~44,207 | created_at | symbol→symbols |
| `brsapi_gold_coin_prices` | 18 | ~9 | fetched_at | symbol→symbols |
| `brsapi_gold_currency_pro_daily_history` | 20 | ~160,567 | created_at | symbol→symbols |
| `brsapi_gold_currency_pro_history_24h` | 14 | ~0 | fetched_at | symbol→symbols |
| `brsapi_gold_currency_pro_prices` | 23 | ~19 | fetched_at | symbol→symbols |
| `brsapi_historical_daily` | 23 | ~8,465,821 | created_at | symbol→symbols |
| `brsapi_historical_real_legal` | 21 | ~906,647 | created_at | symbol→symbols |
| `brsapi_ime_certificates` | 48 | ~3,819 | fetched_at | symbol→symbols |
| `brsapi_ime_funds` | 67 | ~21,019 | fetched_at | symbol→symbols |
| `brsapi_ime_futures` | 59 | ~38 | date_end | symbol→symbols |
| `brsapi_ime_options` | 101 | ~48,213 | fetched_at | symbol→symbols |
| `brsapi_ime_physical_trades` | 37 | ~687 | date_price_settlement | symbol→symbols |
| `brsapi_index_values` | 26 | ~3,437 | fetched_at | symbol→symbols |
| `brsapi_intraday_trades` | 14 | ~1,628,554 | trade_date | symbol→symbols |
| `brsapi_option_snapshots` | 81 | ~374,433 | date_end | symbol→symbols |
| `brsapi_raw_payloads` | 11 | ~0 | fetched_at | — |
| `brsapi_shareholder_records` | 13 | ~772,645 | created_at | symbol→symbols |
| `brsapi_symbol_details` | 65 | ~1,280 | fetched_at | symbol→symbols |
| `brsapi_symbol_snapshots` | 71 | ~826,838 | fetched_at | symbol→symbols |
| `brsapi_sync_log` | 13 | ~25,997 | created_at | — |
| `ml_model_versions` | 13 | ~638 | created_at | — |
| `ml_models` | 11 | ~359 | created_at | — |
| `ml_predictions` | 22 | ~19,960 | created_at | symbol→symbols |
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
| `brsapi_nav_records` | 14 | ~114 | fetched_at | symbol→symbols |
| `candlesticks` | 10 | ~0 | — | FK→symbols |
| `daily_history` | 17 | ~>0 | trade_date | FK→symbols |
| `daily_real_legal` | 16 | ~>0 | trade_date | FK→symbols |
| `etf_nav` | 7 | ~>0 | — | FK→symbols |
| `funds` | 31 | ~26 | snapshot_date | symbol→symbols |
| `indicators` | 13 | ~0 | created_at | symbol→symbols |
| `intraday_trades` | 9 | ~>0 | trade_date | FK→symbols |
| `orderbook_snapshots` | 34 | ~0 | — | FK→symbols |
| `orderbooks` | 12 | ~0 | created_at | symbol→symbols |
| `quotes` | 29 | ~3,374,031 | created_at | symbol→symbols |
| `shareholders` | 8 | ~>0 | record_date | FK→symbols |
| `symbol_snapshots` | 28 | ~0 | — | FK→symbols |
| `trades` | 14 | ~14,851,701 | created_at | symbol→symbols |
| `backtest_runs` | 22 | ~1,579 | start_date | — |
| `backtest_trades` | 18 | ~0 | created_at | symbol→symbols |
| `calibration_models` | 15 | ~0 | — | — |
| `compare_results` | 20 | ~0 | start_date | symbol→symbols |
| `generated_strategies` | 38 | ~0 | created_at | symbol→symbols |
| `generation_batches` | 14 | ~0 | created_at | — |
| `queue_analysis_results` | 30 | ~0 | created_at | symbol→symbols |
| `screener_profiles` | 61 | ~1,562 | created_at | symbol→symbols |
| `screener_signals` | 37 | ~0 | created_at | symbol→symbols |
| `screener_snapshots` | 20 | ~0 | created_at | symbol→symbols |
| `signal_accuracy` | 28 | ~20,550 | created_at | symbol→symbols |
| `signals` | 17 | ~>0 | created_at | symbol→symbols |
| `audit_logs` | 12 | ~0 | — | — |
| `audit_trail` | 10 | ~0 | — | — |
| `decision_architectures` | 9 | ~>0 | created_at | — |
| `decision_results` | 25 | ~0 | created_at | symbol→symbols |
| `job_runs` | 15 | ~0 | created_at | — |
| `provider_health` | 14 | ~0 | created_at | — |
| `provider_health_history` | 8 | ~0 | — | — |
| `alert_history` | 8 | ~217 | — | — |
| `alerts` | 14 | ~1 | created_at | symbol→symbols |
| `commodity_certificates` | 8 | ~125,256 | — | symbol→symbols |
| `commodity_funds` | 8 | ~124 | — | symbol→symbols |
| `commodity_futures` | 11 | ~60 | expiry_date | symbol→symbols |
| `commodity_options` | 11 | ~476 | expiry_date | symbol→symbols |
| `commodity_prices` | 9 | ~>0 | — | symbol→symbols |
| `commodity_trades` | 12 | ~320,005 | created_at | symbol→symbols |
| `dual_date_columns` | 4 | ~102 | — | — |
| `gold_currency_prices` | 12 | ~>0 | — | symbol→symbols |
| `indices` | 8 | ~>0 | — | — |
| `instruments` | 26 | ~499 | created_at | symbol→symbols |
| `symbol_relations` | 13 | ~0 | created_at | — |
| `markets` | 14 | ~0 | created_at | — |
| `portfolio_positions` | 14 | ~0 | created_at | symbol→symbols |
| `portfolios` | 11 | ~0 | created_at | — |
| `recommendations` | 18 | ~0 | created_at | symbol→symbols |
| `saved_filters` | 17 | ~0 | created_at | FK→users |
| `symbols` | 19 | ~511 | created_at | — |
| `users` | 21 | ~0 | created_at | — |
| `account_mappings` | 14 | ~0 | — | FK→dim_account |
| `analysis_reports` | 22 | ~0 | report_date | FK→dim_company، symbol→symbols |
| `brsapi_codal_announcements` | 24 | ~5,053 | date_publish | symbol→symbols |
| `brsapi_codal_attachments` | 18 | ~359 | created_at | symbol→symbols |
| `codal_announcements` | 17 | ~0 | date_publish | symbol→symbols |
| `codal_audit_summary` | 33 | ~451 | report_date | symbol→symbols |
| `codal_financial_statements` | 16 | ~451 | report_date | symbol→symbols |
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
| `import_audit_log` | 9 | ~0 | — | FK→import_document_files |
| `import_document_files` | 18 | ~95,418 | created_at | — |
| `import_document_tables` | 13 | ~522,636 | created_at | FK→import_document_files |
| `macro_indicators` | 15 | ~0 | created_at | — |
| `news_articles` | 16 | ~1,819 | created_at | — |

### خلاصه مشکلات جدول‌ها

تعداد جدول‌هایی که هر نوع مشکل را دارند (هر جدول می‌تواند چند مشکل داشته باشد):

| مشکل | تعداد جدول |
|------|-----------:|
| جدول خالی است | 58 |
| مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست | 43 |
| ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟ | 16 |
| آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید | 10 |
| لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود | 10 |
| بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود | 6 |
| نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است | 3 |
| نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` است | 2 |
| ستون منبع تاریخ `expiry_date` در نمونه NULL دارد | 2 |
| ستون منبع تاریخ `start_date` در نمونه NULL دارد | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_option_snapshots` جایگزین آن است | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_candlesticks` جایگزین آن است | 1 |
| نسخه قدیمی — backfill به `brsapi_candlesticks` می‌نویسد | 1 |
| ۱۲ ردیف یتیم بدون مصرف‌کننده — نسخه‌های زنده `brsapi_nav_records` و `funds` جایگزین‌اند | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_intraday_trades` جایگزین آن است | 1 |
| هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_symbol_snapshots` جایگزین آن است | 1 |
| نسخه قدیمی — `brsapi_symbol_snapshots` (۸۰۳K ردیف) زنده است | 1 |
| رکوردزنی جاب‌ها در `services/job_service.py` پیاده‌سازی نشده — جدول در عمل خالی می‌ماند | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_commodity_prices` جایگزین آن است | 1 |
| هیچ SQL فعالی ندارد — مراجع کد صرفاً از نام ماژول/پکیج هستند | 1 |
| نسخه قدیمی است — جدول زنده `brsapi_codal_announcements` جایگزین آن است | 1 |
| باگ فعال: `services/codal_download_service.py` از این جدول (خالی) می‌خواند → دانلود ضمائم هرگز انجام نمی‌شود | 1 |

### تحلیل عمیق — مشکلات پیدا و ناپیدا

این گزارش با `python scripts/analyze_db_issues.py` تولید می‌شود — مجموع **209 یافته**: 🔴 0 بحرانی، 🟠 6 بالا، 🟡 104 متوسط، 🔵/⚪ 99 کم/اطلاعاتی.

<details>
<summary>نمایش همه 209 یافته (کلیک کنید)</summary>

| شدت | تعداد |
|------|------:|
| 🔴 بحرانی | 0 |
| 🟠 بالا | 6 |
| 🟡 متوسط | 104 |
| 🔵 کم / ⚪ اطلاعاتی | 99 |

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
- 🟡 متوسط `macro_indicators`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `markets`: ستون تاریخ `close_time` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `markets`: ستون تاریخ `open_time` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `ml_symbol_results`: ستون تاریخ `end_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `ml_symbol_results`: ستون تاریخ `start_date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `news_articles`: ستون تاریخ `published_at` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `orderbooks`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `quotes`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*
- 🟡 متوسط `trades`: ستون تاریخ `date` با نوع `character varying` ذخیره شده (باید DATE/TIMESTAMPTZ باشد) → *مهاجرت ستون به نوع زمانی + backfill*

**freshness:**

- 🟡 متوسط `daily_history`: آخرین داده 35 روز پیش است (2026-07-01) → *اجرای جاب سینک مربوطه*
- 🟡 متوسط `intraday_trades`: آخرین داده 32 روز پیش است (2026-07-04) → *اجرای جاب سینک مربوطه*
- 🔵 کم `brsapi_historical_daily`: محاسبه max تاریخ به‌دلیل نبود ایندکس/وقفه انجام نشد
- 🔵 کم `trades`: محاسبه max تاریخ به‌دلیل نبود ایندکس/وقفه انجام نشد
- ⚪ اطلاعاتی `candlesticks`: جدول سری زمانی خالی است
- ⚪ اطلاعاتی `orderbooks`: جدول سری زمانی خالی است
- ⚪ اطلاعاتی `symbol_snapshots`: جدول سری زمانی خالی است

**infra:**

- 🟡 متوسط `-`: 10 هایپرتیبل بدون فشرده‌سازی: candlesticks، commodity_prices، daily_history، daily_real_legal، etf_nav، gold_currency_prices، intraday_trades، orderbook_snapshots → *فعال‌سازی compression + retention policy*
- ⚪ اطلاعاتی `-`: 10 هایپرتیبل TimescaleDB: candlesticks، commodity_prices، daily_history، daily_real_legal، etf_nav، gold_currency_prices، intraday_trades، orderbook_snapshots، shareholders، symbol_snapshots

**legacy:**

- 🟠 بالا `candlesticks`: نسخه قدیمی/تکراری است — `brsapi_candlesticks` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*
- 🟠 بالا `codal_announcements`: نسخه قدیمی/تکراری است — `brsapi_codal_announcements` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*
- 🟠 بالا `commodity_prices`: نسخه قدیمی/تکراری است — `brsapi_commodity_prices` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*
- 🟠 بالا `intraday_trades`: نسخه قدیمی/تکراری است — `brsapi_intraday_trades` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*
- 🟠 بالا `option_snapshots`: نسخه قدیمی/تکراری است — `brsapi_option_snapshots` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*
- 🟠 بالا `symbol_snapshots`: نسخه قدیمی/تکراری است — `brsapi_symbol_snapshots` زنده است (داده اینجا با نسخه زنده همگام نیست) → *پس از تأیید، جدول قدیمی را drop کنید*

**orphan:**

- 🟡 متوسط `alerts`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `codal_audit_summary`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `codal_financial_statements`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `codal_reports`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `ml_symbol_results`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `options`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `screener_profiles`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🟡 متوسط `signal_accuracy`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_candlesticks`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_codal_announcements`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_codal_attachments`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_commodity_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_crypto_daily_history`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_crypto_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_currency_prices`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_gold_coin_history`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_gold_coin_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_gold_currency_pro_daily_history`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_gold_currency_pro_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `brsapi_ime_certificates`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_funds`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_futures`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_options`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_ime_physical_trades`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_index_values`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_nav_records`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_option_snapshots`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `brsapi_symbol_details`: ستون `ins_id` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست
- 🔵 کم `commodity_certificates`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_funds`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_futures`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_options`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `commodity_trades`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `funds`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*
- 🔵 کم `gold_currency_prices`: رجوع به `symbol` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم) → *پاکسازی ردیف‌های یتیم یا تکمیل symbols*

**schema:**

- 🟡 متوسط `commodity_certificates`: فقط ۱ ایندکس دارد اما ~125,256 ردیف دارد → *ایندکس روی ستون‌های پراستفاده اضافه کنید*
- 🟡 متوسط `commodity_trades`: فقط ۱ ایندکس دارد اما ~320,005 ردیف دارد → *ایندکس روی ستون‌های پراستفاده اضافه کنید*
- 🟡 متوسط `brsapi_historical_daily`: constraint یکتا روی `symbol,date` ندارد (upsert با ON CONFLICT پرخطر است) → *ایندکس یکتا اضافه کنید*
- 🟡 متوسط `brsapi_intraday_trades`: constraint یکتا روی `symbol,date,time` ندارد (upsert با ON CONFLICT پرخطر است) → *ایندکس یکتا اضافه کنید*
- 🟡 متوسط `news_articles`: constraint یکتا روی `url` ندارد (upsert با ON CONFLICT پرخطر است) → *ایندکس یکتا اضافه کنید*
- 🟡 متوسط `codal_reports`: constraint یکتا روی `ins_id,report_type` ندارد (upsert با ON CONFLICT پرخطر است) → *ایندکس یکتا اضافه کنید*
- 🔵 کم `account_mappings`: 2 ایندکس با ستون اول یکسان `source_label` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_candlesticks`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
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
- 🔵 کم `brsapi_historical_daily`: 2 ایندکس با ستون اول یکسان `ins_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_daily`: 2 ایندکس با ستون اول یکسان `instrument_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_daily`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_real_legal`: 2 ایندکس با ستون اول یکسان `ins_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_real_legal`: 2 ایندکس با ستون اول یکسان `instrument_id` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_historical_real_legal`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_funds`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_futures`: 2 ایندکس با ستون اول یکسان `contract_code` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_options`: 2 ایندکس با ستون اول یکسان `call_contract_code` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_options`: 2 ایندکس با ستون اول یکسان `put_contract_code` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_ime_physical_trades`: 2 ایندکس با ستون اول یکسان `date_trade` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_intraday_trades`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_nav_records`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_option_snapshots`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_option_snapshots`: 2 ایندکس با ستون اول یکسان `underlying_symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_shareholder_records`: 3 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `brsapi_symbol_snapshots`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
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
- 🔵 کم `signal_accuracy`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `tabdeal_orders`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `tabdeal_trades`: 2 ایندکس با ستون اول یکسان `symbol` → *ادغام ایندکس‌ها*
- 🔵 کم `trades`: 2 ایندکس با ستون اول یکسان `instrument_id` → *ادغام ایندکس‌ها*
- 🔵 کم `volatility_surface`: 2 ایندکس با ستون اول یکسان `underlying_symbol` → *ادغام ایندکس‌ها*

### جزئیات هر جدول (مشکلات + مراجع کد + نمونه داده)

برای هر جدول: مشکلات شناسایی‌شده، مدل ORM و فایل‌های کدی که از آن استفاده می‌کنند، و ۲ ردیف نمونه
(با `LIMIT 2` و بدون `ORDER BY`؛ برای جدول‌های پهن حداکثر ۱۲ ستون اول). مراجع کد بر اساس شمارش
نام جدول در فایل‌های پایتون (به‌جز migrations و همین اسکریپت) محاسبه شده است.

<details>
<summary><code>brsapi_candlesticks</code> — ~819 ردیف، 17 ستون (نمایش 12 ستون از 17)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `CandlestickModel`
- سرویس: `services/history_backfill_service.py` (2)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/backfill_ins_id.py` (1)، `scripts/run_brsapi_sync.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | date | time | open | high | low | close | volume | count | candle_type | created_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | آ س پ |  |  | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 3330 | NULL | 2026-07-15 23:34:47.861865 | … |
| 2 | آباد |  |  | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 4102 | NULL | 2026-07-15 23:35:15.331081 | … |

</details>

<details>
<summary><code>brsapi_commodity_prices</code> — ~7,462 ردیف، 19 ستون (نمایش 12 ستون از 19)</summary>

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
| 1 | XAUUSD | انس طلا | 4021.21 | -31.85 | -0.79 | دلار | precious_metal | 1405/04/24 | 11:11 | 1784101290 | 2026-07-15T07:43:13.727Z | … |
| 2 | XAGUSD | انس نقره | 58.04 | -0.66 | -1.14 | دلار | precious_metal | 1405/04/24 | 11:11 | 1784101290 | 2026-07-15T07:43:13.727Z | … |

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
<summary><code>brsapi_crypto_prices</code> — ~19 ردیف، 22 ستون (نمایش 12 ستون از 22)</summary>

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
| 639667 | بیت‌کوین | BTC | 64352.0 | 0.0 | 0.0 | 1.01 | 1291665779250.0 | 0.0 |  | 0 | 1405/05/14 | … |
| 639668 | اتریوم | ETH | 1871.0 | 0.0 | 0.0 | 0.56 | 226026280215.0 | 0.0 |  | 0 | 1405/05/14 | … |

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
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `bench_schema2_temp.py` (2)، `bench_schema_temp.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | name | price | change_value | change_percent | unit | date | time | time_unix | fetched_at | raw_json | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 14809 | BHD | دینار بحرین | 511870.0 | 5560.0 | 1.1 | IRR | 1405/05/12 | 19:59 | 1785774580 | 2026-08-05T03:17:34.970Z | {"date": "1405/05/12", "time":… | … |
| 14810 | AFN | افغانی | 2933.0 | 30.0 | 1.03 | IRR | 1405/05/12 | 19:54 | 1785774290 | 2026-08-05T03:17:34.970Z | {"date": "1405/05/12", "time":… | … |

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
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `bench_schema2_temp.py` (1)

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
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `bench_schema_temp.py` (2)، `brsapi/services/history_fetch_service.py` (1)

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
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `bench_schema2_temp.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | name | price | change_value | change_percent | unit | date | time | time_unix | fetched_at | raw_json | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 4816 | IR_GOLD_18K | طلای 18 عیار | 18235000.0 | -124600.0 | -0.68 | IRR | 1405/05/13 | 20:49 | 1785863942 | 2026-08-05T03:17:34.935Z | {"date": "1405/05/13", "time":… | … |
| 4817 | IR_GOLD_24K | طلای 24 عیار | 24310000.0 | -167000.0 | -0.68 | IRR | 1405/05/13 | 20:49 | 1785863942 | 2026-08-05T03:17:34.935Z | {"date": "1405/05/13", "time":… | … |

</details>

<details>
<summary><code>brsapi_gold_currency_pro_daily_history</code> — ~160,567 ردیف، 20 ستون (نمایش 12 ستون از 20)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/commodity.py` → `GoldCurrencyProDailyHistoryModel`
- سرویس: `services/quant_signal_orchestrator.py` (4)، `services/auto_retrain_pipeline.py` (3)، `services/multi_timeframe_confirmer.py` (1)، `services/risk_adjusted_filter.py` (1)
- API: `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/signal_insights.py` (1)
- اسکریپت: `scripts/import_history_data.py` (2)، `scripts/add_constraints.py` (1)، `scripts/check_columns.py` (1)، `scripts/check_tables.py` (1)
- تست: `tests/test_brsapi_job_registry.py` (5)
- سایر: `bench_schema_temp.py` (2)، `brsapi/jobs/registry.py` (2)، `bench_schema2_temp.py` (1)، `brsapi/services/history_fetch_service.py` (1)

**نمونه داده:**

| id | symbol | name | sign | unit | url_base_icon | path_icon | date | price_open | price_high | price_low | price_close | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 81766 | OMR | NULL | NULL | NULL | NULL | NULL | 1403-01-25 | 1687400.0 | 1743400.0 | 1686500.0 | 1743400.0 | … |
| 81767 | OMR | NULL | NULL | NULL | NULL | NULL | 1403-01-21 | 1663300.0 | 1671300.0 | 1657400.0 | 1671100.0 | … |

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
| 18579 | cryptocurrency | BTC | Bitcoin | بیت‌کوین |  | 64352.0 | 0.0 | 1.01 | دلار | https://s1.BrsApi.ir/Api/Marke… | BTC.png | … |
| 18580 | cryptocurrency | ETH | Ethereum | اتریوم |  | 1871.0 | 0.0 | 0.56 | دلار | https://s1.BrsApi.ir/Api/Marke… | ETH.png | … |

</details>

<details>
<summary><code>brsapi_historical_daily</code> — ~8,465,821 ردیف، 23 ستون (نمایش 12 ستون از 23)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `HistoricalDailyModel`
- سرویس: `services/backtest_service.py` (7)، `services/auto_retrain_pipeline.py` (6)، `services/iran_fear_greed_index.py` (6)، `services/hidden_accumulation.py` (4)
- API: `apps/api/endpoints/backtests.py` (3)، `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/signal_insights.py` (2)، `apps/admin/dashboard.py` (1)
- اسکریپت: `scripts/check_partitions.py` (8)، `scripts/fix_historical_id.py` (8)، `scripts/fix_historical_id_v2.py` (7)، `scripts/merge_year_tables.py` (7)
- تست: `tests/test_instrument_relations.py` (4)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | date | time | trade_count | trade_volume | trade_value | price_min | price_max | price_yesterday | price_first | price_last | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 3678487 | بالبر3 | 1404-10-23 | 06:10:58 | 0 | 0 | 0.0 | 0.0 | 0.0 | 39290.0 | 0.0 | 39290.0 | … |
| 3678488 | بالبر3 | 1404-10-22 | 06:11:07 | 0 | 0 | 0.0 | 0.0 | 0.0 | 39290.0 | 0.0 | 39290.0 | … |

</details>

<details>
<summary><code>brsapi_historical_real_legal</code> — ~906,647 ردیف، 21 ستون (نمایش 12 ستون از 21)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `HistoricalRealLegalModel`
- سرویس: `services/screener_service.py` (3)، `services/hidden_accumulation.py` (1)، `services/smart_money_service.py` (1)
- API: `apps/admin/dashboard.py` (1)
- اسکریپت: `scripts/import_real_legal.py` (4)، `scripts/check_partitions.py` (3)، `scripts/analyze_patterns.py` (1)، `scripts/backfill_ins_id.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/services/query_service.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | date | buy_real_count | buy_legal_count | sell_real_count | sell_legal_count | buy_real_volume | buy_legal_volume | sell_real_volume | sell_legal_volume | buy_real_value | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 3180 | آ س پ | 1391-01-14 | 49 | 0 | 19 | 0 | 299199 | 0 | 299199 | 0 | 1256482549.0 | … |
| 3181 | آ س پ | 1391-01-09 | 37 | 1 | 14 | 0 | 134609 | 9344 | 143953 | 0 | 572495024.0 | … |

</details>

<details>
<summary><code>brsapi_ime_certificates</code> — ~3,819 ردیف، 48 ستون (نمایش 12 ستون از 48)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeCertificateModel`
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (2)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | commodity | contract_code | contract_description | contract_size | contract_size_unit | contract_currency | price_yesterday | price_first | price_first_change | price_first_change_pct | price_max | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 2302 | شمش روی | ZincIngot | گواهی سپرده پیوسته شمش روی | 1 | ضریب تبدیل نماد به گروه انبار | ریال | 5224059.0 | 5202150.0 | -21909.0 | -0.42 | 5299880.0 | … |
| 2303 | شمش سرب | LeadIngot | گواهی سپرده پیوسته شمش سرب | 1 | ضریب تبدیل نماد به گروه انبار | ریال | 3743013.0 | 3661100.0 | -81913.0 | -2.19 | 3749990.0 | … |

</details>

<details>
<summary><code>brsapi_ime_funds</code> — ~21,019 ردیف، 67 ستون (نمایش 12 ستون از 67)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeFundModel`
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/audit_data_access.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | ins_id | symbol | name | isin | shares_count | base_volume | market_value | price_min | price_max | price_yesterday | price_first | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 643 | 33144542989832366 | زرفام | صندوق س.کالای آشنا | IRTKZFAM0001 | 1000000000 | 1 | 135602000000000.0 | 134610.0 | 136000.0 | 131532.0 | 134610.0 | … |
| 644 | 17244733069907210 | رزگلد | صندوق س.پشتوانه طلا آرمان آتی | IRTKROZG0001 | 2000000000 | 1 | 33860000000000.0 | 16800.0 | 16994.0 | 16442.0 | 16800.0 | … |

</details>

<details>
<summary><code>brsapi_ime_futures</code> — ~38 ردیف، 59 ستون (نمایش 12 ستون از 59) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeFutureModel`
- سرویس: `services/quant_signal_orchestrator.py` (1)
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/start_scheduler.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | contract_code | contract_description | contract_size | contract_size_unit | contract_currency | date_end | date_end_text | days_remaining | margin_initial | margin_maintenance | open_interest | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | SILKH05 | قرارداد آتی گواهی سپرده نقره ت… | 10 | گرم | ریال | 0000-00-00 |  | 0 | 26900000.0 | 18830000.0 | 0 | … |
| 2 | GB19MO05 | قرارداد آتی شمش طلای خام 995 ت… | 1 | گرم | ریال | 0000-00-00 |  | 0 | 66000000.0 | 46200000.0 | 0 | … |

</details>

<details>
<summary><code>brsapi_ime_options</code> — ~48,213 ردیف، 101 ستون (نمایش 12 ستون از 101)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImeOptionModel`
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `brsapi/jobs/registry.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | contract_category | contract_category_sub | contract_category_commodity | strike_price | level_strike | call_contract_id | call_contract_code | call_contract_description | call_contract_size | call_contract_size_unit | call_contract_currency | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 606 | SH05   تاریخ سررسید: 1405/06/2… | KASH05 | KA | 250000.0 | 5 | 1002045 | KASH05C250 | قرارداد اختیار معامله خرید واح… | 10 | واحد | ریال | … |
| 607 | SH05   تاریخ سررسید: 1405/06/2… | KASH05 | KA | 270000.0 | 6 | 1002046 | KASH05C270 | قرارداد اختیار معامله خرید واح… | 10 | واحد | ریال | … |

</details>

<details>
<summary><code>brsapi_ime_physical_trades</code> — ~687 ردیف، 37 ستون (نمایش 12 ستون از 37) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `brsapi/models/ime.py` → `ImePhysicalTradeModel`
- اسکریپت: `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | name | category_id | offer_code | market_hall | producer | supplier | broker | contract_type | settlement_type | date_price_settlement | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1 | NCI-CR08AB-00 | مس مفتول | 1-3-14 | 1273803 | تالار صنعتی | ملی صنایع مس ایران | ملی صنایع مس ایران | سی ولکس | نقدی (مچینگ) | نقدی / اعتباری |  | … |
| 2 | ABRO-GRSUSUB-00 | گوگرد گرانوله | 3-27-68 | 1273412 | تالار فرآورده های نفتی | پالایش نفت آبادان | پالایش نفت آبادان | راهین | نقدی (مچینگ) | نقدی |  | … |

</details>

<details>
<summary><code>brsapi_index_values</code> — ~3,437 ردیف، 26 ستون (نمایش 12 ستون از 26)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `IndexValueModel`
- سرویس: `services/quant_signal_orchestrator.py` (3)، `services/signal_decision_engine.py` (1)
- اسکریپت: `scripts/sync_all_tables.py` (1)
- تست: `tests/unit/test_brsapi_sync_fixes.py` (2)، `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `brsapi/parsers/tsetmc.py` (1)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | name | state | index_value | index_change | index_change_pct | index_equal_weight | index_equal_weight_change | market_value | market_value_main | market_value_base | trade_count | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 49 |  | باز | 4903532.82 | -21150.81 | 0.0 | 1328109.58 | 4592.86 | 1.4271009234205443e+17 | 0.0 | 0.0 | 579506 | … |
| 50 |  | باز | 4902781.49 | -21902.14 | 0.0 | 1327997.95 | 4481.23 | 1.4270697432604384e+17 | 0.0 | 0.0 | 582650 | … |

</details>

<details>
<summary><code>brsapi_intraday_trades</code> — ~1,628,554 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `IntradayTradeModel`
- سرویس: `services/backtest_service.py` (3)
- اسکریپت: `scripts/import_transactions.py` (6)، `scripts/analyze_db_issues.py` (2)، `scripts/import_transaction_top43.py` (2)، `scripts/analyze_patterns.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | row | time | volume | price | canceled | trade_date | created_at | ins_id | instrument_id | updated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 4432 | عیار | 4371 | 12:03:57 | 2 | 508100.0 | False | 1405-05-14 | 2026-08-05 04:40:24.396704 | 34144395039913458 | NULL | NULL | … |
| 4433 | عیار | 4372 | 12:03:57 | 3 | 508100.0 | False | 1405-05-14 | 2026-08-05 04:40:24.396704 | 34144395039913458 | NULL | NULL | … |

</details>

<details>
<summary><code>brsapi_option_snapshots</code> — ~374,433 ردیف، 81 ستون (نمایش 12 ستون از 81)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `OptionSnapshotModel`
- API: `apps/api/endpoints/options.py` (3)، `apps/admin/dashboard.py` (1)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/audit_data_access.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | ins_id | symbol | name | isin | underlying_symbol | underlying_id | option_type | contract_size | strike_price | open_interest | date_begin | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 332 | 2605324180004362 | ضجوا6005 | اختیارخ جوانه.ک-16000-05/06/25 | IRO9JVAN2361 | جوانه کوچک | 67455383896188985 | call | 1000 | 16000.0 | 99 | 1405-03-17 | … |
| 333 | 37113721866142979 | ضملی5026 | اختیارخ فملی-12000-1405/05/14 | IRO9MSMI0B81 | فملی | 35425587644337450 | call | 1000 | 12000.0 | 5085 | 1405-03-11 | … |

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
<summary><code>brsapi_shareholder_records</code> — ~772,645 ردیف، 13 ستون (نمایش 12 ستون از 13)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `ShareholderRecordModel`
- سرویس: `services/history_backfill_service.py` (2)
- اسکریپت: `scripts/import_shareholders.py` (11)، `scripts/analyze_shareholders.py` (9)، `scripts/update_free_float.py` (4)، `scripts/analyze_db_issues.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | shareholder_name | volume | percent | change | date | created_at | ins_id | instrument_id | updated_at | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 935098 | فوكا | شخص حقيقي | 746840709 | 12.49 | 1 | 2019-02-27 | 2026-07-26 06:37:55.119816 | IRO7FVAP0003 | NULL | NULL | 2026-07-26 | … |
| 935106 | فوكا | شخص حقيقي | 746840709 | 12.49 | 1 | 2019-01-31 | 2026-07-26 06:37:55.119816 | IRO7FVAP0003 | NULL | NULL | 2026-07-26 | … |

</details>

<details>
<summary><code>brsapi_symbol_details</code> — ~1,280 ردیف، 65 ستون (نمایش 12 ستون از 65)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `SymbolDetailModel`
- سرویس: `services/populate_profiles_service.py` (3)، `services/watchlist_service.py` (3)، `services/fundamental_service.py` (1)
- API: `apps/admin/dashboard.py` (1)
- اسکریپت: `scripts/full_populate_profiles.py` (5)، `scripts/check_market_field.py` (4)، `scripts/fix_eps.py` (4)، `scripts/fix_null_market_field.py` (3)
- تست: `tests/test_instrument_relations.py` (1)، `tests/test_sync_2.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (2)

**نمونه داده:**

| id | ins_id | instrument_id | symbol | name | name_en | isin | code_12 | code_5 | code_4 | market | board | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 485 | 57273529732791251 | NULL | خموتور | موتورسازان‌تراکتورسازی‌ایران | Motorsazan | IRO1MSTI0001 | IRO1MSTI0003 | MSTI1 | MSTI | بورس | بازار اول (تابلوی فرعی) بورس | … |
| 583 | 31039212000825988 | NULL | آوند | صندوق س. آوند مفید-د | Avand ETF | IRT3AVNF0001 | IRT3AVNF0008 | AVNF1 | AVNF | فرابورس | بازار ابزارهای نوین مالی فرابو… | … |

</details>

<details>
<summary><code>brsapi_symbol_snapshots</code> — ~826,838 ردیف، 71 ستون (نمایش 12 ستون از 71)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `SymbolSnapshotModel`
- سرویس: `services/watchlist_service.py` (8)، `services/market_health_index.py` (5)، `services/iran_fear_greed_index.py` (4)، `services/populate_profiles_service.py` (4)
- API: `apps/api/endpoints/analysis.py` (3)، `apps/api/endpoints/ml.py` (2)، `apps/api/endpoints/news.py` (2)، `apps/api/endpoints/brsapi.py` (1)
- جاب: `jobs/definitions/sync_jobs.py` (3)، `jobs/definitions/alert_jobs.py` (1)
- اسکریپت: `scripts/full_populate_profiles.py` (7)، `scripts/merge_year_tables.py` (7)، `scripts/cleanup_duplicate_symbols.py` (5)، `scripts/fix_eps.py` (5)
- تست: `tests/unit/test_brsapi_sync_fixes.py` (2)، `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `brsapi/tests/test_tsetmc_symbols_integration.py` (2)، `diagnostics/ingestion_audit.py` (2)

**نمونه داده:**

| id | ins_id | symbol | name | isin | sector | sector_id | shares_count | base_volume | market_value | eps | pe_ratio | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 6108740 | 34721884030854211 | سفاسی | شرکت فارسیت اهواز | IRO7SFSP0001 | سایر محصولات کانی غیرفلزی | 54 | 660000000 | 1 | 2382600000000.0 | 339.0 | 10.6 | … |
| 6108741 | 39635413409683200 | کانسار3 | معدنکاران نسوز | IRO3MKNZ0003 | استخراج سایر معادن | 14 | 5600000000 | 1 | 76608000000000.0 | 1506.0 | 9.1 | … |

</details>

<details>
<summary><code>brsapi_sync_log</code> — ~25,997 ردیف، 13 ستون (نمایش 12 ستون از 13) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `brsapi/models/base.py` → `SyncLogModel`
- تست: `tests/unit/repositories/conftest.py` (3)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (2)

**نمونه داده:**

| id | endpoint | category | status | items_count | error_message | duration_ms | params_snapshot | started_at | completed_at | created_at | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 26996 | /Test/Endpoint.php | test | success | 10 | NULL | 100.0 | NULL | 2026-07-27 18:36:12.519643 | 2026-07-27 18:36:12.519643 | 2026-07-27 21:36:12.658160 | 2026-07-27 | … |
| 27002 | /Test/Old-cdf0d30e-f531-410b-b… | test | error | 0 | NULL | 10.0 | NULL | 2026-07-17 21:38:37.505177 | 2026-07-17 21:38:37.505177 | 2026-07-27 21:38:37.642687 | 2026-07-27 | … |

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
<summary><code>ml_predictions</code> — ~19,960 ردیف، 22 ستون (نمایش 12 ستون از 22)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/ml.py` → `MlPredictionModel`
- سرویس: `services/quant_signal_orchestrator.py` (5)، `services/diagnostics_runner.py` (1)

**نمونه داده:**

| id | batch_id | symbol | model_type | prediction | accuracy | confidence | f1_score | mse | samples | duration_seconds | predicted_change_pct | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| mlpred_ea725d2058984f899483270… | 71995e81a17f | خودرو | xgboost | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.06 | NULL | … |
| mlpred_de9ed58713cc4af1b3b528a… | 71995e81a17f | آبادا | xgboost | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.06 | NULL | … |

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
- API: `apps/api/endpoints/options.py` (13)، `apps/api/endpoints/brsapi.py` (2)، `apps/api/endpoints/screener_v2.py` (1)
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/brsapi_full_update.py` (5)، `scripts/run_full_backtest.py` (5)، `scripts/audit_data_access.py` (1)، `scripts/start_scheduler.py` (1)
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
<summary><code>brsapi_nav_records</code> — ~114 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `brsapi/models/tsetmc.py` → `NavRecordModel`
- API: `apps/admin/dashboard.py` (1)
- جاب: `jobs/definitions/sync_jobs.py` (1)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/backfill_ins_id.py` (1)، `scripts/sync_all_tables.py` (1)
- تست: `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (3)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | nav_issue | nav_redemption | date | time | fetched_at | raw_json | created_at | ins_id | instrument_id | updated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 35 | بانکیا | 10664.0 | 10566.0 | 1405-05-12 | 17:31:12 | 2026-08-04 05:53:01 | {"date": "1405-05-12", "time":… | 2026-08-04 09:23:00.210461 | 62478276461613732 | NULL | NULL | … |
| 36 | بذر | 297760.0 | 295124.0 | 1405-05-12 | 18:04:08 | 2026-08-04 05:54:38 | {"date": "1405-05-12", "time":… | 2026-08-04 09:24:38.503886 | 37222720235819361 | NULL | NULL | … |

</details>

<details>
<summary><code>candlesticks</code> — جدول خالی است (10 ستون) ⚠️ 4 مشکل</summary>

**مشکلات (4):**
- جدول خالی است
- نسخه قدیمی است — جدول زنده `brsapi_candlesticks` جایگزین آن است
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- نسخه قدیمی — backfill به `brsapi_candlesticks` می‌نویسد

**مراجع کد:**
- مدل: _بدون مدل ORM_
- سرویس: `services/history_backfill_service.py` (1)
- اسکریپت: `scripts/analyze_db_issues.py` (1)
- تست: `tests/test_instrument_relations.py` (1)

</details>

<details>
<summary><code>daily_history</code> — ~>0 ردیف، 17 ستون (نمایش 12 ستون از 17) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید

**مراجع کد:**
- مدل: `models/market_data.py` → `DailyHistoryModel`
- سرویس: `services/diagnostics_runner.py` (3)، `services/populate_profiles_service.py` (2)، `services/screener110_service.py` (2)، `services/screener_service.py` (2)
- API: `apps/api/endpoints/screener110.py` (1)
- اسکریپت: `scripts/full_populate_profiles.py` (4)، `scripts/brsapi_full_update.py` (2)، `scripts/analyze_db_issues.py` (1)، `scripts/populate_profiles.py` (1)

**نمونه داده:**

| symbol_id | trade_date | trade_count | trade_volume | trade_value | price_min | price_max | price_yesterday | price_first | price_last | price_last_change | price_last_change_pct | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 48934567890123456 | 2023-04-16 | 0 | 0 | 0.0 | 0.0 | 0.0 | 7370.0 | 0.0 | 7380.0 | 0.0 | 0.0 | … |
| 2234567890123456 | 2023-03-25 | 2137 | 3222331 | 37290951110.0 | 11360.0 | 11800.0 | 11370.0 | 11600.0 | 11520.0 | 150.0 | 1.32 | … |

</details>

<details>
<summary><code>daily_real_legal</code> — ~>0 ردیف، 16 ستون (نمایش 12 ستون از 16) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید

**مراجع کد:**
- مدل: `models/market_data.py` → `DailyRealLegalModel`
- سرویس: `services/populate_profiles_service.py` (2)، `services/screener110_service.py` (2)، `services/screener_service.py` (2)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/full_populate_profiles.py` (1)، `scripts/populate_profiles.py` (1)
- سایر: `ml/features/trade_features.py` (2)

**نمونه داده:**

| symbol_id | trade_date | real_buy_count | real_sell_count | legal_buy_count | legal_sell_count | real_buy_volume | real_sell_volume | legal_buy_volume | legal_sell_volume | real_buy_value | real_sell_value | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1234567890123456 | 2026-07-13 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | … |
| 1234567890123456 | 2026-07-12 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | … |

</details>

<details>
<summary><code>etf_nav</code> — ~>0 ردیف، 7 ستون ⚠️ 4 مشکل</summary>

**مشکلات (4):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟
- ۱۲ ردیف یتیم بدون مصرف‌کننده — نسخه‌های زنده `brsapi_nav_records` و `funds` جایگزین‌اند

**مراجع کد:**
- مدل: `models/market_data.py` → `EtfNavModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| symbol_id | time | nav | price | discount_premium | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|
| 57534567890123457 | 2026-07-07 12:28:05+00:00 | 28362.5 | NULL | NULL | NULL | NULL |
| 57534567890123458 | 2026-07-07 11:33:48+00:00 | 50452.0 | NULL | NULL | NULL | NULL |

</details>

<details>
<summary><code>funds</code> — ~26 ردیف، 31 ستون (نمایش 12 ستون از 31)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `iran_market_data/app/storage/models.py` → `FundInfo`
- مدل: `models/fund.py` → `FundModel`
- سرویس: `services/fund_service.py` (13)، `services/symbol_catalog.py` (4)، `services/unified_assistant_service.py` (2)، `services/chat/chat_engine.py` (1)
- API: `apps/api/endpoints/funds.py` (19)، `apps/api/endpoints/market_info.py` (7)، `apps/api/router.py` (5)، `apps/api/endpoints/brsapi.py` (3)
- جاب: `jobs/definitions/brsapi_jobs.py` (1)
- ریپازیتوری: `repositories/fund_repository.py` (5)
- اسکریپت: `scripts/fix_schema_gap.py` (5)، `scripts/analyze_db_issues.py` (1)، `scripts/audit_data_access.py` (1)، `scripts/seed_funds.py` (1)
- تست: `tests/unit/test_funds_api.py` (51)، `tests/unit/services/test_fund_service.py` (4)، `tests/unit/test_backend_api.py` (3)، `tests/test_all_pages.py` (2)
- سایر: `iran_market_data/app/collectors/fipiran.py` (6)، `brsapi/services/sync_service.py` (5)، `domain/funds/__init__.py` (3)، `providers/funds/provider.py` (3)

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
- اسکریپت: `scripts/backtest_all_symbols.py` (3)، `scripts/audit_data_access.py` (2)، `scripts/rebuild_indicators.py` (2)، `scripts/run_full_backtest.py` (2)
- تست: `tests/unit/services/test_audit_modules.py` (7)، `tests/test_compose.py` (5)، `tests/unit/pipelines/test_indicator_pipeline.py` (5)، `tests/fixtures/sample_macro.py` (3)
- سایر: `backtesting/composer/indicator_registry.py` (26)، `domain/indicators/registry/__init__.py` (11)، `backtesting/strategies/incremental_indicators.py` (6)، `domain/indicators/__init__.py` (6)

</details>

<details>
<summary><code>intraday_trades</code> — ~>0 ردیف، 9 ستون ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید
- نسخه قدیمی است — جدول زنده `brsapi_intraday_trades` جایگزین آن است

**مراجع کد:**
- مدل: `models/market_data.py` → `IntradayTradeModel`
- سرویس: `services/block_trade_detector.py` (2)، `services/backtest_service.py` (1)، `services/manipulation_detector.py` (1)، `services/market_health_index.py` (1)
- اسکریپت: `scripts/run_ml_dual.py` (5)، `scripts/analyze_db_issues.py` (1)، `scripts/create_symbol_kpi_view.py` (1)
- سایر: `ingestion/library_sources/finpy_adapter.py` (3)، `ingestion/sources/library_sources.py` (2)، `ingestion/parser/library_parsers.py` (1)

**نمونه داده:**

| symbol_id | trade_date | seq_no | time | volume | price | is_canceled | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|
| 7234567890123456 | 2026-06-09 | 23887 | 10:33:36 | 35 | 146630.0 | False | 2026-06-09 | 1405-03-19 |
| 7234567890123456 | 2026-06-09 | 23888 | 10:34:10 | 70 | 146630.0 | False | 2026-06-09 | 1405-03-19 |

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
- اسکریپت: `scripts/analyze_db_issues.py` (1)
- تست: `tests/comprehensive/test_all.py` (2)
- سایر: `core/constants/paths.py` (1)

</details>

<details>
<summary><code>quotes</code> — ~3,374,031 ردیف، 29 ستون (نمایش 12 ستون از 29)</summary>

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
| brsapi_رتاپ3_2026-07-29 | 7093655625757378 | رتاپ3 | 8320.0 | 8320.0 | 8320.0 | 8320.0 | 8320.0 | 170.0 | 2.09 | 7100000 | 59072000000.0 | … |
| brsapi_همای_2026-08-03 | 15494954332657697 | همای | 10120.0 | 10117.0 | 10128.0 | 10116.0 | 10127.0 | 22.0 | 0.22 | 69187406 | 700177153901.0 | … |

</details>

<details>
<summary><code>shareholders</code> — ~>0 ردیف، 8 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید

**مراجع کد:**
- مدل: `models/market_data.py` → `ShareholderModel`
- سرویس: `services/symbol_detail_service.py` (15)، `services/sync_master_service.py` (1)
- اسکریپت: `scripts/import_shareholders.py` (3)، `scripts/analyze_db_issues.py` (1)، `scripts/analyze_shareholders.py` (1)، `scripts/update_free_float.py` (1)
- سایر: `ingestion/sources/library_sources.py` (3)، `brsapi/migrations/001_create_brsapi_tables.py` (1)، `brsapi/services/query_service.py` (1)، `ingestion/library_sources/pytse_client_adapter.py` (1)

**نمونه داده:**

| symbol_id | record_date | holder_name | volume | percent | change | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 28534567890123456 | 2026-07-08 | شخص حقیقی | 49530000 | 2.008 | 0.0 | 2026-07-08 | 1405-04-17 |
| 35134567890123456 | 2026-07-08 | شخص حقیقی | 45883823 | 1.941 | 0.0 | 2026-07-08 | 1405-04-17 |

</details>

<details>
<summary><code>symbol_snapshots</code> — جدول خالی است (28 ستون) ⚠️ 4 مشکل</summary>

**مشکلات (4):**
- جدول خالی است
- نسخه قدیمی است — جدول زنده `brsapi_symbol_snapshots` جایگزین آن است
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- نسخه قدیمی — `brsapi_symbol_snapshots` (۸۰۳K ردیف) زنده است

**مراجع کد:**
- مدل: _بدون مدل ORM_
- سرویس: `services/populate_profiles_service.py` (1)، `services/sync_master_service.py` (1)
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/dump_complete.py` (1)، `scripts/fix_null_market_field.py` (1)، `scripts/populate_profiles.py` (1)
- سایر: `brsapi/parsers/tsetmc.py` (1)، `brsapi/services/query_service.py` (1)

</details>

<details>
<summary><code>trades</code> — ~14,851,701 ردیف، 14 ستون (نمایش 12 ستون از 14) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/trade.py` → `TradeModel`
- سرویس: `services/block_trade_detector.py` (19)، `services/ensemble_engine.py` (10)، `services/trade_service.py` (10)، `services/mass_scanner_service.py` (9)
- API: `apps/api/endpoints/tabdeal.py` (14)، `apps/api/endpoints/alpha.py` (9)، `apps/api/endpoints/backtests.py` (5)، `apps/api/router.py` (4)
- جاب: `jobs/definitions/brsapi_jobs.py` (1)، `jobs/definitions/housekeeping_jobs.py` (1)
- ریپازیتوری: `repositories/backtest_repository.py` (1)
- اسکریپت: `scripts/backtest_all_symbols.py` (12)، `scripts/test_alpha_direct.py` (9)، `scripts/run_full_backtest.py` (6)، `scripts/test_single_symbol.py` (6)
- تست: `tests/unit/test_trades_e2e.py` (17)، `tests/unit/services/test_trade_service.py` (10)، `tests/comprehensive/test_all.py` (7)، `tests/unit/backtesting/test_excel_report.py` (3)
- سایر: `backtesting/microstructure/calibration.py` (20)، `backtesting/optimization/walk_forward.py` (20)، `backtesting/calibration/nightly_calibration.py` (16)، `backtesting/abm/matching_engine.py` (10)

**نمونه داده:**

| id | instrument_id | symbol | price | volume | value | side | time | date | data_source | created_at | updated_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 7209d04dd7c46de2423972c74d6bae… | رپويا | رپويا | 46750.0 | 3823 | 178725250.0 | NULL | 09:51:52 | 1405-03-24 | tsetmc | 2026-07-12 09:53:16.158994 | NULL | … |
| a71197126ab365324da813fdea8fb6… | رپويا | رپويا | 46750.0 | 10000 | 467500000.0 | NULL | 09:51:52 | 1405-03-24 | tsetmc | 2026-07-12 09:53:16.158994 | NULL | … |

</details>

<details>
<summary><code>backtest_runs</code> — ~1,579 ردیف، 22 ستون (نمایش 12 ستون از 22)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/backtest.py` → `BacktestRunModel`
- سرویس: `services/diagnostics_runner.py` (2)
- API: `apps/api/endpoints/tables.py` (1)
- اسکریپت: `scripts/debug_db_check.py` (3)، `scripts/debug_db_check2.py` (3)، `scripts/backtest_all_symbols.py` (2)
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
- اسکریپت: `scripts/_create_generated_strategies.py` (11)، `scripts/backtest_all_symbols.py` (6)، `scripts/_check_tables.py` (3)، `scripts/run_full_backtest.py` (2)

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
<summary><code>queue_analysis_results</code> — جدول خالی است (30 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/queue_analysis.py` → `QueueAnalysisResult`
- سرویس: `services/queue_analysis_service.py` (2)
- API: `apps/api/endpoints/queue_analysis.py` (1)
- اسکریپت: `scripts/fix_schema_gap.py` (1)

</details>

<details>
<summary><code>screener_profiles</code> — ~1,562 ردیف، 61 ستون (نمایش 12 ستون از 61)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/screener.py` → `ScreenerProfile`
- سرویس: `services/populate_profiles_service.py` (3)، `services/screener110_service.py` (2)، `services/sync_master_service.py` (1)
- API: `apps/api/endpoints/screener110.py` (5)
- اسکریپت: `scripts/full_populate_profiles.py` (13)، `scripts/fix_eps.py` (8)، `scripts/update_free_float.py` (6)، `scripts/import_codal_to_profiles.py` (3)

**نمونه داده:**

| symbol | industry | sub_industry | free_float_shares | eps_current | eps_prev_year | exchange_rate_base | inflation_rate | net_operating_profit | accumulated_loss | registered_capital | legal_reserve | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| شتوکا | محصولات شیمیایی |  | 0 | 1545.0 | 1313.25 | 28500.0 | 35.0 | NULL | 0.0 | 1712.5 | NULL | … |
| غگز | محصولات غذایی و آشامیدنی به جز… |  | 1795230871 | 81.0 | 68.85 | 28500.0 | 35.0 | NULL | 0.0 | 2637.718 | NULL | … |

</details>

<details>
<summary><code>screener_signals</code> — جدول خالی است (37 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/screener.py` → `ScreenerSignal`
- سرویس: `services/screener110_service.py` (1)
- API: `apps/api/endpoints/screener110.py` (3)
- جاب: `jobs/definitions/screener_jobs.py` (1)

</details>

<details>
<summary><code>screener_snapshots</code> — جدول خالی است (20 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/screener.py` → `ScreenerSnapshot`
- سرویس: `services/screener110_service.py` (3)
- جاب: `jobs/definitions/screener_jobs.py` (1)

</details>

<details>
<summary><code>signal_accuracy</code> — ~20,550 ردیف، 28 ستون (نمایش 12 ستون از 28)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/signal_accuracy.py` → `SignalAccuracyModel`
- سرویس: `services/quant_signal_orchestrator.py` (10)، `services/signal_performance_tracker.py` (7)، `services/diagnostics_runner.py` (3)، `services/probability_calibrator.py` (3)
- تست: `tests/e2e/test_orchestrator_pipeline.py` (4)
- سایر: `core/calibration_bootstrap.py` (2)

**نمونه داده:**

| id | signal_id | symbol | market | source | direction | timeframe | actual_return_pct | direction_correct | max_profit_pct | max_loss_pct | hit_target1 | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| sacc_ffae185413c94a3ea9c718f1 | sig_12fda042e6ca4efe900eb515 | BRENT | commodity | commodity_analysis | buy | daily | -0.22693747872459846 | False | 0.0 | 0.0 | False | … |
| sacc_18c0f562033c4f3eac07c854 | sig_82aacdf833e64beab8b546f4 | BRENT | commodity | commodity_analysis | buy | daily | -0.22693747872459846 | False | 0.0 | 0.0 | False | … |

</details>

<details>
<summary><code>signals</code> — ~>0 ردیف، 17 ستون (نمایش 12 ستون از 17) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید

**مراجع کد:**
- مدل: `models/signal.py` → `SignalModel`
- سرویس: `services/quant_signal_orchestrator.py` (63)، `services/multi_market_signal_engine.py` (41)، `services/ensemble_engine.py` (12)، `services/multi_timeframe_confirmer.py` (7)
- API: `apps/api/app.py` (20)، `apps/api/endpoints/signal_insights.py` (9)، `apps/api/endpoints/multi_market_signals.py` (7)، `apps/api/router.py` (5)
- جاب: `jobs/definitions/screener_jobs.py` (2)، `jobs/signal_generation.py` (1)
- ریپازیتوری: `repositories/signal_repository.py` (8)
- اسکریپت: `scripts/run_full_backtest.py` (15)، `scripts/debug_signal_gates.py` (4)، `scripts/dump_signal_code.py` (4)، `scripts/audit_data_access.py` (2)
- تست: `tests/unit/services/test_quant_signal_orchestrator.py` (83)، `tests/benchmark_signal_quality.py` (51)، `tests/unit/test_rate_limit_middleware.py` (50)، `tests/e2e/test_orchestrator_pipeline.py` (22)
- سایر: `backtesting/research/alpha_evaluation_engine.py` (36)، `backtesting/signals/signal_conflict_resolver.py` (12)، `backtesting/alpha/fast_evaluator.py` (8)، `backtesting/signals/signal_router.py` (7)

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
<summary><code>decision_architectures</code> — ~>0 ردیف، 9 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید

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
<summary><code>alert_history</code> — ~217 ردیف، 8 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/alert.py` → `AlertHistoryModel`
- API: `apps/api/endpoints/tables.py` (1)
- جاب: `jobs/definitions/alert_jobs.py` (1)

**نمونه داده:**

| id | alert_id | triggered_at | trigger_value | message | delivered | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| alh_5e4bd15fa07744fd8945aad7 | alr_035b5d82ba7143759a9a776c | 2026-08-03 12:03:05.128201 | 28192.0 | کاج price reached 28192.0 (thr… | True | NULL | NULL |
| alh_ddcefd4b5dd247b68d2e7c62 | alr_035b5d82ba7143759a9a776c | 2026-08-03 12:05:05.137585 | 28192.0 | کاج price reached 28192.0 (thr… | True | NULL | NULL |

</details>

<details>
<summary><code>alerts</code> — ~1 ردیف، 14 ستون (نمایش 12 ستون از 14)</summary>

_مشکلی شناسایی نشد._

**مراجع کد:**
- مدل: `models/alert.py` → `AlertModel`
- سرویس: `services/stock_assistant_service.py` (16)، `services/unified_assistant_service.py` (12)، `services/monitoring_service.py` (10)، `services/alert_service.py` (8)
- API: `apps/api/app.py` (5)، `apps/api/router.py` (4)، `apps/api/endpoints/assistant.py` (2)، `apps/scheduler/app.py` (2)
- جاب: `jobs/definitions/alert_jobs.py` (9)، `jobs/definitions/sync_jobs.py` (1)
- ریپازیتوری: `repositories/alert_repository.py` (1)
- اسکریپت: `scripts/audit_data_access.py` (2)، `scripts/import_shareholders.py` (1)
- تست: `tests/unit/test_rate_limit_middleware.py` (7)، `tests/unit/services/test_alert_service.py` (7)، `tests/unit/test_security_middleware.py` (6)، `tests/unit/test_cron_alerts_real.py` (5)
- سایر: `domain/alerts/__init__.py` (3)، `core/config/__init__.py` (1)، `domain/alerts/rules.py` (1)، `monitoring/__init__.py` (1)

**نمونه داده:**

| id | instrument_id | symbol | alert_type | condition | channels | enabled | triggered_count | last_triggered | description | updated_at | created_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| alr_035b5d82ba7143759a9a776c | کاج | کاج | price_above | {"threshold": 1000, "operator"… | ["email", "console"] | True | 274 | 2026-08-04 06:23:13.054612 |  | NULL | 2026-07-28 13:32:22.564870 | … |

</details>

<details>
<summary><code>commodity_certificates</code> — ~125,256 ردیف، 8 ستون ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityCertificateModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| id | symbol | name | price | volume | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 4598 | PAM-LLD0209AAPP-00 | پلی اتیلن سبک خطی 0209AA | 39215.0 | 5038 | 2026-07-13 02:46:52.449560+00:… | NULL | NULL |
| 4599 | PAM-LLD0209AAPP-00 | پلی اتیلن سبک خطی 0209AA | 39215.0 | 4730 | 2026-07-13 02:46:52.449560+00:… | NULL | NULL |

</details>

<details>
<summary><code>commodity_funds</code> — ~124 ردیف، 8 ستون ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityFundModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| id | symbol | name | nav | price | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 1 | عیار | صندوق طلای عیار مفید | NULL | 501990.0 | 2026-07-14 14:58:08.847483+00:… | NULL | NULL |
| 2 | نقران | صندوق س.کالای کهربا1 | NULL | 10555.0 | 2026-07-14 14:58:08.851409+00:… | NULL | NULL |

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
<summary><code>commodity_prices</code> — ~>0 ردیف، 9 ستون ⚠️ 4 مشکل</summary>

**مشکلات (4):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید
- نسخه قدیمی است — جدول زنده `brsapi_commodity_prices` جایگزین آن است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityGlobalPriceModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)
- سایر: `brsapi/services/query_service.py` (1)

**نمونه داده:**

| symbol | time | name | price | change_value | change_pct | unit | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|
| XAUUSD | 2026-07-14 14:58:08.449514+00:… | انس طلا | 4083.67 | 84.27 | NULL | دلار | NULL | NULL |
| XAGUSD | 2026-07-14 14:58:08.487040+00:… | انس نقره | 59.32 | 1.74 | NULL | دلار | NULL | NULL |

</details>

<details>
<summary><code>commodity_trades</code> — ~320,005 ردیف، 12 ستون ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/market_data.py` → `CommodityTradeModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)

**نمونه داده:**

| id | symbol | name | trade_date | price | volume | value | counter_party | created_at | updated_at | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 87200 | TIOC-PDATARB-00 | PDA TAR | NULL | 72156.0 | 1794 | 129448514.0 | نفت ایرانول\|صبا تأمین | 2026-07-13 02:45:42.100240+00:… | NULL | 2026-07-13 | 1405-04-22 |
| 88027 | CACO-ZII1-00 | شمش روی 99.98 | NULL | 671176.0 | 40 | 26847040.0 | کالسیمین\|سی ولکس | 2026-07-13 02:45:42.100240+00:… | NULL | 2026-07-13 | 1405-04-22 |

</details>

<details>
<summary><code>dual_date_columns</code> — ~102 ردیف، 4 ستون ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: _بدون مدل ORM_
- اسکریپت: `scripts/install_dual_dates.py` (3)، `scripts/backfill_dual_dates.py` (2)، `scripts/analyze_db_issues.py` (1)، `scripts/test_dual_dates.py` (1)
- تست: `tests/unit/test_dual_dates.py` (2)

**نمونه داده:**

| table_name | source_column | gregorian_date | shamsi_date |
|---|---|---|---|
| alerts | created_at | NULL | NULL |
| analysis_reports | report_date | NULL | NULL |

</details>

<details>
<summary><code>gold_currency_prices</code> — ~>0 ردیف، 12 ستون ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/market_data.py` → `GoldCurrencyPriceModel`
- اسکریپت: `scripts/analyze_db_issues.py` (1)، `scripts/populate_profiles.py` (1)

**نمونه داده:**

| symbol | time | name | name_en | sign | price | change_value | change_pct | unit | section | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AED | 2018-04-16 19:30:00+00:00 | AED | NULL | NULL | 14770.0 | -330.0 | -2.185430463576159 | unit | currency | NULL | NULL |
| AMD | 2018-04-16 19:30:00+00:00 | AMD | NULL | NULL | 140.0 | -950.0 | -87.1559633027523 | unit | currency | NULL | NULL |

</details>

<details>
<summary><code>indices</code> — ~>0 ردیف، 8 ستون ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/market_data.py` → `IndexModel`
- سرویس: `services/market_service.py` (8)
- API: `apps/api/endpoints/market_watch.py` (5)، `apps/api/endpoints/market.py` (3)، `apps/api/endpoints/market_dashboard.py` (3)، `apps/api/router.py` (1)
- جاب: `jobs/definitions/sync_jobs.py` (2)، `jobs/definitions/brsapi_jobs.py` (1)
- اسکریپت: `scripts/audit_data_access.py` (1)
- سایر: `domain/indices/__init__.py` (3)، `ml/datasets/sampling.py` (3)، `ml/evaluation/stability.py` (3)، `ml/models/ensemble/blending.py` (3)

**نمونه داده:**

| id | name | value | change_value | change_pct | time | gregorian_date | shamsi_date |
|---|---|---|---|---|---|---|---|
| 1 | شاخص کل | 4924683.63 | -42077.13 | NULL | 2026-07-14 14:41:36.860251+00:… | NULL | NULL |
| 2 | شاخص کل | 4924683.63 | -42077.13 | NULL | 2026-07-14 14:58:05.546302+00:… | NULL | NULL |

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
<summary><code>symbol_relations</code> — جدول خالی است (13 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/symbol_relation.py` → `SymbolRelationModel`
- سرویس: `services/mass_scanner_service.py` (1)
- سایر: `backtesting/relations/symbol_graph.py` (1)

</details>

<details>
<summary><code>markets</code> — جدول خالی است (14 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- هیچ SQL فعالی ندارد — مراجع کد صرفاً از نام ماژول/پکیج هستند

**مراجع کد:**
- مدل: `models/market.py` → `MarketModel`
- سرویس: `services/quant_signal_orchestrator.py` (9)، `services/multi_market_signal_engine.py` (6)، `services/unified_assistant_service.py` (5)، `services/auto_retrain_pipeline.py` (3)
- API: `apps/api/endpoints/tabdeal.py` (6)، `apps/api/endpoints/multi_market_signals.py` (5)، `apps/api/endpoints/signal_insights.py` (2)، `apps/api/app.py` (1)
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
- اسکریپت: `scripts/audit_data_access.py` (2)
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
- API: `apps/api/endpoints/backtests.py` (60)، `apps/api/endpoints/brsapi.py` (39)، `apps/api/endpoints/ml.py` (29)، `apps/api/endpoints/analysis.py` (14)
- جاب: `jobs/market_data_jobs.py` (15)، `jobs/definitions/market_data_jobs.py` (11)، `jobs/definitions/sync_jobs.py` (6)، `jobs/definitions/alert_jobs.py` (4)
- ریپازیتوری: `repositories/news_repository.py` (13)، `repositories/backtest_repository.py` (8)، `repositories/generated_strategy_repository.py` (2)
- اسکریپت: `scripts/brsapi_full_update.py` (29)، `scripts/sync_all_tables.py` (27)، `scripts/sync_symbol_details_all.py` (27)، `scripts/import_analysis_data.py` (26)
- تست: `tests/comprehensive/test_all.py` (29)، `tests/unit/services/test_symbol_catalog.py` (20)، `tests/unit/test_queue_analysis_api.py` (18)، `tests/test_brsapi_job_registry.py` (15)
- سایر: `brsapi/services/sync_service.py` (31)، `brsapi/services/history_fetch_service.py` (22)، `brsapi/jobs/registry.py` (21)، `ingestion/library_sources/universal_collector.py` (14)

**نمونه داده:**

| id | symbol | name | isin | market_type | asset_class | industry | industry_id | total_shares | base_volume | eps | pe | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 1234567890123456 | خودرو | اوراق مشاركت ايران خودرو | IRB5IKCO8751 | stock | equity | خودرو و ساخت قطعات | NULL | 0 | 1 | NULL | NULL | … |
| 2234567890123456 | آبادا | توليد نيروي برق آبادان | IRO1NBAB0001 | stock | equity | عرضه برق، گاز، بخاروآب گرم | NULL | 0 | 1 | NULL | NULL | … |

</details>

<details>
<summary><code>users</code> — جدول خالی است (21 ستون) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- جدول خالی است

**مراجع کد:**
- مدل: `models/user.py` → `UserModel`
- سرویس: `services/user_service.py` (3)، `services/chat/suggestion_engine.py` (2)، `services/codal_analysis/audit_fraud.py` (1)، `services/smart_money/confidence.py` (1)
- API: `apps/api/endpoints/auth.py` (3)، `apps/admin/dashboard.py` (2)، `apps/api/endpoints/symbols.py` (2)، `apps/api/endpoints/decision_engine.py` (1)
- تست: `tests/unit/test_rbac.py` (5)، `tests/unit/test_mfa_integration.py` (3)
- سایر: `postgresql_client.py` (3)، `core/security/permissions.py` (2)، `brsapi/jobs/registry.py` (1)، `core/calibration_bootstrap.py` (1)

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
- اسکریپت: `scripts/fix_schema_gap.py` (6)، `scripts/backfill_ins_id.py` (1)، `scripts/batch_codal_sync.py` (1)، `scripts/check_codal_tables.py` (1)
- تست: `tests/test_codal_sync_3x.py` (1)، `tests/test_instrument_relations.py` (1)
- سایر: `brsapi/migrations/001_create_brsapi_tables.py` (4)، `diagnostics/ingestion_audit.py` (1)

**نمونه داده:**

| id | symbol | company_name | title | code | date_title | date_send | time_send | date_publish | time_publish | link | link_pdf | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 67 | طیور | طیور دانه سلامت دزفول | امیدنامه پذیرش در فرابورس ایرا… |  | NULL | ۱۴۰۵/۰۵/۰۵ | ۱۵:۵۹:۲۵ | ۱۴۰۵/۰۵/۰۵ | ۱۵:۵۹:۲۵ | https://codal.ir/Reports/Attac… | NULL | … |
| 7302 | وبملت | بانک ملت | گزارش فعالیت هیئت مدیره دوره ۱… | ن-۱۱ | ۱۴۰۴/۱۲/۲۹ | ۱۴۰۵/۰۴/۳۱ | ۰۴:۰۴:۴۳ | ۱۴۰۵/۰۴/۳۱ | ۰۴:۰۴:۴۳ | https://codal.ir/Reports/Attac… | NULL | … |

</details>

<details>
<summary><code>brsapi_codal_attachments</code> — ~359 ردیف، 18 ستون (نمایش 12 ستون از 18)</summary>

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
<summary><code>codal_announcements</code> — جدول خالی است (17 ستون) ⚠️ 3 مشکل</summary>

**مشکلات (3):**
- جدول خالی است
- نسخه قدیمی است — جدول زنده `brsapi_codal_announcements` جایگزین آن است
- باگ فعال: `services/codal_download_service.py` از این جدول (خالی) می‌خواند → دانلود ضمائم هرگز انجام نمی‌شود

**مراجع کد:**
- مدل: `iran_market_data/app/storage/models.py` → `CodalAnnouncement`
- سرویس: `services/codal_download_service.py` (2)
- سایر: `database_handler.py` (2)، `data_repo.py` (2)، `postgresql_client.py` (2)، `datenrepo.py` (1)

</details>

<details>
<summary><code>codal_audit_summary</code> — ~451 ردیف، 33 ستون (نمایش 12 ستون از 33) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/codal.py` → `CodalAuditSummaryModel`
- API: `apps/api/endpoints/codal_audit.py` (7)، `apps/api/endpoints/brsapi.py` (2)
- اسکریپت: `scripts/batch_audit_all_symbols.py` (9)، `scripts/codal_deep.py` (4)، `scripts/extract_codal_financials.py` (4)، `scripts/codal_audit.py` (3)

**نمونه داده:**

| id | symbol | company_name | report_type | report_date | revenue | net_profit | total_assets | total_equity | eps | roe | roa | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 11 | وبملت | NULL | ن-۱۰ | ۱۴۰۵ | 2906669266.0 | NULL | NULL | 3132036.0 | NULL | 0.0 | 0.2353 | … |
| 13 | وبانک | NULL | ن-۱۰ | ۱۴۰۵ | 14030930.0 | NULL | NULL | 749998.0 | NULL | 0.0799 | 11982.0 | … |

</details>

<details>
<summary><code>codal_financial_statements</code> — ~451 ردیف، 16 ستون (نمایش 12 ستون از 16) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟

**مراجع کد:**
- مدل: `models/codal_financial.py` → `CodalFinancialStatementModel`
- سرویس: `services/codal_download_service.py` (2)
- API: `apps/api/endpoints/brsapi.py` (1)
- اسکریپت: `scripts/import_codal_excel.py` (8)، `scripts/codal_deep.py` (4)، `scripts/batch_audit_all_symbols.py` (3)، `scripts/codal_audit.py` (3)

**نمونه داده:**

| id | symbol | report_type | report_date | filename | file_path | title | parsed_data | table_count | row_count | import_batch | imported_at | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| cfs_2e86682e45c54ac8 | خودرو | ن-۱۰ | ۱۴۰۵ | NULL | NULL | Batch audit - خودرو | {'dupont': {'roe': 0.0, 'roe_d… | 6 | 0 | batch_1784534071 | 2026-07-20 11:24:29.903036 | … |
| cfs_021ba961c71525cb | وغدیر | ن-۱۰ | ۱۴۰۵ | NULL | NULL | Batch audit - وغدیر | {'dupont': {'roe': 1.7503, 'ro… | 11 | 0 | batch_1784534134 | 2026-07-20 11:25:33.221269 | … |

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
| f7e84d474c297d4ef1439957a83a4d… | خکار | خکار | ایرکا پارت صنعت | NULL | ن-۶۷ | NULL | NULL | NULL | ۱۴۰۵/۰۳/۱۷ | https://codal.ir/Reports/Attac… | آگهی ثبت افزایش سرمایه | … |
| 868d690fe03a8c36d1ef05a8c779be… | خکار | خکار | ایرکا پارت صنعت | NULL | ن-۶۷ | NULL | NULL | NULL | ۱۴۰۳/۱۰/۱۱ | https://codal.ir/Reports/Attac… | آگهی ثبت افزایش سرمایه | … |

</details>

<details>
<summary><code>corporate_actions</code> — جدول خالی است (11 ستون) ⚠️ 2 مشکل</summary>

**مشکلات (2):**
- جدول خالی است
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `models/option.py` → `CorporateActionModel`
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
| 75869 | وصندوق | n31 | 1397-05-07 | وصندوق_ن-۳۱_۱۳۹۷_۰۵_۰۷.xlsx | C:\Users\Iran\Desktop\temce\da… | 97280 | fast:C:\Users\Iran\Desktop\tem… | xls_biff | saved | NULL | 2026-07-20 03:30:37.925852 | … |
| 45400 | شراز | n10 | 1403-07-30 | شراز_ن-۱۰_۱۴۰۳_۰۷_۳۰.xlsx | C:\Users\Iran\Desktop\temce\da… | 496611 | fast:C:\Users\Iran\Desktop\tem… | html | saved | NULL | 2026-07-20 03:22:45.639838 | … |

</details>

<details>
<summary><code>import_document_tables</code> — ~522,636 ردیف، 13 ستون (نمایش 12 ستون از 13) ⚠️ 1 مشکل</summary>

**مشکلات (1):**
- مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست

**مراجع کد:**
- مدل: `bulk_importer/models.py` → `DocumentTable`
- سایر: `bulk_importer/models.py` (1)، `bulk_importer/persistence.py` (1)

**نمونه داده:**

| id | document_file_id | table_name | table_index | logical_section | extraction_status | row_count | column_count | raw_json | created_at | updated_at | gregorian_date | … |
|---|---|---|---|---|---|---|---|---|---|---|---|…|
| 166 | 110 | Sheet1 | 0 | balance_sheet | success | 144 | 61 | {'rows': [['240,000 میلیون ریا… | 2026-07-20 03:14:26.183435 | NULL | 2026-07-20 | … |
| 167 | 113 | Sheet1 | 0 | NULL | success | 68 | 28 | {'rows': [['150,000 میلیون ریا… | 2026-07-20 03:14:26.183436 | NULL | 2026-07-20 | … |

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
<summary><code>news_articles</code> — ~1,819 ردیف، 16 ستون (نمایش 12 ستون از 16)</summary>

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
| news_7cff672805c6485781f0eb55 | آینده تنگه هرمز از نگاه بازار … | NULL | NULL | fardaye_energy | https://www.fardayeeghtesad.co… | companies | NULL | 2026-04-28T07:02:35+00:00 | neutral | 0.0 | rss | … |
| news_d41fd9a46369432d987506f7 | نسخه انتخاب سهام در گروه دارو | واچ‌لیست با علی‌تسنیمی | واچ‌لیست با علی‌تسنیمی | fardaye_bourse | https://www.fardayeeghtesad.co… | market | NULL | 2026-05-30T15:00:00+00:00 | neutral | 0.0 | rss | … |

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

سکوی داده شامل **122 جدول** و حدود **~32,896,752 ردیف** است. از این میان **58 جدول خالی**، **6 جدول نسخه قدیمی** با جایگزین زنده `brsapi_*`، **6 جدول بدون مدل ORM** و **1 جدول بدون هیچ مرجع کد فعال** وجود دارد (برای **10 جدول** آمار PostgreSQL جمع نشده و برآورد ردیف دقیق نیست).

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

## 🧪 تست‌ها

### انواع تست

```bash
# تست‌های unit
pytest tests/unit -v

# تست‌های integration
pytest tests/integration -v

# تست‌های e2e
pytest tests/e2e -v

# تست‌های عملکرد
pytest -m performance

# با coverage
pytest --cov=. --cov-report=html
```

### تست‌های فرانت‌اند

```bash
cd frontend
npm test              # اجرای تست‌ها
npm run test:watch    # حالت watch
npm run lint          # بررسی lint
npx tsc --noEmit      # بررسی TypeScript
```

---

## 🚀 استقرار

### Docker Swarm (تولید)

```bash
# ساخت swarm
docker swarm init

# استقرار
docker stack deploy -c docker-compose.yml -c docker-compose.production.yml market

# مشاهده وضعیت
docker stack services market
```

### CI/CD (GitHub Actions)

```yaml
# .github/workflows/ci.yml
- Lint & Typecheck (ruff, mypy)
- Backend Tests (pytest)
- Docker Build & Push
- Frontend Build & Test
```

---

## ⚠️ مشکلات شناخته‌شده و محدودیت‌ها

> آخرین به‌روزرسانی: ۲۰۲۶-۰۸-۰۵

این بخش شامل اشکلات، محدودیت‌ها و بدهی فنی فعلی پروژه است. وضعیت هر مورد بر اساس **بررسی مستقیم کد** به‌روزرسانی شده است:

- ✅ **رفع شده** — در کد فعلی پیاده‌سازی شده
- 🟡 **جزئی** — زیرساخت/ابزار اضافه شده ولی کامل نیست
- ❌ **فعال** — همچنان وجود دارد

> برای جزئیات بیشتر و کد پیشنهادی، [ANALYSIS.md](ANALYSIS.md) را ببینید.

### 🔴 بحرانی (Critical)

| # | مشکل | مکان | وضعیت | توضیح |
|---|-------|------|--------|-------|
| ۱ | **Connection Pool خیلی کم** | `core/config/__init__.py:27` | ✅ | پیش‌فرض به `pool_size=20, max_overflow=30` افزایش یافت (قابل تنظیم با `DATABASE_POOL_SIZE`) — همه اسکریپت‌ها هم از `settings` می‌خوانند. توجه: در حالت چند-worker، pool هر worker جداگانه است (تا ~۵۰ اتصال در هر worker) — با `workers>1` مقدار `max_connections` پستگرس را بررسی کنید |
| ۲ | **CORS باز** | `core/config/__init__.py:43` | ✅ | پیش‌فرض به `["http://localhost:3000"]` محدود شد (قابل تنظیم با `CORS_ORIGINS`) و `validate_production()` همچنان مقدار `*` را در production رد می‌کند |
| ۳ | **State در حافظه** | `apps/api/app.py:42-61` | ✅ | `_cron_state` و `_alert_state` حالا از Redis (کلیدهای `orchestrator:cron_state` / `orchestrator:alert_state` بدون TTL) بارگذاری/ذخیره می‌شوند — با fallback درون‌حافظه وقتی Redis در دسترس نیست؛ sync بین workerها و بقای state بعد از restart |
| ۴ | **SQL خام در سرویس‌ها** | `multi_market_signal_engine.py` | ✅ | همه کوئری‌های `text()` به ORM `select()` تبدیل شدند — مدل‌های `CodalAuditSummaryModel` و `CryptoDailyHistoryModel` اضافه شدند (ستون‌ها با schema زنده تطبیق داده شدند) و فیلدهای `func.abs` / join بدون f-string |
| ۵ | **BrsApi TLS غیرفعال** | `brsapi/client.py` | ✅ | `verify_ssl` با پیش‌فرض `True` فعال شد (client، history_fetch و همه اسکریپت‌ها) — در صورت نیاز با `BRSAPI_VERIFY_SSL=false` غیرفعال می‌شود |
| ۶ | **رمز عبور در اسکریپت‌ها** | `scripts/_db.py` (جدید) | ✅ | همه اسکریپت‌ها (شامل `check_brsapi_tables.py`, `check_db_direct.py`, `run_train_all_symbols.py`, `sync_live_data.py`, `test_train_foolad.py`, `fix_categories.py`, `find_duplicate_symbols.py`, `remove_duplicate_symbols.py`, `check_codal_data.py`, `check_uncat.py`, `fix_remaining_categories.py` و تست‌ها) به `settings.database_url` منتقل شدند — helper مشترک `scripts/_db.py` با `psycopg2_connect()` / `database_url_async()` و **هیچ credential هاردکدشده‌ای باقی نمانده** |

### 🟠 بالا (High)

| # | مشکل | مکان | وضعیت | توضیح |
|---|-------|------|--------|-------|
| ۷ | **بدون Distributed Locking** | `jobs/locking.py` | ✅ | `JobLocking` به قفل توزیع‌شده Redis با TTL ارتقا یافت (`SET key owner NX PX <ms>` + Lua مقایسه‌ای برای release/extend اتمیک) — فقط owner می‌تواند قفل را آزاد/تمدید کند و TTL خودکار مانع قفل‌ماندن پس از crash می‌شود؛ با fallback درون‌حافظه وقتی Redis در دسترس نیست (خطای مقطعی Redis = fail-closed، اجرای هم‌زمان نمی‌شود) — ۱۷ تست واحد (`tests/unit/jobs/test_locking.py`) |
| ۸ | **رقابت DB در شروع** | `apps/api/app.py` | ✅ | startup sync به یک background task با retry تبدیل شد و dedup در `sync_service` جلوی تکرار را می‌گیرد؛ **حالا `_brsapi_startup_sync`، `_fetch_news_on_startup` و `_decision_engine_startup_seed` با قفل توزیع‌شده (`JobLocking` مشترک، کلید `startup:*`، TTL 600s) محافظت می‌شوند** — worker دوم/فرایند SchedulerApp هم‌زمان همان task را اجرا نمی‌کند (2 تست در `tests/unit/test_input_sanitization.py`) |
| ۹ | **پایپ‌لاین سیگنال تک‌رشته** | `quant_signal_orchestrator.py:1290` | ✅ | از `asyncio.gather(*tasks, return_exceptions=True)` برای موازی‌سازی استفاده می‌شود |
| ۱۰ | **CSRF Protection ندارد** | `apps/api/middleware.py` | ✅ | `CSRFMiddleware` پیاده‌سازی و ثبت شد: برای متدهای ناامن (POST/PUT/PATCH/DELETE) درخواست‌های دارای Origin/Referer فقط در صورت تطبیق با `cors_origins` پذیرفته می‌شوند (بدون Origin/Referer = کلاینت غیرمرورگر → مجاز). غیرفعال وقتی `enable_csrf=False` — ۷ تست واحد (`tests/unit/test_security_hardening.py`) |
| ۱۱ | **JWT Revocation ندارد** | `core/security/tokens.py` | ✅ | blacklist کامل access token با `jti`: هر access token یک `jti` یکتا دارد؛ logout با `revoke_access_token()` آن را در Redis (با TTL تا انقضای طبیعی) باطل می‌کند؛ `get_current_user`/`get_optional_user`/middleware/`verify_token` همه توکن‌های revoked را با 401 رد می‌کنند — با fallback امن وقتی Redis در دسترس نیست — ۹ تست واحد (`tests/unit/test_security_hardening.py`) |
| ۱۲ | **MFA ندارد** | `core/security/secrets.py` | ✅ | MFA/TOTP کامل پیاده‌سازی شد: ماژول `core/security/totp.py` (RFC 6238 بدون وابستگی جدید — HMAC-SHA1/256/512، ۶ رقم، پنجره ±۱ مرحله) + ستون‌های `totp_secret`/`totp_enabled`/`totp_confirmed_at`/`mfa_method` در `UserModel` (مهاجرت‌های `0022` + `0023`) + جریان login دو مرحله‌ای (`/login` → `mfa_required` + توکن یک‌بارمصرف اتمیک در Redis → `/mfa/login`) + endpoint های `/mfa/status`, `/mfa/setup`, `/mfa/confirm`, `/mfa/disable` — **سه روش MFA**: authenticator app (TOTP)، ایمیل یا تلگرام (کد ۶ رقمی با `generate_otp` ارسالی) — fail-closed وقتی Redis/ارسال در دسترس نیست و rate limit ضد brute-force روی تأیید کد (۱۰ تلاش/۵ دقیقه/IP) — ۲۵ تست واحد (`tests/unit/test_totp_mfa.py`) |
| ۱۳ | **بدون Reverse Proxy** | `deploy/nginx/nginx.conf` | ✅ | nginx به عنوان reverse proxy با TLS-ready پیکربندی اضافه شد (`deploy/nginx/nginx.conf`): upstream `api:8000` (backend) و `frontend:3000`، rate limiting، gzip، headerهای امنیتی و health check — سرویس nginx در `docker-compose.production.yml` با پورت ۸۰/۴۴۳ |
| ۱۴ | **بدون TimescaleDB Hypertable** | `migrations/versions/0001_initial_schema.py` | ✅ | `create_hypertable()` برای ۱۰+ جدول (snapshots, trades, daily_history, candlesticks و…) اجرا می‌شود |
| ۱۵ | **Duplicate Cache** | `core/cache.py` vs `integrations/cache/` | ✅ | یکپارچه شد: `integrations/cache/RedisClient` حالا facade روی `get_cache()` مشترک است (یک اتصال Redis برای کل فرایند؛ URL سفارشی همچنان اتصال خصوصی می‌گیرد) + `ping()` اضافه شد (رفع باگ پنهان HealthCheckJob)؛ `CacheManager` مرده (`manager.py`) حذف شد؛ `CacheWarmupJob`/`HealthCheckJob` به `get_cache()` مشترک منتقل شدند و `initialize()` ایدمپوتنت شد — ۱۰ تست واحد (`tests/unit/test_cache_unification.py`) |

### 🟡 متوسط (Medium)

| # | مشکل | مکان | وضعیت | توضیح |
|---|-------|------|--------|-------|
| ۱۶ | **API Versioning ندارد** | `core/config/__init__.py` | ✅ | پیشوند رسمی `/api/v1` فعال است |
| ۱۷ | **Input Sanitization ناقص** | `apps/api/middleware.py` | ✅ | `InputSanitizationMiddleware` پیاده‌سازی و ثبت شد (قابل تنظیم با `ENABLE_INPUT_SANITIZATION`): بدنه JSON درخواست‌ها به‌صورت بازگشتی پاک‌سازی می‌شود — حذف تگ‌های HTML/کاراکترهای کنترلی (CR/LF/NUL)، truncate رشته‌های بزرگ، رد نوع‌های غیرمجاز در فیلدهای متنی (400)، و **حفظ فیلدهای opaque** (رمز عبور، کد، توکن، secret) برای تطبیق دقیق — 15 تست واحد (`tests/unit/test_input_sanitization.py`) |
| ۱۸ | **Monitoring In-Memory** | `integrations/observability/` | 🟡 | `PrometheusExporter` و `OTelExporter` اضافه شده‌اند — اتصال کامل به endpoint هنوز ناقص |
| ۱۹ | **Tracing ناسازگار با OTel** | `integrations/observability/otel_exporter.py` | ✅ | `OTelExporter` سازگار با OpenTelemetry پیاده‌سازی شده |
| ۲۰ | **Prometheus Endpoint ندارد** | `core/config/monitoring.py` | ✅ | route `/metrics` در `apps/api/app.py` فعال شد (متن exposition فرمت Prometheus با `media_type=text/plain; version=0.0.4`) + `MetricsMiddleware` که counter درخواست‌ها، هیستوگرام latency و شمارنده خطاها را با برچسب method/route/status ثبت می‌کند — مسیر از RateLimit exempt شد — ۵ تست واحد (`tests/unit/test_security_hardening.py`) |
| ۲۱ | **Log Aggregation ندارد** | — | ✅ | `integrations/observability/log_aggregator.py` اضافه شد: `RedisLogHandler` هر رکورد لاگ را به Redis Stream (`log-aggregator:stream`، cap ۵۰K) با فیلدهای source/level/timestamp/message انتشار می‌دهد تا collector مرکزی (Loki/ELK/Vector) آن را tail کند — publish best-effort و غیرمسدودکننده (شکست فقط شمارش می‌شود)؛ فعال با `LOG_AGGREGATION_ENABLED=true` |
| ۲۲ | **S3 Storage ناقص** | `codal_attachment_service.py` | ✅ | خواندن از S3 کامل شد: `get_attachment_stream`/`get_attachment_content` از `S3CompatibleStorage` (MinIO) استفاده می‌کنند و پیوست‌ها به‌صورت streaming با `get_object` دانلود می‌شوند — fallback به ذخیره محلی وقتی S3 پیکربندی نشده — endpoint دانلود پیوست (`apps/api/endpoints/codal.py`) به نسخه async ارتقا یافت |
| ۲۳ | **ارز و کالا سیگنال ضعیف** | `multi_market_signal_engine.py` | 🟡 | ارز و طلا به امتیاز ترکیبی `_composite_buy_score` (RSI + مومنتوم + روند MA + فیلتر نوسان ATR) ارتقا یافتند — بازده دنبال‌کردن ارز از ۰.۳۷٪ به ۰.۸۰٪ و طلا از ۰.۴۵٪ به ۰.۵۸٪ رسید؛ هنوز crypto/commodity/ime با threshold ساده `chg_pct` کار می‌کنند |
| ۲۴ | **Models In-Memory** | `ml_signal_connector.py` | 🟡 | `load_models_from_disk()` اضافه شده — lazy loading از disk پشتیبانی می‌شود |
| ۲۵ | **Feature Store ندارد** | `ml/feature_store.py`, `services/smart_money/feature_store.py` | ✅ | Feature Store با TTL caching پیاده‌سازی شده |

### 🟢 پایین (Low) — بدهی فنی

| # | مشکل | مکان | وضعیت | توضیح |
|---|-------|------|--------|-------|
| ۲۶ | **`type: ignore` زیاد** | ۵۰+ نقطه | ❌ | تایپ‌سیفیتی ناقص |
| ۲۷ | **`noqa: BLE001` زیاد** | ۱۰+ نقطه | ❌ | `except Exception` عام |
| ۲۸ | **BUG FIX‌های پراکنده** | `backtesting/` | ✅ | باگ‌های #1-#20 رفع شده و **تست رگرسیون متمرکز اضافه شد** (`tests/unit/backtesting/test_risk_bugfixes_regression.py` — ۳۲ تست برای stop_loss, take_profit, position_sizing, risk_metrics) |
| ۲۹ | **ابزارهای منسوخ** | `scripts/import_csv.py` | ✅ | اسکریپت قدیمی حذف شده؛ ایمپورت CSV اکنون در `providers/reference/manual/file_importer.py` انجام می‌شود |
| ۳۰ | **Endpoints منسوخ BrsApi** | `brsapi/services/sync_service.py` | ✅ | `Coin.php`/`Currency.php` رسماً deprecated اعلام شده و با `Gold_Currency.php` ترکیبی جایگزین شده‌اند |
| ۳۱ | **Jobs منسوخ** | `jobs/definitions/sync_jobs.py` | ✅ | کلاس‌های `SyncInstrumentsJob`, `SyncQuotesJob`, `SyncCodalJob` از `BaseJob` ساخته شده‌اند و توابع قدیمی deprecated شدند |
| ۳۲ | **TODO‌های باقیمانده** | `services/fund_service.py`, `populate_profiles_service.py` | ❌ | همچنان TODO‌ها موجودند (NAV repo, gross_margin, inflation_rate) |
| ۳۳ | **Graceful Shutdown ناقص** | `apps/api/app.py` | ✅ | lifespan شامل توقف RealtimeService، بستن cache و close database است |

### 🔵 بازارهای پوشش‌داده‌نشده

| بازار | وضعیت | توضیح |
|-------|-------|-------|
| اوراق قرضه (Bonds) | ❌ وجود ندارد | نیاز به duration، منحنی بازده، credit spread |
| ETF / صندوق‌ها | 🟡 جزئی | داده و سرویس صندوق (FundService, `/funds`) اضافه شده — تحلیل NAV discount/premium و tracking error هنوز کامل نیست |
| Forex Futures | ❌ وجود ندارد | نیاز به داده‌های آتی ارز |
| شاخص‌های بین‌المللی | ❌ وجود ندارد | S&P500, NASDAQ, DAX, Nikkei |
| کالاهای کشاورزی | ❌ وجود ندارد | گندم، ذرت، سویا |
| اوراق اسلامی (Sukuk) | ❌ وجود ندارد | ابزارهای مالی اسلامی |

### 📊 BUG FIX‌های اعمال‌شده در بک‌تست

این باگ‌ها در موتور بک‌تست شناسایی و رفع شده‌اند:

| # | باگ | فایل | توضیح |
|---|-----|------|-------|
| ۱ | Stop Loss درصدی | `backtesting/risk/stop_loss.py:66` | بررسی نادرست در برابر entry price |
| ۲ | Take Profit درصدی | `backtesting/risk/take_profit.py:44` | بررسی نادرست در برابر entry price |
| ۵ | Volatility صفر | `backtesting/risk/position_sizing.py:19` | تقسیم بر صفر — fallback به max position |
| ۶ | Kelly فرمول | `backtesting/risk/position_sizing.py:27` | فرمول استاندارد Kelly برای payoff کسری |
| ۷ | محاسبه PnL | `backtesting/metrics/trade_metrics.py:21` | جفت‌سازی خرید/فروش به ازای هر نماد |
| ۹ | Calmar Ratio | `backtesting/metrics/risk_metrics.py:28` | max_drawdown از قبل درصد بود — واحد ناسازگار |
| ۱۰ | Omega Ratio | `backtesting/metrics/risk_metrics.py:40` | تقسیم بر صفر — نیاز به clamp |
| ۱۱ | بازده مثبت | `backtesting/metrics/risk_metrics.py:50` | همه بازده‌ها مثبت → خطای Sortino |
| ۱۵ | فروش بدون موقعیت | `backtesting/strategies/rule_based/moving_average_cross.py:45` | فروش وقتی موقعیت long نیست |
| ۲۰ | انحراف معیار نمونه | `backtesting/metrics/risk_metrics.py:16,56` | استفاده از `ddof=1` برای سری بازده مالی |

### 📡 BUG FIX‌های اعمال‌شده در BrsApi Sync

این باگ‌ها هنگام بررسی لاگ‌های تولید (cron، ۲۰۲۶-۰۸-۰۲) شناسایی و رفع شده‌اند — هر دو جاب `brsapi_all_symbols` و `brsapi_index` هر ۲ دقیقه با خطا FAIL می‌شدند:

| # | باگ | فایل | توضیح |
|---|-----|------|-------|
| ۱ | `ON CONFLICT DO UPDATE` بدون target | `brsapi/repositories/base.py:232,259` + `brsapi/services/sync_service.py:287` | سینتکس نامعتبر Postgres باعث FAIL جاب `brsapi_all_symbols` هر ۲ دقیقه می‌شد → پارامتر `conflict_target` الزامی شد و SQL معتبر `ON CONFLICT ("symbol","fetched_at") DO UPDATE` تولید می‌شود (بدون target → `ValueError` صریح) |
| ۲ | رشته در ستون DateTime | `brsapi/parsers/tsetmc.py:209` + `brsapi/models/tsetmc.py:250` | `parse_index` مقدار رشته در `fetched_at` می‌نوشت و asyncpg با `DataError` رد می‌کرد (FAIL جاب `brsapi_index`) → حالا `datetime` واقعی تولید می‌کند و مدل `IndexValueModel.fetched_at` به `DateTime` هماهنگ با دیتابیس زنده شد |
| ۳ | رشته در ستون DateTime + عدم وجود constraint یکتا | `brsapi/parsers/tsetmc.py:41,85` + `brsapi/models/tsetmc.py:125` | باگ پنهان (ماسک‌شده توسط باگ #۱): `parse_all_symbols` رشته در `fetched_at` می‌نوشت در حالی که ستون زنده `timestamptz` است، و `SymbolSnapshotModel.fetched_at` در مدل `String(30)` بود → به `DateTime` تغییر کرد و `uq_snap_symbol_fetched` (symbol, fetched_at) مستقیماً روی دیتابیس زنده اعمال شد (بعد از تأیید صفر duplicate). سینک زنده تأیید شد: `sync_all_symbols` → ۱٬۴۹۰ نماد با success |

> تأیید: ۱۲ تست واحد (`tests/unit/test_brsapi_sync_fixes.py`) + ۳ تست یکپارچه‌سازی روی دیتابیس واقعی (`tests/unit/test_brsapi_sync_integration.py`) پاس شدند + **سینک زنده با API واقعی BrsApi** تأیید شد. ستون‌های زنده از قبل `timestamptz` بودند (نیازی به مهاجرت ستون نبود)؛ فقط constraint یکتا باید روی هر محیط جدید اعمال شود (مهاجرت `0020` به‌دلیل زنجیره شکسته alembic — `0021` موجود نیست — قابل اجرا نیست؛ این زنجیره در بک‌لاگ است).

### 🛣️ نقشه راه رفع مشکلات

> نقشه راه کامل با کد پیشنهادی در [ANALYSIS.md § نقشه راه توسعه](ANALYSIS.md#۱۷-نقشه-راه-توسعه) موجود است.
> وضعیت به‌روزشده: بخشی از فازهای ۱ و ۲ (hypertables، feature store، موازی‌سازی pipeline، API versioning) ✅ تکمیل شده و بقیه عمدتاً مربوط به فازهای ۳ و ۴ است.
> پچ‌های تولید ۲۰۲۶-۰۸ (رفع سینک BrsApi، سیگنال composite ارز/طلا، ریشه‌یابی direction_correct، رفع باگ RSI=0) اعمال شده و با تست‌های واحد + یکپارچه‌سازی روی دیتابیس واقعی تأیید شدند.

| فاز | وضعیت | اولویت‌های باقی‌مانده |
|-----|--------|---------------------|
| **۱. تثبیت** | 🟢 کامل | افزایش `pool_size` پیش‌فرض ✅، TLS برای BrsApi ✅، Redis-backed state ✅، Redis-backed distributed lock (`jobs/locking.py`) ✅ |
| **۲. بهینه‌سازی** | 🟡 نیمه‌کامل | یکپارچه‌سازی cache‌های تکراری، کامل‌کردن S3 storage |
| **۳. امنیت** | ❌ باز | CSRF middleware، JWT blacklist، MFA، input sanitization، secrets manager |
| **۴. مانیتورینگ** | 🟡 در حال انجام | فعال‌سازی route `/metrics`، Prometheus+Grafana، log aggregation |

---

## 🔧 عیب‌یابی

### خطاهای رایج

| مشکل | راه‌حل |
|------|--------|
| **خطای اتصال دیتابیس** | بررسی کنید PostgreSQL در حال اجراست: `pg_isready` — سپس `DATABASE_URL` را در `.env` بررسی کنید |
| **Redis در دسترس نیست** | بررسی کنید Redis در حال اجراست: `redis-cli ping` — سپس `REDIS_URL` را بررسی کنید |
| **CORS Error** | در `.env` مقدار `CORS_ORIGINS` را تنظیم کنید: `CORS_ORIGINS=["http://localhost:3000"]` |
| **خطای Rate Limit** | BrsApi دارای محدودیت ۱۰K/day و ۵۰۰/5min است. صبر کنید یا `brsapi/rate_limiter.py` را تنظیم کنید |
| **خطای CERTIFICATE_VERIFY_FAILED در BrsApi** | از نسخه جدید، `verify_ssl=True` پیش‌فرض است. اگر گواهی سرور در CA store سیستم شما قابل اعتماد نیست، `BRSAPI_VERIFY_SSL=false` را در `.env` تنظیم کنید |
| **فرانت‌اند build نمی‌شود** | `cd frontend && rm -rf node_modules && npm install` را اجرا کنید |
| **مهاجرت اجرا نمی‌شود** | مطمئن شوید `alembic` نصب است و `alembic upgrade head` را اجرا کنید |
| **تلگرام هشدار نمی‌دهد** | `TELEGRAM_BOT_TOKEN` و `TELEGRAM_CHAT_ID` را در `.env` تنظیم کنید (مرحله ساخت ربات را ببینید) |

### نکات توسعه

```bash
# بررسی وضعیت سیستم
python -c "from core.config import settings; print(settings.database_url)"

# پاکسازی کش
redis-cli FLUSHALL

# مشاهده لاگ‌های API
# لاگ‌ها در کنسول و اختیاری در فایل logs/ ذخیره می‌شوند
```

---

## 🤝 توسعه و مشارکت

### راهنمای توسعه

1. **fork** کنید
2. **branch** جدید بسازید
3. **تغییرات** را اعمال کنید
4. **تست** کنید
5. **PR** بفرستید

### استانداردهای کد

- **Linting**: ruff
- **Type Checking**: mypy
- **Testing**: pytest
- **Formatting**: ruff format

### ساختار commits

```
feat: افزودن ویژگی جدید
fix: رفع باگ
docs: به‌روزرسانی مستندات
test: افزودن تست
refactor: بازآرایی کد
chore: وظایف نگهداری
```

---

## 📄 مجوز

MIT License — مشاهده [LICENSE](LICENSE) برای جزئیات.

---

## 🙏 قدردانی

- **FastAPI** — فریمورک API
- **Next.js** — فریمورک React
- **PostgreSQL** — دیتابیس
- **Redis** — کش
- **Recharts** — نمودارها
- **TanStack Query** — مدیریت state
- **BrsApi.ir** — ارائه‌دهنده داده

---

<p align="center">ساخته شده با ❤️ برای بازار سرمایه ایران</p>
