import json

import httpx

# scripts/test_raw.py


def test_raw():
    url = "https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/46348559193224090"
    response = httpx.get(url, timeout=10)
    print(f"وضعیت: {response.status_code}")
    print(f"سرصفحه‌ها: {response.headers}")
    print(f"متن پاسخ (۲۰۰ کاراکتر اول): {response.text[:200]}")
    try:
        data = response.json()
        print("✅ JSON معتبر:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        print("❌ پاسخ JSON معتبر نیست.")


if __name__ == "__main__":
    test_raw()
