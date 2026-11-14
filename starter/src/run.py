"""Runnable ingestion smoke pipeline for strategies A, B and C."""

from __future__ import annotations

import os
from pathlib import Path

from .chunking import by_paragraph, fixed_size
from .chroma_store import ChromaStore
from .embeddings import MyEmbedder
from .ingestion import load_pdf


def main() -> None:
    """Ingest PDFs under ``data/`` into three persistent Chroma collections.

    The benchmark questions are intentionally kept outside this starter; this
    command validates extraction, chunking, embedding and persistence. It exits
    with a clear message when no corpus is present instead of fabricating data.
    """
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    pdfs = sorted(data_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF corpus found in {data_dir}. Add licensed PDFs and rerun.")
        return

    pages = []
    for path in pdfs:
        pages.extend(load_pdf(path, document_id=path.stem, source=str(path)))
    content_pages = [page for page in pages if page.text]
    if not content_pages:
        raise RuntimeError("The corpus contains no extractable text")

    embedder = MyEmbedder()
    strategies = {
        "A": [chunk for page in content_pages for chunk in fixed_size(page)],
        "B": [chunk for page in content_pages for chunk in by_paragraph(page)],
        "C": [chunk for page in content_pages for chunk in by_paragraph(page)],
    }
    for strategy, chunks in strategies.items():
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        store = ChromaStore(name=f"chunks_{strategy.lower()}")
        store.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=vectors,
            metadatas=[chunk.metadata for chunk in chunks],
        )
        print(f"{strategy}: persisted {len(chunks)} chunks ({embedder.dimensions} dimensions)")


if __name__ == "__main__":
    main()