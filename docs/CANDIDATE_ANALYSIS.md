# Selected candidate diagnostic analysis

The current candidate **B3 uses structure-aware hybrid retrieval without reranking**. R1 adds the pinned CrossEncoder reranker as a controlled alternative. The initial run's historical B3 label referred to hybrid with reranking; its results and labels remain unchanged. A label does not determine the actual configuration: inspect the run manifest.

`scripts/analyze_candidate.py` reads completed non-gold diagnostic artifacts only. It makes no provider, embedding, crawling, or model calls, and does not access gold or final-test outputs. By default, it resolves `artifacts/latest-diagnostic.json` and `artifacts/initial-diagnostic.json`; explicit paths make a later analysis reproducible.

```sh
.venv/bin/python scripts/analyze_candidate.py --self-test
.venv/bin/python scripts/analyze_candidate.py \
  artifacts/runs/20261010T040558Z-c2f6c2da \
  --initial artifacts/runs/20261010T035053Z-24ef6136
```

The script waits for neither credentials nor new requests: it rejects an incomplete run. It validates matching diagnostic dataset hashes, exact item IDs, expected actions, no duplicate item/configuration results, shared current hybrid build, B3 rerank=false, R1 rerank=true, and one recorded generator model across provider responses. It checks paired questions, history, retrieval query, filters, and original candidate order/content/source metadata. R1 must retain every candidate and its evidence metadata. Local preflight outcomes with no generator call are recorded separately.

Derived JSON and Markdown go into a new ignored, content-addressed `candidate-analysis-*` subfolder of the current run. The identity includes both original result files, manifests, dataset, seed, bootstrap count, script and helper hashes. Existing differing output is rejected; original run artifacts and previous analyses are never rewritten.

## Controlled current comparison

Run `20261010T040558Z-c2f6c2da` contains 24 completed responses: B3 and R1 over the same 12 diagnostic items, without provider errors. Both use recorded configuration hash `8cbad7c3bf6186b0ef36789ed9c49ad0171cbd5288c2490e33317b7ee1efd51f` and code hash `d24aa6b766b9c89fef57abc5f61038182296f7d0d786017424db9266a0476f94`. Nine items execute retrieval/generation; D010–D012 receive local refusal/clarification. Eight items carry source evidence.

| B3 → R1 outcome | Before → after | Difference and paired 95% interval | Paired n |
| --- | ---: | --- | ---: |
| Source-evidence coverage@5 | 1.000 → 1.000 | 0.000 [0.000, 0.000] | 8 |
| Original/post-rerank chunk Recall@20 | 1.000 → 1.000 | 0.000 [0.000, 0.000] | 8 |
| MRR | 0.854 → 0.781 | −0.073 [−0.219, +0.042] | 8 |
| nDCG@10 | 0.891 → 0.837 | −0.055 [−0.163, +0.033] | 8 |
| Action agreement | 12/12 → 12/12 | 0.000 [0.000, 0.000] | 12 |
| Provisional lexical pass | 5/12 → 5/12 | 0.000 [0.000, 0.000] | 12 |

For all eight evidence-bearing questions, the original pool contains 20 candidates and achieves source-evidence coverage@20 and saved full-universe Recall@20 of 1.0. Reordering the same pool cannot improve that ceiling. Evidence coverage within its top five also stays 1.0. Zero-difference intervals at this ceiling are degenerate observations on this small set, not proof of perfect retrieval on new questions. Reranking shows no measured evidence or lexical benefit. Its lower mean rank metrics have intervals including zero, so the observed decreases are inconclusive.

Both variants answer all eight expected-answer questions, refuse both unanswerables, clarify both ambiguous questions, and have zero false refusals (0/8). These action outcomes follow unverified diagnostic labels. The lexical indicator checks saved action/fact-word overlap/guards; it is **not semantic answer accuracy**. Paraphrases can fail and unsupported content can pass. Human semantic correctness and citation support remain unknown.

## Observed latency

| Saved timing | B3 mean → R1 mean | Difference and paired 95% interval | Paired n |
| --- | ---: | --- | ---: |
| Rerank stage | 0 → 340 ms | +340 [+305, +365] ms | 9 |
| Local retrieval total, including load/rerank | 213 → 519 ms | +306 [+194, +403] ms | 9 |
| End-to-end, every diagnostic request | 1,439 → 1,554 ms | +114 [−15, +240] ms | 12 |
| End-to-end, retrieval executed | 1,919 → 2,071 ms | +152 [−17, +302] ms | 9 |

R1's rerank-stage p50 is 353 ms and p95 382 ms across nine actual stage timings. All-request end-to-end p50/p95 are 1,589/2,905 ms for B3 and 1,890/2,788 ms for R1. Including three near-zero preflight outcomes changes the denominator, so the script also exposes retrieval-executed timing separately. These are recorded observations under two concurrent queries, retained cache state, execution-order effects and provider variability. They do not establish portable production latency. The end-to-end difference includes zero even though the measured local rerank cost is positive.

## Bundled correction comparison

The comparison from initial C2 to current B3 measures a later stage containing prompt, history and guard corrections plus generation variability. It cannot attribute an outcome to one change or claim a causal retrieval improvement. The script deliberately compares only action agreement and lexical-pass outcomes here.

Action agreement changes from 11/12 to 12/12: +0.083 with paired interval [0.000, +0.250], driven by D012. Lexical passes remain 5/12: difference 0.000 with [−0.250, +0.250]; D012 improves while D003 worsens under the lexical proxy. Neither interval establishes a human-reviewed quality improvement. The current run's B3/R1 comparison supplies the controlled reranking evidence; the earlier run stays intact.

All intervals resample exact paired item differences with seed 633 and 10,000 draws. They are exploratory percentile intervals without adjustments for multiple comparisons or source-label uncertainty. Missing numeric metrics and failed pipeline outcomes retain explicit exclusions and denominators. This analysis supports keeping reranking optional; it does not satisfy the separate human gold review or sealed final-test requirements.
