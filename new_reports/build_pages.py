"""Build per-symbol pages + dashboard.md + detection_log.csv + run summary.

Input tables (auto-detected):
  A) history_data/*_history.json   — 95 daily OHLC series (fx/gold/coin/crypto-index families)
  B) t.bin                          — 4 precious metals intraday ticks (39 days)
  C) data/top50_funds_intraday      — 49 fund one-day tick data
  D) data/codal_attachments/codal   — 19 companies: P&L/BS (7), shareholders/audit/board,
                                      monthly activity (2), holding portfolio (1), notices
"""
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analytics
import etl

BASE = etl.BASE
OUT = os.path.join(BASE, 'new_symbol_reports')
os.makedirs(os.path.join(OUT, 'pages'), exist_ok=True)

UNK = 'نامشخص'
NA = 'فاقد موضوعیت'
CANT = 'قابل محاسبه نیست'
ML_WARN = ('⚠️ داده تاریخی بازار ایران برای این نماد معمولاً محدود است؛ مدل مستعد Overfitting است؛ '
           'این پیش‌بینی صرفاً آزمایش آماری اکتشافی است، نه سیگنال معاملاتی، و عملکرد گذشته ضمانتی برای آینده نیست.')
DASH_DISCLAIMER = ('این داشبورد، تجمیع و رتبه‌بندی خودکار داده‌های موجود در صفحات نمادهاست؛ '
                   'یک توصیه سرمایه‌گذاری یا سیگنال خرید/فروش قطعی نیست. فهرست پیشنهادی صرفاً نقطه شروع '
                   'برای بررسی عمیق‌تر شماست، نه نتیجه نهایی. تصمیم و مسئولیت آن با خود سرمایه‌گذار است. '
                   'همچنین، فیلترها و وزن‌های امتیازدهی بالا پیش‌فرض و قابل تغییرند؛ با معیار دیگری، رتبه‌بندی متفاوت می‌شود.')

def fmt(x, nd=2):
    if x is None:
        return UNK
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return UNK
        return f'{x:,.{nd}f}'
    except Exception:
        return str(x)

def pct(x, nd=2):
    return fmt(x, nd) + ('%' if x is not None else '')

det_log = []

def dlog(file, col, ctype, path, conf, ftype='', note=''):
    det_log.append({'نام فایل': file, 'ستون انتخابی': col, 'نوع محتوای تشخیص‌داده‌شده': ctype,
                    'مسیر تشخیص': path, 'درجه اطمینان': conf, 'نوع محتوا فایل': ftype, 'توضیح': note})

def persian_months(y, m, d):
    names = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
    try:
        return f'{int(d)} {names[int(m) - 1]} {int(y)}'
    except Exception:
        return f'{y}/{m}/{d}'

def jdate_words(dstr):
    p = dstr.replace('-', '/').split('/')
    if len(p) >= 3:
        return persian_months(*p[:3])
    return dstr

# ---------- category classification ----------
def classify_symbol(sym, src):
    if src == 't.bin':
        return 'فلزات گران‌بها (جهانی)', 'انس نقره/طلا/پالادیوم/پلاتین'
    if sym.startswith('NIMA_'):
        return 'ارز (نظام نیما)', 'نرخ تسعیر نیما'
    if sym.startswith('SANA_'):
        return 'ارز (صرافی — صنا)', 'نرخ آزاد صنا'
    if sym.startswith('IR_COIN') or sym.startswith('IR_PCOIN'):
        return 'سکه و طلا (ایران)', 'سکه/طلای ایرانی'
    if sym.startswith('IR_GOLD'):
        return 'سکه و طلا (ایران)', 'طلای ایرانی'
    if sym in ('USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'CNY', 'AED', 'AFN', 'AMD', 'AZN', 'BHD',
               'GEL', 'INR', 'IQD', 'KWD', 'MYR', 'OMR', 'PKR', 'QAR', 'RUB', 'SAR', 'SEK', 'SYP', 'THB', 'TRY'):
        return 'ارز (آزاد بازار)', 'نرخ آزاد'
    if sym == 'XAUUSD':
        return 'فلزات گران‌بها (جهانی)', 'انس جهانی'
    return 'سایر', 'سایر'

def direction(x, up_label, down_label, neutral='خنثی'):
    if x is None:
        return UNK
    return up_label if x > 0 else (down_label if x < 0 else neutral)

