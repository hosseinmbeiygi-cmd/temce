# MASTER PROMPT — Iran Commodity Market Intelligence & Trading Platform
### (Unified, corrected, phased specification — merges Backend / Frontend / Saffron-Pilot specs into one buildable system)

---

## 0. Role & Mission

You are a senior full-stack engineering team: a Solution Architect, a Backend/Data Engineer, a Frontend/UI Engineer, and a Data Scientist. Your mission is to design and build a **production-grade, multi-commodity market intelligence platform** for the Iran Mercantile Exchange (IME) ecosystem — covering metals, agricultural products, petrochemicals, and minerals — with **saffron as the fully-implemented pilot commodity** and a clear, config-driven pattern to extend to every other commodity afterward.

This is a merge of three prior specs (multi-commodity backend, multi-commodity frontend dashboard, and a saffron-specific full-stack MVP). Nothing from the three original specs has been dropped — overlapping requirements were deduplicated, contradictions were resolved, and gaps specific to the Iranian market were filled in. Follow this document as the single source of truth.

---

## 1. Legal & Compliance Disclaimer (mandatory, non-negotiable)

- Every price forecast, trading signal, and backtest result must be programmatically and visually tagged: **"For educational and research purposes only — not investment or trading advice."** This disclaimer must appear in the API response payload (a `disclaimer` field on `/signals`, `/forecasts`, `/backtest` endpoints) **and** in the UI wherever these are rendered.
- Data collection must respect `robots.txt` and each source's terms of service. Any data source that legally cannot be scraped or has no free API (see §3.3) must be replaced or marked `estimated`/`unverified`.
- Generating and distributing "confidence-scored buy/sell signals" to end users may fall under investment-advisory regulation in Iran. Do not silently ignore this: surface it explicitly to the (human) project owner as an open compliance question before the signals module is exposed publicly, and keep the disclaimer visible at all times.
- Store only the minimum personal data needed for auth; provide a way to anonymize/delete user data on request.

---

## 2. Development Phases (mandatory — do not attempt everything in one pass)

Large multi-commodity ML/backtesting/risk platforms cannot be reliably generated in a single pass. Build and confirm in this order:

- **Phase 1 — Foundation:** DB schema, shared API contract (OpenAPI, §3), auth, ingestion for **saffron only** (spot/futures price + one fundamental source), mock-data generator for all commodities, base REST endpoints, base dashboard shell (Overview + Saffron detail page) connected to mock data.
- **Phase 2 — Analytics Core:** Technical indicators, seasonality engine (Jalali-aware), correlation engine, news/sentiment pipeline, alerting — for saffron, wired end-to-end front-to-back.
- **Phase 3 — Forecasting & Signals:** SARIMA/GARCH, ML models (RF/XGBoost/LightGBM), ensemble forecast, signal engine with confidence scores, backtesting engine, risk/Monte Carlo module — for saffron.
- **Phase 4 — Multi-commodity extension:** Apply the config-driven "add a commodity" pattern (§8) to 4–5 additional representative commodities (e.g., steel billet, copper cathode, polyethylene, cement), one category at a time (metals → agri → petrochemicals → minerals).
- **Phase 5 — Advanced UI & Studio tools:** Backtesting Studio (visual strategy builder), Advanced Analytics Center, Option Chain Analyzer, customizable workspace/widget grid, PWA polish.

At the end of each phase, produce working, runnable code before moving to the next. Do not generate Phase 5 UI against a Phase 1 backend contract that hasn't been implemented yet.

---

## 3. Shared Data Contract (backend and frontend MUST use this, not independent guesses)

Because backend and frontend can be generated separately, **define the OpenAPI 3.1 schema first**, as its own artifact (`openapi.yaml`), before writing backend or frontend code. Both sides implement against this file. Do not let the frontend invent its own mock schema that diverges from it — the mock API service (§7.9) must be generated FROM this OpenAPI file, not written independently.

### 3.1 Technology Stack (final decisions — no ambiguous "or" choices)

**Backend:**
- Python 3.11+, **FastAPI** (not "FastAPI or Django" — pick FastAPI for async + auto OpenAPI generation)
- **PostgreSQL 15+ with TimescaleDB extension** — this is the only supported database. Do NOT build a SQLite-compatible abstraction layer; TimescaleDB hypertables/compression are core requirements and have no SQLite equivalent. For local dev without Docker, provide a `docker-compose.yml` that spins up Postgres+TimescaleDB in one command instead of an SQLite fallback.
- Redis (cache + Celery broker), Celery + Celery Beat (background/scheduled tasks)
- Alembic for migrations
- JWT auth (`python-jose` + `passlib`), role-based access (admin/analyst/viewer)

