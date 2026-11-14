"""Lightweight retrieval evaluation helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _gold_values(question: dict[str, Any], key: str) -> set[Any]:
    value = question.get(key)
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return set(value)
    return {value}


def _is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    metadata = hit.get("metadata") or {}
    sources = _gold_values(question, "gold_source_id") | _gold_values(question, "gold_source")
    pages = _gold_values(question, "gold_page")
    source_values = {metadata.get("document_id"), metadata.get("source"), hit.get("chunk_id")}
    source_ok = not sources or bool(source_values & sources)
    page_ok = not pages or metadata.get("page") in pages
    if not (source_ok and page_ok):
        return False
    evidence = question.get("evidence_quote") or question.get("evidence_quotes")
    if not evidence:
        return True
    quotes = evidence if isinstance(evidence, (list, tuple, set)) else [evidence]
    text = " ".join(str(hit.get("text") or "").casefold().split())
    evidence_ok = any(" ".join(str(quote).casefold().split()) in text for quote in quotes)
    # Plain-text corpora use logical units rather than physical pages. When
    # the complete gold quote is present, it is stronger evidence than an
    # approximate unit label and remains traceable through the chunk text.
    return evidence_ok and (page_ok or evidence_ok)


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate Hit@1 and Evidence Hit@3 without inferring answer correctness."""
    hit_flags = [_is_hit(question, hit) for hit in hits[:3]]
    return {
        "id": question.get("id"),
        "split": question.get("split", "unknown"),
        "strategy": question.get("strategy", "unknown"),
        "question": question.get("question"),
        "hits": hits[:3],
        "hit_at_1": bool(hit_flags and hit_flags[0]),
        "evidence_hit_at_3": any(hit_flags),
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate counts and rates by strategy and dev/test split."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        groups[(str(trace.get("strategy", "unknown")), str(trace.get("split", "unknown")))].append(trace)
    result: dict[str, Any] = {"groups": {}}
    for (strategy, split), items in groups.items():
        total = len(items)
        hit1 = sum(bool(item.get("hit_at_1")) for item in items)
        hit3 = sum(bool(item.get("evidence_hit_at_3")) for item in items)
        result["groups"][f"{strategy}:{split}"] = {
            "strategy": strategy, "split": split, "total": total,
            "hit_at_1": hit1, "hit_at_1_rate": hit1 / total if total else 0.0,
            "evidence_hit_at_3": hit3, "evidence_hit_at_3_rate": hit3 / total if total else 0.0,
        }
    return result
