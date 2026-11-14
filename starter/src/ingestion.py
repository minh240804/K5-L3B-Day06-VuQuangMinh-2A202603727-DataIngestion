"""Read and normalize source pages while preserving traceability."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while retaining paragraph boundaries."""
    text = unicodedata.normalize("NFKC", text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract one :class:`DocumentPage` per physical PDF page (1-based)."""
    reader = PdfReader(str(path))
    return [
        DocumentPage(
            document_id=document_id,
            source=source,
            page=number,
            text=normalize_text(pdf_page.extract_text() or ""),
        )
        for number, pdf_page in enumerate(reader.pages, start=1)
    ]


def load_text(path: Path, document_id: str, source: str, units: int = 35) -> list[DocumentPage]:
    """Load a plain-text book into stable logical units without inventing pages."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    start = raw.find("*** START OF THE PROJECT GUTENBERG EBOOK")
    end = raw.find("*** END OF THE PROJECT GUTENBERG EBOOK")
    body = raw[raw.find("\n", start) + 1 : end if end >= 0 else len(raw)] if start >= 0 else raw
    normalized = normalize_text(body)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", normalized) if part.strip()]
    if not paragraphs:
        return []
    target = max(1500, len(normalized) // max(1, units))
    pages: list[DocumentPage] = []
    current: list[str] = []
    size = 0
    page_no = 1
    for paragraph in paragraphs:
        if current and size + len(paragraph) + 2 > target:
            text = "\n\n".join(current)
            pages.append(DocumentPage(document_id, source, f"TXT-{page_no}", text, {"section": _section_for(text)}))
            page_no += 1
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        text = "\n\n".join(current)
        pages.append(DocumentPage(document_id, source, f"TXT-{page_no}", text, {"section": _section_for(text)}))
    return pages


def _section_for(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate and len(candidate) <= 90 and (candidate.isupper() or candidate.startswith("Appendix")):
            return candidate
    return "Main content"
