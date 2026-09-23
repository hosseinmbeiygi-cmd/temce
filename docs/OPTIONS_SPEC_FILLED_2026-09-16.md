# مشخصات فنی کامل و نهایی — ماژول آپشن بورس (اختیار معامله)
## سند واحد و یکپارچه
### نسخه تکمیل‌شده با گزارش کاوش کدبیس — ۱۶ سپتامبر ۲۰۲۶

> اصل حاکم: **فقط افزودن، هرگز حذف**. جاهای `[پر کن]` را با اطلاعات واقعی پروژه تکمیل کنید.
>
> **راهنمای نسخه تکمیل‌شده:** هر جا متن اصلی دست‌نخورده مانده و پاسخ واقعی کدبیس با نقل‌قول `> **پاسخ کاوش (واقعیت کد):**` در ادامه افزوده شده است. منبع کامل: `docs/CODEBASE_DISCOVERY_OPTIONS_2026-09-16.md` (همین ریپو).
> خلاصه وضعیت فعلی: روتر `apps/api/endpoints/options.py` با ۲۶ روت **وجود دارد ولی در `apps/api/router.py` mount نشده** (در API زنده ۴۰۴)؛ داده واقعی زنجیره در `brsapi_option_snapshots` (۸۴۱٬۹۸۸ ردیف) و `brsapi_ime_options` (۹۴٬۱۸۵ ردیف) پرشده و sync آن هر ۵ دقیقه فعال است؛ مدل‌های `models/option.py` خالی‌اند.

---

## فهرست مطالب
۰) اصل حفظ داده | ۱) نقشه تب‌ها | ۲) مدل داده | ۳) موتور Payoff و Greeks | ۴) بک‌تست استراتژی آپشن | ۵) Roadmap | ۶) سوالات باز | ۷) Wireframe | ۸) اسکیمای API | ۹) نقش‌ها و پنل مدیریت | ۱۰) Backfill | ۱۱) مانیتورینگ کیفیت داده | ۱۲) Edge Case ها | ۱۳) معماری کامپوننت | ۱۴) برنامه تست | ۱۵) واژه‌نامه | ۱۶) خط لوله خودکار | ۱۷) Rollout | ۱۸) چک‌لیست نهایی | ۱۹) خلاصه اجرایی

---

## بخش ۰. اصل حاکم
لیست فعلی قراردادهای آپشن و هر داده ثبت‌شده دست‌نخورده می‌ماند؛ تغییرات فقط افزودنی‌اند.

> **پاسخ کاوش (واقعیت کد):** داده‌های فعلی که باید دست‌نخورده بمانند:
> - `brsapi_option_snapshots` — ۸۴۱٬۹۸۸ ردیف (۲۰۲۶-۰۷-۱۵ تا ۲۰۲۶-۰۹-۱۶)، منبع BrsApi `/Tsetmc/Option.php`، sync هر ۵ دقیقه (`brsapi/jobs/registry.py:144`, `market_hours_only=True`).
> - `brsapi_ime_options` — ۹۴٬۱۸۵ ردیف، منبع BrsApi `/IME/Option.php`.
> - جدول‌های Legacy `options` (۳٬۲۲۵ ردیف) و `commodity_options` (۴۷۶ ردیف) از migration `0001_initial_schema.py` — هیچ نویسنده‌ای در کد فعلی ندارند و باید حفظ شوند.
> - جدول‌های `models/option.py` (`option_contracts`, `option_snapshots`, `option_trades`, `open_interest_history`, `volatility_surface`, `corporate_actions`) **خالی‌اند (۰ ردیف)** و migration Alembic ندارند (با `scripts/fix_schema_gap.py` ساخته شده‌اند).

---

## بخش ۱. نقشه کامل تب‌ها

```
آپشن بورس (منوی اصلی)
├── زنجیره اختیار معامله برای هر دارایی پایه (صفحه فعلی — حفظ و ارتقا)
├── ماشین‌حساب Payoff (سطح پلتفرم، مستقل)
├── استراتژی‌های آماده (Covered Call | Protective Put | Bull/Bear Spread | Straddle)
└── [صفحه اختصاصی هر قرارداد آپشن]
```

> **پاسخ کاوش (واقعیت کد):** UI فعلی آپشن در `frontend/src/app/options/page.tsx` **۷ تب** دارد: `dashboard, strategies, chain, analytics, professional, forecast, learn` (کامپوننت‌ها در `frontend/src/app/options/components/`: `OptionsDashboard.tsx`, `StrategyAnalyzer.tsx`, `LiveChainPanel.tsx`, `AnalyticsPanel.tsx`, `ProfessionalTools.tsx`, `ForecastPanel.tsx`, `LearnPanel.tsx`, `helpers.tsx`, `types.ts`). منوی اصلی: `frontend/src/components/Sidebar.tsx` → `/options` و `frontend/src/lib/nav-config.tsx`.
> - **صفحه اختصاصی هر قرارداد آپشن: یافت نشد** (روتی به شکل `/options/[contract]` یا مشابه در `frontend/src/app` وجود ندارد) — باید از صفر ساخته شود.
> - اتصال داده این تب‌ها فعلاً به روتر mount نشده می‌خورد (همه `GET/POST /api/v1/options/*` → ۴۰۴)؛ تنها تب `forecast` از `GET /api/v1/forecast` داده می‌گیرد (۲۰۰ و کارا، ولی آپشن‌محور نیست).

### زنجیره اختیار معامله (Option Chain) — تب اصلی
```
[انتخاب دارایی پایه] [فیلتر تاریخ سررسید] [فیلتر ITM/ATM/OTM]
[جدول دو طرفه]
  Call ها (چپ) | قیمت اعمال Strike (وسط) | Put ها (راست)
  هر طرف: قیمت لحظه‌ای | حجم | Open Interest | (Greeks در صورت وجود داده: دلتا/گاما/تتا/وگا)
```

