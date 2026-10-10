I found 7 substantive defects. Three need fixing before the UI is trusted: the inspector no longer matches what the API sends, the Retry flow can bill twice, and the conversation history can be silently dropped for several turns. I only read source; nothing was run, built or rendered.

## Findings (most serious first)

**1. The inspector reads fields the server no longer sends. It shows "Not captured" for values that were captured, and hides the one thing users need to know: whether the question left the computer.** (High)
- **Timing:** `api.ts:140` expects `timing.request_ms`, but `web.py:775` sends `answer_call_ms` / `pipeline_ms` / `server_ms`. "Server request time" (`inspector.tsx:312`) always shows Not captured.
- **Cost:** `inspector.total_cost_estimate_usd` (`api.ts:184`) is never sent. "Estimated model cost (this turn)" (`inspector.tsx:314`) is always Not captured. Meanwhile the per-request cost the server does send (`ledger_window.cost_estimate_usd`, `web.py:436-478`, 819), which includes embedding, failed attempts and retries, is ignored. `inspector.tsx:253` still says embedding cost isn't captured by this view.
- **Embedding status:** the client knows `cache_hit | sent_to_azure | not_requested` (`api.ts:162`). The server sends `not_captured | azure_request_recorded | azure_attempt_failed_recorded | no_azure_request_recorded | not_requested` (`web.py:483-494`). Neither explanation at `inspector.tsx:249-255` ever renders, and a failed Azure attempt shows as "ran".
- **Preflight:** `inspector.tsx:237/246` guesses a preflight stop from `!retrieval.ran && reason` and then states "Nothing left this computer". The server already sends `reason.category` (`web.py:588`), which the client type lacks.
- **Unused fields:** `derivation` (calculation trace for table-based claims, `web.py:822`) and `history` (`web.py:776`) are ignored. The `derivation_used` field the client expects doesn't exist.
- **Fix:** regenerate or hand-sync the types from `public_turn`. Render the ledger window as "cost of this request", map every embedding status to plain wording, and drive the preflight copy from `reason.category === "local_preflight"`. Add a typed contract test or fixture shared by both sides.

**2. Retry and stop can cause repeat billing, and the error card hides what was spent.** (High)
- `ErrorTurn` always says "Request failed — no answer was produced" and offers Retry for every error (`assistant-turn.tsx:103-116`, `chat-view.tsx:149-153,176`). The failed question is also put back in the composer (`chat-view.tsx:143`).
- After a 502 `model_request_failed` (`web.py:890`), a `network_error`, or a timeout, model calls may already be recorded and billed. The server says so (`_EARLIER`, `web.py:877`) and attaches `error.details.ledger_window` (`web.py:861`), but `request()` drops `details` (`api.ts:254-256`).
- Retry is pointless for deterministic failures: `invalid_request`, `question_too_long_for_reranker`, `budget_exhausted`, `pricing_missing`.
- The composer's spinner button doubles as a stop button (`chat-view.tsx:220-225` with `prompt-input.tsx:1248-1278`), so one stray click abandons a reply that is still billed. The next question then gets 409 `busy` (`web.py:834-836`).
- **Fix:**
  - Keep `details` on `ApiError` and show the recorded spend in the card.
  - Offer Retry only for 409, network and other non-billed codes. For 5xx, add "model calls may already have been made"; hide Retry for deterministic 4xx/503.
  - Don't pass `onStop` to `PromptInputSubmit`; keep the explicit "Stop waiting" button.
  - Mention the 409 in the stop and park-switch confirm copy (`App.tsx:326`).

**3. One mention of another park wipes the whole conversation history for up to six later turns, and the UI says something different.** (High/Med)
- `chat.py:248-251` drops all history if any message names another park. The client keeps resending that message as long as it is within the last 12 (`use-chat.ts:51-57`). Example: in Yosemite, a user asks "what about Yellowstone?" and gets refused; every later follow-up then loses all context.
- The notice says "Earlier turns mentioning another park were not sent as context" (`assistant-turn.tsx:161-163`), which is wrong on both counts: all turns are dropped, and they were sent.
- The inspector's "N prior message(s)" is computed in the browser (`App.tsx:172`) instead of from the server's `history.messages_used`.
- A further risk: the server rejects blank history content (`web.py:142-143`), and `history_content` can be `""` (`web.py:723,768`). One empty refusal or clarification would make every later request in the conversation fail with 422.
- **Fix:** leave turns flagged `history_scope_reset` (and other-park refusals) out of future history, skip empty content, correct the copy, and display `messages_received` / `messages_used`.

**4. "Sources used" cards show a keyword-matched snippet, not the quote the reviewer actually used as support.** (Med)
- `source_links.py:86-106` picks a ~25-word window per page, split across the page's passages (a page with 5 cited passages gets about 5 words each), chosen by word overlap with the claim.
- `source-card.tsx:45-53` shows that snippet next to "Cited for claim N". The verified witness quotes only appear inside the dialog (`evidence-dialog.tsx:53-63`), and they aren't highlighted in "Full saved passage".
- **Fix:** lead each card with the verified witness quote(s) and label the snippet "context excerpt", or highlight the witness spans inside `saved_text`.

