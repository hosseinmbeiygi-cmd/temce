#!/usr/bin/env python3
"""
دریافت و نمایش دیتای واقعی بازار بورس تهران از APIهای TSETMC

استفاده از کتابخونه‌های requests و httpx برای دریافت داده
بدون نیاز به Docker، دیتابیس، Redis یا هر سرویس خارجی

Usage:
    python fetch_market_data.py
    python fetch_market_data.py --save          # ذخیره دیتا توی فایل JSON
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Try both major HTTP libraries ──
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("⚠️  requests نصب نیست. با httpx امتحان می‌کنیم...")

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

if not HAS_REQUESTS and not HAS_HTTPX:
    print("❌ هیچ کتابخونه HTTP پیدا نشد!")
    print("   یه دونه رو نصب کن:")
    print("   pip install requests")
    print("   یا:")
    print("   pip install httpx")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────
TSETMC_CDN = "https://cdn.tsetmc.com/api"
TSETMC_OLD = "http://old.tsetmc.com"
TSETMC_MEMBERS = "https://members.tsetmc.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}

OUTPUT_FILE = Path("market_data_output.json")

# ── HTTP Fetcher ───────────────────────────────────────────

def fetch_requests(url: str, params: dict | None = None, timeout: int = 20) -> tuple[int, str]:
    """Fetch with requests (sync)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get(url, params=params, timeout=timeout)
        return resp.status_code, resp.text
    except requests.exceptions.Timeout:
        return -1, "TIMEOUT"
    except requests.exceptions.ConnectionError as e:
        return -2, f"CONNECTION: {e}"
    except Exception as e:
        return -999, f"ERROR: {type(e).__name__}: {e}"
    finally:
        session.close()


def fetch_httpx_sync(url: str, params: dict | None = None, timeout: int = 20) -> tuple[int, str]:
    """Fetch with httpx (sync client)."""
    try:
        with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            return resp.status_code, resp.text
    except httpx.TimeoutException:
        return -1, "TIMEOUT"
    except httpx.ConnectError as e:
        return -2, f"CONNECTION: {e}"
    except Exception as e:
        return -999, f"ERROR: {type(e).__name__}: {e}"


def fetch(url: str, params: dict | None = None, timeout: int = 20) -> tuple[int, str]:
    """Fetch URL, preferring requests, falling back to httpx."""
    if HAS_REQUESTS:
        return fetch_requests(url, params, timeout)
    return fetch_httpx_sync(url, params, timeout)


# ── TSETMC API Methods ─────────────────────────────────────

def get_instrument_list() -> list[dict]:
    """لیست تمام نمادهای بورس"""
    url = f"{TSETMC_CDN}/Instrument/GetInstrumentList"
    code, text = fetch(url)
    if code != 200:
        print(f"  ❌ GetInstrumentList: HTTP {code}")
        return []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        print(f"  ⚠️  GetInstrumentList: not valid JSON, preview: {text[:150]}")
        return []
    instruments = data if isinstance(data, list) else data.get("instrument", data.get("instruments", []))
    return instruments


def get_market_data() -> dict | None:
    """داده‌های لحظه‌ای بازار (شاخص کل، حجم، ارزش)"""
    url = f"{TSETMC_CDN}/MarketData/MarketData"
    code, text = fetch(url)
    if code != 200:
        print(f"  ❌ MarketData: HTTP {code}")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  ⚠️  MarketData: not JSON, preview: {text[:100]}")
        return None