> **پاسخ کاوش (واقعیت کد):** فیلتر ITM/ATM/OTM در `frontend/src/app/markets/search/page.tsx` (تابع `calcMoneyness`) سمت کلاینت پیاده شده؛ `LiveChainPanel.tsx` فعلاً فقط فیلترِ دارایی پایه و `limit` دارد. ستون‌های موجود در DB برای زنجیره کامل است (قیمت، حجم، OI، ۵ سطح سفارش، قیمت پایه) ولی **Greeks در هیچ ستونی ذخیره نمی‌شود** (نه در `brsapi_option_snapshots` و نه در `brsapi_ime_options`).

### صفحه اختصاصی هر قرارداد — ۳ تب
```
Tab 1: نمای کلی قرارداد (Strike، سررسید، قیمت، حجم، OI، Greeks)
Tab 2: نمودار Payoff تکی (سود/زیان این یک قرارداد به تنهایی در سررسید)
Tab 3: افزودن به ماشین‌حساب ترکیبی (لینک به ابزار سطح پلتفرم)
```

> **پاسخ کاوش (واقعیت کد):** این صفحه در فرانت **یافت نشد**؛ باید از صفر ساخته شود. داده لازم برای Tab 1 در `brsapi_option_snapshots` موجود است؛ نمودار Payoff تکی نیازمند یک موتور خالص مشترک است (بخش ۳ همین سند).

### ماشین‌حساب Payoff (سطح پلتفرم)
```
[افزودن موقعیت] نوع (Call/Put) | خرید یا فروش | تعداد | قیمت ورود (Premium)
[امکان افزودن چند موقعیت هم‌زمان برای استراتژی ترکیبی]
[انتخاب الگوی آماده] Covered Call | Protective Put | Bull Spread | Bear Spread | Straddle → پر کردن خودکار موقعیت‌ها بر اساس الگو (کاربر می‌تواند بعد ویرایش کند)
[نمودار Payoff نهایی] محور X: قیمت دارایی پایه در سررسید | محور Y: سود/زیان
[نقاط کلیدی] Break-even، حداکثر سود، حداکثر زیان
```

> **پاسخ کاوش (واقعیت کد):** الگوهای آماده فعلی در `services/options_service.py` به‌صورت **hardcoded** (۳۰ استراتژی) هستند، نه جدول `option_strategy_templates`. بخشی از محاسبه payoff در همان سرویس (`profit_at_expiry`) و رسم آن در `PayoffDiagram` (`frontend/src/app/options/components/helpers.tsx`) وجود دارد، ولی:
> - `profit_at_expiry` فقط برای ۹ استراتژی پر می‌شود (covered_call, married_put, long/short straddle, long/short strangle, bull/bear call/put spread) — برای بقیه (پروانه‌ها، کندور، تقویمی، ...) نمودار رسم نمی‌شود.
> - تابع خالص `calculatePayoffAtPrice` مطابق بخش ۳.۱ سند و endpoint سرور برای ماشین‌حساب ترکیبی **یافت نشد**.
> - ذخیره سناریو (`saved_payoff_scenarios`): **یافت نشد**.

---

## بخش ۲. مدل داده بک‌اند

```sql
-- افزودنی؛ جداول موجود دست‌نخورده

CREATE TABLE option_contracts (
    id BIGSERIAL PRIMARY KEY,
    underlying_symbol VARCHAR(20) NOT NULL,
    contract_symbol VARCHAR(50) UNIQUE,
    option_type VARCHAR(4),      -- 'call' | 'put'
    strike_price NUMERIC,
    expiry_date DATE,
    contract_size INT DEFAULT 1
);

CREATE TABLE option_market_data (
    id BIGSERIAL PRIMARY KEY,
    contract_id BIGINT NOT NULL REFERENCES option_contracts(id),
    recorded_at TIMESTAMP,
    last_price NUMERIC,
    volume BIGINT,
    open_interest BIGINT,
    delta NUMERIC, gamma NUMERIC, theta NUMERIC, vega NUMERIC   -- در صورت وجود از منبع، وگرنه NULL تا محاسبه داخلی جایگزین شود
);
CREATE INDEX idx_option_market_contract ON option_market_data(contract_id, recorded_at);

CREATE TABLE option_strategy_templates (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50),          -- 'covered_call' | 'protective_put' | 'bull_spread' | 'bear_spread' | 'straddle'
    description TEXT,
    default_legs JSONB         -- ساختار پیش‌فرض موقعیت‌ها برای پر کردن خودکار
);

CREATE TABLE saved_payoff_scenarios (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    name VARCHAR(100),
    legs JSONB,                -- [{contractId, action: 'buy'|'sell', quantity, entryPrice}]
    created_at TIMESTAMP DEFAULT now()
);
```

> **پاسخ کاوش (واقعیت کد) — وضعیت هر جدول پیشنهادی:**
> | جدول سند | وضعیت واقعی |
> |---|---|
> | `option_contracts` | **جدول هم‌نام از قبل وجود دارد ولی خالی است (۰ ردیف)** — مدل `models/option.py:OptionContractModel` با فیلدهای `symbol unique, underlying_symbol, underlying_isin, option_type, strike_price, expiry_date, contract_size, currency, style, settlement_mode, asset_class, is_active, isin, market`. سند `contract_symbol` می‌خواهد ولی مدل موجود `symbol` دارد (این اختلاف باید در migration افزودنی حل شود). **این جدول migration Alembic ندارد** و با `scripts/fix_schema_gap.py` ساخته شده است. |
> | `option_market_data` | **یافت نشد** (نه جدول، نه مدل، نه migration). داده‌ی معادلِ واقعیِ آن همین حالا در `brsapi_option_snapshots` (۶۰+ ستون، ۸۴۱٬۹۸۸ ردیف) و `brsapi_ime_options` (۹۴٬۱۸۵ ردیف) جمع می‌شود. |
> | `option_strategy_templates` | **یافت نشد** — استراتژی‌ها hardcoded در `services/options_service.py` هستند. |
> | `saved_payoff_scenarios` | **یافت نشد**. |
>
> - ORM موجود `option_snapshots` (با ستون‌های Greeks: `delta, gamma, theta, vega, rho, implied_volatility`) **خالی** است و migration ندارد.
> - نکته فنی: پروژه از SQLAlchemy 2 async + Alembic + PostgreSQL/TimescaleDB استفاده می‌کند؛ SQL خام سند باید در قالب migration افزودنی و مدل ORM معادل پیاده شود. برای سازگاری با واقعیت، یا باید از `brsapi_option_snapshots` به این جدول‌ها mapper نوشت، یا این جدول‌ها را به‌عنوان لایه نرمال‌شده/خلاصه روی داده برساپی ساخت (تصمیم تیم — بخش ۶).

