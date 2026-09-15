from __future__ import annotations

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class SymbolRelationModel(TimestampMixin, Base):
    """Stores relationships / dependencies between symbols.

    Relation types include:
    - shared_board: same board members
    - same_group: same industry group
    - correlation: price correlation > threshold
    - holding: one symbol holds shares in another
    - parent_subsidiary: parent / subsidiary relationship
    - synthetic: derived from external data source
    """

    __tablename__ = "symbol_relations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol_a: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol_b: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Numeric strength of the relation (0..1 for correlation, etc.)
    strength: Mapped[float | None] = mapped_column(Float)

    # Human-readable label e.g. "مدیر مشترک: علی محمدی"
    label: Mapped[str | None] = mapped_column(String(200))

    # Arbitrary metadata as JSON
    metadata_json: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str | None] = mapped_column(String(100))
    detected_at: Mapped[DateTime | None] = mapped_column(DateTime)
