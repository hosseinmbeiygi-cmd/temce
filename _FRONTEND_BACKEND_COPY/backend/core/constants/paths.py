from __future__ import annotations

from pathlib import Path

BASE_DIR = Path.cwd()
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_DIR = BASE_DIR / "config"
TEMP_DIR = BASE_DIR / "tmp"

RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
EXPORTS_DIR = DATA_DIR / "exports"
ARCHIVE_DIR = DATA_DIR / "archive"
BACKUP_DIR = DATA_DIR / "backup"
STORAGE_DIR = DATA_DIR / "storage"

QUOTES_DIR = RAW_DATA_DIR / "quotes"
ORDERBOOKS_DIR = RAW_DATA_DIR / "orderbooks"
TRADES_DIR = RAW_DATA_DIR / "trades"
NEWS_DIR = RAW_DATA_DIR / "news"
CODAL_DIR = RAW_DATA_DIR / "codal"
MACRO_DIR = RAW_DATA_DIR / "macro"

MIGRATIONS_DIR = BASE_DIR / "migrations"
INDICATORS_DIR = PROCESSED_DATA_DIR / "indicators"
SIGNALS_DIR = PROCESSED_DATA_DIR / "signals"
RECOMMENDATIONS_DIR = PROCESSED_DATA_DIR / "recommendations"
