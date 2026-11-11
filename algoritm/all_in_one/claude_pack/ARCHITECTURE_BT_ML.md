# ARCHITECTURE_BT_ML — معماری کامل لایه‌ی بک‌تست و ML (بازار ایران)

> وابسته به: `ARCHITECTURE.md`، `SPEC_BACKTEST.md`، `SPEC_ML.md`، `SPEC_IRAN_MARKET.md`، `SPEC_VALUATION.md`، `CLAUDE.md`.
> در تعارض: `CLAUDE.md` ← `SPEC_*` ← `ARCHITECTURE.md` ← این سند. هیچ عدد قانونی/آستانه‌ی پذیرش در این سند نیست (همه از `rule_at()` و `acceptance.yaml`).
> هر ردیف «چرا» به یافته‌ی ممیزی (`AUDIT_STAGE0.md`) یا بخشی از SPEC ارجاع دارد.

---

## ۰. اصول طراحی (غیرقابل‌مذاکره)

1. **یک مسیر مرجع، یک مدل هزینه.** فقط یک موتور «عدد قابل‌گزارش» تولید می‌کند؛ مسیر سریع فقط غربال‌گری است و هزینه و گارد دارد. *(چرا: سه موتور با نتایج متناقض، A-06)*
2. **زمان قبل از همه چیز.** هر خواندن داده با `knowledge_time ≤ decision_time`؛ هر اجرا بعد از `decision_time`. *(B-04، C-01)*
3. **قانون داده است.** هیچ عدد بازار در کد؛ فقط `rule_at(key, scope, date)`. قاعده‌ی بدون منبع سطح D است و اعتبار نتیجه را پایین می‌آورد. *(C-02، C2)*
4. **long-only پیش‌فرض.** سفارش فروش بدون پوزیشن رد می‌شود؛ «سیگنال نزولی» = خروج/کاهش وزن. *(`SPEC_IRAN_MARKET` ۱)*
5. **اجرا‌پذیری یک مفهوم درجه‌یک است.** `fillable_rate`، `unfillable`، `days_to_exit` در خروجی هر نتیجه‌اند. *(قفل/صف)*
6. **اندازه‌گیری مستقل از استراتژی تأیید می‌شود.** هر موتور/گزارش با کنترل مثبت (آینده‌بین هم‌تراز) و منفی (تصادفی هم‌نوسان) اعتبارسنجی می‌شود، پیش از اینکه به نتیجه‌ی استراتژی اعتماد شود. *(B-01)*
7. **ML فقط مصرف‌کننده‌ی داده و موتور درست است.** مدل بعد از R1–R4 آموزش می‌بیند؛ پذیرش فقط با `acceptance.yaml`. *(F-01، F-02)*
8. **هر نتیجه یک «درجه‌ی اعتماد» دارد** که ماشینی از گیت‌ها محاسبه می‌شود (بخش ۱۰)؛ نتیجه‌ی بدون درجه گزارش نمی‌شود.
9. **سه معیار و بنچمارک** برای هر نتیجه: اسمی، واقعی، دلاری. *(تورم/ارز)*
10. **نمونه‌ی مستقل کم است.** `N_eff`، `n_epochs`، leave-one-epoch-out اجباری‌اند. *(`SPEC_IRAN_MARKET` ۱۴)*
11. **بازتولیدپذیری.** `run_manifest` برای هر اجرا؛ دو اجرای یکسان ⇒ خروجی bit-identical.
12. **تعلیق به‌جای حدس.** داده‌ی `none/unknown` ⇒ ماژول `suspended`؛ هرگز داده/قاعده‌ی جایگزین ساخته نمی‌شود.

---

## ۱. نمای کلی

```
 ┌───────────── منابع ─────────────┐
 │ قیمت، حقیقی/حقوقی، رویداد شرکتی،  │
 │ کدال، NAV، ارز/سکه/اونس، عمق/صف  │
 └──────────────┬──────────────────┘
                ▼
      Ingestion → raw → clean → adjusted → curated            (لایه‌ی داده، بخش ۳)
                │                │
                │        PIT Store (bitemporal, knowledge_time)
                ▼                ▼
   ┌──────────────────┐   ┌──────────────────┐   ┌───────────────────┐
   │ Rules / Calendar │   │  Feature Store   │   │  Event Store      │
   │ rule_at, epochs  │   │  PIT, versioned  │   │  (کدال/اخبار)      │
   └────────┬─────────┘   └────────┬─────────┘   └─────────┬─────────┘
            │                      ▼                       │
            │            Label Factory (قابل‌اجرا) ◄─────────┘
            │                      ▼
            │              Dataset Builder (universe PIT, purge/embargo)
            │                      ▼
            │              Model Zoo + Training Orchestrator + Trial Registry
            │                      ▼
            │              Evaluation (IC/AUC/دهک) + Leakage Guards
            │                      ▼
            │                  Signals  (scores، احتمال‌ها، meta-label)
            ▼                      ▼
   ┌────────────────────────────────────────────────────────────────┐
   │  Portfolio & Risk (تخصیص، قیود، توقف‌ها، joint-lock stress)      │
   └───────────────────────────────┬────────────────────────────────┘
                                   ▼  Orders
   ┌────────────────────────────────────────────────────────────────┐
   │  موتور مرجع (event-driven kernel)                               │
   │  Clock/Phases → OrderManager → ExecutionModel → Ledger          │
   │  CorporateActionProcessor · CostModel · ExitRisk · MTM          │
   └───────────────────────────────┬────────────────────────────────┘
                                   ▼
   Metrics → Validation (DSR/PBO/bootstrap/stress) → Report → Registry
                                   ▼
   Trust Grade  →  shadow → paper → live_small → live  (چرخه‌ی عمر)
```

