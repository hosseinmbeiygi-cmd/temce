from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from schemas.common.legal import LEGAL_DISCLAIMER_FA

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: dict[str, Any] | None = None
    message: str | None = None
    # Wall-clock instant when the underlying data was produced/fetched (ISO-8601).
    # None when the response carries no freshness information (e.g. passthrough
    # endpoints that do not aggregate snapshots). Consumers can use it to tell
    # success-empty (data_as_of present, empty collection) from a stale cache
    # hit (data_as_of points at an old fetch) and from source failure
    # (success=False with error).
    data_as_of: str | None = None
    # True when the payload was served from the in-process aggregate cache
    # instead of a fresh query. Frontend keeps treating non-empty data as live;
    # this flag only exposes staleness so part 05 can render a degraded banner.
    cache_hit: bool = False
    # Optional SaaS metadata (tier/owner of the scoped token that served the
    # request) — only populated by the monetized surfaces (e.g. /golddesk).
    meta: dict[str, Any] | None = None
    # Most payloads are plain dicts, so the envelope is the only place where the
    # disclaimer is guaranteed to reach the client for every signal/forecast.
    legal_disclaimer: str = Field(default=LEGAL_DISCLAIMER_FA)


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, Any]
    message: str | None = None
