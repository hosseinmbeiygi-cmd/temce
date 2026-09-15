from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssetClass(StrEnum):
    ETF = "gold_etf"
    GOLD = "gold"
    FX = "fx"
    CRYPTO = "crypto"
    GLOBAL = "global"
    COMMODITY = "commodity"


class QualityFlag(StrEnum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    STALE = "stale"
    INVALID = "invalid"


class DecisionBasis(StrEnum):
    """Reference currency used by downstream signal/risk engines."""

    RIAL = "rial"
    DOLLAR = "dollar"
    DUAL = "dual"


class MarketTick(BaseModel):
    """Canonical, source-neutral market observation.

    Prices are represented as Decimal to avoid binary floating point errors.
    ``observed_at`` is the source timestamp; ``received_at`` is assigned by us.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str = Field(min_length=1, max_length=64)
    instrument: str = Field(min_length=1, max_length=128)
    asset_class: AssetClass
    observed_at: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    price: Decimal = Field(gt=0)
    bid: Decimal | None = Field(default=None, gt=0)
    ask: Decimal | None = Field(default=None, gt=0)
    open: Decimal | None = Field(default=None, gt=0)
    high: Decimal | None = Field(default=None, gt=0)
    low: Decimal | None = Field(default=None, gt=0)
    close: Decimal | None = Field(default=None, gt=0)
    volume: Decimal | None = Field(default=None, ge=0)
    value: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="IRR", min_length=3, max_length=12)
    decision_basis: DecisionBasis = DecisionBasis.DUAL
    quality: QualityFlag = QualityFlag.CLEAN
    quality_reasons: list[str] = Field(default_factory=list)
    raw_object_key: str | None = None
    raw_sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at", "received_at", mode="before")
    @classmethod
    def ensure_utc(cls, value: datetime | str) -> datetime:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)

    @field_validator("price", "bid", "ask", "open", "high", "low", "close", "volume", "value", mode="before")
    @classmethod
    def parse_decimal(cls, value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value).replace(",", ""))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"invalid numeric value: {value!r}") from exc


def parse_decimal(value: Any) -> Decimal | None:
    """Best-effort numeric parser used by source adapters."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError, TypeError):
        return None