**مسیر سریع (fast path):** فقط بین Signals و Metrics قرار می‌گیرد، با همان CostModel و گارد؛ خروجی‌اش هرگز گزارش نهایی نیست (بخش ۵.۸).

---

## ۲. هسته‌ی زمان و رویداد

### ۲.۱ ساعت و فازها
- ساعت شبیه‌سازی برای هر `(market, segment)` فازها را از `rule_at('session_phases')` می‌گیرد: `pre_open → opening_auction → continuous → post_close → settlement_run → eod_mark`.
- رویداد: `(ts, priority, seq, type, payload)`؛ ترتیب با `(ts, priority, seq)` ثابت و قطعی.
- `market_status(date, segment) ∈ {open, closed_holiday, closed_unscheduled, halted_symbol}`؛ تعطیلی برنامه‌ریزی‌نشده یک وضعیت درجه‌یک است.

### ۲.۲ سه زمان
| نام | تعریف |
|---|---|
| `decision_time` | لحظه‌ای که همه‌ی داده‌ی لازم با `knowledge_time ≤ decision_time` موجود است |
| `earliest_exec_time` | اولین فاز اجرایی مجاز **بعد از** `decision_time + delay`؛ در همان کندل/روز تصمیم ممنوع |
| `settle_time` | `add_business_days(trade_date, rule_at('settlement_days'))` با تقویم همان بازار؛ در تعطیلی غیرعادی به اولین روز کاری پس از بازگشایی |

### ۲.۳ نگهبان زمان
`TimeGuard` در لایه‌ی دسترسی به داده: هر `get(dataset, asof)` رکوردی با `knowledge_time > asof` برنمی‌گرداند؛ تلاش برای خواندن آینده یک `LookAheadError` است (نه هشدار). این گارد برای **همه‌ی مسیرها** از جمله fast path و ساخت فیچر/برچسب اجباری است.

---

## ۳. لایه‌ی داده برای بک‌تست و ML

### ۳.۱ PIT Store
- رابط واحد: `store.read(dataset, instrument_ids, start, end, asof)`؛ خروجی با پرچم‌های `knowledge_time_assumed`، `stale`، `dq_flag`.
- لایه‌ها: `raw → clean → adjusted → curated`؛ بک‌تست فقط `curated` را می‌بیند.
- **تاریخ معامله (`trade_date`) جدا از تاریخ ingest.** هیچ فیلتر زمانی روی ستون ingest نیست. *(G-01، G-02)*
- **تعدیل:** ضریب از `corporate_actions` (شامل سود نقدی)؛ مصرف‌کننده‌ی پیش‌فرض سری **تعدیل‌شده** است؛ سری خام فقط برای ارزش‌گذاری اسمی/اجرا و با درخواست صریح. *(C-04، C-05)*
- **universe PIT:** `universe_log(date, instrument_id, in_universe, reason)` شامل نمادهای حذف‌شده/تغییر نام‌یافته؛ فیلتر نقدشوندگی با داده تا T. *(C-08)*

### ۳.۲ DQ Gate
هر مجموعه‌داده DQ Score دارد؛ بک‌تست روی داده‌ی زیر آستانه هشدار/توقف می‌دهد. چک‌ها: low≤open,close≤high، قیمت در دامنه‌ی `rule_at` همان روز، سوراخ تقویمی، روز تعطیل با معامله، افت ex-date سود نسبت به مقدار سود، اختلاف با منبع دوم.

### ۳.۳ ماتریس پوشش و تعلیق
ماتریس `SPEC_DATA_SOURCES` منبع حقیقت است: هر ماژول وابسته به مجموعه‌ی `none/unknown` به‌صورت خودکار `status: suspended` با دلیل در `run_manifest` می‌آید.

---

## ۴. قوانین، epoch و اعتماد

- `rules(rule_key, scope, value, effective_from, effective_to, source_ref, confidence, knowledge_time)`؛ تنها دسترسی: `rule_at(key, scope, date)`؛ هم‌پوشانی بازه‌ها ⇒ خطا.
- **scope resolution:** `symbol > segment > market > global`؛ استثناها (بازار پایه، صندوق‌ها، بازارگردان‌دار) ردیف صریح.
- **`regime_epoch`:** هر تغییر مهم قانون (دامنه، حجم مبنا، ساعت، سقف سفارش، تعطیلی بلندمدت) یک epoch جدید؛ شناسه‌ی epoch به داده/فیچر/برچسب/گزارش الصاق می‌شود.
- `policy_events` به‌عنوان رویداد ساختاریافته با زمان انتشار.
- **اثر روی اعتماد:** `run_manifest.rules_confidence_min` = کمترین سطح اطمینان قوانین استفاده‌شده. هر قاعده‌ی سطح D ⇒ گیت «قوانین» در بخش ۱۰ شکست می‌خورد.
- **تست تطبیق:** تغییر روزانه‌ی واقعی هر نماد با دامنه‌ی ثبت‌شده‌ی همان روز سازگار باشد؛ ناسازگاری یعنی خطای جدول یا استثنای ناشناخته.

