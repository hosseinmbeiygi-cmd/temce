# Step 2: Module Classification and Reading Plan

**Project root:** `C:/Users/Iran/Desktop/temce`
**Input:** `report/01-structure.md`
**Status:** IN PROGRESS → must stop for approval after this file

---

## 1. Actual modules in the code (what exists)

The project is a large multi-service Python platform for the Iranian capital markets.
Below are the real modules as they appear in the filesystem. Names are grouped by domain.
Some folders are duplicates/snapshots and are noted as such.

> **Canonical vs duplicate:** `code_dump/`, `.kilo/`, `_FRONTEND_BACKEND_COPY/` are not
> source of truth. Where the same module appears in `services/`, `apps/`, `core/`,
> `brsapi/`, `src/`, `ingestion/`, `backtesting/`, that tree is canonical.

### A. Platform core / infrastructure (Tier 1 — foundational, high blast radius)

| Module | Path | Purpose (one line) | Est. lines | Tier |
|---|---|---|---|---|
| Core config | `core/config/` | App settings, env loading, feature flags | — | 1 |
| Core database | `core/database.py`, `core/db_utils.py`, `core/dbcompat.py` | Async SQLAlchemy engine, sessions, compat | — | 1 |
| Core logging/observability | `core/logging/`, `core/observability_sentry.py` | structlog init, Sentry, OTel | — | 1 |
| Core indicators | `core/indicators.py` | Indicator calculation primitives | — | 1 |
| Core cache | `core/cache.py`, `core/cache_manager.py` | Caching layer | — | 1 |
| Core events / event bus | `core/event_bus.py`, `core/events.py` | Internal event system | — | 1 |
| Core resilience | `core/circuit_breaker.py`, `core/retry/`, `core/rate_limit/`, `core/resilience/` | Retry, backoff, circuit breaker, rate limiting | — | 1 |
| Core concurrency | `core/concurrency/` | Thread/async primitives | — | 1 |
| Core security | `core/security/` | Auth/JWT/crypto helpers | — | 1 |
| Core time | `core/time/` | Calendar, timezone, Jalali/Gregorian | — | 1 |
| Core validation | `core/validation/`, `core/exceptions/` | Input validation, error types | — | 1 |
| Core enums/constants | `core/enums/`, `core/constants/` | Shared enumerations | — | 1 |
| Core IDs | `core/ids/` | Identifier schemes | — | 1 |
| Core typing | `core/typing/` | Shared type aliases | — | 1 |
| Core utils | `core/utils.py`, `core/pagination.py`, `core/context.py` | Helpers | — | 1 |
| Core JSON | `core/json/` | JSON helpers | — | 1 |
| Core feature_flags | `core/feature_flags/` | Feature flag system | — | 1 |
| Core dependency_injection | `core/dependency_injection/` | DI wiring | — | 1 |
| Core health | `core/health/` | Health checks | — | 1 |
| Core paths | `core/paths.py` | Path resolution | — | 1 |

### B. API layer / HTTP surface (Tier 1 for data integrity, Tier 2 for UX)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Main API app | `apps/api/app.py` (1,204), `apps/api/router.py` | FastAPI app, router wiring, middleware | ~1,500+ | 1 |
| API endpoints (large) | `apps/api/endpoints/` | One file per domain endpoint | many | 1/2 |
| — `brsapi.py` | `apps/api/endpoints/brsapi.py` (3,344) | BRSAPI ingestion endpoint (largest) | 3,344 | 1 |
| — `funds.py` | `apps/api/endpoints/funds.py` (1,832) | Fund endpoints | 1,832 | 1 |
| — `backtests.py` | `apps/api/endpoints/backtests.py` (1,310) | Backtest endpoints | 1,310 | 1 |
| — others | `alerts.py`, `codal.py`, `gold.py`, `screener.py`, `signals.py`, `quotes.py`, `symbols.py`, `watchlist.py`, `trades.py`, `market.py`, `news.py`, `options.py`, etc. | Domain endpoints | each <1k (mostly) | 1/2 |
| API middleware | `apps/api/middleware.py` | Request middleware | — | 1 |
| Admin app | `apps/admin/app.py`, `apps/admin/router.py` | Admin dashboard API | — | 2 |
| Gateway | `apps/gateway/app.py` | API gateway (if used) | — | 2 |
| CLI | `apps/cli/` | Command-line tooling | — | 3 |

