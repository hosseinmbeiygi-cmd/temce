from __future__ import annotations

from typing import Any


def get_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": True,
    }


def validate_against_schema(data: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root must be an object"]
    props = schema.get("properties", {})
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    for key, value in data.items():
        prop_schema = props.get(key, {})
        prop_type = prop_schema.get("type", "any")
        if prop_type == "string" and not isinstance(value, str):
            errors.append(f"Field '{key}' must be a string")
        elif prop_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Field '{key}' must be a number")
        elif prop_type == "integer" and not isinstance(value, int):
            errors.append(f"Field '{key}' must be an integer")
        elif prop_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Field '{key}' must be a boolean")
        elif prop_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{key}' must be an array")
    return errors


def merge_schemas(*schemas: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for schema in schemas:
        merged["properties"].update(schema.get("properties", {}))
        merged["required"].extend(schema.get("required", []))
    merged["required"] = list(set(merged["required"]))
    return merged
