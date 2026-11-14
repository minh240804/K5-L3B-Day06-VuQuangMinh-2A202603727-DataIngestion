"""Read and normalize PDF source pages while preserving traceability."""

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