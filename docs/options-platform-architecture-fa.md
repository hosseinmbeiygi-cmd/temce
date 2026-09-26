# معماری کامل پلتفرم معاملات آپشن بورس تهران

## ۱. هدف و دامنه سیستم

پلتفرمی end-to-end برای معامله‌گری اختیار معامله (Option) در بورس اوراق بهادار تهران (TSE) و فرابورس (IFB)، شامل هشت زیرسیستم اصلی:

1. لایه دریافت و پردازش داده (Data Layer)
2. مدل داده و پایگاه‌داده (Data Model)
3. موتور قیمت‌گذاری و یونانی‌ها (Pricing Engine)
4. موتور استراتژی (Strategy Engine)
5. موتور بک‌تست (Backtesting Engine)
6. موتور پیش‌بینی (Forecasting / ML)
7. مدیریت سفارش و ریسک (OMS + Risk)
8. داشبورد، موبایل، زیرساخت و امنیت

---

## ۲. نکات خاص بازار آپشن تهران (باید در طراحی لحاظ شود)

- قراردادها عمدتاً **اروپایی** با تسویه که می‌تواند نقدی یا فیزیکی (تحویل سهم پایه) باشد؛ نوع تسویه باید از اطلاعیه هر نماد استخراج شود، نه فرض ثابت.
- سررسید **ماهانه** با تاریخ متغیر (باید از فایل نمادهای بورس/فرابورس هر روز pull شود، نه هاردکد).
- **وجه تضمین (مارجین)** برای موقعیت‌های تعهدی (فروش Call/Put) با فرمول مصوب سازمان بورس محاسبه و **روزانه (Initial Margin)** و در صورت حرکت شدید بازار **درون‌روز (Variation Margin / Margin Call)** به‌روز می‌شود.
- نماد آپشن ساختار دارد: `نام پایه + نوع (طلب=Call / تعهد=Put) + قیمت اعمال + تاریخ سررسید` — پارسر باید هم نگارش فارسی هم لاتین را پشتیبانی کند.
- نقدشوندگی پایین‌تر از بازارهای توسعه‌یافته → مدل قیمت‌گذاری باید **اسپرد خرید/فروش و عمق سفارش محدود** را لحاظ کند، نه فقط فرمول تئوریک؛ برای نمادهای کم‌معامله باید fallback به نوسان تاریخی وجود داشته باشد.
- داده از **TSETMC**، **فرابورس (IFB)**، **کدال** (برای تعدیلات و افزایش سرمایه) و APIهای کارگزاری‌ها (که رسمی/مستند نیستند) قابل استخراج است → لایه adapter مجزا با قابلیت تحمل خطا لازم است.
- **الزامات رگولاتوری**: معاملات کاملاً خودکار بدون تأیید انسانی محدودیت دارد؛ سامانه‌های معاملات الگوریتمی نیازمند مجوز مشخص از سازمان بورس هستند. فاز اول باید **Decision Support** باشد (تولید سیگنال، اجرای دستی توسط کاربر).

---

## ۲.۵ بررسی پلتفرم‌های موجود بازار ایران و درس‌های طراحی

پیش از طراحی نهایی، پلتفرم‌ها و ابزارهای فعلی بازار آپشن ایران بررسی شدند. (نکته: نامی دقیقاً با عنوان «ره‌آورد» به‌عنوان پلتفرم مستقل و شناخته‌شده آپشن در جست‌وجوها تأیید نشد؛ اگر نام دقیق‌تر یا لینک دارید می‌توانم دوباره بررسی کنم.)

| پلتفرم | نوع | نقاط قوت قابل الگوبرداری | محدودیت‌ها |
|---|---|---|---|
| **صحرا (Sahra Pro)** | پنل معاملاتی چند-کارگزاری (صنعت‌ومعدن، حافظ، فیروزه‌آسیا، تجارت و...) | رابط اختصاصی مشتقه، ابزارهای مدیریت پویای موقعیت آپشن، طراحی برای حرفه‌ای‌ها | بدون بک‌تست، بدون پیش‌بینی، وابسته به کارگزاری |
| **آنلاین‌پلاس** | پنل معاملاتی جایگزین صحرا | سادگی ثبت سفارش مستقیم روی زنجیره | امکانات تحلیلی محدود |
| **ایزی‌تریدر (کارگزاری مفید)** | پنل یکپارچه سهام+آپشن | صفحه اختصاصی آپشن (زنجیره، موقعیت‌های من، «بیشترین‌ها»، «نقشه بازار آپشن»)، ماژول تازه «استراتژی‌های معاملاتی» | استراتژی‌ساز ابتدایی، بدون بک‌تست تاریخی واقعی، وابسته به یک کارگزاری |
| **آپشن‌باز (optionbaaz.ir)** | ابزار مستقل تحلیلی (broker-agnostic) | دیده‌بان و زنجیره مستقل، استراتژی‌ساز، محتوای آموزشی/تحلیلی، پوشش بورس+فرابورس+بورس کالا | بدون اجرای سفارش مستقیم (صرفاً تحلیلی)، بدون ML |
| **کاریزما/مفید و سایرین** | کارگزاری با پیش‌نیاز کد آپشن | UX ساده‌تر برای دریافت کد در برخی کارگزاری‌ها | تنوع پیش‌شرط‌ها (حداقل پرتفوی، آزمون و...) بین کارگزاری‌ها |