---

## ۵. موتور مرجع بک‌تست

### ۵.۱ مؤلفه‌ها
| مؤلفه | وظیفه | ورودی ⇒ خروجی |
|---|---|---|
| `Clock` | فازها و ترتیب رویداد | تقویم + `rule_at` ⇒ رویدادها |
| `MarketState` | قیمت‌های مجاز، وضعیت قفل/توقف/صف (در حد داده) | PIT Store ⇒ وضعیت در لحظه |
| `OrderManager` | چرخه‌ی عمر سفارش و اعتبارسنجی | Order ⇒ ACCEPTED/REJECTED(reason) |
| `ExecutionModel` | fill (بخش ۵.۳) | Order + MarketState ⇒ Fills |
| `CostModel` | کارمزد/مالیات/لغزش/اثر قیمت | Fill ⇒ هزینه‌ی تفکیکی |
| `Ledger` | دفتر دوطرفه، بلوکه، تسویه، بقا | JournalEntries |
| `CorporateActionProcessor` | رویدادهای `ex_date` قبل از بازشدن | جدول رویداد ⇒ تغییر پوزیشن/نقد/قیمت مرجع |
| `ExitRisk` | `days_to_exit`، `exit_blocked_today`، سناریوی صف فروش پایدار | پوزیشن + ADV ⇒ ریسک خروج |
| `Valuator` | MTM روزانه با `valuation_price`، `stale` برای توقف | پوزیشن + قیمت ⇒ equity |
| `Recorder` | جدول‌های خروجی و `run_manifest` | همه ⇒ Parquet |

### ۵.۲ چرخه‌ی سفارش و رد
`NEW → ACCEPTED → WORKING → PARTIALLY_FILLED → FILLED | CANCELLED | EXPIRED`، یا `REJECTED(reason)`.
دلایل رد: `MARKET_CLOSED, SYMBOL_HALTED, PRICE_OUTSIDE_LIMIT, BELOW_TICK, BAD_LOT, INSUFFICIENT_CASH, INSUFFICIENT_MARGIN, POSITION_LIMIT, ORDER_SIZE_LIMIT, NOT_TRADABLE_IN_PHASE, NO_SHORT_ALLOWED`.
**سایز فروش** همیشه از پوزیشن باز (`ledger.position(instr)`) محاسبه می‌شود، نه از نقد. *(A-03)*

### ۵.۳ مدل‌های پرشدن
| مدل | کاربرد | رفتار |
|---|---|---|
| `idealized` | فقط تست واحد؛ برچسب `NOT_REALISTIC` | پر شدن کامل |
| `conservative_ohlc` | پیش‌فرض با داده‌ی روزانه | خرید limit پر می‌شود اگر `low ≤ limit` **و** روز در سمت خرید قفل‌نشده؛ حجم ≤ `participation_cap × volume`؛ قیمت بدتر از VWAP با لغزش |
| `queue_v1` | با داده‌ی عمق/صف | `filled(t) = clip(V_exec(t) − Q_ahead, 0, qty)`؛ بدون داده‌ی صف: ورود در سمت قفل = `unfillable` |
| `auction` | فقط مشاهده تا تأیید قانون | سفارش در مزایده اجرا نمی‌شود |

قواعد تغییرناپذیر:
- **هیچ پر شدنی روی قیمت کندل تصمیم.** *(C-01)*
- **بدون داده‌ی صف و در سمت قفل ⇒ `unfillable`**، نه پر شده، نه «نیمه‌پر».
- تا کالیبراسیون با `own_order_log`: `fill_model_calibrated = false` و هر خروجی `UNCALIBRATED`.
- `assume_front_of_queue_fraction` فقط برای تحلیل حساسیت (پیش‌فرض ۰).

### ۵.۴ هزینه
```
cost = notional × (commission[RULE] + exchange_fee[RULE] + depository_fee[RULE])
     + (SELL ? notional × sell_tax[RULE] : 0) + slippage + impact
slippage = notional × s0 × f(liquidity_bucket)           # کالیبره، پیش‌فرض بدبینانه
impact   = notional × k × σ_daily × sqrt(qty / ADV)      # k کالیبره
cap      : qty ≤ cap × ADV                                # cap از config
```
- **تنها یک `CostModel`** برای همه‌ی مسیرها؛ نرخ‌ها فقط از `rule_at`.
- `ADV` از `trade_volume` تعدیل‌شده و روی `trade_date`؛ pre-warm اجباری؛ **افت به مقدار پیش‌فرض هرگز بی‌صدا نیست** (خطا یا `adv_fallback=true` در خروجی). *(G-04)*
- `cost_stress_multiplier` (۱× و ۲×) در config.

### ۵.۵ دفتر حسابداری و تسویه
حساب‌ها: `CASH_FREE, CASH_BLOCKED_ORDERS, MARGIN_BLOCKED[instr], SETTLE_RECV[date], SETTLE_PAY[date], POSITION[instr] (lot-level), DIV_RECV[date], FEES, TAX, EQUITY`.
ثابت‌ها: تراز همیشه صفر؛ وجه فروش قبل از `settle_date` قابل‌استفاده نیست؛ در نبود هزینه، `EQUITY` فقط با قیمت و رویدادهای شرکتی عوض می‌شود.

