# فاز ۳ — دستیار تصمیم: قرارداد، گیت و پذیرش

**وضعیت پذیرش فاز ۳: NOT DONE — ۲۰۲۶-۱۰-۲۶**
**فاز ۴: DONE نیست و شروع نشده است.** این سند فقط فاز ۳ را ارزیابی می‌کند.

این فایل جایگزین نسخهٔ قبلی است که با متن مخلوط چند زبان، نام‌های ناقص (`missingmissing`، `Thresholdottlenecks`) و چک‌لیست از پیش تیک‌خورده خراب شده بود. نسخهٔ قبلی هیچ شاهد کدی نداشت؛ این نسخه وضعیت واقعی مخزن را ثبت می‌کند.

---

## ۰. خلاصهٔ اجرایی

فاز ۳ در این checkout **فقط مستندات دارد و هیچ کد، endpoint، schema یا تستی ندارد**:

- `scoreVersion` و `actionLanguageAllowed` در کل مخزن فقط در سه فایل مستندات دیده می‌شوند و **صفر مورد** در `src/`، `apps/`، `frontend/src/` و `tests/` دارند.
- مسیرهای `GET /gate` و `GET /brief` وجود ندارند.
- هیچ تستی با نام `phase3` در بک‌اند یا فرانت‌اند وجود ندارد.
- امتیاز موجود (`src/gold_desk/scorer.py`) متعلق به فاز ۰ است و با اجزای وزنی فاز ۳ یکی نیست.
- رگرسیون فاز ۰–۲ سبز است، اما این به‌معنای پذیرش فاز ۳ نیست.

---

## ۱. شواهد بررسی (اجرا شده در همین checkout)

| بررسی | فرمان | نتیجه |
|---|---|---|
| جست‌وجوی قرارداد فاز ۳ | `rg -l "scoreVersion\|actionLanguageAllowed" .` | فقط `docs/contracts/phase3-decision.json`، `docs/phase3-vocabulary-fa.md`، `docs/phase3-decision-assistant.md` |
| مسیرهای طلا | `rg -n "@router\.(get\|post\|put\|delete\|patch)\(" src/gold_desk/api.py` | هیچ `/gate` یا `/brief` وجود ندارد |
| تست فاز ۳ | `Get-ChildItem tests -Recurse -Filter "*phase3*"` | خالی |
| تست فرانت فاز ۳ | `Get-ChildItem frontend/src/__tests__ -Filter "*Phase3*"` | خالی |
| رگرسیون بک‌اند فاز ۰–۲ | `venv\Scripts\python.exe -m pytest tests/gold_desk/test_phase0_*.py tests/gold_desk/test_phase1_terminal.py tests/gold_desk/test_phase2_market_coverage.py -q` | **111 passed, 2 warnings** در 53.25s |
| رگرسیون فرانت طلا | `npx vitest run GoldTrustLabels GoldNoData GoldFrontendSurfaces GoldTerminalPhase1 GoldMarketCoverage` | **40 passed / 5 files** در 27.89s |

نکتهٔ محیط: `.venv` پکیج `pytest` ندارد؛ محیط تست بک‌اند `venv\Scripts\python.exe` است (Python 3.11.9، pytest 9.1.1).

---

## ۲. Score — قرارداد هدف و واقعیت موجود

### ۲.۱ قرارداد هدف فاز ۳

`Score = 100 × Σ (w_i × s_i)` که `s_i ∈ [0,1]` و `Σ w_i = 1`.

| جزء | وزن | فرمول | شرط اعتبار |
|---|---|---|---|
| `bubble_phys` | 0.25 | حباب فیزیکی نرمال‌شده | ارزش منصفانه و قیمت هم‌زمان و هم‌واحد |
| `bubble_nominal` | 0.20 | `bubble_abs / fair_value` | قیمت و مرجع تازه |
| `liquidity_turnover` | 0.15 | `turnover_24h / open_interest` | هر دو عدد موجود و تازه |
| `implied_usd_gap` | 0.20 | `abs(implied_usd − xau_usd) / xau_usd` | هر دو نرخ از یک لحظه |
| `data_freshness` | 0.10 | تابع نزولی `age_seconds / TTL` | `age_seconds` موجود |
| `funding_rate` | 0.10 | نرخ بهرهٔ روزانه | فقط اگر دادهٔ فاز ۴ موجود باشد |
| **جمع** | **1.00** | | |

