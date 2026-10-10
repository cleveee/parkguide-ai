I found no new substantive defects in the current `web.py`, and all seven earlier findings are fixed in the code. This is a source-only review: I ran nothing, read no credentials, data or evaluation files, and changed nothing. The 397 passing tests and the live checks are as reported to me, not something I re-ran.

Files read: all of `src/parkguide/web.py` (1070 lines); `tests/test_web.py` lines 80–124 and 460–614, plus every test name and the key assertions; and the launcher line in `scripts/run_web.sh`. I didn't review the frontend in this pass.

## The seven earlier findings

1. **Request cost didn't include everything — Fixed.** `run_chat` (`web.py:847-863`) reads the budget ledger before and after `answer()` while still holding the lock. `ledger_window` (`:436-478`) then counts:
   - embedding calls, failed attempts and retries;
   - calls with no token usage, which keep their reserved maximum cost and set `includes_reserved_maximums`;
   - an unreadable ledger as `captured: False`, not zero.

   The window is also attached to error responses (`:868`). Tested at `tests/test_web.py:462-526`.
2. **Scope violations were labelled as a pre-search stop — Fixed.** The scope check (`:611-613`) now runs before the general preflight branch and is labelled `scope_check`. The preflight wording is correct for the paths that can reach it.
3. **Zeros shown for stages that didn't run, and a false "no request was sent" message — Fixed.**
   - Generation tokens, time and cost are `None` when generation didn't run (`:816-823`), and rerank time is `None` when reranking didn't run (`:801`).
   - The budget message now says "no further model request" and points to the ledger window (`:899-900`, `:884`).
   - Generation configuration errors are reported as "failed before a request was sent" (`:878-895`).
4. **Passage pages weren't in document order — Fixed.** Sorting happens in SQL before `LIMIT`/`OFFSET` (`:364-367`) and each passage gets a `position`. Tested at `:809`.
5. **A mismatch between review decisions and delivered claims still delivered the answer — Fixed.** `_review_judgments` (`:549-585`) now withholds the answer if:
   - the review is missing or errored, or a decision index is invalid;
   - the number of supported decisions differs from the number of delivered claims;
   - a witness quote is outside the claim's own evidence or isn't verbatim in the stored passage;
   - any cited passage has no witness.

   Any of these sets `delivered=False` (`:685`) and gives a fixed refusal text (`:726-729`). Tested at `:587-599`.
6. **A missing content hash skipped the identity check — Fixed.** The hash is now required to be a non-empty string that matches the stored document's hash (`:672-674`). Every evidence ID a claim cites must also have a validated source card (`:679`). Tested at `:602-612` and `:403`.
7. **No test where the first claim is withheld — Fixed.** `:540-557` withholds claim 0 of 3 and checks that delivered claims 1 and 2 get the witnesses from decisions 1 and 2. It also checks the source numbers and that no rejected text or reason appears.

## The other areas you asked about
- **Draft isolation:** `public_turn` never returns `raw_response`, `history`, the raw review result, `review_payload` or rejected reasons. Review errors expose only `_SAFE_MESSAGE`/`_SAFE_CODE` values (`:533-541`). History is exported as counts only (`:783`).
- **Embedding labels:** the Azure-call status comes from the ledger window (`:481-494`). The cache check is labelled `cache_file_present_before_call`, a file observation (`:403-405`).
- **Lock on cancellation:** the endpoint is synchronous and the lock is taken without blocking inside the worker thread (`:841`). It is released in `finally` only after `answer()` and the ledger read finish (`:862-863`). A second request gets 409 and is never queued, and a browser abort can't release the lock early.
- **Error details:** errors map to fixed codes and wording and never include exception text (`:887-919`).
- **Loopback, Origin and CSP:**
  - Vite dev hosts are allowed only when `PARKGUIDE_WEB_DEV=1` (`:81-82`).
  - Writes need an allowed Origin, a same-origin or absent `Sec-Fetch-Site`, JSON content and a bounded `Content-Length` (`:939-949`).
  - CSP and frame headers are set (`:928-955`).
  - The reranker runs offline because `HF_HUB_OFFLINE` is set in `main()`, which `run_web.sh` invokes via `python -m parkguide.web`.

## New substantive defects
None found.

## What source-only review can't establish
- **Gaps in test coverage.** The tests don't exercise:
  - the real paid claim-review cost path, because the fixture injects its own reviewer;
  - the core's full-page quote-limit check, because the fixture wraps the retriever;
  - the real reranker, because `rerank=False`;
  - real Azure, ledger or uvicorn cancellation timing.
- **Cost attribution limits.**
  - Ledger figures are estimates from published prices, not an invoice.
  - Calls with unknown usage are counted at their reserved maximum.
  - The `generation` kind combines answer drafting and claim review.
  - A CLI or Streamlit process spending at the same time would land in this request's window and could also make the embedding status read as a recorded Azure call. The window's `limitation` text discloses this; the embedding status field doesn't repeat it.
  - Per-stage generation and review figures describe only the final successful call; earlier failed attempts show up only in the window.
- **Limits on what the checks prove.** Witnesses are checked to be verbatim, cited and stored, which proves where a quote came from, not that the source supports the claim. "Source review passed" is an AI judgment, not a human-confirmed or guaranteed-accurate answer. Card excerpts are chosen mechanically by word overlap, and saved sources are a snapshot, not live conditions.
