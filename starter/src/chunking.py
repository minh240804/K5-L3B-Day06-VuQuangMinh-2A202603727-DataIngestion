"""Implement fixed-size and structure-aware chunking."""
import re
from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split text into overlapping windows and retain page metadata."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("size must be positive and overlap must satisfy 0 <= overlap < size")
    text = page.text.strip(); chunks: list[Chunk] = []; step = size - overlap
    for index, start in enumerate(range(0, len(text), step), 1):
        piece = text[start : start + size].strip()
        if piece:
            chunks.append(Chunk(f"{page.document_id}-p{page.page:04d}-a{index:03d}", page.document_id, page.source, page.page, piece,
                                {**page.metadata, "chunking": "fixed", "char_start": start, "char_end": start + len(piece)}))
        if start + size >= len(text): break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group paragraphs, split oversized paragraphs and retain metadata."""
    if max_size <= 0: raise ValueError("max_size must be positive")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page.text) if p.strip()]
    groups: list[str] = []; current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_size:
            if current: groups.append(current); current = ""
            groups.extend(paragraph[i:i + max_size].strip() for i in range(0, len(paragraph), max_size))
        elif not current: current = paragraph
        elif len(current) + 2 + len(paragraph) <= max_size: current += "\n\n" + paragraph
        else: groups.append(current); current = paragraph
    if current: groups.append(current)
    return [Chunk(f"{page.document_id}-p{page.page:04d}-b{i:03d}", page.document_id, page.source, page.page, text,
                  {**page.metadata, "chunking": "paragraph"}) for i, text in enumerate(groups, 1)]
