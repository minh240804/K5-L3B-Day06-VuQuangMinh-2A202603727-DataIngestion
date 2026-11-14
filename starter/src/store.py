"""PostgreSQL + pgvector store implementation."""

from __future__ import annotations

import json
from typing import Any

from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        self.database_url = database_url
        self.dimensions = dimensions
        self._conn = None

    def _connection(self):
        if self._conn is None or self._conn.closed:
            try:
                import psycopg
            except ImportError as exc:  # pragma: no cover
                raise ImportError("Install psycopg[binary] to use PgVectorStore") from exc
            self._conn = psycopg.connect(self.database_url)
        return self._conn

    def create_schema(self) -> None:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    embedding vector({self.dimensions}) NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS chunks_strategy_idx ON chunks(strategy)")
            cur.execute("CREATE INDEX IF NOT EXISTS chunks_metadata_idx ON chunks USING gin(metadata)")
        conn.commit()

    @staticmethod
    def _vector(values: list[float]) -> str:
        return "[" + ",".join(str(float(value)) for value in values) + "]"

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(f"Embedding dimension mismatch: expected {self.dimensions}, got {len(vector)}")
        conn = self._connection()
        with conn.cursor() as cur:
            for chunk, vector in zip(chunks, vectors):
                metadata = dict(chunk.metadata)
                metadata.update({"document_id": chunk.document_id, "source": chunk.source, "page": chunk.page})
                cur.execute(
                    """INSERT INTO chunks
                    (chunk_id, strategy, document_id, source, page, text, metadata, embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::vector)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                      strategy=EXCLUDED.strategy, document_id=EXCLUDED.document_id,
                      source=EXCLUDED.source, page=EXCLUDED.page, text=EXCLUDED.text,
                      metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding""",
                    (chunk.chunk_id, strategy, chunk.document_id, chunk.source, chunk.page,
                     chunk.text, json.dumps(metadata), self._vector(vector)),
                )
        conn.commit()

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dimensions}, got {len(query_vector)}")
        if top_k <= 0:
            return []
        conn = self._connection()
        where = "strategy = %s"
        params: list[Any] = [strategy]
        if filters:
            where += " AND metadata @> %s::jsonb"
            params.append(json.dumps(filters))
        vector_value = self._vector(query_vector)
        query_params: list[Any] = [vector_value, *params, vector_value, top_k]
        with conn.cursor() as cur:
            cur.execute(f"""SELECT chunk_id, text, metadata,
                embedding <=> %s::vector AS distance
                FROM chunks WHERE {where}
                ORDER BY embedding <=> %s::vector LIMIT %s""", query_params)
            rows = cur.fetchall()
        return [
            {"chunk_id": row[0], "text": row[1], "metadata": row[2],
             "distance": float(row[3]), "score": 1.0 - float(row[3])}
            for row in rows
        ]