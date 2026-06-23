import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from services.tsetmc_client import TsetmcClient

async def test_codes():
    client = TsetmcClient()
    
    # لیست کدهای عددی (insCode) برای نمادهای معروف
    codes = {
        "فولاد": "46348559193224090",
        "شپنا": "65825638171690164",
        "وبملت": "50722858641780432",
        "فملی": "57126736379719915",
        "خودرو": "10033858847647367"
    }
    
    print("📡 در حال تست کدهای مختلف...")
    for symbol, code in codes.items():
        print(f"\n🔍 تست {symbol} با کد {code}...")
        result = await client.get_closing_price_info(code)
        if result.success:
            print(f"✅ {symbol} موفق بود! داده دریافت شد:")
            print(result.value)
            return  # اولین کد موفق را برمی‌گرداند
        else:
            print(f"❌ {symbol} خطا: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_codes())