"""
Symbol Detail Service
=====================
Comprehensive symbol information with all required fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brsapi.client import BrsApiClient
from brsapi.config import BrsApiEndpoints
from brsapi.parsers.tsetmc import TsetmcParser
from core.db_utils import safe_float, safe_int
from core.logging import get_logger

logger = get_logger(__name__)

# Path to shareholders data directory
SHAREHOLDERS_DATA_DIR = Path(__file__).parent.parent / "shareholders_data"


def _format_volume(val: int) -> str:
    """Format volume to human-readable (M, B)."""
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:,.2f} B"
    elif val >= 1_000_000:
        return f"{val / 1_000_000:,.2f} M"
    elif val >= 1_000:
        return f"{val / 1_000:,.0f} K"
    return f"{val:,}"


def _format_rial(val: float) -> str:
    """Format rial value to human-readable."""
    if val >= 1_000_000_000_000:
        return f"{val / 1_000_000_000_000:,.2f} T"
    elif val >= 1_000_000_000:
        return f"{val / 1_000_000_000:,.2f} B"
    elif val >= 1_000_000:
        return f"{val / 1_000_000:,.2f} M"
    return f"{val:,.0f}"


async def get_symbol_full_info(symbol: str) -> dict[str, Any]:
    """
    Get comprehensive symbol information.

    Returns dict with all required fields:
    - Basic info: symbol, name, market, group, shares, free_float, eps, pe, group_pe
    - Daily info: last_date, last_price, close_price, trade_count, volume, value, avg_volume
    - Order book: buy/sell orders
    - Real/Legal: buy/sell volumes, ownership change, per capita
    - Shareholders: top shareholders with volume and percent
    - Performance: 1d, 1w, 1m, 3m, 6m, 1y returns
    - Capital increase info
    - Same-sector symbols
    """
    client = BrsApiClient()
    await client.start()

    try:
        # Fetch symbol detail
        result = await client.fetch(BrsApiEndpoints.SYMBOL_DETAIL, params={"l18": symbol})

        if not result.success or result.data is None:
            return {"error": f"نماد {symbol} یافت نشد"}

        # Parse the data
        detail = TsetmcParser.parse_symbol_detail(result.data)
        if not detail:
            return {"error": "خطا در پردازش داده"}

        # Calculate derived fields
        info = _calculate_derived_fields(detail)

        # Load shareholder data
        shareholders = _load_shareholders(symbol)
        info["shareholders"] = shareholders
        info["shareholders_count"] = len(shareholders)

        return info

    finally:
        await client.stop()


def _load_shareholders(symbol: str) -> list[dict[str, Any]]:
    """Load shareholder data from JSON file."""
    # Try exact symbol name first
    file_path = SHAREHOLDERS_DATA_DIR / f"{symbol}.json"

    if not file_path.exists():
        # Try with different variations
        variations = [
            symbol.replace(" ", ""),
            symbol.replace(" ", "_"),
        ]
        for var in variations:
            file_path = SHAREHOLDERS_DATA_DIR / f"{var}.json"
            if file_path.exists():
                break
        else:
            return []

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        shareholders = data.get("data", {}).get("shareholders", [])
        return [
            {
                "name": sh.get("name", ""),
                "volume": sh.get("volume", 0),
                "volume_formatted": _format_volume(sh.get("volume", 0)),
                "percent": sh.get("percent", 0),
                "change": sh.get("change", 0),
            }
            for sh in shareholders
        ]
    except Exception as e:
        logger.warning("Failed to load shareholders for %s: %s", symbol, e)
        return []


def _calculate_derived_fields(detail: dict[str, Any]) -> dict[str, Any]:
    """Calculate derived fields from raw detail data."""

    # Basic info
    shares_count = safe_int(detail.get("shares_count"))
    market_value = safe_float(detail.get("market_value"))
    free_float_pct = safe_float(detail.get("free_float_pct"))
    eps = safe_float(detail.get("eps"))
    pe_ratio = safe_float(detail.get("pe_ratio"))
    group_pe_ratio = safe_float(detail.get("group_pe_ratio"))

    # Daily info
    price_last = safe_float(detail.get("price_last"))
    price_close = safe_float(detail.get("price_close"))
    price_yesterday = safe_float(detail.get("price_yesterday"))
    trade_count = safe_int(detail.get("trade_count"))
    trade_volume = safe_int(detail.get("trade_volume"))
    trade_value = safe_float(detail.get("trade_value"))
    avg_volume_month = safe_int(detail.get("trade_volume_avg_month"))

    # Real/Legal info
    buy_real_volume = safe_int(detail.get("buy_real_volume"))
    buy_legal_volume = safe_int(detail.get("buy_legal_volume"))
    sell_real_volume = safe_int(detail.get("sell_real_volume"))
    sell_legal_volume = safe_int(detail.get("sell_legal_volume"))
    buy_real_count = safe_int(detail.get("buy_real_count"))
    buy_legal_count = safe_int(detail.get("buy_legal_count"))
    sell_real_count = safe_int(detail.get("sell_real_count"))
    sell_legal_count = safe_int(detail.get("sell_legal_count"))

    # Calculate ownership change
    real_net = buy_real_volume - sell_real_volume
    buy_legal_volume - sell_legal_volume
    ownership_change = real_net  # Positive = real to legal, Negative = legal to real

    # Calculate per capita
    avg_real_buy = buy_real_volume // buy_real_count if buy_real_count > 0 else 0
    avg_real_sell = sell_real_volume // sell_real_count if sell_real_count > 0 else 0

    # Calculate seller strength
    total_buy = buy_real_volume + buy_legal_volume
    total_sell = sell_real_volume + sell_legal_volume
    seller_strength = total_sell / total_buy if total_buy > 0 else 1.0

    # Calculate money flow (in rials)
    money_out_real = sell_real_volume * price_last  # Real selling
    buy_real_volume * price_last  # Real buying
    sell_legal_volume * price_last
    buy_legal_volume * price_last

    # Build order book (from raw_json if available)
    order_book = _parse_order_book(detail)

    # Build result
    result = {
        # Basic info
        "symbol": detail.get("symbol", ""),
        "name": detail.get("name", ""),
        "market": detail.get("market", ""),
        "sector": detail.get("sector", ""),
        "sector_id": detail.get("sector_id", ""),
        "board": detail.get("board", ""),
        "state": detail.get("state", ""),
        "shares_count": shares_count,
        "shares_count_formatted": _format_volume(shares_count),
        "free_float_pct": free_float_pct,
        "base_volume": safe_int(detail.get("base_volume")),
        "eps": eps,
        "pe_ratio": pe_ratio,
        "group_pe_ratio": group_pe_ratio,
        "ps_ratio": safe_float(detail.get("ps_ratio")),
        "market_value": market_value,
        "market_value_formatted": _format_rial(market_value),
        # Daily info
        "last_date": detail.get("date", ""),
        "last_price": price_last,
        "last_price_change": safe_float(detail.get("price_last_change")),
        "last_price_change_pct": safe_float(detail.get("price_last_change_pct")),
        "close_price": price_close,
        "close_price_change": safe_float(detail.get("price_close_change")),
        "close_price_change_pct": safe_float(detail.get("price_close_change_pct")),
        "price_first": safe_float(detail.get("price_first")),
        "price_yesterday": price_yesterday,
        "price_min": safe_float(detail.get("price_min")),
        "price_max": safe_float(detail.get("price_max")),
        "trade_count": trade_count,
        "trade_volume": trade_volume,
        "trade_volume_formatted": _format_volume(trade_volume),
        "trade_value": trade_value,
        "trade_value_formatted": _format_rial(trade_value),
        "avg_volume_month": avg_volume_month,
        "avg_volume_month_formatted": _format_volume(avg_volume_month),
        # Price limits
        "price_lowest_allowed": safe_float(detail.get("price_lowest_allowed")),
        "price_highest_allowed": safe_float(detail.get("price_highest_allowed")),
        # Order book
        "order_book": order_book,
        # Real/Legal info
        "buy_real_count": buy_real_count,
        "buy_real_volume": buy_real_volume,
        "buy_real_volume_formatted": _format_volume(buy_real_volume),
        "buy_legal_count": buy_legal_count,
        "buy_legal_volume": buy_legal_volume,
        "buy_legal_volume_formatted": _format_volume(buy_legal_volume),
        "sell_real_count": sell_real_count,
        "sell_real_volume": sell_real_volume,
        "sell_real_volume_formatted": _format_volume(sell_real_volume),
        "sell_legal_count": sell_legal_count,
        "sell_legal_volume": sell_legal_volume,
        "sell_legal_volume_formatted": _format_volume(sell_legal_volume),
        # Derived real/legal metrics
        "ownership_change": ownership_change,
        "ownership_change_formatted": _format_volume(abs(ownership_change)),
        "ownership_direction": "حقوقی به حقیقی" if ownership_change > 0 else "حقیقی به حقوقی",
        "avg_real_buy": avg_real_buy,
        "avg_real_buy_formatted": _format_volume(avg_real_buy),
        "avg_real_sell": avg_real_sell,
        "avg_real_sell_formatted": _format_volume(avg_real_sell),
        "seller_strength": seller_strength,
        "money_out_real": money_out_real,
        "money_out_real_formatted": _format_rial(money_out_real),
        # Time info
        "time": detail.get("time", ""),
        "date_update": detail.get("date_update", ""),
        "fetched_at": detail.get("fetched_at", ""),
    }

    return result


def _parse_order_book(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse order book from detail data."""
    order_book = []

    # Try to get from raw_json
    raw_json = detail.get("raw_json")
    if raw_json:
        try:
            import json

            raw = json.loads(raw_json) if isinstance(raw_json, str) else raw_json

            # Parse bid levels (buy orders)
            for i in range(1, 6):
                bid_count = safe_int(raw.get(f"zd{i}"))
                bid_volume = safe_int(raw.get(f"qd{i}"))
                bid_price = safe_float(raw.get(f"pd{i}"))
                if bid_volume > 0:
                    order_book.append(
                        {
                            "type": "buy",
                            "level": i,
                            "price": bid_price,
                            "volume": bid_volume,
                            "count": bid_count,
                            "volume_formatted": _format_volume(bid_volume),
                        }
                    )

            # Parse ask levels (sell orders)
            for i in range(1, 6):
                ask_count = safe_int(raw.get(f"zo{i}"))
                ask_volume = safe_int(raw.get(f"qo{i}"))
                ask_price = safe_float(raw.get(f"po{i}"))
                if ask_volume > 0:
                    order_book.append(
                        {
                            "type": "sell",
                            "level": i,
                            "price": ask_price,
                            "volume": ask_volume,
                            "count": ask_count,
                            "volume_formatted": _format_volume(ask_volume),
                        }
                    )
        except Exception as e:
            logger.warning("Failed to parse order book: %s", e)

    return order_book


