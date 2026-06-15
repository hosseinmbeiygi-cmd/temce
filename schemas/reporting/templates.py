from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TemplateVariable(BaseModel):
    name: str
    variable_type: str = "string"
    default_value: Any = None
    description: str = ""
    required: bool = False


class TemplateSection(BaseModel):
    name: str
    section_type: str = "table"
    title: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    order: int = 0


class ReportTemplate(BaseModel):
    id: str
    name: str
    description: str = ""
    template_type: str = "report"
    sections: list[TemplateSection] = Field(default_factory=list)
    variables: list[TemplateVariable] = Field(default_factory=list)
    styles: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
