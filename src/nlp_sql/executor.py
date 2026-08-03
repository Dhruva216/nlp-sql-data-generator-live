from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine, Result

from nlp_sql.safety import assert_read_only_sql, ensure_limit, normalize_single_statement


def sanitize_row_value(val: object) -> object:
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except UnicodeDecodeError:
            if len(val) <= 16:
                return "0x" + val.hex().upper()
            return f"<binary data: {len(val)} bytes>"
    return val


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
    final_sql = ensure_limit(
        sql,
        default_limit=default_limit,
        max_rows=max_rows,
        dialect=engine.dialect.name,
    )
    stmt = text(final_sql)

    with engine.connect() as conn:
        result: Result = conn.execute(stmt)
        all_cols: list[str] = []
        all_rows: list[dict[str, object]] = []

        while True:
            if getattr(result, "returns_rows", True):
                try:
                    cols = list(result.keys())
                    rows_raw = result.fetchmany(max_rows + 1)
                except Exception:
                    cols = []
                    rows_raw = []

                if rows_raw:
                    # Ignore lookup tables that only have 2 columns ending with ID/Name if we haven't found main data
                    if not all_rows:
                        all_cols = cols
                        for row in rows_raw[:max_rows]:
                            all_rows.append({cols[i]: sanitize_row_value(row[i]) for i in range(len(cols))})
                    else:
                        for idx, row in enumerate(rows_raw[:max_rows]):
                            if idx < len(all_rows):
                                for i, col in enumerate(cols):
                                    if col not in all_rows[idx]:
                                        all_rows[idx][col] = sanitize_row_value(row[i])
                                        if col not in all_cols:
                                            all_cols.append(col)
                            else:
                                new_row = {col: sanitize_row_value(row[i]) for i, col in enumerate(cols)}
                                all_rows.append(new_row)
                                for col in cols:
                                    if col not in all_cols:
                                        all_cols.append(col)

            try:
                if not hasattr(result, "nextset") or not result.nextset():
                    break
            except Exception:
                break

    return all_cols, all_rows
