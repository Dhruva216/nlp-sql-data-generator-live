from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
@dataclass(frozen=True)
class DatabaseGrant:
    database_id: str
    tables: str | list[str]  # "*" for all tables, or allowlisted names


@dataclass(frozen=True)
class AccessGrant:
    """Opaque capability — no user identity exposed to the LLM."""

    token_id: str
    expires_at: float
    databases: tuple[DatabaseGrant, ...]

    def allowed_database_ids(self) -> set[str]:
        return {g.database_id for g in self.databases}

    def tables_for(self, database_id: str) -> str | list[str] | None:
        for g in self.databases:
            if g.database_id == database_id:
                return g.tables
        return None

    def allows_table(self, database_id: str, table_name: str, schema_name: str | None = None) -> bool:
        scope = self.tables_for(database_id)
        if scope is None:
            return False
        if scope == "*":
            return True
        allowed = [t.lower() for t in scope]
        t_lower = table_name.lower()
        if t_lower in allowed:
            return True
        if schema_name:
            fq = f"{schema_name}.{table_name}".lower()
            if fq in allowed:
                return True
        for entry in allowed:
            if "." in entry:
                parts = entry.split(".", 1)
                if len(parts) == 2 and schema_name:
                    if parts[0] == schema_name.lower() and parts[1] == t_lower:
                        return True
                elif len(parts) == 2 and not schema_name and parts[1] == t_lower:
                    return True
        return False


import json
from pathlib import Path

@dataclass
class TokenStore:
    _by_token: dict[str, AccessGrant] = field(default_factory=dict)
    _db_path: Path = field(default_factory=lambda: Path(".tokens.json"))

    def _load(self) -> None:
        if not self._db_path.is_file():
            return
        try:
            data = json.loads(self._db_path.read_text(encoding="utf-8"))
            self._by_token.clear()
            for k, v in data.items():
                self._by_token[k] = AccessGrant(
                    token_id=v["token_id"],
                    expires_at=v["expires_at"],
                    databases=tuple(
                        DatabaseGrant(database_id=db["database_id"], tables=db["tables"])
                        for db in v["databases"]
                    ),
                )
        except Exception:
            pass

    def _save(self) -> None:
        try:
            data = {}
            for k, grant in self._by_token.items():
                data[k] = {
                    "token_id": grant.token_id,
                    "expires_at": grant.expires_at,
                    "databases": [
                        {"database_id": db.database_id, "tables": db.tables}
                        for db in grant.databases
                    ],
                }
            self._db_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def put(self, token: str, grant: AccessGrant) -> None:
        self._load()
        self._by_token[token] = grant
        self._save()

    def get(self, token: str) -> AccessGrant | None:
        self._load()
        grant = self._by_token.get(token)
        if grant is None:
            return None
        if time.time() > grant.expires_at:
            del self._by_token[token]
            self._save()
            return None
        return grant

    def revoke(self, token: str) -> None:
        self._load()
        if token in self._by_token:
            del self._by_token[token]
            self._save()


# Process-wide store (swap for Redis in production)
_STORE = TokenStore()


def get_token_store() -> TokenStore:
    return _STORE


def issue_token(
    databases: tuple[DatabaseGrant, ...],
    *,
    ttl_seconds: int = 3600,
) -> tuple[str, AccessGrant]:
    raw = secrets.token_urlsafe(32)
    grant = AccessGrant(
        token_id=raw[:12],
        expires_at=time.time() + ttl_seconds,
        databases=databases,
    )
    get_token_store().put(raw, grant)
    return raw, grant


def resolve_token(token: str) -> AccessGrant:
    grant = get_token_store().get(token.strip())
    if grant is None:
        raise PermissionError("Invalid or expired access token")
    return grant