**جمع‌بندی الگوبرداری:**
1. از صحرا/آنلاین‌پلاس → ثبت سفارش سریع مستقیم از سطر زنجیره آپشن.
2. از ایزی‌تریدر → ساختار سه‌تبی «زنجیره + موقعیت‌های من + نقشه حرارتی» + بخش «بیشترین‌ها».
3. از آپشن‌باز → طراحی broker-agnostic، پوشش چندبازاره، محتوای آموزشی کنار ابزار.
4. **مزیت رقابتی پلتفرم پیشنهادی**: هیچ‌کدام از موارد بالا بک‌تست تاریخی رویدادمحور، موتور پیش‌بینی ML، یا Portfolio Greeks تجمیعی خودکار ندارند — این سه، هسته تمایز طراحی ما هستند (بخش‌های ۷، ۸ و ۹).

---

## ۳. معماری کلی (لایه‌ای / Microservice-ready)

```
┌─────────────────────────────────────────────────────────────┐
│              UI: وب (Next.js) + موبایل (React Native)         │
└───────────────────────────┬───────────────────────────────────┘
                             │ REST + WebSocket (قیمت لحظه‌ای)
┌───────────────────────────┴───────────────────────────────────┐
│               API Gateway (FastAPI) + Auth (JWT/OAuth2)        │
└───┬───────────┬────────────┬────────────┬────────────┬────────┘
    │           │            │            │            │
┌───▼───┐  ┌────▼────┐  ┌────▼─────┐ ┌────▼─────┐ ┌────▼─────┐
│ Data  │  │ Pricing │  │ Strategy │ │Backtest  │ │Forecast  │
│Ingest │  │ Engine  │  │ Engine   │ │Engine    │ │(ML)      │
└───┬───┘  └────┬────┘  └────┬─────┘ └────┬─────┘ └────┬─────┘
    │           │            │            │            │
    └───────────┴─────┬──────┴────────────┴────────────┘
                       │
         ┌─────────────┴─────────────┐
         │  Kafka / RabbitMQ (Event Bus) │
         └─────────────┬─────────────┘
                       │
   ┌───────────────────┼───────────────────┐
┌──▼───────┐   ┌────────▼────────┐   ┌──────▼──────┐
│PostgreSQL │   │  TimescaleDB    │   │    Redis    │
│(نمادها،   │   │ (سری زمانی      │   │(کش/صف/      │
│کاربران،   │   │ قیمت، Greeks)   │   │ Rate Limit) │
│سفارش‌ها)  │   │                 │   │             │
└──────────┘   └─────────────────┘   └─────────────┘
                       │
              ┌────────▼────────┐
              │  OMS + Risk Mgr  │──► اتصال به کارگزاری (API/شبه‌FIX یا حالت نیمه‌خودکار)
              └──────────────────┘
```

### جدول Stack پیشنهادی