---

## بخش ۳. موتور Payoff و Greeks

### ۳.۱. موتور Payoff (تابع خالص، حیاتی‌ترین بخش)
```typescript
interface OptionLeg {
  type: 'call' | 'put';
  action: 'buy' | 'sell';
  strike: number;
  premium: number;
  quantity: number;
}

function calculatePayoffAtPrice(legs: OptionLeg[], underlyingPriceAtExpiry: number): number {
  return legs.reduce((total, leg) => {
    const intrinsic = leg.type === 'call'
      ? Math.max(underlyingPriceAtExpiry - leg.strike, 0)
      : Math.max(leg.strike - underlyingPriceAtExpiry, 0);
    const legPayoff = (intrinsic - leg.premium) * leg.quantity;
    return total + (leg.action === 'buy' ? legPayoff : -legPayoff);
  }, 0);
}

function findBreakEvenPoints(legs: OptionLeg[], priceRange: [number, number]): number[] { /* جستجوی تغییر علامت payoff */ }
function findMaxProfitLoss(legs: OptionLeg[], priceRange: [number, number]): { maxProfit: number; maxLoss: number } { /* ... */ }
```
**الزام تست:** این تابع باید با حداقل ۵ سناریوی شناخته‌شده (تک Call خرید، تک Put خرید، Straddle، Bull Spread، Covered Call) تست شود و خروجی با مقادیر مرجع مالی شناخته‌شده مطابقت داده شود.

> **پاسخ کاوش (واقعیت کد):**
> - تابع خالص `calculatePayoffAtPrice` با این امضا و توابع کمکی `findBreakEvenPoints` / `findMaxProfitLoss` در کد **یافت نشد**.
> - معادل‌های موجود: `services/options_service.py` (`OptionsStrategyEngine` — ۳۰ استراتژی، کلید `profit_at_expiry` فقط برای ۹ استراتژی)؛ `PayoffDiagram` در `frontend/src/app/options/components/helpers.tsx` (رسم SVG سمت کلاینت)؛ محاسبات payoff در `domain/options/{monte_carlo,tree_pricing,heston_model}.py` (سناریومحور، نه تابع عمومی).
> - **تست مرجع payoff: یافت نشد** (هیچ تستی در `tests/` برای payoff آپشن‌ها وجود ندارد؛ نزدیک‌ترین‌ها تست‌های Greeks/Black-Scholes/IME هستند).

### ۳.۲. محاسبه Greeks (در صورت نبود داده مستقیم از منبع)
```
اگر API منبع، Greeks را مستقیم نمی‌دهد، پیاده‌سازی مدل Black-Scholes برای محاسبه دلتا/گاما/تتا/وگا لازم است.
ورودی‌های مدل: قیمت لحظه‌ای دارایی پایه، Strike، زمان تا سررسید، نرخ بدون ریسک [پر کن: کدام نرخ به‌عنوان نرخ بدون ریسک در نظر گرفته شود؟]، نوسان‌پذیری ضمنی (Implied Volatility — که خودش نیازمند محاسبه معکوس از قیمت بازار قرارداد است، پیچیده‌تر از بقیه بخش‌ها).
این بخش باید در یک فاز جدا و با مشورت کارشناس مالی تیم پیاده‌سازی شود؛ عدم دقت در این محاسبه مستقیماً به کاربر گمراه‌کننده منتقل می‌شود.
```

**✅ جای `[پر کن]` — نرخ بدون ریسک (پاسخ کاوش):**
منبع زنده/بازاری نرخ بدون ریسک در سیستم **وجود ندارد**؛ نرخ فعلی فقط به‌صورت **ثابت در کد** تعریف شده است:
- `services/options_service.py:48` → `RISK_FREE_RATE = 0.15` (کامنت: «15% annual (Iran)») — همین مقدار پیش‌فرض پارامتر `r` در `apps/api/endpoints/options.py` و مقادیر ثابت `0.15` در `services/options_analytics.py` است.
- `src/gold_desk/black76.py:28` → `IRAN_RISK_FREE_RATE = 0.30` (کامنت: «~30% (اخزا)»).
- `services/fund_quant_engine.py:29` → `DEFAULT_ANNUAL_RISK_FREE = 0.23`.
- جدول‌های تاریخی: `backtesting/metrics/risk_free_rate.py:70` (`get_risk_free_rate`/`get_risk_free_rate_for_period`: ۰٫۱۵ محافظه‌کارانه تا ۰٫۳۰ تهاجمی، به‌ازای سال‌های ۱۳۹۵–۱۴۰۴) و `backtesting/metrics/dynamic_risk_free.py` (۰٫۱۸ تا ۰٫۳۲ + تورم).
- ستون `market_macro_indicators.akhzar_ytm` (`models/stock_enterprise.py:228`) برای YTM اخزا ساخته شده ولی **جدول خالی است (۰ ردیف)**؛ فرانت صریحاً نوشته «اوراق خزانه اسلامی (اخزا) … در دیتای فعلی BrsApi در دسترس نیستند» (`frontend/src/app/markets/bonds/page.tsx:153`).
- **تصمیم تیم لازم است:** (الف) پارامتر قابل‌تنظیم config با پیش‌فرض ۰٫۱۵ (هماهنگ با کد فعلی و سریع‌ترین مسیر)؛ (ب) تأمین فید اخزا/بازار بدهی از صفر (فعلاً موجود نیست)؛ (ج) استفاده از جدول‌های تاریخی برای بازه‌های قبل. تا تصمیم، پیشنهاد کاوش: **گزینه (الف)** و مستندسازی صریح نرخ به کاربر.

