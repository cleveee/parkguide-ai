# ParkGuide web app: refinement summary (Claude Code, claude-opus-5-5)

Date: 2026-10-10. Inputs: `supervisor-findings.md`, `claude-code-review.md`, `claude-contract-review.md`.

Constraints observed:
- No servers started or stopped, no paid calls, no git, no credentials read.
- No reads of `data/evaluation/**`.
- No changes to the core RAG/guard modules, `config/*`, the corpus or database, or historical artifacts.

## Important before live testing

Codex's running 8513 process still has the **previous** `parkguide/web.py` in memory, but the static files are served from disk, so it now serves the **new** `web/dist` bundle. The new frontend expects the new response fields (`history`, `timing.server_ms`, `inspector.ledger_window`, and others), so a chat through the old process would fail to render. **Restart the server** (`bash scripts/run_web.sh`) before any chat test. The restart also applies `HF_HUB_OFFLINE=1`.

## Code-review defects (all seven)

| # | Defect | Fix in `src/parkguide/web.py` | Regression test (`tests/test_web.py`) |
|---|---|---|---|
| 1 | Called `response.cost_estimate_usd` the "total" | `total_cost_estimate_usd` is removed. Holding the answer lock, `run_chat` reads the shared ledger before and after `answer()` (shared `flock`, read-only) and reports `inspector.ledger_window`: events, per-kind counts (reported / failed / unsettled), reported-only token sums, events without usage, and the estimated cost including reserved maximums, with a basis and limitation statement. The successful-call answer/review metrics are kept separately. | `test_ledger_window_includes_embedding_failed_attempts_and_review`, `test_unreadable_ledger_is_not_captured_rather_than_zero` |
| 2 | Scope violation labelled "before any retrieval" | Already reordered in the first pass. The scope check now has its own category, `scope_check`, with the detail "after local search, no answer model call". | `test_wrong_park_source_is_isolated` (category plus wording) |
| 3 | Zeros and false "no request" claims | Generation tokens, elapsed time and cost are `null` when generation did not run. `rerank_ms` is `null` when reranking was off. The retrieval query is `null` when retrieval did not run. `budget_exhausted` now says "no further model request was sent", and every post-stage error adds "Earlier stages … may already have made recorded calls; see the ledger window" with `error.details.ledger_window`. Configuration failures are distinguished: `embedding_not_configured`, `azure_configuration_mismatch` and `model_not_configured` say nothing was sent. | `test_other_park_question_refused_before_embedding`, `test_budget_exhaustion_reports_partial_stage_and_window`, `test_history_counts_and_nested_timings` |
| 4 | Passage pages not in document order | The SQL `ORDER BY json_extract(span,'$[0].start'), json_extract(span,'$[#-1].start'), chunk_id` runs before `LIMIT/OFFSET`, and each passage carries its `position`. | `test_passage_pages_are_contiguous_in_document_order` (asserts hash order differs) |
| 5 | Judgment-count mismatch failed open | New `_review_judgments` fails closed (`review_integrity_failed`, category `validation_failure`). It rejects: a missing or errored review on an answer, non-int indexes, a count mismatch, a witness outside its claim's evidence, a witness not verbatim in the stored passage text, and a cited passage without a witness. | `test_review_integrity_failures_withhold_the_answer` (5 cases) |
| 6 | A missing `content_hash` skipped the identity check | The hash is now required, and a missing or empty hash means stale. | `test_missing_content_hash_fails_closed` |
| 7 | Witness test couldn't catch an off-by-one | A three-claim case with claim 0 withheld. It asserts that delivered claims 1 and 2 receive decision 1's and decision 2's witnesses, that the source numbers match, and that the withheld text and reason are absent. | `test_witnesses_follow_retained_claims_when_first_claim_is_withheld`, plus `test_guard_failure_after_review_delivers_no_witnesses_or_cards` |

## Supervisor findings

1. **Ledger-window cost.** Implemented as above.
   - The limitation is stated: concurrent CLI or legacy Streamlit spend would also appear in the window.
   - Missing usage is counted as missing, never as zero, and reserved maximums are flagged.
   - Generation-kind events cover both answer and review calls; the label says so.
