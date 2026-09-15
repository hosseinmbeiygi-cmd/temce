"""LearningEngine — Learn from user interactions (Level 19).

Features:
- Track user feedback on recommendations
- Improve intent classification over time
- Adapt response style based on user preferences
- Learn effective filter/screener patterns
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
import time
from collections import defaultdict
from typing import Any

# Module-level lock: serialises all JSON file writes across instances
# to prevent data corruption when two async tasks call _save().
_WRITE_LOCK = threading.Lock()


class LearningEngine:
    """Learn from user interactions to improve responses."""

    def __init__(self, storage_path: str = "data/learning_data.json"):
        self._storage_path = storage_path
        self._data: dict[str, Any] = {
            "feedback": [],
            "intent_patterns": defaultdict(int),
            "successful_filters": [],
            "response_quality": [],
            "user_preferences": {},
        }
        self._load()

    def _load(self) -> None:
        """Load learning data from disk."""
        try:
            if os.path.exists(self._storage_path):
                with open(self._storage_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data["feedback"] = loaded.get("feedback", [])
                    self._data["intent_patterns"] = defaultdict(int, loaded.get("intent_patterns", {}))
                    self._data["successful_filters"] = loaded.get("successful_filters", [])
                    self._data["response_quality"] = loaded.get("response_quality", [])
                    self._data["user_preferences"] = loaded.get("user_preferences", {})
        except Exception:
            pass

    def _save(self) -> None:
        """Save learning data to disk atomically.

        Uses temp-file + ``os.replace`` so a crash mid-write never corrupts
        the file.  A ``threading.Lock`` serialises concurrent callers.
        """
        try:
            os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
            data_to_save = {
                "feedback": self._data["feedback"][-500:],
                "intent_patterns": dict(self._data["intent_patterns"]),
                "successful_filters": self._data["successful_filters"][-100:],
                "response_quality": self._data["response_quality"][-500:],
                "user_preferences": self._data["user_preferences"],
            }
            with _WRITE_LOCK:
                fd, tmp = tempfile.mkstemp(
                    dir=os.path.dirname(self._storage_path) or ".",
                    suffix=".json.tmp",
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                    os.replace(tmp, self._storage_path)
                except Exception:
                    # Clean up partial temp file on failure
                    with contextlib.suppress(OSError):
                        os.unlink(tmp)
                    raise
        except Exception:
            pass

    def record_feedback(self, user_id: str, query: str, response: str, rating: int, feedback_text: str = "") -> None:
        """Record user feedback on a response.

        Args:
            rating: 1-5 (1=bad, 5=excellent)
        """
        self._data["feedback"].append(
            {
                "user_id": user_id,
                "query": query,
                "response_preview": response[:100],
                "rating": max(1, min(5, rating)),
                "feedback_text": feedback_text,
                "timestamp": time.time(),
            }
        )
        self._save()

    def record_successful_intent(self, text: str, intent: str) -> None:
        """Record that a text-intent mapping was successful."""
        # Create a normalized pattern key
        key = f"{text.lower().strip()[:30]}->{intent}"
        self._data["intent_patterns"][key] += 1

        # Periodically clean up
        if len(self._data["intent_patterns"]) % 50 == 0:
            self._clean_intent_patterns()

        self._save()

    def record_successful_filter(self, filter_desc: str, result_count: int) -> None:
        """Record a successful filter."""
        self._data["successful_filters"].append(
            {
                "filter": filter_desc,
                "result_count": result_count,
                "timestamp": time.time(),
            }
        )
        self._save()

    def get_effective_intent_patterns(self, min_uses: int = 3) -> list[tuple[str, str]]:
        """Get commonly successful intent patterns."""
        patterns = []
        for key, count in self._data["intent_patterns"].items():
            if count >= min_uses and "->" in key:
                parts = key.split("->")
                if len(parts) == 2:
                    patterns.append((parts[0], parts[1]))
        return patterns

    def get_popular_filters(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get most popular filter patterns."""
        filters = self._data["successful_filters"]
        # Group by filter description
        filter_counts: dict[str, dict] = {}
        for f in filters:
            desc = f["filter"]
            if desc not in filter_counts:
                filter_counts[desc] = {"filter": desc, "count": 0, "avg_results": 0}
            filter_counts[desc]["count"] += 1
            filter_counts[desc]["avg_results"] = (
                filter_counts[desc]["avg_results"] * (filter_counts[desc]["count"] - 1) + f["result_count"]
            ) / filter_counts[desc]["count"]

        sorted_filters = sorted(
            filter_counts.values(),
            key=lambda x: x["count"],
            reverse=True,
        )
        return sorted_filters[:limit]

    def update_user_preference(self, user_id: str, key: str, value: Any) -> None:
        """Update a learned user preference."""
        if user_id not in self._data["user_preferences"]:
            self._data["user_preferences"][user_id] = {}
        self._data["user_preferences"][user_id][key] = value
        self._save()

    def get_user_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Get a learned user preference."""
        user_prefs = self._data["user_preferences"].get(user_id, {})
        return user_prefs.get(key, default)

    def _clean_intent_patterns(self) -> None:
        """Remove intent patterns with low usage."""
        to_remove = [k for k, v in self._data["intent_patterns"].items() if v < 2]
        for k in to_remove:
            del self._data["intent_patterns"][k]

    def get_stats(self) -> dict[str, Any]:
        """Get learning statistics."""
        feedback = self._data.get("feedback", [])
        avg_rating = sum(f["rating"] for f in feedback) / len(feedback) if feedback else 0

        return {
            "total_feedback": len(feedback),
            "avg_rating": round(avg_rating, 2),
            "intent_patterns_learned": len(self._data["intent_patterns"]),
            "successful_filters": len(self._data["successful_filters"]),
            "popular_filters": self.get_popular_filters(3),
        }
