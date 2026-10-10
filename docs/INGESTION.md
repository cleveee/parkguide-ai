# Public-source ingestion

`parkguide.ingest.ingest_document` extracts one saved HTML/PDF without networking. `ingest_corpus(root, source_config, max_html=150, max_pdf=5)` collects a qualifying corpus and returns an explicit complete/incomplete summary. These numbers are target minima; the summary contains observed counts after cleaning and content-hash deduplication.

The live source configuration authorizes Yosemite, Yellowstone, and Grand Canyon visitor paths on the exact `www.nps.gov` host. PDFs outside those paths require an explicit path in `additional_public_pdf_paths`. External links, login/profile paths, people/staff directories, non-HTTPS URLs, traversal paths, and media assets are excluded. Static NPS source identity removes URL query strings and fragments; this crawler is not intended for query-dependent applications.

## Source and contact prerequisites

Before creating a network session, the crawler checks a configured contact address, confirmed domain approval, and a request rate between zero and one request per second. Robin confirmed instructor domain approval and explicitly requested the placeholder contact `parkguide-poc@example.com`. The user instruction permits this PoC run, but the placeholder does **not** establish the course's working-contact expectation. The corpus summary records that gap rather than describing it as a working address.

Robots rules are fetched, saved, parsed, and cached for the host before fetching documents. A 404 robots response permits access; other unsuccessful robots responses fail closed. Robots crawl delays/request rates can slow the entire crawler. Automatic redirects are disabled; every redirect target must pass the allowlist and robots checks before another request. Initial requests, redirects, robots requests, and bounded retries share one serial global start-rate limiter. Every ten attempts/accepted documents produce a compact progress record.

## Artifacts and extraction contract

- `data/raw/<raw_sha256>.<extension>`: original response bytes, written before parsing. Raw responses include failures/redirects for auditability.
- `data/raw/manifest.jsonl`: URL, UTC capture time, SHA-256, content type, byte count, HTTP status, and local raw path, appended before normalization.
- `data/documents.jsonl`: usable, deduplicated document records, saved incrementally for restartability.
- `data/corpus_summary.json`: actual HTML/PDF/table counts, rejected/duplicate/discovery/request counts, targets, limits, and coverage limitations.

Each document has a deterministic SHA-256 ID from its canonical URL; its content hash describes normalized text, while `raw_sha256` describes the unchanged response bytes. `normalized_text` joins block text with two newlines. Every block contains `text`, a string `heading_path`, `kind` (`paragraph` or `table`), and `[start,end)` character offsets into that exact canonical text. `normalized_blocks_json` serializes the block list for the database importer. Records also include title, page type, discovered date, capture time, and `has_table`.

HTML extraction removes navigation, scripts, footers, sidebars, and forms, then preserves heading hierarchy, paragraphs/lists, and Markdown tables. It expands `rowspan`/`colspan` cells into aligned columns and combines multiple header rows, for example `Summer 2026 / First Day`. PDF extraction uses selectable text and detected table cells, excludes detected table areas from body text to avoid duplication, and retains page numbers in heading paths. Empty or insufficient text does not count as a usable page. Email/phone patterns are redacted; path exclusions and these patterns do not constitute comprehensive name/PII detection. Publication/update/creation dates do not by themselves prove current applicability. Representative pages, PDFs, and tables still need human inspection.

Saved raw bytes are reloaded and hash-checked on resume. Existing qualifying document records are reused; unchanged normalized hashes are deduplicated. Rechunking and index migration should consume these saved normalized records with networking disabled, rather than invoke the crawler.

## Verification

Seventeen offline tests pass. They cover canonical IDs and stable normalized hashes; exact spans; heading/table/header preservation including merged cells; fixture PDF text/tables/page references; contact redaction; host/path/privacy boundaries; gates before any fetch; raw preservation before parsing; rate-limited retries; duplicate rejection; robots denial; blocked external redirects; and reuse without another request.

Manual inspection of the first live records identified NPS's `CS_Layout_Table` wrapper as page layout rather than a data table. The crawler was interrupted, the extractor and regression fixture were corrected, and all saved documents were re-extracted from unchanged raw bytes before capture resumed. The prior outputs remain in `data/diagnostics/layout-table-before-fix.jsonl`. The three explicit HTML table seeds then correctly retained campground, operating-date, and trail-distance tables, while ordinary visitor index pages stopped counting as tables.

The PDF fixture is a tiny, explicitly invented selectable-text/table PDF generated with a standard-library PDF writer; its presence requires no reportlab dependency. Fixture passes establish parser and crawler contracts, not actual NPS corpus coverage.

The completed capture at `2026-10-10T02:50:24Z` contains exactly **150 HTML and 5 PDF documents**, with 155 unique canonical IDs and normalized hashes: Yosemite 56, Yellowstone 40, and Grand Canyon 59. All 158 response records across the interrupted and resumed runs retain raw bytes. Every raw hash, document hash, and normalized block span was checked. Forty-five documents contain extracted table blocks; the three required campground, operating-date, and trail-distance pages were sampled and their substantive tables confirmed. This does not claim that all 45 table-bearing pages were fully reviewed.

Final table QA also found that Yellowstone's two-row seasonal headers needed merged-cell expansion. The regression test and extractor were corrected, then all 150 saved HTML records were re-extracted offline. Only the campground, operating-date, and Grand Canyon sunrise tables changed. Earlier normalized outputs are retained under `data/diagnostics/`. Final `data/documents.jsonl` SHA-256: `2d1285fed3c6b9960496999daa4dff4656df40c20c10d89c821c913db8d9589d`.

The Tonto distances PDF preserves numeric matrix cells but its rotated column labels have reversed glyph ordering. Use its original raw PDF for manual confirmation before relying on those labels in gold answers. The dated Yosemite guides are historical snapshots; their publication/creation metadata must not be presented as current schedules. One `.brf` Braille download was saved raw and rejected as an unsupported document type. None of these records artificially inflate usable HTML/PDF counts.
