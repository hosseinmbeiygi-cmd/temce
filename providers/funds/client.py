from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient

MOCK_FUND_LIST = [
    {
        "fund_id": "F001",
        "name": "Omid Equity Fund",
        "symbol": "OMID",
        "isin": "IRO1OMID0001",
        "fund_type": "equity",
        "manager": "Omid Investment Management",
        "custodian": "Melli Bank",
        "currency": "IRR",
        "nav": 12500.0,
        "total_units": 50000000,
        "unit_price": 12500,
        "status": "active",
    },
    {
        "fund_id": "F002",
        "name": "Aseman Fixed Income Fund",
        "symbol": "ASEM",
        "isin": "IRO1ASEM0001",
        "fund_type": "fixed_income",
        "manager": "Aseman Asset Management",
        "custodian": "Saderat Bank",
        "currency": "IRR",
        "nav": 5200.0,
        "total_units": 120000000,
        "unit_price": 5200,
        "status": "active",
    },
    {
        "fund_id": "F003",
        "name": "Saham Mixed Fund",
        "symbol": "SAHM",
        "isin": "IRO1SAHM0001",
        "fund_type": "mixed",
        "manager": "Saham Investment Co",
        "custodian": "Tejarat Bank",
        "currency": "IRR",
        "nav": 8900.0,
        "total_units": 30000000,
        "unit_price": 8900,
        "status": "active",
    },
]

MOCK_NAV_HISTORY = {
    "F001": [
        {"date": "2026-01-01", "nav": 10000.0, "unit_price": 10000, "daily_return_pct": 0.0},
        {"date": "2026-01-02", "nav": 10050.0, "unit_price": 10050, "daily_return_pct": 0.5},
        {"date": "2026-01-03", "nav": 10120.0, "unit_price": 10120, "daily_return_pct": 0.6965},
        {"date": "2026-01-04", "nav": 10080.0, "unit_price": 10080, "daily_return_pct": -0.3953},
        {"date": "2026-01-05", "nav": 10200.0, "unit_price": 10200, "daily_return_pct": 1.1905},
    ],
    "F002": [
        {"date": "2026-01-01", "nav": 5000.0, "unit_price": 5000, "daily_return_pct": 0.0},
        {"date": "2026-01-02", "nav": 5005.0, "unit_price": 5005, "daily_return_pct": 0.1},
        {"date": "2026-01-03", "nav": 5010.0, "unit_price": 5010, "daily_return_pct": 0.0999},
        {"date": "2026-01-04", "nav": 5012.0, "unit_price": 5012, "daily_return_pct": 0.0399},
        {"date": "2026-01-05", "nav": 5018.0, "unit_price": 5018, "daily_return_pct": 0.1197},
    ],
    "F003": [
        {"date": "2026-01-01", "nav": 8500.0, "unit_price": 8500, "daily_return_pct": 0.0},
        {"date": "2026-01-02", "nav": 8540.0, "unit_price": 8540, "daily_return_pct": 0.4706},
        {"date": "2026-01-03", "nav": 8600.0, "unit_price": 8600, "daily_return_pct": 0.7026},
        {"date": "2026-01-04", "nav": 8550.0, "unit_price": 8550, "daily_return_pct": -0.5814},
        {"date": "2026-01-05", "nav": 8700.0, "unit_price": 8700, "daily_return_pct": 1.7544},
    ],
}

