from __future__ import annotations

from typing import Any


class CashManager:
    def __init__(self, initial_capital: float = 0.0) -> None:
        self._cash: float = initial_capital
        self._locked: float = 0.0
        self._initial_capital: float = initial_capital
        self._cash_flow: list[dict[str, Any]] = []

    def reset(self, initial_capital: float) -> None:
        self._cash = initial_capital
        self._locked = 0.0
        self._initial_capital = initial_capital
        self._cash_flow.clear()

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def locked(self) -> float:
        return self._locked

    @property
    def free(self) -> float:
        return self._cash - self._locked

    def deposit(self, amount: float, reason: str = "") -> None:
        self._cash += amount
        self._cash_flow.append({"type": "deposit", "amount": amount, "reason": reason, "balance": self._cash})

    def withdraw(self, amount: float, reason: str = "") -> bool:
        if amount > self.free:
            return False
        self._cash -= amount
        self._cash_flow.append({"type": "withdraw", "amount": amount, "reason": reason, "balance": self._cash})
        return True

    def lock(self, amount: float) -> None:
        self._locked += amount

    def unlock(self, amount: float) -> None:
        self._locked = max(0.0, self._locked - amount)

    def can_afford(self, amount: float) -> bool:
        return amount <= self.free

    def get_cash_flow_history(self) -> list[dict[str, Any]]:
        return list(self._cash_flow)

    def get_total_return(self) -> float:
        return self._cash - self._initial_capital
