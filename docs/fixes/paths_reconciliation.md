# GoldDesk Fixes - Phase 0: Paths Reconciliation

## Modified Files Categorization

### Engine Group
- BrsApi_Forecasting/api/routers/precompute_router.py
- BrsApi_Forecasting/api/websocket/ws_manager.py
- BrsApi_Forecasting/contracts/events.py
- BrsApi_Forecasting/contracts/schemas.py
- BrsApi_Forecasting/main.py
- src/gold_desk/constants.py
- src/gold_desk/pricer.py
- src/gold_desk/bubbler.py
- src/gold_desk/scorer.py
- src/gold_desk/live_signals.py
- src/gold_desk/dca_planner.py
- src/gold_desk/black76.py
- src/gold_desk/signal_engine.py
- src/gold_desk/pattern_detector.py
- src/gold_desk/backtest_runner.py
- src/gold_desk/nav_checker.py
- src/gold_desk/macro_news.py
- src/gold_desk/parity.py
- indicators.py
- tests/gold_desk/test_parity.py
- tests/gold_desk/test_backtest_runner.py
- tests/gold_desk/test_black76.py
- tests/gold_desk/test_live_signals.py
- tests/gold_desk/test_macro_news.py
- tests/gold_desk/test_dca_planner.py
- tests/gold_desk/test_pricer_bubbler.py
- tests/gold_desk/test_scorer.py
- tests/gold_desk/test_pattern_detector.py
- tests/gold_desk/test_signal_engine.py

### Backend Group (incl. migrations)
- migrations/versions/0043_gold_holding_soft_delete.py
- src/gold_desk/models.py
- src/gold_desk/api.py
- src/gold_desk/portfolio.py
- src/gold_desk/snapshot_service.py
- src/gold_desk/indexes.py
- core/database.py
- scripts/test_backup_golddesk.sh

### Frontend-infra Group
- Dockerfile.golddesk
- .github/workflows/ci.yml
- frontend/src/__tests__/GoldApiLayer.test.ts
- frontend/src/__tests__/GoldFrontendSurfaces.test.tsx
- frontend/src/__tests__/GoldNoData.test.tsx
- frontend/src/__tests__/GoldServiceWorker.test.ts
- frontend/src/__tests__/GoldSnapshotPolling.test.tsx
- frontend/src/__tests__/GoldSwBoundary.test.ts
- frontend/src/__tests__/GoldThemeTokens.test.tsx
- frontend/src/__tests__/GoldWebSocket.test.tsx
- frontend/src/components/gold/ConfirmDialog.tsx
- frontend/src/hooks/useGoldWS.ts
- frontend/src/lib/gold-decision.ts

### Docs/Ops Group
- docs/fixes/
- docs/audit_findings.md
- docs/remediation_plan.json
- scripts/backup_golddesk.sh
- scripts/test_backup_golddesk.sh
- generate_ruff_report.py
- baseline_api.txt
- baseline_api_gold.txt
- baseline_backtesting.txt
- baseline_core.txt
- baseline_gold_desk.txt
- baseline_ml.txt
- baseline_ruff.txt
- baseline_services.txt

### Files Without Clear Ownership (isolated)
- scripts/import_cached_trades.py
- scripts/news_parity_window.py
- scripts/verify_cached_trades.py
- services/calibration_loop.py
- services/codal_download_service.py
- services/codal_financial_statement_import.py
- services/data_layer.py
- services/news_dual_write.py
- services/news_source_health.py
- services/options_service.py
- services/resample_timeframes.py
- services/signal_composer.py
- services/signal_explain.py
- services/signal_store.py
- services/smart_money/layer7_buyer_power.py
- services/smart_money/stats.py
- tests/integration/backtesting/test_walk_forward_e2e_real_sim.py
- tests/unit/api/test_news_category.py
- tests/unit/api/test_news_date_range.py
- tests/unit/apps/api/test_walk_forward_api.py
- tests/unit/backtesting/test_audit_fixes_regression.py
- tests/unit/backtesting/test_consumer_cost_parity.py
- tests/unit/backtesting/test_tick_cutoff.py
- tests/unit/decision_engine_v5/test_v5_engine.py
- tests/unit/ml/test_purged_cv.py
- tests/unit/ml/test_seed_determinism.py
- tests/unit/observability/test_prometheus_exporter_parity.py
- tests/unit/options/test_strategy_engine.py
- tests/unit/services/test_news_dual_write.py
- tests/unit/services/test_news_items_read_path.py
- tests/unit/services/test_news_read_canary.py
- tests/unit/services/test_news_source_health.py
- tests/unit/services/test_p0_regression.py
- tests/unit/services/test_signal_decision_engine.py
- tests/unit/test_api_inbound_simulation.py
- tests/unit/test_audit_fixes_batch2.py
- tests/unit/test_audit_stages_2_3_5.py
- tests/unit/test_brsapi_sync_nav_all_endpoint.py
- tests/unit/test_funds_regulator_api.py
- tests/unit/test_gold_silver_funds_critical_regressions.py
- z.py

## Summary
- **Engine**: 35 files (core engine logic, schemas, APIs)
- **Backend**: 12 files (migrations, models, API, portfolio service)
- **Frontend-infra**: 22 files (frontend components, tests, configs)
- **Docs/Ops**: 18 files (documentation, baselines, scripts)
- **Uncategorized**: 38 files (require owner determination)