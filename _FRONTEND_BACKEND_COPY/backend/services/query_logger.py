"""User query logger — saves all user questions to file for analysis."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Storage path
_LOG_DIR = Path("data/user_queries")
_LOG_FILE = _LOG_DIR / "queries.jsonl"


def log_query(
    query: str,
    intent: str | None = None,
    params: dict[str, Any] | None = None,
    response_type: str | None = None,
    success: bool = True,
    response_time_ms: float = 0,
    session_id: str | None = None,
) -> None:
    """Log a user query to the JSONL file."""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "query": query,
            "intent": intent,
            "params": params or {},
            "response_type": response_type,
            "success": success,
            "response_time_ms": round(response_time_ms, 2),
            "session_id": session_id,
        }

        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    except Exception as e:
        logger.warning("Failed to log query: %s", e)


def get_query_stats() -> dict[str, Any]:
    """Get statistics about logged queries."""
    try:
        if not _LOG_FILE.exists():
            return {"total": 0, "intents": {}, "top_queries": []}

        queries: list[dict] = []
        with open(_LOG_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    queries.append(json.loads(line))

        total = len(queries)
        intents: dict[str, int] = {}
        query_counts: dict[str, int] = {}

        for q in queries:
            intent = q.get("intent", "unknown")
            intents[intent] = intents.get(intent, 0) + 1
            query_text = q.get("query", "")
            query_counts[query_text] = query_counts.get(query_text, 0) + 1

        # Top 10 most frequent queries
        top_queries = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Intent distribution
        intent_pct = {
            k: round(v / total * 100, 1) for k, v in sorted(intents.items(), key=lambda x: x[1], reverse=True)
        }

        return {
            "total": total,
            "intents": intent_pct,
            "top_queries": [{"query": q, "count": c} for q, c in top_queries],
            "last_10": queries[-10:] if queries else [],
        }

    except Exception as e:
        logger.warning("Failed to get query stats: %s", e)
        return {"total": 0, "intents": {}, "top_queries": []}


def get_recent_queries(limit: int = 50) -> list[dict[str, Any]]:
    """Get the most recent queries."""
    try:
        if not _LOG_FILE.exists():
            return []

        queries: list[dict] = []
        with open(_LOG_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    queries.append(json.loads(line))

        return queries[-limit:]

    except Exception:
        return []