MOCK_HOLDINGS = {
    "F001": [
        {
            "instrument_id": "I001",
            "symbol": "FOLD",
            "quantity": 150000,
            "market_value": 4500000000,
            "weight_pct": 28.5,
            "asset_type": "equity",
        },
        {
            "instrument_id": "I002",
            "symbol": "خودرو",
            "quantity": 200000,
            "market_value": 3200000000,
            "weight_pct": 20.2,
            "asset_type": "equity",
        },
        {
            "instrument_id": "I003",
            "symbol": "شپنا",
            "quantity": 180000,
            "market_value": 2880000000,
            "weight_pct": 18.2,
            "asset_type": "equity",
        },
        {
            "instrument_id": "I004",
            "symbol": "فولاد",
            "quantity": 120000,
            "market_value": 2400000000,
            "weight_pct": 15.2,
            "asset_type": "equity",
        },
        {
            "instrument_id": "I005",
            "symbol": "وبملت",
            "quantity": 100000,
            "market_value": 1800000000,
            "weight_pct": 11.4,
            "asset_type": "equity",
        },
        {
            "instrument_id": "I006",
            "symbol": "سهام",
            "quantity": 50000,
            "market_value": 1000000000,
            "weight_pct": 6.5,
            "asset_type": "cash",
        },
    ],
    "F002": [
        {
            "instrument_id": "I010",
            "symbol": "امواج1",
            "quantity": 500000,
            "market_value": 5000000000,
            "weight_pct": 40.0,
            "asset_type": "bond",
        },
        {
            "instrument_id": "I011",
            "symbol": "اجماد1",
            "quantity": 300000,
            "market_value": 3000000000,
            "weight_pct": 24.0,
            "asset_type": "bond",
        },
        {
            "instrument_id": "I012",
            "symbol": "اسداس1",
            "quantity": 200000,
            "market_value": 2000000000,
            "weight_pct": 16.0,
            "asset_type": "bond",
        },
        {
            "instrument_id": "I013",
            "symbol": "سهام",
            "quantity": 250000,
            "market_value": 2500000000,
            "weight_pct": 20.0,
            "asset_type": "cash",
        },
    ],
    "F003": [
        {
            "instrument_id": "I001",
            "symbol": "FOLD",
            "quantity": 80000,
            "market_value": 2400000000,
            "weight_pct": 20.0,
            "asset_type": "equity",
        },
        {
            "instrument_id": "I002",
            "symbol": "خودرو",
            "quantity": 100000,
            "market_value": 1600000000,
            "weight_pct": 13.3,
            "asset_type": "equity",
        },
        {
            "instrument_id": "I010",
            "symbol": "امواج1",
            "quantity": 250000,
            "market_value": 2500000000,
            "weight_pct": 20.8,
            "asset_type": "bond",
        },
        {
            "instrument_id": "I011",
            "symbol": "اجماد1",
            "quantity": 150000,
            "market_value": 1500000000,
            "weight_pct": 12.5,
            "asset_type": "bond",
        },
        {
            "instrument_id": "I014",
            "symbol": "طلا",
            "quantity": 500,
            "market_value": 2000000000,
            "weight_pct": 16.7,
            "asset_type": "commodity",
        },
        {
            "instrument_id": "I013",
            "symbol": "سهام",
            "quantity": 200000,
            "market_value": 2000000000,
            "weight_pct": 16.7,
            "asset_type": "cash",
        },
    ],
}


class FundApiClient(HttpClient):
    def __init__(self) -> None:
        base_url = getattr(settings, "fund_api_base_url", "http://localhost:8500/api/funds")
        super().__init__(base_url=base_url, timeout=settings.provider_default_timeout)

    async def get_fund_list(self) -> Result[Any]:
        result = await self.get("/list")
        if result.success:
            return result
        return Result.ok(MOCK_FUND_LIST)

    async def get_fund_detail(self, fund_id: str) -> Result[Any]:
        result = await self.get(f"/detail/{fund_id}")
        if result.success:
            return result
        for fund in MOCK_FUND_LIST:
            if fund.get("fund_id") == fund_id:
                return Result.ok(fund)
        return Result.fail(f"Fund not found: {fund_id}")

    async def get_fund_nav_history(self, fund_id: str, start_date: str = "", end_date: str = "") -> Result[Any]:
        result = await self.get(f"/nav/{fund_id}", params={"start_date": start_date, "end_date": end_date})
        if result.success:
            return result
        nav_list = MOCK_NAV_HISTORY.get(fund_id, [])
        if not nav_list:
            return Result.fail(f"No NAV history for fund: {fund_id}")
        filtered = nav_list
        if start_date:
            filtered = [n for n in filtered if n["date"] >= start_date]
        if end_date:
            filtered = [n for n in filtered if n["date"] <= end_date]
        return Result.ok(filtered)

    async def get_fund_holdings(self, fund_id: str) -> Result[Any]:
        result = await self.get(f"/holdings/{fund_id}")
        if result.success:
            return result
        holdings = MOCK_HOLDINGS.get(fund_id, [])
        if not holdings:
            return Result.fail(f"No holdings for fund: {fund_id}")
        return Result.ok(holdings)
