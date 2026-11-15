"""Run the three retrieval strategies with one OpenAI-compatible embedder."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .models import DocumentPage
from .store import ChromaVectorStore


def load_jsonl_corpus(path: Path) -> list[DocumentPage]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pages = [DocumentPage(r["document_id"], r.get("source", ""), int(r.get("source_line_start", 0)), r["text"],
                           {k: r[k] for k in ("unit_id", "chapter", "section", "language") if k in r}) for r in records]
    if not pages: raise ValueError(f"Corpus is empty: {path}")
    return pages


def load_questions(path: Path) -> list[dict]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or not questions: raise ValueError("Benchmark must be a non-empty JSON list")
    return questions


def validate_alignment(pages: list[DocumentPage], questions: list[dict]) -> None:
    source_names = {Path(page.source).name.lower() for page in pages}
    source_names.update({"books.txt"} if {page.document_id for page in pages} == {"gutenberg-6109"} else set())
    sections = {str(page.metadata.get("section", "")) for page in pages}
    languages = {str(page.metadata.get("language", "")) for page in pages}
    for question in questions:
        source_path = Path(str(question.get("source_path", ""))).name.lower()
        if source_path not in source_names:
            raise ValueError(f"Question {question.get('id')} source_path does not match corpus: {source_path}")
        if str(question.get("gold_page", "")) not in sections:
            raise ValueError(f"Question {question.get('id')} gold_page is absent from corpus sections")
        filters = question.get("filter") or {}
        if "section" in filters and str(filters["section"]) not in sections:
            raise ValueError(f"Question {question.get('id')} has an unknown section filter")
        if "language" in filters and str(filters["language"]) not in languages:
            raise ValueError(f"Question {question.get('id')} has an unknown language filter")
    if not {"dev", "test"}.issubset({q.get("split") for q in questions}):
        raise ValueError("Benchmark must contain both dev and test splits")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    corpus_path = Path(os.getenv("CORPUS_PATH", str(root / "data" / "processed" / "corpus.jsonl")))
    benchmark_path = Path(os.getenv("BENCHMARK_PATH", str(root / "data" / "question.json")))
    chroma_path = Path(os.getenv("CHROMA_PATH", str(root / "results" / "chroma")))
    results_path = root / "results"; results_path.mkdir(exist_ok=True)
    pages, questions = load_jsonl_corpus(corpus_path), load_questions(benchmark_path)
    validate_alignment(pages, questions)
    fixed_chunks = [c for p in pages for c in fixed_size(p, int(os.getenv("FIXED_SIZE", "1200")), int(os.getenv("FIXED_OVERLAP", "150")))]
    structure_chunks = [c for p in pages for c in by_paragraph(p, int(os.getenv("STRUCTURE_MAX_SIZE", "1400")))]
    embedder = MyEmbedder(os.getenv("BASE_MODEL", "")); store = ChromaVectorStore(str(chroma_path))
    traces: list[dict] = []
    strategy_chunks = {"A": fixed_chunks, "B": structure_chunks, "C": structure_chunks}
    query_vectors = {str(q["id"]): embedder.embed_query(q["question"]) for q in questions}
    embedded: dict[str, list[list[float]]] = {}
    timings: dict[str, float] = {}
    for strategy, chunks in strategy_chunks.items():
        started = time.perf_counter()
        cache_key = "A" if strategy == "A" else "B"
        if cache_key not in embedded:
            embedded[cache_key] = embedder.embed_documents([c.text for c in chunks])
        vectors = embedded[cache_key]
        store.upsert(strategy, chunks, vectors)
        timings[strategy] = time.perf_counter() - started
        for question in questions:
            filters = question.get("filter") if strategy == "C" else None
            result = evaluate_query(question, store.search(strategy, query_vectors[str(question["id"])], 3, filters))
            result.update({"strategy": strategy, "chunk_count": len(chunks), "ingest_seconds": timings[strategy]}); traces.append(result)
    (results_path / "traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = summarize(traces)
    (results_path / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
