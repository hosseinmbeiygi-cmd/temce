# Iran Market Data Collector

A modular data collection tool for Iran's capital market.

## Sources

| Source | Description | Data Types |
|--------|-------------|------------|
| **TSETMC** | Tehran Stock Exchange | Market watch, daily prices, order books |
| **Codal** | Corporate disclosure system | Announcements, financial reports, PDF/Excel files |
| **Fipiran** | Fund information platform | Fund NAV, returns, fund profiles |

## Project Structure

```
iran_market_data/
├── app/
│   ├── collectors/      # Data collectors (TSETMC, Codal, Fipiran)
│   ├── parsers/         # HTML, Excel, PDF parsers
│   ├── storage/         # File & database storage
│   └── utils/           # HTTP, text normalizer, logger
├── data/
│   ├── raw/             # Raw collected data (JSON, HTML, PDF, Excel)
│   └── processed/       # Cleaned/processed data
├── scripts/             # Run scripts for each source
├── requirements.txt
└── .env
```

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Find the API endpoint
Open the source website in Chrome, open DevTools (F12) → Network tab,
find the actual JSON/API endpoint.

### 3. Update the collector
Replace `PUT_TSETMC_JSON_ENDPOINT_HERE` in the collector file
with the real URL from DevTools.

### 4. Run
```bash
python scripts/run_tsetmc.py
```

### 5. View raw data
```bash
ls data/raw/json/tsetmc/
```

## Workflow

1. **Collect raw data** → save to `data/raw/`
2. **Parse raw data** → extract structured fields
3. **Store processed data** → save to database or `data/processed/`

## Recommended Order

1. TSETMC (simplest - JSON API)
2. Fipiran (HTML tables → pandas)
3. Codal (HTML pages → file downloads → PDF/Excel parsing)
