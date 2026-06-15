from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from reports.templates.base_template import BaseReportTemplate

logger = get_logger(__name__)


class HtmlExporter:
    def __init__(self, template: BaseReportTemplate | None = None):
        self._template = template or BaseReportTemplate()

    async def export(self, data: dict[str, Any], output_path: str = "") -> Result[str]:
        html = self._template.render(data)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            return Result.ok(output_path)
        return Result.ok(html)

    async def export_to_bytes(self, data: dict[str, Any]) -> Result[bytes]:
        html = self._template.render(data)
        return Result.ok(html.encode("utf-8"))

    async def export_table(
        self, rows: list[dict[str, Any]], title: str = "Report", output_path: str = ""
    ) -> Result[str]:
        if not rows:
            return Result.fail("No data to export")
        headers = list(rows[0].keys())
        thead = "".join(f"<th>{h}</th>" for h in headers)
        tbody = ""
        for row in rows:
            tbody += "<tr>" + "".join(f"<td>{row.get(h, '')}</td>" for h in headers) + "</tr>"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>table{{border-collapse:collapse;width:100%;font-family:sans-serif}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
th{{background-color:#f4f4f4}}</style></head>
<body><h1>{title}</h1><p>Generated: {datetime.now(UTC).isoformat()}</p>
<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></body></html>"""
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            return Result.ok(output_path)
        return Result.ok(html)
