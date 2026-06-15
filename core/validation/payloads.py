from __future__ import annotations

from typing import Any


def validate_payload(data: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    required_fields = schema.get("required", [])
    fields = schema.get("fields", {})

    for field in required_fields:
        if field not in data or data[field] is None:
            errors.append({"field": field, "message": "required"})

    for field, rules in fields.items():
        if field not in data:
            continue
        value = data[field]
        field_type = rules.get("type", "any")
        if field_type == "string" and not isinstance(value, str):
            errors.append({"field": field, "message": f"expected string, got {type(value).__name__}"})
        elif field_type == "number" and not isinstance(value, (int, float)):
            errors.append({"field": field, "message": f"expected number, got {type(value).__name__}"})
        elif field_type == "integer" and not isinstance(value, int):
            errors.append({"field": field, "message": f"expected integer, got {type(value).__name__}"})
        elif field_type == "boolean" and not isinstance(value, bool):
            errors.append({"field": field, "message": f"expected boolean, got {type(value).__name__}"})
        elif field_type == "array" and not isinstance(value, list):
            errors.append({"field": field, "message": f"expected array, got {type(value).__name__}"})
        if "min_length" in rules and isinstance(value, str) and len(value) < rules["min_length"]:
            errors.append({"field": field, "message": f"minimum length {rules['min_length']}"})
        if "max_length" in rules and isinstance(value, str) and len(value) > rules["max_length"]:
            errors.append({"field": field, "message": f"maximum length {rules['max_length']}"})
        if "min" in rules and isinstance(value, (int, float)) and value < rules["min"]:
            errors.append({"field": field, "message": f"minimum value {rules['min']}"})
        if "max" in rules and isinstance(value, (int, float)) and value > rules["max"]:
            errors.append({"field": field, "message": f"maximum value {rules['max']}"})
        if "choices" in rules and value not in rules["choices"]:
            errors.append({"field": field, "message": f"must be one of: {rules['choices']}"})

    return errors


def validate_payload_strict(data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    errors = validate_payload(data, schema)
    if errors:
        from core.exceptions import ValidationError

        raise ValidationError(errors=errors)
    return data