> **پاسخ کاوش (ادامه) — Greeks:**
> - **منبع، Greeks نمی‌دهد:** پارسر `brsapi/parsers/tsetmc.py:parse_options` هیچ فیلد delta/gamma/theta/vega/IV را map نمی‌کند و جدول `brsapi_option_snapshots` هم این ستون‌ها را ندارد.
> - پیاده‌سازی داخلی **از قبل موجود است** (نیاز به «پیاده‌سازی از صفر» نیست، فقط اتصال/تست): `domain/options/pricing.py` (`black_scholes_call/put`, `black_scholes_price`, `implied_volatility` نیوتن-رافسون)، `domain/options/greeks.py` (dataclass با delta/gamma/theta/vega/rho/speed/charm/vanna/vomma)، `domain/options/higher_order_greeks.py`، `domain/options/commodity_pricing.py` (Black-76 + IV با brentq)، `domain/decision_engine_v5/pricing_tiered.py` (`black76_price`, `black76_greeks`, displaced diffusion)، `src/gold_desk/black76.py`، و `services/options_analytics.py` (Greeks پورتفوی و IV Surface).
> - تست‌های موجود: `tests/unit/options/test_greeks.py`, `test_options_comprehensive.py` (parity/Greeks/IV roundtrip)، `test_ime_pricing_engine.py` (مرجع Hull 6.87)، `test_phase2_ci.py` (parity + Greeks + کیفیت داده) — یعنی بخشی از الزام «مشورت و تست» از قبل پوشش داده شده است.

---

## بخش ۴. جزئیات بک‌تست استراتژی آپشن
```
متفاوت از بک‌تست سایر ماژول‌ها چون آپشن سررسید مشخص دارد (نه یک دارایی پیوسته):
- ورودی: انتخاب یک استراتژی (مثلاً Covered Call ماهانه تکرارشونده) و بازه زمانی
- پردازش: برای هر دوره (مثلاً هر ماه)، شبیه‌سازی باز/بسته شدن موقعیت بر اساس قیمت واقعی تاریخی قرارداد در آن دوره (نیازمند داده تاریخی قیمت آپشن، نه فقط دارایی پایه)
- خروجی مشابه سایر ماژول‌ها: بازده کل، Max Drawdown، + هشدار «داده گذشته» همیشه‌نمایان
- [پر کن: آیا اصلاً داده تاریخی قیمت قراردادهای آپشن گذشته (نه فقط زنجیره فعلی) در دسترس است؟ این پیش‌نیاز این تب است]
```

**✅ جای `[پر کن]` — داده تاریخی (پاسخ کاوش):**
**بله، داده تاریخی وجود دارد — ولی اسنپ‌شاتی است، نه معامله‌به‌معامله:**
- `brsapi_option_snapshots` — **۸۴۱٬۹۸۸ ردیف**، بازه **۲۰۲۶-۰۷-۱۵ تا ۲۰۲۶-۰۹-۱۶** (بررسی زنده DB در ۲۰۲۶-۰۹-۱۶)، **۲٬۴۵۷ نماد** و **۲۵ دارایی پایه**؛ یک ردیف به ازای هر قرارداد در هر سیکل ~۵ دقیقه در ساعات بازار. هر ردیف شامل: `price_first/max/min/last/close`، `trade_count/volume/value`، `open_interest`، خرید/فروش حقیقی/حقوقی، ۵ سطح سفارش خرید و ۵ سطح فروش، `underlying_price_last`، `days_remaining` و `date_end`.
- `brsapi_ime_options` — **۹۴٬۱۸۵ ردیف**، همان بازه (آپشن کالا، جفت call/put هر Strike با قیمت/OI/مارجین و ۳ سطح سفارش).
- **ذخیره نشده:** Greeks، IV و قیمت تسویه نهایی؛ این‌ها باید داخلی محاسبه شوند (بخش ۳.۲).
- جدول‌های `option_snapshots/option_contracts/...` (`models/option.py`) خالی‌اند (۰ ردیف) و migration ندارند.
- **نتیجه برای این تب:** پیش‌نیاز «قیمت تاریخی قرارداد» برای دوره ~۲ ماهه برآورده است و بک‌تست Covered Call ماهانه روی همان بازه قابل اجراست؛ اما:
  - بک‌تست باید بر پایه‌ی **اسنپ‌شات‌ها** (آخرین قیمت/بهترین bid-ask) طراحی شود، نه داده tick-by-tick.
  - برای دوره‌های قدیمی‌تر، Backfill از همان endpoint برساپی (`/Tsetmc/Option.php` فقط زنجیره فعلی است؛ تاریخچه قرارداد باید از `raw_json` ذخیره‌شده یا خرید تاریخچه/Windowing تأمین شود) نیاز است.
  - استراتژی‌های فعلی بک‌تست آپشن در `backtesting/strategies/options/` (۶ فایل) **اسکلت/placeholder** هستند (مثلاً `covered_call_strategy.py` فقط سهم می‌خرد و call نمی‌فروشد) و به داده آپشن وصل نیستند → باید بازنویسی شوند.

---

## بخش ۵. Roadmap پیشنهادی
۱) مدل داده + اتصال منبع زنجیره فعلی  ۲) موتور Payoff + تست کامل (پیش‌نیاز همه‌چیز دیگر)  ۳) UI زنجیره اختیار معامله  ۴) ماشین‌حساب Payoff تکی و ترکیبی + الگوهای آماده  ۵) محاسبه Greeks (در صورت نیاز)  ۶) بک‌تست (نیازمند داده تاریخی آپشن که ممکن است دیرتر آماده شود)

