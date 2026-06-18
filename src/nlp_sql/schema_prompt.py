from __future__ import annotations

from collections import defaultdict

from nlp_sql.models import DatabaseCatalogEntry, RetrievalHit
from nlp_sql.registry import table_sql_name


def build_schema_prompt(
    catalog: list[DatabaseCatalogEntry],
    hits: list[RetrievalHit],
) -> tuple[str, list[str]]:
    """Narrow catalog to hit tables and render DDL-like description per database."""
    wanted: dict[str, set[tuple[str | None, str]]] = defaultdict(set)
    db_order: list[str] = []
    for h in hits:
        if h.db_id not in db_order:
            db_order.append(h.db_id)
        wanted[h.db_id].add((h.schema_name, h.table_name))

    lines: list[str] = []
    db_ids_used: list[str] = []
    for e in catalog:
        if e.db_id not in wanted:
            continue
        if e.db_id not in db_ids_used:
            db_ids_used.append(e.db_id)
        lines.append(f"### Database id: `{e.db_id}` (dialect: {e.dialect})")
        for t in e.tables:
            key = (t.schema_name, t.name)
            if key not in wanted[e.db_id]:
                continue
            tsql = table_sql_name(e.dialect, e.db_id, t)
            col_lines = ", ".join(f"{c.name} ({c.type_name})" for c in t.columns)
            lines.append(f"- Table {tsql}: columns: {col_lines}")
    return "\n".join(lines), db_ids_used
