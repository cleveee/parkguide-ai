# ParkGuide web app: final UI correctness pass (Claude Code, claude-opus-5-5)

Date: 2026-10-10. Inputs: `claude-frontend-review.md` and `supervisor-followup.md`, checked against the **current** files.

Scope: frontend files under `web/src` only. No changes to the Python bridge, core RAG/guard/config/data, `app.py` or `AGENTS.md`, and no Git action. No gold, test or secret reads. No servers started or stopped and no paid calls. All new output is plain React text; traffic stays same-origin.

## Already fixed before this pass (verified in current files, not changed)

- **API types match `public_turn`.** `timing.{server_ms,answer_call_ms,pipeline_ms}`, `inspector.ledger_window`, the new embedding statuses, `reason.category`, `history`, `derivation` and `integrity_errors` are all typed and rendered. No `request_ms`, `total_cost_estimate_usd` or `derivation_used` remains.
- **Errors keep their details.** `ApiError.details` is kept, and the ledger window appears in the error card.
- **History counts come from the server** (`history.messages_received/used/scope_reset`). Locally refused other-park turns (`selected_park_mismatch`) are excluded from the history sent.
- **Persistence disclosure.** How it works already states that query hashes/vectors and the budget ledger persist locally, that Azure handles data under its own terms, that `store=false` is only a request, and the exact shared resource.

## Fixed in this pass

1. **Mobile dialog overflow** (browser-confirmed at 375×812).
   - Cause: the Radix `ScrollArea` viewport's `size-full` had no resolved height inside a `max-h`-only flex column, so the viewport grew to 1597 px and spilled past the dialog.
   - Fix: `HowItWorks` and `EvidenceDialog` now use `flex max-h-[min(85dvh,…)] flex-col overflow-hidden` on the dialog, a `shrink-0` header, and a single `min-h-0 flex-1 overflow-y-auto overscroll-contain` body. The `ScrollArea` is removed from both.
   - Long user text, claims, witnesses, excerpts, full saved passages and error text now wrap (`[overflow-wrap:anywhere]` / `break-words`).
   - **Root should re-measure at 375×812**: the dialog should stay within the viewport and its body should scroll.
2. **Witnesses first.**
   - Source cards now lead with "Cited for claim N" and the verified **Reviewer witness** quotes. The mechanical snippet follows as a **Context excerpt (chosen by word overlap, not by the reviewer)**.
   - In the evidence dialog, the claims and AI-review block with witnesses comes first. The **Context excerpt** follows, with a note that it is not the reviewer's evidence.
   - Provenance is unchanged: excerpts and witnesses both come only from the server's validated stored passage.
3. **Errors, Retry and Stop.**
   - The error card keeps the server message and the recorded ledger spend. When no ledger record was returned, it says spend is unknown here.
   - Retry is hidden for deterministic failures: validation, reranker length, budget, pricing, configuration, cache integrity, local resource, index/database state, and Host/Origin/JSON/body errors.
   - For other errors, the button reads "Retry (may spend again)", with a warning that retrying can make new paid Azure calls.
   - A 409 `busy` is titled as not processed, and its Retry carries no spend warning.
   - The composer's send button no longer acts as a stop button. `onStop` was removed from `PromptInputSubmit`, which stays disabled while a reply is pending. **"Stop waiting"** (an outlined, explicitly labelled button on the pending turn) is the only stop control.
   - The stopped-turn note and the park-switch/new-conversation confirmation now say the server keeps working, including paid calls, and that a new question gets "busy" until it finishes.
4. **History safety.**
   - Other-park refusals are still excluded.
   - A pair whose question or `history_content` is blank is skipped, because the server rejects blank history content.
   - A reply whose `selected_park` differs from the selected park is now settled as an error turn (`response_park_mismatch`, with its ledger window when present) instead of returning while the turn stays pending forever.
5. **Metadata failures.**
   - The footer shows the real load error (message, code and HTTP status) with a **Reload metadata** button, which calls `loadMeta` in `App.tsx`.
   - When metadata loads but chat isn't ready, it shows the server's `meta.chat.reason` code. The hard-coded gold-draft sentence is removed.
