from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from nlp_sql.config import AppConfig, resolve_database_uri
from nlp_sql.models import ColumnInfo, DatabaseCatalogEntry, TableInfo

_SYSTEM_SCHEMAS = frozenset(
    {
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "mysql",
        "performance_schema",
        "sys",
        "guest",
        "db_accessadmin",
        "db_accessoperator",
        "db_backupoperator",
        "db_datareader",
        "db_datawriter",
        "db_ddladmin",
        "db_denydatareader",
        "db_denydatawriter",
        "db_owner",
        "db_securityadmin",
    }
)


def _mask_password(uri: str) -> str:
    if "@" not in uri or "://" not in uri:
        return uri
    try:
        p = urlparse(uri)
        if p.password:
            netloc = p.netloc.replace(f":{p.password}@", ":****@")
            return p._replace(netloc=netloc).geturl()
    except Exception:
        pass
    return uri


def _ensure_sqlite_parent_dir(uri: str) -> None:
    if not uri.startswith("sqlite:///"):
        return
    path = uri.replace("sqlite:///", "", 1)
    if path in (":memory:",):
        return
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)


def _schema_allowed(name: str) -> bool:
    return name.lower() not in _SYSTEM_SCHEMAS


def build_engine_for_db(db_id: str, uri: str) -> Engine:
    resolved = resolve_database_uri(uri)
    _ensure_sqlite_parent_dir(resolved)
    connect_args: dict = {}
    if resolved.startswith("mssql"):
        connect_args["timeout"] = 30
    return create_engine(
        resolved,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args or {},
    )


def reflect_database(db_id: str, engine: Engine) -> DatabaseCatalogEntry:
    insp = inspect(engine)
    tables: list[TableInfo] = []

    if engine.dialect.name == "sqlite":
        for t in insp.get_table_names():
            cols: list[ColumnInfo] = []
            for c in insp.get_columns(t):
                tname = str(c.get("type", "text"))
                cols.append(ColumnInfo(name=c["name"], type_name=tname))
            tables.append(TableInfo(schema_name=None, name=t, columns=tuple(cols)))
    else:
        schema_names = [s for s in insp.get_schema_names() if _schema_allowed(s)]
        for schema in schema_names:
            for t in insp.get_table_names(schema=schema):
                cols_pg: list[ColumnInfo] = []
                for c in insp.get_columns(t, schema=schema):
                    tname = str(c.get("type", "text"))
                    cols_pg.append(ColumnInfo(name=c["name"], type_name=tname))
                tables.append(
                    TableInfo(
                        schema_name=schema,
                        name=t,
                        columns=tuple(cols_pg),
                    )
                )

    uri_display = _mask_password(str(engine.url))
    return DatabaseCatalogEntry(
        db_id=db_id,
        dialect=engine.dialect.name,
        uri_masked=uri_display,
        tables=tuple(tables),
    )


def load_catalog(config: AppConfig) -> list[DatabaseCatalogEntry]:
    out: list[DatabaseCatalogEntry] = []
    for d in config.databases:
        eng = build_engine_for_db(d.id, d.uri)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        out.append(reflect_database(d.id, eng))
    return out


def table_fqn(db_id: str, t: TableInfo) -> str:
    if t.schema_name:
        return f"{db_id}.{t.schema_name}.{t.name}"
    return f"{db_id}.{t.name}"


def table_sql_name(dialect: str, db_id: str, t: TableInfo) -> str:
    """How to refer to a table in generated SQL for this engine."""
    if t.schema_name:
        if dialect in ("postgresql",):
            return f'"{t.schema_name}"."{t.name}"'
        if dialect == "mssql":
            return f"[{t.schema_name}].[{t.name}]"
        return f"{t.schema_name}.{t.name}"
    if dialect == "sqlite":
        return f'"{t.name}"'
    if dialect == "mssql":
        return f"[{t.name}]"
    return t.name
