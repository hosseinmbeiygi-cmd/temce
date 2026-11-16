#!/usr/bin/env python3

"""
برنامه جامع تست کتابخانه‌های دریافت دیتای آپشن بورس تهران
نسخه: 2.0
تاریخ: ۱۴۰۴/۱۱/۰۸
"""

import contextlib
import json
import os
import subprocess
import sys
import time
import traceback

from core.time import now_utc

# ============================================================
# بخش ۱: مدیریت پروکسی و محیط
# ============================================================

def clear_proxy():
    """پاک کردن کامل تنظیمات پروکسی از محیط"""
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
                  'NO_PROXY', 'no_proxy', 'ALL_PROXY', 'all_proxy']
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]
    os.environ['NO_PROXY'] = '*'

    # غیرفعال کردن پروکسی برای urllib
    with contextlib.suppress(Exception):
        import urllib.request
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)

    print("✅ تنظیمات پروکسی پاک شد.")

def is_vpn_active():
    """بررسی فعال بودن VPN با تست اتصال به چند سایت"""
    try:
        import requests
        test_sites = [
            ("http://www.google.com", 5),
            ("http://www.tsetmc.com", 10),
            ("https://Api.BrsApi.ir", 5)
        ]
        for url, timeout in test_sites:
            try:
                resp = requests.get(url, timeout=timeout)
                if resp.status_code < 400:
                    print(f"✅ اتصال به {url} برقرار است.")
                    return True
            except Exception:
                continue
        print("❌ هیچ اتصال اینترنتی فعالی یافت نشد.")
        return False
    except Exception:
        print("⚠️ کتابخانه requests نصب نیست، نمی‌توان اتصال را تست کرد.")
        return True  # فرض می‌کنیم اتصال هست

# ============================================================
# بخش ۲: نصب خودکار کتابخانه‌ها (اختیاری)
# ============================================================

