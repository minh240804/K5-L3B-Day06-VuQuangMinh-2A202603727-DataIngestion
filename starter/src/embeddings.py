"""Deterministic local embeddings; no corpus text leaves the machine."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


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
    """Feature-hashing local embedder with cosine-compatible unit vectors."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or "local-feature-hash-v1"
        self.dimensions = 384

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
        return [self._embed(text) for text in texts]

    def embed_query(self, question: str) -> list[float]:
        return self._embed(question)

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        lowered = text.casefold()
        features = re.findall(r"[a-z0-9]+", lowered)
        features.extend(lowered[i:i + 3] for i in range(max(0, len(lowered) - 2)))
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            values[index] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
