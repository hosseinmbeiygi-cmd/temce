import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

import httpx

from services.tsetmc_client import TsetmcClient


async def find_valid_code(symbol: str) -> str | None:
    """
    با جستجوی نماد در TSETMC، کد معتبر را پیدا می‌کند.
    """
    # استفاده از endpoint جستجوی TSETMC
    search_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentBySymbol/{symbol}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(search_url)
            if response.status_code == 200:
                data = response.json()
                # استخراج اولین کد معتبر از نتایج جستجو
                if data and isinstance(data, list) and len(data) > 0:
                    # معمولاً اولین نتیجه بهترین گزینه است
                    instrument = data[0]
                    # اولویت با insCode (عددی) است، چون مطمئن‌تر است
                    if "insCode" in instrument:
                        return str(instrument["insCode"])
                    elif "ISIN" in instrument:
                        return instrument["ISIN"]
                elif isinstance(data, dict) and "insCode" in data:
                    return str(data["insCode"])
    except Exception as e:
        print(f"⚠️ خطا در جستجوی نماد: {e}")
    return None

async def fetch_with_library(symbol: str):
    # 1. پیدا کردن کد معتبر برای نماد
    print(f"🔍 در حال جستجوی کد معتبر برای '{symbol}'...")
    valid_code = await find_valid_code(symbol)

    if not valid_code:
        print(f"❌ کد معتبری برای '{symbol}' پیدا نشد.")
        return

    print(f"✅ کد معتبر پیدا شد: {valid_code}")

    # 2. استفاده از کتابخانه TsetmcClient برای دریافت داده
    client = TsetmcClient()
    print(f"📡 در حال دریافت داده با کد: {valid_code}")
    result = await client.get_closing_price_info(valid_code)

    if result.success:
        print("✅ داده دریافت شد:")
        print(result.value)
    else:
        print(f"❌ خطا در دریافت داده: {result.error}")

if __name__ == "__main__":
    # نام نماد مورد نظر خود را وارد کنید
    symbol = "فولاد"
    asyncio.run(fetch_with_library(symbol))
