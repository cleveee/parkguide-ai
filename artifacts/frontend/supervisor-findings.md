# Supervisor findings to resolve before web acceptance

These are based on the actual first FastAPI bridge, not the earlier hypothetical integration review. Preserve the core RAG/guard modules and all historical artifacts. Claude Code should implement the fixes; Codex will test them independently.

1. `public_turn` labels `response.cost_estimate_usd` as `total_cost_estimate_usd`. Core response cost excludes query embedding, failed retries, and some failed review attempts. Capture the actual ledger event window before/after `core.answer` while holding the answer lock, including unknown-usage reservations and failed calls; label it an estimate, not an invoice. Include per-kind attempt/token totals where observed. Retain separate successful-call answer/review metrics. State the limit that other CLI/legacy processes can affect a ledger window. Do not invent unrecorded tokens or treat missing usage as zero. Add an offline regression for failed-attempt/embedding cost inclusion.

2. `_classify` says “no request was sent” for budget exhaustion. Exhaustion can occur after a paid embedding or generation stage. Use accurate partial-stage wording and expose a safe measured event window for failed requests where possible. Never imply a browser abort prevented server calls.

3. `_observed_embedder` observes cache-file presence before the shared call. Be precise about what proves a hit or an Azure request; another process can create a cache entry between checks. Prefer actual request-window embedding events to label a network call. A file-presence observation should remain explicitly described as that observation if no stronger evidence exists.

4. Keep review witness numbering mapped to the retained delivered claims. Supported review decisions are over the original draft; skipped claims must not shift a witness onto the wrong delivered claim. Only show witnesses for delivered answers, ensure each witness belongs to that claim's cited evidence, and keep rejection reasons/raw draft payloads out of exports. Include the regression recommended in `claude-contract-review.md`.

5. Provide safe source-table arithmetic details when `source_derivation` exists, not just a boolean, so the user can inspect the actual cells/units/operation. Label nested/overlapping timing metrics correctly and successful-call timings separately from whole-request time.

6. Surface `history_scope_reset` and actual bounded history message count in the Data flow view. Distinguish local preflight refusal, model refusal, validation failure and reviewer failure. Ensure a pending old-park response cannot repopulate chat or evidence after a park switch/new conversation.

Also review `artifacts/frontend/claude-code-review.json` when ready. Do not claim final browser QA or human accuracy from a passing build or offline tests.

## First localhost observations (read-only UI checks; no paid chat yet)

- `/api/health`, `/api/meta`, and `/` return 200. CSP restricts connections/assets to this origin. Selected Yosemite correctly shows 56 documents and 1,377 active structure passages; the corpus browser distinguishes all 5,405 chunks/vectors and the two builds. Corpus source reader and Escape focus behavior work; no browser error logs so far.
- Date wording is inconsistent: the sidebar and corpus say “captured today” while the date reads Oct 9, 2026 and the user's current local date is Oct 10. A less-than-24-hours age bucket should say “under 24 hours ago”, or compare actual local calendar dates. Keep exact capture timestamp/timezone available.
- Desktop document preview currently defaults to a narrow 384px drawer and stacks 20 sections plus 10 passages in one long scroll. Use a Tailwind-default wider panel (for example `sm:max-w-xl`) and useful Sections/Indexed passages tabs, with counts and bounded pagination retained. Source evidence should open on the relevant cited passage. Keep measured details available, but progressively disclosed.
- Avoid large animated backdrop blur in drawers; a restrained dim overlay is sufficient. Preserve opacity/transform animations at 200ms or less and reduced-motion handling.
- The How it works dialog explains the six stages clearly. Add that query hashes/vectors and the budget ledger persist locally, while conversation text stays in browser memory, and show the exact shared Azure resource identity. Do not imply that all user-derived data remains only in browser memory or that Azure has no provider retention merely because `store=False` is requested.
