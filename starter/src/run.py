"""Run the three retrieval strategies and benchmark them offline."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_text


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / ((math.sqrt(sum(x * x for x in a)) or 1) * (math.sqrt(sum(y * y for y in b)) or 1))


def _search(records: list[dict], query: list[float], query_text: str, top_k: int, filters: dict | None) -> list[dict]:
    candidates = records
    if filters:
        candidates = [r for r in records if all(r["metadata"].get(k) == v for k, v in filters.items())]
    stopwords = {"the", "a", "an", "of", "in", "on", "to", "what", "is", "are", "does", "how", "according", "document", "book", "and", "for", "with", "when", "why", "this", "that"}
    qwords = set(re.findall(r"[a-z0-9]+", query_text.casefold())) - stopwords
    def score(record: dict) -> float:
        words = set(re.findall(r"[a-z0-9]+", record["text"].casefold()))
        lexical = len(qwords & words) / (len(qwords) or 1)
        return _cosine(query, record["embedding"]) + 2.0 * lexical
    ranked = sorted(candidates, key=score, reverse=True)[:top_k]
    return [{k: r[k] for k in ("chunk_id", "text", "metadata")} | {"score": score(r)} for r in ranked]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    txt = next(data_dir.glob("*.txt"), None)
    if txt is None:
        raise FileNotFoundError("No .txt corpus found in starter/data")
    pages = load_text(txt, "SEQ_PROBLEM_SOLVING_001", str(txt))
    questions = json.loads((data_dir / "questions.json").read_text(encoding="utf-8"))
    embedder = MyEmbedder()
    strategies = {
        "A": [c for p in pages for c in fixed_size(p)],
        "B": [c for p in pages for c in by_paragraph(p)],
        "C": [c for p in pages for c in by_paragraph(p)],
    }
    traces = []
    for strategy, chunks in strategies.items():
        records = [{"chunk_id": c.chunk_id, "text": c.text, "metadata": {**c.metadata, "language": "English"}, "embedding": v} for c, v in zip(chunks, embedder.embed_documents([c.text for c in chunks]))]
        for question in questions:
            hits = _search(records, embedder.embed_query(question["question"]), question["question"], 3, question.get("filter") if strategy == "C" else None)
            trace = evaluate_query({**question, "strategy": strategy}, hits)
            traces.append(trace)
    results = root / "results"
    results.mkdir(exist_ok=True)
    (results / "traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    (results / "summary.json").write_text(json.dumps(summarize(traces), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summarize(traces), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
