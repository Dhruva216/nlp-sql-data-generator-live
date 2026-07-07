from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DatabaseEntry(BaseModel):
    id: str = Field(..., description="Stable id for this connection")
    uri: str


class RetrievalSettings(BaseModel):
    top_k: int = 24
    min_score: float = 0.12


class ExecutionSettings(BaseModel):
    max_rows: int = 500
    default_limit: int = 100
    read_only: bool = True


class LLMSettings(BaseModel):
    provider: str = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 1024
    custom_instructions: str | None = None


class ClientDatabaseGrant(BaseModel):
    id: str
    tables: str | list[str] = "*"


class AuthClientConfig(BaseModel):
    client_id: str
    client_secret: str
    databases: list[ClientDatabaseGrant]


class AuthSettings(BaseModel):
    token_ttl_seconds: int = 3600
    clients: list[AuthClientConfig] = Field(default_factory=list)


class ServerSettings(BaseModel):
    """HTTP server / chat frontend — browsers never receive database URIs."""

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ]
    )
    serve_chat_ui: bool = True


class AppConfig(BaseModel):
    databases: list[DatabaseEntry]
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)


def load_config(path: Path | None = None) -> AppConfig:
    env_path = os.environ.get("NLP_SQL_CONFIG")
    cfg_path = path or (Path(env_path) if env_path else Path("config.yaml"))
    if not cfg_path.is_file():
        example = Path("config.example.yaml")
        if example.is_file():
            raise FileNotFoundError(
                f"Missing {cfg_path}. Copy config.example.yaml to config.yaml and edit."
            )
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(raw)


def substitute_env_vars(value: str) -> str:
    if value.startswith("${") and value.endswith("}"):
        key = value[2:-1]
        found = os.environ.get(key)
        if not found:
            raise ValueError(f"Environment variable {key} not set for URI substitution")
        return found
    return value


def resolve_database_uri(uri: str) -> str:
    uri = uri.strip()
    if uri.startswith("${") and uri.endswith("}"):
        return substitute_env_vars(uri)
    return uri
