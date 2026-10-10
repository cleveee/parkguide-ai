# ParkGuide Hallucination Pilot and Evaluation Best Practices

October 10, 2026

ParkGuide's saved production responses show why hallucination testing must measure usefulness as well as factual support. A retrospective audit of 39 responses found an unsupported route relationship and a missing permission condition in the earlier stage. In the later 21 responses, all 14 delivered claims had source support, while two of 16 answerable questions received refusals and two broad route answers remained incomplete. These are provisional judgments from one AI reviewer, not independently verified accuracy results.

The independent sub-agent experiment requested for this task has **not run**. This side conversation explicitly prohibits starting or interacting with sub-agents. The completed work is an offline retrospective pilot, source validation, a blinded evaluation packet, and a protocol for conducting the requested panel in the main conversation. No new chatbot or evaluator calls were made. Application code, gold records, and deployment were not changed.

## Study Question and Scope

The intended study question is whether ParkGuide's reliability pipeline reduces unsupported content without unnecessarily withholding supported answers. The pilot asks a narrower observational question: what factual support and usefulness problems are visible in saved production responses from two stages of development?

The product supports one selected park per conversation and answers from saved official sources. A question about two parks belongs in a boundary test with a refusal expectation, rather than in a factual comparison benchmark. Future opening status and private reservation records likewise require source-limit handling. A statement that a table does not indicate drinking water must not become a claim about current water availability.

The sampled production responses used the Vercel profile, hybrid retrieval, and no cross-encoder reranker. The generator and source critic used the pinned Luna snapshot recorded in the response traces. Historical local runs with reranking are not interchangeable with these production measurements. Product boundaries and reviewer behavior are documented in [Park scope](../../docs/PARK_SCOPE.md) and [Claim review](../../docs/CLAIM_REVIEW.md).

## Completed Pilot Method

The pilot includes every response in three saved runs: the original 18-turn production baseline, a later 18-turn production run over the same user questions, and the later three-question pet-route supplement. The original questions form six conversations with three turns each. No failed or inconvenient answer was excluded. The supplement was authored after a development failure and is reported separately because it is especially selected for known weaknesses.

All 39 responses were inspected against saved cited passages and source-authored expectations. A new offline runner froze the allowlisted inputs, recorded their hashes, opened SQLite read-only, and checked displayed passages against the active stored chunks. It also checked exact reviewer quotes and their association with delivered claims. The audit checked 28 passage appearances and 49 quote appearances, with zero mechanical errors. Repeated passages count as appearances, not distinct documents. Source identity and exact quotes do not establish semantic entailment; semantic labels are separate.

The reviewer saw earlier AI assessments and was not blinded. The semantic annotations are therefore explicitly marked `AI_provisional`, with `human_verified: false` and `independent_panel: false`. Earlier AI annotations were not rewritten. The pilot's full-pass grades are descriptive judgments about the frozen requirements, rather than calibrated accuracy measurements.

The blinded packet contains the same 39 observations in a seeded random order. It removes stage names, generator identity, the application's review verdicts, reviewer reasons, reviewer witnesses, and this pilot's labels. It retains the question, actual conversation history, selected park, answer, citation passages, and independent reference evidence. A decoder in the manifest maps anonymous evaluation IDs back to observations. Independent evaluators must receive the packet and instructions only; the report, decoder, and pilot annotations would reveal the labels.

## Definitions Used in the Pilot

| Label | Meaning |
| --- | --- |
| Supported | The cited source establishes the factual assertion in its question and conversation context. |
| Unsupported | The answer adds a fact or relationship that the cited sources do not establish. This does not by itself prove real-world falsity. |
| Material qualification omitted | The answer drops a condition that changes the scope of a permission or restriction. Report separately because borderline omissions need adjudication. |
| Incomplete | The delivered claims are supported, but the answer omits information required to answer the question usefully. |
| Answerable no answer | The saved reference supports an answer, but the response refuses or asks an unnecessary clarification. |
| Correct boundary handling | The response respects the selected park or explains why saved sources cannot confirm future or private information. |