def install_libraries():
    """نصب کتابخانه‌های مورد نیاز در صورت عدم وجود"""
    required = ['requests', 'pandas']
    optional = ['algotik-tse', 'pytsetmc-api']

    installed = {}
    for lib in required + optional:
        try:
            __import__(lib.replace('-', '_'))
            installed[lib] = True
        except ImportError:
            installed[lib] = False

    missing = [lib for lib, status in installed.items() if not status]
    if missing:
        print(f"\n📦 کتابخانه‌های زیر نصب نیستند: {', '.join(missing)}")
        answer = input("آیا مایل به نصب خودکار آنها هستید؟ (y/n): ")
        if answer.lower() == 'y':
            for lib in missing:
                print(f"در حال نصب {lib}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
            print("✅ نصب کامل شد.")
            # بروزرسانی وضعیت
            return check_installations()
    return installed

def check_installations():
    """بررسی نصب کتابخانه‌ها"""
    libs = {
        'algotik_tse': 'algotik-tse',
        'pytsetmc_api': 'pytsetmc-api',
        'requests': 'requests',
        'pandas': 'pandas'
    }
    installed = {}
    for lib, _package in libs.items():
        try:
            __import__(lib)
            installed[lib] = True
        except ImportError:
            installed[lib] = False
    return installed

# ============================================================
# بخش ۳: توابع تست کتابخانه‌ها
# ============================================================

def test_algotik_tse():
    """تست کتابخانه algotik-tse با تشخیص خودکار کلاس"""
    try:
        import algotik_tse
        # پیدا کردن کلاس مناسب
        client = None
        class_names = ['TSE', 'TSETMC', 'Client', 'Tsetmc']
        for name in class_names:
            if hasattr(algotik_tse, name):
                try:
                    client = getattr(algotik_tse, name)()
                    print(f"   ✅ کلاس {name} پیدا شد")
                    break
                except Exception:
                    continue

        if client is None:
            return {
                "library": "algotik-tse",
                "status": "failed",
                "error": "کلاس معتبری در کتابخانه پیدا نشد",
                "available_classes": [c for c in dir(algotik_tse) if not c.startswith('_')]
            }

        print("   📡 در حال دریافت لیست آپشن‌ها...")
        options = client.get_options_list()

        if options is None:
            return {"library": "algotik-tse", "status": "warning", "data": [], "count": 0}

        if hasattr(options, 'empty') and options.empty:
            return {"library": "algotik-tse", "status": "warning", "data": [], "count": 0}

        data = options.head(10).to_dict(orient='records')
        return {
            "library": "algotik-tse",
            "status": "success",
            "data": data,
            "count": len(options),
            "note": f"{len(options)} رکورد دریافت شد"
        }
    except Exception as e:
        return {"library": "algotik-tse", "status": "failed", "error": str(e), "trace": traceback.format_exc()}

def test_pytsetmc_api():
    """تست کتابخانه pytsetmc-api با timeout بالا"""
    try:
        from pytsetmc_api import TSETMCClient
        client = TSETMCClient(timeout=90, max_retries=2)
        print("   📡 در حال دریافت تاریخچه قیمت اهرم (حداکثر ۹۰ ثانیه)...")
        history = client.get_price_history(
            stock="اهرم",
            start_date="1403-01-01",
            end_date="1403-06-01"
        )

        if history is None:
            return {"library": "pytsetmc-api", "status": "warning", "data": [], "count": 0}

        if hasattr(history, 'empty') and history.empty:
            return {"library": "pytsetmc-api", "status": "warning", "data": [], "count": 0}

        data = history.head(10).to_dict(orient='records')
        return {
            "library": "pytsetmc-api",
            "status": "success",
            "data": data,
            "count": len(history),
            "note": f"{len(history)} رکورد دریافت شد"
        }
    except Exception as e:
        return {"library": "pytsetmc-api", "status": "failed", "error": str(e), "trace": traceback.format_exc()}

def test_brsapi():
    """تست BrsApi.ir - معمولاً پایدارترین گزینه"""
    try:
        import requests
        print("   📡 در حال دریافت داده از BrsApi.ir...")
        url = "https://Api.BrsApi.ir/Tsetmc/History.php"
        import os
        params = {
            "key": os.environ.get("BRSAPI_API_KEY", ""),
            "type": 0,
            "l18": "اهرم"
        }
        resp = requests.get(url, params=params, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) == 0:
                return {"library": "BrsApi.ir", "status": "warning", "data": [], "count": 0}

            return {
                "library": "BrsApi.ir",
                "status": "success",
                "data": data if isinstance(data, list) else [data],
                "count": len(data) if isinstance(data, list) else 1,
                "note": "داده با موفقیت دریافت شد"
            }
        else:
            return {"library": "BrsApi.ir", "status": "failed", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"library": "BrsApi.ir", "status": "failed", "error": str(e), "trace": traceback.format_exc()}

def test_direct_tsetmc():
    """تست مستقیم tsetmc.com (بدون کتابخانه)"""
    try:
        import requests
        print("   📡 در حال تست مستقیم tsetmc.com...")
        # تست اتصال ساده
        resp = requests.get("http://www.tsetmc.com", timeout=10)
        if resp.status_code == 200:
            return {
                "library": "Direct-TSETMC",
                "status": "success",
                "data": {"status": "connected", "content_length": len(resp.text)},
                "note": "اتصال به tsetmc.com برقرار است"
            }
        else:
            return {"library": "Direct-TSETMC", "status": "failed", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"library": "Direct-TSETMC", "status": "failed", "error": str(e)}

# ============================================================
# بخش ۴: اجرای اصلی
# ============================================================

def main():
    print("\n" + "="*70)
    print("🔍 برنامه جامع تست کتابخانه‌های دریافت دیتای آپشن بورس تهران")
    print("="*70)

    # ۱. پاکسازی پروکسی
    clear_proxy()

    # ۲. بررسی VPN
    vpn_status = is_vpn_active()
    if not vpn_status:
        print("\n⚠️ هشدار: به نظر می‌رسد VPN فعال نیست یا اینترنت قطع است.")
        print("   برای دسترسی به tsetmc.com حتماً VPN خود را روشن کنید.")
        print("   اما BrsApi.ir ممکن است بدون VPN هم کار کند.\n")

    # ۳. نصب و بررسی کتابخانه‌ها
    print("\n📦 بررسی کتابخانه‌های مورد نیاز...")
    installed = install_libraries()

    print("\nوضعیت نصب:")
    for lib, status in installed.items():
        icon = "✅" if status else "❌"
        print(f"   {icon} {lib}: {'نصب شده' if status else 'نصب نشده'}")

    if not any(installed.values()):
        print("\n❌ هیچ کتابخانه‌ای نصب نیست. برنامه متوقف شد.")
        print("   لطفاً دستی نصب کنید: pip install requests pandas algotik-tse pytsetmc-api")
        sys.exit(1)

    # ۴. ایجاد پوشه خروجی
    output_dir = "test_results"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = now_utc().strftime("%Y%m%d_%H%M%S")

    # ۵. تعریف تست‌ها
    tests = []
    if installed.get('algotik_tse'):
        tests.append(("algotik_tse", test_algotik_tse))
    if installed.get('pytsetmc_api'):
        tests.append(("pytsetmc_api", test_pytsetmc_api))
    if installed.get('requests'):
        tests.append(("brsapi", test_brsapi))
        tests.append(("direct_tsetmc", test_direct_tsetmc))

    if not tests:
        print("\n❌ هیچ کتابخانه‌ای برای تست موجود نیست.")
        sys.exit(1)

    # ۶. اجرای تست‌ها
    print("\n" + "="*70)
    print("🚀 شروع تست‌ها...")
    print("="*70 + "\n")

    summary = {
        "timestamp": timestamp,
        "total": len(tests),
        "vpn_active": vpn_status,
        "installed_libraries": installed,
        "results": [],
        "system_info": {
            "python_version": sys.version,
            "platform": sys.platform,
            "working_directory": os.getcwd()
        }
    }

    for name, func in tests:
        print(f"🔍 تست {name} ...")
        start_time = time.time()
        result = func()
        elapsed = time.time() - start_time
        result["duration_seconds"] = round(elapsed, 1)

        summary["results"].append(result)

        # ذخیره فایل جداگانه
        filename = os.path.join(output_dir, f"{name}_{timestamp}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # نمایش نتیجه
        status_icon = {
            "success": "✅",
            "failed": "❌",
            "warning": "⚠️",
            "not_installed": "📦",
            "skipped": "⏭️"
        }.get(result.get("status", "unknown"), "❓")

        print(f"{status_icon} {name}: {result.get('status', 'unknown')} ({elapsed:.1f}s)")
        if "note" in result:
            print(f"   📝 {result['note']}")
        if "error" in result and result["status"] != "not_installed":
            error_msg = result['error'][:150]
            print(f"   ❌ خطا: {error_msg}")
        print()

    # ۷. ذخیره خلاصه کلی
    summary_file = os.path.join(output_dir, f"summary_{timestamp}.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ۸. گزارش نهایی
    print("="*70)
    print("📊 گزارش نهایی")
    print("="*70)
    print(f"📁 خروجی‌ها در پوشه: {output_dir}")
    print(f"📄 فایل خلاصه: {summary_file}")
    print("\nوضعیت کتابخانه‌ها:")
    for r in summary["results"]:
        icon = {
            "success": "✅", "failed": "❌", "warning": "⚠️",
            "not_installed": "📦", "skipped": "⏭️"
        }.get(r.get("status", "unknown"), "❓")
        print(f"   {icon} {r['library']}: {r['status']}")

    # ۹. راهنمایی نهایی
    print("\n" + "="*70)
    print("💡 راهنمایی:")
    print("   - اگر BrsApi موفق بوده، از آن برای دریافت داده استفاده کنید.")
    print("   - اگر همه خطا دادند، VPN خود را بررسی کنید.")
    print("   - برای دریافت داده‌های تاریخی، از BrsApi یا کتابخانه‌های موفق استفاده کنید.")
    print("   - برای مشاهده جزئیات کامل، فایل‌های JSON را باز کنید.")
    print("="*70)
    print("✅ برنامه با موفقیت پایان یافت.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ برنامه توسط کاربر متوقف شد.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ خطای غیرمنتظره: {e}")
        traceback.print_exc()
        sys.exit(1)
