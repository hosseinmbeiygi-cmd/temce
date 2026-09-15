from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DashboardWidget(BaseModel):
    id: str
    widget_type: str = "chart"
    title: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, int] = Field(default_factory=lambda: {"x": 0, "y": 0, "w": 6, "h": 4})
    dataset: str = ""
    refresh_interval_seconds: int = 60


class DashboardConfig(BaseModel):
    name: str
    description: str = ""
    widgets: list[DashboardWidget] = Field(default_factory=list)
    layout: str = "grid"
    is_public: bool = False


class DashboardResponse(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    widgets: list[DashboardWidget] = Field(default_factory=list)
    widget_count: int = 0
    layout: str = "grid"
    is_public: bool = False
    created_at: str = ""
    updated_at: str = ""
