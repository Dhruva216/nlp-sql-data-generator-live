from __future__ import annotations

import re
from rapidfuzz import fuzz

from nlp_sql.models import DatabaseCatalogEntry, RetrievalHit
from nlp_sql.registry import table_fqn


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _chunk_texts(entries: list[DatabaseCatalogEntry]) -> list[tuple[str, str | None, str, str]]:
    """Return list of (full_text, schema_name, table_name, db_id) for scoring."""
    chunks: list[tuple[str, str | None, str, str]] = []
    for e in entries:
        for t in e.tables:
            col_parts = [f"{c.name} {c.type_name}" for c in t.columns]
            col_blob = " ".join(col_parts)
            fq = table_fqn(e.db_id, t)
            full = f"{e.db_id} {fq} {t.name} {col_blob}"
            chunks.append((full, t.schema_name, t.name, e.db_id))
    return chunks


def search_keywords(
    query: str,
    catalog: list[DatabaseCatalogEntry],
    top_k: int,
    min_score: float,
) -> list[RetrievalHit]:
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    q_joined = " ".join(q_tokens)

    chunks = _chunk_texts(catalog)
    scored: list[tuple[float, str, str | None, str, str]] = []
    for full, schema, table, db_id in chunks:
        table_lower = table.lower()
        best = 0.0
        for tok in q_tokens:
            best = max(
                best,
                fuzz.partial_ratio(tok, full.lower()) / 100.0,
                fuzz.token_set_ratio(tok, table_lower) / 100.0,
            )
        doc_score = fuzz.token_set_ratio(q_joined, full.lower()) / 100.0
        score = max(best, doc_score * 0.85)
        if score >= min_score:
            scored.append((score, full, schema, table, db_id))

    scored.sort(key=lambda x: x[0], reverse=True)

    by_table: dict[tuple[str, str, str | None], tuple[float, str]] = {}
    for score, full, schema, table, db_id in scored:
        key = (db_id, table, schema)
        if key not in by_table or score > by_table[key][0]:
            by_table[key] = (score, full)

    ordered = sorted(by_table.items(), key=lambda x: x[1][0], reverse=True)[:top_k]
    hits: list[RetrievalHit] = []
    for (db_id, table, schema), (score, full) in ordered:
        hits.append(
            RetrievalHit(
                db_id=db_id,
                score=score,
                text=full,
                schema_name=schema,
                table_name=table,
            )
        )
    return hits