**5. The data-retention statements are incomplete.** (Med)
- `how-it-works.tsx:72-73` ("The server does not store it") and `App.tsx:144` are accurate about the transcript. But query embedding vectors and their SHA-256 hashes are persisted under `data/embedding-cache` (`web.py:400-410`, `embedding_cache.py:66`), and the retrieval query can include topics carried over from earlier turns (`web.py:907`).
- The dialog subtitle "what stays on this computer" (`how-it-works.tsx:44`) says nothing about how Azure handles the question, snippets and history it receives.
- **Fix:** state the on-disk vector cache and that Azure data handling follows that resource's terms.

**6. Mobile and short screens: dialog content probably can't scroll, and long text is cut off.** (Med — confirm in a browser)
- The Evidence and How-it-works dialogs (`evidence-dialog.tsx:108,129`, `how-it-works.tsx:41,46`) put a `ScrollArea` inside a container that only has `max-h`. The root has no `overflow-hidden` and the viewport is `size-full` (`scroll-area.tsx:13-20`), so the viewport's height likely doesn't resolve and content spills past the dialog instead of scrolling.
- `MessageContent` is `overflow-hidden` (`message.tsx:58`), so long unbroken user text (`assistant-turn.tsx:61`) gets clipped. Monospace witness quotes (`evidence-dialog.tsx:58`) are likewise clipped in the hidden-overflow viewport.
- **Fix:** use a fixed `h-[min(85dvh,48rem)]` or a plain `min-h-0 flex-1 overflow-y-auto` div (the Inspector and DocumentSheet already do this), and add `break-words` / `[overflow-wrap:anywhere]`.

**7. If metadata fails to load, chat is disabled for the wrong stated reason, with no way to retry.** (Med-Low)
- `getMeta` runs once with no retry (`App.tsx:164-168`), and `chatReady` defaults to false (`App.tsx:197`).
- The footer then hard-codes "disabled until the 40 source-based gold drafts are frozen" (`chat-view.tsx:231-233`). That is wrong when the real cause is a load error, and it exposes internal development detail. The server's `meta.chat.reason` is ignored.
- **Fix:** show `metaError` or `meta.chat.reason`, plus a Retry button.

## Behaviours I confirmed in the code
- **Stale replies are discarded.** Reset, park switch and stop-waiting all bump an epoch counter and abort the request. Late replies are ignored, and the `finally` block only clears state for the current epoch (`use-chat.ts:30-46,67,72,80`). Park switch and clear go through `reset`, close the evidence dialog and inspector, and ask for confirmation first.
- **Double submission is blocked**, via the `inflight` ref, the Enter-key path's `pending` throw, and Retry being disabled while pending.
- **History stays in order and bounded:** user/assistant pairs, sliced to 12 so pairs stay aligned, content ≤ 4000 chars; the server rejects unknown fields and non-alternating history.
- **Only reviewed claims reach the screen.** The server sends claims only after the passage check, review-count match and witness checks pass (`web.py:678-686,549-585`); every witness must appear verbatim in the stored passage and cite its own claim's evidence. Claim numbering in `cited_source_pages` matches `public_claims`. Withheld claims appear only as a count. Refusals get no source cards. Uncited passages appear only in the Retrieval tab.
- **Loading is honest:** an indeterminate spinner, no percentages, nothing shown until review finishes, and latency measured in the browser.

## XSS and external-asset check
I found no XSS path and no external asset leak in the custom surfaces.
- There's no `dangerouslySetInnerHTML`, `innerHTML` or `eval` in `web/`. The Streamdown markdown renderer was removed, and all model and corpus text renders as React text nodes.
- Every `href` comes from `official_source_url`, which allows only `https://www.nps.gov/{yose|yell|grca}/planyourvisit/…` with no query or unsafe characters, plus a `#page=N` for PDFs. The browser doesn't re-check these, so it relies on the server.
- Links use `target=_blank` with `rel=noreferrer`. The server sends a strict CSP (`script-src 'self'`, `connect-src 'self'`, `img-src 'self' data:`), `Referrer-Policy: no-referrer`, and `X-Frame-Options: DENY`.
- Fonts are system-only, `index.html` loads only local assets, and there are no remote images. The only outbound traffic is user-clicked links to nps.gov.

## Recheck after the API and UI changes
- The type contract for everything in #1.
- `exportJson` exports the whole turn object as-is, so any new server field is exported automatically. Check it for safety.
- `send` returns early on a park mismatch without settling the turn, which would leave a spinner forever. It's unreachable today because the server echoes the park back.
- Error `details` handling, and that the 409 copy still matches.
- Under reduced motion, `index.css:91` freezes the spinner; the text still shows it's loading.

## Limits of this review
- No rendering, browser, keyboard or screen-reader testing, so the layout points in #6 are inferred from CSS.
- No typecheck, build or tests were run, and the React version wasn't confirmed.
- I read the Sheet/Select/Tabs primitives and the core `answer()` pipeline only partly.
- Passing AI source review does not establish human-verified accuracy.
