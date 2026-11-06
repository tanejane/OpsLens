
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://opslens_admin:opslens_local_dev@localhost:5432/opslens",
)

MODEL_NAME = os.getenv(
    "OPSLENS_EMBEDDING_MODEL",
    "BAAI/bge-small-en-v1.5",
)
EMBEDDING_DIM = 384

DATE_RE = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])(?:-([0-3]\d))?\b")


def infer_source_date(text_value: str):
    m = DATE_RE.search(text_value or "")
    if not m:
        return None
    year, month, day = m.group(1), m.group(2), m.group(3) or "01"
    return f"{year}-{month}-{day}"


def chunk_text(text_value: str, max_chars: int = 900, overlap_chars: int = 160):
    text_value = (text_value or "").strip()
    if not text_value:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text_value) if p.strip()]
    chunks = []
    buffer = ""

    for paragraph in paragraphs:
        candidate = paragraph if not buffer else buffer + "\n\n" + paragraph
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            chunks.append(buffer)

        if len(paragraph) <= max_chars:
            buffer = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(len(paragraph), start + max_chars)
            chunks.append(paragraph[start:end].strip())
            if end >= len(paragraph):
                break
            start = max(0, end - overlap_chars)
        buffer = ""

    if buffer:
        chunks.append(buffer)

    return chunks


def vector_literal(values):
    return "[" + ",".join(f"{float(x):.8f}" for x in values) + "]"


def main():
    print("=" * 92)
    print("OPSLENS PHASE 3D — BUILD HYBRID RETRIEVAL INDEX")
    print("=" * 92)
    print("Embedding model:", MODEL_NAME)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS knowledge.document_chunks (
                chunk_id text PRIMARY KEY,
                document_id text NOT NULL,
                filename text NOT NULL,
                source_type text,
                trust_level text,
                source_date date,
                chunk_index integer NOT NULL,
                content text NOT NULL,
                embedding_model text NOT NULL,
                embedding vector(384),
                textsearch tsvector GENERATED ALWAYS AS (
                    to_tsvector('english', coalesce(filename, '') || ' ' || coalesce(content, ''))
                ) STORED
            )
            """
        )

        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS idx_document_chunks_textsearch
            ON knowledge.document_chunks USING GIN (textsearch)
            """
        )

        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
            ON knowledge.document_chunks
            USING hnsw (embedding vector_cosine_ops)
            """
        )

        docs = conn.execute(
            text(
                """
                SELECT document_id, filename, content, source_type, trust_level
                FROM knowledge.documents
                ORDER BY document_id
                """
            )
        ).mappings().all()

    records = []
    texts = []

    for doc in docs:
        chunks = chunk_text(doc["content"])
        source_date = infer_source_date(
            f"{doc['filename']} {doc['content']}"
        )

        for idx, chunk in enumerate(chunks):
            records.append(
                {
                    "chunk_id": f"{doc['document_id']}::chunk::{idx}",
                    "document_id": str(doc["document_id"]),
                    "filename": doc["filename"],
                    "source_type": doc["source_type"],
                    "trust_level": doc["trust_level"],
                    "source_date": source_date,
                    "chunk_index": idx,
                    "content": chunk,
                }
            )
            texts.append("passage: " + doc["filename"] + "\n" + chunk)

    model = TextEmbedding(model_name=MODEL_NAME)
    vectors = list(model.embed(texts))

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE knowledge.document_chunks"))

        insert_sql = text(
            """
            INSERT INTO knowledge.document_chunks (
                chunk_id,
                document_id,
                filename,
                source_type,
                trust_level,
                source_date,
                chunk_index,
                content,
                embedding_model,
                embedding
            )
            VALUES (
                :chunk_id,
                :document_id,
                :filename,
                :source_type,
                :trust_level,
                CAST(:source_date AS date),
                :chunk_index,
                :content,
                :embedding_model,
                CAST(:embedding AS vector)
            )
            """
        )

        payload = []
        for record, vector in zip(records, vectors):
            payload.append(
                {
                    **record,
                    "embedding_model": MODEL_NAME,
                    "embedding": vector_literal(vector),
                }
            )

        conn.execute(insert_sql, payload)

    print(f"Documents indexed: {len(docs)}")
    print(f"Chunks indexed: {len(records)}")
    print("PASS: hybrid retrieval index built.")


if __name__ == "__main__":
    main()