This separates factual support from completeness. For example, saying that most trails prohibit dogs can be supported while failing to answer which routes permit them. By contrast, removing a posted-sign exception from a permission can make that permission too broad. The two types of omission should not be collapsed into one score.

The source-relative approach follows RAGTruth's distinction between unsupported and contradictory content in RAG responses. Its detailed annotation methodology is a useful precedent for locating the exact problematic span rather than scoring only the whole response. [RAGTruth](https://aclanthology.org/2024.acl-long.585/)

## Pilot Results

| Measurement | Earlier original suite | Later original suite | Later supplement |
| --- | ---: | ---: | ---: |
| Saved requests | 18 | 18 | 3 |
| Substantive answers | 11 | 12 | 2 |
| Delivered claims | 12 | 12 | 2 |
| Unsupported delivered claims | 1/12 | 0/12 | 0/2 |
| Material qualification omissions | 1/12 | 0/12 | 0/2 |
| Answers with either support problem among all requests | 2/18 | 0/18 | 0/3 |
| Answers with either support problem among substantive answers | 2/11 | 0/12 | 0/2 |
| Refusals on answerable questions | 2/13 | 1/13 | 1/3 |
| Answerable questions without an answer, including clarification | 3/13 | 1/13 | 1/3 |
| Full pass on factual support and usefulness, provisional | 10/18 | 17/18 | 0/3 |
| Partial results | 5/18 | 0/18 | 2/3 |
| Failures | 3/18 | 1/18 | 1/3 |

Across the later original suite and supplement, the observed unsupported-claim count is **0/14**, and the observed answerable-refusal count is **2/16**. This combination is more informative than reporting zero hallucinations alone. It also does not mean the chatbot is hallucination-free: the sample is small, selected during development, and provisionally graded.

The earlier suite's full-pass count differs from its historical AI report, which gave 11/18. The new audit marks the first Mirror Lake permission answer partial because it omits the posted-sign condition already required in the frozen source-first expectation. This is a correction to provisional grading, not a rewritten question or newly invented rubric. The qualification judgment remains an explicit human-review item.

Among the 18 matched question IDs, eight provisional grades improve, one regresses, and nine are unchanged. An exploratory bootstrap over the six dialogue clusters gives a change of minus 11.1 percentage points in answers with unsupported content or a material qualification omission; the percentile interval is minus 22.2 to 0.0 percentage points, with seed 633 and 10,000 resamples. It includes zero and is not confirmatory evidence. Different assistant histories, multiple implementation changes, repeated development exposure, and unblinded labels prevent a causal claim that source review caused the observed change.

## Concrete Failure Cases

**Unsupported route relationship.** The earlier winter-road answer combines two valid passages into a route from Mammoth Hot Springs to the Northeast Entrance “through Cooke City.” The cited passages do not establish that combined relationship. Real citations can therefore accompany an unsupported assertion. The later answer follows the direct saved route description and preserves the weather condition.

**Missing permission condition.** The earlier Mirror Lake answer permits pets on the paved road but omits the source's posted-sign exception. The later answer explicitly includes that exception. General answer summaries need not repeat every source detail, but they should preserve conditions that change what a visitor is permitted to do.

**Refusal despite useful evidence.** In the later original suite, the unpaved Mirror Lake follow-up refuses after all drafted claims are withheld. The reference supports a negative answer, and the saved diagnostic context includes relevant evidence. A second answerable refusal occurs when the supplement asks which Yosemite trails allow pets. The public trace omits the rejected draft text, so these are answer-level over-refusals; they cannot be labeled proven reviewer false rejections.

**Supported but incomplete route guidance.** The two delivered supplemental answers give qualified trail restrictions. Neither fabricates a permission, but both omit useful permitted-route coverage. Removing uncertain claims can leave a response factually supported yet insufficiently useful.

