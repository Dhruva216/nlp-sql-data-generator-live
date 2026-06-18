from __future__ import annotations

import os
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from nlp_sql.auth.service import authenticate_client
from nlp_sql.auth.tokens import DatabaseGrant, issue_token
from nlp_sql.config import AppConfig
from nlp_sql.deps import get_app_config

router = APIRouter()


class TokenRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class AdminDatabaseGrant(BaseModel):
    database_id: str
    tables: str | list[str] = "*"


class AdminTokenRequest(BaseModel):
    databases: list[AdminDatabaseGrant]


@router.post("/token", response_model=TokenResponse)
def issue_client_token(
    body: TokenRequest,
    config: AppConfig = Depends(get_app_config),
) -> TokenResponse:
    """Exchange client credentials for an opaque capability token (no user profile in response)."""
    try:
        token, grant = authenticate_client(config, body.client_id, body.client_secret)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    return TokenResponse(
        access_token=token,
        expires_in=max(1, int(grant.expires_at - time.time())),
    )


@router.post("/token/admin", response_model=TokenResponse)
def issue_admin_token(
    body: AdminTokenRequest,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
    config: AppConfig = Depends(get_app_config),
) -> TokenResponse:
    """Issue a scoped token using admin secret (server-side only — not for LLM)."""
    admin = os.environ.get("NLP_SQL_ADMIN_SECRET", "")
    if not admin:
        raise HTTPException(status_code=503, detail="NLP_SQL_ADMIN_SECRET not configured")
    if x_admin_secret != admin:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    grants = tuple(
        DatabaseGrant(database_id=item.database_id, tables=item.tables)
        for item in body.databases
    )
    token, grant = issue_token(grants, ttl_seconds=config.auth.token_ttl_seconds)
    return TokenResponse(
        access_token=token,
        expires_in=config.auth.token_ttl_seconds,
    )
