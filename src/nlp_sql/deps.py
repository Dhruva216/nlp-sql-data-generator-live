from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nlp_sql.auth.tokens import AccessGrant, resolve_token
from nlp_sql.config import AppConfig, load_config

_bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_app_config() -> AppConfig:
    env_path = os.environ.get("NLP_SQL_CONFIG")
    path = Path(env_path) if env_path else Path("config.yaml")
    return load_config(path)


def get_grant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AccessGrant:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer access token required")
    try:
        return resolve_token(credentials.credentials)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
