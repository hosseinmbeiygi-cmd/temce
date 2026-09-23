"""ETL: load all raw input tables (price history, tick data, codal financials)."""
import csv
import glob
import gzip
import json
import os
import re
import statistics as st

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(BASE, 'new_symbol_reports')

def fa2en(s):
    return s.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹/', '0123456789/'))

def jdate_key(d):
    """Shamsi date '1405/05/01' -> sortable int 14050501 (first-of-month rows kept as-is)."""
    return int(fa2en(d).replace('/', '')[:8])

def detect_scale(close):
    """Rial (>=10000) vs Toman. History prices are Rial per project data (USD ~1.9M)."""
    return 'ریال' if st.median(close) >= 5000 else 'نامشخص(احتمالاً تومان)'

def load_history_files():
    """95 daily OHLC JSON files in history_data/. Returns {symbol: {rows, meta}}."""
    out = {}
    for p in sorted(glob.glob(os.path.join(BASE, 'history_data', '*_history.json'))):
        sym = os.path.basename(p).replace('_history.json', '')
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        rows = d if isinstance(d, list) else d.get('history_daily', [])
        if not rows:
            continue
        # files are newest-first; sort ascending
        rows = sorted(rows, key=lambda r: jdate_key(r['date']))
        closes = [float(r['close']) for r in rows]
        out[sym] = {
            'rows': rows,
            'n': len(rows),
            'first': rows[0]['date'], 'last': rows[-1]['date'],
            'unit': detect_scale(closes),
            'source': 'history_data/' + os.path.basename(p),
        }
    return out

def load_metals_ticks():
    """t.bin: intraday tick snapshots for XAU/XAG/XPD/XPT (39 days, ~50 ticks/day)."""
    with open(os.path.join(BASE, 't.bin'), encoding='utf-8') as f:
        d = json.load(f)
    out = {}
    for r in d['data']:
        out.setdefault(r['symbol'], []).append(r)
    res = {}
    for sym, rows in out.items():
        rows.sort(key=lambda r: (jdate_key(r['date']), r['time']))
        res[sym] = {
            'rows': rows, 'n': len(rows),
            'first': rows[0]['date'], 'last': rows[-1]['date'],
            'unit': 'دلار', 'name': rows[0].get('name', ''),
            'source': 't.bin (تیک درون‌روز)',
        }
    return res

def load_funds_intraday():
    """top50 funds: one trading day tick data per fund (from funds/*.csv.gz + summary)."""
    meta = {}
    with open(os.path.join(BASE, 'data/top50_funds_intraday/summary.csv'), encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            meta[r['symbol']] = r
    out = {}
    fdir = os.path.join(BASE, 'data/top50_funds_intraday/funds')
    for p in sorted(glob.glob(fdir + os.sep + '*.csv.gz')):
        sym = os.path.basename(p)[:-7]
        ticks = []
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            rd = csv.DictReader(f)
            for row in rd:
                if row.get('canceled', 'False') == 'True':
                    continue
                ticks.append((row['time'], float(row['price']), int(row['volume'])))
        if not ticks:
            continue
        m = meta.get(sym, {})
        out[sym] = {
            'ticks': ticks, 'n': len(ticks),
            'name': m.get('name', ''), 'sector': m.get('sector', ''),
            'market_value': float(m.get('market_value') or 0),
            'last_trade_date': m.get('last_trade_date', ''),
            'price_min': float(m.get('price_min') or 0), 'price_max': float(m.get('price_max') or 0),
            'volume': float(m.get('volume') or 0), 'value': float(m.get('value') or 0),
            'source': 'data/top50_funds_intraday (تیک درون‌روز یک جلسه)',
        }
    return out

# ---------- Codal HTML-as-Excel parsing ----------

def _norm(s):
    s = s.replace('\u200c', ' ').replace('&nbsp;', ' ')
    s = s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s)).strip()

def _num(s):
    t = fa2en(s).replace(',', '').replace('٬', '').strip().rstrip('%')
    neg = t.startswith('(') and t.endswith(')')
    t = t.strip('()')
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v

