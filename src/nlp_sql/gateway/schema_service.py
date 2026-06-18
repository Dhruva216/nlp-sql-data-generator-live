from __future__ import annotations

from typing import Any

from nlp_sql.auth.permissions import filter_catalog
from nlp_sql.auth.tokens import AccessGrant
from nlp_sql.config import AppConfig
from nlp_sql.engine_map import build_engines
from nlp_sql.keyword_search import search_keywords
from nlp_sql.models import DatabaseCatalogEntry, RetrievalHit
from nlp_sql.registry import load_catalog
from nlp_sql.schema_prompt import build_schema_prompt


class SchemaService:
    """Schema metadata only — never returns row data or connection secrets."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._catalog_cache: list[DatabaseCatalogEntry] | None = None

    def _catalog(self) -> list[DatabaseCatalogEntry]:
        if self._catalog_cache is None:
            self._catalog_cache = load_catalog(self._config)
        return self._catalog_cache

    def refresh_catalog(self) -> None:
        self._catalog_cache = None
        build_engines(self._config)

    def search(
        self,
        query: str,
        grant: AccessGrant,
        *,
        database_id: str | None = None,
    ) -> tuple[list[RetrievalHit], list[dict[str, Any]]]:
        catalog = filter_catalog(self._catalog(), grant)
        if database_id:
            catalog = [e for e in catalog if e.db_id == database_id]

        hits = search_keywords(
            query,
            catalog,
            top_k=self._config.retrieval.top_k,
            min_score=self._config.retrieval.min_score,
        )
        return hits, self.hits_to_schema_documents(hits, catalog)

    def hits_to_schema_documents(
        self,
        hits: list[RetrievalHit],
        catalog: list[DatabaseCatalogEntry],
    ) -> list[dict[str, Any]]:
        """Public schema DTO — no URIs, no row samples."""
        wanted = {(h.db_id, h.schema_name, h.table_name) for h in hits}
        docs: list[dict[str, Any]] = []
        for entry in catalog:
            for t in entry.tables:
                key = (entry.db_id, t.schema_name, t.name)
                if key not in wanted:
                    continue
                docs.append(
                    {
                        "database_id": entry.db_id,
                        "dialect": entry.dialect,
                        "schema": t.schema_name,
                        "table": t.name,
                        "columns": [
                            {"name": c.name, "type": c.type_name} for c in t.columns
                        ],
                    }
                )
        return docs

    def schema_prompt_for_llm(
        self,
        query: str,
        grant: AccessGrant,
    ) -> tuple[str, list[str], list[RetrievalHit]]:
        catalog = filter_catalog(self._catalog(), grant)
        hits = search_keywords(
            query,
            catalog,
            top_k=self._config.retrieval.top_k,
            min_score=self._config.retrieval.min_score,
        )
        text, db_ids = build_schema_prompt(catalog, hits)
        return text, db_ids, hits