### C. Market data ingestion / BRSAPI (Tier 1 — data correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| BRSAPI client | `brsapi/client.py` | HTTP client for BRSAPI (TSE/Fara) | — | 1 |
| BRSAPI services/sync | `brsapi/services/sync_service.py` (1,812) | Sync orchestration | 1,812 | 1 |
| BRSAPI jobs/registry | `brsapi/jobs/registry.py` (1,768) | Job registry for ingestion | 1,768 | 1 |
| BRSAPI config/budget/rate-limit | `brsapi/config.py`, `brsapi/budget.py`, `brsapi/rate_limiter.py`, `brsapi/readiness.py` | Budget, readiness, rate-limiting | — | 1 |
| BRSAPI models/parsers/repos | `brsapi/models/`, `brsapi/parsers/`, `brsapi/repositories/` | Data models, parsing, repos | — | 1 |
| BRSAPI pipelines/json_sink | `brsapi/pipelines/`, `brsapi/json_sink.py` | Ingestion pipelines | — | 1 |
| Ingestion worker | `jobs/ingestion_worker.py`, `apps/ingestion_worker/` | Ingestion worker entrypoint | — | 1 |
| Ingestion service (domain) | `services/ingestion_service.py` | High-level ingestion service | — | 1 |
| Ingestion (platform) | `ingestion/` | Platform ingestion layer (sources, parsers, storage, validation, retry) | large | 1 |
| Ingestion sources | `ingestion/sources/`, `ingestion/library_sources/` | Data source adapters | — | 1 |
| Ingestion scanners | `ingestion/scanners/`, `ingestion/symbol_scanner.py` | Symbol scanning | — | 2 |
| Ingestion market_data | `ingestion/market_data.py` | Market data ingestion | — | 1 |
| Ingestion fx/gold | `ingestion/fx/`, `ingestion/gold/` | FX and gold ingestion | — | 2 |
| Ingestion validation | `ingestion/raw_validation.py`, `ingestion/validation.py` | Raw data validation | — | 1 |
| Ingestion storage/layered_store | `ingestion/storage/`, `ingestion/layered_store.py` | Storage abstraction | — | 1 |

### D. Quotes / market data services (Tier 1 — pricing correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Quote service | `services/quote_service.py`, `services/quote_import_service.py` | Quote CRUD/import | — | 1 |
| Real-time quote | `services/realtime_quote_service.py`, `services/realtime_service.py` | Real-time quotes | — | 1 |
| Market service | `services/market_service.py`, `services/market_cache.py` | Market data service/cache | — | 1 |
| Historical data | `services/historical_data_service.py`, `services/history_backfill_service.py` | History backfill | — | 1 |
| Symbol service | `services/symbol_service.py`, `services/symbol_catalog.py`, `services/symbol_detail_service.py` | Symbol info | — | 2 |
| Data layer / data mesh | `services/data_layer.py`, `services/data_mesh/` | Data access abstraction | — | 1 |
| Materialized views | `services/materialized_view_service.py` | MV management | — | 2 |
| TSETMC client | `services/tsetmc_client.py` | TSETMC data client | — | 1 |
| Market watch helper | `services/market_watch_helper.py` | Watch helpers | — | 2 |

### E. Indicators / technical analysis (Tier 1 — computation correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Core indicators | `core/indicators.py` | Indicator primitives | — | 1 |
| Indicators library | `src/indicators/` (advanced.py, general.py, scoring.py, specs.py, stocks.py, trend_momentum.py) | Indicator implementations | — | 1 |
| Indicator precompute service | `services/indicator_precompute_service.py` | Precompute pipeline | — | 1 |
| Technical engine | `services/stock_technical_engine.py` | Technical analysis engine | — | 1 |
| Stock tape engine | `services/stock_tape_engine.py` | Tape reading | — | 1 |
| Signal feature pipeline | `services/signal_feature_pipeline.py` | Feature pipeline for signals | — | 1 |

### F. Signals / signal engine (Tier 1 — monetary impact)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Multi-market signal engine | `services/multi_market_signal_engine.py` (1,539) | Multi-market signals | 1,539 | 1 |
| Quant signal orchestrator | `services/quant_signal_orchestrator.py` (2,049) | Signal orchestration | 2,049 | 1 |
| Signal service | `services/signal_service.py` | Signal CRUD/serve | — | 1 |
| Signal store | `services/signal_store.py` | Signal persistence | — | 1 |
| Signal composer | `services/signal_composer.py` | Compose signals | — | 1 |
| Signal decision engine | `services/signal_decision_engine.py` | Decision logic | — | 1 |
| Signal voting system | `services/signal_voting_system.py` | Voting/ensemble | — | 1 |
| Signal backtest engine | `services/signal_backtest_engine.py` | Backtest signals | — | 1 |
| Signal circuit breaker | `services/signal_circuit_breaker.py` | Circuit break signals | — | 1 |
| Signal performance tracker | `services/signal_performance_tracker.py` | Track performance | — | 2 |
| Signal accuracy tracker | `services/signal_accuracy_tracker.py` | Accuracy metrics | — | 2 |
| Signal explain | `services/signal_explain.py` | Explainability | — | 2 |
| Stock signal engine | `services/stock_signal_engine.py` | Stock-level signals | — | 1 |
| IME signal | `services/ime_signal_adapter.py`, `services/ime_signal_factory.py` | IME signals | — | 1 |
| IME slippage simulator | `services/ime_slippage_simulator.py` | Slippage sim | — | 1 |
| Pre-buy | `services/pre_buy_service.py`, `services/pre_buy_evidence.py`, `services/pre_buy_instrument.py` | Pre-buy checks | — | 1 |

### G. Smart money / microstructure (Tier 1 — monetary impact)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Smart money service | `services/smart_money_service.py` | Smart money analytics | — | 1 |
| Smart money layers | `services/smart_money/` (layer1–layer8 + advanced_analytics, confidence, config_loader, data_quality, feature_store, normalizer, parallel_engine, phase_alerts, resilience, scoring_engine, stats) | Orderbook/microstructure layers | — | 1 |
| Orderbook service | `services/orderbook_service.py` | Orderbook | — | 1 |
| Block trade detector | `services/block_trade_detector.py` | Block trades | — | 1 |
| Manipulation detector | `services/manipulation_detector.py` | Manipulation detection | — | 1 |
| Hidden accumulation | `services/hidden_accumulation.py` | Hidden accumulation | — | 1 |
| Queue analysis | `services/queue_analysis.py`, `services/queue_analysis_service.py` | Queue analysis | — | 2 |
| Fake queue detector | `services/fake_queue_detector.py` | Fake queue detection | — | 2 |

