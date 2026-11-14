"""OpenAI-compatible embedding provider used by the ingestion pipeline."""

from __future__ import annotations

import os
from typing import Protocol, Any

from dotenv import load_dotenv


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Adapter around the OpenAI-compatible embeddings API with dimension checks."""

    def __init__(self, model_name: str | None = None) -> None:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required to create an embedder")
        self.model_name = (model_name or os.getenv("BASE_MODEL") or os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small")
        self.dimensions = 0
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("The OpenAI SDK is required; install it with `pip install openai`.") from exc
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        base_url = os.getenv("BASE_URL")
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)

    @staticmethod
    def _validate_vectors(vectors: list[list[float]]) -> int:
        if not vectors:
            raise ValueError("Embedding response contained no vectors")
        dimension = len(vectors[0])
        if dimension == 0 or any(len(vector) != dimension for vector in vectors):
            raise ValueError("Embedding response contains inconsistent dimensions")
        return dimension

    def _check_dimension(self, dimension: int) -> None:
        if self.dimensions == 0:
            self.dimensions = dimension
        elif dimension != self.dimensions:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dimensions}, got {dimension}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self.model_name, input=texts)
        vectors = [list(item.embedding) for item in response.data]
        dimension = self._validate_vectors(vectors)
        if len(vectors) != len(texts):
            raise ValueError(f"Embedding count mismatch: expected {len(texts)}, got {len(vectors)}")
        self._check_dimension(dimension)
        return vectors

    def embed_query(self, question: str) -> list[float]:
        response = self._client.embeddings.create(model=self.model_name, input=[question])
        vectors = [list(item.embedding) for item in response.data]
        dimension = self._validate_vectors(vectors)
        self._check_dimension(dimension)
        return vectors[0]