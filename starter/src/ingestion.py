"""Read and normalize source data."""
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    from pypdf import PdfReader
    pages: list[DocumentPage] = []
    for page_number, pdf_page in enumerate(PdfReader(str(path)).pages, 1):
        text = normalize_text(pdf_page.extract_text() or "")
        pages.append(DocumentPage(document_id, source, page_number, text, {"has_text": bool(text)}))
    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without discarding useful structure."""
    value = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()
