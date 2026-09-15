from __future__ import annotations

IRAN_MARKET_OPEN = "09:00"
IRAN_MARKET_CLOSE = "12:30"
IRAN_TIMEZONE = "Asia/Tehran"

# Tehran equity market is closed on Thursday and Friday.
# datetime.weekday(): Monday=0, Thursday=3, Friday=4.
MARKET_WEEKEND_DAYS = (3, 4)
TEHRAN_STOCK_EXCHANGE_CODE = "TSE"
FARABOURSE_CODE = "FaraBourse"
IRAN_FARA_BOURSE_NAME = "فرابورس ایران"
TEHRAN_STOCK_EXCHANGE_NAME = "بورس اوراق بهادار تهران"

MARKET_SECTORS = (
    "financial",
    "petrochemical",
    "metal",
    "pharmaceutical",
    "automotive",
    "construction",
    "food",
    "insurance",
    "holding",
)

CURRENCY_PAIRS = ("USD_IRR", "EUR_IRR", "GBP_IRR", "TRY_IRR", "AED_IRR")
COMMODITIES = ("gold", "oil", "copper", "steel", "cement")
INDICES = ("TEDPIX", "TEDIX", "TEFIX", "TEDIX30")