| لایه | تکنولوژی | دلیل انتخاب |
|---|---|---|
| Backend سرویس‌های مالی/ML | Python + FastAPI | اکوسیستم قوی محاسبات مالی (NumPy, SciPy, scikit-learn) |
| بخش‌های latency-critical (OMS/Matching) | Go یا Rust (اختیاری فاز ۲) | کارایی و همزمانی بالاتر |
| پایگاه‌داده رابطه‌ای | PostgreSQL | تراکنش‌های ACID برای سفارش و کاربران |
| سری زمانی | TimescaleDB (روی PostgreSQL) | فشرده‌سازی و کوئری سریع روی میلیون‌ها ردیف قیمت |
| کش/صف سریع | Redis | کش زنجیره آپشن، Rate limiting، Pub/Sub |
| پیام‌رسان رویداد | Kafka (یا RabbitMQ برای مقیاس کوچک‌تر) | جریان قیمت لحظه‌ای بین سرویس‌ها |
| فرانت وب | Next.js + TradingView Lightweight Charts | SSR سریع + نمودار حرفه‌ای |
| موبایل | React Native (اشتراک کد با وب تا حد امکان) | توسعه سریع‌تر برای دو پلتفرم |
| ML | scikit-learn, XGBoost, PyTorch (مدل‌های عمیق‌تر فاز بعد) | استاندارد صنعتی |
| Containerization | Docker + Kubernetes (یا Docker Compose برای MVP) | مقیاس‌پذیری و استقرار یکنواخت |
| Monitoring | Prometheus + Grafana، Sentry برای خطاها | پایش سلامت سیستم real-time |
| CI/CD | GitHub Actions / GitLab CI | استقرار خودکار و تست پیوسته |

---

## ۴. مدل داده (Database Schema)

```sql
-- نمادهای پایه
CREATE TABLE underlying_symbols (
    symbol_id       SERIAL PRIMARY KEY,
    ticker          VARCHAR(20) UNIQUE NOT NULL,   -- مثلا فولاد
    market          VARCHAR(10) NOT NULL,          -- TSE / IFB
    sector          VARCHAR(50)
);

-- قراردادهای آپشن
CREATE TABLE option_contracts (
    contract_id     SERIAL PRIMARY KEY,
    symbol_id       INT REFERENCES underlying_symbols(symbol_id),
    option_type     CHAR(4) NOT NULL,              -- CALL / PUT
    strike_price    NUMERIC(18,2) NOT NULL,
    expiry_date     DATE NOT NULL,
    settlement_type VARCHAR(10) NOT NULL,          -- CASH / PHYSICAL
    contract_size   INT DEFAULT 1000,
    ticker          VARCHAR(40) UNIQUE NOT NULL    -- نماد کامل آپشن
);

-- قیمت لحظه‌ای/تاریخی سهم پایه (Hypertable در TimescaleDB)
CREATE TABLE underlying_prices (
    symbol_id   INT REFERENCES underlying_symbols(symbol_id),
    ts          TIMESTAMPTZ NOT NULL,
    open        NUMERIC(18,2), high NUMERIC(18,2),
    low         NUMERIC(18,2), close NUMERIC(18,2),
    volume      BIGINT,
    PRIMARY KEY (symbol_id, ts)
);

-- قیمت و یونانی‌های آپشن (Hypertable)
CREATE TABLE option_market_data (
    contract_id   INT REFERENCES option_contracts(contract_id),
    ts            TIMESTAMPTZ NOT NULL,
    bid           NUMERIC(18,2), ask NUMERIC(18,2), last NUMERIC(18,2),
    volume        BIGINT, open_interest BIGINT,
    implied_vol   NUMERIC(8,5),
    delta NUMERIC(8,5), gamma NUMERIC(8,5), vega NUMERIC(8,5),
    theta NUMERIC(8,5), rho NUMERIC(8,5),
    PRIMARY KEY (contract_id, ts)
);

-- کاربران و پرتفوی
CREATE TABLE users (user_id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE, ...);
CREATE TABLE positions (
    position_id  SERIAL PRIMARY KEY,
    user_id      INT REFERENCES users(user_id),
    contract_id  INT REFERENCES option_contracts(contract_id),
    quantity     INT NOT NULL,               -- منفی = فروش/تعهد
    avg_price    NUMERIC(18,2),
    opened_at    TIMESTAMPTZ DEFAULT now()
);

-- سفارش‌ها
CREATE TABLE orders (
    order_id     SERIAL PRIMARY KEY,
    user_id      INT REFERENCES users(user_id),
    contract_id  INT REFERENCES option_contracts(contract_id),
    side         VARCHAR(4),                 -- BUY/SELL
    order_type   VARCHAR(10),                -- LIMIT/MARKET
    quantity     INT, price NUMERIC(18,2),
    status       VARCHAR(15),                -- PENDING/FILLED/PARTIAL/CANCELLED
    strategy_id  INT NULL,                   -- در صورت تعلق به یک استراتژی چندپایه
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- استراتژی‌های چندپایه (Multi-leg)
CREATE TABLE strategies (
    strategy_id   SERIAL PRIMARY KEY,
    user_id       INT REFERENCES users(user_id),
    strategy_type VARCHAR(30),               -- COVERED_CALL / IRON_CONDOR / ...
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- نتایج بک‌تست
CREATE TABLE backtest_runs (
    run_id        SERIAL PRIMARY KEY,
    user_id       INT REFERENCES users(user_id),
    strategy_type VARCHAR(30),
    params        JSONB,
    start_date    DATE, end_date DATE,
    metrics       JSONB,                     -- شارپ، مکس دراودان، وین‌ریت و...
    equity_curve  JSONB,
    created_at    TIMESTAMPTZ DEFAULT now()
);
```