def _table_rows(html):
    out = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        cells = [_norm(x) for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
        if cells and any(cells):
            out.append(cells)
    return out

# canonical financial row labels -> regex on normalized first cell
PL_PATS = {
    'revenue': r'^(جمع )?درآمدهای عملیاتی$',
    'gross': r'^سود ?\(زیان\) ناخالص$',
    'operating': r'^سود ?\(زیان\) عملیاتی$',
    'net': r'^سود ?\(زیان\) خالص$',
    'eps': r'^سود ?\(زیان\) خالص هر سهم',
    'finexp': r'^هزینه ?های? مالی$',
    'depr': r'^هزینه استهلاک$',
    'capex': r'^پرداخت ?های? نقدی برای خرید دارایی ?های? ثابت',
}
BS_PATS = {
    'equity': r'^جمع حقوق مالکانه$',
    'capital': r'^سرمایه$',
    'assets': r'^جمع دارایی ?ها?$',
    'curr_assets': r'^جمع دارایی ?های? جاری$',
    'debt_cur': r'^جمع بدهی ?های? جاری$',
    'debt_total': r'^جمع بدهی ?ها?$',
    'cash': r'^موجودی نقد',
}
PERIODS = {  # per-symbol: (current_date, prior_date, current is unaudited?)
    'خاذین': ('1405/03/31', '1404/03/31', True),
    'سفارس': ('1405/02/31', '1404/02/31', True),
    'فارس': ('1405/02/31', '1404/02/31', True),
    'وبهمن': ('1405/03/31', '1404/03/31', True),
    'وکار': ('1404/12/29', '1403/12/30', True),
    'وگنجینه ایرانیان': ('1405/03/31', '1404/03/31', True),
    'پارسان': ('1404/12/29', '1403/12/30', True),
}

def load_codal_financials():
    """P&L+BS from codal *_excel.xlsx (HTML framesets) for companies with statements."""
    res = {}
    cdir = os.path.join(BASE, 'data/codal_attachments/codal')
    for d in sorted(glob.glob(cdir + os.sep + '*')):
        comp = os.path.basename(d)
        if comp not in PERIODS:
            continue
        files = sorted(glob.glob(d + os.sep + '*_excel.xlsx'))
        if not files:
            continue
        with open(files[0], encoding='utf-8', errors='replace') as f:
            html = f.read()
        trs = _table_rows(html)
        fin = {}
        for r in trs:
            k0 = r[0]
            for k, pat in {**PL_PATS, **BS_PATS}.items():
                if k in fin:
                    continue
                if re.match(pat, k0) and len(r) > 1 and _num(r[1]) is not None:
                    # current col=1, prior col=2
                    fin[k] = {'cur': _num(r[1]), 'prev': _num(r[2]) if len(r) > 2 and _num(r[2]) is not None else None}
        if fin:
            res[comp] = {
                'fin': fin,
                'periods': PERIODS[comp],
                'source': 'data/codal_attachments/codal/' + comp + '/' + os.path.basename(files[0]),
            }
    return res

def load_codal_html_reports():
    """Shareholder tables, audit opinions, board lists, monthly reports, notices."""
    out = {}
    cdir = os.path.join(BASE, 'data/codal_attachments/codal')
    for p in sorted(glob.glob(cdir + os.sep + '*' + os.sep + '*_html.html')):
        parts = p.replace(os.sep, '/').split('/')
        comp, fname = parts[-2], parts[-1]
        with open(p, encoding='utf-8', errors='replace') as f:
            html = f.read()
        trs = _table_rows(html)
        plain = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html).replace('&nbsp;', ' '))
        rec = {'file': fname, 'shareholders': [], 'board': [], 'audit': {}, 'subject': ''}
        m = re.search(r'موضوع[:：]\s*(.{0,140})', plain)
        if m:
            rec['subject'] = m.group(1).strip()
        # shareholders table: after header ['اسامی سهامداران','تعداد سهام','درصد مالکیت']
        sh_open = False
        for r in trs:
            if 'اسامی سهامداران' in r[0] and 'تعداد سهام' in ' '.join(r):
                sh_open = True
                continue
            if sh_open:
                if r[0] == 'جمع':
                    sh_open = False
                elif r[0] and len(r) >= 3 and _num(r[1]) is not None:
                    rec['shareholders'].append({'name': r[0], 'shares': _num(r[1]), 'pct': _num(r[2])})
        # audit opinion keywords
        for kw, label in [('مشروط', 'مشروط'), ('مردود', 'مردود'), ('عدم اظهارنظر', 'عدم اظهارنظر'),
                          ('بررسی اجمالی', 'بررسی اجمالی (صورت‌های میان‌دوره‌ای)'), ('تأکید بر مطلب خاص', 'مقبول با تأکید بر مطلب خاص')]:
            if kw in plain:
                rec['audit']['opinion_kw'] = label
                break
        # auditor firm
        for r in trs:
            joined = ' '.join(r)
            if ('موسسه حسابرسی' in joined or 'مؤسسه حسابرسی' in joined or 'سازمان حسابرسی' in joined) and 'موسسه حسابرسي بهمند' not in joined:
                for x in r:
                    if 'حسابرسی' in x and len(x) < 60:
                        rec['audit']['firm'] = x.strip()
                        break
                if rec['audit'].get('firm'):
                    break
        if not rec['audit'].get('firm'):
            m2 = re.search(r'((?:موسسه|مؤسسه|سازمان) حسابرسی [^\s<،"]{2,30})', plain)
            if m2:
                rec['audit']['firm'] = m2.group(1)
        # board members (rows with role in col 7 like 'عضو هیئت مدیره')
        for r in trs:
            if len(r) >= 7 and r[0] and r[0] != 'نام عضو حقیقی یا حقوقی هیئت مدیره' and ('عضو هیئت مدیره' in r[6] or 'رئیس هیئت' in r[6] or 'نایب رئیس' in r[6]):
                rec['board'].append({'name': r[0], 'rep': r[4] if len(r) > 4 else '', 'role': r[6]})
        out.setdefault(comp, []).append(rec)
    return out

