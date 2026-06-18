from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from nlp_sql.auth.tokens import AccessGrant
from nlp_sql.config import AppConfig
from nlp_sql.deps import get_app_config, get_grant
from nlp_sql.gateway.data_service import DataService

router = APIRouter()


class DataQueryRequest(BaseModel):
    database_id: str = Field(..., min_length=1)
    sql: str = Field(..., min_length=1, description="Read-only SELECT / WITH only")


class DataQueryResponse(BaseModel):
    database_id: str
    column_names: list[str]
    rows: list[dict[str, Any]]


@router.post("/query", response_model=DataQueryResponse)
def execute_read_query(
    body: DataQueryRequest,
    grant: AccessGrant = Depends(get_grant),
    config: AppConfig = Depends(get_app_config),
) -> DataQueryResponse:
    svc = DataService(config)
    try:
        cols, rows = svc.execute(body.database_id, body.sql, grant)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return DataQueryResponse(
        database_id=body.database_id,
        column_names=cols,
        rows=rows,
    )