**Table scope preserved.** The later Cedar Ridge answer describes the absence of a drinking-water indication in the saved table and cites both the row and abbreviation definition. It does not guarantee current water conditions. Blank-cell interpretation and current availability should remain distinct experimental categories.

## Independent Evaluator Protocol

The prepared packet can support a retrospective panel of three isolated evaluators, with Claude Code as an optional fourth evaluator when authorized in the main conversation. All evaluators must score the same full rubric independently. Giving each evaluator a different specialty would prevent direct agreement comparisons.

1. Give each evaluator only [the blinded packet](judge-packet.jsonl) and [the evaluator instructions](JUDGE_INSTRUCTIONS.md). Isolate workspaces and prevent access to the report, manifest decoder, existing labels, and other evaluators' outputs.
2. Require a label for every claim, an exact supporting or contradicting source reference, a usefulness assessment, and an explicit `insufficient_evidence` option. Preserve each evaluator's raw output and actual model identity.
3. Collect all outputs before comparing them. Report unanimity, pairwise agreement, disagreements by failure type, and missing annotations. Agreement is a reliability observation; it is not proof that the panel is correct.
4. Keep majority labels provisional. Queue every disagreement, every unsupported or contradicted claim, every qualification omission, and every answerable refusal for human review. Also include a preregistered sample of unanimous supported labels, such as ten cases, to look for shared mistakes.
5. If using multiple instances of the same model, describe them as independent executions with correlated model limitations. A second model family can broaden the panel but does not establish independence from common training or reasoning errors.