> **پاسخ کاوش (واقعیت کد — چه چیزی از این Roadmap از قبل هست):**
> | گام | وضعیت فعلی |
> |---|---|
> | ۱) مدل داده + اتصال منبع | **نیمه‌آماده** — منبع وصل است (`brsapi_options` هر ۵ دقیقه؛ ۸۴۱٬۹۸۸ ردیف)؛ ولی مدل داده سند (option_market_data) وجود ندارد و روتر API mount نشده. |
> | ۲) موتور Payoff | **انجام نشده** (تابع خالص + تست وجود ندارد) — پرریسک‌ترین بخش، دقیقاً مطابق سند. |
> | ۳) UI زنجیره | **نیمه‌آماده** — ۷ تب فرانت + جدول زنجیره وجود دارد؛ چون API mount نیست، عملاً بی‌داده است. |
> | ۴) ماشین‌حساب + الگوها | **نیمه‌آماده** — ۳۰ استراتژی hardcoded + PayoffDiagram سمت کلاینت؛ الگوی جدولی و ذخیره سناریو وجود ندارد. |
> | ۵) Greeks | **موتور محاسبه آماده و تست‌شده** (`domain/options/`)، فقط اتصال API/UI لازم است. |
> | ۶) بک‌تست | **اسکلت** — ۶ فایل placeholder؛ داده ~۲ ماهه موجود. |

---

## بخش ۶. سوالات باز
- [x] آیا Greeks از منبع داده مستقیم در دسترس است یا باید داخلی محاسبه شود؟
- [x] داده تاریخی قیمت قراردادهای آپشن (نه فقط لحظه‌ای) در دسترس است؟
- [x] نرخ بدون ریسک برای مدل Black-Scholes از کجا گرفته شود؟

**پاسخ‌های کاوش:**
۱. **از منبع در دسترس نیست** → محاسبه داخلی؛ پیاده‌سازی Black-Scholes/Black-76/IV از قبل در `domain/options/`، `domain/decision_engine_v5/pricing_tiered.py` و `src/gold_desk/black76.py` موجود و بخشی تست‌شده است.
۲. **بله** — `brsapi_option_snapshots` (۸۴۱٬۹۸۸ ردیف، ۲۰۲۶-۰۷-۱۵ تا ۲۰۲۶-۰۹-۱۶، هر ~۵ دقیقه ساعات بازار) و `brsapi_ime_options` (۹۴٬۱۸۵ ردیف). Greeks/IV ذخیره نمی‌شوند.
۳. **فید زنده وجود ندارد** — نرخ‌های ثابت ۰٫۱۵/۰٫۲۳/۰٫۳۰ در کد؛ ستون `akhzar_ytm` خالی؛ **تصمیم تیم** (بخش ۳.۲).

---

## بخش ۷. Wireframe

### زنجیره اختیار معامله
```
[هدر] انتخاب دارایی پایه | قیمت لحظه‌ای دارایی پایه | انتخاب سررسید
[جدول دو طرفه، ستون وسط Strike مشترک]
  ردیف‌های ITM (نزدیک قیمت لحظه‌ای) با رنگ پس‌زمینه متفاوت از OTM برای تشخیص سریع بصری
```

> **پاسخ کاوش (واقعیت کد):** داده‌های لازم برای این wireframe در `brsapi_option_snapshots` موجود است (`underlying_price_last`, `strike_price`, `price_last`, `trade_volume`, `open_interest`, `days_remaining`, سطوح bid/ask). محاسبه ITM/ATM/OTM سمت کلاینت نمونه دارد (`frontend/src/app/markets/search/page.tsx` تابع `calcMoneyness`). endpoint زنجیره در `apps/api/endpoints/options.py` روت ۲۴ (`GET /live/chain/{underlying}`) با raw SQL روی همین جدول نوشته شده، ولی mount نشده.

### ماشین‌حساب Payoff
```
[فرم افزودن موقعیت] + [لیست موقعیت‌های اضافه‌شده - قابل حذف هرکدام]
[نمودار Payoff بزرگ] با خط افقی صفر مشخص، ناحیه سود سبز کم‌رنگ / زیان قرمز کم‌رنگ
[کارت خلاصه] Break-even: [مقادیر] | حداکثر سود: [مقدار یا "نامحدود"] | حداکثر زیان: [مقدار یا "نامحدود"]
[دکمه] "ذخیره این سناریو" (برای کاربران لاگین‌کرده)
```

> **پاسخ کاوش (واقعیت کد):** فقط یک `PayoffDiagram` ساده SVG در `frontend/src/app/options/components/helpers.tsx` وجود دارد (بدون فرم چندموقعیتی، بدون ناحیه رنگی، بدون کارت خلاصه break-even). دکمه ذخیره سناریو و جدول `saved_payoff_scenarios` **یافت نشد**.

---

## بخش ۸. اسکیمای API
```json
// GET /api/options/chain?underlying=فولاد&expiry=2026-10-15
{
  "underlyingSymbol": "فولاد",
  "underlyingPrice": 8500,
  "expiryDate": "2026-10-15",
  "chain": [
    {
      "strike": 8000,
      "call": { "contractSymbol": "...", "lastPrice": 650, "volume": 120, "openInterest": 3400, "delta": 0.68 },
      "put": { "contractSymbol": "...", "lastPrice": 90, "volume": 40, "openInterest": 900, "delta": -0.32 }
    }
  ]
}
```
```json
// POST /api/options/payoff-calculator
// Request
{
  "legs": [
    { "type": "call", "action": "buy", "strike": 8000, "premium": 650, "quantity": 10 },
    { "type": "call", "action": "sell", "strike": 8500, "premium": 300, "quantity": 10 }
  ],
  "priceRange": { "min": 6000, "max": 11000, "step": 100 }
}
// Response
{
  "payoffCurve": [{ "price": 6000, "payoff": -3500000 }],
  "breakEvenPoints": [8350],
  "maxProfit": 1500000,
  "maxLoss": -3500000
}
```
```
GET  /api/options/strategy-templates
POST /api/options/backtest
```

