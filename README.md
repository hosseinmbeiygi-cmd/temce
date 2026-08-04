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

### جداول اصلی

| جدول | توضیح |
|------|---------|
| `instruments` | نمادها و ابزارها |
| `quotes` | قیمت‌ها |
| `trades` | معاملات |
| `orderbooks` | دفتر سفارشات |
| `signals` | سیگنال‌ها |
| `recommendations` | پیشنهادات |
| `news` | اخبار |
| `codal_reports` | اطلاعیه‌های کدال |
| `codal_financials` | صورت‌های مالی کدال |
| `backtests` | نتایج بک‌تست |
| `ml_models` | مدل‌های ML |
| `portfolios` | پرتفوی |
| `alerts` | هشدارها |
| `watchlists` | دیده‌بان |
| `saved_filters` | فیلترهای ذخیره شده |
| `decision_architectures` | معماری تصمیم‌گیری |
| `brsapi_crypto_daily_history` | ~۱۸K ردیف — تاریخچه رمزارز (۱۹ نماد) |
| `brsapi_gold_coin_history` | ~۴۴K ردیف — تاریخچه طلا و سکه (۲۳ نماد) |
| `brsapi_gold_currency_pro_daily_history` | ~۱۶۰K ردیف — تاریخچه ارز و XAUUSD (۷۲ نماد) |
| `codal_reports` | ~۲۲۷K ردیف — اطلاعیه‌های کدال (۵۱۹+ نماد) |
| `smart_money_scores` | امتیازهای Smart Money |
| `signal_accuracy` | دقت سیگنال‌ها |
| `job_runs` | اجرای شغل‌ها |
| `decision_architectures` | معماری تصمیم‌گیری |

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
| ۸ | **رقابت DB در شروع** | `apps/api/app.py` | 🟡 | startup sync به یک background task با retry تبدیل شده و dedup در `sync_service` جلوی تکرار را می‌گیرد — ولی همچنان هم‌زمان با SchedulerApp اجرا می‌شود |
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
| ۱۷ | **Input Sanitization ناقص** | — | ❌ | همچنان بررسی نشده / متصل نیست |
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
