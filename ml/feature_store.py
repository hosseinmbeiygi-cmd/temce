"""In-memory feature store — MLD-09 disambiguation.

This module holds an in-memory dict-backed FeatureStore used for feature
*registration* (tracking name → dtype mappings within a process).

The file-backed FeatureStore that persists feature vectors to JSON files lives
in ml.features.store.FeatureStore. Use that one for persistent feature storage.

MLD-09: having two classes with the same name in different modules causes
import confusion. Prefer ml.features.store.FeatureStore for any new code that
needs persistent feature storage.
"""

from __future__ import annotations


class FeatureStore:
    """Feature store for ML feature registration and management."""

    def __init__(self) -> None:
        self._features: dict[str, dict[str, str]] = {}

    def register_feature(self, name: str, group: str, dtype: str) -> None:
        if name in self._features:
            raise ValueError(f"Feature '{name}' is already registered")
        self._features[name] = {"group": group, "dtype": dtype}

    def get_features(self) -> dict[str, dict[str, str]]:
        return dict(self._features)

    def get_features_by_group(self, group: str) -> dict[str, dict[str, str]]:
        return {k: v for k, v in self._features.items() if v["group"] == group}

    def list_groups(self) -> list[str]:
        return list({v["group"] for v in self._features.values()})

    def remove_feature(self, name: str) -> None:
        self._features.pop(name, None)