### ۵.۶ رویدادهای شرکتی
در `ex_date` قبل از بازشدن، به ترتیب: سود نقدی (`DIV_RECV`)، تجزیه/ادغام، افزایش سرمایه، حق تقدم. `adj_factor` از جدول رویداد؛ **تطبیق با سری رسمی/منبع دوم** و گزارش اختلاف. حق تقدم: پیش‌فرض بدبینانه (فروش حق یا رها).

### ۵.۷ حالت‌های ایران‌محور
- **قفل خرید/فروش:** وضعیت `lock_up/lock_down` از `MarketState`؛ `lock_streak`؛ سفارش در سمت قفل طبق ۵.۳.
- **بازده سانسورشده:** بازده روز قفل نماینده‌ی «قیمت قابل‌معامله» نیست؛ برچسب و فیچر جدا (بخش ۷.۳).
- **توقف/تعطیلی طولانی:** پوزیشن قابل‌خروج نیست؛ MTM با `stale=true` و (اختیاری) `stale_haircut`؛ شکاف در بازگشایی ثبت؛ روزهای تعطیل از آمار نوسان/شارپ حذف (نه صفر).
- **ریسک خروج سیستماتیک:** `joint_lock_stress` (صف فروش هم‌زمان چند پوزیشن)؛ `market_lock_share_daily`.
- **حدس‌های رفتاری [H]** (شناوری، بازارگردان، عرضه اولیه) فقط فیچر/فیلتر با تست آماری؛ نه قاعده‌ی کد.

### ۵.۸ مسیر سریع (Vectorized)
- هدف: جستجوی گسترده/ML؛ فرض‌های ساده.
- **الزامات:** (۱) همان `CostModel` (پارامتر هزینه اجباری)؛ (۲) رد سیگنال منفی (`NO_SHORT_ALLOWED`) مگر `short_allowed`؛ (۳) گارد منشأ سیگنال: بازتولید سیگنال روی داده‌ی بریده تا t-۱ و مقایسه (تست truncation)؛ (۴) `execution lag ≥ 1` جلسه.
- **پذیرش:** نتیجه‌ی امیدوارکننده باید در موتور مرجع بازاجرا و در تلورانس ثبت‌شده منطبق شود (تست parity). *(A-06، B-05)*
- خروجی با برچسب `FASTPATH_SCREENING` و بدون «درجه‌ی اعتماد».

### ۵.۹ قطعیت
یک `seed` سراسری؛ هر مؤلفه‌ی تصادفی RNG جدا (`seed + component_id`)؛ دو اجرا ⇒ خروجی یکسان.

---

## ۶. پورتفوی و ریسک

- **تخصیص:** هدف نوسان، Kelly کسری، HRP، حداقل واریانس با shrinkage؛ بهینه‌ساز آگاه از هزینه‌ی گردش.
- **قیود:** سقف سهم/صنعت/نقدشوندگی؛ `participation_cap`؛ `max_avg_days_to_exit`؛ سرمایه‌ی آزاد پس از ضمانت.
- **ریسک:** VaR/CVaR، ریسک نقدشوندگی و رژیم، تحلیل عوامل (بازار/اندازه/ارزش/مومنتوم)، `beta` به بازار.
- **توقف‌ها:** سقف ضرر روزانه/ماهانه، drawdown، کلید توقف دستی.
- **long-only:** وزن منفی ممنوع؛ خروجی «زیان اجتناب‌شده» برای سیگنال‌های خروج.
- مؤلفه‌ی «۱۰ دروازه‌ی سیگنال» فعلی (`signal_decision_engine`) در این لایه‌ی `portfolio/gates` فقط **پس از** عبور baseline و با دروازه‌ی ۹ fail-closed فعال می‌شود (تعلیق تا آن موقع).

---

## ۷. معماری ML

### ۷.۱ Feature Store
- هر فیچر: `name, group, definition, window, inputs, knowledge_time_rule, version, leakage_test`.
- بسته‌ها: قیمت/بازده، نقدشوندگی، جریان پول (حقیقی/حقوقی)، بنیادی (زمان انتشار)، صندوق/NAV، بازار/ارز/کالا، مشتقه، رویداد، تقویم.
- **فیچرهای قفل (ایران):** `lock_up_today, lock_down_today, lock_streak, limit_up_days_k, limit_down_days_k, market_lock_share_daily`.
- نرمال‌سازی **مقطعی روزانه** (rank→gaussian/z robust)؛ winsorize با کران‌های تا T؛ مقدار گمشده: `is_missing` + جایگزین مقطعی؛ «گزارش هنوز منتشر نشده» نباید نشت‌دهنده باشد.
- کش با کلید hash(تعریف+داده). **ورود فیچر بدون `knowledge_time_rule` رد می‌شود.**

### ۷.۲ گارد نشت در خط لوله (نه فقط تست)
`FeatureGuard` در زمان محاسبه: هر فیچر با ورودی‌ای که `knowledge_time > asof` دارد ⇒ خطا. تست‌های دائمی: **canary** («بازده فردا» باید توسط گارد گرفته شود)، **shift**، **label shuffle**، **knowledge_time audit**، **fold audit**، **universe audit**. *(F-04)*

