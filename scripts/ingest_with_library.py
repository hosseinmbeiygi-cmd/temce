import sys
from pathlib import Path
# اضافه کردن مسیر پروژه به sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from services.tsetmc_client import TsetmcClient
from core.result import Result

async def fetch_with_library():
    # ساخت یک نمونه از کلاینت مخصوص TSETMC
    client = TsetmcClient()
    
    # 🔥 کلید مورد نظر (insCode/ISIN)
    # با توجه به خطای 400 که گرفتیم، IRO1FOLD0001 معتبر نیست
    # یا باید ISIN درست را پیدا کنید یا از insCode عددی استفاده کنید
    key = "IRO1FOLD0001"  # ← این را با کلید صحیح جایگزین کنید
    
    print(f"📡 در حال دریافت داده برای کلید: {key}")
    result = await client.get_closing_price_info(key)
    
    if result.success:
        print("✅ داده دریافت شد:")
        print(result.value)
    else:
        print(f"❌ خطا: {result.error}")

if __name__ == "__main__":
    asyncio.run(fetch_with_library())