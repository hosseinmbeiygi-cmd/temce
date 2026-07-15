import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import sqlite3

from core.ids import new_id
from services.tsetmc_client import TsetmcClient

DB_PATH = "data/market.db"

async def fetch_and_save(symbol: str, ins_code: str):
    # 1. دریافت داده از TSETMC
    client = TsetmcClient()
    result = await client.get_closing_price_info(ins_code)
    if not result.success:
        print(f"❌ خطا در دریافت داده: {result.error}")
        return

    data = result.value
    print("✅ داده دریافت شد، در حال ذخیره‌سازی...")

    # 2. اتصال به SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 3. پیدا کردن instrument_id بر اساس symbol
    cursor.execute("SELECT id FROM instruments WHERE symbol = ?", (symbol,))
    row = cursor.fetchone()
    if not row:
        print(f"❌ نماد {symbol} در دیتابیس پیدا نشد. لطفاً ابتدا آن را اضافه کنید.")
        conn.close()
        return

    instrument_id = row[0]

    # 4. استخراج فیلدهای مورد نیاز
    quote_id = new_id("quote")
    price_close = data.get("pClosing", 0)
    price_last = data.get("pDrCotVal", 0)
    price_open = data.get("priceFirst", 0) or 0
    price_high = data.get("priceMax", 0) or 0
    price_low = data.get("priceMin", 0) or 0
    price_change = data.get("priceChange", 0)
    price_yesterday = data.get("priceYesterday", 0)
    volume = data.get("zTotTran", 0)
    value = data.get("qTotTran5J", 0)
    trade_count = data.get("nvt", 0) or 0
    date_str = str(data.get("dEven", ""))
    time_str = str(data.get("hEven", ""))
    timeframe = "1d"
    data_source = "tsetmc"

    # 5. درج در جدول quotes
    cursor.execute("""
        INSERT INTO quotes (
            id, instrument_id, symbol, price_close, price_last, price_open,
            price_high, price_low, price_change, price_yesterday,
            volume, value, trade_count, date, time, timeframe, data_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        quote_id, instrument_id, symbol, price_close, price_last,
        price_open, price_high, price_low, price_change, price_yesterday,
        volume, value, trade_count, date_str, time_str, timeframe, data_source
    ))

    conn.commit()
    conn.close()

    print(f"✅ داده‌های {symbol} با موفقیت در دیتابیس ذخیره شد.")
    print(f"📊 قیمت پایانی: {price_close}")

if __name__ == "__main__":
    symbol = "فولاد"
    ins_code = "46348559193224090"
    asyncio.run(fetch_and_save(symbol, ins_code))
