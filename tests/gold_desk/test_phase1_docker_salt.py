"""Phase 1 — GOLD_API_TOKEN_SALT must be declared in production docker-compose.

RED: file does not contain the required variable.
GREEN: after adding it to the x-app-prod anchor's environment block.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_gold_api_token_salt_in_production_compose():
    """GOLD_API_TOKEN_SALT must appear in docker-compose.production.yml with :? guard."""
    compose_path = ROOT / "docker-compose.production.yml"
    assert compose_path.exists(), "docker-compose.production.yml not found"

    text = compose_path.read_text(encoding="utf-8")
    assert "GOLD_API_TOKEN_SALT" in text, (
        "GOLD_API_TOKEN_SALT missing from docker-compose.production.yml; "
        "add it to the x-app-prod environment block with :? to fail on deploy."
    )
    assert ":?" in text or "GOLD_API_TOKEN_SALT must be set" in text, (
        "GOLD_API_TOKEN_SALT must use the :? fail-hard syntax so a missing value "
        "causes docker-compose to error at startup, not silently use an empty string."
    )
