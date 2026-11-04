"""Backfill Alembic-created schema for 28 core ORM tables (audit run2, D3).

Root cause this closes: ``core.database.init_database`` used to run
``Base.metadata.create_all`` in early development, so ~26% of the ORM tables
(portfolios, users, instruments, quotes, signals, alerts, ml_*, ...) were never
captured by an Alembic migration. A clean production database (which never runs
``create_all``) therefore lacked them and any dependent query failed with
``UndefinedTable``. See AUDIT_REPORTS/MODULAR_TEMCE/14_DB_SCHEMA_INTEGRITY_RUNTIME_DDL_run1_20261029.md.

The DDL below is FROZEN (generated from the ORM metadata on 2026-10-29) so the
migration is reproducible and cannot drift with the models. A DB-free guard test
(``tests/unit/test_core_tables_migration.py``) fails if the ORM ever diverges from
this frozen DDL, forcing a new migration instead of a silent fork.

Every statement is ``IF NOT EXISTS`` and targets PostgreSQL: these tables already
exist in current databases (created historically by ``create_all``), so the
migration is a no-op there and only fills the gap in a fresh database.

Revision ID: 0118
Revises: 0117
"""

from __future__ import annotations

from alembic import op

revision = "0118_core_tables_backfill"
down_revision = "0117"
branch_labels = None
depends_on = None


