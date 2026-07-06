import requests
import json

def test_codal_api():
    url = "https://codal.ir/api/FinancialReport/GetFinancialReport"
    
    # پارامترهای مختلف برای تست
    test_params = [
        {"symbol": "فولاد", "reportType": "income_statement", "fromDate": "1400-01-01", "toDate": "1404-12-29"},
        {"symbol": "فولاد", "reportType": "balance_sheet", "fromDate": "1400-01-01", "toDate": "1404-12-29"},
        {"symbol": "فولاد", "reportType": "income_statement"},  # بدون تاریخ
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    for params in test_params:
        print(f"\n🔄 تست با پارامترها: {params}")
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            print(f"   ✅ وضعیت: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    print(f"   📊 تعداد رکوردها: {len(data)}")
                    if len(data) > 0:
                        print(f"   📋 نمونه: {json.dumps(data[0], ensure_ascii=False)[:200]}...")
                else:
                    print(f"   📋 پاسخ: {json.dumps(data, ensure_ascii=False)[:200]}")
            else:
                print(f"   ❌ خطا: {response.text[:200]}")
        except requests.Timeout:
            print("   ❌ Timeout: سرور پاسخ نداد")
        except Exception as e:
            print(f"   ❌ خطا: {e}")

if __name__ == "__main__":
    test_codal_api()