import asyncio
import json

import httpx


async def fetch_quote(isin: str):
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{isin}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)

        if response.status_code != 200:
            print(f"❌ خطا: {response.status_code} - {response.text}")
            return

        data = response.json()
        print("✅ داده دریافت شد:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # استخراج اطلاعات کلیدی
        if data and "pClosing" in data:
            print(f"\n📊 قیمت پایانی: {data['pClosing']}")
            print(f"📈 قیمت آخرین معامله: {data.get('pDrCotVal', 'N/A')}")
            print(f"📊 حجم معاملات: {data.get('zTotTran', 0):,}")

    except httpx.TimeoutException:
        print("❌ خطا: زمان ارتباط با سرور به پایان رسید. (VPN خود را بررسی کنید)")
    except Exception as e:
        print(f"❌ خطا: {e}")

if __name__ == "__main__":
    isin = "IRO1FOLD0001"  # کد ISIN فولاد
    asyncio.run(fetch_quote(isin))
