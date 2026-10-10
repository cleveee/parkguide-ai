# Paired diagnostic analysis

`scripts/analyze_diagnostics.py` reads a **completed non-gold diagnostic** run and its matching diagnostic definitions. It makes no embedding, generation, crawling, or model calls. It rejects other run kinds, unmarked diagnostic datasets, changed dataset hashes, duplicate item results, missing configurations/items, changed expected actions, mismatched recorded retrieval modes/builds, and different generator models across completed RAG variants. Recorded configuration checks cannot establish that two unrecorded prompt templates or corpus snapshots were identical; those snapshots still require review.

```sh
.venv/bin/python scripts/analyze_diagnostics.py --self-test
.venv/bin/python scripts/analyze_diagnostics.py artifacts/runs/20261010T035053Z-24ef6136
```

The default definitions are `data/evaluation/diagnostic.jsonl`; `--dataset` can select another explicitly diagnostic file matching the run hash. Output goes into a new content-addressed analysis subfolder of that run. The script never rewrites the original results, summary, manifest, gold records, or root reports. Identical analysis can be read again; different existing content is rejected rather than overwritten.

## What each comparison changes

| Pair | Intended factor |
| --- | --- |
| B1 → B2 | BM25 representation/scoring → dense embeddings, with fixed chunks |
| B2 → C1 | Fixed → structure-aware chunking, retaining dense retrieval |
| C1 → C2 | Dense → hybrid rank fusion |
| C2 → B3 | Add CrossEncoder reranking to the same structure/hybrid setup |

B1 → B2 tests keyword versus dense retrieval; it is not an embedding-model training experiment. These initial controlled outputs stay separate from later prompt, guard, or history corrections. Model and prompt changes must be reported as additional stages, not silently folded into the earlier comparison.

## Pairing, units, and uncertainty

For every pair, the script matches **exact item IDs** and resamples their per-item differences with a recorded seed and 10,000 bootstrap draws. It reports before/after means, mean difference, a paired 95% interval, denominator, item IDs, excluded IDs, and degenerate intervals. Metrics are evidence coverage@5/@20, chunk Recall@20, MRR, nDCG@10, and the saved provisional lexical-pass indicator.

Numeric metrics absent because of non-answerable items or errors are omitted only with explicit excluded IDs. Lexical-pass provider errors count as failed pipeline outcomes. Chunk relevance denominators change after re-chunking; frozen source-evidence coverage provides a complementary unit. These are exploratory intervals on a small AI-authored diagnostic set, without adjustment for multiple comparisons, uncertain source labels, or judge errors. An interval including zero is inconclusive.

The lexical diagnostic measures saved expected-action agreement, required-word overlap, and guard outcomes. It does not establish fact correctness, contradictions, or semantic citation support. Paraphrases can fail its overlap rule. **Human answer accuracy and semantic citation validity remain unknown**, regardless of its interval.

## Reranking and refusals

Within each B3 request, compare the original candidate ordering with the complete post-rerank ordering. Check that candidate membership is unchanged, then compute source-evidence coverage in the first five passages before and after reranking. Also compare evidence coverage over the same 20-passage pool; reranking cannot recover absent evidence. Report the saved rerank-stage mean/p50/p95 latency and count. Cold model loading, contention, and cache state remain part of the observed policy; these timings are not new requests.

Action tables show completed/total items, agreement, errors, false refusals on expected-answer items, and expected refusals. Genuine unanswerable refusal is restricted to `category=unanswerable`; safety/adversarial expected refusals are separate. Every rate shows its numerator and completed denominator plus total eligible counts in JSON. No absent group is reported as zero performance.

The B0-incorrect **provisional** subset contains completed expected-answer items failing B0's lexical diagnostic. Failed provider requests are listed separately; refusal/injection expectations do not measure prior knowledge. Exact subset IDs and per-configuration metrics are saved. This remains a diagnostic proxy until a human reviews semantic correctness.

## Initial observed run

The completed run `20261010T035053Z-24ef6136` contains 72 responses: six variants over the same 12 diagnostic items, without provider errors. Eight items carry source evidence; two expect refusal and two expect clarification. All labels remain AI-authored and unverified. Results were analyzed with seed 633 and 10,000 paired bootstrap draws.

| Controlled change | MRR before → after | MRR difference and paired 95% interval | nDCG@10 difference and paired 95% interval |
| --- | ---: | --- | --- |
| B1 → B2, BM25 → dense | 0.875 → 0.550 | −0.325 [−0.563, −0.100] | −0.246 [−0.429, −0.077] |
| B2 → C1, fixed → structure | 0.550 → 0.854 | +0.304 [+0.083, +0.513] | +0.229 [+0.060, +0.384] |
| C1 → C2, dense → hybrid | 0.854 → 0.854 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| C2 → B3, add reranking | 0.854 → 0.781 | −0.073 [−0.219, +0.042] | −0.055 [−0.163, +0.033] |

Source-evidence coverage@5/@20 and chunk Recall@20 were 1.0 for all five retrieval variants on these eight evidence-bearing items. Their zero-difference intervals are degenerate because every observed item is already at the ceiling; they do not establish perfect retrieval on new questions. Structure-aware dense retrieval improved these diagnostic rank metrics relative to fixed dense chunks. Hybrid fusion showed no additional rank change. Reranking showed no evidence-coverage lift, and its observed MRR decrease has an interval that includes zero. This run provides no basis for assuming reranking improves this corpus.

Within B3, all original 20-candidate memberships were preserved after reranking. Evidence coverage in the top five stayed 1.0 before and after for all eight relevant items. Saved rerank-stage timing across 12 requests was mean 284 ms, p50 264 ms, and p95 382 ms under the recorded two-query concurrency/cache policy.

| Variant | Action agreement | False refusals on answerables | Refusals on unanswerables | Provisional lexical passes |
| --- | ---: | ---: | ---: | ---: |
| B0 | 12/12 | 0/8 | 2/2 | 2/12 |
| B1 | 9/12 | 1/8 | 1/2 | 4/12 |
| B2 | 8/12 | 2/8 | 1/2 | 3/12 |
| C1 | 10/12 | 0/8 | 1/2 | 6/12 |
| C2 | 11/12 | 0/8 | 2/2 | 5/12 |
| B3 | 9/12 | 1/8 | 1/2 | 5/12 |

All eight completed answerable B0 responses failed the lexical diagnostic. They form the saved provisional subset; this does not show eight factual knowledge errors. Lexical passes miss paraphrases, and their pairwise intervals do not establish an improvement. For example, the B2 → C1 lexical change is +0.250 with interval [0.000, +0.500], while C2 → B3 is 0.000 with [−0.250, +0.250]. Human semantic correctness and citation support remain unknown. Later prompt/history/guard fixes must retain these initial observations as a separate stage.