### ۷.۳ Label Factory
| برچسب | تعریف | نکته‌ی ایران |
|---|---|---|
| T1/T2 | بازده افق h از **قیمت قابل‌اجرا** (`open[t+1]`→`open[t+1+h]` با هزینه) | هرگز `close[t]`؛ *(C-06)* |
| T3 | triple-barrier `m×σ_k`، انقضا h | عبور مرز در روز قفل ⇒ خروج با قیمت قابل‌اجرای روز بعد |
| T4 | احتمال معامله‌پذیری/خروج‌پذیری | از `fillable`/`days_to_exit`/توقف |
| T5 | نوسان آینده | — |
| T6 | تغییر حباب (صندوق‌ها) | وابسته به داده‌ی NAV (تعلیق در نبود) |
| T7 | meta-label (سیگنال پایه خالص هزینه سودآور بود؟) | — |
- ورود در روز قفل خرید یا نماد متوقف ⇒ نمونه حذف یا `untradable`.
- وزن نمونه ∝ یکتایی میانگین (average uniqueness)؛ ذخیره‌ی دو نسخه‌ی ناخالص/خالص.

### ۷.۴ Dataset Builder
universe PIT؛ فیلتر نقدشوندگی از config؛ `universe_log`؛ تفکیک کلاس دارایی (سهام/صندوق/اوراق/آپشن/کالا‌ارز)؛ **purge + embargo ≥ افق h**؛ شناسه‌ی `regime_epoch` روی هر نمونه.

### ۷.۵ Model Zoo و چرخه‌ی عمر
1. baseline: قوانین ساده + رگرسیون خطی/لجستیک؛ 2. درخت‌ها (LightGBM/XGBoost)؛ 3. سری زمانی (GARCH/HMM/VECM)؛ 4. عمیق فقط پس از شکست baseline درختی؛ 5. ensemble + calibrator فقط پس از پذیرش مدل پایه.
```
candidate → shadow → paper → live_small → live → retired
```
ارتقا فقط با گیت‌ها (بخش ۱۰)؛ بازگشت خودکار به `shadow` با افت IC برای K دوره، drift شدید، افزایش tracking error، یا تغییر قانون که فرض مدل را نقض کند (ماشه‌ی `regime_epoch`).
**هر مدل:** `model_card` (داده، فیچرها، دوره، epochها، معیارها، قوانین فعال هنگام آموزش، محدودیت‌ها) و `run_manifest`. مدل بدون این دو `UNVERIFIED` است (وضعیت فعلی ۳۵۹ مدل). *(F-01، F-02)*

### ۷.۶ Training Orchestrator
- walk-forward تو در تو (expanding و rolling)؛ **Optuna/Grid فقط داخل fold آموزشی**؛ fold ارزیابی هرگز در انتخاب پارامتر نقش ندارد.
- CPCV اختیاری برای توزیع مسیرها/PBO؛ **TimeSeriesSplit/CPCV به‌جای KFold معمولی**. *(C-07)*
- `TrialRegistry`: هر آزمایش (فرضیه، پارامتر، seed، نتیجه) ثبت و شمرده می‌شود؛ `n_trials` به DSR تغذیه می‌شود.
- **Hold-out یک‌نگاهی:** زمان و نسخه‌ی مدل هنگام دیدن ثبت؛ بعد از آن تغییر برای همان فرضیه ممنوع (فرضیه‌ی جدید = شمارش جدید).

### ۷.۷ ارزیابی
- آماری روزانه: IC، Rank IC، `ICIR`، درصد روز مثبت؛ طبقه‌بندی: AUC، log-loss، Brier، منحنی کالیبراسیون؛ ده‌ک‌ها؛ MAE/RMSE.
- **Rank IC مقطعی فقط با N نماد کافی** (با N بسیار کم گزارش نمی‌شود).
- اقتصادی: همیشه از موتور مرجع (نه از IC)؛ بازده خالص سه‌معیاره، Sharpe/Sortino، MDD، turnover، ظرفیت، `days_to_exit`، تمرکز سود، `fillable_rate` به‌تفکیک دهک امتیاز.
- مقایسه‌ی زوجی با BL-1..BL-3 و bootstrap بلوکی (بلوک بلند).

### ۷.۸ پایش
drift فیچر (PSI/KS هفتگی نسبت به آموزش و ۳ ماه اخیر)؛ توزیع امتیاز؛ IC و کالیبراسیون متحرک؛ شکاف paper-vs-backtest؛ هشدار خودکار با تغییر `rules` (epoch جدید).

### ۷.۹ بازآموزی
زمان‌بندی‌شده؛ مدل جدید فقط با برتری روی داده‌ی کنار‌گذاشته و عبور از گیت‌ها جایگزین می‌شود (فعلاً `_min_accuracy_gain` موجود حفظ و با مرحله‌ی shadow/paper تکمیل می‌شود). *(C-10)*

---

## ۸. لایه‌ی اعتبارسنجی آماری