### H. Backtesting (Tier 1 — methodology correctness, monetary impact)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Backtesting framework | `services/backtest_framework.py`, `services/backtest_service.py` | Backtest service | — | 1 |
| Backtesting library | `backtesting/` (large tree: engine, execution, portfolio, risk, metrics, strategies, signals, validation, etc.) | Full backtesting system | large | 1 |
| Backtest worker | `apps/backtest_worker/`, `jobs/backtest_jobs.py` | Backtest job execution | — | 1 |
| Backtest costs | `backtesting/costs/`, `services/backtest/cost_model.py` | Cost/slippage/fee models | — | 1 |
| Walk-forward validator | `services/walk_forward_validator.py` | Walk-forward validation | — | 1 |
| Event backtest | `services/event_backtest.py` | Event-driven backtest | — | 1 |
| Options backtest | `services/options_backtest_service.py` | Options backtest | — | 1 |
| Backtest data | `backtest_data_all/` | Backtest data (excluded — data) | data | n/a |

### I. Options (Tier 1 — pricing/Greeks correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Options service | `services/options_service.py` (1,153) | Options CRUD/serve | 1,153 | 1 |
| Options analytics | `services/options_analytics.py` | Analytics | — | 1 |
| Options signals | `services/options_signals.py` | Signals | — | 1 |
| Options ML | `services/options_ml_service.py` | ML on options | — | 1 |
| Options reference | `services/options_reference.py` | Reference data | — | 2 |
| Black76 pricer (gold desk) | `src/gold_desk/black76.py` | Options pricing | — | 1 |
| Options signals (gold desk) | `src/gold_desk/` (pricer.py, scorer.py, etc.) | Gold desk options | — | 1 |

### J. Portfolio / risk / trade execution (Tier 1 — monetary impact)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Portfolio service | `services/portfolio_service.py` | Portfolio management | — | 1 |
| Trade service | `services/trade_service.py` | Trade CRUD | — | 1 |
| Risk engine v1 | `services/risk_engine_v1.py` | Risk engine | — | 1 |
| Risk metrics | `services/risk_metrics.py` | Risk metrics | — | 1 |
| Risk-adjusted filter | `services/risk_adjusted_filter.py` | Filter by risk | — | 2 |
| Live risk monitor | `services/live_risk_monitor.py` | Live risk monitoring | — | 1 |
| Kill switch | `services/kill_switch.py` | Kill switch | — | 1 |
| Paper trading service | `services/paper_trading_service.py` | Paper trading | — | 1 |
| Broker (paper) | `services/broker/paper_broker.py` | Paper broker impl | — | 1 |
| Real return calculator | `services/real_return_calculator.py` | Return calc | — | 1 |
| Corporate actions | `services/corporate_action_service.py` | Splits/dividends | — | 1 |
| Recommendation service | `services/recommendation_service.py` | Recommendations | — | 2 |

### K. Alerts (Tier 1 — missed alert / alert storm risk)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Alert service | `services/alert_service.py` (21 commits — frequently changed) | Alert orchestration | — | 1 |
| Alert engine (gold desk) | `src/gold_desk/alert_engine.py` | Alert logic | — | 1 |
| Symbol alerts endpoint | `apps/api/endpoints/symbol_alerts.py` | Alert API | — | 1 |
| Alert jobs | `jobs/definitions/alert_jobs.py` | Alert scheduling | — | 1 |

### L. Codal (Iranian disclosure system) (Tier 2 — data extraction correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Codal service | `services/codal_service.py` (33) | Codal orchestration | 33 | 2 |
| Codal financial service | `services/codal_financial_service.py` (280) | Financial statement import | 280 | 2 |
| Codal download service | `services/codal_download_service.py` (314) | Download | 314 | 2 |
| Codal import service | `services/codal_import_service.py` | Import | — | 2 |
| Codal accounting service | `services/codal_accounting_service.py` | Accounting | — | 2 |
| Codal attachment service | `services/codal_attachment_service.py` | Attachments | — | 2 |
| Codal analysis | `services/codal_analysis/` (large: analysis_engine, forensic, nlp_analyzer, report_generator, semantic_mapper, scoring, validation, etc.) | Codal analysis/NLP/audit | large | 2 |
| Codal endpoint | `apps/api/endpoints/codal.py` (21 commits — frequently changed) | Codal API | — | 2 |
| Codal sync job | `jobs/definitions/codal_jobs.py` | Codal sync | — | 2 |
| Codal repository | `repositories/codal_repository.py` | Codal repo | — | 2 |
| Codal in ingestion | `ingestion/` (codal sources/parsers) | Codal ingestion | — | 2 |
| Codal in domain | `domain/codal/` | Codal domain models | — | 2 |

