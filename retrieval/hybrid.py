
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from fastembed import TextEmbedding
from sqlalchemy import text

# IMPORTANT:
# Server-side retrieval uses the existing read-only MCP runtime DB engine
# directly. It must NOT import agent.mcp_bridge or mcp_server.server, otherwise
# the server imports itself recursively.
from mcp_server.runtime_tools import engine


load_dotenv()

MODEL_NAME = os.getenv(
    "OPSLENS_EMBEDDING_MODEL",
    "BAAI/bge-small-en-v1.5",
)

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?previous",
    r"reveal (the )?(system|developer) (prompt|instructions)",
    r"auto[- ]?approve",
    r"bypass (the )?(rules|policy|approval)",
    r"do not follow",
]


@dataclass
class RetrievalHit:
    chunk_id: str
    document_id: str
    filename: str
    content: str
    source_type: str | None
    trust_level: str | None
    source_date: str | None
    dense_rank: int | None
    lexical_rank: int | None
    rrf_score: float
    rerank_score: float
    injection_flag: bool
    blocked_from_context: bool


_MODEL = None


def _model():
    global _MODEL

    if _MODEL is None:
        _MODEL = TextEmbedding(
            model_name=MODEL_NAME
        )

    return _MODEL


def _vector_literal(values) -> str:
    return (
        "["
        + ",".join(
            f"{float(x):.8f}"
            for x in values
        )
        + "]"
    )


def _injection_flag(text_value: str) -> bool:
    low = (text_value or "").lower()

    return any(
        re.search(pattern, low)
        for pattern in INJECTION_PATTERNS
    )


def _trust_boost(
    trust_level: str | None,
) -> float:
    if trust_level == "internal":
        return 0.06

    if trust_level == "untrusted_external":
        return -0.12

    return 0.0


def _freshness_boost(
    source_date: str | None,
) -> float:
    # Tiny tie-breaker only. Recency must never dominate relevance.
    return 0.01 if source_date else 0.0


def _build_filter_sql(
    trust_level: str | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if trust_level:
        clauses.append(
            "trust_level = :trust_level"
        )
        params["trust_level"] = trust_level

    if start_date:
        clauses.append(
            "source_date >= CAST(:start_date AS date)"
        )
        params["start_date"] = start_date

    if end_date:
        clauses.append(
            "source_date < CAST(:end_date AS date)"
        )
        params["end_date"] = end_date

    if not clauses:
        return "", params

    return " AND " + " AND ".join(clauses), params


def _dense_candidates(
    query_vector: str,
    candidate_k: int,
    trust_level: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    filter_sql, params = _build_filter_sql(
        trust_level,
        start_date,
        end_date,
    )

    sql = text(
        f"""
        SELECT
            chunk_id,
            document_id,
            filename,
            content,
            source_type,
            trust_level,
            source_date,
            embedding <=> CAST(:query_vector AS vector)
                AS distance
        FROM knowledge.document_chunks
        WHERE 1 = 1
        {filter_sql}
        ORDER BY
            embedding <=> CAST(:query_vector AS vector)
        LIMIT :candidate_k
        """
    )

    params.update(
        {
            "query_vector": query_vector,
            "candidate_k": candidate_k,
        }
    )

    with engine.connect() as conn:
        rows = conn.execute(
            sql,
            params,
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def _lexical_candidates(
    query: str,
    candidate_k: int,
    trust_level: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    filter_sql, params = _build_filter_sql(
        trust_level,
        start_date,
        end_date,
    )

    sql = text(
        f"""
        SELECT
            chunk_id,
            document_id,
            filename,
            content,
            source_type,
            trust_level,
            source_date,
            ts_rank_cd(
                textsearch,
                websearch_to_tsquery(
                    'english',
                    :query
                )
            ) AS lexical_score
        FROM knowledge.document_chunks
        WHERE
            textsearch @@ websearch_to_tsquery(
                'english',
                :query
            )
        {filter_sql}
        ORDER BY lexical_score DESC
        LIMIT :candidate_k
        """
    )

    params.update(
        {
            "query": query,
            "candidate_k": candidate_k,
        }
    )

    with engine.connect() as conn:
        rows = conn.execute(
            sql,
            params,
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


async def hybrid_search(
    query: str,
    top_k: int = 5,
    candidate_k: int = 20,
    trust_level: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_security_hits: bool = False,
) -> list[RetrievalHit]:
    """
    Server-side hybrid retrieval.

    This function intentionally performs controlled DB reads directly through
    the dedicated read-only runtime engine. It does not re-enter MCP.

    Application/agent code should still call search_knowledge through MCP.
    """
    top_k = min(
        max(int(top_k), 1),
        20,
    )

    candidate_k = min(
        max(int(candidate_k), top_k),
        100,
    )

    vector = list(
        _model().embed(
            ["query: " + query]
        )
    )[0]

    query_vector = _vector_literal(
        vector
    )

    dense_rows = _dense_candidates(
        query_vector=query_vector,
        candidate_k=candidate_k,
        trust_level=trust_level,
        start_date=start_date,
        end_date=end_date,
    )

    lexical_rows = _lexical_candidates(
        query=query,
        candidate_k=candidate_k,
        trust_level=trust_level,
        start_date=start_date,
        end_date=end_date,
    )

    by_id: dict[str, dict[str, Any]] = {}

    for rank, row in enumerate(
        dense_rows,
        start=1,
    ):
        item = dict(row)
        item["dense_rank"] = rank
        item["lexical_rank"] = None

        by_id[item["chunk_id"]] = item

    for rank, row in enumerate(
        lexical_rows,
        start=1,
    ):
        chunk_id = row["chunk_id"]

        if chunk_id not in by_id:
            item = dict(row)
            item["dense_rank"] = None

            by_id[chunk_id] = item

        by_id[chunk_id]["lexical_rank"] = rank

    hits: list[RetrievalHit] = []

    for row in by_id.values():
        dense_rank = row.get(
            "dense_rank"
        )

        lexical_rank = row.get(
            "lexical_rank"
        )

        rrf = 0.0

        if dense_rank is not None:
            rrf += (
                1.0
                / (60 + dense_rank)
            )

        if lexical_rank is not None:
            rrf += (
                1.0
                / (60 + lexical_rank)
            )

        injection = _injection_flag(
            (
                f"{row.get('filename', '')} "
                f"{row.get('content', '')}"
            )
        )

        blocked = (
            injection
            and not include_security_hits
        )

        source_date = (
            None
            if row.get("source_date") is None
            else str(
                row.get("source_date")
            )
        )

        rerank = (
            rrf
            + _trust_boost(
                row.get("trust_level")
            )
            + _freshness_boost(
                source_date
            )
            - (
                0.30
                if injection
                else 0.0
            )
        )

        hits.append(
            RetrievalHit(
                chunk_id=row["chunk_id"],
                document_id=str(
                    row["document_id"]
                ),
                filename=row["filename"],
                content=row["content"],
                source_type=row.get(
                    "source_type"
                ),
                trust_level=row.get(
                    "trust_level"
                ),
                source_date=source_date,
                dense_rank=dense_rank,
                lexical_rank=lexical_rank,
                rrf_score=round(
                    rrf,
                    6,
                ),
                rerank_score=round(
                    rerank,
                    6,
                ),
                injection_flag=injection,
                blocked_from_context=blocked,
            )
        )

    hits.sort(
        key=lambda h: (
            h.rerank_score
        ),
        reverse=True,
    )

    safe_hits = [
        hit
        for hit in hits
        if (
            include_security_hits
            or not hit.blocked_from_context
        )
    ]

    return safe_hits[:top_k]