def load_codal_monthly():
    """Monthly activity sales (خاذین ن-۳۰, سخزر ن-۳۰) — top-line sales from production tables."""
    res = {}
    spec = {'خاذین': 'ن-۳۰', 'سخزر': 'ن-۳۰'}
    cdir = os.path.join(BASE, 'data/codal_attachments/codal')
    for comp, pref in spec.items():
        for p in glob.glob(os.path.join(cdir, comp, pref + '_excel.xlsx')):
            with open(p, encoding='utf-8', errors='replace') as f:
                html = f.read()
            trs = _table_rows(html)
            # sum of 'مبلغ فروش' columns for month section: rows with product names.
            # Simplest robust figure: find row 'جمع فروش داخلی' (Sukhozr had it); else sum 'مبلغ فروش' col in month block.
            total = None
            for r in trs:
                if r[0].startswith('جمع فروش داخلی') and len(r) > 4 and _num(r[4]) is not None:
                    total = _num(r[4])
                    break
            res[comp] = {'month_sales_million_rial': total, 'source': os.path.basename(p)}
    return res

def load_holdings_portfolio():
    """هلد پایندگان ن-۳۱: portfolio by company (bourse market value vs cost)."""
    p = None
    cdir = os.path.join(BASE, 'data/codal_attachments/codal')
    for f in glob.glob(os.path.join(cdir, 'هلد پایندگان', '*_excel.xlsx')):
        p = f
    if not p:
        return None
    with open(p, encoding='utf-8', errors='replace') as f:
        html = f.read()
    trs = _table_rows(html)
    comps = []
    for r in trs:
        if r[0] in ('فولاد خوزستان', 'سرمایه گذاری غدیر', 'بورس اوراق بهادار تهران', 'خدمات انفورماتیک',
                    'فرابورس ایران', 'گروه مپنا', 'سرمایه گذاری نفت و گاز و پتروشیمی', 'بیمه هوشمند فردا',
                    'توسعه سامانه های نرم افزاری نگین', 'ریل گردش ایرانیان', 'سیمان خزر', 'درین بها بازار',
                    'سرمایه گذاری داروئی تامین') and len(r) > 6:
            comps.append({'name': r[0], 'shares': _num(r[3]), 'cost': _num(r[4]), 'mv': _num(r[5])})
    return {'companies': comps, 'source': os.path.basename(p)}

if __name__ == '__main__':
    h = load_history_files()
    t = load_metals_ticks()
    f = load_funds_intraday()
    c = load_codal_financials()
    r = load_codal_html_reports()
    m = load_codal_monthly()
    hp = load_holdings_portfolio()
    print('history:', len(h), '| metals:', len(t), '| funds:', len(f), '| codal fin:', len(c), '| codal html:', len(r), '| monthly:', len(m), '| holdings:', bool(hp))