---

## ۵. لایه دریافت داده (Data Ingestion)

### ۵.۱ منابع و Adapterها
- **TSETMC Adapter**: پول دوره‌ای (هر ۱-۵ ثانیه در ساعات معاملاتی) endpointهای غیررسمی + مکانیزم retry/backoff.
- **IFB Adapter**: مشابه برای فرابورس.
- **Kodal (کدال) Adapter**: افزایش سرمایه، سود نقدی و اطلاعیه‌هایی که روی تعدیل قیمت اعمال قرارداد آپشن اثر می‌گذارند.
- **Broker API Adapter**: در صورت وجود دسترسی API از کارگزاری (برای اجرای سفارش واقعی).

### ۵.۲ اجزای پردازشی
- `Fetcher Service`: زمان‌بند pull + مدیریت نرخ درخواست برای جلوگیری از IP-block.
- `Normalizer`: تبدیل داده خام هر منبع به schema یکسان بالا.
- `Symbol Parser`: استخراج regex-based از نماد آپشن فارسی/لاتین، مثال ساختار:
```python
import re
PATTERN = re.compile(
    r"^(?P<base>[آ-ی\w]+)-?(?P<type>ط|ت|C|P)(?P<strike>\d+)-?(?P<expiry>\d{6,8})$"
)
def parse_option_symbol(ticker: str) -> dict:
    m = PATTERN.match(ticker)
    if not m:
        raise ValueError(f"نماد نامعتبر: {ticker}")
    return {
        "base": m.group("base"),
        "type": "CALL" if m.group("type") in ("ط", "C") else "PUT",
        "strike": float(m.group("strike")),
        "expiry": m.group("expiry"),
    }
```
- `Corporate Actions Handler`: به‌روزرسانی خودکار قیمت اعمال قراردادهای باز پس از افزایش سرمایه، طبق دستورالعمل بورس.
- `Data Quality Monitor`: تشخیص gap، قیمت پرت (outlier)، و توقف نماد؛ هشدار خودکار به تیم فنی.

---

## ۶. موتور قیمت‌گذاری (Pricing Engine)

### ۶.۱ فرمول Black-Scholes (پایه اروپایی، بدون سود نقدی)

```
Call = S·N(d1) − K·e^(−rT)·N(d2)
Put  = K·e^(−rT)·N(−d2) − S·N(−d1)

d1 = [ln(S/K) + (r + σ²/2)·T] / (σ·√T)
d2 = d1 − σ·√T
```

### ۶.۲ یونانی‌ها (فرمول‌های بسته)

| یونانی | فرمول (Call) |
|---|---|
| Delta | N(d1) |
| Gamma | φ(d1) / (S·σ·√T) |
| Vega | S·φ(d1)·√T |
| Theta | −(S·φ(d1)·σ)/(2√T) − r·K·e^(−rT)·N(d2) |
| Rho | K·T·e^(−rT)·N(d2) |

(برای Put، فرمول‌ها با علامت متناظر طبق تئوری Put-Call Parity محاسبه می‌شوند.)

### ۶.۳ پیاده‌سازی نمونه

```python
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

class OptionPricer:
    def _d1_d2(self, S, K, T, r, sigma):
        d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return d1, d2

    def black_scholes(self, S, K, T, r, sigma, option_type="call"):
        d1, d2 = self._d1_d2(S, K, T, r, sigma)
        if option_type == "call":
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    def implied_volatility(self, market_price, S, K, T, r, option_type="call"):
        f = lambda sigma: self.black_scholes(S, K, T, r, sigma, option_type) - market_price
        try:
            return brentq(f, 1e-4, 5.0)
        except ValueError:
            return None   # قیمت خارج از بازه معتبر آربیتراژ

    def greeks(self, S, K, T, r, sigma, option_type="call"):
        d1, d2 = self._d1_d2(S, K, T, r, sigma)
        sign = 1 if option_type == "call" else -1
        return {
            "delta": sign * norm.cdf(sign * d1),
            "gamma": norm.pdf(d1) / (S * sigma * np.sqrt(T)),
            "vega":  S * norm.pdf(d1) * np.sqrt(T) / 100,
            "theta": (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
                      - sign * r * K * np.exp(-r * T) * norm.cdf(sign * d2)) / 365,
            "rho":   sign * K * T * np.exp(-r * T) * norm.cdf(sign * d2) / 100,
        }
```

