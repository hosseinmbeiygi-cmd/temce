# GoldDesk Secret Hygiene Report
Generated: 2026-10-24

## Detected Secrets

| File:Line | Type | Description |
|---|---|---|
| src/gold_desk/api_token.py:28 | Default salt | Default configuration present in os.getenv() |
| docker-compose.yml:59 | Environment variable | API token salt environment variable must be set as secret |
| docker-compose.yml:29 | Redis password | Redis password environment variable required in .env |
| .env.example | Job queue token | Job queue token environment variable present as placeholder |

