from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        raise NotImplementedError

    def and_(self, other: Specification[T]) -> AndSpecification[T]:
        return AndSpecification(self, other)

    def or_(self, other: Specification[T]) -> OrSpecification[T]:
        return OrSpecification(self, other)

    def not_(self) -> NotSpecification[T]:
        return NotSpecification(self)

    def __call__(self, candidate: T) -> bool:
        return self.is_satisfied_by(candidate)


class AndSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        super().__init__()
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class OrSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        super().__init__()
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class NotSpecification(Specification[T]):
    def __init__(self, spec: Specification[T]) -> None:
        super().__init__()
        self._spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)


class AttributeSpecification(Specification[Any]):
    def __init__(self, attr_name: str, expected_value: Any) -> None:
        super().__init__()
        self._attr_name = attr_name
        self._expected_value = expected_value

    def is_satisfied_by(self, candidate: Any) -> bool:
        return getattr(candidate, self._attr_name, None) == self._expected_value
