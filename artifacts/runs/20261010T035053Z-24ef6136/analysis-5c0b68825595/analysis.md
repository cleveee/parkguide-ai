# Paired non-gold diagnostic analysis

Run: `/Users/robin/Build/Personal/parkguide-ai/artifacts/runs/20261010T035053Z-24ef6136`. Items per configuration: 12.

All lexical outcomes are provisional diagnostic signals. Human semantic accuracy and citation support remain unknown.

| Pair | Metric | Paired n | Before | After | Difference | Paired 95% interval |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| B1->B2 | evidence_coverage_5 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| B1->B2 | evidence_coverage_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| B1->B2 | recall_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| B1->B2 | mrr | 8 | 0.875 | 0.550 | -0.325 | [-0.562, -0.100] |
| B1->B2 | ndcg_10 | 8 | 0.908 | 0.662 | -0.246 | [-0.429, -0.077] |
| B1->B2 | provisional_lexical_pass | 12 | 0.333 | 0.250 | -0.083 | [-0.333, +0.167] |
| B2->C1 | evidence_coverage_5 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| B2->C1 | evidence_coverage_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| B2->C1 | recall_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| B2->C1 | mrr | 8 | 0.550 | 0.854 | +0.304 | [+0.083, +0.512] |
| B2->C1 | ndcg_10 | 8 | 0.662 | 0.891 | +0.229 | [+0.060, +0.384] |
| B2->C1 | provisional_lexical_pass | 12 | 0.250 | 0.500 | +0.250 | [+0.000, +0.500] |
| C1->C2 | evidence_coverage_5 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| C1->C2 | evidence_coverage_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| C1->C2 | recall_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| C1->C2 | mrr | 8 | 0.854 | 0.854 | +0.000 | [+0.000, +0.000] |
| C1->C2 | ndcg_10 | 8 | 0.891 | 0.891 | +0.000 | [+0.000, +0.000] |
| C1->C2 | provisional_lexical_pass | 12 | 0.500 | 0.417 | -0.083 | [-0.250, +0.000] |
| C2->B3 | evidence_coverage_5 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| C2->B3 | evidence_coverage_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| C2->B3 | recall_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| C2->B3 | mrr | 8 | 0.854 | 0.781 | -0.073 | [-0.219, +0.042] |
| C2->B3 | ndcg_10 | 8 | 0.891 | 0.837 | -0.055 | [-0.163, +0.033] |
| C2->B3 | provisional_lexical_pass | 12 | 0.417 | 0.417 | +0.000 | [-0.250, +0.250] |

Intervals including zero are inconclusive. A positive or negative interval describes these diagnostic observations only; no human-reviewed course improvement is established.

## Action outcomes

| Variant | Completed/total | Action agreement | False refusals/answerables | Unanswerable refusals | Expected refusals (all reasons) | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 12/12 | 12/12 | 0/8 | 2/2 | 2/2 | 0 |
| B1 | 12/12 | 9/12 | 1/8 | 1/2 | 1/2 | 0 |
| B2 | 12/12 | 8/12 | 2/8 | 1/2 | 1/2 | 0 |
| B3 | 12/12 | 9/12 | 1/8 | 1/2 | 1/2 | 0 |
| C1 | 12/12 | 10/12 | 0/8 | 1/2 | 1/2 | 0 |
| C2 | 12/12 | 11/12 | 0/8 | 2/2 | 2/2 | 0 |

## Same-request reranking

```json
{
  "item_ids": [
    "D001",
    "D002",
    "D003",
    "D004",
    "D005",
    "D006",
    "D007",
    "D008"
  ],
  "same_request_top5_evidence_change": {
    "before_mean": 1.0,
    "after_mean": 1.0,
    "difference": 0.0,
    "ci95": [
      0.0,
      0.0
    ],
    "positive_interval": false,
    "negative_interval": false,
    "degenerate": true,
    "paired_denominator": 8,
    "seed": 633,
    "samples": 10000
  },
  "same_request_pool20_evidence_change": {
    "before_mean": 1.0,
    "after_mean": 1.0,
    "difference": 0.0,
    "ci95": [
      0.0,
      0.0
    ],
    "positive_interval": false,
    "negative_interval": false,
    "degenerate": true,
    "paired_denominator": 8,
    "seed": 633,
    "samples": 10000
  },
  "rerank_latency_ms": {
    "completed_denominator": 12,
    "mean": 283.8125694543123,
    "p50": 263.86112452019006,
    "p95": 381.7538402392529
  },
  "latency_note": "Actual saved local stage timing; may include cold model loading and two-query contention. No extra calls.",
  "candidate_pool_limit": "Reordering cannot recover evidence absent from the original 20-candidate pool."
}
```

B0-incorrect **provisional lexical** subset: 8 completed answerable items. Exact IDs and variant metrics are in analysis.json; this is not a semantic knowledge baseline.

## Limits

- AI-authored diagnostic labels are unverified; semantic answer accuracy/citation support remain unknown.
- Lexical pass is the saved action/fact-word-overlap/guard heuristic, not semantic correctness; paraphrases can fail it.
- Metric intervals resample exact paired item IDs. These exploratory intervals do not adjust for multiple comparisons or annotation uncertainty.
- Chunk-level relevance denominators change after re-chunking; immutable-source evidence coverage complements them.
- Provider errors remain visible; missing numeric metrics are excluded with IDs, while lexical error outcomes count as failures.
- B0 provisional subset uses completed answerable items failing the lexical diagnostic, not demonstrated prior-knowledge errors.