2. **Partial-stage wording.** Implemented as in defect 3. The 409 message now says that stopping in the browser does not stop the server.
3. **Embedding evidence.** The status comes from the ledger window:
   - `azure_request_recorded`, `azure_attempt_failed_recorded` or `no_azure_request_recorded`;
   - `not_captured` when the ledger can't be read;
   - `not_requested` when the embedder was never called.

   File presence is reported separately as `cache_file_present_before_call` and labelled as a file observation another process could change. `query_sha256` is exposed.
4. **Witness mapping.** Covered by defects 5 and 7. Witnesses are emitted only for delivered answers. Rejection reasons, `raw_response`, `review_payload` and roles are absent; a test asserts this.
5. **Derivation and timing.**
   - `inspector.derivation` is a safe, bounded view: operation, column, unit, equation, result, and operands (row label, saved cell, value, chunk) restricted to cited chunks, plus a note. It is shown in the Evidence tab as a table.
   - Timing is nested and labelled: `server_ms` ⊃ `answer_call_ms` ⊃ `pipeline_ms` ⊃ retrieval `total_ms` ⊃ load/scoring/rerank. Per-call figures are for successful calls only.
6. **History, refusal kinds and stale replies.**
   - The response carries `history: {messages_received, messages_used, scope_reset}`, shown in Data flow and in the chat when a reset occurs.
   - `reason.category` is one of `local_preflight`, `scope_check`, `validation_failure`, `review_failure`, `review_rejected`, `no_evidence`, `model_refusal` or `model_clarification`, with distinct chat labels.
   - The client now excludes locally refused other-park turns from the history it sends, so they no longer silently reset later follow-ups.
   - Stale protection is unchanged and still works: the epoch check plus turn-id mapping mean an old reply can't repopulate a cleared conversation.

## Supervisor observations

- **Date age.** `captureAge` uses elapsed-time buckets ("captured under 24 hours ago", "N days ago") and never says "today". Exact local timestamps with time zone (`formatDateTime`) appear in the sidebar tooltip, the empty state, the corpus overview, the evidence dialog and the document reader.
- **Wider tabbed readers.**
  - Root cause: a plain `sm:max-w-*` can't beat the primitive's `data-[side=right]:sm:max-w-sm`.
  - The document reader is now `data-[side=right]:sm:max-w-xl` with **Sections (count) / Indexed passages (count) / Details** tabs, keeping pagination by 20 and 10. The inspector sheet is also `sm:max-w-xl`, and the menu uses `data-[side=left]:w-72`.
  - The evidence dialog shows one tab per cited passage and opens on the passage that the clicked claim cites.
- **No large blur.** Removed `supports-backdrop-filter:backdrop-blur-xs` from the sheet, dialog and alert-dialog overlays, which now use a plain `bg-black/20` dim. The existing ≤200 ms opacity/transform animations and reduced-motion CSS are unchanged.
- **How it works.**
  - Discloses that query SHA-256 hashes and vectors persist in `data/embedding-cache/` (no query text) and that the budget ledger persists per-call kind, time, status, tokens and cost (no text).
  - Conversation text stays in tab memory and is sent to the local server per request.
  - States that `store=false` is a request that does not itself guarantee the provider keeps no data.
  - Shows the exact shared Azure resource from `/api/meta` (`models.azure_resource`): `https://rd-foundry-dev-eastus2.cognitiveservices.azure.com`, with deployments `text-embedding-3-small` and `gpt-6-luna`.

## Other review items addressed

- Port-5173 Host/Origin values are refused unless `PARKGUIDE_WEB_DEV=1` (tested).
- `main()` sets `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`, so the reranker cannot download. `OSError` maps to `local_resource_unavailable`.
- The document-list park filter uses the same `/planyourvisit/` rule as the metadata counts (tested with a new fixture document).
- Retrieval candidates carry `park` and `in_selected_park`. Entries in `candidates`/`final` that are missing from `reranked` are now listed, so an injected foreign passage is visible and badged.
- Error responses carry safe `details` (ledger window, embedding observation, answer-call time), which appear in the chat error alert.

