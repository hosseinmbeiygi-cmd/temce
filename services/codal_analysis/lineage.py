from __future__ import annotations

from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LineageEntry:
    fact_id: str
    source_document: str
    source_section: str | None = None
    source_row_label: str | None = None
    source_cell_reference: str | None = None
    extraction_rule: str | None = None
    parser_version: str | None = None
    mapping_version: str | None = None
    source_company: str | None = None
    source_report_type: str | None = None
    source_date: str | None = None
    raw_file_path: str | None = None
    transformation_chain: list[str] = field(default_factory=list)


@dataclass
class LineageGraph:
    entries: list[LineageEntry] = field(default_factory=list)

    def add_entry(self, entry: LineageEntry) -> None:
        self.entries.append(entry)

    def find_by_fact_id(self, fact_id: str) -> list[LineageEntry]:
        return [e for e in self.entries if e.fact_id == fact_id]

    def find_by_document(self, document_id: str) -> list[LineageEntry]:
        return [e for e in self.entries if e.source_document == document_id]


class TransformationTracker:
    def __init__(self):
        self._transformations: dict[str, list[str]] = {}

    def register(self, fact_id: str, transformation: str) -> None:
        if fact_id not in self._transformations:
            self._transformations[fact_id] = []
        self._transformations[fact_id].append(transformation)

    def get_chain(self, fact_id: str) -> list[str]:
        return self._transformations.get(fact_id, [])


def build_lineage(
    classified_data: dict[str, float],
    parser_version: str = "1.0",
    mapping_version: str = "1.0",
    document_id: str = "",
    source_section: str = "",
    symbol: str = "",
    report_type: str = "",
    report_date: str = "",
    raw_path: str = "",
) -> LineageGraph:
    graph = LineageGraph()
    for i, (label, _value) in enumerate(classified_data.items()):
        entry = LineageEntry(
            fact_id=f"fact_{symbol}_{report_date}_{i}",
            source_document=document_id,
            source_section=source_section,
            source_row_label=label,
            source_cell_reference=f"R{i}",
            extraction_rule="keyword_classification",
            parser_version=parser_version,
            mapping_version=mapping_version,
            source_company=symbol,
            source_report_type=report_type,
            source_date=report_date,
            raw_file_path=raw_path,
            transformation_chain=[f"extract_{label}", f"map_to_canonical_{i}"],
        )
        graph.add_entry(entry)
    return graph
