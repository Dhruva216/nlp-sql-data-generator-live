from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine, Result

from nlp_sql.safety import assert_read_only_sql, ensure_limit, normalize_single_statement


GENDER_MAP = {
    254: "Male",
    "254": "Male",
    255: "Female",
    "255": "Female",
}


def sanitize_row_value(val: object, col_name: str = "") -> object:
    if isinstance(val, bytes):
        try:
            val = val.decode("utf-8")
        except UnicodeDecodeError:
            if len(val) <= 16:
                return "0x" + val.hex().upper()
            return f"<binary data: {len(val)} bytes>"

    if col_name.lower() in ("gender", "studentgender", "gendercode", "genderid"):
        if val in GENDER_MAP:
            return GENDER_MAP[val]

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
        # Use underlying DB-API connection/cursor to support nextset() for stored procedures
        raw_conn = getattr(conn.connection, "driver_connection", conn.connection)
        cursor = raw_conn.cursor()
        cursor.execute(final_sql)

        all_cols: list[str] = []
        all_rows: list[dict[str, object]] = []

        while True:
            desc = getattr(cursor, "description", None)
            if desc:
                cols = [d[0] for d in desc]
                try:
                    rows_raw = cursor.fetchall()
                except Exception:
                    rows_raw = []

                if rows_raw:
                    if not all_rows:
                        all_cols = list(cols)
                        for row in rows_raw[:max_rows]:
                            all_rows.append({cols[i]: sanitize_row_value(row[i], cols[i]) for i in range(len(cols))})
                    else:
                        for idx, row in enumerate(rows_raw[:max_rows]):
                            if idx < len(all_rows):
                                for i, col in enumerate(cols):
                                    if col not in all_rows[idx]:
                                        all_rows[idx][col] = sanitize_row_value(row[i], col)
                                        if col not in all_cols:
                                            all_cols.append(col)
                            else:
                                new_row = {col: sanitize_row_value(row[i], col) for i, col in enumerate(cols)}
                                all_rows.append(new_row)
                                for col in cols:
                                    if col not in all_cols:
                                        all_cols.append(col)

            try:
                has_next = getattr(cursor, "nextset", None)
                if not has_next or not has_next():
                    break
            except Exception:
                break

    return all_cols, all_rows
