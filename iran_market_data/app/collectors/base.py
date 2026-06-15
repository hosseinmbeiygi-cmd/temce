from __future__ import annotations

from pathlib import Path

from iran_market_data.app.storage.raw_storage import RawStorage
from iran_market_data.app.utils.http import HttpClient
from iran_market_data.app.utils.logger import setup_logger


class BaseCollector:
    """Base class for all data collectors."""

    source_name: str = "base"

    def __init__(self) -> None:
        self.http = HttpClient()
        self.raw_storage = RawStorage()
        self.logger = setup_logger(f"collector.{self.source_name}")

    @property
    def session(self):
        """Access the underlying requests.Session for header customization."""
        return self.http.session

    def save_raw(
        self,
        source: str,
        name: str,
        content: str | bytes,
        file_format: str = "txt",
    ) -> Path:
        """Save raw content to disk, auto-detecting format.

        Delegates to the appropriate RawStorage method based on file_format.
        """
        if file_format in ("json",):
            import json

            try:
                data = json.loads(content) if isinstance(content, str) else json.loads(content.decode())
                return self.raw_storage.save_json(source, name, data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        if file_format in ("html", "htm"):
            text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
            return self.raw_storage.save_html(source, name, text)

        if file_format in ("pdf", "xls", "xlsx", "csv", "zip"):
            data = content if isinstance(content, bytes) else content.encode()
            filename = f"{name}_{self.raw_storage.timestamp}.{file_format}"
            return self.raw_storage.save_file(source, filename, data)

        # Default: save as text file
        text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        folder = self.raw_storage.base_dir / "txt" / source
        folder.mkdir(parents=True, exist_ok=True)
        file_path = folder / f"{name}_{self.raw_storage.timestamp}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)
        return file_path

    def collect(self) -> dict:
        raise NotImplementedError("Subclasses must implement collect()")
