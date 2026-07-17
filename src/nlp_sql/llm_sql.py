from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from nlp_sql.config import LLMSettings
from nlp_sql.safety import extract_sql_fenced


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Model did not return a JSON object")
    return json.loads(m.group(0))


def _is_local_url(base_url: str) -> bool:
    try:
        p = urlparse(base_url)
        return p.hostname in ("127.0.0.1", "localhost", None) or (p.hostname or "").endswith(
            ".local"
        )
    except Exception:
        return False


def _auth_headers(base_url: str) -> dict[str, str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key and not _is_local_url(base_url):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. For local OpenAI-compatible servers (Ollama, etc.) "
            "set base_url to http://127.0.0.1:...; an empty key is allowed for many local servers."
        )
    h: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def generate_sql_sync(
    user_request: str,
    schema_context: str,
    database_ids: list[str],
    settings: LLMSettings,
) -> tuple[str, str, str | None, dict[str, int]]:
    """Call OpenAI-compatible chat API; return (database_id, sql, explanation, usage)."""
    system_lines = [
        "You are a SQL author that only sees database SCHEMA (table and column names/types).",
        "You do NOT have direct database access and you must NEVER assume or invent row values.",
        "Your SQL will be submitted to a secure read-only API that enforces permissions and blocks "
        "INSERT, UPDATE, DELETE, DROP, ALTER, and all other write/DDL operations.",
        "Read the dialect name listed next to the Database ID in the schema context, and follow its syntax rules:",
        "  - If dialect is 'mssql' (SQL Server): Use T-SQL syntax. Use SELECT TOP N instead of LIMIT. Use T-SQL functions like DB_NAME() where appropriate.",
        "  - If dialect is 'sqlite': Use standard SQLite syntax and functions.",
        "Output a single JSON object only, no markdown, with keys:",
        '  "database_id" (one of the allowed ids), "sql" (one read-only SELECT or WITH query), '
        '  and optional "explanation" (short). Use only tables and columns from the schema context.',
        "Qualify table names EXACTLY as shown in the schema context. Do not prepend database IDs to table names. No SQL comments."
    ]
    if settings.custom_instructions:
        system_lines.append("\nAdditional Custom Rules and Examples:\n" + settings.custom_instructions)
    system = "\n".join(system_lines)
    dbs = ", ".join(f"`{d}`" for d in database_ids)
    user = (
        f"User request:\n{user_request}\n\n"
        f"Allowed database ids: {dbs}\n\n"
        f"Schema (keyword-matched subset):\n{schema_context}\n"
    )

    url = settings.base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = _auth_headers(settings.base_url)

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    usage = data.get("usage", {})
    usage_dict = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }

    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("Unexpected API response shape")

    try:
        obj = _parse_json_object(content)
    except json.JSONDecodeError:
        fenced = extract_sql_fenced(content)
        if fenced and database_ids:
            return database_ids[0], fenced, content[:2000], usage_dict
        raise

    db_id = str(obj.get("database_id", "")).strip()
    sql = str(obj.get("sql", "")).strip()
    if db_id not in database_ids:
        raise ValueError(f'Model chose unknown database_id "{db_id}"')
    if not sql:
        raise ValueError("Model returned empty sql")
    expl = obj.get("explanation")
    expl_str = str(expl) if expl is not None else None
    return db_id, sql, expl_str, usage_dict
