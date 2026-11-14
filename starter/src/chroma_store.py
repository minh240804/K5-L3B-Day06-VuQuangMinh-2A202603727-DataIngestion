"""Persistent ChromaDB vector store."""

from __future__ import annotations

from typing import Any, Sequence

import chromadb


class ChromaStore:
    """Store and search chunks using a persistent Chroma collection."""

    def __init__(self, name: str = "chunks") -> None:
        self.client = chromadb.PersistentClient(path="chroma_data")
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        """Insert or replace records, requiring aligned input lists."""
        lengths = (len(ids), len(documents), len(embeddings), len(metadatas))
        if len(set(lengths)) != 1:
            raise ValueError(
                "ids, documents, embeddings, and metadatas must have the same length"
            )
        self.collection.upsert(
            ids=list(ids),
            documents=list(documents),
            embeddings=[list(vector) for vector in embeddings],
            metadatas=list(metadatas),
        )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the nearest chunks with cosine distance and similarity score."""
        if top_k <= 0:
            return []
        query: dict[str, Any] = {
            "query_embeddings": [list(query_embedding)],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if filters:
            query["where"] = filters
        result = self.collection.query(**query)

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        matches: list[dict[str, Any]] = []
        for index, chunk_id in enumerate(ids):
            distance = float(distances[index])
            matches.append(
                {
                    "chunk_id": chunk_id,
                    "text": documents[index] if index < len(documents) else None,
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "distance": distance,
                    "score": 1.0 - distance,
                }
            )
        return matches