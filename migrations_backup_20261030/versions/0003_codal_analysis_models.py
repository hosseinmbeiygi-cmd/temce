"""Add codal professional analysis models (Star Schema, SCD Type 2, Lineage)

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _create_table_if_not_exists(table_name, columns_sql, constraints_sql=""):
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {columns_sql}
            {constraints_sql}
        )
    """)

def upgrade() -> None:
    # ── Dimension Tables ────────────────────────────────────────────────
    _create_table_if_not_exists("dim_company", """
        company_id VARCHAR(50) PRIMARY KEY,
        symbol VARCHAR(50) UNIQUE NOT NULL,
        company_name VARCHAR(200),
        national_id VARCHAR(30),
        industry VARCHAR(100),
        sector VARCHAR(100),
        listing_date VARCHAR(20),
        fiscal_year_end VARCHAR(10),
        is_active BOOLEAN DEFAULT TRUE,
        metadata_ JSONB
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dim_company_symbol ON dim_company (symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dim_company_industry ON dim_company (industry)")

    _create_table_if_not_exists("dim_date", """
        date_id VARCHAR(20) PRIMARY KEY,
        gregorian_date VARCHAR(20),
        jalali_date VARCHAR(20),
        year INTEGER,
        quarter INTEGER,
        month INTEGER,
        is_month_end BOOLEAN DEFAULT FALSE,
        is_quarter_end BOOLEAN DEFAULT FALSE,
        is_year_end BOOLEAN DEFAULT FALSE
    """)

    _create_table_if_not_exists("dim_account", """
        account_id VARCHAR(50) PRIMARY KEY,
        canonical_code VARCHAR(50) UNIQUE NOT NULL,
        canonical_name VARCHAR(200) NOT NULL,
        account_category VARCHAR(50),
        statement_type VARCHAR(50),
        parent_account_id VARCHAR(50) REFERENCES dim_account(account_id),
        sign_nature VARCHAR(10) DEFAULT 'debit',
        display_order INTEGER
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dim_account_canonical_code ON dim_account (canonical_code)")

    _create_table_if_not_exists("dim_report_type", """
        report_type_id VARCHAR(20) PRIMARY KEY,
        code VARCHAR(20) UNIQUE NOT NULL,
        name VARCHAR(100),
        periodicity VARCHAR(20),
        description TEXT
    """)

    _create_table_if_not_exists("dim_document", """
        document_id VARCHAR(50) PRIMARY KEY,
        codal_tracking_id VARCHAR(100),
        company_id VARCHAR(50) REFERENCES dim_company(company_id),
        report_type_id VARCHAR(20) REFERENCES dim_report_type(report_type_id),
        publish_date VARCHAR(20),
        fiscal_period_end VARCHAR(20),
        correction_flag BOOLEAN DEFAULT FALSE,
        correction_number INTEGER DEFAULT 0,
        auditor_opinion VARCHAR(50),
        parser_version VARCHAR(20),
        raw_storage_path TEXT,
        file_hash VARCHAR(100),
        document_status VARCHAR(20) DEFAULT 'pending'
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dim_document_company ON dim_document (company_id)")

    # ── Fact Tables ─────────────────────────────────────────────────────
    _create_table_if_not_exists("fact_financials", """
        fact_id VARCHAR(50) PRIMARY KEY,
        company_id VARCHAR(50) REFERENCES dim_company(company_id),
        date_id VARCHAR(20) REFERENCES dim_date(date_id),
        account_id VARCHAR(50) REFERENCES dim_account(account_id),
        document_id VARCHAR(50) REFERENCES dim_document(document_id),
        report_type_id VARCHAR(20) REFERENCES dim_report_type(report_type_id),
        amount NUMERIC(18,2),
        currency VARCHAR(10) DEFAULT 'IRR',
        scale VARCHAR(10) DEFAULT 'RIALS',
        restatement_version INTEGER DEFAULT 1,
        valid_from VARCHAR(20),
        valid_to VARCHAR(20),
        is_current BOOLEAN DEFAULT TRUE,
        validation_status VARCHAR(20) DEFAULT 'pending',
        UNIQUE (company_id, date_id, account_id, document_id, restatement_version)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_financials_company ON fact_financials (company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_financials_date ON fact_financials (date_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_financials_account ON fact_financials (account_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_financials_document ON fact_financials (document_id)")

    _create_table_if_not_exists("fact_ratios", """
        id VARCHAR(50) PRIMARY KEY,
        company_id VARCHAR(50) REFERENCES dim_company(company_id),
        date_id VARCHAR(20) REFERENCES dim_date(date_id),
        ratio_code VARCHAR(50) NOT NULL,
        ratio_value DOUBLE PRECISION,
        numerator DOUBLE PRECISION,
        denominator DOUBLE PRECISION,
        analysis_version VARCHAR(20),
        calculation_status VARCHAR(20),
        metadata_ JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (company_id, date_id, ratio_code)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_ratios_company ON fact_ratios (company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_ratios_date ON fact_ratios (date_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_ratios_code ON fact_ratios (ratio_code)")

    _create_table_if_not_exists("fact_growth", """
        id VARCHAR(50) PRIMARY KEY,
        company_id VARCHAR(50) REFERENCES dim_company(company_id),
        date_id VARCHAR(20) REFERENCES dim_date(date_id),
        metric_code VARCHAR(50) NOT NULL,
        growth_yoy DOUBLE PRECISION,
        growth_qoq DOUBLE PRECISION,
        growth_ttm DOUBLE PRECISION,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (company_id, date_id, metric_code)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_growth_company ON fact_growth (company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_growth_date ON fact_growth (date_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_growth_metric ON fact_growth (metric_code)")

    _create_table_if_not_exists("fact_quality_signals", """
        id VARCHAR(50) PRIMARY KEY,
        company_id VARCHAR(50) REFERENCES dim_company(company_id),
        date_id VARCHAR(20) REFERENCES dim_date(date_id),
        signal_code VARCHAR(50) NOT NULL,
        signal_value DOUBLE PRECISION,
        severity VARCHAR(20),
        explanation TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_quality_signal_code ON fact_quality_signals (signal_code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_quality_company ON fact_quality_signals (company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_quality_date ON fact_quality_signals (date_id)")

    _create_table_if_not_exists("fact_text_analytics", """
        id VARCHAR(50) PRIMARY KEY,
        company_id VARCHAR(50) REFERENCES dim_company(company_id),
        document_id VARCHAR(50) REFERENCES dim_document(document_id),
        sentiment_score DOUBLE PRECISION,
        optimism_score DOUBLE PRECISION,
        uncertainty_score DOUBLE PRECISION,
        risk_phrases JSONB,
        topic_tags JSONB,
        model_version VARCHAR(20),
        created_at TIMESTAMP DEFAULT NOW()
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_fact_text_company ON fact_text_analytics (company_id)")

    # ── Supporting Tables ───────────────────────────────────────────────
    _create_table_if_not_exists("account_mappings", """
        mapping_id VARCHAR(50) PRIMARY KEY,
        source_label VARCHAR(300) NOT NULL,
        normalized_label VARCHAR(300),
        canonical_account_id VARCHAR(50) REFERENCES dim_account(account_id),
        account_type VARCHAR(50),
        industry_scope VARCHAR(100) DEFAULT '*',
        effective_from VARCHAR(20),
        effective_to VARCHAR(20),
        mapping_version VARCHAR(20),
        confidence_level DOUBLE PRECISION,
        approved_by VARCHAR(50),
        is_active BOOLEAN DEFAULT TRUE,
        UNIQUE (source_label, industry_scope)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_account_mappings_label ON account_mappings (source_label)")

    _create_table_if_not_exists("analysis_reports", """
        report_id VARCHAR(50) PRIMARY KEY,
        company_id VARCHAR(50) REFERENCES dim_company(company_id),
        symbol VARCHAR(50),
        report_type VARCHAR(20) DEFAULT 'professional',
        analysis_version VARCHAR(20),
        parser_version VARCHAR(20),
        mapping_version VARCHAR(20),
        scoring_version VARCHAR(20),
        report_date VARCHAR(20),
        fiscal_period VARCHAR(20),
        overall_score DOUBLE PRECISION,
        classification VARCHAR(20),
        summary JSONB,
        sections JSONB,
        alerts JSONB,
        report_pdf_path TEXT,
        report_status VARCHAR(20) DEFAULT 'draft',
        generated_by VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_analysis_reports_company ON analysis_reports (company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_analysis_reports_symbol ON analysis_reports (symbol)")

    # ── Governance Tables ───────────────────────────────────────────────
    _create_table_if_not_exists("data_lineage", """
        lineage_id VARCHAR(50) PRIMARY KEY,
        fact_id VARCHAR(50) REFERENCES fact_financials(fact_id),
        source_document_id VARCHAR(50) REFERENCES dim_document(document_id),
        source_section VARCHAR(100),
        source_row_label VARCHAR(300),
        source_cell_reference VARCHAR(50),
        extraction_rule VARCHAR(100),
        parser_version VARCHAR(20),
        mapping_version VARCHAR(20),
        created_at VARCHAR(30)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_data_lineage_fact ON data_lineage (fact_id)")

    _create_table_if_not_exists("audit_trail", """
        audit_id VARCHAR(50) PRIMARY KEY,
        user_id VARCHAR(50),
        action VARCHAR(50) NOT NULL,
        resource_type VARCHAR(50),
        resource_id VARCHAR(50),
        details JSONB,
        ip_address VARCHAR(50),
        timestamp TIMESTAMP DEFAULT NOW()
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_trail_user ON audit_trail (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_trail_action ON audit_trail (action)")


def downgrade() -> None:
    for tbl in ['audit_trail', 'data_lineage', 'analysis_reports', 'account_mappings',
                'fact_text_analytics', 'fact_quality_signals', 'fact_growth', 'fact_ratios',
                'fact_financials', 'dim_document', 'dim_report_type', 'dim_account',
                'dim_date', 'dim_company']:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
