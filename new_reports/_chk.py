import glob
import os

import etl

cdir = "data/codal_attachments/codal"
for comp in ["خاذین", "سخزر"]:
    for p in glob.glob(cdir + "/" + comp + "/*_excel.xlsx"):
        with open(p, encoding="utf-8", errors="replace") as f:
            html = f.read()
        trs = etl._table_rows(html)
        print("=====", comp, os.path.basename(p), "rows:", len(trs))
        for r in trs:
            if "جمع" in r[0] or "صادرات" in r[0]:
                print("  ", [x[:24] for x in r[:9]])
