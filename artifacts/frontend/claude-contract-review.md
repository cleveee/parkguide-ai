I reviewed the six modules plus `store.py`, `azure.py`, `embedding_cache.py`, `guards.py` and the legacy `app.py`. `src/parkguide/web.py` doesn't exist yet, and `web/` is still the Vite template, so everything below is a requirement on code not yet written, not a finding against it. I didn't read `.env` or gold/test files, make model calls, or change anything. This is a code-reading risk list, not acceptance testing.

## 1. Selected-park isolation
- [ ] **`selected_park` is optional in the core.** `chat.py:240` accepts `None`, which means no scope filter. The API must require one of `yose`, `yell` or `grca` and always pass it.
- [ ] **Allowed call shape.** `answer(question, history, selected_park=park)` is fine; it could also pass a fixed `build_id` (next item). Don't pass `mode`, `rerank`, `retriever`, `generator`, `reviewer`, `closed_book` or `enforce_gate`. Two traps:
  - A wrapped `retriever` silently turns off the full-page quote-limit check, because `chat.py:375` tests `retriever.__module__`.
  - A custom `generator` without a `reviewer` is forced to refuse (`chat.py:349`).
- [ ] **Build drift.** With `build_id=None`, retrieval uses whichever build is active (`store.py:163`). The evaluated B3 run uses `artifacts/builds/structure.json` (`cli.py:73-80`). Either pass that build explicitly or check at startup, read-only, that the active build matches. Don't copy Streamlit's mode/rerank selectors (`app.py:52-53`).
- [ ] **Silent history reset.** If any history turn mentions another park, the server drops the whole history (`chat.py:248`). A mismatched question the user asked earlier stays in browser history, so every later follow-up quietly loses its context. Either leave refused-mismatch turns out of the history the browser sends, or show `history_scope_reset`.
- [ ] **No server-side state.** Build source cards only from the current `answer()` result. A `/api/source/{id}` lookup or a cached "last result" makes stale or uncited cards possible. On the client, tag each request with a (park, conversation epoch, request id) and drop any reply that doesn't match.

## 2. Reviewed output only
- [ ] **Never return `raw_response`** (`chat.py:340,390`). It is the unreviewed draft: it includes withheld claims and the model's own refusal wording, which `chat.py:369-373` replaces.
- [ ] **Source cards come from `cited_source_pages(result)` only** (`source_links.py:41`), called on the full result. "Other retrieved" passages are `contexts` minus cited IDs, as in `app.py:77-78`, and appear only in the inspector.
- [ ] **Render claims from `response.claims`, not the `rendered` markdown** (`guards.py:107-119`). If markdown is ever rendered, it needs a safe link policy and no raw HTML.
- [ ] **Allowlist fields in the retrieval inspector.** Each candidate gets the whole `document_snapshot` merged in (`retrieval.py:88`), so any stored fields (possibly local paths) come along. Don't dump candidates wholesale.

## 3. Mapping witnesses to delivered claims
- [ ] **Indexes shift after a withheld claim.** Review decisions are indexed over the claims before review (`claim_review.py:224`). Delivered claims are the retained subset (`chat.py:358-361`), and card `claim_numbers` count delivered claims from 1 (`source_links.py:55`). Mapping `decision.claim_index + 1` is wrong once anything is withheld. The delivered number is the decision's position among the `supported` decisions.
- [ ] **Hide witnesses when the answer was refused afterwards.** Guard errors after review (`chat.py:379-384`) refuse the whole answer, but `citation_review.decisions` still holds supported decisions with witnesses. Show witnesses only when `response.action == "answer"`. Each witness's `evidence_id` must be one of that delivered claim's `evidence_ids`.
- [ ] **Don't expose withheld content.**
  - For withheld claims, show the count (`withheld_claims`), not the `reason`, which can restate the unsupported claim.
  - On review failure, `error.diagnostics.review_payload` (`claim_review.py:355`) holds model reasons and quotes. Export `validation_reason` only.
