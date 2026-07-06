import json
import os
import re
import subprocess
import time
import urllib.parse

EXCEL_DIR = "codal_excel_files"
JSON_DIR = "codal_data_db"
DELAY = 1.0
RETRIES = 2


def download_excel(url, output_path):
    """دانلود فایل اکسل با curl"""
    if os.path.exists(output_path):
        return True
    curl_path = "C:\\Windows\\System32\\curl.exe"
    cmd = [curl_path, "-k", "-L", "-s", "-o", output_path, url]
    try:
        subprocess.run(cmd, check=True, timeout=60)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    except subprocess.CalledProcessError:
        return False
    except Exception:  # خطای غیرمنتظره را لاگ می‌کنیم (اما bare except مجاز نیست)
        return False


def generate_filename(symbol, ann):
    """تولید نام فایل بر اساس اطلاعات اطلاعیه"""
    code = ann.get('code', '')
    date_publish = ann.get('date_publish', '')
    safe_code = re.sub(r'[\\/*?:"<>|]', "_", str(code)) if code else "unknown"
    safe_date = re.sub(r'[\\/*?:"<>|]', "_", str(date_publish)) if date_publish else "nodate"
    base = f"{symbol}_{safe_code}_{safe_date}"
    link = ann.get('link_excel', '')
    if link:
        parsed = urllib.parse.urlparse(link)
        ext = os.path.splitext(parsed.path)[1]
        if ext.lower() in ['.xlsx', '.xls']:
            return f"{base}{ext}"
    return f"{base}.xlsx"


def main():
    os.makedirs(EXCEL_DIR, exist_ok=True)
    for json_file in os.listdir(JSON_DIR):
        if not json_file.endswith('.json'):
            continue
        symbol = json_file.replace('.json', '')
        filepath = os.path.join(JSON_DIR, json_file)
        with open(filepath, encoding='utf-8') as f:  # حالت پیش‌فرض 'r' کافی است
            data = json.load(f)
        announcements = data.get('announcements', [])
        print(f"📂 پردازش {symbol} با {len(announcements)} اطلاعیه")
        symbol_dir = os.path.join(EXCEL_DIR, symbol)
        os.makedirs(symbol_dir, exist_ok=True)

        for ann in announcements:
            excel_url = ann.get('link_excel')
            if not excel_url:
                continue
            filename = generate_filename(symbol, ann)
            out_path = os.path.join(symbol_dir, filename)
            if os.path.exists(out_path):
                continue
            print(f"  ⏬ دانلود {filename}")
            for attempt in range(1, RETRIES + 1):
                if download_excel(excel_url, out_path):
                    print("    ✅ دانلود شد")
                    break
                print(f"    ❌ تلاش {attempt} ناموفق")
                time.sleep(DELAY)
        time.sleep(DELAY)


if __name__ == "__main__":
    main()