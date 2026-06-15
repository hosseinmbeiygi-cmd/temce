from __future__ import annotations

import pandas as pd


def read_excel_file(file_path: str, sheet_name: int | str = 0) -> pd.DataFrame:
    """Read a single sheet from an Excel file.

    Args:
        file_path: Path to the Excel file.
        sheet_name: Sheet name or index (default: first sheet).

    Returns:
        DataFrame with the sheet data.
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    return df


def read_all_sheets(file_path: str) -> dict[str, pd.DataFrame]:
    """Read all sheets from an Excel file.

    Args:
        file_path: Path to the Excel file.

    Returns:
        Dict mapping sheet names to DataFrames.
    """
    sheets = pd.read_excel(file_path, sheet_name=None)
    return sheets
