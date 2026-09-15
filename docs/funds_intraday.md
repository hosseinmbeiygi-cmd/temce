# Funds Intraday — داده‌های درون‌روز ۵۰ صندوق برتر

End-to-end pipeline برای استخراج، همگام‌سازی، تحلیل، و نمایش تیک‌های
درون‌روز صندوق‌های سرمایه‌گذاری بورس تهران و کالا.

## معماری

```
┌────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│ BrsApi.ir  │───▶│  Sync Job   │───▶│  PostgreSQL  │◀──▶│  FastAPI     │
│ (Tsetmc)   │    │  Service    │    │ brsapi_      │    │  /funds/     │
└────────────┘    └─────────────┘    │ intraday_    │    │  intraday/*  │
                                    │ trades       │    └──────┬───────┘
                                    └──────────────┘           │
                                                                ▼
                                                  ┌──────────────────────┐
                                                  │ Next.js (lightweight- │
                                                  │ charts) / CLI / SSE   │
                                                  └──────────────────────┘
```

## API Endpoints (mounted at `/api/v1/funds/`)

| Method | Path                          | توضیح                                              |
| ------ | ----------------------------- | -------------------------------------------------- |
| GET    | `/intraday`                   | تیک‌های خام (`time, price, volume, canceled`)      |
| GET    | `/intraday/candles`           | کندل OHLCV با `vwap` (interval_minutes=1..60)      |
| GET    | `/intraday/stream`            | **SSE** — استریم زنده تیک‌ها (heartbeat هر 5s)     |
| GET    | `/top`                        | رتبه‌بندی صندوق‌ها بر اساس ۵ معیار                  |

### مثال‌ها

```bash
# تیک‌های خام (۳ تیک آخر)
curl "http://localhost:8000/api/v1/funds/intraday?symbols=عیار,یاقوت&limit=3"

# کندل ۵ دقیقه‌ای
curl "http://localhost:8000/api/v1/funds/intraday/candles?symbols=عیار&interval_minutes=5"

# استریم زنده (heartbeat با "."، تیک با JSON)
curl -N "http://localhost:8000/api/v1/funds/intraday/stream?symbols=عیار&poll_seconds=2"

# رتبه‌بندی بر اساس تعداد تیک
curl "http://localhost:8000/api/v1/funds/top?metric=intraday_volume&top=10"
```

### پارامترهای `/top`

| metric            | منبع داده                                    |
| ----------------- | -------------------------------------------- |
| `market_value`    | `brsapi_symbol_snapshots.market_value`       |
| `trade_volume`    | اسنپ‌شات — حجم معامله روز                    |
| `trade_value`     | اسنپ‌شات — ارزش معامله روز (ریال)            |
| `nav_change_pct`  | اسنپ‌شات — درصد تغییر NAV                    |
| `intraday_volume` | **زنده** — تعداد تیک‌های امروز               |

## Frontend (Next.js)

| مسیر                        | کامپوننت‌ها                                            |
| --------------------------- | ------------------------------------------------------ |
| `/funds/intraday`           | `IntradayCandleChart` + لیست برترین + جدول کندل        |
| `hooks/useFundIntraday.ts`  | `useFundIntraday`, `useFundCandles`, `useTopFunds`     |

اندیکاتورهای قابل انتخاب: **SMA20 / SMA50 / EMA20**. Interval: **1m/5m/15m/30m**.

## Data Pipeline

```bash
# 1) استخراج ۵۰ صندوق برتر (از اسنپ‌شات‌های امروز) + تیک‌هایشان
python scripts/fetch_top50_funds_intraday.py
# → data/top50_funds_intraday.json  (340 MB)

# 2) همگام‌سازی صندوق‌های فاقد تیک از BrsApi (با backwalk تاریخ)
python scripts/sync_missing_funds_intraday.py

# 3) بسته‌بندی: JSON → CSV.gz (340MB → 18MB)
python scripts/package_top50_funds.py
# → data/top50_funds_intraday/{summary.csv, ticks.csv.gz, funds/*.csv.gz, analysis.{json,txt}}

# 4) آمار per-fund
python scripts/analyze_top50_funds.py
```

## CLI Tools

```bash
# دریافت تیک/خلاصه برای یک یا چند صندوق
python scripts/cli_fund_intraday.py عیار یاقوت --limit 20
python scripts/cli_fund_intraday.py طلا --stats
python scripts/cli_fund_intraday.py عیار --date 1405-05-18 --include-canceled
python scripts/cli_fund_intraday.py عیار --limit 100 --csv out.csv

# مانیتور زنده (SSE)
python scripts/cli_fund_intraday_stream.py عیار یاقوت --poll 2
python scripts/cli_fund_intraday_stream.py عیار --max 50 --csv live.csv
```

## منابع داده

| جدول                              | محتوا                                              |
| --------------------------------- | -------------------------------------------------- |
| `brsapi_intraday_trades`          | تیک‌های خام (time, price, volume, canceled)        |
| `brsapi_symbol_snapshots`         | اسنپ‌شات لحظه‌ای هر نماد                           |
| `brsapi_nav_records`              | NAV صدور/ابطال روزانه (غنی‌سازی قیمت)              |
| `brsapi_ime_funds`                | صندوق‌های کالایی (طلا، نقره)                       |

## آمار نمونه (۲۰۲۶-۰۷-۱۵ شمسی)

| صندوق | تیک      | ارزش (ریال)       | VWAP    |
| ----- | -------- | ----------------- | ------- |
| عیار  | 676,117  | ۳۲۷٫۷ تریلیون     | ۵۱۰٬۷۷۲ |
| یاقوت | 349,054  | ۳۳۲٫۸ تریلیون     | ۴۵٬۰۷۰  |
| افران | 132,606  | ۱۳۹٫۶ تریلیون     | ۵۱٬۶۶۶  |
| لبخند | 130,112  | ۱۴۲٫۴ تریلیون     | ۲۹٬۵۸۹  |
| پاسارگاد | 105,014 | ۲۸۳٫۰ تریلیون | ۱۶٬۶۲۹ |

**کل**: ۲,۰۸۲,۱۱۳ تیک معتبر + ۱,۰۷۶ کنسل — ۴۷ از ۵۰ صندوق.

## نکات

- **backwalk تاریخ**: BrsApi برای ETFهای نسل جدید (نمادهای `*4`) در روزهای
  ابتدایی خطای `invalid_param` می‌دهد. اسکریپت sync با پیمایش ۱۴ روز اخیر
  بهترین تاریخ معتبر را پیدا می‌کند.
- **per-symbol last date**: هر صندوق ممکن است آخرین تاریخ تیک متفاوتی
  داشته باشد (آخر هفته، تعطیلی، ساعت کاری). API ها per-symbol last
  trade_date را query می‌کنند.
- **CORS**: frontend در `localhost:3000` به `/api/v1/*` proxy می‌شود
  (پیکربندی در `frontend/next.config.ts`).
