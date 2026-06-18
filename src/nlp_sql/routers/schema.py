from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from nlp_sql.auth.tokens import AccessGrant
from nlp_sql.config import AppConfig
from nlp_sql.deps import get_app_config, get_grant
from nlp_sql.gateway.schema_service import SchemaService

router = APIRouter()


class SchemaSearchResponse(BaseModel):
    query: str
    tables: list[dict[str, Any]] = Field(
        description="Schema metadata only (columns/types). No row data or connection strings."
    )


@router.get("/search", response_model=SchemaSearchResponse)
def search_schema(
    q: str = Query(..., min_length=1, description="Keywords / natural language"),
    database_id: Optional[str] = Query(None, description="Optional filter to one database id"),
    grant: AccessGrant = Depends(get_grant),
    config: AppConfig = Depends(get_app_config),
) -> SchemaSearchResponse:
    svc = SchemaService(config)
    _hits, docs = svc.search(q, grant, database_id=database_id)
    return SchemaSearchResponse(query=q, tables=docs)