def get_closing_price_history(ins_code: str) -> dict | None:
    """تاریخچه قیمت‌های پایانی یک نماد"""
    url = f"{TSETMC_CDN}/ClosingPrice/GetClosingPriceHistory/{ins_code}"
    code, text = fetch(url)
    if code != 200:
        print(f"  ❌ ClosingPrice ({ins_code[:8]}...): HTTP {code}")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def get_order_book(ins_code: str) -> dict | None:
    """مظنه خرید و فروش (بهترین حدود قیمت)"""
    url = f"{TSETMC_CDN}/BestLimits/{ins_code}/0"
    code, text = fetch(url)
    if code != 200:
        print(f"  ❌ OrderBook ({ins_code[:8]}...): HTTP {code}")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def get_client_type_history(ins_code: str) -> dict | None:
    """تاریخچه خرید/فروش حقیقی و حقوقی"""
    url = f"{TSETMC_CDN}/ClientType/GetClientTypeHistory/{ins_code}"
    code, text = fetch(url)
    if code != 200:
        print(f"  ❌ ClientType ({ins_code[:8]}...): HTTP {code}")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def get_market_map() -> dict | None:
    """نقشه بازار (Market Map)"""
    url = f"{TSETMC_CDN}/ClosingPrice/GetMarketMap"
    params = {"market": 0, "size": 1920, "sector": 0, "typeSelected": 0, "hEven": 0}
    code, text = fetch(url, params=params)
    if code != 200:
        print(f"  ❌ MarketMap: HTTP {code}")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── Display Formatting ─────────────────────────────────────

SEPARATOR = "=" * 70
DIVIDER = "─" * 70


def format_number(n: int | float) -> str:
    """Format number with commas."""
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def format_price(price: int | float | None) -> str:
    """Format price in Rials/Tomans."""
    if price is None:
        return "—"
    return format_number(price)


def print_market_summary(market_data: dict | None) -> None:
    """Print market overview."""
    print(f"\n{DIVIDER}")
    print("  📊  خلاصه بازار بورس تهران")
    print(DIVIDER)

    if not market_data:
        print("  ❌ داده‌ای از MarketData دریافت نشد")
        return

    # Try to extract common fields
    md = market_data
    if isinstance(md, dict):
        market_state = md.get("marketState", md.get("marketStatus", "?"))
        index_val = md.get("indexLastValue", md.get("index", md.get("indexValue")))
        index_change = md.get("indexChange", md.get("indexVariation"))
        index_pct = md.get("indexChangePercent", md.get("pctChange"))
        volume = md.get("totalTradeVolume", md.get("volume"))
        value = md.get("totalTradeValue", md.get("value"))
        count = md.get("totalTradeCount", md.get("tradeCount"))

        print(f"  وضعیت بازار    : {market_state}")
        if index_val:
            print(f"  شاخص کل        : {format_number(index_val)}")
        if index_change:
            sign = "+" if index_change >= 0 else ""
            print(f"  تغییر شاخص     : {sign}{format_number(index_change)}", end="")
            if index_pct:
                print(f"  ({sign}{index_pct:.2f}%)", end="")
            print()
        if volume:
            print(f"  حجم معاملات    : {format_number(volume)}")
        if value:
            print(f"  ارزش معاملات   : {format_number(value)} ریال")
        if count:
            print(f"  تعداد معاملات  : {format_number(count)}")
    else:
        print(f"  پاسخ غیرمنتظره: {str(md)[:200]}")


def print_instrument_table(instruments: list[dict], limit: int = 25) -> None:
    """Print instrument list as a formatted table."""
    print(f"\n{DIVIDER}")
    print(f"  📋  لیست نمادهای بورس (نمایش {min(limit, len(instruments))} از {len(instruments)})")
    print(DIVIDER)

    if not instruments:
        print("  ❌ لیست نمادها خالیست")
        return

    # Header
    print(f"  {'کد':<16} | {'نماد':<12} | {'نام':<32} | {'گروه'}")
    print(f"  {'─' * 16}─┼─{'─' * 12}─┼─{'─' * 32}─┼─{'─' * 12}")

    for i, inst in enumerate(instruments[:limit]):
        ins_code = inst.get("insCode", inst.get("inscode", "")) or "?"
        symbol = inst.get("lVal18AFC", inst.get("symbol", "")) or "?"
        name = inst.get("lVal30", inst.get("name", inst.get("latinName", ""))) or "?"
        # Truncate long names
        name_str = str(name)
        name_display = name_str[:30] + ".." if len(name_str) > 32 else name_str
        group = inst.get("flowTitle", inst.get("group", "")) or "?"

        print(f"  {str(ins_code):<16} | {str(symbol):<12} | {name_display:<32} | {group}")


