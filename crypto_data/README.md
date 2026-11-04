# Static research snapshot (not live data)

These CSVs are a frozen crypto snapshot, **not** a live feed:

- price rows end at **2026-08-26**; files were written 2026-09-16;
- `all_data_180d.csv` contains 393 empty cells across 184 rows;
- `btc_history_180d.csv` / `eth_history_180d.csv` have 181 rows each and no nulls.

No runtime module reads this directory. It is input for offline research only.
Do not treat these values as current market data; re-fetch before any analysis.

Related audit: `AUDIT_REPORTS/MODULAR_TEMCE/40_DATA_FRESHNESS_run1_20261030.md`.