## Dashboard

- `scripts/build_dashboard.py` loads `artifacts/ui/web-app-verification.json` when present (none exists yet), plus `artifacts/ui/web-app-preview.png` when present. It adds a "Web-app check" ledger snapshot when the record has `api_usage.ledger_after`. Nothing new is read from evaluation files.
- `dashboard/template.html`: the hard-coded "Measured state" card is replaced by a **Live web-app verification** card. Without the record it states that verification is pending; with it, it shows the time, summary, JSON and optional screenshot. The card is separate from the historical Streamlit proof.
- `dashboard/index.html`: my earlier first-pass hand edits are **reversed** exactly (header link, nav link, section, Chat UI row), so the file again matches the previous builder output. **Codex needs to run** `.venv/bin/python scripts/build_dashboard.py` for the new template to appear.
- `docs/DASHBOARD.md` is updated to match.

## Licenses

AI Elements remains Apache-2.0 (verified from the `ai-elements@1.9.0` package LICENSE, stored in `web/src/components/ai-elements/LICENSE`), and no project doc says MIT for it. shadcn/ui and Radix remain MIT. The `FRONTEND_REFERENCES.md` adaptations section now records the overlay-blur removal and the sheet-width override.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `.venv/bin/python -m pytest tests/test_web.py -q -x` (after the first backend edit) | 1 failure: the fixture read the **real** ledger because `ledger_path` wasn't patched. The fixture now uses a private tmp ledger, invented prices and the real `Budget` class |
| `.venv/bin/python -m pytest tests/test_web.py -q` | 3 failures, all fixed: (a) a real bridge gap where injected candidates absent from `reranked` were hidden, now listed; (b) a test key collided with the new `history` counts field, so it now checks for raw `"role"`; (c) a test stub wrote to its own corrupted ledger. Then 107 passed |
| `.venv/bin/python -m pytest -q` (repo root, final) | **397 passed** (290 existing + 107 web) |
| `.venv/bin/python -m pip check`; `pip freeze` vs `requirements-full.lock` | No broken requirements; **LOCK_MATCHES_ENV** (no dependency changes) |
| `npm --prefix web run build` (`tsc -b && vite build`, final) | **Passed**: JS 616.43 kB (189.58 kB gzip), CSS 81.24 kB; the existing >500 kB chunk warning remains |
| `npm --prefix web run lint` | 0 errors; 11 `only-export-components` fast-refresh warnings, the same as before |
| `.venv/bin/python -m py_compile scripts/build_dashboard.py src/parkguide/web.py` | Compiled. The builder was **not run** |
| A `cat >> … <<EOF` heredoc append to `inspector.tsx` | Blocked by the permission checker ("brace with quote character"). The same content was appended with the Edit tool |
| `grep -o …` on the template | Required approval; the Grep tool was used instead |

## Remaining limitations

1. No live verification. There has been no paid chat, no browser QA and no human labels. Codex must restart 8513 first (see the top section).
2. The ledger window attributes every event added during the lock to this request. A concurrent CLI or Streamlit process would be included; this is stated in the UI and export. The `generation` kind combines answer and review calls because the shared Budget doesn't distinguish them.
3. No upfront worst-case budget pre-check: review can still hit the cap after generation was paid. That case surfaces honestly as `source_review_failed` with the ledger window, and core modules were deliberately left unchanged.
4. The embedding cache-path rule (`data/embedding-cache/<identity digest>/<sha256>`) is duplicated from `embedding_cache.py` for the file observation only. It is labelled as an observation; the network-call label comes from the ledger.
5. The 12-message history cap can drop the first-topic anchor that `resolve_query` keeps with Streamlit's unbounded history, so follow-up behavior may differ from Streamlit.
6. The reranker overflow (`question_too_long_for_reranker`) still occurs after a possible paid embedding; the message now says so.
7. The dashboard HTML won't show the new web-app section until the builder is rerun.
