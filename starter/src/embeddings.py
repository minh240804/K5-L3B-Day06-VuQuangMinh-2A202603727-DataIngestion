"""OpenAI-compatible embedding adapter."""
import os
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
    """Use OPENAI_API_KEY, BASE_URL and BASE_MODEL from the environment."""

    def __init__(self, model_name: str) -> None:
        from openai import OpenAI
        self.model_name = model_name or os.getenv("BASE_MODEL", "")
        api_key = os.getenv("OPENAI_API_KEY"); base_url = os.getenv("BASE_URL")
        if not api_key or not self.model_name: raise ValueError("OPENAI_API_KEY and BASE_MODEL are required")
        kwargs = {"api_key": api_key}
        if base_url: kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs); self.dimensions = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 64):
            response = self.client.embeddings.create(model=self.model_name, input=texts[start:start + 64])
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda item: item.index))
        if vectors: self.dimensions = len(vectors[0])
        return vectors

    def embed_query(self, question: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model_name, input=[question])
        vector = response.data[0].embedding; self.dimensions = len(vector); return vector