- [ ] **Label excerpt and witness differently.** The card excerpt is a mechanical word-overlap window (`source_links.py:86-106`). The witness is the AI reviewer's selected quote (`claim_review.py:172`). Don't present either as the other.

## 4. Real timing, cache, score, usage and cost
- [ ] **Show "no model call" or "not captured", never 0.**
  - Preflight payloads report `elapsed_ms: 0` and `usage: {}` (`chat.py:147-167`).
  - A rejected generation can have `elapsed_ms: None` (`chat.py:326`).
  - Reranking turned off still reports `rerank_ms: 0.0` (`retrieval.py:160`).
  - The preflight path's trace has `timings: {}` (`chat.py:275`).
- [ ] **Embedding time and cache hits are never measured.** `cached_embed` returns only vectors (`embedding_cache.py:74`), and retrieval timings start after embedding. Report cache status as "not captured" rather than inferring it. The total `result.elapsed_ms` also includes retry sleeps and the reranker's cold load on the first request.
- [ ] **`cost_estimate_usd` undercounts:**
  - It covers generation plus review only (`chat.py:360`); embedding is excluded (`embedding_cache.py:49`).
  - Failed retry attempts are not included (`chat.py:339`).
  - Review cost is missing when review raises (`chat.py:362-366`).

  To fix this, take a ledger difference (`Budget().summary()` before and after, under the process lock), labeled as an estimate that other processes such as the CLI could also affect.
- [ ] **Usage and model are split across two places.** Generation is in `response.usage`/`response.model`; review is in `citation_review.usage`/`citation_review.model`. Label score types with `retrieval.score_types` (`retrieval.py:160`); the reranker score is a raw, uncalibrated value.
- [ ] **NaN would discard a paid answer.** Starlette's `JSONResponse` serializes with `allow_nan=False`, so one non-finite number causes a 500 after the calls were already paid for. Sanitize values to `null` before responding.

## 5. Credential and error redaction
- [ ] **Map exceptions to a fixed set of error codes; don't return `str(error)`.** Don't copy Streamlit's `st.error(str(error))` (`app.py:91-92`). Exceptions that can escape `answer()` include:
  - the gate `RuntimeError` (`chat.py:257`)
  - budget-cap and pricing errors (`budget.py:32-44`)
  - embedding errors (`azure.py:73-118`, `embedding_cache.py:35`)
  - `GenerationError` with `.code`/`.status_code` (`generation.py:116`)
  - retrieval `ValueError`s for reranker truncation and missing index (`retrieval.py:145`, `store.py:165`)
  - reranker load and Hugging Face `OSError`s, plus sqlite errors (these can carry paths)
  - `KeyError` from malformed history (`chat.py:81`)
- [ ] **Keep request errors separate from refusals.** Request errors return 4xx/5xx with a code. Refusals return 200 with `action: refuse` plus the actual reason:
  - A rejected generation's text is replaced by "not enough supporting information" (`chat.py:322-327` → `370`). Show `generation_error.code` as the real reason.
  - A review failure, including the budget cap hit at review time (`chat.py:362`), should read "source review unavailable", not "no support found".
- [ ] **Reranker download.** On first use, `load_reranker` may download from Hugging Face (`retrieval.py:63`), which violates "only Azure". Run the web process with HF offline mode, or verify the model is already cached.

## 6. Input bounds that protect the budget
- [ ] **Validate history before calling `answer()`.** Generation budget is reserved (`chat.py:312`) before `build_messages` rejects bad roles (`generation.py:149`). That error isn't in the rejected set, so it raises and the full maximum estimate stays committed. Validate roles and types, cap turn count and characters, and reject unknown fields.
- [ ] **Cap question length.** The reranker raises when query plus passage exceeds 512 tokens (`retrieval.py:144-145`), but only after embedding has been paid. The retrieval query grows with inherited topics (`chat.py:110-119`), so the cap needs headroom. Map this error to a "question too long" code.
- [ ] **Assistant turns in history.** Send `result.rendered` as the assistant turn, as `app.py:97` does: `table_followup_filters` reads NPS links from it (`chat.py:198`). Plain text silently degrades table follow-ups.

