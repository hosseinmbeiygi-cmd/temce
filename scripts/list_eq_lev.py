import json

with open('json/brsapi/symbol_details.json', encoding='utf-8') as fh:
    d = json.load(fh)
recs = d['records']
lev = sorted({r.get('symbol') for r in recs if (r.get('sub_sector') or '') == 'صندوق های سرمایه گذاری اهرمی' and r.get('symbol')})
eq = sorted({r.get('symbol') for r in recs if (r.get('sub_sector') or '') == 'صندوق سرمایه گذاری در سهام' and r.get('symbol')})
out = {"leveraged": lev, "equity": eq}
with open('C:/Users/Iran/AppData/Local/Temp/opencode/funds_eq_lev.json', 'w', encoding='utf-8') as fh:
    fh.write(json.dumps(out, ensure_ascii=False, indent=2))
print("OK", len(lev), len(eq))
