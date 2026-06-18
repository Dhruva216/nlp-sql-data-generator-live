from __future__ import annotations

import re


COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT = re.compile(r"--[^\n]*")

# Blocked even as substrings in normalized SQL (word boundaries)
_FORBIDDEN = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|truncate|create|replace|merge|"
    r"grant|revoke|attach|detach|pragma|vacuum|reindex|"
    r"call|execute|exec|into\s+outfile|load\s+data"
    r")\b",
    re.IGNORECASE,
)

_FROM_JOIN = re.compile(
    r"\b(?:from|join)\s+"
    r'(?:"([^"]+)"|`([^`]+)`|\'([^\']+)\'|([\w.]+))',
    re.IGNORECASE,
)


def strip_sql_comments(sql: str) -> str:
    s = COMMENT_BLOCK.sub(" ", sql)
    s = LINE_COMMENT.sub(" ", s)
    return s


def normalize_single_statement(sql: str) -> str:
    s = strip_sql_comments(sql).strip().rstrip(";")
    return " ".join(s.split())


def assert_read_only_sql(sql: str) -> None:
    """Reject anything that is not a single read-only SELECT / WITH."""
    n = normalize_single_statement(sql)
    if ";" in n:
        raise ValueError("Multiple SQL statements are not allowed")
    low = n.lower()
    if not low.startswith("select") and not low.startswith("with"):
        raise ValueError("Only read-only SELECT (or WITH) queries are allowed")
    if _FORBIDDEN.search(n):
        raise ValueError("Query contains forbidden write or DDL keywords")


def assert_select_only(sql: str) -> None:
    """Alias for backward compatibility."""
    assert_read_only_sql(sql)


def ensure_limit(sql: str, default_limit: int, max_rows: int) -> str:
    n = normalize_single_statement(sql)
    low = n.lower()
    cap = min(default_limit, max_rows)
    if re.search(r"\blimit\s+\d+\b", low):
        return n + ";" if not n.endswith(";") else n
    return f"{n} LIMIT {cap}"


def extract_sql_fenced(text: str) -> str | None:
    m = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _split_table_ref(raw: str) -> tuple[str | None, str]:
    raw = raw.strip()
    if "." in raw:
        parts = raw.split(".")
        if len(parts) == 2:
            return parts[0], parts[1]
        if len(parts) >= 3:
            return parts[-2], parts[-1]
    return None, raw


def extract_referenced_tables(sql: str) -> list[tuple[str | None, str]]:
    """Tables appearing after FROM / JOIN (best-effort for permission checks)."""
    n = normalize_single_statement(sql)
    seen: set[tuple[str | None, str]] = set()
    out: list[tuple[str | None, str]] = []
    for m in _FROM_JOIN.finditer(n):
        raw = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
        raw = raw.strip()
        if not raw or raw.lower() in ("select", "where", "on", "as"):
            continue
        schema, table = _split_table_ref(raw)
        key = (schema.lower() if schema else None, table.lower())
        if key not in seen:
            seen.add(key)
            out.append((schema, table))
    return out
