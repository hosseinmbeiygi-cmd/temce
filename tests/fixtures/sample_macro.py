from __future__ import annotations

from core.ids import new_id
from domain.macro.entities import MacroEntity


def sample_macro_indicator(
    id: str | None = None,
    indicator: str = "inflation",
    country: str = "iran",
) -> MacroEntity:
    return MacroEntity(
        id=id or new_id("mac"),
        name=indicator,
        value=42.5,
        previous_value=44.0,
        change_pct=-3.41,
        date=None,
        source="cbi",
        unit="percent",
        frequency="monthly",
        category=country,
        extra={"data_source": "rss"},
    )


def sample_macro_list(count: int = 5) -> list[MacroEntity]:
    indicators = ["inflation", "unemployment", "gdp_growth", "interest_rate", "money_supply"]
    return [sample_macro_indicator(indicator=indicators[i % len(indicators)]) for i in range(count)]

