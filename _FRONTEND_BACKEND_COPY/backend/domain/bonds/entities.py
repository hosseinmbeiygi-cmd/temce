from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Bond(BaseEntity):
    name: str
    issuer: str = ""
    isin: str = ""
    face_value: float = 100000.0
    coupon_rate: float = 0.0
    coupon_frequency: str = "annual"
    issue_date: date | None = None
    maturity_date: date | None = None
    currency: str = "IRR"
    rating: str = ""
    status: str = "active"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        issuer: str = "",
        isin: str = "",
        face_value: float = 100000.0,
        coupon_rate: float = 0.0,
        coupon_frequency: str = "annual",
        issue_date: date | None = None,
        maturity_date: date | None = None,
        currency: str = "IRR",
        rating: str = "",
        status: str = "active",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.issuer = issuer
        self.isin = isin
        self.face_value = face_value
        self.coupon_rate = coupon_rate
        self.coupon_frequency = coupon_frequency
        self.issue_date = issue_date
        self.maturity_date = maturity_date
        self.currency = currency
        self.rating = rating
        self.status = status
        self.extra = extra or {}

    @property
    def years_to_maturity(self) -> float:
        if self.maturity_date is None:
            return 0.0
        return (self.maturity_date - date.today()).days / 365.0

    @property
    def is_matured(self) -> bool:
        if self.maturity_date is None:
            return False
        return date.today() >= self.maturity_date


@dataclass
class BondCoupon(BaseEntity):
    bond_id: str
    payment_date: date | None = None
    amount: float = 0.0
    currency: str = "IRR"
    is_paid: bool = False
    period_number: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        bond_id: str,
        payment_date: date | None = None,
        amount: float = 0.0,
        currency: str = "IRR",
        is_paid: bool = False,
        period_number: int = 0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.bond_id = bond_id
        self.payment_date = payment_date
        self.amount = amount
        self.currency = currency
        self.is_paid = is_paid
        self.period_number = period_number
        self.extra = extra or {}

    def mark_paid(self) -> None:
        self.is_paid = True
        self.mark_updated()