### M. Funds / ETF / FOF (Tier 2 — data correctness, some Tier 1 if trading)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Fund service | `services/fund_service.py` | Fund CRUD | — | 2 |
| Funds facade | `services/funds_facade.py`, `services/funds_facade/base.py` | Fund facade | — | 2 |
| Fund API adapter | `services/fund_api_adapter.py` | External fund API | — | 2 |
| Fund NAV engine | `services/fund_nav_engine.py` | NAV calculation | — | 1 |
| Fund NAV reconciliation | `services/fund_nav_reconciliation.py` | NAV reconciliation | — | 1 |
| Fund scoring | `services/fund_scoring.py` | Scoring | — | 2 |
| Fund discovery | `services/fund_discovery.py` | Discovery | — | 2 |
| Fund compliance | `services/fund_compliance.py`, `services/fund_circuit_breaker.py` | Compliance | — | 2 |
| Fund tax | `services/fund_tax.py` | Tax | — | 2 |
| Fund sync | `services/fund_sync_service.py`, `services/fund_read_through.py`, `services/fund_identity.py`, `services/fund_ledger.py`, `services/fund_fof.py`, `services/fund_explainer.py`, `services/fund_quant_engine.py`, `services/fund_class_nav.py` | Fund sub-modules | — | 2 |
| Funds app | `apps/funds/` (large tree: adapters, api, auth, db, metrics, models, peers, resilience, router, schemas, scoring, services) | Funds subsystem | large | 2 |
| Funds endpoints | `apps/api/endpoints/funds.py` (1,832), `apps/api/endpoints/funds_v2.py`, `funds_compliance.py`, `funds_ledger.py`, `funds_nav.py`, `funds_regulator.py` | Fund HTTP API | 1,832+ | 2 |
| Fund jobs | `jobs/definitions/fund_jobs.py`, `jobs/definitions/fund_nav_jobs.py` | Fund scheduling | — | 2 |

### N. News / sentiment (Tier 2 — data quality)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| News service | `services/news_service.py` | News CRUD | — | 2 |
| News ingestion | `services/news_ingestion.py` | News ingestion | — | 2 |
| News deduplication | `services/news_dedup.py` | Dedup | — | 2 |
| News filter | `services/news_filter.py` | Filtering | — | 2 |
| News sentiment pipeline | `services/news_sentiment_pipeline.py` | Sentiment | — | 2 |
| News source health | `services/news_source_health.py` | Source health | — | 2 |
| News tag/symbol mapper | `services/news_tag_symbol_mapper.py` | Symbol mapping | — | 2 |
| News dual write | `services/news_dual_write.py` | Dual write | — | 2 |
| News read canary | `services/news_read_canary.py` | Read canary | — | 2 |
| Stocks news sentiment engine | `services/stock_news_sentiment_engine.py` | News sentiment for stocks | — | 2 |
| Persian sentiment service | `services/persian_sentiment_service.py` | Persian NLP sentiment | — | 2 |
| News repository | `repositories/news_repository.py` (24 commits) | News repo | — | 2 |
| News endpoint | `apps/api/endpoints/news.py` (30 commits — most-changed endpoint) | News API | — | 2 |
| Sentiment endpoint | `apps/api/endpoints/sentiment.py` | Sentiment API | — | 2 |
| Sentiment in ingestion | `ingestion/` (news sources/parsers) | News ingestion | — | 2 |
| News in domain | `domain/news/` | News domain models | — | 2 |

### O. ML / forecasting / training (Tier 1 — leakage/overfitting risk)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| ML lifecycle service | `services/ml_lifecycle_service.py` | Model lifecycle | — | 1 |
| Training service | `services/training_service.py` | Training | — | 1 |
| Global training service | `services/global_training_service.py` | Global training | — | 1 |
| Auto-retrain pipeline | `services/auto_retrain_pipeline.py` | Auto retraining | — | 1 |
| Inference service | `services/inference_service.py` | Inference | — | 1 |
| ML signal connector | `services/ml_signal_connector.py` | Connect ML to signals | — | 1 |
| ML repository | `repositories/ml_repository.py` | ML artifact repo | — | 1 |
| Feature engine | `services/feature_engine.py` | Feature engineering | — | 1 |
| Confidence scorer | `services/confidence_scorer.py` | Confidence scoring | — | 1 |
| Probability calibrator | `services/probability_calibrator.py` | Calibration | — | 1 |
| Isotonic calibrator | `services/isotonic_calibrator.py` | Isotonic calibration | — | 1 |
| Calibration loop | `services/calibration_loop.py` | Calibration loop | — | 1 |
| Calibration bootstrap | `core/calibration_bootstrap.py` | Calibration bootstrap | — | 1 |
| Gap prediction | `services/gap_prediction.py` | Gap prediction | — | 2 |
| Iran fear & greed index | `services/iran_fear_greed_index.py` | Sentiment index | — | 2 |
| Forecast engine (src) | `src/forecast_engine/` (forecasting_service.py, redis_adapter.py, safe_forecast.py, symbol_registry.py) | Forecast engine | — | 1 |
| Forecasting (src) | `src/forecasting/` (service.py) | Forecasting | — | 1 |
| Forecast endpoint | `apps/api/endpoints/forecast.py`, `forecast_engine.py` | Forecast API | — | 1 |
| ML worker | `apps/ml_worker/` | ML worker | — | 1 |
| ML jobs | `jobs/definitions/ml_jobs.py` | ML scheduling | — | 1 |
| ML in domain | `domain/ml/` | ML domain models | — | 1 |
| ML schemas | `schemas/ml/` | ML schemas | — | 1 |
| ML artifacts (data) | `ml_artifacts/` | Model outputs (excluded — data) | data | n/a |

