
from __future__ import annotations

from typing import Any

from mcp_server.server import mcp
from retrieval.hybrid import hybrid_search


@mcp.tool()
async def search_knowledge(
    query: str,
    top_k: int = 5,
    trust_level: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """
    Hybrid retrieval over governed OpsLens document chunks.

    Combines dense vector retrieval with PostgreSQL full-text retrieval,
    reciprocal-rank fusion, provenance-aware reranking, temporal/trust filters,
    and prompt-injection filtering.
    """
    hits = await hybrid_search(
        query=query,
        top_k=top_k,
        trust_level=trust_level,
        start_date=start_date,
        end_date=end_date,
        include_security_hits=False,
    )

    return {
        "ok": True,
        "tool": "search_knowledge",
        "data": [
            {
                "chunk_id": h.chunk_id,
                "document_id": h.document_id,
                "filename": h.filename,
                "content": h.content,
                "source_type": h.source_type,
                "trust_level": h.trust_level,
                "source_date": h.source_date,
                "dense_rank": h.dense_rank,
                "lexical_rank": h.lexical_rank,
                "rrf_score": h.rrf_score,
                "rerank_score": h.rerank_score,
                "injection_flag": h.injection_flag,
            }
            for h in hits
        ],
        "error": None,
        "meta": {
            "retrieval": "dense+lexical+RRF+provenance-rerank",
            "top_k": top_k,
        },
    }