## 7. Cancellation, locking and budget races
- [ ] **Use a non-blocking lock held by the worker thread.** `answer()` is synchronous and can sleep up to 60 s per retry (`chat.py:207-212,334`; `embedding_cache.py:58`). An `asyncio.Lock` around `await run_in_threadpool(...)` is released on cancellation while the thread keeps running, allowing a second paid request to overlap. Use a `threading.Lock` acquired without blocking and released in the worker's `finally`, and return 409 "busy" rather than queueing. Queued requests become paid calls after the user has left.
- [ ] **Pre-check the whole budget.** Generation and review reserve separately (`chat.py:312`, `chat.py:220`), so review can hit the cap after generation was paid. Under the lock, check that the remaining budget (`budget.py:60`) covers embedding, generation and review at worst case before starting. Otherwise, at least report it as a review/budget failure.
- [ ] **Browser abort doesn't stop the server.** UI copy must not suggest otherwise. After "new conversation" or a park switch, show "previous request still finishing" (409), not a refusal.

## 8. Read-only metadata and corpus
- [ ] **`_connection` isn't read-only.** It calls `sqlite3.connect` directly (`store.py:18-19`), which creates a missing database file. Open with `file:…?mode=ro` (`uri=True`), use parameterized queries and allowlisted sort columns, and paginate. Never call `initialize` (`store.py:35`) or `load_reranker` at startup.
- [ ] **Corpus URLs** go through `official_source_url` (`source_links.py:9`) and must also match the selected park's path where the label says it's park-scoped.

## Offline tests worth adding
Stub `chat.answer`, `cached_embed`, `Budget` and `gold_drafts_ready` the way `tests/test_park_scope.py:21,420` and `tests/test_retry.py:28,62` do.

1. **Call shape:** monkeypatch `parkguide.chat.answer` and assert the exact arguments (park, plus the structure `build_id` if pinned), with no overrides.
2. **Schema rejection:** missing or invalid park, unknown fields, `mode`/`rerank`/`build_id` in the body, `system` role in history, over-long question or history, non-string content. Each returns 422 and `answer` is never called.
3. **Withheld-claim mapping:** stub a generator returning 3 claims and a reviewer rejecting claim 0. Assert delivered claims 1–2 get the witnesses from decisions 1–2, card `claim_numbers` match, and the withheld claim's text and reason appear nowhere in the response or export.
4. **Guard-after-review:** a supported review followed by a guard error. Assert no witnesses and no source cards.
5. **No draft leakage:** grep the serialized response and export for `raw_response`, the withheld claim text, `review_payload`, `api-key`, and the `AZURE_*` env values set in the test.
6. **Wrong park:** a retriever returning a `/yell/` chunk while `yose` is selected leads to the `invalid_selected_park_sources` refusal, with no cards. A Yellowstone question with Yosemite selected leads to the mismatch refusal and no paid calls.
7. **Error mapping:** a parametrized set covering the exception list in section 5. Assert a stable code, no message text or paths, and that review/generation failures come back as 200 refusals with their reason.
8. **Not zero:** a preflight refusal serializes timing/usage/cost as `null` or "not captured", not 0. A NaN score doesn't cause a 500.
9. **Concurrency:** a slow stubbed `answer` holds the lock, a second POST gets 409, and the lock is released after the worker finishes even if the first client disconnects.
10. **Read-only metadata:** pointing at a missing DB path returns an error without creating the file. SQL-like search strings and traversal-like IDs are handled safely. Pagination caps hold.
11. **Origin/Host:** a POST with a foreign `Origin` or a non-loopback `Host` is rejected, and there is no `Access-Control-Allow-Origin: *`.

Still open and needing Codex's live check: actual cancellation behavior under uvicorn, the reranker's cold-start latency, and whether the active build matches `structure.json` on this machine.