### P. Screener / screening (Tier 2 — signal quality; smart screener may be Tier 1)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Screener service | `services/screener_service.py` (1,181) | Screener orchestration | 1,181 | 2 |
| Smart screener v2 | `services/smart_screener_v2.py` | Smart screener | — | 1 |
| Screener 110 service | `services/screener110_service.py` | Program 110 screener | — | 1 |
| Screener AI report service | `services/screener_ai_report_service.py` | AI report | — | 2 |
| Screener endpoints | `apps/api/endpoints/screener.py`, `screener_v2.py`, `screener110.py`, `scanner.py`, `saved_filters.py` | Screener API | — | 2 |
| Screener jobs | `jobs/definitions/screener_jobs.py` | Screener scheduling | — | 2 |
| Screener in domain | `domain/screening/` | Screening domain | — | 2 |
| Screener in backtesting | `backtesting/signals/`, `backtesting/strategies/` | Screener-backed strategies | — | 1 |

### Q. USD / gold / silver / oil / commodities (Tier 2 — price correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Gold desk (src) | `src/gold_desk/` (large tree: api.py (1,374), backtest.py, backtest_real.py, backtest_runner.py, black76.py, bubbler.py, chat.py, constants.py, crypto.py, dca_planner.py, forecaster.py, hard_stops.py, hotpath.py, live_signals.py, macro_news.py, metrics.py, models.py, nav_checker.py, parity.py, pattern_detector.py, portfolio.py, pricer.py, push.py, schemas.py, scorer.py, secondary_source.py, signal_engine.py, snapshot_service.py, telegram_bot.py, ws_hub.py, alert_engine.py, antigravity/, api_token.py, auto_trade.py) | Gold/commodity desk | large | 1/2 |
| Gold service (services) | `services/gold/` | Gold service | — | 2 |
| Commodities (domain) | `domain/commodities/` | Commodity domain | — | 2 |
| Metals (domain) | `domain/metals/` | Metals domain | — | 2 |
| Energy (domain) | `domain/energy/` | Energy domain | — | 2 |
| FX (domain) | `domain/fx/`, `ingestion/fx/` | FX domain/ingestion | — | 2 |
| Gold endpoint | `apps/api/endpoints/gold.py`, `golddesk.py` | Gold API | — | 2 |
| Crypto | `services/` (crypto?), `crypto_data/`, `crypto_history/` (excluded) | Crypto | — | 2 |

### R. Program 110 (Tier 2 — logic correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Screener 110 service | `services/screener110_service.py` | Program 110 | — | 1/2 |
| Screener 110 endpoint | `apps/api/endpoints/screener110.py` | 110 API | — | 2 |
| Sum program (src) | `src/sum_program.py` | Program 110 logic | — | 2 |

### S. Chat / assistant / natural language (Tier 3 — UX; verify no live actions)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Unified assistant service | `services/unified_assistant_service.py` (2,010) | Unified assistant | 2,010 | 3 |
| Stock assistant service | `services/stock_assistant_service.py` (2,137) | Stock assistant | 2,137 | 3 |
| Chat service | `services/chat/` (chat_engine, dialog_manager, intent_classifier, entity_extractor, news_analyzer, news_fetcher, sentiment_analyzer, suggestion_engine, learning_engine, compound_splitter, comparison_engine, personalization) | Chat subsystem | large | 3 |
| Chat endpoint | `apps/api/endpoints/chat.py`, `apps/api/endpoints/assistant.py`, `stock_assistant.py` | Chat API | — | 3 |
| Assistant in domain | `domain/` (recommendations, signals) | Assistant domain | — | 3 |

### T. Decision engine / orchestration / jobs (Tier 1 — if it triggers actions; Tier 2 otherwise)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Decision engine app | `apps/decision_engine/app.py` | Decision engine | — | 1/2 |
| Decision engine domain | `domain/decision_engine_v5/` | Decision engine domain | — | 1/2 |
| Orchestration | `orchestration/` (large tree: backtest_flow, codal_flow, context, contracts, fund_flow, market_flow, news_flow, policies, recovery, runners, signal_flow, state_machine, steps, training_flow, types) | Workflow orchestration | large | 1/2 |
| Jobs registry | `jobs/registry.py`, `jobs/definitions/` (23+ job definition files), `jobs/worker.py` | Job system | — | 2 |
| Job service | `services/job_service.py` | Job CRUD | — | 2 |
| Sync master service | `services/sync_master_service.py` | Sync orchestration | — | 2 |
| Job endpoints | `apps/api/endpoints/jobs.py` | Job API | — | 2 |

### U. User / auth / RBAC (Tier 3 — security; verify auth correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| User service | `services/user_service.py` | User CRUD | — | 3 |
| Auth endpoint | `apps/api/endpoints/auth.py` | Auth API | — | 3 |
| RBAC (from git log) | git log mentions "fix(rbac)" | RBAC system | — | 3 |
| User repository | `repositories/user_repository.py` | User repo | — | 3 |