**Frontend:**
- React 18+ with TypeScript, Vite
- Redux Toolkit (global state) + TanStack Query (server state/caching)
- Tailwind CSS + shadcn/ui (pick ONE component library, not MUI-and-Ant-and-shadcn simultaneously) for consistent, highly-customized components
- **Charting — maximum two libraries, not five:**
  1. **TradingView Lightweight Charts** for all financial/price charts (candlestick, area, line, volume, overlays, drawing tools)
  2. **Apache ECharts** for everything else (heatmaps, treemaps, correlation matrices, radar, Sankey, 3D surface for parameter optimization)
  - Do not also add klinecharts, Recharts, Victory, or D3 — ECharts covers those use cases and keeps the bundle and visual language consistent.
- Framer Motion (animations), React Grid Layout (customizable dashboard grid)
- i18next (Persian/English), vite-plugin-pwa
- **jalaali-js** (or equivalent) for Jalali/Gregorian calendar conversion — see §6

**Shared:**
- Docker + docker-compose for full-stack local orchestration
- GitHub Actions CI/CD (lint, test, build)

### 3.2 Core API Endpoints (versioned `/api/v1/`)

```
GET  /commodities                          - list all commodities + metadata
GET  /commodities/{id}                     - single commodity detail
GET  /commodities/{id}/prices              - historical OHLCV (query: start, end, interval, instrument_type)
GET  /commodities/{id}/indicators          - technical indicator values
GET  /commodities/{id}/seasonality         - seasonal indices (Jalali-month aware)
GET  /commodities/{id}/forecasts           - model forecasts + confidence intervals (query: model, horizon)
GET  /commodities/{id}/signals             - current signals + confidence scores + disclaimer
POST /commodities/{id}/backtest            - run backtest with given strategy/params
GET  /commodities/{id}/backtest/{run_id}   - retrieve stored backtest result
GET  /commodities/{id}/risk                - position sizing, VaR/CVaR, scenario results
GET  /commodities/{id}/news                - news + sentiment feed
GET  /correlations                         - cross-commodity + macro correlation matrix (query: window)
GET  /portfolio/analysis                   - portfolio risk analytics (POST positions)
GET  /alerts / POST /alerts / DELETE /alerts/{id}
POST /auth/register /auth/login /auth/refresh
GET  /data-health                          - data freshness/quality dashboard feed
WS   /ws/prices?symbols=...                - real-time price stream
WS   /ws/alerts                            - real-time alert push
```

Every endpoint: consistent error envelope (`{error: {code, message}}`), proper HTTP status codes, rate limiting, and OpenAPI-documented request/response models.

### 3.3 Data Sources — corrected for real-world availability

The original specs listed sources that are unreliable or no longer free. Use this corrected list, and **degrade gracefully** (mark data `unavailable`/`estimated` in the DB rather than crashing) when a source is unreachable:

| Category | Use | Do NOT rely on as primary |
|---|---|---|
| IME prices | Scrape official IME site listings (respecting robots.txt) or any published data feed | — |
| Global benchmark prices | Tridge, ITC Trade Map, LME (metals), public CBOT delayed data | Paid Platts feeds (mention as "optional, requires paid key") |
| FX rates | Central Bank of Iran published rates, tgju.org (public site scrape) | — |
| Weather | Open-Meteo (free, no key needed), NOAA | meteostat if rate-limited |
| Satellite NDVI | Mark as **optional/Phase-4-stretch** — Google Earth Engine requires a registered cloud project and is not "plug and play"; do not block core delivery on it |
| News | RSS feeds (feedparser), public news site scraping | — |
| Social sentiment | **Do not use `tweepy`/Twitter API** — it is no longer free. Substitute: public Telegram channel scraping (via `telethon`, read-only, clearly marked `unverified` source) or drop social sentiment to news-only sentiment for Phase 1–3, revisit later | Twitter/X API |
| Informal inventory chatter | Public Telegram channels, marked `estimated` | — |

Collection frequency: prices every 5 min (liquid instruments) / daily (illiquid), fundamentals daily (weather) to monthly (production/export), news every 15–60 min.

Data validation: missing-value checks, outlier detection (z-score/IQR), cross-source consistency checks, all logged to a `data_quality_log` table feeding the `/data-health` endpoint.

