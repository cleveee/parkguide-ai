# Local run dashboard

Open the [live local dashboard](http://127.0.0.1:8512/) or the standalone [HTML snapshot](../dashboard/index.html). The HTML embeds all data, styles, scripts and its UI proof image; it opens offline with no provider calls, analytics or external dependencies. The chatbot link requires the separate Streamlit app to be running.

The dashboard includes the crawl/corpus, both chunk/vector builds, all seven measured stages and 305 attempted evaluation rows, final baseline/dialogue AI judgments, uncertainty intervals, safeguards, technical/runtime settings, database/storage integrity, API usage/reservations, gold/review status, planning/report documents, and a source-path/hash manifest. Original large retrieval contexts remain in the local raw artifacts; the dashboard retains selected metadata and trace/calculation summaries rather than duplicating all contexts.

Current provider settings come from `config/project.json`: embeddings, answers and claim reviews use the same existing Azure development resource. The `gpt-6-luna` deployment alias returned the required `gpt-6-luna-2026-09-22` model. The independent smoke accepted temperature 0, reasoning `none`, strict JSON and `store=False` with a 128-token cap; the app requests 1,000 output tokens. The report preserves both this successful probe and the prior HTTP 404 for the snapshot name used as a deployment name. Setup observations and the later scoped runs remain separate from the historical OpenAI stages. Azure deployment SKU and invoice rates are unverified.

The **Park selector & evidence boundary** section records the current scoped UI behavior, offline contract count when recorded, separate selected-park diagnostic runs, every attempt including failures, observed providers/returned models, and saved browser proof when available. The current scoped UI enables local reranking; historical comparisons keep their actual settings. These operational checks do not replace or alter the original seven-stage metrics or 66 provisional AI labels. Browser proof is shown only when its verification record and screenshot exist. [Park scope details](PARK_SCOPE.md) explain strict refusals and the remaining AI entailment limit.

`artifacts/park-scope/support-observations.json` records AI audit observations linked to exact run/result hashes. In particular, an expected-action match in the second run concealed a source-support problem; its 19/21 operational count remains unchanged and is not presented as semantic accuracy. These observations are not human adjudication, new benchmark grades or proof that the latest model is correct. The selected-park retrieval check records an independent recovery of the existing drone rule; it does not establish a general reranking quality gain.

Each historical answer now has clickable **Sources used** cards derived from its delivered claims and original saved contexts: 196 responses have 307 page cards retaining 336 cited passages across the 305 attempts. Cards group repeated pages and show claim numbers, dates, saved text offsets, and verbatim excerpts totaling at most 25 words per page. PDF links use the recorded starting page. Official links open today's page; excerpts describe the saved snapshot. Nonanswers, closed-book replies and uncited retrieval do not gain cards. This presentation update does not change the original results or AI grades. [Source-link details](SOURCE_LINKS.md) and `artifacts/ui/source-links-verification.json` record the separate verification.

Costs distinguish the historical final verification snapshot from later ledger snapshots, scoped runs, setup probes and UI checks. Historical OpenAI prices and costs are preserved in their original events; current Azure Luna estimates come from the current pricing configuration. Stage costs contain successful generation and review only. The ledger also includes query/document embeddings, failed-call reservations, safeguards and live UI usage; do not sum stage costs or the new Azure setup probes onto the ledger. Only the original separately recorded connectivity probes are added outside it. The most recent recorded event-count snapshot supplies the displayed total. AI semantic labels are provisional. No formal held-out test or human review is claimed.

To serve only the dashboard directory on loopback:

```sh
cd /Users/robin/Build/Personal/parkguide-ai
.venv/bin/python -m http.server 8512 --bind 127.0.0.1 --directory dashboard
```

To regenerate the page and machine-readable export from preserved inputs:

```sh
.venv/bin/python scripts/build_dashboard.py
```

The builder reads saved artifacts without calling providers or modifying source evidence. It checks source counts, stage/row counts, final AI-review totals and support-observation result hashes. `artifacts/dashboard/stage-audit.json` and `technical-audit.json` are curated, timestamped inputs assembled from raw results/read-only database checks; preserve them with ignored local artifacts. Rebuilding HTML refreshes its build timestamp, report text and derived source cards, but does not rerun those audits or claim their measurements are newer. New Azure discovery/smoke artifacts, selected-park retrieval proof and completed scoped-run manifests/results are included in the path/SHA-256 provenance manifest. Each UI check and screenshot has its own recorded time; its live check is separate from the seven evaluation stages. Update the audit snapshots explicitly if the app/corpus/ledger changes.

`dashboard/run-data.json` and the **JSON data** link contain the same sanitized metadata, actual responses and report text as the HTML, excluding the screenshot bytes. The JSON link requires the adjacent `run-data.json` file; the HTML itself embeds its data and works without that file. **Print / PDF** prints the visible dashboard and currently expanded details. Original documents, corpora, caches, SQLite and `.env` remain outside the served directory. The HTML contains no credential values.
