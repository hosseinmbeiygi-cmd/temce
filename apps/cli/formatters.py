from __future__ import annotations

import json
from typing import Any


def format_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "No data"
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    lines = [sep]
    header_row = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths, strict=False)) + " |"
    lines.append(header_row)
    lines.append(sep)
    for row in rows:
        data_row = "| " + " | ".join(str(c).ljust(w) for c, w in zip(row, col_widths, strict=False)) + " |"
        lines.append(data_row)
    lines.append(sep)
    return "\n".join(lines)


def format_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_text(data: Any) -> str:
    if isinstance(data, list):
        return "\n".join(str(item) for item in data)
    if isinstance(data, dict):
        return "\n".join(f"{k}: {v}" for k, v in data.items())
    return str(data)
