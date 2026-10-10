# Hosted visitor testing

These are **non-gold development diagnostics**, authored from the frozen read-only SQLite sources before any answers in this suite. They are separate from the course gold benchmark and sealed final test. Semantic grades below are AI proposals, not human verification.

**Latest measured result:** Candidate 3 passed all 18 source-grounded conversation expectations on the local hosted-profile server, with all 15 delivered claims supported. The original deployed baseline had 11 full-quality passes, four partial results and three failures. This suite was reused to develop the fixes; it is not an independent accuracy benchmark or proof that the candidate is deployed.

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

## Source-grounded findings

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

Two separate final-candidate browser questions correctly answered carrying a dog to Vernal Fall and pet leash rules when the visitor merely mentions visiting today. Their three delivered claims and all cited passage bytes were checked against the frozen SQLite data; these spot checks are separate from the 18-turn suite. An emulated lost connection restored the submitted question in the composer and displayed a recoverable error. The final offline checks passed 474 Python tests, 10 browser-request tests, the TypeScript/production build and lint (11 existing Fast Refresh warnings). [Verification record](../artifacts/reliability/verification.json) preserves the observations and source checks.
