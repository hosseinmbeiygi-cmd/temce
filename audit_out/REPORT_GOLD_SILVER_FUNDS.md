# گزارش ممیزی قابلیت‌اتکا — طلا، نقره، صندوق‌ها (GoldDesk / Silver / Funds)

> **حکم نهایی: غیرقابل‌اتکا** — سه حوزه به سه درجهٔ متفاوت:
>
> | حوزه | حکم | کوتاه |
> |---|---|---|
> | **طلا (GoldDesk)** | غیرقابل‌اتکا | موتور امتیاز هیچ‌گاه سبز نمی‌شود (سقف واقعی ۵۳ از ۱۰۰)، بخش صندوق‌ها همیشه خالی است، بک‌تست همیشه «داده ندارد»، و حباب «طلای آب‌شده» ۳۱۲٪ گزارش می‌شود. |
> | **نقره (Silver)** | ناقص/غیرقابل‌اتکا برای صندوق‌ها | دادهٔ انس جهانی از سرور می‌آید، اما **هیچ صندوق نقره‌ای هرگز در صفحه دیده نمی‌شود** (فیلتر `market=ime` در برابر دادهٔ `tse`) و لایهٔ بک‌اند نقره وجود ندارد. |
> | **صندوق‌ها (Funds)** | شبیه‌سازی‌نشده + یک باگ حسابداری قطعی | محاسبهٔ NAV در مسیر fallback بدهی را دو بار کم می‌کند (‎−۱۱.۱٪‎ بر عدد واقعی)، نقد هرگز اضافه نمی‌شود، و ورودی‌های واقعی موتور تقریباً صفرند (holdings=0، reports=0، history=1). |
>
> این فایل همهٔ ممیزی طلا/نقره/صندوق‌ها را در **یک فایل** جمع می‌کند: ۷ بخش (A تا G)، جدول کامل **۳۳ یافته** (۵ بحرانی، ۷ بالا، ۱۲ متوسط، ۶ پایین، ۳ اطلاعاتی) و پیوست شواهد خام.
>
> قواعد رعایت‌شده: هیچ عدد/نام فایل/شماره خطی ساخته نشده؛ هر ادعا با عین سطر یا عین خروجی فرمان پشتیبانی شده؛ **هیچ فایل موجود پروژه تغییر/حذف نشده** (فقط فایل‌های جدید زیر `audit_out/`)؛ روی DB زنده **فقط SELECT** اجرا شده است.

## اعداد کلیدی (همه از اجرای واقعی، نه تخمین)

| ادعا | عدد | منبع |
|---|---|---|
| صندوق‌های طلا برگشتی از `nav_checker.get_all_funds_status` | **۰ از ۱۰** | `_logs/gold_desk_snapshot.out` بخش B |
| سقف امتیاز با ورودی‌های بهینه | **۵۳** (آستانه YELLOW = ۵۵) | همان، بخش C |
| امتیاز snapshot زندهٔ DB | **۳۰ → RED** | همان، بخش D |
| ردیف‌های `brsapi_gold_coin_history` برای `IR_COIN_EMAMI` / تطابق با cutoff کد | **۴۸۶۹ / ۰** | `_logs/gold_silver_funds_db2.out` بخش A |
| اختلاف NAV/unit در مسیر fallback صندوق | **‎−۱۱.۱٪** (۸۰۰ در برابر ۹۰۰) | `_logs/gold_silver_funds_probe.out` بخش ۴ |
| حباب `IR_GOLD_MELTED` در snapshot زنده | **+۳۱۲.۶۵٪** | `_logs/gold_desk_snapshot.out` بخش D |
| اختلاف حباب سکه بین دو ماژول (عیار ۹۰۰ در برابر ۰.۹۱۵) | **۵.۰۰٪ در برابر ۳.۳۰٪** | `_logs/gold_silver_funds_probe.out` بخش ۱ |
| صندوق‌های نقرهٔ دیده‌شدنی در صفحهٔ نقره | **۰** (۳ صندوق در DB، همه `market=tse`) | `_logs/gold_silver_funds_db4.out` بخش A |
| ورودی‌های واقعی موتور NAV | holdings=**۰**، portfolio_reports=**۰**، nav_history=**۱**، nav_runs=**۱** | `_logs/gold_silver_funds_db.out` بخش F (و `db2` بخش D) |
| آزمون‌های طلا/صندوق | **۱۴۹ + ۲۸۱ + ۱۶۵ = همه سبز** | `_logs/gold_desk_pytest.log`، `_logs/funds_unit_pytest.log`، `_logs/gold_funds_api_pytest.log` |

## فهرست مطالب

