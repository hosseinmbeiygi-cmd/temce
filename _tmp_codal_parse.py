import re, glob, os, json, sys
sys.stdout.reconfigure(encoding='utf-8')

def cells_of(tr):
    return [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', x).replace('&nbsp;', ' ')).strip()
            for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]

def to_num(s):
    if s is None: return None
    t = s.replace('٬', '').replace('،', '').replace(',', '').replace('%', '').strip()
    t = t.replace('۰', '0').replace('۱', '1').replace('۲', '2').replace('۳', '3').replace('۴', '4') \
         .replace('۵', '5').replace('۶', '6').replace('۷', '7').replace('۸', '8').replace('۹', '9')
    m = re.search(r'-?\d+(?:\.\d+)?', t)
    return float(m.group()) if m else None

out = {}
for p in sorted(glob.glob('data/codal_attachments/codal/*/*_html.html')):
    parts = p.replace(os.sep, '/').split('/')
    comp, fname = parts[3], parts[4]
    with open(p, encoding='utf-8', errors='replace') as f:
        c = f.read()
    rec = {'file': comp + '/' + fname, 'shareholders': [], 'directors': [], 'audit': {}, 'netincome': None, 'report_date': None}
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', c, re.S)
    header_idx = {}
    for tr in rows:
        cells = cells_of(tr)
        if not cells: continue
        # shareholders block
        if 'اسامی سهامداران' in cells[0] and 'تعداد سهام' in ' '.join(cells):
            header_idx['sh'] = True
            continue
        if header_idx.get('sh') and not rec.get('sh_done'):
            if cells and to_num(cells[1]) is not None and len(cells) >= 3 and to_num(cells[2]) is not None:
                nm = cells[0]
                if nm in ('جمع', 'ساير', 'سایر', ''):
                    if nm == 'جمع': rec['sh_done'] = True
                else:
                    rec['shareholders'].append({'name': nm, 'shares': to_num(cells[1]), 'pct': to_num(cells[2])})
            else:
                if rec['shareholders']: rec['sh_done'] = True
        # audit opinion
        m = re.search(r'اظهار نظر[:：]?\s*(\S+)', ' '.join(cells))
        if m and not rec['audit'].get('opinion'):
            rec['audit']['opinion'] = m.group(1)[:40]
        # net income
        if 'NetIncomeLoss' in cells[0] and len(cells) > 1:
            rec['netincome'] = cells[1]
        # board
        if 'هیئت\u200cمدیره' in cells[0] and 'سمت' in ' '.join(cells):
            header_idx['board'] = True
            continue
        if header_idx.get('board') and not rec.get('board_done') and len(cells) >= 7 and cells[0] and 'عضو' in cells[6]:
            rec['directors'].append({'name': cells[0], 'rep': cells[4] if len(cells) > 4 else '', 'role': cells[6]})
        # auditor firm
        if 'موسسه حسابرسي' in ' '.join(cells) or 'مؤسسه حسابرسی' in ' '.join(cells) or 'سازمان حسابرسي' in ' '.join(cells) or 'سازمان حسابرسی' in ' '.join(cells):
            for x in cells:
                if 'حسابرسي' in x or 'حسابرسی' in x:
                    rec['audit']['firm'] = x.strip()
                    break
    # date from title/signature
    md = re.findall(r'\b(\d{2}[ /-](?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند))\d*', c)
    if md: rec['report_date'] = md[0]
    out[comp + '/' + fname] = rec

for k, v in out.items():
    print('=====', k)
    if v['shareholders']: print('  SH:', [(s['name'][:30], s['pct']) for s in v['shareholders'][:8]])
    if v['directors']: print('  Board:', [(d['name'][:25], d['role'][:20]) for d in v['directors'][:6]])
    if v['audit']: print('  Audit:', v['audit'])
    if v['netincome']: print('  NetIncome:', v['netincome'])
