# Pipeline decisions

Recorded 2026-11-15.

- Embedding: OpenAI-compatible API using `OPENAI_API_KEY`, `BASE_URL`, and `BASE_MODEL` from `.env`; no mock fallback.
- Vector store: persistent Chroma at `results/chroma`, cosine distance, metadata filters.
- Strategy A: fixed-size character windows, default 1,200 characters and 150-character overlap.
- Strategy B: paragraph-aware grouping capped at 1,400 characters; oversized paragraphs are split.
- Strategy C: exactly B's chunks and embeddings, with the question's `filter` applied before search.
- Outputs: `results/traces.json` and `results/summary.json`.
- Benchmark identifiers: `gold_source_id` values such as `HOW_TO_STUDY_001` identify benchmark items, while corpus `document_id` is `gutenberg-6109`. Alignment is checked by `source_path`, section and language; retrieval hits require the corpus document ID and matching section.
- Corpus: keep `PREFACE` because T01 cites it. Metadata `section` uses `PREFACE` or `CHAPTER I` etc.; `language` uses `English`, matching the benchmark filters.
- Evidence: automated Hit@1/Hit@3 requires a full normalized evidence quote in one chunk. Quotes containing editorial `...` may need manual adjudication; the runner does not count them as automatic hits.