### ۶.۴ مدل Binomial (برای احتمال اعمال زودهنگام یا تعدیل سود نقدی)
از روش **Cox-Ross-Rubinstein** با N≈200 گام برای دقت کافی؛ در صورت وجود سود نقدی سهم پایه، تعدیل درخت با کسر سود در تاریخ مربوطه.

### ۶.۵ ملاحظات بومی (Market Microstructure)
- Fair Value = میانگین وزنی (mid) بهترین صف خرید/فروش، نه صرفاً آخرین معامله.
- برای نمادهای با حجم صفر یا کم، fallback به **نوسان تاریخی (Historical Volatility)** جای IV.
- محاسبه **IV Rank / IV Percentile** (موقعیت IV فعلی نسبت به بازه ۵۲ هفته) برای شناسایی آپشن گران/ارزان.

---

## ۷. موتور استراتژی (Strategy Engine)

### ۷.۱ کتابخانه استراتژی‌ها با فرمول Payoff

| استراتژی | ساختار | حداکثر سود | حداکثر ضرر | نقطه سر‌به‌سر |
|---|---|---|---|---|
| Covered Call | Long سهم + Short Call | K − Cost + Premium | Cost − Premium (تا صفر شدن سهم) | Cost − Premium |
| Protective Put | Long سهم + Long Put | نامحدود | Cost − K + Premium | Cost + Premium |
| Long Straddle | Long Call + Long Put (هم‌قیمت اعمال) | نامحدود | مجموع پرمیوم پرداختی | K ± مجموع پرمیوم |
| Bull Call Spread | Long Call(K1) + Short Call(K2>K1) | (K2−K1) − Net Debit | Net Debit | K1 + Net Debit |
| Bear Put Spread | Long Put(K1) + Short Put(K2<K1) | (K1−K2) − Net Debit | Net Debit | K1 − Net Debit |
| Iron Condor | Short Put(K1) + Long Put(K2<K1) + Short Call(K3) + Long Call(K4>K3) | Net Credit | (K1−K2) یا (K4−K3) − Net Credit | دو نقطه (بالا/پایین) |
| Naked Call/Put | تک‌پایه بدون پوشش | محدود (Put) / نامحدود ریسک (Call) | نامحدود (Call) / K − Premium (Put) | K ± Premium |

### ۷.۲ معماری موتور
```python
class StrategyLeg:
    def __init__(self, option_type, position, strike, premium, quantity=1):
        self.option_type = option_type   # CALL / PUT / STOCK
        self.position = position         # LONG / SHORT
        self.strike = strike
        self.premium = premium
        self.quantity = quantity

class StrategyBuilder:
    def __init__(self, legs: list[StrategyLeg]):
        self.legs = legs

    def payoff(self, spot_prices: np.ndarray) -> np.ndarray:
        total = np.zeros_like(spot_prices, dtype=float)
        for leg in self.legs:
            if leg.option_type == "CALL":
                intrinsic = np.maximum(spot_prices - leg.strike, 0)
            elif leg.option_type == "PUT":
                intrinsic = np.maximum(leg.strike - spot_prices, 0)
            else:
                intrinsic = spot_prices
            sign = 1 if leg.position == "LONG" else -1
            total += sign * leg.quantity * (intrinsic - leg.premium)
        return total

    def breakeven_points(self, spot_range) -> list[float]:
        payoffs = self.payoff(spot_range)
        signs = np.sign(payoffs)
        crossings = np.where(np.diff(signs) != 0)[0]
        return [spot_range[i] for i in crossings]
```

- `SignalGenerator`: تولید سیگنال بر اساس IV Rank، Skew، روند سهم پایه، فاصله تا سررسید.
- `PositionSizer`: تعیین حجم با **Fixed Fractional** (درصد ثابت سرمایه در ریسک) یا **Kelly محدودشده** (حداکثر تا ۲۵٪ Kelly کامل برای کاهش ریسک).
- `RuleEngine`: قوانین ورود/خروج به‌صورت DSL قابل تعریف کاربر (JSON schema)، مثال:
```json
{
  "entry": {"iv_rank": {"gt": 70}, "days_to_expiry": {"between": [20, 45]}},
  "exit":  {"profit_target_pct": 50, "stop_loss_pct": 100, "days_to_expiry": {"lt": 5}}
}
```

