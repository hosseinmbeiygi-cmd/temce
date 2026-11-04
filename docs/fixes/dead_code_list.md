# فهرست کد مرده — GoldDesk frontend (S6)

تاریخ: ۲۰۲۶-۱۰-۲۴ · مجری: دستیار ۳ (`fix/frontend-infra`)

> ## ⛔ در این رفع **هیچ فایلی حذف نشد**
> سیاست repo: حذف داده/فایل با صاحب کار است، نه با دستیار (ببین
> `docs/fixes/` و قاعدهٔ مرحلهٔ ۳). این سند **فهرست آمادهٔ حذف** است، نه اقدام.
> برای هر مورد: روش کشف، نتیجهٔ grep، و «آیا واقعاً حذف‌کردنی است؟» — چون دو مورد
> از آنچه ظاهرش «مرده» بود، در واقع زنده است (§۳).

بازتولید شواهد:

```bash
cd frontend
# الف) کامپوننتی که بیرون از تست هیچ import ندارد:
python - <<'PY'
import glob, os
files=[f for p in ("src/**/*.ts","src/**/*.tsx") for f in glob.glob(p,recursive=True) if ".test." not in f]
corpus="\n".join(open(f,encoding="utf-8",errors="replace").read() for f in files)
for c in sorted(glob.glob("src/components/gold/**/*.tsx",recursive=True)):
    mod="@/"+c.replace("\\","/")[:-4]
    if mod not in corpus: print("unimported:", os.path.basename(c))
PY
# ب) route های بدون لینک:
python -c "import re,glob;tabs=set(re.findall(r'\{ href: \"([^\"]+)\"',open('src/app/gold/layout.tsx',encoding='utf-8').read()));routes={'/gold'+p.replace(chr(92),'/').split('app/gold')[1][:-len('/page.tsx')] for p in glob.glob('src/app/gold/**/page.tsx',recursive=True)};print(sorted(routes-tabs))"
```

## ۱) کامپوننت‌های `components/gold/**` که بیرون از تست هیچ import ندارند (۱۰)

اجرای روش بالا در ۲۰۲۶-۱۰-۲۴ — ستون «وضعیت» سطر به سطر بررسی شده است:

| فایل | وضعیت واقعی | توضیح |
|---|---|---|
| `CoinBubbleTable.tsx` | **تبدیل به adapter شد (F8)** | دیگر پیاده‌سازی موازی نیست؛ فقط prop قدیمی را به نسخهٔ مرجع وصل می‌کند. حذفش الان فقط یک re-export را می‌بَرَد — بی‌ضرر ولی بی‌فایده. |
| `ScoreGauge.tsx` | اصلاح شد، هنوز بی‌import | در مرحلهٔ ۱ کرشِ `map[decision]` روی آن رفع شد (تست `GoldNoData`)؛ تا وصل نشدن به یک صفحه، مرده است. |
| `ScoreBreakdown.tsx` | بی‌import | نسخهٔ فعالِ همان محتوا `SummarySection.tsx` است. |
| `FundNAVTable.tsx` | بی‌import | معادل فعال: `app/gold/components/FundsPnavTable.tsx`. **نامزد واقعی حذف** (تکراری). |
| `BubbleGauge.tsx` | بی‌import | تنها مصرف‌کنندهٔ احتمالی هم `ScoreGauge` است که آن هم بی‌import است. |
| `GoldKPICard.tsx` | بی‌import | کارت‌های `/gold` امروز inline در `SummarySection` ساخته می‌شوند. |
| `ParityBadge.tsx` | بی‌import (غلط املایی‌اش رفع شد) | F8: `کمی偏离` → `کمی انحراف`. رفع باگ روی کد مرده بود — ارزشش جلوگیری از کپی‌شدن الگو بود. |
| `RSIIndicator.tsx` | بی‌import | |
| `TimeSeriesChart.tsx` | بی‌import | نمودارهای gold امروز SVG inline در `analytics/page.tsx` دارند. |
| `DCACalculator.tsx` | بی‌import، و **تنها مصرف‌کنندهٔ `planDCA`** | نکتهٔ مهم: C4 (حذف `current_score`) روی همین فایل اعمال شد. چون هیچ صفحه‌ای آن را mount نمی‌کند، ریسک 422 برای `/dca/plan` عملاً صفر است — این را در `CHANGELOG_2` هم ثبت کرده‌ام. ولی یعنی «ماشین‌حساب DCA inline» که `PLAN_GOLD.md` وعده می‌دهد، **در UI وجود خارجی ندارد**. |

**جمع:** ۱۰ فایل، ~۱٬۰۰۰ خط. هیچ‌کدام در build نهایی استفاده نمی‌شوند (Next.js
با `import`-graph درخت را می‌بَرَد)، ولی نگه‌داشتنشان هزینهٔ واقعی دارد: همان
واگرایی‌ای که F8 ساخت (دو `CoinBubbleTable` با دو رفتار null-safe متفاوت).