| ابزار | کاربرد |
|---|---|
| DSR / PBO / White RC (SPA) | تصحیح تعداد آزمایش‌ها (با `N_eff`) |
| bootstrap بلوکی (بلوک بلند) | فاصله‌ی اطمینان پهن |
| `N_eff` | تعداد مؤثر نمادها از ماتریس همبستگی |
| `n_epochs` و leave-one-epoch-out | وابستگی به یک رژیم |
| تست‌های تخریبی | هزینه ×۲، تأخیر +۱ روز، shuffle، نویز قیمت، حذف بهترین ماه‌ها/بزرگ‌ترین نماد، پارامتر ±۲۰٪ |
| سناریوی تنش | جهش ارزی، موج صعود/ریزش، قیمت‌گذاری دستوری، بسته‌شدن طولانی، صف فروش پایدار |
| گزارش تفکیکی | رژیم/epoch/سال/صنعت |
| تفکیک beta/timing | بازده فراتر از بازار |

---

## ۹. گزارش و ثبت

### ۹.۱ گزارش استاندارد (یک قالب برای همه)
1. `run_manifest` و **درجه‌ی اعتماد** (بخش ۱۰).
2. سه معیار (اسمی/واقعی/دلاری) و بنچمارک‌ها (BL-1..BL-7 از `BASELINES.md`).
3. ریسک: MDD مطلق **و نسبی به buy-and-hold**، Sharpe/Sortino/Calmar، time-under-water.
4. اجرا‌پذیری: `fillable_rate` (دهک امتیاز)، `days_to_exit`، ظرفیت، `unfillable` و `rejections(reason)`.
5. هزینه‌ی تفکیکی (کمیسیون/مالیات/لغزش/اثر) با نرخ‌های `rule_at` و epoch.
6. آماری: DSR/PBO، `n_trials`، `N_eff`، `n_epochs`، leave-one-epoch-out، beta.
7. کنترل‌ها: نتیجه‌ی BL-3/BL-4/BL-5/BL-6 همان اجرا.
8. هشدارها: قوانین سطح C/D، داده‌ی `knowledge_time_assumed`، `adv_fallback`، `UNCALIBRATED`.
- متن روایتی فارسی از قالب؛ **هر عدد در متن با داده‌ی ساختاریافته تطبیق می‌شود**؛ عدد بی‌منبع ممنوع.

### ۹.۲ `run_manifest`
`experiment_id, hypothesis_id, data_hash, rules_hash, features_version, code_version, config_hash, seed, engine_id (reference|fastpath), fill_model, fill_model_calibrated, cost_model_version, universe_hash, epochs_covered, n_trials, rules_confidence_min, dq_score_min, suspended_modules, started_at, finished_at`.

### ۹.۳ جدول‌های خروجی
`orders, fills, rejections(reason), positions_daily, equity_daily(nominal, real, usd), exposures_daily, costs_breakdown, settlement_queue_daily, corporate_action_log, margin_log, exit_risk_daily, control_results, trust_gates, run_manifest`.

---

## ۱۰. درجه‌ی اعتماد نتیجه (Trust Grade)

هر گزارش گیت‌های زیر را محاسبه می‌کند (آستانه‌های عددی از `acceptance.yaml`/config؛ در این سند عدد نیست):

| گیت | شرط | بحرانی؟ |
|---|---|---|
| G1 قوانین | `rules_confidence_min` ≥ سطح مورد نیاز مالک؛ بدون placeholder | بله |
| G2 داده | `dq_score_min` ≥ آستانه؛ `trade_date`؛ سری تعدیل‌شده؛ سود نقدی موجود یا برچسب «بدون تعدیل سود» | بله |
| G3 زمان | `LookAheadError` صفر؛ canary گرفته می‌شود؛ shift بهتر نمی‌شود | بله |
| G4 کنترل‌ها | BL-3 منفی/نزدیک صفر؛ BL-4 منفی؛ BL-5 غیرعادی و رد‌شده؛ BL-6 بهتر نمی‌شود | بله |
| G5 parity | موتور مرجع با fast path (در صورت استفاده) در تلورانس | بله برای fastpath |
| G6 اجرا‌پذیری | `fillable_rate` گزارش شده؛ مدل صف کالیبره یا نتیجه `UNCALIBRATED` | خیر (برچسب) |
| G7 آماری | `n_trials` شمرده؛ DSR/PBO؛ `n_epochs`؛ leave-one-epoch-out | بله |
| G8 بنچمارک | سه معیار؛ برتری بر بنچمارک مناسب طبق `acceptance.yaml` | بله |
| G9 بازتولید | دو اجرا ⇒ hash یکسان | بله |

**درجه:** هر گیت بحرانی ناموفق ⇒ **«غیرقابل‌اتکا»**؛ همه‌ی بحرانی‌ها موفق و G6 `UNCALIBRATED` ⇒ **«قابل‌اتکا با محدودیت»**؛ همه موفق و کالیبره ⇒ **«قابل‌اتکا»**؛ گیتی که نتوان سنجید ⇒ **«نامشخص»**. درجه را کد حساب می‌کند، نه متن.

---

## ۱۱. رابط‌های کد (Protocol)