def print_closing_price(closing_data: dict | None, symbol: str = "?") -> None:
    """Print closing price history for a symbol."""
    print(f"\n{DIVIDER}")
    print(f"  📈  تاریخچه قیمت پایانی — {symbol}")
    print(DIVIDER)

    if not closing_data:
        print("  ❌ داده‌ای دریافت نشد")
        return

    if isinstance(closing_data, dict):
        history = closing_data.get("closingPriceHistory", closing_data.get("history", closing_data.get("data", [])))
    elif isinstance(closing_data, list):
        history = closing_data
    else:
        print(f"  پاسخ ناشناخته: {type(closing_data)}")
        return

    if not history:
        print("  ⚠️  تاریخچه خالیست")
        return

    print(f"  تعداد رکوردها: {len(history)}")
    print()
    print(f"  {'تاریخ':<14} | {'قیمت پایانی':<16} | {'آخرین':<14} | {'بیشترین':<14} | {'کمترین':<14} | {'حجم'}")
    print(f"  {'─' * 14}─┼─{'─' * 16}─┼─{'─' * 14}─┼─{'─' * 14}─┼─{'─' * 14}─┼─{'─' * 12}")

    # Show last 10 records
    for row in history[-10:]:
        date = row.get("dEven", row.get("date", "?"))
        close = row.get("pClosing", row.get("close", 0))
        last = row.get("pDrCotVal", row.get("last", 0))
        high = row.get("priceMax", row.get("high", 0))
        low = row.get("priceMin", row.get("low", 0))
        vol = row.get("qTotTran5J", row.get("volume", 0))

        print(f"  {str(date):<14} | {format_price(close):<16} | {format_price(last):<14} | {format_price(high):<14} | {format_price(low):<14} | {format_number(vol)}")

    # Summary
    if history:
        first = history[0]
        last_rec = history[-1]
        first_close = first.get("pClosing", first.get("close", 0))
        last_close = last_rec.get("pClosing", last_rec.get("close", 0))
        if first_close and last_close and first_close != 0:
            change_pct = ((last_close - first_close) / first_close) * 100
            print(f"\n  📊 تغییرات از {first.get('dEven','?')} تا {last_rec.get('dEven','?')}:")
            print(f"     قیمت اول:  {format_price(first_close)}")
            print(f"     قیمت آخر:  {format_price(last_close)}")
            print(f"     تغییر:     {format_price(last_close - first_close)}  ({change_pct:+.2f}%)")


def print_order_book(ob_data: dict | None, symbol: str = "?") -> None:
    """Print order book (best limits) for a symbol."""
    print(f"\n{DIVIDER}")
    print(f"  📖  مظنه سفارشات — {symbol}")
    print(DIVIDER)

    if not ob_data:
        print("  ❌ داده‌ای دریافت نشد")
        return

    buys = ob_data.get("bestLimits", ob_data.get("buyRows", []))
    sells = ob_data.get("bestLimits", ob_data.get("sellRows", []))

    if not buys and not sells:
        # Try old format
        for key in ob_data:
            if isinstance(ob_data[key], list) and len(ob_data[key]) > 0:
                if "buy" in key.lower():
                    buys = ob_data[key]
                elif "sell" in key.lower():
                    sells = ob_data[key]

    print()
    print(f"  {'قیمت خرید':<14} | {'حجم خرید':<12} | {'تعداد':<8} ‖ {'قیمت فروش':<14} | {'حجم فروش':<12} | {'تعداد'}")
    print(f"  {'─' * 14}─┼─{'─' * 12}─┼─{'─' * 8}─┼─{'─' * 14}─┼─{'─' * 12}─┼─{'─' * 8}")

    max_len = max(len(buys), len(sells), 5)
    for i in range(min(max_len, 10)):
        buy_price = format_price(buys[i].get("price", buys[i].get("pMeDem", ""))) if i < len(buys) else ""
        buy_vol = format_number(buys[i].get("volume", buys[i].get("qTitMeDem", 0))) if i < len(buys) else ""
        buy_count = format_number(buys[i].get("count", buys[i].get("zOrdMeDem", 0))) if i < len(buys) else ""

        sell_price = format_price(sells[i].get("price", sells[i].get("pMeOf", ""))) if i < len(sells) else ""
        sell_vol = format_number(sells[i].get("volume", sells[i].get("qTitMeOf", 0))) if i < len(sells) else ""
        sell_count = format_number(sells[i].get("count", sells[i].get("zOrdMeOf", 0))) if i < len(sells) else ""

        print(f"  {str(buy_price):<14} | {str(buy_vol):<12} | {str(buy_count):<8} ‖ {str(sell_price):<14} | {str(sell_vol):<12} | {str(sell_count)}")


