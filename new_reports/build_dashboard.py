"""Build dashboard.md (tabs Alef/Beh/Jim + side-by-side) + run summary from _pages_meta.json."""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etl

OUT = etl.OUTDIR
UNK = 'نامشخص'
CANT = 'قابل محاسبه نیست'
DISC = ('این داشبورد، تجمیع و رتبه‌بندی خودکار داده‌های موجود در صفحات نمادهاست؛ '
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

def main():
    meta = json.load(open(os.path.join(OUT, '_pages_meta.json'), encoding='utf-8'))
    # dedupe by symbol: prefer history_data > t.bin > codal (funds unique)
    pri = {'history_data': 0, 't.bin': 1, 'top50_funds_intraday': 2, 'codal': 3}
    best = {}
    for x in meta:
        s = x['sym']
        if s not in best or pri.get(x['src'], 9) < pri.get(best[s]['src'], 9):
            best[s] = x
    rows = sorted(best.values(), key=lambda x: x['sym'])

    L = []
    L.append('# داشبورد کلی نمادها')
    L.append('')
    L.append('> ' + DISC)
    L.append('')
    L.append(f'تعداد کل نمادهای پردازش‌شده: **{len(rows)}**')
    L.append('')

    # ============ تب الف ============
    L.append('# تب الف — تحلیل داخلی')
    L.append('')
    L.append('## ۴.۱ جدول کلی غربالگری')
    L.append('ستون‌های P/E(TTM)، رشد سود خالص YoY، نسبت بدهی و Margin of Safety برای هیچ نمادی قابل محاسبه نیستند — '
             'داده ورودی شامل سری قیمت روزانه سهام بورسی، صورت مالی سالانه/میان‌دوره‌ای (بدون قیمت) یا نرخ ارز/طلاست؛ '
             'ترکیب «قیمت + EPS + بدهی» برای هیچ نمادی هم‌زمان موجود نیست. لذا غربال ۴.۲ قابل اجرا نیست و همه نمادها '
             'با علت «داده ناکافی» مشخص می‌شوند (از جدول حذف نمی‌شوند).')
    L.append('')
    L.append('| نماد | قیمت فعلی | P/E(TTM) | P/E نسبت به میانگین صنعت | رشد سود خالص YoY% | RSI14 | نسبت بدهی% | Margin of Safety% | میانگین ارزش معاملات۳۰روزه | نتیجه غربال |')
    L.append('|---|---|---|---|---|---|---|---|---|---|')
    for x in rows:
        price = fmt(x['last'], 0) if x['last'] else UNK
        rsi = fmt(x['rsi']) if x['rsi'] is not None else UNK
        L.append(f"| {x['sym']} | {price} ({x['unit']}) | {CANT} | {CANT} | {CANT if x['cat'] != 'سهام بازار سرمایه ایران' else UNK} | {rsi} | {CANT if x['cat'] == 'سهام بازار سرمایه ایران' else NA_MARK(x)} | {CANT} | {CANT} | رد شد — دلیل: داده ناکافی |")
    L.append('')
    L.append('## ۴.۲ فیلترهای غربالگری پیش‌فرض')
    L.append('- شرط P/E < میانگین صنعت: قابل ارزیابی نیست (P/E برای هیچ نماد داده‌ای ندارد)')
    L.append('- شرط رشد سود خالص YoY > ۰: فقط برای ۷ شرکت صورت مالی موجود است و قیمت/مقایسه سالانه هم‌زمان ندارد — قابل ارزیابی نیست')
    L.append('- شرط RSI بین ۳۰ و ۷۰: قابل ارزیابی برای ۹۹ نماد دارای سری قیمت (در جدول ۴.۱)')
    L.append('- شرط نسبت بدهی < ۷۰٪: نسبت بدهی ترازنامه برای ۷ شرکت قابل محاسبه است اما قیمت بازار ندارد — ترکیب شرط ممکن نیست')
    L.append('- شرط ارزش معاملات ۳۰روزه > ۵ میلیارد تومان: ستون ارزش/حجم در سری‌های قیمتی ورودی وجود ندارد — قابل ارزیابی نیست')
    L.append('- شرط Margin of Safety > ۰: ارزش منصفانه قابل محاسبه نیست')
    L.append('- **نتیجه: هیچ نمادی از غربال عبور نکرد؛ علت همه: داده ناکافی برای ترکیب شرایط غربال.**')
    L.append('')
    L.append('## ۴.۳ و ۴.۴ امتیاز رتبه‌بندی و فهرست پیشنهادی')
    L.append('- چون هیچ نمادی از غربال عبور نکرد، امتیاز ۴.۳ و فهرست Top Candidates ۴.۴ **تولید نشد** — تولید عدد بدون داده، نقض قانون صداقت این پرامپت است.')
    L.append('')
    L.append('## ۴.۵ جدول نمادهای دارای تناقض')
    L.append('- تناقض سیگنال قابل استخراج: برای ۲ شرکت صورت مالی، سود خالص دوره جاری بهبود یافته اما اظهارنظر حسابرسی مردود/مشروط است:')
    L.append('| نماد | تناقض |')
    L.append('|---|---|')
    L.append('| پارسان | روند سود خالص بهبود یافته (زیان کاهش یافته) ولی اظهارنظر حسابرسی: **مردود** |')
    L.append('| وکار | سودآوری بالا ولی اظهارنظر حسابرسی: **مشروط** (آثار موارد عدم رعایت الزامات) |')
    L.append('')

    # ============ تب ب ============
    L.append('# تب ب — سیستم امتیازدهی اختصاصی کاربر (۱۱۰ پارامتر)')
    L.append('')
    L.append('در جداول خام ورودی این اجرا، **هیچ جدولی با الگوی «شمار زیاد ستون عددی به‌ازای هر نماد که به ستون امتیاز/رتبه/برچسب نهایی ختم شود» شناسایی نشد.** '
             'جداول ورودی عبارت‌اند از: سری قیمت روزانه OHLC، تیک درون‌روز فلزات و صندوق‌ها، صورت‌های مالی کدال (شرح/دوره)، و اطلاعیه‌های کدال. '
             'هیچ‌کدام ۱۱۰ پارامتر عددی به‌ازای نماد با خروجی امتیاز ندارند. لذا این تب با محتوای «فاقد داده — جدول سیستم امتیازدهی کاربر در ورودی یافت نشد» پر می‌شود و طبق قاعده ۴.۶ هیچ مقداری جعل نشد.')
    L.append('')

    # ============ جدول مقایسه ============
    L.append('# مقایسه کنار هم دو تحلیل (فقط برای دید کاربر)')
    L.append('')
    L.append('| نماد | نتیجه غربال تب الف | امتیاز داخلی تب الف | نتیجه/امتیاز تب ب (خام) | هم‌جهت یا ناهم‌جهت؟ |')
    L.append('|---|---|---|---|---|')
    for x in rows:
        L.append(f"| {x['sym']} | رد شد (داده ناکافی) | بدون امتیاز (عبورکرده‌ای وجود ندارد) | فاقد داده (سیستم کاربر در ورودی نیست) | ناهم‌جهت — نیاز به بررسی دستی |")
    L.append('')

    # ============ تب ج ============
    L.append('# تب ج — فهرست شناسنامه و خلاصه سریع همه نمادها')
    L.append('')
    L.append('| نماد | نام کامل شرکت | صنعت | زیرصنعت | بازار | سرمایه ثبتی | تعداد سهام | آخرین قیمت | تغییر روزانه% | وضعیت نماد | نام فایل صفحه اختصاصی |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for x in rows:
        price = fmt(x['last'], 0) if x['last'] else UNK
        L.append(f"| {x['sym']} | {UNK} | {x['cat']} | {x['sub']} | فاقد موضوعیت (دارایی غیربورسی/صندوق/ارز) | {UNK} | فاقد موضوعیت | {price} {x['unit'] if x['last'] else ''} | {UNK} | {UNK} | {x['file']} |")
    L.append('')
    L.append('**گروه‌بندی بر اساس صنعت:**')
    L.append('')
    bycat = {}
    for x in rows:
        bycat.setdefault(x['cat'], []).append(x)
    for cat in sorted(bycat):
        L.append(f'### {cat}')
        L.append('')
        for x in bycat[cat]:
            price = fmt(x['last'], 0) if x['last'] else UNK
            L.append(f"- **{x['sym']}** — آخرین قیمت: {price} {x['unit'] if x['last'] else ''} | تعداد مشاهدات: {x['n'] if x['n'] else UNK} | صفحه: {x['file']}")
        L.append('')

    with open(os.path.join(OUT, 'dashboard.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))

    # ---- run summary ----
    n = len(rows)
    # completeness: count filled fields roughly from unknowns count (19 fields total per spec)
    filled = [(19 - x['unknowns']) / 19 * 100 for x in rows]
    avg = sum(filled) / len(filled)
    worst = sorted(rows, key=lambda x: x['unknowns'], reverse=True)[:8]
    S = []
    S.append('# گزارش خلاصه اجرا')
    S.append('')
    S.append(f'- تعداد کل نمادهای پردازش‌شده: **{n}**')
    S.append(f'- میانگین درصد فیلدهای پرشده به‌ازای هر نماد (شاخص کامل‌بودن، از ۱۹ فیلد الزامی صفحه): **{avg:.1f}%**')
    ml_cnt = sum(1 for x in rows if x['ml'])
    bt_cnt = sum(1 for x in rows if x['bt'])
    S.append(f'- نمادهای دارای مدل ML اجراشده: {ml_cnt} | دارای بک‌تست In/Out-of-Sample: {bt_cnt}')
    S.append(f'- خروجی‌ها: {n} صفحه در `pages/`، `dashboard.md`، `detection_log.csv`')
    S.append('')
    S.append('## توزیع دسته‌ها')
    from collections import Counter
    for cat, c in Counter(x['cat'] for x in rows).most_common():
        S.append(f'- {cat}: {c}')
    S.append('')
    S.append('## نمادهای نیازمند بررسی دستی (بیشترین فیلد نامشخص)')
    for x in worst:
        S.append(f"- **{x['sym']}** — {x['unknowns']} فیلد از ۱۹ نامشخص (منبع: {x['src']})")
    S.append('')
    S.append('## یادداشت صداقت')
    S.append('- هیچ عددی در صفحات جعل نشده؛ فیلدهای بدون داده با «نامشخص/فاقد موضوعیت/قابل محاسبه نیست» پر شدند.')
    S.append('- غربالگری تب الف به دلیل فقدان هم‌زمان «قیمت + صورت مالی» برای هیچ نمادی، عبورکرده‌ای تولید نکرد.')
    S.append('- ML و بک‌تست فقط روی سری‌های قیمتی با عمق کافی اجرا شد؛ هشدار Overfitting عیناً در صفحات درج شد.')
    with open(os.path.join(OUT, 'run_summary.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(S))
    print('dashboard + summary done:', n, 'symbols')

def NA_MARK(x):
    return 'فاقد موضوعیت'

if __name__ == '__main__':
    main()