**پیشنهاد حذف امن (به صاحب کار):** اول `FundNAVTable`, `BubbleGauge`,
`GoldKPICard`, `RSIIndicator`, `TimeSeriesChart`, `ScoreBreakdown` (بدون مصرف‌کنندهٔ
معرف‌شده). `ScoreGauge`/`ParityBadge`/`DCACalculator` را یا وصل کنید یا حذف —
هر دو بهتر از بلاتکلیفی است. `CoinBubbleTable` فعلاً adapter است و می‌تواند با یک
commit حذف شود چون نسخهٔ مرجع در `app/gold/components/` است.

## ۲) route های زیر `/gold` که در ناوبری نیستند (۵) — **اکثراً حذف‌کردنی نیستند**

`TABS` در `app/gold/layout.tsx` پانزده مقصد دارد؛ بیست فایل `page.tsx` زیر
`/gold` وجود دارد. پنج تا بیرون ناوبری‌اند:

| route | خطوط | واقعیت | حذف؟ |
|---|---|---|---|
| `/gold/dashboard` | ۵ | `redirect("/gold")` | ❌ **زنده** — حذف = ۴۰۴ برای بوکمارک قدیمی |
| `/gold/dca` | ۵ | `redirect("/gold#dca")` | ❌ زنده |
| `/gold/funds` | ۵ | `redirect("/gold#funds")` | ❌ زنده |
| `/gold/technical` | ۵ | `redirect("/gold#technical")` | ❌ زنده |
| `/gold/coins` | **۳۹۰** | صفحهٔ کامل با `DecisionBadge`، watchlist، فیلتر حباب — و **هیچ** لینکی در `src/` به آن نیست (`grep '"/gold/coins"'` → صفر) | ⚠️ تصمیم محصول: یا به ناوبری برگردد (منطقاً بین «داشبورد» و «صندوق ETF» جایش است) یا حذف شود |

> این مهم‌ترین تصحیح گزارش است: اگر فقط عدد «۵ route یتیم» را می‌دیدم و پاک
> می‌کردم، چهار redirect را می‌شکستم. `grep` خط‌به‌خط نگهم داشت.

## ۳) دو موردی که «مرده» به نظر می‌رسند ولی **تست دارند**

`HealthRatioGauge.tsx` و `KillSwitchBanner.tsx` و `SpecRulesCard.tsx` و
`AlertEventList/AlertRuleForm/NativeBridge/PWAProvider/ThemeProvider/SkeletonBlock`
همگی import دارند (بخش اول جدول بالا را ببینید: فقط ۱۰ فایل بی‌import است) — پس
در فهرست حذف قرار **نمی‌گیرند**. این تفکیک را از خودِ اجرای اسکریپت گرفتم، نه از
حدس نام فایل.

## ۴) چیزهای مردهٔ غیرکامپوننتی که دیدم (ثبت، بدون اقدام)

| مورد | شواهد | چرا دست نزدم |
|---|---|---|
| `frontend/public/sw.js` در کنار `golddesk-sw.js` | هر دو ثبت می‌شوند (`providers.tsx:15`، `PWAProvider.tsx:21`) | S1: با تست قفل شد که هیچ‌کدام دادهٔ مالی را از cache نمی‌دهد؛ ادغام به یک SW فقط **پیشنهاد** است (`CHANGELOG_2` §S1) |
| `frontend/eslint_report.json`, `lint_full.txt`, `lint_report.txt`, `output.txt`, `frontend_err.txt`, `frontend_out.txt`, `s3.html`…`s7.html`, `silver2.html`, `silver_check.html`, `nul`, `dashboard_live.png`, `pytest-logs/` | فایل‌های دورریز debug در `frontend/` ریشه | حذف فایل = تصمیم صاحب کار. ولی **نباید** publish شوند: `docs/security/secret_scan_report.md` نشان داد لاگ‌ها می‌توانند متن سورس/secret را کپی کنند (`reports/runs/...:1658`) |
| `tsconfig.tsbuildinfo`، `capacitor.config.ts` + `package.cap.json` | تنظیمات بیلد موبایل | ممکن است عمدی باشد |
| `scripts/_q.py`, `scripts/_sample_dups.py` | اسکریپت‌های موقت با پیشوند `_` | فایل پایتون — ممنوع |

## ۵) خلاصهٔ اقدام‌پذیر

1. حذف `FundNAVTable.tsx` (تکراریِ صریح، معادل فعال دارد) — کم‌ریسک‌ترین.
2. تکلیف `/gold/coins`: وصل به ناوبری، یا حذف.
3. شش کامپوننت بی‌مصرفِ باقی‌مانده: با تأیید شما در یک commit جدا.
4. `DCACalculator`/`planDCA`: یا به `/gold/dca` وصل شود (آن route الان فقط
   redirect است) یا وعدهٔ «DCA inline calculator» از `PLAN_GOLD.md` برداشته شود.
   من وعده را نگه داشتم و وضعیت را در `CHANGELOG_2` ثبت کردم؛ حذف ادعا هم کار
   من است اگر بگویید.
