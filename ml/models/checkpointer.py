from __future__ import annotations

from typing import Any


class ModelCheckpointer:
    def __init__(self, checkpoint_dir: str = "./checkpoints") -> None:
        from pathlib import Path

        self.checkpoint_dir = str(Path(checkpoint_dir).resolve())
        Path(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, model: Any, epoch: int, path: str | None = None) -> str:
        import pickle

        from core.paths import validate_safe_path

        save_path = path or f"{self.checkpoint_dir}/epoch_{epoch}.pkl"
        safe = validate_safe_path(save_path)
        safe.write_bytes(pickle.dumps({"epoch": epoch, "model": model}))
        return str(safe)

    def load_checkpoint(self, path: str) -> tuple[Any, int]:
        import pickle

        from core.paths import validate_safe_path

        safe = validate_safe_path(path)
        data = pickle.loads(safe.read_bytes())
        return data["model"], data["epoch"]
