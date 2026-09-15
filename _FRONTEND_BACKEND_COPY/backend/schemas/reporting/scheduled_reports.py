from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReportDelivery(BaseModel):
    method: str = "email"
    recipients: list[str] = Field(default_factory=list)
    subject: str = ""
    body: str = ""


class ReportSchedule(BaseModel):
    cron_expression: str = "0 8 * * 1"
    timezone: str = "Asia/Tehran"
    start_date: str = ""
    end_date: str | None = None
    max_runs: int | None = None


class ScheduledReport(BaseModel):
    id: str
    name: str
    report_type: str = "summary"
    schedule: ReportSchedule = Field(default_factory=ReportSchedule)
    delivery: ReportDelivery = Field(default_factory=ReportDelivery)
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    last_run: str | None = None
    next_run: str | None = None
    created_at: str = ""
    updated_at: str = ""