### V. Reporting / analytics / dashboards (Tier 3 — mostly read-only)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Analytics service | `services/analytics_service.py` | Analytics | — | 3 |
| Report service | `services/report_service.py` | Report generation | — | 3 |
| Analytics worker | `apps/analytics_worker/` | Analytics worker | — | 3 |
| Market dashboard endpoint | `apps/api/endpoints/market_dashboard.py` | Dashboard API | — | 3 |
| Reports endpoint | `apps/api/endpoints/reports.py` | Reports API | — | 3 |
| Comprehensive analysis endpoint | `apps/api/endpoints/comprehensive_analysis.py` | Analysis API | — | 3 |
| Analysis endpoint | `apps/api/endpoints/analysis.py` | Analysis API | — | 3 |
| Reports (schemas) | `schemas/reporting/` | Report schemas | — | 3 |
| Build symbol reports | `build_symbol_reports.py` (1,990) | Symbol report generation script | 1,990 | 3 |
| Diagnostics runner | `services/diagnostics_runner.py` | Diagnostics | — | 3 |

### W. Composition / strategy generation (Tier 2 — logic correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Strategy generator | `services/strategy_generator.py` | Strategy generation | — | 2 |
| Compose service | `services/compose_service.py` | Composition | — | 2 |
| Compose endpoint | `apps/api/endpoints/compose.py` | Compose API | — | 2 |
| Generated strategy repo | `repositories/generated_strategy_repository.py` | Strategy repo | — | 2 |
| Composer (backtesting) | `backtesting/composer/` | Backtest composer | — | 1 |

### X. Data import / instrumentation (Tier 2 — data correctness)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Instrument service | `services/instrument_service.py`, `services/instrument_import_service.py` | Instrument CRUD/import | — | 2 |
| Instrument repository | `repositories/instrument_repository.py` | Instrument repo | — | 2 |
| Instruments domain | `domain/instruments/` | Instrument domain | — | 2 |
| Data import endpoint | `apps/api/endpoints/data_import.py` | Data import API | — | 2 |
| Populate profiles | `services/populate_profiles_service.py` | Profile population | — | 3 |

### Y. Domain models (cross-cutting, Tier 1/2 depending on module)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Domain roots | `domain/` (alerts, analytics, audit, backtest, bonds, calendar, codal, commodities, common, decision_engine_v5, energy, funds, fx, indicators, indices, instruments, macro, market_data, markets, metals, ml, news, options, orderbook, portfolios, pricing_version, quotes, recommendations, screening, signals, trades, trading, watchlists) | Domain models & logic | large | varies |

### Z. Schema / contracts / events (cross-cutting)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Schemas | `schemas/` (admin, api, backtest, common, ml, providers, reporting) | Pydantic/DB schemas | — | 2 |
| Contracts | `contracts/` (events.md, events.py, exceptions.py, schemas.py) | Event contracts | — | 2 |

### AA. Bulk import / utility scripts (Tier 3)

| Module | Path | Purpose | Est. lines | Tier |
|---|---|---|---|---|
| Bulk importer | `bulk_importer/` | Bulk import tooling | — | 3 |
| CSV utils | `services/csv_utils.py` | CSV helpers | — | 3 |
| Scripts | `scripts/` | Ad-hoc scripts | — | 3 |
| Root scripts | `main.py`, `collector.py`, `build_symbol_reports.py`, `gen_all.py`, `mkpages.py`, `z.py`, `fix_test_syntax.py`, etc. | Various scripts | — | 3 |

---

## 2. Duplicate, orphaned, or dead modules

| Item | Observation | Action |
|---|---|---|
| `code_dump/` | Contains full copies of modules (e.g., `code_dump/01_signal_engine/multi_market_signal_engine.py`, `code_dump/02_orchestrator/quant_signal_orchestrator.py`, `code_dump/15_brsapi_endpoints/brsapi.py`) | Canonical source is `services/` / `apps/` / `brsapi/`. Treat `code_dump/` as snapshots; spot-check for drift, do not read as primary. |
| `.kilo/` | Git worktree clones — duplicate entire trees | Skip entirely. |
| `_FRONTEND_BACKEND_COPY/` | Duplicate backend copy | Skip entirely. |
| `codal_env/` | Codal Python virtualenv (vendor libs) | Skip; size noted. |
| `claw-code/`, `mimicode-go/` | Separate side projects (in .gitignore) | Skip. |
| `go/`, `go.cmd`, `go.ps1`, `start`, `stop`, `t.bin` | Go toolchain / shell helpers / binary | Skip (not Python application code). |
| `.agents/skills/*` | Downloaded skills (50) | Data only; Step 6 covers them. |
| `ml_artifacts/`, `history_data/`, `crypto_history/`, `backtest_data_all/`, `dump.rdb` | Data/model artifacts | Skip (data only, sizes noted). |
| `reports/` (pre-existing) | Pre-existing reports dir | Preserve; do not confuse with `report/` audit output. |

**Orphan / dead detection:** Not yet performed (requires import-graph or grep for consumers). Deferred to Step 3/4. Likely candidates to check:
- `services/funds_facade/base.py` — is it used?
- `core/fix_network.py` — purpose?
- `core/question_bank/` — used?
- `core/json/` — used?
- Root scripts like `z.py`, `fix_test_syntax.py`, `split_to_10.py`, `gen_all.py`, `mkpages.py` — run by CI or ad-hoc?

---

## 3. Reading plan