6. **`formatUsd`.** Zero stays `$0.00`. Positive values below $0.0001 use scientific notation with three significant digits (for example `$1.20e-7`), and values below $0.01 use three significant digits. No positive estimate rounds to zero.
7. **Local-check wording.**
   - The How it works step now says pattern checks refuse *recognized phrasings* of other-park, live and private requests. Differently worded requests can continue to search, drafting and review, where they may still be refused. It points to the per-turn Data flow as authoritative.
   - The Data flow "passed" text now says no recognized pattern matched and that this doesn't prove absence.
   - The local-preflight refusal label states only what happened on that turn: a recognized pattern stopped it, and nothing was sent to Azure for that turn.
   - This matches the observed "FAKE-LOCAL-123" case, which was refused after retrieval and generation.

## Checks run

| Command | Result |
|---|---|
| `npm --prefix web run build` (`tsc -b && vite build`) | Passed. JS 606.55 kB (187.33 kB gzip), CSS 81.38 kB; the existing >500 kB chunk warning remains |
| `npm --prefix web run lint` | 0 errors; 0 warnings other than the 11 known `only-export-components` fast-refresh notices |
| `.venv/bin/python -m pytest -q` | **397 passed** (no Python file changed in this pass) |
| Grep of `web/src` for `dangerouslySetInnerHTML` / `innerHTML` / `eval(` | None. The dashboard template's pre-existing `innerHTML` code is untouched; its web-app hook uses `textContent` |

The rebuilt `web/dist` is served from disk by the running server. No backend change was made, so no restart is needed for API compatibility; a browser reload picks up the new bundle.

## Dashboard hook (unchanged, pending)

`scripts/build_dashboard.py` loads `artifacts/ui/web-app-verification.json` only if it exists, plus `artifacts/ui/web-app-preview.png` if that also exists. It is separate from the legacy Streamlit proof. The template shows "Live web-app verification is pending…" when the file is absent. No such file was written and `dashboard/index.html` was not edited; the root writes the record and rebuilds the report.

### Expected `artifacts/ui/web-app-verification.json` schema

Fields read by the template and builder:
- `verified_at_utc`: ISO-8601 string, shown as the local time.
- `summary`: a one-line string shown after the time.
- `api_usage.ledger_after`: optional. If present, it is added as a "Web-app check" ledger snapshot and must contain a numeric `events`, like the other snapshots.
- Everything else is displayed verbatim as JSON.

Suggested shape, with every value filled from real observations only:

```json
{
  "verified_at_utc": "…",
  "verifier": "root agent (browser automation)",
  "server": {"url": "http://127.0.0.1:8513", "bundle": "web/dist/assets/index-<hash>.js", "backend_started_at_utc": "…"},
  "summary": "…actual outcome…",
  "viewports": [{"width": 1440, "height": 900}, {"width": 375, "height": 812, "dialog_fits_viewport": true, "dialog_body_scrolls": true}],
  "conversations": [{"park": "yose", "turns": [{"question": "…", "status": "answer|refusal|clarification|error",
                    "reason_code": "…", "reason_category": "…", "sources": 0, "ledger_events": 0, "ledger_cost_estimate_usd": 0.0}]}],
  "cancellation": {"stop_waiting_clicked": true, "followup_status": 409, "late_reply_discarded": true},
  "api_usage": {"ledger_before": {"events": 976, "estimated_committed_usd": 0.746827504}, "ledger_after": {"events": 0, "estimated_committed_usd": 0.0}},
  "screenshots": ["artifacts/ui/web-app-preview.png"],
  "browser_console_errors": [],
  "limitations": ["AI source review is not human verification", "…"],
  "human_review_pending": true
}
```

The `ledger_before` values come from `supervisor-followup.md`. Every other value above is a placeholder to replace with real measurements.

## Pending and limitations

- **Still to test in the browser** (root): real conversations, refusals and cancellation; the 375×812 dialog re-measurement; keyboard and screen-reader behavior; reduced-motion behavior. Nothing here claims browser QA, human accuracy or a paid-chat result.
- The local pattern checks in the core still miss differently worded private or live requests. This pass changed only the UI wording; core modules stay unchanged by instruction.
- The Retry policy is a client-side list of error codes. A new server error code defaults to "Retry (may spend again)" with the spend warning, which is the cautious default.
- The bundle is still a single chunk of about 607 kB.