# (table_name, "CREATE TABLE IF NOT EXISTS ...") - frozen from ORM metadata 2026-10-29.
_TABLES: tuple[tuple[str, str], ...] = (
    (
        'alert_history',
        """CREATE TABLE IF NOT EXISTS alert_history (
	id VARCHAR(50) NOT NULL,
	alert_id VARCHAR(50) NOT NULL,
	triggered_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	trigger_value FLOAT,
	message TEXT,
	delivered BOOLEAN DEFAULT false,
	PRIMARY KEY (id)
)""",
    ),
    (
        'alerts',
        """CREATE TABLE IF NOT EXISTS alerts (
	id VARCHAR(50) NOT NULL,
	user_id VARCHAR(100),
	instrument_id VARCHAR(50),
	symbol VARCHAR(50),
	alert_type VARCHAR(50) NOT NULL,
	condition TEXT,
	channels TEXT,
	enabled BOOLEAN DEFAULT true,
	triggered_count INTEGER DEFAULT '0',
	last_triggered TIMESTAMP WITHOUT TIME ZONE,
	description TEXT,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	signal_id VARCHAR(50),
	market VARCHAR(20),
	timeframe VARCHAR(10),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'audit_logs',
        """CREATE TABLE IF NOT EXISTS audit_logs (
	id VARCHAR(50) NOT NULL,
	action VARCHAR(100) NOT NULL,
	entity_type VARCHAR(50) NOT NULL,
	entity_id VARCHAR(50),
	actor VARCHAR(100) DEFAULT 'system',
	changes TEXT,
	ip_address VARCHAR(50),
	user_agent VARCHAR(500),
	details TEXT,
	timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
)""",
    ),
    (
        'backtest_runs',
        """CREATE TABLE IF NOT EXISTS backtest_runs (
	id VARCHAR(50) NOT NULL,
	name VARCHAR(200) NOT NULL,
	strategy_type VARCHAR(100),
	symbols TEXT,
	status VARCHAR(20) DEFAULT 'queued',
	start_date VARCHAR(20),
	end_date VARCHAR(20),
	initial_capital FLOAT,
	current_value FLOAT,
	total_return_pct FLOAT,
	commission_pct FLOAT DEFAULT '0.0035',
	slippage_bps FLOAT DEFAULT '10',
	strategy_params TEXT,
	metrics TEXT,
	progress_pct FLOAT DEFAULT '0',
	started_at TIMESTAMP WITHOUT TIME ZONE,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	created_by VARCHAR(100) DEFAULT 'system',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'backtest_trades',
        """CREATE TABLE IF NOT EXISTS backtest_trades (
	id VARCHAR(50) NOT NULL,
	run_id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50),
	direction VARCHAR(10),
	entry_date VARCHAR(20),
	exit_date VARCHAR(20),
	entry_price FLOAT,
	exit_price FLOAT,
	quantity INTEGER,
	gross_profit FLOAT,
	net_profit FLOAT,
	return_pct FLOAT,
	commission FLOAT,
	exit_reason VARCHAR(50),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'codal_audit_summary',
        """CREATE TABLE IF NOT EXISTS codal_audit_summary (
	id BIGSERIAL NOT NULL,
	symbol VARCHAR(50) NOT NULL,
	company_name VARCHAR(200),
	report_type VARCHAR(20),
	report_date VARCHAR(20),
	revenue FLOAT,
	net_profit FLOAT,
	total_assets FLOAT,
	total_equity FLOAT,
	eps FLOAT,
	roe FLOAT,
	roa FLOAT,
	gross_margin FLOAT,
	net_margin FLOAT,
	current_ratio FLOAT,
	debt_to_equity FLOAT,
	asset_turnover FLOAT,
	revenue_growth FLOAT,
	net_profit_growth FLOAT,
	health_score FLOAT,
	health_classification VARCHAR(20),
	earnings_quality_score FLOAT,
	forensic_risk VARCHAR(20),
	going_concern_risk VARCHAR(20),
	materiality_planning FLOAT,
	materiality_performance FLOAT,
	top_audit_risks JSONB,
	total_reports INTEGER DEFAULT '0',
	analysis_status VARCHAR(20),
	full_results JSONB,
	PRIMARY KEY (id)
)""",
    ),
    (
        'codal_reports',
        """CREATE TABLE IF NOT EXISTS codal_reports (
	id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50),
	symbol VARCHAR(50),
	company_name VARCHAR(200),
	isin VARCHAR(50),
	report_type VARCHAR(50),
	fiscal_year VARCHAR(20),
	period VARCHAR(50),
	audit_status VARCHAR(20),
	publish_date VARCHAR(20),
	attachment_url TEXT,
	summary TEXT,
	data_source VARCHAR(20) DEFAULT 'codal',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'compare_results',
        """CREATE TABLE IF NOT EXISTS compare_results (
	id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50) NOT NULL,
	total_strategies INTEGER NOT NULL,
	successful INTEGER NOT NULL,
	failed INTEGER NOT NULL,
	best VARCHAR(100),
	worst VARCHAR(100),
	results_json TEXT,
	best_return_pct FLOAT,
	worst_return_pct FLOAT,
	avg_return_pct FLOAT,
	start_date VARCHAR(20),
	end_date VARCHAR(20),
	capital FLOAT,
	notes VARCHAR(500),
	executed_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'indicators',
        """CREATE TABLE IF NOT EXISTS indicators (
	id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50),
	indicator_type VARCHAR(50) NOT NULL,
	params TEXT,
	values TEXT,
	timeframe VARCHAR(10) DEFAULT '1d',
	date VARCHAR(20),
	data_source VARCHAR(20) DEFAULT 'system',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'instruments',
        """CREATE TABLE IF NOT EXISTS instruments (
	id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50) NOT NULL,
	name VARCHAR(200),
	isin VARCHAR(50),
	market_type VARCHAR(20),
	asset_class VARCHAR(20),
	status VARCHAR(20) DEFAULT 'active',
	sector_code VARCHAR(20),
	group_code VARCHAR(20),
	sub_group_code VARCHAR(20),
	tick_size FLOAT DEFAULT '1.0',
	lot_size INTEGER DEFAULT '1',
	par_value INTEGER DEFAULT '1000',
	eps FLOAT DEFAULT '0',
	shares_count BIGINT DEFAULT '0',
	base_volume BIGINT DEFAULT '0',
	market_id VARCHAR(50),
	exchange_code VARCHAR(20),
	board_code VARCHAR(20),
	data_source VARCHAR(20) DEFAULT 'tsetmc',
	tags JSON,
	metadata_ JSON,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (isin)
)""",
    ),
    (
        'job_runs',
        """CREATE TABLE IF NOT EXISTS job_runs (
	id VARCHAR(50) NOT NULL,
	job_type VARCHAR(100) NOT NULL,
	status VARCHAR(20) DEFAULT 'pending',
	progress_pct FLOAT DEFAULT '0',
	started_at TIMESTAMP WITHOUT TIME ZONE,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	duration_seconds FLOAT,
	error_message TEXT,
	result TEXT,
	params TEXT,
	triggered_by VARCHAR(50) DEFAULT 'scheduler',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'macro_indicators',
        """CREATE TABLE IF NOT EXISTS macro_indicators (
	id VARCHAR(50) NOT NULL,
	indicator VARCHAR(100) NOT NULL,
	country VARCHAR(50) DEFAULT 'iran',
	value FLOAT,
	previous_value FLOAT,
	change_pct FLOAT,
	date VARCHAR(20),
	source VARCHAR(100),
	unit VARCHAR(50),
	frequency VARCHAR(20) DEFAULT 'monthly',
	data_source VARCHAR(20) DEFAULT 'rss',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'markets',
        """CREATE TABLE IF NOT EXISTS markets (
	id VARCHAR(50) NOT NULL,
	name VARCHAR(200) NOT NULL,
	market_type VARCHAR(20),
	exchange_code VARCHAR(20),
	country VARCHAR(50) DEFAULT 'IR',
	timezone VARCHAR(50) DEFAULT 'Asia/Tehran',
	open_time VARCHAR(10) DEFAULT '09:00',
	close_time VARCHAR(10) DEFAULT '12:30',
	status VARCHAR(20) DEFAULT 'active',
	description TEXT,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'ml_model_versions',
        """CREATE TABLE IF NOT EXISTS ml_model_versions (
	id VARCHAR(50) NOT NULL,
	model_id VARCHAR(50) NOT NULL,
	version VARCHAR(20) NOT NULL,
	stage VARCHAR(20) DEFAULT 'development',
	metrics TEXT,
	parameters TEXT,
	artifact_path TEXT,
	dataset_snapshot VARCHAR(100),
	training_run_id VARCHAR(50),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'ml_models',
        """CREATE TABLE IF NOT EXISTS ml_models (
	id VARCHAR(50) NOT NULL,
	name VARCHAR(200) NOT NULL,
	task VARCHAR(50) DEFAULT 'classification',
	framework VARCHAR(50) DEFAULT 'sklearn',
	latest_version VARCHAR(20) DEFAULT '1.0.0',
	description TEXT,
	tags TEXT,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)""",
    ),
    (
        'ml_predictions',
        """CREATE TABLE IF NOT EXISTS ml_predictions (
	id VARCHAR(50) NOT NULL,
	batch_id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50) NOT NULL,
	model_type VARCHAR(50) NOT NULL,
	prediction FLOAT,
	accuracy FLOAT DEFAULT '0',
	confidence FLOAT DEFAULT '0',
	f1_score FLOAT DEFAULT '0',
	mse FLOAT DEFAULT '0',
	samples INTEGER DEFAULT '0',
	duration_seconds FLOAT DEFAULT '0',
	predicted_change_pct FLOAT,
	last_price FLOAT,
	feature_importance TEXT,
	model_loaded_from VARCHAR(30),
	prediction_failed BOOLEAN DEFAULT false,
	model_id VARCHAR(50),
	executed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'ml_training_runs',
        """CREATE TABLE IF NOT EXISTS ml_training_runs (
	id VARCHAR(50) NOT NULL,
	experiment_name VARCHAR(200),
	run_name VARCHAR(200),
	status VARCHAR(20) DEFAULT 'pending',
	model_type VARCHAR(50),
	config TEXT,
	metrics TEXT,
	best_params TEXT,
	progress_pct FLOAT DEFAULT '0',
	started_at TIMESTAMP WITHOUT TIME ZONE,
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	duration_seconds FLOAT,
	error TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'news_articles',
        """CREATE TABLE IF NOT EXISTS news_articles (
	id VARCHAR(50) NOT NULL,
	title VARCHAR(500) NOT NULL,
	summary TEXT,
	content TEXT,
	source VARCHAR(100),
	url TEXT,
	category VARCHAR(50),
	symbols TEXT,
	published_at VARCHAR(40),
	published_at_ts TIMESTAMP WITHOUT TIME ZONE,
	sentiment VARCHAR(20) DEFAULT 'neutral',
	sentiment_score FLOAT DEFAULT '0',
	data_source VARCHAR(20) DEFAULT 'rss',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'orderbooks',
        """CREATE TABLE IF NOT EXISTS orderbooks (
	id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50),
	bids TEXT,
	asks TEXT,
	time VARCHAR(20),
	date VARCHAR(20),
	data_source VARCHAR(20) DEFAULT 'tsetmc',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'portfolio_positions',
        """CREATE TABLE IF NOT EXISTS portfolio_positions (
	id VARCHAR(50) NOT NULL,
	portfolio_id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50),
	symbol VARCHAR(50),
	quantity INTEGER,
	avg_cost FLOAT,
	current_price FLOAT,
	market_value FLOAT,
	unrealized_pnl FLOAT,
	weight_pct FLOAT,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'portfolios',
        """CREATE TABLE IF NOT EXISTS portfolios (
	id VARCHAR(50) NOT NULL,
	name VARCHAR(200) NOT NULL,
	description TEXT,
	initial_capital FLOAT DEFAULT '0',
	current_value FLOAT DEFAULT '0',
	currency VARCHAR(10) DEFAULT 'IRR',
	owner VARCHAR(100) DEFAULT 'system',
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'provider_health',
        """CREATE TABLE IF NOT EXISTS provider_health (
	id VARCHAR(50) NOT NULL,
	provider VARCHAR(100) NOT NULL,
	status VARCHAR(20) DEFAULT 'unknown',
	latency_ms FLOAT DEFAULT '0',
	last_success TIMESTAMP WITHOUT TIME ZONE,
	last_failure TIMESTAMP WITHOUT TIME ZONE,
	consecutive_failures INTEGER DEFAULT '0',
	uptime_pct FLOAT DEFAULT '100',
	error_message TEXT,
	checked_at TIMESTAMP WITHOUT TIME ZONE,
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (provider)
)""",
    ),
    (
        'provider_health_history',
        """CREATE TABLE IF NOT EXISTS provider_health_history (
	id VARCHAR(50) NOT NULL,
	provider VARCHAR(100) NOT NULL,
	status VARCHAR(20),
	latency_ms FLOAT,
	error_message TEXT,
	checked_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
)""",
    ),
    (
        'quotes',
        """CREATE TABLE IF NOT EXISTS quotes (
	id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50),
	price_close FLOAT,
	price_open FLOAT,
	price_high FLOAT,
	price_low FLOAT,
	price_last FLOAT,
	price_change FLOAT,
	price_change_pct FLOAT,
	volume BIGINT,
	value FLOAT,
	trade_count BIGINT,
	price_yesterday FLOAT,
	price_first FLOAT,
	price_max FLOAT,
	price_min FLOAT,
	ask_price FLOAT,
	ask_volume BIGINT,
	bid_price FLOAT,
	bid_volume BIGINT,
	time VARCHAR(20),
	date VARCHAR(20),
	timeframe VARCHAR(10) DEFAULT '1d',
	data_source VARCHAR(20) DEFAULT 'tsetmc',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'recommendations',
        """CREATE TABLE IF NOT EXISTS recommendations (
	id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50),
	symbol VARCHAR(50) NOT NULL,
	action VARCHAR(20) NOT NULL,
	confidence FLOAT DEFAULT '0',
	target_price FLOAT,
	stop_loss FLOAT,
	rationale TEXT,
	strategy VARCHAR(50),
	risk_level VARCHAR(20),
	horizon VARCHAR(20),
	data_source VARCHAR(20) DEFAULT 'system',
	generated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	expires_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'signals',
        """CREATE TABLE IF NOT EXISTS signals (
	id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50),
	symbol VARCHAR(50) NOT NULL,
	signal_type VARCHAR(30) NOT NULL,
	strength FLOAT DEFAULT '0',
	direction VARCHAR(20),
	source VARCHAR(100),
	indicators TEXT,
	message TEXT,
	timeframe VARCHAR(10) DEFAULT '1d',
	data_source VARCHAR(20) DEFAULT 'system',
	generated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	expires_at TIMESTAMP WITHOUT TIME ZONE,
	market VARCHAR(20),
	entry FLOAT DEFAULT '0',
	stop_loss FLOAT DEFAULT '0',
	take_profit FLOAT DEFAULT '0',
	confidence FLOAT DEFAULT '0',
	top_reasons TEXT,
	backtest_stats TEXT,
	eval_due_at TIMESTAMP WITHOUT TIME ZONE,
	schema_version INTEGER DEFAULT '1',
	model_version VARCHAR(64),
	status VARCHAR(20) DEFAULT 'pending',
	actual_outcome_price FLOAT,
	actual_return_pct FLOAT,
	was_correct BOOLEAN,
	checked_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'trades',
        """CREATE TABLE IF NOT EXISTS trades (
	id VARCHAR(50) NOT NULL,
	instrument_id VARCHAR(50) NOT NULL,
	symbol VARCHAR(50),
	price FLOAT,
	volume INTEGER,
	value FLOAT,
	side VARCHAR(10),
	time VARCHAR(20),
	date VARCHAR(20),
	data_source VARCHAR(20) DEFAULT 'tsetmc',
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
    (
        'users',
        """CREATE TABLE IF NOT EXISTS users (
	id VARCHAR(50) NOT NULL,
	username VARCHAR(50) NOT NULL,
	email VARCHAR(255) NOT NULL,
	hashed_password VARCHAR(255) NOT NULL,
	full_name VARCHAR(100),
	phone VARCHAR(20),
	roles VARCHAR(255) DEFAULT 'viewer' NOT NULL,
	is_active BOOLEAN DEFAULT true NOT NULL,
	is_verified BOOLEAN DEFAULT false NOT NULL,
	last_login TIMESTAMP WITHOUT TIME ZONE,
	refresh_token TEXT,
	metadata TEXT,
	totp_secret VARCHAR(64),
	totp_enabled BOOLEAN DEFAULT false NOT NULL,
	totp_confirmed_at TIMESTAMP WITHOUT TIME ZONE,
	mfa_method VARCHAR(16),
	telegram_chat_id VARCHAR(64),
	updated_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)""",
    ),
)

# (index_name, table_name, "CREATE INDEX IF NOT EXISTS ...") - frozen from ORM metadata.
_INDEXES: tuple[tuple[str, str, str], ...] = (
    (
        'ix_alert_history_alert_id',
        'alert_history',
        """CREATE INDEX IF NOT EXISTS ix_alert_history_alert_id ON alert_history (alert_id)""",
    ),
    (
        'ix_alerts_alert_type',
        'alerts',
        """CREATE INDEX IF NOT EXISTS ix_alerts_alert_type ON alerts (alert_type)""",
    ),
    (
        'ix_alerts_enabled',
        'alerts',
        """CREATE INDEX IF NOT EXISTS ix_alerts_enabled ON alerts (enabled)""",
    ),
    (
        'ix_alerts_instrument_id',
        'alerts',
        """CREATE INDEX IF NOT EXISTS ix_alerts_instrument_id ON alerts (instrument_id)""",
    ),
    (
        'ix_alerts_market',
        'alerts',
        """CREATE INDEX IF NOT EXISTS ix_alerts_market ON alerts (market)""",
    ),
    (
        'ix_alerts_signal_id',
        'alerts',
        """CREATE INDEX IF NOT EXISTS ix_alerts_signal_id ON alerts (signal_id)""",
    ),
    (
        'ix_alerts_user_id',
        'alerts',
        """CREATE INDEX IF NOT EXISTS ix_alerts_user_id ON alerts (user_id)""",
    ),
    (
        'ix_audit_logs_action',
        'audit_logs',
        """CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)""",
    ),
    (
        'ix_audit_logs_actor',
        'audit_logs',
        """CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs (actor)""",
    ),
    (
        'ix_audit_logs_entity_id',
        'audit_logs',
        """CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_id ON audit_logs (entity_id)""",
    ),
    (
        'ix_audit_logs_entity_type',
        'audit_logs',
        """CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs (entity_type)""",
    ),
    (
        'ix_backtest_runs_created_by',
        'backtest_runs',
        """CREATE INDEX IF NOT EXISTS ix_backtest_runs_created_by ON backtest_runs (created_by)""",
    ),
    (
        'ix_backtest_runs_status',
        'backtest_runs',
        """CREATE INDEX IF NOT EXISTS ix_backtest_runs_status ON backtest_runs (status)""",
    ),
    (
        'ix_backtest_runs_strategy_type',
        'backtest_runs',
        """CREATE INDEX IF NOT EXISTS ix_backtest_runs_strategy_type ON backtest_runs (strategy_type)""",
    ),
    (
        'ix_backtest_trades_run_id',
        'backtest_trades',
        """CREATE INDEX IF NOT EXISTS ix_backtest_trades_run_id ON backtest_trades (run_id)""",
    ),
    (
        'ix_codal_audit_summary_symbol',
        'codal_audit_summary',
        """CREATE UNIQUE INDEX IF NOT EXISTS ix_codal_audit_summary_symbol ON codal_audit_summary (symbol)""",
    ),
    (
        'ix_codal_reports_company_name',
        'codal_reports',
        """CREATE INDEX IF NOT EXISTS ix_codal_reports_company_name ON codal_reports (company_name)""",
    ),
    (
        'ix_codal_reports_fiscal_year',
        'codal_reports',
        """CREATE INDEX IF NOT EXISTS ix_codal_reports_fiscal_year ON codal_reports (fiscal_year)""",
    ),
    (
        'ix_codal_reports_instrument_id',
        'codal_reports',
        """CREATE INDEX IF NOT EXISTS ix_codal_reports_instrument_id ON codal_reports (instrument_id)""",
    ),
    (
        'ix_codal_reports_isin',
        'codal_reports',
        """CREATE INDEX IF NOT EXISTS ix_codal_reports_isin ON codal_reports (isin)""",
    ),
    (
        'ix_codal_reports_period',
        'codal_reports',
        """CREATE INDEX IF NOT EXISTS ix_codal_reports_period ON codal_reports (period)""",
    ),
    (
        'ix_codal_reports_report_type',
        'codal_reports',
        """CREATE INDEX IF NOT EXISTS ix_codal_reports_report_type ON codal_reports (report_type)""",
    ),
    (
        'ix_codal_reports_symbol',
        'codal_reports',
        """CREATE INDEX IF NOT EXISTS ix_codal_reports_symbol ON codal_reports (symbol)""",
    ),
    (
        'ix_compare_results_symbol',
        'compare_results',
        """CREATE INDEX IF NOT EXISTS ix_compare_results_symbol ON compare_results (symbol)""",
    ),
    (
        'ix_indicators_date',
        'indicators',
        """CREATE INDEX IF NOT EXISTS ix_indicators_date ON indicators (date)""",
    ),
    (
        'ix_indicators_indicator_type',
        'indicators',
        """CREATE INDEX IF NOT EXISTS ix_indicators_indicator_type ON indicators (indicator_type)""",
    ),
    (
        'ix_indicators_instrument_id',
        'indicators',
        """CREATE INDEX IF NOT EXISTS ix_indicators_instrument_id ON indicators (instrument_id)""",
    ),
    (
        'ix_indicators_symbol',
        'indicators',
        """CREATE INDEX IF NOT EXISTS ix_indicators_symbol ON indicators (symbol)""",
    ),
    (
        'ix_indicators_timeframe',
        'indicators',
        """CREATE INDEX IF NOT EXISTS ix_indicators_timeframe ON indicators (timeframe)""",
    ),
    (
        'ix_instruments_asset_class',
        'instruments',
        """CREATE INDEX IF NOT EXISTS ix_instruments_asset_class ON instruments (asset_class)""",
    ),
    (
        'ix_instruments_group_code',
        'instruments',
        """CREATE INDEX IF NOT EXISTS ix_instruments_group_code ON instruments (group_code)""",
    ),
    (
        'ix_instruments_market_type',
        'instruments',
        """CREATE INDEX IF NOT EXISTS ix_instruments_market_type ON instruments (market_type)""",
    ),
    (
        'ix_instruments_sector_code',
        'instruments',
        """CREATE INDEX IF NOT EXISTS ix_instruments_sector_code ON instruments (sector_code)""",
    ),
    (
        'ix_instruments_status',
        'instruments',
        """CREATE INDEX IF NOT EXISTS ix_instruments_status ON instruments (status)""",
    ),
    (
        'ix_instruments_symbol',
        'instruments',
        """CREATE UNIQUE INDEX IF NOT EXISTS ix_instruments_symbol ON instruments (symbol)""",
    ),
    (
        'ix_job_runs_job_type',
        'job_runs',
        """CREATE INDEX IF NOT EXISTS ix_job_runs_job_type ON job_runs (job_type)""",
    ),
    (
        'ix_job_runs_status',
        'job_runs',
        """CREATE INDEX IF NOT EXISTS ix_job_runs_status ON job_runs (status)""",
    ),
    (
        'ix_macro_indicators_country',
        'macro_indicators',
        """CREATE INDEX IF NOT EXISTS ix_macro_indicators_country ON macro_indicators (country)""",
    ),
    (
        'ix_macro_indicators_date',
        'macro_indicators',
        """CREATE INDEX IF NOT EXISTS ix_macro_indicators_date ON macro_indicators (date)""",
    ),
    (
        'ix_macro_indicators_indicator',
        'macro_indicators',
        """CREATE INDEX IF NOT EXISTS ix_macro_indicators_indicator ON macro_indicators (indicator)""",
    ),
    (
        'ix_markets_exchange_code',
        'markets',
        """CREATE INDEX IF NOT EXISTS ix_markets_exchange_code ON markets (exchange_code)""",
    ),
    (
        'ix_markets_market_type',
        'markets',
        """CREATE INDEX IF NOT EXISTS ix_markets_market_type ON markets (market_type)""",
    ),
    (
        'ix_ml_model_versions_model_id',
        'ml_model_versions',
        """CREATE INDEX IF NOT EXISTS ix_ml_model_versions_model_id ON ml_model_versions (model_id)""",
    ),
    (
        'ix_ml_model_versions_stage',
        'ml_model_versions',
        """CREATE INDEX IF NOT EXISTS ix_ml_model_versions_stage ON ml_model_versions (stage)""",
    ),
    (
        'ix_ml_predictions_batch_id',
        'ml_predictions',
        """CREATE INDEX IF NOT EXISTS ix_ml_predictions_batch_id ON ml_predictions (batch_id)""",
    ),
    (
        'ix_ml_predictions_executed_at',
        'ml_predictions',
        """CREATE INDEX IF NOT EXISTS ix_ml_predictions_executed_at ON ml_predictions (executed_at)""",
    ),
    (
        'ix_ml_predictions_model_id',
        'ml_predictions',
        """CREATE INDEX IF NOT EXISTS ix_ml_predictions_model_id ON ml_predictions (model_id)""",
    ),
    (
        'ix_ml_predictions_model_type',
        'ml_predictions',
        """CREATE INDEX IF NOT EXISTS ix_ml_predictions_model_type ON ml_predictions (model_type)""",
    ),
    (
        'ix_ml_predictions_symbol',
        'ml_predictions',
        """CREATE INDEX IF NOT EXISTS ix_ml_predictions_symbol ON ml_predictions (symbol)""",
    ),
    (
        'ix_ml_training_runs_experiment_name',
        'ml_training_runs',
        """CREATE INDEX IF NOT EXISTS ix_ml_training_runs_experiment_name ON ml_training_runs (experiment_name)""",
    ),
    (
        'ix_ml_training_runs_status',
        'ml_training_runs',
        """CREATE INDEX IF NOT EXISTS ix_ml_training_runs_status ON ml_training_runs (status)""",
    ),
    (
        'ix_news_articles_category',
        'news_articles',
        """CREATE INDEX IF NOT EXISTS ix_news_articles_category ON news_articles (category)""",
    ),
    (
        'ix_news_articles_published_at',
        'news_articles',
        """CREATE INDEX IF NOT EXISTS ix_news_articles_published_at ON news_articles (published_at)""",
    ),
    (
        'ix_news_articles_published_at_ts',
        'news_articles',
        """CREATE INDEX IF NOT EXISTS ix_news_articles_published_at_ts ON news_articles (published_at_ts)""",
    ),
    (
        'ix_news_articles_source',
        'news_articles',
        """CREATE INDEX IF NOT EXISTS ix_news_articles_source ON news_articles (source)""",
    ),
    (
        'ix_orderbooks_date',
        'orderbooks',
        """CREATE INDEX IF NOT EXISTS ix_orderbooks_date ON orderbooks (date)""",
    ),
    (
        'ix_orderbooks_instrument_id',
        'orderbooks',
        """CREATE INDEX IF NOT EXISTS ix_orderbooks_instrument_id ON orderbooks (instrument_id)""",
    ),
    (
        'ix_orderbooks_symbol',
        'orderbooks',
        """CREATE INDEX IF NOT EXISTS ix_orderbooks_symbol ON orderbooks (symbol)""",
    ),
    (
        'ix_portfolio_positions_instrument_id',
        'portfolio_positions',
        """CREATE INDEX IF NOT EXISTS ix_portfolio_positions_instrument_id ON portfolio_positions (instrument_id)""",
    ),
    (
        'ix_portfolio_positions_portfolio_id',
        'portfolio_positions',
        """CREATE INDEX IF NOT EXISTS ix_portfolio_positions_portfolio_id ON portfolio_positions (portfolio_id)""",
    ),
    (
        'ix_portfolio_positions_symbol',
        'portfolio_positions',
        """CREATE INDEX IF NOT EXISTS ix_portfolio_positions_symbol ON portfolio_positions (symbol)""",
    ),
    (
        'ix_provider_health_history_provider',
        'provider_health_history',
        """CREATE INDEX IF NOT EXISTS ix_provider_health_history_provider ON provider_health_history (provider)""",
    ),
    (
        'ix_quotes_date',
        'quotes',
        """CREATE INDEX IF NOT EXISTS ix_quotes_date ON quotes (date)""",
    ),
    (
        'ix_quotes_instrument_id',
        'quotes',
        """CREATE INDEX IF NOT EXISTS ix_quotes_instrument_id ON quotes (instrument_id)""",
    ),
    (
        'ix_quotes_symbol',
        'quotes',
        """CREATE INDEX IF NOT EXISTS ix_quotes_symbol ON quotes (symbol)""",
    ),
    (
        'ix_quotes_symbol_date',
        'quotes',
        """CREATE INDEX IF NOT EXISTS ix_quotes_symbol_date ON quotes (symbol, date)""",
    ),
    (
        'ix_recommendations_action',
        'recommendations',
        """CREATE INDEX IF NOT EXISTS ix_recommendations_action ON recommendations (action)""",
    ),
    (
        'ix_recommendations_generated_at',
        'recommendations',
        """CREATE INDEX IF NOT EXISTS ix_recommendations_generated_at ON recommendations (generated_at)""",
    ),
    (
        'ix_recommendations_instrument_id',
        'recommendations',
        """CREATE INDEX IF NOT EXISTS ix_recommendations_instrument_id ON recommendations (instrument_id)""",
    ),
    (
        'ix_recommendations_symbol',
        'recommendations',
        """CREATE INDEX IF NOT EXISTS ix_recommendations_symbol ON recommendations (symbol)""",
    ),
    (
        'ix_signals_direction',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_direction ON signals (direction)""",
    ),
    (
        'ix_signals_eval_due_at',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_eval_due_at ON signals (eval_due_at)""",
    ),
    (
        'ix_signals_generated_at',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_generated_at ON signals (generated_at)""",
    ),
    (
        'ix_signals_instrument_id',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_instrument_id ON signals (instrument_id)""",
    ),
    (
        'ix_signals_market',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_market ON signals (market)""",
    ),
    (
        'ix_signals_model_version',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_model_version ON signals (model_version)""",
    ),
    (
        'ix_signals_signal_type',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_signal_type ON signals (signal_type)""",
    ),
    (
        'ix_signals_status',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_status ON signals (status)""",
    ),
    (
        'ix_signals_symbol',
        'signals',
        """CREATE INDEX IF NOT EXISTS ix_signals_symbol ON signals (symbol)""",
    ),
    (
        'ix_trades_date',
        'trades',
        """CREATE INDEX IF NOT EXISTS ix_trades_date ON trades (date)""",
    ),
    (
        'ix_trades_instrument_id',
        'trades',
        """CREATE INDEX IF NOT EXISTS ix_trades_instrument_id ON trades (instrument_id)""",
    ),
    (
        'ix_trades_side',
        'trades',
        """CREATE INDEX IF NOT EXISTS ix_trades_side ON trades (side)""",
    ),
    (
        'ix_trades_symbol',
        'trades',
        """CREATE INDEX IF NOT EXISTS ix_trades_symbol ON trades (symbol)""",
    ),
    (
        'ix_trades_symbol_date',
        'trades',
        """CREATE INDEX IF NOT EXISTS ix_trades_symbol_date ON trades (symbol, date)""",
    ),
    (
        'ix_users_email',
        'users',
        """CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)""",
    ),
    (
        'ix_users_username',
        'users',
        """CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)""",
    ),
)


def upgrade() -> None:
    for _name, ddl in _TABLES:
        op.execute(ddl)
    for _name, _table, ddl in _INDEXES:
        op.execute(ddl)


def downgrade() -> None:
    for name, _table, _ddl in reversed(_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS "{name}"')
    for name, _ddl in reversed(_TABLES):
        op.execute(f'DROP TABLE IF EXISTS "{name}"')
