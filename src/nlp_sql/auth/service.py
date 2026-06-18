from __future__ import annotations

from nlp_sql.auth.tokens import AccessGrant, DatabaseGrant, issue_token
from nlp_sql.config import AppConfig, AuthClientConfig


def client_grants(client: AuthClientConfig) -> tuple[DatabaseGrant, ...]:
    return tuple(
        DatabaseGrant(database_id=db.id, tables=db.tables) for db in client.databases
    )


def authenticate_client(
    config: AppConfig,
    client_id: str,
    client_secret: str,
) -> tuple[str, AccessGrant]:
    for client in config.auth.clients:
        if client.client_id == client_id and client.client_secret == client_secret:
            token, grant = issue_token(
                client_grants(client),
                ttl_seconds=config.auth.token_ttl_seconds,
            )
            return token, grant
    raise PermissionError("Invalid client credentials")
