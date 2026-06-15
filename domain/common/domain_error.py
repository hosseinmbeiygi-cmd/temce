from __future__ import annotations

from typing import Any


class DomainError(Exception):
    def __init__(
        self, message: str = "Domain rule violated", code: str = "DOMAIN_ERROR", details: dict[str, Any] | None = None
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, entity: str = "Entity", identifier: str | None = None) -> None:
        msg = f"{entity} not found" + (f": {identifier}" if identifier else "")
        super().__init__(message=msg, code="NOT_FOUND", details={"entity": entity, "identifier": identifier})


class ValidationError(DomainError):
    def __init__(self, message: str = "Validation failed", errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", details={"errors": errors or []})


class DomainRuleViolation(DomainError):
    def __init__(self, rule: str, message: str = "Domain rule violation") -> None:
        super().__init__(message=message, code="RULE_VIOLATION", details={"rule": rule})
