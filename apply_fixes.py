#!/usr/bin/env python3
import sys

# Fix 1: MACD validation
with open('/c/Users/Iran/Desktop/temce/services/market_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add MACD validation after slow is set
old_macd = '''        if indicator == "macd":\n            fast = int(params.get("fast", 12))\n            slow = int(params.get("slow", 26))\n            signal_p = int(params.get("signal", 9))\n            macd_line, signal_line, histogram = MarketService._macd(closes, fast, slow, signal_p)\n            return {"macd": macd_line, "signal": signal_line, "histogram": histogram}'''

new_macd = '''        if indicator == "macd":\n            fast = int(params.get("fast", 12))\n            slow = int(params.get("slow", 26))\n            # Validate that fast < slow for valid MACD calculation\n            if fast >= slow:\n                return Result.fail("MACD parameter error: fast must be less than slow")\n            signal_p = int(params.get("signal", 9))\n            macd_line, signal_line, histogram = MarketService._macd(closes, fast, slow, signal_p)\n            return {"macd": macd_line, "signal": signal_line, "histogram": histogram}'''

if old_macd in content:
    content = content.replace(old_macd, new_macd)
    print("MACD validation applied")
else:
    print("MACD validation pattern not found")

# Fix 2: Ichimoku alignment
old_ichimoku = '''        if indicator == "ichimoku":\n            tenkan_p = int(params.get("tenkan", 9))\n            kijun_p = int(params.get("kijun", 26))\n            senkou_b_p = int(params.get("senkou_b", 52))\n            tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(\n                highs or [], lows or [], closes, tenkan_p, kijun_p, senkou_b_p,\n            )\n            return {"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a, "senkou_b": senkou_b, "chikou": chikou}'''

new_ichimoku = '''        if indicator == "ichimoku":\n            tenkan_p = int(params.get("tenkan", 9))\n            kijun_p = int(params.get("kijun", 26))\n            senkou_b_p = int(params.get("senkou_b", 52))\n            tenkan, kijun, senkou_a, senkou_b, chikou = MarketService._ichimoku(\n                highs or [], lows or [], closes, tenkan_p, kijun_p, senkou_b_p,\n            )\n            # Align all series to the same date axis (kijun period)\n            offset = kijun_p  # Shift all series by kijun_period bars\n            tenkan_aligned = tenkan[offset:] if len(tenkan) > offset else []\n            kijun_aligned = kijun\n            senkou_a_aligned = senkou_a\n            senkou_b_aligned = senkou_b\n            chikou_aligned = chikou[offset:] if len(chikou) > offset else []\n            # Return aligned series - all start from kijun_period bar\n            return {\n                "tenkan": tenkan_aligned,\n                "kijun": kijun_aligned,\n                "senkou_a": senkou_a_aligned,\n                "senkou_b": senkou_b_aligned,\n                "chikou": chikou_aligned,\n                "offset": offset,\n            }'''

if old_ichimoku in content:
    content = content.replace(old_ichimoku, new_ichimoku)
    print("Ichimoku alignment applied")
else:
    print("Ichimoku alignment pattern not found")

# Fix 3: Stochastic K/D alignment
old_stochastic = '''    def _stochastic(\n        highs: list[float],\n        lows: list[float],\n        closes: list[float],\n        period: int,\n        k_smooth: int = 3,\n        d_smooth: int = 3,\n    ) -> tuple[list[float], list[float]]:\n        \"\"\"Stochastic Oscillator: returns (raw %K, %D).\"\"\"\n        n = min(len(highs), len(lows), len(closes))\n        if n < period:\n            return [], []\n        raw_k: list[float] = []\n        for i in range(period - 1, n):\n            window_high = max(highs[i - period + 1:i + 1])\n            window_low = min(lows[i - period + 1:i + 1])\n            if window_high == window_low:\n                raw_k.append(50.0)\n            else:\n                raw_k.append(((closes[i] - window_low) / (window_high - window_low)) * 100.0)\n        # Smooth %K (SMA of raw %K)\n        k_line = MarketService._sma(raw_k, k_smooth)\n        # %D = SMA of smoothed %K\n        d_line = MarketService._sma(k_line, d_smooth)\n        return k_line, d_line'''

new_stochastic = '''    def _stochastic(\n        highs: list[float],\n        lows: list[float],\n        closes: list[float],\n        period: int,\n        k_smooth: int = 3,\n        d_smooth: int = 3,\n    ) -> tuple[list[float], list[float]]:\n        \"\"\"Stochastic Oscillator: returns (raw %K, %D).\"\"\"\n        n = min(len(highs), len(lows), len(closes))\n        if n < period:\n            return [], []\n        raw_k: list[float] = []\n        for i in range(period - 1, n):\n            window_high = max(highs[i - period + 1:i + 1])\n            window_low = min(lows[i - period + 1:i + 1])\n            if window_high == window_low:\n                raw_k.append(50.0)\n            else:\n                raw_k.append(((closes[i] - window_low) / (window_high - window_low)) * 100.0)\n        # Smooth %K (SMA of raw %K)\n        k_line = MarketService._sma(raw_k, k_smooth)\n        # %D = SMA of smoothed %K; align d_line to same length as k_line\n        d_line = MarketService._sma(k_line, d_smooth)\n        # Align d_line to k_line: d_line is shorter, so pad from the left with the first value\n        if len(d_line) < len(k_line) and len(k_line) > 0:\n            d_line = [d_line[0]] * (len(k_line) - len(d_line)) + d_line\n        elif len(d_line) > len(k_line) and len(k_line) > 0:\n            d_line = d_line[:len(k_line)]\n        return k_line, d_line'''

if old_stochastic in content:
    content = content.replace(old_stochastic, new_stochastic)
    print("Stochastic alignment applied")
else:
    print("Stochastic alignment pattern not found")

# Fix 4: Sector field mapping and avg_change
old_sectors = '''    def _build_sectors(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:\n        sectors: dict[str, dict[str, Any]] = {}\n        for s in snapshots:\n            sector = s.get("sector_name") or s.get("industry", "ساری")\n            if sector not in sectors:\n                sectors[sector] = {"name": sector, "count": 0, "total_value": 0, "avg_change": 0}\n            sectors[sector]["count"] += 1\n            sectors[sector]["total_value"] += s.get("trade_value", 0) or 0\n        result = list(sectors.values())\n        for sec in result:\n            sec["avg_change"] = 0\n        return result'''

new_sectors = '''    def _build_sectors(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:\n        sectors: dict[str, dict[str, Any]] = {}\n        for s in snapshots:\n            # Unified field mapping: sector_name, industry, or sector from snapshot model\n            sector = s.get("sector_name") or s.get("industry") or s.get("sector", "ساری")\n            if sector not in sectors:\n                sectors[sector] = {"name": sector, "count": 0, "total_value": 0, "avg_change": 0}\n            sectors[sector]["count"] += 1\n            sectors[sector]["total_value"] += s.get("trade_value", 0) or 0\n        result = list(sectors.values())\n        # Calculate actual avg_change from the data\n        if result:\n            # Group snapshots by sector and calculate average change\n            sector_changes: dict[str, list[float]] = {}\n            for s in snapshots:\n                sec = s.get("sector_name") or s.get("industry") or s.get("sector", "ساری")\n                change = s.get("price_last_change_pct") or 0\n                if sec not in sector_changes:\n                    sector_changes[sec] = []\n                sector_changes[sec].append(change)\n            for sec in result:\n                if sec["name"] in sector_changes and sector_changes[sec["name"]]:\n                    changes = sector_changes[sec["name"]]\n                    sec["avg_change"] = round(sum(changes) / len(changes), 2)\n                else:\n                    sec["avg_change"] = 0\n        return result'''

if old_sectors in content:
    content = content.replace(old_sectors, new_sectors)
    print("Sector field mapping and avg_change applied")
else:
    print("Sector field mapping pattern not found")

with open('/c/Users/Iran/Desktop/temce/services/market_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("All fixes applied to market_service.py")