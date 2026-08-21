"""Personalizer — User profile and personalization (Level 15).

Tracks:
- Favorite symbols
- Recent searches/filters
- User activity patterns
- Preference-based result boosting
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
import time
from typing import Any

# Module-level lock: serialises all JSON file writes across instances.
_WRITE_LOCK = threading.Lock()


class ProfileStore:
    """Persistent user profile storage using JSON file."""

    def __init__(self, storage_path: str = "data/user_profiles.json"):
        self._storage_path = storage_path
        self._profiles: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        """Load profiles from disk."""
        try:
            if os.path.exists(self._storage_path):
                with open(self._storage_path, encoding="utf-8") as f:
                    self._profiles = json.load(f)
        except Exception:
            self._profiles = {}

    def _save(self) -> None:
        """Save profiles to disk atomically.

        Uses temp-file + ``os.replace`` so a crash mid-write never corrupts
        the file.  A ``threading.Lock`` serialises concurrent callers.
        """
        try:
            os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
            with _WRITE_LOCK:
                fd, tmp = tempfile.mkstemp(
                    dir=os.path.dirname(self._storage_path) or ".",
                    suffix=".json.tmp",
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(self._profiles, f, ensure_ascii=False, indent=2)
                    os.replace(tmp, self._storage_path)
                except Exception:
                    with contextlib.suppress(OSError):
                        os.unlink(tmp)
                    raise
        except Exception:
            pass

    def get_profile(self, user_id: str) -> dict[str, Any]:
        """Get or create a user profile."""
        if user_id not in self._profiles:
            self._profiles[user_id] = {
                "favorite_symbols": [],
                "recent_searches": [],
                "recent_filters": [],
                "activity_count": 0,
                "first_seen": time.time(),
                "last_seen": time.time(),
                "preferences": {
                    "language": "fa",
                    "detail_level": "normal",
                    "chart_preference": True,
                },
                "intent_history": [],
            }
            self._dirty = True
            self._save()
        return self._profiles[user_id]

    def update_favorite_symbols(self, user_id: str, symbol: str) -> None:
        """Add a symbol to user's favorites."""
        profile = self.get_profile(user_id)
        favs = profile["favorite_symbols"]
        if symbol in favs:
            favs.remove(symbol)
        favs.insert(0, symbol)
        profile["favorite_symbols"] = favs[:20]  # Keep max 20
        profile["last_seen"] = time.time()
        self._save()

    def add_recent_search(self, user_id: str, query: str) -> None:
        """Add a search to user's history."""
        profile = self.get_profile(user_id)
        searches = profile["recent_searches"]
        if query in searches:
            searches.remove(query)
        searches.insert(0, query)
        profile["recent_searches"] = searches[:50]
        profile["activity_count"] += 1
        profile["last_seen"] = time.time()
        self._save()

    def add_recent_filter(self, user_id: str, filter_desc: str) -> None:
        """Record a filter the user applied."""
        profile = self.get_profile(user_id)
        filters = profile["recent_filters"]
        if filter_desc in filters:
            filters.remove(filter_desc)
        filters.insert(0, filter_desc)
        profile["recent_filters"] = filters[:10]
        self._save()

    def add_intent(self, user_id: str, intent: str) -> None:
        """Record user intent for learning."""
        profile = self.get_profile(user_id)
        profile["intent_history"].append({
            "intent": intent,
            "timestamp": time.time(),
        })
        # Keep last 100 intents
        profile["intent_history"] = profile["intent_history"][-100:]
        self._save()

    def get_recent_filters(self, user_id: str) -> list[str]:
        """Get user's recent filters."""
        return self.get_profile(user_id).get("recent_filters", [])

    def get_favorite_symbols(self, user_id: str) -> list[str]:
        """Get user's favorite symbols."""
        return self.get_profile(user_id).get("favorite_symbols", [])

    def get_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Get a user preference value."""
        prefs = self.get_profile(user_id).get("preferences", {})
        return prefs.get(key, default)

    def set_preference(self, user_id: str, key: str, value: Any) -> None:
        """Set a user preference."""
        profile = self.get_profile(user_id)
        if "preferences" not in profile:
            profile["preferences"] = {}
        profile["preferences"][key] = value
        self._save()


class Personalizer:
    """Personalize responses based on user profile and preferences."""

    def __init__(self, store: ProfileStore | None = None):
        self._store = store or ProfileStore()

    @property
    def store(self) -> ProfileStore:
        return self._store

    def update_from_intent(
        self, user_id: str, intent: str, entities: dict[str, Any], text: str
    ) -> None:
        """Update user profile based on detected intent."""
        profile = self._store.get_profile(user_id)

        # Track intent
        self._store.add_intent(user_id, intent)

        # Track analyzed symbols as favorites
        symbols = entities.get("symbols", [])
        for sym in symbols:
            self._store.update_favorite_symbols(user_id, sym)

        # Track search queries
        if intent in ("screener", "dynamic_filter", "find_best", "find_cheap"):
            self._store.add_recent_search(user_id, text)

        # Track filters
        conditions = entities.get("conditions", [])
        if conditions:
            filter_desc = " ".join(
                f"{c['field']}{c['operator']}{c['value']}" for c in conditions[:3]
            )
            self._store.add_recent_filter(user_id, filter_desc)

        profile["activity_count"] += 1
        profile["last_seen"] = time.time()

    def boost_results(
        self, user_id: str, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Boost favorite symbols in results."""
        favs = self._store.get_favorite_symbols(user_id)
        if not favs:
            return results

        boosted = []
        boosted_set = set()

        # First, add favorite symbols found in results
        for sym in favs:
            for r in results:
                if r.get("symbol") == sym and sym not in boosted_set:
                    r_copy = dict(r)
                    r_copy["is_favorite"] = True
                    boosted.append(r_copy)
                    boosted_set.add(sym)

        # Then add remaining results
        for r in results:
            if r.get("symbol") not in boosted_set:
                boosted.append(r)
                boosted_set.add(r.get("symbol"))

        return boosted

    def get_suggestion_text(self, user_id: str) -> str | None:
        """Get personalized suggestion based on user history."""
        profile = self._store.get_profile(user_id)
        favs = profile.get("favorite_symbols", [])
        recent_filters = profile.get("recent_filters", [])

        parts = []

        if favs:
            fav_list = ", ".join(favs[:3])
            parts.append(f"⭐ دنبال‌شده: {fav_list}")

        if recent_filters:
            last_filter = recent_filters[0]
            parts.append(f"🔁 فیلتر آخر: {last_filter}")

        if profile.get("activity_count", 0) > 0:
            parts.append(f"📊 {profile['activity_count']} تعامل")

        return "\n".join(parts) if parts else None
