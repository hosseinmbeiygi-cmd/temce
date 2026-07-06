from __future__ import annotations

import json
from typing import Any


class TestRawStorage:
    """Tests for RawStorage class."""

    def test_save_json(self, temp_raw_storage: Any, sample_json_data: dict) -> None:
        """save_json should create a JSON file with correct content."""
        file_path = temp_raw_storage.save_json("test_source", "test_data", sample_json_data)

        assert file_path.exists()
        assert file_path.suffix == ".json"
        assert "test_source" in str(file_path)
        assert "test_data" in str(file_path)

        with open(file_path, encoding="utf-8") as f:
            saved = json.load(f)

        assert saved["symbol"] == "فولاد"
        assert saved["price"] == 15000

    def test_save_html(self, temp_raw_storage: Any) -> None:
        """save_html should create an HTML file with correct content."""
        html_content = "<html><body><h1>Test</h1></body></html>"
        file_path = temp_raw_storage.save_html("test_source", "test_page", html_content)

        assert file_path.exists()
        assert file_path.suffix == ".html"
        assert "test_source" in str(file_path)

        with open(file_path, encoding="utf-8") as f:
            saved = f.read()

        assert saved == html_content

    def test_save_file_excel(self, temp_raw_storage: Any) -> None:
        """save_file for .xlsx should save in excel directory."""
        file_path = temp_raw_storage.save_file("codal", "report.xlsx", b"fake_excel_content")

        assert file_path.exists()
        assert "excel" in str(file_path)
        assert "codal" in str(file_path)

        with open(file_path, "rb") as f:
            content = f.read()
        assert content == b"fake_excel_content"

    def test_save_file_pdf(self, temp_raw_storage: Any) -> None:
        """save_file for .pdf should save in pdf directory."""
        file_path = temp_raw_storage.save_file("codal", "report.pdf", b"fake_pdf_content")

        assert file_path.exists()
        assert "pdf" in str(file_path)

    def test_save_file_csv(self, temp_raw_storage: Any) -> None:
        """save_file for .csv should save in excel directory (like xlsx)."""
        file_path = temp_raw_storage.save_file("tsetmc", "data.csv", b"a,b,c\n1,2,3")

        assert file_path.exists()
        assert "excel" in str(file_path)

    def test_save_file_unknown_extension(self, temp_raw_storage: Any) -> None:
        """save_file for unknown extension should save in files directory."""
        file_path = temp_raw_storage.save_file("general", "data.txt", b"text content")

        assert file_path.exists()
        assert "files" in str(file_path)
        assert "general" in str(file_path)

    def test_timestamp_format(self, temp_raw_storage: Any) -> None:
        """timestamp should return a string in YYYYMMDD_HHMMSS format."""
        ts = temp_raw_storage.timestamp
        assert len(ts) == 15  # YYYYMMDD_HHMMSS = 15 chars
        assert "_" in ts
        # Should be parseable as date
        parts = ts.split("_")
        assert len(parts) == 2
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS

    def test_save_json_file_naming(self, temp_raw_storage: Any) -> None:
        """save_json should include source, name, and timestamp in filename."""
        file_path = temp_raw_storage.save_json("mysource", "myname", {"key": "val"})
        filename = file_path.name

        assert filename.startswith("myname_")
        assert filename.endswith(".json")
        # Verify timestamp is in the name
        parts = filename.replace(".json", "").split("_")
        assert len(parts) >= 2
        assert parts[0] == "myname"

    def test_multiple_saves_same_source(self, temp_raw_storage: Any) -> None:
        """Multiple saves to the same source should create separate files."""
        p1 = temp_raw_storage.save_json("src", "data1", {"a": 1})
        p2 = temp_raw_storage.save_json("src", "data2", {"b": 2})

        assert p1.exists()
        assert p2.exists()
        assert p1 != p2
        assert p1.parent == p2.parent  # Same directory

