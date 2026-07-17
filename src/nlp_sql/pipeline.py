from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from nlp_sql.auth.tokens import AccessGrant, resolve_token
from nlp_sql.config import AppConfig, load_config
from nlp_sql.gateway.data_service import DataService
from nlp_sql.gateway.schema_service import SchemaService
from nlp_sql.llm_sql import generate_sql_sync
from nlp_sql.models import QueryResult


def _bootstrap_env() -> None:
    load_dotenv(override=False)
    if not os.environ.get("OPENAI_API_KEY") and Path(".env").is_file():
        load_dotenv(".env", override=True)


def answer_request(
    user_request: str,
    *,
    config_path: Path | None = None,
    config: AppConfig | None = None,
    grant: AccessGrant | None = None,
    access_token: str | None = None,
) -> QueryResult:
    """
    Schema-only LLM path + read-only execution via DataService.

    The LLM never receives connection strings, credentials, or row data during
  generation. Execution is scoped to the opaque access grant (not user identity).
    """
    _bootstrap_env()
    cfg = config or load_config(config_path)
    if grant is None:
        if not access_token:
            raise ValueError("access_token or grant is required")
        grant = resolve_token(access_token)

    schema_svc = SchemaService(cfg)
    data_svc = DataService(cfg)

    schema_text, db_ids, hits = schema_svc.schema_prompt_for_llm(user_request, grant)

    if not hits:
        return QueryResult(
            sql="",
            rows=[],
            column_names=[],
            database_ids_used=[],
            retrieval_context=[],
            explanation=(
                "No schema objects matched your keywords within this token's scope. "
                "Try broader terms or request access to additional tables."
            ),
        )

    if not db_ids:
        return QueryResult(
            sql="",
            rows=[],
            column_names=[],
            database_ids_used=[],
            retrieval_context=hits,
            explanation="Matched keywords but no schema entries are available for this token.",
        )

    db_id, sql, expl, usage = generate_sql_sync(user_request, schema_text, db_ids, cfg.llm)

    cols, rows = data_svc.execute(db_id, sql, grant)

    return QueryResult(
        sql=sql,
        rows=rows,
        column_names=cols,
        database_ids_used=[db_id],
        retrieval_context=hits,
        explanation=expl,
        llm_usage=usage,
    )