# ---------- page builder ----------
def build_page(sym, info, ctx):
    """ctx: dict with category, subcat, symbol-source, tech, backtest, ml, risk, extras."""
    cat, sub = ctx['category']
    L = []
    L.append(f'# صفحه اختصاصی نماد {sym}')
    L.append(f'> دسته: {cat} — {sub} | منبع داده: {ctx.get("source", UNK)} | واحد ارقام: {info.get("unit", UNK)} (شمسی)')
    L.append('')
    # 1 شناسنامه
    L.append('## ۱. شناسنامه نماد')
    ident = [
        ('نام کامل', info.get('name') or UNK), ('نماد فارسی', sym if not sym.isascii() else UNK),
        ('نماد لاتین', sym if sym.isascii() else UNK), ('کد ISIN', UNK), ('صنعت', cat), ('زیرصنعت', sub),
        ('بازار (بورس-فرابورس)', 'فاقد موضوعیت — داده قیمت جهانی/ارزی'), ('تابلو', NA), ('تاریخ پذیرش', UNK),
        ('سرمایه ثبتی (میلیارد تومان)', NA), ('تعداد کل سهام', NA), ('درصد سهام شناور آزاد', NA),
    ]
    if ctx.get('fund_meta'):
        m = ctx['fund_meta']
        ident[0] = ('نام کامل', m['name'])
        ident[4] = ('صنعت', m['sector'])
        ident[9] = ('سرمایه ثبتی (میلیارد تومان)', UNK)
    for k, v in ident:
        L.append(f'- {k}: {v}')
    L.append('')
    # 2 درون‌روز
    L.append('## ۲. وضعیت درون‌روز')
    intr = ctx.get('intraday')
    if intr:
        for k, v in intr:
            L.append(f'- {k}: {v}')
    else:
        L.append('- فاقد داده (جدول تیک درون‌روز برای این نماد موجود نیست)')
    L.append('')
    # 3 وضعیت بازار و کدال
    L.append('## ۳. وضعیت بازار و کدال')
    codal = ctx.get('codal_news')
    if codal:
        for line in codal:
            L.append(line)
    else:
        L.append('- وضعیت نماد: فاقد موضوعیت (دارایی غیربورسی)')
        L.append('- ۵ اطلاعیه اخیر کدال: فاقد داده')
    L.append('')
    # 4 تکنیکال
    L.append('## ۴. قیمت و اندیکاتورهای تکنیکال')
    t = ctx.get('tech')
    if t:
        L.append(f'- تاریخ و قیمت آخرین روز: **{t["date"]} = {fmt(t["close"], 0)} {info.get("unit", "")}**')
        L.append(f'- درصد تغییر روزانه: {pct(t["chg_day"])}')
        L.append(f'- SMA20: {fmt(t["sma20"], 0)} ({direction((t["close"] or 0) - (t["sma20"] or 0), "قیمت بالای SMA20", "قیمت زیر SMA20") if t["sma20"] else UNK})')
        L.append(f'- SMA50: {fmt(t["sma50"], 0)} ({direction((t["close"] or 0) - (t["sma50"] or 0), "قیمت بالای SMA50", "قیمت زیر SMA50") if t["sma50"] else UNK})')
        rsi = t['rsi14']
        interp = 'اشباع خرید' if rsi and rsi > 70 else ('اشباع فروش' if rsi and rsi < 30 else 'ناحیه خنثی')
        L.append(f'- RSI14: {fmt(rsi)} — تفسیر: {interp}')
        L.append(f'- MACD: {fmt(t["macd"])} | Signal: {fmt(t["macd_sig"])} | Histogram: {fmt(t["macd_hist"])} — جهت شتاب: {direction(t["macd_hist"], "صعودی", "نزولی")}')
        L.append(f'- Bollinger(20,2): Upper={fmt(t["bb_upper"], 0)} / Middle={fmt(t["bb_mid"], 0)} / Lower={fmt(t["bb_lower"], 0)} | %B={fmt(t["pctb"], 3)}')
        L.append(f'- ATR14: {fmt(t["atr14"], 0)}')
        L.append(f'- حمایت نزدیک (کف ۲۰ کندل): {fmt(t["support20"], 0)} | مقاومت نزدیک (سقف ۲۰ کندل): {fmt(t["resist20"], 0)}')
        L.append(f'- سقف تاریخی بازه داده: {fmt(t["hist_high"], 0)} ({t["hist_high_date"]}) | فاصله تا سقف: {pct((t["close"] / t["hist_high"] - 1) * 100 if t["hist_high"] else None)}')
        L.append(f'- کف تاریخی بازه داده: {fmt(t["hist_low"], 0)} ({t["hist_low_date"]})')
        L.append(f'- بازدهی ۱هفته/۱ماه/۳ماه: {pct(t["ret5"])} / {pct(t["ret21"])} / {pct(t["ret63"])}')
        L.append(f'- میانگین ارزش معاملات ۳۰روزه: {CANT} (ستون ارزش/حجم معاملات در جدول ورودی این نماد وجود ندارد)')
    else:
        L.append(f'- {CANT} — سری روزانه کافی نیست (کمتر از ۲۰ مشاهده).')
    L.append('')
    # 5 عملکرد مالی
    L.append('## ۵. عملکرد مالی')
    fin = ctx.get('fin')
    if fin:
        L.append('| دوره | درآمد عملیاتی | سود ناخالص | سود عملیاتی | سود خالص | EPS | حاشیه ناخالص% | حاشیه عملیاتی% | حاشیه خالص% | رشد درآمد YoY% | رشد سود خالص YoY% | ROE% | ROA% | نسبت بدهی% | نسبت جاری | پوشش هزینه مالی |')
        L.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for row in fin:
            L.append('| ' + ' | '.join(row) + ' |')
        L.append('')
        L.append('*مبالغ بر حسب میلیون ریال طبق صورت مالی کدال. ROE/ROA با میانگین حقوق صاحبان سهام/دارایی (میانگین دو دوره) محاسبه شد.*')
    else:
        L.append(f'- {NA} — صورت سود و زیان/ترازنامه در داده ورودی این نماد موجود نیست (دارایی غیرسهامی).')
    L.append('')
    # 6 ارزش‌گذاری
    L.append('## ۶. ارزش‌گذاری')
    L.append(f'- P/E(TTM) / P/B / P/S / EV / EV/EBITDA: {NA} — فاقد قیمت سهام/سرمایه/بدهی بازار در داده ورودی (دارایی غیرسهامی).')
    L.append(f'- NAV هر سهم و P/NAV: {NA} (هلدینگ نیست)')
    L.append(f'- مفروضات DCF (R_f، β، ERP، r_e، g): {CANT} — داده شاخص کل و صورت جریان نقدی کامل در ورودی نیست. [فرض محاسباتی] موردی ثبت نشد.')
    L.append(f'- ارزش هر سهم DCF / RIM / DDM: {CANT}')
    L.append(f'- ارزش منصفانه ترکیبی و Margin of Safety: {CANT}')
    L.append('')
    # 7 NAV صندوق
    L.append('## ۷. NAV اختصاصی صندوق')
    if ctx.get('is_fund'):
        m = ctx['fund_meta']
        L.append(f'- نوع صندوق: {m["sector"]}')
        L.append(f'- NAV صدور/ابطال هر واحد: {UNK} (در داده ورودی افشا نشده)')
        L.append(f'- قیمت بازار فعلی واحد: آخرین قیمت تیک درون‌روز = {fmt(ctx.get("fund_last_price"), 0)} ریال')
        L.append(f'- درصد حباب/تخفیف نسبت به NAV: {CANT} (NAV افشا نشده)')
        L.append('- ترکیب دارایی‌ها (سهام/اوراق/سپرده %): نامشخص')
    else:
        L.append(f'- {NA} (این نماد صندوق/ETF نیست)')
    L.append('')
    # 8 حقیقی/حقوقی
    L.append('## ۸. تابلوی معاملات حقیقی/حقوقی')
    L.append(f'- {NA} — داده تفکیک حقیقی/حقوقی در ورودی موجود نیست.')
    L.append('')
    # 9 بک‌تست
    L.append('## ۹. نتیجه بک‌تست')
    bt = ctx.get('bt')
    if bt:
        ins, oos = bt
        L.append('- استراتژی: تقاطع SMA(20)/SMA(50) — ورود در تقاطع صعودی، خروج در تقاطع نزولی | بدون Look-ahead Bias | کارمزد فرضی ۰.۵٪ هر طرف (فرض محاسباتی)')
        L.append(f'- بازه داده: {ins["start_date"]} تا {oos["end_date"]}')
        for lbl, b in [('In-Sample (۷۰٪ ابتدایی)', ins), ('Out-of-Sample (۳۰٪ انتهایی)', oos)]:
            L.append(f'- **{lbl}:** تعداد معاملات: {b["n_trades"]} | Win Rate: {pct(b["win_rate"])} | '
                     f'Profit Factor: {fmt(b["profit_factor"])} | بازده کل: {pct(b["total_ret"])} | CAGR: {pct(b["cagr"])} | '
                     f'Max Drawdown: {pct(b["max_dd"])} | Sharpe: {fmt(b["sharpe"])}')
        L.append(f'- مقایسه Buy&Hold: بازده کل بازه: {pct(ins["buyhold_ret"])} (In-Sample) | {pct(oos["buyhold_ret"])} (Out-of-Sample)')
        concl = 'داده ناکافی برای نتیجه‌گیری' if ins['n_trades'] < 5 else (
            'پایدار' if (oos['win_rate'] or 0) > 35 and (oos['total_ret'] or 0) > 0 else 'نشانه Overfitting')
        L.append(f'- نتیجه‌گیری پایداری: **{concl}**')
    else:
        L.append(f'- {CANT} — تعداد معاملات تولیدشده برای آمار معنادار کافی نیست یا داده کوتاه است.')
    L.append('')
    # 10 ML
    L.append('## ۱۰. نتیجه مدل ML')
    ml = ctx.get('ml')
    if ml:
        L.append('- افق پیش‌بینی: آیا Close طی ۵ روز آینده حداقل ۲٪ رشد می‌کند؟ (۱/۰)')
        L.append(f'- تعداد نمونه معتبر: {ml["n"]} | تقسیم Train/Val/Test (زمانی، بدون Shuffle): {ml["train"]}/{ml["val"]}/{ml["test"]}')
        L.append(f'- Class Balance (نسبت کلاس ۱): {pct(ml["balance"])}')
        names = ml.get('names') or []
        for name, r in ml['models'].items():
            if r:
                nm = 'Logistic Regression' if name == 'logreg' else 'Gradient Boosting (stump)'
                L.append(f'- **{nm}:** Accuracy: {pct(r["acc"])} | Precision: {pct(r["prec"])} | Recall: {pct(r["rec"])} | F1: {fmt(r["f1"])} | AUC-ROC: {fmt(r["auc"], 3)}')
                if r.get('imp'):
                    imp_str = ', '.join(f'{names[j] if j < len(names) else f"فیچر#{j+1}"} ({pct(v, 1)})' for j, v in r['imp'][:5] if v > 0)
                    L.append(f'  - Feature Importance: {imp_str or UNK}')
            else:
                nm = 'Logistic Regression' if name == 'logreg' else 'Gradient Boosting'
                L.append(f'- **{nm}:** اجرا نشد (داده کافی نیست)')
        L.append(f'- Accuracy Baseline (حدس اکثریت کلاس): {pct(ml["baseline_acc"])}')
        gb_imp = (ml['models'].get('gboost') or {}).get('imp') or []
        top5 = ', '.join(names[j] for j, _ in gb_imp[:5]) if names and gb_imp else UNK
        L.append(f'- ۵ فیچر برتر: {top5}')
        L.append(f'- {ML_WARN}')
    else:
        L.append(f'- {CANT} — حداقل چند ده نمونه معتبر پس از حذف NaN باقی نماند (داده کوتاه).')
    L.append('')
    # 11 مالکیت
    L.append('## ۱۱. مالکیت، مدیریت و رویدادهای شرکتی')
    own = ctx.get('ownership')
    if own:
        for line in own:
            L.append(line)
    else:
        L.append(f'- {NA} — دارایی غیرسهامی؛ جدول سهامداران/افزایش سرمایه/سود تقسیمی در ورودی وجود ندارد.')
    L.append('')
    # 12 اخبار
    L.append('## ۱۲. اخبار و اطلاعیه‌های اثرگذار')
    news = ctx.get('news')
    if news:
        L.append('| تاریخ | عنوان | خلاصه یک‌خطی | نوع اثر |')
        L.append('|---|---|---|---|')
        for r in news:
            L.append('| ' + ' | '.join(r) + ' |')
    else:
        L.append('- فاقد داده (اطلاعیه کدال برای این نماد در ورودی نیست)')
    L.append('')
    # 13 حسابرسی
    L.append('## ۱۳. حسابرسی و کیفیت گزارشگری')
    aud = ctx.get('audit')
    if aud:
        for line in aud:
            L.append(line)
    else:
        L.append('- فاقد داده (گزارش حسابرسی در ورودی موجود نیست)')
    L.append('')
    # 14 هم‌گروهی
    L.append('## ۱۴. مقایسه با هم‌گروهی‌ها')
    peers = ctx.get('peers')
    if peers:
        L.append('| نماد | P/E | P/B | حاشیه سود خالص% | رشد فروش سالانه% | بازدهی ۱۲ماهه% |')
        L.append('|---|---|---|---|---|---|')
        for r in peers:
            L.append('| ' + ' | '.join(r) + ' |')
        L.append(f'- جایگاه نسبی: {ctx.get("peer_pos", UNK)}')
    else:
        L.append(f'- {CANT} — داده چند نماد هم‌صنعت با قیمت/مالی هم‌زمان در ورودی نیست.')
    L.append('')
    # 15 استرس‌تست
    L.append('## ۱۵. سناریوهای استرس‌تست کلان')
    st_rows = ctx.get('stress')
    if st_rows:
        L.append('| سناریو | مفروضات کلیدی (نرخ ارز/انرژی) | اثر بر EPS | اثر بر ارزش منصفانه |')
        L.append('|---|---|---|---|')
        for r in st_rows:
            L.append('| ' + ' | '.join(r) + ' |')
    else:
        L.append(f'- {CANT} — صورت سود و زیان تفصیلی با تفکیک ارزی/انرژی در ورودی نیست.')
        L.append('| سناریو | مفروضات کلیدی (نرخ ارز/انرژی) | اثر بر EPS | اثر بر ارزش منصفانه |')
        L.append('|---|---|---|---|')
        L.append('| خوش‌بینانه | قابل برآورد نیست | قابل برآورد نیست | قابل برآورد نیست |')
        L.append('| پایه | قابل برآورد نیست | قابل برآورد نیست | قابل برآورد نیست |')
        L.append('| بدبینانه | قابل برآورد نیست | قابل برآورد نیست | قابل برآورد نیست |')
    L.append(f'- ریسک رگولاتوری/قیمت‌گذاری دستوری خاص صنعت: {UNK}')
    L.append('')
    # 16 ریسک
    L.append('## ۱۶. معیارهای ریسک و نوسان')
    rk = ctx.get('risk')
    if rk:
        L.append(f'- انحراف معیار سالانه بازده: {pct(rk["vol_annual"])}')
        L.append(f'- بتا (β) نسبت به شاخص کل: {CANT} — داده هم‌زمان شاخص کل در ورودی نیست')
        L.append(f'- ضریب همبستگی با شاخص کل: {CANT} — داده شاخص کل در ورودی نیست')
        L.append(f'- حداکثر افت تاریخی در کل بازه داده: {pct(rk["max_dd"])}')
    else:
        L.append(f'- {CANT} — داده کافی نیست')
    L.append('')
    # 17 بلوکی
    L.append('## ۱۷. معاملات بلوکی و اشخاص وابسته')
    L.append('- فاقد داده (جدول مربوطه در ورودی موجود نیست)')
    L.append('| تاریخ | نوع (بلوکی/وابسته) | طرفین معامله | تعداد سهم | قیمت | درصد نسبت به سرمایه |')
    L.append('|---|---|---|---|---|---|')
    L.append('')
    # 18 خلاصه
    L.append('## ۱۸. خلاصه تصمیم‌یار')
    unknown_cnt = ctx.get('unknown_fields', 0)
    conf = 'پایین' if unknown_cnt > 10 else ('متوسط' if unknown_cnt > 4 else 'بالا')
    L.append(f'- سیگنال تکنیکال کلی: {ctx.get("tech_signal", UNK)}')
    L.append(f'- سیگنال بنیادی کلی: {NA} (دارایی غیرسهامی بدون صورت مالی)')
    L.append(f'- سیگنال ارزش‌گذاری: {CANT}')
    L.append(f'- سیگنال جریان نقدینگی امروز: {ctx.get("flow_signal", UNK)}')
    L.append(f'- سیگنال نسبی به هم‌گروهی‌ها: {CANT}')
    L.append(f'- ریسک سناریو بدبینانه کلان: {CANT}')
    L.append(f'- سطح ریسک نوسان نسبت به بازار: {CANT} (بتا قابل محاسبه نیست) — انحراف معیار سالانه: {pct(ctx["risk"]["vol_annual"]) if ctx.get("risk") else UNK}')
    L.append(f'- ریسک‌های فعال شناسایی‌شده: {ctx.get("risks", UNK)}')
    L.append(f'- تناقض‌ها: {ctx.get("contras", "تناقض سیگنالی مشاهده نشد (اکثر فیلدها قابل محاسبه نیستند)")}')
    L.append(f'- درجه اطمینان کلی سند بر اساس تعداد فیلدهای نامشخص ({unknown_cnt} فیلد): **{conf}**')
    L.append('- یادآوری: «این خلاصه تجمیع خودکار داده‌های همین صفحه است، نه توصیه سرمایه‌گذاری؛ تصمیم نهایی و مسئولیت آن با خود سرمایه‌گذار است.»')
    L.append('')
    # 19 شفافیت
    L.append('## ۱۹. شفافیت تشخیص خودکار')
    L.append(f'- فیلدهای نامشخص باقی‌مانده: {unknown_cnt} مورد (عمدتاً شناسنامه سهامی، NAV، حقیقی/حقوقی، ارزش‌گذاری سهامی، DCF)')
    L.append('- جدول درجه اطمینان تشخیص ستون‌ها: در فایل مشترک `detection_log.csv` (همراه همه نمادها).')
    L.append('')
    return '\n'.join(L), unknown_cnt, conf

