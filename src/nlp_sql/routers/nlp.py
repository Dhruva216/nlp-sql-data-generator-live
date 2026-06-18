from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from nlp_sql.auth.tokens import AccessGrant
from nlp_sql.config import AppConfig
from nlp_sql.deps import get_app_config, get_grant
from nlp_sql.pipeline import answer_request

router = APIRouter()


class NlpQueryRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Natural language question")


class NlpQueryResponse(BaseModel):
    sql: str
    column_names: list[str]
    rows: list[dict[str, Any]]
    database_ids_used: list[str]
    explanation: str | None = None
    schema_tables_used: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/query", response_model=NlpQueryResponse)
def nlp_query(
    body: NlpQueryRequest,
    grant: AccessGrant = Depends(get_grant),
    config: AppConfig = Depends(get_app_config),
) -> NlpQueryResponse:
    """LLM sees schema only; execution uses the data API layer with your token (server-side)."""
    try:
        result = answer_request(body.text, config=config, grant=grant)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    schema_tables_used = [
        {
            "database_id": h.db_id,
            "schema": h.schema_name,
            "table": h.table_name,
            "score": h.score,
        }
        for h in result.retrieval_context
    ]

    return NlpQueryResponse(
        sql=result.sql,
        column_names=result.column_names,
        rows=result.rows,
        database_ids_used=result.database_ids_used,
        explanation=result.explanation,
        schema_tables_used=schema_tables_used,
    )