---

## ۸. موتور بک‌تست (Backtesting Engine)

### ۸.۱ اصول طراحی
- **Event-Driven** (نه vectorized ساده) برای شبیه‌سازی واقعی ترتیب رویدادها (تیک به تیک یا کندل به کندل).
- شبیه‌سازی **کارمزد کارگزاری + کارمزد سازمان بورس + اسپرد + Slippage** به‌طور جداگانه قابل‌تنظیم.
- مدل‌سازی **محدودیت نقدشوندگی**: رد یا اجرای جزئی سفارش اگر حجم موجود در بازار کمتر از حجم سفارش باشد.
- **Walk-Forward Testing**: تقسیم داده به پنجره‌های آموزش/آزمون متوالی برای جلوگیری از overfitting؛ به‌علاوه **Out-of-Sample validation** روی بازه کاملاً جدا.

### ۸.۲ فرمول‌های متریک خروجی

```
Sharpe Ratio   = (میانگین بازده − نرخ بدون ریسک) / انحراف‌معیار بازده × √۲۵۲
Sortino Ratio  = (میانگین بازده − نرخ بدون ریسک) / انحراف‌معیار بازده‌های منفی × √۲۵۲
Max Drawdown   = max[(Peak − Trough) / Peak]  روی منحنی سرمایه
Win Rate       = تعداد معاملات سودده / کل معاملات
Profit Factor  = مجموع سود معاملات برنده / |مجموع ضرر معاملات بازنده|
```

### ۸.۳ معماری
```
BacktestEngine
 ├── DataReplay          (پخش تاریخی tick/candle با همان توالی زمانی واقعی)
 ├── StrategyRunner      (اجرای همان StrategyEngine روی داده گذشته، بدون look-ahead bias)
 ├── PortfolioSimulator  (موجودی، مارجین، PnL، margin call شبیه‌سازی‌شده)
 └── ReportGenerator     (متریک‌ها + equity curve + تحلیل حساسیت به IV/نرخ بهره)
```

**نکته حیاتی ضد Look-Ahead Bias**: در هر گام زمانی بک‌تست، موتور فقط به داده‌ای دسترسی دارد که تا همان لحظه در بازار واقعی منتشر شده بود (مثلاً IV محاسبه‌شده باید از قیمت‌های *قبل* از آن لحظه باشد).

---

## ۹. موتور پیش‌بینی (Forecasting)

### ۹.۱ فیچرهای ورودی مدل
- تکنیکال: RSI، MACD، Bollinger Bands، حجم نسبی، ATR
- ساختار آپشن: IV Rank، Put/Call Ratio، Skew (تفاوت IV بین Call و Put هم‌فاصله)، Open Interest تغییرات
- بازار کلان: بازده شاخص کل، نرخ ارز (در صورت مرتبط بودن صنعت)، نرخ بهره بین‌بانکی

### ۹.۲ مدل‌ها
- **پیش‌بینی نوسان آتی**: GARCH(1,1) به‌عنوان baseline + مقایسه با IV بازار برای شناسایی آپشن گران/ارزان.
- **پیش‌بینی جهت سهم پایه**: XGBoost/LightGBM با فیچرهای بالا؛ برای سری‌های پیچیده‌تر، LSTM/Transformer در فاز توسعه‌یافته‌تر.
- **Ensemble**: ترکیب وزنی چند مدل با وزن‌دهی پویا بر اساس عملکرد rolling اخیر (نه وزن ثابت).

### ۹.۳ Pipeline
```
داده خام → Feature Engineering → Train/Validation Split (Walk-Forward) →
مدل‌ها (GARCH + XGBoost + Ensemble) → کالیبراسیون احتمال → خروجی به SignalGenerator
```

### ۹.۴ هشدار مهم
خروجی مدل همیشه به‌صورت **احتمال/بازه اطمینان** ارائه شود، نه سیگنال قطعی. این خروجی فقط یکی از ورودی‌های `SignalGenerator` است، نه تصمیم خودکار نهایی — به‌ویژه با توجه به محدودیت رگولاتوری معاملات کاملاً خودکار.

---

## ۱۰. مدیریت ریسک (Risk Management)

