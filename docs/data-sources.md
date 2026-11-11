# Data Sources — Assistant 4 (Market Data & Integrations)

جدول منابع از `docs/phase0-gold-foundation.md` (فاز ۰)،
`docs/phase1-gold-parity.md` (فاز ۱)، `docs/phase2-market-coverage.md` (فاز ۲) و
`docs/data-sources-phase{1,2,3}.md` (فاز ۳) استخراج شده است.
در صورت تضاد، `docs/phase0-gold-foundation.md` و `docs/phase1-gold-parity.md` مرجع‌اند.

> لایه منبع (Assistant 4) لایه تصمیم یا UI نیست — فقط جمع‌آوری، نرمال‌سازی،
> زمان‌بندی و کیفیت‌سنجی داده بازار و تحویل به قرارداد دستیار ۱. ثبت سفارش، کیف،
> پرداخت و تحویل خارج از وظیفه است.

## قوانین مطلق (همه منابع)

- هر رکورد خروجی حداقل داشته باشد: `value` (عدد|null), `unit`, `asOf` (ISO ۸۶۰۱ با
  منطقه زمانی), `source`, `quality` ∈ {LIVE, DELAYED, SAMPLE, EDUCATIONAL, UNAVAILABLE}.
- `quality` هرگز `LIVE` برای منبع خام `SAMPLE`/`EDUCATIONAL` الإعلان نمی‌شود.
- داده نداشته → `quality=UNAVAILABLE`, `value=null`, `asOf=null` (هیچ عدد حدس زده‌ای).
- رمز/توکن/کوکی در لاگ یا خروجی ثبت نمی‌شود (`_strip_secrets` در هر ادAPTER).
- حباب/Score اینجا محاسبه نمی‌شود (مالک فرمول = دستیار ۱).
- تأخیر بیشتر از TTL ⇒ شه به DELAYED/SAMPLE + `staleFlag=true`.

## جدول منابع

| منبع | نمادها | فیلدهای قابل اعتماد | کیفیت معمول | تاخیر معمول | ریسک قطع | نکات |
|------|--------|---------------------|-------------|-------------|-----------|-------|
| `brsapi` | XAU_USD, USD_IRR, XAU18; ۱۸, ۲۴, آبشده, بهاری, نیم,ربع, گرمی; صندوق price/nav/volume/turnover/marketCap; نقره داخل XAG_IRR | price, asOf, source, quality_flag | LIVE / DELAYED / SAMPLE | < ۵ دقیقه | کم | API داخلی رسمی؛ mock در تست quality=SAMPLE |
| `tgju` | طلا/سکه/دلار آزاد | price, change_pct, asOf | DELAYED | ۱۵–۳۰ دقیقه | متوسط | تغییر HTML ⇒ شکست Adapter؛ تگ نسخه در `source` |
| `cis` | نرخ رسمی البنك مرکزی، حجم | official_price, daily_volume, asOf | LIVE/DELAYED/SAMPLE | روزانه ۱۵:۳۰؛ داخل‌روز نیست | بالا (پایان هفته) | Cutoff ⇒ SAMPLE؛ بدون داخل‌روز |
| `coin_supply` (عدل/ثبت) | سکه امامی/بهاری | price, mintage, purity, asOf | SAMPLE | متغیر (per mint) | متوسط | بیشتراً قیمت ceremonial |
| `London_Bullion_Market` | نقره XAG_USD | spot usd/oz, asOf | DELAYED | بازار جهانی | پایین | فقط Fallback؛ تبدیل به toman/gram فقط با USD_IRR صریح |
| `motor_forward` / `motor_option` | یک مشتقه read-only | price, settlement, expiry, distance_from_spot_pct | LIVE از موتور | لحظه‌ای | — | فقط خواندنی؛ سفارش/موقعیت کاربر نیست |
| پلتفرم‌های عمومی (A, B, …) | buy/sell/dayLow/dayHigh فقط | buy_price, sell_price, dayLow, dayHigh, asOf | DELAYED | ۱–۵ دقیقه (ToS) | — | بدون سشن کاربر؛ فقط ToS مجاز؛ نام پلتفرم با تأیید حقوقی |

## شکل رکورد خروجی (همه ادAPTERها)

```json
{
  "symbol": "XAU18 | null",
  "value": 26396987.8 | null,
  "unit": "toman",
  "asOf": "2026-10-26T09:59:00+03:30 | null",
  "source": "brsapi",
  "quality": "LIVE",
  "metadata": {
    "ageSeconds": 60,
    "freshness": "fresh",
    "staleFlag": false
  }
}
```

`ageSeconds = now − asOf` (ثانیه); `freshness ∈ {fresh, stale, unknown}` بر اساس TTL
(پیش‌فرض ۹۰۰ ثانیه فاز ۳، ۳۰۰ ثانیه BrsApi); `staleFlag=true` وقتی `ageSeconds > TTL`.

## چه چیزها ثبت نمی‌شود (ممنوعیات)

- عدد LIVE بدون `asOf`/`source`
- حباب محاسبه‌شده با فرمول دوم موازی (مالک Motor = دستیار ۱)
- توصیه بخر/بفروش؛ موجودی طلای کاربر در سیستم
- هر secret در لاگ/کمیت/پاسخ API
- اسکریپ با رمز کاربر (فاز ۰ ممنوع است)

## فیکست‌های آفلاین (CI بدون شبکه)

- `tests/fixtures/phase3-silver.json` — نقره داخل + بین‌المللی
- `tests/fixtures/phase3-derivative.json` — مشتقه read-only
- `tests/fixtures/phase3-news.json` — ورودی رژیم خبری
- `tests/fixtures/phase3-stale.json` — رکورد منقضی برای گیت `data_stale`
- `tests/fixtures/phase3-secret.json` — پذیف symbol (توکن strip شود)

تست: `tests/gold_desk/test_phase3_adapters.py` (۱۴ تست، بدون شبکه)

## اجرای استقocoa

```
venv\Scripts\python.exe -m pytest tests/gold_desk/test_phase3_adapters.py -q
ruff check services/data tests/gold_desk/test_phase3_adapters.py
```
