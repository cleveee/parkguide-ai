# Hosted visitor testing

These are **non-gold development diagnostics**, authored from the frozen read-only SQLite sources before any answers in this suite. They are separate from the course gold benchmark and sealed final test. Semantic grades below are AI proposals, not human verification.

**Current outcome:** The production test of backend release `1daf0ab661f711c3f49977255792073af8002c57` on [the production alias](https://parkguide-ai-dh24.vercel.app) gives **17/18 original-suite passes**, plus **two partial results and one refusal failure** in the separate broad-trail set. All fourteen claims delivered across those twenty-one requests have source support and exact stored witnesses. Two answerable questions still refuse, and broad pet-route coverage remains incomplete. All grades are AI provisional, with human review pending; this reused development suite is not an independent accuracy benchmark.

| Check | Latest observed result |
|---|---|
| Latest production original 18-turn suite | 17 pass, 1 fail; all 12 delivered claims supported. Baseline was 11 pass, 4 partial, 3 fail. |
| Original-suite regression | Unpaved Mirror Lake pet follow-up refuses despite correct retrieved source context. Earlier local and production runs passed it. |
| Latest production three added trail variants | 2 partial, 1 fail; both delivered claims are coherent and supported, but no answer meets complete frozen coverage. |
| Cedar Ridge table | Passes on production with row/header and DW-definition witnesses; no current-water guarantee. |
| Local candidate 7 comparison | All 18 originally passed locally; production's one failure remains preserved and was not retried. |
| Coverage limit | Five-passage retrieval can omit Wawona; answers must not invent absent context or imply that a short list is exhaustive. |

The original suite was reused to develop fixes; the extra questions were authored after observing a manual failure. Neither set is an independent accuracy benchmark. All earlier failures and the verified production pass remain preserved below.

## Baseline: October 10, 2026

The deployed origin `https://parkguide-ai-dh24.vercel.app` completed six conversations of three actual user turns each. Each follow-up sent the exact preceding `history_content` returned by `/api/chat`; histories were 0, 2 and 4 messages. All 18 requests returned HTTP 200. The hosted profile reported hybrid retrieval with reranking disabled and the same frozen active build as local SQLite.

The baseline exposed three answerable follow-ups that received no answer: carrying a pet below the Grand Canyon rim, taking that pet on a shuttle, and the saved Cedar Ridge drinking-water table. It also exposed two precision issues and two generic refusal messages that could give a more useful next step.

| Measurement | Observed baseline |
|---|---:|
| Completed actual conversations / turns | 6 / 18 |
| Expected action/status accepted | 15 / 18 |
| Full semantic and usefulness pass, provisional | 11 / 18 |
| Partial precision or refusal-recovery result, provisional | 4 / 18 |
| Answerable refusal/clarification failures, provisional | 3 / 18 |
| Cited source identity/text mismatches | 0 |
| Delivered claim support, provisional | 11 supported; 1 partially supported |
| Per-turn ledgers captured | 18 / 18 |
| Published-price estimate including failed-attempt reservation | $0.012921154 |
| HTTP latency p50 / p95 / maximum | 3.56 s / 16.58 s / 35.79 s |

Action/status checks are operational checks, not semantic accuracy. Source identity checks confirm that the displayed text and IDs exist in the frozen database; they do not independently establish claim support. Latency uses linear interpolation over the 18 fresh HTTP requests and includes provider retry/cold-start effects. One failed generation attempt retained a conservative cost reservation; the estimate is not an invoice. Hosted instance ledgers are ephemeral, so the runner independently accumulates every returned window and stops before its own $0.50 cap.

In these tests, the app did not endorse touching thermal runoff, deliver cross-park facts for a Yellowstone-only chat, invent a private booking payment, or guarantee a future trail/road opening. That observation applies to these turns only.

## Candidate 1: measured mixed result

The full same 18-turn suite was repeated against `http://127.0.0.1:8515` with the hosted runtime, frozen database read-only, reranking disabled, and an isolated ephemeral ledger. This was a local HTTP test harness; its loopback origin shim differed from production. Do not compare its latency directly with the deployed baseline.

| Measurement | Baseline | Candidate 1 |
|---|---:|---:|
| Completed HTTP 200 turns | 18 / 18 | 18 / 18 |
| Expected action/status accepted | 15 / 18 | 17 / 18 |
| Full semantic/usefulness pass, provisional | 11 / 18 | 13 / 18 |
| Partial result, provisional | 4 / 18 | 4 / 18 |
| Answerable no-answer failure, provisional | 3 / 18 | 1 / 18 |
| Source identity/text mismatches | 0 | 0 |
| Delivered claim support, provisional | 11 full; 1 partial | 13 full |
| Run cost estimate | $0.012921154 | $0.010013142 |

The two Grand Canyon pet follow-ups now answer correctly. The winter-road answer uses the exact alternative `conditions.htm` description and no longer invents the merged “through Cooke City” route. That alternative source was retained during baseline assessment; the frozen expectations were not changed to match the candidate. The Cedar Ridge water question improves to supported general South Kaibab no-water prose, but review still withholds one claim and the specific table answer is missing.

Two regressions remain: the leash follow-up now refuses because its expanded query overweights both earlier Mirror Lake route questions, and the future Yellowstone road answer loses its explicit date limitation in favor of a generic refusal. The below-rim pet answer repeats the same rule twice. The paired provisional grades show four improved, two regressed, and twelve unchanged turns, counting partial improvements separately. This mixed development result does not establish a benchmark accuracy gain or justify selecting the candidate unchanged.

Evidence: [candidate raw turns](../artifacts/user-testing/20261010T164610Z-candidate-1b-a2c08c/turns.jsonl), [semantic assessments](../artifacts/user-testing/20261010T164610Z-candidate-1b-a2c08c/semantic-assessment.jsonl), [semantic summary](../artifacts/user-testing/20261010T164610Z-candidate-1b-a2c08c/semantic-summary.json), and [paired comparison](../artifacts/user-testing/20261010T164610Z-candidate-1b-a2c08c/comparison.json).

An earlier local harness attempt returned HTTP 403 before completing any conversation. It is preserved [with its incident record](../artifacts/user-testing/20261010T164512Z-candidate-1-4dfc5e/incident.json); because no ledger accompanied that error, the runner retained a separate conservative $0.025 reservation. The successful baseline/candidate windows total $0.022934296; including that unreported-usage reservation, the runner's conservative combined amount is $0.047934296. No failed attempt or negative semantic result was replaced or deleted.

## Candidate 2: 16 useful answers/boundaries, two remaining failures

The full frozen suite was repeated again on the hosted-profile loopback server, preserving newly generated history in each conversation. It completed 18/18 HTTP 200 responses, captured all ledgers, and had zero source identity/text mismatches. Provisional source review gives **16/18 full-quality passes and two failures**, while the mechanical accepted-status count is 17/18. All twelve delivered claims have source support; that does not make every response relevant to its question.

The leash response now correctly preserves **no more than six feet**. Future-date refusals explain the saved-source limitation and direct visitors to official updates/park confirmation. The booking refusal explains that the public database has no personal records and directs the visitor to the booking provider. The below-rim pet answer no longer repeats the same fact.

Two cases still require work:

- **H05.3, pet on shuttle:** the response says the shuttle system provides access to trails, including South Kaibab. That fact is supported, but it ignores the dog in the conversation and omits the source's explicit pet prohibition. Candidate 1 had correctly answered this question. A source-supported but nonresponsive answer can mislead a visitor.
- **H06.2, Cedar Ridge table:** the full conversation again refuses because review withholds its only drafted claim. The Cedar Ridge row is first in context, the DW legend second, and the South Kaibab no-water prose fourth. A separate root-run targeted probe succeeded, but that probe is not substituted for this failed full-suite result.

Against Candidate 1, the provisional ordinal comparison is four improved, two regressed and twelve unchanged turns. Against the baseline, five grades improve and thirteen remain unchanged. The latter does not capture the qualitative worsening of the already-failing shuttle case from clarification to a potentially misleading general answer; the individual assessments preserve that distinction. Do not select this candidate unchanged on the basis of its higher aggregate score.

The run estimate is **$0.016118160**, including reservations for two failed provider attempts. All successful full-run windows now total **$0.039052456**; including the separate harness-error reservation gives **$0.064052456** conservatively accounted across these runs. The targeted root probe is outside these runner totals.

Evidence: [raw turns](../artifacts/user-testing/20261010T173917Z-candidate-2-2e58b2/turns.jsonl), [individual semantic assessments](../artifacts/user-testing/20261010T173917Z-candidate-2-2e58b2/semantic-assessment.jsonl), [semantic summary](../artifacts/user-testing/20261010T173917Z-candidate-2-2e58b2/semantic-summary.json), and [paired comparisons](../artifacts/user-testing/20261010T173917Z-candidate-2-2e58b2/comparison.json). The source-first suite hash and every exact history chain were reverified; no expectations were changed and no human certification was added.

## Candidate 3: all 18 expectations observed passing

The full frozen suite completed another six actual three-turn conversations against the stable hosted-profile candidate. All 18 requests returned HTTP 200, all ledger windows were captured, and every displayed source text/ID matched the frozen database. Independent provisional assessment found **18/18 full-quality passes**, with all **15/15 delivered claims** supported by saved source text. Compared with Candidate 2, the two remaining failures improved and the other sixteen grades stayed passing; no new semantic regression was observed.

The pet-shuttle follow-up now retains the dog and explicitly prohibits pets on park buses. The Cedar Ridge answer says **the table does not indicate drinking water**, cites the row and the separate DW legend, and passes source review with no claims withheld. This describes the table's contents without treating a blank cell as proof of current real-world water availability. Leash limits, generator/quiet hours, thermal safety, park scope, private-booking boundaries and future-date limitations remain correct in this run. The below-rim answer distinguishes the pet rule from the supported service-animal exception.

The run estimate is **$0.016437600**, including two failed-provider-attempt reservations. The four completed full runs now total 72 turns and **$0.055490056** in returned ledger estimates. Including the separate harness-error reservation, the conservative runner amount is **$0.080490056**. These figures exclude other root-run targeted/browser probes and are not billing statements.

Evidence: [raw turns](../artifacts/user-testing/20261010T175228Z-candidate-3-5722c0/turns.jsonl), [semantic assessments](../artifacts/user-testing/20261010T175228Z-candidate-3-5722c0/semantic-assessment.jsonl), [semantic summary](../artifacts/user-testing/20261010T175228Z-candidate-3-5722c0/semantic-summary.json), and [paired comparisons](../artifacts/user-testing/20261010T175228Z-candidate-3-5722c0/comparison.json). All exact returned-history chains, hosted runtime/reranking-off settings and the original source-first hash were checked again. Prior failures remain preserved; this successful development run does not erase model variability observed earlier. Verify deployment and deployed behavior separately.

## Production verification: `fad4601`

Vercel deployment `dpl_5UhJQY5QcDF5wPkgy1XbwjmPME4n` was verified **READY**, attached to the production alias, and associated with code commit `fad4601a0a73d78e6cdb8edeb4e263bbd6109b25`. The [root verification record](../artifacts/reliability/deployment-fad4601.json) preserves deployment/alias, health and asset checks. The [run provenance record](../artifacts/user-testing/20261010T180046Z-deployed-fad4601-a9d031/deployment-provenance.json) distinguishes that control-plane evidence from the chat API's directly observed behavior.

The full frozen suite then completed six actual three-turn conversations over HTTPS on the production alias. Results were **18/18 HTTP 200**, **18/18 provisional semantic/usefulness passes**, **14/14 supported delivered claims**, all ledgers captured, and zero source text/ID mismatches. No semantic regression from Candidate 3 was observed. Seven baseline grades improve and eleven remain passing. Actual returned histories and the original source-first expectation hash were verified again.

The previously failing pet-shuttle question now says pets are prohibited on park shuttle buses. The water follow-up says the Cedar Ridge row does not indicate drinking water, citing its blank DW cell and the separate DW legend, with no claims withheld. The other sixteen turns retain the corrected bounds, exceptions, clarification, park scope, private-record limits and future-date guidance.

The production run estimate is **$0.015995434**, including two failed-provider-attempt reservations. Median HTTP latency was **3.02 s**; p95 was **33.22 s** and maximum **33.45 s**. The two slow cases included provider retries. This run verifies response content and successful recovery, not a latency improvement; the slow tail remains a practical limitation.

Across all five completed full suites, 90 turns have **$0.071485490** in returned ledger estimates. Including the separate retained $0.025 harness-error reservation gives **$0.096485490** conservatively accounted by this runner. Root/browser/targeted probes are outside that total. These estimates are not invoices.

Evidence: [production raw turns](../artifacts/user-testing/20261010T180046Z-deployed-fad4601-a9d031/turns.jsonl), [semantic assessments](../artifacts/user-testing/20261010T180046Z-deployed-fad4601-a9d031/semantic-assessment.jsonl), [semantic summary](../artifacts/user-testing/20261010T180046Z-deployed-fad4601-a9d031/semantic-summary.json), and [paired comparisons](../artifacts/user-testing/20261010T180046Z-deployed-fad4601-a9d031/comparison.json). All earlier failures remain preserved. Human gold verification and the sealed final benchmark remain separate and untouched.

## Additional broad-trail regression: observed after the 18-turn production run

An independent source audit of the [manual production response](../artifacts/reliability/production-pet-trails-ui-response.json) confirms a **cross-claim exception-scope failure**. Its first claim says pets are prohibited on trails except Wawona Meadow Loop. Its second allows Bridalveil Fall and Lower Yosemite Fall paved trails. The first statement treats Wawona as the only exception and is therefore too broad when read with the second.

This is not a missing-source problem: the allowed-routes passage was first in final context, the prohibited-trails/Wawona passage third, and the source's “not allowed on most trails” summary was also present. Both cited passage IDs and their full bytes match SQLite. Generation and review needed to reconcile the scope of all claims together; checking each against a favorable excerpt did not establish a coherent answer. The AI claim reviewer marked both supported with no withholding, while this independent audit marks the overall answer failed.

The relevant normalized spans are `pets.htm` **188–481** (paved routes, named examples, sign restrictions), **1122–1238** (trail prohibition with Wawona exception), and `index.htm` **2760–3012** (pets prohibited on **most** trails). A correct broad answer should explain the general hiking-trail restriction together with the permitted paved-route and Wawona exceptions, without declaring either category the sole exception. If discussing specific prohibited routes, Vernal Fall and the unpaved Mirror Lake loop remain prohibited; carrying a pet does not override the restrictions.

Three new single-turn regression questions are saved in [a separate case file](../artifacts/user-testing/pet-trails-regression/cases.json):

1. “Are pets allowed on trails?” — the already observed seed question.
2. “Can I take my dog hiking in Yosemite, or are all the trails off limits?”
3. “Which Yosemite trails can I walk with my pet dog?”

**Provenance:** these cases were added after the manual failure was observed. The exact SQLite evidence and expectations were saved before further requests, but this is a targeted regression set, not a pre-answer independent test. The original 18-turn suite is unchanged. The [independent failure audit](../artifacts/user-testing/pet-trails-regression/observed-production-failure.json) preserves the response hash, claim-level analysis, retrieval evidence and the root probe's $0.000856758 ledger estimate. That probe remains outside the full-suite runner totals.

The existing runner can use the separate suite without changing the frozen cases:

```sh
.venv/bin/python scripts/test_hosted_experience.py \
  --suite artifacts/user-testing/pet-trails-regression/cases.json \
  --base-url http://127.0.0.1:8515 \
  --stage pet-trails-candidate \
  --followup-of artifacts/reliability/production-pet-trails-ui-response.json
```

### Candidate 4: coherent rules, incomplete coverage, one original-suite regression

The three separate regression requests all returned HTTP 200 and source-consistent identities. All three avoid the observed cross-claim contradiction. **All three remain partial against the unchanged pre-run coverage rubric**, rather than being counted as full passes:

| Case | Independent assessment |
|---|---|
| RPT01 | “Exceptions include the Wawona Meadow Loop and specified paved trails” is coherent, but supplies no named paved example. |
| RPT02 | Gives valid Bridalveil/Lower Yosemite examples, but “fully paved paths” drops the posted-sign restriction and broadens the source categories. Wawona is also omitted; its passage was absent from final context. |
| RPT03 | Gives a useful, supported shortlist of four paved routes and excludes the unpaved Mirror Lake loop. It omits Wawona and the general hiking-trail rule required by the saved rubric. Wawona was absent from final context; the answer does not claim an exhaustive list. |

The coverage gaps are distinct from the repaired contradiction. Five delivered claims are fully supported and one has incomplete permission scope. A model should not invent a missing exception from outside its supplied passages to satisfy a coverage target. Evidence: [three raw responses](../artifacts/user-testing/20261010T180815Z-candidate-4-pet-trails-b88e7d/turns.jsonl), [unchanged-rubric assessments](../artifacts/user-testing/20261010T180815Z-candidate-4-pet-trails-b88e7d/semantic-assessment.jsonl), and [summary](../artifacts/user-testing/20261010T180815Z-candidate-4-pet-trails-b88e7d/semantic-summary.json).

The full original suite then completed 18/18 HTTP 200 responses with actual returned histories. **17/18 expectations pass; H06.2 regresses to a refusal.** All thirteen delivered claims are supported, all ledgers were captured, and source identity checks found no mismatches. The saved table, DW legend and general South Kaibab no-water prose were all retrieved. The internal trace directly establishes that generation correctly said the table **does not indicate drinking water**; review misread this source-scoped observation as a claim of physical water absence and withheld it. The failure is retained, with no same-candidate semantic retry.

Evidence: [full raw run](../artifacts/user-testing/20261010T180846Z-candidate-4-22ab89/turns.jsonl), [semantic assessment](../artifacts/user-testing/20261010T180846Z-candidate-4-22ab89/semantic-assessment.jsonl), [comparison](../artifacts/user-testing/20261010T180846Z-candidate-4-22ab89/comparison.json), and [withholding diagnosis](../artifacts/user-testing/20261010T180846Z-candidate-4-22ab89/H06.2-withholding-diagnostic.json). All original source-first expectations and exact history chains remain unchanged.

Candidate 4 cost estimates are **$0.002755414** for the additional three questions and **$0.020147280** for the original eighteen, totaling **$0.022902694**. The full suite includes three failed-provider-attempt reservations. Across six complete original suites plus the three added questions, the runner has recorded 111 successful HTTP turns and **$0.094388184** in ledger estimates; retaining the separate harness-error reservation gives **$0.119388184** conservatively accounted. Root/browser probes remain outside these totals. This is development evidence, not a billing statement or human-certified accuracy benchmark.

### Candidate 5: necessary citations and permission wording still fail

The additional three requests yield **two partial results and one failure**, all HTTP 200. RPT01 qualifies the trail rule and describes Wawona as an exception, but omits every paved option despite supplied evidence. RPT02 now preserves the posted-sign restriction and gives valid examples; it remains partial for missing Wawona context/coverage. RPT03 regresses: review withholds its permitted-route list for missing the signage condition, leaving only “Dogs are not allowed on unpaved hiking trails, including the Mirror Lake loop.” That is nonresponsive to a request for permitted routes and insufficiently qualifies its broader restriction. Three delivered claims have full support; the surviving broad prohibition has only partial support. [Raw supplemental responses](../artifacts/user-testing/20261010T181332Z-candidate-5-pet-trails-bd59bc/turns.jsonl), [assessments](../artifacts/user-testing/20261010T181332Z-candidate-5-pet-trails-bd59bc/semantic-assessment.jsonl), and [withholding diagnosis](../artifacts/user-testing/20261010T181332Z-candidate-5-pet-trails-bd59bc/RPT03-withholding-diagnostic.json) preserve the result.

The full original suite completes **18/18 HTTP 200, 17/18 semantic passes**, with fourteen supported delivered claims and zero source identity mismatches. H06.2 still refuses, but for a different directly observed reason: generation correctly describes the table's missing indication while citing only the row/header. The separate DW legend is retrieved at rank one but omitted from the claim's evidence IDs. Review correctly withholds the abbreviation-dependent claim from that incomplete citation set. This is a generation citation-completeness failure, rather than Candidate 4's review misunderstanding. [Full raw run](../artifacts/user-testing/20261010T181352Z-candidate-5-530525/turns.jsonl), [semantic assessments](../artifacts/user-testing/20261010T181352Z-candidate-5-530525/semantic-assessment.jsonl), [comparison](../artifacts/user-testing/20261010T181352Z-candidate-5-530525/comparison.json), and [table diagnosis](../artifacts/user-testing/20261010T181352Z-candidate-5-530525/H06.2-withholding-diagnostic.json) retain every outcome.

Candidate 5 costs **$0.002625360** for the additional three and **$0.019999440** for the original eighteen, totaling **$0.022624800**; three provider-failure reservations are included. Seven original suites and six supplemental turns now total 132 successful HTTP responses and **$0.117012984** in returned ledger estimates, or **$0.142012984** including the retained harness-error reservation. No same-candidate failed answer was replaced by a retry, and no rubric was changed.

### Candidate 5b: content improves, citation gaps remain

This scoped check ran the same three supplemental questions and the complete three-turn H06 dialogue, not another full eighteen-turn suite. All six returned HTTP 200 with actual history, captured ledgers and matching source identities.

The supplemental grades are **one pass, one partial and one failure**. RPT01 now gives a coherent “most trails” rule and a nonexhaustive named shortlist including paved Bridalveil/Lower Yosemite trails and Wawona. RPT02 gives only the supported “most trails” restriction after its permission claim is withheld for omitted signage. RPT03 gives only the specific unpaved Mirror Lake prohibition: the prior broad inferred ban is gone, but no permitted route survives review, so it still fails the visitor's route-selection request. [Raw responses](../artifacts/user-testing/20261010T181726Z-candidate-5b-pet-trails-aea49b/turns.jsonl), [assessments](../artifacts/user-testing/20261010T181726Z-candidate-5b-pet-trails-aea49b/semantic-assessment.jsonl) and [summary](../artifacts/user-testing/20261010T181726Z-candidate-5b-pet-trails-aea49b/semantic-summary.json) retain the complete result.

H06's three responses contain correct information/boundaries, but **only one is a full pass; two have partial citation support**. The distance answer selects a PDF fragment that starts mid-word and omits its South Kaibab origin heading; the full saved PDF confirms the fact, while the reviewer's claim that the heading is supplied is incorrect. The drinking-water answer correctly describes the saved table, but again cites only the row/header and omits the separate DW legend. Review accepts this time, demonstrating inconsistent enforcement of citation completeness. Independent knowledge of the full source must not be substituted for each claim's missing witnesses. [H06 raw turns](../artifacts/user-testing/20261010T181755Z-candidate-5b-H06-6d03bf/turns.jsonl), [assessments](../artifacts/user-testing/20261010T181755Z-candidate-5b-H06-6d03bf/semantic-assessment.jsonl), [PDF context evidence](../artifacts/user-testing/20261010T181755Z-candidate-5b-H06-6d03bf/additional-PDF-context-evidence.json), and [water citation diagnosis](../artifacts/user-testing/20261010T181755Z-candidate-5b-H06-6d03bf/H06.2-citation-diagnostic.json) distinguish correct wording from incomplete support.

Candidate 5b costs **$0.004217280** across the six requests, with no failed-provider reservations. The cumulative runner estimate is **$0.121230264** across 138 successful HTTP turns, or **$0.146230264** including the retained harness-error reservation. These mixed results are preserved and are not described as a clean deployment verification.

### Candidate 6: stricter blocking, continuing generation/review failures

This scoped check again runs the unchanged supplemental three questions and actual three-turn H06 dialogue once. All six return HTTP 200, all ledgers are captured, and source identities match. It does not substitute for a full production suite.

The supplemental result is **zero full passes, one partial and two failures**. RPT01 drafts the original overbroad Wawona-only rule again; review correctly withholds it, so the visitor receives a refusal. RPT02 gives a coherent most-trails rule, named paved examples and the explicit sign restriction; its two delivered claims have complete source witnesses, but Wawona remains absent from retrieved context/coverage. RPT03 drafts allowed routes without the required conditions and adds an uncited leash qualification; review withholds both claims. Evidence-first field ordering did not reliably resolve these generation omissions. [Raw responses](../artifacts/user-testing/20261010T182223Z-candidate-6-pet-trails-2d0753/turns.jsonl), [assessments](../artifacts/user-testing/20261010T182223Z-candidate-6-pet-trails-2d0753/semantic-assessment.jsonl), and [comparison](../artifacts/user-testing/20261010T182223Z-candidate-6-pet-trails-2d0753/comparison.json) preserve that mixed outcome.

H06 gives **two full passes and one failure**. The distance claim now cites the HTML table with exact origin/header/row witnesses. The future-date boundary remains correct. The water draft now cites the necessary row and DW legend, plus an additional South Kaibab prose passage. Review supports the source-scoped observation and quotes the first two, but gives no witness for the third cited passage. Deterministic validation raises `missing_cited_witness` and refuses the answer. The correct draft does not replace the delivered failure. [Raw dialogue](../artifacts/user-testing/20261010T182243Z-candidate-6-H06-dac114/turns.jsonl), [assessment](../artifacts/user-testing/20261010T182243Z-candidate-6-H06-dac114/semantic-assessment.jsonl), and [exact diagnostic](../artifacts/user-testing/20261010T182243Z-candidate-6-H06-dac114/H06.2-missing-witness-diagnostic.json) retain both the improved citation selection and the review-validation failure.

Candidate 6 costs **$0.004258680** across six requests. Its water turn records one failed generation/review event for the invalid review response, with usage included; this is not evidence of a network retry. The cumulative runner estimate is **$0.125488944** across 144 successful HTTP turns, or **$0.150488944** including the retained harness-error reservation. The observed blockers are now safer refusals in these cases, but answerability remains unresolved; this is not a clean success or an accuracy benchmark.

### Candidate 7: full original suite passes; supplemental limitations persist

The scoped H06 dialogue passes all three turns, followed by **two partial results and one failure** in the unchanged supplemental set. H06's water answer preserves source-scoped wording and cites both the Cedar Ridge row/header and the separate DW definition. RPT01 now qualifies its general trail rule and names Wawona as an exception without making it the only exception, but omits paved options. RPT02 gives valid named paved options with the signage condition, but lacks Wawona in its final context and answer. RPT03 still refuses after review withholds its drafted route permissions for missing conditions and an uncited leash qualification. No unsupported surviving claim was observed in these six turns. [H06 evidence](../artifacts/user-testing/20261010T190038Z-candidate-7-H06-ff95a5/semantic-assessment.jsonl) and [supplemental evidence](../artifacts/user-testing/20261010T190056Z-candidate-7-pet-trails-2450b8/semantic-assessment.jsonl) preserve the unchanged grading distinctions.

Because the scoped test improved the table dialogue without an unsupported surviving claim, the full original eighteen-turn suite ran once. It completed **18/18 HTTP 200, 18/18 semantic/usefulness passes and 14/14 supported delivered claims**, with all ledger windows captured and zero source identity mismatches. The water answer succeeds in this full run too; the separate scoped success is not substituted for it. [Full raw turns](../artifacts/user-testing/20261010T190135Z-candidate-7-6ef70c/turns.jsonl), [individual assessments](../artifacts/user-testing/20261010T190135Z-candidate-7-6ef70c/semantic-assessment.jsonl), [summary](../artifacts/user-testing/20261010T190135Z-candidate-7-6ef70c/semantic-summary.json), and [paired comparisons](../artifacts/user-testing/20261010T190135Z-candidate-7-6ef70c/comparison.json) retain all responses. Against the preceding full Candidate 5 run, H06.2 improves and seventeen grades remain passing; against the baseline, seven improve and eleven remain passing.

This candidate introduces an explicit **`witness-selected-v1` citation contract**. The critic must still support the entire unchanged claim using only that claim's original citation IDs. The final citations may be a sufficient subset selected by exact bound witnesses; every final citation still requires a verbatim witness, and no claim may borrow another claim's or an uncited source's support. This deliberately changes the earlier requirement that every original ID have a witness. An explicit glossary guard also rejects abbreviated-table claims whose full-phrase meaning depends on a missing selected definition. That guard recognizes literal `ABBR = phrase` definitions and matching table headers/full-phrase claims; it is not a general semantic proof system. The tradeoff and changed validation contract must be considered when comparing runs.

Independent [original/final citation audits](../artifacts/user-testing/20261010T190135Z-candidate-7-6ef70c/citation-contract-audit.json) verify unchanged text, original claim ownership and exact SQLite witnesses for the twelve Yosemite/Grand Canyon turns recorded by the local trace harness. The six Yellowstone turns have public source/witness verification but no internal original/final trace in this harness. **No supported claim in the available Candidate 7 traces removed an original citation**, including both successful H06 water turns. The [full-suite water excerpt](../artifacts/user-testing/20261010T190135Z-candidate-7-6ef70c/H06.2-contract-excerpt.json) records this explicitly. These live outcomes therefore do not demonstrate that redundant-citation removal caused the improvement; model variation and the combined changes remain relevant.

The interface also offers related official NPS pages for refused or partially withheld responses, using same-park pages already in retrieved context. In RPT03, its data provides the Yosemite Pets and Plan Your Visit pages as navigation options. This is a useful recovery path, separate from numbered evidence for delivered claims. It does not turn a refusal into a successful answer or repair missing coverage. The [related-link record](../artifacts/user-testing/20261010T190056Z-candidate-7-pet-trails-2450b8/related-link-recovery-evidence.json) is based on component and actual response-data inspection; browser-rendering verification is tracked by the root agent separately.

The targeted H06 dialogue costs **$0.001668840**, the supplemental set **$0.002452320**, and the full suite **$0.020572560**, totaling **$0.024693720** under the combined $0.30 cap. The full run includes three failed-provider-attempt reservations. Across all runner attempts, 168 successful HTTP turns now total **$0.150182664** in returned ledger estimates, or **$0.175182664** including the separate harness-error reservation. All earlier failures remain preserved. Production identity and deployed behavior still require separate verification after release.

### Production verification: backend release `1daf0ab`

Before these calls, root verified deployment `dpl_2tz7j6E3ysNbKjAte5GzhQ1irRJG` as **READY**, associated with commit `1daf0ab661f711c3f49977255792073af8002c57` and attached to the production alias. The [initial deployment record](../artifacts/reliability/deployment-1daf0ab.json) includes matching JavaScript/CSS bytes, hosted health, the frozen build and HTML cache/conditional-request checks. The [test's initial provenance record](../artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/deployment-provenance-start.json) preserves that evidence separately from the API observations. The [final lineage record](../artifacts/reliability/deployment-lineage.json) verifies the later source-card UI release `d5724ac` as READY with matching live assets and the same frozen build. The exact Git diff from the tested release changes only `web/src/components/source-card.tsx`; backend, configuration and database are identical. This establishes backend lineage without inventing a per-request commit identity.

The original suite runs once with actual returned histories: **18/18 HTTP 200, 17/18 provisional semantic/usefulness passes, 12/12 supported delivered claims, zero source identity mismatches and all ledgers captured**. H01.2, the unpaved Mirror Lake pet follow-up, regresses to a refusal. Its final context contains the explicit saved prohibition, but public review status says all claims were withheld. The rejected draft and detailed reason are not public, so the precise generation/review cause remains unknown. It is not a missing-retrieval diagnosis or a successful answer merely because refusal is safer than inventing permission. [Raw run](../artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/turns.jsonl), [assessments](../artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/semantic-assessment.jsonl), [comparison](../artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/comparison.json), and [failure diagnostic](../artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/H01.2-public-failure-diagnostic.json) preserve the result without a retry.

The Cedar Ridge water answer succeeds with exact row/header and DW-definition witnesses, grouped under one source page. Pet-shuttle and below-rim follow-ups, leash maximum, generator/quiet hours, thermal safety, future-date boundaries, private-booking limitations and selected-park scope also pass. The [public witness audit](../artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/public-witness-audit.json) checks each final citation against SQLite. Production does not expose original citation-ID sets or rejected drafts; original/final selection cannot be independently asserted from those public fields.

The frozen supplemental set also runs once: **three HTTP 200 responses, two partial grades and one failure**. RPT01 says pets are generally restricted with Wawona as an exception, coherently avoiding the previous sole-exception claim, but omits paved options. RPT02 now says only that most trails are off limits after one drafted claim is withheld; it is less useful than the local candidate answer with examples, despite retaining the same partial grade. RPT03 refuses after both claims are withheld. Its related NPS navigation provides a recovery route, not a correct chatbot answer. The two surviving claims are source-supported. [Supplemental raw responses](../artifacts/user-testing/20261010T191153Z-deployed-1daf0ab-pet-trails-260807/turns.jsonl), [assessments](../artifacts/user-testing/20261010T191153Z-deployed-1daf0ab-pet-trails-260807/semantic-assessment.jsonl), [witness audit](../artifacts/user-testing/20261010T191153Z-deployed-1daf0ab-pet-trails-260807/public-witness-audit.json), and [withholding diagnostics](../artifacts/user-testing/20261010T191153Z-deployed-1daf0ab-pet-trails-260807/public-withholding-diagnostics.json) retain all outcomes. No coverage criterion was relaxed, and absent Wawona context was not filled with invented facts.

The original production suite costs **$0.017049514**, with median latency **3.37 seconds**, p95 **33.78 seconds** and maximum **34.14 seconds**; the slow tail includes provider retries. The supplemental suite costs **$0.005730334**. Their combined estimate is **$0.022779848**, including three failed-provider-attempt reservations, under the $0.30 cap. Cumulative runner accounting is **$0.172962512** for 189 successful HTTP turns, or **$0.197962512** including the retained harness-error reservation. These are estimates, exclude root's separate UI/targeted calls, and are not invoices. All human gold certification and sealed final-test work remain untouched.

## Baseline source-grounded findings

| Case | Observed result | Frozen-source finding and implication |
|---|---|---|
| H01.3 — Yosemite leash follow-up | “The leash should be six feet long.” | The cited safety recommendation mentions a six-foot leash, but the regulatory block says **not more than six feet**. The answer should preserve the upper bound. `yose/planyourvisit/pets.htm`, normalized span 583–680. |
| H04.1 — Yellowstone winter road | Combined Mammoth → Northeast Entrance wording with “through Cooke City.” | One page describes Mammoth–northeast entrance; `parkroads.htm` specifies North Entrance/Gardiner → Cooke City via Tower Junction. The merged route relationship is not established by the excerpts. Preserve the exact route from a single supporting statement or explain the distinction. |
| H04.3 — private reservation payment | Safe generic source-gap refusal | The corpus has no `BB-9274` reservation. Explain lack of booking/account access and point to the booking provider rather than suggesting this payment status is an NPS source-search question. |
| H05.2 — carrying pet below rim | Unnecessary source-gap refusal | `grca/planyourvisit/pets.htm` spans 799–840 and 1997–2036 prohibit pets below the rim; service animals have a separate rule. The query lost “dog/pet” while resolving “him,” leaving general hiking passages in context. |
| H05.3 — same pet on shuttle | Unnecessary clarification | The same page spans 754–797 and 2038–2060 explicitly prohibit pets on park shuttles. The query again lost the pet subject despite receiving all prior messages. |
| H06.2 — Cedar Ridge drinking water | All drafted claims withheld by review | `trail-distances.htm` includes the DW legend, Cedar Ridge's blank DW cell/TF=Y, and South Kaibab no-water prose. Those passages entered the final context, so this is a review-stage over-refusal. The public payload does not expose the rejected draft; blank-cell interpretation is a hypothesis, not a proven root cause. |
| H06.3 — July 18, 2027 opening | Safe generic source-gap refusal | The frozen snapshot cannot establish that future opening. Name the future/live-status limitation and direct the visitor to current alerts, without presenting older dates as guarantees. |

The remaining tests correctly handled Mirror Lake paved/unpaved pet routes, initial ambiguity, generator and quiet hours, thermal swimming/contact rules, selected-park scope, a future Yellowstone road date, above-rim pet permission, and Cedar Ridge's 1.5-mile distance.

## Preserved evidence

- [Pre-answer expectations and exact source spans](../artifacts/user-testing/source-first-cases.json), SHA-256 `bf70ee1824515883da95e237132b41f8c59fe467f0eda49a0829054bf591660c`.
- [Baseline requests, complete public responses and per-turn ledgers](../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/turns.jsonl), SHA-256 `a60291107c8631c0a35662c7f83c09dfa2496fc467616a470bb9f8c72a59083b`.
- [Run manifest](../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/manifest.json), [endpoint metadata](../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/metadata.json), and [operational summary](../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/summary.json).
- [Individual provisional semantic assessments](../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/semantic-assessment.jsonl) and [semantic summary](../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/semantic-summary.json).
- [Alternative road-source evidence inspected after answers](../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/additional-assessment-evidence.json). This supplements assessment without modifying the frozen expectations.

The manifest's checkout revision/component hashes describe the **local checkout at run start**. They are not proof of the remote Vercel deployment revision; verify deployment identity separately. The remote active build ID and each displayed source text were directly checked.

## Reproduce and compare

The runner sends an exact same-origin `Origin` header, accepts another base URL, saves a new immutable run folder, checks every ledger window, and never retries a semantic failure to replace an answer. It makes no calls to the gold or final-test datasets. The original source-first suite is already frozen; do not rerun `--prepare` to overwrite it.

```sh
.venv/bin/python scripts/test_hosted_experience.py \
  --base-url https://parkguide-ai-dh24.vercel.app \
  --stage deployed-check \
  --followup-of artifacts/user-testing/20261010T164035Z-baseline-c5e32e

# Rerun whole affected dialogues against a hosted-profile candidate server.
.venv/bin/python scripts/test_hosted_experience.py \
  --base-url http://127.0.0.1:8515 \
  --stage candidate --case H01 --case H04 --case H05 --case H06 \
  --followup-of artifacts/user-testing/20261010T164035Z-baseline-c5e32e
```

Each run requires a separate source-span semantic assessment before claiming improvement. Preserve negative outcomes and review all claimed improvements against the original expectations. Whole-dialogue reruns carry their newly generated prior responses, so paired outcomes are realistic conversation comparisons rather than identical fixed-history model trials.

## Additional browser and offline checks

Two earlier candidate browser questions correctly answered carrying a dog to Vernal Fall and pet leash rules when the visitor merely mentions visiting today. Their three delivered claims and all cited passage bytes were checked against frozen SQLite; these spot checks are separate from the conversation suites. An emulated lost connection restored the submitted question in the composer and displayed a recoverable error.

The latest offline checks passed **508 Python tests**, **10 browser-request tests**, the TypeScript/production build and lint (11 existing Fast Refresh warnings). A fresh production browser question, “Can I carry my dog to Vernal Fall?”, answered correctly with an exact saved NPS witness, no claims withheld and a $0.000776086 ledger estimate. This single attempt is separate from the 21-turn production runner totals. Its [real response](../artifacts/reliability/production-final-ui-response.json) and [browser screenshot](../artifacts/reliability/production-final-ui.jpg) are preserved. The related-link fallback was separately checked by replaying an earlier recorded refusal in the browser; that check made no provider call and is not a new semantic result. [Verification record](../artifacts/reliability/verification.json) distinguishes these observations and source checks.
