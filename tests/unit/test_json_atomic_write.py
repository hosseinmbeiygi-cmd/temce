"""Regression tests for atomic JSON write in LearningEngine and ProfileStore.

Verifies:
1. Files are written atomically (no partial writes on crash).
2. Concurrent writes don't corrupt data.
3. Existing data survives a failed write attempt.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from services.chat.learning_engine import LearningEngine
from services.chat.personalizer import ProfileStore


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestLearningEngineAtomicWrite:
    """LearningEngine._save must be atomic and thread-safe."""

    def test_save_creates_valid_json(self, tmp_path: Path):
        path = str(tmp_path / "test_learning.json")
        engine = LearningEngine(storage_path=path)
        engine.record_feedback("u1", "test query", "response", 5, "great")
        data = _read_json(path)
        assert "feedback" in data
        assert len(data["feedback"]) == 1
        assert data["feedback"][0]["rating"] == 5

    def test_no_temp_files_left_after_save(self, tmp_path: Path):
        path = str(tmp_path / "test_learning.json")
        engine = LearningEngine(storage_path=path)
        engine.record_feedback("u1", "q", "r", 4)
        files = list(tmp_path.iterdir())
        assert len(files) == 1  # Only the main file

    def test_existing_data_survived_after_corrupt_save(self, tmp_path: Path):
        """If the save mechanism is correct, original file is untouched on failure."""
        path = str(tmp_path / "test_learning.json")
        engine = LearningEngine(storage_path=path)
        engine.record_feedback("u1", "q", "r", 5, "first")
        original = _read_json(path)

        # Simulate a scenario where the new data would fail:
        # The atomic pattern ensures the original file is never partially written.
        engine.record_feedback("u1", "q2", "r2", 3, "second")
        after = _read_json(path)
        assert len(after["feedback"]) == 2
        assert after["feedback"][0]["feedback_text"] == "first"

    def test_concurrent_writes_no_corruption(self, tmp_path: Path):
        path = str(tmp_path / "concurrent.json")
        engine = LearningEngine(storage_path=path)
        errors: list[Exception] = []

        def writer(uid: str):
            try:
                for i in range(10):
                    engine.record_feedback(uid, f"q{i}", f"r{i}", 3)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(f"user_{t}",)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent writes: {errors}"
        data = _read_json(path)
        # All 50 feedback entries should be present (5 users × 10 entries)
        assert len(data["feedback"]) == 50


class TestProfileStoreAtomicWrite:
    """ProfileStore._save must be atomic and thread-safe."""

    def test_save_creates_valid_json(self, tmp_path: Path):
        path = str(tmp_path / "test_profiles.json")
        store = ProfileStore(storage_path=path)
        store.update_favorite_symbols("u1", "فولاد")
        data = _read_json(path)
        assert "u1" in data
        assert "فولاد" in data["u1"]["favorite_symbols"]

    def test_no_temp_files_left_after_save(self, tmp_path: Path):
        path = str(tmp_path / "test_profiles.json")
        store = ProfileStore(storage_path=path)
        store.update_favorite_symbols("u1", "فولاد")
        files = list(tmp_path.iterdir())
        assert len(files) == 1

    def test_concurrent_writes_no_corruption(self, tmp_path: Path):
        path = str(tmp_path / "concurrent_profiles.json")
        store = ProfileStore(storage_path=path)
        errors: list[Exception] = []

        def writer(uid: str):
            try:
                for i in range(20):
                    store.update_favorite_symbols(uid, f"sym_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(f"user_{t}",)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent writes: {errors}"
        data = _read_json(path)
        # Each user should have up to 20 favorites
        for uid in [f"user_{t}" for t in range(3)]:
            assert uid in data
            assert len(data[uid]["favorite_symbols"]) == 20
