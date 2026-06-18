from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine, Result

from nlp_sql.safety import assert_read_only_sql, ensure_limit, normalize_single_statement


def run_query(
    engine: Engine,
    sql: str,
    *,
    default_limit: int,
    max_rows: int,
    read_only: bool,
) -> tuple[list[str], list[dict[str, object]]]:
    if read_only:
        assert_read_only_sql(sql)
    final_sql = ensure_limit(sql, default_limit=default_limit, max_rows=max_rows)
    stmt = text(final_sql)

    with engine.connect() as conn:
        result: Result = conn.execute(stmt)
        cols = list(result.keys())
        rows_raw = result.fetchmany(max_rows + 1)

    if len(rows_raw) > max_rows:
        rows_raw = rows_raw[:max_rows]

    rows: list[dict[str, object]] = []
    for row in rows_raw:
        rows.append({cols[i]: row[i] for i in range(len(cols))})
    return cols, rows