---

## 4. Database Schema (corrected — EAV replaced)

The original EAV ("entity-attribute-value") design for fundamentals is an anti-pattern here: it produces slow, hard-to-index joins at scale. Use this instead:

- `commodities` — id, name, symbol, category (metal/agri/petrochem/mineral), unit, margin_rate, jalali_season_profile, metadata (`JSONB` for the genuinely variable, rarely-queried attributes only — e.g., saffron quality grade, steel thickness — not for core queryable fields)
- `price_data` — TimescaleDB hypertable: commodity_id, timestamp, open, high, low, close, volume, open_interest, instrument_type, source. Indexed on `(commodity_id, timestamp)`.
- `fundamental_data_<category>` — one properly-typed table per commodity category (e.g., `fundamental_data_agri` with production_ton, acreage_ha, rainfall_mm; `fundamental_data_metal` with inventory_ton, smelter_output) rather than a single generic EAV table. Use `JSONB` only for a small "extra" column, not the whole schema.
- `indicators` — precomputed time-series indicator values (hypertable)
- `forecasts` — model_name, horizon, generated_at, predicted_value, lower_ci, upper_ci, commodity_id
- `signals` — timestamp, commodity_id, strategy, signal_type, confidence, reason, disclaimer_shown
- `backtest_results` — run_id, commodity_id, strategy, params (JSONB), metrics (JSONB), equity_curve (JSONB or linked hypertable), created_at
- `news` — title, content, source, url, timestamp, sentiment_score, commodity_tags (array)
- `users`, `roles_permissions`, `alerts`, `alert_history`
- `data_quality_log` — source, commodity_id, check_type, status, detail, timestamp
- `audit_logs` — for admin actions

All monetary values stored with an explicit currency column (`IRR` rial as canonical storage unit — see §6.2), never assume Toman/Rial implicitly.

---

## 5. Backend Functional Modules (merged from multi-commodity + saffron specs)

1. **Ingestion layer** — per-source adapters (one Python module per source), each implementing a common `fetch() -> DataFrame` interface so a new source can be added without touching the pipeline core.
2. **Preprocessing** — cleaning, missing-value imputation, outlier flagging, timezone alignment, continuous-futures construction (volume/open-interest roll).
3. **Feature engineering** — technical indicators (SMA, EMA, WMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, OBV, Ichimoku, Parabolic SAR, VWAP), seasonality features **computed on the Jalali calendar** (see §6.1), fundamental feature normalization, sentiment aggregation (NLP: VADER or a multilingual transformer for Persian text), cross-commodity spreads/ratios, macro features (USD/IRR, inflation).
4. **Seasonality engine** — ratio-to-moving-average seasonal index per Jalali month, ANOVA significance test, year-over-year comparison.
5. **Correlation engine** — rolling correlation matrix across commodities + macro assets, queryable by window length.
6. **Forecasting** — SARIMA (`pmdarima` auto-ARIMA) for monthly averages, GARCH (`arch`) for volatility, Random Forest/XGBoost/LightGBM for direction + level prediction, optional LSTM (`tensorflow`) as a stretch goal, ensemble combining models weighted by backtested performance, output with 80%/95% confidence intervals.
7. **Signal engine** — per-strategy signals (seasonal, momentum, mean-reversion, ML-direction-probability) combined via a configurable weighted-vote into Strong Buy/Buy/Neutral/Sell/Strong Sell, each with a confidence score and human-readable reason — **and the mandatory disclaimer (§1)**.
8. **Backtesting engine** — any strategy, any commodity; includes commission, slippage, per-commodity margin requirements; computes total/annualized return, Sharpe, Sortino, max drawdown, win rate, profit factor, Calmar ratio; supports walk-forward analysis, grid-search parameter optimization, Monte Carlo permutation testing.
9. **Risk management** — position sizing (Kelly, fixed-fractional, volatility targeting), portfolio VaR/CVaR/correlation risk/efficient frontier, Monte Carlo scenario simulation (e.g., "20% global price drop", "30% IRR devaluation"), per-commodity stress testing.
10. **Alerting** — price/indicator/signal/news-keyword triggers, evaluated via scheduled Celery tasks or real-time WebSocket, delivered via email/Telegram bot/in-app.
11. **Scheduling** — Celery Beat: price collection (5 min / daily by liquidity), daily indicator/forecast/signal computation, weekly seasonality/correlation refresh, hourly news sentiment.
12. **Auth & admin** — JWT + refresh tokens, role-based access, audit logging, an admin surface to trigger manual re-collection and view logs.
13. **Mock data generator** — deterministic-seed synthetic data (prices, fundamentals, news, precomputed analytics) for **every** commodity in the registry, so the whole system runs and demos fully without any live source configured.

