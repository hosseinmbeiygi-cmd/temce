from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AppErrorSchema(BaseModel):
    code: str = Field(default="UNKNOWN", description="Error code identifier")
    message: str = Field(default="An error occurred", description="Human-readable error message")
    details: dict[str, Any] | None = None


class ValidationErrorSchema(AppErrorSchema):
    code: str = "VALIDATION_ERROR"
    field_errors: list[dict[str, Any]] = Field(default_factory=list, description="Per-field validation errors")
