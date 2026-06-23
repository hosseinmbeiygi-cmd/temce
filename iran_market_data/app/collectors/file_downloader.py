from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from iran_market_data.app.collectors.base import BaseCollector


class FileDownloader(BaseCollector):
    """Download files (PDF, Excel, ZIP) from URLs."""

    source_name = "files"

    def download(self, file_url: str, source: str = "general", filename: str | None = None) -> str:
        """Download a file from a URL and save to raw storage.

        Args:
            file_url: The URL of the file to download.
            source: Source identifier for organizing files.
            filename: Optional custom filename. If None, extracted from URL.

        Returns:
            Path to the saved file.
        """
        response = self.http.get(file_url, timeout=60)

        if filename is None:
            path = urlparse(file_url).path
            filename = Path(path).name or "downloaded_file"

        saved_path = self.raw_storage.save_file(
            source=source,
            filename=filename,
            content=response.content,
        )

        self.logger.info("Downloaded %s -> %s", file_url, saved_path)

        return str(saved_path)

    def collect(self) -> dict:
        """FileDownloader doesn't have a default collect action."""
        return {"message": "Use download(file_url, source) instead"}
