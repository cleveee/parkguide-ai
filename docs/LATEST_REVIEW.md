# Final candidate: provisional AI semantic review

Reviewed all 48 final baseline outputs and all 18 final dialogue turns. These are diagnostic examples used during iteration, not held-out gold results. Every review remains **human review pending**; no human-verified accuracy or citation-support figure is claimed. The same agent authored the fixtures before seeing outputs and now reviewed them against the supplied contexts and the frozen full corpus. This is a second AI check, not an independent human assessment.

Inputs: baseline `20261010T042905Z-54d33f15`, dialogues `7bbd1b0ccdb649edbaf2b64ccc9797e3`, corpus 155 saved NPS documents, SHA256 `2d1285fed3c6b9960496999daa4dff4656df40c20c10d89c821c913db8d9589d`. Baseline input SHA256 `29b0eb113a99ca83641342507c9ba4bc28e25d6bdd1d08ee16dbfef0c0ae7c20`; dialogue input SHA256 `77aeeeb943a12a704d84f8d86dfe2246db43c6479fb28b224d64fe7d21cad2a3`. Earlier 42-row review remains in `artifacts/reviews/pre-runtime-semantic-review.jsonl` with SHA256 `460ca298d0d69a55af8f63cc8cddd84e929ce33faa312a83fd238d60e8d7f1cc`. Complete 66-row judgments and source witnesses are in `artifacts/reviews/latest-semantic-review.jsonl`.

## Observed outcomes

Semantic review checks the delivered answer for correct facts, completeness needed by the actual question, scope, and appropriate refusal/clarification. Optional facts from the fixture are not mandatory when the user did not ask for them. Any substantive incorrect extra guidance still counts as failure. Uncertain measurement or causal wording stays uncertain instead of being forced into a pass or fail.

| Configuration | Clear correct | Incorrect | Uncertain | Delivered claims supported / total | Unsupported; uncertain claims |
| --- | ---: | ---: | ---: | ---: | --- |
| B0, closed book | 8/12 | 4 | 0 | 9/13 | 3; 1 |
| B1, fixed chunks + BM25 | 11/12 | 1 | 0 | 11/11 | 0; 0 |
| B2, fixed chunks + dense | 11/12 | 1 | 0 | 12/13 | 1; 0 |
| B3, structure + hybrid, selected | 12/12 | 0 | 0 | 15/15 | 0; 0 |
| Six dialogues, three turns each | 16/18 | 0 | 2 | 21/23 | 1; 1 |

The selected B3 plus dialogue sample has **28 clear-correct responses, no clear incorrect responses, and two uncertain responses out of 30**. Its delivered claim count is **36 supported of 38**, with one unsupported causal extension and one ambiguous measurement claim. Unsupported and uncertain claims remain in the denominator; refusals and clarifications with no factual claims contribute no claim denominator. These are provisional AI findings on reused diagnostic cases, and cannot establish a 90% formal benchmark result. Across all 54 RAG responses (B1/B2/B3 plus dialogues), 59 of 62 delivered claims are supported, two unsupported, and one uncertain. Across all 66 responses, 58 are clear correct, six incorrect, and two uncertain. B0 has no citations; its factual claims were compared with the full corpus and citation support is N/A. B0 D004 correctly denies train service; its additional usual-arrival claim is plausible from vehicle guidance but lacks direct modal-share evidence, so that claim is uncertain.

## Actual failures and remaining cautions

The AI-provisional **B0 incorrect subset is D001, D002, D006, D008**. D001 invents a 2 pm check-in time; D002 sets the RV maximum to 35 rather than 40 feet and omits the requested eight-site count; D006 gives only the 30-inch wheelchair width and omits the essential 48-inch length; D008 says 25 instead of 23 miles. The selected B3 answers all four questions correctly. This four-item comparison is a descriptive subset of the diagnostic sample, not a separate benchmark.

