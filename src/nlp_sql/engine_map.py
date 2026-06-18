from __future__ import annotations

from sqlalchemy.engine import Engine

from nlp_sql.config import AppConfig
from nlp_sql.registry import build_engine_for_db


def build_engines(config: AppConfig) -> dict[str, Engine]:
    ids = [d.id for d in config.databases]
    if len(ids) != len(set(ids)):
        raise ValueError("Each database id in config must be unique")

    out: dict[str, Engine] = {}
    for d in config.databases:
        out[d.id] = build_engine_for_db(d.id, d.uri)
    return out
