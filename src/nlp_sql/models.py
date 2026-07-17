from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type_name: str


@dataclass(frozen=True)
class TableInfo:
    schema_name: str | None
    name: str
    columns: tuple[ColumnInfo, ...]


@dataclass(frozen=True)
class DatabaseCatalogEntry:
    db_id: str
    dialect: str
    uri_masked: str
    tables: tuple[TableInfo, ...]


@dataclass(frozen=True)
class RetrievalHit:
    db_id: str
    score: float
    text: str
    schema_name: str | None
    table_name: str


@dataclass
class QueryResult:
    sql: str
    rows: list[dict[str, object]]
    column_names: list[str]
    database_ids_used: list[str]
    retrieval_context: list[RetrievalHit] = field(default_factory=list)
    explanation: str | None = None
    llm_usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