B1 D001 retrieves the noon fact in two passages and generates it, but the runtime citation reviewer rejects the wording that combines checkout with the arrival date; the pipeline then refuses the entire answer. The FAQ itself uses that awkward phrase. This is one **probable support-review false rejection / over-withholding**, with a legitimate date-wording concern: correcting the phrase would preserve the supported noon answer. It is not a human-confirmed reviewer false positive.

B2 D001 gives the right noon time but adds an unsupported check-in procedure. NPS says to proceed to the campsite on a late arrival, then check in at the **kiosk or reservation office** next morning. The response says **campsite or kiosk** next morning. Its runtime reviewer accepts the incorrect substitution, a provisional false acceptance.

T02/1 remains uncertain: the table's **1.5 miles (2.4 km)** is along-trail distance. The question and answer both say **below the rim**, which could mean vertical depth; the table elevations give **7260 − 6120 = 1140 feet**. The response does not resolve this distinction. No confirmed wrong distance is asserted under the along-trail interpretation, and this turn is not a clear semantic pass.

T05/3 correctly says an ordinary soft pack cannot replace the required food container. Its extra instruction says leaving pockets unzipped will **deter animals**. The source says this lets nocturnal visitors snoop without gnawing gear; that is a narrower rationale and does not establish animal deterrence. The procedural instruction is sourced, but the causal extension is unsupported. The whole turn remains uncertain because “deter” may loosely refer to gnawing rather than animals approaching.

B3 D001's core noon answer is supported. Its extra 10 am next-day deadline matches the newer regulations page, while the older FAQ gives a noon forfeiture threshold. The answer does not identify the disagreement. This remains a source-conflict warning requiring park/human confirmation, not a fabricated main time.

## Conversation and reviewer checks

All 18 saved histories are correct snapshots: **0, 2, 4 prior messages** per dialogue, exactly matching the actual preceding user messages and rendered assistant responses, including citations. No conversation row is missing or records an exception. The table's Cedar Ridge drinking-water answer now cites its actual blank DW row. T02/3's delivered difference is correctly and transparently computed as **3 − 1.5 = 1.5 mi** from the same column and source cells; `raw_response` retains the model's two endpoints, and `source_derivation` records the deterministic completion. Credit this result to the complete pipeline rather than to unaided model arithmetic.

Final dialogues correctly change year and park, resolve bear-distance follow-ups, ask for clarification before an unspecified entry question, use Hetch Hetchy's daylight restriction for midnight, refuse private booking lookup, reject an injected drone override, and refuse personal medication dosing while referring to qualified help. Hetch Hetchy's response adds park-wide snow/parking context without claiming the specific Hetch Hetchy road closes in that period.

The runtime reviewer made **63 claim decisions: 62 accepted and one rejected**. This AI audit agrees with 59, identifies one clear false acceptance (B2 D001 procedure), flags two uncertain acceptances (T02/1 dimension; T05/3 causal wording), and flags the one probable false rejection with the checkout-date caveat (B1 D001). Denominators: one probable over-rejection among one rejected decision and 63 total decisions; one clear false acceptance among 62 accepted decisions. These observed disagreements are not a calibrated reviewer error rate; human adjudication is still missing.

Lexical diagnostics miss many good paraphrases and appropriate abstentions. Their false-failure IDs relative to this AI semantic review are B0 `D003, D004, D005, D007, D010, D011`, B1 `D002, D003, D005, D007, D008, D009, D010, D011`, B2 `D002, D003, D005, D007, D008, D009, D010, D011`, B3 `D003, D005, D007, D008, D009, D010, D011`, dialogues `T04-3, T05-1, T05-2, T06-2, T06-3`. Conversely, lexical grading passes the wrong-time B0 D001, the unsupported-procedure B2 D001, and the ambiguous T02/1. T04/3's daylight rule already excludes midnight, even without an explicit “no.” Neither lexical flags nor this AI review should populate human verification fields.

The remaining verification step is human adjudication of the untouched 40-item gold drafts and these explicit diagnostic cautions. No provider call, gold edit, code change, commit, remote, push, or deployment was performed by this review.