```python
class PITStore(Protocol):
    def read(self, dataset: str, ids: list[str], start: date, end: date, asof: datetime) -> DataFrame: ...

class RuleSet(Protocol):
    def rule_at(self, key: str, scope: Scope, on: date) -> RuleValue: ...      # value + confidence + source_ref

class ExecutionModel(Protocol):
    name: str; calibrated: bool
    def fill(self, order: Order, state: MarketState) -> list[Fill]: ...

class CostModel(Protocol):
    def cost(self, fill: Fill, ctx: CostContext) -> CostBreakdown: ...         # فقط از RuleSet

class Strategy(Protocol):
    def on_event(self, ev: Event, ctx: Context) -> list[Order]: ...            # ctx.position(...) برای سایز فروش

class FeaturePack(Protocol):
    name: str; version: str
    def compute(self, store: PITStore, asof: datetime) -> DataFrame: ...       # با FeatureGuard

class LabelFactory(Protocol):
    def build(self, kind: str, store: PITStore, exec_model: ExecutionModel, asof_end: date) -> DataFrame: ...

class Model(Protocol):
    def fit(self, X, y, w) -> None: ...
    def predict(self, X) -> Scores: ...

class Validator(Protocol):
    def run(self, result: BacktestResult, controls: ControlResults) -> TrustReport: ...
```
قانون: هیچ کلاسی مستقیم به فایل/اینترنت/DB دسترسی ندارد؛ فقط از طریق Store/Adapter.

---

## ۱۲. چیدمان پوشه‌ها و نگاشت از ریپوی فعلی (Strangler)

```
src/
  core/          # زمان، تقویم (جلالی/میلادی)، شناسه، TimeGuard، bitemporal
  rules/         # rules, rule_at, epochs
  data/          # adapters, ingestion, adjust, dq, universe
  features/      # packs + FeatureGuard
  models/        # labels, datasets, zoo, training, trial_registry, calibration, lifecycle, drift
  portfolio/     # allocation, constraints, risk, gates (suspended)
  execution/     # fill models, costs, queue, exit_risk
  backtest/      # kernel (clock, orders, ledger, corp_actions, mtm), fastpath
  validation/    # stats, controls, stress, trust_grade
  reports/       # standard report, narrative
tests/           # unit, property, golden, leakage, validity, integration
experiments/     # run_manifest + خروجی‌ها
```

| ماژول فعلی | مقصد | تصمیم |
|---|---|---|
| `backtesting/engine/backtest_engine.py` | `backtest/kernel` | مرجع پیشنهادی (پس از parity) |
| `backtesting/engine/simulator.py`, `broker.py` | `execution/` + legacy | بازنویسی اجرا/ADV؛ حفظ `cost_model` |
| `backtesting/costs/iran_costs.py`, `domain/trading/iran_costs.py` | `execution/costs` | حفظ فرمول، اتصال به `rule_at` |
| `services/backtest_framework.py` (Vectorized) | `backtest/fastpath` | بازنویسی (هزینه، گارد، رد short) |
| `services/backtest_framework.py` (CPCV، DSR) | `validation/stats` | حفظ و وصل |
| `services/signal_backtest_engine.py` | `validation/signal_eval` | **ارزیاب نتیجه‌ی سیگنال**، نه موتور؛ هزینه از CostModel؛ ستون `trade_date` |
| `backtesting/strategies/*` | `src/strategies` | اصلاح سایز فروش |
| `backtesting/metrics/*`, `analytics` | `reports/metrics` | حفظ + MDD نسبی + `profit_factor` یکسان |
| `backtesting/data/price_limits.py`, `market/rule_versioning.py` | `rules/` | مهاجرت به جدول |
| `ml/datasets/labeling.py` | `models/labels` | بازنویسی (قابل‌اجرا) |
| `ml/models/sweeper.py` | `models/training` | بازنویسی (purged/CPCV + trial registry) |
| `services/feature_engine.py` | `features/packs` | حفظ + `knowledge_time` + FeatureGuard |
| `ml/artifacts.py` + `ml_artifacts/` | `models/registry` | اصلاح مسیر؛ مدل‌ها `UNVERIFIED` |
| `services/auto_retrain_pipeline.py` | `models/lifecycle` | حفظ + shadow/paper |
| `services/quant_signal_orchestrator.py`, `signal_decision_engine.py` | `portfolio/gates` | تعلیق؛ دروازه‌ی ۹ fail-closed |

مهاجرت ماژول‌به‌ماژول با آداپتر؛ ماژول قدیم تا جایگزینی کامل کار می‌کند؛ خروجی جدید/قدیم مقایسه و اختلاف توضیح داده می‌شود.

---

## ۱۳. جریان یک اجرا

### ۱۳.۱ بک‌تست
1. بارگذاری config → `run_manifest` اولیه → `rules_hash/data_hash`.
2. ساخت universe PIT و بارگذاری داده‌ی `curated` (تعدیل‌شده) با `TimeGuard`.
3. تولید سیگنال‌ها (مدل یا قاعده) از فیچرهای تا `decision_time`.
4. پورتفوی ⇒ سفارش‌ها با `earliest_exec_time`.
5. موتور مرجع: رویدادها به ترتیب؛ OrderManager → ExecutionModel → CostModel → Ledger؛ رویدادهای شرکتی و تسویه؛ MTM.
6. کنترل‌ها (BL-3..BL-6) روی همان داده و موتور.
7. Metrics + Validation + Trust Grade.
8. گزارش + `run_manifest` نهایی + ثبت در Registry.

### ۱۳.۲ آموزش
1. فرضیه و `hypothesis_id` ثبت قبل از اجرا؛ `acceptance.yaml` خوانده می‌شود (فقط‌خواندنی).
2. Dataset Builder (universe PIT، purge/embargo، epoch).
3. Label Factory (قابل‌اجرا).
4. walk-forward تو در تو؛ هر آزمایش در `TrialRegistry`.
5. ارزیابی آماری + اقتصادی از موتور مرجع؛ کنترل‌های نشت.
6. `model_card` + ثبت در Registry با وضعیت `candidate`.
7. ارتقا به `shadow/paper/...` فقط با گیت‌ها.