# ---------- main ----------
def main():
    hist = etl.load_history_files()
    metals = etl.load_metals_ticks()
    funds = etl.load_funds_intraday()
    codal_fin = etl.load_codal_financials()
    codal_html = etl.load_codal_html_reports()
    monthly = etl.load_codal_monthly()
    holdings = etl.load_holdings_portfolio()

    # detection log entries (name-based path = high confidence)
    for _sym, info in hist.items():
        dlog(info['source'], 'date/open/high/low/close', 'قیمت روزانه OHLC', 'نام‌محور', 'بالا', 'قیمت روزانه',
             f'سری {info["n"]} روزه از {info["first"]} تا {info["last"]}؛ واحد تشخیص: {info["unit"]}')
    for sym, info in metals.items():
        dlog('t.bin', 'date/time/price/change_percent', 'قیمت درون‌روز/لحظه‌ای', 'نام‌محور', 'بالا', 'قیمت درون‌روز',
             f'{sym}: {info["n"]} تیک در ۳۹ روز؛ واحد دلار')
    for sym, info in funds.items():
        dlog('top50_funds_intraday', 'time/price/volume/canceled', 'قیمت درون‌روز/لحظه‌ای', 'نام‌محور', 'بالا', 'قیمت درون‌روز',
             f'{sym}: {info["n"]} تیک یک جلسه ({info["last_trade_date"]})')
    for comp, data in codal_fin.items():
        dlog(data['source'], 'درآمد عملیاتی/سود ناخالص/عملیاتی/خالص/EPS/دارایی/بدهی/حقوق مالکانه', 'صورت سودوزیان و ترازنامه', 'نام‌محور', 'بالا', 'صورت مالی میان‌دوره/سالیانه',
             f'{comp}: دوره منتهی به {data["periods"][0]} در مقابل {data["periods"][1]}')
    for comp, recs in codal_html.items():
        for rec in recs:
            kind = 'سود تقسیمی/مجامع' if 'مجمع' in rec['subject'] else ('سهامداران' if rec['shareholders'] else 'حسابرسی')
            dlog(f'codal/{comp}/{rec["file"]}', 'اسامی سهامداران/تعداد سهام/درصد مالکیت' if rec['shareholders'] else 'متن اظهارنظر', kind, 'نام‌محور', 'متوسط', 'اطلاعیه کدال', rec['subject'][:60])
    for comp, data in monthly.items():
        dlog(f'codal/{comp}/{data["source"]}', 'نام محصول/تعداد فروش/مبلغ فروش', 'گزارش فعالیت ماهانه', 'نام‌محور', 'بالا', 'فعالیت ماهانه',
             f'جمع فروش داخلی ماهانه: {fmt(data.get("month_sales_million_rial"), 0)} میلیون ریال' if data.get('month_sales_million_rial') else 'مجموع فروش استخراج نشد')
    if holdings:
        dlog(f'codal/هلد پایندگان/{holdings["source"]}', 'نام شرکت/تعداد سهام/بهای تمام شده/ارزش بازار', 'داده پرتفوی هلدینگ', 'نام‌محور', 'بالا', 'پرتفوی هلدینگ',
             f'{len(holdings["companies"])} شرکت پرتفویی')

    pages_meta = []

    # ---- A) history symbols ----
    for sym, info in hist.items():
        cat = classify_symbol(sym, 'hist')
        rows = info['rows']
        tech = analytics.tech_snapshot(rows)
        closes = [float(r['close']) for r in rows]
        risk = analytics.risk_metrics(closes)
        bt_split = analytics.backtest_split(rows)
        ml = analytics.ml_run(rows)
        # zero-volume/flat detection (no volume column in history; flat close runs)
        flat_runs = 0
        run = 0
        for i in range(1, len(closes)):
            if closes[i] == closes[i - 1]:
                run += 1
                flat_runs = max(flat_runs, run)
            else:
                run = 0
        risk_note = []
        if flat_runs >= 30:
            risk_note.append(f'قیمت ثابت طولانی ({flat_runs} روز متوالی) — نشانه داده رسمی/رسمی‌سازی نرخ، نه معامله واقعی')
        if risk and risk['vol_annual'] > 60:
            risk_note.append(f'نوسان سالانه بسیار بالا ({fmt(risk["vol_annual"], 1)}%)')
        tech_signal = UNK
        if tech:
            sigs = []
            if tech['sma20'] and tech['sma50']:
                sigs.append(1 if tech['sma20'] > tech['sma50'] else -1)
            if tech['macd_hist'] is not None:
                sigs.append(1 if tech['macd_hist'] > 0 else -1)
            if tech['rsi14']:
                if tech['rsi14'] > 70: sigs.append(-1)
                elif tech['rsi14'] < 30: sigs.append(1)
            if sigs and sum(sigs) > 0: tech_signal = 'صعودی (SMA20>SMA50 و مومنتوم مثبت)'
            elif sigs and sum(sigs) < 0: tech_signal = 'نزولی (SMA20<SMA50 و مومنتوم منفی)'
            else: tech_signal = 'خنثی/مختلط'
        ctx = {
            'category': cat, 'source': info['source'], 'tech': tech, 'bt': bt_split, 'ml': ml, 'risk': risk,
            'tech_signal': tech_signal, 'risks': '؛ '.join(risk_note) if risk_note else 'ریسک خاصی از داده استخراج نشد',
            'unknown_fields': 10,
        }
        name_map = {'USD': 'دلار آمریکا (نرخ آزاد)', 'EUR': 'یورو', 'XAUUSD': 'انس طلا جهانی'}
        info.setdefault('name', name_map.get(sym, UNK))
        page, uc, conf = build_page(sym, info, ctx)
        with open(os.path.join(OUT, 'pages', sym + '.md'), 'w', encoding='utf-8') as f:
            f.write(page)
        pages_meta.append({'sym': sym, 'cat': cat[0], 'sub': cat[1], 'last': tech['close'] if tech else None,
                           'date': tech['date'] if tech else UNK, 'n': info['n'], 'rsi': tech['rsi14'] if tech else None,
                           'ret21': tech['ret21'] if tech else None, 'vol': risk['vol_annual'] if risk else None,
                           'file': sym + '.md', 'unit': info['unit'], 'conf': conf, 'unknowns': uc,
                           'bt': bool(bt_split), 'ml': bool(ml), 'src': 'history_data'})
    print(f'history pages: {len(pages_meta)}')

    # ---- B) metals intraday ----
    for sym, info in metals.items():
        # resample to daily OHLC from ticks
        by_day = {}
        for r in info['rows']:
            by_day.setdefault(r['date'], []).append(float(r['price']))
        drows = [{'date': d, 'open': v[0], 'high': max(v), 'low': min(v), 'close': v[-1]}
                 for d, v in sorted(by_day.items(), key=lambda kv: etl.jdate_key(kv[0]))]
        tech = analytics.tech_snapshot(drows)
        risk = analytics.risk_metrics([r['close'] for r in drows])
        bt_split = analytics.backtest_split(drows)
        ml = analytics.ml_run(drows)
        intraday_rows = sorted(info['rows'], key=lambda r: (etl.jdate_key(r['date']), r['time']))
        last = intraday_rows[-1]
        day_ticks = intraday_rows[-1]['date']
        todays = [r for r in intraday_rows if r['date'] == day_ticks]
        intr = [
            ('آخرین قیمت لحظه‌ای', f'{fmt(float(last["price"]))} دلار'),
            ('زمان آخرین بروزرسانی', f'{jdate_words(day_ticks)} ساعت {last["time"]}'),
            ('بهترین قیمت و حجم صف خرید', 'فاقد داده (ساختار بازار جهانی SPOT صف ندارد)'),
            ('بهترین قیمت و حجم صف فروش', 'فاقد داده'),
            ('وضعیت صف', NA),
            ('حجم و تعداد معاملات امروز', f'{len(todays)} تیک ثبت‌شده در این جلسه'),
        ]
        cat = classify_symbol(sym, 't.bin')
        ctx = {
            'category': cat, 'source': info['source'], 'tech': tech, 'bt': bt_split, 'ml': ml, 'risk': risk,
            'intraday': intr, 'tech_signal': UNK, 'unknown_fields': 11, 'risks': 'داده ۳۹ روزه — عمق تاریخی کم',
        }
        info2 = dict(info); info2['unit'] = 'دلار'
        page, uc, conf = build_page(sym, info2, ctx)
        with open(os.path.join(OUT, 'pages', sym + '.md'), 'w', encoding='utf-8') as f:
            f.write(page)
        pages_meta.append({'sym': sym, 'cat': cat[0], 'sub': cat[1], 'last': tech['close'] if tech else None,
                           'date': tech['date'] if tech else UNK, 'n': len(drows), 'rsi': tech['rsi14'] if tech else None,
                           'ret21': tech['ret21'] if tech else None, 'vol': risk['vol_annual'] if risk else None,
                           'file': sym + '.md', 'unit': 'دلار', 'conf': conf, 'unknowns': uc,
                           'bt': bool(bt_split), 'ml': bool(ml), 'src': 't.bin'})
    print(f'+metals: {len(pages_meta)}')

    # ---- C) funds intraday ----
    for sym, info in funds.items():
        ticks = info['ticks']
        prices = [p for _, p, _ in ticks]
        vols = [v for _, _, v in ticks]
        vwap = sum(p * v for _, p, v in ticks) / sum(vols) if sum(vols) else None
        first, last = ticks[0], ticks[-1]
        chg = (last[1] / first[1] - 1) * 100 if first[1] else None
        # 5-min candlesticks for technicals
        buckets = {}
        for t, p, _v in ticks:
            h, m = t.split(':')[:2]
            buckets.setdefault((h, int(m) // 5 * 5), []).append((t, p))
        candles = []
        for (h, m), lst in sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            ps = [p for _, p in lst]
            candles.append({'date': f'{h}:{m:02d}', 'open': ps[0], 'high': max(ps), 'low': min(ps), 'close': ps[-1]})
        tech = analytics.tech_snapshot(candles) if len(candles) >= 20 else None
        risk = None  # single day, annualization meaningless
        intr = [
            ('آخرین قیمت لحظه‌ای', f'{fmt(last[1], 0)} ریال'),
            ('زمان آخرین بروزرسانی', f'جلسه {info["last_trade_date"]} ساعت {last[0]}'),
            ('بهترین قیمت و حجم صف خرید', 'فاقد داده (تیک معاملات، اطلاعات صف ندارد)'),
            ('بهترین قیمت و حجم صف فروش', 'فاقد داده'),
            ('وضعیت صف', UNK),
            ('حجم و تعداد معاملات از ابتدای جلسه', f'حجم: {fmt(sum(vols), 0)} سهم | تعداد تیک معتبر: {fmt(info["n"], 0)}'),
            ('VWAP جلسه', f'{fmt(vwap, 0)} ریال'),
            ('کف/سقف قیمت جلسه', f'{fmt(min(prices), 0)} / {fmt(max(prices), 0)} ریال'),
        ]
        ctx = {
            'category': ('صندوق سرمایه‌گذاری قابل معامله', info['sector']), 'source': info['source'],
            'tech': tech, 'bt': None, 'ml': None, 'risk': None, 'intraday': intr,
            'fund_meta': {'name': info['name'], 'sector': info['sector']},
            'is_fund': True, 'fund_last_price': last[1],
            'flow_signal': f'تغییر قیمت از ابتدای جلسه: {pct(chg)}',
            'tech_signal': 'فاقد داده کافی (فقط یک جلسه درون‌روز)' if not tech else UNK,
            'unknown_fields': 12,
            'risks': 'فقط داده یک جلسه — تحلیل روند ممکن نیست',
        }
        info2 = {'unit': 'ریال', 'name': info['name']}
        page, uc, conf = build_page(sym, info2, ctx)
        with open(os.path.join(OUT, 'pages', sym + '.md'), 'w', encoding='utf-8') as f:
            f.write(page)
        pages_meta.append({'sym': sym, 'cat': 'صندوق/ETF', 'sub': info['sector'], 'last': last[1],
                           'date': info['last_trade_date'], 'n': info['n'], 'rsi': None, 'ret21': None, 'vol': None,
                           'file': sym + '.md', 'unit': 'ریال', 'conf': conf, 'unknowns': uc,
                           'bt': False, 'ml': False, 'src': 'top50_funds_intraday'})
    print(f'+funds: {len(pages_meta)}')

    # ---- D) codal companies ----
    # share count = capital (million rial) / 1000 rial nominal * 1e6... In Iran capital in million rial, shares = capital*1e6/1000 (nominal 1000 rial)
    for comp, data in sorted(codal_fin.items()):
        fin = data['fin']
        cur_d, prev_d, unaudited = data['periods']
        shares = fin['capital']['cur'] * 1e6 / 1000 if fin.get('capital') else None  # capital million rial -> shares
        def ratio(num_, den):
            return num_ / den * 100 if (num_ is not None and den not in (None, 0)) else None
        def g(k, _fin=fin):
            return (_fin[k]['cur'], _fin[k]['prev']) if k in _fin else (None, None)
        rev_c, rev_p = g('revenue')
        gr_c, gr_p = g('gross')
        op_c, op_p = g('operating')
        nt_c, nt_p = g('net')
        eq_c, eq_p = g('equity')
        as_c, as_p = g('assets')
        db_c, db_p = g('debt_total')
        ca_c, _ = g('curr_assets')
        dc_c, _ = g('debt_cur')
        fe_c, _ = g('finexp')
        dp_c, _ = g('depr')
        eps_c, eps_p = g('eps')
        def row_for(period, rev, gr, op, nt, eps, eq, asst, db, _ca_c=ca_c, _dc_c=dc_c, _fe_c=fe_c):
            mg = ratio(gr, rev) if gr is not None else None
            mo = ratio(op, rev) if op is not None else None
            mn = ratio(nt, rev)
            roe = ratio(nt, (eq or 0)) if eq and eq > 0 else None
            roa = ratio(nt, (asst or 0)) if asst else None
            dbr = ratio(db, asst) if db is not None and asst else None
            cur_ratio = _ca_c / _dc_c if _ca_c and _dc_c else None
            cov = op / abs(_fe_c) if op is not None and _fe_c not in (None, 0) else None
            return [period, fmt(rev, 0), fmt(gr, 0) if gr is not None else UNK, fmt(op, 0) if op is not None else UNK,
                    fmt(nt, 0), fmt(eps, 0) if eps is not None else UNK, fmt(mg, 1) if mg is not None else UNK,
                    fmt(mo, 1) if mo is not None else UNK, fmt(mn, 1), UNK, UNK, fmt(roe, 1) if roe is not None else UNK,
                    fmt(roa, 1) if roa is not None else UNK, fmt(dbr, 1) if dbr is not None else UNK,
                    fmt(cur_ratio, 2) if cur_ratio else UNK, fmt(cov, 2) if cov not in (None,) else UNK]
        r1 = row_for(f'دوره منتهی به {cur_d}' + (' (حسابرسی‌نشده)' if data['periods'][2] else ''), rev_c, gr_c, op_c, nt_c, eps_c, eq_c, as_c, db_c)
        r2 = row_for(f'دوره منتهی به {prev_d} (تجدید ارائه)', rev_p, gr_p, op_p, nt_p, eps_p, eq_p, as_p, db_p)
        if rev_p:
            yoy_rev = (rev_c / rev_p - 1) * 100
            r1[9] = fmt(yoy_rev, 1)
            r2[9] = UNK
        if nt_p:
            r1[10] = fmt((nt_c / nt_p - 1) * 100, 1)
        own = None
        audit = None
        news = None
        recs = codal_html.get(comp, [])
        for rec in recs:
            if rec['shareholders']:
                own = [f'- جدول سهامداران عمده (از اطلاعیه {rec["file"][:8]}):', '| نام | تعداد سهم | درصد |', '|---|---|---|']
                for s in rec['shareholders']:
                    own.append(f'| {s["name"]} | {fmt(s["shares"], 0)} | {fmt(s["pct"], 2)}% |')
                own.append(f'- مدیرعامل: {UNK}')
                own.append('- جدول افزایش سرمایه‌ها: فاقد داده')
                own.append('- جدول سود تقسیمی سالانه: فاقد داده')
            if rec['audit'].get('firm'):
                opinion = rec['audit'].get('opinion_kw', UNK)
                audit = [f'- مؤسسه حسابرسی: {rec["audit"]["firm"]} (برای صورت مالی این دوره)', f'- نوع اظهارنظر: {opinion}']
        if not own and comp == 'هلد پایندگان' and holdings:
            own = [f'- پرتفوی هلدینگ (از اطلاعیه {holdings["source"][:9]}):',
                   '| شرکت | تعداد سهم | بهای تمام شده (میلیون ریال) | ارزش بازار (میلیون ریال) |', '|---|---|---|---|']
            for c in holdings['companies']:
                own.append(f'| {c["name"]} | {fmt(c["shares"], 0)} | {fmt(c["cost"], 0)} | {fmt(c["mv"], 0)} |')
        # news: subject lines from all reports of this company
        news = []
        for rec in recs:
            subj = rec['subject'] or ''
            if subj and 'window.close' not in subj:
                kind = 'نامشخص'
                if 'شفاف' in subj: kind = 'نامشخص (شفاف‌سازی)'
                elif 'مجمع' in subj: kind = 'خنثی (رویداد مجمع)'
                news.append([rec['file'][:10].replace('_html.htm', UNK and '') or UNK, subj[:80], subj[:60], kind])
        if not news:
            news = None
        monthly_rec = monthly.get(comp)
        stress = None
        if monthly_rec and monthly_rec.get('month_sales_million_rial'):
            stress = [
                ['خوش‌بینانه', 'نرخ ارز/انرژی در داده ورودی تفکیک نشده', 'قابل برآورد نیست', 'قابل برآورد نیست'],
                ['پایه', f'فروش داخلی ماهانه (از گزارش ماهانه): {fmt(monthly_rec["month_sales_million_rial"], 0)} میلیون ریال', 'قابل برآورد نیست', 'قابل برآورد نیست'],
                ['بدبینانه', 'نرخ ارز/انرژی در داده ورودی تفکیک نشده', 'قابل برآورد نیست', 'قابل برآورد نیست'],
            ]
        info2 = {'unit': 'میلیون ریال (صورت مالی)', 'name': {'خاذین': 'طراحی و ساخت قطعات داخلی خودرو سایپا آذین',
                                                             'سفارس': 'صنایع پتروشیمی فارس (شبهرن؟ خیر)',
                                                             }.get(comp, comp)}
        # correct names from codal subjects where known
        ctx = {
            'category': ('سهام بازار سرمایه ایران', 'بورس تهران'), 'source': data['source'],
            'fin': [r1, r2], 'bt': None, 'ml': None, 'risk': None, 'ownership': own,
            'audit': audit, 'news': news, 'stress': stress,
            'codal_news': [f'- وضعیت نماد: {UNK} (از داده ورودی قابل استخراج نیست)',
                           '- ۵ اطلاعیه اخیر کدال: فاقد داده (فقط اطلاعیه‌های پیوست‌شده پردازش شد)'],
            'unknown_fields': 9, 'risks': 'سری قیمت روزانه در ورودی نیست — تحلیل تکنیکال/ریسک قیمت ممکن نیست',
            'tech_signal': CANT,
        }
        page, uc, conf = build_page(comp, info2, ctx)
        with open(os.path.join(OUT, 'pages', comp + '.md'), 'w', encoding='utf-8') as f:
            f.write(page)
        pages_meta.append({'sym': comp, 'cat': 'سهام بازار سرمایه ایران', 'sub': 'بورس تهران', 'last': None,
                           'date': cur_d, 'n': None, 'rsi': None, 'ret21': None, 'vol': None,
                           'file': comp + '.md', 'unit': 'میلیون ریال', 'conf': conf, 'unknowns': uc,
                           'bt': False, 'ml': False, 'src': 'codal'})
    # companies with only html reports (no P&L)
    for comp, recs in codal_html.items():
        if comp in codal_fin:
            continue
        has_any = any(r['shareholders'] or r['subject'] for r in recs)
        if comp in ('خاذین', 'سخزر'):  # monthly-only
            mr = monthly.get(comp)
            fin_rows = None
            ctx = {
                'category': ('سهام بازار سرمایه ایران', 'بورس تهران'), 'source': f'codal/{comp}',
                'fin': None, 'bt': None, 'ml': None, 'risk': None,
                'codal_news': [f'- گزارش فعالیت ماهانه موجود (جمع فروش داخلی: {fmt(mr["month_sales_million_rial"], 0) if mr and mr.get("month_sales_million_rial") else UNK} میلیون ریال)'],
                'unknown_fields': 10, 'risks': 'سری قیمت و صورت مالی کامل در ورودی نیست',
                'tech_signal': CANT,
            }
        else:
            own = None
            for rec in recs:
                if rec['shareholders']:
                    own = ['- جدول سهامداران عمده:', '| نام | تعداد سهم | درصد |', '|---|---|---|']
                    for s in rec['shareholders']:
                        own.append(f'| {s["name"]} | {fmt(s["shares"], 0)} | {fmt(s["pct"], 2)}% |')
            if not own and comp == 'هلد پایندگان' and holdings:
                own = ['- پرتفوی هلدینگ (طبق اطلاعیه تفکیک سرمایه‌گذاری‌ها):',
                       '| شرکت | تعداد سهم | بهای تمام شده (میلیون ریال) | ارزش بازار (میلیون ریال) |', '|---|---|---|---|']
                for c in holdings['companies']:
                    own.append(f'| {c["name"]} | {fmt(c["shares"], 0)} | {fmt(c["cost"], 0)} | {fmt(c["mv"], 0)} |')
                own.append(f'- جمع ارزش بازار پرتفوی بورسی: {fmt(sum(c["mv"] for c in holdings["companies"]), 0)} میلیون ریال | جمع بهای تمام شده: {fmt(sum(c["cost"] for c in holdings["companies"]), 0)} میلیون ریال')
            news = []
            for rec in recs:
                subj = (rec['subject'] or '').strip()
                if subj and 'window' not in subj:
                    news.append([UNK, subj[:80], subj[:60], 'نامشخص'])
            audit = None
            for rec in recs:
                if rec['audit'].get('firm'):
                    audit = [f'- مؤسسه حسابرسی: {rec["audit"]["firm"]}', f'- نوع اظهارنظر: {rec["audit"].get("opinion_kw", UNK)}']
            ctx = {
                'category': ('سهام بازار سرمایه ایران', 'بورس تهران'), 'source': f'codal/{comp}',
                'fin': None, 'bt': None, 'ml': None, 'risk': None, 'ownership': own,
                'news': news if news else None, 'audit': audit,
                'unknown_fields': 10, 'risks': 'صورت مالی/سری قیمت در ورودی نیست',
                'tech_signal': CANT,
            }
        page, uc, conf = build_page(comp, {'unit': UNK, 'name': comp}, ctx)
        with open(os.path.join(OUT, 'pages', comp + '.md'), 'w', encoding='utf-8') as f:
            f.write(page)
        pages_meta.append({'sym': comp, 'cat': 'سهام بازار سرمایه ایران', 'sub': 'بورس تهران', 'last': None,
                           'date': UNK, 'n': None, 'rsi': None, 'ret21': None, 'vol': None,
                           'file': comp + '.md', 'unit': UNK, 'conf': conf, 'unknowns': uc,
                           'bt': False, 'ml': False, 'src': 'codal'})
    print(f'+codal: {len(pages_meta)}')

    # dedupe pages_meta (funds symbols could clash with codal? unlikely)
    # ---- detection_log.csv ----
    with open(os.path.join(OUT, 'detection_log.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['نام فایل', 'ستون انتخابی', 'نوع محتوای تشخیص‌داده‌شده', 'مسیر تشخیص', 'درجه اطمینان', 'نوع محتوا فایل', 'توضیح'])
        w.writeheader()
        for r in det_log:
            w.writerow(r)

    json.dump(pages_meta, open(os.path.join(OUT, '_pages_meta.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('TOTAL pages:', len(pages_meta))
    return pages_meta

if __name__ == '__main__':
    main()
