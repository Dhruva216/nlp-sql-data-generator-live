from __future__ import annotations

from nlp_sql.auth.tokens import AccessGrant
from nlp_sql.models import DatabaseCatalogEntry, TableInfo
from nlp_sql.safety import extract_referenced_tables


def filter_catalog(catalog: list[DatabaseCatalogEntry], grant: AccessGrant) -> list[DatabaseCatalogEntry]:
    allowed = grant.allowed_database_ids()
    out: list[DatabaseCatalogEntry] = []
    for entry in catalog:
        if entry.db_id not in allowed:
            continue
        tables: list[TableInfo] = []
        for t in entry.tables:
            if grant.allows_table(entry.db_id, t.name, t.schema_name):
                tables.append(t)
        if tables:
            out.append(
                DatabaseCatalogEntry(
                    db_id=entry.db_id,
                    dialect=entry.dialect,
                    uri_masked="",
                    tables=tuple(tables),
                )
            )
    return out


def assert_sql_allowed(grant: AccessGrant, database_id: str, sql: str) -> None:
    if database_id not in grant.allowed_database_ids():
        raise PermissionError(f"Database '{database_id}' is not permitted for this token")

    for schema_name, table_name in extract_referenced_tables(sql):
        if not grant.allows_table(database_id, table_name, schema_name):
            raise PermissionError(
                f"Table '{table_name}' is not permitted for database '{database_id}'"
            )