قواعد پیشنهادی (نیازمند تأیید مالک، چون کد ندارد):

- اگر `funding_rate` موجود نباشد، وزن‌ها روی اجزای موجود نرمال می‌شوند و `coverage` گزارش می‌شود.
- اگر `coverage < 0.60` باشد → `NO_DATA`، نه امتیاز سبز.
- هر تغییر وزن باید `scoreVersion` را بالا ببرد و تست داشته باشد.

### ۲.۲ امتیاز موجود در کد (فاز ۰)

`src/gold_desk/constants.py`:

```text
SCORE_WEIGHTS = {
  "bubble": 20, "nav": 18, "tsetmc": 18,
  "technical": 15, "parity": 15, "fund_flow": 14
}  # sum = 100
SCORE_GREEN_MIN = 80
SCORE_YELLOW_MIN = 55
```

`ScoreBlock` در `src/gold_desk/schemas.py` این اجزا را دارد و `decision` یکی از `GREEN|YELLOW|RED|NO_DATA` است. اما:

- `scoreVersion` ندارد.
- `actionLanguageAllowed` ندارد.
- اجزای آن با قرارداد فاز ۳ یکی نیست.
- `components` به‌صورت شیء ثابت است، نه آرایهٔ وزن‌دار قابل‌مستندسازی.

**نتیجه:** «Score با components و وزن مستند» فقط برای فاز ۰ برقرار است؛ برای فاز ۳ **NOT DONE**.

---

## ۳. گیت — قرارداد هدف و آستانه‌ها

| کد | شرط | شدت | پیامد |
|---|---|---|---|
| `data_stale` | `age_seconds > 900` (۱۵ دقیقه) | high | `red` |
| `extreme_retail_premium` | `bubble_abs / fair_value > 0.30` | high | `red` |
| `implied_conflict` | `abs(implied_usd − xau_usd) / xau_usd > 0.15` | medium | `yellow` |
| `insufficient_coverage` | پوشش وزن کمتر از ۰٫۶۰ | medium | `yellow` یا `NO_DATA` |
| `low_liquidity` | نقدشوندگی زیر آستانهٔ config | low | `yellow` |

نگاشت وضعیت:

- هر `high` → `red`
- بدون `high` و با هر `medium` → `yellow`
- بدون دلیل و با دادهٔ کامل و تازه → `green`
- دادهٔ ناقص یا ناموجود → `red` با `insufficient_coverage`

قاعدهٔ سخت: `actionLanguageAllowed = (status != "red")`.

**واقعیت:** هیچ‌کدام از این کدها، آستانه‌ها یا نگاشت در کد وجود ندارد. `acceptance.yaml` فقط آستانهٔ Production Gate استراتژی (`walk_forward`, `risk_management`) را دارد و هیچ کلید فاز ۳ ندارد. بنابراین «طبق config» فعلاً **NOT DONE** است.

---

## ۴. Brief — دو افق

ساختار الزامی برای هر افق:

```json
{
  "horizon": "short|medium",
  "scoreVersion": "v1.0",
  "statusBullets": ["..."],
  "keyNumbers": { "price": null, "bubble_pct": null, "score": null },
  "risks": ["data_stale"],
  "checklist": ["..."],
  "gate": { "status": "red", "actionLanguageAllowed": false },
  "score": { "value": null, "components": [], "weightsSum": 1.0 },
  "disclaimer": "..."
}
```

- `short` و `medium` هر کدام `score`، `gate`، `statusBullets` و `keyNumbers` مستقل دارند.
- عدد بدون `source`/`asOf` مجاز نیست.
- مقدار ناموجود `null` است و در UI `—` نمایش داده می‌شود.