---

## 6. Iran-Market-Specific Requirements (missing from all three original specs — now mandatory)

### 6.1 Jalali (Shamsi) Calendar
- All seasonality computation (§5.4), the economic calendar, and date pickers in the UI must operate on the **Jalali calendar** as the primary display/analysis calendar, since Iranian agricultural cycles (e.g., saffron harvest in Mehr–Aban) are defined by Jalali months, not Gregorian ones. Store timestamps in UTC internally; convert for display/analysis using `jalaali-js` (frontend) / `jdatetime` or `khayyam` (Python backend).
- Provide a Gregorian/Jalali toggle in date-range pickers.

### 6.2 Currency
- Canonical storage currency: **Rial (IRR)**. The UI must let the user toggle Rial/Toman display (1 Toman = 10 Rial) — this is a near-universal Iranian UX expectation and was absent from all three source specs.

### 6.3 Chart directionality
- Even though the overall UI is RTL (Persian), **financial charts (candlestick/line/volume) must render left-to-right** with time increasing rightward — this is the global convention traders expect, and flipping it would confuse users. Explicitly set the charting components to LTR internally regardless of the page's RTL context.

### 6.4 Regulatory framing
- Reflect §1's disclaimer and compliance flag prominently wherever signals/forecasts appear in the UI, not buried in fine print.

---

## 7. Frontend Modules & Pages (merged from dashboard spec + saffron spec, deduplicated)

### 7.1 Global Overview
Live price ticker (scrolling, color-coded), customizable widget grid (drag/drop via React Grid Layout), key metric cards (price, change, volume, open interest, volatility, RSI, sparkline), market heatmap (ECharts treemap), top movers list, news/sentiment feed, Jalali-aware economic calendar.

### 7.2 Commodity Explorer
Product catalogue cards (icon, price, mini chart) filterable by category/exchange/tag, side-by-side comparison table, interactive correlation-matrix heatmap.

### 7.3 Dedicated Commodity Page (fully built for Saffron in Phase 1–3; pattern reused for others in Phase 4)
- **Header:** name, price, change, high/low, mini candlestick.
- **Price & Charts tab:** multi-timeframe candlestick/line/area/Heikin-Ashi (TradingView Lightweight Charts), drawing tools (trendline, Fibonacci, S/R, annotations), indicator overlays + sub-panel indicators, order book/depth chart where available, time & sales tape.
- **Seasonality tab:** Jalali-month seasonal index bar chart with confidence bands, multi-year overlay, daily-return heatmap by month/year, best/worst-month stats table.
- **Forecasts & Signals tab:** ML forecast chart with confidence bands, model/horizon selectors, signal dashboard with per-strategy confidence scores, reasoning panel, **disclaimer banner**.
- **Backtesting tab:** strategy selector, parameter panel, equity curve, drawdown chart, monthly-returns heatmap, metrics table, trade list overlaid on price chart.
- **Risk & Portfolio tab:** position-size calculator, Monte Carlo price-path simulation, portfolio risk-contribution pie chart.
- **News & Social tab:** sentiment gauge, word cloud, tagged headlines.

### 7.4 Advanced Analytics Center (Phase 5)
Multi-commodity synchronized view (up to 5), spread analysis with z-score charts, option chain analyzer (IV + Greeks + payoff diagrams, if options data exists), volume-at-price market profile, seasonality opportunity scanner across all commodities, ML model explorer (feature importance, performance, prediction intervals).

### 7.5 Backtesting Studio (Phase 5)
Visual/no-code strategy builder, grid-search parameter optimization visualized as heatmap/3D surface (ECharts), walk-forward analysis, Monte Carlo permutation testing (luck-vs-skill assessment).

### 7.6 Alerts & Notifications
Alert manager (price/indicator/signal/news-keyword triggers), in-app + sound + optional email/Telegram notifications, alert history log.

### 7.7 User Workspace
Saved custom dashboard layouts, multiple watchlists, dark/light theme, Persian/English language, Rial/Toman toggle, Gregorian/Jalali toggle, keyboard shortcuts, chart export (PNG/SVG), data export (CSV/Excel).

