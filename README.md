# ParkGuide local RAG proof of concept

ParkGuide answers questions about Yosemite, Yellowstone, and Grand Canyon from saved official NPS sources. The local application, Azure embeddings, retrieval pipeline, and real evaluation runners are implemented. The course benchmark awaits human verification of the 40 source-authored gold drafts.

The three workstreams are [corpus/database, retrieval/chat, and evaluation](docs/PLAN.md). Python, one SQLite file, NumPy exact search and BM25 keep the pipeline simple. The primary interface is a small React + TypeScript web app served by FastAPI; Streamlit remains an optional legacy tool. One existing Azure resource generates embeddings with `text-embedding-3-small` and answers/claim review with `gpt-6-luna-2026-09-22`; a pinned CrossEncoder reranks locally. The [live demo](https://parkguide-ai-dh24.vercel.app/) uses the [Vercel hosted profile](docs/VERCEL.md) and a frozen read-only copy of SQLite, without a cloud database service.

## Run locally

Start the web app (it builds `web/dist` first if it is missing) and open [http://127.0.0.1:8513](http://127.0.0.1:8513):

```sh
cd /Users/robin/Build/Personal/parkguide-ai
bash scripts/run_web.sh            # add --build to rebuild the frontend first
```

The equivalent manual steps are `npm --prefix web ci && npm --prefix web run build`, then `.venv/bin/python -m parkguide.web`. The server binds only to 127.0.0.1:8513, serves the compiled frontend and same-origin `/api/*`, and reads the existing SQLite database. Startup never ingests, indexes or embeds anything; Azure calls happen only when you ask a question. Frontend development: start the server with `PARKGUIDE_WEB_DEV=1` (otherwise port-5173 Host/Origin values are refused), then run `npm --prefix web run dev` (Vite on 127.0.0.1:5173 proxies `/api`). The server sets `HF_HUB_OFFLINE=1`, so the pinned reranker must already be in the local Hugging Face cache. Persisted locally: query hashes and vectors in `data/embedding-cache/`, and paid-call kind, tokens and cost in `artifacts/api-ledger.json`. Conversation text stays in browser localStorage.

Choose a park (Yosemite, Yellowstone or Grand Canyon) before chatting; the selected park is shown in the header and next to the composer. Every question goes through the shared `parkguide.chat.answer` path with that park, hybrid retrieval over the active structure-aware build, and selected-park reranking. New conversation starts a separate chat and keeps earlier conversations in **Your chats**. Select a saved chat to reopen it and continue with its own park and context. Use its × button to close it; confirmation removes that chat and its content from browser storage. Switching or clearing the park also preserves a conversation with messages and starts a separate chat. Leaving a pending reply asks for confirmation; late replies for that earlier conversation are ignored. **Stop waiting** stops the browser from waiting, but the server may still finish that request. All conversations and the active chat are saved in browser localStorage and restored on reload. Clearing site data also removes it.

Only claims that passed source review are shown. Numbered citations open the saved excerpt, the reviewer's verbatim witnesses (labelled as an AI judgment) and a separate link to the current official NPS page. **Sources used** groups cited passages by saved page. The inspector (side panel on wide screens, sheet on smaller ones) has **Evidence**, **Retrieval** (query, filters, counts, cosine/BM25/RRF/reranker ranking scores, timings) and **Data flow** (embedding cache status, returned models, tokens, estimated cost, refusal reasons) tabs, with JSON copy/download. **Corpus** in the sidebar browses the read-only database. **How it works** explains what leaves the machine. [Park scope and verification](docs/PARK_SCOPE.md) describes the enforced boundaries and AI-review limits; [frontend references](docs/FRONTEND_REFERENCES.md) record component origins and licenses.

Select Yosemite and ask “What distance should I keep from a bear outside developed areas?”, then “What should I do if that bear is in a developed area?” Ask about Yellowstone to see the scope refusal, or an imaginary Blue Lantern Lagoon submarine tour to see a source-gap refusal. Select another park to begin its separate conversation. These examples are non-gold diagnostics.

Follow-up retrieval retains the conversation subject while keyword search emphasizes a new concrete detail, such as a pet's leash length. Refused off-park exchanges do not erase valid earlier context. Missing references ask for clarification; recognized live/future-status and private-booking requests explain the source limitation and next step. After a supported answer, **Explore next** offers up to three relevant questions with exact supporting passages in the selected park’s saved corpus. Select a question to edit and send; suggestions make no extra model calls. Submitted catalog questions use their saved supporting passage and still pass the normal answer/source review. [Follow-up grounding](docs/SUGGESTED_FOLLOWUPS.md) describes the catalog and checks. A failed request restores the question when the composer is still empty. Chat requests stop waiting after 110 seconds, without automatically resending a potentially paid request. [Hosted visitor testing](docs/HOSTED_USER_TESTING.md) preserves source-first conversations, unsuccessful iterations, source checks and provisional semantic assessments.

Selected-park follow-ups now use a bounded conversation decision on the existing Azure deployment. Requests such as “I don't understand” keep the subject and reload the previous answer's cited passages from SQLite; the browser sends only bounded citation IDs as hints. New factual follow-ups use a complete contextual question for semantic search while retaining the visitor's concrete follow-up terms for keyword ranking. Source review still runs for each factual answer, and an unavailable conversation decision falls back to local context resolution. [Conversation repair verification](docs/CONVERSATION_REPAIRS.md) records the implementation and development limits.

### Vercel hosted profile

The repository can also be imported into Vercel as one FastAPI project. The entry point is `server.py`, and the hosted profile is selected by `VERCEL=1`. It serves the same app from the frozen read-only database, without the cross-encoder reranker. The saved local evaluations do not measure that retrieval profile. The hosted query cache and budget ledger live in per-instance `/tmp`, so the $5 cap applies per instance and is not global. See [docs/VERCEL.md](docs/VERCEL.md) for import settings, the four server-only Azure variables and the limits. Local behavior is unchanged.

### Legacy Streamlit app

The earlier Streamlit interface remains available as an optional tool; historical screenshots and proof in the reports refer to it:

```sh
.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false
```

Its sidebar **Search settings** expose search/reranking ablation controls that the web app intentionally does not accept. [Source-link details](docs/SOURCE_LINKS.md) explain attribution in both interfaces.

## Setup and verification

Use Python 3.12. The verified runtime here is Python 3.12.14 on macOS ARM64:

```sh
PARKGUIDE_PYTHON=/Users/robin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 bash scripts/setup.sh
.venv/bin/parkguide doctor
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
npm --prefix web ci && npm --prefix web run build   # typecheck + production build
node --test web/tests/*.test.mjs                  # request recovery and chat persistence
```

The web app needs Node.js (verified with Node 26.7 / npm 11.19); `web/package-lock.json` pins the frontend packages. `tests/test_web.py` covers the API bridge offline with stubbed model calls.

Elsewhere use `PARKGUIDE_PYTHON=python3.12 bash scripts/setup.sh`. Setup installs `requirements-full.lock`, initializes SQLite without deleting existing rows, and makes no model calls. `PARKGUIDE_CORE_ONLY=1` selects `requirements-core.lock`; reranking then requires the optional packages. Locks were resolved on macOS ARM64; verify compatibility elsewhere. Pinned model weights download on first use and remain cached.

Create a private `.env` from `.env.example`, mode `0600`; this machine is already configured. Never print or commit keys. [Azure verification](docs/AZURE.md) records the existing ReviewDoc dev/staging resource. The same Azure endpoint and key serve both deployment names. The ignored `.env` needs only the four variables in `.env.example`; there is no direct OpenAI API configuration or fallback. [Generation documentation](docs/GENERATION.md) records the verified Luna snapshot and request settings. Hosted credentials remain server-only; the database is never served as a public asset.

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

The saved corpus, SQLite database, embedding caches, reports, and run evidence are versioned in [the public repository](https://github.com/cleveee/parkguide-ai). A clone includes the prebuilt database and vectors; ingestion and corpus re-embedding are not required to run this snapshot. Install dependencies and provide your own private Azure credentials in ignored `.env`. Environments, dependencies, compiled output, and runtime locks stay excluded. [Repository data documentation](docs/REPOSITORY_DATA.md) and [the file manifest](reports/DATA_SNAPSHOT.json) record the published snapshot and its limits. Protected shared GitHub, teammate approvals, individual contributions, 15 human-labeled failures, and the class demonstration remain coursework deliverables.

Known extraction limits include rotated PDF chart headers and possible column interleaving. Contact redaction uses patterns and is not a complete PII detector. The crawler address `parkguide-poc@example.com` is a user-requested placeholder and does not satisfy the course's real contact-email requirement. Instructor topic approval is user-confirmed.

Codex and three scoped subagents implemented the system, investigated failures, drafted source-based questions, and proposed semantic diagnostic labels. No agent certified human review. The $5 API cap uses reservations across processes. Costs use published prices and actual returned usage, retaining conservative reservations for unknown failed-call usage; estimates are not billing statements. Connectivity probes are recorded separately.