**واقعیت:** هیچ endpoint یا schemaای برای Brief وجود ندارد. **NOT DONE**.

---

## ۵. مرز اخلاقی محصول

### ۵.۱ این محصول

- تحلیل، تصمیم‌یاری و آموزش؛ نه اجرا.
- هیچ سفارش، کیف پول، تحویل، پرداخت یا کارگزاری.
- هیچ وعدهٔ سود یا بازده تضمینی.
- هر عدد با `value` + `unit` + `asOf` + `source` + `quality`.
- شکست داده → «اطلاعات ناکافی» یا `NO_DATA`، نه عدد جای‌گزین.

### ۵.۲ رهآورد ۳۶۵

در مخزن، رهآورد به‌عنوان **نرم‌افزار داده و گزارش بنیادی** حضور دارد:

- `frontend/src/app/plugins/rahavard/page.tsx` — صفحهٔ placeholder «اتصال به نرم‌افزار رهآورد ۳۶۵».
- `frontend/src/components/RahavardMarketingBanner.tsx` — معرفی گزارش‌های بنیادی و کدال.

مرز: دادهٔ بنیادی رهآورد می‌تواند **ورودی تحلیل** باشد، اما خروجی آن به‌تنهایی سیگنال خرید/فروش نیست. هیچ گزارش رهآورد نباید بدون منبع و زمان به «توصیه» تبدیل شود.

### ۵.۳ میلی

هیچ ارجاع مستندی به محصولی با نام «میلی» در مخزن پیدا نشد. بنابراین هیچ ادعای مقایسه‌ای دربارهٔ آن نوشته نمی‌شود.

**اقدام لازم:** مالک محصول باید منبع/مشخصات «میلی» را ارائه کند. تا آن زمان این بخش «تأییدنشده» می‌ماند و در UI هیچ مقایسه‌ای با آن منتشر نمی‌شود.

---

## ۶. نحوهٔ اجرای تست‌ها

```powershell
# بک‌اند — از ریشهٔ مخزن
venv\Scripts\python.exe -m pytest tests/gold_desk/test_phase0_engine_core.py tests/gold_desk/test_phase0_snapshot_provenance.py tests/gold_desk/test_phase0_snapshot_integration.py tests/gold_desk/test_phase0_secondary_source.py tests/gold_desk/test_phase0_mount.py tests/gold_desk/test_phase1_terminal.py tests/gold_desk/test_phase2_market_coverage.py -q

# فرانت‌اند
cd frontend
npx vitest run src/__tests__/GoldTrustLabels.test.tsx src/__tests__/GoldNoData.test.tsx src/__tests__/GoldFrontendSurfaces.test.tsx src/__tests__/GoldTerminalPhase1.test.tsx src/__tests__/GoldMarketCoverage.test.tsx
```

تست‌های فاز ۳ (که هنوز نوشته نشده‌اند) باید حداقل این پنج مورد را پوشش دهند:

1. fixture حباب ربع افراطی → گیت `yellow`/`red` طبق config.
2. `asOf` کهنه → `data_stale` و `actionLanguageAllowed=false`.
3. UI با `gate=red` → هیچ دکمه یا جملهٔ خرید/فروش.
4. تغییر وزن Score بدون تست → رد.
5. رگرسیون what-if و حباب اسمی صندوق.

---

## ۷. چک‌لیست پذیرش فاز ۳

