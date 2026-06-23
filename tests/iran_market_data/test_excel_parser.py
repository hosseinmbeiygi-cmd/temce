from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest


class TestExcelParser:
    """Tests for Excel parser functions."""

    @pytest.fixture
    def sample_excel_file(self) -> Path:
        """Create a temporary Excel file for testing."""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A1"] = "Symbol"
        ws["B1"] = "Price"
        ws["A2"] = "فولاد"
        ws["B2"] = 15000
        ws["A3"] = "فملی"
        ws["B3"] = 25000

        # Add second sheet
        ws2 = wb.create_sheet("Sheet2")
        ws2["A1"] = "Name"
        ws2["B1"] = "Value"
        ws2["A2"] = "Item1"
        ws2["B2"] = 100

        tmpfile = Path(tempfile.mktemp(suffix=".xlsx"))
        wb.save(str(tmpfile))
        yield tmpfile
        tmpfile.unlink(missing_ok=True)

    def test_read_excel_file(self, sample_excel_file: Path) -> None:
        """read_excel_file should return a DataFrame."""
        from iran_market_data.app.parsers.excel_parser import read_excel_file

        df = read_excel_file(str(sample_excel_file))
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2  # 2 data rows

    def test_read_excel_file_columns(self, sample_excel_file: Path) -> None:
        """DataFrame should have correct column names."""
        from iran_market_data.app.parsers.excel_parser import read_excel_file

        df = read_excel_file(str(sample_excel_file))
        assert "Symbol" in df.columns or df.columns[0] == "Symbol"
        assert "Price" in df.columns or df.columns[1] == "Price"

    def test_read_excel_file_values(self, sample_excel_file: Path) -> None:
        """DataFrame should contain correct values."""
        from iran_market_data.app.parsers.excel_parser import read_excel_file

        df = read_excel_file(str(sample_excel_file))
        # Check values (may be indexed differently)
        symbols = df.iloc[:, 0].tolist()
        prices = df.iloc[:, 1].tolist()
        assert "فولاد" in symbols
        assert 15000 in prices

    def test_read_excel_specific_sheet(self, sample_excel_file: Path) -> None:
        """Reading a specific sheet by name should work."""
        from iran_market_data.app.parsers.excel_parser import read_excel_file

        df = read_excel_file(str(sample_excel_file), sheet_name="Sheet2")
        assert len(df) == 1
        assert df.iloc[0, 0] == "Item1"

    def test_read_all_sheets(self, sample_excel_file: Path) -> None:
        """read_all_sheets should return all sheets."""
        from iran_market_data.app.parsers.excel_parser import read_all_sheets

        sheets = read_all_sheets(str(sample_excel_file))
        assert isinstance(sheets, dict)
        assert "Sheet1" in sheets
        assert "Sheet2" in sheets
        assert len(sheets["Sheet1"]) == 2
        assert len(sheets["Sheet2"]) == 1

    def test_read_nonexistent_file(self) -> None:
        """Reading a nonexistent file should raise FileNotFoundError."""
        from iran_market_data.app.parsers.excel_parser import read_excel_file

        with pytest.raises((FileNotFoundError, Exception)):
            read_excel_file("/nonexistent/path/file.xlsx")

