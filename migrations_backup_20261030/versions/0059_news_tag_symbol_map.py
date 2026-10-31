"""add news tag symbol mapping table

Revision ID: 0056
Revises: 0055
Create Date: 2026-09-18

Persian news taggers emit human tickers (خودرو، فولاد، وبانک…) whose
spelling varies (Arabic ي/ك vs Persian ی/ک, ZWNJ, spacing). This migration
adds ``news_tag_symbol_map`` — a persisted, auditable join table between
``news_tags.tag_value`` and the ``symbols``/``funds`` tables:

* ``resolved_type``/``resolved_id`` — the canonical target row.
  ``resolved_id`` is TEXT on purpose: ``symbols.id`` is BIGINT but
  ``funds.id`` is VARCHAR (verified live) so one polymorphic column must
  hold both as strings.
* ``match_type`` — how the mapping was established: ``manual`` overrides
  always win, then ``exact`` (direct symbol equality after Persian
  normalization), then ``arabic_fallback`` (normalized tag matches the
  Arabic-spelled symbol, e.g. وبانک → وبانك, فملی → فملي), ``unmapped``
  = no target found yet.
* ``confidence`` — 1.0 manual, 0.95 exact, 0.8 arabic_fallback
* ``normalized_tag`` — the Persian-normalized tag form, indexed so the
  mapping lookup is a single indexed query per page of tagged news.

The mapping is resolved lazily by the tag-mapping service; nothing in the
read path is forced through this table until a row exists.
"""

from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS news_tag_symbol_map (
        id              BIGSERIAL PRIMARY KEY,
        tag_value       VARCHAR(50)  NOT NULL,
        normalized_tag  VARCHAR(50)  NOT NULL,
        resolved_type   VARCHAR(10)  CHECK (resolved_type IN ('symbol', 'fund')),
        resolved_id     TEXT,
        match_type      VARCHAR(20)  NOT NULL DEFAULT 'unmapped'
                        CHECK (match_type IN ('manual', 'exact', 'arabic_fallback', 'unmapped')),
        confidence      NUMERIC(3,2) NOT NULL DEFAULT 0,
        mapped_at       TIMESTAMPTZ,
        created_at      TIMESTAMP    NOT NULL DEFAULT now(),
        CONSTRAINT uq_news_tag_symbol_map_tag UNIQUE (tag_value)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ntsm_normalized ON news_tag_symbol_map (normalized_tag)",
    "CREATE INDEX IF NOT EXISTS idx_ntsm_target ON news_tag_symbol_map (resolved_type, resolved_id)",
]


def upgrade() -> None:
    for stmt in _DDL:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS news_tag_symbol_map")