| # | مورد | وضعیت | شاهد / دلیل |
|---|---|---|---|
| ۱ | Score با components و وزن مستند | **NOT DONE** | امتیاز موجود فاز ۰ است؛ اجزای فاز ۳ وجود ندارد |
| ۲ | `scoreVersion` موجود | **NOT DONE** | صفر مورد در کد |
| ۳ | `gate=red` → `actionLanguageAllowed=false` در API و UI | **NOT DONE** | گیت وجود ندارد؛ UI فعلی در چند صفحه زبان BUY/SELL بدون گیت دارد |
| ۴ | دو افق `short`/`medium` جدا | **NOT DONE** | Brief وجود ندارد |
| ۵ | Brief بدون قیمت جعلی | **NOT DONE** | Brief وجود ندارد؛ قرارداد متن در واژه‌نامه آماده است |
| ۶ | نقره حداقل read-only در میز | **NOT DONE** | فقط طبقه‌بندی صندوق نقره در `phase1.py` و `SilverBar` در مشتقه‌ها |
| ۷ | یک مشتقه read-only بدون سفارش | **NOT DONE** | تحلیل‌های اختیار موجود read-only هستند، اما قرارداد فاز ۳ پیاده نشده |
| ۸ | رژیم خبری برچسب ثابت | **NOT DONE** | کد و برچسب‌گذاری وجود ندارد؛ برچسب‌های فارسی در واژه‌نامه نهایی شد |
| ۹ | رگرسیون فاز ۰–۲ | **DONE** | ۱۱۱ تست بک‌اند + ۴۰ تست فرانت سبز |
| ۱۰ | هیچ route سفارش در diff | **DONE (محدود به diff طلای فعلی)** | diff فعلی فقط phase1/phase2 read-only است؛ ریسک‌های پیش‌موجود در §۹ |

**جمع:** ۲ مورد DONE، ۸ مورد NOT DONE. پذیرش فاز ۳ **رد** می‌شود.

---

## ۸. یافته‌های اضافی مرتبط با گیت

در UI فعلی، زبان اقدام بدون گیت وجود دارد:

- `frontend/src/app/gold/antigravity/page.tsx` — `BUY`/`SELL`، «فرصت خرید»، «خرید ETF و فروش آب‌شده».
- `frontend/src/app/gold/coins/page.tsx` — «خرید»، «خرید تدریجی».
- `frontend/src/app/gold/physical/page.tsx` — برچسب «خرید».
- `frontend/src/app/gold/etf/page.tsx` — «سیگنال خرید».

این موارد در فاز ۰ با disclaimer و برچسب کیفیت قابل قبول تلقی شده‌اند، اما برای فاز ۳ کافی نیستند: تا وقتی گیت وجود ندارد، نمی‌توان اثبات کرد `gate=red` زبان اقدام را خاموش می‌کند. این مورد باید در فاز ۳ بسته شود.

---

## ۹. ریسک‌های پیش‌موجود (خارج از diff فاز ۳)

- `src/gold_desk/auto_trade.py` حالت `dry_run=False` با broker adapter دارد. هیچ route به آن ارجاع نمی‌دهد، اما وجود آن باید پیش از فاز ۴ بازبینی شود.
- `apps/api/endpoints/tabdeal.py` مسیرهای `/sync/orders` و `/orders` دارد. این سطح Tabdeal و خارج از GoldDesk است، اما در بازبینی «هیچ route سفارش» باید مستثنا یا مستند شود.
- `docs/data-sources-phase0.md` با قرارداد تأییدشدهٔ فاز ۰ تضاد دارد؛ مرجع، `docs/phase0-gold-foundation.md` است.

---

## ۱۰. رد PR

PR رد می‌شود اگر شامل یکی از این‌ها باشد:

1. route سفارش، سبد، checkout، کیف پول، تحویل یا اجرای کارگزاری.
2. زبان اقدام (خرید/فروش/هدف قیمت) روی `gate=red`.
3. برچسب `LIVE` برای دادهٔ اثبات‌نشده یا کهنه.
4. تغییر آستانه یا وزن Score بدون مستند و تست.
5. تیک‌زدن چک‌لیست پذیرش بدون شاهد فرمان و خروجی.
6. وعدهٔ سود، بازده تضمینی یا «بدون ریسک».

---

## ۱۱. وضعیت فاز ۴

فاز ۴ **DONE نیست و شروع نشده است**. این سند هیچ مجوزی برای فاز ۴، paywall، شبکهٔ اجتماعی یا دادهٔ ۳۶۵روزه نمی‌دهد. تا زمانی که همهٔ موارد §۷ سبز نشوند، فاز ۴ باز نمی‌شود.