### Principles
- Tier 1 first (high-risk core: ingestion, financial calculations, indicators, backtesting, ML, alerts, portfolio/risk, order execution).
- Tier 2 next (screeners, Codal, options, USD/gold/silver/oil, Program 110).
- Tier 3 last (UI, symbols table, utilities, settings, chat/assistant).
- Batch size: 30–60 files per turn.
- Save each module card to `report/modules/<name>.md` immediately.
- Keep `report/PROGRESS.md` up to date.

### Batch plan (approximate; refine during reading)

#### Tier 1 batches (first pass)
| Batch | Focus | Estimated files | Notes |
|---|---|---|---|
| T1-1 | Core infrastructure: config, database, logging, observability, events, cache, resilience (retry/circuit-breaker/rate-limit), concurrency, security, time, validation, enums/constants, ids, typing, utils, pagination, context, feature_flags, dependency_injection, health, paths, json | ~30–40 files | Foundational; many small files. Read config + database + logging + resilience deeply. |
| T1-2 | Market data ingestion — BRSAPI: client, sync_service, budget, readiness, rate_limiter, registry, models, parsers, repositories, pipelines, json_sink; plus ingestion/ core (sources, storage, layered_store, market_data, raw_validation, validation, retry, worker) | ~40–60 files | Highest data-correctness risk. Read parsing + validation + sync deeply. |
| T1-3 | Quotes / market data services: quote_service, quote_import_service, realtime_quote_service, realtime_service, market_service, market_cache, historical_data_service, history_backfill_service, tsetmc_client, data_layer, data_mesh, materialized_view_service | ~30–40 files | Pricing correctness. |
| T1-4 | Indicators + technical engines: core/indicators.py, src/indicators/*, indicator_precompute_service, stock_technical_engine, stock_tape_engine, signal_feature_pipeline; plus domain/indicators/ | ~30–40 files | Computation correctness. |
| T1-5 | Signals — core: multi_market_signal_engine, quant_signal_orchestrator, signal_service, signal_store, signal_composer, signal_decision_engine, signal_voting_system, signal_backtest_engine, signal_circuit_breaker, stock_signal_engine, ime_signal_adapter/factory/slippage_simulator, pre_buy_service/evidence/instrument | ~40–60 files | Monetary impact. quant_signal_orchestrator (2,049) and multi_market_signal_engine (1,539) are large — read deeply. |
| T1-6 | Smart money / microstructure: smart_money_service, smart_money/* (layer1–8, advanced_analytics, confidence, config_loader, data_quality, feature_store, normalizer, parallel_engine, phase_alerts, resilience, scoring_engine, stats), orderbook_service, block_trade_detector, manipulation_detector, hidden_accumulation, queue_analysis, fake_queue_detector | ~40–60 files | Orderbook/microstructure correctness. |
| T1-7 | Backtesting — services layer: backtest_framework, backtest_service, walk_forward_validator, event_backtest, options_backtest_service, real_return_calculator, services/backtest/cost_model | ~20–30 files | Then continue to backtesting/ library in next batch. |
| T1-8 | Backtesting — library: backtesting/engine, execution, portfolio, risk, metrics, strategies, signals, validation, data, costs, slippage, orders, sizing, types, data_quality, observability, reporting, visualization, runtime/platform | ~50–60 files | Large tree; split if needed. Methodology correctness is critical. |
| T1-9 | Options: services/options_service, options_analytics, options_signals, options_ml_service, options_reference; src/gold_desk/black76.py, pricer.py, scorer.py; domain/options/ | ~20–30 files | Greeks/pricing model + IV solver. |
| T1-10 | Portfolio / risk / trade / kill switch / paper trading: portfolio_service, trade_service, risk_engine_v1, risk_metrics, live_risk_monitor, kill_switch, paper_trading_service, broker/paper_broker, corporate_action_service, recommendation_service; plus domain/portfolios/, domain/trades/, domain/trading/ | ~30–40 files | Monetary impact; verify no real-order automation. |
| T1-11 | Alerts: alert_service, src/gold_desk/alert_engine.py, symbol_alerts endpoint, alert_jobs; plus domain/alerts/ | ~15–25 files | Alert storm / duplicate / delivery risk. |
| T1-12 | ML / forecasting / training: ml_lifecycle_service, training_service, global_training_service, auto_retrain_pipeline, inference_service, ml_signal_connector, ml_repository, feature_engine, confidence_scorer, probability_calibrator, isotonic_calibrator, calibration_loop, calibration_bootstrap, gap_prediction, iran_fear_greed_index; src/forecast_engine/*, src/forecasting/*; domain/ml/, schemas/ml/; apps/ml_worker/; jobs/definitions/ml_jobs.py; endpoints/forecast.py, forecast_engine.py | ~40–60 files | Data leakage / overfitting / time-split risk. |

#### Tier 2 batches
| Batch | Focus | Estimated files | Notes |
|---|---|---|---|
| T2-1 | Codal: codal_service, codal_financial_service, codal_download_service, codal_import_service, codal_accounting_service, codal_attachment_service; services/codal_analysis/* (large: analysis_engine, forensic, nlp_analyzer, report_generator, semantic_mapper, scoring, validation, audit_*); domain/codal/; endpoints/codal.py; jobs/codal_jobs.py; repositories/codal_repository.py; ingestion codal sources | ~40–60 files | Large analysis tree. Structured extraction correctness. |
| T2-2 | News / sentiment: news_service, news_ingestion, news_dedup, news_filter, news_sentiment_pipeline, news_source_health, news_tag_symbol_mapper, news_dual_write, news_read_canary, stock_news_sentiment_engine, persian_sentiment_service; domain/news/; endpoints/news.py, sentiment.py; repositories/news_repository.py; ingestion news sources | ~30–40 files | News is the most-changed endpoint (30 commits) — verify stability. |
| T2-3 | Funds / ETF / FOF: fund_service, funds_facade, fund_api_adapter, fund_nav_engine, fund_nav_reconciliation, fund_scoring, fund_discovery, fund_compliance, fund_circuit_breaker, fund_tax, fund_sync_service, fund_read_through, fund_identity, fund_ledger, fund_fof, fund_explainer, fund_quant_engine, fund_class_nav; apps/funds/*; endpoints/funds.py (1,832), funds_v2.py, funds_compliance.py, funds_ledger.py, funds_nav.py, funds_regulator.py; jobs/fund_jobs.py, fund_nav_jobs.py; domain/funds/; repositories/fund_repository.py | ~40–60 files | Large subsystem. NAV correctness is Tier 1-ish if used in pricing. |
| T2-4 | Screener / Program 110: screener_service (1,181), smart_screener_v2, screener110_service, screener_ai_report_service; endpoints/screener.py, screener_v2.py, screener110.py, scanner.py, saved_filters.py; jobs/screener_jobs.py; domain/screening/; backtesting/signals/, backtesting/strategies/; src/sum_program.py | ~30–40 files | Indicator formula correctness + Program 110 logic. |
| T2-5 | USD/gold/silver/oil/commodities — services + domain + endpoints: services/gold/*, domain/commodities/, domain/metals/, domain/energy/, domain/fx/, ingestion/fx/, ingestion/gold/, endpoints/gold.py, golddesk.py; plus src/gold_desk/ non-options files (bubbler, crypto, dca_planner, forecaster, macro_news, parity, portfolio, secondary_source, snapshot_service, ws_hub, telegram_bot, auto_trade, api_token, chat, constants, metrics, models, nav_checker, pattern_detector, schema, signal_engine) — but select deeply, not all | ~40–60 files | unit conversion + price source + currency conversion. Note telegram_bot/auto_trade — verify no real orders. |
| T2-6 | Composition / strategy generation / data import: strategy_generator, compose_service, compose endpoint, generated_strategy_repository; instrument_service, instrument_import_service, instrument_repository; domain/instruments/; endpoints/data_import.py; populate_profiles_service | ~20–30 files | |

#### Tier 3 batches
| Batch | Focus | Estimated files | Notes |
|---|---|---|---|---|
| T3-1 | User/auth/RBAC: user_service, auth endpoint, user_repository, domain/common/, RBAC-related code (from git log "fix(rbac)") | ~15–25 files | Security; verify authn/authz. |
| T3-2 | Chat/assistant: unified_assistant_service (2,010), stock_assistant_service (2,137), services/chat/*, endpoints/chat.py, assistant.py, stock_assistant.py, domain/recommendations/, domain/signals/ (assistant side) | ~30–40 files | Verify no real actions; large files — read key functions. |
| T3-3 | Reporting/analytics/dashboards: analytics_service, report_service, apps/analytics_worker/, endpoints/market_dashboard.py, reports.py, comprehensive_analysis.py, analysis.py; schemas/reporting/; build_symbol_reports.py (1,990) | ~20–30 files | Mostly read-only; check for sensitive data in reports. |
| T3-4 | API surface / app wiring / jobs / scheduling / admin / gateway / CLI: apps/api/app.py (1,204), router.py, middleware.py, endpoints/* (remaining smaller ones), apps/admin/*, apps/gateway/*, apps/scheduler/*, apps/decision_engine/*, jobs/registry.py, jobs/definitions/* (23+ files), jobs/worker.py, job_service, sync_master_service, schemas/*, contracts/*, orchestration/*, apps/cli/* | ~40–60 files | Wiring + entry points. Read app.py, router.py, middleware, job system deeply. |
| T3-5 | Root scripts / utilities / misc: main.py, collector.py, build_symbol_reports.py, gen_all.py, mkpages.py, z.py, fix_test_syntax.py, split_to_10.py, bulk_importer/, scripts/*, services/csv_utils.py, query_logger.py, monitoring_service.py, diagnostics_runner.py, etc. | ~20–30 files | Identify which are ad-hoc vs used. |

### Total batches (rough): ~18–22 batches of 30–60 files
### Total file-touch estimate: far less than 20k — most Python files are vendor/duplicate/data; real application modules are a few thousand files at most, and we read Tier 1 fully and Tier 2/3 selectively.

---

## 4. Stop for approval

Per the prompt: after Steps 1 and 2, **stop and wait for approval** before starting Step 3 (deep reading).

**Decision needed from project owner:**
1. Does the module list above look right, or are there modules to add/split/merge?
2. Any modules to prioritize or skip?
3. Any regions to exclude (e.g., don't read chat/assistant at all, or skip Go side)?
4. Confirm `report/` output path is correct (created at project root: `C:/Users/Iran/Desktop/temce/report/`).

---

## Output files produced in this step

- `report/02-modules-plan.md` (this file)
- `report/PROGRESS.md` (updated)

## Next step (after approval)

Step 3: Deep module-by-module reading, starting with Tier 1 Batch T1-1 (core infrastructure).
