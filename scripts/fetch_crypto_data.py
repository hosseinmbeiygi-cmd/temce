#!/usr/bin/env python
"""
جمع‌آوری داده‌های رمزارز از CoinDesk و Investing.com.

منابع:
  - CoinDesk API: قیمت‌های تاریخی بیتکوین و اتریوم
  - Investing.com: قیمت‌های جهانی (طلا، نفت، شاخص‌ها)
  - Yahoo Finance: شاخص‌های مالی (S&P 500، داوجونز، دلار)
  - CoinGecko: داده‌های شبکه (تراکنش‌ها، سختی)

Usage:
    python scripts/fetch_crypto_data.py                    # همه داده‌ها
    python scripts/fetch_crypto_data.py --only bitcoin     # فقط بیتکوین
    python scripts/fetch_crypto_data.py --only ethereum    # فقط اتریوم
    python scripts/fetch_crypto_data.py --only market      # فقط بازار جهانی
    python scripts/fetch_crypto_data.py --days 365         # یک سال اخیر
    python scripts/fetch_crypto_data.py --format csv       # خروجی CSV
    python scripts/fetch_crypto_data.py --all-in-one       # ترکیب همه
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OUTPUT_DIR = _project_root / "crypto_data"
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}


# ═══════════════════════════════════════════════════════════════
#  ۱. CoinDesk — قیمت‌های تاریخی
# ═══════════════════════════════════════════════════════════════


def coindesk_historical(coin: str = "BTC", days: int = 365) -> list[dict]:
    """
    دریافت قیمت‌های تاریخی از CoinDesk API.

    Args:
        coin: BTC, ETH, XRP, LTC, ...
        days: تعداد روزهای اخیر
    """
    print(f"  [CoinDesk] دریافت {coin} (آخرین {days} روز)...")
    try:
        url = "https://api.coindesk.com/v1/bpi/historical/close.json"
        params = {}
        if days:
            end = datetime.now()
            start = end - timedelta(days=days)
            params["start"] = start.strftime("%Y-%m-%d")
            params["end"] = end.strftime("%Y-%m-%d")

        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        bpi = data.get("bpi", {})
        records = []
        for date_str, price in bpi.items():
            records.append(
                {
                    "date": date_str,
                    "symbol": coin,
                    "price": price,
                    "source": "coindesk",
                }
            )

        print(f"    ✓ {len(records)} رکورد")
        return records
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return []


def coindesk_current() -> dict:
    """دریافت قیمت لحظه‌ای بیتکوین."""
    print("  [CoinDesk] قیمت لحظه‌ای...")
    try:
        url = "https://api.coindesk.com/v1/bpi/currentprice.json"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        bpi = data.get("bpi", {})
        result = {
            "USD": bpi.get("USD", {}).get("rate_float"),
            "EUR": bpi.get("EUR", {}).get("rate_float"),
            "GBP": bpi.get("GBP", {}).get("rate_float"),
            "time": data.get("time", {}).get("updated"),
        }
        print(f"    ✓ BTC = ${result['USD']:,.2f}")
        return result
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════
#  ۲. CoinGecko — داده‌های رمزارزی
# ═══════════════════════════════════════════════════════════════


def coingecko_market_data(coin: str = "bitcoin") -> dict:
    """اطلاعات بازار یک رمزارز."""
    print(f"  [CoinGecko] اطلاعات بازار {coin}...")
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}"
        params = {
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        md = data.get("market_data", {})
        result = {
            "name": data.get("name"),
            "symbol": data.get("symbol"),
            "price_usd": md.get("current_price", {}).get("usd"),
            "market_cap": md.get("market_cap", {}).get("usd"),
            "total_volume": md.get("total_volume", {}).get("usd"),
            "high_24h": md.get("high_24h", {}).get("usd"),
            "low_24h": md.get("low_24h", {}).get("usd"),
            "price_change_24h": md.get("price_change_24h"),
            "price_change_7d": md.get("price_change_percentage_7d"),
            "price_change_30d": md.get("price_change_percentage_30d"),
            "price_change_1y": md.get("price_change_percentage_1y"),
            "ath": md.get("ath", {}).get("usd"),
            "ath_date": md.get("ath_date", {}).get("usd"),
            "circulating_supply": md.get("circulating_supply"),
            "total_supply": md.get("total_supply"),
            "max_supply": md.get("max_supply"),
        }
        print(f"    ✓ ${result['price_usd']:,.2f} | MCap: ${result['market_cap']:,.0f}")
        return result
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return {}


def coingecko_history(coin: str = "bitcoin", days: int = 365) -> list[dict]:
    """تاریخچه قیمت روزانه از CoinGecko."""
    print(f"  [CoinGecko] تاریخچه {coin}...")
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        params = {
            "vs_currency": "usd",
            "days": str(days),
            "interval": "daily",
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        mcaps = data.get("market_caps", [])

        records = []
        for i, (ts, price) in enumerate(prices):
            rec = {
                "date": datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                "symbol": coin.upper(),
                "price": round(price, 2),
                "source": "coingecko",
            }
            if i < len(volumes):
                rec["volume"] = volumes[i][1]
            if i < len(mcaps):
                rec["market_cap"] = mcaps[i][1]
            records.append(rec)

        print(f"    ✓ {len(records)} رکورد")
        return records
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return []


def coingecko_top_coins(n: int = 20) -> list[dict]:
    """لیست برترین رمزارزها."""
    print(f"  [CoinGecko] برترین {n} رمزارز...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": str(n),
            "page": "1",
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d",
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        records = []
        for coin in data:
            records.append(
                {
                    "rank": coin.get("market_cap_rank"),
                    "symbol": coin.get("symbol", "").upper(),
                    "name": coin.get("name"),
                    "price": coin.get("current_price"),
                    "market_cap": coin.get("market_cap"),
                    "volume_24h": coin.get("total_volume"),
                    "change_24h": coin.get("price_change_percentage_24h"),
                    "change_7d": coin.get("price_change_percentage_7d_in_currency"),
                    "ath": coin.get("ath"),
                    "source": "coingecko",
                }
            )

        print(f"    ✓ {len(records)} رمزارز")
        return records
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
#  ۳. Yahoo Finance — بازار جهانی
# ═══════════════════════════════════════════════════════════════


def yahoo_chart(ticker: str, col_name: str, days: int = 365) -> list[dict]:
    """داده روزانه از Yahoo Finance."""
    print(f"  [Yahoo] {ticker}...")
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        p1 = int((datetime.now() - timedelta(days=days)).timestamp())
        p2 = int(datetime.now().timestamp())
        params = {"period1": p1, "period2": p2, "interval": "1d"}
        resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        resp.raise_for_status()
        res = resp.json()["chart"]["result"][0]

        timestamps = res["timestamp"]
        quotes = res["indicators"]["quote"][0]
        records = []
        for i, ts in enumerate(timestamps):
            rec = {
                "date": pd.Timestamp(ts, unit="s").strftime("%Y-%m-%d")
                if "pd" in dir()
                else datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
                col_name: quotes["close"][i] if i < len(quotes["close"]) else None,
                "source": "yahoo",
            }
            records.append(rec)

        print(f"    ✓ {len(records)} رکورد")
        return records
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return []


def fetch_market_data(days: int = 365) -> list[dict]:
    """دریافت داده‌های بازار جهانی."""
    print("\n  [Market] دریافت داده‌های بازار جهانی...")

    tickers = {
        "^GSPC": "sp500",
        "^DJI": "dowjones",
        "GC=F": "gold",
        "CL=F": "crude_oil",
        "DX-Y.NYB": "dxy",
        "^VIX": "vix",
        "^TNX": "us_10y_yield",
    }

    all_data = {}
    for ticker, col in tickers.items():
        records = yahoo_chart(ticker, col, days)
        for rec in records:
            date = rec["date"]
            if date not in all_data:
                all_data[date] = {"date": date}
            all_data[date][col] = rec.get(col)
        time.sleep(0.3)

    result = sorted(all_data.values(), key=lambda x: x["date"])
    print(f"    ✓ {len(result)} روز")
    return result


# ═══════════════════════════════════════════════════════════════
#  ۴. ذخیره‌سازی
# ═══════════════════════════════════════════════════════════════


def save(data: list[dict], name: str, fmt: str = "csv") -> Path:
    """ذخیره داده."""
    if fmt == "json":
        fp = OUTPUT_DIR / f"{name}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif fmt == "csv":
        import pandas as pd

        fp = OUTPUT_DIR / f"{name}.csv"
        pd.DataFrame(data).to_csv(fp, index=False, encoding="utf-8-sig")
    else:
        fp = OUTPUT_DIR / f"{name}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"    💾 {fp} ({len(data)} رکورد)")
    return fp


def merge_all(btc: list, eth: list, market: list) -> list[dict]:
    """ترکیب تمام داده‌ها بر اساس تاریخ."""
    import pandas as pd

    dfs = []
    if btc:
        df_btc = pd.DataFrame(btc)[["date", "price"]].rename(columns={"price": "btc_price"})
        dfs.append(df_btc)
    if eth:
        df_eth = pd.DataFrame(eth)[["date", "price"]].rename(columns={"price": "eth_price"})
        dfs.append(df_eth)
    if market:
        dfs.append(pd.DataFrame(market))

    if not dfs:
        return []

    result = dfs[0]
    for df in dfs[1:]:
        result = pd.merge(result, df, on="date", how="outer")

    result = result.sort_values("date").reset_index(drop=True)
    return result.to_dict("records")


# ═══════════════════════════════════════════════════════════════
#  ۵. CLI
# ═══════════════════════════════════════════════════════════════


def parse_args():
    p = argparse.ArgumentParser(description="جمع‌آوری داده‌های رمزارز")
    p.add_argument("--only", choices=["bitcoin", "ethereum", "market", "top"], default=None)
    p.add_argument("--days", type=int, default=365, help="روزهای اخیر")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.add_argument("--all-in-one", action="store_true")
    p.add_argument("--top", type=int, default=20, help="تعداد برترین رمزارزها")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print("  جمع‌آوری داده‌های رمزارز")
    print(f"  روزها: {args.days} | فرمت: {args.format}")
    print("=" * 70)

    only = args.only
    btc_data, eth_data, market_data, top_data = [], [], [], []

    # ── قیمت لحظه‌ای ──
    if only in (None, "bitcoin"):
        current = coindesk_current()
        if current:
            print("\n  ── قیمت لحظه‌ای بیتکوین ──")
            print(f"    USD: ${current['USD']:,.2f}")
            print(f"    EUR: €{current['EUR']:,.2f}")
            print(f"    GBP: £{current['GBP']:,.2f}")

    # ── اطلاعات بازار ──
    if only in (None, "bitcoin"):
        coingecko_market_data("bitcoin")
    if only in (None, "ethereum"):
        coingecko_market_data("ethereum")

    # ── تاریخچه ──
    if only in (None, "bitcoin"):
        btc_data = coingecko_history("bitcoin", args.days)
        if btc_data:
            save(btc_data, f"btc_history_{args.days}d", args.format)

    if only in (None, "ethereum"):
        eth_data = coingecko_history("ethereum", args.days)
        if eth_data:
            save(eth_data, f"eth_history_{args.days}d", args.format)

    # ── بازار جهانی ──
    if only in (None, "market"):
        market_data = fetch_market_data(args.days)
        if market_data:
            save(market_data, f"market_data_{args.days}d", args.format)

    # ── برترین رمزارزها ──
    if only in (None, "top"):
        top_data = coingecko_top_coins(args.top)
        if top_data:
            save(top_data, "top_coins", args.format)

    # ── ترکیب ──
    if args.all_in_one:
        merged = merge_all(btc_data, eth_data, market_data)
        if merged:
            save(merged, f"all_data_{args.days}d", args.format)

    # ── خلاصه ──
    print(f"\n{'═' * 70}")
    print("  خلاصه")
    print(f"{'═' * 70}")
    print(f"  بیتکوین:     {len(btc_data)} رکورد")
    print(f"  اتریوم:      {len(eth_data)} رکورد")
    print(f"  بازار جهانی: {len(market_data)} رکورد")
    print(f"  برترین‌ها:   {len(top_data)} رمزارز")
    print(f"  پوشه:        {OUTPUT_DIR.resolve()}")
    print(f"{'═' * 70}")


if __name__ == "__main__":
    main()