- **Portfolio Greeks** لحظه‌ای (تجمیع Delta/Gamma/Vega/Theta روی کل پورتفوی) + هشدار در صورت عبور از حد مجاز تعریف‌شده کاربر.
- **Margin Call Simulator**: پیش‌بینی نیاز به وجه تضمین اضافه *قبل* از وقوع، بر اساس فرمول رسمی سازمان بورس.
- **Stress Testing**: شبیه‌سازی حرکت ناگهانی ±۵٪/±۱۰٪/±۲۰٪ سهم پایه و اثر آن روی کل پورتفوی (شامل نوسان IV هم‌زمان – Vega shock).
- **سقف ضرر روزانه (Circuit Breaker داخلی)**: مستقل از نوسانگیر رسمی بورس، برای توقف خودکار پیشنهاد معاملات جدید پس از رسیدن به حد ضرر تعیین‌شده کاربر.
- **Concentration Limit**: هشدار وقتی بیش از درصد مشخصی از پرتفوی روی یک سهم پایه یا یک سررسید متمرکز شده.

---

## ۱۱. مدیریت سفارش (OMS)

- `OrderRouter`: مسیر اول = **Decision Support** (تولید سفارش پیشنهادی برای تأیید دستی کاربر)؛ مسیر دوم (فاز بعد، منوط به مجوز) = اتصال مستقیم به API کارگزاری.
- `ExecutionTracker`: پیگیری وضعیت سفارش (باز/پر شده جزئی یا کامل/لغو) با Webhook یا polling.
- `Multi-leg Order Handler`: ارسال هم‌زمان چند پایه یک استراتژی با کنترل all-or-none در صورت نیاز.

### نمونه API Endpointها (REST)
```
GET  /api/v1/options/chain?symbol=فولاد&expiry=YYYY-MM-DD
GET  /api/v1/options/{contract_id}/greeks
POST /api/v1/strategies              # ساخت استراتژی چندپایه
POST /api/v1/backtest/run            # اجرای بک‌تست
GET  /api/v1/backtest/{run_id}       # نتیجه بک‌تست
GET  /api/v1/portfolio/greeks        # Greeks تجمیعی پورتفوی
POST /api/v1/orders                  # ثبت سفارش پیشنهادی
WS   /ws/v1/prices                   # جریان قیمت لحظه‌ای
```

---

## ۱۲. امنیت و زیرساخت

- **احراز هویت**: JWT + Refresh Token، پشتیبانی از 2FA (الزامی برای عملیات مالی).
- **رمزنگاری**: TLS 1.3 برای انتقال، رمزنگاری at-rest برای اطلاعات حساس (کد بورسی، اطلاعات کاربری) در دیتابیس.
- **Rate Limiting** روی API Gateway برای جلوگیری از سوءاستفاده و فشار به منابع upstream (TSETMC و...).
- **Audit Log**: ثبت تمام تغییرات پرتفوی، سفارش، و دسترسی‌های حساس برای انطباق رگولاتوری.
- **استقرار**: Docker Compose برای MVP → مهاجرت به Kubernetes با auto-scaling برای مقیاس تولید؛ محیط‌های جدا برای dev/staging/production.
- **Backup & DR**: پشتیبان‌گیری روزانه از PostgreSQL + point-in-time recovery برای TimescaleDB.
- **Monitoring**: Prometheus/Grafana برای متریک‌های سیستمی، Sentry برای ردیابی خطا، Alertmanager برای هشدار قطعی/کندی سرویس.

---

## ۱۳. داشبورد (وب)

ساختار تب‌بندی، ترکیبی از بهترین الگوهای موجود در بازار (ایزی‌تریدر، آپشن‌باز) به‌علاوه قابلیت‌های جدید:

- **زنجیره آپشن (Option Chain)**: زنجیره کامل با IV، Greeks، حجم، OI به تفکیک سررسید + ثبت سفارش مستقیم روی سطر (الگو از صحرا/آنلاین‌پلاس).
- **موقعیت‌های من**: موقعیت‌های باز، PnL لحظه‌ای، Greeks تجمیعی.
- **بیشترین‌ها و نقشه بازار**: پرمعامله‌ترین قراردادها + نقشه حرارتی نوسان/حجم (الگو از ایزی‌تریدر).
- **Strategy Builder**: کشیدن‌ورهانداختن Legها با نمودار Payoff زنده و الگوهای آماده.
- **Backtest Lab**: تنظیم پارامتر و اجرای بک‌تست با نمودار equity curve تعاملی — *قابلیت غایب در پلتفرم‌های داخلی موجود*.
- **Forecast Panel**: پیش‌بینی + بازه اطمینان + عملکرد تاریخی مدل — *قابلیت غایب در پلتفرم‌های داخلی موجود*.
- **آموزش/تحلیل**: محتوای آموزشی کنار ابزار (الگو از آپشن‌باز)، با تأکید ویژه بر ریسک نامحدود فروش تعهدی بدون پوشش (Naked Short).