### 7.8 Data Explorer
Raw data tables (filter/sort), interactive Swagger UI link, data-health dashboard (freshness, missing data, quality scores from `data_quality_log`).

### 7.9 Mock API Layer
A mock API/service module **generated from the shared `openapi.yaml`** (§3) that simulates both REST and WebSocket, with deterministic realistic data for all commodities, so the frontend runs standalone before the backend is wired up.

### 7.10 Mobile & Performance
Fully responsive with bottom nav + swipe gestures on mobile; lazy loading and route-level code splitting; virtualization for large tables; Web Workers for heavy client-side computation (Monte Carlo, correlation matrices) if needed; IndexedDB for local caching; PWA installable.

### 7.11 Design Guidelines
Dark theme default (neon cyan/magenta/green accents for data highlights) with a clean professional light theme option; modern sans-serif (e.g., Inter/Vazirmatn for Persian) + monospace for numbers; consistent icon set (Lucide React); subtle hover/transition animations; dense-but-organized card layout; WCAG AA contrast, full keyboard navigation, aria labels.

**Objective quality bar (replacing vague "best in Iran" language):** Lighthouse performance score ≥ 90, initial route load < 2s on a throttled 4G profile, WCAG 2.1 AA compliance, zero console errors in production build, 80%+ unit/integration test coverage on shared logic.

---

## 8. Multi-Commodity Extension Pattern (Phase 4)

Adding a new commodity must require **only**:
1. A new row in the `commodities` registry table (name, symbol, category, unit, margin_rate).
2. A category-appropriate row in the relevant `fundamental_data_<category>` table (create the table once per category, not per commodity).
3. If the commodity needs a source not yet integrated, one new adapter module implementing the common `fetch()` interface (§5.1) — no changes to the pipeline core.
4. No frontend code changes: the Commodity Explorer, comparison table, and Dedicated Commodity Page must all be data-driven off the registry, not hardcoded per commodity.

Demonstrate this pattern in Phase 4 with: steel billet (metals), copper cathode (metals), polyethylene (petrochemicals), cement (minerals) — in addition to the saffron pilot.

---

## 9. Non-Functional Requirements

- API p95 response time < 200ms for hot-path market endpoints (cached).
- Support ≥ 100,000 concurrent users via horizontal scaling (stateless API pods behind a load balancer, Redis for shared cache/session).
- 99.9% uptime target with automated failover.
- TimescaleDB compression + `(commodity_id, timestamp)` indexing for time-series scale.
- Off-peak scheduling for ML training jobs.
- OWASP Top 10 mitigations, TLS 1.3 in transit, encrypted secrets via environment variables (never committed), rate limiting, WAF-friendly headers.

---

## 10. Deployment & Documentation Deliverables

- `docker-compose.yml` orchestrating: backend, PostgreSQL+TimescaleDB, Redis, Celery worker, Celery beat, frontend (dev + prod build stages).
- `openapi.yaml` (the shared contract from §3) checked into the repo root.
- Alembic migration scripts.
- Mock data generator script (deterministic seed) covering all commodities and all modules (prices, fundamentals, news, precomputed analytics).
- `README.md`: setup instructions, environment variables, data-source configuration, how to run each phase, how to add a new commodity (§8).
- Auto-generated Swagger/OpenAPI docs at `/docs`.
- GitHub Actions CI/CD: lint, test, build, (optional) deploy.
- User guide explaining dashboard usage.
- Prometheus + Grafana monitoring config (optional, Phase 5 stretch).

---

## 11. Constraints

- Free/open-source libraries only (flag any paid dependency — e.g., Platts, GEE cloud costs — as clearly optional/stretch, never load-bearing for core delivery).
- Backend fully decoupled from frontend; all communication via the shared OpenAPI contract (REST) and documented WebSocket events.
- Code must be modular, PEP8 (Python) / ESLint+Prettier (TypeScript) compliant, and well-commented.
- No feature listed in §5 or §7 should be silently dropped — if something is infeasible in a given phase, say so explicitly in the code/README rather than omitting it without note.

---

## 12. Execution Instruction

Work phase by phase per §2. For each phase:
1. Restate what you're building and confirm it maps to the relevant sections above.
2. Produce the `openapi.yaml` delta for that phase first (if new endpoints are introduced).
3. Produce backend code, then frontend code, both against that contract.
4. Note explicitly which items from this spec are deferred to a later phase and why.
5. Stop and wait for confirmation before starting the next phase.
