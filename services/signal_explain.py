"""Explainability (Layer 4): top-k features -> Persian sentences + low_sample flag (5.9)."""
from __future__ import annotations
LOW_SAMPLE_THRESHOLD = 30

FA_TEMPLATES = {
    "volume_ratio": "حجم معاملات {v} برابر میانگین {n} روزه",
    "resistance_break": "عبور قیمت از مقاومت {n} روزه",
    "money_flow": "ورود پول حقیقی مثبت در {n} روز اخیر",
    "rsi": "RSI در سطح {v}",
    "macd": "تقاطع MACD ({v})",
    "nav_discount": "فاصله NAV تا قیمت بازار {v}٪",
    "bubble": "حباب سکه {v}٪",
    "spread": "اسپرد بازارها {v}٪",
    "iv_hv": "انحراف IV از HV به میزان {v}",
}

def top_features(importances: dict, k=5) -> list[str]:
    return [n for n,_ in sorted(importances.items(), key=lambda x: -abs(x[1]))[:k]]

def to_fa_reasons(names: list[str], ctx: dict | None = None) -> list[str]:
    ctx = ctx or {}
    return [FA_TEMPLATES.get(n, n).format(**{**{"v":"…","n":20}, **ctx.get(n,{})}) for n in names[:5]]

def backtest_stats(win_rate, avg_return, sample_size):
    return {"win_rate":float(win_rate),"avg_return":float(avg_return),
        "sample_size":int(sample_size),"low_sample":int(sample_size)<LOW_SAMPLE_THRESHOLD}