## ۱۳.۵ اپلیکیشن موبایل
- نسخه سبک‌شده از داشبورد با اولویت: **زنجیره آپشن + موقعیت‌های من + هشدارهای ریسک (Push Notification)**.
- هشدار لحظه‌ای برای: نزدیک شدن به margin call، رسیدن به سقف ضرر تعیین‌شده، نزدیکی به سررسید موقعیت باز.
- Strategy Builder و Backtest Lab در فاز اول موبایل حذف می‌شوند (نیازمند صفحه بزرگ‌تر)؛ در نسخه تبلت/دسکتاپ کامل ارائه می‌شوند.

---

## ۱۴. تست و کیفیت (QA)

- **Unit Test** برای فرمول‌های مالی (مقایسه خروجی Black-Scholes با جداول مرجع استاندارد).
- **Backtest Sanity Check**: اجرای استراتژی‌های ساده (مثل Buy & Hold سهم پایه) و مقایسه با بازده واقعی شناخته‌شده برای اطمینان از صحت موتور.
- **Load Testing** روی API Gateway و WebSocket قیمت لحظه‌ای (شبیه‌سازی ساعات پرترافیک بازار).
- **Data Quality Test**: بررسی خودکار gap، outlier و توقف نماد در pipeline دریافت داده.
- **Paper Trading Mode**: قبل از اتصال به کارگزاری واقعی، دوره آزمایشی با پول مجازی برای اعتبارسنجی کل سیستم end-to-end.

---

## ۱۵. نقشه راه پیاده‌سازی (Roadmap)

| فاز | محتوا | مدت تقریبی | نیروی پیشنهادی |
|---|---|---|---|
| ۱ | Data Layer + مدل داده + Pricing Engine | ۳-۴ هفته | ۲ Backend |
| ۲ | Strategy Engine + Payoff Visualizer | ۲-۳ هفته | ۱ Backend + ۱ Frontend |
| ۳ | Backtesting Engine + گزارش‌گیری | ۳-۴ هفته | ۲ Backend |
| ۴ | Risk Manager + Portfolio Greeks | ۲ هفته | ۱ Backend |
| ۵ | Dashboard وب کامل (زنجیره، موقعیت‌ها، Strategy Builder، Backtest Lab) | ۴-۵ هفته | ۲ Frontend |
| ۶ | OMS (Decision Support) + Paper Trading | ۳-۴ هفته | ۲ Backend |
| ۷ | Forecasting/ML (فاز اختیاری، پیچیدگی بالاتر) | ۴+ هفته | ۱-۲ ML Engineer |
| ۸ | موبایل + امنیت/زیرساخت production-grade | ۴-۵ هفته | ۱ Mobile + ۱ DevOps |
| ۹ | اتصال واقعی به کارگزاری (منوط به مجوز رگولاتوری) | متغیر | حقوقی + Backend |

---

## ۱۶. جمع‌بندی

این معماری ماژولار است تا هر بخش (قیمت‌گذاری، استراتژی، بک‌تست، پیش‌بینی) مستقل توسعه و تست شود. بزرگ‌ترین ریسک فنی پروژه **کیفیت و پایداری داده خام بازار آپشن ایران** است، نه پیچیدگی مدل‌های مالی — پیشنهاد می‌شود فاز اول کاملاً روی Data Layer و Pricing Engine متمرکز شود. مزیت رقابتی اصلی نسبت به ابزارهای موجود بازار (صحرا، آنلاین‌پلاس، ایزی‌تریدر، آپشن‌باز) در سه حوزه **بک‌تست رویدادمحور واقعی، موتور پیش‌بینی مبتنی بر ML، و مدیریت ریسک تجمیعی پرتفوی** است که در حال حاضر در هیچ‌کدام از ابزارهای داخلی به‌صورت کامل وجود ندارد.

اگر بخواهید، می‌توانم در ادامه کد اولیه (Skeleton) واقعی هر یک از این ماژول‌ها (مثلاً Pricing Engine یا Backtesting Engine) را به‌صورت پروژه قابل‌اجرا در Python بنویسم.
