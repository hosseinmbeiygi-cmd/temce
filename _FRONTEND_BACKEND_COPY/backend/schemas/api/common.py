from __future__ import annotations

from pydantic import BaseModel


class ApiMessage(BaseModel):
    message: str
    code: str = "OK"


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"


class VersionResponse(BaseModel):
    version: str = "0.1.0"
    build: str = ""
    environment: str = "development"
