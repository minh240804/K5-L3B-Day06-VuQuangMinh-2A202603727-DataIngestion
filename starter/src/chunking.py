"""Chunking strategies for books, with traceable and conservative metadata.

The project uses three comparable strategies:

* A: fixed 500-character windows with 50-character overlap.
* B: paragraph-aware chunks, capped at 500 characters.
* C: the same paragraph-aware chunks as B; filtering is performed by the
  store only when the query supplies a filter.

Every chunk carries ``document_id`` (string), ``source`` (string), and ``page``
(integer) in metadata as well as on the :class:`Chunk` fields.  ``section`` is
included only when the extractor supplied it explicitly in ``DocumentPage``
metadata.  This makes section a useful book filter without inventing headings.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .models import Chunk, DocumentPage

DEFAULT_FIXED_SIZE = 500
DEFAULT_OVERLAP = 50


def _metadata(page: DocumentPage) -> dict[str, Any]:
    """Build metadata from source facts; do not infer missing values."""
    metadata: dict[str, Any] = {
        "document_id": page.document_id,
        "source": page.source,
        "page": page.page,
    }
    # A section is a trustworthy filter only when supplied by ingestion (for
    # example, from an explicit heading or a curated manifest).
    if page.metadata.get("section") is not None:
        metadata["section"] = page.metadata["section"]
    for key, value in page.metadata.items():
        if key not in metadata and value is not None:
            metadata[key] = value
    return metadata


def _chunk_id(page: DocumentPage, index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{page.document_id}:{page.page}:{index}:{digest}"


def _make_chunk(page: DocumentPage, index: int, text: str) -> Chunk:
    text = text.strip()
    return Chunk(
        chunk_id=_chunk_id(page, index, text),
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=_metadata(page),
    )


def fixed_size(
    page: DocumentPage,
    size: int = DEFAULT_FIXED_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Split a page into overlapping character windows.

    ``size`` and ``overlap`` are character counts. Empty/whitespace-only pages
    produce no chunks, while metadata always retains the physical page number.
    """
    if size <= 0:
        raise ValueError("size must be greater than zero")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and smaller than size")
    text = page.text.strip()
    if not text:
        return []
    step = size - overlap
    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(text):
        piece = text[start : start + size].strip()
        if piece:
            chunks.append(_make_chunk(page, index, piece))
            index += 1
        if start + size >= len(text):
            break
        start += step
    return chunks


def _split_oversized(paragraph: str, max_size: int) -> list[str]:
    """Split an oversized paragraph without inventing structure."""
    return [paragraph[start : start + max_size].strip() for start in range(0, len(paragraph), max_size)]


def by_paragraph(page: DocumentPage, max_size: int = DEFAULT_FIXED_SIZE) -> list[Chunk]:
    """Group source paragraphs up to ``max_size`` characters.

    Paragraph boundaries are taken from blank lines. An individual paragraph
    larger than the limit is split into contiguous character slices.
    """
    if max_size <= 0:
        raise ValueError("max_size must be greater than zero")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", page.text) if part.strip()]
    if not paragraphs:
        return []

    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_oversized(paragraph, max_size))
        elif not current:
            current = paragraph
        elif len(current) + 2 + len(paragraph) <= max_size:
            current = f"{current}\n\n{paragraph}"
        else:
            pieces.append(current)
            current = paragraph
    if current:
        pieces.append(current)
    return [_make_chunk(page, index, piece) for index, piece in enumerate(pieces)]


# Named presets make the benchmark configurations explicit and reproducible.
CHUNKING_CONFIGS = {
    "A": {"strategy": "fixed_size", "size": DEFAULT_FIXED_SIZE, "overlap": DEFAULT_OVERLAP},
    "B": {"strategy": "by_paragraph", "max_size": DEFAULT_FIXED_SIZE},
    "C": {"strategy": "by_paragraph", "max_size": DEFAULT_FIXED_SIZE, "filtering": "trusted metadata only"},
}