The bias controls are motivated by research documenting position, verbosity, and self-enhancement biases in LLM judges. That research evaluates preference judgments; its agreement results should not be transferred to ParkGuide factual-support accuracy. [Judging LLM as a Judge](https://arxiv.org/abs/2306.05685)

The earlier four-evaluator artifacts in this repository label source-based questions and candidate reference answers. They do not label this pilot's chatbot outputs. Their 72 annotations must not be reused as a hallucination denominator or represented as a completed evaluator panel for this experiment.

## Prospective Controlled Experiment

A stronger study needs fresh cases and access to the candidate immediately before source review. Use 36 realistic cases, with three parks, six failure categories, and two cases per park/category: ordinary facts; permission conditions and exceptions; tables and PDFs; plausible absent facts; current or future conditions; and misleading prompts or contextual follow-ups. Keep cross-park factual requests as separately reported scope controls.

Author expected actions, required facts, forbidden contradictions, and exact evidence before observing outputs. Verify PDF interpretation against the original page where extraction may be unreliable. Group paraphrases, shared evidence families, and dialogue turns together so they cannot leak across development and holdout sets. Leave the existing sealed course-test workflow intact. The original gold drafts and adapted candidates remain human-review pending, as required by [the evaluation plan](../../docs/EVALUATION.md).

Capture four stages for each run: raw generation, candidate after deterministic derivation, source-review decisions, and final output after remaining guards. Table derivation can change a draft before review; comparing `raw_response` directly to final output would otherwise misattribute a deterministic correction to the critic. Reuse each actual pre-review candidate in an offline counterfactual where source review is omitted but all other guards remain the same. This is the controlled comparison for the critic's incremental effect. Do not change the public chatbot to collect the counterfactual.

Add a separate synthetic reviewer challenge with 12 pairs of correct and minimally corrupted claims over identical questions and evidence. Mutations should include a swapped table column, a changed number or unit, a removed negation, an omitted permission condition, an unsupported relationship between two source facts, and a stale-to-current guarantee. Have evaluators judge these without knowing which version was planted. Synthetic difficulty estimates detector behavior under these manipulations, not ordinary visitor hallucination frequency. Verify the mutation labels before using them as reference truth.

Freeze code, database, retrieval profile, prompts, schema, and model identity. A cost pilot should precede a fixed number of repetitions; three repetitions per case is a proposed design choice, not an already approved expenditure. Retain every attempt and charged failure, and predefine transient retries. Do not repeat bad semantic answers until one passes. Follow-ups must carry the actual preceding assistant history, and their analysis should account for differences in that history between conditions.

Atomic claim annotation makes mixed-quality responses easier to diagnose. Split a compound claim into factual units for evaluation while preserving its original wording and parent claim ID. Report both atomic support and answer-level errors so changes in claim segmentation do not create an artificial improvement. FActScore provides a methodological precedent for evaluating individual factual assertions against a knowledge source; this pilot's existing application-claim counts are not FActScore measurements. [FActScore](https://aclanthology.org/2023.emnlp-main.741/)

## Metrics and Interpretation

| Metric | Required numerator and denominator |
| --- | --- |
| Unsupported output risk | Requests with at least one unsupported delivered factual unit / all attempted requests; additionally report the same count / substantive answers. |
| Claim grounding error | Unsupported delivered factual units / delivered factual units; report contradictions and qualification omissions separately. |
| Reviewer miss rate | Unsupported reviewed candidates accepted / unsupported reviewed candidates. |
| Reviewer false rejection rate | Supported reviewed candidates rejected / supported reviewed candidates. |
| Over-refusal | Answerable requests refused / all answerable requests; report unnecessary clarification separately. |
| Completeness | Required reference facts correctly delivered / applicable required facts. |
| Appropriate boundary action | Correct scope, live-status, private-record or clarification action / applicable requests, broken down by type. |
| Operational cost | Tokens, observed cost estimates, failures, retries, and latency per attempt, including the extra critic calls. |

Reviewer miss and false-rejection rates are **not available in the completed production pilot**, because the public responses omit rejected drafts. Four withheld claims in the later 21 responses do not establish four false rejections. Empty metric groups are N/A, rather than zero errors.

In the prospective study, use paired results from identical candidates for the critic comparison, randomize evaluation order, and calculate uncertainty at the case or dialogue/source-family level. Repeated runs and individual claims from the same conversation are not independent samples. Report both conservative labels and unresolved cases; do not silently discard disagreements. Freeze the primary metric and acceptable usefulness tradeoff before tuning.

## Practical Recommendations

Preserve complete pre-review candidates in restricted local experiment artifacts so failures can be attributed to generation, derivation, review, or final guards. Keep that internal trace separate from the public visitor experience.

Use the existing frozen sources to test negative table cells, units, exceptions, and combined source relationships. These concrete tests are more diagnostic than asking only obvious factual questions or relying on fictional-location refusals.

Review the two remaining answerable refusals and broad-route incompleteness alongside hallucination risk. A zero unsupported-claim count is not an adequate acceptance criterion if the system avoids answering useful questions.

Complete the independent panel and human adjudication before treating any semantic metric as verified. The next valid claim is a calibrated, reproducible estimate on frozen cases, with its sample limitations; it is not a guarantee of hallucination-free behavior.

## Artifacts and Reproduction

The report bundle contains [frozen inputs](pilot-input.jsonl), [provisional annotations](annotations.jsonl), [mechanical checks](mechanical-checks.jsonl), [aggregate results](summary.json), and [the manifest](manifest.json). The manifest records input hashes, the single-reviewer status, the selection policy, and the blinded packet decoder.

The [offline runner](build_offline_pilot.py) makes no network calls. Its build operation creates new files exclusively. The following verification command reads the existing bundle and reproduces its aggregates without writing files:

```sh
/Users/robin/Build/Personal/parkguide-ai/.venv/bin/python -B /Users/robin/Build/Personal/parkguide-ai/reports/hallucination-experiment-20261010/build_offline_pilot.py --verify
```

Original observations remain in the [baseline run](../../artifacts/user-testing/20261010T164035Z-baseline-c5e32e/turns.jsonl), [later original run](../../artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/turns.jsonl), and [later supplemental run](../../artifacts/user-testing/20261010T191153Z-deployed-1daf0ab-pet-trails-260807/turns.jsonl). These saved runs describe tested historical stages; this pilot did not verify the currently deployed revision.