---

## ۱۴. معماری تست

| سطح | آزمون‌های کلیدی |
|---|---|
| Unit | `rule_at` (مرزی/هم‌پوشان)، تبدیل جلالی/میلادی، `add_business_days`، CostModel، سایز فروش |
| Property (Hypothesis) | `filled ≤ qty`؛ پر شدن قبل از `t_submit` ممنوع؛ نقد قبل از `settle_date` غیرقابل‌استفاده؛ تراز دفتر صفر |
| Golden | ۱ تا ۳ نماد، چند ماه، محاسبه‌ی دستی مالک؛ هر تغییر نتیجه بدون ADR ممنوع |
| Leakage | آینده‌بین رد شود؛ shift بهتر نکند؛ canary فیچر؛ label shuffle؛ fold/universe/knowledge_time audit |
| Validity (کنترل‌ها) | BL-3 ≈ صفر/منفی؛ BL-4 منفی؛ BL-5 غیرعادی و رد‌شده؛ BL-6 بهتر نشود |
| Invariant | بقای سرمایه؛ پیوستگی ارزش در `ex_date`؛ تعطیلی N‌ماهه بدون معامله و با gap |
| Parity | مرجع ⟷ fast path؛ مرجع ⟷ Simulator قدیم (در تلورانس) |
| Integration | خط لوله روی نمونه‌ی کوچک؛ قطعیت (دو اجرا یکسان) |
| Regression | تغییر کد نباید golden را بدون دلیل تغییر دهد |
| Iran-specific | `NO_SHORT_ALLOWED`؛ سفارش قفل بدون داده‌ی صف ⇒ `unfillable`؛ دو املای یک نماد ⇒ یک `instrument_id`؛ داده با offset اشتباه ⇒ هشدار |

---

## ۱۵. عملیات و چرخه‌ی زنده

- خط لوله‌ی روزانه: دریافت → DQ → تعدیل → فیچر → پیش‌بینی → گزارش، با تلاش مجدد و هشدار.
- `shadow` (پیش‌بینی بدون اثر) → `paper` (چند ماه، tracking error نسبت به بک‌تست) → `live_small` (سقف ضرر، تأیید دستی) → `live`.
- ماشه‌های توقف خودکار: افت IC، drift، tracking error، تغییر قانون (epoch)، شکست گیت.
- **ثبت از امروز:** عمق/صف، snapshot ها، `own_order_log`، اخبار با زمان‌مهر (تاریخچه‌ی بدون زمان‌مهر وارد بک‌تست نمی‌شود).
- امنیت: کلیدها فقط secret store؛ بدون رمز در کد/لاگ؛ DB فقط‌خواندنی برای ابزارهای تحلیلی.

---

## ۱۶. ردیابی: یافته‌ی ممیزی ⇒ عنصر معماری

| یافته | عنصر معماری |
|---|---|
| A-03 سایز فروش | ۵.۲ (سایز فروش از پوزیشن)؛ تست property |
| A-04 MDD | ۹.۱ (MDD نسبی)؛ ۱۰ G4 |
| A-06، B-04، B-05 | ۰.۱، ۵.۸، `parity`، `TimeGuard` |
| B-01 | ۰.۶، `BASELINES.md`، G4 |
| C-01، C-06 | ۲.۲، ۵.۳، ۷.۳ |
| C-02، C-03، C2 | ۴، rule_at، epoch |
| C-04، C-05 | ۳.۱ تعدیل/سود |
| C-07 | ۷.۶ |
| C-08 | ۳.۱ universe PIT |
| D-03 | ۶ (دروازه‌ی ۹ fail-closed) |
| F-01، F-02 | ۷.۵ (`UNVERIFIED`، model_card) |
| F-04 | ۷.۲ FeatureGuard |
| G-01، G-02، G-03 | ۳.۱ (`trade_date`، bitemporal) |
| G-04، A-02 | ۵.۴ (ADV، بدون fallback بی‌صدا) |

---

## ۱۷. خارج از محدوده / تعلیق

HFT و درون‌روزی بدون داده‌ی مناسب؛ مدل عمیق قبل از baseline؛ ensemble/calibrator/۱۰ دروازه/Agent-Based/ژنتیک تا عبور baseline؛ مشتقه/اوراق/صندوق/کالا تا ماتریس پوشش `partial/full`؛ اخبار بدون زمان‌مهر؛ انتشار عمومی قبل از دو دوره paper موفق.

## ۱۸. تصمیم‌های باز (فقط مالک)

۱. تأیید ADR-001 (موتور مرجع) و ADR-002 (`trade_date`)؛ ۲. `acceptance.yaml` و `reference_rates`؛ ۳. منابع رسمی قوانین؛ ۴. افق (روزانه/هفتگی) و سرمایه/ظرفیت هدف؛ ۵. بازه‌ی hold-out؛ ۶. وجود `own_order_log` و داده‌ی عمق/صف؛ ۷. اولویت بازارها (پیشنهاد: سهام ← طلا/صندوق‌ها ← اوراق ← آپشن).
