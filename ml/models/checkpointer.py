from __future__ import annotations

from typing import Any


class ModelCheckpointer:
    def __init__(self, checkpoint_dir: str = "./checkpoints") -> None:
        import os

        os.makedirs(checkpoint_dir, exist_ok=True)
        self.checkpoint_dir = checkpoint_dir

    def save_checkpoint(self, model: Any, epoch: int, path: str | None = None) -> str:
        import pickle

        save_path = path or f"{self.checkpoint_dir}/epoch_{epoch}.pkl"
        with open(save_path, "wb") as f:
            pickle.dump({"epoch": epoch, "model": model}, f)
        return save_path

    def load_checkpoint(self, path: str) -> tuple[Any, int]:
        import pickle

        with open(path, "rb") as f:
            data = pickle.load(f)
        return data["model"], data["epoch"]
