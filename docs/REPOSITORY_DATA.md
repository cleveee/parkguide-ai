# Public repository data snapshot

Robin authorized the database, reports, saved artifacts and non-secret project state to be pushed to [cleveee/parkguide-ai](https://github.com/cleveee/parkguide-ai) on October 10, 2026. This archive supplements the working Azure/Streamlit checkpoint `bdbba39`.

Snapshot captured: **2026-10-10T16:02:54.299798+00:00**. [The file manifest](../reports/DATA_SNAPSHOT.json) records SHA-256 and byte length for all **10,771 published files**, excluding the manifest itself. Later work belongs to a later snapshot.

## Included material

- `data/raw/`: saved NPS HTML/PDF bytes and capture provenance.
- `data/documents.jsonl`, `data/corpus_summary.json`: the 155-document processed corpus and saved measurements.
- `data/parkguide.sqlite`: a consistent, prebuilt database containing 155 documents, 5,405 chunks, 5,405 embedding rows and two index builds.
- `data/embedding-cache/`: **5,142** saved vector arrays and their paired metadata, including corpus and query reuse. Arrays were checked for finite float32 values, 1,536 dimensions and L2 normalization.
- `data/diagnostics/`, `data/evaluation/`: parsing diagnostics, source-authored gold drafts, diagnostic questions, dialogues and human-review instructions. Human review remains pending.
- `reports/`, `artifacts/`: reports, measured runs, conversation outputs, support reviews, the API ledger, index-build manifests, proof databases, Azure setup probes, dashboards, screenshots and execution records.
- The original working application source, configuration, dependency locks, tests, documentation and standalone HTML dashboard. Existing staged test-discovery/failure-state records are retained in `.pytest_cache/`.
- `docs/FRONTEND_BRIEF.md`, `docs/FRONTEND_REFERENCES.md` and `artifacts/frontend/`: design references and work-in-progress execution/review records. The new frontend source remains outside this archive commit while its implementation continues. Recorded checks describe their exact observed versions; they do not certify later edits.

`artifacts/builds/*.json` contain index provenance and remain versioned. Compiled application bundles and installed dependencies are excluded.

## Verification and exclusions

A brief read-only SQLite transaction held the source database stable for an exact-byte copy. The running database was not replaced or edited. The copy passed `PRAGMA integrity_check` and `PRAGMA foreign_key_check` with zero errors. Database SHA-256: `2e017b08ae4a358944716da3b62357b70c988bb61feebe62c39b9b0160feba5c`.

The frozen publication was scanned for the configured credential and common private-key/provider-token patterns, including archived ZIP contents. No credential was found. Individual files were checked against the 100 MiB publication limit. No embedding regeneration or paid API call was needed.

Excluded: `.env` and other credential-bearing environment files; virtual environments; `node_modules`; compiled output; Python bytecode; `.DS_Store`; lock/PID/socket files; transient SQLite WAL/SHM/journal files. `.env.example` contains placeholders only. There is no blanket exclusion for reports, JSONL traces, screenshots, saved vectors or index metadata.

Mutable logs, query caches and the API ledger may continue changing locally after capture. The manifest identifies the published bytes. One previously staged scratch inspection script deleted during ongoing work is retained as historical evidence. Completed JSONL records are preserved; any partial live-stream record removed from a snapshot is disclosed in the manifest. Historical model names, dates, results and human-review status remain unchanged.

## Using the saved state

Clone the repository, run `bash scripts/setup.sh`, create a private `.env` from `.env.example`, and run the working app as described in [README](../README.md). The corpus, database and stored vectors are already present; do not rerun ingestion or indexing to run this snapshot. Dependencies and the pinned local reranker still need installation/download, and live chat needs valid credentials for the configured Azure resource. Historical traces are evidence; no completed human review, sealed-test result, deployment or course submission is claimed.