# ── Also try iran_market_data collectors ───────────────────

def try_collector():
    """Try to use iran_market_data collectors if available."""
    try:
        from iran_market_data.app.collectors.tsetmc import TsetmcCollector

        print(f"\n{DIVIDER}")
        print("  🧪  تست با iran_market_data collector (سیستم قدیمی TSETMC)")
        print(DIVIDER)

        collector = TsetmcCollector()
        # Try old system market watch
        try:
            result = collector.collect_market_watch()
            raw_path = result.get("raw_path", "?")
            data_preview = str(result.get("data", ""))[:200]
            print(f"  ✅ MarketWatch جمع‌آوری شد")
            print(f"     مسیر فایل: {raw_path}")
            print(f"     پیش‌نمایش: {data_preview}")
        except Exception as e:
            print(f"  ❌ MarketWatch: {type(e).__name__}: {e}")

        # Try client type
        try:
            result = collector.collect_client_type_all()
            data_preview = str(result.get("data", ""))[:200]
            print(f"  ✅ ClientType جمع‌آوری شد")
            print(f"     پیش‌نمایش: {data_preview}")
        except Exception as e:
            print(f"  ❌ ClientType: {type(e).__name__}: {e}")

        # Try a known instrument
        SAMPLE_ID = "43362635835198978"
        try:
            result = collector.collect_instrument_info(SAMPLE_ID)
            data_preview = str(result.get("data", ""))[:200]
            print(f"  ✅ InstrumentInfo ({SAMPLE_ID}) جمع‌آوری شد")
            print(f"     پیش‌نمایش: {data_preview}")
        except Exception as e:
            print(f"  ❌ InstrumentInfo: {type(e).__name__}: {e}")

    except ImportError as e:
        print(f"\n  ⚠️  iran_market_data collector در دسترس نیست: {e}")
    except Exception as e:
        print(f"\n  ⚠️  خطا در collector: {type(e).__name__}: {e}")


# ── Main ───────────────────────────────────────────────────

