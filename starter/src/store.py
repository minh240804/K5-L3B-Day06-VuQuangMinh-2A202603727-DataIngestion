"""Persistent Chroma vector store with metadata filtering."""
from typing import Any
from .models import Chunk


class ChromaVectorStore:
    def __init__(self, path: str, dimensions: int | None = None) -> None:
        import chromadb
        self.client = chromadb.PersistentClient(path=path)
        self.dimensions = dimensions

    def create_schema(self) -> None:
        return None

    def _collection(self, strategy: str):
        return self.client.get_or_create_collection(name=f"day6_{strategy}", metadata={"hnsw:space": "cosine"})

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors): raise ValueError("chunks and vectors must have equal length")
        if not chunks: return
        dimension = len(vectors[0])
        if any(len(vector) != dimension for vector in vectors): raise ValueError("all vectors must have same dimension")
        self.dimensions = self.dimensions or dimension
        collection = self._collection(strategy)
        collection.upsert(ids=[c.chunk_id for c in chunks], documents=[c.text for c in chunks], embeddings=vectors,
                          metadatas=[{"document_id": c.document_id, "source": c.source, "page": c.page,
                                      **{k: str(v) for k, v in c.metadata.items() if v is not None}} for c in chunks])

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where = None
        if filters:
            clauses = [{key: str(value)} for key, value in filters.items()]
            where = clauses[0] if len(clauses) == 1 else {"$and": clauses}
        result = self._collection(strategy).query(query_embeddings=[query_vector], n_results=top_k, where=where)
        hits = []
        for i, chunk_id in enumerate(result["ids"][0]):
            distance = result.get("distances", [[None]])[0][i]
            hits.append({"chunk_id": chunk_id, "text": result["documents"][0][i],
                         "score": None if distance is None else 1 - distance,
                         "metadata": result["metadatas"][0][i]})
        return hits