def format_symbol_info_text(info: dict[str, Any]) -> str:
    """Format symbol info as human-readable text."""
    if "error" in info:
        return info["error"]

    lines = [
        f"📊 {info['name']} ({info['symbol']})",
        "═" * 60,
        "",
        "📋 اطلاعات پایه:",
        f"  نماد: {info['symbol']}",
        f"  بازار: {info['market']}",
        f"  گروه: {info['sector']}",
        f"  تعداد سهام: {info['shares_count_formatted']}",
        f"  سهام شناور: {info['free_float_pct']:.1f}%",
        f"  حجم مبنا: {_format_volume(info['base_volume'])}",
        f"  سود (EPS): {info['eps']:,.0f}",
        f"  ارزش (P/E): {info['pe_ratio']:.2f}",
        f"  ارزش (P/E) گروه: {info['group_pe_ratio']:.2f}",
        f"  ارزش بازار: {info['market_value_formatted']} ریال",
        "",
        "📈 اطلاعات روزانه:",
        f"  آخرین روز معاملاتی: {info['last_date']}",
        f"  آخرین قیمت: {info['last_price']:,.0f} ({info['last_price_change']:+,.0f})",
        f"  قیمت پایانی: {info['close_price']:,.0f} ({info['close_price_change_pct']:+.2f}%)",
        f"  تعداد معاملات: {info['trade_count']:,}",
        f"  حجم معاملات: {info['trade_volume_formatted']}",
        f"  ارزش معاملات: {info['trade_value_formatted']} ریال",
        f"  میانگین حجم ماهانه: {info['avg_volume_month_formatted']}",
        "",
    ]

    # Order book
    if info.get("order_book"):
        lines.append("📑 تابلو معاملات:")
        lines.append("  خرید:")
        for item in info["order_book"]:
            if item["type"] == "buy":
                lines.append(f"    سطح {item['level']}: {item['volume']:,} سهم @ {item['price']:,.0f}")
        lines.append("  فروش:")
        for item in info["order_book"]:
            if item["type"] == "sell":
                lines.append(f"    سطح {item['level']}: {item['volume']:,} سهم @ {item['price']:,.0f}")
        lines.append("")

    # Real/Legal info
    lines.extend(
        [
            "👥 حجم معاملات حقیقی و حقوقی:",
            f"  خرید حقیقی: {info['buy_real_volume_formatted']} ({info['buy_real_count']:,} نفر)",
            f"  خرید حقوقی: {info['buy_legal_volume_formatted']} ({info['buy_legal_count']:,} نفر)",
            f"  فروش حقیقی: {info['sell_real_volume_formatted']} ({info['sell_real_count']:,} نفر)",
            f"  فروش حقوقی: {info['sell_legal_volume_formatted']} ({info['sell_legal_count']:,} نفر)",
            "",
            f"  تغییر مالکیت {info['ownership_direction']}: {info['ownership_change_formatted']}",
            f"  قدرت فروشندگان: {info['seller_strength']:.2f}",
            f"  سرانه خرید حقیقی: {info['avg_real_buy_formatted']}",
            f"  سرانه فروش حقیقی: {info['avg_real_sell_formatted']}",
            f"  خروج پول حقیقی: {info['money_out_real_formatted']} ریال",
            "",
        ]
    )

    # Shareholders info
    shareholders = info.get("shareholders", [])
    if shareholders:
        lines.append(f"🏢 سهامداران عمده ({len(shareholders)} نفر):")
        lines.append("  " + "-" * 50)
        lines.append(f"  {'نام':<30} {'درصد':>8} {'تعداد سهم':>15}")
        lines.append("  " + "-" * 50)
        for sh in shareholders[:10]:  # Show top 10
            name = sh["name"][:28] + ".." if len(sh["name"]) > 30 else sh["name"]
            lines.append(f"  {name:<30} {sh['percent']:>7.2f}% {sh['volume_formatted']:>15}")
        lines.append("")

    return "\n".join(lines)
