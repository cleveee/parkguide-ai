# Independent source-link review

Review scope: source attribution in the local Streamlit UI and offline run dashboard. No provider requests, gold edits, usage-ledger writes, commits, or external messages were made by this review.

## Existing behavior

The answer renderer already resolves final claim evidence IDs against saved retrieval contexts and renders inline NPS citations. Streamlit currently exposes all selected contexts only inside its search-trace expander, including passages not cited by a delivered claim. The dashboard currently HTML-escapes the rendered answer, so Markdown citations appear as text.

## Required attribution behavior

- Source cards derive only from an answer's final `response.claims[].evidence_ids`, resolved against that answer's `contexts`.
- `raw_response`, withheld claims, previous replies, candidates, and uncited contexts never contribute cards.
- Closed-book, refused, clarification, and failed responses produce no source cards.
- Unknown evidence IDs and invalid URLs do not create links. Clickable source URLs stay within HTTPS `www.nps.gov` and the approved park paths.
- Deduplicate a page while preserving each distinct cited passage and its associated claim numbers.
- Exact saved passage text, source heading, capture timestamp, content revision hash, and extracted source date should remain inspectable. Extracted dates are not guarantees of current applicability.
- A source link opens the current official page. It may differ from the captured text used for the answer; the snapshot caveat must be visible.
- PDF page anchors come only from recorded `PDF page N` headings. For fixed chunks this identifies a recorded starting page; a chunk can span later pages, so it does not prove a complete page range.
- Escape text and titles when rendering HTML or Markdown. Unknown, model-written, or history-supplied URLs must not be parsed as answer evidence.

## Reconciled saved-run counts

Read-only audit over all seven dashboard stages:

| Measurement | Count |
| --- | ---: |
| Saved attempts | 305 |
| Delivered responses | 304 |
| Grounded answers | 196 |
| Grounded refusals | 56 |
| Clarifications | 28 |
| Closed-book responses | 24 |
| Claim-to-passage references, including repeated references | 472 |
| Distinct cited passages summed per answer | 336 |
| Distinct source-page cards summed per answer | 307 |
| PDF claim-to-passage references, including repeated references | 23 |
| Uncited retrieved passages summed per grounded answer | 644 |
| Unknown cited IDs / unexpected source URLs / missing provenance fields | 0 |

Latest selected B3 single-turn run plus six dialogues: 30 responses contain 23 grounded answers, 32 distinct page cards, and 33 distinct cited passages. Seven nonanswers produce no cards. The one final cited PDF passage has the recorded heading `Yosemite Guide - Volume 51, Issue 8 > PDF page 3`.

Counts use the saved final delivered claims, not raw model output. Source-card counts are summed per answer rather than distinct global source URLs. Initial B0 traces omit the `closed_book` flag; row configuration identifies those 12 additional closed-book responses. They have no evidence IDs and correctly receive no cards. No new API calls were needed.

## Code-review status

The new `src/parkguide/source_links.py` and `app.py` were independently inspected. Helper readback across all 305 attempts produces exactly 307 page cards and 336 distinct passages; 196 responses have cards and 109 attempts do not. There are 22 distinct anchored PDF passages, compared with 23 repeated PDF claim-to-passage references. Latest selected 30 responses produce 32 cards, 33 passages, and one anchored PDF passage. No refused/clarification response produces cards and all excerpts stay within 25 words per page.

Requested small refinements were implemented: the 25-word excerpt budget is distributed across passages using verbatim relevant windows, malformed/control/encoded-traversal URLs are rejected, and headings render as plain text. Independent readback of all 305 attempts found zero over-limit page excerpts, zero nonverbatim excerpts, and zero nonempty cited passages without a displayed excerpt. The latest same-page multi-passage case is T05/3 food storage; both passages now receive excerpts. T02/3 arithmetic cites a single saved passage containing both source rows.

Four malformed URL probes (encoded traversal, quote-bearing path, newline, and encoded control character) were rejected. A captured URL fragment is removed before producing the canonical official-page link. Dashboard card rendering escapes dynamic labels, URLs, headings, and excerpts. The wording `Cited for claim` is recommended instead of claiming a deterministic semantic support guarantee.

No attribution-boundary issue remains in the saved-run replay. Browser verification remains root-owned.

## Final implementation and report review

Read-only inspection of the final app, attribution helper, dashboard builder/template, and source-link/dashboard documentation found no concrete regressions. The final wording says `Cited for claim`, preserving the distinction between attribution and semantic verification. The HTML uses bounded excerpts and retains full text only in the original local result artifacts.

Independent comparison of every exported historical row against the preserved stage audit found zero original measurement/answer metadata changes. Derived source cards match a fresh helper replay for all 305 attempts: 307 cards and 336 passages. Every exported source-manifest hash matched its current input file at review time.

The cost separation also reconciles: the preserved technical audit has 710 ledger events at $0.389990038; the live source-link check adds exactly three returned-usage events totaling $0.001801842; the actual ledger and dashboard export both show 713 events at $0.391791880. Stage costs are preserved and are not added to the full ledger total. No providers were called during this independent review.

Root-owned browser evidence records the visible source card/excerpt and successful navigation to the official Yellowstone Current Conditions page. Final dashboard browser verification was still marked pending in the saved evidence when this review ran; that remaining root check does not alter the successful read-only attribution/data review.