1. [بخش A — طلا: مسیر snapshot و امتیاز](#بخش-a--طلا-مسیر-snapshot-و-امتیاز)
2. [بخش B — طلا: بک‌تست، پیش‌بینی، پرتفوی، معاملهٔ خودکار](#بخش-b--طلا-بکتست-پیشبینی-پرتفوی-معاملهٔ-خودکار)
3. [بخش C — طلا: ماژول Antigravity و مدل‌های هزینه](#بخش-c--طلا-ماژول-antigravity-و-مدلهای-هزینه)
4. [بخش D — نقره](#بخش-d--نقره)
5. [بخش E — صندوق‌ها: موتور NAV و تطبیق](#بخش-e--صندوقها-موتور-nav-و-تطبیق)
6. [بخش F — آزمون‌ها](#بخش-f--آزمونها)
7. [بخش G — جمع‌بندی و اولویت‌ها](#بخش-g--جمعبندی-و-اولویتها)
8. [پیوست الف — جدول کامل یافته‌ها](#پیوست-الف--جدول-کامل-یافتهها)
9. [پیوست ب — شواهد خام و بازتولید](#پیوست-ب--شواهد-خام-و-بازتولید)

---

# بخش A — طلا: مسیر snapshot و امتیاز

مسیر محصول: `src/gold_desk/snapshot_service.py::build_snapshot()` → `nav_checker` + `signal_engine` + `pricer` + `bubbler` + `scorer`. این مسیر را روی DB زنده اجرا کردم (فقط SELECT، `_tmp/gold_desk_snapshot_probe7.py`).

## A1. بخش صندوق‌ها همیشه خالی است — و ۳۲ امتیاز را با خود می‌برد (GS-01، GS-02)

`nav_checker._latest_nav` این کوئری را می‌سازد:

```python
# src/gold_desk/nav_checker.py:45  (و تکرار در :64)
select(NavRecordModel.nav)
```

اما `NavRecordModel` (`brsapi/models/tsetmc.py:261`) هیچ ستونی به نام `nav` ندارد؛ فقط `nav_issue` و `nav_redemption`. خروجی اجرا:

```
A) NavRecordModel — وجود ستون nav که nav_checker می‌خواند
   hasattr(NavRecordModel, 'nav') = False
   hasattr(NavRecordModel, 'nav_issue') = True
   attribute access: AttributeError: type object 'NavRecordModel' has no attribute 'nav'
B) nav_checker.get_all_funds_status برای ۱۰ صندوق طلا (DB زنده، فقط SELECT)
   returned: 0 funds (از 10 نماد درخواستی)
```

خطا در `except Exception: return None` بی‌صدا خورده می‌شود، پس `get_fund_status` برای **هر ۱۰ نماد** `None` می‌دهد، `funds=[]` می‌شود و در `build_snapshot` (خطوط ۲۸۳–۲۸۷) `bpr=None`، `nav_bubble_pct=None` و `nav_7d_pct=None` باقی می‌مانند.

نتیجهٔ محاسباتی (اجرای واقعی `scorer.compute_score` با بهترین ورودی‌های ممکن برای بقیهٔ اجزا):

```
components: bubble=(20,20) nav=(0,18) tsetmc=(18,18) technical=(0,15) parity=(15,15) fund_flow=(0,14)
total=53  decision=RED   (GREEN>=80، YELLOW>=55)
```

**پس سقف امتیاز واقعی ۵۳ است و آستانهٔ YELLOW ۵۵** — یعنی حتی در بهترین حالت بازار، decision هرگز سبز/زرد نمی‌شود. snapshot زنده هم `total=30 → RED` داد (نگاه A3).

## A2. جزء تکنیکال و hard stop هرگز داده نمی‌گیرند (GS-06، GS-07)

`signal_engine.fetch_closes` از `brsapi_gold_coin_history` می‌خواند و `_calc_daily_changes` هم برای USD/TSE/DXY به همان جدول تکیه دارد. اما در DB زنده:

```
gold_hist_hardstop_symbols  → (no rows)        # USD, DXY, TSE_INDEX, INDEX, TEDPIX, XAUUSD, AED
E) نماد XAUUSD در جداول دیگر
   brsapi_gold_coin_history           XAUUSD rows = 0
```

در همین حال `XAUUSD` در جدول دیگر موجود است (`get_gold_coin_prices()` → `…, 'IR_GOLD_MELTED', 'XAUUSD']`)، یعنی داده هست ولی ماژول از منبع اشتباه می‌خواند. پیامدها:

- `xau_rsi = None` → `score_technical` همیشه `0/15` با دلیل ثابت «RSI موجود نیست» (در snapshot زنده هم همین بود).
- `changes["usd"|"dxy"|"tse"] = None` → `hard_stops.check_hard_stops` هیچ‌گاه فعال نمی‌شود؛ در snapshot زنده `hard_stop=False`.
- کل بلوک محاسبه در `contextlib.suppress(Exception)` است (خطوط ۱۳۹–۱۷۲) پس «نبود داده» به‌جای هشدار، سکوت تولید می‌کند.

## A3. اجرای واقعی snapshot روی DB زنده

```
refs: xau=4346.66 usd=265100.0 aed=72588.0 gap=-0.555%
gold blocks=3 coins=4 funds=0
  coin_emami: market=269,310,000  fair=271,282,178  bubble=-0.727%
  gold_melted: market=114,669,000  fair=27,788,247  bubble=312.65%
score total=30 decision=RED  hard_stop=False
  bubble=20 (حباب -0.7٪ < 8.0٪ — عالی)
  nav=0    (NAV موجود نیست)
  tsetmc=0 (BPR موجود نیست)
  technical=0 (RSI موجود نیست)
  parity=10 (|gap|=0.55٪ — کمی偏离)      ← کاراکترهای چینی در خروجی واقعی
  fund_flow=0 (NAV 7d موجود نیست)
```

سه نکتهٔ مهم در همین خروجی:

1. **`gold_melted` با حباب ۳۱۲.۶۵٪** — `MESGHAL_GRAMS = 4.6083` در `constants.py:15` تعریف شده و **هیچ‌جای مخزن استفاده نشده** (grep: تنها یک ارجاع، همان تعریف). `pricer.fair_value` برای `IR_GOLD_MELTED` یک گرم ۱۸ عیار برمی‌گرداند (`pricer.py:78`)، در حالی که قیمت بازار مثقالی است: `114,669,000 / 27,788,247 ≈ 4.13`. بررسی نرم (`VALID_BUBBLE_PCT_RANGE`) فقط لاگ هشدار می‌کند و عدد ۳۱۲٪ در snapshots و UI باقی می‌ماند.
2. **بلوک‌های غایب** — از ۹ نماد ثبت‌شده فقط ۷ بلوک آمد (`gold=3` از ۴، `coins=4` از ۵). علت: `IR_GOLD_1G` و `IR_COIN_GERAMI` در منبع قیمت وجود ندارند، در حالی که `IR_COIN_1G` (بدون ثبت در رجیستری) موجود است (GS-20).
3. **خطای زبانی در خروجی محصول**: `parity_reason` = «|gap|=0.55٪ — کمی偏离» (`scorer.py:146`) با حروف چینی (GS-26).

## A4. ناهم‌خوانی BPR و جریان پول صندوق‌ها (GS-15، GS-16)

- `snapshot_service.py:283`: `bpr = sum(f.bpr …) / len(fund_statuses)` — میانگین سادهٔ *نسبت‌ها* روی صندوق‌های با حجم بسیار متفاوت، و صندوقی که داده ندارد با `bpr=0` میانگین را پایین می‌کشد.
- `snapshot_service.py:285`: `if bpr is not None and bpr == 0 and not fund_statuses: bpr = None` — اگر `fund_statuses` خالی باشد `bpr` از خط ۲۸۳ **قبلاً None** است، پس شرط هیچ‌وقت برقرار نمی‌شود: کد مرده.
- `nav_checker.py:79-85` (`_fund_market_data`): آخرین ردیف `brsapi_historical_real_legal` **بدون سقف تازگی** خوانده می‌شود.در DB:

```
('عیار',  3337, '1397-03-19', '1405-06-23')
('آلتون', 5447, '1402-01-15', '1405-07-15')     ← سایر نمادها تا 1405-07-15 به‌روزند
```

یعنی BPR/Inflow صندوق مرجع امتیاز («عیار») حدود سه هفته قدیمی‌تر از منبع است و همان عدد در `tsetmc` (۱۸ امتیاز) به‌کار می‌رود. این در تناقض آشکار با طراحی خودِ ماژول است: در `FundNAVStatus` صریحاً `market_price: float | None` با توضیح «None یعنی قیمتی پیدا نشد، نه حباب صفر» گذاشته شده، ولی برای `bpr` همان اشتباه (صفر به‌جای نامعلوم) انجام می‌شود.

## A5. خطای پیام alert (GS-13)

```python
# src/gold_desk/alert_engine.py:121
message=f"{rule.name}: {value:.2f} {'>' if rule.threshold > 0 else '<'} {rule.threshold:.2f}",
```

جهت عملگر از **علامت threshold** گرفته می‌شود، نه از `rule_type`. اجرای واقعی روی `DEFAULT_RULES`:

```
rule_type=bubble_below       threshold=3.0    msg_operator='>'   name=حباب سکه پایین (فرصت خرید)
_check_condition('bubble_below', value=2.0, threshold=3.0) = True
```

یعنی برای قانون پیش‌فرض «حباب سکه پایین» شرط `<` است ولی پیام «> 3.00» رندر می‌شود — اعلان درست شلیک می‌شود ولی متن آن معکوس است.

## A6. سایر یافته‌های مسیر طلا

- **تاریخچهٔ گمشده در پرتفوی (GS-17)**: `portfolio.py:79` در نبود قیمت، `avg_buy` را جایگزین می‌کند (`current = current_prices.get(sym, avg_buy)`) → PnL صفر کاذب.
- **معاملهٔ خودکار (GS-18)**: `auto_trade.py:158` مبلغ را با سقف ثابت `min(config.max_position_irt, 50_000_000)` می‌بُرد (اجرا: config=۵۰۰M → ۵۰M)، در `dry_run` ردیف `gold_trades` با `quantity=0, price=0` ثبت می‌کند (خط ۱۸۱) و مسیر live فقط `{"status": "live_placeholder"}` برمی‌گرداند (خط ۲۰۰).
- **`metrics.py`** (GS-27): شمارنده‌ها متغیرهای گلوبال بدون قفل و `_percentile` کوانتیل واقعی نیست.
- **جداول خالی (GS-33)**: `gold_snapshots=0، gold_fund_nav=0، gold_score_history=0، gold_holdings=0، gold_trades=0، gold_alert_rules=0، gold_alert_events=0، gold_dca_plans=0`.

---

# بخش B — طلا: بک‌تست، پیش‌بینی، پرتفوی، معاملهٔ خودکار

## B1. بک‌تست غیرقابل‌اجرا: تقویم میلادی در برابر ستون شمسی (GS-03)

```python
# src/gold_desk/backtest.py:39,44
cutoff = (utc_now_naive() - timedelta(days=days + 60)).strftime("%Y-%m-%d")   # "2026-05-14"
.where(GoldCoinHistoryModel.symbol == symbol, GoldCoinHistoryModel.date >= cutoff,)
```

اما ستون `date` شمسی است (اسکریپت واردکننده خودش می‌گوید «OHLC data … with Persian dates»، `scripts/import_gold_currency_history.py:5`). اجرای واقعی همان predicate:

```
cutoff code-generated = '2026-05-14' (میلادی)
rows matching date >= cutoff : 0
rows total (IR_COIN_EMAMI)   : 4869
rows matching date >= '1405-01-01' (ژلالی): 146
```

پس `_daily_bubble_pct` همیشه `[]` برمی‌گرداند و `run_backtest` همیشه `sample_warning="no data"` می‌دهد. نکتهٔ مثبت: اصلاح lookahead در همان فایل (SMA علّی به‌جای `np.convolve(mode="same")`) درست انجام شده و کامنت هشدار هم دارد — اما هیچ‌وقت اجرا نمی‌شود.

## B2. پیش‌بینی: باند بدون کران و «EMA trend» بدون EMA (GS-19)

```python
# src/gold_desk/forecaster.py:179-180
band_pct = 1.96 * vol * math.sqrt(h)
lower = pred * (1 - band_pct)
```

اجرای واقعی با سری پرنوسان:

```
quiet   : vol=0.0%   h=30 lower=109  pred=109
volatile: vol=12.1%  band_pct(30d)=1.299  h=30 pred=64  lower=-19  upper=147
EMA(14) واقعی=111.07  اما _forecast_ema_trend(h=7)=114.10
```

دو مشکل: (۱) باند بدون کران → **قیمت منفی** در خروجی؛ (۲) `_forecast_ema_trend` مقادیر `ema` را محاسبه می‌کند (`forecaster.py:104`) و در مسیر اصلی دور می‌ریزد و در واقع `closes[-1] * (1+drift)**horizon` برمی‌گرداند — نام مدل با رفتارش نمی‌خواند.

## B3. سه مدل هزینهٔ جدا برای یک دارایی (GS-29، GS-28)

| فایل | مدل | عدد |
|---|---|---|
| `backtesting/costs/gold_costs.py:21` | اسپرد دو طرفه | `BASE_SPREAD_PCT = 0.005` (۰.۵٪ کل) |
| `src/gold_desk/constants.py:40` | کارمزد ETF | `buy/sell = 0.15%` هر طرف |
| `domain/trading/iran_costs.py` | مدل عمومی کارمزد/مالیات | بدون ارجاع متقابل |

هیچ SSOTی وجود ندارد و در `GoldCostModel`:

```python
# backtesting/costs/gold_costs.py:49
def effective_spread(self) -> float:
    return max(self.min_spread_pct, min(self.max_spread_pct, self.base_spread_pct))
```

چون `base_spread_pct` ثابت است و **هیچ ورودی نوسانی وجود ندارد**، کران‌های ۰.۲٪ و ۲٪ هرگز فعال نمی‌شوند — خلاف docstring («never exceed this regardless of volatility» و «Spread varies by product type»).

---

# بخش C — طلا: ماژول Antigravity و مدل‌های هزینه

ماژول `src/gold_desk/antigravity/` یک پیاده‌سازی موازی از همان مفاهیم (حباب سکه، پرمیوم NAV، آربیتراژ، ریسک آتی) با ثابت‌های متفاوت است.

## C1. عیار سکه: ۰.۹۱۵ در برابر ۰.۹۰۰ (GS-12)

```python
# src/gold_desk/antigravity/assets.py:65-66
"purity": "900/1000",
"purity_ratio": 0.915,  # 900/1000 + اجرت ضرب per spec      ← انحراف مستندشده از عیار اعلامی
# src/gold_desk/constants.py:14
GOLD_PURITY_COIN: float = 900.0
# src/gold_desk/antigravity/calculations.py:54
_COIN_PURITY: float = 0.915
```

اجرای واقعی هر دو مسیر با یک ورودی یکسان (`XAU=4000$`, `USD=900,000`, سکهٔ امامی):

```
gold_desk.pricer.fair_coin = 847,366,479        (عیار ۰.۹۰۰)
antigravity intrinsic      = 861,321,137        (عیار ۰.۹۱۵)  → +13,954,658 (+1.647%)
market = 889,734,803
bubble via gold_desk (bubbler)      = +5.000%   signal=(n/a)
bubble via antigravity.calculations = +3.299%   signal=NEUTRAL
```

دو عدد متفاوت برای یک دارایی در یک برنامه، با فاصله‌ای که می‌تواند یک سیگنال «فروش» را به «خنثی» تبدیل کند.

## C2. آستانه‌های P/NAV سه‌گانه (GS-14)

| منبع | آستانهٔ «ارزان/گران» |
|---|---|
| `src/gold_desk/constants.py:67` | `NAV_GREEN_MAX=0.5` ، `NAV_YELLOW_MAX=1.5` ، `NAV_RED_MAX=3.0` |
| `src/gold_desk/antigravity/calculations.py:26,29` | `SELL` اگر > +۲٪ ، `BUY` اگر < ‎−۱٪ |
| `services/fund_scoring.py` (docstring override) | حباب > +۳٪ → سقف «اجتناب از خرید» ، ‎< ‎−۲٪ → کاندید ورود |

اجرای واقعی روی premium مرزی:

```
premium=+1.00%  antigravity=NEUTRAL   gold_desk_scorer_nav=75%
premium=+2.00%  antigravity=NEUTRAL   gold_desk_scorer_nav=30%   ← در آستانهٔ «بالا»ی scorer
premium=+3.00%  antigravity=SELL      gold_desk_scorer_nav=30%
```

یعنی در +۲٪ یک ماژول «خنثی» و ماژول دیگر تقریباً «حباب شدید» می‌گوید.

## C3. نکات مثبت همین ماژول (برای انصاف گزارش)

- `KillSwitchStatus` سه‌وضعیتی (`NORMAL/WARNING/ACTIVE`) با فهرست قوانین فعال و کلمات ماشه — طراحی شفاف‌تر از `HardStopResult` دوتایی.
- مدیریت خطای `DistributedMutex` با Lua آزادسازی امن و fallback محلی (در `fund_read_through.py`) درست پیاده شده.
- چرخهٔ عمر مغایرت در `fund_nav_reconciliation.py` (`ALLOWED_TRANSITIONS`) اعتبارسنجی می‌شود و گذار نامعتبر خطا می‌دهد — تنها جاهایی که state‑machine واقعاً گارد دارد.

---

# بخش D — نقره

## D1. وسعت واقعی سطح نقره (شواهد فایل‌محور)

تمام ارجاعات «نقره» در مخزن (بدون پوشهٔ کپی `_FRONTEND_BACKEND_COPY`):

```
frontend/src/app/markets/silver/page.tsx + components/{BacktestTab,ForecastTab,MlTab,PriceChart,helpers,GoldSilverRatioCard}
scripts/sync_gold_silver_sectoral_intraday.py
```

یعنی **هیچ مدل، سرویس، endpoint یا رجیستری نماد نقره در بک‌اند وجود ندارد**؛ صفحهٔ نقره روی endpointهای عمومی `commodities` / `funds` / `ime-futures` / `news` سوار است و تشخیص نقره با regex روی نام است (`helpers.ts:27-33`).

## D2. دادهٔ انس نقره هست، صندوق نقره هرگز دیده نمی‌شود (GS-09)

دادهٔ فلز جهانی سالم است:

```
XAGUSD: 4633 rows در precious_metal، date از 1405/04/24 تا 1405/07/18 (۵۸ روز متمایز)
```

اما مسیر صندوق‌ها:

```
merged funds: 636        by market: {'tse': 631, 'ime': 5}
silver-matching funds در کل merged: 3
   symbol='سیلور'  market='tse' fund_type='سهامی' nav=13824.0 price_last=None
   symbol='سیلور2' market='tse' fund_type='سهامی' nav=None    price_last=None
   symbol='سیمین'  market='tse' fund_type='سهامی' nav=13549.0 price_last=None
silver در market=ime: 0
```

و صفحهٔ نقره این‌گونه می‌پرسد (`page.tsx:143-149`):

```tsx
const r = await apiGet(... "/funds?market=ime&limit=200");
... const silver = isSilverText(n) || f.fund_type === "نقره";
    const commodity = f.fund_type === "کالایی" || /کالایی|کالا/.test(n);
    return (silver || commodity) && !isGoldText(n) && ((f.nav ?? 0) > 0 || (f.price_last ?? 0) > 0);
```

سه فیلتر مستقل هر سه صندوق نقره را حذف می‌کنند: `market=ime` (داده `tse` است)، `fund_type` (داده `سهامی` است نه «نقره/کالایی») و در یک مورد `price_last=None`. نتیجه: بخش صندوق‌های نقره در عمل همیشه خالی است.

## D3. قرارداد API و حجم پاسخ (GS-24)

صفحه سه بار `limit=2000` می‌فرستد (خطوط ۱۲۰، ۱۷۸، ۲۲۷) اما endpoint هیچ پارامتر `limit` ندارد:

```python
# apps/api/endpoints/brsapi.py:69
async def get_commodity_prices(category: str | None = Query(None, ...), service=Depends(...)):
```

`FastAPI` پارامتر ناشناس را نادیده می‌گیرد، پس **۱۸٬۵۳۲ ردیف** کامل `precious_metal` (۴ نماد × ۴۶۳۳ ردیف) دانلود و در مرورگر فیلتر می‌شود. همچنین docstring سرویس «Latest commodity prices» است ولی همهٔ تاریخچه برگردانده می‌شود (`brsapi/services/query_service.py:610` → تنها `order_by(category, symbol)`، بدون dedupe).

## D4. اسکریپت همگام‌سازی: «تا امروز» محقق نمی‌شود (GS-30)

```python
# scripts/sync_gold_silver_sectoral_intraday.py:78-90
def _missing_for(s, symbols):        # هر نمادی که «حداقل یک» تیک دارد موجود شمرده می‌شود
...
# :104
break                                # در اولین روز غیرخالی، از ادامهٔ walkback بیرون می‌آید
```

- نمادی که یک‌بار تیک گرفته، در اجراهای بعدی «موجود» است و **داده امروز آن هرگز sync نمی‌شود** — در تناقض با docstring «up to today's latest available trading day».
- نمادهای بی‌تیک هر اجرا کامل دوباره تلاش می‌شوند (بدون negative cache) → هر اجرا تا ۱۴ درخواست تکراری برای هر نماد مرده.
- نقطهٔ قوت: تقسیم به gold/silver/sectoral با «نقره» و «طلا/زر» با اولویت درست انجام شده و گزارش JSON (`data/top50_funds_intraday/sync_gss.json`) شامل `still_missing` است.

## D5. فیلتر نام‌محور و شکننده (GS-25)

```ts
// helpers.ts:31
export function isGoldText(value: unknown): boolean { return /طلا|زر|سکه|gold|xau/i.test(String(value ?? "")); }
```

«زر» در فارسی پسوند بسیار رایجی است (زرفام، زرین، …) و در `page.tsx:149` برای **حذف** ردیف استفاده می‌شود؛ هر ردیف نقره/کالایی که «زر» در نامش باشد حذف می‌شود. همین منطق در `scripts/sync_gold_silver_sectoral_intraday.py:66-70` هم تکرار شده (طبقه‌بندی با `in` روی نام).

---

# بخش E — صندوق‌ها: موتور NAV و تطبیق

دو مسیر مستقل برای صندوق‌ها وجود دارد: (۱) GoldDesk (`nav_checker` روی `brsapi_nav_records`)، (۲) ماژول Enterprise (`services/fund_nav_engine.py` + `fund_nav_reconciliation.py` + `fund_scoring.py` + `apps/funds/*`).

## E1. باگ قطعی حسابداری: کسر مضاعف بدهی (GS-04)

```python
# services/fund_nav_engine.py:303-317
if not holdings and report and report.get("net_asset_value"):
    total = float(report["net_asset_value"])          # ← این عدد خودش «دارایی − بدهی» است
    payload.warnings.append("holdings_missing_used_report_net_assets")
...
payload.total_liabilities = float((report or {}).get("total_liabilities") or 0.0)
payload.net_assets, payload.nav_per_unit = compute_nav(payload.total_assets, payload.total_liabilities, payload.units)
```

و `compute_nav` (خطوط ۶۸–۷۴):

```python
net = float(total_assets) - float(total_liabilities or 0.0)
```

اجرای واقعی همین تابع با اعداد نمونه (دارایی ۱B، بدهی ۱۰۰M، ۱M واحد):

```
مسیر A (assets - liabilities)          : net=900,000,000  nav/unit=900.00
مسیر B (net_asset_value - liabilities) : net=800,000,000  nav/unit=800.00
اختلاف nav/unit = -100.00 (-11.111%)
```

این مسیر دقیقاً همان حالتی است که در DB واقعی رخ می‌دهد (`fund_holdings=0`)، پس یکی از دو مسیر موجود برای محاسبهٔ NAV سیستماتیک ۱۱٪ کم‌برآورد می‌کند.

## E2. نقد هرگز به NAV اضافه نمی‌شود (GS-08)

```
196:            SELECT period_end_date, total_assets, total_liabilities,
196:                   net_asset_value, units_outstanding, cash_and_equivalents
213:            "cash_and_equivalents": row[5],
```

این تنها دو ارجاع در کل فایل است (grep روی `services/fund_nav_engine.py`). مقدار خوانده و در dict گزارش ذخیره می‌شود ولی در `_build_payload` هنگام ساخت `total_assets` (که فقط جمع ارزش موقعیت‌هاست) استفاده نمی‌شود.

## E3. موتور NAV روی داده واقعی تقریباً بی‌ورودی است (GS-10)

منبع اعداد زیر: `_logs/gold_silver_funds_db2.out` (بخش D) و بازتأیید تک‌درخواستی در `_logs/gold_silver_funds_db.out` (بخش F):

```
fund_holdings                     0
fund_portfolio_reports            0
fund_nav_history                  1 row  (tse:آگاس, 2026-09-20)
fund_nav_runs                     1
fund_position_valuations          0
fund_nav_reconciliation_runs      0
funds                           575
fund_universe                   575
```

یعنی مسیر «NAV مستقل + تطبیق نسخه‌دار» در محیط فعلی نه ورودی دارد و نه سابقه‌ای؛ خروجی‌های `quality_from_coverage` هم عملاً همیشه `BLOCKED`/`PARTIAL` است. (نکتهٔ مثبت: منطق کیفیت در حالت‌های بررسی‌شدهٔ خط ۳۰۳–۳۱۰ درست کار می‌کند و `BLOCKED` را بازنویسی نمی‌کند.)

## E4. تطبیق تاریخی هرگز COMPARABLE نمی‌شود (GS-11)

```python
# services/fund_nav_reconciliation.py:167-178
async def _load_reference(self, fund_id: str, nav_type: str) -> dict[str, Any] | None:
    ... FROM fund_nav_history WHERE fund_id = :fid ORDER BY nav_date DESC LIMIT 1
```

هیچ پارامتر تاریخی ندارد، پس برای `reconcile(..., as_of=<تاریخ گذشته>)` هم **جدیدترین** مرجع خوانده می‌شود؛ در ادامه `same_date = reference_date == valuation_date` نادرست می‌شود و `evaluate_comparability` → `NOT_COMPARABLE`. یعنی بازپخش/بک‌فیل هرگز به MATCHED/BREACH ختم نمی‌شود و `calibrate_thresholds` (که از ردیف‌های `COMPARABLE` می‌خواند) هم همیشه «نمونه کافی نیست» می‌دهد.

## E5. برچسب‌های کیفیت بیش‌ازحد خوش‌بین (GS-21، GS-22)

- `fund_nav_engine.py:95`: هر قیمت موجود در `brsapi_symbol_snapshots` برچسب `"quality": "LIVE"` می‌گیرد، در حالی که `price_at` (خط ۹۳) ذخیره می‌شود و **هیچ‌جا** برای گیتی بر اساس عمر استفاده نمی‌شود (خط ۳۰۰ فقط `pos["quality"] == "LIVE"` را می‌شمارد).
- `fund_nav_engine.py:311-314`: اگر هیچ موقعیت سهامی وجود نداشته باشد، `equity_reported == 0` → `coverage_pct = 100` می‌شود و با `has_report=True` کیفیت `COMPLETE` می‌گیرد، هرچند **هیچ قیمت‌گذاری مستقلی** انجام نشده و همهٔ ارزش‌ها از گزارش دوره آمده‌اند.

## E6. امتیازدهی صندوق (GS-23) و تکرار کد (GS-31، GS-32)

اندازه‌گیری واقعی توابع نمره (`services/fund_scoring.py`):

```
style_drift            f(5.0)=95.000  f(5.01)=79.990  jump=-15.010
ter                    f(0.5)=95.000  f(0.51)=89.733  jump=-5.267
tracking_difference    f(0.5)=95.000  f(0.51)=79.800  jump=-15.200
```

پرش‌های ۱۵ امتیازی روی آستانه‌ها می‌توانند رتبهٔ صندوق‌ها را با تغییر ناچیز داده جابه‌جا کنند. (وزن‌های هر هفت گروه را جمع زدم: همه دقیقاً ۱۰۰ — ایرادی ندارد.)

همچنین: ~۱۰۰ خط درج SQL بین `_persist_payload` و `calculate` تکرار شده (GS-31) و `datetime.utcnow()` در `fund_nav_reconciliation.py:290` (SLA و نسخهٔ آستانه) naive است (GS-32).

---

# بخش F — آزمون‌ها

هر سه گروه آزمون مرتبط را اجرا کردم؛ **همه سبزند** — که خودش بخشی از یافته است، چون هیچ‌کدام از ۳۳ مورد بالا را نمی‌گیرند:

```
pytest tests/gold_desk -q
→ 149 passed in 5.88s                                    (_logs/gold_desk_pytest.log)

pytest tests/unit/services -q -k fund
→ 281 passed, 1 skipped, 2267 deselected in 11.47s        (_logs/funds_unit_pytest.log)

pytest tests/unit/backtesting/test_gold_costs.py tests/unit/ingestion/test_gold_*.py \
       tests/unit/monitoring/test_gold_monitor.py tests/unit/api/test_golddesk_http.py \
       tests/unit/jobs/test_fund_jobs.py tests/unit/api/test_funds_serializers_declare_null.py \
       tests/test_funds_adapters.py tests/test_funds_api.py tests/test_funds_metrics.py \
       tests/unit/test_funds*api*.py tests/unit/test_funds_nav_endpoint.py
→ 165 passed, 21 skipped in 34.95s                        (_logs/gold_funds_api_pytest.log)
```

شکاف مشخص پوشش: هیچ تستی (الف) سقف/کف امتیاز را قفل نمی‌کند، (ب) مسیر `holdings_missing` موتور NAV را با اعداد ترازنامه اجرا نمی‌کند، (ج) قرارداد تاریخ (شمسی/میلادی) را روی دادهٔ واقعی چک نمی‌کند، (د) هم‌ارزی دو ماژول محاسبهٔ سکه را نمی‌سنجد.

---

# بخش G — جمع‌بندی و اولویت‌ها

**پنج اصلاح اول که بدون آن‌ها هیچ عددی از این حوزه‌ها قابل استناد نیست:**

| # | اصلاح | یافته |
|---|---|---|
| ۱ | `nav_checker` باید `nav_issue`/`nav_redemption` را بخواند (یا به `NavRecord` آنتی‌گولای نگاشت شود) و `except` بی‌صدا حذف/لاگ شود | GS-01 |
| ۲ | سقف واقعی ۵۳ امتیاز در برابر آستانهٔ ۵۵ → یا منابع `technical`/`nav`/`fund_flow` وصل شود یا آستانه و وزن‌ها بازتعریف و با تست قفل شود | GS-02، GS-06 |
| ۳ | یکسان‌سازی تقویم در `backtest.py` (و هر جایی که `date` با رشتهٔ میلادی مقایسه می‌شود) | GS-03 |
| ۴ | رفع کسر مضاعف بدهی در مسیر `holdings_missing` و افزودن نقد به `total_assets` | GS-04، GS-08 |
| ۵ | تعیین واحد `IR_GOLD_MELTED` (گرم یا مثقال) در `pricer` و تبدیل هشدار نرم به خطای داده | GS-05 |

**اصلاحات بعدی به ترتیب اثر:** فیلتر صندوق نقره در صفحه (GS-09)، سقف تازگی دادهٔ BPR (GS-16)، یکسان‌سازی آستانه‌های P/NAV و عیار سکه (GS-12، GS-14)، حذف کد مرده و شرط‌های بی‌اثر (GS-15، GS-28)، و افزودن صفحه‌بندی معتبر به `/brsapi/commodities` (GS-24).

---

# پیوست الف — جدول کامل یافته‌ها

منبع: `audit_out/findings_gold_silver_funds.csv` — ستون‌ها: `id,severity,area,file,line,description,confidence,suggested_action` — **۳۳ یافته** (۵ بحرانی، ۷ بالا، ۱۲ متوسط، ۶ پایین، ۳ اطلاعاتی).

توزیع به‌ازای حوزه: طلا **۱۹**، صندوق‌ها **۹**، نقره **۴**، و **۱** یافته مشترک طلا/صندوق (GS-01).

## بحرانی (۵)

| id | حوزه | فایل:خط | یافته | وضعیت شواهد |
|---|---|---|---|---|
| GS-01 | طلا/صندوق | `src/gold_desk/nav_checker.py:45` | `select(NavRecordModel.nav)` روی مدلی بدون ستون `nav`؛ خطا بی‌صدا → ۰ از ۱۰ صندوق | اجراشده |
| GS-02 | طلا | `src/gold_desk/constants.py:57` | سقف امتیاز واقعی ۵۳ < YELLOW(۵۵) → decision هرگز GREEN/YELLOW | اجراشده |
| GS-03 | طلا | `src/gold_desk/backtest.py:39` | cutoff میلادی در برابر ستون شمسی → ۰ ردیف → backtest همیشه «no data» | اجراشده |
| GS-04 | صندوق | `services/fund_nav_engine.py:303` | کسر مضاعف بدهی در مسیر fallback → NAV/unit ‎−۱۱.۱٪ | اجراشده |
| GS-05 | طلا | `src/gold_desk/pricer.py:78` | `IR_GOLD_MELTED` گرمی محاسبه و مثقالی قیمت‌گذاری می‌شود → حباب +۳۱۲.۶۵٪ | اجراشده |

## بالا (۷)

| id | حوزه | فایل:خط | یافته | وضعیت شواهد |
|---|---|---|---|---|
| GS-06 | طلا | `src/gold_desk/signal_engine.py:44` | XAUUSD/USD/DXY در `brsapi_gold_coin_history` صفر ردیف → RSI دائماً None (۱۵ امتیاز صفر) | اجراشده |
| GS-07 | طلا | `src/gold_desk/snapshot_service.py:139` | کل محاسبهٔ تغییرات روزانه در `suppress` → hard stop هیچ‌گاه فعال نمی‌شود | اجراشده |
| GS-08 | صندوق | `services/fund_nav_engine.py:196` | `cash_and_equivalents` خوانده و هرگز جمع نمی‌شود | اجراشده |
| GS-09 | نقره | `frontend/src/app/markets/silver/page.tsx:143` | صندوق‌های نقره `tse` هستند و صفحه `market=ime` می‌پرسد → ۰ نتیجه | اجراشده |
| GS-10 | صندوق | `services/fund_nav_engine.py` | ورودی‌های واقعی صفر: holdings=0، reports=0، history=1، runs=1 | اجراشده |
| GS-11 | صندوق | `services/fund_nav_reconciliation.py:167` | مرجع بدون فیلتر تاریخ → تطبیق تاریخی هرگز COMPARABLE نیست | اجراشده |
| GS-12 | طلا | `src/gold_desk/antigravity/assets.py:66` | عیار ۰.۹۱۵ در برابر ۰.۹۰۰ → حباب سکه ۵.۰۰٪ در برابر ۳.۳۰٪ | اجراشده |

## متوسط (۱۲)

| id | حوزه | فایل:خط | یافته | وضعیت شواهد |
|---|---|---|---|---|
| GS-13 | طلا | `src/gold_desk/alert_engine.py:121` | جهت عملگر پیام از علامت threshold → «> 3.00» برای قانون `bubble_below` | اجراشده |
| GS-14 | طلا | `src/gold_desk/constants.py:67` | سه مجموعه آستانهٔ P/NAV متناقض (۰.۵/۱.۵/۳.۰ ، ±۲/‎−۱ ، ±۳/‎−۲) | اجراشده |
| GS-15 | طلا | `src/gold_desk/snapshot_service.py:283` | میانگین سادهٔ BPR + شرط خط ۲۸۵ کد مرده | اجراشده |
| GS-16 | طلا | `src/gold_desk/nav_checker.py:79` | آخرین ردیف real/legal بدون سقف تازگی («عیار» ~۳ هفته قدیمی) | اجراشده |
| GS-17 | طلا | `src/gold_desk/portfolio.py:79` | قیمت ناموجود → `avg_buy` → PnL صفر کاذب | خوانده‌شده |
| GS-18 | طلا | `src/gold_desk/auto_trade.py:158` | سقف ثابت ۵۰M نادیده‌گیرندهٔ config؛ dry-run با `quantity=0`؛ live = placeholder | اجراشده |
| GS-19 | طلا | `src/gold_desk/forecaster.py:179` | باند بدون کران (lower منفی)؛ `_forecast_ema_trend` بدون EMA | اجراشده |
| GS-20 | طلا | `src/gold_desk/constants.py:110` | `IR_GOLD_1G` و `IR_COIN_GERAMI` در منبع غایب → ۲ بلوک همیشه خالی | اجراشده |
| GS-21 | صندوق | `services/fund_nav_engine.py:95` | برچسب `LIVE` بدون سقف عمر؛ `price_at` ذخیره و بی‌استفاده | اجراشده |
| GS-22 | صندوق | `services/fund_nav_engine.py:311` | coverage=۱۰۰٪ و کیفیت COMPLETE بدون هیچ قیمت‌گذاری مستقل | خوانده‌شده |
| GS-23 | صندوق | `services/fund_scoring.py:336` | پرش ۱۵ امتیازی در آستانه‌های style_drift / tracking_diff و ۵.۳ در ter | اجراشده |
| GS-24 | نقره | `apps/api/endpoints/brsapi.py:69` | `limit=2000` پارامتری ندارد → ۱۸٬۵۳۲ ردیف دانلود؛ docstring «Latest» نادرست | اجراشده |

## پایین (۶)

| id | حوزه | فایل:خط | یافته | وضعیت شواهد |
|---|---|---|---|---|
| GS-25 | نقره | `frontend/.../silver/components/helpers.ts:31` | `isGoldText` شامل «زر» → حذف کاذب ردیف‌های نقره/کالایی | خوانده‌شده |
| GS-26 | طلا | `src/gold_desk/scorer.py:146` | متن حاوی «偏离» چینی و ظهور آن در خروجی واقعی | اجراشده |
| GS-27 | طلا | `src/gold_desk/metrics.py:19` | شمارنده‌های گلوبال بدون قفل؛ `_percentile` کوانتیل واقعی نیست | خوانده‌شده |
| GS-28 | طلا | `backtesting/costs/gold_costs.py:24` | کران‌های ۰.۲٪/۲٪ اسپرد هرگز فعال نمی‌شوند (بدون ورودی نوسان) | خوانده‌شده |
| GS-29 | طلا | `backtesting/costs/gold_costs.py:21` | سه مدل هزینهٔ طلا بدون SSOT (۰.۵٪ / ۰.۱۵٪ / مدل عمومی) | خوانده‌شده |
| GS-30 | نقره | `scripts/sync_gold_silver_sectoral_intraday.py:78` | نماد با تیک قبلی هرگز دوباره sync نمی‌شود؛ نماد خالی هر اجرا تکرار | خوانده‌شده |

## اطلاعاتی (۳)

| id | حوزه | فایل:خط | یافته | وضعیت شواهد |
|---|---|---|---|---|
| GS-31 | صندوق | `services/fund_nav_engine.py:391` | ~۱۰۰ خط درج SQL تکراری بین دو متد | خوانده‌شده |
| GS-32 | صندوق | `services/fund_nav_reconciliation.py:290` | `datetime.utcnow()` naive در SLA و نسخهٔ آستانه | خوانده‌شده |
| GS-33 | طلا | `src/gold_desk/models.py` | همهٔ جداول `gold_*` در DB زنده صفر ردیف → هیچ مسیر GoldDesk در محیط واقعی اجرا نشده | اجراشده |

---

# پیوست ب — شواهد خام و بازتولید

## ب۱. اسکریپت‌های ممیزی (جدید؛ هیچ فایل موجودی تغییر نکرده)

| فایل | کارکرد |
|---|---|
| `audit_out/_tmp/gold_silver_funds_probe.py` | اجرای واقعی کد طلا/آنتی‌گولای/صندوق (عیار، آستانه‌ها، alert، `compute_nav`، forecaster، fund_scoring، auto_trade) |
| `audit_out/_tmp/gold_silver_funds_db_probe.py` … `probe6.py` | فقط SELECT: تقویم تاریخ‌ها، پوشش صندوق‌ها، جداول `gold_*`/`fund_*`، مسیر `/funds`، منابع قیمت |
| `audit_out/_tmp/gold_desk_snapshot_probe7.py` | اجرای واقعی `build_snapshot()` روی DB زنده (فقط SELECT) + سقف امتیاز |

## ب۲. خروجی‌های خام

```
audit_out/_logs/gold_silver_funds_probe.out      # بخش‌های ۱–۷ (عیار، آستانه، alert، NAV، باند، نمره، مبلغ)
audit_out/_logs/gold_silver_funds_db.out         # نمادها و تاریخ‌های brsapi_gold_coin_history + فهرست جداول + بخش F (بازتأیید شمارش fund_nav_history=1 با جزئیات tse:آگاس)
audit_out/_logs/gold_silver_funds_db2.out        # cutoff میلادی/شمسی، صندوق‌های طلا، شمارش جداول، XAUUSD
audit_out/_logs/gold_silver_funds_db3.out        # نمادهای نقره، ستون‌های funds، خالی‌بودن gold_snapshots
audit_out/_logs/gold_silver_funds_db4.out        # merged funds (۶۳۶)، صندوق نقره (۳، همه tse)، منابع قیمت
audit_out/_logs/gold_silver_funds_db5.out        # XAUUSD/XAGUSD در برsapi_commodity_prices (۴۶۳۳ ردیف هر کدام)
audit_out/_logs/gold_silver_funds_db6.out        # brsapi_nav_records: فقدان ستون nav، پوشش ۱۰ صندوق طلا
audit_out/_logs/gold_desk_snapshot.out           # اجرای واقعی build_snapshot + سقف امتیاز ۵۳
audit_out/_logs/gold_desk_pytest.log             # ۱۴۹ passed
audit_out/_logs/funds_unit_pytest.log            # ۲۸۱ passed, ۱ skipped
audit_out/_logs/gold_funds_api_pytest.log        # ۱۶۵ passed, ۲۱ skipped
audit_out/findings_gold_silver_funds.csv         # ۳۳ یافته در قالب CSV
```

## ب۳. فرمان‌های بازتولید

```bash
# آزمون‌ها
PYTHONUTF8=1 venv/Scripts/python.exe -m pytest tests/gold_desk -q
PYTHONUTF8=1 venv/Scripts/python.exe -m pytest tests/unit/services -q -k fund

# اجرای واقعی مسیر GoldDesk روی DB (فقط SELECT)
PYTHONUTF8=1 venv/Scripts/python.exe audit_out/_tmp/gold_desk_snapshot_probe7.py

# کاوش‌های DB (فقط SELECT)
PYTHONUTF8=1 venv/Scripts/python.exe audit_out/_tmp/gold_silver_funds_db_probe2.py
PYTHONUTF8=1 venv/Scripts/python.exe audit_out/_tmp/gold_silver_funds_db_probe4.py
```

DB استفاده‌شده: `postgresql+asyncpg://<user>@localhost:5432/my_first_db` (از `.env`) — **هیچ INSERT/UPDATE/DELETE اجرا نشد؛ فقط SELECT**.

## ب۴. بندهای انجام‌نشده (به‌عنوان «پاس» گزارش نمی‌شوند)

- اجرای frontend (Playwright/Next) برای تأیید بصری خالی‌بودن بخش صندوق نقره — استنتاج GS-09 از کد صفحه + پاسخ واقعی `_load_merged_funds` است، نه از اجرای مرورگر.
- اجرای `apps/funds` (سرویس مستقل FastAPI) و endpointهای `/gold/*` روی HTTP — فقط کد و منطق بررسی شد؛ `tests/unit/api/test_golddesk_http.py` و تست‌های funds API سبز هستند ولی مسیرهای زندهٔ scheduler/worker اجرا نشد.
- اندازه‌گیری عملکرد (زمان پاسخ `/brsapi/commodities` با ۱۸٬۵۳۲ ردیف) — حجم داده و غیبت `limit` روی کد تأیید شد، اما زمان پاسخ اندازه‌گیری نشد.
- بررسی تاریخچهٔ گیت برای رمز/کلید در فایل‌های این حوزه انجام نشد.
