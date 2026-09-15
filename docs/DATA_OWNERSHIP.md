# Data Ownership Registry (Phase 1 input, Phase 0 baseline)

> Authority for table ownership disputes. Schema changes to a domain's tables
> require that domain's CODEOWNERS approval once Phase 1 lands. Generated from
> `models/` + `migrations/versions/` table definitions; 110 tables as of 2026-09-09.

## Market Data (23)

| Table |
|---|
| `candlesticks` |
| `corporate_actions` |
| `daily_history` |
| `daily_real_legal` |
| `data_lineage` |
| `indicators` |
| `indices` |
| `instruments` |
| `intraday_trades` |
| `market_data_quality_events` |
| `market_data_sources` |
| `market_snapshots` |
| `market_ticks` |
| `trades` |
| `markets` |
| `orderbook_snapshots` |
| `orderbooks` |
| `provider_health` |
| `provider_health_history` |
| `quotes` |
| `shareholders` |
| `symbol_relations` |
| `symbol_snapshots` |
| `symbols` |

## Identity / Auth (2)

| Table |
|---|
| `account_mappings` |
| `users` |

## Audit (2)

| Table |
|---|
| `audit_logs` |
| `audit_trail` |

## Signals (5)

| Table |
|---|
| `queue_analysis_results` |
| `recommendations` |
| `scoring_config_history` |
| `signal_accuracy` |
| `signals` |

## Screener (5)

| Table |
|---|
| `saved_filters` |
| `screener_daily_scores` |
| `screener_profiles` |
| `screener_signals` |
| `screener_snapshots` |

## Backtesting (3)

| Table |
|---|
| `backtest_runs` |
| `backtest_trades` |
| `compare_results` |

## Strategy (2)

| Table |
|---|
| `generated_strategies` |
| `generation_batches` |

## ML / Feature Store (5)

| Table |
|---|
| `ml_engineered_features` |
| `ml_model_versions` |
| `ml_models` |
| `ml_predictions` |
| `ml_training_runs` |

## Funds / NAV (3)

| Table |
|---|
| `etf_nav` |
| `fund_categories` |
| `funds` |

## CODAL (4)

| Table |
|---|
| `codal_announcements` |
| `codal_audit_summary` |
| `codal_financial_statements` |
| `codal_reports` |

## CODAL Analytics (10)

| Table |
|---|
| `dim_account` |
| `dim_company` |
| `dim_date` |
| `dim_document` |
| `dim_report_type` |
| `fact_financials` |
| `fact_growth` |
| `fact_quality_signals` |
| `fact_ratios` |
| `fact_text_analytics` |

## News (1)

| Table |
|---|
| `news_articles` |

## BrsApi Integration (2)

| Table |
|---|
| `brsapi_codal_attachments` |
| `brsapi_daily_usage` |

## Currency Service (1)

| Table |
|---|
| `currency_manual_positions` |

## Gold Desk (12)

| Table |
|---|
| `gold_alert_events` |
| `gold_alert_rules` |
| `gold_currency_prices` |
| `gold_dca_plans` |
| `gold_fund_nav` |
| `gold_futures_positions` |
| `gold_holdings` |
| `gold_kill_switch_events` |
| `gold_portfolio_holdings` |
| `gold_score_history` |
| `gold_snapshots` |
| `gold_trades` |

## Commodity (IME) (7)

| Table |
|---|
| `commodity_certificates` |
| `commodity_funds` |
| `commodity_futures` |
| `commodity_options` |
| `commodity_prices` |
| `commodity_trades` |
| `contracts` |

## Options (6)

| Table |
|---|
| `open_interest_history` |
| `option_contracts` |
| `option_snapshots` |
| `option_trades` |
| `options` |
| `volatility_surface` |

## Portfolio (2)

| Table |
|---|
| `portfolio_positions` |
| `portfolios` |

## Paper Trading (5)

| Table |
|---|
| `paper_equity_history` |
| `paper_orders` |
| `paper_positions` |
| `paper_signal_snapshots` |
| `paper_trades` |

## Alerts (2)

| Table |
|---|
| `alert_history` |
| `alerts` |

## Decision Engine (4)

| Table |
|---|
| `decision_architectures` |
| `decision_results` |
| `proposal_audit` |
| `proposals` |

## Macro (1)

| Table |
|---|
| `macro_indicators` |

## Job Orchestration (1)

| Table |
|---|
| `job_runs` |

## Reports / Assistant (1)

| Table |
|---|
| `analysis_reports` |

