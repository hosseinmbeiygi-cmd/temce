from codal_tsetmc import get_stock_detail, get_stock_ids
import json

symbol = "شپدیس"
ids = get_stock_ids(symbol)
if ids:
    detail = get_stock_detail(ids[0])
    if detail:
        with open(f"{symbol}_info.json", "w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False, indent=2)
        print("✅ ذخیره شد")
    else: print("داده‌ای نیست")
else: print("نماد یافت نشد")