> **پاسخ کاوش (واقعیت کد):**
> - **این مسیرها با کد فعلی تفاوت دارند:** روتر موجود `apps/api/endpoints/options.py` مسیرهای `GET /strategies`، `GET /live/chain/{underlying}`، `GET /live/symbols`، `GET /greeks`، `POST /analyze` و ... دارد؛ مسیرهای `GET /chain`، `POST /payoff-calculator`، `GET /strategy-templates` و `POST /backtest` **یافت نشد**.
> - **roter موجود در `apps/api/router.py` mount نشده** → در API زنده `GET /api/v1/options/strategies` و `/live/chain/...` هر دو ۴۰۴ برمی‌گردانند (تأیید زنده ۲۰۲۶-۰۹-۱۶).
> - پاسخِ `GET /live/chain/{underlying}` فعلی ساختار متفاوتی دارد (تحلیل زنجیره: ATM/PCR/Max-Pain از `services/options_analytics.analyze_options_chain`)، نه دقیقاً ساختار JSON بالا.
> - پیشنهاد سازگاری: mount کردن روتر فعلی + افزودن مسیرهای جدید سند به‌صورت افزودنی؛ یا پیاده‌سازی مسیرهای سند و حفظ مسیرهای قبلی در کنار آن‌ها (اصل «فقط افزودن»).

---

## بخش ۹. نقش‌ها و پنل مدیریت
همان الگوی مشترک. پنل مدیریت اختصاصی: مدیریت لیست دارایی‌های پایه دارای آپشن پیگیری‌شده، ویرایش/افزودن الگوهای استراتژی آماده (`option_strategy_templates`) توسط Admin.

> **پاسخ کاوش (واقعیت کد):**
> - نقش‌ها: `core/enums/rbac.py` → **admin / analyst / user / viewer** (با سلسله‌مراتب، admin bypass). سیستم دوم برای IME: `core/security/ime_rbac.py` → **viewer / trader / quant / admin**. نقش پیش‌فرض کاربر جدید: `viewer`.
> - اعمال در API با `require_roles` (`apps/api/dependencies.py`)؛ پنل ادمین مستقل در `apps/admin/` روی prefix `/admin` (dashboard, jobs, providers, models, backtests, audit).
> - **پنل مدیریت اختصاصی آپشن (مدیریت دارایی‌های پایه/الگوها): یافت نشد** — باید ساخته شود. نزدیک‌ترین ابزار مدیریتی موجود صفحه «Sync Manager» فرانت + روت‌های `POST /api/v1/brsapi/manage/sync/option|ime-options` است (کار می‌کند).
> - فرانت: `RoleGate.tsx` وجود دارد ولی در هیچ صفحه‌ای استفاده نشده؛ گیت اصلی `middleware.ts` (چک کوکی) است.

---

## بخش ۱۰. Backfill تاریخی
اگر داده تاریخی قیمت آپشن در دسترس است، حداقل چند ماه برای فعال‌سازی معنادار تب بک‌تست backfill شود؛ در غیر این صورت این تب تا تأمین داده به تعویق بیفتد (نه اینکه با داده ناقص/جعلی نمایش داده شود).

> **پاسخ کاوش (واقعیت کد):** داده تاریخی **از ۲۰۲۶-۰۷-۱۵ تا ۲۰۲۶-۰۹-۱۶ (~۲ ماه)** به‌طور خودکار در `brsapi_option_snapshots`/`brsapi_ime_options` جمع شده و همین حالا «چند ماه» اولیه را پوشش می‌دهد. اسکریپت `scripts/backfill_250_working_days.py` برای `brsapi_option_snapshots` (ستون `gregorian_date`) وجود دارد. بنابراین: تب بک‌تست روی این بازه قابل فعال‌سازی است؛ برای بازه‌های قدیمی‌تر، تأمین داده (خرید تاریخچه یا بازسازی از `raw_json`) تصمیم تیم است.

---

## بخش ۱۱. مانیتورینگ کیفیت داده
- Open Interest یا حجم منفی → رد داده
- قرارداد با Strike غیرمنطقی (خیلی دور از قیمت لحظه‌ای دارایی پایه، احتمال خطای واحد) → flag برای بررسی
- عدم به‌روزرسانی زنجیره یک دارایی پایه پرمعامله بیش از X دقیقه در ساعات بازار → هشدار

> **پاسخ کاوش (واقعیت کد):** مانیتورینگ **اختصاصی آپشن یافت نشد**. زیرساخت عمومی موجود: `monitoring/` (data_freshness, drift, sla, incidents, job_monitor), `brsapi/raw_validation.py`, `brsapi/readiness.py`, جدول‌های `provider_health` و صفحه `/data-health` فرانت. برای سه بند بالا باید قواعد اختصاصی (مثلاً در pipeline برساپی) افزوده شود. آستانه X دقیقه باید با فاصله واقعی sync (۵ دقیقه) انتخاب شود — پیشنهاد: ۱۵ دقیقه.

---

## بخش ۱۲. Edge Case ها
- قرارداد با نقدشوندگی صفر (بدون معامله) — نمایش با برچسب "بدون معامله" به‌جای قیمت گمراه‌کننده صفر
- سررسید در روز جاری (Payoff باید بر اساس قیمت لحظه‌ای، نه فرضی، محاسبه شود)
- دارایی پایه بدون قیمت لحظه‌ای معتبر (نماد متوقف) — زنجیره باید این وضعیت را شفاف نشان دهد، نه محاسبه نادرست Payoff

> **پاسخ کاوش (واقعیت کد):** داده واقعی این edge caseها را نشان می‌دهد: در نمونه زنده `ضسپا6047` قراردادی با `days_remaining=0` وجود دارد (سررسید همان روز) و قراردادهای IME با `put_price_last=0.0` و `put_open_interest=0` دیده می‌شود. **هیچ منطق اختصاصی برای این حالت‌ها در کد یافت نشد** (نه برچسب «بدون معامله»، نه تشخیص نماد متوقف)؛ باید در موتور و UI افزوده شود.

---

## بخش ۱۳. معماری کامپوننت فرانت‌اند
```
OptionChainPage/
├── <UnderlyingSelector />
├── <ExpirySelector />
└── <OptionChainTable />

PayoffCalculatorPage/
├── <LegBuilderForm />
├── <StrategyTemplatePicker />
├── <PayoffChart />           ← منطق محاسبه از موتور مشترک بخش ۳ استفاده می‌کند، نه بازنویسی در کامپوننت
└── <PayoffSummaryCard />
```

