import json

import z

METALS = ["فلزفارابی","متال","استیل","فلزا","پولاد","معدن","مسگون","آلیاژ","صنوین"]
with open("metal_rank.json","w",encoding="utf-8") as f:
    json.dump(METALS, f, ensure_ascii=False, indent=2)
z.FUND_RANK_FILE = "metal_rank.json"
z.TOP_FUNDS_COUNT = len(METALS)
z.RECENT_MONTHS = 1200
z.MARKET_FILTER = "funds_only"
z.MAX_WORKERS = 6
symbols = z.extract_all_symbols()
print("ALL:", len(symbols))
col = z.SmartCollector(symbols)
col.run()
