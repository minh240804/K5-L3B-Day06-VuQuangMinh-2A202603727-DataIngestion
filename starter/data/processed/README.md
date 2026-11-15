# Prepared corpus

`corpus.jsonl` contains 30 chapter-aware units derived from `../books.txt`.
The Gutenberg wrapper, table of contents and license boilerplate are excluded
from the units. Each record keeps the original source line range and the
chapter name used by the metadata filter experiment.

## Before sending text to an embedding API

1. Record the date the ebook was obtained in `manifest.json` as
   `source_accessed_at`.
2. Read the current Project Gutenberg License for ebook 6109 and verify that
   sending the text to the selected provider is permitted in the jurisdiction
   where the work is run.
3. Record the provider, model version, dimensions, retention period, training
   use, deletion process, input-token limit and price in the experiment log.
4. Keep the API key in `starter/.env`; never put it in this directory or in a
   trace file.
5. Use the same model and document/query embedding method for strategies A, B
   and C. Check the longest chunk against the provider's token limit before
   ingesting.

The current manifest intentionally marks provider approval as
`PENDING_PROVIDER_TERMS_CHECK` because no provider was specified.
