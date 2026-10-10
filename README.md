# ParkGuide local RAG proof of concept

ParkGuide answers questions about Yosemite, Yellowstone, and Grand Canyon from saved official NPS sources. The local application, Azure embeddings, retrieval pipeline, and real evaluation runners are implemented. The course benchmark awaits human verification of the 40 source-authored gold drafts.

The three workstreams are [corpus/database, retrieval/chat, and evaluation](docs/PLAN.md). Python, one SQLite file, NumPy exact search, BM25, and Streamlit keep the application simple. One existing Azure resource generates embeddings with `text-embedding-3-small` and answers/claim review with `gpt-6-luna-2026-09-22`; a pinned CrossEncoder reranks locally. There is no application deployment or cloud database.

## Run locally

The current session already serves [ParkGuide](http://127.0.0.1:8511). To start it again:

```sh
cd /Users/robin/Build/Personal/parkguide-ai
.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false
```

Choose **Park** before chatting. The selected park is clearly shown above the conversation, and every search is filtered to its saved NPS sources. Changing parks starts a fresh conversation. Missing support leads to a refusal; every delivered claim needs cited source passages and checked verbatim witnesses. Live conditions and personal records cannot be verified from the saved database. [Park scope and verification](docs/PARK_SCOPE.md) describes the enforced boundaries and AI-review limits.

**Sources used** appears below cited answers with official page links, source/capture dates, and expandable saved excerpts. Repeated pages share a card while retaining each cited passage; PDF passages also link to their recorded starting page. Expand **Search trace and other retrieved passages** for query, filter, review and calculation details. **New conversation** clears history within the selected park. Optional search/reranking controls are inside the sidebar's **Search settings**. [Source-link details](docs/SOURCE_LINKS.md) explain attribution.

Select Yosemite and ask “What distance should I keep from a bear outside developed areas?”, then “What should I do if that bear is in a developed area?” Ask about Yellowstone to see the scope refusal, or an imaginary Blue Lantern Lagoon submarine tour to see a source-gap refusal. Select another park to begin its separate conversation. These examples are non-gold diagnostics.

## Setup and verification

Use Python 3.12. The verified runtime here is Python 3.12.14 on macOS ARM64:

```sh
PARKGUIDE_PYTHON=/Users/robin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 bash scripts/setup.sh
.venv/bin/parkguide doctor
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

Elsewhere use `PARKGUIDE_PYTHON=python3.12 bash scripts/setup.sh`. Setup installs `requirements-full.lock`, initializes SQLite without deleting existing rows, and makes no model calls. `PARKGUIDE_CORE_ONLY=1` selects `requirements-core.lock`; reranking then requires the optional packages. Locks were resolved on macOS ARM64; verify compatibility elsewhere. Pinned model weights download on first use and remain cached.

Create a private `.env` from `.env.example`, mode `0600`; this machine is already configured. Never print or commit keys. [Azure verification](docs/AZURE.md) records the existing ReviewDoc dev/staging resource. The same Azure endpoint and key serve both deployment names. The ignored `.env` needs only the four variables in `.env.example`; there is no direct OpenAI API configuration or fallback. [Generation documentation](docs/GENERATION.md) records the verified Luna snapshot and request settings. The database and UI stay local.

## Pipeline commands

The frozen corpus contains **150 HTML documents, five PDFs, and 45 table-bearing documents**. Fixed chunks: **1,698**; structure-aware chunks: **3,707**. Both retain source spans and valid normalized float32 Azure vectors of dimension 1,536. See `data/corpus_summary.json` and `artifacts/builds/` for hashes.

```sh
.venv/bin/parkguide ingest
.venv/bin/parkguide index --strategy fixed
.venv/bin/parkguide index --strategy structure
.venv/bin/parkguide search "Yosemite campsite check-in time" --mode bm25
.venv/bin/parkguide chat "Can I use a drone in Yellowstone?" --mode hybrid
.venv/bin/parkguide migrate
```

Ingestion resumes saved data, follows the public allowlist/parsed robots rules, limits requests to one per second, and saves raw bytes before parsing. Embedding builds reuse verified text/config caches. New source text and chat calls incur API charges. Migration runs on a database copy, removes obsolete rows, and records zero-network proof while preserving the main baselines. Details: [ingestion](docs/INGESTION.md), [retrieval](docs/RETRIEVAL.md).

## Development evaluation

All 40 gold drafts were authored and sealed **before live chatbot answers**. They remain human review pending. Review [GOLD_REVIEW.md](data/evaluation/GOLD_REVIEW.md), confirm/correct the sources and expected answers in `gold-drafts.jsonl`, and record the actual verifier/date. Agents cannot fill those fields as a human.

Separate diagnostics contain 12 questions and six three-turn dialogues carrying actual preceding assistant responses. The six-variant initial run isolates retrieval representation, chunking, hybrid fusion, and reranking. Subsequent candidate runs preserve failures and corrections. [Status](docs/STATUS.md), [iterations](docs/ITERATIONS.md), [diagnostic analysis](docs/DIAGNOSTIC_ANALYSIS.md), and [evaluation design](docs/EVALUATION.md) distinguish actual measurements, lexical checks, AI semantic proposals, and human review.

```sh
.venv/bin/python scripts/run_development.py
.venv/bin/python scripts/run_selected.py
.venv/bin/python scripts/run_safeguard_checks.py
.venv/bin/python scripts/check_park_scope.py
.venv/bin/parkguide budget
.venv/bin/parkguide reports
```

`run_development.py` runs all six variants and six conversations and updates report pointers. Its historical B3 label denotes the reranking ablation; the historical selected B3 used reranking off. The current park-selector UI uses the existing local reranker by default; the model and guard changes are separate from that older ablation. Add `--rerank` to CLI chat/dialogues for the optional ablation. Individual commands are `parkguide eval data/evaluation/diagnostic.jsonl --diagnostic` and `parkguide dialogues data/evaluation/dialogues.jsonl --mode hybrid`. Use `scripts/analyze_diagnostics.py --help` for paired analysis of a completed six-variant run. Lexical fact coverage is a troubleshooting heuristic, **not answer accuracy**. Mechanical citation checks do not establish semantic support. Evidence judgments can omit valid alternative pages.

The legacy CLI/evaluation path retains cross-park diagnostic behavior when no explicit selection is supplied. The UI always requires a selected park. `check_park_scope.py` runs six new three-turn selected-park conversations and three singleton source-gap checks, saving every actual attempt under `artifacts/park-scope/`. Its operational checks are separate from semantic accuracy and the historical seven-stage evaluation.

After actual human verification, run `parkguide gold-split data/evaluation/gold-drafts.jsonl` to freeze the seeded 24/16 split. Tune only on `dev.jsonl`. Run `.venv/bin/python scripts/prepare_final_review.py` to create an unapproved template. After reviewing development evidence, save `dev-acceptance.json` with the real verifier/date, reviewed gates, `accepted_dev_hash`, and `accepted_snapshot_hash` matching `evaluation.final_snapshot` for the exact B0–B3 batch. Then run `parkguide final-test` once. Acceptance hashes live source/chunk/vector rows as well as code/config/build manifests, so deletion or mutation invalidates it. Original authoring seals are immutable; gold-split records a separate human-reviewed revision after real verification. An unchanged interrupted batch skips completed pairs and preserves human annotations. The formal test is currently neither created nor consumed.

## Evidence and limits

[Run dashboard](http://127.0.0.1:8512/) collects all seven stages, source coverage, technical specs, token/cost breakdowns and review status. Its [standalone HTML](dashboard/index.html) works offline; [dashboard instructions](docs/DASHBOARD.md) explain rebuilding, serving and exporting the snapshot.

[Status](docs/STATUS.md) links the results. [Reports 00–07](reports/00_proposal.md) derive from actual corpus, builds, migration, usage, and runs. [Demo instructions](docs/DEMO.md) cover an 8–10-minute classroom walkthrough. The [active implementation prompt](docs/IMPLEMENTATION_PROMPT.md) preserves the persistent workflow and gates.

Raw data, SQLite, `.env`, model/embedding caches, and artifacts are ignored by Git and live on this machine. Preserve those folders with the code to reproduce this snapshot; later NPS content can change. Git is local on `main`, with no commits or remote. Protected shared GitHub, teammate approvals, individual contributions, 15 human-labeled failures, and the class demonstration remain coursework deliverables.

Known extraction limits include rotated PDF chart headers and possible column interleaving. Contact redaction uses patterns and is not a complete PII detector. The crawler address `parkguide-poc@example.com` is a user-requested placeholder and does not satisfy the course's real contact-email requirement. Instructor topic approval is user-confirmed.

Codex and three scoped subagents implemented the system, investigated failures, drafted source-based questions, and proposed semantic diagnostic labels. No agent certified human review. The $5 API cap uses reservations across processes. Costs use published prices and actual returned usage, retaining conservative reservations for unknown failed-call usage; estimates are not billing statements. Connectivity probes are recorded separately.
