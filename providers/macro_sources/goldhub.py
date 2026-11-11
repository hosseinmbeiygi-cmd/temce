"""World Gold Council (Goldhub) data provider — file-based Excel/CSV importer.

Goldhub (gold.org) has no public JSON API. Data is distributed as Excel files
downloaded from https://www.gold.org/goldhub/data. Supported datasets:

  * gold-demand-statistics      — quarterly supply & demand by use category
  * central-bank-statistics     — official sector net purchases by country
  * investment-statistics       — ETF holdings, bar & coin demand
  * mine-production             — quarterly mine production by country

Usage:
    provider = GoldhubProvider()
    result = await provider.load(file_path="downloads/gold_demand_2024.xlsx",
                                  dataset="gold-demand-statistics")

The returned rows are JSON-safe dicts. The provider is stateless; callers
persist rows via MacroSyncService or directly.

No API key, no network call: everything is file-local.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.result import Result
from providers.base.base_provider import BaseProvider

logger = logging.getLogger(__name__)

# Official column→canonical-key renames for Goldhub demand sheet
_DEMAND_COL_MAP: dict[str, str] = {
    "Date":                     "as_of",
    "Jewellery":                "jewellery_tonnes",
    "Technology":               "technology_tonnes",
    "Investment":               "investment_tonnes",
    "Central banks & other inst.": "central_banks_tonnes",
    "Total demand":             "total_demand_tonnes",
    "Total supply":             "total_supply_tonnes",
    "Mine production":          "mine_production_tonnes",
    "Recycled gold":            "recycled_tonnes",
}

SUPPORTED_DATASETS = frozenset([
    "gold-demand-statistics",
    "central-bank-statistics",
    "investment-statistics",
    "mine-production",
])


def _load_openpyxl() -> Any:
    try:
        import openpyxl  # noqa: PLC0415
        return openpyxl
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl is required to read Goldhub Excel files. "
            "Add it to requirements.txt and run: pip install openpyxl"
        ) from exc


def _xlsx_to_rows(path: Path) -> list[dict[str, Any]]:
    """Read the first worksheet of an Excel file into a list of dicts."""
    openpyxl = _load_openpyxl()
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    result: list[dict[str, Any]] = []
    for row in rows[1:]:
        if all(cell is None for cell in row):
            continue
        result.append({headers[i]: cell for i, cell in enumerate(row)})
    return result


def _csv_to_rows(path: Path) -> list[dict[str, Any]]:
    import csv  # stdlib — always available
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def _normalise_demand_rows(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rename Goldhub demand columns to canonical keys and drop nulls."""
    out: list[dict[str, Any]] = []
    for row in raw:
        norm = {_DEMAND_COL_MAP.get(k, k): v for k, v in row.items()}
        # Skip rows where every numeric field is None
        numeric = {k: v for k, v in norm.items() if k != "as_of" and v is not None}
        if not numeric:
            continue
        out.append(norm)
    return out


class GoldhubProvider(BaseProvider):
    """File-based World Gold Council data importer.

    Not a live feed — it loads a pre-downloaded Goldhub Excel or CSV file.
    Inject ``fs_root`` to override the default download directory.
    """

    def __init__(self, fs_root: str | Path | None = None) -> None:
        super().__init__(name="goldhub")
        self._fs_root = Path(fs_root) if fs_root else Path("downloads/goldhub")

    async def fetch(
        self,
        *,
        file_path: str | Path | None = None,
        dataset: str = "gold-demand-statistics",
        **kwargs: Any,
    ) -> Result[Any]:
        """Load a Goldhub file and return normalised rows.

        Args:
            file_path: Explicit path to the Excel/CSV file. When omitted the
                provider looks for a file named ``<dataset>.xlsx`` (or .csv)
                under ``self._fs_root``.
            dataset: One of :attr:`SUPPORTED_DATASETS`. Used to auto-locate
                the file and select the normalisation logic.
        """
        if dataset not in SUPPORTED_DATASETS:
            return Result.fail(
                f"Unknown dataset {dataset!r}. Supported: {sorted(SUPPORTED_DATASETS)}"
            )

        path = self._resolve_path(file_path, dataset)
        if path is None or not path.exists():
            return Result.fail(
                f"Goldhub file not found for dataset={dataset!r}. "
                f"Download it from https://www.gold.org/goldhub/data and place it at "
                f"{self._fs_root / dataset}.xlsx (or .csv)."
            )

        try:
            raw = self._read_file(path)
        except Exception as exc:
            logger.warning("GoldhubProvider: failed to read %s: %s", path, exc)
            return Result.fail(f"Failed to read {path.name}: {exc}")

        rows = self._normalise(dataset, raw)
        logger.info("GoldhubProvider: loaded %d rows from %s", len(rows), path.name)
        return Result.ok({"dataset": dataset, "source_file": path.name, "rows": rows})

    async def health(self) -> dict[str, Any]:
        """Reports available pre-downloaded Goldhub files."""
        found = []
        for ds in sorted(SUPPORTED_DATASETS):
            p = self._resolve_path(None, ds)
            if p and p.exists():
                found.append(ds)
        if found:
            return {"healthy": True, "available_datasets": found}
        return {
            "healthy": False,
            "message": f"No Goldhub files found under {self._fs_root}. "
                       "Download from https://www.gold.org/goldhub/data",
        }

    # ── private helpers ───────────────────────────────────────────────────────

    def _resolve_path(
        self,
        explicit: str | Path | None,
        dataset: str,
    ) -> Path | None:
        if explicit is not None:
            return Path(explicit)
        for ext in (".xlsx", ".csv"):
            candidate = self._fs_root / f"{dataset}{ext}"
            if candidate.exists():
                return candidate
        return self._fs_root / f"{dataset}.xlsx"

    def _read_file(self, path: Path) -> list[dict[str, Any]]:
        if path.suffix.lower() in (".xlsx", ".xls"):
            return _xlsx_to_rows(path)
        return _csv_to_rows(path)

    def _normalise(self, dataset: str, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if dataset == "gold-demand-statistics":
            return _normalise_demand_rows(raw)
        return raw
