# ParkGuide AI evaluation plan

**Status: approved implementation design; actual gold verification and final benchmark require human review.** See reports/ and saved artifacts for current measured execution. The local assignment document is the authority: `/Users/robin/Downloads/MSAI633_RAG_Chatbot_Project.docx`. Targets below are PoC acceptance gates, not instructor grading thresholds.

Current configuration uses `gpt-6-luna-2026-09-22` on the same Azure resource as embeddings, per Robin's October 10 decision. Original seven-stage GPT-4 diagnostics are historical. New park-scoped Luna diagnostics are separate operational checks, not a controlled model-quality comparison or human gold benchmark. Future formal B0–B3 must all use the same frozen current model/settings.

## 1. Keep the evaluation small and inspectable

Use JSONL datasets, a plain Python runner, NumPy bootstrap statistics, and pytest for pipeline contracts. Record actual model calls separately from mocked tests. No evaluation platform is required. SciPy/statsmodels are reference implementations, optional only if needed; NumPy is sufficient for the planned paired bootstrap.

[Ragas](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/) offers context and faithfulness metrics, but LLM-based scores add judge calls. [DeepEval](https://deepeval.com/guides/guides-multi-turn-evaluation-metrics) adds conversation metrics. [Promptfoo](https://www.promptfoo.dev/docs/guides/evaluate-rag/) can wrap a Python application for comparison. These are optional adapters; none replaces human gold verification. Start with explicit metric formulas and a review sheet.

## 2. Create and freeze the gold set before chatbot outputs

After source capture, author and save all 40 question drafts from saved pages before any live chatbot answers, including non-gold diagnostics. Freeze the draft hash before generation. AI can draft candidates; a human must verify every gold record against its source. An agent must never set `human_verified`, invent a verifier, or infer verification from silence. Use `draft`, `human_review_pending`, and `human_verified` states. Keep human annotations distinct from AI proposals.

Each record includes an ID, category, question, expected answer/action, required facts, forbidden contradictions, source URLs, source document IDs and hashes, normalized-text evidence spans, and evidence quotes of at most 25 words each. Record searches performed and corpus scope for every unanswerable item. Multi-hop items need evidence from at least two different pages. Temporal items specify the relevant date/effective period and snapshot date. Ambiguous items state the expected clarification or refusal behavior.

Use this exact category-stratified split for 40 items:

| Category | Development | Test | Total |
|---|---:|---:|---:|
| Single-hop factual | 9 | 6 | 15 |
| Multi-hop | 4 | 2 | 6 |
| Comparative | 2 | 2 | 4 |
| Temporal | 2 | 2 | 4 |
| Unanswerable | 5 | 3 | 8 |
| Ambiguous/adversarial | 2 | 1 | 3 |
| **Total** | **24** | **16** | **40** |

Use a saved random seed; group dependent or near-duplicate questions together. Freeze IDs, source hashes, split membership, and dataset hashes before tuning. Exclude test questions from routine agent context. File sealing is an integrity control, not access security. If verification is pending, implement independent contracts and diagnostics, while withholding claims of assignment-valid evaluation.

## 3. Baselines and one-factor changes

Use one generator model/version, settings, output schema, and token limit. B1–B3 share the exact grounded generation prompt and context budget.

| Configuration | Retrieval/chunking | Generation |
|---|---|---|
| B0 | Disabled | Closed-book knowledge; citations N/A |
| B1 | BM25, fixed overlapping chunks | Shared grounded prompt |
| B2 | Dense, same fixed chunks | Shared grounded prompt |
| B3 | Selected structure-aware hybrid; optional measured reranker (currently off) | Shared grounded prompt |

B0 needs a documented instruction to answer from model knowledge. Simply disabling retrieval under a source-only prompt makes it refuse everything and fails to measure prior knowledge. Apart from this necessary grounding difference, keep settings comparable.

Measure B2, then change one factor per experiment: structure-aware chunks, hybrid fusion, cross-encoder reranking, and any conversation-query rewrite. Preserve negative or inconclusive results. Initial fixed chunk settings are 200 tokens with 40-token overlap; these are development settings, not validated choices. Retrieve at least 20 unique candidates, retain a complete reranked order, and send at most five to generation. Record score types and stage latency.

## 4. Relevance survives re-chunking

Gold evidence lives in immutable source-text spans, never only in temporary chunk IDs. Derive chunk relevance labels for each index: a relevant chunk contains sufficient supporting evidence for a required fact. A tiny overlap with the right page is insufficient. Include all supporting alternatives known to the human reviewer; report incompleteness in relevance judgments.

Report standard chunk-level Recall@5/@20, MRR, and nDCG@10 with per-configuration qrels. State that changing chunks changes the relevant-chunk denominator. Also report strategy-independent **evidence coverage@5/@20**: the fraction of required source evidence units fully present in the actual top-k chunk contexts. Overlapping chunks do not earn duplicate credit. Evidence covered only by the combined context can count for coverage but must not be relabeled as individually supported chunk relevance.

Report Recall@20 before reranking, top-five results after reranking, and reranker latency. The actual candidate pool limits what reranking can recover; evidence coverage complements chunk recall when duplicate relevant chunks inflate its denominator. Re-chunk from saved normalized text with network disabled. Verify old IDs are absent, new IDs match expected IDs, and metadata/vector orphan counts are zero.

## 5. Metrics, grading, and artifacts

For every baseline and selected ablation, report retrieval metrics, answer correctness, claim-level citation validity, correct refusal on unanswerables, over-refusal on answerables, p50/p95 latency, and query cost. Score clarification separately. Show numerator/denominator and N/A for empty groups. Also report performance on the B0-incorrect subset, with its exact size.

Correctness uses required facts and contradictions, not answer-string similarity alone. Citation validity checks both source identity and support for the associated claim. A real URL does not prove support. Human grading is the reference; automated/LLM rubric scores remain labeled provisional and require calibration against human-reviewed development outputs. Agents may prepare review sheets and provisional grades. Human review must confirm final semantic scores and the assignment's hand-labeled failures.

Every run saves immutable configuration, corpus/index, prompt, and dataset hashes; timestamps; item IDs; retrieved/reranked IDs and scores; context; answer; citations; refusal/action; stage timing; token usage/cost; errors; grading provenance; and failure tags. Save raw JSONL, aggregate JSON, and generated Markdown tables. Do not drop failed API calls or silently retry bad answers. Record caching/warm-up policy; do not count cached responses as fresh latency measurements. Unknown pricing is unknown, not zero.

## 6. Evaluate real conversations

Add six development-only dialogues with at least three user turns each, beyond the 40-item gold set. Use the real chat path and real model responses; carry actual assistant history into the next turn. Do not substitute canned history. Cover same-park follow-ups; park/date changes; comparisons; ambiguity then clarification; answerable then unanswerable follow-ups; and injection/staleness/high-stakes handling. Use dev sources only.

Save each turn's history, rewritten retrieval query if any, evidence trace, response, and citations. Check context retention, latest constraints, supported facts, refusal, and citation support. Retrieved text remains untrusted; previous generated answers are conversation context, not evidence. [IBM's MTRAG](https://github.com/IBM/mt-rag-benchmark/blob/main/mtrag-human/README.md) provides educational examples of follow-ups, clarification, and answerability; do not copy its questions into the team's gold set.

## 7. Proposed acceptance and bounded iteration

| Gate | Proposed target |
|---|---|
| Required corpus/pipeline contracts | All assignment counts, filters, deterministic IDs, deletion, and migration checks pass |
| Dev evidence coverage@20 / @5 | ≥90% / ≥80% |
| Correctness on 17 clearly answerable dev items | ≥14/17 |
| Correct refusal / over-refusal | 5/5 unanswerables; ≤1/17 answerables |
| Claim citation support | ≥95%; zero invented/unresolvable source IDs |
| Quote and planted-injection safeguards | No quote-limit violations; all explicit injection checks resist instructions |
| Six live dialogues | All complete; ≥90% scored turns pass; no incorrect park/date carryover or unsupported high-stakes advice |
| Reproduction | Every reported table generated from saved actual results |

Run baseline → identify failure → one-factor change → targeted verification → development evaluation → record paired comparison. Complete at least three meaningful measured stages. Continue until gates pass or a genuine dependency/limit remains. Cap at ten full cycles, stop after three consecutive cycles without a new actionable hypothesis or concrete gain, and preserve the best candidate. Passing provisional metrics is not human verification. Limit exhaustion is not completion.

Approved local implementation API spend cap: **$5**, including generation/judging/embedding costs; a future explicit user instruction may change it. Record the independently authorized endpoint smoke separately and include its known cost in total project spend. Missing price information blocks bulk spend. Retry transient timeouts/429/5xx at most twice with backoff; fail immediately on credentials/configuration errors. Never retry semantic failures to cherry-pick a passing answer.

## 8. Final test, uncertainty, and failure analysis

After human verification and development prerequisites, freeze code/configuration/source data/prompts and run B0–B3 once each on the same sealed 16 items in one final batch. Do not tune after inspecting test results. Resume only unfinished calls after an interrupted run, with unchanged hashes and an incident record.

For improvement claims use a paired 95% bootstrap interval on per-item differences, e.g. 10,000 resamples with a recorded seed, or exact McNemar for binary outcomes. [SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) documents paired resampling; [statsmodels](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html) documents exact McNemar. Resample dialogues as clusters, not independent turns. Disclose degenerate intervals. An interval including zero is inconclusive. One item in the 16-item test changes accuracy by 6.25 percentage points; small gains and small B0-incorrect subsets are uncertain.

Have a human label at least 15 real failed outputs from dev baselines/diagnostics: retrieval miss, rank failure, chunk boundary, extraction failure, stale content, reranker demotion, ignored context, invalid citation, over-refusal, or hallucination. Preserve run/item IDs and evidence. If stress diagnostics are needed, label them explicitly; do not fabricate failures or present deliberately weakened runs as final performance. Reports contain actual numbers, reproducible commands, limitations, and AI usage.
