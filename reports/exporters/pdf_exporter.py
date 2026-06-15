from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class PdfExporter:
    def __init__(self, html_exporter: Any | None = None):
        self._html_exporter = html_exporter

    async def export(self, data: dict[str, Any], output_path: str = "") -> Result[str]:
        html_result = (
            await self._html_exporter.export(data) if self._html_exporter else Result.ok(self._dict_to_html(data))
        )
        if not html_result.success:
            return Result.fail(html_result.error)
        html_content = html_result.value if isinstance(html_result.value, str) else ""
        try:
            from weasyprint import HTML

            pdf_bytes = HTML(string=html_content).write_pdf()
            if output_path:
                with open(output_path, "wb") as f:
                    f.write(pdf_bytes)
                return Result.ok(output_path)
            return Result.ok(html_content)
        except ImportError:
            return Result.fail("PDF export requires weasyprint: pip install weasyprint")

    async def export_to_bytes(self, data: dict[str, Any]) -> Result[bytes]:
        html_result = (
            await self._html_exporter.export(data) if self._html_exporter else Result.ok(self._dict_to_html(data))
        )
        if not html_result.success:
            return Result.fail(html_result.error)
        html_content = html_result.value if isinstance(html_result.value, str) else ""
        try:
            from weasyprint import HTML

            pdf_bytes = HTML(string=html_content).write_pdf()
            return Result.ok(pdf_bytes)
        except ImportError:
            return Result.fail("PDF export requires weasyprint: pip install weasyprint")

    def _dict_to_html(self, data: dict[str, Any]) -> str:
        rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in data.items())
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body><table border="1">{rows}</table></body></html>"""
