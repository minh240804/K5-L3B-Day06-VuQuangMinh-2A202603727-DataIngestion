"""Evaluate retrieval against documented gold source/page/evidence."""
import re
from pathlib import Path
from typing import Any


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source/page and enough gold evidence; keep hit@1 and hit@3 trace.

    Accept any documented alternative gold evidence. Do not infer human grounding
    or chunk coherence labels from exact string match.
    """
    gold_source = str(question.get("gold_source_id", ""))
    gold_page = str(question.get("gold_page", ""))
    evidence = str(question.get("evidence_quote", "")).strip().lower()
    alternatives = [str(item.get("evidence_quote", "")).strip().lower() for item in question.get("all_valid_gold_spans", []) if isinstance(item, dict)]
    alternatives = [value for value in alternatives if value] or [evidence]

    def hit(item: dict[str, Any]) -> bool:
        metadata = item.get("metadata", {})
        source_ok = Path(str(question.get("source_path", ""))).name.lower() == "books.txt" and str(metadata.get("document_id", "")) == "gutenberg-6109"
        page_ok = not gold_page or str(metadata.get("section", "")) == gold_page
        text = re.sub(r"\s+", " ", str(item.get("text", ""))).lower()
        evidence_ok = any(re.sub(r"\s+", " ", candidate) in text for candidate in alternatives if candidate)
        return source_ok and page_ok and evidence_ok

    return {"question_id": question.get("id"), "split": question.get("split"), "question": question.get("question"),
            "gold_source_id": gold_source, "gold_page": gold_page,
            "hit_at_1": bool(hits and hit(hits[0])), "evidence_hit_at_3": any(hit(item) for item in hits[:3]),
            "hits": hits}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    summary: dict[str, Any] = {}
    for strategy in sorted({trace.get("strategy", "unknown") for trace in traces}):
        subset = [trace for trace in traces if trace.get("strategy", "unknown") == strategy]
        summary[strategy] = {}
        for split in ("dev", "test"):
            rows = [trace for trace in subset if trace.get("split") == split]
            n = len(rows)
            summary[strategy][split] = {"n": n, "hit_at_1": sum(bool(row.get("hit_at_1")) for row in rows),
                                        "evidence_hit_at_3": sum(bool(row.get("evidence_hit_at_3")) for row in rows)}
    return summary
