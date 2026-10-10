I read all of `web.py`, and the bridge mostly does what the integration requirements need. I found three real data-flow defects, mainly in cost reporting and refusal labelling, plus a few smaller fail-open or false-statement issues. Nothing was edited or run (no tests, no model calls), and I didn't read gold or test data.

## What I inspected
- **`src/parkguide/web.py`**: all 783 lines.
- **`tests/test_web.py`**: the fixture and lines 95–294 in full; the remaining tests by name only.
- **Frontend**: `web/src/App.tsx` has no API code yet. I spot-checked `ai-elements/message.tsx` and `sources.tsx`, and searched `web/package.json` for markdown and AI SDK packages.
- **Core modules**: everything from the first pass, plus `schema.sql`, `store.py:147` and `ingest.py:234`.
- **Note**: `message.tsx` and `tests/test_web.py` changed while I was reading, so the worker is still active.

## Verified as correct
- **Delivered-claim/witness mapping** (`web.py:424-435`): it uses supported decisions in sorted `claim_index` order. That matches how the core keeps retained claims (`chat.py:357-358`, `claim_review.py:224`). Witnesses are filtered to each passage's `chunk_id` and delivered claim numbers (`:498-501`).
- **Draft isolation**: `raw_response`, `history`, `review_payload` and rejected-claim reasons are never sent. Non-answer text comes from the core's fixed templates.
- **Foreign source scope and stored identity** (`:473-480`): each cited passage is checked against the active build's stored chunk text, `doc_id`, document `content_hash`, the official URL and the selected park.
- **Lock lifetime** (`:604-620`): the handler is a sync `def`, so it runs in a worker thread. The lock is taken without blocking and released in `finally` after `answer()` returns. A disconnected client therefore can't release it early, and a second request gets 409 instead of queueing.
- **Request schema** (`:138-166`): `extra="forbid"` plus strict mode, a `Literal` park, length limits on question and history, control-character rejection, and user/assistant pairs. The core call shape (`:609-613`) keeps the review and `retriever.__module__` checks working.
- **Read-only database access** (`:75-85`) uses `mode=ro` and never creates the file.

## Actual defects
1. **`total_cost_estimate_usd` isn't the true request cost** (`web.py:543, 588, 591`). It is `response.cost_estimate_usd`, which leaves out:
   - embedding cost (`embedding_cache.py:49`);
   - failed generation retries (`chat.py:339`);
   - all review cost when review raises (`chat.py:362-366`).

   In the review-error case it is labelled "total" but equals generation only. **Fix:** inside the lock, take `Budget().summary()["estimated_committed_usd"]` before and after `answer()` and report the difference as the request estimate. Label it as possibly including concurrent CLI or Streamlit spend, and keep the per-stage figures as reported values.
2. **Scope violations are mislabelled.** In `_refusal_reason`, the `preflight_reason` branch (`:446-447`) runs before the scope check (`:448`). The core sets `preflight_reason="invalid_selected_park_sources"` *after* embedding and retrieval (`chat.py:281-284`), so the UI says "Stopped by a local check before any retrieval or model call", which is false. **Fix:** check `selected_park_source_scope_violation` first, or exclude that reason from the "before retrieval" detail.
3. **Zeros and false "no request" claims:**
   - On preflight, `generation.elapsed_ms` returns `0` (`:587`, from `chat.py:147-167`) even though `ran` is false. **Fix:** return `None` when `ran` is false.
   - `budget_exhausted` says "no request was sent" (`:633`), but the generation-stage cap check happens after the query may already have gone to Azure for embedding. **Fix:** say "no further request was sent" or mention the embedding status.
4. **Passage pagination isn't in document order** (`:339-350`). `LIMIT/OFFSET` is applied in `chunk_id` (hash) order and then each page is re-sorted by span. Pages are therefore arbitrary sets of chunks, despite the "read in document order" comment. **Fix:** in SQL, `ORDER BY json_extract(source_span_json,'$[0].start'), chunk_id`.
5. **A judgment-count mismatch fails open** (`:427-428`). If the number of supported decisions differs from the number of delivered claims, the answer is still delivered with no witnesses and review status `"passed"`. The core shouldn't produce this, but it should fail closed: treat it like `stale` and withhold.
6. **A missing hash skips the identity check** (`:477`): `passage.get("content_hash") and …` skips the comparison when the hash is missing. Require it.
7. **The witness-mapping test can't catch an off-by-one.** In the fixture, the withheld claim is the *second* one (`tests/test_web.py:124-130, 274-285`), so positional mapping and `claim_index+1` give the same result. The test also never checks delivered witnesses. **Fix:** add a case where claim 0 is withheld, and assert that delivered claim 1's `reviewer_witnesses` equal decision 1's quote and that no rejected text appears.

## Optional improvements
- **Budget pre-check before generation.** At `:604`, check that remaining budget covers embedding, generation and review at their maximums. Otherwise the review reservation can fail after generation was paid; that already surfaces honestly as `source_review_failed`.
- **Error classification** (`:634`): "Azure environment differs…" and "Embedding cache integrity check failed" become `internal_error` (500). "Azure embedding configuration is incomplete" is reported as a failed request even though nothing was sent.
- **Reranker overflow** (`:638`) returns 422 only after embedding was paid. Inherited history topics (`chat.py:110-119`) also contribute, so "the question is too long" can be misleading.
- **`saved_text` in source cards** (`:495`): the UI should show only `excerpt` under "Sources used" to respect the 25-word per-page excerpt limit (`source_links.py:86`), and keep the full text in the inspector.
- **Inconsistent park counts**: metadata uses `_park_of`, which requires `/planyourvisit/` (`:219`), while the document list uses a URL-prefix `LIKE` (`:268-269`). Counts can differ if any stored document falls outside that path.
- **Inspector detail:**
  - Retrieval candidates have no `park` field, so on a scope violation the foreign candidates appear unflagged.
  - `retrieval.query` is shown even when retrieval didn't run.
  - `request_ms` leaves out the pre-lock checks and the post-answer database validation (`:606, 621`).
- **Duplicated cache logic**: `_observed_embedder` copies the cache path and key rules from `embedding_cache.py:17-22`, which can drift. Port 5173 hosts are allowed in production (`:40`).
- **Leftover dependencies**: `web/package.json` still lists `streamdown` and `ai`, while the `message.tsx` header says the Streamdown renderer was removed.
- **Shorter history than Streamlit**: the 12-message cap drops the first-topic anchor that `resolve_query` keeps, so follow-up behaviour will differ from Streamlit's unbounded history.

## Not yet reviewable or not reviewed
- **The whole browser data flow**, because `App.tsx` has no fetch code yet:
  - dropping stale replies per park, conversation or request;
  - trimming history to 12 messages and sending `history_content`;
  - handling `history_scope_reset`;
  - the abort / 409 messaging;
  - plain-text rendering of claims.
- **Also not reviewed**: the rest of `tests/test_web.py` beyond its test names, `docs/FRONTEND_REFERENCES.md`, the README and run scripts, and real behaviour under uvicorn (cancellation, reranker cold start), which is Codex's live check.
- **Test coverage gap**: the fixture passes its own `reviewer`, a wrapped `retriever` and `rerank=False` (`tests/test_web.py:105-106`). So `paid_claim_review` cost accounting and the full-page quote-limit check never run on the web path in tests.
