from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MaintenanceWindow(BaseModel):
    id: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    affected_services: list[str] = Field(default_factory=list)
    status: str = "scheduled"
    created_by: str = "admin"


class MaintenanceRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    description: str
    affected_services: list[str] = Field(default_factory=list)
