# Current candidate diagnostic analysis

Current run: `/Users/robin/Build/Personal/parkguide-ai/artifacts/runs/20261010T040558Z-c2f6c2da`; initial run: `/Users/robin/Build/Personal/parkguide-ai/artifacts/runs/20261010T035053Z-24ef6136`.

Selected B3 is hybrid without reranking; R1 adds reranking to the same current configuration. Human semantic accuracy and citation support remain unknown.

| B3 → R1 metric | Paired n | Before | After | Difference | Paired 95% interval |
| --- | ---: | ---: | ---: | ---: | --- |
| evidence_coverage_5 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| evidence_coverage_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| recall_20 | 8 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] |
| mrr | 8 | 0.854 | 0.781 | -0.073 | [-0.219, +0.042] |
| ndcg_10 | 8 | 0.891 | 0.837 | -0.055 | [-0.163, +0.033] |
| provisional_lexical_pass | 12 | 0.417 | 0.417 | +0.000 | [+0.000, +0.000] |

## Original candidate ceiling

```json
{
  "item_rows": [
    {
      "item_id": "D001",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    },
    {
      "item_id": "D002",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    },
    {
      "item_id": "D003",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    },
    {
      "item_id": "D004",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    },
    {
      "item_id": "D005",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    },
    {
      "item_id": "D006",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    },
    {
      "item_id": "D007",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    },
    {
      "item_id": "D008",
      "original_candidate_count": 20,
      "original_candidate_recall_20": 1.0,
      "post_rerank_recall_20": 1.0,
      "original_source_evidence_coverage_20": 1.0,
      "post_source_evidence_coverage_20": 1.0
    }
  ],
  "denominator": 8,
  "recall_20_provenance": "Saved selected B3 has no reranking and preserves original candidate ordering; its Recall@20 uses the run's full indexed relevance universe. Same candidate membership is validated for R1.",
  "limitation": "Reranking cannot retrieve missing chunks or source spans outside the original candidate pool."
}
```

## Observed paired latency

| Metric (ms) | Paired n | Before mean | After mean | Difference | Paired 95% interval |
| --- | ---: | ---: | ---: | ---: | --- |
| end_to_end_ms | 12 | 1439.4 | 1553.6 | +114.2 | [-14.8, +240.0] |
| generation_ms | 12 | 1144.2 | 1087.1 | -57.1 | [-172.2, +69.9] |
| load_ms | 9 | 141.9 | 109.9 | -32.0 | [-145.8, +55.7] |
| retrieval_ms | 9 | 70.9 | 68.8 | -2.1 | [-39.4, +28.7] |
| rerank_ms | 9 | 0.0 | 339.9 | +339.9 | [+304.6, +364.8] |
| total_ms | 9 | 212.8 | 518.7 | +305.9 | [+193.8, +403.2] |
| end_to_end_retrieval_executed_ms | 9 | 1918.7 | 2071.0 | +152.3 | [-16.7, +302.1] |

## Bundled correction stage

Initial C2 to current selected B3: bundled prompt/history/guard corrections and generation variability; not a causal retrieval comparison

```json
{
  "action_agreement": {
    "paired_item_ids": [
      "D001",
      "D002",
      "D003",
      "D004",
      "D005",
      "D006",
      "D007",
      "D008",
      "D009",
      "D010",
      "D011",
      "D012"
    ],
    "comparison": {
      "before_mean": 0.9166666666666666,
      "after_mean": 1.0,
      "difference": 0.08333333333333333,
      "ci95": [
        0.0,
        0.25
      ],
      "positive_interval": false,
      "negative_interval": false,
      "degenerate": false,
      "paired_denominator": 12,
      "seed": 633,
      "samples": 10000
    },
    "improved_ids": [
      "D012"
    ],
    "worsened_ids": [],
    "error_outcomes_count_as_failures": true
  },
  "provisional_lexical_pass": {
    "paired_item_ids": [
      "D001",
      "D002",
      "D003",
      "D004",
      "D005",
      "D006",
      "D007",
      "D008",
      "D009",
      "D010",
      "D011",
      "D012"
    ],
    "comparison": {
      "before_mean": 0.4166666666666667,
      "after_mean": 0.4166666666666667,
      "difference": 0.0,
      "ci95": [
        -0.25,
        0.25
      ],
      "positive_interval": false,
      "negative_interval": false,
      "degenerate": false,
      "paired_denominator": 12,
      "seed": 633,
      "samples": 10000
    },
    "improved_ids": [
      "D012"
    ],
    "worsened_ids": [
      "D003"
    ],
    "error_outcomes_count_as_failures": true
  }
}
```

Detailed actions, exact exclusions, rerank evidence changes, timings, hashes and control checks are in candidate-analysis.json.

## Limits

- AI-authored diagnostic evidence/actions remain unverified; all semantic quality metrics are unknown.
- Lexical pass measures saved action/fact-word overlap/guard outcomes; paraphrases can fail and false statements can pass.
- Paired percentile intervals use exact item IDs, without multiple-comparison or annotation-uncertainty adjustments.
- All-request latency includes early refusal/clarification. Retrieval-executed latency and stage timings expose their own denominators.
- Timings are observed under cache state, two-query contention and provider variability; they do not establish portable latency or isolate all execution-order effects.
- Current B3 means hybrid without reranking; initial historical B3 meant hybrid with reranking. The initial run is never relabeled or overwritten.
