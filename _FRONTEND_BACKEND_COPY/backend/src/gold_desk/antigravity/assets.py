"""رجیستری دارایی‌های Antigravity — مطابق پرامپت جامع."""

from __future__ import annotations

# ── 1. صندوق‌های ETF طلا ───────────────────────────────────────────
ETF_ASSETS: dict[str, dict] = {
    "زرافشان": {
        "symbol": "ZARFSHANG",
        "isin": "IRO1ZARA0001",
        "type": "physical_backed",
        "liquidity": "high",
        "management_fee": 0.005,
        "tsetmc_symbol": "زرفام",  # نگاشت به نماد TSETMC فعلی
    },
    "لوتوس": {
        "symbol": "LOTUS",
        "isin": "IRO1LOTU0001",
        "type": "physical_backed",
        "liquidity": "high",
        "management_fee": 0.005,
        "tsetmc_symbol": "لوتوس",
    },
    "گوهر": {
        "symbol": "GOHAR",
        "isin": "IRO1GOHA0001",
        "type": "physical_backed",
        "liquidity": "medium",
        "management_fee": 0.005,
        "tsetmc_symbol": "گوهر",
    },
    "ثامان": {
        "symbol": "SAMAN",
        "isin": "IRO1SAMA0001",
        "type": "physical_backed",
        "liquidity": "medium",
        "management_fee": 0.005,
        "tsetmc_symbol": "ثامان",
    },
}

# نگاشت معکوس symbol -> نام فارسی
ETF_BY_SYMBOL: dict[str, str] = {v["symbol"]: k for k, v in ETF_ASSETS.items()}
ETF_BY_ISIN: dict[str, str] = {v["isin"]: k for k, v in ETF_ASSETS.items()}

# ── 2. قراردادهای آتی ─────────────────────────────────────────────
FUTURES_CONTRACTS: dict[str, dict] = {
    "سکه_آتی_IME": {
        "exchange": "IME",
        "contract_size": 10,
        "leverage": 10,
        "initial_margin": "10%",
        "initial_margin_ratio": 0.10,
        "maintenance_margin": "5%",
        "maintenance_margin_ratio": 0.05,
        "settlement": "physical_delivery",
        "tick_size_irt": 1000,
    }
}

# ── 3. بازار فیزیکی ──────────────────────────────────────────────
PHYSICAL_MARKET: dict[str, dict] = {
    "سکه_بهار_آزادی": {
        "weight": "8.133g",
        "weight_grams": 8.133,
        "purity": "900/1000",
        "purity_ratio": 0.915,  # 900/1000 + اجرت ضرب per spec
        "reference_source": "BrsApi.ir",
    },
    "نیم_سکه": {"weight": "4.066g", "weight_grams": 4.066, "purity": "900/1000", "purity_ratio": 0.915},
    "ربع_سکه": {"weight": "2.033g", "weight_grams": 2.033, "purity": "900/1000", "purity_ratio": 0.915},
    "گرم_طلای_18_عیار": {"weight": "1.0g", "weight_grams": 1.0, "purity": "750/1000", "purity_ratio": 0.750},
    "مثقال": {"weight": "4.608g", "weight_grams": 4.608, "purity": "1000/1000", "purity_ratio": 1.0},
}

# ── 4. اونس جهانی ────────────────────────────────────────────────
GLOBAL_GOLD: dict[str, object] = {
    "symbol": "XAU/USD",
    "unit": "troy_ounce",
    "troy_ounce_grams": 31.1035,
    "exchanges": ["COMEX", "LBMA"],
    "trading_hours": "23/5",
}

# ── 5. منابع داده و API ──────────────────────────────────────────
BRSAPI_ENDPOINTS: dict[str, object] = {
    "live_prices": {
        "gold_ounce": "https://brsapi.ir/api/gold/ounce",
        "gold_18k": "https://brsapi.ir/api/gold/18k",
        "coin_bahar": "https://brsapi.ir/api/gold/coin",
        "usd_rate": "https://brsapi.ir/api/forex/usd",
    },
    "cache_strategy": {"ttl": 3, "fallback": "use_last_valid_value", "retry": 3},
}

TSETMC_DATA: dict[str, object] = {
    "etf_nav": "http://www.tsetmc.com/Loader.aspx?ParTree=15131F",
    "intraday": "http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList",
    "update_frequency": "5_seconds",
    "cache_ttl": 5,
}

IME_ENDPOINTS: dict[str, object] = {
    "futures": "https://www.ime.co.ir/Market",
    "settlements": "https://www.ime.co.ir/Settlement",
    "cache_ttl": 10,
}

TGJU_DATA: dict[str, object] = {
    "coin_price": "https://www.tgju.org/profile/sekee",
    "ounce_price": "https://www.tgju.org/profile/gold-ounce",
    "use_case": "secondary_validation",
    "cache_ttl": 30,
}

# ── 6. Data Layer Strategy ───────────────────────────────────────
DATA_LAYER: dict[str, dict] = {
    "realtime_price": {"db": "Redis", "resolution": "1s/5s/1m", "ttl": "5-60s", "source": "BrsApi.ir, TSETMC"},
    "ohlcv": {
        "db": "TimescaleDB",
        "resolution": "5m,15m,1h,1D",
        "ttl": "permanent (Hypertable)",
        "source": "BrsApi, TSETMC, IME",
    },
    "nav_bubble": {
        "db": "TimescaleDB",
        "resolution": "1m (market hours)",
        "ttl": "permanent",
        "source": "TSETMC/internal",
    },
    "portfolio": {"db": "PostgreSQL", "resolution": "Event-based", "ttl": "permanent", "source": "Manual User Entry"},
}
