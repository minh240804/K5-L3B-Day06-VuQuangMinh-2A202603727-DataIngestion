"""Prepare the supplied Project Gutenberg text for the ingestion lab.

The script removes the Gutenberg wrapper, keeps the book's chapter boundaries,
and emits JSONL records with stable source and line metadata. It deliberately
does not call an embedding provider; provider terms and credentials must be
checked separately before running ingestion.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


CHAPTER_RE = re.compile(r"^CHAPTER\s+([IVXLCDM]+)\.?\s*$", re.I)
START_RE = re.compile(r"^\*\*\* START OF THE PROJECT GUTENBERG EBOOK .+ \*\*\*$")
END_RE = re.compile(r"^\*\*\* END OF THE PROJECT GUTENBERG EBOOK .+ \*\*\*$")


def nonempty(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def chapter_blocks(lines: list[str], line_offset: int = 0) -> list[tuple[str, str, list[str], int, int]]:
    starts = [i for i, line in enumerate(lines) if CHAPTER_RE.match(line.strip())]
    if not starts:
        raise ValueError("No chapter headings found")
    blocks = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        chapter_no = CHAPTER_RE.match(lines[start].strip()).group(1).upper()
        title_lines = []
        cursor = start + 1
        while cursor < end and len(title_lines) < 4:
            value = lines[cursor].strip()
            if value:
                title_lines.append(value)
            cursor += 1
        title = " ".join(title_lines)
        body = lines[start:end]
        blocks.append((chapter_no, title, body, start + 1 + line_offset, end + line_offset))
    return blocks


def split_paragraphs(lines: list[str]) -> list[tuple[str, int, int]]:
    paragraphs: list[tuple[str, int, int]] = []
    current: list[str] = []
    first = 0
    for index, line in enumerate(lines):
        value = line.strip()
        if value:
            if not current:
                first = index
            current.append(value)
        elif current:
            paragraphs.append((" ".join(current), first, index))
            current = []
    if current:
        paragraphs.append((" ".join(current), first, len(lines)))
    return paragraphs


def allocate(total: int, count: int) -> list[int]:
    base, extra = divmod(total, count)
    return [base + (1 if i < extra else 0) for i in range(count)]


def build_units(blocks: list[tuple[str, str, list[str], int, int]], target: int) -> list[dict]:
    counts = allocate(len(blocks), target)
    # Start with one unit per chapter, then distribute the remaining units by size.
    counts = [1] * len(blocks)
    for _ in range(target - len(blocks)):
        index = max(range(len(blocks)), key=lambda i: len("\n".join(blocks[i][2])) / counts[i])
        counts[index] += 1

    records: list[dict] = []
    for (chapter, title, lines, source_start, source_end), unit_count in zip(blocks, counts):
        paragraphs = split_paragraphs(lines)
        if not paragraphs:
            continue
        boundaries = allocate(len(paragraphs), unit_count)
        cursor = 0
        for unit_index, paragraph_count in enumerate(boundaries, 1):
            selected = paragraphs[cursor : cursor + paragraph_count]
            cursor += paragraph_count
            text = "\n\n".join(item[0] for item in selected).strip()
            start_line = source_start + selected[0][1]
            end_line = source_start + selected[-1][2] - 1
            records.append(
                {
                    "unit_id": f"gutenberg-6109-ch{chapter.lower()}-u{unit_index:02d}",
                    "document_id": "gutenberg-6109",
                    "title": "How to Study and Teaching How to Study",
                    "author": "Frank M. McMurry",
                    "source": "Project Gutenberg ebook #6109",
                    "source_url": "https://www.gutenberg.org/ebooks/6109",
                    "license": "Project Gutenberg License (verify current terms before API upload)",
                    "language": "English",
                    "release_year": 2004,
                    "chapter": "PREFACE" if chapter == "PREFACE" else f"CHAPTER {chapter}",
                    "section": "PREFACE" if chapter == "PREFACE" else f"CHAPTER {chapter}",
                    "source_line_start": start_line,
                    "source_line_end": end_line,
                    "text": text,
                }
            )
    if len(records) != target:
        raise ValueError(f"Expected {target} units, produced {len(records)}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/books.txt"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--units", type=int, default=30)
    args = parser.parse_args()

    raw_lines = args.input.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(raw_lines) if START_RE.match(line.strip())), None)
    end = next((i for i, line in enumerate(raw_lines) if END_RE.match(line.strip())), None)
    if start is None or end is None or end <= start:
        raise ValueError("Could not locate Gutenberg START/END markers")
    content = raw_lines[start + 1 : end]
    blocks = chapter_blocks(content, line_offset=start + 1)
    first_chapter = next(i for i, line in enumerate(content) if CHAPTER_RE.match(line.strip()))
    preface_index = next((i for i in range(first_chapter) if content[i].strip().upper() == "PREFACE"), None)
    if preface_index is not None:
        preface_body = content[preface_index:first_chapter]
        blocks.insert(0, ("PREFACE", "PREFACE", preface_body, preface_index + start + 2, first_chapter + start + 1))
    records = build_units(blocks, args.units)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = args.output_dir / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "corpus_id": "gutenberg-6109-prepared",
        "prepared_at": date.today().isoformat(),
        "source_file": str(args.input.as_posix()),
        "source_url": "https://www.gutenberg.org/ebooks/6109",
        "title": "How to Study and Teaching How to Study",
        "author": "Frank M. McMurry",
        "provider_upload_status": "PENDING_PROVIDER_TERMS_CHECK",
        "license": "Project Gutenberg License; verify current terms and local law before third-party API upload",
        "source_accessed_at": None,
        "unit_rule": "30 chapter-aware units, split only at paragraph boundaries; each unit retains source line range",
        "unit_count": len(records),
        "chapter_count": len(blocks),
        "unit_characters": {
            "min": min(len(record["text"]) for record in records),
            "max": max(len(record["text"]) for record in records),
        },
        "unit_words": {
            "min": min(len(record["text"].split()) for record in records),
            "max": max(len(record["text"].split()) for record in records),
        },
        "filter_field": "chapter",
        "filter_values": sorted({record["chapter"] for record in records}),
        "embedding_requirements": {
            "same_model_for_all_strategies": True,
            "document_query_compatibility_required": True,
            "max_chunk_tokens_must_be_checked_against_provider_limit": True,
            "api_key_must_stay_in_env": True,
            "provider_retention_and_training_terms_must_be_recorded": True,
        },
        "files": ["corpus.jsonl", "../books.txt"],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(records)} units to {corpus_path}")
    print(f"Wrote manifest to {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
