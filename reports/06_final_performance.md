# Performance and remaining final-test work

These are implementation reports. Gold verification, semantic grading, and the final held-out benchmark remain subject to real human review. Diagnostic scores are not assignment-valid gold accuracy.

The sealed final test has not been consumed. No final gold accuracy, human-calibrated semantic citation score, or established course improvement is claimed. Current candidate diagnostic summaries:

```json
{
  "B0": {
    "items": 12,
    "errors": 0,
    "grading_status": "HUMAN_REVIEW_PENDING",
    "recall_5": {
      "mean": null,
      "denominator": 0
    },
    "recall_20": {
      "mean": null,
      "denominator": 0
    },
    "mrr": {
      "mean": null,
      "denominator": 0
    },
    "ndcg_10": {
      "mean": null,
      "denominator": 0
    },
    "evidence_coverage_5": {
      "mean": null,
      "denominator": 0
    },
    "evidence_coverage_20": {
      "mean": null,
      "denominator": 0
    },
    "diagnostic_passes": 3,
    "action_correct": 12,
    "latency_p50_ms": 1038.2,
    "latency_p95_ms": 1982.82,
    "latency_denominator": 12,
    "latency_failure_policy": "Completed responses only; failed requests are counted separately, not assigned zero latency",
    "generation_cost_estimate_usd": 0.004194,
    "generation_cost_denominator": 12,
    "generation_cost_scope": "Successful generation and successful claim-review calls only; excludes query embeddings and failed-call reservations. Whole implementation cost is in the API ledger.",
    "answer_accuracy": null,
    "citation_semantic_support": null
  },
  "B1": {
    "items": 12,
    "errors": 0,
    "grading_status": "HUMAN_REVIEW_PENDING",
    "recall_5": {
      "mean": 1.0,
      "denominator": 8
    },
    "recall_20": {
      "mean": 1.0,
      "denominator": 8
    },
    "mrr": {
      "mean": 0.875,
      "denominator": 8
    },
    "ndcg_10": {
      "mean": 0.9077324383928644,
      "denominator": 8
    },
    "evidence_coverage_5": {
      "mean": 1.0,
      "denominator": 8
    },
    "evidence_coverage_20": {
      "mean": 1.0,
      "denominator": 8
    },
    "diagnostic_passes": 3,
    "action_correct": 11,
    "latency_p50_ms": 2619.1000000000004,
    "latency_p95_ms": 3226.2,
    "latency_denominator": 12,
    "latency_failure_policy": "Completed responses only; failed requests are counted separately, not assigned zero latency",
    "generation_cost_estimate_usd": 0.0193004,
    "generation_cost_denominator": 12,
    "generation_cost_scope": "Successful generation and successful claim-review calls only; excludes query embeddings and failed-call reservations. Whole implementation cost is in the API ledger.",
    "answer_accuracy": null,
    "citation_semantic_support": null
  },
  "B2": {
    "items": 12,
    "errors": 0,
    "grading_status": "HUMAN_REVIEW_PENDING",
    "recall_5": {
      "mean": 1.0,
      "denominator": 8
    },
    "recall_20": {
      "mean": 1.0,
      "denominator": 8
    },
    "mrr": {
      "mean": 0.55,
      "denominator": 8
    },
    "ndcg_10": {
      "mean": 0.6621780785943642,
      "denominator": 8
    },
    "evidence_coverage_5": {
      "mean": 1.0,
      "denominator": 8
    },
    "evidence_coverage_20": {
      "mean": 1.0,
      "denominator": 8
    },
    "diagnostic_passes": 4,
    "action_correct": 12,
    "latency_p50_ms": 2661.7,
    "latency_p95_ms": 3119.22,
    "latency_denominator": 12,
    "latency_failure_policy": "Completed responses only; failed requests are counted separately, not assigned zero latency",
    "generation_cost_estimate_usd": 0.0193356,
    "generation_cost_denominator": 12,
    "generation_cost_scope": "Successful generation and successful claim-review calls only; excludes query embeddings and failed-call reservations. Whole implementation cost is in the API ledger.",
    "answer_accuracy": null,
    "citation_semantic_support": null
  },
  "B3": {
    "items": 12,
    "errors": 0,
    "grading_status": "HUMAN_REVIEW_PENDING",
    "recall_5": {
      "mean": 1.0,
      "denominator": 8
    },
    "recall_20": {
      "mean": 1.0,
      "denominator": 8
    },
    "mrr": {
      "mean": 0.8541666666666666,
      "denominator": 8
    },
    "ndcg_10": {
      "mean": 0.8913662191964322,
      "denominator": 8
    },
    "evidence_coverage_5": {
      "mean": 1.0,
      "denominator": 8
    },
    "evidence_coverage_20": {
      "mean": 1.0,
      "denominator": 8
    },
    "diagnostic_passes": 5,
    "action_correct": 12,
    "latency_p50_ms": 2559.0,
    "latency_p95_ms": 3633.9849999999997,
    "latency_denominator": 12,
    "latency_failure_policy": "Completed responses only; failed requests are counted separately, not assigned zero latency",
    "generation_cost_estimate_usd": 0.01716,
    "generation_cost_denominator": 12,
    "generation_cost_scope": "Successful generation and successful claim-review calls only; excludes query embeddings and failed-call reservations. Whole implementation cost is in the API ledger.",
    "answer_accuracy": null,
    "citation_semantic_support": null
  }
}
```

AI provisional semantic review counts (the linked review retains exact input hashes; not human labels):

```json
{
  "B0": {
    "False": 4,
    "True": 8
  },
  "B1": {
    "False": 1,
    "True": 11
  },
  "B2": {
    "False": 1,
    "True": 11
  },
  "B3": {
    "True": 28,
    "uncertain": 2
  }
}
```

API ledger:

```json
{
  "cap_usd": 5.0,
  "estimated_committed_usd": 0.388879216,
  "remaining_estimated_usd": 4.611120784,
  "events": 708,
  "basis": "published prices and provider token usage; not a billing statement"
}
```

There are 22 actual observed failure instances proposed in failure-review.jsonl, each with an immutable run/item and source evidence when available. Their hand labels require human confirmation; lexical misses are not automatically semantic failures. Actual token-based costs are dated list-price estimates. Run cost fields include successful generation/review only; query embedding and failed-call reservations are included in the whole-implementation ledger rather than attributed per query. Formal B0-incorrect subset reporting awaits human labels. Pairwise intervals from diagnostic observations are separate from final gold inference. See docs/ITERATIONS.md, docs/LATEST_REVIEW.md, and docs/STATUS.md for candidate selection, AI provisional judgments, and remaining failures.
