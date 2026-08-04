# 💡 بینش بازار — Market Insights

> صفحه `/market-insights` در پلتفرم تحلیل بازار سرمایه ایران

سیستمی جامع برای شناسایی الگوهای پنهان، دستکاری، و تحلیل رفتار بازار با استفاده از داده‌های لحظه‌ای و تاریخی.

---

## 📑 فهرست مطالب

- [نمای کلی](#نمای-کلی)
- [ساختار کد](#ساختار-کد)
- [۶ ماژول تحلیلی](#۶-ماژول-تحلیلی)
  - [۱. شاخص ترس و طمع](#۱-شاخص-ترس-و-طمع-ایران)
  - [۲. شاخص سلامت بازار](#۲-شاخص-سلامت-بازار)
  - [۳. تشخیص صف کاذب](#۳-تشخیص-صف-کاذب)
  - [۴. انباشت پنهان](#۴-انباشت-پنهان)
  - [۵. تشخیص دستکاری](#۵-تشخیص-دستکاری)
  - [۶. معاملات بلوکی](#۶-معاملات-بلوکی)
- [ماژول‌های اضافی API](#ماژول‌های-اضافی-api)
- [API Endpoints](#api-endpoints)
- [مدل داده](#مدل-داده)
- [فناوری‌ها](#فناوری‌ها)

---

## نمای کلی

صفحه بینش بازار با ۶ تب ارائه می‌شود و داده‌ها را از جداول زیر استخراج می‌کند:

| جدول PostgreSQL | کاربرد |
|-----------------|--------|
| `brsapi_symbol_snapshots` | قیمت لحظه‌ای، حجم، صف خرید/فروش، جریان حقیقی/حقوقی |
| `brsapi_symbol_details` | EPS، P/E، شناور، حد مجاز |
| `brsapi_historical_daily` | قیمت‌های تاریخی، میانگین حجم ۲۰ روزه |
| `intraday_trades` | تیک‌های لحظه‌ای (۱۴.۸ میلیون+ رکورد) |
| `news_articles` | اخبار و تحلیل احساسات |
| `macro_indicators` | نرخ تورم و شاخص‌های کلان |

---

## ساختار کد

```
apps/api/endpoints/market_insights.py    ← API Endpoints (۱۲ endpoint)
frontend/src/app/market-insights/page.tsx ← صفحه فرانت‌اند (۶ تب)

services/
├── iran_fear_greed_index.py    ← شاخص ترس و طمع ایران
├── market_health_index.py      ← شاخص سلامت بازار
├── fake_queue_detector.py      ← تشخیص صف کاذب
├── hidden_accumulation.py      ← تشخیص انباشت پنهان
├── manipulation_detector.py    ← تشخیص دستکاری قیمت
├── block_trade_detector.py     ← تشخیص معاملات بلوکی
├── real_return_calculator.py   ← محاسبه بازده واقعی (تورم+ارز)
├── gap_prediction.py           ← پیش‌بینی شکاف قیمتی بازگشایی
└── historical_level_analyzer.py ← سطوح حمایت/مقاومت تاریخی
```

---

## ۶ ماژول تحلیلی

### ۱. شاخص ترس و طمع ایران 🎯

**کلاس:** `IranFearGreedIndex`  
**API:** `GET /api/v1/market-insights/fear-greed`

شاخص اختصاصی بازار ایران از ترکیب ۵ مؤلفه:

| مؤلفه | وزن | محاسبه | منبع |
|-------|-----|--------|------|
| نسبت خرید حقیقی/حقوقی | ۳۰٪ | نسبت حجم خرید حقیقی به کل خرید | `brsapi_symbol_snapshots` |
| سطح فعالیت بازار | ۲۰٪ | نسبت ارزش معاملات امروز به میانگین ۳۰ روزه | `brsapi_historical_daily` |
| فاصله از میانگین ۲۰۰ روزه | ۲۰٪ | فاصله قیمت متوسط ۳۰ نماد برتر از MA200 | `brsapi_historical_daily` |
| نوسان‌پذیری | ۱۵٪ | نسبت ATR فعلی به میانگین ۶ ماهه | `brsapi_historical_daily` |
| احساسات اخبار | ۱۵٪ | نسبت اخبار منفی ۲۴ ساعت اخیر | `news_articles` |

**خروجی:**
```json
{
  "overall_score": 65.3,
  "label": "طمع",
  "components": {
    "real_legal_ratio": 72.1,
    "activity_level": 58.4,
    "trend_extension": 71.0,
    "volatility": 55.2,
    "news_sentiment": 68.0
  },
  "date": "2026-07-28"
}
```

** مقیاس:**
| امتیاز | برچسب | توصیه |
|--------|-------|-------|
| ۰-۲۰ | ترس شدید | فروش اضطراری در بازار |
| ۲۰-۴۰ | ترس | احتیاط در خرید |
| ۴۰-۶۰ | خنثی | بازار عادی |
| ۶۰-۸۰ | طمع | فرصت خرید |
| ۸۰-۱۰۰ | طمع شدید | احتیاط در خرید بیشتر |

---

### ۲. شاخص سلامت بازار 💓

**کلاس:** `MarketHealthIndex`  
**API:** `GET /api/v1/market-insights/market-health`

شاخص سلامت ساختاری بازار از ترکیب ۴ مؤلفه:

| مؤلفه | وزن | محاسبه |
|-------|-----|--------|
| جریان پول حقیقی/حقوقی | ۳۰٪ | نسبت خالص خرید به کل معاملات |
| پراکندگی قیمت | ۳۰٪ | انحراف معیار تغییرات قیمت بین گروه‌های بازار |
| نسبت معاملات بلوکی | ۲۰٪ | درصد معاملات بالای ۵ میلیارد تومان |
| ثبات VWAP | ۲۰٪ | میانگین دامنه نوسان درون‌روزی |

**خروجی:**
```json
{
  "overall_score": 58.7,
  "label": "بازار عادی",
  "components": {
    "real_legal_flow": 62.3,
    "price_dispersion": 55.1,
    "block_trade_ratio": 52.8,
    "vwap_stability": 64.5
  },
  "recommendations": [
    "استراتژی‌های معمول قابل اجراست",
    "تنوع‌بخشی را رعایت کنید"
  ]
}
```

**مقیاس:**
| امتیاز | برچسب | توصیه |
|--------|-------|-------|
| ۰-۳۰ | بازار بیمار | از معامله خودداری کنید |
| ۳۰-۵۰ | بازار ضعیف | فقط معاملات کوتاه‌مدت |
| ۵۰-۷۰ | بازار عادی | استراتژی‌های معمول |
| ۷۰-۱۰۰ | بازار سالم | شرایط مساعد برای معامله |

---

### ۳. تشخیص صف کاذب 🎭

**کلاس:** `FakeQueueDetector`  
**API:** `GET /api/v1/market-insights/fake-queues?limit=50`  
**API:** `GET /api/v1/market-insights/fake-queues/{symbol}`

شناسایی صف‌های کاذب خرید و فروش با تحلیل ۴ الگو:

| الگو | شرط شناسایی | امتیان اطمینان |
|------|-------------|---------------|
| صف بزرگ بدون حرکت قیمت | نسبت صف > ۳x حجم معاملات + تغییر قیمت < ۰.۵٪ | ۰.۴ |
| سفارش متوسط بزرگ | اندازه متوسط سفارش > ۱۰x اندازه متوسط معامله | ۰.۳ |
| فقط حقوقی در صف | خرید حقوقی > ۰ بدون خرید حقیقی | ۰.۲ |

**خروجی:**
```json
{
  "items": [
    {
      "symbol": "فولاد",
      "name": "فولاد مبارکه",
      "fake_buy_queue": true,
      "fake_sell_queue": false,
      "confidence": 0.85,
      "reason": " صف خرید ۴.۲x حجم معاملات با تغییر قیمت کمتر از ۰.۵٪"
    }
  ],
  "total": 12
}
```

---

### ۴. انباشت پنهان 🏦

**کلاس:** `HiddenAccumulationDetector`  
**API:** `GET /api/v1/market-insights/accumulation?limit=50`

شناسایی نمادهایی که پول هوشمند در حال جمع‌آوری بدون حرکت قیمت هستند:

| الگو | شرط | امتیاز |
|------|-----|--------|
| حجم بالا + قیمت ثابت | حجم > ۲x میانگین ۲۰ روزه + تغییر قیمت < ۱٪ | ۳۰ |
| فشار خرید خالص | نسبت خرید > ۶۰٪ | ۲۵ |
| ترکیب حجم + خرید خالص | حجم > ۲.۵x + خرید خالص مثبت | ۲۰ |
| خرید حقوقی بالا | خرید حقوقی > فروش حقوقی | ۱۵ |
| حجم فوق‌العاده | حجم > ۳x میانگین | ۱۰ |

**نمره‌دهی:** مجموع امتیازات تا ۱۰۰ (حداقل ۳۰ برای نمایش)

**خروجی:**
```json
{
  "items": [
    {
      "symbol": "فملی",
      "name": "ملی مس ایران",
      "score": 85,
      "volume_ratio": 3.2,
      "price_change_pct": 0.8,
      "net_real_flow": 15000000000,
      "reason": "حجم ۳.۲x میانگین با تغییر قیمت ۰.۸٪ | فشار خرید خالص ۶۸٪"
    }
  ]
}
```

---

### ۵. تشخیص دستکاری ⚠️

**کلاس:** `ManipulationDetector`  
**API:** `GET /api/v1/market-insights/manipulation?limit=50`  
**API:** `GET /api/v1/market-insights/manipulation/{symbol}`

شناسایی ۲ الگوی رایج دستکاری:

#### الگوی ۱:دامنه (Range Trap)
- قیمت در محدوده < ۲٪ نوسان می‌کند
- تعداد معاملات > ۵۰۰
- شدت معاملات > ۵۰ معامله/میلیون تومان
- **توصیه:** احتمال چرخش پول بین حساب‌ها

#### الگوی ۲: پامپ و دامپ (Pump and Dump)
- رشد قیمت > ۳٪
- نسبت خرید حقیقی > ۶۰٪
- تعداد معاملات > ۳۰۰
- **توصیه:** ریسک بالا برای ورود

**سطح شدت:**
| شرط | شدت |
|-----|-----|
| اطمینان ≥ ۷۰٪ | بالا (قرمز) |
| اطمینان ≥ ۵۰٪ | متوسط (نارنجی) |
| اطمینان < ۵۰٪ | پایین (زرد) |

---

### ۶. معاملات بلوکی 📦

**کلاس:** `BlockTradeDetector`  
**API:** `GET /api/v1/market-insights/block-trades?limit=30`  
**API:** `GET /api/v1/market-insights/block-trades/summary`

شناسایی معاملات غیرعادی بزرگ با Z-Score > ۳:

| معیار | توضیح |
|-------|-------|
| **Z-Score** | انحراف حجم از میانگین بر حسب انحراف معیار |
| **جهت** | `accumulation` (انباشت) یا `distribution` (توزیع) |
| **اعتماد** | min(1.0, Z-Score / 5.0) |

**روش تعیین جهت:**
- قیمت > ۱.۰۱x میانگین → توزیع (فروش در سقف)
- قیمت < ۰.۹۹x میانگین → انباشت (خرید در کف)

**خروجی خلاصه:**
```json
{
  "total": 28,
  "accumulation": 18,
  "distribution": 10,
  "top_accumulation": [...],
  "top_distribution": [...]
}
```

---

## ماژول‌های اضافی API

### بازده واقعی 📊

**کلاس:** `RealReturnCalculator`  
**API:** `GET /api/v1/market-insights/real-return/{symbol}?period_days=30`  
**API:** `GET /api/v1/market-insights/real-return`

محاسبه بازده واقعی (تعدیل‌شده با تورم و نرخ ارز):

```
بازده واقعی = بازده اسمی - تعدیل تورم - تعدیل نرخ ارز
```

**منابع داده:**
- نرخ تورم: `macro_indicators`
- نرخ ارز: `brsapi_gold_currency_pro_prices`
- قیمت سهام: `brsapi_historical_daily`

### سطوح تاریخی 📈

**کلاس:** `HistoricalLevelAnalyzer`  
**API:** `GET /api/v1/market-insights/levels/{symbol}`

تحلیل سطوح حمایت و مقاومت تاریخی با اطلاعات:
- نزدیک‌ترین حمایت و مقاومت
- فاصله درصدی تا سطوح
- منطقه ازدحام قیمت

### پیش‌بینی شکاف قیمتی 🔮

**کلاس:** `GapPredictor`  
**API:** `GET /api/v1/market-insights/gap-prediction?limit=30`

پیش‌بینی شکاف قیمتی بازگشایی فردا بر اساس:
- تغییرات قیمت جهانی (طلا، نفت)
- تغییرات نرخ ارز
- وضعیت صف پایان روز
- احساسات اخبار

---

## API Endpoints

| متد | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/api/v1/market-insights/fear-greed` | شاخص ترس و طمع |
| `GET` | `/api/v1/market-insights/market-health` | شاخص سلامت بازار |
| `GET` | `/api/v1/market-insights/fake-queues?limit=50` | لیست صف‌های کاذب |
| `GET` | `/api/v1/market-insights/fake-queues/{symbol}` | صف کاذب یک نماد |
| `GET` | `/api/v1/market-insights/accumulation?limit=50` | انباشت پنهان |
| `GET` | `/api/v1/market-insights/manipulation?limit=50` | دستکاری قیمت |
| `GET` | `/api/v1/market-insights/manipulation/{symbol}` | دستکاری یک نماد |
| `GET` | `/api/v1/market-insights/block-trades?limit=30` | معاملات بلوکی |
| `GET` | `/api/v1/market-insights/block-trades/summary` | خلاصه بلوکی |
| `GET` | `/api/v1/market-insights/real-return/{symbol}` | بازده واقعی نماد |
| `GET` | `/api/v1/market-insights/real-return` | بازده واقعی بازار |
| `GET` | `/api/v1/market-insights/levels/{symbol}` | سطوح حمایت/مقاومت |
| `GET` | `/api/v1/market-insights/gap-prediction?limit=30` | پیش‌بینی شکاف |

---

## مدل داده

### ساختار فرانت‌اند

```typescript
interface FakeQueueItem {
  symbol: string;        // نماد
  name: string;          // نام شرکت
  fake_buy_queue: boolean;  // صف خرید کاذب
  fake_sell_queue: boolean; // صف فروش کاذب
  confidence: number;    // اطمینان ۰-۱
  reason: string;        // دلیل شناسایی
}

interface AccumulationItem {
  symbol: string;
  name: string;
  score: number;         // امتیاز ۰-۱۰۰
  volume_ratio: number;  // نسبت حجم به میانگین
  price_change_pct: number;
  net_real_flow: number; // جریان خالص پول
  reason: string;
}

interface ManipulationItem {
  symbol: string;
  name: string;
  pattern: string;       // pump_and_dump | range_trap
  confidence: number;
  severity: string;      // low | medium | high
  reason: string;
  recommendation: string;
}

interface BlockTradeItem {
  symbol: string;
  name: string;
  trade_time: string;
  price: number;
  volume: number;
  value: number;
  direction: string;     // accumulation | distribution | neutral
  z_score: number;
}
```

---

## فناوری‌ها

| لایه | فناوری |
|------|--------|
| **فرانت‌اند** | React 19, TanStack Query, Tailwind CSS |
| **بک‌اند** | FastAPI, SQLAlchemy async, PostgreSQL |
| **پردازش داده** | Python 3.11+, NumPy, Pandas |
| **تحلیل آماری** | Z-Score, ATR, Moving Average, Percentile |

---

## نکات اجرایی

1. **بروزرسانی خودکار:** داده‌های ترس/طمع و سلامت بازار هر ۵ دقیقه بروزرسانی می‌شوند (`refetchInterval: 300000`)
2. **داده‌های صف/انباشت/دستکاری:** هر ۶۰ ثانیه بروزرسانی (`refetchInterval: 60000`)
3. **پیش‌نیاز:** جداول `brsapi_symbol_snapshots` و `brsapi_historical_daily` باید داده داشته باشند
4. **عملکرد:** کوئری‌ها از `DISTINCT ON` و `ORDER BY trade_value DESC` برای سرعت استفاده می‌کنند