> **پاسخ کاوش (واقعیت کد):** ساختار واقعی `frontend/src/app/options/components/`:
> `OptionsDashboard`, `StrategyAnalyzer`, `LiveChainPanel` (معادل OptionChainTable — بدون UnderlyingSelector/ExpirySelector مستقل؛ دارایی پایه با دکمه‌های preset: ذوب، فخز، وامد، کچاد، شپنا، وبصا، فاخر، وپمی), `AnalyticsPanel`, `ProfessionalTools`, `ForecastPanel`, `LearnPanel`, `helpers.tsx` (شامل `PayoffDiagram`), `types.ts`.
> - `PayoffCalculatorPage`/`LegBuilderForm`/`StrategyTemplatePicker`/`PayoffSummaryCard`: **یافت نشد** — باید ساخته شود (می‌توان از `StrategyAnalyzer` فعلی به‌عنوان پایه استفاده کرد).
> - منطق محاسبه payoff فعلاً داخل کامپوننت/سرویس پایتون است، نه یک موتور مشترک دوسویه؛ مطابق هشدار سند، قبل از ساخت UI باید موتور مشترک استخراج شود.

---

## بخش ۱۴. برنامه تست
Unit: موتور Payoff با ۵+ سناریوی مرجع (الزام سند). Integration: از ورودی کاربر در فرم تا رسم نمودار نهایی. E2E: ساخت یک استراتژی Bull Spread از الگوی آماده و بررسی صحت نمودار و Break-even.

> **پاسخ کاوش (واقعیت کد):**
> - **Unit موتور Payoff: یافت نشد.**
> - تست‌های مرتبط موجود در `tests/unit/options/` (۱۱ فایل): `test_greeks.py`, `test_options_comprehensive.py` (Black-Scholes parity/Greeks/IV، درخت، مارجین، VaR، Max-Pain)، `test_phase2_ci.py`, `test_ime_pricing_engine.py`, `test_ime_signal_factory.py`, `test_ime_slippage_simulator.py`, `test_margin_engine.py`, `test_var_calculator.py`, `test_monte_carlo.py`, `test_commodity_pricing_guards.py`, `test_tier2_prediction.py` + `tests/gold_desk/test_black76.py`.
> - **Integration/E2E برای مسیر آپشن: یافت نشد** (هیچ تستی `apps/api/endpoints/options.py` یا صفحات فرانت آپشن را اجرا نمی‌کند؛ فقط اسکریپت‌های legacy `tests/legacy/scripts/_tmp_api_test*.py` که به سرور زنده درخواست می‌زنند).
> - CI: pytest با Postgres/Redis در `ci.yml` و `ci-pr.yml` اجرا می‌شود؛ تست‌های unit آپشن در مسیر `tests/unit` هستند و در CI بالا می‌آیند.

---

## بخش ۱۵. واژه‌نامه
Strike: قیمت اعمال قرارداد آپشن. Premium: قیمت خرید/فروش قرارداد. ITM/ATM/OTM: وضعیت سودآور بودن/خنثی/زیان‌آور بودن آپشن نسبت به قیمت فعلی دارایی پایه. Open Interest: تعداد قراردادهای باز (اعمال‌نشده) در بازار. Greeks: حساسیت‌های قیمت آپشن نسبت به عوامل مختلف (دلتا نسبت به قیمت دارایی، تتا نسبت به گذر زمان، و غیره).

> **پاسخ کاوش (واقعیت کد):** نسخه کامل‌تر (۲۵ آیتم) از قبل به‌صورت داده ثابت در `services/options_reference.py` (`GLOSSARY`) موجود است و از طریق `GET /options/reference/glossary` (unmounted) سرو می‌شود؛ همین‌طور فرمول‌ها (`KEY_FORMULAS`)، اشتباهات رایج (`COMMON_MISTAKES`)، قوانین ایران (`IRAN_MARKET_RULES`) و نمونه‌های واقعی (`IRANIAN_EXAMPLES`).

---

## بخش ۱۶. خط لوله خودکار دریافت داده
```
Scheduler: به‌روزرسانی زنجیره اختیار معامله با فرکانس بالا در ساعات بازار (پیشنهاد هر چند دقیقه، بسته به فرکانس واقعی تغییر منبع)
API Client: مشابه الگوی مشترک با retry/backoff
Validator: Strike/Premium/Volume/OI نباید منفی باشند؛ تطابق contract_symbol با فرمت استاندارد بررسی شود
Upsert Writer: هر رکورد option_market_data به‌صورت insert-only (تاریخچه‌ای) ذخیره می‌شود؛ فقط "آخرین وضعیت" هر قرارداد در یک view/جدول خلاصه upsert می‌شود
Audit Log: جدول مشترک ingestion_run_logs با job_type='option_chain_sync'
```

> **پاسخ کاوش (واقعیت کد):**
> - **Scheduler:** موجود و فعال — `brsapi_options` با cron `_EVERY_5_MIN` و `market_hours_only=True` (`brsapi/jobs/registry.py:144`)؛ `brsapi_ime_options` هم هر ۵ دقیقه. زمان‌بندی: APScheduler `Asia/Tehran`.
> - **API Client:** `brsapi/client.py` با retry/backoff نمایی، احترام به `Retry-After`، circuit breaker per-path و rate-limit سه‌لایه (`brsapi/rate_limiter.py`, `brsapi/budget.py` — سقف روزانه پیش‌فرض ۴۰۰۰).
> - **Validator:** `brsapi/raw_validation.py` در pipeline برساپی وجود دارد، ولی **قاعده اختصاصی آپشن (منفی‌بودن Strike/Premium/Volume/OI و فرمت contract_symbol) یافت نشد** — باید افزوده شود.
> - **Upsert Writer:** insert-only فعلی = `brsapi_option_snapshots` (هر sync یک ردیف جدید؛ تاریخچه حفظ می‌شود). **view/جدول خلاصه «آخرین وضعیت» یافت نشد** — باید ساخته شود (سند migration `0048_materialized_latest_views.py` برای جدول‌های دیگر معادل دارد و می‌تواند الگو باشد).
> - **Audit Log:** جدول `ingestion_run_logs` **یافت نشد**؛ معادل‌های واقعی: `job_runs` (مدل `models/job_run.py`، بدون migration) و `fund_ingestion_runs` (با migration). یا باید از `job_runs` با `job_type='option_chain_sync'` استفاده شود یا جدول جدید ساخته شود.

