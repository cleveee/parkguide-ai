# Evaluation questions versus the current product

Static audit of checkout `d7c4918` on October 10, 2026. No application or provider requests were made. References remain AI proposals, not human-verified gold.

## Actual functionality

The React chat selects exactly one of `yose`, `yell` or `grca`. `POST /api/chat` requires that selected park, the question and bounded completed history. Retrieval and factual evidence stay within that park. A question naming another park cannot switch this conversation's scope.

Changing the selector in a conversation with messages preserves it and opens a separate chat. The new chat starts without the previous park's history. Reopening a saved chat restores its own park and history. See [CHAT_PERSISTENCE.md](CHAT_PERSISTENCE.md), `src/parkguide/web.py:198`, `src/parkguide/chat.py:230` and `web/src/App.tsx:244`.

The data is a captured public NPS snapshot. Saved schedules and historical status descriptions can be answered with their dates and qualifications. Live availability, exact future weather, private bookings and personal medical clearance cannot be verified from it. Questions asking for these are useful **refusal tests**, not requests for supported product functionality.

## Original suite findings

The complete machine-readable reviews are [original-gold-audit.json](../artifacts/evaluation-functionality/original-gold-audit.json) and [conversation-audit.json](../artifacts/evaluation-functionality/conversation-audit.json).

| Cases | Finding | Revision |
| --- | --- | --- |
| G022–G025 | Each expects an answer combining two parks. All four trigger scope refusal under every selector. | Replace with comparisons inside one selected park. Keep foreign-park prompts only in a separate refusal-control suite. |
| All 40 original gold questions; diagnostics/dialogues | Definitions/runners omit explicit selected-park setup. Legacy evaluation calls `answer` without `selected_park`. | Supply park setup and use the real selected-park API/service path. Old results are not proof of current UI compliance. |
| G038–G039, D011–D012, T04-1 | Some rubrics ask which park even though the selector already supplied it; history also affects ambiguity. | Use fresh chats for missing-reference cases and clarify only the missing place, item, pass details or starting point. Rewrite T04-1 to “Is it open?”; the old general opening-hours wording could legitimately be answered. |
| T01-3, T03-2, T03-3 | Expect a second park's facts inside the first park's conversation. | Replace with same-park date changes and follow-up comparisons. A selector change is a separate UI-transition test, not a turn carrying cross-park history. |
| G011, T02-2 | The reference's required facts turn a blank drinking-water table cell into a categorical absence. | Require “not marked in the saved table”; preserve DW/TF column identity and add the table header. |
| G010 | Requires the globe's weight even though the question asks what it illustrates. | Require the subject illustrated; weight is optional. |
| G030 | “Tonight” is tied to a past literal date, and `vacant` bypasses the deterministic vacancy preflight. | Remove the stale literal date; retain the live-inventory refusal requirement. Model-dependent handling is still an implementation gap to test. |
| Nonanswer rubrics | Literal keyword coverage can penalize valid controlled refusals or clarifications. | Grade missing/unavailable facts and behavior semantically; do not require exact prose or identifiers to be repeated. |

The original gold audit classifies 32 compatible items, two needing setup/rubric adaptation, and six expectation mismatches. Those six include the four unsupported comparisons, the table-reference defect, and an implementation quality gap in G035. The last two are not missing product features. Compatibility assumes the explicit park fixture provided by the audit.

The diagnostic audit finds eight compatible cases and four requiring setup/grading adaptation. The dialogue audit finds ten compatible turns, four requiring adaptation and four expectation mismatches (three cross-park turns plus the table-cell defect).

## Product-aligned revision proposals

Saved separately under [product-scope-v1](../data/evaluation/product-scope-v1/manifest.json); the original drafts and authoring seal remain unchanged:

- [gold-candidates.jsonl](../data/evaluation/product-scope-v1/gold-candidates.jsonl): 40 candidates, preserving original IDs/questions as lineage and supplying `selected_park` plus empty history.
- [dialogue-candidates.jsonl](../data/evaluation/product-scope-v1/dialogue-candidates.jsonl): six same-park, three-turn plans. A future runner must append actual completed assistant responses and their evidence IDs, never reference answers.
- [diagnostic-candidates.jsonl](../data/evaluation/product-scope-v1/diagnostic-candidates.jsonl): 12 diagnostics with park setup and corrected clarification/grading behavior.
- [scope-controls.jsonl](../data/evaluation/product-scope-v1/scope-controls.jsonl): four foreign-park prompts expected to refuse. These are excluded from the knowledge suite and must not count as failures to answer cross-park facts.

The four knowledge comparisons now cover Yellowstone bear versus bison distances; Yosemite quiet versus generator hours; Grand Canyon pet versus service-dog shuttle access; and Yosemite paved Mirror Lake access versus its unpaved loop, with the Wawona Meadow Loop exception. Every factual reference uses evidence from its selected park.

The revision keeps the original category counts: 15 factual, six multi-hop, four comparative, four temporal, eight unanswerable and three ambiguous/adversarial. Repeated evidence/topic families are grouped for future split review. No dev/test split has been created; some “multi-hop” questions still combine facts from one page and should not be advertised as requiring multi-document reasoning.

All revised records have `human_review_pending`, null human reviewer/date and `benchmark_eligible=false`. They were revised after earlier development outputs and disclose that authorship; they do not inherit the original claim of being authored before outputs. The existing legacy evaluator is **not compatible** with this revision merely because a `selected_park` field has been added.

The earlier independent 18-question study remains a separate corpus-QA study. AL07–AL09 explicitly allow cross-park answers, so their labels do not establish product correctness. Three Codex subagents and Claude Code labeled that study; their original outputs and comparison remain intact. No additional Claude run was made for this audit.

## Verification and remaining gaps

[offline-validation.json](../artifacts/evaluation-functionality/offline-validation.json) checks all 74 candidate/control/diagnostic/turn field shapes, 103 evidence units against exact frozen source text, headings, hashes and selected-park URLs, and the 12 combinations of original cross-park questions with three selectors. These checks passed. This establishes source identity and static contracts, not semantic reference accuracy, retrieval performance, live chatbot quality or conversation correctness.

Independent revision review also caught “how far below the rim” ambiguity in T02-1 and incomplete quote support for several original reference qualifiers. The revision explicitly asks for one-way trail distance, records the comparison calculation, and adds source spans for those qualifications and the South Kaibab section label. See [revision-independent-review.json](../artifacts/evaluation-functionality/revision-independent-review.json) for the review and disposition of findings.

The independent reviewer rechecked the final revision, confirmed all 13 discovered reference/rubric findings resolved, and found no remaining material source-support or one-park-scope defect. This is an AI review result; human adjudication and actual product execution remain pending.

The source DB and original gold hashes are unchanged. No provider calls, application requests or final-test runs were made. Reproduce offline checks with:

```sh
.venv/bin/python scripts/check_product_scope_candidates.py
```

Known implementation issues remain visible in the proposed requirements:

- G035's model-refusal path substitutes generic NPS prose and can lose the required qualified-clinician referral. The revision **retains** the clinician requirement; generic refusal alone must not be scored as fully passing this quality check.
- G039 can return a generic place/date/detail clarification instead of asking which pass type. Asking for meaningful pass details remains the target behavior.
- G030's `vacant` wording needs generation/review rather than the current local live-vacancy guard. No fabricated vacancy was observed in this static audit.

The questions still do not cover the full product. Add explicit UI checks for changing parks into a fresh chat, reopening the old park/history, isolation of late responses during switching/closing, reload and interrupted requests. Existing frontend storage/browser tests cover many of these mechanisms but are not NPS answer-quality tests. Keep those outcomes separate.

The 40 knowledge candidates also still lack PDF extraction coverage and broad within-park paraphrases, mixed supported/live requests, negation and long-history stress. A small review set should sample those intentionally and balance source families, rather than simply increase the count of easy lookups. Human source verification and an independently reviewed, grouped split remain necessary before formal gold evaluation.