def main(save: bool = False) -> int:
    print(SEPARATOR)
    print("  📡  دریافت دیتای بازار بورس تهران از TSETMC")
    print(f"  ⏰  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEPARATOR)

    all_data: dict[str, Any] = {"fetched_at": datetime.now().isoformat()}
    errors = 0
    successes = 0

    # ── 1. Instrument List ──
    print("\n🔄 دریافت لیست نمادها...")
    instruments = get_instrument_list()
    if instruments:
        successes += 1
        all_data["instruments_count"] = len(instruments)
        all_data["instruments"] = instruments[:50]  # Save first 50
        print_instrument_table(instruments, limit=20)
    else:
        errors += 1

    # ── 2. Market Data (Index, Volume, Value) ──
    print("\n🔄 دریافت داده‌های لحظه‌ای بازار...")
    market_data = get_market_data()
    if market_data:
        successes += 1
        all_data["market_data"] = market_data
        print_market_summary(market_data)
    else:
        errors += 1

    # ── 3. Sample Instrument: Closing Price History ──
    if instruments:
        # Pick first active instrument with valid code
        sample = None
        for inst in instruments:
            code = inst.get("insCode", inst.get("inscode", ""))
            if code and code != "?" and len(str(code)) > 10:
                sample = inst
                break
        if not sample:
            sample = instruments[0]

        ins_code = sample.get("insCode", sample.get("inscode", ""))
        symbol = sample.get("lVal18AFC", sample.get("symbol", "?"))

        if ins_code and ins_code != "?":
            print(f"\n🔄 دریافت تاریخچه قیمت برای {symbol} ({ins_code})...")
            cp = get_closing_price_history(ins_code)
            if cp:
                successes += 1
                all_data["sample_closing_price"] = {"symbol": symbol, "ins_code": ins_code, "data": cp}
                print_closing_price(cp, symbol)
            else:
                errors += 1

            print(f"\n🔄 دریافت مظنه سفارشات برای {symbol}...")
            ob = get_order_book(ins_code)
            if ob:
                successes += 1
                all_data["sample_order_book"] = {"symbol": symbol, "ins_code": ins_code, "data": ob}
                print_order_book(ob, symbol)
            else:
                errors += 1

            print(f"\n🔄 دریافت حقیقی/حقوقی برای {symbol}...")
            ct = get_client_type_history(ins_code)
            if ct:
                successes += 1
                all_data["sample_client_type"] = {"symbol": symbol, "ins_code": ins_code, "data": ct}
                print(f"  ✅ ClientTypeHistory دریافت شد ({len(json.dumps(ct))} کاراکتر)")
            else:
                errors += 1

    # ── 4. Market Map ──
    print("\n🔄 دریافت نقشه بازار...")
    market_map = get_market_map()
    if market_map:
        successes += 1
        all_data["market_map"] = market_map
        # Count map items
        items = market_map.get("marketMapRows", market_map.get("rows", market_map.get("items", [])))
        print(f"  ✅ MarketMap دریافت شد ({len(items) if items else '?'} آیتم)")
    else:
        errors += 1

    # ── 5. Try iran_market_data collector ──
    try_collector()

    # ── Summary ──
    print(f"\n{SEPARATOR}")
    print(f"  📊  نتیجه نهایی")
    print(SEPARATOR)
    total = successes + errors
    print(f"  ✅ موفق: {successes}/{total}")
    print(f"  ❌ ناموفق: {errors}/{total}")
    print()

    if errors > 0 and successes == 0:
        print("  ⚠️  هیچ APIای جواب نداد. دلایل احتمالی:")
        print("     1. نیاز به VPN برای دسترسی به cdn.tsetmc.com")
        print("     2. سایت TSETMC APIها رو تغییر داده")
        print("     3. فایروال یا تحریم اینترنت")
        print("     4. CDN جدید منتقل شده")
        print()
        print("  راه حل‌های پیشنهادی:")
        print("     • VPN روشن کن و دوباره اجرا کن")
        print("     • از DNS شکن (shecan.ir یا 403.online) استفاده کن")
        print("     • آدرس https://cdn.tsetmc.com رو در مرورگر باز کن ببین بالا میاد؟")
    elif successes >= 3:
        print("  🎉 دریافت دیتا با موفقیت انجام شد!")
        print("     سیستم آماده اجرای ingestion کامل هست.")

    # ── Save ──
    if save and all_data:
        all_data.pop("instruments", None)  # Too big, already shown
        try:
            OUTPUT_FILE.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n  💾 داده‌ها در {OUTPUT_FILE} ذخیره شد")
        except Exception as e:
            print(f"\n  ⚠️  خطا در ذخیره‌سازی: {e}")

    return 0 if successes > 0 else 1


if __name__ == "__main__":
    save = "--save" in sys.argv
    sys.exit(main(save=save))