---

## بخش ۱۷. Rollout بدون اختلال
مرحله ۱: Migration افزودنی. مرحله ۲: موتور Payoff و تست کامل آن قبل از هرگونه نمایش عمومی (چون خطای محاسباتی اینجا مستقیماً روی تصمیم مالی کاربر اثر می‌گذارد). مرحله ۳: فعال‌سازی تدریجی UI برای Admin/Analyst سپس عموم.

> **پاسخ کاوش (واقعیت کد):** پیش‌نیاز مرحله ۱ (Migration افزودنی) باید Alembic-محور باشد؛ چون `option_contracts` فعلی migration ندارد و با script ساخته شده، migration جدید باید idempotent باشد. برای مرحله ۳، گیت نقش از قبل وجود دارد (`require_roles("admin")` / `"analyst","admin"` در mountها) و می‌توان از همان الگو برای feature-gating آپشن استفاده کرد؛ فرانت `RoleGate` آماده ولی بی‌استفاده است.

---

## بخش ۱۸. چک‌لیست نهایی
- [ ] هیچ داده/فیچر فعلی حذف نشده
- [ ] موتور Payoff با ۵+ سناریوی مرجع تست و تأیید شده
- [ ] زنجیره اختیار معامله با فیلتر ITM/ATM/OTM کار می‌کند
- [ ] ماشین‌حساب ترکیبی + الگوهای آماده پیاده‌سازی شده‌اند
- [ ] Greeks (محاسبه‌شده یا از منبع) با دقت مشخص نمایش داده می‌شود
- [ ] هشدار «داده گذشته» در بک‌تست همیشه‌نمایان است
- [ ] مانیتورینگ کیفیت داده فعال است
- [ ] Rollout بدون downtime انجام شده

> **پاسخ کاوش (وضعیت فعلی هر بند در ۲۰۲۶-۰۹-۱۶):**
> ۱) داده فعلی (brsapi_option_snapshots/IME/Legacy) دست‌نخورده است؛ هر تغییر باید افزودنی باشد. ۲) **انجام نشده** (موتور + تست وجود ندارد). ۳) جدول/فیلتر در فرانت نمونه دارد ولی چون API mount نیست، عملاً کار نمی‌کند. ۴) **انجام نشده** (فقط ۳۰ استراتژی hardcoded و رسم ساده). ۵) موتور محاسبه و تست‌ها موجود؛ نمایش API/UI متصل نیست. ۶) **یافت نشد**. ۷) **یافت نشد** (فقط زیرساخت عمومی). ۸) طبق روال پروژه (Docker/compose/CI) ممکن است؛ سندیتی برای آپشن وجود ندارد.

---

## بخش ۱۹. خلاصه اجرایی
```
هدف: تبدیل نمایش ساده قرارداد آپشن به یک ماشین‌حساب تحلیلی کامل برای تصمیم‌گیری روی مشتقات.
نکته کلیدی و پرریسک‌ترین بخش فنی: موتور محاسبه Payoff و Greeks — خطا در این بخش مستقیماً منجر به تصمیم مالی اشتباه کاربر می‌شود، پس تست دقیق قبل از هر نمایش عمومی الزامی است.
بدون خراب کردن چیزی که الان کار می‌کند؛ فقط لایه‌های تحلیلی/محاسباتی جدید اضافه می‌شود.
```

> **پاسخ کاوش (واقعیت کد):** دو یافته تعیین‌کننده قبل از شروع:
> ۱. **روتر `apps/api/endpoints/options.py` (۲۶ روت) در `apps/api/router.py` mount نشده و در API زنده ۴۰۴ می‌دهد** — بنابراین «نمایش سادهٔ فعلی» هم عملاً در دسترس کاربر نیست؛ اولین گام بستن این شکاف است (بدون حذف هیچ روت فعلی).
> ۲. منبع داده و موتورهای محاسبه (Black-Scholes/Greeks/IME) و UI ۷ تبی از قبل وجود دارند؛ کار اصلی، **اتصال، تست موتور Payoff مشترک، مدل داده افزودنی و اتصال الگوهای آماده** است، نه ساخت همه‌چیز از صفر.

---

### پیوست — وابستگی‌های تصمیم تیم (طبق قانون طلایی کاوش)
| # | تصمیم | گزینه‌ها | تصمیم ثبت‌شده (۲۰۲۶-۰۹-۱۶) |
|---|---|---|---|
| ۱ | منبع واحد داده آپشن | `brsapi_option_snapshots` به‌عنوان source of truth + view خلاصه، یا پر کردن `option_contracts/option_market_data` از برساپی، یا حفظ دو لایه | **باز** — نیاز به تصمیم (باید به‌عنوان گام اول فاز پیاده‌سازی تعیین شود) |
| ۲ | نرخ بدون ریسک | ثابت config با پیش‌فرض ۰٫۱۵ / فید اخزا از صفر / جدول‌های تاریخی | **تصمیم تیم: ثابت config با پیش‌فرض ۰٫۱۵** (هماهنگ با `services/options_service.py:48` و پیش‌فرض فعلی API؛ قابل‌تنظیم در آینده) |
| ۳ | روتر فعلی | mount ساده + افزودن مسیرهای سند، یا بازنویسی در قالب اسکیمای سند | **تصمیم تیم: mount همان روتر `apps/api/endpoints/options.py` در `apps/api/router.py` + افزودن مسیرهای جدید سند به‌صورت افزودنی** (هیچ روت فعلی حذف/تغییر نمی‌شود) |
| ۴ | محل محاسبه Payoff | endpoint سرور (`POST /payoff-calculator`) یا تابع مشترک فقط سمت کلاینت | **باز** — مطابق بخش ۳.۱ سند، موتور خالص مشترک الزامی است؛ محل endpoint با تصمیم ۳ هم‌راستا می‌شود |
