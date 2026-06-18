from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine

from nlp_sql.auth.permissions import assert_sql_allowed
from nlp_sql.auth.tokens import AccessGrant
from nlp_sql.config import AppConfig
from nlp_sql.engine_map import build_engines
from nlp_sql.executor import run_query
from nlp_sql.safety import assert_read_only_sql


class DataService:
    """Read-only query execution behind authorization — no DDL/DML."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._engines: dict[str, Engine] | None = None

    def _engines_map(self) -> dict[str, Engine]:
        if self._engines is None:
            self._engines = build_engines(self._config)
        return self._engines

    def execute(
        self,
        database_id: str,
        sql: str,
        grant: AccessGrant,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        assert_read_only_sql(sql)
        assert_sql_allowed(grant, database_id, sql)

        engine = self._engines_map().get(database_id)
        if engine is None:
            raise ValueError(f"Unknown database_id: {database_id}")

        cols, rows = run_query(
            engine,
            sql,
            default_limit=self._config.execution.default_limit,
            max_rows=self._config.execution.max_rows,
            read_only=True,
        )
        return cols, rows
