from __future__ import annotations


def validate_metal_price(price: float) -> bool:
    return price >= 0


def validate_spot_price(price: float) -> bool:
    return price > 0


def validate_contract_price(price: float) -> bool:
    return price >= 0


PRECIOUS_METALS = {"gold", "silver", "platinum", "palladium"}
BASE_METALS = {"copper", "aluminum", "zinc", "lead", "nickel", "tin"}


def is_precious_metal(metal_type: str) -> bool:
    return metal_type.lower() in PRECIOUS_METALS


def is_base_metal(metal_type: str) -> bool:
    return metal_type.lower() in BASE_METALS
